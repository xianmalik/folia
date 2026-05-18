#!/usr/bin/env python3
from __future__ import annotations

import re
from datetime import date
from typing import NamedTuple

MONTHS: dict[str, int] = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class DateRange(NamedTuple):
    start: date
    end: date | None  # None = "Present"
    raw: str
    parseable: bool


def _parse_single(s: str) -> date | None:
    s = s.strip().lower()
    if s in ("present", "current", "now", "ongoing"):
        return date.today()
    m = re.match(r"([a-z]+)\s+(\d{4})$", s)
    if m:
        month = MONTHS.get(m.group(1))
        if month:
            return date(int(m.group(2)), month, 1)
    m = re.match(r"(\d{4})$", s)
    if m:
        return date(int(m.group(1)), 1, 1)
    return None


def parse_date_range(raw: str) -> DateRange:
    parts = re.split(r"\s*[-–—]\s*", raw.strip(), maxsplit=1)
    if len(parts) != 2:
        return DateRange(start=date.today(), end=date.today(), raw=raw, parseable=False)

    start_str, end_str = parts[0].strip(), parts[1].strip()
    start = _parse_single(start_str)
    is_present = end_str.lower() in ("present", "current", "now", "ongoing")
    end = None if is_present else _parse_single(end_str)

    if start is None or (end is None and not is_present):
        return DateRange(start=date.today(), end=date.today(), raw=raw, parseable=False)

    return DateRange(start=start, end=end, raw=raw, parseable=True)


def compute_years_experience(positions: list) -> float:
    """Sum non-overlapping experience years across all positions."""
    today = date.today()
    spans: list[list[date]] = []

    for pos in positions:
        dr = parse_date_range(pos.dates)
        if not dr.parseable:
            continue
        end = dr.end if dr.end is not None else today
        spans.append([dr.start, end])

    if not spans:
        return 0.0

    spans.sort(key=lambda x: x[0])
    merged: list[list[date]] = [spans[0]]
    for start, end in spans[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    total_days = sum((m[1] - m[0]).days for m in merged)
    return round(total_days / 365.25, 1)
