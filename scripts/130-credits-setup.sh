#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：配置 Credits（积分）所需的 Stripe 价格 ID 环境变量
# 参数：$1 [profile], $2 [project_dir]
# 返回：无
##
configure_credits() {
  local profile="$1"
  local project_dir="$2"

  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  printf "\n配置积分（Credits）\n"
  open_url "MkSaaS Credits 文档" "https://mksaas.com/docs/credits"
  open_url "MkSaaS 环境变量（积分）" "https://mksaas.com/zh/docs/env#%E7%A7%AF%E5%88%86"
  open_url "Stripe 产品（Product Catalog）" "https://dashboard.stripe.com/products"
  cat <<'EOF'
申请步骤：
1. 在 Stripe 里为每个积分包创建一个 Product + Price。
2. 把对应的 price_... 填入以下变量（可先留空，后续再补）：
   - NEXT_PUBLIC_STRIPE_PRICE_CREDITS_BASIC
   - NEXT_PUBLIC_STRIPE_PRICE_CREDITS_STANDARD
   - NEXT_PUBLIC_STRIPE_PRICE_CREDITS_PREMIUM
   - NEXT_PUBLIC_STRIPE_PRICE_CREDITS_ENTERPRISE
EOF

  local input=""
  prompt_input "NEXT_PUBLIC_STRIPE_PRICE_CREDITS_BASIC（price_... 可留空）" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_STRIPE_PRICE_CREDITS_BASIC")"
  upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_STRIPE_PRICE_CREDITS_BASIC" "$input"

  prompt_input "NEXT_PUBLIC_STRIPE_PRICE_CREDITS_STANDARD（price_... 可留空）" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_STRIPE_PRICE_CREDITS_STANDARD")"
  upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_STRIPE_PRICE_CREDITS_STANDARD" "$input"

  prompt_input "NEXT_PUBLIC_STRIPE_PRICE_CREDITS_PREMIUM（price_... 可留空）" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_STRIPE_PRICE_CREDITS_PREMIUM")"
  upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_STRIPE_PRICE_CREDITS_PREMIUM" "$input"

  prompt_input "NEXT_PUBLIC_STRIPE_PRICE_CREDITS_ENTERPRISE（price_... 可留空）" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_STRIPE_PRICE_CREDITS_ENTERPRISE")"
  upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_STRIPE_PRICE_CREDITS_ENTERPRISE" "$input"

  upsert_project_meta_kv "$project_dir" "CREDITS_ENABLED" "true"
  upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_CREDITS_ENABLED" "true"
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
  configure_credits "$profile" "$project_dir"
}

main "$@"
