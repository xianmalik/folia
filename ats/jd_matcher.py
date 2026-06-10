#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .models import Position, ResumeData
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
_KW_SCORE_COMPOUND = _JC["keyword_scores"]["compound"]
_KW_SCORE_FUZZY    = _JC["keyword_scores"]["fuzzy"]
_SKILLS_ONLY_FACTOR = _JC["skills_only_factor"]
_STALE_FACTOR       = _JC["stale_factor"]
_IMP_REQUIRED_BOOST = _JC["importance"]["required_boost"]
_IMP_NICE_FACTOR    = _JC["importance"]["nice_factor"]
_IMP_FREQ_BONUS     = _JC["importance"]["freq_bonus"]
_IMP_FREQ_CAP       = _JC["importance"]["freq_cap"]
_FUZZY_MIN_RATIO   = _JC["fuzzy_min_ratio"]
_PASS_THRESHOLD    = _JC["pass_threshold"]
_MAX_REWRITES      = _JC["max_rewrites"]

_GENERIC_TERMS: set[str] = set(_KW["generic_terms"])
_SOFT_SKILLS: list[str] = _KW.get("soft_skills", [])
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
    matched_via: str  # "direct" | "ontology" | "compound" | "fuzzy"
    score: float
    weight: float = 1.0  # importance of this keyword in the JD
    stale: bool = False  # matched only in roles older than the current one


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
    author_email: str = ""
    mode: str = "jd"
    suggestions: list[str] = field(default_factory=list)
    role_fit: str = ""
    backend: str = "spacy"  # "spacy" | "llm"
    llm_fallback: bool = False  # True when LLM was attempted but rate-limited
    keyword_density: dict[str, int] = field(default_factory=dict)  # section → hit count
    bullet_rewrites: list[BulletRewrite] = field(default_factory=list)
    keyword_weights: dict[str, float] = field(default_factory=dict)  # JD keyword → importance
    soft_skills: list[tuple[str, bool]] = field(default_factory=list)  # (skill in JD, present in resume)


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


_PRONOUNS = {"you", "your", "yours", "our", "ours", "we", "us", "my", "their", "everyone", "someone"}
_LEADING_ARTICLES = {"a", "an", "the", "this", "that", "these", "those"}
_TIME_RE = re.compile(r"\b\d{1,2}\s*(?:am|pm)\b")


def _strip_leading_article(text: str) -> str:
    words = text.split()
    if len(words) > 1 and words[0].lower() in _LEADING_ARTICLES:
        return " ".join(words[1:])
    return text


def _looks_like_noise(norm: str) -> bool:
    """Reject non-skill phrases: pronoun talk, clock times, generic terms."""
    if not norm or len(norm) <= 2 or norm in _GENERIC_TERMS:
        return True
    words = norm.split()
    if any(w in _PRONOUNS for w in words):
        return True
    if _TIME_RE.search(norm):
        return True
    words_stripped = [w.rstrip("s") for w in words]
    if len(words) > 1 and any(w in _HR_WORD_BLOCKLIST for w in words_stripped):
        return True
    return False


def _company_norms(doc, known_tech: dict) -> set[str]:
    """Normalized employer-name terms from the JD's opening lines.

    The hiring company's name is not a skill — drop it and its words from
    keyword extraction, unless the word is itself a known technology.
    """
    head = "\n".join(doc.text.split("\n")[:6]).lower()
    norms: set[str] = set()
    for ent in doc.ents:
        if ent.label_ != "ORG" or ent.text.lower() not in head:
            continue
        n = ont.normalize(ent.text)
        if not n or n in known_tech:
            continue
        norms.add(n)
        norms.update(w for w in n.split() if len(w) > 2 and w not in known_tech)
    return norms


def _extract_jd_keywords(doc, ontology: dict) -> list[str]:
    """Extract technical keywords from a spaCy-processed JD document."""
    implies_keys = set(ontology.get("implies", {}).keys())
    alias_vals = set(ontology.get("aliases", {}).values())
    known_tech: dict[str, str] = {ont.normalize(k): k for k in implies_keys | alias_vals}
    company = _company_norms(doc, known_tech)

    seen_norms: set[str] = set()
    keywords: list[str] = []

    def _add(text: str) -> None:
        text = _strip_leading_article(" ".join(text.split()))
        if not text:
            return
        n = ont.normalize(text)
        if n in seen_norms or _looks_like_noise(n):
            return
        if n in company or any(w in company for w in n.split()):
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


def _term_variants(norm: str) -> set[str]:
    """Singular/plural variants of a normalized term (last word only).

    Additive: the original form is always included, so the worst case is a
    variant that simply never matches.
    """
    variants = {norm}
    words = norm.split()
    last = words[-1] if words else ""
    head = " ".join(words[:-1])

    def _with_last(new_last: str) -> str:
        return f"{head} {new_last}".strip()

    if len(last) > 3:
        if last.endswith("ies"):
            variants.add(_with_last(last[:-3] + "y"))
        elif last.endswith("es"):
            variants.add(_with_last(last[:-2]))
            variants.add(_with_last(last[:-1]))
        elif last.endswith("s") and not last.endswith("ss"):
            variants.add(_with_last(last[:-1]))
    if last and not last.endswith("s"):
        variants.add(_with_last(last + "s"))
    return variants


_STEM_STRIP = ("ment", "tion", "ing", "ed", "es", "er", "s")
_STEM_GROW = ("", "e", "s", "es", "ed", "ing", "ment", "ement", "ion", "er")


def _stem_family(norm: str) -> set[str]:
    """Derivational surface forms of the head word (Sovren-style stemming).

    "manage" ↔ "managed" ↔ "managing" ↔ "management" all hit. Junk forms are
    harmless — matching is additive, and a form like "manageed" never occurs
    in real text. Words under 5 chars are left alone (protects Go, AWS, C#…).
    """
    words = norm.split()
    last = words[-1] if words else ""
    if len(last) < 5 or not last.isalpha():
        return set()

    bases = {last}
    for suf in _STEM_STRIP:
        if last.endswith(suf) and len(last) - len(suf) >= 4:
            bases.add(last[: -len(suf)])
    for b in list(bases):
        if b.endswith("e"):
            bases.add(b[:-1])

    head = " ".join(words[:-1])
    return {f"{head} {b}{suf}".strip() for b in bases for suf in _STEM_GROW}


def _direct_sections(kw_norm: str, section_norms: dict[str, str]) -> list[str]:
    """Sections where the keyword appears whole-word, including
    singular/plural variants and the stemmed family of the head word."""
    forms = _term_variants(kw_norm) | _stem_family(kw_norm)
    pattern = "|".join(re.escape(v) for v in sorted(forms))
    rx = re.compile(rf"\b(?:{pattern})\b")
    return [section for section, text in section_norms.items() if rx.search(text)]


def _compound_words(kw_norm: str) -> list[str]:
    """Content words of a multi-word term ([] when not a compound)."""
    words = [w for w in kw_norm.split() if len(w) > 2 and w not in _GENERIC_TERMS]
    return words if len(words) >= 2 else []


def _score_keyword(
    kw: str,
    section_norms: dict[str, str],
    expanded_norms: set[str],
    fuzzy_candidates: list[str],
) -> tuple[float, list[str], str]:
    """Score one JD keyword against the resume.

    Match ladder: direct (whole-word incl. singular/plural variants) →
    ontology expansion → compound (every content word of a multi-word term
    covered individually) → fuzzy string match. Direct matches that appear
    only in the skills list are slightly discounted: a skill demonstrated in
    experience or projects reads stronger to a reviewer than a bare list entry.
    """
    kw_norm = ont.normalize(kw)

    found_in = _direct_sections(kw_norm, section_norms)
    if found_in:
        score = _KW_SCORE_DIRECT
        if found_in == ["skills"]:
            score *= _SKILLS_ONLY_FACTOR
        return score, found_in, "direct"

    # Ontology expansion match (resume skills imply this keyword)
    if _term_variants(kw_norm) & expanded_norms:
        return _KW_SCORE_ONTOLOGY, ["skills"], "ontology"

    # Compound: "node.js microservices" counts when every content word is
    # covered somewhere (directly or via ontology), just not as one phrase.
    words = _compound_words(kw_norm)
    if words:
        covered_sections: set[str] = set()
        all_covered = True
        for w in words:
            secs = _direct_sections(w, section_norms)
            if secs:
                covered_sections.update(secs)
            elif _term_variants(w) & expanded_norms:
                covered_sections.add("skills")
            else:
                all_covered = False
                break
        if all_covered:
            return _KW_SCORE_COMPOUND, sorted(covered_sections), "compound"

    # Fuzzy match against short candidate strings (skill items + project tech)
    if _HAS_RAPIDFUZZ:
        scorer = _fuzz.token_set_ratio if " " in kw_norm else _fuzz.ratio
        for item in fuzzy_candidates:
            if scorer(kw_norm, ont.normalize(item)) >= _FUZZY_MIN_RATIO:
                return _KW_SCORE_FUZZY, ["skills"], "fuzzy"

    return 0.0, [], "none"


# ── keyword importance ───────────────────────────────────────────────────────

_REQUIRED_CTX_RE = re.compile(
    r"\b(?:required|must[ -]have|must\b|essential|proficient|proficiency|expert(?:ise)?|strong)\b",
    re.IGNORECASE,
)
_NICE_CTX_RE = re.compile(
    r"\b(?:nice[ -]to[ -]have|preferred|a plus|plus\b|bonus|good[ -]to[ -]have|familiar(?:ity)?)\b",
    re.IGNORECASE,
)
_REQUIRED_HEADING_RE = re.compile(
    r"^(?:requirements?|(?:minimum |basic )?qualifications?|must[ -]haves?"
    r"|what (?:you(?:'|’)?ll need|we(?:'|’)re looking for)|skills?(?: required)?)\b",
    re.IGNORECASE,
)
_NICE_HEADING_RE = re.compile(
    r"^(?:nice[ -]to[ -]haves?|preferred(?: qualifications?)?|bonus(?: points?)?"
    r"|good[ -]to[ -]haves?|extra credit|pluses)\b",
    re.IGNORECASE,
)


def _classify_jd_blocks(jd_text: str) -> list[tuple[str, str]]:
    """Split the JD into (kind, text) blocks by heading: "required",
    "nice", or "body". Real JDs put must-haves and nice-to-haves under
    separate headings, not on the same line as the skill."""
    blocks: list[tuple[str, str]] = []
    for block in re.split(r"\n{2,}", jd_text):
        heading = block.strip().split("\n")[0].strip()
        if _REQUIRED_HEADING_RE.match(heading):
            kind = "required"
        elif _NICE_HEADING_RE.match(heading):
            kind = "nice"
        else:
            kind = "body"
        blocks.append((kind, block.lower()))
    return blocks


def _keyword_weights(jd_text: str, keywords: list[str]) -> dict[str, float]:
    """Importance of each JD keyword from repetition and surrounding context.

    Context comes from two signals: the heading of the JD block the keyword
    sits under (Requirements vs Nice-to-have), and required/preferred phrasing
    on the same line. A keyword mentioned three times under "Requirements"
    matters far more than one mentioned once under "Bonus points". Weights
    multiply each keyword's contribution to the keyword score (matched and
    missing alike).
    """
    norm_text = ont.normalize(jd_text)
    lines = [ln for ln in jd_text.split("\n") if ln.strip()]
    blocks = _classify_jd_blocks(jd_text)

    weights: dict[str, float] = {}
    for kw in keywords:
        kw_norm = ont.normalize(kw)
        freq = len(re.findall(rf"\b{re.escape(kw_norm)}\b", norm_text)) if kw_norm else 0
        weight = 1.0 + _IMP_FREQ_BONUS * min(max(freq - 1, 0), _IMP_FREQ_CAP)

        kw_lower = kw.lower()

        # Same-line phrasing is the most specific signal ("GraphQL is a plus"
        # under a Requirements heading is still a nice-to-have).
        line_required = line_nice = False
        for line in lines:
            if kw_lower in line.lower():
                if _REQUIRED_CTX_RE.search(line):
                    line_required = True
                elif _NICE_CTX_RE.search(line):
                    line_nice = True

        block_required = block_nice = False
        for kind, block in blocks:
            if kind != "body" and kw_lower in block:
                if kind == "required":
                    block_required = True
                else:
                    block_nice = True

        if line_nice and not line_required:
            weight *= _IMP_NICE_FACTOR
        elif line_required or block_required:
            weight *= _IMP_REQUIRED_BOOST
        elif block_nice:
            weight *= _IMP_NICE_FACTOR

        weights[kw] = round(weight, 3)
    return weights


def _canonical_title_tokens(title: str, ontology: dict) -> set[str]:
    """Normalize a job title to comparable role tokens.

    Applies the ontology's title_aliases phrase map (e.g. "swe" →
    "software engineer"), strips seniority words, and folds role synonyms
    (developer/programmer → engineer).
    """
    t = ont.normalize(title)
    for phrase, canonical in ontology.get("title_aliases", {}).items():
        p = ont.normalize(phrase)
        if p and re.search(rf"\b{re.escape(p)}\b", t):
            t = re.sub(rf"\b{re.escape(p)}\b", ont.normalize(canonical), t)
    tokens = set(t.split()) - _SENIORITY
    return {_ROLE_EQUIV.get(tok, tok) for tok in tokens}


def _seniority_level(title: str, levels: dict[str, int]) -> int | None:
    tokens = set(ont.normalize(title).split())
    found = [lvl for tok, lvl in levels.items() if tok and tok in tokens]
    return max(found) if found else None


def _seniority_bonus(jd_title: str, positions: list[Position], levels: dict[str, int]) -> float:
    """0-10 bonus for how well resume seniority lines up with the JD's."""
    jd_lvl = _seniority_level(jd_title, levels)
    resume_lvls = [lvl for p in positions if (lvl := _seniority_level(p.title, levels)) is not None]
    resume_lvl = max(resume_lvls) if resume_lvls else None

    if jd_lvl is None and resume_lvl is None:
        return 10.0  # no seniority requirement to miss
    if jd_lvl is None or resume_lvl is None:
        return 5.0
    diff = abs(jd_lvl - resume_lvl)
    if diff == 0:
        return 10.0
    if diff == 1:
        return 6.0
    return 0.0


def _title_score(jd_title: str, positions: list[Position], ontology: dict | None = None) -> float:
    if not jd_title or not positions:
        return 50.0
    ontology = ontology or ont.load_ontology()

    jd_tokens = _canonical_title_tokens(jd_title, ontology)
    if not jd_tokens:
        return 50.0

    best = 0.0
    for pos in positions:
        pos_tokens = _canonical_title_tokens(pos.title, ontology)
        if not pos_tokens:
            continue
        inter = jd_tokens & pos_tokens
        # Blend overlap coefficient (containment: "software engineer" inside
        # "senior full stack software engineer" scores 1.0) with Jaccard
        # (penalises titles that share little overall).
        overlap = len(inter) / min(len(jd_tokens), len(pos_tokens))
        jaccard = len(inter) / len(jd_tokens | pos_tokens)
        sim = 0.6 * overlap + 0.4 * jaccard
        if sim > best:
            best = sim

    bonus = _seniority_bonus(jd_title, positions, ontology.get("seniority_levels", {}))
    return min(100.0, round(best * 90.0 + bonus, 1))


def _experience_score(resume: ResumeData, jd_text: str) -> tuple[float, float]:
    """Returns (score, years_detected).

    Continuous curves instead of cliffs: 4.9 years against a 5-year
    requirement should score ~98, not drop a whole bracket.
    """
    years = compute_years_experience(resume.all_positions())
    req_match = re.search(r"(\d+)\+?\s*(?:to\s*\d+\s*)?years?", jd_text.lower())
    req_years = float(req_match.group(1)) if req_match else None

    if req_years and req_years > 0:
        ratio = years / req_years
        if ratio >= 1.0:
            score = 100.0
        else:
            # Slightly superlinear: small shortfalls cost little, large ones a lot.
            score = max(15.0, round(100.0 * ratio ** 1.15, 1))
    else:
        # No stated requirement — interpolate the config ladder linearly.
        ladder = [
            (float(_EXP_IDEAL), 100.0),
            (float(_EXP_GOOD), 90.0),
            (float(_EXP_OK), 70.0),
            (float(_EXP_PARTIAL), 40.0),
            (0.0, 10.0),
        ]
        if years >= ladder[0][0]:
            score = 100.0
        else:
            score = 10.0
            for (hi_y, hi_s), (lo_y, lo_s) in zip(ladder, ladder[1:]):
                if lo_y <= years < hi_y:
                    frac = (years - lo_y) / (hi_y - lo_y) if hi_y > lo_y else 0.0
                    score = round(lo_s + (hi_s - lo_s) * frac, 1)
                    break

    return score, years


_CS_TERMS = {"computer science", "software engineering", "information technology", "computing"}


def _resume_education_level(resume: ResumeData, edu_levels: dict[str, float]) -> tuple[float, str, str]:
    """Return (level, level_keyword, cs_field) for the resume's highest degree.

    Assumes a bachelor's if no known degree keyword is found. cs_field is the
    matched CS-adjacent field of study, or "" when none matched.
    """
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

    cs_match = next((t for t in _CS_TERMS if t in all_edu_text), "")
    return highest, highest_kw, cs_match


def _jd_education_requirement(
    jd_text: str, edu_levels: dict[str, float]
) -> tuple[float, str, bool, float]:
    """Extract the JD's degree requirement.

    Returns (required_level, required_keyword, is_flexible, preferred_level).
    required_level is 0.0 when the JD states no degree requirement. When the
    JD offers alternatives ("Bachelor or Master"), is_flexible is True,
    required_level is the minimum, and preferred_level the maximum.
    """
    jd_lower = jd_text.lower()

    jd_found: list[tuple[str, float, int]] = []  # (keyword, level, pos)
    for keyword, level in edu_levels.items():
        pos = jd_lower.find(keyword)
        if pos != -1:
            jd_found.append((keyword, float(level), pos))
    if not jd_found:
        return 0.0, "", False, 0.0

    # Multiple degree keywords within ~120 chars joined by "or" indicate a
    # flexible requirement (e.g. "Bachelor or Master degree").
    jd_found.sort(key=lambda x: x[2])  # sort by position
    for i in range(len(jd_found) - 1):
        kw_a, lvl_a, pos_a = jd_found[i]
        kw_b, lvl_b, pos_b = jd_found[i + 1]
        span = jd_lower[pos_a: pos_b + len(kw_b)]
        if "or" in span and (pos_b - pos_a) <= 120:
            req = min(lvl_a, lvl_b)
            preferred = max(lvl_a, lvl_b)
            req_kw = kw_a if lvl_a < lvl_b else kw_b
            return req, req_kw, True, preferred

    # No "or" alternative — take the highest mentioned as strict requirement
    req_kw, req, _ = max(jd_found, key=lambda x: x[1])
    return req, req_kw, False, 0.0


def _education_score(resume: ResumeData, jd_text: str, ontology: dict) -> tuple[float, EduGap | None]:
    edu_levels: dict[str, float] = ontology.get("education_levels", {})
    if not resume.schools:
        return 30.0, None

    highest, highest_kw, cs_match = _resume_education_level(resume, edu_levels)
    cs_bonus = 10.0 if cs_match else 0.0
    jd_req, jd_req_kw, jd_is_flexible, jd_preferred = _jd_education_requirement(jd_text, edu_levels)

    if jd_req <= 0:
        return min(100.0, highest + cs_bonus), None

    matched = highest >= jd_req
    if matched:
        if jd_is_flexible and jd_preferred > jd_req and highest < jd_preferred:
            # Meets the minimum of a flexible "X or Y" requirement but not the
            # preferred higher degree — light penalty proportional to the gap
            # between min and preferred on the degree ladder.
            ladder_gap = jd_preferred - jd_req
            light_penalty = min(12.0, round(ladder_gap * 0.3, 1))
            score = min(100.0, 100.0 - light_penalty + cs_bonus)
        else:
            score = min(100.0, 100.0 + cs_bonus)
    else:
        # Below the stated requirement — heavy penalty by how far below:
        # one ladder step (e.g. BSc vs Masters-only) vs two or more (vs PhD).
        score = min(100.0, (50.0 if jd_req - highest <= 30 else 25.0) + cs_bonus)

    gap = EduGap(resume_level=highest_kw, resume_field=cs_match,
                 jd_required=jd_req_kw, jd_required_level=jd_req,
                 resume_level_score=highest, cs_bonus=cs_bonus, matched=matched)
    return score, gap


def run(
    resume: ResumeData,
    jd_text: str,
    threshold: float = _PASS_THRESHOLD,
    use_llm: bool = False,
    progress=None,
) -> JDResult:
    """Score *resume* against *jd_text*. Pure — prints nothing.

    *progress* may provide step(label) / done(note) methods (e.g. ats.term)
    to receive progress events; by default they are discarded.
    """
    if not jd_text or not jd_text.strip():
        raise ValueError("jd_text must not be empty")

    progress = progress if progress is not None else _NULL_PROGRESS
    if use_llm:
        return _run_llm(resume, jd_text, threshold, progress)
    return _run_spacy(resume, jd_text, threshold, progress)


class _NullProgress:
    """Default progress sink — scoring stays silent unless the caller listens."""

    def step(self, label: str) -> None:
        pass

    def done(self, note: str = "") -> None:
        pass


_NULL_PROGRESS = _NullProgress()


def _compute_density(matched: list[KeywordMatch]) -> dict[str, int]:
    """Count how many matched keywords appear in each resume section."""
    density: Counter[str] = Counter()
    for km in matched:
        for section in km.found_in:
            density[section] += 1
    return dict(density)


def _assemble_result(
    resume: ResumeData,
    jd_text: str,
    jd_title: str,
    ontology: dict,
    matched: list[KeywordMatch],
    missing: list[str],
    jd_keywords: list[str],
    kw_weights: dict[str, float],
    threshold: float,
    backend: str,
    **extras,
) -> JDResult:
    """Compute the weighted component scores and build the final JDResult.

    The keyword score is an importance-weighted average: each keyword
    contributes match_score × importance, normalized by total importance —
    so missing a "required" keyword hurts more than missing a "plus".
    """
    for m in matched:
        m.weight = kw_weights.get(m.keyword, 1.0)
    missing = sorted(missing, key=lambda k: kw_weights.get(k, 1.0), reverse=True)

    total_importance = sum(kw_weights.get(k, 1.0) for k in jd_keywords)
    earned = sum(m.score * m.weight for m in matched)
    keyword_score = (earned / total_importance) * 100.0 if total_importance else 0.0
    title_score = _title_score(jd_title, resume.positions, ontology)
    exp_score, years_detected = _experience_score(resume, jd_text)
    edu_score, edu_gap = _education_score(resume, jd_text, ontology)
    overall = (
        keyword_score * _W_KEYWORD
        + title_score * _W_TITLE
        + exp_score * _W_EXP
        + edu_score * _W_EDU
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
        edu_gap=edu_gap,
        author_name=resume.contact.full_name,
        author_email=resume.contact.email,
        backend=backend,
        keyword_density=_compute_density(matched),
        keyword_weights=kw_weights,
        **extras,
    )


def _run_spacy(resume: ResumeData, jd_text: str, threshold: float, progress) -> JDResult:
    progress.step("Parsing job description…")
    ontology = ont.load_ontology()
    jd_title = _extract_jd_title(jd_text)
    cleaned_jd = _strip_nontechnical_sections(jd_text)
    progress.done(f"title: {jd_title!r}" if jd_title else "")

    progress.step("Extracting keywords via NLP…")
    nlp = _load_spacy()
    doc = nlp(cleaned_jd)
    jd_keywords = _extract_jd_keywords(doc, ontology)
    progress.done(f"{len(jd_keywords)} keywords identified")

    progress.step("Matching resume against keywords…")
    section_norms = {s: ont.normalize(t) for s, t in _build_section_texts(resume).items()}
    fuzzy_candidates = [item for sc in resume.skills for item in sc.items]
    for proj in resume.projects:
        fuzzy_candidates.extend(proj.tech)
    expanded = ont.expand_skills(fuzzy_candidates, ontology)
    expanded_norms = {ont.normalize(s) for s in expanded}

    matched: list[KeywordMatch] = []
    missing: list[str] = []
    for kw in jd_keywords:
        score, found_in, via = _score_keyword(kw, section_norms, expanded_norms, fuzzy_candidates)
        if score > 0:
            matched.append(KeywordMatch(keyword=kw, found_in=found_in, matched_via=via, score=score))
        else:
            missing.append(kw)
    _apply_stale_discount(matched, resume)
    progress.done(f"{len(matched)} matched · {len(missing)} missing")

    progress.step("Computing weighted scores…")
    kw_weights = _keyword_weights(jd_text, jd_keywords)
    result = _assemble_result(
        resume, jd_text, jd_title, ontology,
        matched, missing, jd_keywords, kw_weights,
        threshold, backend="spacy",
        soft_skills=_scan_soft_skills(jd_text, resume),
    )
    progress.done()
    return result


def _apply_stale_discount(matched: list[KeywordMatch], resume: ResumeData) -> None:
    """Discount skills demonstrated only in roles before the current one.

    Real ATS weight recent experience in the required stack more heavily —
    a skill last used three jobs ago is a weaker signal than one used today.
    Skills/projects/summary mentions are treated as current.
    """
    if not resume.positions:
        return
    current = resume.positions[0]
    recent_norm = {"recent": ont.normalize(f"{current.title} {' '.join(current.items)}")}
    for m in matched:
        if m.found_in == ["experience"] and not _direct_sections(ont.normalize(m.keyword), recent_norm):
            m.score = round(m.score * _STALE_FACTOR, 3)
            m.stale = True


def _scan_soft_skills(jd_text: str, resume: ResumeData) -> list[tuple[str, bool]]:
    """Soft skills the JD asks for, and whether the resume mentions them.

    Reported for awareness (the way market checkers do) rather than scored —
    soft-skill keyword presence is a weak signal either way.
    """
    jd_lower = jd_text.lower()
    resume_lower = resume.all_text().lower()
    return [
        (skill, skill in resume_lower)
        for skill in _SOFT_SKILLS
        if skill in jd_lower
    ]


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


def _run_llm(resume: ResumeData, jd_text: str, threshold: float, progress) -> JDResult:
    from . import llm_analyzer

    progress.step("Parsing job description…")
    ontology = ont.load_ontology()
    jd_title = _extract_jd_title(jd_text)
    progress.done(f"title: {jd_title!r}" if jd_title else "")

    progress.step("Extracting keywords via LLM…")
    jd_keywords = llm_analyzer.extract_jd_keywords(jd_text)
    progress.done(f"{len(jd_keywords)} keywords identified")

    progress.step("Matching resume semantically…")
    analysis = llm_analyzer.analyze_resume_match(resume, jd_text, jd_keywords)
    progress.done(f"{len(analysis.matched)} matched · {len(analysis.missing)} missing")

    progress.step("Generating bullet rewrites…")
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
    progress.done(f"{len(bullet_rewrites)} rewrite(s)")

    progress.step("Computing weighted scores…")
    matched: list[KeywordMatch] = []
    for lm in analysis.matched:
        via   = _LLM_VIA_MAP.get(lm.match_type, "direct")
        score = _LLM_SCORE_MAP.get(lm.match_type, _KW_SCORE_DIRECT)
        matched.append(KeywordMatch(keyword=lm.keyword, found_in=lm.found_in, matched_via=via, score=score))

    kw_weights = _keyword_weights(jd_text, jd_keywords)
    result = _assemble_result(
        resume, jd_text, jd_title, ontology,
        matched, analysis.missing, jd_keywords, kw_weights,
        threshold, backend="llm",
        suggestions=analysis.suggestions,
        role_fit=analysis.role_fit,
        bullet_rewrites=bullet_rewrites,
        soft_skills=_scan_soft_skills(jd_text, resume),
    )
    progress.done()
    return result
