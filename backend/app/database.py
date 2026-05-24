import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import BACKEND_DATA_DIR, DB_PATH


def now_iso() -> str:
    """返回统一的UTC时间字符串，便于日志和前端排序。"""
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    """初始化本地SQLite数据库。"""
    BACKEND_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS encrypted_secrets (
                name TEXT PRIMARY KEY,
                encrypted_value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trade_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                level TEXT NOT NULL,
                symbol TEXT,
                strategy TEXT,
                message TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                task_type TEXT NOT NULL,
                market_state TEXT,
                strategy TEXT,
                prompt TEXT NOT NULL,
                response TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                mode TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                amount REAL NOT NULL,
                price REAL,
                status TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS positions_snapshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT,
                contracts REAL,
                entry_price REAL,
                mark_price REAL,
                pnl REAL,
                payload TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS backtest_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                strategy TEXT NOT NULL,
                symbol TEXT NOT NULL,
                metrics TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS replay_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                symbol TEXT NOT NULL,
                result TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    """获取SQLite连接，并使用Row方便字段读取。"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def set_setting(key: str, value: Any) -> None:
    with db() as conn:
        conn.execute(
            "REPLACE INTO settings(key, value, updated_at) VALUES (?, ?, ?)",
            (key, json.dumps(value, ensure_ascii=False), now_iso()),
        )


def get_setting(key: str, default: Any = None) -> Any:
    with db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if not row:
        return default
    return json.loads(row["value"])


def append_log(table: str, **fields: Any) -> int:
    """写入日志类表，payload统一JSON化，返回自增ID。"""
    allowed = {"trade_logs", "ai_decisions", "orders", "positions_snapshot", "backtest_runs", "replay_runs", "system_logs"}
    if table not in allowed:
        raise ValueError(f"不允许写入未知日志表: {table}")
    keys = list(fields.keys())
    values = [json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for v in fields.values()]
    placeholders = ", ".join(["?"] * len(keys))
    with db() as conn:
        cur = conn.execute(
            f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({placeholders})",
            values,
        )
        return int(cur.lastrowid)


def export_rows(table: str) -> list[dict[str, Any]]:
    allowed = {"trade_logs", "ai_decisions", "system_logs"}
    if table not in allowed:
        raise ValueError("日志类型只能是 trade、ai 或 system")
    with db() as conn:
        rows = conn.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT 2000").fetchall()
    return [dict(row) for row in rows]


def database_ready() -> bool:
    return Path(DB_PATH).exists()
