#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:
    print("loader.py: PyYAML not installed — run: pip install PyYAML", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "source"
RESUME_TEX = REPO_ROOT / "core" / "resume.tex"

_BOLD_RE = re.compile(r"\[\[(.+?)\]\]")


def _strip_bold(s: str) -> str:
    return _BOLD_RE.sub(r"\1", str(s))


def _tex_macro(tex: str, macro: str) -> str:
    m = re.search(rf"\\{re.escape(macro)}\{{([^}}]*)\}}", tex)
    return m.group(1).strip() if m else ""


@dataclass
class ContactInfo:
    first_name: str = ""
    last_name: str = ""
    position: str = ""
    address: str = ""
    mobile: str = ""
    email: str = ""
    github: str = ""
    linkedin: str = ""
    homepage: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


@dataclass
class Position:
    title: str
    company: str
    location: str
    dates: str
    items: list[str]


@dataclass
class Project:
    name: str
    subtitle: str
    items: list[str]
    tech: list[str]
    url: str | None


@dataclass
class SkillCategory:
    category: str
    items: list[str]


@dataclass
class School:
    degree: str
    institution: str
    location: str
    dates: str
    items: list[str]


@dataclass
class Language:
    name: str
    level: str


@dataclass
class ResumeData:
    contact: ContactInfo = field(default_factory=ContactInfo)
    summary: str = ""
    positions: list[Position] = field(default_factory=list)
    internships: list[Position] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    skills: list[SkillCategory] = field(default_factory=list)
    schools: list[School] = field(default_factory=list)
    languages: list[Language] = field(default_factory=list)

    def all_positions(self) -> list[Position]:
        return self.positions + self.internships

    def all_text(self) -> str:
        parts = [self.summary]
        for pos in self.all_positions():
            parts += [pos.title, pos.company] + pos.items
        for proj in self.projects:
            parts += [proj.name, proj.subtitle] + proj.items + proj.tech
        for sc in self.skills:
            parts += [sc.category] + sc.items
        for school in self.schools:
            parts += [school.degree, school.institution] + school.items
        return " ".join(parts)


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        warnings.warn(f"Skipping {path}: {e}")
        return {}


def _parse_contact(tex_path: Path) -> ContactInfo:
    if not tex_path.exists():
        return ContactInfo()
    tex = tex_path.read_text(encoding="utf-8")
    m = re.search(r"\\name\{([^}]*)\}\{([^}]*)\}", tex)
    return ContactInfo(
        first_name=m.group(1).strip() if m else "",
        last_name=m.group(2).strip() if m else "",
        position=_tex_macro(tex, "position"),
        address=_tex_macro(tex, "address"),
        mobile=_tex_macro(tex, "mobile"),
        email=_tex_macro(tex, "email"),
        github=_tex_macro(tex, "github"),
        linkedin=_tex_macro(tex, "linkedin"),
        homepage=_tex_macro(tex, "homepage"),
    )


def _parse_position(raw: dict) -> Position:
    return Position(
        title=_strip_bold(raw.get("title", "")),
        company=_strip_bold(raw.get("company", "")),
        location=_strip_bold(raw.get("location", "")),
        dates=str(raw.get("dates", "")),
        items=[_strip_bold(i) for i in raw.get("items", [])],
    )


def load(repo_root: Path | None = None) -> ResumeData:
    data_dir = (repo_root or REPO_ROOT) / "source"
    tex_path = (repo_root or REPO_ROOT) / "core" / "resume.tex"

    resume = ResumeData(contact=_parse_contact(tex_path))

    summary_data = _load_yaml(data_dir / "00-summary.yml")
    resume.summary = _strip_bold(summary_data.get("summary", ""))

    exp_data = _load_yaml(data_dir / "10-experience.yml")
    resume.positions = [_parse_position(p) for p in exp_data.get("positions", [])]
    resume.internships = [_parse_position(p) for p in exp_data.get("internships", [])]

    proj_data = _load_yaml(data_dir / "20-projects.yml")
    resume.projects = [
        Project(
            name=_strip_bold(p.get("name", "")),
            subtitle=_strip_bold(p.get("subtitle", "")),
            items=[_strip_bold(i) for i in p.get("items", [])],
            tech=[str(t) for t in p.get("tech", [])],
            url=p.get("url"),
        )
        for p in proj_data.get("projects", [])
    ]

    skills_data = _load_yaml(data_dir / "30-skills.yml")
    resume.skills = [
        SkillCategory(
            category=str(s.get("category", "")),
            items=[str(i) for i in s.get("items", [])],
        )
        for s in skills_data.get("skills", [])
    ]

    edu_data = _load_yaml(data_dir / "40-education.yml")
    resume.schools = [
        School(
            degree=_strip_bold(s.get("degree", "")),
            institution=_strip_bold(s.get("institution", "")),
            location=_strip_bold(s.get("location", "")),
            dates=str(s.get("dates", "")),
            items=[_strip_bold(i) for i in s.get("items", [])],
        )
        for s in edu_data.get("schools", [])
    ]

    lang_data = _load_yaml(data_dir / "50-languages.yml")
    resume.languages = [
        Language(name=str(lg.get("name", "")), level=str(lg.get("level", "")))
        for lg in lang_data.get("languages", [])
    ]

    if not resume.contact.full_name:
        raise ValueError(
            f"Could not parse a name from {tex_path} — check the \\name macro"
        )
    return resume
