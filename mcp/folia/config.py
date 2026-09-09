"""Paths, limits, and tool-annotation presets for the folia MCP server."""
from __future__ import annotations

from pathlib import Path

from mcp.types import ToolAnnotations

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = REPO_ROOT / "source"
JD_DIR = REPO_ROOT / "jd"
DIST_DIR = REPO_ROOT / "dist"
RESUME_TEX = REPO_ROOT / "core" / "resume.tex"
SCRIPTS_DIR = REPO_ROOT / "core" / "scripts"
VENV_PY = REPO_ROOT / ".venv" / "bin" / "python3"

SERVER_INSTRUCTIONS = (
    "Central hub for Malik Zubayer's resume (the folia repo). Use these tools "
    "to read resume content when writing portfolio material, cover letters, or "
    "project references; to rebuild the PDF; and to run ATS checks or match the "
    "CV against a job description. Resume content lives in YAML — [[text]] "
    "marks bold in the rendered PDF."
)

# Hardening limits
SUBPROCESS_TIMEOUT = 600  # seconds; builds take ~30s, LLM JD matches ~60s
MAX_JD_CHARS = 200_000  # largest JD accepted by ats_match_jd
MAX_REPORT_CHARS = 20_000  # ATS report text returned to the client
MAX_NAME_CHARS = 100  # JD filename slugs
MAX_BUILD_TAIL = 4_000  # build log tail returned on failure

# Annotation presets. Hints only — clients may use them to skip confirmation
# prompts for reads; they carry no security guarantees.
READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
BUILD = ToolAnnotations(  # writes only regeneratable artifacts (dist/, TeX)
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
LLM = ToolAnnotations(  # may call the Groq API when a key is configured
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True
)
WRITE = ToolAnnotations(  # overwrites jd/<name>.txt if it already exists
    readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False
)
ADD = ToolAnnotations(  # append-only: inserts new entries, never overwrites
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
