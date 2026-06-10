#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

##
# 功能：打印错误并退出
# 参数：$1 message
# 返回：无
##
err() {
  printf "错误: %s\n" "$1" >&2
}

##
# 功能：交互读取输入
# 参数：$1 prompt, $2 var_name, $3 default_value
# 返回：通过引用变量写回
##
prompt_input() {
  local prompt="$1"
  local var_name="$2"
  local default_value="$3"

  local input=""
  if [[ -n "$default_value" ]]; then
    read -r -p "$prompt (默认: $default_value): " input
    if [[ -z "$input" ]]; then
      input="$default_value"
    fi
  else
    read -r -p "$prompt: " input
  fi

  printf -v "$var_name" "%s" "$input"
}

##
# 功能：解析脚本真实目录（支持 symlink）
# 参数：无
# 返回：输出真实目录到 stdout
##
get_real_script_dir() {
  local source="${BASH_SOURCE[0]}"
  while [[ -h "$source" ]]; do
    local dir
    dir="$(cd -P "$(dirname "$source")" && pwd)"
    source="$(readlink "$source")"
    [[ "$source" != /* ]] && source="${dir}/${source}"
  done
  cd -P "$(dirname "$source")" && pwd
}

##
# 功能：确保 PATH 包含指定目录（仅提示，不强制修改）
# 参数：$1 bin_dir
# 返回：无
##
print_path_hint() {
  local bin_dir="$1"
  if [[ ":$PATH:" != *":${bin_dir}:"* ]]; then
    printf "\n检测到你的 PATH 不包含：%s\n" "$bin_dir"
    printf "你可以把下面这行加入 ~/.zshrc 后重新打开终端：\n"
    printf "  export PATH=\"%s:$PATH\"\n\n" "$bin_dir"
  fi
}

##
# 功能：安装命令（使用 symlink 指向 main.sh）
# 参数：$1 repo_dir, $2 bin_dir, $3 cmd_name
# 返回：无
##
do_install() {
  local repo_dir="$1"
  local bin_dir="$2"
  local cmd_name="$3"

  mkdir -p "$bin_dir"
  chmod +x "${repo_dir}/main.sh" "${repo_dir}/mksaas-bootstrap.sh" "${repo_dir}/scripts/"*.sh || true

  local target="${repo_dir}/main.sh"
  local link_path="${bin_dir}/${cmd_name}"
  ln -sf "$target" "$link_path"

  printf "\n已安装命令：%s\n" "$cmd_name"
  printf "位置：%s\n" "$link_path"
  printf "指向：%s\n\n" "$target"
}

main() {
  local repo_dir
  repo_dir="$(get_real_script_dir)"

  local cmd_name_default="mksaas"
  local cmd_name=""
  prompt_input "命令名" cmd_name "$cmd_name_default"
  if [[ -z "$cmd_name" ]]; then
    err "命令名不能为空"
    exit 1
  fi

  local bin_dir_default="${HOME}/.local/bin"
  local bin_dir=""
  prompt_input "安装到哪个 bin 目录（需要在 PATH 中）" bin_dir "$bin_dir_default"
  if [[ -z "$bin_dir" ]]; then
    err "bin 目录不能为空"
    exit 1
  fi

  local confirm=""
  prompt_input "确认安装？输入 yes 继续" confirm "yes"
  if [[ "$confirm" != "yes" ]]; then
    err "已取消"
    exit 1
  fi

  do_install "$repo_dir" "$bin_dir" "$cmd_name"
  print_path_hint "$bin_dir"

  printf "现在你可以在任意目录运行：\n"
  printf "  %s init my-saas\n" "$cmd_name"
  printf "  %s project create my-saas\n" "$cmd_name"
  printf "  %s project clone <template_repo> <template_branch> <project_dir>\n" "$cmd_name"
  printf "  %s env setup test|prod [project_dir]\n" "$cmd_name"
  printf "  %s env generate [project_dir]\n\n" "$cmd_name"
  printf "  %s env migrate-secrets [project_dir]\n\n" "$cmd_name"
  printf "  %s repo push <project_dir> <repo_url>\n\n" "$cmd_name"
  printf "  %s email setup [project_dir]\n" "$cmd_name"
  printf "  %s email resend [project_dir]\n" "$cmd_name"
  printf "  %s email resend [project_dir]\n" "$cmd_name"
  printf "  %s email newsletter [project_dir]\n" "$cmd_name"
  printf "  %s payment setup [project_dir]\n" "$cmd_name"
  printf "  %s payment stripe|creem [project_dir]\n" "$cmd_name"
  printf "  %s notification setup [project_dir]\n" "$cmd_name"
  printf "  %s credits setup [project_dir]\n" "$cmd_name"
  printf "  %s analytics setup [project_dir]\n" "$cmd_name"
  printf "  %s affiliates setup [project_dir]\n\n" "$cmd_name"
}

main "$@"
