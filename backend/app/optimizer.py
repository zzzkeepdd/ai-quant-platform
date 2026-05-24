from typing import Any

from .backtest import iterate_parameters, market_snapshot
from .config import STRATEGY_MAPPING, SUPPORTED_SYMBOLS
from .database import now_iso


def _symbols(symbol: str | list[str] | None) -> list[str]:
    if not symbol or symbol == "ALL":
        return SUPPORTED_SYMBOLS
    if isinstance(symbol, list):
        return symbol
    return [symbol]


def classify_market(snapshot: dict[str, Any]) -> dict[str, str]:
    ret_120 = float(snapshot.get("return_120h_pct", 0) or 0)
    vol_24 = float(snapshot.get("volatility_24h", 0) or 0)
    bb_width = float(snapshot.get("bb_width20", 0) or 0)
    atr = float(snapshot.get("atr14", 0) or 0)
    last = float(snapshot.get("last", 0) or 0)
    atr_pct = atr / last if last else 0
    if abs(ret_120) >= 4 and (vol_24 >= 0.006 or atr_pct >= 0.006):
        return {
            "state": "TREND_EXHAUSTION",
            "reason": "120小时涨跌幅较大且波动抬升，优先检测趋势衰竭反转。",
        }
    if vol_24 >= 0.008 or bb_width >= 0.035:
        return {
            "state": "HIGH_VOLATILITY",
            "reason": "短期波动或布林带宽度升高，优先使用波动突破策略。",
        }
    if abs(ret_120) >= 1.8:
        return {
            "state": "TRENDING",
            "reason": "120小时方向性足够明显，优先使用结构突破策略。",
        }
    return {
        "state": "RANGING",
        "reason": "方向性和波动都不极端，优先使用区间反转策略。",
    }


def auto_optimize_strategy(
    symbols: str | list[str] | None = "ALL",
    timeframe: str = "15m",
    initial_capital: float = 10000,
    mode: str = "sandbox",
    limit: int = 1200,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for symbol in _symbols(symbols):
        snapshot = market_snapshot(symbol, timeframe=timeframe, prefer_okx=True)
        classification = classify_market(snapshot)
        market_state = classification["state"]
        strategy = STRATEGY_MAPPING.get(market_state, STRATEGY_MAPPING["RANGING"])
        iteration = iterate_parameters(
            strategy,
            symbol,
            timeframe,
            limit,
            initial_capital,
            None,
        )
        best = iteration.get("best") or {}
        metrics = best.get("metrics") or {}
        applied = mode == "sandbox"
        rows.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "market_state": market_state,
                "state_reason": classification["reason"],
                "strategy": strategy,
                "best_params": best.get("params", {}),
                "best_metrics": metrics,
                "score": best.get("score", 0),
                "parameter_version": f"auto:{strategy}:{timeframe}:{round(float(best.get('score', 0) or 0), 4)}",
                "iteration": iteration,
                "market_snapshot": snapshot,
                "data_source": snapshot.get("source"),
                "recommended_action": "模拟盘可自动采用该策略和参数。" if applied else "实盘仅记录建议，等待人工确认。",
                "applied_to_simulation": applied,
                "updated_at": now_iso(),
            }
        )
    return {
        "mode": mode,
        "timeframe": timeframe,
        "initial_capital": initial_capital,
        "results": rows,
        "selected_strategies": {row["symbol"]: row["strategy"] for row in rows},
        "updated_at": now_iso(),
    }
