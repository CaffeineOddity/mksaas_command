#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：生成 .env.test / .env.prod（并同步 .env 指向测试环境），同时生成 SETUP_NEXT_STEPS.md
# 参数：
#   $1 project_dir
#   $2 dev_base_url（可选，仅用于首次写入/覆盖）
#   $3 prod_base_url（可选，仅用于首次写入/覆盖）
# 返回：无
##
prepare_env_and_guides() {
  local project_dir="$1"
  local dev_base_url="${2:-}"
  local prod_base_url="${3:-}"
  local db_provider="${4:-}"
  local deploy_target="${5:-}"

  if [[ -n "$dev_base_url" ]]; then
    upsert_project_meta_kv "$project_dir" "DEV_BASE_URL" "$dev_base_url"
    upsert_profile_env_kv "$project_dir" "test" "NEXT_PUBLIC_BASE_URL" "$dev_base_url"
  fi
  if [[ -n "$prod_base_url" ]]; then
    upsert_project_meta_kv "$project_dir" "PROD_BASE_URL" "$prod_base_url"
    upsert_profile_env_kv "$project_dir" "prod" "NEXT_PUBLIC_BASE_URL" "$prod_base_url"
  fi

  if [[ -n "$db_provider" ]]; then
    upsert_project_meta_kv "$project_dir" "DB_PROVIDER" "$db_provider"
    upsert_project_meta_kv "$project_dir" "TEST_DB_PROVIDER" "$db_provider"
    upsert_project_meta_kv "$project_dir" "PROD_DB_PROVIDER" "$db_provider"
  fi

  if [[ -n "$deploy_target" ]]; then
    upsert_project_meta_kv "$project_dir" "DEPLOY_TARGET" "$deploy_target"
    upsert_project_meta_kv "$project_dir" "TEST_DEPLOY_TARGET" "$deploy_target"
    upsert_project_meta_kv "$project_dir" "PROD_DEPLOY_TARGET" "$deploy_target"
  fi

  printf "\n环境准备步骤\n"
  open_url "MkSaaS 环境变量文档" "https://mksaas.com/zh/docs/env"
  cat <<EOF
执行说明：
1. 写入并记录测试/开发 与 正式/生产 两套 Base URL。
2. 自动生成两套 BETTER_AUTH_SECRET（如未配置）。
3. 生成：.env.test 与 .env.prod，并将 .env 同步为 .env.test（用于本地开发默认读取）。
EOF

  local final_dev_base_url
  local final_prod_base_url
  final_dev_base_url="$(read_project_meta_kv "$project_dir" "DEV_BASE_URL")"
  final_prod_base_url="$(read_project_meta_kv "$project_dir" "PROD_BASE_URL")"

  if [[ -n "$final_dev_base_url" ]]; then
    upsert_profile_env_kv "$project_dir" "test" "NEXT_PUBLIC_BASE_URL" "$final_dev_base_url"
  fi
  if [[ -n "$final_prod_base_url" ]]; then
    upsert_profile_env_kv "$project_dir" "prod" "NEXT_PUBLIC_BASE_URL" "$final_prod_base_url"
  fi

  local test_secret prod_secret
  test_secret="$(read_profile_env_kv "$project_dir" "test" "BETTER_AUTH_SECRET")"
  if [[ -z "$test_secret" ]]; then
    test_secret="$(generate_better_auth_secret)"
    upsert_profile_env_kv "$project_dir" "test" "BETTER_AUTH_SECRET" "$test_secret"
  fi
  prod_secret="$(read_profile_env_kv "$project_dir" "prod" "BETTER_AUTH_SECRET")"
  if [[ -z "$prod_secret" ]]; then
    prod_secret="$(generate_better_auth_secret)"
    upsert_profile_env_kv "$project_dir" "prod" "BETTER_AUTH_SECRET" "$prod_secret"
  fi

  local test_db_provider prod_db_provider
  test_db_provider="$(read_project_meta_kv "$project_dir" "TEST_DB_PROVIDER")"
  prod_db_provider="$(read_project_meta_kv "$project_dir" "PROD_DB_PROVIDER")"
  if [[ -z "$test_db_provider" ]]; then
    test_db_provider="$(read_project_meta_kv "$project_dir" "DB_PROVIDER")"
    [[ -n "$test_db_provider" ]] && upsert_project_meta_kv "$project_dir" "TEST_DB_PROVIDER" "$test_db_provider"
  fi
  if [[ -z "$prod_db_provider" ]]; then
    prod_db_provider="$(read_project_meta_kv "$project_dir" "DB_PROVIDER")"
    [[ -n "$prod_db_provider" ]] && upsert_project_meta_kv "$project_dir" "PROD_DB_PROVIDER" "$prod_db_provider"
  fi

  if [[ "${test_db_provider:-}" != "d1" ]]; then
    if [[ -z "$(read_profile_env_kv "$project_dir" "test" "DATABASE_URL")" ]]; then
      upsert_profile_env_kv "$project_dir" "test" "DATABASE_URL" ""
    fi
  fi
  if [[ "${prod_db_provider:-}" != "d1" ]]; then
    if [[ -z "$(read_profile_env_kv "$project_dir" "prod" "DATABASE_URL")" ]]; then
      upsert_profile_env_kv "$project_dir" "prod" "DATABASE_URL" ""
    fi
  fi

  local env_test env_prod
  env_test="$(generate_profile_env_file "$project_dir" "test")"
  env_prod="$(generate_profile_env_file "$project_dir" "prod")"
  cp "$env_test" "${project_dir}/.env"
  chmod 600 "${project_dir}/.env" || true

  local gitignore="${project_dir}/.gitignore"
  if [[ ! -f "$gitignore" ]]; then
    : > "$gitignore"
  fi
  if grep -qE '^\.mksaas/([[:space:]]*)$' "$gitignore"; then
    local tmp_gitignore="${gitignore}.tmp.$$"
    awk '$0 !~ /^\.mksaas\/[[:space:]]*$/' "$gitignore" > "$tmp_gitignore"
    mv "$tmp_gitignore" "$gitignore"
  fi
  if ! grep -qE '^\.env([[:space:]]*)$' "$gitignore"; then
    printf ".env\n" >> "$gitignore"
  fi
  if ! grep -qE '^\.env\.test([[:space:]]*)$' "$gitignore"; then
    printf ".env.test\n" >> "$gitignore"
  fi
  if ! grep -qE '^\.env\.prod([[:space:]]*)$' "$gitignore"; then
    printf ".env.prod\n" >> "$gitignore"
  fi
  if ! grep -qE '^\.mksaas/secrets\.\*\.env([[:space:]]*)$' "$gitignore"; then
    printf ".mksaas/secrets.*.env\n" >> "$gitignore"
  fi

  local setup_md="${project_dir}/SETUP_NEXT_STEPS.md"
  cat > "$setup_md" <<EOF
# MkSaaS 初始化后的下一步

## 1) 数据库

EOF

  local doc_db_provider
  doc_db_provider="${prod_db_provider:-${test_db_provider:-none}}"
  case "$doc_db_provider" in
    neon)
      cat >> "$setup_md" <<'EOF'

你选择的是 Neon（Postgres）。准备好连接串并写入 \`.env\` 的 \`DATABASE_URL\`。

- Neon：https://neon.tech/
- 文档：https://mksaas.com/zh/docs/database

EOF
      ;;
    supabase)
      cat >> "$setup_md" <<'EOF'

你选择的是 Supabase（Postgres）。准备好连接串并写入 \`.env\` 的 \`DATABASE_URL\`。

- Supabase：https://supabase.com/
- 文档：https://mksaas.com/zh/docs/database

EOF
      ;;
    local-docker)
      cat >> "$setup_md" <<'EOF'

你选择的是本地 Docker Postgres。可以用下面方式启动本地数据库，然后把连接串写入 \`.env\` 的 \`DATABASE_URL\`：

```bash
docker run --name drizzle-postgres -e POSTGRES_PASSWORD=mypassword -d -p 5432:5432 postgres
```

```bash
DATABASE_URL="postgres://postgres:mypassword@localhost:5432/postgres"
```

文档：https://mksaas.com/zh/docs/database

EOF
      ;;
    none)
      cat >> "$setup_md" <<'EOF'

你选择了暂不配置数据库。后续你需要把 \`.env\` 里的 \`DATABASE_URL\` 补齐后再进行迁移初始化。

文档：https://mksaas.com/zh/docs/database

EOF
      ;;
    d1)
      cat >> "$setup_md" <<'EOF'

你选择的是 Cloudflare D1（仅适用于 `cloudflare-d1` 分支）。请按 D1 部署文档创建 D1 数据库并绑定到 Worker：

- Cloudflare D1 部署：https://mksaas.com/zh/docs/deployment/cloudflare-d1

EOF
      ;;
    *)
      cat >> "$setup_md" <<EOF

未知 db_provider：$doc_db_provider

EOF
      ;;
  esac

  cat >> "$setup_md" <<'EOF'

初始化数据库（在项目目录中执行，D1 方案除外）：

```bash
pnpm install
pnpm run db:generate
pnpm run db:migrate
```

EOF

  local doc_deploy_target
  doc_deploy_target="$(read_project_meta_kv "$project_dir" "PROD_DEPLOY_TARGET")"
  [[ -z "$doc_deploy_target" ]] && doc_deploy_target="$(read_project_meta_kv "$project_dir" "DEPLOY_TARGET")"
  case "$doc_deploy_target" in
    vercel)
      cat >> "$setup_md" <<EOF
## 2) 部署到 Vercel

- 文档：https://mksaas.com/zh/docs/deployment/vercel
- 关键环境变量（生产环境）：
  - NEXT_PUBLIC_BASE_URL=\`${final_prod_base_url}\`（如果暂时没有域名/线上地址，先部署后再回填并重新部署）
EOF
      if [[ "$doc_db_provider" != "d1" ]]; then
        cat >> "$setup_md" <<'EOF'
  - DATABASE_URL（生产数据库）
EOF
      fi
      cat >> "$setup_md" <<'EOF'
  - BETTER_AUTH_SECRET
  - 其他你启用的功能对应的变量（邮件/存储/支付等）

你可以在 Vercel 控制台导入 GitHub 仓库后，在 Project Settings → Environment Variables 配置。

EOF
      ;;
    cloudflare-pg)
      cat >> "$setup_md" <<'EOF'
## 2) 部署到 Cloudflare Workers（PG）

- 文档：https://mksaas.com/zh/docs/deployment/cloudflare
- 重要：部署到 Cloudflare Workers 需要 `cloudflare` 分支（不是 `main`）。
- 需要准备 Postgres（Neon/Supabase/自建均可）并配置相关环境变量。

EOF
      ;;
    cloudflare-d1)
      cat >> "$setup_md" <<'EOF'
## 2) 部署到 Cloudflare Workers（D1）

- 文档：https://mksaas.com/zh/docs/deployment/cloudflare-d1
- 重要：必须使用 `cloudflare-d1` 分支，并按文档创建并绑定 D1 数据库。

EOF
      ;;
    none)
      cat >> "$setup_md" <<'EOF'
## 2) 部署

你选择了暂不部署。后续可参考：

- Vercel：https://mksaas.com/zh/docs/deployment/vercel
- Cloudflare Workers（PG）：https://mksaas.com/zh/docs/deployment/cloudflare
- Cloudflare Workers（D1）：https://mksaas.com/zh/docs/deployment/cloudflare-d1

EOF
      ;;
    *)
      cat >> "$setup_md" <<EOF
## 2) 部署

未知 deploy_target：$doc_deploy_target

EOF
      ;;
  esac

  cat >> "$setup_md" <<'EOF'

## 3) OAuth（GitHub / Google）

回调 URL 规则（生产环境）：

- GitHub: \`\${NEXT_PUBLIC_BASE_URL}/api/auth/callback/github\`
- Google: \`\${NEXT_PUBLIC_BASE_URL}/api/auth/callback/google\`

对应文档：https://mksaas.com/zh/docs/auth

建议分别创建开发/生产两套 OAuth 应用（回调 URL 不同）。

## 4) Cloudflare（存储 + Turnstile）

如果你打算用 Cloudflare R2 作为对象存储（S3 兼容），需要准备：

- R2 Bucket
- R2 Access Key / Secret（注意权限最小化）
- Endpoint / Public URL

环境变量参考：https://mksaas.com/zh/docs/env （存储、验证码 Turnstile）

（脚本只生成指引，不会自动在 Cloudflare 上创建资源。）

## 5) 邮件 / Newsletter

- Email（Resend）：https://mksaas.com/docs/email
- Newsletter（Resend / Beehiiv）：https://mksaas.com/docs/newsletter
- 环境变量参考：https://mksaas.com/zh/docs/env （邮件、邮件订阅）

## 6) 支付 / 订阅

- 支付入口：https://mksaas.com/docs/payment
- Stripe：https://mksaas.com/docs/payment/stripe
- Creem：https://mksaas.com/docs/payment/creem
- 环境变量参考：https://mksaas.com/zh/docs/env （支付）

## 7) 支付通知（Discord / 飞书）

- 文档：https://mksaas.com/docs/notification
- 环境变量参考：https://mksaas.com/zh/docs/env （通知）

## 8) 积分（Credits）

- 文档：https://mksaas.com/docs/credits
- 环境变量参考：https://mksaas.com/zh/docs/env （积分）

## 9) 统计分析（Analytics）

- 文档：https://mksaas.com/docs/analytics
- 环境变量参考：https://mksaas.com/zh/docs/env （统计分析）

## 10) 联盟营销（Affiliates）

- 文档：https://mksaas.com/docs/affiliates
- 环境变量参考：https://mksaas.com/zh/docs/env （联盟营销）
EOF
}

main() {
  local project_dir=""
  local dev_base_url="http://localhost:3000"
  local prod_base_url=""
  local db_provider=""
  local deploy_target=""

  case "$#" in
    0|1)
      project_dir="$(resolve_existing_project_dir "${1:-}")"
      require_project_meta "$project_dir"
      dev_base_url="$(read_project_meta_kv "$project_dir" "DEV_BASE_URL")"
      prod_base_url="$(read_project_meta_kv "$project_dir" "PROD_BASE_URL")"
      db_provider="$(read_project_meta_kv "$project_dir" "DB_PROVIDER")"
      deploy_target="$(read_project_meta_kv "$project_dir" "DEPLOY_TARGET")"
      ;;
    3|5)
      project_dir="$(resolve_existing_project_dir "$1")"
      dev_base_url="$2"
      prod_base_url="$3"
      db_provider="${4:-neon}"
      deploy_target="${5:-vercel}"
      ;;
    *)
      err "用法: $0 [project_dir] | $0 <project_dir> <dev_base_url> <prod_base_url> [db_provider] [deploy_target]"
      exit 1
      ;;
  esac

  prepare_env_and_guides "$project_dir" "$dev_base_url" "$prod_base_url" "${db_provider:-}" "${deploy_target:-}"
}

main "$@"
