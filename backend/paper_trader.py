"""
Autonomous Paper Trading Engine
================================
Single $500 master account. All 5 strategies compete for up to 2 trade slots/day.

Daily rules:
  - Target:      +3% (+$15 on $500)  → stop new trades for the day
  - Risk limit:  -5% (-$25 on $500)  → stop new trades for the day
  - Max trades:  2 per day total

Position sizing (XAU/USD):
  lot_size = balance / 100  →  0.05 lots  →  5 oz
  TP = $3/oz from entry     →  +$15 per win
  SL = $2/oz from entry     →  -$10 per loss

Smart invalidation: every 5 min, re-run signal analysis on open trades.
If direction flips or score collapses, close early at market price.
"""
import json
import logging
from datetime import datetime, date
from sqlalchemy import and_
from database import SessionLocal
from models import PaperTrade, PaperPortfolio
from data_fetcher import fetch_candles
from strategy import analyze_signal
from config import SYMBOLS

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

PORTFOLIO_ID     = "master"
INITIAL_BALANCE  = 500.0
DAILY_TARGET_PCT = 3.0    # stop new entries at +3%
DAILY_RISK_PCT   = 5.0    # stop new entries at -5%
MAX_DAILY_TRADES = 2      # hard cap on trades per day

# Per-instrument: contract size (units per lot), fixed TP/SL distances in price
INSTRUMENT_CONFIG = {
    "XAU/USD":   {"contract_size": 100, "tp_distance": 3.00, "sl_distance": 2.00},
    "PAXG/USDT": {"contract_size": 1,   "tp_distance": 3.00, "sl_distance": 2.00},
    "BTC/USD":   {"contract_size": 1,   "tp_distance": 200.0, "sl_distance": 100.0},
    "BTC/USDT":  {"contract_size": 1,   "tp_distance": 200.0, "sl_distance": 100.0},
}

# Smart invalidation: re-check open trades every N seconds (5 min)
INVALIDATION_INTERVAL = 300
_invalidation_cache: dict = {}   # trade_id → last datetime checked

# ── Strategy definitions (still used for scanning & analytics) ────────────────

STRATEGIES = {
    "1h_baseline": {
        "label": "1H Baseline",
        "timeframe": "1h",
        "analyzer": "analyze_signal",
        "symbols": None,
        "params": {
            "min_score_forming": 6, "min_score_confirmed": 8,
            "rsi_buy_low": 45,  "rsi_buy_high": 62,
            "rsi_sell_low": 38, "rsi_sell_high": 55,
            "atr_sl_mult": 1.5, "atr_tp_mult": 3.0,
        },
    },
    "4h_conservative": {
        "label": "4H Conservative",
        "timeframe": "4h",
        "analyzer": "analyze_signal",
        "symbols": None,
        "params": {
            "min_score_forming": 7, "min_score_confirmed": 8,
            "rsi_buy_low": 46,  "rsi_buy_high": 60,
            "rsi_sell_low": 40, "rsi_sell_high": 54,
            "atr_sl_mult": 1.8, "atr_tp_mult": 3.5,
        },
    },
    "15m_aggressive": {
        "label": "15M Aggressive",
        "timeframe": "15m",
        "analyzer": "analyze_signal",
        "symbols": None,
        "params": {
            "min_score_forming": 5, "min_score_confirmed": 7,
            "rsi_buy_low": 42,  "rsi_buy_high": 65,
            "rsi_sell_low": 35, "rsi_sell_high": 58,
            "atr_sl_mult": 1.2, "atr_tp_mult": 2.5,
        },
    },
    "xau_fibonacci": {
        "label": "XAU Fibonacci",
        "timeframe": "1h",
        "analyzer": "analyze_fibonacci",
        "symbols": ["XAU/USD"],
        "params": {
            "min_score_forming": 5, "min_score_confirmed": 7,
            "atr_sl_mult": 1.5, "atr_tp_mult": 3.5,
        },
    },
    "xau_structure": {
        "label": "XAU Smart Money",
        "timeframe": "1h",
        "analyzer": "analyze_orderblock_liquidity",
        "symbols": ["XAU/USD"],
        "params": {
            "min_score_forming": 5, "min_score_confirmed": 7,
            "atr_sl_mult": 1.2, "atr_tp_mult": 3.0,
        },
    },
}

# ── Bootstrap ─────────────────────────────────────────────────────────────────

def ensure_portfolios():
    """Create the single master portfolio on first run."""
    db = SessionLocal()
    try:
        if not db.query(PaperPortfolio).filter(PaperPortfolio.strategy_id == PORTFOLIO_ID).first():
            db.add(PaperPortfolio(
                strategy_id=PORTFOLIO_ID,
                label="Trade Buttler",
                timeframe="multi",
                balance=INITIAL_BALANCE,
                initial_balance=INITIAL_BALANCE,
                peak_balance=INITIAL_BALANCE,
                day_start_balance=INITIAL_BALANCE,
                last_day_reset=date.today().isoformat(),
                daily_trades=0,
                daily_profit_target_pct=DAILY_TARGET_PCT,
                daily_risk_limit_pct=DAILY_RISK_PCT,
            ))
            db.commit()
    finally:
        db.close()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_portfolio(db):
    return db.query(PaperPortfolio).filter(PaperPortfolio.strategy_id == PORTFOLIO_ID).first()


def _check_and_reset_daily(portfolio):
    """Reset daily counters at the start of each new calendar day."""
    today = date.today().isoformat()
    if portfolio.last_day_reset != today:
        portfolio.day_start_balance = portfolio.balance
        portfolio.last_day_reset = today
        portfolio.daily_trades = 0


def _daily_status(portfolio):
    """Returns (can_trade, reason, daily_pnl, daily_pnl_pct)."""
    day_start    = portfolio.day_start_balance or portfolio.balance
    daily_pnl    = portfolio.balance - day_start
    daily_pnl_pct = (daily_pnl / day_start * 100) if day_start > 0 else 0
    daily_trades = portfolio.daily_trades or 0

    if daily_pnl_pct >= DAILY_TARGET_PCT:
        return False, "daily_target_reached", daily_pnl, daily_pnl_pct
    if daily_pnl_pct <= -DAILY_RISK_PCT:
        return False, "daily_risk_limit_hit", daily_pnl, daily_pnl_pct
    if daily_trades >= MAX_DAILY_TRADES:
        return False, "max_trades_reached", daily_pnl, daily_pnl_pct
    return True, "active", daily_pnl, daily_pnl_pct


def _has_any_open_trade(db):
    """Returns True if any trade is currently open (one at a time policy)."""
    return db.query(PaperTrade).filter(PaperTrade.status == "open").first() is not None


def _build_analysis(trade):
    """Brief post-trade note."""
    tp_dist   = abs(trade.take_profit - trade.entry_price)
    exit_dist = abs((trade.exit_price or trade.entry_price) - trade.entry_price)
    pct_tp    = (exit_dist / tp_dist * 100) if tp_dist > 0 else 0
    if trade.result == "win":
        rr = tp_dist / abs(trade.stop_loss - trade.entry_price) if trade.stop_loss != trade.entry_price else 0
        return f"TP hit @ ${trade.exit_price:,.2f} ({rr:.1f}R) | +${trade.pnl_usd:.2f}"
    elif trade.result == "invalidated":
        return f"Early close @ ${trade.exit_price:,.2f} — signal conditions changed | {trade.pnl_usd:+.2f}"
    else:
        return f"SL hit @ ${trade.exit_price:,.2f} — {pct_tp:.0f}% toward TP | ${trade.pnl_usd:.2f}"


def _should_invalidate(trade):
    """
    Re-run the signal analyzer every 5 min. Returns (should_close, reason).
    Closes early if: direction flipped OR score collapsed.
    """
    now  = datetime.now()
    last = _invalidation_cache.get(trade.id)
    if last and (now - last).total_seconds() < INVALIDATION_INTERVAL:
        return False, None
    _invalidation_cache[trade.id] = now

    try:
        from strategy import analyze_fibonacci, analyze_orderblock_liquidity
        _analyzers = {
            "analyze_signal":               analyze_signal,
            "analyze_fibonacci":            analyze_fibonacci,
            "analyze_orderblock_liquidity": analyze_orderblock_liquidity,
        }
        cfg = STRATEGIES.get(trade.strategy_id)
        if not cfg:
            return False, None

        df = fetch_candles(trade.symbol, cfg["timeframe"], limit=100)
        if df is None:
            return False, None

        fn     = _analyzers.get(cfg.get("analyzer", "analyze_signal"), analyze_signal)
        result = fn(df, trade.symbol, cfg["params"])

        if result is None:
            return True, "signal_disappeared"
        if result.get("direction") != trade.direction and result.get("score", 0) >= 5:
            return True, "direction_flipped"
        if result.get("score", 10) < 3:
            return True, "signal_score_collapsed"

    except Exception as e:
        logger.debug(f"[Paper] invalidation check error for #{trade.id}: {e}")

    return False, None


# ── Core actions ──────────────────────────────────────────────────────────────

def try_enter_trade(strategy_id, symbol, signal_data, broadcast_fn=None):
    """
    Attempt to open a paper trade on the master portfolio.
    Enforces: confirmed signal, daily limits, one-at-a-time.
    """
    if signal_data.get("signal_type") != "confirmed":
        return False

    db = SessionLocal()
    try:
        portfolio = _get_portfolio(db)
        if not portfolio or portfolio.balance <= 1.0:
            return False

        _check_and_reset_daily(portfolio)
        can_trade, reason, _, _ = _daily_status(portfolio)
        if not can_trade:
            logger.info(f"[Paper] SKIP {strategy_id}/{symbol} — {reason}")
            db.commit()
            return False

        if _has_any_open_trade(db):
            return False

        entry = signal_data["entry_price"]
        icfg  = INSTRUMENT_CONFIG.get(symbol, {})
        contract_size = icfg.get("contract_size", 1)
        tp_dist = icfg.get("tp_distance")
        sl_dist = icfg.get("sl_distance")

        # Use instrument-specific tight TP/SL, fallback to strategy values
        if tp_dist and sl_dist:
            if signal_data["direction"] == "BUY":
                tp = round(entry + tp_dist, 2)
                sl = round(entry - sl_dist, 2)
            else:
                tp = round(entry - tp_dist, 2)
                sl = round(entry + sl_dist, 2)
        else:
            sl = signal_data["stop_loss"]
            tp = signal_data["take_profit"]
            sl_dist = abs(entry - sl)

        lot_size = round(portfolio.balance / 100.0, 2)
        units    = round(lot_size * contract_size, 6)
        risk_usd = round(units * abs(entry - sl), 4)

        cfg = STRATEGIES.get(strategy_id, STRATEGIES["1h_baseline"])
        trade = PaperTrade(
            strategy_id=strategy_id,
            symbol=symbol,
            timeframe=cfg["timeframe"],
            direction=signal_data["direction"],
            entry_price=entry,
            stop_loss=sl,
            take_profit=tp,
            lot_size=lot_size,
            units=units,
            risk_usd=risk_usd,
            score=signal_data["score"],
            reasons=json.dumps(signal_data.get("reasons", [])),
            status="open",
        )
        db.add(trade)
        portfolio.total_trades     += 1
        portfolio.daily_trades      = (portfolio.daily_trades or 0) + 1
        portfolio.updated_at        = datetime.now()
        db.commit()

        logger.info(
            f"[Paper] OPEN  {strategy_id} | {symbol} {signal_data['direction']} "
            f"@ ${entry:,.2f} | SL ${sl:,.2f} | TP ${tp:,.2f} | "
            f"Lots {lot_size} ({units} units) | Risk ${risk_usd:.2f}"
        )

        if broadcast_fn:
            broadcast_fn({
                "type": "paper_trade_opened",
                "strategy_id": strategy_id,
                "label": cfg["label"],
                "symbol": symbol,
                "direction": signal_data["direction"],
                "entry_price": entry,
                "stop_loss": sl,
                "take_profit": tp,
                "lot_size": lot_size,
                "risk_usd": risk_usd,
                "score": signal_data["score"],
            })
        return True
    finally:
        db.close()


def check_and_close_trades(symbol, current_price, broadcast_fn=None):
    """
    Called every 10s. Closes trades that:
      (a) hit SL or TP, OR
      (b) signal conditions have reversed (smart invalidation, checked every 5 min)
    """
    db = SessionLocal()
    closed = 0
    try:
        open_trades = db.query(PaperTrade).filter(
            and_(PaperTrade.symbol == symbol, PaperTrade.status == "open")
        ).all()

        for trade in open_trades:
            # ── SL / TP check ─────────────────────────────────────────────
            hit_sl = hit_tp = False
            if trade.direction == "BUY":
                hit_sl = current_price <= trade.stop_loss
                hit_tp = current_price >= trade.take_profit
            else:
                hit_sl = current_price >= trade.stop_loss
                hit_tp = current_price <= trade.take_profit

            invalidated, inv_reason = False, None
            if not hit_sl and not hit_tp:
                invalidated, inv_reason = _should_invalidate(trade)

            if not hit_sl and not hit_tp and not invalidated:
                continue

            # ── Determine exit ─────────────────────────────────────────────
            if hit_sl:
                exit_price = trade.stop_loss
                result     = "loss"
            elif hit_tp:
                exit_price = trade.take_profit
                result     = "win"
            else:
                # Early close at current price
                exit_price = current_price
                result     = (
                    "win"
                    if (trade.direction == "BUY" and current_price > trade.entry_price) or
                       (trade.direction == "SELL" and current_price < trade.entry_price)
                    else "invalidated"
                )

            pnl_usd = (
                (exit_price - trade.entry_price) * trade.units
                if trade.direction == "BUY"
                else (trade.entry_price - exit_price) * trade.units
            )

            trade.status     = "closed"
            trade.result     = result
            trade.exit_price = round(exit_price, 2)
            trade.pnl_usd    = round(pnl_usd, 4)
            trade.closed_at  = datetime.now()
            trade.analysis   = _build_analysis(trade)

            portfolio = _get_portfolio(db)
            if portfolio:
                portfolio.balance      = round(portfolio.balance + pnl_usd, 4)
                portfolio.peak_balance = max(portfolio.peak_balance, portfolio.balance)
                if result == "win":
                    portfolio.winning_trades += 1
                else:
                    portfolio.losing_trades += 1
                portfolio.updated_at = datetime.now()

            db.commit()
            closed += 1
            _invalidation_cache.pop(trade.id, None)

            close_reason = inv_reason or ("SL" if hit_sl else "TP")
            logger.info(
                f"[Paper] CLOSE {trade.strategy_id} | {symbol} {result.upper()} [{close_reason}] "
                f"@ ${exit_price:,.2f} | PnL ${pnl_usd:+.2f} | Bal ${portfolio.balance:.2f}"
            )

            if broadcast_fn:
                broadcast_fn({
                    "type": "paper_trade_closed",
                    "strategy_id": trade.strategy_id,
                    "symbol": symbol,
                    "direction": trade.direction,
                    "result": result,
                    "entry_price": trade.entry_price,
                    "exit_price": round(exit_price, 2),
                    "pnl_usd": round(pnl_usd, 4),
                    "balance": round(portfolio.balance, 2) if portfolio else None,
                    "close_reason": close_reason,
                })

    except Exception as e:
        logger.error(f"[Paper] check_and_close error for {symbol}: {e}")
        db.rollback()
    finally:
        db.close()

    return closed


def scan_strategy(strategy_id, broadcast_fn=None):
    """Scan a strategy and try to enter a trade on the master portfolio."""
    from strategy import analyze_fibonacci, analyze_orderblock_liquidity

    _analyzers = {
        "analyze_signal":               analyze_signal,
        "analyze_fibonacci":            analyze_fibonacci,
        "analyze_orderblock_liquidity": analyze_orderblock_liquidity,
    }

    cfg         = STRATEGIES[strategy_id]
    analyzer_fn = _analyzers.get(cfg.get("analyzer", "analyze_signal"), analyze_signal)
    symbols     = cfg.get("symbols") or SYMBOLS

    for symbol in symbols:
        try:
            df = fetch_candles(symbol, interval=cfg["timeframe"], limit=210)
            if df is None:
                continue
            signal_data = analyzer_fn(df, symbol, cfg["params"])
            if signal_data:
                try_enter_trade(strategy_id, symbol, signal_data, broadcast_fn)
        except Exception as e:
            logger.error(f"[Paper] scan_strategy {strategy_id}/{symbol} error: {e}")


# ── Read endpoints ────────────────────────────────────────────────────────────

def get_all_portfolios():
    db = SessionLocal()
    try:
        p = _get_portfolio(db)
        if not p:
            return []

        _check_and_reset_daily(p)
        can_trade, daily_reason, daily_pnl, daily_pnl_pct = _daily_status(p)
        day_start = p.day_start_balance or p.balance

        total_closed = p.winning_trades + p.losing_trades
        win_rate  = (p.winning_trades / total_closed * 100) if total_closed > 0 else 0
        roi       = ((p.balance - p.initial_balance) / p.initial_balance * 100)
        drawdown  = ((p.peak_balance - p.balance) / p.peak_balance * 100) if p.peak_balance > 0 else 0

        open_count = db.query(PaperTrade).filter(PaperTrade.status == "open").count()

        # Per-strategy breakdown for analytics tab
        strategy_breakdown = {}
        for sid, scfg in STRATEGIES.items():
            s_trades = db.query(PaperTrade).filter(PaperTrade.strategy_id == sid).all()
            wins   = sum(1 for t in s_trades if t.result == "win")
            losses = sum(1 for t in s_trades if t.result in ("loss", "invalidated"))
            total  = wins + losses
            pnl    = sum(t.pnl_usd or 0 for t in s_trades if t.status == "closed")
            strategy_breakdown[sid] = {
                "label":    scfg["label"],
                "timeframe": scfg["timeframe"],
                "total":    total,
                "wins":     wins,
                "losses":   losses,
                "pnl":      round(pnl, 2),
                "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
            }

        db.commit()
        return [{
            "strategy_id":     PORTFOLIO_ID,
            "label":           p.label,
            "balance":         round(p.balance, 2),
            "initial_balance": p.initial_balance,
            "peak_balance":    round(p.peak_balance, 2),
            "roi_pct":         round(roi, 2),
            "drawdown_pct":    round(drawdown, 2),
            "total_trades":    p.total_trades,
            "winning_trades":  p.winning_trades,
            "losing_trades":   p.losing_trades,
            "win_rate":        round(win_rate, 1),
            "open_trades":     open_count,
            "lot_size":        round(p.balance / 100.0, 2),
            # daily
            "daily_pnl":           round(daily_pnl, 2),
            "daily_pnl_pct":       round(daily_pnl_pct, 2),
            "daily_target_pct":    DAILY_TARGET_PCT,
            "daily_risk_pct":      DAILY_RISK_PCT,
            "daily_target_usd":    round(day_start * DAILY_TARGET_PCT / 100, 2),
            "daily_risk_usd":      round(day_start * DAILY_RISK_PCT / 100, 2),
            "day_start_balance":   round(day_start, 2),
            "daily_trades":        p.daily_trades or 0,
            "max_daily_trades":    MAX_DAILY_TRADES,
            "daily_status":        "active" if can_trade else daily_reason,
            # per-strategy breakdown
            "strategy_breakdown":  strategy_breakdown,
        }]
    finally:
        db.close()


def get_paper_trades(strategy_id=None, status=None, limit=200):
    db = SessionLocal()
    try:
        q = db.query(PaperTrade).order_by(PaperTrade.opened_at.desc())
        if strategy_id:
            q = q.filter(PaperTrade.strategy_id == strategy_id)
        if status:
            q = q.filter(PaperTrade.status == status)
        trades = q.limit(limit).all()
        return [{
            "id":          t.id,
            "strategy_id": t.strategy_id,
            "label":       STRATEGIES.get(t.strategy_id, {}).get("label", t.strategy_id),
            "symbol":      t.symbol,
            "timeframe":   t.timeframe,
            "direction":   t.direction,
            "entry_price": t.entry_price,
            "stop_loss":   t.stop_loss,
            "take_profit": t.take_profit,
            "lot_size":    t.lot_size,
            "units":       t.units,
            "risk_usd":    t.risk_usd,
            "status":      t.status,
            "result":      t.result,
            "exit_price":  t.exit_price,
            "pnl_usd":     t.pnl_usd,
            "score":       t.score,
            "reasons":     json.loads(t.reasons) if t.reasons else [],
            "analysis":    t.analysis,
            "opened_at":   t.opened_at.isoformat() if t.opened_at else None,
            "closed_at":   t.closed_at.isoformat() if t.closed_at else None,
        } for t in trades]
    finally:
        db.close()


def reset_portfolio():
    """Hard reset — wipe all trades and restore $500."""
    db = SessionLocal()
    try:
        db.query(PaperTrade).delete()
        p = _get_portfolio(db)
        if p:
            p.balance           = INITIAL_BALANCE
            p.peak_balance      = INITIAL_BALANCE
            p.day_start_balance = INITIAL_BALANCE
            p.last_day_reset    = date.today().isoformat()
            p.total_trades      = 0
            p.winning_trades    = 0
            p.losing_trades     = 0
            p.daily_trades      = 0
            p.updated_at        = datetime.now()
        db.commit()
        _invalidation_cache.clear()
        return True
    finally:
        db.close()
