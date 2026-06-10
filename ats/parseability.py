"""Formatting & parseability check — the failures every real ATS shares.

Commercial ATS parsers (Sovren/Textkernel, RChilli) all break on the same
structural issues: image-only content, font/encoding damage, multi-column
layouts that scramble reading order, content the parser can't attribute to
a section, and resumes far outside the expected length. This check measures
those signals on the actual compiled PDF, not the YAML source.
"""
from __future__ import annotations

from . import config as _cfg
from .health import CheckResult
from .loader import ExtractionStats

_P = _cfg.get()["health"]["parseability"]
_MIN_CHARS_PER_PAGE = _P["min_chars_per_page"]
_WORD_COUNT_MIN     = _P["word_count_min"]
_WORD_COUNT_MAX     = _P["word_count_max"]
_MAX_UNLABELED      = _P["max_unlabeled_lines"]
_MIN_MEDIAN_LINE    = _P["min_median_line_len"]

MAX_SCORE = 20.0


def check(stats: ExtractionStats) -> CheckResult:
    score = 0.0
    findings: list[str] = []

    # (a) Text extraction yield → 6 pts. Scanned/image-heavy pages yield
    # almost no text and are invisible to every ATS.
    if stats.chars_per_page >= _MIN_CHARS_PER_PAGE:
        score += 6.0
    else:
        findings.append(
            f"Low text yield: {stats.chars_per_page:.0f} chars/page "
            f"(min {_MIN_CHARS_PER_PAGE}) — content may be images or unparseable"
        )

    # (b) Font/encoding integrity → 4 pts.
    if stats.replacement_chars == 0:
        score += 4.0
    else:
        findings.append(
            f"{stats.replacement_chars} broken character(s) in extracted text — "
            "non-standard fonts can render as garbage in ATS parsers"
        )

    # (c) No embedded raster images → 3 pts. Icons, photos, and skill
    # graphics are skipped by parsers; anything inside them is lost.
    if stats.images == 0:
        score += 3.0
    else:
        findings.append(
            f"{stats.images} embedded image(s) — graphics are invisible to ATS parsers"
        )

    # (d) Structure: parser can attribute content to sections → 4 pts.
    if stats.unlabeled_lines <= _MAX_UNLABELED:
        score += 2.0
    else:
        findings.append(
            f"{stats.unlabeled_lines} line(s) precede the first recognised section "
            "header — parsers can't categorise unlabeled content"
        )
    if stats.median_line_len >= _MIN_MEDIAN_LINE:
        score += 2.0
    else:
        findings.append(
            f"Median extracted line is {stats.median_line_len:.0f} chars — very short "
            "lines suggest a multi-column layout scrambling reading order"
        )

    # (e) Word count window → 3 pts.
    if _WORD_COUNT_MIN <= stats.words <= _WORD_COUNT_MAX:
        score += 3.0
    elif _WORD_COUNT_MIN * 0.75 <= stats.words <= _WORD_COUNT_MAX * 1.25:
        score += 1.5
        hint = "short" if stats.words < _WORD_COUNT_MIN else "long"
        findings.append(
            f"Resume is {stats.words} words — slightly {hint} "
            f"(target {_WORD_COUNT_MIN}-{_WORD_COUNT_MAX})"
        )
    else:
        hint = "short" if stats.words < _WORD_COUNT_MIN else "long"
        findings.append(
            f"Resume is {stats.words} words — too {hint} "
            f"(target {_WORD_COUNT_MIN}-{_WORD_COUNT_MAX})"
        )

    if not findings:
        findings = [
            f"{stats.pages} page(s) · {stats.words} words · clean extraction, "
            "no images, all content under recognised headers"
        ]
    return CheckResult("parseability", "Parseability", round(score, 1), MAX_SCORE, findings)
