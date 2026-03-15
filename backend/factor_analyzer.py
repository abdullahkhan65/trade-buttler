"""
Factor Analyzer: Analyzes which confluence factors most predict wins.
Computes per-factor win rates from closed signals in the DB.
Provides factor weights that can boost/adjust the live scoring.
"""
import json
import logging
from collections import defaultdict
from typing import Dict, List, Any
from database import SessionLocal
from models import Signal

logger = logging.getLogger(__name__)


FACTOR_KEYWORDS = {
    "ema_trend":    ["EMA20 > EMA50", "EMA20 < EMA50"],
    "ema200":       ["EMA200"],
    "crossover":    ["crossover"],
    "rsi_zone":     ["RSI", "zone"],
    "rsi_dir":      ["RSI rising", "RSI falling"],
    "ema20_bounce": ["Bounced off EMA20", "Rejected at EMA20"],
}


def analyze_factors(symbol: str = None) -> Dict[str, Any]:
    """
    Analyze which factors correlate with wins.
    Returns per-factor win rates and weights.
    """
    db = SessionLocal()
    try:
        query = db.query(Signal).filter(Signal.result.in_(["win", "loss"]))
        if symbol:
            query = query.filter(Signal.symbol == symbol)
        signals = query.all()
    finally:
        db.close()

    if not signals:
        return {
            "total_closed": 0,
            "factors": {},
            "weights": {},
            "message": "Not enough closed signals for analysis. Record trade results to enable factor analysis."
        }

    # Per-factor tracking
    factor_stats = {
        k: {"wins": 0, "losses": 0, "appearances": 0}
        for k in FACTOR_KEYWORDS
    }

    for sig in signals:
        try:
            reasons = json.loads(sig.reasons) if sig.reasons else []
        except Exception:
            reasons = []

        reasons_text = " ".join(reasons).lower()
        is_win = sig.result == "win"

        for factor_key, keywords in FACTOR_KEYWORDS.items():
            # Check if any keyword appears in any reason
            matched = any(
                any(kw.lower() in r.lower() for r in reasons)
                for kw in keywords
            )
            if matched:
                factor_stats[factor_key]["appearances"] += 1
                if is_win:
                    factor_stats[factor_key]["wins"] += 1
                else:
                    factor_stats[factor_key]["losses"] += 1

    # Compute win rates and weights
    overall_wr = sum(1 for s in signals if s.result == "win") / len(signals) if signals else 0.5

    factors_out = {}
    weights = {}

    for factor, stats in factor_stats.items():
        total = stats["wins"] + stats["losses"]
        if total < 3:
            wr = overall_wr
            weight = 1.0
            confidence = "low"
        else:
            wr = stats["wins"] / total
            # Weight = ratio of factor WR to overall WR
            # 1.0 = neutral, >1.0 = bullish factor, <1.0 = weak factor
            weight = wr / overall_wr if overall_wr > 0 else 1.0
            weight = round(max(0.3, min(2.0, weight)), 3)  # clamp 0.3-2.0
            confidence = "high" if total >= 20 else "medium" if total >= 10 else "low"

        factors_out[factor] = {
            "appearances": stats["appearances"],
            "wins": stats["wins"],
            "losses": stats["losses"],
            "win_rate": round(wr * 100, 1),
            "weight": weight,
            "confidence": confidence,
        }
        weights[factor] = weight

    # Score distribution analysis
    score_stats = defaultdict(lambda: {"wins": 0, "losses": 0})
    for sig in signals:
        score_stats[sig.score]["wins" if sig.result == "win" else "losses"] += 1

    score_analysis = {
        str(score): {
            "wins": v["wins"],
            "losses": v["losses"],
            "win_rate": round(v["wins"] / (v["wins"] + v["losses"]) * 100, 1)
            if (v["wins"] + v["losses"]) > 0 else 0
        }
        for score, v in sorted(score_stats.items())
    }

    return {
        "symbol": symbol or "all",
        "total_closed": len(signals),
        "overall_win_rate": round(overall_wr * 100, 1),
        "factors": factors_out,
        "weights": weights,
        "score_analysis": score_analysis,
        "recommendation": _generate_recommendation(factors_out, overall_wr, len(signals)),
    }


def _generate_recommendation(factors: dict, overall_wr: float, total: int) -> str:
    if total < 10:
        return f"Record {10 - total} more trade results to enable reliable analysis."

    strong = [f for f, d in factors.items() if d["weight"] >= 1.3 and d["confidence"] != "low"]
    weak = [f for f, d in factors.items() if d["weight"] <= 0.7 and d["confidence"] != "low"]

    parts = []
    if strong:
        parts.append(f"Strongest predictors: {', '.join(strong)}")
    if weak:
        parts.append(f"Weakest factors: {', '.join(weak)} (consider raising min score)")
    if overall_wr >= 0.6:
        parts.append(f"Win rate {overall_wr*100:.0f}% — strategy performing well")
    elif overall_wr < 0.4:
        parts.append(f"Win rate {overall_wr*100:.0f}% — consider re-running optimizer")

    return ". ".join(parts) if parts else "Accumulate more trades for deeper analysis."


def get_adaptive_score_adjustment(symbol: str, current_score: int, reasons: List[str]) -> float:
    """
    Returns an adjusted score (float) based on factor weights.
    Used by the live engine to rank signals more accurately.
    """
    analysis = analyze_factors(symbol)
    if analysis["total_closed"] < 10:
        return float(current_score)  # not enough data, return raw score

    weights = analysis["weights"]
    reasons_text = " ".join(reasons).lower()

    adjusted = 0.0
    for factor, w in weights.items():
        keywords = FACTOR_KEYWORDS.get(factor, [])
        if any(kw.lower() in reasons_text for kw in keywords):
            adjusted += w  # add weighted contribution

    # Normalize to 0-9 scale proportionally
    raw_max_possible = len(FACTOR_KEYWORDS) * 2.0  # approximate max weight sum
    normalized = (adjusted / raw_max_possible) * 9

    # Blend 50% raw score + 50% adaptive
    blended = (current_score * 0.5) + (normalized * 0.5)
    return round(blended, 2)
