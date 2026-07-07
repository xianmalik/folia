"""Smoke tests: every result shape must render without raising."""
from __future__ import annotations

from ats import health, renderer
from ats.jd_matcher import BulletRewrite, EduGap, JDResult, KeywordMatch


def _jd_result(**overrides) -> JDResult:
    base = dict(
        overall_score=72.5,
        keyword_score=65.0,
        title_score=90.0,
        exp_score=80.0,
        edu_score=70.0,
        matched_keywords=[
            KeywordMatch("React", ["skills", "experience"], "direct", 1.0),
            KeywordMatch("CI/CD", ["skills"], "ontology", 0.8),
        ],
        missing_keywords=["Kubernetes", "Terraform"],
        jd_keyword_count=10,
        jd_title="Senior Software Engineer",
        years_detected=6.2,
        passed=True,
        threshold=70.0,
        author_name="Ada Lovelace",
        author_email="ada@example.com",
        keyword_density={"skills": 2, "experience": 1},
    )
    base.update(overrides)
    return JDResult(**base)


def test_render_jd_spacy_backend(capsys):
    renderer.render(_jd_result(backend="spacy"), no_color=True)
    out = capsys.readouterr().out
    assert "Overall ATS Score" in out
    assert "Kubernetes" in out


def test_render_jd_llm_backend_with_extras(capsys):
    result = _jd_result(
        backend="llm",
        role_fit="Strong fit for the role.",
        suggestions=["Add Kubernetes to skills"],
        bullet_rewrites=[
            BulletRewrite(
                keyword="Kubernetes",
                role="Engineer at Acme",
                original="Deployed services to production",
                rewritten="Deployed services to production Kubernetes clusters",
            )
        ],
        edu_gap=EduGap("bsc", "computer science", "master", 85.0, 60.0, 10.0, False),
    )
    renderer.render(result, no_color=True)
    out = capsys.readouterr().out
    assert "Role Fit Assessment" in out
    assert "Bullet Rewrite Suggestions" in out


def test_render_jd_failed_result(capsys):
    renderer.render(_jd_result(passed=False, overall_score=42.0), no_color=True)
    out = capsys.readouterr().out
    assert "FAIL" in out


def test_render_jd_header(capsys):
    renderer.render_jd_header("Ada Lovelace", "ada@example.com", no_color=True)
    out = capsys.readouterr().out
    assert "Ada Lovelace" in out
    assert "ada@example.com" in out


def test_render_health(sample_resume, capsys):
    result = health.run(sample_resume)
    renderer.render(result, no_color=True)
    out = capsys.readouterr().out
    assert "Overall CV Score" in out
    assert 0 < result.total_score <= 100


def test_health_scores_within_bounds(sample_resume):
    result = health.run(sample_resume)
    for chk in result.checks:
        assert 0 <= chk.score <= chk.max_score


def test_grade_boundaries():
    assert renderer._grade(95.0)[0] == "A+"
    assert renderer._grade(82.0)[0] == "A"
    assert renderer._grade(72.2)[0] == "B+"
    assert renderer._grade(55.0)[0] == "C"
    assert renderer._grade(10.0)[0] == "F"


def test_render_jd_shows_grade_and_contributions(capsys):
    renderer.render(_jd_result(), no_color=True)
    out = capsys.readouterr().out
    assert "[B+]" in out          # 72.5 overall
    assert "× 40%" in out         # keyword weight contribution
    assert "pts" in out


def test_missing_keywords_grouped_by_importance(capsys):
    result = _jd_result(
        missing_keywords=["Kubernetes", "Terraform"],
        keyword_weights={"Kubernetes": 1.56, "Terraform": 0.6},
    )
    renderer.render(result, no_color=True)
    out = capsys.readouterr().out
    assert "Critical (1)" in out
    assert "Other (1)" in out


def test_top_fixes_rendered_for_weak_keyword_score(capsys):
    result = _jd_result(keyword_score=35.0, missing_keywords=["Kubernetes", "Terraform"])
    renderer.render(result, no_color=True)
    out = capsys.readouterr().out
    assert "Top Fixes" in out
    assert "Kubernetes" in out
