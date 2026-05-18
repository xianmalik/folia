#!/usr/bin/env python3
"""Central config loader — edit ats/config.yml to tune all thresholds."""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ats/config.py: PyYAML not installed — run: pip install PyYAML", file=sys.stderr)
    sys.exit(1)

_CONFIG_PATH = Path(__file__).parent / "config.yml"
_CACHED: dict | None = None


def get() -> dict:
    """Return the parsed config dict (loaded once, then cached)."""
    global _CACHED
    if _CACHED is None:
        _CACHED = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    return _CACHED


def _reset_cache() -> None:
    """Clear the cached config — for tests only."""
    global _CACHED
    _CACHED = None
