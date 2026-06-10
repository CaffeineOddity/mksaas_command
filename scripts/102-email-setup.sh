#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：邮件模块引导（选择 provider 后调用对应脚本）
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

  printf "\n邮件服务引导\n"
  open_url "MkSaaS Email 文档" "https://mksaas.com/docs/email"

  local provider_choice
  provider_choice="$(choose_option "选择邮件服务商：" "1" \
    "Resend" \
    "跳过")"

  case "$provider_choice" in
    Resend)
      exec "${SCRIPT_DIR}/100-email-resend.sh" "$profile" "$project_dir"
      ;;
    跳过)
      printf "已跳过邮件服务配置\n"
      ;;
    *)
      err "未知选择"
      exit 1
      ;;
  esac
}

main "$@"
