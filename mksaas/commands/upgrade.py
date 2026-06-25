"""Sample upgrade command."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

APP_NAME = "mksaas"


def run_upgrade(args: Any) -> int:
    """Upgrade this CLI: pull a release from PyPI by default, or install from local build artifacts with --local."""
    try:
        if getattr(args, "local", None):
            version = _upgrade_from_local(Path(args.local).resolve(), args.version)
        else:
            version = _upgrade_from_pypi(args.version)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}")
        return 1
    print(f"Upgrade complete: {version}")
    return 0


def _upgrade_from_pypi(version: str | None) -> str:
    """Upgrade to the latest or a specific release version from PyPI."""
    spec = [APP_NAME, "--upgrade"] if version is None else [f"{APP_NAME}=={version}"]
    subprocess.run(
        [sys.executable, "-m", "pip", "install", *spec, "--disable-pip-version-check"],
        check=True,
    )
    return version or "latest"


def _upgrade_from_local(project_root: Path, version: str | None) -> str:
    """Upgrade from a local project's build artifacts; defaults to the latest version if version is omitted."""
    resolved = version or _latest_product_version(project_root)
    wheel = _find_local_wheel(project_root, resolved)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--force-reinstall", str(wheel), "--disable-pip-version-check"],
        check=True,
    )
    return resolved


def _find_local_wheel(project_root: Path, version: str) -> Path:
    """Locate the wheel file for a given local build-artifact version."""
    config_path = project_root / "build.config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    build_root = config.get("build_root", ".build")
    dist_dir = project_root / build_root / "dist" / version / "dist"
    wheels = sorted(dist_dir.glob("*.whl")) if dist_dir.is_dir() else []
    if not wheels:
        raise FileNotFoundError(
            f"Local wheel for {version} not found at {dist_dir}; run `build` first"
        )
    return wheels[0]


def _latest_product_version(project_root: Path) -> str:
    """Return the latest version found in the local build-artifacts directory."""
    config_path = project_root / "build.config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    build_root = config.get("build_root", ".build")
    dist = project_root / build_root / "dist"
    if not dist.is_dir():
        raise FileNotFoundError(f"Build artifacts directory not found: {dist}")
    candidates = []
    for sub in dist.iterdir():
        if sub.is_dir() and (sub / "dist").is_dir() and any((sub / "dist").glob("*.whl")):
            candidates.append(sub.name)
    if not candidates:
        raise FileNotFoundError(f"No upgradable artifacts found: {dist}")
    candidates.sort(key=_version_sort_key)
    return candidates[-1]


def _version_sort_key(version_str: str) -> tuple:
    """Produce a sort key for release/dev version strings (handles .devN and -devN)."""
    base = version_str
    dev = 0
    for sep in (".dev", "-dev"):
        if sep in base:
            base, dev_part = base.split(sep, 1)
            dev = int(dev_part)
            break
    segments = base.split(".")
    if len(segments) != 3 or not all(seg.isdigit() for seg in segments):
        return (0, 0, 0, 0, 0)
    major, minor, patch = (int(seg) for seg in segments)
    is_release = 0 if (".dev" in version_str or "-dev" in version_str) else 1
    return (major, minor, patch, is_release, dev)
