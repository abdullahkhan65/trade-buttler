"""
Backtester: Simulates the strategy on historical OHLCV data.
For each candle, generates a signal and checks if TP/SL was hit forward.
"""
import pandas as pd
import numpy as np
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from strategy import calculate_ema, calculate_rsi, calculate_atr
from data_fetcher import fetch_candles

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    symbol: str
    direction: str
    entry_idx: int
    entry_price: float
    stop_loss: float
    take_profit: float
    score: int
    signal_type: str
    reasons: List[str]
    outcome: Optional[str] = None   # 'win' / 'loss' / 'open'
    exit_price: Optional[float] = None
    exit_idx: Optional[int] = None
    bars_held: Optional[int] = None
    pnl_r: Optional[float] = None   # profit in R (risk units)


@dataclass
class BacktestResult:
    symbol: str
    interval: str
    params: Dict[str, Any]
    trades: List[BacktestTrade] = field(default_factory=list)

    @property
    def total(self): return len(self.trades)

    @property
    def closed(self): return [t for t in self.trades if t.outcome in ('win', 'loss')]

    @property
    def wins(self): return [t for t in self.closed if t.outcome == 'win']

    @property
    def losses(self): return [t for t in self.closed if t.outcome == 'loss']

    @property
    def win_rate(self):
        c = self.closed
        return (len(self.wins) / len(c) * 100) if c else 0.0

    @property
    def profit_factor(self):
        gross_win = sum(abs(t.pnl_r or 0) for t in self.wins)
        gross_loss = sum(abs(t.pnl_r or 0) for t in self.losses)
        return gross_win / gross_loss if gross_loss > 0 else gross_win

    @property
    def avg_r(self):
        closed = self.closed
        if not closed: return 0.0
        return sum(t.pnl_r or 0 for t in closed) / len(closed)

    @property
    def max_drawdown(self):
        if not self.closed: return 0.0
        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        for t in self.closed:
            equity += (t.pnl_r or 0)
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @property
    def sharpe(self):
        pnls = [t.pnl_r or 0 for t in self.closed]
        if len(pnls) < 2: return 0.0
        mean = np.mean(pnls)
        std = np.std(pnls)
        return (mean / std * np.sqrt(len(pnls))) if std > 0 else 0.0

    @property
    def equity_curve(self):
        curve = []
        equity = 0.0
        for t in self.closed:
            equity += (t.pnl_r or 0)
            curve.append(round(equity, 4))
        return curve

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "interval": self.interval,
            "params": self.params,
            "total_trades": self.total,
            "closed_trades": len(self.closed),
            "wins": len(self.wins),
            "losses": len(self.losses),
            "win_rate": round(self.win_rate, 2),
            "profit_factor": round(self.profit_factor, 2),
            "avg_r": round(self.avg_r, 3),
            "max_drawdown_r": round(self.max_drawdown, 3),
            "sharpe": round(self.sharpe, 3),
            "equity_curve": self.equity_curve,
            "trades": [
                {
                    "direction": t.direction,
                    "entry_price": t.entry_price,
                    "stop_loss": t.stop_loss,
                    "take_profit": t.take_profit,
                    "score": t.score,
                    "signal_type": t.signal_type,
                    "outcome": t.outcome,
                    "exit_price": t.exit_price,
                    "bars_held": t.bars_held,
                    "pnl_r": round(t.pnl_r, 3) if t.pnl_r is not None else None,
                    "reasons": t.reasons,
                }
                for t in self.trades
            ]
        }


def _score_candle(df_slice, symbol, params):
    """Score a single candle slice with given params. Returns signal dict or None."""
    close = df_slice['close']
    high = df_slice['high']
    low = df_slice['low']

    ema20 = calculate_ema(close, 20)
    ema50 = calculate_ema(close, 50)
    ema200 = calculate_ema(close, 200)
    rsi = calculate_rsi(close, 14)
    atr = calculate_atr(high, low, close, 14)

    curr_close = close.iloc[-1]
    curr_ema20 = ema20.iloc[-1]
    curr_ema50 = ema50.iloc[-1]
    curr_ema200 = ema200.iloc[-1]
    curr_rsi = rsi.iloc[-1]
    curr_atr = atr.iloc[-1]
    prev_rsi = rsi.iloc[-2] if len(rsi) > 1 else curr_rsi

    if pd.isna(curr_atr) or curr_atr == 0:
        return None

    score = 0
    reasons = []
    bullish_bias = curr_ema20 > curr_ema50
    direction = "BUY" if bullish_bias else "SELL"

    # 1. EMA trend alignment
    if bullish_bias:
        score += 2
        reasons.append("EMA20 > EMA50 (bullish trend)")
    else:
        score += 2
        reasons.append("EMA20 < EMA50 (bearish trend)")

    # 2. EMA200 position
    if bullish_bias and curr_close > curr_ema200:
        score += 1
        reasons.append("Price above EMA200")
    elif not bullish_bias and curr_close < curr_ema200:
        score += 1
        reasons.append("Price below EMA200")

    # 3. Fresh crossover
    crossover_found = False
    for i in range(-4, -1):
        try:
            p20, p50 = ema20.iloc[i], ema50.iloc[i]
            n20, n50 = ema20.iloc[i+1], ema50.iloc[i+1]
            if bullish_bias and p20 <= p50 and n20 > n50:
                crossover_found = True
                break
            elif not bullish_bias and p20 >= p50 and n20 < n50:
                crossover_found = True
                break
        except IndexError:
            pass
    if crossover_found:
        score += 2
        reasons.append("Fresh EMA20/50 crossover")

    # 4. RSI zone
    rsi_buy_low = params.get('rsi_buy_low', 40)
    rsi_buy_high = params.get('rsi_buy_high', 65)
    rsi_sell_low = params.get('rsi_sell_low', 35)
    rsi_sell_high = params.get('rsi_sell_high', 60)

    if direction == "BUY" and rsi_buy_low <= curr_rsi <= rsi_buy_high:
        score += 2
        reasons.append(f"RSI {curr_rsi:.1f} in BUY zone")
    elif direction == "SELL" and rsi_sell_low <= curr_rsi <= rsi_sell_high:
        score += 2
        reasons.append(f"RSI {curr_rsi:.1f} in SELL zone")

    # 5. RSI direction
    if direction == "BUY" and curr_rsi > prev_rsi:
        score += 1
        reasons.append("RSI rising")
    elif direction == "SELL" and curr_rsi < prev_rsi:
        score += 1
        reasons.append("RSI falling")

    # 6. EMA20 bounce
    prev_close = close.iloc[-2]
    prev_ema20 = ema20.iloc[-2]
    if direction == "BUY" and prev_close <= prev_ema20 and curr_close > curr_ema20:
        score += 1
        reasons.append("Bounced off EMA20")
    elif direction == "SELL" and prev_close >= prev_ema20 and curr_close < curr_ema20:
        score += 1
        reasons.append("Rejected at EMA20")

    min_forming = params.get('min_score_forming', 5)
    min_confirmed = params.get('min_score_confirmed', 7)

    if score < min_forming:
        return None

    signal_type = "confirmed" if score >= min_confirmed else "forming"

    sl_mult = params.get('atr_sl_mult', 1.5)
    tp_mult = params.get('atr_tp_mult', 3.0)

    if direction == "BUY":
        sl = curr_close - curr_atr * sl_mult
        tp = curr_close + curr_atr * tp_mult
    else:
        sl = curr_close + curr_atr * sl_mult
        tp = curr_close - curr_atr * tp_mult

    return {
        "direction": direction,
        "signal_type": signal_type,
        "score": score,
        "entry_price": curr_close,
        "stop_loss": sl,
        "take_profit": tp,
        "atr": curr_atr,
        "reasons": reasons,
    }


def run_backtest(symbol: str, interval: str = "1h", params: dict = None, limit: int = 500) -> BacktestResult:
    """Run a full backtest on historical data."""
    if params is None:
        params = {
            "rsi_buy_low": 40, "rsi_buy_high": 65,
            "rsi_sell_low": 35, "rsi_sell_high": 60,
            "min_score_forming": 5, "min_score_confirmed": 7,
            "atr_sl_mult": 1.5, "atr_tp_mult": 3.0,
        }

    result = BacktestResult(symbol=symbol, interval=interval, params=params)

    df = fetch_candles(symbol, interval=interval, limit=limit)
    if df is None or len(df) < 220:
        logger.warning(f"Not enough data for backtest: {symbol}")
        return result

    df = df.reset_index(drop=True)
    min_idx = 210  # need at least 210 candles for EMA200
    max_forward_bars = 100  # max bars to look forward for TP/SL

    in_trade = False
    last_signal_idx = -20  # prevent re-entry too soon

    for i in range(min_idx, len(df) - 1):
        if in_trade:
            continue  # one trade at a time
        if (i - last_signal_idx) < 5:
            continue  # cooldown between signals

        df_slice = df.iloc[:i+1].copy()
        sig = _score_candle(df_slice, symbol, params)
        if sig is None:
            continue

        # Simulate forward to find TP or SL hit
        entry = sig['entry_price']
        sl = sig['stop_loss']
        tp = sig['take_profit']
        direction = sig['direction']

        outcome = "open"
        exit_price = None
        exit_idx = None

        forward_end = min(i + 1 + max_forward_bars, len(df))
        for j in range(i + 1, forward_end):
            candle_high = df.iloc[j]['high']
            candle_low = df.iloc[j]['low']

            if direction == "BUY":
                if candle_low <= sl:
                    outcome = "loss"
                    exit_price = sl
                    exit_idx = j
                    break
                if candle_high >= tp:
                    outcome = "win"
                    exit_price = tp
                    exit_idx = j
                    break
            else:  # SELL
                if candle_high >= sl:
                    outcome = "loss"
                    exit_price = sl
                    exit_idx = j
                    break
                if candle_low <= tp:
                    outcome = "win"
                    exit_price = tp
                    exit_idx = j
                    break

        risk = abs(entry - sl)
        if outcome == "win":
            pnl_r = abs(tp - entry) / risk if risk > 0 else 0
        elif outcome == "loss":
            pnl_r = -1.0
        else:
            pnl_r = None

        trade = BacktestTrade(
            symbol=symbol,
            direction=direction,
            entry_idx=i,
            entry_price=round(entry, 4),
            stop_loss=round(sl, 4),
            take_profit=round(tp, 4),
            score=sig['score'],
            signal_type=sig['signal_type'],
            reasons=sig['reasons'],
            outcome=outcome,
            exit_price=round(exit_price, 4) if exit_price else None,
            exit_idx=exit_idx,
            bars_held=(exit_idx - i) if exit_idx else None,
            pnl_r=round(pnl_r, 4) if pnl_r is not None else None,
        )
        result.trades.append(trade)

        if outcome != "open":
            last_signal_idx = exit_idx or i
        else:
            last_signal_idx = i

        # Allow next trade after exit
        in_trade = False

    logger.info(
        f"Backtest {symbol} {interval}: {result.total} trades, "
        f"WR={result.win_rate:.1f}%, PF={result.profit_factor:.2f}, "
        f"Sharpe={result.sharpe:.2f}"
    )
    return result
