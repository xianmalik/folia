from __future__ import annotations

from ats import health, parseability
from ats.loader import ExtractionStats


def _stats(**overrides) -> ExtractionStats:
    base = dict(
        pages=2,
        chars=4200,
        words=620,
        lines=90,
        images=0,
        replacement_chars=0,
        unlabeled_lines=0,
        median_line_len=58.0,
    )
    base.update(overrides)
    return ExtractionStats(**base)


def test_clean_extraction_scores_full():
    chk = parseability.check(_stats())
    assert chk.score == parseability.MAX_SCORE
    assert "clean extraction" in chk.findings[0]


def test_low_text_yield_flagged():
    chk = parseability.check(_stats(chars=150, words=20))
    assert chk.score < parseability.MAX_SCORE
    assert any("text yield" in f for f in chk.findings)


def test_broken_characters_flagged():
    chk = parseability.check(_stats(replacement_chars=7))
    assert any("broken character" in f for f in chk.findings)


def test_images_flagged():
    chk = parseability.check(_stats(images=3))
    assert any("invisible to ATS parsers" in f for f in chk.findings)


def test_multi_column_heuristic():
    chk = parseability.check(_stats(median_line_len=12.0))
    assert any("multi-column" in f for f in chk.findings)


def test_word_count_window():
    too_long = parseability.check(_stats(words=1400))
    assert any("too long" in f for f in too_long.findings)
    slightly_short = parseability.check(_stats(words=350))
    assert any("slightly short" in f for f in slightly_short.findings)


def test_health_includes_parseability_when_stats_given(sample_resume):
    result = health.run(sample_resume, stats=_stats())
    names = [chk.name for chk in result.checks]
    assert "parseability" in names
    # and stays out when stats are omitted
    result_no_stats = health.run(sample_resume)
    assert "parseability" not in [chk.name for chk in result_no_stats.checks]
