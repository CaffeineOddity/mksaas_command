# mksaas

MkSaaS 配置编排 CLI —— 一个纯 Python 实现的命令行工具，用于引导 MkSaaS 项目从仓库就位、环境变量采集到 `.env` 文件落地与推送的完整配置流程。

采用「先采集配置到统一 JSON 状态文件，后统一生成环境」的模式：每一步只负责收集/校验/更新状态，最后由 `apply` 统一落地。

## 安装

```bash
# 正式发布（从 PyPI）
pip install mksaas

# 开发态（editable，源码即改即生效）
pip install -e .

# 本地构建制品
shipcli build
pip install .build/dist/<版本>/dist/*.whl
```

安装完成后：

```bash
mksaas --version
mksaas --help
```

> 依赖 Python ≥ 3.10 与 `pyyaml`。

## 命令

```
mksaas <command> ...

命令:
  init       全流程编排器
  project    采集项目与仓库信息并就位本地目录
  env        采集某一环境分组
  apply      统一执行落地
  help       显示帮助信息
  version    打印当前版本号
  upgrade    升级本 CLI（默认从 PyPI，--local 用本地构建产物）
  uninstall  卸载本 CLI
```

### 业务命令

| 命令 | 作用 |
|---|---|
| `mksaas init` | 全流程编排器，串行引导 `project → env <group> × N → apply`，可重复执行、按已有进度续跑 |
| `mksaas project` | 采集项目与仓库信息，就位本地工作目录（clone / 绑定 remote），不推送 |
| `mksaas env <group> [--profile test\|prod]` | 采集并更新单个环境分组。17 个分组见 `mksaas env --help` |
| `mksaas apply` | 根据状态文件统一重建 `.env.test` / `.env.prod`，同步根 `.env`，并按策略推送 |

环境分组（`<group>`，kebab-case）：`core` `database` `better-auth` `github-oauth` `google-oauth` `email-newsletter` `storage` `payment` `configurations` `analytics` `notification` `affiliate` `captcha` `crisp` `cron-jobs` `ai` `firecrawl`。变量全集见 `docs/env-schema.yaml`。

### 交付命令

| 命令 | 作用 |
|---|---|
| `mksaas version` | 打印当前版本号 |
| `mksaas upgrade` | 默认从 PyPI 升级；`--local <project>` 从本地构建产物升级；`--version <v>` 指定版本 |
| `mksaas uninstall` | `pip uninstall` 并清理残留的旧体系目录/符号链接（不删项目内 `.mksaas/` 与 `.env.*`） |

## 工作流

```bash
mksaas init              # 串行引导完整流程（推荐入口）
# 或分步:
mksaas project           # 1. 仓库就位
mksaas env core          # 2. 逐个采集环境分组
mksaas env github-oauth --profile prod
mksaas apply             # 3. 统一落地 + 推送
```

状态文件位于项目内 `.mksaas/setup-state.json`，每步启动时先读取、修改后回写。

## 构建

本项目使用 [shipcli](https://github.com/CaffeineOddity/shipcli) 交付体系（wheel / sdist），不再使用 PyInstaller 或 shell 脚本：

```bash
shipcli build                 # dev 构建，产出 .build/dist/<version>.devN/dist/*.whl
shipcli build --release       # release 构建
shipcli build --increase minor  # 提升次版本号
```

构建细节、版本号约定与安装/升级/卸载规则见 [`docs/build_install_upgrade_uninstall.md`](docs/build_install_upgrade_uninstall.md)。

## 文档

- [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) —— 根需求文档与索引
- [`docs/build_install_upgrade_uninstall.md`](docs/build_install_upgrade_uninstall.md) —— 构建/安装/升级/卸载真相来源
- [`docs/steps/`](docs/steps/) —— 各步骤详细需求（init / apply / project）
- [`docs/env-groups/`](docs/env-groups/) —— 17 个环境分组定义
- [`docs/env-schema.yaml`](docs/env-schema.yaml) —— 环境变量全集（唯一真相来源）

## License

MIT
