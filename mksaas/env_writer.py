"""mksaas.env_writer — 全量重建 .env.test/.env.prod 与同步根 .env。

docs/steps/02-apply.md §10；REQUIREMENTS §5.2.1。
按 schema 遍历全部变量：已采集取状态值，未采集取 schema 默认，
无默认且非必填写空串；必填缺失返回缺失列表由 apply 拦截。
generate_if_empty 空值在此生成并回写状态。每次先删后建，不留旧变量。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from mksaas.schema import load_schema
from mksaas.secrets_gen import gen_better_auth_secret

_PROFILE_FILE = {"test": ".env.test", "prod": ".env.prod"}


def _resolve_value(var: Dict[str, Any], collected: Dict[str, Any], profile: str,
                   state: Dict[str, Any], group_id: str) -> str:
    """返回单个变量最终值；generate_if_empty 空值时生成并回写状态。"""
    name = var["name"]
    field = collected.get(name, {})
    value = (field.get("value") or "").strip()

    if not value and var.get("generate_if_empty"):
        value = gen_better_auth_secret()
        # 回写状态文件，source=prompt_or_generate
        field = {
            "value": value, "source": "prompt_or_generate",
            "required": bool(var.get("required")),
            "description": var.get("description", ""),
            "generate_if_empty": True,
        }
        if var.get("sensitive"):
            field["sensitive"] = True
        state["profiles"][profile]["env_groups"][group_id][name] = field

    if not value:
        value = var.get("default") or ""
    return value


def rebuild_envs(state: Dict[str, Any], schema: List[Dict[str, Any]],
                 project_dir: Path) -> Dict[str, List[str]]:
    """全量重建 .env.test 与 .env.prod，返回每个 profile 的缺失必填列表。"""
    project_dir = Path(project_dir)
    env_dir = project_dir / ".mksaas"
    env_dir.mkdir(parents=True, exist_ok=True)

    missing: Dict[str, List[str]] = {}
    for profile in ("test", "prod"):
        lines: List[str] = []
        miss: List[str] = []
        groups = state.setdefault("profiles", {}).setdefault(
            profile, {"base_url": "", "env_groups": {}}).setdefault("env_groups", {})
        for g in schema:
            group_id = g["id"]
            collected = groups.setdefault(group_id, {})
            for var in g["variables"]:
                name = var["name"]
                value = _resolve_value(var, collected, profile, state, group_id)
                if not value and var.get("required"):
                    miss.append(name)
                    continue  # 必填缺失不写入
                lines.append(f"{name}={value}")
        missing[profile] = miss
        out = env_dir / _PROFILE_FILE[profile]
        if out.exists():
            out.unlink()  # 先删后建
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return missing


def sync_root_env(state: Dict[str, Any], project_dir: Path, profile: str) -> None:
    """删除并按所选 profile 重建项目根 .env（内容同 .env.<profile>）。"""
    project_dir = Path(project_dir)
    src = project_dir / ".mksaas" / _PROFILE_FILE[profile]
    dst = project_dir / ".env"
    if dst.exists():
        dst.unlink()
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
