from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import RISK_RULES
from .database import get_setting, set_setting


def get_risk_rules() -> dict[str, Any]:
    saved = get_setting("risk_rules", {})
    merged = dict(RISK_RULES)
    if isinstance(saved, dict):
        merged.update(saved)
    merged["position_modes"] = RISK_RULES["position_modes"]
    return merged


def save_risk_rules(rules: dict[str, Any]) -> dict[str, Any]:
    merged = get_risk_rules()
    for key, value in rules.items():
        if key in merged and value is not None:
            merged[key] = value
    set_setting("risk_rules", merged)
    return merged


@dataclass
class RiskDecision:
    allowed: bool
    reason: str
    adjusted_order: dict[str, Any] | None = None


class RiskGuard:
    """所有风控硬规则集中在这里，AI和策略都不能绕过。"""

    def __init__(self) -> None:
        self.daily_start_equity: float | None = None
        self.last_strategy_switch: dict[str, datetime] = {}

    def risk_status(self) -> dict[str, Any]:
        return {
            "rules": get_risk_rules(),
            "daily_start_equity": self.daily_start_equity,
            "cooldowns": {k: v.isoformat() for k, v in self.last_strategy_switch.items()},
        }

    def check_order(self, order: dict[str, Any], account: dict[str, Any], market: dict[str, Any]) -> RiskDecision:
        rules = get_risk_rules()
        leverage = float(order.get("leverage", 1))
        notional = abs(float(order.get("amount", 0)) * float(order.get("price", market.get("last", 0) or 0)))
        equity = float(account.get("equity", account.get("total", 0) or 0))
        daily_pnl = float(account.get("daily_pnl", 0) or 0)

        if leverage > float(rules["max_leverage"]):
            return RiskDecision(False, f"杠杆超过上限{rules['max_leverage']}x")
        if notional < float(rules["min_notional_usdt"]):
            return RiskDecision(False, f"订单名义价值低于最小仓位{rules['min_notional_usdt']} USDT")
        if equity > 0 and daily_pnl <= -equity * float(rules["daily_loss_circuit_breaker"]):
            return RiskDecision(False, f"单日亏损达到{float(rules['daily_loss_circuit_breaker']) * 100:.1f}%，触发熔断")
        atr = float(market.get("atr", 0) or 0)
        last = float(market.get("last", 0) or 0)
        candle_range = float(market.get("range", 0) or 0)
        if atr > 0 and candle_range > atr * float(rules["atr_circuit_breaker_mult"]):
            return RiskDecision(False, "ATR异常波动熔断，暂停开仓")
        if last <= 0:
            return RiskDecision(False, "市场价格无效，禁止下单")
        return RiskDecision(True, "风控审核通过", order)

    def can_switch_strategy(self, symbol: str, new_state: str) -> RiskDecision:
        rules = get_risk_rules()
        if new_state == "TREND_EXHAUSTION":
            self.last_strategy_switch[symbol] = datetime.now(timezone.utc)
            return RiskDecision(True, "趋势末端信号无视冷却期，并触发顺势仓位平仓")
        last = self.last_strategy_switch.get(symbol)
        if not last:
            self.last_strategy_switch[symbol] = datetime.now(timezone.utc)
            return RiskDecision(True, "首次策略选择通过")
        cooldown = timedelta(hours=float(rules["strategy_cooldown_hours"]))
        if datetime.now(timezone.utc) - last < cooldown:
            return RiskDecision(False, f"策略切换冷却期{rules['strategy_cooldown_hours']}小时内，保持当前策略")
        self.last_strategy_switch[symbol] = datetime.now(timezone.utc)
        return RiskDecision(True, "策略冷却期已结束，允许切换")


risk_guard = RiskGuard()
