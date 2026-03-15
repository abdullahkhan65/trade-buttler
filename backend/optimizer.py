"""
Strategy Optimizer: Runs backtests across parameter grids to find best-performing
configuration per symbol. Stores results and provides optimal params to the live engine.
"""
import json
import logging
import os
from itertools import product
from typing import Dict, Any, List
from backtester import run_backtest, BacktestResult

logger = logging.getLogger(__name__)

OPTIMIZER_RESULTS_FILE = "optimizer_results.json"

# Parameter grid to search
PARAM_GRID = {
    "rsi_buy_low":       [35, 40, 45],
    "rsi_buy_high":      [60, 65, 70],
    "rsi_sell_low":      [30, 35, 40],
    "rsi_sell_high":     [55, 60, 65],
    "min_score_forming": [5, 6],
    "min_score_confirmed": [7, 8],
    "atr_sl_mult":       [1.0, 1.5, 2.0],
    "atr_tp_mult":       [2.0, 3.0, 4.0],
}

DEFAULT_PARAMS = {
    "rsi_buy_low": 40, "rsi_buy_high": 65,
    "rsi_sell_low": 35, "rsi_sell_high": 60,
    "min_score_forming": 5, "min_score_confirmed": 7,
    "atr_sl_mult": 1.5, "atr_tp_mult": 3.0,
}

# In-memory best params cache
_best_params: Dict[str, Dict[str, Any]] = {}


def _score_result(result: BacktestResult) -> float:
    """Composite score: win_rate * profit_factor * (1 + sharpe*0.1), penalize < 10 trades."""
    if len(result.closed) < 10:
        return 0.0
    wr = result.win_rate / 100
    pf = min(result.profit_factor, 5.0)  # cap
    sharpe = max(result.sharpe, 0)
    return wr * pf * (1 + sharpe * 0.1)


def optimize_symbol(symbol: str, interval: str = "1h", quick: bool = False) -> Dict[str, Any]:
    """
    Run grid search over param combinations.
    quick=True uses a reduced grid for faster execution.
    """
    logger.info(f"Starting optimization for {symbol} {interval}...")

    if quick:
        # Reduced grid for quick runs
        grid = {
            "rsi_buy_low":       [38, 43],
            "rsi_buy_high":      [62, 67],
            "rsi_sell_low":      [33, 38],
            "rsi_sell_high":     [57, 62],
            "min_score_forming": [5],
            "min_score_confirmed": [7],
            "atr_sl_mult":       [1.5],
            "atr_tp_mult":       [3.0],
        }
    else:
        grid = PARAM_GRID

    keys = list(grid.keys())
    values = list(grid.values())
    combinations = list(product(*values))

    best_score = -1.0
    best_params = DEFAULT_PARAMS.copy()
    best_summary = None
    all_results = []

    for combo in combinations:
        params = dict(zip(keys, combo))
        # Skip invalid RSI configs
        if params["rsi_buy_low"] >= params["rsi_buy_high"]:
            continue
        if params["rsi_sell_low"] >= params["rsi_sell_high"]:
            continue
        if params["atr_tp_mult"] <= params["atr_sl_mult"]:
            continue

        result = run_backtest(symbol, interval, params, limit=500)
        score = _score_result(result)

        summary = {
            "params": params,
            "score": round(score, 4),
            "win_rate": round(result.win_rate, 2),
            "profit_factor": round(result.profit_factor, 2),
            "sharpe": round(result.sharpe, 3),
            "total_trades": result.total,
            "closed_trades": len(result.closed),
            "avg_r": round(result.avg_r, 3),
            "max_drawdown_r": round(result.max_drawdown, 3),
        }
        all_results.append(summary)

        if score > best_score:
            best_score = score
            best_params = params.copy()
            best_summary = summary

    # Sort all results
    all_results.sort(key=lambda x: x['score'], reverse=True)

    output = {
        "symbol": symbol,
        "interval": interval,
        "best_params": best_params,
        "best_score": round(best_score, 4),
        "best_summary": best_summary,
        "top_10": all_results[:10],
        "total_combinations_tested": len(all_results),
    }

    # Update in-memory cache
    _best_params[symbol] = best_params

    # Persist to disk
    _save_results(symbol, output)

    logger.info(
        f"Optimization done for {symbol}: best WR={best_summary['win_rate'] if best_summary else 0}%, "
        f"PF={best_summary['profit_factor'] if best_summary else 0}"
    )
    return output


def get_best_params(symbol: str) -> Dict[str, Any]:
    """Return best params for symbol, loading from disk if needed."""
    if symbol in _best_params:
        return _best_params[symbol]

    # Try load from disk
    saved = _load_results()
    if symbol in saved:
        params = saved[symbol].get("best_params", DEFAULT_PARAMS)
        _best_params[symbol] = params
        return params

    return DEFAULT_PARAMS.copy()


def get_all_optimization_results() -> Dict[str, Any]:
    """Return all saved optimization results."""
    return _load_results()


def _save_results(symbol: str, data: Dict[str, Any]):
    existing = _load_results()
    existing[symbol] = data
    try:
        with open(OPTIMIZER_RESULTS_FILE, 'w') as f:
            json.dump(existing, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save optimizer results: {e}")


def _load_results() -> Dict[str, Any]:
    if not os.path.exists(OPTIMIZER_RESULTS_FILE):
        return {}
    try:
        with open(OPTIMIZER_RESULTS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}
