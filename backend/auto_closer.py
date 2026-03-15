"""
Auto Closer: Checks all open signals and automatically closes them
when price hits TP or SL. Runs every scan cycle.
"""
import json
import logging
from datetime import datetime
from database import SessionLocal
from models import Signal
from data_fetcher import get_live_price

logger = logging.getLogger(__name__)


def auto_close_signals():
    """
    Check all open/forming/confirmed signals.
    Auto-close as win if price >= TP (BUY) or <= TP (SELL).
    Auto-close as loss if price <= SL (BUY) or >= SL (SELL).
    """
    db = SessionLocal()
    closed_count = 0
    try:
        open_signals = db.query(Signal).filter(
            Signal.status.in_(["forming", "confirmed"]),
            Signal.result == None
        ).all()

        if not open_signals:
            return 0

        # Fetch prices once per symbol
        prices = {}
        for sig in open_signals:
            if sig.symbol not in prices:
                price = get_live_price(sig.symbol)
                if price:
                    prices[sig.symbol] = price

        for sig in open_signals:
            price = prices.get(sig.symbol)
            if not price:
                continue

            direction = sig.direction
            sl = sig.stop_loss
            tp = sig.take_profit

            outcome = None
            if direction == "BUY":
                if price >= tp:
                    outcome = "win"
                elif price <= sl:
                    outcome = "loss"
            elif direction == "SELL":
                if price <= tp:
                    outcome = "win"
                elif price >= sl:
                    outcome = "loss"

            if outcome:
                sig.result = outcome
                sig.status = "closed"
                sig.closed_at = datetime.now()

                # Calculate R
                entry = sig.entry_price
                risk = abs(entry - sl) if sl else 1
                if outcome == "win":
                    pnl = abs(tp - entry)
                else:
                    pnl = -abs(entry - sl)
                sig.pnl_pips = round(pnl, 4)

                closed_count += 1
                logger.info(
                    f"[AUTO-CLOSE] {sig.symbol} {direction} #{sig.id} → {outcome.upper()} "
                    f"@ ${price:,.2f} (entry ${entry:,.2f})"
                )

        if closed_count > 0:
            db.commit()

    except Exception as e:
        logger.error(f"Auto-close error: {e}")
        db.rollback()
    finally:
        db.close()

    return closed_count
