"""mksaas.cli — argparse 主入口与子命令分发。

本模块负责构建顶层 CLI 解析器并把命令分发到各 commands/* 子模块。
所有终端 I/O 经 Console 缝，便于测试注入。
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from mksaas.console import Console, TerminalConsole

# CLI 显示用版本占位；真实版本字符串由 version.py 在 F10 接管。
_VERSION = "0.1.0-dev0"


def build_parser() -> argparse.ArgumentParser:
    """构造顶层 argparse 解析器并注册全部子命令。"""
    parser = argparse.ArgumentParser(
        prog="mksaas",
        description="MkSaaS 配置编排 CLI",
    )
    parser.add_argument("--version", action="store_true", help="显示版本号")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="全流程编排器")
    sub.add_parser("project", help="采集项目与仓库信息并就位本地目录")

    env = sub.add_parser("env", help="采集某一环境分组")
    env.add_argument("group", nargs="?", help="分组标识符（连字符形式，如 github-oauth）")
    env.add_argument("--profile", choices=["test", "prod"], default=None, help="目标 profile")

    sub.add_parser("apply", help="统一执行落地")

    upgrade = sub.add_parser("upgrade", help="从本地构建产物升级")
    upgrade.add_argument("--local", action="store_true", help="从本地产物升级")

    sub.add_parser("uninstall", help="卸载本地安装")
    return parser


def main(argv: Optional[List[str]] = None, console: Optional[Console] = None) -> int:
    """解析 argv 并分发到子命令，返回退出码。"""
    console = console or TerminalConsole()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        console.print(f"mksaas { _VERSION }")
        return 0

    if not args.command:
        parser.print_help()
        return 1

    # 各子命令实现于 commands 包；未注册命令由 argparse 报错。
    from mksaas import commands as cmd

    dispatch = {
        "init": cmd.run_init,
        "project": cmd.run_project,
        "env": cmd.run_env,
        "apply": cmd.run_apply,
        "upgrade": cmd.run_upgrade,
        "uninstall": cmd.run_uninstall,
    }
    handler = dispatch.get(args.command)
    if handler is None:
        console.print(f"命令 { args.command } 尚未实现")
        return 2
    return handler(args, console)


if __name__ == "__main__":
    sys.exit(main())
