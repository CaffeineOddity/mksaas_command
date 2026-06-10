#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：交互式生成本地 Postgres DATABASE_URL
# 参数：$1 [profile], $2 [project_dir]
# 返回：无
##
configure_local_postgres_database() {
  local profile="$1"
  local project_dir="$2"

  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  local db_user="postgres"
  local db_password="mypassword"
  local db_host="localhost"
  local db_port="5432"
  local db_name="postgres"

  printf "\n配置本地 Postgres 数据库\n"
  open_url "MkSaaS 数据库文档" "https://mksaas.com/zh/docs/database"
  open_url "Docker Hub Postgres" "https://hub.docker.com/_/postgres"
  cat <<'EOF'
申请步骤：
1. 如果本机没有 Postgres，最简单是先用 Docker 启动一个 postgres 容器。
2. 确认用户名、密码、端口和数据库名。
3. 按这些信息拼接 DATABASE_URL。
4. 填完后执行 pnpm run db:generate && pnpm run db:migrate。
EOF
  prompt_input "数据库用户" db_user "$db_user"
  prompt_input "数据库密码" db_password "$db_password" "true"
  prompt_input "数据库主机" db_host "$db_host"
  prompt_input "数据库端口" db_port "$db_port"
  prompt_input "数据库名" db_name "$db_name"

  local database_url="postgres://${db_user}:${db_password}@${db_host}:${db_port}/${db_name}"
  upsert_profile_env_kv "$project_dir" "$profile" "DATABASE_URL" "$database_url"
  upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_DB_PROVIDER" "local-docker"
  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  printf "已保存敏感配置到：%s\n" "$(get_profile_secrets_env_file "$project_dir" "$profile")"
  printf "已生成环境文件：%s\n" "$(get_profile_env_file "$project_dir" "$profile")"
  printf "Docker 启动示例：docker run --name drizzle-postgres -e POSTGRES_PASSWORD=%s -d -p %s:5432 postgres\n" "$db_password" "$db_port"
}

main() {
  local project_dir=""
  local profile="test"

  if [[ $# -gt 2 ]]; then
    err "用法: $0 [profile] [project_dir]"
    exit 1
  fi

  IFS=$'\n' read -r profile project_dir < <(parse_profile_and_project_dir "${1:-}" "${2:-}")
  configure_local_postgres_database "$profile" "$project_dir"
}

main "$@"
