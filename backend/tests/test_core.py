from fastapi.testclient import TestClient

import asyncio

from app.ai import ai_engine
from app.backtest import default_param_grid, iterate_parameters, run_backtest
from app.exchange import ExchangeManager
from app.main import app
from app.optimizer import auto_optimize_strategy
from app.replay import run_replay
from app.risk import RiskGuard, get_risk_rules, save_risk_rules
from app.secrets import delete_secret, has_secret, load_secret, save_secret
from app.strategy_loader import list_strategies, load_strategy
from app.trading import TradingEngine


def test_strategy_loader_only_four_strategies():
    strategies = list_strategies()
    assert len(strategies) == 4
    assert {s["score"] for s in strategies} == {"5/5"}
    for item in strategies:
        loaded = load_strategy(item["file"])
        assert hasattr(loaded.module, "strategy_logic")
        assert item["tags"]


def test_backtest_returns_metrics():
    result = run_backtest("BB挤压突破.py", "BTC/USDT:USDT", 200, {})
    assert "equity" in result
    assert "drawdown" in result
    assert result["metrics"]["trades"] >= 0


def test_bos_backtest_keeps_timestamp_and_initial_capital():
    result = run_backtest(
        "BOS移动止损增强版.py",
        "BTC/USDT:USDT",
        1200,
        {"symbol": "BTC/USDT:USDT"},
        initial_capital=25000,
        preset="high_freq",
    )
    assert result["equity"][0] == 25000
    assert result["metrics"]["trades"] >= 0
    if result["trades"]:
        assert "entry_time" in result["trades"][0]


def test_all_strategies_expose_effective_presets():
    files = [item["file"] for item in list_strategies()]
    for file_name in files:
        high = run_backtest(file_name, "BTC/USDT:USDT", 300, {"symbol": "BTC/USDT:USDT"}, preset="high_freq")
        stable = run_backtest(file_name, "BTC/USDT:USDT", 300, {"symbol": "BTC/USDT:USDT"}, preset="stable")
        assert high["preset_label"]
        assert high["preset_description"]
        assert high["effective_params"]
        assert high["effective_params"] != stable["effective_params"]


def test_parameter_iteration_returns_ranked_metrics():
    result = iterate_parameters(
        "BOS移动止损增强版.py",
        "BTC/USDT:USDT",
        "1h",
        1200,
        10000,
        {"n_swings": [1, 2], "vol_mult": [0.75, 1.0]},
    )
    assert len(result["results"]) >= 2
    scores = [row["score"] for row in result["results"]]
    assert scores == sorted(scores, reverse=True)
    assert {"return_pct", "max_drawdown_pct", "win_rate", "trades"} <= set(result["results"][0]["metrics"])
    assert result["trade_count_quality"]
    assert result["overfit_warning"]
    assert result["selected_reason"]


def test_all_strategies_have_param_grids():
    for item in list_strategies():
        assert default_param_grid(item["file"])


def test_auto_optimize_selects_strategy_without_manual_strategy(monkeypatch):
    def fake_snapshot(symbol, start_date=None, end_date=None, timeframe="15m", prefer_okx=True):
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "source": "okx_public_candles",
            "last_time": "2026-05-24T09:30:00+00:00",
            "last": 100,
            "return_24h_pct": 0.5,
            "return_120h_pct": 2.5,
            "volatility_24h": 0.004,
            "atr14": 1,
            "bb_width20": 0.02,
            "trend_hint": "上涨",
            "candles": 300,
        }

    def fake_iterate(strategy_file, symbol, timeframe, limit, initial_capital, param_grid=None, start_date=None, end_date=None):
        return {
            "strategy": strategy_file,
            "symbol": symbol,
            "best": {"params": {"demo": 1}, "metrics": {"trades": 20, "return_pct": 3, "win_rate": 55, "max_drawdown_pct": -1}, "score": 30},
            "results": [{"params": {"demo": 1}, "metrics": {"trades": 20, "return_pct": 3, "win_rate": 55, "max_drawdown_pct": -1}, "score": 30}],
            "trade_count_quality": "可参考",
            "overfit_warning": "未发现明显过拟合信号",
            "selected_reason": "测试选择",
        }

    monkeypatch.setattr("app.optimizer.market_snapshot", fake_snapshot)
    monkeypatch.setattr("app.optimizer.iterate_parameters", fake_iterate)
    result = auto_optimize_strategy("BTC/USDT:USDT", "15m", 10000, "sandbox")
    row = result["results"][0]
    assert row["strategy"] == "BOS移动止损增强版.py"
    assert row["best_params"] == {"demo": 1}
    assert row["applied_to_simulation"]


def test_risk_guard_blocks_hard_limits():
    guard = RiskGuard()
    decision = guard.check_order(
        {"amount": 1, "price": 100, "leverage": 4},
        {"equity": 1000, "daily_pnl": 0},
        {"last": 100, "atr": 1, "range": 1},
    )
    assert not decision.allowed
    assert "杠杆" in decision.reason

    decision = guard.check_order(
        {"amount": 0.01, "price": 100, "leverage": 1},
        {"equity": 1000, "daily_pnl": 0},
        {"last": 100, "atr": 1, "range": 1},
    )
    assert not decision.allowed
    assert "10 USDT" in decision.reason


def test_risk_rules_can_be_saved_and_used():
    original = get_risk_rules()
    try:
        save_risk_rules({"max_leverage": 2, "principal_usdt": 5000, "risk_per_trade": 0.02})
        guard = RiskGuard()
        decision = guard.check_order(
            {"amount": 1, "price": 100, "leverage": 3},
            {"equity": 5000, "daily_pnl": 0},
            {"last": 100, "atr": 1, "range": 1},
        )
        assert not decision.allowed
        assert get_risk_rules()["principal_usdt"] == 5000
    finally:
        save_risk_rules(original)


def test_trend_exhaustion_ignores_cooldown():
    guard = RiskGuard()
    assert guard.can_switch_strategy("BTC/USDT:USDT", "TRENDING").allowed
    assert guard.can_switch_strategy("BTC/USDT:USDT", "TREND_EXHAUSTION").allowed


def test_consecutive_failures_pause_trading():
    engine = TradingEngine()
    engine.running = True
    assert not engine.record_order_failure("BTC/USDT:USDT", "失败1")["paused"]
    assert not engine.record_order_failure("BTC/USDT:USDT", "失败2")["paused"]
    third = engine.record_order_failure("BTC/USDT:USDT", "失败3")
    assert third["paused"]
    assert not engine.running


def test_api_health_and_strategies():
    client = TestClient(app)
    assert client.get("/api/health").json()["ok"]
    strategies = client.get("/api/strategies").json()
    assert len(strategies) == 4


def test_settings_empty_secret_submit_does_not_clear_existing_secret():
    client = TestClient(app)
    original = load_secret("deepseek_api_key")
    try:
        save_secret("deepseek_api_key", "test-secret")
        response = client.post("/api/settings/secrets", json={"deepseek_api_key": "", "market_mode": "sandbox"})
        assert response.status_code == 200
        assert has_secret("deepseek_api_key")
        settings = client.get("/api/settings").json()
        assert settings["secrets"]["deepseek_api_key"]
    finally:
        if original:
            save_secret("deepseek_api_key", original)
        else:
            delete_secret("deepseek_api_key")


def test_okx_demo_50038_keeps_auth_ok_status():
    manager = ExchangeManager()
    manager.auth_ok = True
    manager.data_warnings = ["OKX demo余额接口不可用"]
    manager.last_error = None
    status = manager.status()
    assert status["auth_ok"]
    assert status["connected"]
    assert status["display_state"] == "模拟认证通过"


def test_ai_auth_error_is_sanitized():
    text = ai_engine._friendly_ai_error(Exception("Error code: 401 - {'error': {'message': 'Authentication Fails, Your api key is invalid'}}"))
    assert "DeepSeek 密钥无效" in text
    assert "Authentication Fails" not in text


def test_replay_returns_real_strategy_stats():
    result = run_replay(
        "ETH/USDT:USDT",
        "BOS移动止损增强版.py",
        720,
        initial_capital=15000,
        timeframe="1h",
    )
    assert result["equity"][0] == 15000
    assert "strategy_stats" in result
    assert "trades" in result
    assert "strategy_switches" in result
    assert "active_strategy_stats" in result
