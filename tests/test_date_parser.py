from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from ats.date_parser import compute_years_experience, parse_date_range


def test_full_month_range():
    dr = parse_date_range("January 2020 - March 2022")
    assert dr.parseable
    assert dr.start == date(2020, 1, 1)
    assert dr.end == date(2022, 3, 1)


def test_present_end_is_none():
    dr = parse_date_range("June 2019 - Present")
    assert dr.parseable
    assert dr.start == date(2019, 6, 1)
    assert dr.end is None


def test_abbreviated_months_and_en_dash():
    dr = parse_date_range("Jan 2020 – Dec 2021")
    assert dr.parseable
    assert dr.start == date(2020, 1, 1)
    assert dr.end == date(2021, 12, 1)


def test_year_only_range():
    dr = parse_date_range("2018 - 2020")
    assert dr.parseable
    assert dr.start == date(2018, 1, 1)
    assert dr.end == date(2020, 1, 1)


def test_unparseable_returns_flag():
    for raw in ("Summer 2020", "ongoing", "Jan 2020", ""):
        assert not parse_date_range(raw).parseable


def test_years_experience_merges_overlaps():
    positions = [
        SimpleNamespace(dates="January 2018 - January 2020"),
        SimpleNamespace(dates="January 2019 - January 2021"),  # overlaps the first
    ]
    # Union is 2018-01 → 2021-01 = 3 years, not 2 + 2 = 4.
    assert compute_years_experience(positions) == 3.0


def test_years_experience_sums_disjoint_spans():
    positions = [
        SimpleNamespace(dates="January 2015 - January 2016"),
        SimpleNamespace(dates="January 2018 - January 2019"),
    ]
    assert compute_years_experience(positions) == 2.0


def test_years_experience_skips_unparseable(recwarn):
    positions = [
        SimpleNamespace(dates="not a date"),
        SimpleNamespace(dates="January 2020 - January 2021"),
    ]
    assert compute_years_experience(positions) == 1.0
