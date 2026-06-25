"""mksaas.version — 版本号约定与构建配置读写。

docs/build_install_upgrade_uninstall.md §3 为真相来源。
build.config.json 含 version(MAJOR.MINOR.PATCH) 与 build(整数)。
产物版本字符串：debug=<version>-dev<build>，release=<version>。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Tuple

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class VersionError(Exception):
    """版本状态文件或格式异常。"""


def read_version(path: Path) -> Tuple[str, int]:
    """读取 build 配置中的版本字段，返回 (version, build)。"""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        v = data["version"]
        b = int(data["build"])
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        raise VersionError(f"构建配置读取失败：{path} ({exc})") from exc
    if not _VERSION_RE.match(v):
        raise VersionError(f"version 格式非法：{v}")
    return v, b


def write_version(path: Path, version_str: str, build: int) -> None:
    """回写 build 配置中的 version/build，并保留其余字段。"""
    payload = {}
    p = Path(path)
    if p.is_file():
        try:
            current = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current = {}
        if isinstance(current, dict):
            payload.update(current)
    payload["version"] = version_str
    payload["build"] = build
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def version_string(version_str: str, build: int, release: bool = False) -> str:
    """构造产物版本字符串。"""
    if release:
        return version_str
    return f"{version_str}-dev{build}"


def bump(version_str: str, level: str) -> Tuple[str, int]:
    """提升版本号并重置 build=0。level: patch/minor/major。"""
    m = _VERSION_RE.match(version_str)
    if not m:
        raise ValueError(f"version 格式非法：{version_str}")
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if level == "patch":
        patch += 1
    elif level == "minor":
        minor += 1
        patch = 0
    elif level == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        raise ValueError(f"未知 bump 位级：{level}")
    return f"{major}.{minor}.{patch}", 0


def product_path(dist_dir: str, version_str: str, build: int,
                 release: bool = False) -> str:
    """产物存储路径：<dist_dir>/<版本字符串>/mksaas。"""
    return f"{dist_dir}/{version_string(version_str, build, release)}/mksaas"


def sort_key(version_str_with_suffix: str):
    """为版本字符串（如 0.1.0-dev10 / 0.1.0）提供排序键。

    release 形式视为该 version 的最高点（dev 之后）。
    """
    s = version_str_with_suffix
    if "-dev" in s:
        base, dev = s.split("-dev")
        m = _VERSION_RE.match(base)
        major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return (major, minor, patch, 0, int(dev))
    m = _VERSION_RE.match(s)
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return (major, minor, patch, 1, 0)
