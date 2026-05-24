from typing import Any

from .backtest import drawdown_curve, load_cached_or_synthetic, metrics_from_equity, run_backtest
from .config import STRATEGY_MAPPING
from .database import append_log, now_iso


def _classify_state(window) -> tuple[str, str]:
    vol = float(window["close"].pct_change().tail(24).std() or 0)
    trend = float(window["close"].iloc[-1] / window["close"].iloc[-48] - 1) if len(window) > 48 else 0
    if abs(trend) > 0.035 and vol > 0.006:
        return "TREND_EXHAUSTION", "趋势涨跌幅和波动同时过高，优先观察衰竭反转"
    if vol > 0.0065:
        return "HIGH_VOLATILITY", "波动率升高，优先挤压突破/波动扩张策略"
    if abs(trend) > 0.018:
        return "TRENDING", "48根趋势强度较高，优先结构突破策略"
    return "RANGING", "波动和趋势强度偏低，优先区间反转策略"


def _trade_bar(trade: dict[str, Any]) -> int:
    for key in ("entry_idx", "ei", "bar", "i"):
        if key in trade:
            return int(trade.get(key) or 0)
    return 0


def _trade_pnl_pct(trade: dict[str, Any]) -> float:
    for key in ("pnl_pct", "pnl", "return", "profit_pct"):
        if key in trade:
            return float(trade.get(key) or 0)
    return 0.0


def run_replay(
    symbol: str,
    strategy_file: str,
    candles: int,
    start_date: str | None = None,
    end_date: str | None = None,
    initial_capital: float = 10000.0,
    timeframe: str = "1h",
) -> dict[str, Any]:
    df = load_cached_or_synthetic(symbol, candles, start_date, end_date, timeframe)
    decisions: list[dict[str, Any]] = []
    strategy_switches: list[dict[str, Any]] = []
    active_by_bar: dict[int, dict[str, Any]] = {}
    current_strategy = ""
    for i in range(60, len(df), 8):
        window = df.iloc[: i + 1]
        state, reason = _classify_state(window)
        mapped = STRATEGY_MAPPING[state]
        if mapped != current_strategy:
            strategy_switches.append(
                {
                    "bar": i,
                    "time": df["timestamp"].iloc[i].isoformat() if "timestamp" in df.columns else i,
                    "market_state": state,
                    "strategy": mapped,
                    "reason": reason,
                }
            )
            current_strategy = mapped
        decisions.append(
            {
                "bar": i,
                "price": round(float(window["close"].iloc[-1]), 2),
                "market_state": state,
                "strategy": mapped,
                "parameter_version": "high_freq" if mapped == "BOS移动止损增强版.py" else "default",
                "reason": reason,
            }
        )
        active_by_bar[i] = {"strategy": mapped, "market_state": state}

    candidate_metrics: dict[str, Any] = {}
    active_trades: list[dict[str, Any]] = []
    for mapped in sorted(set(STRATEGY_MAPPING.values())):
        preset = "high_freq" if mapped == "BOS移动止损增强版.py" else "balanced"
        bt = run_backtest(mapped, symbol, candles, {"symbol": symbol}, start_date, end_date, timeframe=timeframe, initial_capital=initial_capital, preset=preset)
        candidate_metrics[mapped] = bt["metrics"]
        for trade in bt["trades"]:
            entry_idx = _trade_bar(trade)
            prior = [bar for bar in active_by_bar if bar <= entry_idx]
            active = active_by_bar[max(prior)] if prior else {"strategy": STRATEGY_MAPPING["RANGING"], "market_state": "RANGING"}
            if active["strategy"] == mapped:
                enriched = dict(trade)
                enriched["active_strategy"] = mapped
                enriched["market_state"] = active["market_state"]
                active_trades.append(enriched)

    active_trades.sort(key=_trade_bar)
    equity = [float(initial_capital)]
    for trade in active_trades:
        pnl = _trade_pnl_pct(trade)
        equity.append(equity[-1] * (1 + pnl))
    metrics = metrics_from_equity(equity, active_trades)
    active_strategy_stats: dict[str, dict[str, Any]] = {}
    for mapped in sorted(set(t["active_strategy"] for t in active_trades)):
        trades_for_strategy = [t for t in active_trades if t["active_strategy"] == mapped]
        strategy_equity = [float(initial_capital)]
        for trade in trades_for_strategy:
            strategy_equity.append(strategy_equity[-1] * (1 + _trade_pnl_pct(trade)))
        active_strategy_stats[mapped] = metrics_from_equity(strategy_equity, trades_for_strategy)
    result = {
        "symbol": symbol,
        "strategy_file": strategy_file,
        "timeframe": timeframe,
        "initial_capital": initial_capital,
        "equity": equity,
        "decisions": decisions,
        "trades": active_trades,
        "active_trades": active_trades,
        "metrics": metrics,
        "drawdown": drawdown_curve(equity),
        "strategy_switches": strategy_switches,
        "strategy_stats": active_strategy_stats,
        "active_strategy_stats": active_strategy_stats,
        "candidate_metrics": candidate_metrics,
        "date_range": {"start_date": start_date, "end_date": end_date},
    }
    append_log("replay_runs", ts=now_iso(), symbol=symbol, result=result)
    return result
