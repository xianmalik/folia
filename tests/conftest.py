"""Shared pytest fixtures for ATS tests."""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = REPO_ROOT / "samples" / "jds"


@pytest.fixture(scope="session")
def resume_data():
    """Load the real resume from data/*.yml — integration-level fixture."""
    from ats.loader import load
    return load(REPO_ROOT)


@pytest.fixture(scope="session")
def ontology():
    """Load the shared ontology once per session."""
    from ats import ontology as ont
    return ont.load_ontology()


def jd_text(name: str) -> str:
    """Helper: read a sample JD by filename stem."""
    return (SAMPLES_DIR / f"{name}.txt").read_text(encoding="utf-8")


# Expose sample JD texts as fixtures so tests can use them by name
@pytest.fixture(scope="session")
def jd_staff_fullstack() -> str:
    return jd_text("staff-fullstack")


@pytest.fixture(scope="session")
def jd_senior_backend() -> str:
    return jd_text("senior-backend")


@pytest.fixture(scope="session")
def jd_frontend_react() -> str:
    return jd_text("frontend-react")


@pytest.fixture(scope="session")
def jd_devops_cloud() -> str:
    return jd_text("devops-cloud")


@pytest.fixture(scope="session")
def jd_ai_fullstack() -> str:
    return jd_text("ai-fullstack")
