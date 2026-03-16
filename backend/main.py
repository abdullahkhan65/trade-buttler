import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel

import models
from database import get_db, init_db
from engine import start_engine, stop_engine, get_engine_status, set_broadcast_callback
from emailer import send_test_email
from data_fetcher import fetch_candles, get_live_price
from config import SYMBOLS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)


# WebSocket connection manager — defined before lifespan so it can be referenced
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, data: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    set_broadcast_callback(manager.broadcast)
    start_engine()
    logger.info("Trade Buttler started")
    yield
    stop_engine()


app = FastAPI(title="Trade Buttler API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle ping/pong
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

# --- API Endpoints ---

@app.get("/api/signals")
def get_signals(limit: int = 100, db: Session = Depends(get_db)):
    signals = db.query(models.Signal).order_by(models.Signal.created_at.desc()).limit(limit).all()
    result = []
    for s in signals:
        result.append({
            "id": s.id,
            "symbol": s.symbol,
            "signal_type": s.signal_type,
            "direction": s.direction,
            "entry_price": s.entry_price,
            "stop_loss": s.stop_loss,
            "take_profit": s.take_profit,
            "confidence": s.confidence,
            "score": s.score,
            "reasons": json.loads(s.reasons) if s.reasons else [],
            "status": s.status,
            "result": s.result,
            "pnl_pips": s.pnl_pips,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "triggered_at": s.triggered_at.isoformat() if s.triggered_at else None,
            "closed_at": s.closed_at.isoformat() if s.closed_at else None,
        })
    return result

@app.get("/api/signals/live")
def get_live_signals(db: Session = Depends(get_db)):
    signals = db.query(models.Signal).filter(
        models.Signal.status.in_(["forming", "confirmed"])
    ).order_by(models.Signal.created_at.desc()).all()
    result = []
    for s in signals:
        result.append({
            "id": s.id,
            "symbol": s.symbol,
            "signal_type": s.signal_type,
            "direction": s.direction,
            "entry_price": s.entry_price,
            "stop_loss": s.stop_loss,
            "take_profit": s.take_profit,
            "confidence": s.confidence,
            "score": s.score,
            "reasons": json.loads(s.reasons) if s.reasons else [],
            "status": s.status,
        })
    return result

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    all_signals = db.query(models.Signal).all()
    total = len(all_signals)
    closed = [s for s in all_signals if s.result in ("win", "loss")]
    wins = [s for s in closed if s.result == "win"]
    losses = [s for s in closed if s.result == "loss"]
    win_rate = (len(wins) / len(closed) * 100) if closed else 0
    total_pnl = sum(s.pnl_pips or 0 for s in closed)
    return {
        "total_signals": total,
        "closed_signals": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 1),
        "total_pnl": round(total_pnl, 2),
    }

@app.get("/api/candles/{symbol:path}")
def get_candles(symbol: str, interval: str = "1h"):
    from urllib.parse import unquote
    symbol = unquote(symbol)
    df = fetch_candles(symbol, interval=interval, limit=200)
    if df is None:
        raise HTTPException(status_code=503, detail="Failed to fetch candle data")

    candles = []
    for _, row in df.iterrows():
        ts = row['timestamp']
        if hasattr(ts, 'timestamp'):
            unix_ts = int(ts.timestamp())
        else:
            unix_ts = int(ts)
        candles.append({
            "time": unix_ts,
            "open": round(float(row['open']), 2),
            "high": round(float(row['high']), 2),
            "low": round(float(row['low']), 2),
            "close": round(float(row['close']), 2),
        })
    return candles

class SignalResult(BaseModel):
    result: str  # win / loss
    pnl_pips: Optional[float] = None

@app.post("/api/signals/{signal_id}/result")
def record_result(signal_id: int, body: SignalResult, db: Session = Depends(get_db)):
    signal = db.query(models.Signal).filter(models.Signal.id == signal_id).first()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    signal.result = body.result
    signal.pnl_pips = body.pnl_pips
    signal.status = "closed"
    signal.closed_at = datetime.now()
    db.commit()
    return {"success": True}

@app.get("/api/config")
def get_config():
    from config import (EMAIL_SENDER, EMAIL_RECIPIENT, SCAN_INTERVAL,
                        ATR_SL_MULTIPLIER, ATR_TP_MULTIPLIER,
                        MIN_SCORE_FORMING, MIN_SCORE_CONFIRMED)
    return {
        "email_sender": EMAIL_SENDER,
        "email_recipient": EMAIL_RECIPIENT,
        "scan_interval": SCAN_INTERVAL,
        "atr_sl_multiplier": ATR_SL_MULTIPLIER,
        "atr_tp_multiplier": ATR_TP_MULTIPLIER,
        "min_score_forming": MIN_SCORE_FORMING,
        "min_score_confirmed": MIN_SCORE_CONFIRMED,
    }

class ConfigUpdate(BaseModel):
    email_sender: Optional[str] = None
    email_recipient: Optional[str] = None
    scan_interval: Optional[int] = None

@app.post("/api/config")
def update_config(body: ConfigUpdate):
    # Write to .env file
    import os
    env_path = ".env"
    lines = []
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            lines = f.readlines()

    updates = {}
    if body.email_sender:
        updates["EMAIL_SENDER"] = body.email_sender
    if body.email_recipient:
        updates["EMAIL_RECIPIENT"] = body.email_recipient
    if body.scan_interval:
        updates["SCAN_INTERVAL"] = str(body.scan_interval)

    new_lines = []
    updated_keys = set()
    for line in lines:
        key = line.split("=")[0].strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}\n")
            updated_keys.add(key)
        else:
            new_lines.append(line)

    for key, val in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}\n")

    with open(env_path, 'w') as f:
        f.writelines(new_lines)

    return {"success": True, "message": "Config updated. Restart server to apply changes."}

@app.post("/api/test-email")
def test_email():
    success = send_test_email()
    return {"success": success, "message": "Test email sent" if success else "Failed to send email. Check config."}

# ---- Backtest endpoints ----

from backtester import run_backtest
from optimizer import optimize_symbol, get_all_optimization_results, get_best_params
from factor_analyzer import analyze_factors

class BacktestRequest(BaseModel):
    symbol: str
    interval: str = "1h"
    params: Optional[dict] = None
    limit: int = 500

@app.post("/api/backtest")
def backtest(body: BacktestRequest):
    result = run_backtest(body.symbol, body.interval, body.params, body.limit)
    return result.to_dict()

class OptimizeRequest(BaseModel):
    symbol: str
    interval: str = "1h"
    quick: bool = True

@app.post("/api/optimize")
def optimize(body: OptimizeRequest):
    """Run grid-search optimization. quick=True is faster (fewer combinations)."""
    result = optimize_symbol(body.symbol, body.interval, body.quick)
    return result

@app.get("/api/optimize/results")
def get_optimize_results():
    return get_all_optimization_results()

@app.get("/api/optimize/params/{symbol:path}")
def get_params(symbol: str):
    from urllib.parse import unquote
    symbol = unquote(symbol)
    return {"symbol": symbol, "params": get_best_params(symbol)}

@app.get("/api/factors")
def get_factors(symbol: Optional[str] = None):
    return analyze_factors(symbol)


@app.get("/api/prices")
def get_prices():
    """Instant live prices for both symbols — used on page load."""
    result = {}
    for sym in SYMBOLS:
        price = get_live_price(sym)
        result[sym] = price
    return result


@app.get("/api/health")
def health():
    status = get_engine_status()
    return {"status": "ok", "engine": status}


# ---- Paper Trading endpoints ----

from paper_trader import (
    get_all_portfolios, get_paper_trades, reset_portfolio, scan_strategy,
)

@app.get("/api/paper/portfolios")
def paper_portfolios():
    return get_all_portfolios()

@app.get("/api/paper/trades")
def paper_trades_endpoint(strategy_id: Optional[str] = None, status: Optional[str] = None, limit: int = 100):
    return get_paper_trades(strategy_id=strategy_id, status=status, limit=limit)

@app.post("/api/paper/reset/{strategy_id}")
def paper_reset(strategy_id: str):
    from paper_trader import STRATEGIES
    if strategy_id not in STRATEGIES:
        raise HTTPException(status_code=404, detail="Unknown strategy")
    ok = reset_portfolio(strategy_id)
    return {"success": ok}

@app.post("/api/paper/scan/{strategy_id}")
def paper_scan_now(strategy_id: str):
    """Manually trigger a scan for a specific paper strategy."""
    from paper_trader import STRATEGIES
    if strategy_id not in STRATEGIES:
        raise HTTPException(status_code=404, detail="Unknown strategy")
    import threading
    threading.Thread(target=scan_strategy, args=(strategy_id,), daemon=True).start()
    return {"success": True, "message": f"Scanning {strategy_id}..."}
