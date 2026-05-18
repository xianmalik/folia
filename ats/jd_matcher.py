#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

from .loader import ResumeData, Position
from .date_parser import compute_years_experience
from . import ontology as ont

try:
    import spacy
    _HAS_SPACY = True
except ImportError:
    _HAS_SPACY = False

try:
    from rapidfuzz import fuzz as _fuzz
    _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False

_GENERIC_TERMS = {
    "team", "company", "role", "position", "experience", "skill", "skills", "ability",
    "abilities", "candidate", "employer", "environment", "culture", "opportunity",
    "benefit", "work", "job", "requirement", "requirements", "responsibility",
    "responsibilities", "year", "years", "month", "months", "time", "project", "product",
    "service", "solution", "platform", "system", "application", "app", "tool", "technology",
    "technologies", "software", "engineering", "development", "problem", "challenge", "task",
    "feature", "result", "impact", "knowledge", "understanding", "strong", "good", "excellent",
    "great", "ideal", "preferred", "required", "plus", "bonus", "nice", "proficiency",
    "familiarity", "background", "passion", "focus", "interest", "desire", "ownership",
    "quality", "mindset", "communication", "leadership", "mentorship", "degree", "bachelor",
    "master", "field", "relevant", "modern", "high", "large", "scale", "complex", "fast",
    "paced", "driven", "member", "partner", "startup", "remote", "hybrid", "onsite",
    "fulltime", "part", "contract", "compensation", "salary", "equity", "based", "using",
    "building", "writing", "working", "etc", "ie", "eg",
}

_SENIORITY = {"senior", "sr", "lead", "principal", "staff", "head", "junior", "jr", "associate"}


@dataclass
class KeywordMatch:
    keyword: str
    found_in: list[str]
    matched_via: str  # "direct" | "ontology" | "fuzzy"
    score: float


@dataclass
class JDResult:
    overall_score: float
    keyword_score: float
    title_score: float
    exp_score: float
    edu_score: float
    matched_keywords: list[KeywordMatch]
    missing_keywords: list[str]
    jd_keyword_count: int
    jd_title: str
    years_detected: float
    passed: bool
    threshold: float
    mode: str = "jd"


def _load_spacy():
    if not _HAS_SPACY:
        print(
            "jd_matcher: spaCy not installed — run: make ats-deps",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        return spacy.load("en_core_web_sm")
    except OSError:
        print(
            "jd_matcher: spaCy model not found — run: make ats-deps",
            file=sys.stderr,
        )
        sys.exit(1)


def _extract_jd_title(text: str) -> str:
    """Best-effort extraction of job title from first lines of JD."""
    title_words = {
        "engineer", "developer", "manager", "lead", "architect", "designer",
        "analyst", "scientist", "intern", "head", "director", "specialist",
        "consultant", "staff", "principal", "frontend", "backend", "fullstack",
        "full-stack", "software", "mobile", "data", "devops", "sre", "qa",
    }
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    # First pass: short heading-style lines with a known title word (wider window)
    for line in lines[:30]:
        words = line.split()
        if 1 <= len(words) <= 8 and not line.endswith((".", "?", "!")):
            if any(w.lower().rstrip(",;-") in title_words for w in words):
                return line.strip(":-–—|/\\").strip()

    # Second pass: regex scan for "looking for a/an <title>" or "hiring a/an <title>"
    role_pattern = re.compile(
        r"(?:looking for|hiring|seeking|need(?:ing)?)\s+(?:an?\s+)?([A-Za-z][\w\s\-/]{2,40}?)(?:\s+who|\s+to|\s+with|[,.]|$)",
        re.IGNORECASE,
    )
    for line in lines[:30]:
        m = role_pattern.search(line)
        if m:
            candidate = m.group(1).strip()
            cwords = candidate.split()
            if 1 <= len(cwords) <= 6 and any(w.lower().rstrip("s") in title_words for w in cwords):
                return candidate

    return lines[0][:80] if lines else ""


def _extract_jd_keywords(doc, ontology: dict) -> list[str]:
    """Extract technical keywords from a spaCy-processed JD document."""
    implies_keys = set(ontology.get("implies", {}).keys())
    alias_vals = set(ontology.get("aliases", {}).values())
    known_tech: dict[str, str] = {ont.normalize(k): k for k in implies_keys | alias_vals}

    seen_norms: set[str] = set()
    keywords: list[str] = []

    def _add(text: str) -> None:
        text = " ".join(text.split())  # collapse all whitespace incl. newlines
        if not text:
            return
        n = ont.normalize(text)
        if n in seen_norms or len(n) <= 2 or n in _GENERIC_TERMS:
            return
        seen_norms.add(n)
        keywords.append(text)

    # Named entities (ORG, PRODUCT, LANGUAGE, GPE often contains tech names)
    for ent in doc.ents:
        if ent.label_ in ("ORG", "PRODUCT", "LANGUAGE", "GPE"):
            _add(ent.text.strip())

    # Noun chunks — short ones with at least one uppercase word or known tech term
    for chunk in doc.noun_chunks:
        text = chunk.text.strip()
        words = text.split()
        if not (1 <= len(words) <= 4):
            continue
        n = ont.normalize(text)
        if n in _GENERIC_TERMS:
            continue
        has_cap = any(w[0].isupper() for w in words if w)
        is_known = n in known_tech or any(ont.normalize(w) in known_tech for w in words)
        if has_cap or is_known:
            _add(text)

    # Single PROPN/NOUN tokens — title-cased or known tech
    for token in doc:
        if token.pos_ in ("PROPN", "NOUN") and len(token.text) > 2:
            n = ont.normalize(token.text)
            if n in _GENERIC_TERMS or not token.is_alpha:
                continue
            if token.text[0].isupper() or n in known_tech:
                _add(token.text)

    # Also scan for explicit tech mentioned inline with special chars (e.g. "Node.js", "C++")
    tech_pattern = re.compile(
        r"\b(?:Node\.js|Next\.js|Vue\.js|React\.js|Express\.js|TypeScript|JavaScript"
        r"|PostgreSQL|MongoDB|GraphQL|WebSocket|WebSockets|FastAPI|CI/CD|REST\s?API"
        r"|GitHub\s?Actions|TailwindCSS|Tailwind\s?CSS)\b",
        re.IGNORECASE,
    )
    for m in tech_pattern.finditer(doc.text):
        _add(m.group(0))

    return keywords


def _build_section_texts(resume: ResumeData) -> dict[str, str]:
    return {
        "summary": resume.summary,
        "experience": " ".join(
            f"{p.title} {p.company} {' '.join(p.items)}"
            for p in resume.positions + resume.internships
        ),
        "projects": " ".join(
            f"{p.name} {p.subtitle} {' '.join(p.items)} {' '.join(p.tech)}"
            for p in resume.projects
        ),
        "skills": " ".join(
            f"{s.category} {' '.join(s.items)}" for s in resume.skills
        ),
        "education": " ".join(
            f"{s.degree} {s.institution} {' '.join(s.items)}"
            for s in resume.schools
        ),
    }


def _score_keyword(
    kw: str,
    section_texts: dict[str, str],
    expanded_norms: set[str],
    skill_items: list[str],
) -> tuple[float, list[str], str]:
    kw_norm = ont.normalize(kw)
    found_in: list[str] = []

    # Direct match
    for section, text in section_texts.items():
        if kw_norm in ont.normalize(text):
            found_in.append(section)
    if found_in:
        return 1.0, found_in, "direct"

    # Ontology expansion match
    if kw_norm in expanded_norms:
        return 0.7, ["skills"], "ontology"

    # Fuzzy match against individual skill items (rapidfuzz)
    if _HAS_RAPIDFUZZ:
        for item in skill_items:
            if _fuzz.ratio(kw_norm, ont.normalize(item)) >= 85:
                return 0.4, ["skills"], "fuzzy"

    return 0.0, [], "none"


# Terms treated as equivalent when comparing JD title to resume titles
_ROLE_EQUIV: dict[str, str] = {
    "developer": "engineer",
    "developers": "engineer",
    "programmer": "engineer",
    "programmers": "engineer",
    "coder": "engineer",
    "dev": "engineer",
}


def _normalize_title_tokens(tokens: set[str]) -> set[str]:
    """Map role synonyms to a canonical token so Jaccard can match across terms."""
    return {_ROLE_EQUIV.get(t, t) for t in tokens}


def _title_score(jd_title: str, positions: list[Position]) -> float:
    if not jd_title or not positions:
        return 50.0

    jd_tokens = _normalize_title_tokens(set(ont.normalize(jd_title).split()) - _SENIORITY)
    if not jd_tokens:
        return 50.0

    best = 0.0
    for pos in positions:
        pos_tokens = _normalize_title_tokens(set(ont.normalize(pos.title).split()) - _SENIORITY)
        if not pos_tokens:
            continue
        inter = jd_tokens & pos_tokens
        union = jd_tokens | pos_tokens
        sim = len(inter) / len(union) if union else 0.0
        if sim > best:
            best = sim

    # Seniority match bonus
    jd_full_tokens = set(ont.normalize(jd_title).split())
    resume_titles_concat = " ".join(ont.normalize(p.title) for p in positions)
    resume_tokens = set(resume_titles_concat.split())
    bonus = 10.0 if (jd_full_tokens & _SENIORITY) and (resume_tokens & _SENIORITY) else 0.0

    return min(100.0, best * 100 + bonus)


def _experience_score(resume: ResumeData, jd_text: str) -> tuple[float, float]:
    """Returns (score, years_detected)."""
    years = compute_years_experience(resume.all_positions())
    req_match = re.search(r"(\d+)\+?\s*(?:to\s*\d+\s*)?years?", jd_text.lower())
    req_years = float(req_match.group(1)) if req_match else None

    if req_years and req_years > 0:
        ratio = years / req_years
        if ratio >= 1.0:
            score = 100.0
        elif ratio >= 0.8:
            score = 75.0
        elif ratio >= 0.5:
            score = 50.0
        else:
            score = 25.0
    else:
        if years >= 8:
            score = 100.0
        elif years >= 5:
            score = 90.0
        elif years >= 3:
            score = 70.0
        elif years >= 1:
            score = 40.0
        else:
            score = 10.0

    return score, years


def _education_score(resume: ResumeData, jd_text: str, ontology: dict) -> float:
    edu_levels: dict[str, float] = ontology.get("education_levels", {})
    if not resume.schools:
        return 30.0

    highest = 0.0
    all_edu_text = " ".join(f"{s.degree} {s.institution}".lower() for s in resume.schools)
    for keyword, level in edu_levels.items():
        if keyword in all_edu_text and float(level) > highest:
            highest = float(level)
    if highest == 0.0:
        highest = 60.0  # assume bachelor if not detected

    cs_terms = {"computer science", "software engineering", "information technology", "computing"}
    cs_bonus = 10.0 if any(t in all_edu_text for t in cs_terms) else 0.0

    jd_lower = jd_text.lower()
    jd_req = 0.0
    for keyword, level in edu_levels.items():
        if keyword in jd_lower and float(level) > jd_req:
            jd_req = float(level)

    if jd_req > 0:
        if highest >= jd_req:
            return min(100.0, 100.0 + cs_bonus)
        elif highest >= jd_req - 30:
            return min(100.0, 65.0 + cs_bonus)
        else:
            return min(100.0, 30.0 + cs_bonus)

    return min(100.0, highest + cs_bonus)


def run(resume: ResumeData, jd_text: str, threshold: float = 70.0) -> JDResult:
    nlp = _load_spacy()
    ontology = ont.load_ontology()

    doc = nlp(jd_text)
    jd_title = _extract_jd_title(jd_text)
    jd_keywords = _extract_jd_keywords(doc, ontology)

    section_texts = _build_section_texts(resume)
    skill_items = [item for sc in resume.skills for item in sc.items]
    all_skill_names = skill_items[:]
    for proj in resume.projects:
        all_skill_names.extend(proj.tech)
    expanded = ont.expand_skills(all_skill_names, ontology)
    expanded_norms = {ont.normalize(s) for s in expanded}

    matched: list[KeywordMatch] = []
    missing: list[str] = []
    total_weighted = 0.0

    for kw in jd_keywords:
        score, found_in, via = _score_keyword(kw, section_texts, expanded_norms, skill_items)
        if score > 0:
            matched.append(KeywordMatch(keyword=kw, found_in=found_in, matched_via=via, score=score))
            total_weighted += score
        else:
            missing.append(kw)

    keyword_score = (total_weighted / len(jd_keywords)) * 100.0 if jd_keywords else 0.0
    title_score = _title_score(jd_title, resume.positions)
    exp_score, years_detected = _experience_score(resume, jd_text)
    edu_score = _education_score(resume, jd_text, ontology)

    overall = (
        keyword_score * 0.40
        + title_score * 0.25
        + exp_score * 0.20
        + edu_score * 0.15
    )

    return JDResult(
        overall_score=round(overall, 1),
        keyword_score=round(keyword_score, 1),
        title_score=round(title_score, 1),
        exp_score=round(exp_score, 1),
        edu_score=round(edu_score, 1),
        matched_keywords=matched,
        missing_keywords=missing,
        jd_keyword_count=len(jd_keywords),
        jd_title=jd_title,
        years_detected=years_detected,
        passed=overall >= threshold,
        threshold=threshold,
    )
