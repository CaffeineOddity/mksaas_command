# install.mksass

用于在本机（MacOS）快速初始化一个 MkSaaS 项目：克隆模板（保留 template 远程）→ 绑定你的 GitHub 私有仓库并推送（可跳过）→ 生成 `.env.test/.env.prod` 与下一步配置指引。

## 前置条件

- `git`
- `openssl`
- `curl`

可选：

- `pnpm`（用于安装依赖与数据库迁移）
- `vercel`（Vercel CLI）
- `wrangler`（Cloudflare CLI）

## 使用

```bash
chmod +x ./main.sh ./mksaas-bootstrap.sh ./scripts/*.sh
./main.sh
```

也可以用兼容入口（同样是交互式）：

```bash
./mksaas-bootstrap.sh
```

## 安装为命令（推荐）

安装后可以在任意目录直接运行初始化命令：

```bash
chmod +x ./install.sh
./install.sh

mksaas init my-saas
```

安装后也支持 command 子命令模式：

```bash
mksaas init my-saas
mksaas project create my-saas
mksaas project clone https://github.com/MkSaaSHQ/mksaas-template.git main /absolute/path/to/your-project
cd /absolute/path/to/your-project
mksaas env generate
mksaas repo push
mksaas cloudflare r2
mksaas cloudflare turnstile
mksaas db neon
mksaas deploy vercel
mksaas auth github
```

卸载：

```bash
chmod +x ./uninstall.sh
./uninstall.sh
```

执行完成后：

- 项目代码在 `./my-saas/`
- 下一步手动配置说明在 `./my-saas/SETUP_NEXT_STEPS.md`
- 环境变量文件：
  - `./my-saas/.env.test`（测试/开发，默认本地开发）
  - `./my-saas/.env.prod`（正式/生产）
  - `./my-saas/.env` 会自动同步为 `.env.test`
- 敏感信息文件（不要提交）：
  - `./my-saas/.mksaas/secrets.test.env`
  - `./my-saas/.mksaas/secrets.prod.env`
- 项目元信息在 `./my-saas/.mksaas/project.yaml`

申请资源类命令会自动：

- 在 macOS 上用默认浏览器打开对应控制台/文档链接
- 在终端打印申请步骤说明，再提示你填写拿到的参数
- `mksaas init` 会按你选择的数据库、部署、Cloudflare、OAuth 选项，串起整套引导流

交互式流程会询问：

- 部署到哪里（Vercel / Cloudflare Workers PG / Cloudflare Workers D1 / 暂不部署）
- 使用哪个数据库（Neon / Supabase / 本地 Docker Postgres / 暂不配置；D1 部署会自动选择 D1）

## 脚本拆分

- `scripts/00-project-create.sh`：仅创建项目骨架目录与 `.mksaas/project.yaml`
- `scripts/10-clone-template.sh`：克隆模板并将 origin 重命名为 template
- `scripts/20-prepare-env.sh`：合并 `.mksaas/project.yaml`（非敏感）与 `secrets.*.env`（敏感）生成 `.env.test/.env.prod` 与 `SETUP_NEXT_STEPS.md`
- `scripts/21-env-setup.sh`：交互式配置 test/prod 环境（敏感值写入 `secrets.*.env`，并触发重新生成 env 文件）
- `scripts/30-github-create-push.sh`：绑定 GitHub 私有仓库远程并 push（仓库需提前创建）
- `scripts/40-print-hints.sh`：输出后续步骤提示
- `scripts/50-cloudflare-r2.sh`：单独配置 Cloudflare R2 存储环境变量
- `scripts/60-cloudflare-turnstile.sh`：单独配置 Cloudflare Turnstile 环境变量
- `scripts/70-database-neon.sh`：单独配置 Neon 的 `DATABASE_URL`
- `scripts/71-database-supabase.sh`：单独配置 Supabase 的 `DATABASE_URL`
- `scripts/72-database-local-postgres.sh`：单独生成本地 Postgres 的 `DATABASE_URL`
- `scripts/80-deploy-vercel.sh`：单独配置 Vercel 部署相关基础 URL
- `scripts/81-deploy-cloudflare-pg.sh`：单独配置 Cloudflare Workers（PG）部署相关基础 URL
- `scripts/82-deploy-cloudflare-d1.sh`：单独配置 Cloudflare Workers（D1）部署相关基础 URL
- `scripts/90-auth-github.sh`：单独配置 GitHub OAuth 环境变量
- `scripts/91-auth-google.sh`：单独配置 Google OAuth 环境变量
- `scripts/100-email-resend.sh`：单独配置 Resend 邮件服务
- `scripts/101-newsletter-setup.sh`：单独配置 Newsletter（Resend / Beehiiv）
- `scripts/110-payment-stripe.sh`：单独配置 Stripe 支付/订阅
- `scripts/111-payment-creem.sh`：单独配置 Creem 支付/订阅
- `scripts/120-notification-setup.sh`：单独配置支付通知（Discord / 飞书）
- `scripts/130-credits-setup.sh`：单独配置积分（Credits）价格 ID
- `scripts/140-analytics-setup.sh`：单独配置统计分析（Analytics）
- `scripts/150-affiliates-setup.sh`：单独配置联盟营销（Affiliates）
- `main.sh`：交互式聚合执行上述脚本

## Command 模式

`main.sh` / `mksaas` 既可以直接交互运行，也可以用两级子命令单独执行某一步：

```bash
./main.sh init [project_name]
./main.sh project create [project_name]
./main.sh project clone <project_dir>
./main.sh project clone <template_branch> <project_dir>
./main.sh project clone <template_repo> <template_branch> <project_dir>
./main.sh env setup [profile] [project_dir]
./main.sh env generate [project_dir]
./main.sh env migrate-secrets [project_dir]
./main.sh repo push [project_dir]
./main.sh repo push <project_dir> <repo_url>
./main.sh cloudflare r2 [project_dir]
./main.sh cloudflare turnstile [project_dir]
./main.sh db neon [project_dir]
./main.sh db supabase [project_dir]
./main.sh db local-postgres [project_dir]
./main.sh deploy vercel [project_dir]
./main.sh deploy cloudflare-pg [project_dir]
./main.sh deploy cloudflare-d1 [project_dir]
./main.sh auth github [project_dir]
./main.sh auth google [project_dir]
./main.sh email setup [project_dir]
./main.sh email resend [project_dir]
./main.sh email newsletter [project_dir]
./main.sh payment setup [project_dir]
./main.sh payment stripe [project_dir]
./main.sh payment creem [project_dir]
./main.sh notification setup [project_dir]
./main.sh credits setup [project_dir]
./main.sh analytics setup [project_dir]
./main.sh affiliates setup [project_dir]
```

## 常用命令示例

完整初始化（整套流程）：

```bash
mksaas init
mksaas init my-saas
```

只创建项目骨架：

```bash
mksaas project create
mksaas project create my-saas
```

进入项目目录后，后续命令会优先读取：

```bash
.mksaas/project.yaml
```

克隆模板：

```bash
mksaas project clone /absolute/path/to/my-saas
```

指定分支克隆：

```bash
mksaas project clone cloudflare /absolute/path/to/my-saas
```

完全自定义模板仓库：

```bash
mksaas project clone https://github.com/MkSaaSHQ/mksaas-template.git main /absolute/path/to/my-saas
```

复制并准备环境文件：

```bash
mksaas env generate
mksaas env generate my-saas
mksaas env generate /absolute/path/to/my-saas http://localhost:3000 https://your-domain.com neon vercel
```

上传到 GitHub 私有仓库：

```bash
mksaas repo push
mksaas repo push my-saas
mksaas repo push /absolute/path/to/my-saas your-github-owner my-saas
```

在项目目录中直接继续引导流：

```bash
cd my-saas
mksaas cloudflare r2
mksaas cloudflare turnstile
mksaas email setup
mksaas email newsletter
mksaas payment setup
mksaas notification setup
mksaas credits setup
mksaas analytics setup
mksaas affiliates setup
mksaas db neon
mksaas db supabase
mksaas deploy vercel
mksaas deploy cloudflare-pg
mksaas auth github
mksaas auth google
```
