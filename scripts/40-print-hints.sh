#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：输出后续手动步骤提示（账号授权/支付/风控相关动作保持手动）
# 参数：
#   $1 project_dir
#   $2 repo_url
# 返回：无
##
print_manual_steps_hint() {
  local project_dir="$1"
  local repo_url="$2"

  if [[ -n "$repo_url" ]]; then
    printf "\n代码仓库：%s\n" "$repo_url"
  else
    printf "\n代码仓库：未绑定（可在项目目录运行：mksaas repo push）\n"
  fi
  printf "下一步请查看：%s/SETUP_NEXT_STEPS.md\n\n" "$project_dir"
  printf "项目配置文件：%s/.mksaas/project.yaml\n\n" "$project_dir"
  printf "环境文件：%s/.env.test（默认本地开发）与 %s/.env.prod（正式）\n" "$project_dir" "$project_dir"
  printf "提示：%s/.env 会自动同步为 .env.test\n\n" "$project_dir"
  printf "敏感信息文件（不要提交）：\n"
  printf -- "- %s/.mksaas/secrets.test.env\n" "$project_dir"
  printf -- "- %s/.mksaas/secrets.prod.env\n\n" "$project_dir"

  printf -- "- 环境变量：https://mksaas.com/zh/docs/env\n"
  printf -- "- 数据库：https://mksaas.com/zh/docs/database\n"
  printf -- "- OAuth：https://mksaas.com/zh/docs/auth\n"
  printf -- "- 部署（Vercel）：https://mksaas.com/zh/docs/deployment/vercel\n"
  printf -- "- 邮件：https://mksaas.com/docs/email\n"
  printf -- "- Newsletter：https://mksaas.com/docs/newsletter\n"
  printf -- "- 支付：https://mksaas.com/docs/payment\n"
  printf -- "- 通知：https://mksaas.com/docs/notification\n"
  printf -- "- 积分：https://mksaas.com/docs/credits\n"
  printf -- "- 统计分析：https://mksaas.com/docs/analytics\n"
  printf -- "- 联盟营销：https://mksaas.com/docs/affiliates\n\n"

  printf "在项目目录中可以继续运行引导命令（支持无参，默认当前目录）：\n"
  printf -- "- mksaas env setup test|prod\n"
  printf -- "- mksaas env generate\n"
  printf -- "- mksaas env migrate-secrets\n"
  printf -- "- mksaas cloudflare r2\n"
  printf -- "- mksaas cloudflare turnstile\n"
  printf -- "- mksaas email setup\n"
  printf -- "- mksaas email resend\n"
  printf -- "- mksaas email newsletter\n"
  printf -- "- mksaas payment setup\n"
  printf -- "- mksaas payment stripe|creem\n"
  printf -- "- mksaas notification setup\n"
  printf -- "- mksaas credits setup\n"
  printf -- "- mksaas analytics setup\n"
  printf -- "- mksaas affiliates setup\n\n"
}

main() {
  if [[ $# -ne 2 ]]; then
    err "用法: $0 <project_dir> <repo_url>"
    exit 1
  fi
  print_manual_steps_hint "$1" "$2"
}

main "$@"
