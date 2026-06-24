"""mksaas.prompts — 通用环境分组采集交互。

docs/env-groups/*.md §5 为采集流程模板；REQUIREMENTS §3.3 为交互确认顺序。
依赖 Console 缝与 schema。collect_group：展示已有值 → 确认修改 → 逐项采集
（敏感走 getpass）→ 校验 → 回写。
"""

from __future__ import annotations

import re
from typing import Any, Dict
from urllib.parse import urlsplit

from mksaas.console import Console
from mksaas.masking import mask
from mksaas.schema import find_group
from mksaas.secrets_gen import gen_better_auth_secret

# 视为 URL 的变量名（采集时校验 http/https）
_URL_VARS = {"NEXT_PUBLIC_BASE_URL"}

_URL_RE = re.compile(r"^https?://[^\s]+$")


def _is_url_var(name: str) -> bool:
    return name in _URL_VARS


def _existing_group(state: Dict[str, Any], group_id: str, profile: str) -> Dict[str, Any]:
    return (
        state.setdefault("profiles", {})
        .setdefault(profile, {"base_url": "", "env_groups": {}})
        .setdefault("env_groups", {})
        .get(group_id, {})
    )


def _display_existing(console: Console, group_id: str, profile: str, existing: Dict[str, Any]) -> None:
    """展示已有值（敏感字段 mask）。"""
    console.print(f"当前分组：{group_id}（profile={profile}）")
    if not existing:
        console.print("  尚未采集")
        return
    schema = find_group(group_id)
    sensitive_names = {v["name"] for v in schema["variables"] if v.get("sensitive")}
    for name, field in existing.items():
        raw = field.get("value", "")
        shown = mask(raw) if name in sensitive_names else (raw or "<empty>")
        console.print(f"  {name} = {shown}")


def _collect_one(console: Console, var: Dict[str, Any], group_id: str) -> str:
    """采集单个变量值，敏感走 getpass，URL 校验，必填空重输。

    generate_if_empty 的必填变量允许留空（由调用方决定自动生成）。
    """
    name = var["name"]
    required = bool(var.get("required"))
    sensitive = bool(var.get("sensitive"))
    allow_empty = bool(var.get("generate_if_empty"))
    prompt = f"  {name}{var.get('description', '')}"
    if sensitive:
        prompt += "（隐藏输入）"

    while True:
        raw = console.getpass(prompt + "> ") if sensitive else console.input(prompt + "> ")
        raw = (raw or "").strip()
        if not raw:
            if required and not allow_empty:
                console.print(f"  {name} 为必填，请重新输入")
                continue
            return ""
        if _is_url_var(name) and not _URL_RE.match(raw):
            console.print(f"  {name} 需为 http:// 或 https:// 开头的 URL")
            continue
        return raw


def collect_group(state: Dict[str, Any], group_id: str, profile: str,
                  console: Console) -> bool:
    """采集某分组某 profile 的变量，回写 state，返回是否发生修改。"""
    schema = find_group(group_id)
    existing = _existing_group(state, group_id, profile)
    _display_existing(console, group_id, profile, existing)

    if existing:
        if not console.confirm("是否修改该分组？", default=False):
            return False

    console.print("逐项采集（留空=保留默认/空，敏感字段隐藏输入）：")
    new_group: Dict[str, Any] = {}
    for var in schema["variables"]:
        name = var["name"]
        # BETTER_AUTH_SECRET 空值可自动生成
        if var.get("generate_if_empty"):
            value = _collect_one(console, var, group_id)
            if not value and console.confirm("是否自动生成？", default=True):
                value = gen_better_auth_secret()
                source = "prompt_or_generate"
            else:
                source = "prompt" if value else "default"
        else:
            value = _collect_one(console, var, group_id)
            source = "prompt" if value else ("default" if var.get("default") else "prompt")

        new_group[name] = {
            "value": value,
            "source": source,
            "required": bool(var.get("required")),
            "description": var.get("description", ""),
        }
        if var.get("sensitive"):
            new_group[name]["sensitive"] = True
        if var.get("generate_if_empty"):
            new_group[name]["generate_if_empty"] = True

    state["profiles"][profile]["env_groups"][group_id] = new_group
    console.print(f"分组 {group_id} 已采集（未应用，需在 apply 阶段统一落地）")
    return True
