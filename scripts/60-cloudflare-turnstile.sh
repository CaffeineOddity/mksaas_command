#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：交互式写入 Cloudflare Turnstile 相关环境变量
# 参数：
#   $1 [profile], $2 [project_dir]
# 返回：无
##
configure_cloudflare_turnstile() {
  local profile="$1"
  local project_dir="$2"

  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  local site_key=""
  local secret_key=""

  printf "\n配置 Cloudflare Turnstile\n"
  open_url "Cloudflare Turnstile 控制台" "https://dash.cloudflare.com/?to=/:account/turnstile"
  open_url "MkSaaS 环境变量文档" "https://mksaas.com/zh/docs/env"
  cat <<'EOF'
申请步骤：
1. 在 Cloudflare 控制台进入 Turnstile。
2. 创建一个 Site，选择要绑定的域名；本地开发可额外加 localhost。
3. 创建完成后复制 Site Key 和 Secret Key。
4. 分别填入 NEXT_PUBLIC_TURNSTILE_SITE_KEY 和 TURNSTILE_SECRET_KEY。
EOF
  prompt_input "Turnstile Site Key" site_key ""
  prompt_input "Turnstile Secret Key" secret_key "" "true"

  upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_TURNSTILE_SITE_KEY" "$site_key"
  upsert_profile_env_kv "$project_dir" "$profile" "TURNSTILE_SECRET_KEY" "$secret_key"
  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  printf "已保存配置到：%s（敏感值会写入 secrets.*.env）\n" "${project_dir}/.mksaas"
  printf "已生成环境文件：%s\n" "$(get_profile_env_file "$project_dir" "$profile")"
}

main() {
  local project_dir=""
  local profile="test"

  if [[ $# -gt 2 ]]; then
    err "用法: $0 [profile] [project_dir]"
    exit 1
  fi

  IFS=$'\n' read -r profile project_dir < <(parse_profile_and_project_dir "${1:-}" "${2:-}")
  configure_cloudflare_turnstile "$profile" "$project_dir"
}

main "$@"
