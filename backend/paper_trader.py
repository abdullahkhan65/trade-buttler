"""
Autonomous Paper Trading Engine
================================
Runs 5 strategies simultaneously, each starting with $100 virtual balance:

  1h_baseline     — 1H multi-confluence (score ≥ 8)
  4h_conservative — 4H multi-confluence (score ≥ 8)
  15m_aggressive  — 15M multi-confluence (score ≥ 7)
  xau_fibonacci   — 1H Fibonacci retracement, XAU only (score ≥ 7)
  xau_structure   — 1H Order Blocks + Liquidity Sweeps, XAU only (score ≥ 7)

Each confirmed signal auto-enters a trade. Risk is 2% of current balance.
SL/TP is checked every ~10 seconds via the price ticker.
Losing trades get an analysis note. Daily analyzer compares factor win rates.
"""
import json
import logging
from datetime import datetime
from sqlalchemy import and_
from database import SessionLocal
from models import PaperTrade, PaperPortfolio
from data_fetcher import fetch_candles
from strategy import analyze_signal
from config import SYMBOLS

logger = logging.getLogger(__name__)

# ── Strategy definitions ──────────────────────────────────────────────────────

STRATEGIES = {
    "1h_baseline": {
        "label": "1H Baseline",
        "timeframe": "1h",
        "risk_pct": 2.0,
        "analyzer": "analyze_signal",
        "symbols": None,            # None = all symbols
        "params": {
            "min_score_forming": 6,
            "min_score_confirmed": 8,
            "rsi_buy_low": 45,  "rsi_buy_high": 62,
            "rsi_sell_low": 38, "rsi_sell_high": 55,
            "atr_sl_mult": 1.5, "atr_tp_mult": 3.0,
        },
    },
    "4h_conservative": {
        "label": "4H Conservative",
        "timeframe": "4h",
        "risk_pct": 2.0,
        "analyzer": "analyze_signal",
        "symbols": None,
        "params": {
            "min_score_forming": 7,
            "min_score_confirmed": 8,
            "rsi_buy_low": 46,  "rsi_buy_high": 60,
            "rsi_sell_low": 40, "rsi_sell_high": 54,
            "atr_sl_mult": 1.8, "atr_tp_mult": 3.5,
        },
    },
    "15m_aggressive": {
        "label": "15M Aggressive",
        "timeframe": "15m",
        "risk_pct": 1.5,
        "analyzer": "analyze_signal",
        "symbols": None,
        "params": {
            "min_score_forming": 5,
            "min_score_confirmed": 7,
            "rsi_buy_low": 42,  "rsi_buy_high": 65,
            "rsi_sell_low": 35, "rsi_sell_high": 58,
            "atr_sl_mult": 1.2, "atr_tp_mult": 2.5,
        },
    },
    # ── XAU/USD-specific strategies ───────────────────────────────────────────
    "xau_fibonacci": {
        "label": "XAU Fibonacci",
        "timeframe": "1h",
        "risk_pct": 2.0,
        "analyzer": "analyze_fibonacci",
        "symbols": ["XAU/USD"],     # gold only
        "params": {
            "min_score_forming": 5,
            "min_score_confirmed": 7,
            "atr_sl_mult": 1.5,
            "atr_tp_mult": 3.5,
        },
    },
    "xau_structure": {
        "label": "XAU Smart Money",
        "timeframe": "1h",
        "risk_pct": 2.0,
        "analyzer": "analyze_orderblock_liquidity",
        "symbols": ["XAU/USD"],     # gold only
        "params": {
            "min_score_forming": 5,
            "min_score_confirmed": 7,
            "atr_sl_mult": 1.2,
            "atr_tp_mult": 3.0,
        },
    },
}

# ── Bootstrap ─────────────────────────────────────────────────────────────────

def ensure_portfolios():
    """Create PaperPortfolio rows for every strategy on first run."""
    db = SessionLocal()
    try:
        for sid, cfg in STRATEGIES.items():
            if not db.query(PaperPortfolio).filter(PaperPortfolio.strategy_id == sid).first():
                db.add(PaperPortfolio(
                    strategy_id=sid,
                    label=cfg["label"],
                    timeframe=cfg["timeframe"],
                    balance=100.0,
                    initial_balance=100.0,
                    peak_balance=100.0,
                ))
        db.commit()
    finally:
        db.close()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_portfolio(db, strategy_id):
    return db.query(PaperPortfolio).filter(PaperPortfolio.strategy_id == strategy_id).first()


def _has_open_trade(db, strategy_id, symbol):
    return db.query(PaperTrade).filter(
        and_(
            PaperTrade.strategy_id == strategy_id,
            PaperTrade.symbol == symbol,
            PaperTrade.status == "open",
        )
    ).first() is not None


def _generate_analysis(trade, reasons):
    """Build a brief post-trade note explaining what happened."""
    parts = []
    tp_dist = abs(trade.take_profit - trade.entry_price)
    exit_dist = abs((trade.exit_price or trade.entry_price) - trade.entry_price)
    pct_toward_tp = (exit_dist / tp_dist * 100) if tp_dist > 0 else 0

    if trade.result == "win":
        rr = tp_dist / abs(trade.stop_loss - trade.entry_price) if trade.stop_loss != trade.entry_price else 0
        parts.append(f"TP hit at ${trade.exit_price:,.2f} ({rr:.1f}R achieved)")
    else:
        parts.append(f"SL hit at ${trade.exit_price:,.2f} — reached {pct_toward_tp:.0f}% toward TP")
        parts.append("Review: check EMA separation strength and RSI zone at entry")

    for r in (reasons or []):
        if "EMA20/50" in r:
            parts.append(f"Trend: {r}")
            break
    for r in (reasons or []):
        if "RSI" in r:
            parts.append(f"RSI: {r}")
            break

    return " | ".join(parts)


# ── Core actions ──────────────────────────────────────────────────────────────

def try_enter_trade(strategy_id, symbol, signal_data, broadcast_fn=None):
    """
    Open a paper trade if the signal is CONFIRMED and no trade is already open
    for this strategy + symbol.  Returns True if a trade was opened.
    """
    if signal_data.get("signal_type") != "confirmed":
        return False

    db = SessionLocal()
    try:
        if _has_open_trade(db, strategy_id, symbol):
            return False

        portfolio = _get_portfolio(db, strategy_id)
        if not portfolio or portfolio.balance <= 1.0:
            return False

        cfg = STRATEGIES[strategy_id]
        risk_usd = portfolio.balance * (cfg["risk_pct"] / 100.0)

        entry = signal_data["entry_price"]
        sl    = signal_data["stop_loss"]
        tp    = signal_data["take_profit"]
        sl_dist = abs(entry - sl)

        if sl_dist < 0.0001:
            return False

        units = risk_usd / sl_dist

        trade = PaperTrade(
            strategy_id=strategy_id,
            symbol=symbol,
            timeframe=cfg["timeframe"],
            direction=signal_data["direction"],
            entry_price=entry,
            stop_loss=sl,
            take_profit=tp,
            units=round(units, 6),
            risk_usd=round(risk_usd, 4),
            score=signal_data["score"],
            reasons=json.dumps(signal_data.get("reasons", [])),
            status="open",
        )
        db.add(trade)
        portfolio.total_trades += 1
        portfolio.updated_at = datetime.now()
        db.commit()

        logger.info(
            f"[Paper] OPEN  {strategy_id} | {symbol} {signal_data['direction']} "
            f"@ ${entry:,.2f} | SL ${sl:,.2f} | TP ${tp:,.2f} | Risk ${risk_usd:.2f}"
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
                "risk_usd": round(risk_usd, 4),
                "score": signal_data["score"],
            })
        return True
    finally:
        db.close()


def check_and_close_trades(symbol, current_price, broadcast_fn=None):
    """
    Called every ~10s.  Closes any open paper trade for this symbol
    whose SL or TP has been touched by the current price.
    """
    db = SessionLocal()
    closed = 0
    try:
        open_trades = db.query(PaperTrade).filter(
            and_(PaperTrade.symbol == symbol, PaperTrade.status == "open")
        ).all()

        for trade in open_trades:
            hit_sl = hit_tp = False
            if trade.direction == "BUY":
                hit_sl = current_price <= trade.stop_loss
                hit_tp = current_price >= trade.take_profit
            else:
                hit_sl = current_price >= trade.stop_loss
                hit_tp = current_price <= trade.take_profit

            if not hit_sl and not hit_tp:
                continue

            exit_price = trade.stop_loss if hit_sl else trade.take_profit
            result = "loss" if hit_sl else "win"

            pnl_usd = (
                (exit_price - trade.entry_price) * trade.units
                if trade.direction == "BUY"
                else (trade.entry_price - exit_price) * trade.units
            )

            trade.status    = "closed"
            trade.result    = result
            trade.exit_price = round(exit_price, 2)
            trade.pnl_usd   = round(pnl_usd, 4)
            trade.closed_at = datetime.now()

            portfolio = _get_portfolio(db, trade.strategy_id)
            if portfolio:
                portfolio.balance = round(portfolio.balance + pnl_usd, 4)
                portfolio.peak_balance = max(portfolio.peak_balance, portfolio.balance)
                if result == "win":
                    portfolio.winning_trades += 1
                else:
                    portfolio.losing_trades += 1
                portfolio.updated_at = datetime.now()

            reasons = json.loads(trade.reasons) if trade.reasons else []
            trade.analysis = _generate_analysis(trade, reasons)

            db.commit()
            closed += 1

            logger.info(
                f"[Paper] CLOSE {trade.strategy_id} | {symbol} {result.upper()} "
                f"@ ${exit_price:,.2f} | PnL ${pnl_usd:+.2f} | Bal ${portfolio.balance:.2f}"
            )

            if broadcast_fn:
                broadcast_fn({
                    "type": "paper_trade_closed",
                    "strategy_id": trade.strategy_id,
                    "label": STRATEGIES.get(trade.strategy_id, {}).get("label", trade.strategy_id),
                    "symbol": symbol,
                    "direction": trade.direction,
                    "result": result,
                    "entry_price": trade.entry_price,
                    "exit_price": round(exit_price, 2),
                    "pnl_usd": round(pnl_usd, 4),
                    "balance": round(portfolio.balance, 2) if portfolio else None,
                })

    except Exception as e:
        logger.error(f"[Paper] check_and_close error for {symbol}: {e}")
        db.rollback()
    finally:
        db.close()

    return closed


def scan_strategy(strategy_id, broadcast_fn=None):
    """
    Full scan for a strategy — fetch candles, run the strategy's analyzer,
    and enter a paper trade if a confirmed signal is found.
    """
    from strategy import analyze_fibonacci, analyze_orderblock_liquidity

    _analyzers = {
        "analyze_signal":              analyze_signal,
        "analyze_fibonacci":           analyze_fibonacci,
        "analyze_orderblock_liquidity": analyze_orderblock_liquidity,
    }

    cfg         = STRATEGIES[strategy_id]
    analyzer_fn = _analyzers.get(cfg.get("analyzer", "analyze_signal"), analyze_signal)
    symbols     = cfg.get("symbols") or SYMBOLS   # None → all symbols

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


# ── Read endpoints (called by main.py) ───────────────────────────────────────

def get_all_portfolios():
    db = SessionLocal()
    try:
        result = []
        for p in db.query(PaperPortfolio).all():
            total_closed = p.winning_trades + p.losing_trades
            win_rate = (p.winning_trades / total_closed * 100) if total_closed > 0 else 0
            roi = ((p.balance - p.initial_balance) / p.initial_balance * 100)
            drawdown = ((p.peak_balance - p.balance) / p.peak_balance * 100) if p.peak_balance > 0 else 0

            # Count open trades
            open_count = db.query(PaperTrade).filter(
                and_(PaperTrade.strategy_id == p.strategy_id, PaperTrade.status == "open")
            ).count()

            result.append({
                "strategy_id": p.strategy_id,
                "label": p.label,
                "timeframe": p.timeframe,
                "balance": round(p.balance, 2),
                "initial_balance": p.initial_balance,
                "peak_balance": round(p.peak_balance, 2),
                "roi_pct": round(roi, 2),
                "drawdown_pct": round(drawdown, 2),
                "total_trades": p.total_trades,
                "winning_trades": p.winning_trades,
                "losing_trades": p.losing_trades,
                "win_rate": round(win_rate, 1),
                "open_trades": open_count,
            })
        return result
    finally:
        db.close()


def get_paper_trades(strategy_id=None, status=None, limit=100):
    db = SessionLocal()
    try:
        q = db.query(PaperTrade).order_by(PaperTrade.opened_at.desc())
        if strategy_id:
            q = q.filter(PaperTrade.strategy_id == strategy_id)
        if status:
            q = q.filter(PaperTrade.status == status)
        trades = q.limit(limit).all()
        return [{
            "id": t.id,
            "strategy_id": t.strategy_id,
            "label": STRATEGIES.get(t.strategy_id, {}).get("label", t.strategy_id),
            "symbol": t.symbol,
            "timeframe": t.timeframe,
            "direction": t.direction,
            "entry_price": t.entry_price,
            "stop_loss": t.stop_loss,
            "take_profit": t.take_profit,
            "units": t.units,
            "risk_usd": t.risk_usd,
            "status": t.status,
            "result": t.result,
            "exit_price": t.exit_price,
            "pnl_usd": t.pnl_usd,
            "score": t.score,
            "reasons": json.loads(t.reasons) if t.reasons else [],
            "analysis": t.analysis,
            "opened_at": t.opened_at.isoformat() if t.opened_at else None,
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        } for t in trades]
    finally:
        db.close()


def reset_portfolio(strategy_id):
    """Hard reset a strategy — wipe trades and reset balance to $100."""
    db = SessionLocal()
    try:
        db.query(PaperTrade).filter(PaperTrade.strategy_id == strategy_id).delete()
        portfolio = _get_portfolio(db, strategy_id)
        if portfolio:
            portfolio.balance = 100.0
            portfolio.peak_balance = 100.0
            portfolio.total_trades = 0
            portfolio.winning_trades = 0
            portfolio.losing_trades = 0
            portfolio.updated_at = datetime.now()
        db.commit()
        return True
    finally:
        db.close()
