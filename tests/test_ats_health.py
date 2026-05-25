"""Tests for ats/health.py — standalone CV health scoring."""
from __future__ import annotations


def test_health_passes_on_current_resume(resume_data):
    """Current resume should clear the default 70-point health threshold."""
    from ats.health import run
    result = run(resume_data)
    assert result.total_score >= 70.0, (
        f"Health score {result.total_score:.1f} is below threshold 70.0. "
        f"Failing checks: {[c.name for c in result.checks if not c.passed]}"
    )


def test_health_returns_six_checks(resume_data):
    """Health check must always return exactly 6 sub-checks."""
    from ats.health import run
    result = run(resume_data)
    assert len(result.checks) == 6


def test_health_scores_in_range(resume_data):
    """Every individual check score must be ≥ 0 and within its max."""
    from ats.health import run
    result = run(resume_data)
    assert 0.0 <= result.total_score <= 100.0
    for check in result.checks:
        assert 0.0 <= check.score <= check.max_score, (
            f"Check '{check.name}' score {check.score} out of range [0, {check.max_score}]"
        )


def test_health_passed_field_matches_threshold(resume_data):
    """HealthResult.passed must agree with total_score vs threshold."""
    from ats.health import run
    result = run(resume_data, threshold=70.0)
    if result.total_score >= 70.0:
        assert result.passed
    else:
        assert not result.passed


def test_health_custom_threshold(resume_data):
    """Very low threshold should always pass; very high should likely fail."""
    from ats.health import run
    assert run(resume_data, threshold=0.0).passed
    assert not run(resume_data, threshold=100.1).passed
