#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .loader import ResumeData, Position
from .date_parser import compute_years_experience
from . import ontology as ont
from . import config as _cfg

_KEYWORDS_PATH = Path(__file__).parent / "data" / "keywords.json"
_KW = json.loads(_KEYWORDS_PATH.read_text(encoding="utf-8"))

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

_JC = _cfg.get()["jd_match"]
_W_KEYWORD         = _JC["weights"]["keyword"]
_W_TITLE           = _JC["weights"]["title"]
_W_EXP             = _JC["weights"]["experience"]
_W_EDU             = _JC["weights"]["education"]
_EXP_IDEAL         = _JC["experience_years"]["ideal"]
_EXP_GOOD          = _JC["experience_years"]["good"]
_EXP_OK            = _JC["experience_years"]["ok"]
_EXP_PARTIAL       = _JC["experience_years"]["partial"]
_KW_SCORE_DIRECT   = _JC["keyword_scores"]["direct"]
_KW_SCORE_ONTOLOGY = _JC["keyword_scores"]["ontology"]
_KW_SCORE_FUZZY    = _JC["keyword_scores"]["fuzzy"]
_FUZZY_MIN_RATIO   = _JC["fuzzy_min_ratio"]
_PASS_THRESHOLD    = _JC["pass_threshold"]
_MAX_REWRITES      = _JC["max_rewrites"]

_GENERIC_TERMS: set[str] = set(_KW["generic_terms"])
_SENIORITY: set[str] = set(_KW["seniority"])
_HR_WORD_BLOCKLIST: set[str] = set(_KW["hr_word_blocklist"])
_ROLE_EQUIV: dict[str, str] = _KW["role_equiv"]
_NOISE_SECTION_RE = re.compile(
    r"^(" + "|".join(_KW["noise_section_patterns"]) + r")",
    re.IGNORECASE,
)


def _strip_nontechnical_sections(text: str) -> str:
    """Remove HR/benefits/culture paragraphs from JD before keyword extraction."""
    blocks = re.split(r"\n{2,}", text)
    kept = []
    for block in blocks:
        heading = block.strip().split("\n")[0].strip()
        if _NOISE_SECTION_RE.match(heading):
            continue
        kept.append(block)
    return "\n\n".join(kept)


@dataclass
class KeywordMatch:
    keyword: str
    found_in: list[str]
    matched_via: str  # "direct" | "ontology" | "fuzzy"
    score: float


@dataclass
class BulletRewrite:
    keyword: str    # the missing keyword this rewrite incorporates
    role: str       # "Job Title at Company"
    original: str   # original bullet text
    rewritten: str  # suggested humanlike rewrite


@dataclass
class EduGap:
    resume_level: str       # e.g. "BSc"
    resume_field: str       # e.g. "Computer Science"
    jd_required: str        # e.g. "Master"
    jd_required_level: float
    resume_level_score: float
    cs_bonus: float
    matched: bool           # True if resume meets or exceeds JD requirement


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
    edu_gap: EduGap | None = None
    author_name: str = ""
    mode: str = "jd"
    suggestions: list[str] = field(default_factory=list)
    role_fit: str = ""
    backend: str = "spacy"  # "spacy" | "llm"
    keyword_density: dict[str, int] = field(default_factory=dict)  # section → hit count
    bullet_rewrites: list[BulletRewrite] = field(default_factory=list)


def _load_spacy():
    if not _HAS_SPACY:
        raise RuntimeError("spaCy not installed — run: make ats-deps")
    try:
        return spacy.load("en_core_web_sm")
    except OSError as e:
        raise RuntimeError("spaCy model 'en_core_web_sm' not found — run: make ats-deps") from e


_TITLE_WORDS: set[str] = set(_KW["title_words"])
_TECH_PATTERN = re.compile(
    r"\b(?:" + "|".join(_KW["tech_patterns"]) + r")\b",
    re.IGNORECASE,
)


def _extract_jd_title(text: str) -> str:
    """Best-effort extraction of job title from first lines of JD."""
    title_words = _TITLE_WORDS
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


def _collect_noun_chunks(doc, known_tech: dict, add) -> None:
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
            add(text)


def _collect_tokens(doc, known_tech: dict, add) -> None:
    for token in doc:
        if token.pos_ in ("PROPN", "NOUN") and len(token.text) > 2:
            n = ont.normalize(token.text)
            if n in _GENERIC_TERMS or not token.is_alpha:
                continue
            if token.text[0].isupper() or n in known_tech:
                add(token.text)


def _extract_jd_keywords(doc, ontology: dict) -> list[str]:
    """Extract technical keywords from a spaCy-processed JD document."""
    implies_keys = set(ontology.get("implies", {}).keys())
    alias_vals = set(ontology.get("aliases", {}).values())
    known_tech: dict[str, str] = {ont.normalize(k): k for k in implies_keys | alias_vals}

    seen_norms: set[str] = set()
    keywords: list[str] = []

    def _add(text: str) -> None:
        text = " ".join(text.split())  # collapse whitespace incl. newlines
        if not text:
            return
        n = ont.normalize(text)
        if n in seen_norms or len(n) <= 2 or n in _GENERIC_TERMS:
            return
        words_lower = [w.lower().rstrip("s") for w in n.split()]
        if len(words_lower) > 1 and any(w in _HR_WORD_BLOCKLIST for w in words_lower):
            return
        seen_norms.add(n)
        keywords.append(text)

    for ent in doc.ents:
        if ent.label_ in ("ORG", "PRODUCT", "LANGUAGE", "GPE"):
            _add(ent.text.strip())

    _collect_noun_chunks(doc, known_tech, _add)
    _collect_tokens(doc, known_tech, _add)

    for m in _TECH_PATTERN.finditer(doc.text):
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

    # Direct match (whole-word to prevent e.g. "java" matching "javascript")
    for section, text in section_texts.items():
        if re.search(rf"\b{re.escape(kw_norm)}\b", ont.normalize(text)):
            found_in.append(section)
    if found_in:
        return _KW_SCORE_DIRECT, found_in, "direct"

    # Ontology expansion match
    if kw_norm in expanded_norms:
        return _KW_SCORE_ONTOLOGY, ["skills"], "ontology"

    # Fuzzy match against individual skill items (rapidfuzz)
    if _HAS_RAPIDFUZZ:
        for item in skill_items:
            if _fuzz.ratio(kw_norm, ont.normalize(item)) >= _FUZZY_MIN_RATIO:
                return _KW_SCORE_FUZZY, ["skills"], "fuzzy"

    return 0.0, [], "none"


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
        if years >= _EXP_IDEAL:
            score = 100.0
        elif years >= _EXP_GOOD:
            score = 90.0
        elif years >= _EXP_OK:
            score = 70.0
        elif years >= _EXP_PARTIAL:
            score = 40.0
        else:
            score = 10.0

    return score, years


def _education_score(resume: ResumeData, jd_text: str, ontology: dict) -> tuple[float, EduGap | None]:
    edu_levels: dict[str, float] = ontology.get("education_levels", {})
    if not resume.schools:
        return 30.0, None

    highest = 0.0
    highest_kw = ""
    all_edu_text = " ".join(f"{s.degree} {s.institution}".lower() for s in resume.schools)
    for keyword, level in edu_levels.items():
        if keyword in all_edu_text and float(level) > highest:
            highest = float(level)
            highest_kw = keyword
    if highest == 0.0:
        highest = 60.0
        highest_kw = "bachelor"  # assumed

    cs_terms = {"computer science", "software engineering", "information technology", "computing"}
    cs_match = next((t for t in cs_terms if t in all_edu_text), None)
    cs_bonus = 10.0 if cs_match else 0.0

    jd_lower = jd_text.lower()
    jd_req = 0.0
    jd_req_kw = ""
    jd_preferred = 0.0  # highest level when JD offers alternatives via "or"
    jd_is_flexible = False  # True when JD accepts a range (e.g. "Bachelor or Master")

    # Collect all edu keywords found in the JD with their positions
    jd_found: list[tuple[str, float, int]] = []  # (keyword, level, pos)
    for keyword, level in edu_levels.items():
        pos = jd_lower.find(keyword)
        if pos != -1:
            jd_found.append((keyword, float(level), pos))

    if jd_found:
        # Check if multiple degree keywords appear within ~120 chars of each other
        # with "or" between them — indicating flexible requirements
        jd_found.sort(key=lambda x: x[2])  # sort by position
        if len(jd_found) >= 2:
            for i in range(len(jd_found) - 1):
                kw_a, lvl_a, pos_a = jd_found[i]
                kw_b, lvl_b, pos_b = jd_found[i + 1]
                span = jd_lower[pos_a: pos_b + len(kw_b)]
                if "or" in span and (pos_b - pos_a) <= 120:
                    jd_is_flexible = True
                    jd_req = min(lvl_a, lvl_b)
                    jd_preferred = max(lvl_a, lvl_b)
                    jd_req_kw = kw_a if lvl_a < lvl_b else kw_b
                    break

        if not jd_is_flexible:
            # No "or" alternative — take the highest mentioned as strict requirement
            for keyword, level, _ in jd_found:
                if level > jd_req:
                    jd_req = level
                    jd_req_kw = keyword

    resume_field = cs_match or ""
    resume_degree = resume.schools[0].degree if resume.schools else ""

    if jd_req > 0:
        if highest >= jd_req:
            if jd_is_flexible and jd_preferred > jd_req and highest < jd_preferred:
                # Meets the minimum of a flexible "X or Y" requirement but not the preferred higher degree
                # Penalty proportional to the gap between min and preferred on the degree ladder
                ladder_gap = jd_preferred - jd_req
                light_penalty = min(12.0, round(ladder_gap * 0.3, 1))
                score = min(100.0, 100.0 - light_penalty + cs_bonus)
            else:
                # Exactly meets or exceeds the requirement
                score = min(100.0, 100.0 + cs_bonus)
            gap = EduGap(resume_level=highest_kw, resume_field=resume_field,
                         jd_required=jd_req_kw, jd_required_level=jd_req,
                         resume_level_score=highest, cs_bonus=cs_bonus, matched=True)
        else:
            # Does not meet the stated requirement — heavy penalty proportional to how far below
            degree_gap = jd_req - highest
            if degree_gap <= 30:
                # One step below (e.g. BSc vs Masters-only JD)
                score = min(100.0, 50.0 + cs_bonus)
            else:
                # Two or more steps below (e.g. BSc vs PhD-only JD)
                score = min(100.0, 25.0 + cs_bonus)
            gap = EduGap(resume_level=highest_kw, resume_field=resume_field,
                         jd_required=jd_req_kw, jd_required_level=jd_req,
                         resume_level_score=highest, cs_bonus=cs_bonus, matched=False)
        return score, gap

    return min(100.0, highest + cs_bonus), None


def run(
    resume: ResumeData,
    jd_text: str,
    threshold: float = _PASS_THRESHOLD,
    use_groq: bool = False,  # kept for call-site compat; prefer use_llm
    use_llm: bool = False,
) -> JDResult:
    if not jd_text or not jd_text.strip():
        raise ValueError("jd_text must not be empty")

    if use_llm or use_groq:
        return _run_llm(resume, jd_text, threshold)
    return _run_spacy(resume, jd_text, threshold)


# ── ANSI helpers for inline step output ─────────────────────────────────────
_CYAN  = "\033[0;36m"
_GREEN = "\033[0;32m"
_GRAY  = "\033[0;37m"
_BOLD  = "\033[1m"
_NC    = "\033[0m"
_STEP_W = 56  # fixed width for the label column


def _step(n: int, total: int, label: str) -> None:
    prefix = f"  {_CYAN}[{n}/{total}]{_NC} {label}"
    plain_len = 2 + len(f"[{n}/{total}]") + 1 + len(label)
    pad = max(1, _STEP_W - plain_len)
    print(f"{prefix}{' ' * pad}", end="", flush=True)


def _done(note: str = "") -> None:
    note_str = f"  {_GRAY}{note}{_NC}" if note else ""
    print(f"{_GREEN}✓{_NC}{note_str}")


def _compute_density(matched: list[KeywordMatch]) -> dict[str, int]:
    """Count how many matched keywords appear in each resume section."""
    density: Counter[str] = Counter()
    for km in matched:
        for section in km.found_in:
            density[section] += 1
    return dict(density)


def _run_spacy(resume: ResumeData, jd_text: str, threshold: float) -> JDResult:
    print()
    _step(1, 4, "Parsing job description…")
    ontology = ont.load_ontology()
    jd_title = _extract_jd_title(jd_text)
    cleaned_jd = _strip_nontechnical_sections(jd_text)
    _done(f"title: {jd_title!r}" if jd_title else "")

    _step(2, 4, "Extracting keywords via NLP…")
    nlp = _load_spacy()
    doc = nlp(cleaned_jd)
    jd_keywords = _extract_jd_keywords(doc, ontology)
    _done(f"{len(jd_keywords)} keywords identified")

    _step(3, 4, "Matching resume against keywords…")
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
    _done(f"{len(matched)} matched · {len(missing)} missing")

    _step(4, 4, "Computing weighted scores…")
    keyword_score = (total_weighted / len(jd_keywords)) * 100.0 if jd_keywords else 0.0
    title_score = _title_score(jd_title, resume.positions)
    exp_score, years_detected = _experience_score(resume, jd_text)
    edu_score, edu_gap = _education_score(resume, jd_text, ontology)
    overall = (
        keyword_score * _W_KEYWORD
        + title_score * _W_TITLE
        + exp_score * _W_EXP
        + edu_score * _W_EDU
    )
    _done()
    print()

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
        edu_gap=edu_gap,
        author_name=resume.contact.full_name,
        backend="spacy",
        keyword_density=_compute_density(matched),
    )


# Map LLM match types → score values and renderer "matched_via" labels.
_LLM_SCORE_MAP = {
    "direct":   _KW_SCORE_DIRECT,
    "semantic": _KW_SCORE_ONTOLOGY,
    "implied":  _KW_SCORE_FUZZY,
}
_LLM_VIA_MAP = {
    "direct":   "direct",
    "semantic": "ontology",
    "implied":  "fuzzy",
}


def _run_llm(resume: ResumeData, jd_text: str, threshold: float) -> JDResult:
    from . import llm_analyzer

    print()
    _step(1, 5, "Parsing job description…")
    ontology = ont.load_ontology()
    jd_title = _extract_jd_title(jd_text)
    _done(f"title: {jd_title!r}" if jd_title else "")

    _step(2, 5, "Extracting keywords via LLM…")
    jd_keywords = llm_analyzer.extract_jd_keywords(jd_text)
    _done(f"{len(jd_keywords)} keywords identified")

    _step(3, 5, "Semantic resume matching via LLM…")
    analysis = llm_analyzer.analyze_resume_match(resume, jd_text, jd_keywords)
    _done(f"{len(analysis.matched)} matched · {len(analysis.missing)} missing")

    _step(4, 5, "Generating bullet rewrites…")
    raw_rewrites = llm_analyzer.generate_bullet_rewrites(
        resume, analysis.missing, jd_text, max_rewrites=_MAX_REWRITES
    )
    bullet_rewrites = [
        BulletRewrite(
            keyword=r.get("keyword", ""),
            role=r.get("role", ""),
            original=r.get("original", ""),
            rewritten=r.get("rewritten", ""),
        )
        for r in raw_rewrites
    ]
    _done(f"{len(bullet_rewrites)} rewrite(s)")

    _step(5, 5, "Computing weighted scores…")
    matched: list[KeywordMatch] = []
    total_weighted = 0.0
    for lm in analysis.matched:
        via   = _LLM_VIA_MAP.get(lm.match_type, "direct")
        score = _LLM_SCORE_MAP.get(lm.match_type, _KW_SCORE_DIRECT)
        matched.append(KeywordMatch(keyword=lm.keyword, found_in=lm.found_in, matched_via=via, score=score))
        total_weighted += score

    all_kw_count  = len(jd_keywords)
    keyword_score = (total_weighted / all_kw_count) * 100.0 if all_kw_count else 0.0
    title_score   = _title_score(jd_title, resume.positions)
    exp_score, years_detected = _experience_score(resume, jd_text)
    edu_score, edu_gap        = _education_score(resume, jd_text, ontology)
    overall = (
        keyword_score * _W_KEYWORD
        + title_score * _W_TITLE
        + exp_score   * _W_EXP
        + edu_score   * _W_EDU
    )
    _done()
    print()

    return JDResult(
        overall_score=round(overall, 1),
        keyword_score=round(keyword_score, 1),
        title_score=round(title_score, 1),
        exp_score=round(exp_score, 1),
        edu_score=round(edu_score, 1),
        matched_keywords=matched,
        missing_keywords=analysis.missing,
        jd_keyword_count=all_kw_count,
        jd_title=jd_title,
        years_detected=years_detected,
        passed=overall >= threshold,
        threshold=threshold,
        edu_gap=edu_gap,
        author_name=resume.contact.full_name,
        suggestions=analysis.suggestions,
        role_fit=analysis.role_fit,
        backend="llm",
        keyword_density=_compute_density(matched),
        bullet_rewrites=bullet_rewrites,
    )
