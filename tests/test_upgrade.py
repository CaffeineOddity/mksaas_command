"""tests.test_upgrade — mksaas upgrade --local 测试。"""

from __future__ import annotations

import argparse
from pathlib import Path

from mksaas import paths
from mksaas.commands import upgrade as upgrade_cmd
from mksaas.console import FakeConsole


def make_args(local=True, product_version=None):
    return argparse.Namespace(command="upgrade", version=False,
                              local=local, product_version=product_version)


def _make_onedir_product(dist_root: Path, ver_str: str, content: str = "binary") -> Path:
    """在 dist_root 下造一个 onedir 版本产物目录。"""
    d = dist_root / ver_str
    f = d / "mksaas" / "mksaas"
    f.parent.mkdir(parents=True)
    f.write_text(content)
    return f


def _make_onefile_product(dist_root: Path, ver_str: str, content: str = "binary") -> Path:
    """在 dist_root 下造一个 onefile 版本产物文件。"""
    d = dist_root / ver_str
    d.mkdir(parents=True)
    f = d / "mksaas"
    f.write_text(content)
    return f


def test_upgrade_requires_local(tmp_path, monkeypatch):
    """upgrade 不带 --local → 报错。"""
    monkeypatch.setattr(paths, "dist_dir", lambda: tmp_path / ".build" / "dist")
    c = FakeConsole(inputs=[])
    rc = upgrade_cmd.run_upgrade(make_args(local=False), c)
    assert rc != 0
    assert any("--local" in line for line in c.stdout)


def test_upgrade_no_product_prompts_build(tmp_path, monkeypatch):
    """产物不存在→提示先 build.sh。"""
    monkeypatch.setattr(paths, "dist_dir", lambda: tmp_path / ".build" / "dist")
    c = FakeConsole(inputs=[])
    rc = upgrade_cmd.run_upgrade(make_args(), c)
    assert rc != 0
    assert any("build.sh" in line for line in c.stdout)


def test_upgrade_latest_version_selected(tmp_path, monkeypatch):
    """版本排序取最大：dev10 > dev2。"""
    dist = tmp_path / ".build" / "dist"
    _make_onedir_product(dist, "0.1.0-dev2", "old")
    _make_onedir_product(dist, "0.1.0-dev10", "new")
    monkeypatch.setattr(paths, "dist_dir", lambda: dist)
    monkeypatch.setattr(paths, "install_dir", lambda: tmp_path / "install")
    monkeypatch.setattr(paths, "executable_path", lambda: (tmp_path / "install") / "mksaas")

    c = FakeConsole(inputs=["y"])  # 确认升级
    rc = upgrade_cmd.run_upgrade(make_args(), c)
    assert rc == 0
    install = tmp_path / "install"
    bundle = install / "current" / "mksaas" / "mksaas"
    exe = install / "mksaas"
    assert bundle.read_text() == "new"
    assert str(bundle) in exe.read_text()


def test_upgrade_atomic_replaces(tmp_path, monkeypatch):
    """原子替换：写临时文件再 rename，失败不破坏旧版。"""
    dist = tmp_path / ".build" / "dist"
    _make_onedir_product(dist, "0.1.0-dev1", "newbin")
    install = tmp_path / "install"
    install.mkdir()
    exe = install / "mksaas"
    exe.write_text("old-wrapper")
    old_bundle = install / "current" / "mksaas" / "mksaas"
    old_bundle.parent.mkdir(parents=True)
    old_bundle.write_text("oldbin")

    monkeypatch.setattr(paths, "dist_dir", lambda: dist)
    monkeypatch.setattr(paths, "install_dir", lambda: install)
    monkeypatch.setattr(paths, "executable_path", lambda: exe)

    c = FakeConsole(inputs=["y"])
    rc = upgrade_cmd.run_upgrade(make_args(), c)
    assert rc == 0
    assert old_bundle.read_text() == "newbin"
    assert str(old_bundle) in exe.read_text()
    assert not (install / "current.tmp").exists()
    assert not (install / "current.bak").exists()
    assert not (install / "mksaas.tmp").exists()


def test_upgrade_declined_keeps_old(tmp_path, monkeypatch):
    """用户不确认→保留旧版。"""
    dist = tmp_path / ".build" / "dist"
    _make_onedir_product(dist, "0.1.0-dev1", "newbin")
    install = tmp_path / "install"
    install.mkdir()
    exe = install / "mksaas"
    exe.write_text("old-wrapper")
    old_bundle = install / "current" / "mksaas" / "mksaas"
    old_bundle.parent.mkdir(parents=True)
    old_bundle.write_text("oldbin")
    monkeypatch.setattr(paths, "dist_dir", lambda: dist)
    monkeypatch.setattr(paths, "install_dir", lambda: install)
    monkeypatch.setattr(paths, "executable_path", lambda: exe)

    c = FakeConsole(inputs=["n"])
    rc = upgrade_cmd.run_upgrade(make_args(), c)
    assert rc == 0
    assert exe.read_text() == "old-wrapper"
    assert old_bundle.read_text() == "oldbin"


def test_upgrade_supports_onefile_product(tmp_path, monkeypatch):
    """onefile 产物也能升级到固定 current 目录。"""
    dist = tmp_path / ".build" / "dist"
    _make_onefile_product(dist, "0.1.0", "release-bin")
    install = tmp_path / "install"

    monkeypatch.setattr(paths, "dist_dir", lambda: dist)
    monkeypatch.setattr(paths, "install_dir", lambda: install)
    monkeypatch.setattr(paths, "executable_path", lambda: install / "mksaas")

    c = FakeConsole(inputs=["y"])
    rc = upgrade_cmd.run_upgrade(make_args(), c)
    assert rc == 0
    assert (install / "current" / "mksaas").read_text() == "release-bin"
