"""
Data fetcher — gold uses Binance PAXG/USDT (gold-backed token, tracks XAU/USD spot).
BTC uses Binance BTCUSDT directly. No yfinance dependency.
"""
import requests
import pandas as pd
import logging

logger = logging.getLogger(__name__)

BINANCE_BASE = "https://api.binance.com/api/v3"

BINANCE_INTERVAL = {"15m": "15m", "1h": "1h", "4h": "4h"}


def _binance_klines(symbol: str, interval: str, limit: int):
    """Fetch OHLCV from Binance klines endpoint. Returns DataFrame or None."""
    try:
        r = requests.get(
            f"{BINANCE_BASE}/klines",
            params={
                "symbol": symbol,
                "interval": BINANCE_INTERVAL.get(interval, "1h"),
                "limit": limit,
            },
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        df = pd.DataFrame([{
            "timestamp": pd.to_datetime(k[0], unit="ms"),
            "open":   float(k[1]),
            "high":   float(k[2]),
            "low":    float(k[3]),
            "close":  float(k[4]),
            "volume": float(k[5]),
        } for k in data])
        return df
    except Exception as e:
        logger.error(f"Binance klines {symbol} failed: {e}")
        return None


def fetch_gold_candles(interval="1h", limit=200):
    """
    XAU/USD via Binance PAXGUSDT.
    PAXG (Paxos Gold) = 1 troy oz of gold — tracks XAU/USD spot exactly.
    """
    df = _binance_klines("PAXGUSDT", interval, limit)
    if df is not None:
        logger.info(f"Gold (PAXGUSDT) data: {len(df)} candles @ ${df['close'].iloc[-1]:,.2f}")
        return df
    logger.error("Failed to fetch gold data from Binance PAXGUSDT")
    return None


def fetch_btc_candles(interval="1h", limit=200):
    """BTC/USD via Binance BTCUSDT."""
    df = _binance_klines("BTCUSDT", interval, limit)
    if df is not None:
        logger.info(f"BTC (BTCUSDT) data: {len(df)} candles @ ${df['close'].iloc[-1]:,.0f}")
        return df
    logger.error("Failed to fetch BTC data from Binance")
    return None


def fetch_candles(symbol, interval="1h", limit=200):
    if symbol == "XAU/USD":
        return fetch_gold_candles(interval, limit)
    elif symbol == "BTC/USD":
        return fetch_btc_candles(interval, limit)
    return None


def get_live_price(symbol):
    """Get latest price from Binance ticker. Never raises."""
    try:
        binance_symbol = "PAXGUSDT" if symbol == "XAU/USD" else "BTCUSDT"
        r = requests.get(
            f"{BINANCE_BASE}/ticker/price",
            params={"symbol": binance_symbol},
            timeout=5,
        )
        if r.status_code == 200:
            return float(r.json()["price"])
    except Exception as e:
        logger.error(f"get_live_price({symbol}) failed: {e}")
    return None
