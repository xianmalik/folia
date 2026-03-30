#!/usr/bin/env python3
"""
Minimal YAML → TeX generator. Reads data/*.yml and writes sections/*.tex.
No-op if data directory or files are missing, or if PyYAML is unavailable.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:
    print("generate.py: PyYAML not installed — skipping generation", file=sys.stderr)
    sys.exit(0)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
SECTIONS_DIR = REPO_ROOT / "sections"

if not DATA_DIR.exists() or not SECTIONS_DIR.exists():
    sys.exit(0)


def read_yaml(filename: str) -> dict | None:
    path = DATA_DIR / filename
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        print(f"generate.py: failed to parse {filename} — {e}", file=sys.stderr)
        return None


def write_file(path: Path, content: str) -> None:
    """Write content to path using UTF-8 encoding."""
    path.write_text(content, encoding="utf-8")


def _escape_special(s: str) -> str:
    """Escape LaTeX special characters in a plain string, leaving no formatting."""
    return (
        s
        .replace("\\", "\\textbackslash{}")
        .replace("%", "\\%")
        .replace("&", "\\&")
        .replace("#", "\\#")
        .replace("_", "\\_")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("$", "\\$")
    )


def latex_escape(s: str) -> str:
    """Escape s for LaTeX output, converting [[text]] markers to \\textbf{text}.

    Bold markers are split out before escaping so their braces are not
    themselves escaped.
    """
    s = str(s)
    parts = re.split(r"(\[\[.*?\]\])", s)
    result = []
    for part in parts:
        if part.startswith("[[") and part.endswith("]]"):
            result.append(f"\\textbf{{{_escape_special(part[2:-2])}}}")
        else:
            result.append(_escape_special(part))
    return "".join(result)


def _build_cventry(entry: dict, title_key: str, org_key: str) -> str:
    """Render a single \\cventry block from an entry dict.

    Args:
        entry: Dict with keys for title_key, org_key, location, dates, items.
        title_key: Key to use as the position/degree field (e.g. "title", "degree").
        org_key: Key to use as the organisation field (e.g. "company", "institution").
    """
    bullets = "\n".join(
        f"        \\item {{{latex_escape(t)}}}" for t in entry.get("items", [])
    )
    return (
        "  \\cventry\n"
        f"    {{{latex_escape(entry.get(title_key, ''))}}}\n"
        f"    {{{latex_escape(entry.get(org_key, ''))}}}\n"
        f"    {{{latex_escape(entry.get('location', ''))}}}\n"
        f"    {{{latex_escape(entry.get('dates', ''))}}}\n"
        "    {\n"
        "      \\begin{cvitems}\n"
        f"{bullets}\n"
        "      \\end{cvitems}\n"
        "    }"
    )


def _wrap_section(title: str, body: str) -> str:
    """Wrap pre-rendered entry blocks in a \\cvsection + cventries environment."""
    return (
        f"\\cvsection{{{title}}}\n\n"
        "\\begin{cventries}\n\n"
        f"{body}\n\n"
        "\\end{cventries}\n"
    )


def gen_summary(data: dict | None) -> str | None:
    """Generate the ABOUT ME section from 00-summary.yml."""
    if not data or not data.get("summary"):
        return None
    return (
        "\\cvsection{ABOUT ME}\n\n"
        "\\begin{cvparagraph}\n"
        f"  {data['summary']}\n"
        "\\end{cvparagraph}\n"
    )


def gen_experience(data: dict | None) -> str | None:
    """Generate PROFESSIONAL EXPERIENCE (and optional INTERNSHIPS) from 10-experience.yml."""
    if not data or not isinstance(data.get("positions"), list):
        return None

    body = "\n\n".join(
        _build_cventry(p, title_key="title", org_key="company")
        for p in data["positions"]
    )
    tex = _wrap_section("PROFESSIONAL EXPERIENCE", body)

    internships = data.get("internships")
    if isinstance(internships, list) and internships:
        ibody = "\n\n".join(
            _build_cventry(p, title_key="title", org_key="company")
            for p in internships
        )
        tex += "\n" + _wrap_section("INTERNSHIPS", ibody)

    return tex


def gen_education(data: dict | None) -> str | None:
    """Generate the EDUCATION section from 40-education.yml."""
    if not data or not isinstance(data.get("schools"), list):
        return None

    body = "\n\n".join(
        _build_cventry(s, title_key="degree", org_key="institution")
        for s in data["schools"]
    )
    return _wrap_section("EDUCATION", body)


def gen_projects(data: dict | None) -> str | None:
    """Generate the PROJECTS section from 20-projects.yml."""
    if not data or not isinstance(data.get("projects"), list):
        return None

    chunks = []
    for p in data["projects"]:
        bullets = "\n".join(
            f"        \\item {{{latex_escape(t)}}}" for t in p.get("items", [])
        )
        tech = latex_escape(", ".join(p.get("tech", [])))
        url = p.get("url")
        url_label = p.get("urlLabel") or url or ""
        url_tex = f"\\href{{{url}}}{{{latex_escape(url_label)}}}" if url else ""
        chunks.append(
            "  \\cvproject\n"
            f"    {{{latex_escape(p.get('name', ''))}}}\n"
            f"    {{{latex_escape(p.get('subtitle', ''))}}}\n"
            "    {\n"
            "      \\begin{cvitems}\n"
            f"{bullets}\n"
            "      \\end{cvitems}\n"
            "    }\n"
            f"    {{{tech}}}\n"
            f"    {{{url_tex}}}"
        )

    body = "\n\n".join(chunks)
    return _wrap_section("PROJECTS", body)


def gen_skills(data: dict | None) -> str | None:
    """Generate the SKILLS section from 30-skills.yml."""
    if not data or not isinstance(data.get("skills"), list):
        return None
    rows = "\n".join(
        f"        \\cvskill {{{latex_escape(s.get('category', ''))}}} {{{latex_escape(', '.join(s.get('items', [])))}}}"
        for s in data["skills"]
    )
    return (
        "\\cvsection{SKILLS}\n"
        "    \\begin{cvskills}\n"
        f"{rows}\n"
        "\\end{cvskills}\n"
    )


def gen_languages(data: dict | None) -> str | None:
    """Generate the LANGUAGES section from 50-languages.yml."""
    if not data or not isinstance(data.get("languages"), list):
        return None
    rows = "\n\n".join(
        "  \\cvskill\n    {" + latex_escape(item.get("name", "")) + "}\n    {" + latex_escape(item.get("level", "")) + "}"
        for item in data["languages"]
    )
    return (
        "\\cvsection{LANGUAGES}\n\n"
        "\\begin{cvlanguages}\n\n"
        f"{rows}\n\n"
        "\\end{cvlanguages}\n"
    )


outputs = {
    "00-summary.tex":   (gen_summary,    "00-summary.yml"),
    "10-experience.tex": (gen_experience, "10-experience.yml"),
    "20-projects.tex":  (gen_projects,   "20-projects.yml"),
    "30-skills.tex":    (gen_skills,     "30-skills.yml"),
    "40-education.tex": (gen_education,  "40-education.yml"),
    "50-languages.tex": (gen_languages,  "50-languages.yml"),
}

for tex_file, (gen_fn, yml_file) in outputs.items():
    data = read_yaml(yml_file)
    content = gen_fn(data)
    if content:
        write_file(SECTIONS_DIR / tex_file, content)
    elif data is not None:
        print(f"generate.py: {yml_file} loaded but produced no output — check required fields", file=sys.stderr)

sys.exit(0)
