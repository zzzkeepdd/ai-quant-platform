from datetime import datetime, timezone
from typing import Any

import requests

from .config import DEFAULT_MARKET_MODE, SUPPORTED_SYMBOLS
from .database import get_setting


OKX_BASE_URL = "https://www.okx.com"
DEFILLAMA_CHAINS_URL = "https://api.llama.fi/v2/chains"

OKX_SWAP_INSTRUMENTS = {
    "BTC/USDT:USDT": "BTC-USDT-SWAP",
    "ETH/USDT:USDT": "ETH-USDT-SWAP",
    "SOL/USDT:USDT": "SOL-USDT-SWAP",
}

CHAIN_ROWS = [
    {"asset": "BTC", "chain": "Bitcoin", "aliases": {"bitcoin", "btc"}},
    {"asset": "ETH", "chain": "Ethereum", "aliases": {"ethereum", "eth"}},
    {"asset": "SOL", "chain": "Solana", "aliases": {"solana", "sol"}},
]

_market_cache: dict[str, Any] | None = None
_onchain_cache: dict[str, Any] | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _proxy_url() -> str | None:
    proxy = get_setting("proxy", {"type": "http", "host": "127.0.0.1", "port": 7897})
    if proxy.get("type") == "none":
        return None
    return f"{proxy.get('type', 'http')}://{proxy.get('host', '127.0.0.1')}:{proxy.get('port', 7897)}"


def _proxies() -> dict[str, str] | None:
    proxy = _proxy_url()
    return {"http": proxy, "https": proxy} if proxy else None


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _change_pct(last: float | None, open_24h: float | None) -> float | None:
    if not last or not open_24h:
        return None
    return (last / open_24h - 1) * 100


def _ts_to_iso(value: Any) -> str:
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return _now_iso()


def _market_row(symbol: str, inst_id: str, ticker: dict[str, Any]) -> dict[str, Any]:
    last = _to_float(ticker.get("last"))
    open_24h = _to_float(ticker.get("open24h"))
    return {
        "symbol": symbol,
        "inst_id": inst_id,
        "instrument_type": ticker.get("instType") or "SWAP",
        "last": last,
        "open_24h": open_24h,
        "high_24h": _to_float(ticker.get("high24h")),
        "low_24h": _to_float(ticker.get("low24h")),
        "change_24h_pct": _change_pct(last, open_24h),
        "volume_24h": _to_float(ticker.get("volCcyQuote24h") or ticker.get("volCcy24h") or ticker.get("vol24h")),
        "bid": _to_float(ticker.get("bidPx")),
        "ask": _to_float(ticker.get("askPx")),
        "source": "okx_public_ticker",
        "updated_at": _ts_to_iso(ticker.get("ts")),
    }


def fetch_live_market() -> dict[str, Any]:
    """Read public OKX market snapshots without using API keys or trade permissions."""
    global _market_cache
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    mode = get_setting("market_mode", DEFAULT_MARKET_MODE)
    headers = {"x-simulated-trading": "1"} if mode == "sandbox" else None

    try:
        response = requests.get(
            f"{OKX_BASE_URL}/api/v5/market/tickers",
            params={"instType": "SWAP"},
            headers=headers,
            proxies=_proxies(),
            timeout=12,
        )
        payload = response.json()
        if response.status_code >= 400 or payload.get("code") != "0":
            raise RuntimeError(str(payload)[:200])
        by_inst_id = {item.get("instId"): item for item in payload.get("data", [])}
        for symbol in SUPPORTED_SYMBOLS:
            inst_id = OKX_SWAP_INSTRUMENTS.get(symbol)
            ticker = by_inst_id.get(inst_id)
            if not inst_id:
                errors.append(f"No OKX instrument mapping for {symbol}")
                continue
            if not ticker:
                errors.append(f"No OKX ticker row for {inst_id}")
                continue
            rows.append(_market_row(symbol, inst_id, ticker))
    except Exception as exc:
        errors.append(f"OKX tickers: {str(exc)[:160]}")

    result = {
        "ok": bool(rows),
        "source": "OKX public market ticker",
        "mode": mode,
        "data": rows,
        "errors": errors,
        "updated_at": _now_iso(),
        "stale": False,
    }
    if rows:
        _market_cache = result
        return result
    if _market_cache:
        cached = dict(_market_cache)
        cached["errors"] = errors
        cached["stale"] = True
        return cached
    return result


def _chain_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        keys = {str(row.get("name") or "").lower(), str(row.get("tokenSymbol") or "").lower()}
        for key in keys:
            if key:
                lookup[key] = row
    return lookup


def fetch_onchain_summary() -> dict[str, Any]:
    """Read no-key chain-level metrics from DefiLlama."""
    global _onchain_cache
    errors: list[str] = []
    try:
        response = requests.get(DEFILLAMA_CHAINS_URL, proxies=_proxies(), timeout=12)
        payload = response.json()
        if response.status_code >= 400 or not isinstance(payload, list):
            raise RuntimeError(str(payload)[:200])
        lookup = _chain_lookup(payload)
        rows: list[dict[str, Any]] = []
        for item in CHAIN_ROWS:
            chain_data = next((lookup.get(alias) for alias in item["aliases"] if lookup.get(alias)), None)
            if not chain_data:
                errors.append(f"No DefiLlama chain row for {item['chain']}")
                continue
            rows.append(
                {
                    "asset": item["asset"],
                    "chain": item["chain"],
                    "raw_chain": chain_data.get("name"),
                    "tvl": _to_float(chain_data.get("tvl")),
                    "change_1d_pct": _to_float(chain_data.get("change_1d")),
                    "change_7d_pct": _to_float(chain_data.get("change_7d")),
                    "protocols": chain_data.get("protocols"),
                    "token_symbol": chain_data.get("tokenSymbol"),
                    "source": "defillama_chains",
                    "updated_at": _now_iso(),
                }
            )
        result = {
            "ok": bool(rows),
            "source": "DefiLlama chains TVL",
            "data": rows,
            "errors": errors,
            "updated_at": _now_iso(),
            "stale": False,
        }
        if rows:
            _onchain_cache = result
        return result
    except Exception as exc:
        errors.append(str(exc)[:160])
        if _onchain_cache:
            cached = dict(_onchain_cache)
            cached["errors"] = errors
            cached["stale"] = True
            return cached
        return {
            "ok": False,
            "source": "DefiLlama chains TVL",
            "data": [],
            "errors": errors,
            "updated_at": _now_iso(),
            "stale": False,
        }
