#!/usr/bin/env python3
"""
ATS integrity checker — detect keyword stuffing and hidden-text tricks.

These patterns are actively detected and penalized (or result in rejection)
by modern ATS systems such as Workday Illuminate, Greenhouse, and Lever.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

#: Maximum keyword density per 100 words before triggering the stuffing flag.
#: Studies show ATS flags kick in around 6–8% density.
KEYWORD_DENSITY_LIMIT = 0.08   # 8 %

#: Minimum words in a text block before density analysis is meaningful.
MIN_WORDS_FOR_DENSITY = 50

#: Regex patterns that often indicate hidden-text or white-font tricks in
#: raw LaTeX source (if we have it). These are heuristics, not guarantees.
_HIDDEN_TEXT_LATEX_RE = re.compile(
    r"\\textcolor\s*\{[Ww]hite\}|"
    r"\\color\s*\{[Ww]hite\}|"
    r"\\fontsize\s*\{\s*[01]\s*\}",  # 0pt or 1pt font — invisible
    re.VERBOSE,
)

#: Repeated-keyword pattern: same word appearing ≥5× in ≤100 words.
_REPEAT_RE = re.compile(r"\b([a-zA-Z][a-zA-Z0-9\+\#\-\.]{2,})\b")


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class IntegrityIssue:
    code: str           # e.g. "KEYWORD_STUFFING"
    severity: str       # "error" | "warning"
    message: str
    detail: str = ""


@dataclass
class IntegrityResult:
    ok: bool
    issues: list[IntegrityIssue] = field(default_factory=list)
    keyword_density: float = 0.0   # fraction (0–1)
    top_repeated: list[tuple[str, int]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def _count_words(text: str) -> int:
    return len(text.split())


def _keyword_density(text: str, keywords: list[str]) -> float:
    """
    Fraction of total words that are extracted JD keywords.

    A high ratio suggests the resume may have been padded to match the JD
    rather than naturally describing real work.
    """
    total = _count_words(text)
    if total < MIN_WORDS_FOR_DENSITY:
        return 0.0
    lower = text.lower()
    kw_hits = sum(
        1
        for kw in keywords
        if re.search(rf"\b{re.escape(kw.lower())}\b", lower)
    )
    return kw_hits / total


def _top_repeated_words(text: str, top_n: int = 5, min_count: int = 4) -> list[tuple[str, int]]:
    """
    Find words that appear suspiciously often — a signal of keyword repetition.
    Returns (word, count) pairs sorted by count descending.
    """
    counts: dict[str, int] = {}
    for m in _REPEAT_RE.finditer(text):
        w = m.group(1).lower()
        counts[w] = counts.get(w, 0) + 1

    # Filter out stop words and very short words
    _STOP = {
        "the", "and", "for", "with", "that", "this", "are", "was", "were",
        "have", "has", "had", "not", "but", "from", "been", "will", "can",
        "use", "used", "our", "their", "also", "all", "its", "more", "they",
        "you", "your", "who", "how", "what", "when", "then", "than", "into",
        "over", "such", "each", "which", "while", "both", "through", "within",
        "across", "about", "other",
    }
    filtered = [
        (w, c) for w, c in counts.items()
        if c >= min_count and w not in _STOP and len(w) > 3
    ]
    return sorted(filtered, key=lambda x: -x[1])[:top_n]


def _check_hidden_text_latex(source_path: Optional[Path]) -> list[IntegrityIssue]:
    """Scan LaTeX source for known hidden-text patterns."""
    if source_path is None or not source_path.exists():
        return []
    try:
        src = source_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    issues = []
    for m in _HIDDEN_TEXT_LATEX_RE.finditer(src):
        issues.append(IntegrityIssue(
            code="HIDDEN_TEXT_LATEX",
            severity="error",
            message="Hidden or invisible text found in LaTeX source.",
            detail=f"Pattern: {m.group(0)!r} at position {m.start()}",
        ))
    return issues


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check(
    resume_text: str,
    jd_keywords: list[str],
    latex_source: Optional[Path] = None,
) -> IntegrityResult:
    """
    Run all integrity checks against ``resume_text``.

    Parameters
    ----------
    resume_text:
        The full plain-text content of the resume (all sections concatenated).
    jd_keywords:
        Keywords extracted from the job description (from jd_matcher).
    latex_source:
        Optional path to the ``.tex`` source file for hidden-text scanning.

    Returns
    -------
    IntegrityResult
        ``ok`` is True when no *error*-severity issues are found.
        Warnings are informational only.
    """
    issues: list[IntegrityIssue] = []

    # 1. Keyword density check
    density = _keyword_density(resume_text, jd_keywords)
    if density > KEYWORD_DENSITY_LIMIT:
        pct = density * 100
        issues.append(IntegrityIssue(
            code="KEYWORD_STUFFING",
            severity="error",
            message=f"Keyword density {pct:.1f}% exceeds limit ({KEYWORD_DENSITY_LIMIT * 100:.0f}%).",
            detail=(
                "A keyword density this high signals keyword stuffing to modern ATS AI. "
                "Reduce repetition and let skills appear naturally in context."
            ),
        ))

    # 2. Repeated-word check
    top_repeated = _top_repeated_words(resume_text)
    for word, count in top_repeated:
        if count >= 8:
            issues.append(IntegrityIssue(
                code="EXCESSIVE_REPETITION",
                severity="warning",
                message=f"Word '{word}' appears {count}× — may look unnatural.",
                detail="Consider varying phrasing across bullets.",
            ))

    # 3. Hidden text in LaTeX source
    issues.extend(_check_hidden_text_latex(latex_source))

    ok = not any(i.severity == "error" for i in issues)
    return IntegrityResult(
        ok=ok,
        issues=issues,
        keyword_density=density,
        top_repeated=top_repeated,
    )
