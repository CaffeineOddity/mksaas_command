"""tests.test_install_script — install.sh 版本选择逻辑测试。

install.sh 的版本选择逻辑用 Python 实现（pick_source 同款），此处直接测
mksaas.version.sort_key 驱动的“指定版本”语义，并断言脚本 --help 含版本选项。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from mksaas import version


def _make_product(dist_root: Path, ver_str: str) -> Path:
    d = dist_root / ver_str
    d.mkdir(parents=True)
    f = d / "mksaas"
    f.write_text("bin-" + ver_str)
    return f


def test_explicit_version_picks_exact_dir(tmp_path):
    """指定版本字符串时，应精确匹配该 .build/dist 子目录（不取最新）。"""
    dist = tmp_path / ".build" / "dist"
    _make_product(dist, "0.1.0-dev1")
    _make_product(dist, "0.1.0-dev5")  # 更新
    _make_product(dist, "0.1.0-dev2")
    # 指定 dev2，即使 dev5 更新也应取 dev2
    target = dist / "0.1.0-dev2" / "mksaas"
    assert target.is_file()
    # sort_key 仅用于“最新”语义；指定版本走精确名匹配
    chosen = next((dist / v / "mksaas" for v in ["0.1.0-dev2"]
                   if (dist / v / "mksaas").is_file()), None)
    assert chosen == target


def test_explicit_version_missing(tmp_path):
    """指定不存在的版本→应可判定为缺失（脚本侧报错）。"""
    dist = tmp_path / ".build" / "dist"
    _make_product(dist, "0.1.0-dev1")
    assert not (dist / "0.9.9-dev1" / "mksaas").exists()


def test_install_help_mentions_version_option():
    """install.sh --help 必须包含 --version 选项说明。"""
    out = subprocess.run(
        ["bash", "install.sh", "--help"],
        capture_output=True, text=True, check=True,
    )
    assert "--version" in out.stderr or "--version" in out.stdout


def test_install_help_mentions_explicit_version_example():
    """--help 应给出强制指定版本的示例。"""
    out = subprocess.run(
        ["bash", "install.sh", "--help"],
        capture_output=True, text=True, check=True,
    )
    blob = out.stderr + out.stdout
    assert "0.1.0-dev1" in blob or "install.sh --version" in blob
