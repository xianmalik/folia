"""Structured result types and report parsing."""
from __future__ import annotations

import re
from typing import TypedDict


class ResumeStatus(TypedDict):
    version: str
    repo: str
    pdf_path: str
    pdf_built: bool
    stale: bool
    stale_sources: list[str]


class AtsResult(TypedDict):
    passed: bool
    score: float | None
    threshold: float
    report: str


_SCORE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*/\s*100")


def overall_score(output: str) -> float | None:
    """Pull the overall 0-100 score out of a rendered ATS report."""
    for line in output.splitlines():
        if "Overall" in line:
            match = _SCORE_RE.search(line)
            if match:
                return float(match.group(1))
    matches = _SCORE_RE.findall(output)
    return float(matches[-1]) if matches else None


def clamp_threshold(threshold: float) -> float:
    """Constrain a passing threshold to the meaningful 0-100 range."""
    return min(max(threshold, 0.0), 100.0)
