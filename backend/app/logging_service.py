import csv
import io
import json
from typing import Any

from .database import append_log, export_rows, now_iso


def log_system(level: str, message: str, payload: dict[str, Any] | None = None) -> None:
    append_log(
        "system_logs",
        ts=now_iso(),
        level=level,
        message=message,
        payload=payload or {},
    )


def log_trade(level: str, message: str, symbol: str | None = None, strategy: str | None = None, payload: dict[str, Any] | None = None) -> None:
    append_log(
        "trade_logs",
        ts=now_iso(),
        level=level,
        symbol=symbol,
        strategy=strategy,
        message=message,
        payload=payload or {},
    )


def export_csv(kind: str) -> str:
    table = {"trade": "trade_logs", "ai": "ai_decisions", "system": "system_logs"}.get(kind)
    if not table:
        raise ValueError("日志类型只能是 trade、ai 或 system")
    rows = export_rows(table)
    output = io.StringIO()
    if not rows:
        return ""
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def safe_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """日志脱敏，避免密钥、密码、token写入日志。"""
    redacted = {}
    for key, value in payload.items():
        lower = key.lower()
        if any(word in lower for word in ["key", "secret", "password", "token"]):
            redacted[key] = "***"
        elif isinstance(value, dict):
            redacted[key] = safe_payload(value)
        else:
            redacted[key] = value
    return redacted
