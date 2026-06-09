#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

from . import config as _cfg

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
    print(f"{c(CYAN)}╭{'─' * 76}╮{c(NC)}")
    print(f"{c(CYAN)}│{c(WHITE)}  folia · ATS Health Check{c(GRAY)}                                               {c(CYAN)}│{c(NC)}")
    print(f"{c(CYAN)}╰{'─' * 76}╯{c(NC)}")
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


def _render_jd(result, use_color: bool) -> None:
    c = lambda code: _c(code, use_color)
    BOX_W = 76
    author = getattr(result, "author_name", "")
    backend = getattr(result, "backend", "spacy")
    backend_label = "LLM" if backend == "llm" else "NLP"
    title_text = f"  folia · ATS Score vs Job Description  [{backend_label}]"
    title_pad = BOX_W - len(title_text)
    print()
    print(f"{c(CYAN)}╭{'─' * BOX_W}╮{c(NC)}")
    print(f"{c(CYAN)}│{c(WHITE)}{title_text}{' ' * max(title_pad, 0)}{c(CYAN)}│{c(NC)}")
    if author:
        author_text = f"  Author: {author}"
        author_pad = BOX_W - len(author_text)
        print(f"{c(CYAN)}│{c(GRAY)}{author_text}{' ' * max(author_pad, 0)}{c(CYAN)}│{c(NC)}")
    print(f"{c(CYAN)}╰{'─' * BOX_W}╯{c(NC)}")
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

    CONTENT_W = BOX_W - 4

    def _wrap(words: list[str], indent: int = 0) -> list[str]:
        max_w = CONTENT_W - indent
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

    def _kw_row(border_col: str, label: str, label_col: str, kw_line: str, first: bool) -> None:
        prefix = f"{c(label_col)}{label}{c(NC)}" if first else " " * len(label)
        content = f"{prefix}{kw_line}"
        pad = CONTENT_W - len(label) - len(kw_line)
        print(f"  {c(border_col)}│{c(NC)}  {content}{' ' * max(pad, 0)}  {c(border_col)}│{c(NC)}")

    def _plain_row(border_col: str, kw_col: str, kw_line: str) -> None:
        pad = CONTENT_W - len(kw_line)
        print(f"  {c(border_col)}│{c(NC)}  {c(kw_col)}{kw_line}{c(NC)}{' ' * max(pad, 0)}  {c(border_col)}│{c(NC)}")

    def _box_header(border_col: str, title: str) -> None:
        title_pad = BOX_W - 2 - len(title)
        print(f"  {c(border_col)}╭{'─' * BOX_W}╮{c(NC)}")
        print(f"  {c(border_col)}│{c(BOLD)}{c(WHITE)}  {title}{' ' * title_pad}{c(NC)}{c(border_col)}│{c(NC)}")
        print(f"  {c(border_col)}├{'─' * BOX_W}┤{c(NC)}")

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
            pad = CONTENT_W - len(label)
            print(f"  {c(GREEN)}│{c(NC)}  {c(col)}{c(BOLD)}{label}{c(NC)}{' ' * max(pad, 0)}  {c(GREEN)}│{c(NC)}")
            kw_indent = "    "
            for ln in _wrap([m.keyword for m in group], indent=len(kw_indent)):
                pad = CONTENT_W - len(kw_indent) - len(ln)
                print(f"  {c(GREEN)}│{c(NC)}  {kw_indent}{ln}{' ' * max(pad, 0)}  {c(GREEN)}│{c(NC)}")
        print(f"  {c(GREEN)}╰{'─' * BOX_W}╯{c(NC)}")
        print()

    if result.missing_keywords:
        _box_header(RED, "Missing Keywords")
        for ln in _wrap(result.missing_keywords):
            _plain_row(RED, RED, ln)
        print(f"  {c(RED)}╰{'─' * BOX_W}╯{c(NC)}")
        print()

        print(f"  {c(GRAY)}{'─' * (BOX_W + 2)}{c(NC)}")
        print(f"  {c(YELLOW)}💡  Suggestion:{c(NC)} add missing keywords naturally to your experience bullets.")
        print(f"  {c(GRAY)}{'─' * (BOX_W + 2)}{c(NC)}")
        print()

    if backend == "llm":
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

        role_fit = getattr(result, "role_fit", "")
        suggestions = getattr(result, "suggestions", [])
        bullet_rewrites = getattr(result, "bullet_rewrites", [])

    if backend == "llm" and role_fit:
        print(f"  {c(BOLD)}{c(WHITE)}Role Fit Assessment:{c(NC)}")
        print(f"  {c(GRAY)}{role_fit}{c(NC)}")
        print()

    if backend == "llm" and suggestions:
        print(f"  {c(BOLD)}{c(WHITE)}AI Suggestions:{c(NC)}")
        for idx, sug in enumerate(suggestions, 1):
            print(f"  {c(CYAN)}{idx}.{c(NC)} {sug}")
        print()

    if backend == "llm" and bullet_rewrites:
        _box_header(CYAN, "Bullet Rewrite Suggestions")
        for idx, rw in enumerate(bullet_rewrites):
            if idx > 0:
                print(f"  {c(CYAN)}├{'─' * BOX_W}┤{c(NC)}")
            kw_line = f"Keyword  {rw.keyword}"
            kw_pad = CONTENT_W - len(kw_line)
            print(f"  {c(CYAN)}│{c(NC)}  {c(YELLOW)}{c(BOLD)}{kw_line}{c(NC)}{' ' * max(kw_pad, 0)}  {c(CYAN)}│{c(NC)}")
            role_line = f"Role     {rw.role}"
            role_pad = CONTENT_W - len(role_line)
            print(f"  {c(CYAN)}│{c(NC)}  {c(YELLOW)}{role_line}{c(NC)}{' ' * max(role_pad, 0)}  {c(CYAN)}│{c(NC)}")
            # Before
            before_label = "Before  "
            for i, chunk in enumerate(_chunk_text(rw.original, CONTENT_W - len(before_label))):
                lbl = before_label if i == 0 else " " * len(before_label)
                pad = CONTENT_W - len(lbl) - len(chunk)
                print(f"  {c(CYAN)}│{c(NC)}  {c(GRAY)}{lbl}{chunk}{c(NC)}{' ' * max(pad, 0)}  {c(CYAN)}│{c(NC)}")
            # After
            after_label = "After   "
            for i, chunk in enumerate(_chunk_text(rw.rewritten, CONTENT_W - len(after_label))):
                lbl = after_label if i == 0 else " " * len(after_label)
                pad = CONTENT_W - len(lbl) - len(chunk)
                print(f"  {c(CYAN)}│{c(NC)}  {c(GREEN)}{lbl}{chunk}{c(NC)}{' ' * max(pad, 0)}  {c(CYAN)}│{c(NC)}")
        print(f"  {c(CYAN)}╰{'─' * BOX_W}╯{c(NC)}")
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
