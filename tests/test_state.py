"""tests.test_state — 状态文件读写、定位与默认结构。"""

import json

import pytest

from mksaas.state import (
    StateError,
    ensure_state_dir,
    init_default,
    load,
    locate_state_file,
    save,
)


def test_locate_state_file_found(tmp_path):
    state_dir = tmp_path / ".mksaas"
    state_dir.mkdir()
    (state_dir / "setup-state.json").write_text("{}")
    p = locate_state_file(tmp_path)
    assert p == state_dir / "setup-state.json"


def test_locate_state_file_missing(tmp_path):
    assert locate_state_file(tmp_path) is None


def test_load_valid(tmp_path):
    p = tmp_path / "s.json"
    p.write_text('{"a": 1}')
    assert load(p) == {"a": 1}


def test_load_corrupt_raises(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{not json")
    with pytest.raises(StateError):
        load(p)


def test_save_creates_dir_and_idempotent(tmp_path):
    p = tmp_path / ".mksaas" / "setup-state.json"
    data = {"x": 1}
    save(p, data)
    save(p, data)
    assert json.loads(p.read_text()) == data


def test_init_default_top_level_keys():
    s = init_default()
    for k in ("version", "project", "steps", "profiles", "modules", "artifacts", "apply", "meta"):
        assert k in s, f"缺顶层 {k}"
    for step in ("init", "project", "apply"):
        assert "status" in s["steps"][step]
    assert s["profiles"]["test"]["env_groups"] == {}
    assert s["profiles"]["prod"]["env_groups"] == {}


def test_ensure_state_dir_idempotent(tmp_path):
    ensure_state_dir(tmp_path)
    assert (tmp_path / ".mksaas").is_dir()
    ensure_state_dir(tmp_path)  # 再次调用不应报错
    assert (tmp_path / ".mksaas").is_dir()


def test_ensure_gitignore_appends_mksaas(tmp_path):
    ensure_state_dir(tmp_path)
    gi = tmp_path / ".gitignore"
    assert ".mksaas" in gi.read_text()
