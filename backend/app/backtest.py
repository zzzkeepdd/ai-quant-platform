import itertools
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

from .config import DATA_CACHE_DIR, MARKET_DATA_DIR, SMC_RAW_DATA_DIR
from .database import append_log, get_setting, now_iso
from .strategy_loader import load_strategy


def synthetic_ohlcv(limit: int = 600, seed: int = 42) -> pd.DataFrame:
    """无真实数据时生成确定性演示行情，保证平台能离线启动。"""
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.0002, 0.015, limit)
    close = 30000 * np.exp(np.cumsum(returns))
    open_ = np.r_[close[0], close[:-1]]
    spread = np.abs(rng.normal(0.006, 0.004, limit))
    high = np.maximum(open_, close) * (1 + spread)
    low = np.minimum(open_, close) * (1 - spread)
    volume = rng.lognormal(9, 0.4, limit)
    ts = pd.date_range("2025-01-01", periods=limit, freq="h", tz="UTC")
    return pd.DataFrame({"timestamp": ts, "open": open_, "high": high, "low": low, "close": close, "volume": volume})


def _filter_by_date(df: pd.DataFrame, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
    """按前端传入的日期范围过滤真实K线。"""
    if "timestamp" not in df.columns:
        return df
    data = df.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True, errors="coerce")
    if start_date:
        data = data[data["timestamp"] >= pd.to_datetime(start_date, utc=True)]
    if end_date:
        end = pd.to_datetime(end_date, utc=True) + pd.Timedelta(days=1) - pd.Timedelta(milliseconds=1)
        data = data[data["timestamp"] <= end]
    return data


def _safe_symbol(symbol: str) -> str:
    return symbol.replace("/", "_").replace(":", "_")


def _asset(symbol: str) -> str:
    return symbol.split("/")[0].upper()


def _candidate_file_names(symbol: str, timeframe: str) -> list[str]:
    asset = _asset(symbol)
    safe = _safe_symbol(symbol)
    return [f"{asset}_USDT_{timeframe}.csv", f"{safe}_{timeframe}.csv"]


def _project_market_path(symbol: str, timeframe: str) -> Path:
    return MARKET_DATA_DIR / _candidate_file_names(symbol, timeframe)[0]


def _ensure_project_market_data(symbol: str, timeframe: str) -> Path | None:
    MARKET_DATA_DIR.mkdir(parents=True, exist_ok=True)
    project_path = _project_market_path(symbol, timeframe)
    if project_path.exists():
        return project_path
    for name in _candidate_file_names(symbol, timeframe):
        external = SMC_RAW_DATA_DIR / name
        if external.exists():
            shutil.copy2(external, project_path)
            return project_path
    legacy = DATA_CACHE_DIR / f"{_safe_symbol(symbol)}_{timeframe}.csv"
    if legacy.exists():
        shutil.copy2(legacy, project_path)
        return project_path
    return None


def _normalize_ohlcv(df: pd.DataFrame, limit: int, start_date: str | None, end_date: str | None) -> pd.DataFrame:
    data = df.copy()
    if "timestamp" not in data.columns:
        data.insert(0, "timestamp", pd.date_range("2025-01-01", periods=len(data), freq="h", tz="UTC"))
    data = _filter_by_date(data, start_date, end_date)
    cols = ["timestamp", "open", "high", "low", "close", "volume"]
    return data[cols].tail(limit).reset_index(drop=True)


def load_cached_or_synthetic(
    symbol: str,
    limit: int,
    start_date: str | None = None,
    end_date: str | None = None,
    timeframe: str = "1h",
) -> pd.DataFrame:
    asset = symbol.split("/")[0].upper()
    path = _ensure_project_market_data(symbol, timeframe)
    if path and path.exists():
        df = pd.read_csv(path)
        return _normalize_ohlcv(df, limit, start_date, end_date)

    return _normalize_ohlcv(synthetic_ohlcv(limit=limit, seed=abs(hash(f"{asset}:{timeframe}")) % 10000), limit, start_date, end_date)


def _proxy_url() -> str | None:
    proxy = get_setting("proxy", {"type": "http", "host": "127.0.0.1", "port": 7897})
    if proxy.get("type") == "none":
        return None
    return f"{proxy.get('type', 'http')}://{proxy.get('host', '127.0.0.1')}:{proxy.get('port', 7897)}"


def _okx_inst_id(symbol: str) -> str:
    base, quote = symbol.split("/")[0], symbol.split("/")[1].split(":")[0]
    return f"{base}-{quote}-SWAP"


def _okx_bar(timeframe: str) -> str:
    return {"15m": "15m", "1h": "1H"}.get(timeframe, "15m")


def fetch_okx_ohlcv(symbol: str, timeframe: str = "15m", limit: int = 300) -> pd.DataFrame:
    """从OKX公共行情接口读取最新K线，用于AI当前行情分析。"""
    proxy = _proxy_url()
    response = requests.get(
        "https://www.okx.com/api/v5/market/candles",
        params={"instId": _okx_inst_id(symbol), "bar": _okx_bar(timeframe), "limit": min(limit, 300)},
        proxies={"http": proxy, "https": proxy} if proxy else None,
        timeout=12,
    )
    data = response.json()
    if response.status_code >= 400 or data.get("code") != "0":
        raise RuntimeError(f"OKX candles failed: {data}")
    rows = list(reversed(data.get("data", [])))
    frame = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume", "vol_ccy", "vol_quote", "confirm"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"].astype("int64"), unit="ms", utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame[["timestamp", "open", "high", "low", "close", "volume"]].dropna().reset_index(drop=True)


def market_snapshot(
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
    timeframe: str = "15m",
    prefer_okx: bool = True,
) -> dict[str, Any]:
    """为DeepSeek补充OKX最新行情上下文，失败时才回退项目缓存。"""
    source = "project_cache"
    try:
        if prefer_okx and not start_date and not end_date:
            df = fetch_okx_ohlcv(symbol, timeframe, 300)
            source = "okx_public_candles"
        else:
            df = load_cached_or_synthetic(symbol, 720, start_date, end_date, timeframe)
    except Exception as exc:
        df = load_cached_or_synthetic(symbol, 720, start_date, end_date, timeframe)
        source = f"project_cache_fallback: {str(exc)[:80]}"
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    ret_24 = float(close.iloc[-1] / close.iloc[-24] - 1) if len(close) > 24 else 0.0
    ret_120 = float(close.iloc[-1] / close.iloc[-120] - 1) if len(close) > 120 else 0.0
    vol_24 = float(close.pct_change().tail(24).std() or 0.0)
    atr = float((high - low).tail(14).mean() or 0.0)
    bb_mid = float(close.tail(20).mean() or 0.0)
    bb_std = float(close.tail(20).std() or 0.0)
    bb_width = (bb_std * 4 / bb_mid) if bb_mid else 0.0
    trend = "上涨" if ret_120 > 0.03 else "下跌" if ret_120 < -0.03 else "震荡"
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "source": source,
        "last_time": df["timestamp"].iloc[-1].isoformat() if "timestamp" in df.columns and len(df) else None,
        "last": round(float(close.iloc[-1]), 4),
        "return_24h_pct": round(ret_24 * 100, 2),
        "return_120h_pct": round(ret_120 * 100, 2),
        "volatility_24h": round(vol_24, 5),
        "atr14": round(atr, 4),
        "bb_width20": round(bb_width, 5),
        "trend_hint": trend,
        "candles": len(df),
    }


def metrics_from_equity(equity: list[float], trades: list[dict[str, Any]]) -> dict[str, Any]:
    eq = pd.Series(equity, dtype="float64").replace([np.inf, -np.inf], np.nan).ffill().bfill()
    if len(eq) < 2:
        return {"return_pct": 0, "max_drawdown_pct": 0, "sharpe": 0, "trades": 0, "win_rate": 0}
    ret = eq.pct_change().fillna(0)
    drawdown = eq / eq.cummax() - 1
    sharpe = float(np.sqrt(365 * 24) * ret.mean() / ret.std()) if ret.std() > 0 else 0.0
    pnl_values: list[float] = []
    for trade in trades or []:
        try:
            pnl_values.append(float(trade.get("pnl", trade.get("profit", trade.get("return", trade.get("pnl_pct", 0))))))
        except Exception:
            continue
    wins = sum(1 for value in pnl_values if value > 0)
    return {
        "return_pct": round(float((eq.iloc[-1] / eq.iloc[0] - 1) * 100), 2),
        "profit_usdt": round(float(eq.iloc[-1] - eq.iloc[0]), 2),
        "max_drawdown_pct": round(float(drawdown.min() * 100), 2),
        "sharpe": round(sharpe, 2),
        "trades": len(trades or []),
        "win_rate": round(wins / len(pnl_values) * 100, 2) if pnl_values else 0,
    }


def drawdown_curve(equity: list[float]) -> list[float]:
    eq = pd.Series(equity, dtype="float64")
    return ((eq / eq.cummax() - 1) * 100).fillna(0).round(4).tolist()


PRESET_INFO = {
    "high_freq": ("高频", "放宽入场条件，提高交易次数。"),
    "balanced": ("平衡", "交易次数和胜率折中。"),
    "stable": ("稳健", "更严格过滤，减少交易。"),
    "conservative": ("保守", "更低风险、更少交易，适合确认策略质量。"),
}


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    merged.update(updates)
    return merged


def _strategy_presets(strategy_file: str) -> dict[str, dict[str, Any]]:
    if strategy_file == "BOS移动止损增强版.py":
        return {
            "high_freq": {"swing_lookback": 3, "n_swings": 1, "sl_buffer": 0.001, "bos_buffer": 0.0, "tp_rr": 0, "vol_filter": False, "vol_lookback": 20, "vol_mult": 0.5},
            "balanced": {"swing_lookback": 5, "n_swings": 1, "sl_buffer": 0.001, "bos_buffer": 0.001, "tp_rr": 0, "vol_filter": True, "vol_lookback": 20, "vol_mult": 1.0},
            "stable": {"swing_lookback": 5, "n_swings": 2, "sl_buffer": 0.001, "bos_buffer": 0.001, "tp_rr": 0, "vol_filter": True, "vol_lookback": 20, "vol_mult": 1.25},
            "conservative": {"swing_lookback": 7, "n_swings": 2, "sl_buffer": 0.0015, "bos_buffer": 0.0015, "tp_rr": 0, "vol_filter": True, "vol_lookback": 30, "vol_mult": 1.5},
        }
    if strategy_file == "BB挤压突破.py":
        return {
            "high_freq": {"squeeze_lb": 35, "squeeze_pct": 20, "expansion_mult": 1.0, "rr": 1.5, "confirm_bars": 0, "vol_filter": False, "vol_mult": 0, "adx_filter": False, "adx_threshold": 0},
            "balanced": {"squeeze_lb": 50, "squeeze_pct": 15, "expansion_mult": 1.2, "rr": 2.0, "confirm_bars": 0, "vol_filter": False, "vol_mult": 0, "adx_filter": False, "adx_threshold": 0},
            "stable": {"squeeze_lb": 50, "squeeze_pct": 10, "expansion_mult": 1.5, "rr": 2.5, "confirm_bars": 1, "vol_filter": True, "vol_mult": 1.0, "adx_filter": False, "adx_threshold": 0},
            "conservative": {"squeeze_lb": 80, "squeeze_pct": 8, "expansion_mult": 1.8, "rr": 2.5, "confirm_bars": 1, "vol_filter": True, "vol_mult": 1.5, "adx_filter": True, "adx_threshold": 20},
        }
    if strategy_file == "摆动点区间反转.py":
        return {
            "high_freq": {"pivot_lb": 3, "approach_ratio": 0.28, "rr_ratio": 1.2, "adx_filter": True, "adx_threshold": 28, "vol_filter": False, "vol_mult": 0},
            "balanced": {"pivot_lb": 4, "approach_ratio": 0.20, "rr_ratio": 1.5, "adx_filter": True, "adx_threshold": 25, "vol_filter": False, "vol_mult": 0},
            "stable": {"pivot_lb": 5, "approach_ratio": 0.18, "rr_ratio": 2.0, "adx_filter": True, "adx_threshold": 22, "vol_filter": False, "vol_mult": 0},
            "conservative": {"pivot_lb": 6, "approach_ratio": 0.15, "rr_ratio": 2.0, "adx_filter": True, "adx_threshold": 20, "vol_filter": True, "vol_mult": 0.5},
        }
    if strategy_file == "趋势衰竭反转.py":
        return {
            "high_freq": {"lookback": 50, "rr": 1.5, "wick_ratio": 0.3, "body_ratio": 0.35, "divergence_window": 3, "vol_filter": False, "vol_mult": 0},
            "balanced": {"lookback": 75, "rr": 2.0, "wick_ratio": 0.4, "body_ratio": 0.3, "divergence_window": 5, "vol_filter": False, "vol_mult": 0},
            "stable": {"lookback": 100, "rr": 2.0, "wick_ratio": 0.5, "body_ratio": 0.25, "divergence_window": 8, "vol_filter": False, "vol_mult": 0},
            "conservative": {"lookback": 120, "rr": 2.0, "wick_ratio": 0.5, "body_ratio": 0.2, "divergence_window": 10, "vol_filter": True, "vol_mult": 1.5},
        }
    return {}


def preset_params(strategy_file: str, preset: str | None) -> dict[str, Any]:
    presets = _strategy_presets(strategy_file)
    if not presets:
        return {}
    return dict(presets.get(preset or "balanced", presets["balanced"]))


def _jsonable(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def run_backtest(
    strategy_file: str,
    symbol: str,
    limit: int,
    params: dict[str, Any],
    start_date: str | None = None,
    end_date: str | None = None,
    timeframe: str = "1h",
    initial_capital: float = 10000.0,
    preset: str | None = None,
) -> dict[str, Any]:
    strategy = load_strategy(strategy_file)
    ohlc = load_cached_or_synthetic(symbol, limit, start_date, end_date, timeframe)
    preset_key = preset or "balanced"
    merged_params = preset_params(strategy_file, preset_key)
    merged_params.update(params or {})
    merged_params.setdefault("symbol", symbol)
    merged_params["initial_capital"] = initial_capital
    merged_params["capital"] = initial_capital
    factor_df = pd.DataFrame(index=ohlc.index)
    result = strategy.module.strategy_logic(ohlc.copy(), factor_df, merged_params)
    equity = [float(x) for x in result.get("equity", [])] or [float(initial_capital)] * len(ohlc)
    trades = [_jsonable(t) for t in result.get("trades", [])]
    metrics = metrics_from_equity(equity, trades)
    payload = {
        "strategy": strategy_file,
        "symbol": symbol,
        "timeframe": timeframe,
        "initial_capital": initial_capital,
        "preset": preset_key,
        "preset_label": PRESET_INFO.get(preset_key, ("自定义", ""))[0],
        "preset_description": PRESET_INFO.get(preset_key, ("自定义", "手动传入参数。"))[1],
        "effective_params": merged_params,
        "params": merged_params,
        "data_source": str(_project_market_path(symbol, timeframe)) if _project_market_path(symbol, timeframe).exists() else "synthetic",
        "metrics": metrics,
        "equity": equity,
        "drawdown": drawdown_curve(equity),
        "trades": trades[-200:] if isinstance(trades, list) else [],
        "date_range": {"start_date": start_date, "end_date": end_date},
    }
    append_log("backtest_runs", ts=now_iso(), strategy=strategy_file, symbol=symbol, metrics=metrics, payload=payload)
    return payload


def default_param_grid(strategy_file: str) -> dict[str, list[Any]]:
    if strategy_file == "BOS移动止损增强版.py":
        return {
            "swing_lookback": [3, 5],
            "n_swings": [1, 2],
            "bos_buffer": [0.0, 0.001],
            "vol_filter": [False, True],
            "vol_mult": [0.5, 0.75, 1.0, 1.25],
        }
    if strategy_file == "BB挤压突破.py":
        return {
            "squeeze_lb": [30, 40, 50],
            "squeeze_pct": [12, 18, 25],
            "expansion_mult": [0.9, 1.1, 1.35],
            "rr": [1.3, 1.6, 2.0],
            "confirm_bars": [0, 1],
            "vol_filter": [False, True],
        }
    if strategy_file == "摆动点区间反转.py":
        return {
            "pivot_lb": [3, 4, 5],
            "approach_ratio": [0.18, 0.24, 0.3],
            "rr_ratio": [1.1, 1.4, 1.8],
            "adx_threshold": [22, 26, 30],
            "vol_filter": [False, True],
        }
    if strategy_file == "趋势衰竭反转.py":
        return {
            "lookback": [45, 60, 80],
            "rr": [1.2, 1.6, 2.0],
            "wick_ratio": [0.25, 0.35, 0.5],
            "body_ratio": [0.25, 0.35, 0.45],
            "divergence_window": [3, 5, 8],
            "vol_filter": [False, True],
        }
    return {}


def _score(metrics: dict[str, Any]) -> float:
    trades = float(metrics.get("trades", 0) or 0)
    return_pct = float(metrics.get("return_pct", 0) or 0)
    drawdown = abs(float(metrics.get("max_drawdown_pct", 0) or 0))
    win_rate = float(metrics.get("win_rate", 0) or 0)
    trade_score = min(trades / 30.0, 1.0) * 20
    return round(return_pct + win_rate * 0.25 + trade_score - drawdown * 1.5, 4)


def _trade_count_quality(trades: int) -> str:
    if trades >= 30:
        return "充足"
    if trades >= 12:
        return "可参考"
    if trades > 0:
        return "偏少"
    return "无交易"


def _overfit_warning(rows: list[dict[str, Any]], best: dict[str, Any] | None) -> str:
    if not best:
        return "没有可评估参数，不能判断过拟合。"
    trades = int((best.get("metrics") or {}).get("trades", 0) or 0)
    if trades < 8:
        return "最优参数交易数偏少，可能是偶然样本，建议只用于模拟盘观察。"
    if rows and len(rows) > 20:
        top_scores = [float(row.get("score", 0) or 0) for row in rows[:5]]
        if max(top_scores) - min(top_scores) > 30:
            return "Top参数评分差距过大，存在过拟合风险，建议关注回撤和交易数。"
    return "未发现明显过拟合信号，但实盘前仍需人工确认。"


def iterate_parameters(
    strategy_file: str,
    symbol: str,
    timeframe: str,
    limit: int,
    initial_capital: float,
    param_grid: dict[str, list[Any]] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    grid = param_grid or default_param_grid(strategy_file)
    keys = [key for key, values in grid.items() if isinstance(values, list) and values]
    combinations = list(itertools.product(*(grid[key] for key in keys)))[:72] if keys else [()]
    rows: list[dict[str, Any]] = []
    for values in combinations:
        params = dict(zip(keys, values))
        params["symbol"] = symbol
        try:
            result = run_backtest(
                strategy_file,
                symbol,
                limit,
                params,
                start_date,
                end_date,
                timeframe=timeframe,
                initial_capital=initial_capital,
                preset="high_freq",
            )
            rows.append(
                {
                    "params": params,
                    "metrics": result["metrics"],
                    "score": _score(result["metrics"]),
                    "trades_preview": result["trades"][-5:],
                }
            )
        except Exception as exc:
            rows.append({"params": params, "metrics": {}, "score": -9999, "error": str(exc)[:160], "trades_preview": []})
    rows.sort(key=lambda item: item["score"], reverse=True)
    best = rows[0] if rows else None
    best_metrics = (best or {}).get("metrics") or {}
    best_trades = int(best_metrics.get("trades", 0) or 0)
    return {
        "strategy": strategy_file,
        "symbol": symbol,
        "timeframe": timeframe,
        "initial_capital": initial_capital,
        "objective": "综合评分=收益+胜率+交易数-回撤惩罚",
        "best": best,
        "results": rows,
        "trade_count_quality": _trade_count_quality(best_trades),
        "overfit_warning": _overfit_warning(rows, best),
        "selected_reason": (
            f"选择综合评分最高的参数；交易数{best_trades}笔，"
            f"收益{best_metrics.get('return_pct', 0)}%，"
            f"回撤{best_metrics.get('max_drawdown_pct', 0)}%，"
            f"胜率{best_metrics.get('win_rate', 0)}%。"
        )
        if best
        else "没有生成有效参数结果。",
    }
