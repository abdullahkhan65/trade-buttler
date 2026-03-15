import yfinance as yf
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)

YAHOO_TICKERS = {
    "XAU/USD": "GC=F",
    "BTC/USD": "BTC-USD"
}

BINANCE_BASE = "https://api.binance.com/api/v3"

def fetch_gold_candles(interval="1h", limit=200):
    """Fetch XAU/USD candles from Yahoo Finance."""
    try:
        ticker = YAHOO_TICKERS["XAU/USD"]
        yf_interval_map = {
            "15m": "15m",
            "1h": "1h",
            "4h": "1h",  # yfinance doesn't have 4h, use 1h
        }
        period_map = {
            "15m": "7d",
            "1h": "30d",
            "4h": "60d",
        }
        yf_interval = yf_interval_map.get(interval, "1h")
        period = period_map.get(interval, "30d")

        ticker_obj = yf.Ticker(ticker)
        df = ticker_obj.history(period=period, interval=yf_interval)

        if df.empty:
            logger.error(f"No data returned for XAU/USD")
            return None

        df = df.reset_index()
        df = df.rename(columns={
            "Datetime": "timestamp",
            "Date": "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })

        # Ensure timestamp is timezone-naive
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize(None)

        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].tail(limit)
        df = df.dropna()
        return df
    except Exception as e:
        logger.error(f"Error fetching gold data: {e}")
        return None

def fetch_btc_candles_binance(interval="1h", limit=200):
    """Fetch BTC/USD candles from Binance."""
    try:
        binance_interval_map = {
            "15m": "15m",
            "1h": "1h",
            "4h": "4h",
        }
        b_interval = binance_interval_map.get(interval, "1h")

        url = f"{BINANCE_BASE}/klines"
        params = {
            "symbol": "BTCUSDT",
            "interval": b_interval,
            "limit": limit
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        candles = []
        for k in data:
            candles.append({
                "timestamp": pd.to_datetime(k[0], unit='ms'),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5])
            })

        df = pd.DataFrame(candles)
        return df
    except Exception as e:
        logger.error(f"Error fetching BTC Binance data: {e}")
        return fetch_btc_candles_yahoo(interval, limit)

def fetch_btc_candles_yahoo(interval="1h", limit=200):
    """Fallback: Fetch BTC/USD from Yahoo Finance."""
    try:
        ticker = YAHOO_TICKERS["BTC/USD"]
        yf_interval_map = {"15m": "15m", "1h": "1h", "4h": "1h"}
        period_map = {"15m": "7d", "1h": "30d", "4h": "60d"}
        yf_interval = yf_interval_map.get(interval, "1h")
        period = period_map.get(interval, "30d")

        ticker_obj = yf.Ticker(ticker)
        df = ticker_obj.history(period=period, interval=yf_interval)

        if df.empty:
            return None

        df = df.reset_index()
        df = df.rename(columns={
            "Datetime": "timestamp",
            "Date": "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })

        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize(None)

        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].tail(limit)
        df = df.dropna()
        return df
    except Exception as e:
        logger.error(f"Error fetching BTC Yahoo data: {e}")
        return None

def fetch_candles(symbol, interval="1h", limit=200):
    """Main dispatcher for fetching candles."""
    if symbol == "XAU/USD":
        return fetch_gold_candles(interval, limit)
    elif symbol == "BTC/USD":
        return fetch_btc_candles_binance(interval, limit)
    return None

def get_live_price(symbol):
    """Get the latest price for a symbol."""
    try:
        if symbol == "XAU/USD":
            ticker = yf.Ticker("GC=F")
            hist = ticker.history(period="1d", interval="1m")
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
        elif symbol == "BTC/USD":
            url = f"{BINANCE_BASE}/ticker/price"
            response = requests.get(url, params={"symbol": "BTCUSDT"}, timeout=5)
            if response.status_code == 200:
                return float(response.json()['price'])
    except Exception as e:
        logger.error(f"Error getting live price for {symbol}: {e}")
    return None
