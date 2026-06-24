"""tests.test_uninstall — mksaas uninstall 测试。"""

from __future__ import annotations

import argparse
from pathlib import Path

from mksaas import paths
from mksaas.commands import uninstall as uninstall_cmd
from mksaas.console import FakeConsole


def make_args():
    return argparse.Namespace(command="uninstall", version=False)


def test_uninstall_removes_exe_and_symlink(tmp_path, monkeypatch):
    """卸载删除可执行文件、版本信息与符号链接。"""
    install = tmp_path / "install"
    install.mkdir()
    (install / "mksaas").write_text("bin")
    (install / "VERSION.installed").write_text("{}")
    link_dir = tmp_path / "bin"
    link_dir.mkdir()
    link = link_dir / "mksaas"
    link.symlink_to(install / "mksaas")

    monkeypatch.setattr(paths, "install_dir", lambda: install)
    monkeypatch.setattr(paths, "executable_path", lambda: install / "mksaas")
    monkeypatch.setattr(paths, "version_info_path", lambda: install / "VERSION.installed")
    monkeypatch.setattr(paths, "symlink_target", lambda: link)
    monkeypatch.setattr(paths, "symlink_dir", lambda: link_dir)

    c = FakeConsole(inputs=["y"])
    rc = uninstall_cmd.run_uninstall(make_args(), c)
    assert rc == 0
    assert not (install / "mksaas").exists()
    assert not (install / "VERSION.installed").exists()
    assert not link.exists()


def test_uninstall_idempotent_when_absent(tmp_path, monkeypatch):
    """幂等：已不存在→提示已卸载。"""
    install = tmp_path / "install"
    install.mkdir()
    link_dir = tmp_path / "bin"
    link_dir.mkdir()
    monkeypatch.setattr(paths, "install_dir", lambda: install)
    monkeypatch.setattr(paths, "executable_path", lambda: install / "mksaas")
    monkeypatch.setattr(paths, "version_info_path", lambda: install / "VERSION.installed")
    monkeypatch.setattr(paths, "symlink_target", lambda: link_dir / "mksaas")
    monkeypatch.setattr(paths, "symlink_dir", lambda: link_dir)

    c = FakeConsole(inputs=["y"])
    rc = uninstall_cmd.run_uninstall(make_args(), c)
    assert rc == 0
    assert any("已卸载" in line or "未安装" in line for line in c.stdout)


def test_uninstall_declined_keeps(tmp_path, monkeypatch):
    """用户不确认→保留。"""
    install = tmp_path / "install"
    install.mkdir()
    (install / "mksaas").write_text("bin")
    monkeypatch.setattr(paths, "install_dir", lambda: install)
    monkeypatch.setattr(paths, "executable_path", lambda: install / "mksaas")
    monkeypatch.setattr(paths, "version_info_path", lambda: install / "VERSION.installed")
    monkeypatch.setattr(paths, "symlink_target", lambda: tmp_path / "bin" / "mksaas")
    monkeypatch.setattr(paths, "symlink_dir", lambda: tmp_path / "bin")

    c = FakeConsole(inputs=["n"])
    rc = uninstall_cmd.run_uninstall(make_args(), c)
    assert rc == 0
    assert (install / "mksaas").exists()


def test_uninstall_does_not_touch_project_mksaas(tmp_path, monkeypatch):
    """卸载不删用户项目内 .mksaas/。"""
    # 假项目目录（模拟用户项目）
    project = tmp_path / "myproject"
    (project / ".mksaas").mkdir(parents=True)
    (project / ".mksaas" / "setup-state.json").write_text("{}")

    install = tmp_path / "install"
    install.mkdir()
    (install / "mksaas").write_text("bin")
    monkeypatch.setattr(paths, "install_dir", lambda: install)
    monkeypatch.setattr(paths, "executable_path", lambda: install / "mksaas")
    monkeypatch.setattr(paths, "version_info_path", lambda: install / "VERSION.installed")
    monkeypatch.setattr(paths, "symlink_target", lambda: tmp_path / "bin" / "mksaas")
    monkeypatch.setattr(paths, "symlink_dir", lambda: tmp_path / "bin")

    c = FakeConsole(inputs=["y"])
    uninstall_cmd.run_uninstall(make_args(), c)
    # 项目内 .mksaas 仍在
    assert (project / ".mksaas" / "setup-state.json").exists()
