import os
import sys
from pathlib import Path


# 项目根目录：backend/app/config.py -> backend -> 项目根
PROJECT_ROOT = Path(os.environ.get("AI_QUANT_PROJECT_ROOT") or getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
BACKEND_ROOT = PROJECT_ROOT / "backend"
STRATEGY_DIR = PROJECT_ROOT / "strategies"
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
BACKEND_DATA_DIR = BACKEND_ROOT / "data_cache"
DATA_CACHE_DIR = PROJECT_ROOT / "data_cache"
MARKET_DATA_DIR = BACKEND_DATA_DIR / "market_data"
SMC_RAW_DATA_DIR = Path("D:/量化平台V2/data/smc_raw")
DB_PATH = BACKEND_DATA_DIR / "quant_platform.sqlite3"
FERNET_KEY_PATH = BACKEND_DATA_DIR / ".secret.key"

APP_VERSION = "1.0.0"
SUPPORTED_SYMBOLS = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
TIMEFRAME = "1h"
DEFAULT_MARKET_MODE = "sandbox"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_DEFAULT_MODEL = "deepseek-v4-pro"
DEEPSEEK_FAST_MODEL = "deepseek-v4-flash"

STRATEGY_MAPPING = {
    "TRENDING": "BOS移动止损增强版.py",
    "RANGING": "摆动点区间反转.py",
    "HIGH_VOLATILITY": "BB挤压突破.py",
    "TREND_EXHAUSTION": "趋势衰竭反转.py",
}

RISK_RULES = {
    "principal_usdt": 10000,
    "max_leverage": 3,
    "risk_per_trade": 0.01,
    "daily_loss_circuit_breaker": 0.05,
    "atr_circuit_breaker_mult": 3.5,
    "min_notional_usdt": 10,
    "strategy_cooldown_hours": 12,
    "max_consecutive_order_failures": 3,
    "position_modes": ["固定", "复利", "回撤降档"],
}
