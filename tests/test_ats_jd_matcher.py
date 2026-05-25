"""Tests for ats/jd_matcher.py — job description matching."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Smoke / shape tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("jd_fixture", [
    "jd_staff_fullstack",
    "jd_senior_backend",
    "jd_frontend_react",
    "jd_devops_cloud",
    "jd_ai_fullstack",
])
def test_jd_matcher_returns_valid_shape(request, resume_data, jd_fixture):
    """run() must return a JDResult with all sub-scores in [0, 100]."""
    from ats.jd_matcher import run
    jd = request.getfixturevalue(jd_fixture)
    result = run(resume_data, jd)

    assert 0.0 <= result.overall_score <= 100.0, f"{jd_fixture}: overall out of range"
    assert 0.0 <= result.keyword_score <= 100.0, f"{jd_fixture}: keyword_score out of range"
    assert 0.0 <= result.title_score <= 100.0, f"{jd_fixture}: title_score out of range"
    assert 0.0 <= result.exp_score <= 100.0, f"{jd_fixture}: exp_score out of range"
    assert 0.0 <= result.edu_score <= 100.0, f"{jd_fixture}: edu_score out of range"


def test_jd_matcher_produces_keywords(resume_data, jd_staff_fullstack):
    """Matcher must extract at least 5 keywords from a real JD."""
    from ats.jd_matcher import run
    result = run(resume_data, jd_staff_fullstack)
    total = len(result.matched_keywords) + len(result.missing_keywords)
    assert total >= 5, f"Only {total} keywords extracted — JD parsing may be broken"


def test_jd_matcher_matched_plus_missing_equals_total(resume_data, jd_senior_backend):
    """matched + missing must equal jd_keyword_count."""
    from ats.jd_matcher import run
    result = run(resume_data, jd_senior_backend)
    assert (
        len(result.matched_keywords) + len(result.missing_keywords)
        == result.jd_keyword_count
    )


def test_jd_matcher_passed_field_consistency(resume_data, jd_frontend_react):
    """JDResult.passed must agree with overall_score vs threshold."""
    from ats.jd_matcher import run
    result = run(resume_data, jd_frontend_react, threshold=70.0)
    if result.overall_score >= 70.0:
        assert result.passed
    else:
        assert not result.passed


# ---------------------------------------------------------------------------
# Score sanity: the user's resume should match *something* on strong-fit JDs
# ---------------------------------------------------------------------------

def test_fullstack_jd_keyword_score_nonzero(resume_data, jd_staff_fullstack):
    """A TypeScript full-stack JD should have >0 keyword score for this resume."""
    from ats.jd_matcher import run
    result = run(resume_data, jd_staff_fullstack)
    assert result.keyword_score > 0.0, "keyword_score is 0 on a matching JD — parsing broken"


def test_ai_jd_keyword_score_nonzero(resume_data, jd_ai_fullstack):
    """An AI/LLM JD should match this resume's AI skills section."""
    from ats.jd_matcher import run
    result = run(resume_data, jd_ai_fullstack)
    assert result.keyword_score > 0.0


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def test_loader_produces_nonempty_resume(resume_data):
    """Loader must populate positions, skills, and contact info."""
    assert resume_data.positions, "No positions loaded"
    assert resume_data.skills, "No skills loaded"
    assert resume_data.contact.full_name, "No name loaded"


def test_loader_summary_nonempty(resume_data):
    """Summary field must be non-empty."""
    assert resume_data.summary.strip(), "Summary is empty"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_jd_matcher_raises_on_empty_jd(resume_data):
    """run() must raise ValueError on an empty JD string."""
    from ats.jd_matcher import run
    with pytest.raises(ValueError):
        run(resume_data, "")


def test_jd_matcher_raises_on_whitespace_jd(resume_data):
    """run() must raise ValueError on an all-whitespace JD."""
    from ats.jd_matcher import run
    with pytest.raises(ValueError):
        run(resume_data, "   \n\t  ")
