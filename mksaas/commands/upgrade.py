"""mksaas.commands.upgrade — 从本地构建产物升级。

docs/build_install_upgrade_uninstall.md §7 为真相来源。
仅从本地 dist 目录读取产物，不发起网络请求；原子替换保留符号链接。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mksaas import paths, version
from mksaas.console import Console


def _latest_product(dist_dir: Path) -> Path | None:
    """在 dist 目录下按版本字符串排序取最大版本子目录。"""
    if not dist_dir.is_dir():
        return None
    subs = [p for p in dist_dir.iterdir() if p.is_dir() and (p / "mksaas").is_file()]
    if not subs:
        return None
    subs.sort(key=lambda p: version.sort_key(p.name))
    return subs[-1] / "mksaas"


def run_upgrade(args: Any, console: Console) -> int:
    """upgrade --local 子命令入口。"""
    if not getattr(args, "local", False):
        console.print("upgrade 必须带 --local（首版只支持本地升级）")
        return 1

    dist = paths.dist_dir()
    target = _latest_product(dist)
    if target is None:
        console.print(f"未找到构建产物：{dist}，请先执行 build.sh")
        return 1

    exe = paths.executable_path()
    current = _read_installed_version()
    console.print(f"当前已安装版本：{current or '(未安装)'}")
    console.print(f"产物版本：{target.parent.name}")
    if not console.confirm("是否升级？", default=True):
        console.print("已取消")
        return 0

    # 原子替换：写临时文件再 rename
    exe.parent.mkdir(parents=True, exist_ok=True)
    tmp = exe.with_suffix(exe.suffix + ".tmp")
    tmp.write_bytes(target.read_bytes())
    tmp.replace(exe)
    paths.version_info_path().write_text(
        f'{{"installed_from": "{target.parent.name}"}}', encoding="utf-8"
    )
    console.print(f"升级完成：{target.parent.name}（符号链接未变动）")
    return 0


def _read_installed_version() -> str | None:
    """读取已安装版本信息。"""
    p = paths.version_info_path()
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8").strip()
    except OSError:
        return None
