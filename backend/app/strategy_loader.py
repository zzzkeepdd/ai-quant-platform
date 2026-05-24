import ast
import hashlib
import importlib.util
import re
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from .config import STRATEGY_DIR


ALLOWED_STRATEGIES = {
    "BB挤压突破.py": {"score": "5/5", "market_state": "HIGH_VOLATILITY"},
    "BOS移动止损增强版.py": {"score": "5/5", "market_state": "TRENDING"},
    "摆动点区间反转.py": {"score": "5/5", "market_state": "RANGING"},
    "趋势衰竭反转.py": {"score": "5/5", "market_state": "TREND_EXHAUSTION"},
}


@dataclass
class LoadedStrategy:
    file: str
    name: str
    module: ModuleType
    params: dict[str, Any]
    tags: dict[str, str]


def _strategy_path(file_name: str) -> Path:
    if file_name not in ALLOWED_STRATEGIES:
        raise ValueError("只允许加载四个通过质检的策略")
    path = STRATEGY_DIR / file_name
    if not path.exists():
        raise FileNotFoundError(f"策略文件不存在: {file_name}")
    return path


def _read_head(path: Path, max_lines: int = 80) -> list[str]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    return lines[:max_lines]


def parse_header_tags(path: Path) -> dict[str, str]:
    """解析策略文件头部中文注释，展示到策略管理页。"""
    tags: dict[str, str] = {}
    pending_key: str | None = None
    for line in _read_head(path):
        stripped = line.strip()
        if not stripped.startswith("#"):
            if stripped and not stripped.startswith('"""'):
                break
            continue
        content = stripped.lstrip("#").strip()
        if not content:
            continue
        if "：" in content or ":" in content:
            key, value = re.split("[：:]", content, maxsplit=1)
            key = key.strip()
            if key in {"适用行情", "不适行情", "交易频率", "核心逻辑", "标的", "标的限制", "默认参数", "推荐参数", "仓位限制", "择时警告", "与其他策略互补"}:
                tags[key] = value.strip()
                pending_key = key
        elif pending_key and content.startswith(("→", "扩张", "赚", "SOL", "ETH", "BTC")):
            tags[pending_key] = f"{tags[pending_key]} {content}".strip()
    return tags


def parse_params(path: Path) -> dict[str, Any]:
    """用AST安全提取所有PARAMS开头的参数包。"""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    params: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.startswith("PARAMS"):
                    try:
                        params[target.id] = ast.literal_eval(node.value)
                    except Exception:
                        params[target.id] = {"说明": "该参数包包含动态展开，运行时可用但不可静态展示"}
    return params


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def list_strategies() -> list[dict[str, Any]]:
    result = []
    for file_name, meta in ALLOWED_STRATEGIES.items():
        path = _strategy_path(file_name)
        tags = parse_header_tags(path)
        result.append(
            {
                "file": file_name,
                "name": path.stem,
                "score": meta["score"],
                "market_state": meta["market_state"],
                "tags": tags,
                "params": parse_params(path),
                "sha256": file_hash(path),
            }
        )
    return result


def load_strategy(file_name: str) -> LoadedStrategy:
    path = _strategy_path(file_name)
    module_name = f"strategy_{file_hash(path)}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载策略: {file_name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "strategy_logic"):
        raise AttributeError(f"策略缺少 strategy_logic: {file_name}")
    return LoadedStrategy(
        file=file_name,
        name=path.stem,
        module=module,
        params=parse_params(path),
        tags=parse_header_tags(path),
    )
