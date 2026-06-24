"""mksaas.commands.uninstall — 卸载本地安装。

docs/build_install_upgrade_uninstall.md §8 为真相来源。
删除安装目录内可执行文件与版本信息、PATH 符号链接；幂等；不删用户项目内 .mksaas/。
"""

from __future__ import annotations

from typing import Any

from mksaas import paths
from mksaas.console import Console


def run_uninstall(args: Any, console: Console) -> int:
    """uninstall 子命令入口。"""
    exe = paths.executable_path()
    info = paths.version_info_path()
    link = paths.symlink_target()

    targets = [exe, info, link]
    existing = [t for t in targets if t.exists() or t.is_symlink()]
    if not existing:
        console.print("未检测到 mksaas 安装（已卸载）")
        return 0

    console.print("将删除以下路径：")
    for t in existing:
        console.print(f"  {t}")
    if not console.confirm("确认卸载？", default=False):
        console.print("已取消")
        return 0

    for t in existing:
        try:
            if t.is_symlink() or t.is_file():
                t.unlink()
        except OSError as exc:
            console.print(f"删除失败：{t} ({exc})")

    console.print("卸载完成。项目内 .mksaas/ 与 .env.* 不受影响")
    return 0
