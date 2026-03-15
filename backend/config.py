import os
from dotenv import load_dotenv

load_dotenv()

EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", "")
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "60"))

SYMBOLS = ["XAU/USD", "BTC/USD"]
RISK_PERCENT = 1.5
ATR_SL_MULTIPLIER = 1.5
ATR_TP_MULTIPLIER = 3.0
MIN_SCORE_FORMING = 5
MIN_SCORE_CONFIRMED = 7

# Yahoo Finance tickers
YAHOO_TICKERS = {
    "XAU/USD": "GC=F",
    "BTC/USD": "BTC-USD"
}

# Binance symbols
BINANCE_SYMBOLS = {
    "BTC/USD": "BTCUSDT"
}
