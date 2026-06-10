#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：交互式写入 Supabase 数据库连接串
# 参数：$1 [profile], $2 [project_dir]
# 返回：无
##
configure_supabase_database() {
  local profile="$1"
  local project_dir="$2"
  local env_file
  env_file="$(get_profile_env_file "$project_dir" "$profile")"

  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  local current_value=""
  current_value="$(read_profile_env_kv "$project_dir" "$profile" "DATABASE_URL")"
  if [[ -z "$current_value" && -f "$env_file" ]]; then
    current_value="$(read_env_kv "$env_file" "DATABASE_URL")"
  fi

  local database_url=""
  printf "\n配置 Supabase 数据库\n"
  open_url "Supabase 控制台" "https://supabase.com/dashboard/projects"
  open_url "MkSaaS 数据库文档" "https://mksaas.com/zh/docs/database"
  cat <<'EOF'
申请步骤：
1. 登录 Supabase 后创建一个 Project。
2. 等数据库初始化完成，进入 Connect。
3. 优先复制 Transaction pooler 连接串。
4. 把连接串填入 DATABASE_URL。
5. 如果后面迁移报连接问题，优先检查密码、网络和连接串端口。
EOF
  prompt_input "Supabase DATABASE_URL（建议 transaction pooler）" database_url "$current_value" "true"

  upsert_profile_env_kv "$project_dir" "$profile" "DATABASE_URL" "$database_url"
  upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_DB_PROVIDER" "supabase"
  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  printf "已保存敏感配置到：%s\n" "$(get_profile_secrets_env_file "$project_dir" "$profile")"
  printf "已生成环境文件：%s\n" "$(get_profile_env_file "$project_dir" "$profile")"
  printf "下一步可执行：pnpm run db:generate && pnpm run db:migrate\n"
}

main() {
  local project_dir=""
  local profile="test"

  if [[ $# -gt 2 ]]; then
    err "用法: $0 [profile] [project_dir]"
    exit 1
  fi

  IFS=$'\n' read -r profile project_dir < <(parse_profile_and_project_dir "${1:-}" "${2:-}")
  configure_supabase_database "$profile" "$project_dir"
}

main "$@"
