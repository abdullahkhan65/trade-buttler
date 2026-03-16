"""
Daily Trade Analyzer & Learning Engine
=======================================
Runs every 6 hours. Analyzes ALL closed paper trades, computes:
  - Per-strategy win rates and P&L
  - Per-factor win rates (which signal conditions actually work)
  - Score distribution for wins vs losses
  - Directional performance (BUY vs SELL)
  - Actionable recommendations to improve thresholds

Results stored in DailyAnalysisReport table and broadcast to frontend.
"""
import json
import logging
from datetime import datetime
from collections import defaultdict
from database import SessionLocal
from models import PaperTrade, DailyAnalysisReport

logger = logging.getLogger(__name__)


def _categorize_reason(reason: str) -> str:
    """Map a raw reason string to a short category label."""
    r = reason.lower()
    if "crossover" in r:                        return "EMA crossover"
    if "ema20/50" in r or "ema 20/50" in r:    return "EMA 20/50 alignment"
    if "ema200" in r or "ema 200" in r:         return "EMA200 filter"
    if "fib golden" in r or "retracement" in r: return "Fibonacci golden zone"
    if "50% fibonacci" in r or "fib_500" in r:  return "Fibonacci 50% level"
    if "order block" in r:                      return "Order Block"
    if "liquidity sweep" in r:                  return "Liquidity Sweep"
    if "rsi" in r and any(w in r for w in ["rising", "falling", "turning", "rebounding", "declining", "momentum"]):
        return "RSI momentum"
    if "rsi" in r:                              return "RSI zone"
    if "bounced" in r or "rejected" in r:       return "EMA20 bounce/rejection"
    if "macro" in r or "above ema200" in r or "below ema200" in r: return "Macro trend (EMA200)"
    return "other"


def analyze_trades():
    """
    Full analysis pass over all closed paper trades.
    Returns a report dict. Also persists a DailyAnalysisReport to DB.
    """
    db = SessionLocal()
    try:
        trades = db.query(PaperTrade).filter(PaperTrade.status == "closed").all()

        if len(trades) < 3:
            return {
                "status": "insufficient_data",
                "message": f"Only {len(trades)} closed trades — need at least 3 for meaningful analysis.",
                "total_trades": len(trades),
                "insights": [],
                "recommendations": [],
                "strategy_data": {},
                "factor_data": {},
            }

        report = {
            "generated_at": datetime.now().isoformat(),
            "total_trades_analyzed": len(trades),
            "strategy_data": {},
            "factor_data": {},
            "direction_data": {},
            "score_data": {},
            "insights": [],
            "recommendations": [],
        }

        wins_all   = [t for t in trades if t.result == "win"]
        losses_all = [t for t in trades if t.result == "loss"]
        overall_wr = len(wins_all) / len(trades) * 100

        # ── Per-strategy breakdown ────────────────────────────────────────────
        by_strat = defaultdict(list)
        for t in trades:
            by_strat[t.strategy_id].append(t)

        for sid, st in by_strat.items():
            wins   = [t for t in st if t.result == "win"]
            losses = [t for t in st if t.result == "loss"]
            pnl    = sum(t.pnl_usd or 0 for t in st)
            wr     = len(wins) / len(st) * 100 if st else 0
            report["strategy_data"][sid] = {
                "total":    len(st),
                "wins":     len(wins),
                "losses":   len(losses),
                "win_rate": round(wr, 1),
                "total_pnl": round(pnl, 2),
                "avg_win":  round(sum(t.pnl_usd or 0 for t in wins)   / len(wins),   4) if wins   else 0,
                "avg_loss": round(sum(t.pnl_usd or 0 for t in losses) / len(losses), 4) if losses else 0,
                "profit_factor": round(
                    abs(sum(t.pnl_usd or 0 for t in wins)) /
                    max(abs(sum(t.pnl_usd or 0 for t in losses)), 0.0001), 2
                ),
            }

        # ── Per-factor win rates ──────────────────────────────────────────────
        factor_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0.0})
        for t in trades:
            reasons = json.loads(t.reasons) if t.reasons else []
            for reason in reasons:
                cat = _categorize_reason(reason)
                if t.result == "win":
                    factor_stats[cat]["wins"] += 1
                else:
                    factor_stats[cat]["losses"] += 1
                factor_stats[cat]["pnl"] += (t.pnl_usd or 0)

        for cat, s in factor_stats.items():
            total = s["wins"] + s["losses"]
            if total >= 2:
                report["factor_data"][cat] = {
                    "occurrences": total,
                    "wins":        s["wins"],
                    "losses":      s["losses"],
                    "win_rate":    round(s["wins"] / total * 100, 1),
                    "pnl":         round(s["pnl"], 2),
                }

        # ── Direction performance (BUY vs SELL) ───────────────────────────────
        for direction in ("BUY", "SELL"):
            dt = [t for t in trades if t.direction == direction]
            if dt:
                dw = [t for t in dt if t.result == "win"]
                report["direction_data"][direction] = {
                    "total":    len(dt),
                    "wins":     len(dw),
                    "win_rate": round(len(dw) / len(dt) * 100, 1),
                    "pnl":      round(sum(t.pnl_usd or 0 for t in dt), 2),
                }

        # ── Score distribution ────────────────────────────────────────────────
        win_scores  = [t.score for t in wins_all  if t.score is not None]
        loss_scores = [t.score for t in losses_all if t.score is not None]
        report["score_data"] = {
            "avg_win_score":  round(sum(win_scores)  / len(win_scores),  2) if win_scores  else None,
            "avg_loss_score": round(sum(loss_scores) / len(loss_scores), 2) if loss_scores else None,
            "min_win_score":  min(win_scores)  if win_scores  else None,
            "max_loss_score": max(loss_scores) if loss_scores else None,
        }

        # ── Generate insights ─────────────────────────────────────────────────
        insights = []
        insights.append(f"Overall: {len(trades)} closed trades — {overall_wr:.0f}% win rate")

        # Best / worst strategy
        ranked = sorted(report["strategy_data"].items(), key=lambda x: x[1]["win_rate"], reverse=True)
        for sid, sd in ranked:
            if sd["total"] >= 2:
                pf_note = f", PF {sd['profit_factor']:.2f}" if sd["profit_factor"] else ""
                insights.append(
                    f"{sid}: {sd['win_rate']}% win rate ({sd['wins']}W/{sd['losses']}L"
                    f", PnL ${sd['total_pnl']:+.2f}{pf_note})"
                )

        # Score insight
        sd = report["score_data"]
        if sd["avg_win_score"] and sd["avg_loss_score"]:
            insights.append(
                f"Score: winners avg {sd['avg_win_score']:.1f}/9 vs losers avg {sd['avg_loss_score']:.1f}/9"
            )
            if sd["avg_win_score"] > sd["avg_loss_score"] + 0.5:
                insights.append("Higher scores strongly correlate with wins — raising thresholds could help")

        # Direction insight
        for d, dd in report["direction_data"].items():
            if dd["total"] >= 3:
                status = "performing well" if dd["win_rate"] >= 55 else "underperforming"
                insights.append(f"{d} trades {status}: {dd['win_rate']}% win rate ({dd['total']} trades)")

        # Top factors
        top_factors = sorted(
            [(k, v) for k, v in report["factor_data"].items() if v["occurrences"] >= 2],
            key=lambda x: x[1]["win_rate"], reverse=True
        )
        if top_factors:
            best = top_factors[0]
            insights.append(f"Best signal factor: '{best[0]}' → {best[1]['win_rate']}% win rate ({best[1]['occurrences']} trades)")
        if len(top_factors) > 1:
            worst = top_factors[-1]
            if worst[1]["win_rate"] < 40:
                insights.append(f"Weakest factor: '{worst[0]}' → only {worst[1]['win_rate']}% win rate ({worst[1]['occurrences']} trades)")

        report["insights"] = insights

        # ── Generate recommendations ──────────────────────────────────────────
        recs = []

        if overall_wr < 40 and len(trades) >= 5:
            recs.append(
                "Win rate below 40% — run Strategy Lab optimizer on both symbols to recalibrate "
                "RSI zones and EMA separation thresholds"
            )
        elif overall_wr >= 65:
            recs.append("Win rate above 65% — system is performing well. Maintain current parameters.")

        # Recommend pausing losing direction
        for d, dd in report["direction_data"].items():
            if dd["total"] >= 4 and dd["win_rate"] < 30:
                recs.append(
                    f"PAUSE {d} signals — only {dd['win_rate']}% win rate over {dd['total']} trades. "
                    f"Market structure likely opposes {d} entries currently."
                )

        # Factor-level recommendations
        for cat, s in report["factor_data"].items():
            if s["occurrences"] >= 3 and s["win_rate"] <= 30:
                recs.append(
                    f"'{cat}' condition has only {s['win_rate']}% win rate — "
                    f"consider removing it from scoring or reducing its weight"
                )
            elif s["occurrences"] >= 3 and s["win_rate"] >= 80:
                recs.append(
                    f"'{cat}' is a strong predictor ({s['win_rate']}% win rate) — "
                    f"consider requiring it as a mandatory condition"
                )

        # Score threshold recommendation
        if sd["avg_win_score"] and sd["avg_loss_score"] and sd["avg_win_score"] > sd["avg_loss_score"] + 1:
            threshold = round(sd["avg_win_score"] - 0.5)
            recs.append(
                f"Winning trades average {sd['avg_win_score']:.1f}/9 vs losing {sd['avg_loss_score']:.1f}/9 — "
                f"consider raising min_confirmed to {int(threshold)} to filter weak entries"
            )

        if not recs:
            recs.append("No major parameter changes recommended at this time. Continue monitoring.")

        report["recommendations"] = recs

        # ── Persist to DB ─────────────────────────────────────────────────────
        db.add(DailyAnalysisReport(
            report_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            total_trades=len(trades),
            insights=json.dumps(insights),
            recommendations=json.dumps(recs),
            strategy_data=json.dumps(report["strategy_data"]),
            factor_data=json.dumps(report["factor_data"]),
        ))
        db.commit()

        logger.info(f"[Analyzer] Report generated: {len(trades)} trades, {overall_wr:.0f}% win rate, {len(insights)} insights")
        return report

    except Exception as e:
        logger.error(f"[Analyzer] Error during analysis: {e}")
        return {"status": "error", "message": str(e), "insights": [], "recommendations": []}
    finally:
        db.close()


def get_latest_report():
    db = SessionLocal()
    try:
        r = db.query(DailyAnalysisReport).order_by(DailyAnalysisReport.created_at.desc()).first()
        if not r:
            return None
        return {
            "id":              r.id,
            "report_date":     r.report_date,
            "total_trades":    r.total_trades,
            "insights":        json.loads(r.insights)       if r.insights       else [],
            "recommendations": json.loads(r.recommendations) if r.recommendations else [],
            "strategy_data":   json.loads(r.strategy_data)  if r.strategy_data  else {},
            "factor_data":     json.loads(r.factor_data)    if r.factor_data    else {},
            "created_at":      r.created_at.isoformat()     if r.created_at     else None,
        }
    finally:
        db.close()


def get_all_reports(limit=20):
    db = SessionLocal()
    try:
        rows = db.query(DailyAnalysisReport).order_by(DailyAnalysisReport.created_at.desc()).limit(limit).all()
        return [{
            "id":           r.id,
            "report_date":  r.report_date,
            "total_trades": r.total_trades,
            "created_at":   r.created_at.isoformat() if r.created_at else None,
        } for r in rows]
    finally:
        db.close()
