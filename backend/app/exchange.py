import base64
import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode

import requests

from .config import DEFAULT_MARKET_MODE, SUPPORTED_SYMBOLS
from .database import get_setting
from .logging_service import log_system, safe_payload
from .risk import get_risk_rules
from .secrets import has_secret, load_secret


class ExchangeManager:
    """OKX连接管理器，真实环境有ccxt就连OKX，缺配置时返回清晰状态。"""

    def __init__(self) -> None:
        self.mode = DEFAULT_MARKET_MODE
        self.last_error: str | None = None
        self.auth_ok = False
        self.data_warnings: list[str] = []

    def _is_demo_unavailable(self, exc: Exception) -> bool:
        text = str(exc)
        return "50038" in text or "unavailable in demo trading" in text.lower()

    def status(self) -> dict[str, Any]:
        configured = has_secret("okx_api_key") and has_secret("okx_secret_key") and has_secret("okx_password")
        mode = get_setting("market_mode", self.mode)
        if not configured:
            state = "not_configured"
            display_state = "未配置"
            connected = False
        elif self.last_error:
            state = "error"
            display_state = self.last_error.split("：", 1)[0]
            connected = False
        elif self.auth_ok and mode == "sandbox":
            state = "demo_auth_ok"
            display_state = "模拟认证通过"
            connected = True
        elif self.auth_ok:
            state = "connected"
            display_state = "实盘已连接"
            connected = True
        else:
            state = "configured"
            display_state = "已配置待诊断"
            connected = False
        return {
            "exchange": "OKX",
            "connected": connected,
            "configured": configured,
            "auth_ok": self.auth_ok,
            "state": state,
            "display_state": display_state,
            "mode": mode,
            "symbols": SUPPORTED_SYMBOLS,
            "last_error": self.last_error,
            "data_warnings": self.data_warnings[-6:],
        }

    def _proxy_url(self) -> str | None:
        proxy = get_setting("proxy", {"type": "http", "host": "127.0.0.1", "port": 7897})
        if proxy.get("type") == "none":
            return None
        scheme = proxy.get("type", "http")
        return f"{scheme}://{proxy.get('host', '127.0.0.1')}:{proxy.get('port', 7897)}"

    def _client(self) -> Any:
        try:
            import ccxt
        except Exception as exc:
            raise RuntimeError("未安装ccxt，请先安装后端依赖") from exc
        api_key = load_secret("okx_api_key")
        secret = load_secret("okx_secret_key")
        password = load_secret("okx_password")
        if not api_key or not secret or not password:
            raise RuntimeError("OKX API Key、Secret或Passphrase尚未配置")
        proxy = self._proxy_url()
        options: dict[str, Any] = {
            "apiKey": api_key,
            "secret": secret,
            "password": password,
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        }
        if get_setting("market_mode", DEFAULT_MARKET_MODE) == "sandbox":
            # OKX模拟盘使用x-simulated-trading头；保留set_sandbox_mode兼容ccxt实现。
            options["headers"] = {"x-simulated-trading": "1"}
        if proxy:
            options["proxies"] = {"http": proxy, "https": proxy}
        client = ccxt.okx(options)
        return client

    def _signed_request(self, method: str, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        api_key = load_secret("okx_api_key")
        secret = load_secret("okx_secret_key")
        password = load_secret("okx_password")
        if not api_key or not secret or not password:
            raise RuntimeError("OKX API Key、Secret或Passphrase尚未配置")
        query = f"?{urlencode(params)}" if params else ""
        body = ""
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        prehash = f"{timestamp}{method.upper()}{path}{query}{body}"
        signature = base64.b64encode(hmac.new(secret.encode(), prehash.encode(), hashlib.sha256).digest()).decode()
        headers = {
            "OK-ACCESS-KEY": api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": password,
            "Content-Type": "application/json",
        }
        if get_setting("market_mode", DEFAULT_MARKET_MODE) == "sandbox":
            headers["x-simulated-trading"] = "1"
        response = requests.request(
            method.upper(),
            f"https://www.okx.com{path}{query}",
            headers=headers,
            data=body,
            proxies=self._requests_proxies(),
            timeout=15,
        )
        data = response.json()
        if response.status_code >= 400 or data.get("code") not in (None, "0"):
            raise RuntimeError(f"OKX {path} failed: {data}")
        return data

    def _requests_proxies(self) -> dict[str, str] | None:
        proxy = self._proxy_url()
        return {"http": proxy, "https": proxy} if proxy else None

    def _public_client(self) -> Any:
        try:
            import ccxt
        except Exception as exc:
            raise RuntimeError("未安装ccxt，请先安装后端依赖") from exc
        options: dict[str, Any] = {"enableRateLimit": True, "options": {"defaultType": "swap"}}
        proxy = self._proxy_url()
        if proxy:
            options["proxies"] = {"http": proxy, "https": proxy}
        return ccxt.okx(options)

    def classify_error(self, exc: Exception) -> str:
        text = str(exc)
        if "Authentication" in text or "Invalid Sign" in text or "api key" in text.lower():
            return "认证失败：请检查OKX API Key、Secret和Passphrase。"
        if self._is_demo_unavailable(exc):
            return "模拟盘接口限制：OKX demo 当前不支持该数据接口。"
        if "timeout" in text.lower() or "timed out" in text.lower():
            return "连接超时：请检查代理、网络或OKX服务状态。"
        if "proxy" in text.lower() or "connection" in text.lower():
            return "网络连接失败：请检查HTTP/SOCKS5代理配置。"
        return f"未知连接错误：{text[:160]}"

    async def test_connection(self) -> dict[str, Any]:
        diagnosis = await self.diagnose()
        ok = bool(diagnosis.get("private_auth", {}).get("ok"))
        return {"ok": ok, "message": diagnosis["recommended_action"], "diagnosis": diagnosis}

    async def diagnose(self) -> dict[str, Any]:
        self.data_warnings = []
        mode = get_setting("market_mode", self.mode)
        configured = has_secret("okx_api_key") and has_secret("okx_secret_key") and has_secret("okx_password")
        result: dict[str, Any] = {
            "mode": mode,
            "configured": configured,
            "public_market": {"ok": False},
            "private_auth": {"ok": False},
            "balance": {"ok": False},
            "positions": {"ok": False},
            "orders": {"ok": False},
            "permissions": {"read": False, "trade": False},
            "warnings": [],
            "recommended_action": "",
        }
        try:
            public_client = self._public_client()
            ticker = public_client.fetch_ticker("BTC/USDT:USDT")
            result["public_market"] = {"ok": True, "last": ticker.get("last"), "symbol": "BTC/USDT:USDT"}
        except Exception as exc:
            result["public_market"] = {"ok": False, "message": self.classify_error(exc)}
            result["warnings"].append(result["public_market"]["message"])

        if not configured:
            self.auth_ok = False
            self.last_error = "OKX API Key、Secret或Passphrase尚未配置"
            result["recommended_action"] = "请先在系统设置保存 OKX API Key、Secret 和 Passphrase。"
            return result

        try:
            config = self._signed_request("GET", "/api/v5/account/config")
            self.auth_ok = True
            self.last_error = None
            result["private_auth"] = {"ok": True, "account_config": safe_payload(config)}
        except Exception as exc:
            self.auth_ok = False
            self.last_error = self.classify_error(exc)
            log_system("ERROR", self.last_error)
            result["private_auth"] = {"ok": False, "message": self.last_error}
            result["recommended_action"] = self.last_error
            return result

        checks = [
            ("balance", lambda: self._signed_request("GET", "/api/v5/account/balance")),
            ("funding_balance", lambda: self._signed_request("GET", "/api/v5/asset/balances")),
            ("positions", lambda: self._signed_request("GET", "/api/v5/account/positions")),
            ("orders", lambda: self._signed_request("GET", "/api/v5/trade/orders-pending")),
        ]
        for key, fn in checks:
            try:
                data = fn()
                result[key] = {"ok": True, "sample": safe_payload(data)}
            except Exception as exc:
                if self._is_demo_unavailable(exc) and mode == "sandbox":
                    warning = f"OKX demo {key} 接口不可用，认证仍然有效。"
                    result[key] = {"ok": False, "demo_unavailable": True, "message": warning}
                    result["warnings"].append(warning)
                    self.data_warnings.append(warning)
                else:
                    message = self.classify_error(exc)
                    result[key] = {"ok": False, "message": message}
                    result["warnings"].append(message)

        result["permissions"] = {
            "read": bool(result["private_auth"]["ok"]),
            "trade": bool(result["private_auth"]["ok"]),
        }
        if mode == "sandbox":
            if result.get("balance", {}).get("ok"):
                result["recommended_action"] = "OKX 模拟盘认证通过，已读取 OKX 模拟盘交易账户资金、持仓和挂单。"
            else:
                result["recommended_action"] = "OKX 模拟盘认证通过，但余额接口未返回成功；请查看诊断步骤里的具体限制。"
        else:
            private_data_ok = any(bool(result[key].get("ok")) for key in ("balance", "positions", "orders"))
            result["recommended_action"] = "OKX 实盘已连接。" if private_data_ok else "OKX 已认证，但实盘私有数据接口未返回成功，请检查 API 权限。"
        log_system("INFO", "OKX诊断完成", safe_payload({"mode": mode, "auth_ok": self.auth_ok, "warnings": result["warnings"]}))
        return result

    async def account(self) -> dict[str, Any]:
        try:
            balance = self._signed_request("GET", "/api/v5/account/balance")
            funding = self._signed_request("GET", "/api/v5/asset/balances")
            self.auth_ok = True
            self.last_error = None
            account = (balance.get("data") or [{}])[0]
            details = account.get("details") or []
            total_eq = float(account.get("totalEq") or 0)
            usdt = next((item for item in details if item.get("ccy") == "USDT"), {})
            total_usdt = float(usdt.get("eq") or usdt.get("cashBal") or total_eq or 0)
            return {
                "equity": total_usdt,
                "total": total_usdt,
                "total_eq_usd": total_eq,
                "auth_ok": True,
                "source": "okx_demo" if get_setting("market_mode", DEFAULT_MARKET_MODE) == "sandbox" else "okx_live",
                "details": details,
                "funding_assets": funding.get("data", []),
                "raw": balance,
            }
        except Exception as exc:
            self.auth_ok = False
            self.last_error = self.classify_error(exc)
            return {"equity": 0, "total": 0, "error": self.last_error}

    async def positions(self) -> list[dict[str, Any]]:
        try:
            data = self._signed_request("GET", "/api/v5/account/positions")
            self.auth_ok = True
            return data.get("data", [])
        except Exception as exc:
            if self._is_demo_unavailable(exc) and self.auth_ok:
                warning = "OKX demo持仓接口不可用。"
                if warning not in self.data_warnings:
                    self.data_warnings.append(warning)
            else:
                self.last_error = self.classify_error(exc)
            return []

    async def orders(self) -> list[dict[str, Any]]:
        try:
            data = self._signed_request("GET", "/api/v5/trade/orders-pending")
            self.auth_ok = True
            return data.get("data", [])
        except Exception as exc:
            if self._is_demo_unavailable(exc) and self.auth_ok:
                warning = "OKX demo挂单接口不可用。"
                if warning not in self.data_warnings:
                    self.data_warnings.append(warning)
            else:
                self.last_error = self.classify_error(exc)
            return []

    async def ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 600) -> list[list[float]]:
        try:
            client = self._client()
            return client.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        except Exception:
            return []


exchange_manager = ExchangeManager()
