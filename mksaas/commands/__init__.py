"""mksaas.commands — 子命令分发入口聚合。"""

from mksaas.commands.apply import run_apply
from mksaas.commands.env import run_env
from mksaas.commands.init import run_init
from mksaas.commands.project import run_project
from mksaas.commands.uninstall import run_uninstall
from mksaas.commands.upgrade import run_upgrade

__all__ = ["run_init", "run_project", "run_env", "run_apply",
           "run_upgrade", "run_uninstall"]
