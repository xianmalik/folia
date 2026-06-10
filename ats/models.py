"""Resume data model shared by the loader, scorers, and renderer."""
from __future__ import annotations

from dataclasses import dataclass, field


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
