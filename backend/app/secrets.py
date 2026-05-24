from cryptography.fernet import Fernet

from .config import FERNET_KEY_PATH
from .database import db, now_iso


def _fernet() -> Fernet:
    """加载或创建本地加密密钥，密钥只保存在data_cache，不进源码。"""
    FERNET_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not FERNET_KEY_PATH.exists():
        FERNET_KEY_PATH.write_bytes(Fernet.generate_key())
    return Fernet(FERNET_KEY_PATH.read_bytes())


def save_secret(name: str, value: str) -> None:
    encrypted = _fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    with db() as conn:
        conn.execute(
            "REPLACE INTO encrypted_secrets(name, encrypted_value, updated_at) VALUES (?, ?, ?)",
            (name, encrypted, now_iso()),
        )


def load_secret(name: str) -> str | None:
    with db() as conn:
        row = conn.execute("SELECT encrypted_value FROM encrypted_secrets WHERE name = ?", (name,)).fetchone()
    if not row:
        return None
    return _fernet().decrypt(row["encrypted_value"].encode("utf-8")).decode("utf-8")


def has_secret(name: str) -> bool:
    return load_secret(name) is not None


def delete_secret(name: str) -> None:
    with db() as conn:
        conn.execute("DELETE FROM encrypted_secrets WHERE name = ?", (name,))
