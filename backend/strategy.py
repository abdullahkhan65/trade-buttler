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
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_atr(high, low, close, period=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()

def analyze_signal(df, symbol):
    """
    Multi-confluence scoring system (0-9 points).
    Returns signal dict or None if score < 5.
    """
    if df is None or len(df) < 210:
        logger.warning(f"Not enough data for {symbol}: {len(df) if df is not None else 0} candles")
        return None

    close = df['close']
    high = df['high']
    low = df['low']

    # Calculate indicators
    ema20 = calculate_ema(close, 20)
    ema50 = calculate_ema(close, 50)
    ema200 = calculate_ema(close, 200)
    rsi = calculate_rsi(close, 14)
    atr = calculate_atr(high, low, close, 14)

    # Current values
    curr_close = close.iloc[-1]
    curr_ema20 = ema20.iloc[-1]
    curr_ema50 = ema50.iloc[-1]
    curr_ema200 = ema200.iloc[-1]
    curr_rsi = rsi.iloc[-1]
    curr_atr = atr.iloc[-1]
    prev_rsi = rsi.iloc[-2] if len(rsi) > 1 else curr_rsi

    score = 0
    reasons = []

    # Determine primary direction
    bullish_bias = curr_ema20 > curr_ema50

    # === SCORING ===

    # 1. EMA 20/50 trend alignment — 2 points
    if bullish_bias:
        score += 2
        reasons.append("EMA20 > EMA50 (bullish trend)")
    else:
        score += 2
        reasons.append("EMA20 < EMA50 (bearish trend)")

    # 2. EMA 200 price position — 1 point
    if bullish_bias and curr_close > curr_ema200:
        score += 1
        reasons.append("Price above EMA200 (macro bullish)")
    elif not bullish_bias and curr_close < curr_ema200:
        score += 1
        reasons.append("Price below EMA200 (macro bearish)")

    # 3. Fresh EMA 20/50 crossover in last 3 candles — 2 points
    crossover_found = False
    for i in range(-4, -1):
        try:
            prev_20 = ema20.iloc[i]
            prev_50 = ema50.iloc[i]
            next_20 = ema20.iloc[i+1]
            next_50 = ema50.iloc[i+1]
            if bullish_bias and prev_20 <= prev_50 and next_20 > next_50:
                crossover_found = True
                break
            elif not bullish_bias and prev_20 >= prev_50 and next_20 < next_50:
                crossover_found = True
                break
        except IndexError:
            pass

    if crossover_found:
        score += 2
        direction_word = "bullish" if bullish_bias else "bearish"
        reasons.append(f"Fresh EMA20/50 {direction_word} crossover (last 3 candles)")

    # 4. RSI in ideal zone — 2 points
    direction = "BUY" if bullish_bias else "SELL"
    if direction == "BUY" and 40 <= curr_rsi <= 65:
        score += 2
        reasons.append(f"RSI {curr_rsi:.1f} in ideal BUY zone (40-65)")
    elif direction == "SELL" and 35 <= curr_rsi <= 60:
        score += 2
        reasons.append(f"RSI {curr_rsi:.1f} in ideal SELL zone (35-60)")

    # 5. RSI direction aligned — 1 point
    if direction == "BUY" and curr_rsi > prev_rsi:
        score += 1
        reasons.append("RSI rising (momentum confirms BUY)")
    elif direction == "SELL" and curr_rsi < prev_rsi:
        score += 1
        reasons.append("RSI falling (momentum confirms SELL)")

    # 6. Price bounced off EMA20 (pullback entry) — 1 point
    prev_close = close.iloc[-2]
    prev_ema20 = ema20.iloc[-2]
    if direction == "BUY" and prev_close <= prev_ema20 and curr_close > curr_ema20:
        score += 1
        reasons.append("Price bounced off EMA20 (pullback entry confirmed)")
    elif direction == "SELL" and prev_close >= prev_ema20 and curr_close < curr_ema20:
        score += 1
        reasons.append("Price rejected at EMA20 (pullback SELL confirmed)")

    # Ignore if score < 5
    if score < 5:
        return None

    # Determine signal type
    if score >= 7:
        signal_type = "confirmed"
    else:
        signal_type = "forming"

    # Entry, SL, TP
    entry_price = curr_close
    if direction == "BUY":
        stop_loss = entry_price - (curr_atr * 1.5)
        take_profit = entry_price + (curr_atr * 3.0)
    else:
        stop_loss = entry_price + (curr_atr * 1.5)
        take_profit = entry_price - (curr_atr * 3.0)

    confidence = (score / 9) * 100

    return {
        "symbol": symbol,
        "signal_type": signal_type,
        "direction": direction,
        "entry_price": round(entry_price, 2),
        "stop_loss": round(stop_loss, 2),
        "take_profit": round(take_profit, 2),
        "confidence": round(confidence, 1),
        "score": score,
        "reasons": reasons,
        "rsi": round(curr_rsi, 2),
        "ema20": round(curr_ema20, 2),
        "ema50": round(curr_ema50, 2),
        "ema200": round(curr_ema200, 2),
        "atr": round(curr_atr, 4),
    }


def analyze_signal_with_params(df, symbol, params):
    """Same as analyze_signal but uses optimizer-provided params."""
    if df is None or len(df) < 210:
        return None

    close = df['close']
    high = df['high']
    low = df['low']

    ema20 = calculate_ema(close, 20)
    ema50 = calculate_ema(close, 50)
    ema200 = calculate_ema(close, 200)
    rsi = calculate_rsi(close, 14)
    atr = calculate_atr(high, low, close, 14)

    curr_close = close.iloc[-1]
    curr_ema20 = ema20.iloc[-1]
    curr_ema50 = ema50.iloc[-1]
    curr_ema200 = ema200.iloc[-1]
    curr_rsi = rsi.iloc[-1]
    curr_atr = atr.iloc[-1]
    prev_rsi = rsi.iloc[-2] if len(rsi) > 1 else curr_rsi

    score = 0
    reasons = []
    bullish_bias = curr_ema20 > curr_ema50

    if bullish_bias:
        score += 2
        reasons.append("EMA20 > EMA50 (bullish trend)")
    else:
        score += 2
        reasons.append("EMA20 < EMA50 (bearish trend)")

    if bullish_bias and curr_close > curr_ema200:
        score += 1
        reasons.append("Price above EMA200 (macro bullish)")
    elif not bullish_bias and curr_close < curr_ema200:
        score += 1
        reasons.append("Price below EMA200 (macro bearish)")

    crossover_found = False
    for i in range(-4, -1):
        try:
            p20, p50 = ema20.iloc[i], ema50.iloc[i]
            n20, n50 = ema20.iloc[i+1], ema50.iloc[i+1]
            if bullish_bias and p20 <= p50 and n20 > n50:
                crossover_found = True
                break
            elif not bullish_bias and p20 >= p50 and n20 < n50:
                crossover_found = True
                break
        except IndexError:
            pass
    if crossover_found:
        score += 2
        reasons.append(f"Fresh EMA20/50 {'bullish' if bullish_bias else 'bearish'} crossover")

    direction = "BUY" if bullish_bias else "SELL"
    rsi_bl = params.get('rsi_buy_low', 40)
    rsi_bh = params.get('rsi_buy_high', 65)
    rsi_sl = params.get('rsi_sell_low', 35)
    rsi_sh = params.get('rsi_sell_high', 60)

    if direction == "BUY" and rsi_bl <= curr_rsi <= rsi_bh:
        score += 2
        reasons.append(f"RSI {curr_rsi:.1f} in ideal BUY zone ({rsi_bl}-{rsi_bh})")
    elif direction == "SELL" and rsi_sl <= curr_rsi <= rsi_sh:
        score += 2
        reasons.append(f"RSI {curr_rsi:.1f} in ideal SELL zone ({rsi_sl}-{rsi_sh})")

    if direction == "BUY" and curr_rsi > prev_rsi:
        score += 1
        reasons.append("RSI rising (momentum confirms BUY)")
    elif direction == "SELL" and curr_rsi < prev_rsi:
        score += 1
        reasons.append("RSI falling (momentum confirms SELL)")

    prev_close = close.iloc[-2]
    prev_ema20 = ema20.iloc[-2]
    if direction == "BUY" and prev_close <= prev_ema20 and curr_close > curr_ema20:
        score += 1
        reasons.append("Price bounced off EMA20 (pullback entry confirmed)")
    elif direction == "SELL" and prev_close >= prev_ema20 and curr_close < curr_ema20:
        score += 1
        reasons.append("Price rejected at EMA20 (pullback SELL confirmed)")

    min_forming = params.get('min_score_forming', 5)
    min_confirmed = params.get('min_score_confirmed', 7)

    if score < min_forming:
        return None

    signal_type = "confirmed" if score >= min_confirmed else "forming"

    sl_mult = params.get('atr_sl_mult', 1.5)
    tp_mult = params.get('atr_tp_mult', 3.0)

    if direction == "BUY":
        stop_loss = curr_close - curr_atr * sl_mult
        take_profit = curr_close + curr_atr * tp_mult
    else:
        stop_loss = curr_close + curr_atr * sl_mult
        take_profit = curr_close - curr_atr * tp_mult

    return {
        "symbol": symbol,
        "signal_type": signal_type,
        "direction": direction,
        "entry_price": round(curr_close, 2),
        "stop_loss": round(stop_loss, 2),
        "take_profit": round(take_profit, 2),
        "confidence": round((score / 9) * 100, 1),
        "score": score,
        "reasons": reasons,
        "rsi": round(curr_rsi, 2),
        "ema20": round(curr_ema20, 2),
        "ema50": round(curr_ema50, 2),
        "ema200": round(curr_ema200, 2),
        "atr": round(curr_atr, 4),
    }
