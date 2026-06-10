#!/usr/bin/env python3
"""Load ResumeData by extracting text from the compiled dist/resume.pdf."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

try:
    import pypdf
    _HAS_PYPDF = True
except ImportError:
    _HAS_PYPDF = False

from .loader import (
    REPO_ROOT,
    ContactInfo,
    Language,
    Position,
    Project,
    ResumeData,
    School,
    SkillCategory,
)

DIST_DIR = REPO_ROOT / "dist"
PDF_PATH = DIST_DIR / "resume.pdf"

# ── section header set (all-caps as they appear in PDF) ───────────────────────
_SECTION_MAP: dict[str, str] = {
    "ABOUT ME": "summary",
    "PROFESSIONAL EXPERIENCE": "experience",
    "EXPERIENCE": "experience",
    "INTERNSHIPS": "internships",
    "PROJECTS": "projects",
    "SKILLS": "skills",
    "EDUCATION": "education",
    "LANGUAGES": "languages",
}

# ── regexes ───────────────────────────────────────────────────────────────────
_PAGE_FOOTER_RE = re.compile(
    r"^(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{1,2},\s+\d{4}\s+\d+$",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{4}"
    r"|\b\d{4}\s*[-–]\s*(?:\d{4}|Present)\b",
    re.IGNORECASE,
)
_BULLET = "•"


# ── text extraction ───────────────────────────────────────────────────────────

def _extract_lines(pdf_path: Path) -> list[str]:
    """Return non-empty, non-footer lines from every page of the PDF."""
    if not _HAS_PYPDF:
        raise RuntimeError("pypdf not installed — run: pip install pypdf")
    reader = pypdf.PdfReader(str(pdf_path))
    lines: list[str] = []
    for page in reader.pages:
        for raw in (page.extract_text() or "").split("\n"):
            ln = raw.strip()
            if ln and not _PAGE_FOOTER_RE.match(ln):
                lines.append(ln)
    return lines


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    """Partition lines into named sections keyed by _SECTION_MAP values."""
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for ln in lines:
        key = _SECTION_MAP.get(ln.upper())
        if key:
            current = key
            sections.setdefault(current, [])
        else:
            sections[current].append(ln)
    return sections


# ── line-joining (handle PDF soft-wrap and hyphenation) ───────────────────────

_STRUCTURAL_PREFIXES = (_BULLET, "Technologies:", "URL:")


def _is_structural(ln: str) -> bool:
    return (
        any(ln.startswith(p) for p in _STRUCTURAL_PREFIXES)
        or bool(_DATE_RE.search(ln))
        or ln.upper() in _SECTION_MAP
    )


def _join_wraps(lines: list[str]) -> list[str]:
    """Join continuation lines back into complete logical lines.

    A line is a continuation of the previous when:
    - previous line ends with '-' (hyphenated word-break)
    - current line starts with a lowercase letter (sentence wrap)
    - previous line ends without sentence-closing punctuation AND
      current line starts with an uppercase letter that is NOT a new
      structural element (bullet, date, Technologies:, URL:, section header)
    """
    if not lines:
        return []
    result: list[str] = []
    current = lines[0]
    for ln in lines[1:]:
        if not ln:
            continue
        # Structural lines always start fresh — never merged into previous
        if _is_structural(ln):
            result.append(current)
            current = ln
        elif current.endswith("-"):
            current = current[:-1] + ln
        elif ln[0].islower():
            current = current + " " + ln
        # Technologies:/URL: lines are always complete — never absorb the next line
        elif any(current.startswith(p) for p in ("Technologies:", "URL:")):
            result.append(current)
            current = ln
        elif current[-1] not in ".!?":
            # Uppercase continuation without sentence boundary (e.g. "Next.js, ...")
            current = current + " " + ln
        else:
            result.append(current)
            current = ln
    result.append(current)
    return result


# ── section parsers ───────────────────────────────────────────────────────────

def _parse_contact(header: list[str]) -> ContactInfo:
    name_parts = header[0].split() if header else []
    first = name_parts[0] if name_parts else ""
    last = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
    position = header[1] if len(header) > 1 else ""
    address = header[2] if len(header) > 2 else ""

    email = mobile = homepage = github = linkedin = ""
    usernames: list[str] = []

    for ln in header[3:]:
        # Contact bar format: "ICON value | ICON value | ..."
        # Each chunk is: single icon character + space + the actual value
        for chunk in ln.split("|"):
            parts = chunk.strip().split(None, 1)  # split at first whitespace
            if len(parts) < 2:
                continue
            val = parts[1].strip()
            if not val:
                continue
            if "@" in val:
                email = val
            elif re.match(r"\+\d", val):
                mobile = val
            elif "." in val and " " not in val:
                homepage = homepage or val
            else:
                usernames.append(val)

    # Assign usernames in the order they appear: first → github, second → linkedin
    if usernames:
        github = usernames[0]
    if len(usernames) > 1:
        linkedin = usernames[1]

    return ContactInfo(
        first_name=first,
        last_name=last,
        position=position,
        address=address,
        email=email,
        mobile=mobile,
        homepage=homepage,
        github=github,
        linkedin=linkedin,
    )


def _parse_summary(lines: list[str]) -> str:
    return " ".join(_join_wraps(lines))


def _collect_bullets(lines: list[str], start: int) -> tuple[list[str], int]:
    """Collect bullet items starting at index start; return (items, next_idx)."""
    items: list[str] = []
    i = start
    while i < len(lines) and lines[i].startswith(_BULLET):
        items.append(lines[i][1:].strip())
        i += 1
    return items, i


def _parse_positions(lines: list[str]) -> list[Position]:
    """Parse experience or internship lines into Position objects."""
    lines = _join_wraps(lines)
    positions: list[Position] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        # Pattern: company line (no date) immediately followed by title+date line
        if (
            not ln.startswith(_BULLET)
            and not _DATE_RE.search(ln)
            and i + 1 < len(lines)
            and not lines[i + 1].startswith(_BULLET)
            and _DATE_RE.search(lines[i + 1])
        ):
            company = ln
            title_ln = lines[i + 1]
            dm = _DATE_RE.search(title_ln)
            title = title_ln[: dm.start()].strip() if dm else title_ln
            dates = title_ln[dm.start() :].strip() if dm else ""
            items, j = _collect_bullets(lines, i + 2)
            positions.append(
                Position(title=title, company=company, location="", dates=dates, items=items)
            )
            i = j
        else:
            i += 1
    return positions


def _parse_projects(lines: list[str]) -> list[Project]:
    lines = _join_wraps(lines)
    projects: list[Project] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith(_BULLET) or ln.startswith("Technologies:") or ln.startswith("URL:"):
            i += 1
            continue
        # New project header line (name + subtitle concatenated)
        name = ln
        items: list[str] = []
        tech: list[str] = []
        url: str | None = None
        j = i + 1
        while j < len(lines):
            bl = lines[j]
            if bl.startswith(_BULLET):
                items.append(bl[1:].strip())
            elif bl.startswith("Technologies:"):
                tech = [t.strip() for t in bl[len("Technologies:"):].split(",") if t.strip()]
            elif bl.startswith("URL:"):
                url = bl[len("URL:"):].strip()
            else:
                break  # next project starts
            j += 1
        projects.append(Project(name=name, subtitle="", items=items, tech=tech, url=url))
        i = j
    return projects


def _is_tech_term_start(word: str, prev_word: str | None) -> bool:
    """Return True if word looks like the first word of the items list."""
    if prev_word == "&":
        return False
    at_start = prev_word is None
    if re.search(r"[./()]", word):
        return True
    if len(word) >= 3 and word.isupper():
        return True
    if not at_start and re.search(r"[a-z][A-Z]", word):
        return True
    if not at_start and word[-1:].isdigit():
        return True
    return False


def _split_skill_line(line: str) -> tuple[str, list[str]]:
    """Split 'Category Item1, Item2, ...' → (category_name, [items])."""
    comma_pos = line.find(",")
    if comma_pos == -1:
        # No comma — split at last space as best effort
        parts = line.rsplit(" ", 1)
        return (parts[0], [parts[1]]) if len(parts) == 2 else ("", [line])

    pre = line[:comma_pos]
    post = line[comma_pos + 1 :]
    words = pre.split()

    item_start = len(words)
    prev: str | None = None
    for idx, w in enumerate(words):
        if _is_tech_term_start(w, prev):
            item_start = idx
            break
        prev = w
    if item_start == len(words):
        item_start = max(len(words) - 1, 0)

    category = " ".join(words[:item_start])
    first_item = " ".join(words[item_start:])
    all_items = (first_item + ", " + post.strip()) if first_item else post.strip()
    items = [s.strip() for s in all_items.split(",") if s.strip()]
    return category, items


def _parse_skills(lines: list[str]) -> list[SkillCategory]:
    """Join wrapped skill lines then parse each into (category, items)."""
    joined: list[str] = []
    for ln in lines:
        if not ln.strip():
            continue
        if not joined:
            joined.append(ln)
            continue
        prev = joined[-1]
        last_word = prev.rstrip().split()[-1] if prev.strip() else ""
        if (
            prev.rstrip().endswith(",")
            or (len(last_word) <= 2 and last_word.isupper())
            or not ln[0].isupper()
        ):
            joined[-1] = prev.rstrip() + " " + ln.strip()
        else:
            joined.append(ln)

    cats: list[SkillCategory] = []
    for ln in joined:
        category, items = _split_skill_line(ln.strip())
        if items:
            cats.append(SkillCategory(category=category, items=items))
    return cats


def _parse_schools(lines: list[str]) -> list[School]:
    lines = _join_wraps(lines)
    schools: list[School] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if (
            not ln.startswith(_BULLET)
            and not _DATE_RE.search(ln)
            and i + 1 < len(lines)
            and _DATE_RE.search(lines[i + 1])
        ):
            institution = ln
            deg_ln = lines[i + 1]
            dm = _DATE_RE.search(deg_ln)
            degree = deg_ln[: dm.start()].strip() if dm else deg_ln
            dates = deg_ln[dm.start() :].strip() if dm else ""
            items, j = _collect_bullets(lines, i + 2)
            schools.append(
                School(
                    degree=degree,
                    institution=institution,
                    location="",
                    dates=dates,
                    items=items,
                )
            )
            i = j
        else:
            i += 1
    return schools


def _parse_languages(lines: list[str]) -> list[Language]:
    langs: list[Language] = []
    for ln in lines:
        parts = ln.split(" ", 1)
        langs.append(Language(name=parts[0], level=parts[1] if len(parts) > 1 else ""))
    return langs


# ── public API ────────────────────────────────────────────────────────────────

def ensure_pdf(pdf_path: Path = PDF_PATH) -> None:
    """Build the PDF if it doesn't exist yet."""
    if pdf_path.exists():
        return
    build_script = REPO_ROOT / "core" / "scripts" / "build.py"
    print(f"  PDF not found — running build first…", flush=True)
    result = subprocess.run(
        [sys.executable, str(build_script)],
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        raise RuntimeError("Build failed — cannot run ATS without dist/resume.pdf")


def load(pdf_path: Path = PDF_PATH) -> ResumeData:
    """Extract and parse ResumeData from a compiled PDF."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    lines = _extract_lines(pdf_path)
    sec = _split_sections(lines)

    resume = ResumeData(
        contact=_parse_contact(sec.get("header", [])),
        summary=_parse_summary(sec.get("summary", [])),
        positions=_parse_positions(sec.get("experience", [])),
        internships=_parse_positions(sec.get("internships", [])),
        projects=_parse_projects(sec.get("projects", [])),
        skills=_parse_skills(sec.get("skills", [])),
        schools=_parse_schools(sec.get("education", [])),
        languages=_parse_languages(sec.get("languages", [])),
    )

    if not resume.contact.full_name:
        raise ValueError("Could not extract a name from the PDF — is the PDF valid?")
    return resume
