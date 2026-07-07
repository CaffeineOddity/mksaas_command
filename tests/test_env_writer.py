"""tests.test_env_writer — env 文件全量重建测试。"""

from __future__ import annotations

from pathlib import Path

from mksaas import env_writer, state
from mksaas.schema import load_schema


def _state_with_test_core():
    s = state.init_default()
    s["profiles"]["test"]["env_groups"]["core"] = {
        "NEXT_PUBLIC_BASE_URL": {
            "value": "https://test.example.com", "source": "prompt",
            "required": True, "description": "应用基础 URL",
        }
    }
    return s


def test_rebuild_uses_collected_values(tmp_path):
    """已采集非空取状态值。"""
    s = _state_with_test_core()
    missing = env_writer.rebuild_envs(s, load_schema(), tmp_path)
    env_test = (tmp_path / ".mksaas" / ".env.test").read_text()
    assert "NEXT_PUBLIC_BASE_URL=https://test.example.com" in env_test
    # core 无缺失
    assert missing["test"] == [] or "NEXT_PUBLIC_BASE_URL" not in missing["test"]


def test_rebuild_uses_schema_default_when_uncollected(tmp_path):
    """未采集变量取 schema default（如 STORAGE_REGION=auto）。"""
    s = state.init_default()  # 未采集任何分组
    env_writer.rebuild_envs(s, load_schema(), tmp_path)
    env_test = (tmp_path / ".mksaas" / ".env.test").read_text()
    assert "STORAGE_REGION=auto" in env_test


def test_rebuild_writes_group_comments_and_blank_lines(tmp_path):
    """每个分组有注释标题，组间空一行，变量行带描述注释。"""
    s = state.init_default()
    env_writer.rebuild_envs(s, load_schema(), tmp_path)
    env_test = (tmp_path / ".mksaas" / ".env.test").read_text()
    # 分组标题
    assert "# ==== 数据库连接 ====" in env_test
    assert "# ==== 认证密钥与鉴权核心配置 ====" in env_test
    # 变量描述注释在 key 的上一行
    assert "# Storage region\nSTORAGE_REGION=auto" in env_test
    # 组间空行：标题行之间至少有一个空行分隔
    assert "\n\n# ==== 认证密钥" in env_test


def test_rebuild_empty_string_when_no_default_optional(tmp_path):
    """无 default 且非必填→写空串。"""
    s = state.init_default()
    env_writer.rebuild_envs(s, load_schema(), tmp_path)
    env_test = (tmp_path / ".mksaas" / ".env.test").read_text()
    assert "GITHUB_CLIENT_ID=" in env_test  # 空串


def test_rebuild_deletes_old_vars(tmp_path):
    """先删后建：旧文件中多余变量不残留。"""
    state_dir = tmp_path / ".mksaas"
    state_dir.mkdir()
    old = state_dir / ".env.test"
    old.write_text("STALE_VAR=keepme\nNEXT_PUBLIC_BASE_URL=old\n")
    s = _state_with_test_core()
    env_writer.rebuild_envs(s, load_schema(), tmp_path)
    content = old.read_text()
    assert "STALE_VAR" not in content
    assert "NEXT_PUBLIC_BASE_URL=https://test.example.com" in content


def test_required_missing_reported(tmp_path):
    """必填缺失→返回缺失列表，不写该变量。

    注：NEXT_PUBLIC_BASE_URL 有 schema 默认 http://localhost:3000，
    故仅 DATABASE_URL（无默认）出现在缺失列表。
    """
    s = state.init_default()  # core 的 NEXT_PUBLIC_BASE_URL 必填但未采集（取默认）
    missing = env_writer.rebuild_envs(s, load_schema(), tmp_path)
    assert "DATABASE_URL" in missing["test"]
    # NEXT_PUBLIC_BASE_URL 有默认值，不视为缺失
    assert "NEXT_PUBLIC_BASE_URL" not in missing["test"]


def test_better_auth_generate_if_empty(tmp_path):
    """generate_if_empty 且空→生成并回写状态。"""
    s = state.init_default()
    env_writer.rebuild_envs(s, load_schema(), tmp_path)
    env_test = (tmp_path / ".mksaas" / ".env.test").read_text()
    # 应有非空值
    for line in env_test.splitlines():
        if line.startswith("BETTER_AUTH_SECRET="):
            assert len(line.split("=", 1)[1]) >= 32
            return
    raise AssertionError("BETTER_AUTH_SECRET 未写入")


def test_both_profiles_written(tmp_path):
    """.env.test 与 .env.prod 都生成。"""
    s = state.init_default()
    env_writer.rebuild_envs(s, load_schema(), tmp_path)
    assert (tmp_path / ".mksaas" / ".env.test").is_file()
    assert (tmp_path / ".mksaas" / ".env.prod").is_file()


def test_sync_root_env(tmp_path):
    """sync_root_env 删除并按 profile 重建根 .env。"""
    s = _state_with_test_core()
    env_writer.rebuild_envs(s, load_schema(), tmp_path)
    root_env = tmp_path / ".env"
    root_env.write_text("OLD=1\n")
    env_writer.sync_root_env(s, tmp_path, "test")
    content = root_env.read_text()
    assert "OLD=1" not in content
    assert "NEXT_PUBLIC_BASE_URL=https://test.example.com" in content
