"""mksaas.schema — 加载 env-schema.yaml，提供变量全集。

schema 文件是环境变量的唯一真相来源（REQUIREMENTS §5.2.1）。
本模块无副作用，仅解析与查找。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

try:
    import yaml
except ImportError as exc:  # pragma: no cover - 运行时硬依赖
    raise RuntimeError("缺少 PyYAML，请 pip install pyyaml") from exc

# schema 文件相对仓库根：mksaas/schema.py -> 上两级 -> docs/env-schema.yaml
_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "docs" / "env-schema.yaml"


class SchemaError(Exception):
    """schema 文件加载或结构异常。"""


def schema_path() -> Path:
    """返回 schema 文件路径。"""
    return _SCHEMA_PATH


@lru_cache(maxsize=1)
def load_schema() -> List[Dict[str, Any]]:
    """加载并返回按 order 升序的 group 列表。"""
    if not _SCHEMA_PATH.is_file():
        raise SchemaError(f"schema 文件不存在：{_SCHEMA_PATH}")
    try:
        raw = yaml.safe_load(_SCHEMA_PATH.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SchemaError(f"schema 解析失败：{exc}") from exc
    groups = raw.get("groups") if isinstance(raw, dict) else None
    if not isinstance(groups, list) or not groups:
        raise SchemaError("schema 缺 groups 列表")
    return sorted(groups, key=lambda g: g["order"])


def find_group(group_id: str) -> Dict[str, Any]:
    """按 group id 查找单个 group 定义，未找到抛 KeyError。"""
    for g in load_schema():
        if g["id"] == group_id:
            return g
    raise KeyError(group_id)
