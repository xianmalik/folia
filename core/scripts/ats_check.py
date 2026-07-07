#!/usr/bin/env python3
"""Thin wrapper so `python3 core/scripts/ats_check.py` works without installing.

The real CLI lives in ats/cli.py (also exposed as the `folia-ats` console
script when the package is installed).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ats.cli import entrypoint  # noqa: E402

if __name__ == "__main__":
    entrypoint()
