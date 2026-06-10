"""Shared test setup: make the repo root and core/scripts importable."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "core" / "scripts"))

import pytest

from ats.loader import ContactInfo, Position, Project, ResumeData, School, SkillCategory


@pytest.fixture
def sample_resume() -> ResumeData:
    """A small but complete resume for scoring and rendering tests."""
    return ResumeData(
        contact=ContactInfo(
            first_name="Ada",
            last_name="Lovelace",
            position="Software Engineer",
            email="ada@example.com",
            mobile="+8801000000000",
            github="adal",
        ),
        summary=(
            "Senior software engineer with 6+ years of experience building "
            "scalable web applications in TypeScript, React, and Node.js. "
            "Delivered measurable performance improvements across distributed systems."
        ),
        positions=[
            Position(
                title="Senior Software Engineer",
                company="Acme Corp",
                location="Dhaka",
                dates="January 2021 - Present",
                items=[
                    "Built React dashboards serving 50k users, cutting load time by 40%",
                    "Led migration of Node.js services to TypeScript across 12 repos",
                ],
            ),
            Position(
                title="Software Engineer",
                company="Initech",
                location="Dhaka",
                dates="June 2018 - December 2020",
                items=[
                    "Developed REST APIs in Python handling 2M requests/day",
                ],
            ),
        ],
        projects=[
            Project(
                name="folia",
                subtitle="Resume generator",
                items=["Generated LaTeX resumes from YAML"],
                tech=["Python", "LaTeX"],
                url=None,
            ),
        ],
        skills=[
            SkillCategory(category="Languages", items=["TypeScript", "JavaScript", "Python"]),
            SkillCategory(category="Frameworks", items=["React", "Node.js"]),
        ],
        schools=[
            School(
                degree="BSc in Computer Science",
                institution="University of Dhaka",
                location="Dhaka",
                dates="January 2014 - December 2017",
                items=[],
            ),
        ],
    )
