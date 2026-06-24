"""mksaas.gitops — git 操作薄函数。

把 clone/remote 等副作用隔离在此，便于测试 monkeypatch 替换为桩。
CLI 不内置任何凭据获取/存储/注入（REQUIREMENTS §9.3）。
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def is_git_repo(d: Path) -> bool:
    """判断 d 是否为 git 仓库。"""
    return (Path(d) / ".git").exists()


def remote_url(d: Path, name: str = "origin") -> str | None:
    """读取 d 的某 remote url，无则 None。"""
    try:
        out = subprocess.run(
            ["git", "-C", str(d), "remote", "get-url", name],
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def remotes(d: Path) -> dict:
    """返回 d 的 {remote_name: url}。"""
    out = subprocess.run(
        ["git", "-C", str(d), "remote", "-v"],
        capture_output=True, text=True, check=False,
    )
    result = {}
    for line in out.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            result.setdefault(parts[0], parts[1])
    return result


def clone(url: str, dst: Path, origin: str | None = None) -> bool:
    """克隆 url 到 dst；origin 指定远程名（默认 origin）。返回是否成功。

    鉴权失败由调用方处理；本函数不注入凭据。
    """
    cmd = ["git", "clone"]
    if origin:
        cmd += ["--origin", origin]
    cmd += [url, str(dst)]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return res.returncode == 0


def remote_add(d: Path, name: str, url: str) -> bool:
    """在 d 内添加 remote。"""
    res = subprocess.run(
        ["git", "-C", str(d), "remote", "add", name, url],
        capture_output=True, text=True, check=False,
    )
    return res.returncode == 0


def checkout_set_upstream(d: Path, branch: str, remote: str = "upstream") -> bool:
    """检出分支并设置上游跟踪。"""
    subprocess.run(["git", "-C", str(d), "checkout", branch],
                   capture_output=True, text=True, check=False)
    res = subprocess.run(
        ["git", "-C", str(d), "branch", "--set-upstream-to", f"{remote}/{branch}"],
        capture_output=True, text=True, check=False,
    )
    return res.returncode == 0


def push(d: Path, remote: str = "origin", branch: str = "HEAD") -> tuple:
    """推送，返回 (成功, stderr)。鉴权失败时 stderr 含提示。"""
    res = subprocess.run(
        ["git", "-C", str(d), "push", "-u", remote, branch],
        capture_output=True, text=True, check=False,
    )
    return res.returncode == 0, res.stderr
