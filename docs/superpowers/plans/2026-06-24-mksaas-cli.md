# MkSaaS CLI 实现计划（F0–F11）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从零实现纯 Python 的 `mksaas` CLI，覆盖 REQUIREMENTS.md 全部需求点。

**Architecture:** 分层包结构（state/schema/groups/masking/prompts/commands）。所有终端 I/O 经可注入 `Console` 缝；文件/git/网络副作用隔离在薄函数后供测试桩替换。每特性独立 TDD + commit。设计规格见 `docs/superpowers/specs/2026-06-24-mksaas-cli-design.md`。

**Tech Stack:** Python 3.10，标准库 + PyYAML；argparse；pytest（已装 9.1.1）。

## 公共约定（每个 Feature 通用）

- 文档为唯一真相来源，编码前先读对应文档（REQUIREMENTS.md / docs/steps / docs/env-groups / docs/env-schema.yaml / docs/build_install_upgrade_uninstall.md）。
- 测试放 `tests/`，命名 `test_<单元>.py`；用 `tmp_path` 隔离文件系统。
- 运行测试：`python -m pytest tests/<file> -v`（仓库根执行）。
- commit 信息中文 + `feat:`/`fix:`/`chore:` 前缀，结尾 `Co-Authored-By: Claude <noreply@anthropic.com>`。
- push 受当前 403 阻塞时本地 commit 累积；特性末尾执行 `git push || echo PUSH_BLOCKED` 记录结果。
- 每特性走：读文档 → 写测试（先红）→ 编码（转绿）→ review → 验证测试 → 修复 → commit & push。

## TDD 步骤模板（每特性统一）

每个测试用例按五步推进：
1. 写失败测试 → 2. `pytest` 验证红 → 3. 写最小实现 → 4. `pytest` 验证绿 → 5. commit。
下方每特性给出 **文件清单** 与 **测试用例清单**（断言细节按对应文档落实；验收点见规格 §5 表）。

---

## Feature F0：脚手架 + Console 缝

**Files:** `mksaas/__init__.py`、`mksaas/__main__.py`、`mksaas/console.py`、`mksaas/cli.py`、`tests/test_console.py`、`tests/test_cli_dispatch.py`

**测试用例：**
- `FakeConsole.print` 追加到 `stdout` 列表
- `FakeConsole.input` 按队列返回，耗尽抛 `IndexError`
- `FakeConsole.getpass` 按独立 `secrets` 队列返回
- `FakeConsole.confirm`：`y/yes`→True，`n/no`→False，空→默认值（默认 False）
- `TerminalConsole` 与 `FakeConsole` 接口方法同名：`print/input/getpass/confirm`
- `cli.main(["--version"])` 退出码 0 并打印版本占位
- `cli.main(["bogus"])` 退出码非 0

**Commit:** `feat: 脚手架与 Console 可测性缝`

---

## Feature F1：state.py 状态文件读写与定位

**先读：** REQUIREMENTS §5、§5.2；docs/steps/03-project.md §4.1/§4.2、§9；docs/setup-state.example.json

**Files:** `mksaas/state.py`、`tests/test_state.py`

**测试用例：**
- `locate_state_file(cwd)`：有 `.mksaas/setup-state.json`→返回路径；否则 None
- `load(path)` 合法 JSON；损坏 JSON 抛 `StateError`
- `save(path, data)` 幂等、目录不存在自动创建
- `init_default()` 含顶层 `version/project/steps/profiles/modules/artifacts/apply/meta`；`steps.{init,project,apply}` 有 status；`profiles.{test,prod}.env_groups` 空 dict
- `ensure_state_dir(project_dir)` 幂等建 `.mksaas/`
- `.gitignore` 追加 `.mksaas/`

**Commit:** `feat: 状态文件读写、定位与默认结构`

---

## Feature F2：schema.py + groups.py

**先读：** docs/env-schema.yaml；REQUIREMENTS §5.2、§5.2.1、§5.1

**Files:** `mksaas/schema.py`、`mksaas/groups.py`、`tests/test_schema.py`、`tests/test_groups.py`

**测试用例：**
- `load_schema()` 返回按 `order` 升序的 17 个 group（core…firecrawl）
- `groups_in_order()` 顺序固定一致
- `group_kebab_to_snake` / `group_snake_to_kebab` 双向映射
- 未知 group 抛 `KeyError`
- 每变量含 `name/required/default/generate_if_empty/sensitive/description`
- schema 文件缺失抛明确错误

**Commit:** `feat: env-schema 加载与分组标识符映射`

---

## Feature F3：masking.py + repo_url.py + secrets_gen.py

**先读：** REQUIREMENTS §9.1/§9.2/§9.3；docs/steps/03-project.md §10/§11

**Files:** `mksaas/masking.py`、`mksaas/repo_url.py`、`mksaas/secrets_gen.py`、3 个测试文件

**测试用例：**
- `mask("")`→`"<empty>"`；长值前4后4脱敏
- `clean_repo_url` 剥离 `user:token@` 并标记；SSH 原样；非法抛 `ValueError`
- `gen_better_auth_secret()` 长度 >32，两次不同，仅用 `secrets`

**Commit:** `feat: 脱敏、repo_url 清洗与安全密钥生成`

---

## Feature F4：mksaas project

**先读：** docs/steps/03-project.md 全文；REQUIREMENTS §6/§8/§9

**Files:** `mksaas/commands/project.py`、`mksaas/gitops.py`、`tests/test_project.py`

**测试用例（FakeConsole + monkeypatch gitops）：**
- 有状态→读已有 project，确认沿用
- existing_local：cwd 是 git 仓库→建 `.mksaas/`，回写 project_dir
- direct_clone：`git clone` 被调用且 URL 干净，apply_strategy=direct_clone
- template_init：`clone --origin upstream` + `remote add origin`，should_push=True
- 还没有仓库：`webbrowser.open` 被调用，回填后走 template_init
- repo_url 含鉴权段→剥离落盘并提示
- 目录已存在非目标仓库→抛错中文提示
- 结尾提示 `cd <project_dir>` 后执行 `mksaas env`

**Commit:** `feat: mksaas project 项目就位与仓库采集`

---

## Feature F5：prompts.py 通用采集

**先读：** docs/env-groups/01-core.md §5/§8；REQUIREMENTS §3.3

**Files:** `mksaas/prompts.py`、`tests/test_prompts.py`

**测试用例：**
- 已有值→展示（敏感 mask）→确认沿用→标记已采集
- 修改→逐项输入；敏感走 getpass；非必填空可留空；必填空重输
- core 的 URL 校验 http/https
- 回写结构 `profiles.<profile>.env_groups.<group>.<VAR>={value,source,required,description,sensitive?}`
- BETTER_AUTH_SECRET 空+自动生成→调 secrets_gen，source=`prompt_or_generate`

**Commit:** `feat: 通用环境分组采集交互`

---

## Feature F6：mksaas env <group>

**先读：** docs/env-groups/*.md §3/§4；REQUIREMENTS §5.1、§5.2

**Files:** `mksaas/commands/env.py`、`tests/test_env_command.py`

**测试用例：**
- `mksaas env core --profile test` 写入 profiles.test
- 连字符 `github-oauth`→github_oauth
- 缺省 profile→默认 test
- 非项目目录→提示先 `mksaas project`，不创建
- 未知 group→列分组并退出非 0

**Commit:** `feat: mksaas env 分组采集命令`

---

## Feature F7：env_writer.py 全量重建

**先读：** docs/steps/02-apply.md §10；REQUIREMENTS §5.2.1

**Files:** `mksaas/env_writer.py`、`tests/test_env_writer.py`

**测试用例：**
- 遍历 schema 全变量；已采集非空取值；未采集取 default；无 default 非必填空串
- 先删后建不留旧变量
- 必填缺失→返回缺失列表不写入
- generate_if_empty 空→生成回写
- 产物行格式 `KEY=VALUE`；`sync_root_env` 删后按 profile 重建根 `.env`

**Commit:** `feat: env 文件全量重建与根 .env 同步`

---

## Feature F8：mksaas apply

**先读：** docs/steps/02-apply.md 全文；REQUIREMENTS §6/§9/§11

**Files:** `mksaas/commands/apply.py`、`tests/test_apply.py`

**测试用例：**
- project 缺失→终止提示先 `mksaas project`
- 必填缺失→提示返回 `env <group>` 补全
- 确认→env_writer 重建+同步根 .env
- should_push 真假分支；repo_url 空→视为假跳过
- push 鉴权失败→中文提示检查凭据不重试
- 生成 SETUP_NEXT_STEPS.md；回写 steps.apply 与 apply.last_*；摘要用 mask

**Commit:** `feat: mksaas apply 统一执行落地`

---

## Feature F9：mksaas init 编排器

**先读：** docs/steps/01-init.md 全文；REQUIREMENTS §6/§7

**Files:** `mksaas/commands/init.py`、`tests/test_init.py`

**测试用例：**
- project 必填不可跳；拒绝→终止
- 逐个 env：处理或跳过；记 skipped
- `os.chdir(project_dir)` 后 env/apply 在项目目录读状态
- apply 前停确认；暂不→提示单独 `mksaas apply`
- 续跑从断点继续；回写 steps.init；摘要不泄露密钥

**Commit:** `feat: mksaas init 全流程编排器`

---

## Feature F10：VERSION + build.sh

**先读：** docs/build_install_upgrade_uninstall.md §2/§3/§4；REQUIREMENTS §12

**Files:** `VERSION`、`mksaas/version.py`、`mksaas/paths.py`、`build.sh`、`tests/test_version.py`

**测试用例：**
- `read_version()` 解析；`version_string` debug=`-devN`/release 无后缀
- `bump` patch/minor/major + build 重置 1
- build.sh 默认 debug 路径 `.build/dist/<v>-dev<b>/mksaas` 且 build+1；--release 不变；--bump 不产二进制；--minor 单用报错
- PyInstaller 不可用→提示不静默失败

**Commit:** `feat: 版本管理与 build.sh 构建`

---

## Feature F11：install.sh + upgrade --local + uninstall

**先读：** docs/build_install_upgrade_uninstall.md §5/§6/§7/§8/§9/§10

**Files:** `install.sh`、`mksaas/commands/upgrade.py`、`mksaas/commands/uninstall.py`、`tests/test_upgrade.py`、`tests/test_uninstall.py`

**测试用例：**
- paths：优先 /usr/local/bin 回退 ~/.local/bin
- upgrade：产物不存在提示 build.sh；原子替换保留符号链接；版本排序取最大
- uninstall：展示待删路径→确认→删；幂等；不删项目内 `.mksaas/`
- install.sh 来源判定：`.build/dist` 有产物→装产物；否则装源码入口

**Commit:** `feat: 安装、升级与卸载生命周期`

---

## 自检（规格覆盖）

- §2 目标 → F0/F1/F5/F6/F8/F10/F11 ✓
- §3 配置驱动/解耦/交互/脱敏 → F1/F5/F3 ✓
- §5 状态文件结构 → F1 ✓
- §5.2 分组标识符 → F2 ✓
- §5.2.1 schema 唯一真相 → F2/F7 ✓
- §5.1 17 分组命令 → F6 ✓
- §6/§7 流程时序 → F9/F4/F8 ✓
- §8 文件结构 → F1/F7 ✓
- §9 安全 → F3/F4/F8 ✓
- §11 验收 → F4/F6/F1/F8/F3/F10/F11 ✓
- §12 + build doc → F10/F11 ✓

无占位符；跨特性类型/函数名一致。
