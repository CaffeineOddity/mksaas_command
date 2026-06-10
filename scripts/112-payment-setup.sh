#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：支付模块引导（选择 provider 后调用对应脚本）
# 参数：$1 [profile], $2 [project_dir]
# 返回：无
##
main() {
  local project_dir=""
  local profile="test"

  if [[ $# -gt 2 ]]; then
    err "用法: $0 [profile] [project_dir]"
    exit 1
  fi

  IFS=$'\n' read -r profile project_dir < <(parse_profile_and_project_dir "${1:-}" "${2:-}")

  printf "\n支付/订阅引导\n"
  open_url "MkSaaS Payment 文档" "https://mksaas.com/docs/payment"

  local provider_choice
  provider_choice="$(choose_option "选择支付服务商：" "3" \
    "Stripe" \
    "Creem" \
    "跳过")"

  case "$provider_choice" in
    Stripe)
      exec "${SCRIPT_DIR}/110-payment-stripe.sh" "$profile" "$project_dir"
      ;;
    Creem)
      exec "${SCRIPT_DIR}/111-payment-creem.sh" "$profile" "$project_dir"
      ;;
    跳过)
      printf "已跳过支付配置\n"
      ;;
    *)
      err "未知选择"
      exit 1
      ;;
  esac
}

main "$@"
