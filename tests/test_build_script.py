"""tests.test_build_script — build.sh 帮助文案测试。"""

from __future__ import annotations

import json
import shutil
import subprocess


def test_build_help_mentions_onefile_option():
    """build.sh --help 必须展示 --onefile 选项。"""
    out = subprocess.run(
        ["bash", "build.sh", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    blob = out.stderr + out.stdout
    assert "--onefile" in blob


def test_build_help_mentions_config_default_mode():
    """build.sh --help 必须说明默认模式来自 build.config.json。"""
    out = subprocess.run(
        ["bash", "build.sh", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    blob = out.stderr + out.stdout
    assert "build.config.json" in blob
    assert "当前: onedir" in blob


def test_build_new_creates_config_template(tmp_path):
    """build.sh new 应创建新的 build.config.json 模板。"""
    script = tmp_path / "build.sh"
    shutil.copy("build.sh", script)
    out = subprocess.run(
        ["bash", "build.sh", "new"],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )
    assert "build.config.json" in (out.stdout + out.stderr)
    cfg = json.loads((tmp_path / "build.config.json").read_text(encoding="utf-8"))
    assert cfg["entry"] == "main.py"
    assert cfg["build_root"] == ".build"
    assert cfg["default_bundle_mode"] == "onedir"
    assert cfg["version"] == "0.1.0"
    assert cfg["build"] == 0
