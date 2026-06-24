"""mksaas.state — setup-state.json 读写、定位与默认结构。

唯一负责状态文件的 I/O 与初始化，不交互、不打印。
状态文件落点：项目目录内 .mksaas/setup-state.json（由 project 命令创建）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

STATE_FILENAME = "setup-state.json"
STATE_DIRNAME = ".mksaas"


class StateError(Exception):
    """状态文件读取或结构异常。"""


def locate_state_file(cwd: Path) -> Optional[Path]:
    """在 cwd 下定位 .mksaas/setup-state.json，存在返回路径，否则 None。"""
    candidate = Path(cwd) / STATE_DIRNAME / STATE_FILENAME
    return candidate if candidate.is_file() else None


def load(path: Path) -> Dict[str, Any]:
    """读取并解析状态文件 JSON；损坏时抛 StateError。"""
    try:
        text = Path(path).read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"状态文件读取失败：{path} ({exc})") from exc
    if not isinstance(data, dict):
        raise StateError(f"状态文件根不是对象：{path}")
    return data


def save(path: Path, data: Dict[str, Any]) -> None:
    """回写状态文件；目录不存在自动创建，幂等。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def ensure_state_dir(project_dir: Path) -> Path:
    """在 project_dir 内创建 .mksaas/（幂等），并在 .gitignore 中登记。"""
    state_dir = Path(project_dir) / STATE_DIRNAME
    state_dir.mkdir(parents=True, exist_ok=True)
    _ensure_gitignore(project_dir)
    return state_dir


def _ensure_gitignore(project_dir: Path) -> None:
    """确保 .gitignore 覆盖 .mksaas/ 与根 .env（REQUIREMENTS §9.1）。"""
    gi = Path(project_dir) / ".gitignore"
    entries = []
    if gi.is_file():
        entries = gi.read_text(encoding="utf-8").splitlines()
    needed = [".mksaas", ".env"]
    changed = False
    for item in needed:
        if not any(e.strip() == item for e in entries):
            entries.append(item)
            changed = True
    if changed:
        gi.write_text("\n".join(entries) + "\n", encoding="utf-8")


def init_default() -> Dict[str, Any]:
    """返回带完整顶层结构与默认字段的空状态。"""
    return {
        "version": "1.0.0",
        "project": {},
        "steps": {
            "init": {"status": "pending", "updated_at": None,
                     "env_groups_processed": [], "env_groups_skipped": [],
                     "apply_confirmed": False, "applied": False, "applied_at": None},
            "project": {"status": "pending", "updated_at": None,
                        "applied": False, "applied_at": None},
            "apply": {"status": "pending", "updated_at": None,
                      "applied": False, "applied_at": None},
        },
        "profiles": {
            "test": {"base_url": "", "env_groups": {}},
            "prod": {"base_url": "", "env_groups": {}},
        },
        "modules": {},
        "artifacts": {
            "env_test_file": ".mksaas/.env.test",
            "env_prod_file": ".mksaas/.env.prod",
            "default_env_file": ".env",
            "steps_doc_file": "SETUP_NEXT_STEPS.md",
        },
        "apply": {
            "dirty": True, "last_run_at": None,
            "last_result": None, "last_applied_project_dir": None,
        },
        "meta": {"language": "zh-CN", "platform": "macos"},
    }
