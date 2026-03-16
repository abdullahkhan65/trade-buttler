import logging
import json
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from data_fetcher import fetch_candles, get_live_price
from strategy import analyze_signal
from emailer import send_forming_email, send_confirmed_email
from database import SessionLocal
from models import Signal, PriceSnapshot
from config import SYMBOLS, SCAN_INTERVAL
from auto_closer import auto_close_signals

logger = logging.getLogger(__name__)

last_signal_state = {symbol: None for symbol in SYMBOLS}
broadcast_callback = None
_event_loop = None          # the FastAPI asyncio event loop, captured at startup
scheduler = BackgroundScheduler()
_scan_count = 0


def set_broadcast_callback(callback):
    """Called from within FastAPI lifespan (async context) — capture the running loop."""
    global broadcast_callback, _event_loop
    import asyncio
    broadcast_callback = callback
    try:
        _event_loop = asyncio.get_running_loop()
    except RuntimeError:
        _event_loop = asyncio.get_event_loop()


def broadcast(data):
    """Thread-safe broadcast: schedules the async send on the FastAPI event loop."""
    if broadcast_callback and _event_loop:
        import asyncio
        try:
            asyncio.run_coroutine_threadsafe(broadcast_callback(data), _event_loop)
        except Exception as e:
            logger.debug(f"Broadcast error: {e}")


# ── Price ticker (runs every 10s) ────────────────────────────────────────────

def tick_prices():
    """
    Fetch live prices every 10 seconds and broadcast to all WebSocket clients.
    Also checks open paper trades for SL/TP hits on each tick.
    """
    from paper_trader import check_and_close_trades
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for symbol in SYMBOLS:
        try:
            price = get_live_price(symbol)
            if price:
                broadcast({
                    "type": "price_update",
                    "symbol": symbol,
                    "price": price,
                    "timestamp": ts,
                })
                check_and_close_trades(symbol, price, broadcast)
        except Exception as e:
            logger.debug(f"tick_prices error for {symbol}: {e}")


# ── Signal scan (runs every SCAN_INTERVAL seconds) ───────────────────────────

def scan_symbol(symbol):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    live_price = get_live_price(symbol)

    df = fetch_candles(symbol, interval="1h", limit=210)
    if df is None:
        logger.error(f"[{timestamp}] [{symbol}] Failed to fetch candles")
        return

    # Get adaptive params if optimizer has run
    try:
        from optimizer import get_best_params
        params = get_best_params(symbol)
    except Exception:
        params = None

    if params:
        from strategy import analyze_signal_with_params
        signal_data = analyze_signal_with_params(df, symbol, params)
    else:
        signal_data = analyze_signal(df, symbol)

    if signal_data:
        try:
            from factor_analyzer import get_adaptive_score_adjustment
            signal_data['adaptive_score'] = get_adaptive_score_adjustment(
                symbol, signal_data['score'], signal_data['reasons']
            )
        except Exception:
            signal_data['adaptive_score'] = float(signal_data['score'])

    if signal_data is None:
        logger.info(f"[{timestamp}] [{symbol}] No signal (score < 6)")
        return

    direction   = signal_data['direction']
    score       = signal_data['score']
    signal_type = signal_data['signal_type']
    entry       = signal_data['entry_price']

    logger.info(f"[{timestamp}] [{symbol}] [{direction}] Score: {score}/9 @ ${entry:,.2f} — {signal_type.upper()}")

    prev_state   = last_signal_state[symbol]
    state_changed = prev_state != signal_type

    if state_changed:
        db = SessionLocal()
        try:
            db_signal = Signal(
                symbol=symbol,
                signal_type=signal_type,
                direction=direction,
                entry_price=signal_data['entry_price'],
                stop_loss=signal_data['stop_loss'],
                take_profit=signal_data['take_profit'],
                confidence=signal_data['confidence'],
                score=score,
                reasons=json.dumps(signal_data['reasons']),
                status=signal_type,
                triggered_at=datetime.now() if signal_type == "confirmed" else None,
            )
            db.add(db_signal)
            db.commit()
        finally:
            db.close()

        if signal_type == "forming":
            send_forming_email(signal_data)
        elif signal_type == "confirmed":
            send_confirmed_email(signal_data)

        broadcast({
            "type": "new_signal" if prev_state is None else "signal_update",
            "symbol": symbol,
            "signal_type": signal_type,
            "direction": direction,
            "entry_price": entry,
            "score": score,
            "adaptive_score": signal_data.get('adaptive_score', score),
            "confidence": signal_data['confidence'],
            "stop_loss": signal_data['stop_loss'],
            "take_profit": signal_data['take_profit'],
            "reasons": signal_data['reasons'],
            "timestamp": timestamp,
        })

        last_signal_state[symbol] = signal_type

        # Auto-enter paper trade on confirmed signals (master portfolio)
        if signal_type == "confirmed":
            try:
                from paper_trader import try_enter_trade
                try_enter_trade("1h_baseline", symbol, signal_data, broadcast)
            except Exception as e:
                logger.error(f"[Paper] 1h_baseline entry failed: {e}")

    if live_price:
        broadcast({"type": "price_update", "symbol": symbol, "price": live_price, "timestamp": timestamp})
        db = SessionLocal()
        try:
            db.add(PriceSnapshot(symbol=symbol, price=live_price))
            db.commit()
        finally:
            db.close()


def run_scan():
    global _scan_count
    _scan_count += 1

    closed = auto_close_signals()
    if closed > 0:
        broadcast({"type": "signals_auto_closed", "count": closed})

    for symbol in SYMBOLS:
        try:
            scan_symbol(symbol)
        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")


def _restore_signal_states():
    """Load last known signal state per symbol from DB so restarts don't resend emails."""
    db = SessionLocal()
    try:
        for symbol in SYMBOLS:
            last = (
                db.query(Signal)
                .filter(Signal.symbol == symbol, Signal.status.in_(["forming", "confirmed"]))
                .order_by(Signal.created_at.desc())
                .first()
            )
            if last:
                last_signal_state[symbol] = last.signal_type
                logger.info(f"Restored signal state [{symbol}]: {last.signal_type}")
    finally:
        db.close()


def _run_analysis():
    """Wrapper so daily_analyzer errors don't crash the scheduler."""
    try:
        from daily_analyzer import analyze_trades
        report = analyze_trades()
        if report.get("status") != "insufficient_data":
            broadcast({
                "type": "analysis_complete",
                "insights": report.get("insights", []),
                "recommendations": report.get("recommendations", []),
            })
            logger.info(f"[Analyzer] Done — {len(report.get('insights', []))} insights generated")
    except Exception as e:
        logger.error(f"[Analyzer] Error: {e}")


def start_engine():
    from paper_trader import ensure_portfolios, scan_strategy

    _restore_signal_states()
    ensure_portfolios()

    logger.info(f"Starting Trade Buttler Signal Engine (interval: {SCAN_INTERVAL}s)")

    # Main 1h signal scan
    scheduler.add_job(
        run_scan,
        trigger=IntervalTrigger(seconds=SCAN_INTERVAL),
        id="signal_scan",
        replace_existing=True,
        max_instances=1,
    )

    # 10-second live price ticker + paper trade SL/TP monitor
    scheduler.add_job(
        tick_prices,
        trigger=IntervalTrigger(seconds=10),
        id="price_ticker",
        replace_existing=True,
        max_instances=1,
    )

    # 15m aggressive — scan every 5 minutes
    scheduler.add_job(
        lambda: scan_strategy("15m_aggressive", broadcast),
        trigger=IntervalTrigger(minutes=5),
        id="paper_scan_15m",
        replace_existing=True,
        max_instances=1,
    )

    # 4h conservative — scan every 30 minutes
    scheduler.add_job(
        lambda: scan_strategy("4h_conservative", broadcast),
        trigger=IntervalTrigger(minutes=30),
        id="paper_scan_4h",
        replace_existing=True,
        max_instances=1,
    )

    # XAU Fibonacci + Smart Money — scan every 15 minutes (1H strategy)
    scheduler.add_job(
        lambda: [scan_strategy(s, broadcast) for s in ("xau_fibonacci", "xau_structure")],
        trigger=IntervalTrigger(minutes=15),
        id="paper_scan_xau_advanced",
        replace_existing=True,
        max_instances=1,
    )

    # Daily learning analysis — runs every 6 hours
    scheduler.add_job(
        _run_analysis,
        trigger=IntervalTrigger(hours=6),
        id="daily_analysis",
        replace_existing=True,
        max_instances=1,
    )

    # One-shot first scan 5s after startup
    scheduler.add_job(
        run_scan,
        trigger=DateTrigger(run_date=datetime.now() + timedelta(seconds=5)),
        id="signal_scan_first",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Signal engine started — first scan in 5s, prices ticking every 10s")


def stop_engine():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Signal engine stopped")


def get_engine_status():
    return {
        "running": scheduler.running,
        "scan_interval": SCAN_INTERVAL,
        "scan_count": _scan_count,
        "last_states": last_signal_state,
    }
