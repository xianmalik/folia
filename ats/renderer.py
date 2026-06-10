#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

from . import config as _cfg
from . import box as _box

# ANSI codes — matches build.py palette
CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
WHITE = "\033[1;37m"
GRAY = "\033[0;37m"
BOLD = "\033[1m"
NC = "\033[0m"

_RC = _cfg.get()["renderer"]
_THRESH_PASS = _RC["thresh_pass"]
_THRESH_GOOD = _RC["thresh_good"]
_THRESH_WARN = _RC["thresh_warn"]


def _c(code: str, use_color: bool) -> str:
    return code if use_color else ""


def _is_tty() -> bool:
    return hasattr(sys.stdout, "fileno") and os.isatty(sys.stdout.fileno())


def _bar(score: float, max_score: float, width: int = 28) -> str:
    frac = min(score / max_score, 1.0) if max_score > 0 else 0.0
    filled = round(frac * width)
    return "█" * filled + "░" * (width - filled)


def _score_color(ratio: float) -> str:
    if ratio >= _THRESH_GOOD:
        return GREEN
    if ratio >= _THRESH_WARN:
        return YELLOW
    return RED


def _status_icon(ratio: float, use_color: bool) -> str:
    if ratio >= _THRESH_PASS:
        return f"{_c(GREEN, use_color)}✓{_c(NC, use_color)}"
    if ratio >= _THRESH_WARN:
        return f"{_c(YELLOW, use_color)}⚠{_c(NC, use_color)}"
    return f"{_c(RED, use_color)}✗{_c(NC, use_color)}"


def _finding_icon(text: str, ratio: float, use_color: bool) -> str:
    if ratio >= _THRESH_PASS:
        return f"  {_c(GREEN, use_color)}✓{_c(NC, use_color)}  {text}"
    if ratio >= _THRESH_WARN:
        return f"  {_c(YELLOW, use_color)}⚠{_c(NC, use_color)}  {text}"
    return f"  {_c(RED, use_color)}✗{_c(NC, use_color)}  {text}"


def render(result, no_color: bool = False) -> None:
    use_color = not no_color and _is_tty()
    if result.mode == "health":
        _render_health(result, use_color)
    else:
        _render_jd(result, use_color)


def _render_health(result, use_color: bool) -> None:
    c = lambda code: _c(code, use_color)
    print()
    b = _box.Box(CYAN, c, indent="")
    b.open()
    b.row("folia · ATS Health Check", color=WHITE)
    b.close()
    print()

    label_w = 22
    for chk in result.checks:
        label = chk.label.ljust(label_w)
        bar = _bar(chk.score, chk.max_score)
        col = _score_color(chk.ratio)
        icon = _status_icon(chk.ratio, use_color)
        pts = f"{chk.score:.0f}/{chk.max_score:.0f}"
        print(f"  {c(WHITE)}{label}{c(NC)}  {c(col)}{bar}{c(NC)}  {pts.rjust(6)}  {icon}")

    print()
    print(f"  {c(GRAY)}{'─' * 74}{c(NC)}")

    overall_ratio = result.total_score / 100.0
    col = _score_color(overall_ratio)
    overall_bar = _bar(result.total_score, 100.0)
    verdict = (
        f"{c(GREEN)}{c(BOLD)} ✓ PASS{c(NC)}"
        if result.passed
        else f"{c(RED)}{c(BOLD)} ✗ FAIL{c(NC)}"
    )
    print(f"  {'Overall CV Score'.ljust(label_w)}  {c(col)}{overall_bar}{c(NC)}  {str(result.total_score).rjust(3)}/100{verdict}")
    print()

    printed_header = False
    for chk in result.checks:
        for finding in chk.findings:
            is_positive = chk.ratio >= _THRESH_PASS
            if is_positive and result.total_score >= 95:
                continue
            if not printed_header:
                print(f"  {c(BOLD)}{c(WHITE)}Findings:{c(NC)}")
                printed_header = True
            print(_finding_icon(finding, chk.ratio, use_color))

    if not printed_header:
        print(f"  {c(GREEN)}✓  No issues detected — CV is well-optimised for ATS parsing.{c(NC)}")

    print()
    _render_threshold_note(result, use_color)
    print()


def _chunk_text(text: str, width: int) -> list[str]:
    """Split text into chunks that fit within width characters."""
    if len(text) <= width:
        return [text]
    chunks = []
    while text:
        if len(text) <= width:
            chunks.append(text)
            break
        cut = text.rfind(" ", 0, width)
        if cut == -1:
            cut = width
        chunks.append(text[:cut])
        text = text[cut:].lstrip()
    return chunks


def render_jd_header(author: str = "", email: str = "", no_color: bool = False) -> None:
    """Print the JD report title box. Called before processing so it sits on top."""
    use_color = not no_color and _is_tty()
    c = lambda code: _c(code, use_color)
    print()
    b = _box.Box(CYAN, c, indent="")
    b.open()
    b.row("folia · ATS Score vs Job Description", color=WHITE)
    if author:
        line = f"Author: {author}"
        if email:
            line += f"  ·  {email}"
        b.row(line, color=GRAY)
    b.close()
    print()


def _render_jd(result, use_color: bool) -> None:
    c = lambda code: _c(code, use_color)

    if getattr(result, "llm_fallback", False):
        print(f"  {c(YELLOW)}⚠  LLM rate limit hit — results based on local NLP analysis (less accurate){c(NC)}")
        print()

    if result.jd_title:
        print(f"  {c(GRAY)}Detected JD title:{c(NC)} {c(WHITE)}{result.jd_title}{c(NC)}")
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
        icon = _status_icon(score / 100.0, use_color)
        print(f"  {label.ljust(label_w)}  {c(col)}{bar}{c(NC)}  {str(score).rjust(3)}/100  {c(GRAY)}({weight}){c(NC)}  {icon}")

    print()
    print(f"  {c(GRAY)}{'─' * 74}{c(NC)}")
    overall_col = _score_color(result.overall_score / 100.0)
    overall_bar = _bar(result.overall_score, 100.0)
    verdict = (
        f"{c(GREEN)}{c(BOLD)} ✓ PASS{c(NC)}"
        if result.passed
        else f"{c(RED)}{c(BOLD)} ✗ FAIL{c(NC)}"
    )
    print(f"  {'Overall ATS Score'.ljust(label_w)}  {c(overall_col)}{overall_bar}{c(NC)}  {str(result.overall_score).rjust(3)}/100{verdict}")
    print()

    print(f"  {c(GRAY)}Experience detected:{c(NC)} {c(WHITE)}{result.years_detected:.1f} years{c(NC)}")
    print(f"  {c(GRAY)}Keywords extracted from JD:{c(NC)} {c(WHITE)}{result.jd_keyword_count}{c(NC)} · matched: {c(GREEN)}{len(result.matched_keywords)}{c(NC)} · missing: {c(RED)}{len(result.missing_keywords)}{c(NC)}")

    g = getattr(result, "edu_gap", None)
    if g:
        resume_label = f"{g.resume_level.upper()}"
        if g.resume_field:
            resume_label += f" in {g.resume_field.title()}"
        cs_note = f" (+{g.cs_bonus:.0f} CS bonus)" if g.cs_bonus else ""
        if g.matched:
            print(f"  {c(GRAY)}Education:{c(NC)} {c(GREEN)}✓ {resume_label} meets JD requirement ({g.jd_required.title()}){cs_note}{c(NC)}")
        else:
            print(f"  {c(GRAY)}Education:{c(NC)} {c(YELLOW)}⚠ {resume_label}{cs_note} · JD prefers {g.jd_required.title()} (score gap: {g.jd_required_level - g.resume_level_score:.0f} pts){c(NC)}")
    print()

    def _wrap(words: list[str], indent: int = 0) -> list[str]:
        max_w = _box.CONTENT_W - indent
        line: list[str] = []
        lines: list[str] = []
        for w in words:
            line.append(w)
            if len(", ".join(line)) > max_w:
                lines.append(", ".join(line[:-1]))
                line = [w]
        if line:
            lines.append(", ".join(line))
        return lines

    if result.matched_keywords:
        direct   = [m for m in result.matched_keywords if m.matched_via == "direct"]
        ontology = [m for m in result.matched_keywords if m.matched_via == "ontology"]
        fuzzy    = [m for m in result.matched_keywords if m.matched_via == "fuzzy"]
        b = _box.Box(GREEN, c)
        b.open("Matched Keywords")
        kw_indent = "    "
        for group, label, col in [
            (direct,   "✓ Direct",   GREEN),
            (ontology, "~ Ontology", YELLOW),
            (fuzzy,    "≈ Fuzzy",    YELLOW),
        ]:
            if not group:
                continue
            b.raw_row(f"{c(col)}{c(BOLD)}{label}{c(NC)}", len(label))
            for ln in _wrap([m.keyword for m in group], indent=len(kw_indent)):
                b.row(kw_indent + ln)
        b.close()
        print()

    if result.missing_keywords:
        b = _box.Box(RED, c)
        b.open("Missing Keywords")
        for ln in _wrap(result.missing_keywords):
            b.row(ln, color=RED)
        b.close()
        print()

        _box.rule(GRAY, c)
        print(f"  {c(YELLOW)}💡  Suggestion:{c(NC)} add missing keywords naturally to your experience bullets.")
        _box.rule(GRAY, c)
        print()

    keyword_density = getattr(result, "keyword_density", {})
    if keyword_density:
        total_hits = sum(keyword_density.values())
        _SECTION_ORDER = ["experience", "skills", "projects", "summary", "education"]
        ordered = [(s, keyword_density[s]) for s in _SECTION_ORDER if s in keyword_density]
        ordered += [(s, v) for s, v in keyword_density.items() if s not in _SECTION_ORDER]
        print(f"  {c(BOLD)}{c(WHITE)}Keyword Density by Section:{c(NC)}")
        label_w2 = 12
        bar_w2 = 20
        for section, hits in ordered:
            frac = hits / total_hits if total_hits > 0 else 0.0
            filled = round(frac * bar_w2)
            bar2 = "█" * filled + "░" * (bar_w2 - filled)
            col2 = _score_color(frac if frac >= 0.3 else frac + 0.1)
            pct = f"{frac * 100:.0f}%"
            print(f"  {section.capitalize().ljust(label_w2)}  {c(col2)}{bar2}{c(NC)}  {str(hits).rjust(2)} hits  {pct.rjust(4)}")
        print()

    backend = getattr(result, "backend", "spacy")
    role_fit = getattr(result, "role_fit", "") if backend == "llm" else ""
    suggestions = getattr(result, "suggestions", []) if backend == "llm" else []
    bullet_rewrites = getattr(result, "bullet_rewrites", []) if backend == "llm" else []

    if role_fit:
        print(f"  {c(BOLD)}{c(WHITE)}Role Fit Assessment:{c(NC)}")
        print(f"  {c(GRAY)}{role_fit}{c(NC)}")
        print()

    if suggestions:
        print(f"  {c(BOLD)}{c(WHITE)}AI Suggestions:{c(NC)}")
        for idx, sug in enumerate(suggestions, 1):
            print(f"  {c(CYAN)}{idx}.{c(NC)} {sug}")
        print()

    if bullet_rewrites:
        b = _box.Box(CYAN, c)
        b.open("Bullet Rewrite Suggestions")
        for idx, rw in enumerate(bullet_rewrites):
            if idx > 0:
                b.sep()
            kw_line   = f"Keyword  {rw.keyword}"
            role_line = f"Role     {rw.role}"
            b.raw_row(f"{c(YELLOW)}{c(BOLD)}{kw_line}{c(NC)}", len(kw_line))
            b.raw_row(f"{c(YELLOW)}{role_line}{c(NC)}", len(role_line))
            before_label = "Before  "
            after_label  = "After   "
            lbl_w = len(before_label)
            for i, chunk in enumerate(_chunk_text(rw.original, _box.CONTENT_W - lbl_w)):
                lbl = before_label if i == 0 else " " * lbl_w
                b.raw_row(f"{c(GRAY)}{lbl}{chunk}{c(NC)}", lbl_w + len(chunk))
            for i, chunk in enumerate(_chunk_text(rw.rewritten, _box.CONTENT_W - lbl_w)):
                lbl = after_label if i == 0 else " " * lbl_w
                b.raw_row(f"{c(GREEN)}{lbl}{chunk}{c(NC)}", lbl_w + len(chunk))
        b.close()
        print()

    _render_threshold_note(result, use_color)
    print()


def _render_threshold_note(result, use_color: bool) -> None:
    c = lambda code: _c(code, use_color)
    threshold = result.threshold
    score = result.total_score if result.mode == "health" else result.overall_score
    diff = score - threshold
    if result.passed:
        print(f"  {c(GRAY)}Pass threshold: {threshold:.0f}  ·  margin: {c(GREEN)}+{diff:.1f}{c(NC)}")
    else:
        print(f"  {c(GRAY)}Pass threshold: {threshold:.0f}  ·  gap: {c(RED)}{diff:.1f}{c(NC)}")
