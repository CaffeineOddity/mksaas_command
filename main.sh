#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

WORKDIR="$(pwd)"
SOURCE="${BASH_SOURCE[0]}"
while [[ -h "$SOURCE" ]]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ "$SOURCE" != /* ]] && SOURCE="${DIR}/${SOURCE}"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
source "${SCRIPT_DIR}/scripts/lib.sh"

TEMPLATE_REPO_DEFAULT="https://github.com/MkSaaSHQ/mksaas-template.git"
TEMPLATE_BRANCH_DEFAULT="main"
DEV_BASE_URL_DEFAULT="http://localhost:3000"

##
# 功能：打印帮助信息并退出
# 参数：无
# 返回：无（直接退出）
##
usage() {
  local cmd
  cmd="$(basename "${0:-mksaas}")"
  cat <<EOF
用法:
  $cmd
  $cmd init [project_name]
  $cmd project <create|clone> [...]
  $cmd env <setup|generate|migrate-secrets> [...]
  $cmd repo push [...]
  $cmd cloudflare <r2|turnstile> [...]
  $cmd db <neon|supabase|local-postgres> [...]
  $cmd deploy <vercel|cloudflare-pg|cloudflare-d1> [...]
  $cmd auth <github|google> [...]
  $cmd email <setup|resend|newsletter> [...]
  $cmd payment <setup|stripe|creem> [...]
  $cmd notification setup [...]
  $cmd credits setup [...]
  $cmd analytics setup [...]
  $cmd affiliates setup [...]

说明:
  init：交互式完整初始化流程：
  1) 克隆模板并将模板远程保留为 template
  2) 生成 .env.test/.env.prod 与 SETUP_NEXT_STEPS.md（并同步 .env=.env.test）
  3) 绑定 GitHub 私有仓库并 push（可跳过）
  project create：只创建项目骨架目录与 .mksaas/project.yaml

提示:
  运行 $cmd <group> -h 查看该分组的详细用法，例如：$cmd deploy -h

依赖:
  git, openssl, curl

可选:
  pnpm, vercel, wrangler
EOF
  exit 1
}

##
# 功能：打印某个命令分组的帮助信息并退出
# 参数：$1 group
# 返回：无（直接退出）
##
usage_group() {
  local group="$1"
  local cmd
  cmd="$(basename "${0:-mksaas}")"

  case "$group" in
    project)
      cat <<EOF
用法:
  $cmd project create [project_name]
  $cmd project clone <project_dir>
  $cmd project clone <template_branch> <project_dir>
  $cmd project clone <template_repo> <template_branch> <project_dir>

说明:
  - create：只创建项目骨架与 .mksaas/project.yaml
  - clone：克隆模板并将 origin 重命名为 template（不推送）
EOF
      ;;
    env)
      cat <<EOF
用法:
  $cmd env setup test|prod [project_dir]
  $cmd env generate [project_dir]
  $cmd env migrate-secrets [project_dir]

说明:
  - 非敏感：.mksaas/project.yaml
  - 敏感：.mksaas/secrets.test.env / .mksaas/secrets.prod.env
  - 产物：.env.test / .env.prod（并同步 .env=.env.test）
EOF
      ;;
    repo)
      cat <<EOF
用法:
  $cmd repo push [project_dir]
  $cmd repo push <project_dir> <repo_url>

说明:
  - 绑定你已创建好的 GitHub 私有仓库并推送当前项目代码
EOF
      ;;
    cloudflare)
      cat <<EOF
用法:
  $cmd cloudflare r2 [profile] [project_dir]
  $cmd cloudflare turnstile [profile] [project_dir]
EOF
      ;;
    db)
      cat <<EOF
用法:
  $cmd db neon [profile] [project_dir]
  $cmd db supabase [profile] [project_dir]
  $cmd db local-postgres [profile] [project_dir]

说明:
  - profile 默认 test
  - DATABASE_URL 属于敏感信息，会写入 secrets.<profile>.env
EOF
      ;;
    deploy)
      cat <<EOF
用法:
  $cmd deploy vercel [project_dir]
  $cmd deploy cloudflare-pg [project_dir]
  $cmd deploy cloudflare-d1 [project_dir]

说明:
  - deploy 主要用于设置生产域名（写入 prod），并提示在部署平台设置 NEXT_PUBLIC_BASE_URL
EOF
      ;;
    auth)
      cat <<EOF
用法:
  $cmd auth github [profile] [project_dir]
  $cmd auth google [profile] [project_dir]

说明:
  - Client Secret 属于敏感信息，会写入 secrets.<profile>.env
EOF
      ;;
    email)
      cat <<EOF
用法:
  $cmd email setup [profile] [project_dir]
  $cmd email resend [profile] [project_dir]
  $cmd email newsletter [profile] [project_dir]
EOF
      ;;
    payment)
      cat <<EOF
用法:
  $cmd payment setup [profile] [project_dir]
  $cmd payment stripe [profile] [project_dir]
  $cmd payment creem [profile] [project_dir]
EOF
      ;;
    notification)
      cat <<EOF
用法:
  $cmd notification setup [profile] [project_dir]
EOF
      ;;
    credits)
      cat <<EOF
用法:
  $cmd credits setup [profile] [project_dir]
EOF
      ;;
    analytics)
      cat <<EOF
用法:
  $cmd analytics setup [profile] [project_dir]
EOF
      ;;
    affiliates)
      cat <<EOF
用法:
  $cmd affiliates setup [profile] [project_dir]
EOF
      ;;
    newsletter)
      cat <<EOF
用法:
  $cmd email newsletter [profile] [project_dir]

说明:
  - newsletter 已归并到 email 分组
EOF
      ;;
    *)
      usage
      ;;
  esac

  exit 1
}

##
# 功能：命令模式分发到独立脚本
# 参数：$@
# 返回：对应脚本退出码
##
dispatch_command() {
  local group="$1"
  local action="${2:-}"

  case "$group" in
    init)
      shift
      main_interactive "$@"
      ;;
    project)
      if [[ -z "$action" || "$action" == "-h" || "$action" == "--help" || "$action" == "help" ]]; then
        usage_group "project"
      fi
      shift 2
      case "$action" in
        create) exec "${SCRIPT_DIR}/scripts/00-project-create.sh" "$@" ;;
        clone|clone-template) exec "${SCRIPT_DIR}/scripts/10-clone-template.sh" "$@" ;;
        *) err "未知 project 子命令：$action"; usage ;;
      esac
      ;;
    env)
      if [[ -z "$action" || "$action" == "-h" || "$action" == "--help" || "$action" == "help" ]]; then
        usage_group "env"
      fi
      shift 2
      case "$action" in
        setup) exec "${SCRIPT_DIR}/scripts/21-env-setup.sh" "$@" ;;
        generate) exec "${SCRIPT_DIR}/scripts/20-prepare-env.sh" "$@" ;;
        migrate-secrets) exec "${SCRIPT_DIR}/scripts/22-env-migrate-secrets.sh" "$@" ;;
        *) err "未知 env 子命令：$action"; usage ;;
      esac
      ;;
    repo)
      if [[ -z "$action" || "$action" == "-h" || "$action" == "--help" || "$action" == "help" ]]; then
        usage_group "repo"
      fi
      shift 2
      case "$action" in
        push) exec "${SCRIPT_DIR}/scripts/30-github-create-push.sh" "$@" ;;
        *) err "未知 repo 子命令：$action"; usage ;;
      esac
      ;;
    github)
      shift 2
      case "$action" in
        create-push|push) exec "${SCRIPT_DIR}/scripts/30-github-create-push.sh" "$@" ;;
        *) err "未知 github 子命令：$action"; usage ;;
      esac
      ;;
    cloudflare)
      if [[ -z "$action" || "$action" == "-h" || "$action" == "--help" || "$action" == "help" ]]; then
        usage_group "cloudflare"
      fi
      shift 2
      case "$action" in
        r2) exec "${SCRIPT_DIR}/scripts/50-cloudflare-r2.sh" "$@" ;;
        turnstile) exec "${SCRIPT_DIR}/scripts/60-cloudflare-turnstile.sh" "$@" ;;
        *) err "未知 cloudflare 子命令：$action"; usage ;;
      esac
      ;;
    db)
      if [[ -z "$action" || "$action" == "-h" || "$action" == "--help" || "$action" == "help" ]]; then
        usage_group "db"
      fi
      shift 2
      case "$action" in
        neon) exec "${SCRIPT_DIR}/scripts/70-database-neon.sh" "$@" ;;
        supabase) exec "${SCRIPT_DIR}/scripts/71-database-supabase.sh" "$@" ;;
        local-postgres) exec "${SCRIPT_DIR}/scripts/72-database-local-postgres.sh" "$@" ;;
        *) err "未知 db 子命令：$action"; usage ;;
      esac
      ;;
    deploy)
      if [[ -z "$action" || "$action" == "-h" || "$action" == "--help" || "$action" == "help" ]]; then
        usage_group "deploy"
      fi
      shift 2
      case "$action" in
        vercel) exec "${SCRIPT_DIR}/scripts/80-deploy-vercel.sh" "$@" ;;
        cloudflare-pg) exec "${SCRIPT_DIR}/scripts/81-deploy-cloudflare-pg.sh" "$@" ;;
        cloudflare-d1) exec "${SCRIPT_DIR}/scripts/82-deploy-cloudflare-d1.sh" "$@" ;;
        *) err "未知 deploy 子命令：$action"; usage ;;
      esac
      ;;
    auth)
      if [[ -z "$action" || "$action" == "-h" || "$action" == "--help" || "$action" == "help" ]]; then
        usage_group "auth"
      fi
      shift 2
      case "$action" in
        github) exec "${SCRIPT_DIR}/scripts/90-auth-github.sh" "$@" ;;
        google) exec "${SCRIPT_DIR}/scripts/91-auth-google.sh" "$@" ;;
        *) err "未知 auth 子命令：$action"; usage ;;
      esac
      ;;
    email)
      if [[ -z "$action" || "$action" == "-h" || "$action" == "--help" || "$action" == "help" ]]; then
        usage_group "email"
      fi
      shift 2
      case "$action" in
        setup) exec "${SCRIPT_DIR}/scripts/102-email-setup.sh" "$@" ;;
        resend) exec "${SCRIPT_DIR}/scripts/100-email-resend.sh" "$@" ;;
        newsletter) exec "${SCRIPT_DIR}/scripts/101-newsletter-setup.sh" "$@" ;;
        *) err "未知 email 子命令：$action"; usage ;;
      esac
      ;;
    newsletter)
      if [[ -z "$action" || "$action" == "-h" || "$action" == "--help" || "$action" == "help" ]]; then
        usage_group "newsletter"
      fi
      shift 2
      case "$action" in
        setup)
          printf "提示：命令已更名为：mksaas email newsletter（旧 newsletter 命令仍可用，但后续可能移除）\n" >&2
          exec "${SCRIPT_DIR}/scripts/101-newsletter-setup.sh" "$@"
          ;;
        *) err "未知 newsletter 子命令：$action"; usage ;;
      esac
      ;;
    payment)
      if [[ -z "$action" || "$action" == "-h" || "$action" == "--help" || "$action" == "help" ]]; then
        usage_group "payment"
      fi
      shift 2
      case "$action" in
        setup) exec "${SCRIPT_DIR}/scripts/112-payment-setup.sh" "$@" ;;
        stripe) exec "${SCRIPT_DIR}/scripts/110-payment-stripe.sh" "$@" ;;
        creem) exec "${SCRIPT_DIR}/scripts/111-payment-creem.sh" "$@" ;;
        *) err "未知 payment 子命令：$action"; usage ;;
      esac
      ;;
    notification)
      if [[ -z "$action" || "$action" == "-h" || "$action" == "--help" || "$action" == "help" ]]; then
        usage_group "notification"
      fi
      shift 2
      case "$action" in
        setup) exec "${SCRIPT_DIR}/scripts/120-notification-setup.sh" "$@" ;;
        *) err "未知 notification 子命令：$action"; usage ;;
      esac
      ;;
    credits)
      if [[ -z "$action" || "$action" == "-h" || "$action" == "--help" || "$action" == "help" ]]; then
        usage_group "credits"
      fi
      shift 2
      case "$action" in
        setup) exec "${SCRIPT_DIR}/scripts/130-credits-setup.sh" "$@" ;;
        *) err "未知 credits 子命令：$action"; usage ;;
      esac
      ;;
    analytics)
      if [[ -z "$action" || "$action" == "-h" || "$action" == "--help" || "$action" == "help" ]]; then
        usage_group "analytics"
      fi
      shift 2
      case "$action" in
        setup) exec "${SCRIPT_DIR}/scripts/140-analytics-setup.sh" "$@" ;;
        *) err "未知 analytics 子命令：$action"; usage ;;
      esac
      ;;
    affiliates)
      if [[ -z "$action" || "$action" == "-h" || "$action" == "--help" || "$action" == "help" ]]; then
        usage_group "affiliates"
      fi
      shift 2
      case "$action" in
        setup) exec "${SCRIPT_DIR}/scripts/150-affiliates-setup.sh" "$@" ;;
        *) err "未知 affiliates 子命令：$action"; usage ;;
      esac
      ;;
    *)
      err "未知命令：$group"
      usage
      ;;
  esac
}

##
# 功能：主流程入口（交互式）
# 参数：$@
# 返回：无
##
main_interactive() {
  if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
  fi

  require_cmd git
  require_cmd openssl
  require_cmd curl

  local project_name="${1:-}"
  local repo_url=""
  local repo_push_enable="false"
  local template_repo="$TEMPLATE_REPO_DEFAULT"
  local dev_base_url="$DEV_BASE_URL_DEFAULT"
  local prod_base_url=""
  local template_branch=""
  local deploy_target=""
  local db_provider=""
  local use_cloudflare_r2="false"
  local use_turnstile="false"
  local use_github_oauth="false"
  local use_google_oauth="false"
  local email_provider="none"
  local newsletter_enable="false"
  local payment_provider="none"
  local notification_enable="false"
  local credits_enable="false"
  local analytics_enable="false"
  local affiliates_enable="false"
  local active_profile="test"

  if [[ -z "$project_name" ]]; then
    prompt_input "项目目录名（本地文件夹名）" project_name ""
    if [[ -z "$project_name" ]]; then
      err "项目名不能为空"
      exit 1
    fi
  fi

  local repo_choice
  repo_choice="$(choose_option "是否现在绑定 GitHub 私有仓库并推送代码？" "1" \
    "是（创建空私仓并输入 URL，推荐）" \
    "是（我已有私仓 URL）" \
    "跳过")"
  case "$repo_choice" in
    "是（创建空私仓并输入 URL，推荐）")
      repo_push_enable="true"
      printf "\n请先创建 GitHub Private 空仓库（不要初始化 README/.gitignore/license）\n"
      open_url "GitHub 新建仓库" "https://github.com/new"
      cat <<'EOF'
创建要点：
1. Visibility 选择 Private
2. 不要勾选 Add a README file / Add .gitignore / Choose a license
3. 创建完成后，复制仓库地址（HTTPS 或 SSH 都可以）
EOF
      prompt_input "请输入你的私仓 repo_url（例如 https://github.com/<owner>/<repo>.git）" repo_url ""
      ;;
    "是（我已有私仓 URL）")
      repo_push_enable="true"
      prompt_input "请输入你的私仓 repo_url（例如 https://github.com/<owner>/<repo>.git）" repo_url ""
      ;;
    "跳过")
      repo_push_enable="false"
      ;;
  esac

  local deploy_choice
  deploy_choice="$(choose_option "部署到哪里？" "1" \
    "Vercel" \
    "Cloudflare Workers（PG）" \
    "Cloudflare Workers（D1）" \
    "暂不部署")"

  case "$deploy_choice" in
    "Vercel") deploy_target="vercel" ;;
    "Cloudflare Workers（PG）") deploy_target="cloudflare-pg" ;;
    "Cloudflare Workers（D1）") deploy_target="cloudflare-d1" ;;
    "暂不部署") deploy_target="none" ;;
    *) err "未知部署选择"; exit 1 ;;
  esac

  if [[ "$deploy_target" == "cloudflare-d1" ]]; then
    db_provider="d1"
  else
    local db_choice
    db_choice="$(choose_option "使用哪个数据库？" "1" \
      "Neon（Postgres）" \
      "Supabase（Postgres）" \
      "本地 Docker Postgres" \
      "暂不配置")"

    case "$db_choice" in
      "Neon（Postgres）") db_provider="neon" ;;
      "Supabase（Postgres）") db_provider="supabase" ;;
      "本地 Docker Postgres") db_provider="local-docker" ;;
      "暂不配置") db_provider="none" ;;
      *) err "未知数据库选择"; exit 1 ;;
    esac
  fi

  prompt_input "模板仓库 URL" template_repo "$template_repo"
  local template_branch_default="$TEMPLATE_BRANCH_DEFAULT"
  if [[ "$deploy_target" == "cloudflare-pg" ]]; then
    template_branch_default="cloudflare"
  elif [[ "$deploy_target" == "cloudflare-d1" ]]; then
    template_branch_default="cloudflare-d1"
  fi
  prompt_input "模板分支" template_branch "$template_branch_default"

  prompt_input "开发环境 Base URL" dev_base_url "$dev_base_url"
  local prod_base_url_default="https://${project_name}.vercel.app"
  if [[ "$deploy_target" != "vercel" ]]; then
    prod_base_url_default="https://YOUR-DOMAIN.com"
  fi
  prompt_input "生产环境 Base URL（可先填占位）" prod_base_url "$prod_base_url_default"

  local profile_choice
  profile_choice="$(choose_option "这次要把配置写入哪个环境？" "1" \
    "测试/开发（test，推荐）" \
    "正式/生产（prod）")"
  if [[ "$profile_choice" == "正式/生产（prod）" ]]; then
    active_profile="prod"
  else
    active_profile="test"
  fi

  local r2_choice
  r2_choice="$(choose_option "是否配置 Cloudflare R2 存储？" "2" \
    "是" \
    "否")"
  [[ "$r2_choice" == "是" ]] && use_cloudflare_r2="true"

  local turnstile_choice
  turnstile_choice="$(choose_option "是否配置 Cloudflare Turnstile 验证码？" "2" \
    "是" \
    "否")"
  [[ "$turnstile_choice" == "是" ]] && use_turnstile="true"

  local github_oauth_choice
  github_oauth_choice="$(choose_option "是否配置 GitHub OAuth？" "2" \
    "是" \
    "否")"
  [[ "$github_oauth_choice" == "是" ]] && use_github_oauth="true"

  local google_oauth_choice
  google_oauth_choice="$(choose_option "是否配置 Google OAuth？" "2" \
    "是" \
    "否")"
  [[ "$google_oauth_choice" == "是" ]] && use_google_oauth="true"

  local email_choice
  email_choice="$(choose_option "是否配置邮件服务？" "2" \
    "Resend" \
    "跳过")"
  [[ "$email_choice" == "Resend" ]] && email_provider="resend"

  local newsletter_choice
  newsletter_choice="$(choose_option "是否配置邮件订阅（Newsletter）？" "2" \
    "是" \
    "跳过")"
  [[ "$newsletter_choice" == "是" ]] && newsletter_enable="true"

  local payment_choice
  payment_choice="$(choose_option "是否配置支付/订阅？" "3" \
    "Stripe" \
    "Creem" \
    "跳过")"
  case "$payment_choice" in
    Stripe) payment_provider="stripe" ;;
    Creem) payment_provider="creem" ;;
    跳过) payment_provider="none" ;;
  esac

  local notification_choice
  notification_choice="$(choose_option "是否配置支付通知（Discord/飞书）？" "2" \
    "是" \
    "跳过")"
  [[ "$notification_choice" == "是" ]] && notification_enable="true"

  local credits_choice
  credits_choice="$(choose_option "是否配置积分（Credits）？" "2" \
    "是" \
    "跳过")"
  [[ "$credits_choice" == "是" ]] && credits_enable="true"

  local analytics_choice
  analytics_choice="$(choose_option "是否配置统计分析（Analytics）？" "2" \
    "是" \
    "跳过")"
  [[ "$analytics_choice" == "是" ]] && analytics_enable="true"

  local affiliates_choice
  affiliates_choice="$(choose_option "是否配置联盟营销（Affiliates）？" "2" \
    "是" \
    "跳过")"
  [[ "$affiliates_choice" == "是" ]] && affiliates_enable="true"

  local project_dir="${WORKDIR}/${project_name}"

  printf "\n将执行以下操作：\n"
  printf "1) 克隆：%s (%s) -> %s\n" "$template_repo" "$template_branch" "$project_dir"
  printf "2) 生成：%s/.env.test/.env.prod 与 SETUP_NEXT_STEPS.md\n" "$project_dir"
  if [[ "$repo_push_enable" == "true" ]]; then
    printf "3) 推送到私有仓库：%s\n\n" "${repo_url:-（运行时输入）}"
  else
    printf "3) 跳过推送仓库（可后续运行：mksaas repo push）\n\n"
  fi
  printf "部署目标：%s\n" "$deploy_choice"
  if [[ "$db_provider" == "d1" ]]; then
    printf "数据库：Cloudflare D1\n\n"
  else
    printf "数据库：%s\n\n" "$db_provider"
  fi

  local confirm=""
  prompt_input "确认继续？输入 yes 继续" confirm "yes"
  if [[ "$confirm" != "yes" ]]; then
    err "已取消"
    exit 1
  fi

  "${SCRIPT_DIR}/scripts/10-clone-template.sh" "$template_repo" "$template_branch" "$project_dir"
  save_project_meta "$project_dir" "$project_name" "$project_name" "" "$template_repo" "$template_branch" "$dev_base_url" "$prod_base_url" "$deploy_target" "$db_provider"
  "${SCRIPT_DIR}/scripts/20-prepare-env.sh" "$project_dir" "$dev_base_url" "$prod_base_url" "$db_provider" "$deploy_target"

  case "$db_provider" in
    neon)
      "${SCRIPT_DIR}/scripts/70-database-neon.sh" "$active_profile" "$project_dir"
      ;;
    supabase)
      "${SCRIPT_DIR}/scripts/71-database-supabase.sh" "$active_profile" "$project_dir"
      ;;
    local-docker)
      "${SCRIPT_DIR}/scripts/72-database-local-postgres.sh" "$active_profile" "$project_dir"
      ;;
  esac

  if [[ "$email_provider" == "resend" ]]; then
    "${SCRIPT_DIR}/scripts/100-email-resend.sh" "$active_profile" "$project_dir"
  fi

  if [[ "$newsletter_enable" == "true" ]]; then
    "${SCRIPT_DIR}/scripts/101-newsletter-setup.sh" "$active_profile" "$project_dir"
  fi

  case "$payment_provider" in
    stripe)
      "${SCRIPT_DIR}/scripts/110-payment-stripe.sh" "$active_profile" "$project_dir"
      ;;
    creem)
      "${SCRIPT_DIR}/scripts/111-payment-creem.sh" "$active_profile" "$project_dir"
      ;;
  esac

  if [[ "$notification_enable" == "true" ]]; then
    "${SCRIPT_DIR}/scripts/120-notification-setup.sh" "$active_profile" "$project_dir"
  fi

  if [[ "$credits_enable" == "true" ]]; then
    if [[ "$payment_provider" != "stripe" ]]; then
      printf "提示：Credits 默认使用 Stripe Price ID，如果你没有用 Stripe，可先跳过或仅填写占位。\n"
    fi
    "${SCRIPT_DIR}/scripts/130-credits-setup.sh" "$active_profile" "$project_dir"
  fi

  if [[ "$analytics_enable" == "true" ]]; then
    "${SCRIPT_DIR}/scripts/140-analytics-setup.sh" "$active_profile" "$project_dir"
  fi

  if [[ "$affiliates_enable" == "true" ]]; then
    "${SCRIPT_DIR}/scripts/150-affiliates-setup.sh" "$active_profile" "$project_dir"
  fi

  local final_repo_url=""
  if [[ "$repo_push_enable" == "true" ]]; then
    final_repo_url="$("${SCRIPT_DIR}/scripts/30-github-create-push.sh" "$project_dir" "${repo_url:-}")"
  else
    final_repo_url="$(read_project_meta_kv "$project_dir" "REPO_URL")"
  fi

  case "$deploy_target" in
    vercel)
      "${SCRIPT_DIR}/scripts/80-deploy-vercel.sh" "$project_dir"
      ;;
    cloudflare-pg)
      "${SCRIPT_DIR}/scripts/81-deploy-cloudflare-pg.sh" "$project_dir"
      ;;
    cloudflare-d1)
      "${SCRIPT_DIR}/scripts/82-deploy-cloudflare-d1.sh" "$project_dir"
      ;;
  esac

  if [[ "$use_cloudflare_r2" == "true" ]]; then
    "${SCRIPT_DIR}/scripts/50-cloudflare-r2.sh" "$active_profile" "$project_dir"
  fi

  if [[ "$use_turnstile" == "true" ]]; then
    "${SCRIPT_DIR}/scripts/60-cloudflare-turnstile.sh" "$active_profile" "$project_dir"
  fi

  if [[ "$use_github_oauth" == "true" ]]; then
    "${SCRIPT_DIR}/scripts/90-auth-github.sh" "$active_profile" "$project_dir"
  fi

  if [[ "$use_google_oauth" == "true" ]]; then
    "${SCRIPT_DIR}/scripts/91-auth-google.sh" "$active_profile" "$project_dir"
  fi
  "${SCRIPT_DIR}/scripts/40-print-hints.sh" "$project_dir" "$final_repo_url"
}

main() {
  if [[ $# -eq 0 ]]; then
    main_interactive
    return
  fi

  case "${1:-}" in
    -h|--help)
      usage
      ;;
    init|project|env|repo|github|cloudflare|db|deploy|auth|email|newsletter|payment|notification|credits|analytics|affiliates)
      dispatch_command "$@"
      ;;
    *)
      err "未知命令：${1:-}"
      usage
      ;;
  esac
}

main "$@"
