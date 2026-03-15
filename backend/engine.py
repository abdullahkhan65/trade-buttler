import logging
import json
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
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
scheduler = BackgroundScheduler()
_scan_count = 0


def set_broadcast_callback(callback):
    global broadcast_callback
    broadcast_callback = callback


def broadcast(data):
    if broadcast_callback:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(broadcast_callback(data))
        except Exception as e:
            logger.debug(f"Broadcast error: {e}")


def scan_symbol(symbol):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    live_price = get_live_price(symbol)

    df = fetch_candles(symbol, interval="1h", limit=210)
    if df is None:
        logger.error(f"[{timestamp}] [{symbol}] Failed to fetch candles")
        if live_price:
            broadcast({"type": "price_update", "symbol": symbol, "price": live_price, "timestamp": timestamp})
        return

    # Get adaptive params if optimizer has run
    try:
        from optimizer import get_best_params
        params = get_best_params(symbol)
    except Exception:
        params = None

    # Run strategy (with adaptive params if available)
    if params:
        from strategy import analyze_signal_with_params
        signal_data = analyze_signal_with_params(df, symbol, params)
    else:
        signal_data = analyze_signal(df, symbol)

    # Apply adaptive score adjustment if we have enough closed trades
    if signal_data:
        try:
            from factor_analyzer import get_adaptive_score_adjustment
            adaptive_score = get_adaptive_score_adjustment(
                symbol, signal_data['score'], signal_data['reasons']
            )
            signal_data['adaptive_score'] = adaptive_score
        except Exception:
            signal_data['adaptive_score'] = float(signal_data['score'])

    if signal_data is None:
        logger.info(f"[{timestamp}] [{symbol}] No signal (score < 5)")
        if live_price:
            broadcast({"type": "price_update", "symbol": symbol, "price": live_price, "timestamp": timestamp})
        return

    direction = signal_data['direction']
    score = signal_data['score']
    signal_type = signal_data['signal_type']
    entry = signal_data['entry_price']

    logger.info(f"[{timestamp}] [{symbol}] [{direction}] Score: {score}/9 @ ${entry:,.2f} — {signal_type.upper()}")

    prev_state = last_signal_state[symbol]
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
                triggered_at=datetime.now() if signal_type == "confirmed" else None
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
            "timestamp": timestamp
        })

        last_signal_state[symbol] = signal_type

    if live_price:
        broadcast({"type": "price_update", "symbol": symbol, "price": live_price, "timestamp": timestamp})
        db = SessionLocal()
        try:
            snap = PriceSnapshot(symbol=symbol, price=live_price)
            db.add(snap)
            db.commit()
        finally:
            db.close()


def run_scan():
    global _scan_count
    _scan_count += 1

    # Auto-close open signals on every scan
    closed = auto_close_signals()
    if closed > 0:
        broadcast({"type": "signals_auto_closed", "count": closed})

    for symbol in SYMBOLS:
        try:
            scan_symbol(symbol)
        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")


def start_engine():
    logger.info(f"Starting Trade Buttler Signal Engine (interval: {SCAN_INTERVAL}s)")
    scheduler.add_job(
        run_scan,
        trigger=IntervalTrigger(seconds=SCAN_INTERVAL),
        id="signal_scan",
        replace_existing=True,
        max_instances=1
    )
    scheduler.start()
    run_scan()
    logger.info("Signal engine started successfully")


def stop_engine():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Signal engine stopped")


def get_engine_status():
    return {
        "running": scheduler.running,
        "scan_interval": SCAN_INTERVAL,
        "scan_count": _scan_count,
        "last_states": last_signal_state
    }
