# 构建、安装、升级与卸载

## 1. 目标

本文档定义 `mksaas` 的本地安装生命周期：版本号约定、构建产物、安装、升级与卸载。它是 `install.sh`、`build.sh`、`mksaas upgrade --local`、`mksaas uninstall` 的唯一真相来源。

`REQUIREMENTS.md` 只保留索引与本文件入口，详细规则以本文件为准。

## 2. 固定本地路径

`install.sh`、`build.sh`、`mksaas upgrade --local`、`mksaas uninstall` 共享以下固定本地路径（具体路径值由实现固定，所有脚本与命令须读写同一处）：

1. 安装目录：本地固定目录（如 `~/.mksaas-cli`），存放被安装的 `mksaas` 可执行文件及其版本信息
2. 构建产物目录：仓库固定目录（如 `<repo>/.build/dist`），`build.sh` 产出的 PyInstaller 发布产物落点，`mksaas upgrade --local` 从此处读取
3. 命令符号链接：`mksaas` 符号链接，指向安装目录内的可执行文件。PATH 目录优先级见 §6

## 3. 版本号约定与状态文件

仓库根目录维护一个构建配置文件（如 `build.config.json`），其中包含以下版本状态字段：

1. `version`：语义化版本号的基础部分，形如 `0.1.0`（`MAJOR.MINOR.PATCH`），不含 `-devN` 后缀
2. `build`：整数，表示当前 `version` 下的第几次 build，与 debug 产物 `-devN` 中的 `N` 一一对应

产物版本字符串规则：

1. debug 构建：`<version>-dev<build>`，例如 `0.1.0-dev10`
2. release 构建：`<version>`，不带 `-devN` 后缀，例如 `0.1.0`
3. 产物容器路径：`.build/dist/<产物版本字符串>/mksaas`
4. 默认目录型产物（`--onedir`）：可执行文件位于 `.build/dist/<产物版本字符串>/mksaas/mksaas`
5. 单文件产物（`--onefile`）：可执行文件位于 `.build/dist/<产物版本字符串>/mksaas`

### 3.1 build 行为

1. 开发态默认继续使用源码运行，`install.sh` 无参数安装源码入口；`build.sh` 主要用于生成可分发的本地发布产物
2. `build.sh` 默认为 debug 构建：读取 `version` 与 `build`，先计算 `next_build = build + 1`，默认产出目录型产物 `.build/dist/<version>-dev<next_build>/mksaas/`，其可执行文件为 `.../mksaas/mksaas`；仅在构建成功后，才把 `build` 字段回写为 `next_build`
3. `build.sh --release` 为 release 构建：读取 `version`，默认产出目录型产物 `.build/dist/<version>/mksaas/`，**不**递增 `build` 字段
4. `build.sh --onefile` 将产物切换为单文件模式；可与默认 debug 或 `--release` 组合
5. `build.sh --bump` 为版本号提升：默认提升 `PATCH` 位（`0.1.0` → `0.1.1`），`build` 重置为 `0`，回写状态文件后即结束（不产出二进制）；这样新版本第一次 debug 构建会产出 `dev1`
6. `--bump` 可选位级：`--bump --minor` 提升 `MINOR` 位并清零 `PATCH`（`0.1.5` → `0.2.0`）；`--bump --major` 提升 `MAJOR` 位并清零 `MINOR` 与 `PATCH`（`1.2.3` → `2.0.0`）；不指定位级时默认 `PATCH`
7. `--bump` 可与构建参数组合使用，如 `build.sh --bump` 后再 `build.sh`，或 `build.sh --bump --release` 一次性 bump 并产出 release 产物；组合时先 bump 回写状态，再按 `--release`/默认决定产物形态
8. `--minor` 与 `--major` 仅在与 `--bump` 组合时生效，单独使用应报错提示

### 3.2 示例

1. 当前状态 `version=0.1.0 build=10` → `build.sh`（debug）产出 `.build/dist/0.1.0-dev11/mksaas/`，状态变为 `version=0.1.0 build=11`
2. 当前状态 `version=0.1.0 build=10` → `build.sh --bump` 状态变为 `version=0.1.1 build=0`
3. 当前状态 `version=0.1.1 build=0` → `build.sh --release` 产出 `.build/dist/0.1.1/mksaas/`，状态不变
4. 当前状态 `version=0.1.1 build=3` → `build.sh --bump --minor` 状态变为 `version=0.2.0 build=0`
5. 当前状态 `version=1.2.3 build=5` → `build.sh --bump --major` 状态变为 `version=2.0.0 build=0`

## 4. build.sh

要求：

1. 仓库根目录提供 `build.sh`，用户执行 `bash build.sh` 构建产物
2. 使用 PyInstaller 构建发布产物；默认产出目录型二进制（`--onedir`），仅在显式传入 `--onefile` 时生成单文件产物
3. 版本号与产物路径遵循 §3 约定：debug 产物默认落 `.build/dist/<version>-dev<next_build>/mksaas/`，release 产物默认落 `.build/dist/<version>/mksaas/`
4. 构建产物容器名固定为 `mksaas`，便于 `upgrade --local` 与 `install.sh --version` 定位；目录型产物的实际可执行文件固定为 `mksaas/mksaas`
5. 支持参数：默认 debug 构建；`--release` 产出 release 产物；`--onefile` 切换到单文件产物；`--bump` 提升版本并重置 `build`（见 §3.1）；`--bump --minor` / `--bump --major` 指定位级；参数组合行为见 §3.1
6. 构建前校验 PyInstaller 是否可用；不可用时给出安装提示（如 `pip install pyinstaller`），不静默失败
7. 构建成功后打印产物路径（含版本字符串）、产物类型与可执行文件路径
8. debug 构建成功后必须将 `build` 字段回写为本次产物对应的 `next_build`；release 构建不递增 `build`
9. 产物二进制内嵌构建时的版本字符串，供 `upgrade --local` 与 `mksaas --version` 读取

## 5. install.sh

要求：

1. 仓库根目录提供 `install.sh`，用户执行 `bash install.sh` 或 `./install.sh` 完成安装
2. 安装方式为「本地目录 + 符号链接」：安装目录中保留一个稳定包装入口 `mksaas`，并在 PATH 可达目录建立 `mksaas` 符号链接指向它
3. 若安装目录或符号链接已存在，按升级语义处理（覆盖旧版），并提示用户
4. 安装完成后打印 `mksaas` 的实际路径与符号链接位置，并提示用户确认 PATH 是否包含符号链接所在目录
5. 安装失败时给出明确中文提示，不残留半安装状态（已写入的文件应回滚或提示用户手动清理）
6. 不自动修改用户 shell 配置文件；若符号链接目录不在 PATH，仅提示用户自行加入
7. install.sh 默认安装仓库源码入口（开发态安装），不自动切换到最新构建产物
8. 支持 `install.sh --version <版本字符串>` 安装 `.build/dist/` 下指定版本子目录的产物（如 `0.1.0-dev1`、`0.1.0`），同时兼容 `onedir` / `onefile`；该版本不存在时报错并列出可用版本后退出
9. 安装目录内保留固定的 `current/` 目录承载已安装发布产物：`onedir` 产物落 `current/mksaas/`，`onefile` 产物落 `current/mksaas`；稳定包装入口负责转发到真实可执行文件

## 6. 命令符号链接 PATH 优先级

`install.sh` 建立符号链接时，按以下优先级选择目标目录（命中第一个可写即用）：

1. 优先 `/usr/local/bin`（系统级，通常已在 PATH，所有用户可用）
2. 回退 `~/.local/bin`（用户级，无需 sudo，但可能需用户自行加入 PATH）

要求：

1. 优先尝试 `/usr/local/bin`；若不可写（无权限），回退 `~/.local/bin`
2. 回退到 `~/.local/bin` 时，若该目录不在 PATH，提示用户将其加入 shell 配置
3. 不静默提权；需要 sudo 写入 `/usr/local/bin` 时，提示用户手动以 sudo 执行或接受回退到 `~/.local/bin`

## 7. mksaas upgrade --local

要求：

1. `mksaas upgrade` 必须带 `--local` 子参数，表示从本地构建产物升级（首版只支持本地升级，不支持远程拉取）
2. 从构建产物目录读取 PyInstaller 发布产物，兼容 `onedir` / `onefile`，并替换安装目录中的当前发布内容
3. 升级前校验产物是否存在；不存在时提示用户先执行 `build.sh`
4. 升级前展示当前已安装版本与产物版本（产物内嵌的版本字符串，含 `-devN` 或 release 形态），让用户确认
5. 升级保留符号链接不动（指向同一安装路径），通过稳定包装入口切换到新的 `current/` 内容
6. 升级完成后打印新版本信息
7. 升级失败时不得破坏旧版可执行文件（建议先写入临时文件再原子替换）
8. `upgrade --local` 默认从构建产物目录中最新版本子目录（按 §3 版本字符串排序取最大）读取

## 8. mksaas uninstall

要求：

1. `mksaas uninstall` 卸载本地安装的 `mksaas`
2. 删除安装目录内的可执行文件与版本信息
3. 删除 PATH 目录下的 `mksaas` 符号链接
4. 卸载前展示将要删除的路径列表并让用户确认
5. 不删除用户项目内的 `.mksaas/` 状态目录与 `.env.*` 文件（这些属于用户项目，不属于 CLI 安装）
6. 卸载完成后提示用户卸载结果，并说明项目内配置不受影响

## 9. 安全要求

1. `install.sh`、`build.sh` 不内置任何凭据获取或网络鉴权逻辑
2. `build.sh` 仅在本地构建，不上传产物到任何远程
3. `upgrade --local` 仅读取本地构建产物目录，不发起网络请求
4. 安装、升级、卸载过程不得打印用户项目内的密钥、连接串、token
5. 写入符号链接到 `/usr/local/bin` 等系统目录时若需权限，提示用户而非静默提权

## 10. 异常处理

需要处理以下情况：

1. 构建配置文件（`build.config.json`）不存在或字段非法
2. `--bump` 时版本号格式不合法（非 `MAJOR.MINOR.PATCH`）
3. `--minor` / `--major` 未与 `--bump` 组合使用
4. PyInstaller 不可用
5. 构建产物目录不可写
6. 升级时构建产物不存在
7. 卸载时安装目录或符号链接不存在（幂等处理，提示已卸载）
8. 符号链接目标目录均不可写
