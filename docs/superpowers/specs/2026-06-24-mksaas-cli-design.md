# MkSaaS Python CLI — 设计规格

- 日期：2026-06-24
- 状态：待评审
- 范围：从零实现 `mksaas` Python CLI，覆盖需求文档（REQUIREMENTS.md / docs/steps / docs/env-groups / docs/env-schema.yaml / docs/build_install_upgrade_uninstall.md）的全部需求点

本规格不重复需求细节，只锁定**架构边界、特性拆分顺序、可测性策略与每特性验收**。需求以现有文档为唯一真相来源；冲突时文档优先。

## 1. 技术约束（来自 REQUIREMENTS §10）

1. Python 3 实现（实际 3.10）
2. 优先标准库；唯一第三方依赖：`PyYAML`（加载 env-schema.yaml，开发机已装 6.0.3）
3. CLI 首版用 `argparse`
4. 函数级注释
5. 兼容重复执行，优先复用状态文件已有值
6. 统一交互：读取已有值 → 确认 → 修改 → 回写

测试：`pytest`（已装 9.1.1）。打包：`PyInstaller`（仅 build.sh 阶段需要，运行时不强依赖）。

## 2. 目录结构

```text
mksaas_command/
├── mksaas/                      ← Python 包（CLI 运行入口）
│   ├── __init__.py
│   ├── __main__.py              ← python -m mksaas 入口
│   ├── cli.py                   ← argparse 主入口与子命令分发
│   ├── console.py               ← Console 接口与默认终端实现（可测性缝）
│   ├── state.py                 ← setup-state.json 读写、定位、初始化
│   ├── schema.py                ← 加载 env-schema.yaml，提供变量全集
│   ├── masking.py               ← 密钥/连接串/token 摘要脱敏
│   ├── repo_url.py              ← repo_url 清洗（剥离鉴权段）
│   ├── secrets_gen.py           ← 安全随机数生成（BETTER_AUTH_SECRET）
│   ├── groups.py                ← 分组 id 连字符↔下划线映射、顺序、元信息
│   ├── prompts.py               ← 通用采集交互（已有值展示/确认/逐项输入/校验）
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── project.py           ← mksaas project
│   │   ├── env.py               ← mksaas env <group> [--profile]
│   │   ├── apply.py             ← mksaas apply
│   │   ├── init.py              ← mksaas init（编排器）
│   │   ├── upgrade.py           ← mksaas upgrade --local
│   │   └── uninstall.py         ← mksaas uninstall
│   ├── env_writer.py            ← 全量重建 .env.test/.env.prod、复制根 .env
│   ├── version.py               ← 读 VERSION，构造版本字符串
│   └── paths.py                 ← 固定本地路径（安装/产物/符号链接）
├── VERSION                      ← {version, build}
├── build.sh
├── install.sh
├── tests/                       ← pytest，每特性一个测试文件
└── docs/  (既有)
```

## 3. 架构边界（每个单元单一职责，可独立测试）

1. **state.py**：唯一负责 `.mksaas/setup-state.json` 的读写与定位。提供 `locate_state_file(cwd)`、`load(path)`、`save(path, data)`、`init_default()`。不交互、不打印。
2. **schema.py**：加载 `docs/env-schema.yaml`，返回按 `order` 排序的 group 列表与变量定义。无副作用。
3. **groups.py**：`group_kebab_to_snake` / `group_snake_to_kebab`、`ordered_groups()`。无 I/O。
4. **masking.py**：`mask(value)`——按类型摘要。纯函数。
5. **repo_url.py**：`clean_repo_url(url)`——剥离 `user:token@`，校验格式。纯函数。
6. **secrets_gen.py**：`gen_better_auth_secret()`——`secrets.token_urlsafe(48)`。纯函数。
7. **console.py**：定义 `Console` 协议（`print`、`input`、`getpass`、`confirm`）；`TerminalConsole` 为默认实现；测试用 `FakeConsole`（预置响应队列 + 记录输出）。
8. **prompts.py**：通用采集流，依赖 `Console` 与 `schema`。`collect_group(state, group_id, profile, console)`：展示已有值 → 确认是否修改 → 逐项采集（敏感字段走 getpass）→ 校验 → 回写。
9. **commands/**：每个子命令一个模块，编排上述单元；不直接读 stdin。
10. **env_writer.py**：`rebuild_envs(state, schema)` 全量重建两个 `.env.*`；`sync_root_env(state, profile)` 重建根 `.env`。
11. **version.py / paths.py**：构建/安装生命周期专用，独立可测。

依赖方向：`commands → prompts/state/schema/env_writer → console`。底层无反向依赖，便于单测。

## 4. 可测性策略：Console 缝

所有终端 I/O 经 `Console` 接口。测试注入 `FakeConsole`：

- 预置响应队列（普通 `input` 与 `getpass` 分队列，或带类型标记）
- 记录所有 `print` 输出，断言脱敏、提示文案、退出提示
- `confirm` 返回 bool，便于驱动“沿用/修改”分支

这样无需 PTY 即可端到端验证 `env` / `project` / `init` / `apply` 的交互流与回写结果。真实终端交互由 `qa-tester` agent（tmux）在集成阶段抽样验证。

文件系统副作用（写 setup-state.json、.env.*、clone）用 `tmp_path` 隔离；git/网络操作（clone、push、open github.com/new）封装在薄函数后，测试中 monkeypatch 为桩，断言“调用了什么、传了什么参数”，不真正联网。

## 5. 特性拆分与开发顺序（command-by-command）

每特性严格走：**阅读文档 → 写测试用例 → 编码 → review → 验证测试 → 修复 → commit & push**。commit 信息以 `feat:` / `fix:` 前缀，符合现有 `docs:` 风格的中文描述体例。

| # | 特性 | 依赖 | 主要测试用例 |
|---|------|------|-------------|
| F0 | 脚手架 + console 缝 | — | cli 分发未知命令报错；FakeConsole 记录 |
| F1 | state.py 状态文件读写与定位 | F0 | 定位规则；损坏 JSON 报错；init_default 结构；幂等 save |
| F2 | schema.py + groups.py | F0 | 加载 schema；分组顺序固定；连字符↔下划线映射 |
| F3 | masking.py + repo_url.py + secrets_gen.py | F0 | mask 不泄露全量；剥离鉴权段；密钥长度与随机性 |
| F4 | `mksaas project` | F1,F3 | direct_clone/template_init/existing_local 分流；干净 URL 落盘；目录已存在冲突；提示 cd |
| F5 | prompts.py 通用采集 | F2,F0 | 沿用已有值；修改逐项；敏感字段隐藏；回写结构正确 |
| F6 | `mksaas env <group>` | F1,F2,F5 | 17 分组顺序映射；test/prod 写入对应 profile；已有值确认；非项目目录提示 |
| F7 | env_writer.py 全量重建 | F2,F1 | schema 全变量遍历；已采集取值/未采集取默认/无默认写空串；必填缺失拦截；先删后建不留旧变量；.env 同步来源 |
| F8 | `mksaas apply` | F4,F6,F7 | project 缺失终止；必填校验；重建+同步；should_push 真假分支；push 鉴权失败提示；回写 steps.apply |
| F9 | `mksaas init` 编排器 | F4,F6,F8 | project 必填不可跳；env 可跳；apply 前停确认；续跑进度；不泄露密钥摘要 |
| F10 | VERSION/build.sh | — | debug 产物路径与 build+1；--release 不递增；--bump PATCH/minor/major；--minor 单用报错 |
| F11 | install.sh + paths.py + upgrade --local + uninstall | F10 | 符号链接 PATH 优先级回退；install 来源判定；upgrade 原子替换、保留符号链接；uninstall 幂等、不删项目内 .mksaas |

F0–F3 为底层基石；F4–F9 为主线命令；F10–F11 为安装生命周期。每特性独立 commit & push。

## 6. 交互与脱敏约定（统一）

1. 进入任一步骤先读状态、展示已有值（敏感字段以 `mask()` 摘要，如 `abcd…wxyz`）
2. 确认沿用 → 直接回写标记；选修改 → 逐项输入（敏感走 getpass）
3. 回写后提示“已采集未应用，需在 apply 阶段统一落地”
4. project 命令结尾提示 `cd <project_dir>` 后再执行 `mksaas env <group>`
5. 所有 repo_url 输出为干净 URL；误输入鉴权段时剥离并提示

## 7. 错误处理与异常

1. JSON 损坏/字段非法 → 明确中文提示，不静默覆盖
2. 逐步模式状态文件缺失 → 提示先执行 `mksaas project`，不自行创建
3. apply 缺 project → 终止并提示
4. clone/push 鉴权失败 → 提示检查本地凭据，不注入
5. 必填缺失 → 拦截并提示返回对应 `env` 补全
6. 构建产物不存在 → 提示先 `build.sh`

## 8. 验收（对应 REQUIREMENTS §11）

逐特性测试覆盖；F11 完成后，§11 全部条目由测试 + qa-tester 抽样人工验证共同保证。push 仍受当前 git 鉴权 403 阻塞——按用户选择“我来修 auth”，循环会在 auth 就绪后随特性推进逐步 push；未就绪期间本地累积 commit。

## 9. 未决/留待实现期决定

1. `modules` 块（provider/enabled/plans）在首版只做最小落盘与透传，深度采集留后续——首版 env 命令聚焦 schema 变量采集，modules 仅 project 阶段初始化默认结构
2. `SETUP_NEXT_STEPS.md` 内容模板在 F8 实现期确定
3. install.sh 来源判定（`.build/dist` 最新产物 vs 源码入口）在 F11 实现期按文档 §5 第 7 条固定
