# Trade Buttler — 24/7 Gold & Bitcoin Signal Engine

A full-stack trading signal application that monitors XAU/USD and BTC/USD 24/7, calculates multi-confluence signals, and sends email alerts when high-probability trade setups form.

## Quick Start (Mac)

### Prerequisites
- Python 3.10+
- Node.js 18+
- A Gmail account with App Password

### 1. Clone & Setup
```bash
cd /path/to/trade-buttler
cp .env.example backend/.env
```

### 2. Edit backend/.env
```
EMAIL_SENDER=your@gmail.com
EMAIL_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_RECIPIENT=alerts@gmail.com
SCAN_INTERVAL=60
```

### 3. Get Gmail App Password
1. Go to myaccount.google.com
2. Click **Security** → **2-Step Verification** (must be enabled)
3. Scroll down → **App Passwords**
4. Select "Mail" → "Mac" → **Generate**
5. Copy the 16-character password into EMAIL_PASSWORD

### 4. Run
```bash
chmod +x start.sh
./start.sh
```

Open http://localhost:5173

---

## How the Strategy Works

The engine scores each candle on 9 points:

| Check | Points |
|-------|--------|
| EMA20/50 trend alignment | 2 |
| Price above/below EMA200 | 1 |
| Fresh EMA20/50 crossover (last 3 candles) | 2 |
| RSI in ideal zone (BUY: 40-65, SELL: 35-60) | 2 |
| RSI direction matches trade direction | 1 |
| Price bounced off EMA20 (pullback entry) | 1 |

- **Score 5-6** → FORMING — email alert sent, prepare for entry
- **Score 7+** → CONFIRMED — execute email sent, high conviction

**Risk Management:** 1.5× ATR stop loss, 3.0× ATR take profit (minimum 1:2 R:R)

---

## Recording Results

After a trade closes:
1. Go to the **Signals** page
2. Click any signal card
3. Select Win or Loss, optionally enter P&L in pips
4. Click **Record Result**

After 20+ signals, the Analytics page will show win rate by symbol, helping you identify which confluence factors are most predictive.

---

## Email Alerts

**FORMING email** — amber theme, setup developing:
- Shows entry zone, SL, TP
- Lists all confluence factors
- Footer: "Setup developing, not confirmed yet"

**CONFIRMED email** — green/red theme, execute now:
- Shows exact entry, SL, TP, R:R ratio
- All confluence factors listed
- Footer: "High confluence, execute at market or limit"

---

## API Reference

| Endpoint | Description |
|----------|-------------|
| GET /api/signals | All signals (last 100) |
| GET /api/signals/live | Currently active signals |
| GET /api/stats | Win rate & P&L summary |
| GET /api/candles/{symbol} | OHLCV data for charting |
| POST /api/signals/{id}/result | Record trade outcome |
| POST /api/test-email | Send test email |
| WS /ws | Real-time WebSocket feed |
