#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

# ANSI codes — matches build.py palette
CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
WHITE = "\033[1;37m"
GRAY = "\033[0;37m"
BOLD = "\033[1m"
NC = "\033[0m"

_USE_COLOR = True


def _c(code: str) -> str:
    return code if _USE_COLOR else ""


def _is_tty() -> bool:
    return hasattr(sys.stdout, "fileno") and os.isatty(sys.stdout.fileno())


def _bar(score: float, max_score: float, width: int = 28) -> str:
    frac = min(score / max_score, 1.0) if max_score > 0 else 0.0
    filled = round(frac * width)
    return "█" * filled + "░" * (width - filled)


def _score_color(ratio: float) -> str:
    if ratio >= 0.80:
        return GREEN
    if ratio >= 0.76:
        return YELLOW
    return RED


def _status_icon(ratio: float) -> str:
    if ratio >= 0.90:
        return f"{_c(GREEN)}✓{_c(NC)}"
    if ratio >= 0.76:
        return f"{_c(YELLOW)}⚠{_c(NC)}"
    return f"{_c(RED)}✗{_c(NC)}"


def _finding_icon(text: str, ratio: float) -> str:
    if ratio >= 0.90:
        return f"  {_c(GREEN)}✓{_c(NC)}  {text}"
    if ratio >= 0.76:
        return f"  {_c(YELLOW)}⚠{_c(NC)}  {text}"
    return f"  {_c(RED)}✗{_c(NC)}  {text}"


def render(result, no_color: bool = False) -> None:
    global _USE_COLOR
    _USE_COLOR = not no_color and _is_tty()
    if result.mode == "health":
        _render_health(result)
    else:
        _render_jd(result)


def _render_health(result) -> None:
    print()
    print(f"{_c(CYAN)}╭{'─' * 76}╮{_c(NC)}")
    print(f"{_c(CYAN)}│{_c(WHITE)}  folia · ATS Health Check{_c(GRAY)}                                               {_c(CYAN)}│{_c(NC)}")
    print(f"{_c(CYAN)}╰{'─' * 76}╯{_c(NC)}")
    print()

    label_w = 22
    for chk in result.checks:
        label = chk.label.ljust(label_w)
        bar = _bar(chk.score, chk.max_score)
        col = _score_color(chk.ratio)
        icon = _status_icon(chk.ratio)
        pts = f"{chk.score:.0f}/{chk.max_score:.0f}"
        print(f"  {_c(WHITE)}{label}{_c(NC)}  {_c(col)}{bar}{_c(NC)}  {pts.rjust(6)}  {icon}")

    print()
    print(f"  {_c(GRAY)}{'─' * 74}{_c(NC)}")

    overall_ratio = result.total_score / 100.0
    col = _score_color(overall_ratio)
    overall_bar = _bar(result.total_score, 100.0)
    verdict = (
        f"{_c(GREEN)}{_c(BOLD)} ✓ PASS{_c(NC)}"
        if result.passed
        else f"{_c(RED)}{_c(BOLD)} ✗ FAIL{_c(NC)}"
    )
    print(f"  {'Overall CV Score'.ljust(label_w)}  {_c(col)}{overall_bar}{_c(NC)}  {str(result.total_score).rjust(3)}/100{verdict}")
    print()

    # Findings
    has_issues = any(not f.startswith("All") and not f.endswith("present") and "✓" not in f and "—" in f or chk.ratio < 0.9 for chk, f in [(c, fi) for c in result.checks for fi in c.findings])
    printed_header = False
    for chk in result.checks:
        for finding in chk.findings:
            # Skip pure "all good" messages unless everything is perfect
            is_positive = chk.ratio >= 0.90
            if is_positive and result.total_score >= 95:
                continue
            if not printed_header:
                print(f"  {_c(BOLD)}{_c(WHITE)}Findings:{_c(NC)}")
                printed_header = True
            print(_finding_icon(finding, chk.ratio))

    if not printed_header:
        print(f"  {_c(GREEN)}✓  No issues detected — CV is well-optimised for ATS parsing.{_c(NC)}")

    print()
    _render_threshold_note(result)
    print()


def _render_jd(result) -> None:
    print()
    print(f"{_c(CYAN)}╭{'─' * 76}╮{_c(NC)}")
    print(f"{_c(CYAN)}│{_c(WHITE)}  folia · ATS Score vs Job Description{_c(GRAY)}                                 {_c(CYAN)}│{_c(NC)}")
    print(f"{_c(CYAN)}╰{'─' * 76}╯{_c(NC)}")
    print()

    if result.jd_title:
        print(f"  {_c(GRAY)}Detected JD title:{_c(NC)} {_c(WHITE)}{result.jd_title}{_c(NC)}")
        print()

    label_w = 22
    components = [
        ("Keyword Match", result.keyword_score, "40%"),
        ("Title Match", result.title_score, "25%"),
        ("Experience", result.exp_score, "20%"),
        ("Education", result.edu_score, "15%"),
    ]
    for label, score, weight in components:
        bar = _bar(score, 100.0)
        col = _score_color(score / 100.0)
        icon = _status_icon(score / 100.0)
        print(f"  {label.ljust(label_w)}  {_c(col)}{bar}{_c(NC)}  {str(score).rjust(3)}/100  {_c(GRAY)}({weight}){_c(NC)}  {icon}")

    print()
    print(f"  {_c(GRAY)}{'─' * 74}{_c(NC)}")
    overall_col = _score_color(result.overall_score / 100.0)
    overall_bar = _bar(result.overall_score, 100.0)
    verdict = (
        f"{_c(GREEN)}{_c(BOLD)} ✓ PASS{_c(NC)}"
        if result.passed
        else f"{_c(RED)}{_c(BOLD)} ✗ FAIL{_c(NC)}"
    )
    print(f"  {'Overall ATS Score'.ljust(label_w)}  {_c(overall_col)}{overall_bar}{_c(NC)}  {str(result.overall_score).rjust(3)}/100{verdict}")
    print()

    # Experience note
    print(f"  {_c(GRAY)}Experience detected:{_c(NC)} {_c(WHITE)}{result.years_detected:.1f} years{_c(NC)}")
    print(f"  {_c(GRAY)}Keywords extracted from JD:{_c(NC)} {_c(WHITE)}{result.jd_keyword_count}{_c(NC)} · matched: {_c(GREEN)}{len(result.matched_keywords)}{_c(NC)} · missing: {_c(RED)}{len(result.missing_keywords)}{_c(NC)}")

    # Education gap note
    g = getattr(result, "edu_gap", None)
    if g:
        resume_label = f"{g.resume_level.upper()}"
        if g.resume_field:
            resume_label += f" in {g.resume_field.title()}"
        cs_note = f" (+{g.cs_bonus:.0f} CS bonus)" if g.cs_bonus else ""
        if g.matched:
            print(f"  {_c(GRAY)}Education:{_c(NC)} {_c(GREEN)}✓ {resume_label} meets JD requirement ({g.jd_required.title()}){cs_note}{_c(NC)}")
        else:
            print(f"  {_c(GRAY)}Education:{_c(NC)} {_c(YELLOW)}⚠ {resume_label}{cs_note} · JD prefers {g.jd_required.title()} (score gap: {g.jd_required_level - g.resume_level_score:.0f} pts){_c(NC)}")
    print()

    # Matched / Missing keywords
    BOX_W = 76  # visual inner width between the │ characters
    CONTENT_W = BOX_W - 4  # usable text width (2-space padding each side)

    def _wrap(words: list[str]) -> list[str]:
        line: list[str] = []
        lines: list[str] = []
        for w in words:
            line.append(w)
            if len(", ".join(line)) > CONTENT_W:
                lines.append(", ".join(line[:-1]))
                line = [w]
        if line:
            lines.append(", ".join(line))
        return lines

    def _kw_row(border_col: str, label: str, label_col: str, kw_line: str, first: bool) -> None:
        # label is shown only on first line; subsequent lines are indented to match
        prefix_vis = len(label) if first else len(label)
        prefix = f"{_c(label_col)}{label}{_c(NC)}" if first else " " * len(label)
        content = f"{prefix}{kw_line}"
        pad = CONTENT_W - len(label) - len(kw_line)
        print(f"  {_c(border_col)}│{_c(NC)}  {content}{' ' * max(pad, 0)}  {_c(border_col)}│{_c(NC)}")

    def _plain_row(border_col: str, kw_col: str, kw_line: str) -> None:
        pad = CONTENT_W - len(kw_line)
        print(f"  {_c(border_col)}│{_c(NC)}  {_c(kw_col)}{kw_line}{_c(NC)}{' ' * max(pad, 0)}  {_c(border_col)}│{_c(NC)}")

    def _box_header(border_col: str, title: str) -> None:
        title_pad = BOX_W - 2 - len(title)  # "  " left prefix already in title
        print(f"  {_c(border_col)}╭{'─' * BOX_W}╮{_c(NC)}")
        print(f"  {_c(border_col)}│{_c(BOLD)}{_c(WHITE)}  {title}{' ' * title_pad}{_c(NC)}{_c(border_col)}│{_c(NC)}")
        print(f"  {_c(border_col)}├{'─' * BOX_W}┤{_c(NC)}")

    if result.matched_keywords:
        direct = [m for m in result.matched_keywords if m.matched_via == "direct"]
        ontology = [m for m in result.matched_keywords if m.matched_via == "ontology"]
        fuzzy = [m for m in result.matched_keywords if m.matched_via == "fuzzy"]

        _box_header(GREEN, "Matched Keywords")
        for group, label, col in [
            (direct,   "✓ Direct", GREEN),
            (ontology, "~ Ontology", YELLOW),
            (fuzzy,    "≈ Fuzzy", YELLOW),
        ]:
            if not group:
                continue
            # Label on its own row
            pad = CONTENT_W - len(label)
            print(f"  {_c(GREEN)}│{_c(NC)}  {_c(col)}{_c(BOLD)}{label}{_c(NC)}{' ' * max(pad, 0)}  {_c(GREEN)}│{_c(NC)}")
            # Keywords wrapped below, indented 4 spaces
            for ln in _wrap([m.keyword for m in group]):
                indent = "    "
                pad = CONTENT_W - len(indent) - len(ln)
                print(f"  {_c(GREEN)}│{_c(NC)}  {indent}{ln}{' ' * max(pad, 0)}  {_c(GREEN)}│{_c(NC)}")
        print(f"  {_c(GREEN)}╰{'─' * BOX_W}╯{_c(NC)}")
        print()

    if result.missing_keywords:
        _box_header(RED, "Missing Keywords")
        for ln in _wrap(result.missing_keywords):
            _plain_row(RED, RED, ln)
        print(f"  {_c(RED)}╰{'─' * BOX_W}╯{_c(NC)}")
        print()

        print(f"  {_c(GRAY)}{'─' * (BOX_W + 2)}{_c(NC)}")
        print(f"  {_c(YELLOW)}💡  Suggestion:{_c(NC)} add missing keywords naturally to your experience bullets.")
        print(f"  {_c(GRAY)}{'─' * (BOX_W + 2)}{_c(NC)}")
        print()

    _render_threshold_note(result)
    print()


def _render_threshold_note(result) -> None:
    threshold = result.threshold
    score = result.total_score if result.mode == "health" else result.overall_score
    diff = score - threshold
    if result.passed:
        print(f"  {_c(GRAY)}Pass threshold: {threshold:.0f}  ·  margin: {_c(GREEN)}+{diff:.1f}{_c(NC)}")
    else:
        print(f"  {_c(GRAY)}Pass threshold: {threshold:.0f}  ·  gap: {_c(RED)}{diff:.1f}{_c(NC)}")
