"""mksaas.paths — 构建/安装生命周期的固定本地路径。

docs/build_install_upgrade_uninstall.md §2/§6 为真相来源。
安装目录、构建产物目录、符号链接目标共享同一组路径。
"""

from __future__ import annotations

import os
import json
from pathlib import Path


def install_dir() -> Path:
    """安装目录（存放可执行文件与版本信息）。"""
    return Path.home() / ".mksaas-cli"


def dist_dir() -> Path:
    """构建产物目录（优先来自安装元信息，其次回退到源码仓库 .build/dist）。"""
    meta = install_metadata()
    build_dist = meta.get("build_dist_dir")
    if isinstance(build_dist, str) and build_dist:
        return Path(build_dist)
    repo_root = repo_root()
    if repo_root is not None:
        return repo_root / ".build" / "dist"
    return install_dir() / ".build" / "dist"


def executable_path() -> Path:
    """安装目录内的可执行文件路径。"""
    return install_dir() / "mksaas"


def version_info_path() -> Path:
    """已安装版本信息文件。"""
    return install_dir() / "VERSION.installed"


def install_metadata() -> dict:
    """读取安装元信息；失败时返回空字典。"""
    p = version_info_path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def repo_root() -> Path | None:
    """尽量定位源码仓库根目录。"""
    meta = install_metadata()
    repo_root_str = meta.get("repo_root")
    if isinstance(repo_root_str, str) and repo_root_str:
        return Path(repo_root_str)
    candidate = Path(__file__).resolve().parent.parent
    if (candidate / "build.sh").is_file():
        return candidate
    return None


def symlink_target() -> Path:
    """命令符号链接所在目录：优先 /usr/local/bin，不可写回退 ~/.local/bin。"""
    if _is_writable("/usr/local/bin"):
        return Path("/usr/local/bin") / "mksaas"
    return Path.home() / ".local" / "bin" / "mksaas"


def symlink_dir() -> Path:
    """符号链接所在目录。"""
    return symlink_target().parent


def _is_writable(path: str) -> bool:
    """判断目录是否可写（不静默提权）。"""
    try:
        return os.access(path, os.W_OK)
    except OSError:
        return False
