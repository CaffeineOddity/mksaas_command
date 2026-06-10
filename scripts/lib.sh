#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

PROJECT_META_DIR_NAME=".mksaas"
PROJECT_META_FILE_NAME="project.yaml"

##
# 功能：输出错误信息到 stderr
# 参数：$1 message
# 返回：无
##
err() {
  printf "错误: %s\n" "$1" >&2
}

##
# 功能：读取用户输入（可隐藏输入）
# 参数：$1 prompt, $2 var_name, $3 default_value, $4 hide(true/false)
# 返回：通过引用变量写回
##
prompt_input() {
  local prompt="$1"
  local var_name="$2"
  local default_value="${3:-}"
  local hide="${4:-false}"

  local input=""
  if [[ "$hide" == "true" ]]; then
    if [[ -n "$default_value" ]]; then
      read -r -s -p "$prompt (默认已存在): " input
      echo ""
      if [[ -z "$input" ]]; then
        input="$default_value"
      fi
    else
      read -r -s -p "$prompt: " input
      echo ""
    fi
  else
    if [[ -n "$default_value" ]]; then
      read -r -p "$prompt (默认: $default_value): " input
      if [[ -z "$input" ]]; then
        input="$default_value"
      fi
    else
      read -r -p "$prompt: " input
    fi
  fi

  printf -v "$var_name" "%s" "$input"
}

##
# 功能：检查命令是否存在
# 参数：$1 cmd
# 返回：存在返回 0，否则退出 1
##
require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    err "缺少依赖命令：$1"
    exit 1
  fi
}

##
# 功能：生成 Better Auth Secret
# 参数：无
# 返回：输出 secret 到 stdout
##
generate_better_auth_secret() {
  openssl rand -base64 32
}

##
# 功能：获取当前 gh 登录用户（login）
# 参数：无
# 返回：输出 login 到 stdout
##
get_gh_login() {
  gh api user --jq '.login'
}

##
# 功能：安全写入 env 键值（存在则替换，不存在则追加）
# 参数：$1 env_file, $2 key, $3 value（不应包含换行）
# 返回：无
##
upsert_env_kv() {
  local env_file="$1"
  local key="$2"
  local value="$3"

  if [[ "$value" == *$'\n'* ]]; then
    err "环境变量值不允许包含换行：$key"
    exit 1
  fi

  local escaped_value="${value//\\/\\\\}"
  escaped_value="${escaped_value//\"/\\\"}"

  if [[ -f "$env_file" ]] && grep -qE "^${key}=" "$env_file"; then
    local tmp_file="${env_file}.tmp.$$"
    awk -v k="$key" -v v="$escaped_value" '
      BEGIN { updated=0 }
      $0 ~ ("^" k "=") { print k "=\"" v "\""; updated=1; next }
      { print }
      END { if (updated==0) print k "=\"" v "\"" }
    ' "$env_file" > "$tmp_file"
    mv "$tmp_file" "$env_file"
  else
    printf "%s=\"%s\"\n" "$key" "$escaped_value" >> "$env_file"
  fi
}

##
# 功能：读取 env 文件中的键值（简单解析双引号/无引号场景）
# 参数：$1 env_file, $2 key
# 返回：输出 value 到 stdout；不存在则输出空字符串
##
read_env_kv() {
  local env_file="$1"
  local key="$2"

  if [[ ! -f "$env_file" ]]; then
    printf ""
    return 0
  fi

  local line
  line="$(grep -E "^${key}=" "$env_file" | tail -n 1 || true)"
  line="${line#${key}=}"
  line="${line%\"}"
  line="${line#\"}"
  printf "%s" "$line"
}

##
# 功能：返回项目元信息文件路径
# 参数：$1 project_dir
# 返回：输出元信息文件绝对路径
##
get_project_meta_file() {
  local project_dir="$1"
  printf "%s/%s/%s" "$project_dir" "$PROJECT_META_DIR_NAME" "$PROJECT_META_FILE_NAME"
}

##
# 功能：确保项目元信息目录存在
# 参数：$1 project_dir
# 返回：无
##
ensure_project_meta_dir() {
  local project_dir="$1"
  mkdir -p "${project_dir}/${PROJECT_META_DIR_NAME}"
}

##
# 功能：转义 YAML 双引号字符串
# 参数：$1 value
# 返回：输出转义后的字符串
##
yaml_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf "%s" "$value"
}

##
# 功能：读取项目元信息键值
# 参数：$1 project_dir, $2 key
# 返回：输出 value 到 stdout；不存在则输出空字符串
##
read_project_meta_kv() {
  local project_dir="$1"
  local key="$2"
  local meta_file
  meta_file="$(get_project_meta_file "$project_dir")"

  if [[ ! -f "$meta_file" ]]; then
    printf ""
    return 0
  fi

  awk -v key="$key" '
    $0 ~ ("^" key ":") {
      sub("^" key ":[[:space:]]*", "", $0)
      gsub(/^"/, "", $0)
      gsub(/"$/, "", $0)
      gsub(/\\"/, "\"", $0)
      gsub(/\\\\/, "\\", $0)
      print
      exit
    }
  ' "$meta_file"
}

##
# 功能：写入项目元信息键值
# 参数：$1 project_dir, $2 key, $3 value
# 返回：无
##
upsert_project_meta_kv() {
  local project_dir="$1"
  local key="$2"
  local value="$3"
  local meta_file
  meta_file="$(get_project_meta_file "$project_dir")"

  ensure_project_meta_dir "$project_dir"
  if [[ ! -f "$meta_file" ]]; then
    : > "$meta_file"
    chmod 600 "$meta_file" || true
  fi

  if [[ "$value" == *$'\n'* ]]; then
    err "项目配置值不允许包含换行：$key"
    exit 1
  fi

  local escaped_value
  escaped_value="$(yaml_escape "$value")"
  local tmp_file="${meta_file}.tmp.$$"

  awk -v k="$key" -v v="$escaped_value" '
    BEGIN { updated=0 }
    $0 ~ ("^" k ":") { print k ": \"" v "\""; updated=1; next }
    { print }
    END { if (updated==0) print k ": \"" v "\"" }
  ' "$meta_file" > "$tmp_file"
  mv "$tmp_file" "$meta_file"
}

##
# 功能：保存项目元信息
# 参数：
#   $1 project_dir
#   $2 project_name
#   $3 repo_name
#   $4 github_owner
#   $5 template_repo
#   $6 template_branch
#   $7 dev_base_url
#   $8 prod_base_url
#   $9 deploy_target
#   $10 db_provider
# 返回：无
##
save_project_meta() {
  local project_dir="$1"
  local project_name="$2"
  local repo_name="$3"
  local github_owner="$4"
  local template_repo="$5"
  local template_branch="$6"
  local dev_base_url="$7"
  local prod_base_url="$8"
  local deploy_target="$9"
  local db_provider="${10}"

  upsert_project_meta_kv "$project_dir" "PROJECT_NAME" "$project_name"
  upsert_project_meta_kv "$project_dir" "PROJECT_DIR" "$project_dir"
  upsert_project_meta_kv "$project_dir" "REPO_NAME" "$repo_name"
  upsert_project_meta_kv "$project_dir" "GITHUB_OWNER" "$github_owner"
  upsert_project_meta_kv "$project_dir" "TEMPLATE_REPO" "$template_repo"
  upsert_project_meta_kv "$project_dir" "TEMPLATE_BRANCH" "$template_branch"
  upsert_project_meta_kv "$project_dir" "DEV_BASE_URL" "$dev_base_url"
  upsert_project_meta_kv "$project_dir" "PROD_BASE_URL" "$prod_base_url"
  upsert_project_meta_kv "$project_dir" "DEPLOY_TARGET" "$deploy_target"
  upsert_project_meta_kv "$project_dir" "DB_PROVIDER" "$db_provider"
}

##
# 功能：解析已有项目目录；未传参时默认当前目录
# 参数：$1 project_dir（可选）
# 返回：输出解析后的项目目录绝对路径
##
resolve_existing_project_dir() {
  local input_dir="${1:-}"
  local project_dir=""

  if [[ -z "$input_dir" ]]; then
    project_dir="$(pwd)"
  elif [[ "$input_dir" = /* ]]; then
    project_dir="$input_dir"
  else
    project_dir="$(pwd)/$input_dir"
  fi

  if [[ ! -d "$project_dir" ]]; then
    err "项目目录不存在：$project_dir"
    exit 1
  fi

  printf "%s" "$(cd "$project_dir" && pwd)"
}

##
# 功能：确保项目目录下存在元信息文件
# 参数：$1 project_dir
# 返回：无
##
require_project_meta() {
  local project_dir="$1"
  local meta_file
  meta_file="$(get_project_meta_file "$project_dir")"

  if [[ ! -f "$meta_file" ]]; then
    err "未找到项目配置文件：$meta_file"
    err "请先使用 mksaas project create，或在项目目录下补充该文件"
    exit 1
  fi
}

##
# 功能：判断是否为合法环境 Profile（prod/test）
# 参数：$1 profile
# 返回：合法返回 0，否则返回 1
##
is_valid_profile() {
  local profile="${1:-}"
  [[ "$profile" == "prod" || "$profile" == "test" ]]
}

##
# 功能：规范化环境 Profile（默认 test）
# 参数：$1 profile（可选）
# 返回：输出规范化后的 profile（prod/test）
##
normalize_profile() {
  local profile="${1:-}"
  if is_valid_profile "$profile"; then
    printf "%s" "$profile"
    return 0
  fi
  printf "test"
}

##
# 功能：获取 Profile 前缀（prod->PROD，test->TEST）
# 参数：$1 profile（prod/test）
# 返回：输出前缀
##
profile_prefix() {
  local profile
  profile="$(normalize_profile "${1:-}")"
  if [[ "$profile" == "prod" ]]; then
    printf "PROD"
  else
    printf "TEST"
  fi
}

##
# 功能：获取指定 Profile 的 env 文件路径
# 参数：$1 project_dir, $2 profile（prod/test）
# 返回：输出 env 文件路径（例如 .env.prod / .env.test）
##
get_profile_env_file() {
  local project_dir="$1"
  local profile
  profile="$(normalize_profile "${2:-}")"
  printf "%s/.env.%s" "$project_dir" "$profile"
}

##
# 功能：获取指定 Profile 的 secrets env 文件路径
# 参数：$1 project_dir, $2 profile（prod/test）
# 返回：输出 secrets 文件路径（例如 .mksaas/secrets.prod.env）
##
get_profile_secrets_env_file() {
  local project_dir="$1"
  local profile
  profile="$(normalize_profile "${2:-}")"
  printf "%s/%s/secrets.%s.env" "$project_dir" "$PROJECT_META_DIR_NAME" "$profile"
}

##
# 功能：确保 secrets env 文件存在（并设置权限）
# 参数：$1 project_dir, $2 profile（prod/test）
# 返回：无
##
ensure_profile_secrets_env_file() {
  local project_dir="$1"
  local profile
  profile="$(normalize_profile "${2:-}")"
  local secrets_file
  secrets_file="$(get_profile_secrets_env_file "$project_dir" "$profile")"

  ensure_project_meta_dir "$project_dir"
  if [[ ! -f "$secrets_file" ]]; then
    : > "$secrets_file"
    chmod 600 "$secrets_file" || true
  fi
}

##
# 功能：判断 env key 是否属于敏感信息（应写入 secrets.*.env）
# 参数：$1 key
# 返回：敏感返回 0，否则返回 1
##
is_sensitive_env_key() {
  local key="${1:-}"

  if [[ "$key" == "DATABASE_URL" ]]; then
    return 0
  fi

  case "$key" in
    *_SECRET*|*_SECRET|*SECRET_*|*SECRET)
      return 0
      ;;
    *_API_KEY*|*_API_KEY|*API_KEY_*|*API_KEY)
      return 0
      ;;
    *ACCESS_KEY_ID*|*SECRET_ACCESS_KEY*|*PASSWORD*|*TOKEN*|*CLIENT_SECRET*)
      return 0
      ;;
  esac

  return 1
}

##
# 功能：写入指定 Profile 的敏感环境变量到 secrets.<profile>.env
# 参数：$1 project_dir, $2 profile（prod/test）, $3 key, $4 value
# 返回：无
##
upsert_profile_secret_env_kv() {
  local project_dir="$1"
  local profile
  profile="$(normalize_profile "${2:-}")"
  local key="$3"
  local value="$4"

  ensure_profile_secrets_env_file "$project_dir" "$profile"
  local secrets_file
  secrets_file="$(get_profile_secrets_env_file "$project_dir" "$profile")"
  upsert_env_kv "$secrets_file" "$key" "$value"
}

##
# 功能：读取指定 Profile 的敏感环境变量（从 secrets.<profile>.env）
# 参数：$1 project_dir, $2 profile（prod/test）, $3 key
# 返回：输出 value（不存在则空字符串）
##
read_profile_secret_env_kv() {
  local project_dir="$1"
  local profile
  profile="$(normalize_profile "${2:-}")"
  local key="$3"
  local secrets_file
  secrets_file="$(get_profile_secrets_env_file "$project_dir" "$profile")"
  read_env_kv "$secrets_file" "$key"
}

##
# 功能：列出 env 文件中的所有键值对
# 参数：$1 env_file
# 返回：逐行输出：KEY<US>VALUE（US = 0x1f）
##
list_env_file_pairs() {
  local env_file="$1"
  if [[ ! -f "$env_file" ]]; then
    return 0
  fi

  awk -v us="$(printf '\037')" '
    BEGIN {}
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*$/ { next }
    $0 ~ /^[A-Za-z_][A-Za-z0-9_]*=/ {
      key=$0
      sub("=.*", "", key)
      val=$0
      sub("^[A-Za-z_][A-Za-z0-9_]*=", "", val)
      gsub(/\r$/, "", val)
      gsub(/^"/, "", val)
      gsub(/"$/, "", val)
      gsub(/\\"/, "\"", val)
      gsub(/\\\\/, "\\", val)
      print key us val
    }
  ' "$env_file"
}

##
# 功能：解析 profile 与项目目录（支持 [profile] [project_dir] 或仅 [project_dir]）
# 参数：$1 arg1（可选）, $2 arg2（可选）
# 返回：输出两行：第 1 行 profile，第 2 行 project_dir
##
parse_profile_and_project_dir() {
  local arg1="${1:-}"
  local arg2="${2:-}"
  local profile="test"
  local project_dir=""

  if is_valid_profile "$arg1"; then
    profile="$arg1"
    project_dir="$(resolve_existing_project_dir "${arg2:-}")"
  else
    project_dir="$(resolve_existing_project_dir "${arg1:-}")"
  fi

  printf "%s\n%s" "$profile" "$project_dir"
}

##
# 功能：写入指定 Profile 的环境变量到 project.yaml（以 <PREFIX>_ENV_<KEY> 存储）
# 参数：$1 project_dir, $2 profile（prod/test）, $3 key, $4 value
# 返回：无
##
upsert_profile_env_kv() {
  local project_dir="$1"
  local profile
  profile="$(normalize_profile "${2:-}")"
  local key="$3"
  local value="$4"
  local prefix
  prefix="$(profile_prefix "$profile")"

  if is_sensitive_env_key "$key"; then
    upsert_profile_secret_env_kv "$project_dir" "$profile" "$key" "$value"
  else
    upsert_project_meta_kv "$project_dir" "${prefix}_ENV_${key}" "$value"
  fi

  if [[ "$profile" == "test" && "$key" == "NEXT_PUBLIC_BASE_URL" ]]; then
    upsert_project_meta_kv "$project_dir" "DEV_BASE_URL" "$value"
  elif [[ "$profile" == "prod" && "$key" == "NEXT_PUBLIC_BASE_URL" ]]; then
    upsert_project_meta_kv "$project_dir" "PROD_BASE_URL" "$value"
  fi
}

##
# 功能：读取指定 Profile 的环境变量（从 <PREFIX>_ENV_<KEY>）
# 参数：$1 project_dir, $2 profile（prod/test）, $3 key
# 返回：输出 value（不存在则空字符串）
##
read_profile_env_kv() {
  local project_dir="$1"
  local profile
  profile="$(normalize_profile "${2:-}")"
  local key="$3"
  local prefix
  prefix="$(profile_prefix "$profile")"

  if is_sensitive_env_key "$key"; then
    read_profile_secret_env_kv "$project_dir" "$profile" "$key"
    return 0
  fi

  read_project_meta_kv "$project_dir" "${prefix}_ENV_${key}"
}

##
# 功能：列出指定 Profile 的所有环境变量键值对
# 参数：$1 project_dir, $2 profile（prod/test）
# 返回：逐行输出：KEY<US>VALUE（US = 0x1f）
##
list_profile_env_pairs() {
  local project_dir="$1"
  local profile
  profile="$(normalize_profile "${2:-}")"
  local prefix
  prefix="$(profile_prefix "$profile")"
  local meta_file
  meta_file="$(get_project_meta_file "$project_dir")"

  if [[ ! -f "$meta_file" ]]; then
    :
  fi

  if [[ -f "$meta_file" ]]; then
    awk -v prefix="${prefix}_ENV_" -v us="$(printf '\037')" '
      $0 ~ ("^" prefix) {
        key=$0
        sub(":.*", "", key)
        val=$0
        sub("^" key ":[[:space:]]*", "", val)
        gsub(/^"/, "", val)
        gsub(/"$/, "", val)
        gsub(/\\"/, "\"", val)
        gsub(/\\\\/, "\\", val)
        out_key=substr(key, length(prefix)+1)
        print out_key us val
      }
    ' "$meta_file"
  fi

  local secrets_file
  secrets_file="$(get_profile_secrets_env_file "$project_dir" "$profile")"
  list_env_file_pairs "$secrets_file"
}

##
# 功能：根据 project.yaml 生成指定 Profile 的 env 文件（同时会复制 env.example/.env.example 作为基础）
# 参数：$1 project_dir, $2 profile（prod/test）
# 返回：输出生成后的 env 文件路径
##
generate_profile_env_file() {
  local project_dir="$1"
  local profile
  profile="$(normalize_profile "${2:-}")"
  local env_file
  env_file="$(get_profile_env_file "$project_dir" "$profile")"

  if [[ -f "${project_dir}/env.example" ]]; then
    cp "${project_dir}/env.example" "$env_file"
  elif [[ -f "${project_dir}/.env.example" ]]; then
    cp "${project_dir}/.env.example" "$env_file"
  else
    : > "$env_file"
  fi

  local k v
  while IFS=$'\037' read -r k v; do
    [[ -z "$k" ]] && continue
    upsert_env_kv "$env_file" "$k" "$v"
  done < <(list_profile_env_pairs "$project_dir" "$profile")

  chmod 600 "$env_file" || true
  printf "%s" "$env_file"
}

choose_option() {
  local prompt="$1"
  local default_index="$2"
  shift 2

  local options=("$@")
  if [[ ${#options[@]} -eq 0 ]]; then
    err "choose_option 缺少选项"
    exit 1
  fi

  printf "%s\n" "$prompt" >&2
  local i=1
  for opt in "${options[@]}"; do
    printf "  %d) %s\n" "$i" "$opt" >&2
    i=$((i + 1))
  done

  local answer=""
  local max="${#options[@]}"
  while true; do
    if [[ -n "$default_index" ]]; then
      read -r -p "请选择编号（回车默认 ${default_index}）: " answer
      if [[ -z "$answer" ]]; then
        answer="$default_index"
      fi
    else
      read -r -p "请选择编号: " answer
    fi

    if [[ "$answer" =~ ^[0-9]+$ ]] && (( answer >= 1 && answer <= max )); then
      printf "%s" "${options[$((answer - 1))]}"
      return 0
    fi

    err "无效选择，请输入 1-${max}"
  done
}

##
# 功能：在 macOS 中打开链接，并在终端打印说明
# 参数：$1 label, $2 url
# 返回：无
##
open_url() {
  local label="$1"
  local url="$2"

  printf -- "- 打开%s：%s\n" "$label" "$url"
  if command -v open >/dev/null 2>&1; then
    open "$url" >/dev/null 2>&1 || true
  fi
}
