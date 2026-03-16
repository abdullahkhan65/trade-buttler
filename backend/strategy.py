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


# ── Fibonacci Retracement Strategy ───────────────────────────────────────────

def analyze_fibonacci(df, symbol, params=None):
    """
    Fibonacci retracement confluence strategy (XAU/USD focused).

    Identifies the most recent significant swing high/low over 50 candles,
    then waits for price to retrace into the 'golden zone' (38.2–61.8%).

    Scoring (max 9):
      3 pts — price inside 38.2–61.8% golden zone
      1 pt  — price within 1 ATR of 50% level (optimal entry)
      1 pt  — EMA20/50 trend aligned (≥0.2% separation)
      1 pt  — EMA200 macro filter
      2 pts — RSI in neutral confirmation zone (40–60)
      1 pt  — RSI momentum turning in entry direction
    """
    p = params or {}
    min_forming   = p.get("min_score_forming",   5)
    min_confirmed = p.get("min_score_confirmed",  7)
    sl_mult = p.get("atr_sl_mult", 1.5)
    tp_mult = p.get("atr_tp_mult", 3.5)

    if df is None or len(df) < 80:
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
    prev_rsi    = rsi.iloc[-2]
    curr_atr    = atr.iloc[-1]

    # Trend direction
    bullish   = curr_ema20 > curr_ema50
    direction = "BUY" if bullish else "SELL"

    # ── Find swing high/low over last 50 candles ──────────────────────────────
    lookback     = min(50, len(df) - 5)
    window_high  = high.iloc[-lookback:].max()
    window_low   = low.iloc[-lookback:].min()
    swing_range  = window_high - window_low

    if swing_range < curr_close * 0.005:   # need at least 0.5% swing
        return None

    # Fibonacci levels
    fib_382 = window_high - 0.382 * swing_range
    fib_500 = window_high - 0.500 * swing_range
    fib_618 = window_high - 0.618 * swing_range
    tolerance   = curr_atr * 0.5

    score   = 0
    reasons = []

    # 1. Golden zone (38.2–61.8%) — 3 pts
    in_golden = (fib_618 - tolerance) <= curr_close <= (fib_382 + tolerance)
    if in_golden:
        score += 3
        pct = (window_high - curr_close) / swing_range * 100
        reasons.append(f"Fib golden zone ({direction}): {pct:.1f}% retracement (38.2–61.8%)")

    # 2. Near 50% level — 1 pt bonus
    if abs(curr_close - fib_500) <= tolerance:
        score += 1
        reasons.append(f"Price at 50% Fibonacci level (${fib_500:,.2f})")

    # 3. EMA20/50 trend — 1 pt
    ema_sep_pct = abs(curr_ema20 - curr_ema50) / curr_close * 100
    aligned = (direction == "BUY" and curr_ema20 > curr_ema50) or \
              (direction == "SELL" and curr_ema20 < curr_ema50)
    if aligned and ema_sep_pct >= 0.2:
        score += 1
        reasons.append(f"EMA20/50 trend aligned ({ema_sep_pct:.2f}% sep)")

    # 4. EMA200 macro — 1 pt
    if direction == "BUY" and curr_close > curr_ema200:
        score += 1
        reasons.append("Above EMA200 (macro bullish)")
    elif direction == "SELL" and curr_close < curr_ema200:
        score += 1
        reasons.append("Below EMA200 (macro bearish)")

    # 5. RSI zone — 2 pts (neutral zone suits retracements)
    if 40 <= curr_rsi <= 60:
        score += 2
        reasons.append(f"RSI {curr_rsi:.1f} in neutral zone (40–60) — retracement confirmed")

    # 6. RSI momentum — 1 pt
    rsi_delta = curr_rsi - prev_rsi
    if direction == "BUY" and rsi_delta > 0.3:
        score += 1
        reasons.append(f"RSI turning up at fib level (+{rsi_delta:.1f})")
    elif direction == "SELL" and rsi_delta < -0.3:
        score += 1
        reasons.append(f"RSI turning down at fib level ({rsi_delta:.1f})")

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
        "symbol":      symbol,
        "signal_type": signal_type,
        "direction":   direction,
        "entry_price": round(curr_close, 2),
        "stop_loss":   round(stop_loss,  2),
        "take_profit": round(take_profit, 2),
        "confidence":  round((score / 9) * 100, 1),
        "score":       score,
        "reasons":     reasons,
        "rsi":         round(curr_rsi, 2),
        "fib_382":     round(fib_382, 2),
        "fib_500":     round(fib_500, 2),
        "fib_618":     round(fib_618, 2),
    }


# ── Smart Money: Order Blocks + Liquidity Sweeps ─────────────────────────────

def analyze_orderblock_liquidity(df, symbol, params=None):
    """
    Smart Money Concepts strategy (XAU/USD focused).

    Order Block (OB): the last bearish candle before 3+ bullish candles (demand
    zone), or last bullish candle before 3+ bearish candles (supply zone).
    When price returns to that candle's range → potential entry.

    Liquidity Sweep: a wick that pierces a recent swing high/low then closes
    back inside — indicates stop-hunt by institutional money before reversal.

    Scoring (max 9):
      3 pts — price returned to valid order block zone
      2 pts — liquidity sweep detected in last 5 candles
      1 pt  — EMA200 macro filter
      2 pts — RSI in confirmation zone
      1 pt  — RSI momentum aligned
    """
    p = params or {}
    min_forming   = p.get("min_score_forming",   5)
    min_confirmed = p.get("min_score_confirmed",  7)
    sl_mult = p.get("atr_sl_mult", 1.2)
    tp_mult = p.get("atr_tp_mult", 3.0)

    if df is None or len(df) < 60:
        return None

    opens  = df["open"]
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
    prev_rsi    = rsi.iloc[-2]
    curr_atr    = atr.iloc[-1]

    bullish   = curr_ema20 > curr_ema50
    direction = "BUY" if bullish else "SELL"

    score   = 0
    reasons = []
    ob_high = ob_low = None

    # ── 1. Find most recent Order Block (last 50 candles) ────────────────────
    lookback = min(50, len(df) - 5)
    for i in range(-lookback, -4):
        try:
            c_open  = opens.iloc[i]
            c_close = close.iloc[i]
            c_high  = high.iloc[i]
            c_low   = low.iloc[i]

            if direction == "BUY":
                # Bullish OB: a bearish candle followed by 3+ bullish candles
                is_bearish     = c_close < c_open
                next3_bullish  = all(close.iloc[i+j] > opens.iloc[i+j] for j in range(1, 4))
                if is_bearish and next3_bullish:
                    ob_high, ob_low = c_high, c_low
                    break
            else:
                # Bearish OB: a bullish candle followed by 3+ bearish candles
                is_bullish     = c_close > c_open
                next3_bearish  = all(close.iloc[i+j] < opens.iloc[i+j] for j in range(1, 4))
                if is_bullish and next3_bearish:
                    ob_high, ob_low = c_high, c_low
                    break
        except IndexError:
            continue

    if ob_high is not None:
        buf = curr_atr * 0.3
        if (ob_low - buf) <= curr_close <= (ob_high + buf):
            score += 3
            reasons.append(
                f"Price at {'bullish' if direction == 'BUY' else 'bearish'} "
                f"order block (${ob_low:,.2f}–${ob_high:,.2f})"
            )

    # ── 2. Liquidity sweep in last 5 candles ─────────────────────────────────
    swing_window = min(20, len(df) - 8)
    prior_highs  = [high.iloc[i]  for i in range(-swing_window, -6)]
    prior_lows   = [low.iloc[i]   for i in range(-swing_window, -6)]

    if prior_highs and prior_lows:
        ref_high = max(prior_highs)
        ref_low  = min(prior_lows)

        for i in range(-5, -1):
            try:
                c_high_val  = high.iloc[i]
                c_low_val   = low.iloc[i]
                c_close_val = close.iloc[i]

                if direction == "BUY" and c_low_val < ref_low and c_close_val > ref_low:
                    score += 2
                    reasons.append(f"Liquidity sweep below ${ref_low:,.2f} — stop hunt, bullish reversal")
                    break
                if direction == "SELL" and c_high_val > ref_high and c_close_val < ref_high:
                    score += 2
                    reasons.append(f"Liquidity sweep above ${ref_high:,.2f} — stop hunt, bearish reversal")
                    break
            except IndexError:
                continue

    # ── 3. EMA200 macro — 1 pt ────────────────────────────────────────────────
    if direction == "BUY" and curr_close > curr_ema200:
        score += 1
        reasons.append("Above EMA200 (macro bullish)")
    elif direction == "SELL" and curr_close < curr_ema200:
        score += 1
        reasons.append("Below EMA200 (macro bearish)")

    # ── 4. RSI confirmation — 2 pts ───────────────────────────────────────────
    if direction == "BUY" and 35 <= curr_rsi <= 60:
        score += 2
        reasons.append(f"RSI {curr_rsi:.1f} in demand zone (35–60)")
    elif direction == "SELL" and 40 <= curr_rsi <= 65:
        score += 2
        reasons.append(f"RSI {curr_rsi:.1f} in supply zone (40–65)")

    # ── 5. RSI momentum — 1 pt ────────────────────────────────────────────────
    rsi_delta = curr_rsi - prev_rsi
    if direction == "BUY" and rsi_delta > 0.2:
        score += 1
        reasons.append(f"RSI rebounding at OB (+{rsi_delta:.1f})")
    elif direction == "SELL" and rsi_delta < -0.2:
        score += 1
        reasons.append(f"RSI declining at OB ({rsi_delta:.1f})")

    if score < min_forming:
        return None

    signal_type = "confirmed" if score >= min_confirmed else "forming"

    if direction == "BUY":
        sl_base     = ob_low if ob_low is not None else curr_close
        stop_loss   = sl_base  - curr_atr * sl_mult
        take_profit = curr_close + curr_atr * tp_mult
    else:
        sl_base     = ob_high if ob_high is not None else curr_close
        stop_loss   = sl_base  + curr_atr * sl_mult
        take_profit = curr_close - curr_atr * tp_mult

    return {
        "symbol":      symbol,
        "signal_type": signal_type,
        "direction":   direction,
        "entry_price": round(curr_close, 2),
        "stop_loss":   round(stop_loss,  2),
        "take_profit": round(take_profit, 2),
        "confidence":  round((score / 9) * 100, 1),
        "score":       score,
        "reasons":     reasons,
        "rsi":         round(curr_rsi, 2),
    }
