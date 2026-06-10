from __future__ import annotations

from ats import jd_matcher as jm
from ats import ontology as ont
from ats.models import Position


# ── title extraction ─────────────────────────────────────────────────────────

def test_extract_title_from_heading():
    jd = "Senior Software Engineer\n\nWe are a fast-growing startup..."
    assert jm._extract_jd_title(jd) == "Senior Software Engineer"


def test_extract_title_from_hiring_sentence():
    jd = "About us\nOur team ships daily.\nWe are looking for a Backend Developer to join us."
    assert "Backend Developer" in jm._extract_jd_title(jd)


# ── keyword scoring ──────────────────────────────────────────────────────────

def _sections(**kwargs) -> dict[str, str]:
    """Normalized section texts, as _score_keyword now receives them."""
    base = {"summary": "", "experience": "", "projects": "", "skills": "", "education": ""}
    base.update(kwargs)
    return {s: ont.normalize(t) for s, t in base.items()}


def test_direct_match_is_whole_word():
    sections = _sections(skills="JavaScript React")
    score, found_in, via = jm._score_keyword("Java", sections, set(), [])
    # "java" must NOT match inside "javascript"
    assert score == 0.0 and via == "none"

    score, found_in, via = jm._score_keyword("JavaScript", sections, set(), [])
    assert via == "direct"
    assert found_in == ["skills"]
    # skills-only direct matches are slightly discounted
    assert score == jm._KW_SCORE_DIRECT * jm._SKILLS_ONLY_FACTOR


def test_direct_match_in_experience_gets_full_score():
    sections = _sections(experience="Built React dashboards", skills="React")
    score, found_in, via = jm._score_keyword("React", sections, set(), [])
    assert via == "direct"
    assert score == jm._KW_SCORE_DIRECT
    assert set(found_in) == {"experience", "skills"}


def test_direct_match_plural_variants():
    sections = _sections(experience="Designed REST APIs for payments")
    score, _, via = jm._score_keyword("REST API", sections, set(), [])
    assert via == "direct"

    sections = _sections(experience="Built a microservice platform")
    score, _, via = jm._score_keyword("microservices", sections, set(), [])
    assert via == "direct"


def test_ontology_match():
    expanded = {ont.normalize("JSX")}
    score, found_in, via = jm._score_keyword("JSX", _sections(), expanded, [])
    assert score == jm._KW_SCORE_ONTOLOGY
    assert via == "ontology"


def test_compound_match():
    sections = _sections(experience="Built services with Node.js", skills="Docker")
    expanded = {ont.normalize("microservices")}
    score, found_in, via = jm._score_keyword(
        "Node.js microservices", sections, expanded, []
    )
    assert via == "compound"
    assert score == jm._KW_SCORE_COMPOUND


def test_compound_requires_all_words():
    sections = _sections(experience="Built services with Node.js")
    score, _, via = jm._score_keyword("Node.js Kafka pipelines", sections, set(), [])
    assert via == "none" and score == 0.0


def test_fuzzy_match_against_skill_items():
    score, found_in, via = jm._score_keyword(
        "PostgreSQL", _sections(), set(), ["Postgres"]
    )
    assert via in ("fuzzy", "none")  # rapidfuzz optional
    if via == "fuzzy":
        assert score == jm._KW_SCORE_FUZZY


# ── noise filtering ──────────────────────────────────────────────────────────

def test_noise_rejects_pronoun_phrases():
    for phrase in ("you", "our mission", "your body", "we ship daily"):
        assert jm._looks_like_noise(ont.normalize(phrase))


def test_noise_rejects_clock_times():
    assert jm._looks_like_noise(ont.normalize("1 PM"))
    assert jm._looks_like_noise(ont.normalize("10 pm bd time"))


def test_noise_keeps_real_tech_terms():
    for phrase in ("kubernetes", "react native", "event driven architecture", "php"):
        assert not jm._looks_like_noise(ont.normalize(phrase))


def test_leading_articles_stripped():
    assert jm._strip_leading_article("a Good Engineer") == "Good Engineer"
    assert jm._strip_leading_article("the platform") == "platform"
    assert jm._strip_leading_article("Angular") == "Angular"  # single word untouched


# ── keyword importance ───────────────────────────────────────────────────────

def test_required_keywords_weigh_more():
    jd = (
        "Requirements\n"
        "Strong TypeScript experience is required.\n"
        "GraphQL is a plus.\n"
    )
    weights = jm._keyword_weights(jd, ["TypeScript", "GraphQL"])
    assert weights["TypeScript"] > 1.0
    assert weights["GraphQL"] < 1.0
    assert weights["TypeScript"] > weights["GraphQL"]


def test_repeated_keywords_weigh_more():
    jd = "We use React. React powers our frontend. Experience with React required."
    weights = jm._keyword_weights(jd, ["React", "Svelte"])
    assert weights["React"] > weights["Svelte"]


def test_jd_block_headings_set_importance():
    jd = (
        "Requirements\n"
        "- TypeScript\n"
        "- PostgreSQL\n"
        "\n"
        "Nice to have\n"
        "- GraphQL\n"
    )
    weights = jm._keyword_weights(jd, ["TypeScript", "GraphQL"])
    assert weights["TypeScript"] > 1.0   # under Requirements heading
    assert weights["GraphQL"] < 1.0      # under Nice to have heading


# ── stemmed matching ─────────────────────────────────────────────────────────

def test_stem_family_verb_noun_forms():
    family = jm._stem_family("manage")
    assert {"managed", "managing", "management"} <= family
    family = jm._stem_family("management")
    assert "managed" in family


def test_stem_family_protects_short_tech_names():
    assert jm._stem_family("go") == set()
    assert jm._stem_family("aws") == set()


def test_stemmed_direct_match():
    sections = _sections(experience="Managed a team of five engineers")
    score, _, via = jm._score_keyword("manage", sections, set(), [])
    assert via == "direct"

    sections = _sections(experience="Mentored juniors through code review")
    score, _, via = jm._score_keyword("mentoring", sections, set(), [])
    assert via == "direct"


# ── recency / staleness ──────────────────────────────────────────────────────

def test_stale_discount_for_old_roles_only(sample_resume):
    # "Python" appears only in the older Initech position, not the current one
    m_old = jm.KeywordMatch("Python", ["experience"], "direct", 1.0)
    m_new = jm.KeywordMatch("React", ["experience"], "direct", 1.0)
    jm._apply_stale_discount([m_old, m_new], sample_resume)
    assert m_old.stale and m_old.score < 1.0
    assert not m_new.stale and m_new.score == 1.0


# ── soft skills ──────────────────────────────────────────────────────────────

def test_soft_skills_scanned_not_scored(sample_resume):
    jd = "We value strong communication and stakeholder management. TypeScript required."
    found = dict(jm._scan_soft_skills(jd, sample_resume))
    assert "communication" in found
    assert "stakeholder management" in found
    # sample resume mentions neither
    assert found["communication"] is False


# ── title scoring ────────────────────────────────────────────────────────────

def test_title_score_exact_role_match():
    positions = [Position("Senior Software Engineer", "Acme", "", "2020 - Present", [])]
    score = jm._title_score("Senior Software Engineer", positions)
    assert score == 100.0


def test_title_score_synonym_normalisation():
    positions = [Position("Software Developer", "Acme", "", "2020 - Present", [])]
    # "engineer" and "developer" normalise to the same canonical token
    score = jm._title_score("Software Engineer", positions)
    assert score == 100.0


def test_title_score_neutral_when_no_title():
    assert jm._title_score("", []) == 50.0


# ── section noise stripping ──────────────────────────────────────────────────

def test_strip_nontechnical_sections():
    jd = "Requirements\nPython, Django\n\nBenefits\nFree lunch and gym membership"
    cleaned = jm._strip_nontechnical_sections(jd)
    assert "Python" in cleaned
    assert "Free lunch" not in cleaned


# ── education scoring ────────────────────────────────────────────────────────

def test_education_meets_requirement(sample_resume):
    ontology = ont.load_ontology()
    jd = "Requirements: Bachelor degree in Computer Science required."
    score, gap = jm._education_score(sample_resume, jd, ontology)
    assert gap is not None and gap.matched
    assert score >= 100.0


def test_education_below_requirement(sample_resume):
    ontology = ont.load_ontology()
    jd = "Requirements: PhD in Computer Science required."
    score, gap = jm._education_score(sample_resume, jd, ontology)
    assert gap is not None and not gap.matched
    assert score < 60.0


def test_education_flexible_or_requirement(sample_resume):
    ontology = ont.load_ontology()
    jd = "A Bachelor or Master degree in a related field."
    score, gap = jm._education_score(sample_resume, jd, ontology)
    assert gap is not None and gap.matched
    # Meets the minimum of a flexible range → small penalty at most
    assert score >= 85.0


def test_education_no_jd_requirement(sample_resume):
    ontology = ont.load_ontology()
    score, gap = jm._education_score(sample_resume, "No degree mentioned here.", ontology)
    assert gap is None
    assert score > 0


# ── experience scoring ───────────────────────────────────────────────────────

def test_experience_meets_explicit_requirement(sample_resume):
    score, years = jm._experience_score(sample_resume, "5+ years of experience required")
    assert years > 5
    assert score == 100.0


def test_experience_far_below_requirement(sample_resume):
    score, _ = jm._experience_score(sample_resume, "20 years of experience required")
    assert score < 100.0


# ── full pipeline ────────────────────────────────────────────────────────────

def test_run_is_pure_and_silent(sample_resume, capsys):
    """run() must not print — progress goes through the callback only."""
    import pytest

    spacy = pytest.importorskip("spacy")
    try:
        spacy.load("en_core_web_sm")
    except OSError:
        pytest.skip("spaCy model en_core_web_sm not installed")

    jd = (
        "Senior Software Engineer\n\n"
        "Requirements\n"
        "5+ years of experience with TypeScript, React, and Node.js.\n"
        "Bachelor degree in Computer Science required.\n"
    )
    result = jm.run(sample_resume, jd, use_llm=False)
    assert capsys.readouterr().out == ""
    assert 0 <= result.overall_score <= 100
    assert result.backend == "spacy"
    assert result.author_email == "ada@example.com"


def test_run_rejects_empty_jd(sample_resume):
    import pytest

    with pytest.raises(ValueError):
        jm.run(sample_resume, "   ")
