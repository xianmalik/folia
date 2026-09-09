#!/usr/bin/env python3
"""MCP server entrypoint for the folia resume repository.

Exposes the resume content (source/*.yml), contact details, and the
build / ATS flows over the Model Context Protocol so any Claude session —
in any project directory — can read the CV, rebuild the PDF, or score it
against a job description.

The implementation lives in the folia/ subpackage next to this file:
    folia/config.py     paths, limits, annotation presets
    folia/models.py     structured result types, report parsing
    folia/content.py    resume/JD read helpers
    folia/runner.py     subprocess plumbing
    folia/tools.py      tool registrations
    folia/prompts.py    prompt registrations
    folia/resources.py  resource registrations

All paths are anchored via __file__, so the server works regardless of the
working directory it is launched from.

NOTE: this mcp/ directory is intentionally NOT a Python package (no
__init__.py) and is excluded from packaging — a top-level package named
`mcp` would shadow the MCP SDK this server imports. Run server.py directly
as a script:
    /path/to/folia/.venv/bin/python3 /path/to/folia/mcp/server.py

Register for all projects (user scope):
    make mcp-register
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the folia/ subpackage importable when this file is imported (rather
# than run as a script, where sys.path[0] is already this directory).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from folia import mcp  # noqa: E402


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
