import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_atr(high, low, close, period=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()


def analyze_signal(df, symbol, params=None):
    """
    Multi-confluence scoring system (0-9 points).
    Returns signal dict or None if score < min_forming.
    """
    p = params or {}
    min_forming   = p.get("min_score_forming",   6)   # raised from 5 → 6
    min_confirmed = p.get("min_score_confirmed",  8)   # raised from 7 → 8
    sl_mult = p.get("atr_sl_mult", 1.5)
    tp_mult = p.get("atr_tp_mult", 3.0)

    if df is None or len(df) < 60:
        return None

    close  = df["close"]
    high   = df["high"]
    low    = df["low"]

    ema20  = calculate_ema(close, 20)
    ema50  = calculate_ema(close, 50)
    ema200 = calculate_ema(close, 200)
    rsi    = calculate_rsi(close, 14)
    atr    = calculate_atr(high, low, close, 14)

    curr_close  = close.iloc[-1]
    curr_ema20  = ema20.iloc[-1]
    curr_ema50  = ema50.iloc[-1]
    curr_ema200 = ema200.iloc[-1]
    curr_rsi    = rsi.iloc[-1]
    curr_atr    = atr.iloc[-1]
    prev_rsi    = rsi.iloc[-2]
    prev_close  = close.iloc[-2]
    prev_ema20  = ema20.iloc[-2]

    bullish_bias = curr_ema20 > curr_ema50
    direction    = "BUY" if bullish_bias else "SELL"

    score   = 0
    reasons = []

    # ------------------------------------------------------------------
    # 1. EMA 20/50 trend alignment — 2 points
    #    REQUIRES meaningful separation (≥0.3% of price) to count.
    #    Prevents noise from nearly-flat/crossing EMAs scoring full points.
    # ------------------------------------------------------------------
    ema_sep_pct = abs(curr_ema20 - curr_ema50) / curr_close * 100
    if ema_sep_pct >= 0.3:
        score += 2
        label = "bullish" if bullish_bias else "bearish"
        reasons.append(f"EMA20/50 {label} trend — separation {ema_sep_pct:.2f}%")
    elif ema_sep_pct >= 0.1:
        score += 1
        reasons.append(f"EMA20/50 weak trend alignment ({ema_sep_pct:.2f}% sep)")
    # else: 0 — too flat, skip

    # ------------------------------------------------------------------
    # 2. EMA 200 macro filter — 1 point
    # ------------------------------------------------------------------
    if direction == "BUY" and curr_close > curr_ema200:
        score += 1
        reasons.append("Price above EMA200 (macro bullish)")
    elif direction == "SELL" and curr_close < curr_ema200:
        score += 1
        reasons.append("Price below EMA200 (macro bearish)")

    # ------------------------------------------------------------------
    # 3. Fresh EMA 20/50 crossover in last 5 candles — 2 points
    # ------------------------------------------------------------------
    crossover_found = False
    for i in range(-6, -1):
        try:
            p20, p50 = ema20.iloc[i], ema50.iloc[i]
            n20, n50 = ema20.iloc[i + 1], ema50.iloc[i + 1]
            if direction == "BUY"  and p20 <= p50 and n20 > n50:
                crossover_found = True; break
            if direction == "SELL" and p20 >= p50 and n20 < n50:
                crossover_found = True; break
        except IndexError:
            pass

    if crossover_found:
        score += 2
        reasons.append(f"Fresh EMA20/50 {'bullish' if bullish_bias else 'bearish'} crossover (last 5 candles)")

    # ------------------------------------------------------------------
    # 4. RSI in ideal zone — 2 points (tightened zones)
    #    BUY:  45-62  (was 40-65)
    #    SELL: 38-55  (was 35-60)
    # ------------------------------------------------------------------
    rsi_buy_lo  = p.get("rsi_buy_low",   45)
    rsi_buy_hi  = p.get("rsi_buy_high",  62)
    rsi_sell_lo = p.get("rsi_sell_low",  38)
    rsi_sell_hi = p.get("rsi_sell_high", 55)

    if direction == "BUY"  and rsi_buy_lo  <= curr_rsi <= rsi_buy_hi:
        score += 2
        reasons.append(f"RSI {curr_rsi:.1f} in BUY zone ({rsi_buy_lo}-{rsi_buy_hi})")
    elif direction == "SELL" and rsi_sell_lo <= curr_rsi <= rsi_sell_hi:
        score += 2
        reasons.append(f"RSI {curr_rsi:.1f} in SELL zone ({rsi_sell_lo}-{rsi_sell_hi})")

    # ------------------------------------------------------------------
    # 5. RSI momentum aligned — 1 point
    # ------------------------------------------------------------------
    rsi_delta = curr_rsi - prev_rsi
    if direction == "BUY"  and rsi_delta >  0.5:
        score += 1
        reasons.append(f"RSI rising +{rsi_delta:.1f} (momentum confirms BUY)")
    elif direction == "SELL" and rsi_delta < -0.5:
        score += 1
        reasons.append(f"RSI falling {rsi_delta:.1f} (momentum confirms SELL)")

    # ------------------------------------------------------------------
    # 6. Price bounced off / rejected at EMA20 — 1 point
    # ------------------------------------------------------------------
    if direction == "BUY"  and prev_close <= prev_ema20 and curr_close > curr_ema20:
        score += 1
        reasons.append("Price bounced off EMA20 (pullback entry confirmed)")
    elif direction == "SELL" and prev_close >= prev_ema20 and curr_close < curr_ema20:
        score += 1
        reasons.append("Price rejected at EMA20 (pullback SELL confirmed)")

    # ------------------------------------------------------------------
    # Filter
    # ------------------------------------------------------------------
    if score < min_forming:
        return None

    signal_type = "confirmed" if score >= min_confirmed else "forming"

    if direction == "BUY":
        stop_loss   = curr_close - curr_atr * sl_mult
        take_profit = curr_close + curr_atr * tp_mult
    else:
        stop_loss   = curr_close + curr_atr * sl_mult
        take_profit = curr_close - curr_atr * tp_mult

    return {
        "symbol":       symbol,
        "signal_type":  signal_type,
        "direction":    direction,
        "entry_price":  round(curr_close, 2),
        "stop_loss":    round(stop_loss,  2),
        "take_profit":  round(take_profit, 2),
        "confidence":   round((score / 9) * 100, 1),
        "score":        score,
        "reasons":      reasons,
        "rsi":          round(curr_rsi, 2),
        "ema20":        round(curr_ema20, 2),
        "ema50":        round(curr_ema50, 2),
        "ema200":       round(curr_ema200, 2),
        "atr":          round(curr_atr, 4),
    }


# Alias used by engine.py when optimizer params are available
def analyze_signal_with_params(df, symbol, params):
    return analyze_signal(df, symbol, params)
