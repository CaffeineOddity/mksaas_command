"""mksaas.commands.upgrade — 从本地构建产物升级。

docs/build_install_upgrade_uninstall.md §7 为真相来源。
仅从本地 .build/dist 目录读取产物，不发起网络请求；原子替换保留符号链接。
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mksaas import paths, version
from mksaas.console import Console


@dataclass(frozen=True)
class LocalProduct:
    """本地构建产物的统一描述。"""

    version: str
    install_mode: str
    container_path: Path
    executable_path: Path


def _product_from_version_dir(version_dir: Path) -> LocalProduct | None:
    """从单个版本目录中识别 onefile / onedir 产物。"""
    container = version_dir / "mksaas"
    if container.is_dir() and (container / "mksaas").is_file():
        return LocalProduct(
            version=version_dir.name,
            install_mode="onedir",
            container_path=container,
            executable_path=container / "mksaas",
        )
    if container.is_file():
        return LocalProduct(
            version=version_dir.name,
            install_mode="onefile",
            container_path=container,
            executable_path=container,
        )
    return None


def _latest_product(dist_dir: Path) -> LocalProduct | None:
    """在构建产物目录下按版本字符串排序取最大版本子目录。"""
    if not dist_dir.is_dir():
        return None
    products = []
    for sub in dist_dir.iterdir():
        if not sub.is_dir():
            continue
        product = _product_from_version_dir(sub)
        if product is not None:
            products.append(product)
    if not products:
        return None
    products.sort(key=lambda p: version.sort_key(p.version))
    return products[-1]


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
    console.print(f"产物版本：{target.version}")
    console.print(f"产物类型：{target.install_mode}")
    if not console.confirm("是否升级？", default=True):
        console.print("已取消")
        return 0

    _install_product(target, paths.install_dir(), exe)
    _write_install_metadata(target.version, dist, target.install_mode)
    console.print(f"升级完成：{target.version}（符号链接未变动）")
    return 0


def _read_installed_version() -> str | None:
    """读取已安装版本信息。"""
    p = paths.version_info_path()
    if not p.is_file():
        return None
    try:
        raw = p.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw or None
    if isinstance(data, dict):
        value = data.get("installed_from")
        return value if isinstance(value, str) and value else None
    return raw or None


def _write_install_metadata(installed_from: str, dist_dir: Path, install_mode: str) -> None:
    """回写安装元信息，保留已有 repo_root/build_dist_dir。"""
    payload = paths.install_metadata()
    payload["installed_from"] = installed_from
    payload["build_dist_dir"] = str(dist_dir)
    payload["install_mode"] = install_mode
    paths.version_info_path().write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _install_product(product: LocalProduct, install_dir: Path, wrapper_path: Path) -> None:
    """把 onefile / onedir 产物安装到固定 current 目录，并刷新包装入口。"""
    install_dir.mkdir(parents=True, exist_ok=True)
    current = install_dir / "current"
    stage = install_dir / "current.tmp"
    backup = install_dir / "current.bak"

    _remove_path(stage)
    stage.mkdir(parents=True)
    if product.install_mode == "onefile":
        target = stage / "mksaas"
        shutil.copy2(product.container_path, target)
        target.chmod(0o755)
        exec_target = current / "mksaas"
    else:
        shutil.copytree(product.container_path, stage / "mksaas")
        exec_target = current / "mksaas" / "mksaas"

    _swap_product_dir(stage, current, backup)
    _write_exec_wrapper(wrapper_path, exec_target)


def _swap_product_dir(stage: Path, current: Path, backup: Path) -> None:
    """用 staged 目录替换 current，失败时回滚旧目录。"""
    _remove_path(backup)
    if current.exists():
        current.rename(backup)
    try:
        stage.rename(current)
    except Exception:
        _remove_path(current)
        if backup.exists():
            backup.rename(current)
        raise
    _remove_path(backup)


def _write_exec_wrapper(wrapper_path: Path, target_path: Path) -> None:
    """写入稳定的包装脚本，让 PATH 中的 mksaas 始终指向固定入口。"""
    wrapper_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = wrapper_path.with_suffix(wrapper_path.suffix + ".tmp")
    tmp.write_text(
        "#!/usr/bin/env bash\n"
        f'exec "{target_path}" "$@"\n',
        encoding="utf-8",
    )
    tmp.chmod(0o755)
    tmp.replace(wrapper_path)


def _remove_path(path: Path) -> None:
    """删除文件或目录；不存在时静默跳过。"""
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)
