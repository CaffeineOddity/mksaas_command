"""Sample help command."""

from __future__ import annotations

import argparse


def run_help(parser: argparse.ArgumentParser) -> int:
    """Print this CLI's help message."""
    parser.print_help()
    return 0
