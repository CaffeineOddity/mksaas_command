"""tests.test_init — mksaas init 编排器测试。

init 每次都从头走：project（展示已有信息 → 修改 repo url / 下一步 / 结束）
→ 全部 env 分组（每分组：[采集|修改] test / [采集|修改] prod / 下一步 / 结束）
→ apply。
"""

from __future__ import annotations

import argparse

import pytest

from mksaas import state
from mksaas.commands import init as init_cmd
from mksaas.console import FakeConsole
from mksaas.groups import groups_in_order


def make_args():
    return argparse.Namespace(command="init", version=False)


def _seed_project(tmp_path):
    """就位一个有效项目目录（project 已完成，core/database/better_auth 已采集）。"""
    state.ensure_state_dir(tmp_path)
    sp = tmp_path / state.STATE_DIRNAME / state.STATE_FILENAME
    s = state.init_default()
    s["project"] = {"repo_url": "https://github.com/o/r.git",
                    "project_dir": str(tmp_path)}
    s["steps"]["project"]["status"] = "completed"
    for prof, url in (("test", "https://t.com"), ("prod", "https://p.com")):
        s["profiles"][prof]["env_groups"]["core"] = {
            "NEXT_PUBLIC_BASE_URL": {"value": url, "source": "prompt",
                                     "required": True, "description": "x"}}
        s["profiles"][prof]["env_groups"]["database"] = {
            "DATABASE_URL": {"value": "postgres://x", "source": "prompt",
                             "required": True, "description": "x", "sensitive": True}}
        s["profiles"][prof]["env_groups"]["better_auth"] = {
            "BETTER_AUTH_SECRET": {"value": "sec", "source": "prompt",
                                   "required": True, "description": "x", "sensitive": True,
                                   "generate_if_empty": True}}
    state.save(sp, s)
    return tmp_path, sp


def _seed_empty_required(tmp_path):
    """就位 project 完成但所有 env 分组均未采集的状态。"""
    state.ensure_state_dir(tmp_path)
    sp = tmp_path / state.STATE_DIRNAME / state.STATE_FILENAME
    s = state.init_default()
    s["project"] = {"repo_url": "https://github.com/o/r.git",
                    "project_dir": str(tmp_path)}
    s["steps"]["project"]["status"] = "completed"
    state.save(sp, s)
    return tmp_path, sp


# 分组菜单：[采集|修改]test(1) / [采集|修改]prod(2) / 下一步(3) / [上一步(4)] / 结束
# 首个分组无「上一步」→ 4 项（1..4=结束）；其余分组 5 项（1..5=结束，4=上一步）
# 已采集分组：1=修改test 2=修改prod；未采集分组：1=采集test 2=采集prod；「下一步」恒为 3


def test_init_walks_all_groups_next(tmp_path, monkeypatch):
    """project 下一步 + 每个已采集分组都选「下一步」(3) → 走完全部 → apply 暂不。"""
    proj_dir, sp = _seed_project(tmp_path)
    monkeypatch.chdir(proj_dir)
    called = {"env": [], "apply": False}
    monkeypatch.setattr(init_cmd, "_run_env_step",
                        lambda gid, profile, console: called["env"].append((gid, profile)) or 0)
    monkeypatch.setattr(init_cmd, "_run_apply_step",
                        lambda console: called.__setitem__("apply", True) or 0)

    inputs = ["2"]  # project 下一步
    inputs += ["3"] * len(groups_in_order())  # 每个分组下一步
    inputs.append("2")  # apply 暂不
    c = FakeConsole(inputs=inputs)
    rc = init_cmd.run_init(make_args(), c)
    assert rc == 0
    assert called["env"] == []
    assert called["apply"] is False


def test_init_modify_test_of_group(tmp_path, monkeypatch):
    """project 下一步；对 core 选「修改 test」(1)→采集 test；其余下一步；apply 暂不。"""
    proj_dir, sp = _seed_project(tmp_path)
    monkeypatch.chdir(proj_dir)
    called = {"env": []}
    monkeypatch.setattr(init_cmd, "_run_env_step",
                        lambda gid, profile, console: called["env"].append((gid, profile)) or 0)
    monkeypatch.setattr(init_cmd, "_run_apply_step", lambda console: 0)

    inputs = ["2"]  # project 下一步
    inputs.append("1")  # core 修改 test
    inputs.append("3")  # core 采集后停留 → 选「下一步」→ 进 database
    inputs += ["3"] * (len(groups_in_order()) - 1)  # 其余分组下一步
    inputs.append("2")  # apply 暂不
    c = FakeConsole(inputs=inputs)
    rc = init_cmd.run_init(make_args(), c)
    assert rc == 0
    assert called["env"] == [("core", "test")]


def test_init_collect_test_stays_on_group(tmp_path, monkeypatch):
    """未采集分组：选采集 test(1) 后停留在该分组（再次出菜单），选结束(4)。"""
    proj_dir, sp = _seed_empty_required(tmp_path)
    monkeypatch.chdir(proj_dir)
    called = {"env": []}
    monkeypatch.setattr(init_cmd, "_run_env_step",
                        lambda gid, profile, console: called["env"].append((gid, profile)) or 0)
    monkeypatch.setattr(init_cmd, "_run_apply_step", lambda console: 0)

    # project 下一步(2)；core 采集 test(1) → 停留 → 结束(4) → apply 暂不(2)
    inputs = ["2", "1", "4", "2"]
    c = FakeConsole(inputs=inputs)
    rc = init_cmd.run_init(make_args(), c)
    assert rc == 0
    # 只在 core 上采集 test 一次；停留后选结束，未进入其它分组
    assert called["env"] == [("core", "test")]
    assert state.load(sp)["steps"]["init"]["ended_early"] is True


def test_init_end_early_runs_apply(tmp_path, monkeypatch):
    """选「结束」(4) 后询问 apply，选执行→进 apply；后续分组未被处理。"""
    proj_dir, sp = _seed_empty_required(tmp_path)
    monkeypatch.chdir(proj_dir)
    called = {"env": [], "apply": False}
    monkeypatch.setattr(init_cmd, "_run_env_step",
                        lambda gid, profile, console: called["env"].append((gid, profile)) or 0)
    monkeypatch.setattr(init_cmd, "_run_apply_step",
                        lambda console: called.__setitem__("apply", True) or 0)

    # project 下一步(2)；core 采集 test(1)→停留→结束(4) → apply 执行(1)
    inputs = ["2", "1", "4", "1"]
    c = FakeConsole(inputs=inputs)
    rc = init_cmd.run_init(make_args(), c)
    assert rc == 0
    assert called["env"] == [("core", "test")]
    assert called["apply"] is True
    assert state.load(sp)["steps"]["init"]["ended_early"] is True


def test_init_end_early_defer_apply(tmp_path, monkeypatch):
    """选「结束」后询问 apply，选暂不→不进 apply。"""
    proj_dir, sp = _seed_empty_required(tmp_path)
    monkeypatch.chdir(proj_dir)
    called = {"apply": False}
    monkeypatch.setattr(init_cmd, "_run_env_step", lambda gid, profile, console: 0)
    monkeypatch.setattr(init_cmd, "_run_apply_step",
                        lambda console: called.__setitem__("apply", True) or 0)

    # project 下一步(2)；core 采集 test(1)→停留→结束(4) → apply 暂不(2)
    inputs = ["2", "1", "4", "2"]
    c = FakeConsole(inputs=inputs)
    rc = init_cmd.run_init(make_args(), c)
    assert rc == 0
    assert called["apply"] is False


def test_init_apply_confirm_runs_apply(tmp_path, monkeypatch):
    """走完全部分组 → apply 确认执行→执行 apply。"""
    proj_dir, sp = _seed_project(tmp_path)
    monkeypatch.chdir(proj_dir)
    ran = {"apply": False}
    monkeypatch.setattr(init_cmd, "_run_env_step", lambda gid, profile, console: 0)
    monkeypatch.setattr(init_cmd, "_run_apply_step",
                        lambda console: ran.__setitem__("apply", True) or 0)

    inputs = ["2"]  # project 下一步
    inputs += ["3"] * len(groups_in_order())  # 每个分组下一步
    inputs.append("1")  # apply 执行
    c = FakeConsole(inputs=inputs)
    rc = init_cmd.run_init(make_args(), c)
    assert rc == 0
    assert ran["apply"] is True


def test_init_summary_masks_secrets(tmp_path, monkeypatch):
    """摘要不泄露密钥。"""
    proj_dir, sp = _seed_project(tmp_path)
    monkeypatch.chdir(proj_dir)
    monkeypatch.setattr(init_cmd, "_run_env_step", lambda gid, profile, console: 0)
    monkeypatch.setattr(init_cmd, "_run_apply_step", lambda console: 0)

    inputs = ["2"] + ["3"] * len(groups_in_order()) + ["2"]
    c = FakeConsole(inputs=inputs)
    init_cmd.run_init(make_args(), c)
    blob = "\n".join(c.stdout)
    assert "postgres://x" not in blob  # database url 不泄露


def test_init_project_end_early(tmp_path, monkeypatch):
    """project 步骤选「结束」→ 询问 apply，不进 env。"""
    proj_dir, sp = _seed_project(tmp_path)
    monkeypatch.chdir(proj_dir)
    called = {"env": [], "apply": False}
    monkeypatch.setattr(init_cmd, "_run_env_step",
                        lambda gid, profile, console: called["env"].append((gid, profile)) or 0)
    monkeypatch.setattr(init_cmd, "_run_apply_step",
                        lambda console: called.__setitem__("apply", True) or 0)

    # project 菜单 修改 repo url/下一步/结束 → 选结束(3) → apply 暂不(2)
    inputs = ["3", "2"]
    c = FakeConsole(inputs=inputs)
    rc = init_cmd.run_init(make_args(), c)
    assert rc == 0
    assert called["env"] == []
    assert called["apply"] is False
    assert state.load(sp)["steps"]["init"]["ended_early"] is True


def test_init_project_modify_repo_url(tmp_path, monkeypatch):
    """project 选「修改 repo url」→ 输入新地址；成功更新后继续 env。"""
    proj_dir, sp = _seed_project(tmp_path)
    monkeypatch.chdir(proj_dir)
    called = {"env": 0}
    monkeypatch.setattr(init_cmd, "_run_env_step",
                        lambda gid, profile, console: called.__setitem__("env", called["env"] + 1) or 0)
    monkeypatch.setattr(init_cmd, "_run_apply_step", lambda console: 0)

    # project 修改 repo url(1) → 预填当前值，输入新地址；每个分组下一步(3)；apply 暂不(2)
    inputs = ["1", "git@gitcafe:o/new.git"]
    inputs += ["3"] * len(groups_in_order())
    inputs.append("2")
    c = FakeConsole(inputs=inputs)
    rc = init_cmd.run_init(make_args(), c)
    assert rc == 0
    data = state.load(sp)
    assert data["project"]["repo_url"] == "git@gitcafe:o/new.git"
    assert called["env"] == 0


def test_init_project_modify_repo_url_cancel(tmp_path, monkeypatch):
    """project 修改 repo url 但留空（沿用当前值）→ 取消，不更新。"""
    proj_dir, sp = _seed_project(tmp_path)
    monkeypatch.chdir(proj_dir)
    monkeypatch.setattr(init_cmd, "_run_env_step", lambda gid, profile, console: 0)
    monkeypatch.setattr(init_cmd, "_run_apply_step", lambda console: 0)

    original = state.load(sp)["project"]["repo_url"]
    # 修改(1) → 留空（FakeConsole.input 留空返回 default=当前值，视为取消）
    # 用一个与当前值相同的输入模拟取消
    inputs = ["1", original]
    inputs += ["3"] * len(groups_in_order())
    inputs.append("2")
    c = FakeConsole(inputs=inputs)
    rc = init_cmd.run_init(make_args(), c)
    assert rc == 0
    assert state.load(sp)["project"]["repo_url"] == original


def test_init_no_state_runs_project(tmp_path, monkeypatch):
    """无状态文件 → 必须先跑 project；project 失败→终止。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_cmd, "_run_project_step", lambda console: 1)
    c = FakeConsole(inputs=[])
    rc = init_cmd.run_init(make_args(), c)
    assert rc != 0


def test_init_back_to_previous_group(tmp_path, monkeypatch):
    """非首个分组选「上一步」(4) → 回到上一个分组重新出菜单。"""
    proj_dir, sp = _seed_project(tmp_path)
    monkeypatch.chdir(proj_dir)
    called = {"env": [], "apply": False}
    monkeypatch.setattr(init_cmd, "_run_env_step",
                        lambda gid, profile, console: called["env"].append((gid, profile)) or 0)
    monkeypatch.setattr(init_cmd, "_run_apply_step",
                        lambda console: called.__setitem__("apply", True) or 0)

    # project 下一步(2)；core 下一步(3) → database「上一步」(4) → 回 core → 结束(4) → apply 暂不(2)
    inputs = ["2", "3", "4", "4", "2"]
    c = FakeConsole(inputs=inputs)
    rc = init_cmd.run_init(make_args(), c)
    assert rc == 0
    # 未触发任何采集，也未执行 apply
    assert called["env"] == []
    assert called["apply"] is False
    assert state.load(sp)["steps"]["init"]["ended_early"] is True
    # core 概要打印两次（首次进入 + 上一步回退后再次进入）
    blob = "\n".join(c.stdout)
    assert blob.count("=== 分组 core") == 2


def test_init_back_after_collect_stay(tmp_path, monkeypatch):
    """采集后停留菜单也支持「上一步」：database 采集后停留选上一步 → 回 core。"""
    proj_dir, sp = _seed_empty_required(tmp_path)
    monkeypatch.chdir(proj_dir)
    called = {"env": []}
    monkeypatch.setattr(init_cmd, "_run_env_step",
                        lambda gid, profile, console: called["env"].append((gid, profile)) or 0)
    monkeypatch.setattr(init_cmd, "_run_apply_step", lambda console: 0)

    # project 下一步(2)
    # core 采集 test(1) → 停留 core「下一步」(3) → database
    # database 采集 test(1) → 停留 database「上一步」(4) → 回 core
    # core 结束(4) → apply 暂不(2)
    inputs = ["2", "1", "3", "1", "4", "4", "2"]
    c = FakeConsole(inputs=inputs)
    rc = init_cmd.run_init(make_args(), c)
    assert rc == 0
    # core 采集 test 一次；database 采集 test 一次；回退后 core 选结束
    assert called["env"] == [("core", "test"), ("database", "test")]
    assert state.load(sp)["steps"]["init"]["ended_early"] is True
