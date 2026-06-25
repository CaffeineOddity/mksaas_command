# 构建、安装、升级与卸载

## 1. 目标

本文档定义 `mksaas` 的安装生命周期：版本号约定、构建产物、安装、升级与卸载。它是 `shipcli build`、`pip install`、`mksaas upgrade`、`mksaas uninstall` 的唯一真相来源。

`REQUIREMENTS.md` 只保留索引与本文件入口，详细规则以本文件为准。

## 2. 交付体系

`mksaas` 采用标准的 Python 打包交付（与 `shipcli` 体系一致），不再使用 PyInstaller 二进制或 shell 脚本：

1. 包元数据：仓库根目录 `pyproject.toml`（PEP 621），定义包名 `mksaas`、入口点 `mksaas = "mksaas.cli:main"`、运行时依赖 `pyyaml`
2. 构建配置：仓库根目录 `build.config.json`，承载版本号与构建号状态（见 §3）
3. 构建产物：仓库固定目录 `<repo>/.build/dist/<版本>/dist/`，存放 wheel 与 sdist；`mksaas upgrade --local` 从此处读取
4. 安装方式：`pip install`（editable 开发态 / wheel 制品 / PyPI release 三选一），由 pip 负责把 `mksaas` 命令注册到 PATH

不再维护 `~/.mksaas-cli` 安装目录、`current/` 目录或 `/usr/local/bin` 符号链接——这些都由 pip 的 entry point 机制接管。

## 3. 版本号约定与状态文件

`build.config.json` 包含以下版本状态字段：

1. `version`：语义化版本号的基础部分，形如 `0.1.0`（`MAJOR.MINOR.PATCH`），不含开发后缀
2. `build`：整数，表示当前 `version` 下的第几次 dev 构建

产物版本字符串规则（PEP 440）：

1. dev 构建：`<version>.dev<build+1>`，例如 `0.1.0.dev4`
2. release 构建：`<version>`，例如 `0.1.0`
3. 产物路径：`.build/dist/<产物版本字符串>/dist/`，内含 `mksaas-<产物版本字符串>-py3-none-any.whl` 与 `mksaas-<产物版本字符串>.tar.gz`

版本号同时同步到三处，由 `shipcli build` 在构建时回写：

1. `build.config.json` —— 主源
2. `pyproject.toml` 的 `[project] version`
3. `mksaas/__init__.py` 的 `__version__`

### 3.1 build 行为

构建由 `shipcli build` 子命令完成（实现于 `shipcli.builder`，本仓库不自带 `build.sh`）：

1. `shipcli build`（默认 dev 构建）：计算 `next_build = build + 1`，产出 `.build/dist/<version>.dev<next_build>/dist/*.whl`；构建成功后把 `build` 字段回写为 `next_build`
2. `shipcli build --release`：产出 `.build/dist/<version>/dist/*.whl`，不递增 `build`；若在 git 仓库且有改动，自动提交 `release v<version>`
3. `shipcli build --increase {major,minor,patch}`：先提升对应版本位（低位归零）并把 `build` 重置为 0，再按 dev/release 决定产物形态
4. 构建使用 `python -m build`（依赖 `build` 包，见 `pyproject.toml` 的 `[project.optional-dependencies] build`）

### 3.2 示例

1. 当前 `version=0.1.0 build=3` → `shipcli build` 产出 `.build/dist/0.1.0.dev4/dist/`，状态变为 `version=0.1.0 build=4`
2. 当前 `version=0.1.0 build=4` → `shipcli build --release` 产出 `.build/dist/0.1.0/dist/`，状态不变
3. 当前 `version=0.1.0 build=4` → `shipcli build --increase minor` 状态变为 `version=0.2.0 build=0`，再构建产出 `0.2.0.dev1`

## 4. shipcli build

要求：

1. 仓库不提供 `build.sh`；用户执行 `shipcli build`（或 `shipcli build --release`）构建产物
2. 使用 `python -m build` 产出 wheel 与 sdist；不再使用 PyInstaller
3. 版本号与产物路径遵循 §3 约定：dev 产物落 `.build/dist/<version>.dev<next_build>/dist/`，release 产物落 `.build/dist/<version>/dist/`
4. 构建前同步版本号到 `pyproject.toml` 与 `mksaas/__init__.py`，使 wheel 元数据与运行时 `mksaas --version` 一致
5. 支持参数：默认 dev 构建；`--release` 产出 release 产物；`--increase {major,minor,patch}` 提升版本位；`--project <path>` 指定目标项目（默认当前目录）
6. 构建前校验 `build` 包是否可用；不可用时给出安装提示（如 `pip install build`），不静默失败
7. 构建成功后打印产物版本与 dist 目录路径
8. dev 构建成功后回写 `build` 字段；release 构建不递增 `build`

## 5. 安装

要求：

1. 三种安装形态，均由 pip 接管命令注册（写入 PATH 下的 `mksaas` entry point）：
   - **开发态（editable）**：`pip install -e .`，源码即装即改即生效
   - **本地制品**：`pip install .build/dist/<版本>/dist/*.whl`，安装某个本地构建产物
   - **正式发布**：`pip install mksaas`，从 PyPI 安装 release 版本
2. 安装完成后 `mksaas --version` / `mksaas --help` 应立即可用
3. 安装失败由 pip 报错；不残留半安装状态
4. 不修改用户 shell 配置文件；PATH 由 pip 与用户环境负责
5. 不再维护 `~/.mksaas-cli`、`current/` 目录或 `/usr/local/bin` 符号链接

## 6. mksaas upgrade

要求：

1. `mksaas upgrade` 默认从 PyPI 拉取最新 release：`pip install --upgrade mksaas`
2. `mksaas upgrade --version <v>` 升级到指定 PyPI 版本
3. `mksaas upgrade --local <project-root>` 从本地项目的构建产物升级：读取该项目的 `build.config.json`，定位 `<build_root>/dist/<version>/dist/*.whl` 并 `pip install --force-reinstall`
4. `--local` 不带 `--version` 时，默认取本地构建产物目录中版本号最大的那个（按 §3 版本字符串排序）
5. 升级前校验本地 wheel 是否存在；不存在时提示用户先执行 `shipcli build`
6. 升级由 pip 完成，覆盖旧版本；升级完成后打印新版本信息

## 7. mksaas uninstall

要求：

1. `mksaas uninstall` 卸载本地安装的 `mksaas`：`pip uninstall -y mksaas`
2. 清理可能残留的旧体系目录与符号链接（`~/.mksaas-cli`、`/usr/local/bin/mksaas`、`~/.local/bin/mksaas`），保证从旧 PyInstaller 安装迁移过来的用户也能干净卸载
3. 卸载幂等：安装目录或符号链接不存在时不报错，提示已卸载
4. 不删除用户项目内的 `.mksaas/` 状态目录与 `.env.*` 文件（这些属于用户项目，不属于 CLI 安装）
5. 卸载完成后提示用户卸载结果，并说明项目内配置不受影响

## 8. 安全要求

1. 构建与安装不内置任何凭据获取或网络鉴权逻辑
2. `shipcli build` 仅在本地构建；`--release` 自动 git commit 但不上传产物到任何远程（发布到 PyPI/GitHub Release 由 `shipcli publish` 单独负责，需用户显式触发）
3. `upgrade --local` 仅读取本地构建产物目录，不发起网络请求
4. 安装、升级、卸载过程不得打印用户项目内的密钥、连接串、token

## 9. 异常处理

需要处理以下情况：

1. 构建配置文件（`build.config.json`）不存在或字段非法
2. `--increase` 时版本号格式不合法（非 `MAJOR.MINOR.PATCH`）
3. `build` 包不可用
4. 构建产物目录不可写
5. `upgrade --local` 时本地 wheel 不存在
6. `upgrade --local` 时目标项目无 `build.config.json`
7. 卸载时包未安装或旧体系残留目录不存在（幂等处理，提示已卸载）
