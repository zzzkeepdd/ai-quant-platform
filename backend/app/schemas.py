from typing import Any, Literal

from pydantic import BaseModel, Field


class SecretPayload(BaseModel):
    okx_api_key: str | None = None
    okx_secret_key: str | None = None
    okx_password: str | None = None
    deepseek_api_key: str | None = None
    proxy_type: Literal["none", "http", "socks5"] = "http"
    proxy_host: str = "127.0.0.1"
    proxy_port: int = 7897
    market_mode: Literal["sandbox", "live"] = "sandbox"


class BacktestRequest(BaseModel):
    strategy_file: str
    symbol: str = "BTC/USDT:USDT"
    timeframe: Literal["1h", "15m"] = "1h"
    limit: int = Field(default=600, ge=120, le=3000)
    start_date: str | None = None
    end_date: str | None = None
    initial_capital: float = Field(default=10000, gt=0)
    preset: Literal["high_freq", "balanced", "stable", "conservative"] | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class ParameterIterationRequest(BaseModel):
    strategy_file: str
    symbol: str = "BTC/USDT:USDT"
    timeframe: Literal["1h", "15m"] = "1h"
    limit: int = Field(default=1200, ge=120, le=3000)
    start_date: str | None = None
    end_date: str | None = None
    initial_capital: float = Field(default=10000, gt=0)
    param_grid: dict[str, list[Any]] = Field(default_factory=dict)


class AITaskRequest(BaseModel):
    symbol: str = "ALL"
    timeframe: Literal["1h", "15m"] = "15m"
    initial_capital: float = Field(default=10000, gt=0)
    market_summary: str = ""
    strategy_file: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class TradingStartRequest(BaseModel):
    mode: Literal["sandbox", "live"] = "sandbox"
    position_mode: Literal["固定", "复利", "回撤降档"] = "固定"
    confirm: bool = False


class TradingTestOrderRequest(BaseModel):
    inst_id: Literal["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"] = "SOL-USDT-SWAP"
    side: Literal["buy", "sell"] = "buy"
    size: str = Field(default="1", pattern=r"^[0-9]+(\.[0-9]+)?$")
    td_mode: Literal["cross", "isolated"] = "cross"
    confirm: bool = False


class ReplayRequest(BaseModel):
    symbol: str = "BTC/USDT:USDT"
    strategy_file: str = "BOS移动止损增强版.py"
    timeframe: Literal["1h", "15m"] = "1h"
    candles: int = Field(default=240, ge=80, le=1000)
    start_date: str | None = None
    end_date: str | None = None
    initial_capital: float = Field(default=10000, gt=0)


class RiskRulesPayload(BaseModel):
    principal_usdt: float = Field(default=10000, gt=0)
    max_leverage: float = Field(default=3, gt=0)
    risk_per_trade: float = Field(default=0.01, gt=0, le=1)
    daily_loss_circuit_breaker: float = Field(default=0.05, gt=0, le=1)
    atr_circuit_breaker_mult: float = Field(default=3.5, gt=0)
    min_notional_usdt: float = Field(default=10, gt=0)
    strategy_cooldown_hours: float = Field(default=12, ge=0)
    max_consecutive_order_failures: int = Field(default=3, ge=1)
