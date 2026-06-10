from __future__ import annotations

from ats import loader as pl


# ── line joining ─────────────────────────────────────────────────────────────

def test_join_wraps_hyphenation():
    lines = ["Built a micro-", "service platform."]
    assert pl._join_wraps(lines) == ["Built a microservice platform."]


def test_join_wraps_lowercase_continuation():
    lines = ["Built a platform that", "scales horizontally."]
    assert pl._join_wraps(lines) == ["Built a platform that scales horizontally."]


def test_join_wraps_keeps_structural_lines_separate():
    lines = [
        "• Did a thing across many services",
        "• Did another thing",
        "Technologies: Python, Go",
    ]
    assert pl._join_wraps(lines) == lines


def test_join_wraps_date_lines_start_fresh():
    lines = ["Acme Corp", "Senior Engineer January 2020 - Present"]
    assert pl._join_wraps(lines) == lines


# ── skills parsing ───────────────────────────────────────────────────────────

def test_split_skill_line_basic():
    category, items = pl._split_skill_line("Languages TypeScript, JavaScript, Python")
    assert category == "Languages"
    assert items == ["TypeScript", "JavaScript", "Python"]


def test_split_skill_line_multiword_category():
    category, items = pl._split_skill_line("Cloud Platforms AWS, GCP, Azure")
    assert category == "Cloud Platforms"
    assert items == ["AWS", "GCP", "Azure"]


# ── positions parsing ────────────────────────────────────────────────────────

def test_parse_positions():
    # Bullets end with periods — without one, _join_wraps treats the next
    # uppercase line as a soft-wrap continuation (the real resume always
    # ends bullets with sentence punctuation).
    lines = [
        "Acme Corp",
        "Senior Software Engineer January 2021 - Present",
        "• Built dashboards for 50k users.",
        "• Led the TypeScript migration.",
        "Initech",
        "Software Engineer June 2018 - December 2020",
        "• Developed REST APIs.",
    ]
    positions = pl._parse_positions(lines)
    assert len(positions) == 2
    first = positions[0]
    assert first.company == "Acme Corp"
    assert first.title == "Senior Software Engineer"
    assert first.dates == "January 2021 - Present"
    assert len(first.items) == 2
    assert positions[1].company == "Initech"
    assert positions[1].items == ["Developed REST APIs."]


# ── projects parsing ─────────────────────────────────────────────────────────

def test_parse_projects():
    lines = [
        "folia Resume generator",
        "• Generated LaTeX resumes from YAML",
        "Technologies: Python, LaTeX",
        "URL: github.com/x/folia",
        "Other Tool CLI helper",
        "• Did something useful",
    ]
    projects = pl._parse_projects(lines)
    assert len(projects) == 2
    assert projects[0].name == "folia Resume generator"
    assert projects[0].tech == ["Python", "LaTeX"]
    assert projects[0].url == "github.com/x/folia"
    assert projects[1].tech == []


# ── section splitting ────────────────────────────────────────────────────────

def test_split_sections():
    lines = [
        "Ada Lovelace",
        "SKILLS",
        "Languages Python, C",
        "EDUCATION",
        "Some University",
    ]
    sections = pl._split_sections(lines)
    assert sections["header"] == ["Ada Lovelace"]
    assert sections["skills"] == ["Languages Python, C"]
    assert sections["education"] == ["Some University"]
