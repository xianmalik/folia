#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .loader import ResumeData
from .date_parser import parse_date_range
from . import config as _cfg

_KW = json.loads((Path(__file__).parent / "data" / "keywords.json").read_text(encoding="utf-8"))
_ACTION_VERBS: set[str] = set(_KW["action_verbs"])
_IMPACT_PHRASES: list[str] = _KW["impact_phrases"]

_C = _cfg.get()["health"]
_MIN_BULLETS_PER_ROLE   = _C["min_bullets_per_role"]
_MIN_BULLET_WORDS       = _C["min_bullet_words"]
_ACTION_VERB_RATIO_GOOD = _C["action_verb_ratio_good"]
_MIN_SKILLS_TOTAL       = _C["min_skills_total"]
_MIN_SKILL_CATEGORIES   = _C["min_skill_categories"]
_MAX_CATEGORY_SHARE     = _C["max_category_share"]
_SUMMARY_WORD_MIN       = _C["summary_word_min"]
_SUMMARY_WORD_MAX       = _C["summary_word_max"]
_MIN_TECH_KEYWORDS      = _C["min_tech_keywords"]
_MIN_IMPACT_PHRASES     = _C["min_impact_phrases"]
_PASS_THRESHOLD         = _C["pass_threshold"]
_QUANT_RATIO_GOOD       = _C["quant_ratio_good"]
_QUANT_RATIO_OK         = _C["quant_ratio_ok"]
_PASSIVE_RATIO_WARN     = _C["passive_ratio_warn"]

# ── Quantification detection ─────────────────────────────────────────────────
# Matches numbers followed by units (%, x, k, ms…), dollar amounts, and N+ forms.
_METRIC_RE = re.compile(
    r"\$[\d,]+(?:\.\d+)?[kmb]?"                         # $10k, $1.5m
    r"|\b\d[\d,]*(?:\.\d+)?\s*(?:"
    r"%|percent|\+|x\b|[kmb]\b"                          # 25%, 5+, 3x, 10k
    r"|ms\b|s\b|min(?:utes?)?\b|hrs?\b|hours?\b"         # time units
    r"|days?\b|weeks?\b|months?\b|years?\b"              # time periods
    r")",
    re.IGNORECASE,
)

# ── Grammar / voice detection ────────────────────────────────────────────────
_PASSIVE_RE = re.compile(
    r"\b(?:was|were|been|being)\s+\w+(?:ed|en)\b"       # was/were + past participle
    r"|\b(?:responsible for|worked on|assisted (?:with|in)"
    r"|helped (?:with|to)|part of|involved in"
    r"|tasked with|contributed to)\b",
    re.IGNORECASE,
)
_PRONOUN_RE = re.compile(r"\b(?:I|me|my|we|our|us)\b")
_WEAK_STARTERS: set[str] = {
    "helped", "assisted", "supported", "worked", "participated",
    "involved", "contributed", "collaborated", "coordinated",
    "liaised", "facilitated", "aided",
}


@dataclass
class CheckResult:
    name: str
    label: str
    score: float
    max_score: float
    findings: list[str] = field(default_factory=list)

    @property
    def ratio(self) -> float:
        return self.score / self.max_score if self.max_score > 0 else 0.0


@dataclass
class HealthResult:
    checks: list[CheckResult]
    total_score: float
    passed: bool
    threshold: float
    mode: str = "health"


def run(resume: ResumeData | None, threshold: float = _PASS_THRESHOLD) -> HealthResult:
    if resume is None:
        raise ValueError("resume must not be None")
    checks = [
        _check_sections(resume),
        _check_contact(resume),
        _check_dates(resume),
        _check_bullets(resume),
        _check_skills(resume),
        _check_summary(resume),
        _check_quantification(resume),
        _check_grammar(resume),
    ]
    raw = sum(c.score for c in checks)
    max_raw = sum(c.max_score for c in checks)
    total = round((raw / max_raw) * 100, 1) if max_raw else 0.0
    return HealthResult(checks=checks, total_score=total, passed=total >= threshold, threshold=threshold)


def _check_sections(resume: ResumeData) -> CheckResult:
    sections = [
        ("Summary", bool(resume.summary.strip())),
        ("Experience", bool(resume.positions)),
        ("Projects", bool(resume.projects)),
        ("Skills", bool(resume.skills)),
        ("Education", bool(resume.schools)),
        ("Languages", bool(resume.languages)),
    ]
    present = sum(1 for _, ok in sections if ok)
    score = round((present / len(sections)) * 20.0, 1)
    missing = [name for name, ok in sections if not ok]
    findings = [f"Missing section: {n}" for n in missing] or [f"All {len(sections)} sections present"]
    return CheckResult("section_completeness", "Section Completeness", score, 20.0, findings)


def _check_contact(resume: ResumeData) -> CheckResult:
    c = resume.contact
    score = 0.0
    findings = []
    if c.full_name:
        score += 4.0
    else:
        findings.append("No name found in resume.tex (\\name macro)")
    if c.email:
        score += 4.0
    else:
        findings.append("No email found in resume.tex (\\email macro)")
    if c.mobile:
        score += 3.0
    else:
        findings.append("No phone number found in resume.tex (\\mobile macro)")
    if any([c.github, c.linkedin, c.homepage]):
        score += 4.0
    else:
        findings.append("No social/web link found (\\github, \\linkedin, or \\homepage)")
    if not findings:
        findings = ["All contact fields present"]
    return CheckResult("contact_completeness", "Contact Info", score, 15.0, findings)


def _check_dates(resume: ResumeData) -> CheckResult:
    entries: list[tuple[str, str]] = []
    for pos in resume.positions + resume.internships:
        entries.append((f"{pos.title} @ {pos.company}", pos.dates))
    for school in resume.schools:
        entries.append((f"{school.degree} @ {school.institution}", school.dates))

    if not entries:
        return CheckResult("date_consistency", "Date Consistency", 0.0, 20.0, ["No date entries found"])

    findings = []
    good = 0
    for label, raw in entries:
        dr = parse_date_range(raw)
        if dr.parseable:
            good += 1
            if dr.end is not None and dr.end < dr.start:
                findings.append(f"End date before start: '{raw}' in {label}")
        else:
            findings.append(f"Unparseable: '{raw}' in {label} — use 'Month YYYY - Month YYYY'")

    score = round((good / len(entries)) * 20.0, 1)
    if not findings:
        findings = [f"All {len(entries)} date ranges parsed successfully"]
    return CheckResult("date_consistency", "Date Consistency", score, 20.0, findings)


def _check_bullets(resume: ResumeData) -> CheckResult:
    positions = resume.positions
    if not positions:
        return CheckResult("bullet_quality", "Bullet Quality", 0.0, 20.0, ["No positions found"])

    all_items = [item for pos in positions for item in pos.items]
    per_role = [len(pos.items) for pos in positions]
    avg_count = sum(per_role) / len(per_role)

    # (a) avg bullets per role → 8 pts
    if avg_count >= _MIN_BULLETS_PER_ROLE:
        count_score = 8.0
    elif avg_count >= 3:
        count_score = 6.0
    elif avg_count >= 2:
        count_score = 4.0
    else:
        count_score = 0.0

    # (b) avg words per bullet → 7 pts
    word_counts = [len(item.split()) for item in all_items] if all_items else [0]
    avg_words = sum(word_counts) / len(word_counts)
    if avg_words >= _MIN_BULLET_WORDS:
        length_score = 7.0
    elif avg_words >= 10:
        length_score = 5.0
    else:
        length_score = 2.0

    # (c) action verb ratio → 5 pts
    def _has_action(item: str) -> bool:
        first = item.strip().split()[0].lower().rstrip(".,;:") if item.strip() else ""
        return first in _ACTION_VERBS

    action_count = sum(1 for item in all_items if _has_action(item))
    action_ratio = action_count / len(all_items) if all_items else 0.0
    if action_ratio >= _ACTION_VERB_RATIO_GOOD:
        verb_score = 5.0
    elif action_ratio >= 0.6:
        verb_score = 3.0
    elif action_ratio >= 0.4:
        verb_score = 1.0
    else:
        verb_score = 0.0

    score = count_score + length_score + verb_score
    findings = []
    if count_score < 8.0:
        findings.append(f"Average {avg_count:.1f} bullets/role (target: ≥{_MIN_BULLETS_PER_ROLE} per role)")
    if length_score < 7.0:
        findings.append(f"Average bullet length {avg_words:.0f} words (target: ≥{_MIN_BULLET_WORDS})")
    if verb_score < 5.0:
        findings.append(f"Action verbs in {action_ratio:.0%} of bullets (target: ≥{_ACTION_VERB_RATIO_GOOD:.0%})")
    if not findings:
        findings = [f"{len(all_items)} bullets across {len(positions)} roles — strong"]
    return CheckResult("bullet_quality", "Bullet Quality", score, 20.0, findings)


def _check_skills(resume: ResumeData) -> CheckResult:
    if not resume.skills:
        return CheckResult("skills_distribution", "Skills Distribution", 0.0, 15.0, ["No skills section found"])

    total_items = sum(len(s.items) for s in resume.skills)
    num_cats = len(resume.skills)
    max_count = max(len(s.items) for s in resume.skills)
    max_frac = max_count / total_items if total_items > 0 else 0.0

    score = 0.0
    findings = []

    if total_items >= _MIN_SKILLS_TOTAL:
        score += 5.0
    else:
        findings.append(f"Total skill count: {total_items} (target: ≥{_MIN_SKILLS_TOTAL})")

    if num_cats >= _MIN_SKILL_CATEGORIES:
        score += 5.0
    else:
        findings.append(f"Skill categories: {num_cats} (target: ≥{_MIN_SKILL_CATEGORIES})")

    if max_frac <= _MAX_CATEGORY_SHARE:
        score += 5.0
    else:
        heavy = max(resume.skills, key=lambda s: len(s.items))
        findings.append(f"'{heavy.category}' dominates at {max_frac:.0%} of all skills (target: ≤{_MAX_CATEGORY_SHARE:.0%})")

    if not findings:
        findings = [f"{total_items} items across {num_cats} categories — excellent coverage"]
    return CheckResult("skills_distribution", "Skills Distribution", score, 15.0, findings)


def _check_summary(resume: ResumeData) -> CheckResult:
    from . import ontology as ont

    summary = resume.summary.strip()
    if not summary:
        return CheckResult("summary_quality", "Summary Quality", 0.0, 10.0, ["Summary section is empty"])

    word_count = len(summary.split())

    # (a) word count → 4 pts
    if _SUMMARY_WORD_MIN <= word_count <= _SUMMARY_WORD_MAX:
        wc_score = 4.0
    elif 20 <= word_count < _SUMMARY_WORD_MIN or _SUMMARY_WORD_MAX < word_count <= 120:
        wc_score = 2.0
    else:
        wc_score = 0.0

    # (b) tech keyword density → 3 pts
    ontology = ont.load_ontology()
    tech_keys = {ont.normalize(k) for k in ontology.get("implies", {})}
    tech_keys.update(ont.normalize(v) for v in ontology.get("aliases", {}).values())

    summary_lower = summary.lower()
    tech_count = sum(1 for k in tech_keys if k and k in summary_lower)
    if tech_count >= _MIN_TECH_KEYWORDS:
        tech_score = 3.0
    elif tech_count >= 3:
        tech_score = 2.0
    elif tech_count >= 1:
        tech_score = 1.0
    else:
        tech_score = 0.0

    # (c) impact phrases → 3 pts
    impact_count = sum(1 for p in _IMPACT_PHRASES if p.lower() in summary_lower)
    if impact_count >= _MIN_IMPACT_PHRASES:
        impact_score = 3.0
    elif impact_count >= 1:
        impact_score = 2.0
    else:
        impact_score = 0.0

    score = wc_score + tech_score + impact_score
    findings = []
    if wc_score < 4.0:
        hint = "too short" if word_count < _SUMMARY_WORD_MIN else "a bit long"
        findings.append(f"Summary {hint} ({word_count} words — target: {_SUMMARY_WORD_MIN}-{_SUMMARY_WORD_MAX})")
    if tech_score < 3.0:
        findings.append(f"Only {tech_count} distinct tech keywords in summary (target: ≥{_MIN_TECH_KEYWORDS})")
    if impact_score < 3.0:
        findings.append(f"Only {impact_count} impact phrases found (target: ≥{_MIN_IMPACT_PHRASES})")
    if not findings:
        findings = [f"{word_count} words · {tech_count} tech keywords · {impact_count} impact phrases"]
    return CheckResult("summary_quality", "Summary Quality", score, 10.0, findings)


def _check_quantification(resume: ResumeData) -> CheckResult:
    all_items = [item for pos in resume.all_positions() for item in pos.items]
    if not all_items:
        return CheckResult("quantification", "Quantification", 0.0, 10.0, ["No bullet points found"])

    quantified = [item for item in all_items if _METRIC_RE.search(item)]
    ratio = len(quantified) / len(all_items)

    if ratio >= _QUANT_RATIO_GOOD:
        score = 10.0
    elif ratio >= _QUANT_RATIO_OK:
        score = 6.0
    else:
        score = round(max(0.0, ratio / _QUANT_RATIO_OK) * 4.0, 1)

    findings = []
    if ratio < _QUANT_RATIO_GOOD:
        findings.append(
            f"{len(quantified)}/{len(all_items)} bullets ({ratio:.0%}) contain measurable metrics "
            f"(target: ≥{_QUANT_RATIO_GOOD:.0%})"
        )
        unquantified = [item for item in all_items if not _METRIC_RE.search(item)][:3]
        for ex in unquantified:
            snippet = ex[:75] + "…" if len(ex) > 75 else ex
            findings.append(f"Add metrics to: \"{snippet}\"")
    else:
        findings = [
            f"{len(quantified)}/{len(all_items)} bullets ({ratio:.0%}) contain measurable metrics"
        ]
    return CheckResult("quantification", "Quantification", score, 10.0, findings)


def _check_grammar(resume: ResumeData) -> CheckResult:
    all_items = [item for pos in resume.all_positions() for item in pos.items]
    if not all_items:
        return CheckResult("grammar_voice", "Grammar & Voice", 0.0, 10.0, ["No bullet points found"])

    findings = []

    # (a) Passive voice / weak phrases → 5 pts
    passive_hits = [item for item in all_items if _PASSIVE_RE.search(item)]
    passive_ratio = len(passive_hits) / len(all_items)
    if passive_ratio <= 0.05:
        passive_score = 5.0
    elif passive_ratio <= _PASSIVE_RATIO_WARN:
        passive_score = 3.0
        findings.append(
            f"{len(passive_hits)} bullet(s) contain passive constructions or weak phrases"
        )
    else:
        passive_score = 0.0
        findings.append(
            f"{len(passive_hits)}/{len(all_items)} bullets ({passive_ratio:.0%}) use passive voice "
            f"(target: ≤{_PASSIVE_RATIO_WARN:.0%})"
        )
        for ex in passive_hits[:2]:
            snippet = ex[:75] + "…" if len(ex) > 75 else ex
            findings.append(f"  Passive: \"{snippet}\"")

    # (b) First-person pronouns → 3 pts
    pronoun_hits = [item for item in all_items if _PRONOUN_RE.search(item)]
    if not pronoun_hits:
        pronoun_score = 3.0
    else:
        pronoun_score = 0.0
        findings.append(
            f"{len(pronoun_hits)} bullet(s) contain first-person pronouns (I, my, we, our)"
        )

    # (c) Weak opening verbs → 2 pts
    def _first_word(s: str) -> str:
        words = s.strip().split()
        return words[0].lower().rstrip(".,;:") if words else ""

    weak_hits = [item for item in all_items if _first_word(item) in _WEAK_STARTERS]
    if not weak_hits:
        weak_score = 2.0
    elif len(weak_hits) <= 2:
        weak_score = 1.0
        findings.append(f"{len(weak_hits)} bullet(s) open with weak verbs (helped, assisted, worked…)")
    else:
        weak_score = 0.0
        findings.append(
            f"{len(weak_hits)} bullet(s) open with weak verbs — replace with strong action verbs"
        )

    score = passive_score + pronoun_score + weak_score
    if not findings:
        findings = [f"All {len(all_items)} bullets use active voice and strong language"]
    return CheckResult("grammar_voice", "Grammar & Voice", score, 10.0, findings)
