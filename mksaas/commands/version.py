"""Sample version command."""

from __future__ import annotations

from typing import Any

from mksaas import __version__


def run_version(args: Any) -> int:
    """Print the current CLI version."""
    print("mksaas " + __version__)
    return 0
