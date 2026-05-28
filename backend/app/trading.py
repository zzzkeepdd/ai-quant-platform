import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from .backtest import market_snapshot
from .config import DEFAULT_MARKET_MODE, SUPPORTED_SYMBOLS
from .database import get_setting, now_iso
from .exchange import exchange_manager
from .logging_service import log_trade
from .optimizer import auto_optimize_strategy
from .risk import get_risk_rules, risk_guard


class TradingEngine:
    """模拟/实盘自动交易调度器。首版以安全模拟盘为默认。"""

    def __init__(self) -> None:
        self.running = False
        self.mode = "sandbox"
        self.position_mode = "固定"
        self.consecutive_failures = 0
        self.last_market_state = "RANGING"
        self.active_strategies: dict[str, dict[str, Any]] = {}
        self.last_iterations: dict[str, dict[str, Any]] = {}
        self._last_optimized_at: dict[str, datetime] = {}
        self.task: asyncio.Task | None = None

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "mode": self.mode,
            "position_mode": self.position_mode,
            "consecutive_failures": self.consecutive_failures,
            "market_state": self.last_market_state,
            "active_strategies": self.active_strategies,
            "last_iterations": self.last_iterations,
        }

    async def start(self, mode: str, position_mode: str, confirm: bool) -> dict[str, Any]:
        if not confirm:
            return {"ok": False, "message": "开启自动交易必须先确认风险弹窗"}
        if mode == "live" and confirm is not True:
            return {"ok": False, "message": "实盘模式需要二次确认"}
        self.mode = mode
        self.position_mode = position_mode
        self.running = True
        self.consecutive_failures = 0
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._loop())
        log_trade("WARN", "模拟盘自动交易运行中" if mode == "sandbox" else "实盘自动交易运行中")
        return {"ok": True, "message": "自动交易已启动", "status": self.status()}

    async def pause(self) -> dict[str, Any]:
        self.running = False
        log_trade("WARN", "自动交易已暂停")
        return {"ok": True, "message": "自动交易已暂停", "status": self.status()}

    async def stop(self) -> dict[str, Any]:
        self.running = False
        if self.task and not self.task.done():
            self.task.cancel()
        log_trade("WARN", "自动交易已停止")
        return {"ok": True, "message": "自动交易已停止", "status": self.status()}

    async def place_demo_test_order(
        self,
        confirm: bool,
        inst_id: str = "SOL-USDT-SWAP",
        side: str = "buy",
        size: str = "1",
        td_mode: str = "cross",
    ) -> dict[str, Any]:
        if not confirm:
            return {"ok": False, "message": "测试下单必须先确认"}
        if get_setting("market_mode", DEFAULT_MARKET_MODE) != "sandbox":
            return {"ok": False, "message": "测试下单只允许在 OKX 模拟盘模式执行"}
        if inst_id not in {"BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"}:
            return {"ok": False, "message": "测试下单仅开放 BTC/ETH/SOL USDT 永续合约"}
        if side not in {"buy", "sell"}:
            return {"ok": False, "message": "测试下单方向必须是 buy 或 sell"}
        order = {
            "instId": inst_id,
            "tdMode": td_mode,
            "side": side,
            "ordType": "market",
            "sz": size,
        }
        try:
            result = exchange_manager.place_order(order)
            positions = await exchange_manager.positions()
            message = f"OKX模拟盘测试下单成功：{inst_id} {side} {size}张"
            log_trade("INFO", message, symbol=inst_id, payload={"order": order, "response": result})
            return {"ok": True, "message": message, "order": order, "response": result, "positions": positions}
        except Exception as exc:
            failure = self.record_order_failure(inst_id, f"OKX模拟盘测试下单失败：{str(exc)[:160]}")
            return {"ok": False, "message": failure["message"], "order": order}

    async def _loop(self) -> None:
        while self.running:
            for symbol in SUPPORTED_SYMBOLS:
                await self.evaluate_symbol(symbol)
            await asyncio.sleep(30)

    async def evaluate_symbol(self, symbol: str) -> None:
        """轻量调度示例：真实订单前仍经过风控守卫。"""
        rules = get_risk_rules()
        now = datetime.now(timezone.utc)
        last_optimized = self._last_optimized_at.get(symbol)
        if not last_optimized or now - last_optimized > timedelta(minutes=5):
            optimization = auto_optimize_strategy(
                symbol,
                "15m",
                float(rules.get("principal_usdt", 10000)),
                self.mode,
            )
            row = (optimization.get("results") or [{}])[0]
            self.last_iterations[symbol] = {
                "symbol": symbol,
                "market_state": row.get("market_state"),
                "strategy": row.get("strategy"),
                "best_params": row.get("best_params", {}),
                "score": row.get("score", 0),
                "best_metrics": row.get("best_metrics", {}),
                "parameter_version": row.get("parameter_version"),
                "data_source": row.get("data_source"),
                "recommended_action": row.get("recommended_action"),
                "updated_at": row.get("updated_at", now_iso()),
            }
            self.active_strategies[symbol] = {
                "symbol": symbol,
                "market_state": row.get("market_state"),
                "strategy": row.get("strategy"),
                "parameter_version": row.get("parameter_version"),
                "best_params": row.get("best_params", {}),
                "score": row.get("score", 0),
                "best_metrics": row.get("best_metrics", {}),
                "risk_result": "待风控审核",
                "applied_to_simulation": self.mode == "sandbox",
                "updated_at": row.get("updated_at", now_iso()),
            }
            self._last_optimized_at[symbol] = now
        active = self.active_strategies.get(symbol, {})
        snapshot = market_snapshot(symbol)
        market_state = str(active.get("market_state") or "RANGING")
        self.last_market_state = market_state
        strategy = str(active.get("strategy") or "")
        switch = risk_guard.can_switch_strategy(symbol, market_state)
        if not switch.allowed:
            self.active_strategies.setdefault(symbol, active)["risk_result"] = switch.reason
            log_trade("INFO", switch.reason, symbol=symbol, strategy=strategy)
            return
        if market_state == "TREND_EXHAUSTION":
            log_trade("WARN", "趋势末端：应先平掉所有顺势仓位", symbol=symbol, strategy=strategy)
        account = await exchange_manager.account()
        market = {"last": snapshot["last"], "atr": snapshot["atr14"], "range": snapshot["atr14"]}
        risk_usdt = float(rules.get("principal_usdt", 10000)) * float(rules.get("risk_per_trade", 0.01))
        amount = max(risk_usdt / max(float(market["last"]), 1), 0.0001)
        order = {"symbol": symbol, "side": "buy", "amount": amount, "price": market["last"], "leverage": min(1, float(rules["max_leverage"]))}
        decision = risk_guard.check_order(order, account, market)
        if not decision.allowed:
            self.active_strategies.setdefault(symbol, active)["risk_result"] = decision.reason
            log_trade("WARN", decision.reason, symbol=symbol, strategy=strategy)
            return
        parameter_version = str(active.get("parameter_version") or "manual_review")
        self.active_strategies.setdefault(symbol, active)["risk_result"] = decision.reason
        # 首版默认记录模拟订单，真实ccxt下单可在确认实盘后接入同一审核出口。
        message = "风控通过，模拟盘AI策略/参数已记录" if self.mode == "sandbox" else "实盘仅记录AI建议，等待人工确认"
        log_trade("INFO", message, symbol=symbol, strategy=strategy, payload={**(decision.adjusted_order or {}), "parameter_version": parameter_version})

    def record_order_failure(self, symbol: str, message: str) -> dict[str, Any]:
        self.consecutive_failures += 1
        log_trade("ERROR", message, symbol=symbol, payload={"failures": self.consecutive_failures})
        if self.consecutive_failures >= int(get_risk_rules()["max_consecutive_order_failures"]):
            self.running = False
            return {"paused": True, "message": "连续下单失败达到风控上限，自动交易已暂停"}
        return {"paused": False, "message": message}


trading_engine = TradingEngine()
