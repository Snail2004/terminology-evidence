"""Thin script entry point for building the harness RC archive."""

from __future__ import annotations

import sys

from integration_harness.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["build-release", *sys.argv[1:]]))
