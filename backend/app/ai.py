import asyncio
from typing import Any, AsyncIterator

from .backtest import market_snapshot
from .config import DEEPSEEK_BASE_URL, DEEPSEEK_DEFAULT_MODEL, STRATEGY_MAPPING
from .database import append_log, get_setting, now_iso
from .logging_service import safe_payload
from .market_data import fetch_live_market, fetch_onchain_summary
from .optimizer import auto_optimize_strategy
from .secrets import load_secret


class AIEngine:
    """DeepSeek决策引擎；无密钥时用真实K线特征生成本地兜底分析。"""

    def __init__(self) -> None:
        self.tasks: dict[str, list[str]] = {}
        self.pending: dict[str, tuple[str, dict[str, Any]]] = {}
        self.last_error: str | None = None
        self.valid: bool | None = None

    def connected(self) -> bool:
        return load_secret("deepseek_api_key") is not None

    def reset_validation(self) -> None:
        self.valid = None
        self.last_error = None

    def status(self) -> dict[str, Any]:
        configured = self.connected()
        if not configured:
            display_state = "未配置"
        elif self.valid is True:
            display_state = "已连接"
        elif self.valid is False:
            display_state = "认证失败"
        elif self.last_error:
            display_state = "连接异常"
        else:
            display_state = "待验证"
        return {
            "connected": configured and self.valid is not False,
            "configured": configured,
            "valid": self.valid,
            "last_error": self.last_error,
            "display_state": display_state,
        }

    def _is_auth_error(self, exc: Exception) -> bool:
        text = str(exc)
        return "401" in text or "Authentication" in text or "api key" in text.lower()

    def _friendly_ai_error(self, exc: Exception) -> str:
        text = str(exc)
        if self._is_auth_error(exc):
            return "DeepSeek 密钥无效：请在系统设置重新保存 API Key。"
        if "timeout" in text.lower():
            return "DeepSeek 调用超时：已切换本地行情分析。"
        return "DeepSeek 调用失败：已切换本地行情分析。"

    def _deepseek_base_urls(self) -> list[str]:
        urls = [DEEPSEEK_BASE_URL, "https://api.deepseek.com/v1"]
        unique: list[str] = []
        for url in urls:
            if url not in unique:
                unique.append(url)
        return unique

    async def _chat_once(self, key: str, base_url: str, messages: list[dict[str, str]], max_tokens: int, timeout: int):
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=key, base_url=base_url, http_client=self._http_client())
        return await client.chat.completions.create(
            model=DEEPSEEK_DEFAULT_MODEL,
            messages=messages,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    def _http_client(self):
        import httpx

        proxy = get_setting("proxy", {"type": "http", "host": "127.0.0.1", "port": 7897})
        if proxy.get("type") == "none":
            return httpx.AsyncClient()
        proxy_url = f"{proxy.get('type', 'http')}://{proxy.get('host', '127.0.0.1')}:{proxy.get('port', 7897)}"
        return httpx.AsyncClient(proxy=proxy_url)

    async def _chat_with_fallback(self, key: str, messages: list[dict[str, str]], max_tokens: int, timeout: int):
        last_exc: Exception | None = None
        for base_url in self._deepseek_base_urls():
            try:
                return await self._chat_once(key, base_url, messages, max_tokens, timeout)
            except Exception as exc:
                last_exc = exc
                if self._is_auth_error(exc):
                    raise
        if last_exc:
            raise last_exc
        raise RuntimeError("DeepSeek request failed")

    async def _stream_once(self, key: str, base_url: str, messages: list[dict[str, str]], timeout: int):
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=key, base_url=base_url, http_client=self._http_client())
        return await client.chat.completions.create(
            model=DEEPSEEK_DEFAULT_MODEL,
            messages=messages,
            stream=True,
            timeout=timeout,
        )

    async def _stream_with_fallback(self, key: str, messages: list[dict[str, str]], timeout: int):
        last_exc: Exception | None = None
        for base_url in self._deepseek_base_urls():
            try:
                return await self._stream_once(key, base_url, messages, timeout)
            except Exception as exc:
                last_exc = exc
                if self._is_auth_error(exc):
                    raise
        if last_exc:
            raise last_exc
        raise RuntimeError("DeepSeek stream failed")

    async def validate_connection(self) -> dict[str, Any]:
        key = load_secret("deepseek_api_key")
        if not key:
            self.valid = None
            self.last_error = None
            return self.status()
        try:
            await self._chat_with_fallback(key, [{"role": "user", "content": "ping"}], 1, 12)
            self.valid = True
            self.last_error = None
        except Exception as exc:
            self.last_error = self._friendly_ai_error(exc)
            self.valid = False if self._is_auth_error(exc) else None
        return self.status()

    def _symbols(self, symbol: str | None) -> list[str]:
        return ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"] if not symbol or symbol == "ALL" else [symbol]

    def _enrich_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(payload)
        timeframe = payload.get("timeframe") or "15m"
        enriched["market_data"] = [
            market_snapshot(symbol, payload.get("start_date"), payload.get("end_date"), timeframe=timeframe, prefer_okx=True)
            for symbol in self._symbols(payload.get("symbol"))
        ]
        enriched["market_data_note"] = "默认使用OKX最新公共K线；只有OKX不可用或指定历史日期时才回退项目缓存。"
        enriched["live_tickers"] = fetch_live_market()
        enriched["onchain_summary"] = fetch_onchain_summary()
        enriched["data_contract"] = {
            "market_data": "OKX public candles snapshot for structure/trend/volatility",
            "live_tickers": "OKX public tickers for latest price, bid/ask, 24h change and volume",
            "onchain_summary": "DefiLlama chain TVL summary for Bitcoin/Ethereum/Solana",
        }
        if payload.get("auto_optimization"):
            enriched["auto_optimization"] = payload["auto_optimization"]
        return enriched

    def build_prompt(self, task_type: str, payload: dict[str, Any]) -> str:
        enriched = self._enrich_payload(payload)
        if task_type in {"optimize", "auto-select", "auto-optimize"} and not enriched.get("auto_optimization"):
            enriched["auto_optimization"] = auto_optimize_strategy(
                payload.get("symbol", "ALL"),
                payload.get("timeframe", "15m"),
                float(payload.get("initial_capital", 10000) or 10000),
                payload.get("mode", "sandbox"),
            )
        return (
            "你是加密货币量化交易风控助手。只能给建议，不能绕过风控或直接下单。\n"
            f"任务: {task_type}\n"
            f"策略映射: {STRATEGY_MAPPING}\n"
            f"输入与真实市场数据: {enriched}\n"
            "必须优先基于 market_data 中 source=okx_public_candles 的最新OKX行情分析；不要引用过期日期。"
            "用户不需要手动选择策略或参数，你必须引用 auto_optimization 里的确定性迭代结果。"
            "如果输入里有 okx_account 和 okx_positions_count，也要把它作为仓位与风险背景。"
            "请用交易员复盘格式输出：行情状态、证据、当前不交易/交易理由、自动匹配策略、参数包建议、风险提示。"
            "如果是多币种，请分别分析BTC、ETH、SOL。"
            "如果是实盘，只能给建议并提示需要人工确认；如果是模拟盘，可以说明可自动采用的策略和参数。"
        )

    async def stream(self, task_id: str, task_type: str, payload: dict[str, Any]) -> AsyncIterator[str]:
        prompt = self.build_prompt(task_type, safe_payload(payload))
        self.tasks[task_id] = []
        key = load_secret("deepseek_api_key")
        if not key:
            fallback = self.local_answer(task_type, payload)
            for part in fallback:
                await asyncio.sleep(0.04)
                self.tasks[task_id].append(part)
                yield part
            self._log_decision(task_type, prompt, "".join(fallback), payload)
            return
        try:
            stream = await self._stream_with_fallback(key, [{"role": "user", "content": prompt}], 45)
            collected = []
            async for chunk in stream:
                text = chunk.choices[0].delta.content or ""
                if text:
                    collected.append(text)
                    self.tasks[task_id].append(text)
                    yield text
            self.valid = True
            self.last_error = None
            self._log_decision(task_type, prompt, "".join(collected), payload)
        except Exception as exc:
            self.valid = False if self._is_auth_error(exc) else None
            self.last_error = self._friendly_ai_error(exc)
            message = f"{self.last_error}\n"
            self.tasks[task_id].append(message)
            yield message
            for part in self.local_answer(task_type, payload):
                await asyncio.sleep(0.03)
                self.tasks[task_id].append(part)
                yield part

    def local_answer(self, task_type: str, payload: dict[str, Any]) -> list[str]:
        summary = payload.get("market_summary") or "未提供文字摘要，使用最新K线特征兜底。"
        snapshots = [
            market_snapshot(symbol, payload.get("start_date"), payload.get("end_date"), timeframe=payload.get("timeframe") or "15m", prefer_okx=True)
            for symbol in self._symbols(payload.get("symbol"))
        ]
        lines = [
            "### OKX最新行情复盘\n",
            f"- 你的问题：{summary}\n",
        ]
        for snap in snapshots:
            if abs(float(snap["return_120h_pct"])) > 3:
                state = "趋势行情"
                strategy = STRATEGY_MAPPING["TRENDING"]
                preset = "高频/平衡，先看交易数和回撤"
            elif float(snap["volatility_24h"]) > 0.02 or float(snap["bb_width20"]) > 0.06:
                state = "高波动行情"
                strategy = STRATEGY_MAPPING["HIGH_VOLATILITY"]
                preset = "稳健，避免假突破"
            else:
                state = "震荡行情"
                strategy = STRATEGY_MAPPING["RANGING"]
                preset = "平衡或保守，靠近区间边界才交易"
            lines.append(
                f"- {snap['symbol']}：{state}；数据源 {snap.get('source')}，K线 {snap.get('timeframe')}，最后K线 {snap.get('last_time')}，最新价 {snap['last']}，24h {snap['return_24h_pct']}%，120h {snap['return_120h_pct']}%，波动 {snap['volatility_24h']}。建议策略 `{strategy}`，参数包：{preset}。\n"
            )
        if task_type in {"optimize", "auto-select", "auto-optimize"}:
            optimization = payload.get("auto_optimization") or auto_optimize_strategy(
                payload.get("symbol", "ALL"),
                payload.get("timeframe", "15m"),
                float(payload.get("initial_capital", 10000) or 10000),
                payload.get("mode", "sandbox"),
            )
            lines.append("### 自动策略选择与参数迭代\n")
            for row in optimization.get("results", []):
                lines.append(
                    f"- {row['symbol']}：状态 {row['market_state']}，策略 `{row['strategy']}`，"
                    f"最优参数 {row.get('best_params', {})}，"
                    f"指标 {row.get('best_metrics', {})}，综合评分 {row.get('score', 0)}。"
                    f"{row.get('recommended_action')}\n"
                )
        else:
            lines.extend(
                [
                    "- 如果没有靠近策略触发区，不建议为了交易次数强行开仓。\n",
                    "- 模拟盘可以自动采用建议；实盘仍需要人工确认。\n",
                ]
            )
        return lines

    def _log_decision(self, task_type: str, prompt: str, response: str, payload: dict[str, Any]) -> None:
        append_log(
            "ai_decisions",
            ts=now_iso(),
            task_type=task_type,
            market_state=payload.get("market_state"),
            strategy=payload.get("strategy_file"),
            prompt=prompt,
            response=response,
            payload=safe_payload(payload),
        )


ai_engine = AIEngine()
