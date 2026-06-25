"""Sample uninstall command."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

APP_NAME = "mksaas"


def run_uninstall(args: Any) -> int:
    """Uninstall this CLI: pip-uninstall the package and clean up the local install directory and symlinks."""
    subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", APP_NAME, "--disable-pip-version-check"],
        check=False,
    )
    install_dir = Path.home() / f".{APP_NAME}-cli"
    for link_dir in (Path("/usr/local/bin"), Path.home() / ".local" / "bin"):
        link_path = link_dir / APP_NAME
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink(missing_ok=True)
    if install_dir.exists():
        shutil.rmtree(install_dir)
    print(f"Uninstalled: {APP_NAME}")
    return 0
