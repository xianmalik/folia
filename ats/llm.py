#!/usr/bin/env python3
"""
LLM augmentation layer for folia ATS checker (M4 — Phase 3, opt-in).

Activated only when ANTHROPIC_API_KEY or OPENAI_API_KEY is set in the
environment.  When neither key is present, every function is a no-op.

Capabilities
------------
1. Structured JD parsing  — extract {must_have, nice_to_have, responsibilities,
                             screening_criteria} from any format of JD text.
2. Bullet quality grading — grade each resume bullet on STAR format, action verbs,
                             quantification, and JD relevance.
3. Gap analysis           — generate 2–4 sentences of actionable improvement advice.

All LLM calls use a token-cost guardrail: JDs > 8 000 tokens are rejected
unless ``force=True`` is passed.

Usage
-----
    from ats.llm import parse_jd, grade_bullets, gap_analysis, is_available

    if is_available():
        parsed = parse_jd(jd_text)
        gaps   = gap_analysis(resume_text, jd_text)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Availability detection
# ---------------------------------------------------------------------------

_ANTHROPIC_KEY: str | None = os.environ.get("ANTHROPIC_API_KEY")
_OPENAI_KEY: str | None = os.environ.get("OPENAI_API_KEY")


def is_available() -> bool:
    """Return True when at least one LLM API key is configured."""
    return bool(_ANTHROPIC_KEY or _OPENAI_KEY)


def provider() -> str | None:
    """Return the active provider: 'anthropic' | 'openai' | None."""
    if _ANTHROPIC_KEY:
        return "anthropic"
    if _OPENAI_KEY:
        return "openai"
    return None


# ---------------------------------------------------------------------------
# Token guard
# ---------------------------------------------------------------------------

_MAX_TOKENS: int = 8_000   # characters (rough proxy; 1 token ≈ 4 chars)


def _check_length(text: str, *, force: bool = False) -> None:
    approx_tokens = len(text) // 4
    if approx_tokens > _MAX_TOKENS and not force:
        raise ValueError(
            f"JD text is approximately {approx_tokens} tokens "
            f"(limit {_MAX_TOKENS}).  Pass force=True to override."
        )


# ---------------------------------------------------------------------------
# Low-level LLM call
# ---------------------------------------------------------------------------

def _call_llm(system: str, user: str, max_output_tokens: int = 1024) -> str:
    """
    Make a single-turn LLM request using whichever API key is available.
    Returns the text response.  Raises RuntimeError on failure.
    """
    prov = provider()
    if prov is None:
        raise RuntimeError("No LLM API key set (ANTHROPIC_API_KEY or OPENAI_API_KEY).")

    if prov == "anthropic":
        return _call_anthropic(system, user, max_output_tokens)
    return _call_openai(system, user, max_output_tokens)


def _call_anthropic(system: str, user: str, max_tokens: int) -> str:
    try:
        import anthropic  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "anthropic SDK not installed.  Run: pip install anthropic"
        ) from e
    client = anthropic.Anthropic(api_key=_ANTHROPIC_KEY)
    msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text


def _call_openai(system: str, user: str, max_tokens: int) -> str:
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "openai SDK not installed.  Run: pip install openai"
        ) from e
    client = OpenAI(api_key=_OPENAI_KEY)
    resp = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# 1. Structured JD parsing
# ---------------------------------------------------------------------------

@dataclass
class ParsedJD:
    must_have: list[str] = field(default_factory=list)
    nice_to_have: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    screening_criteria: list[str] = field(default_factory=list)
    raw: str = ""   # raw LLM output for debugging


_JD_PARSE_SYSTEM = """
You are an expert technical recruiter assistant.  Extract structured information
from job descriptions.  Return ONLY valid JSON, no markdown, no preamble.

Schema:
{
  "must_have": ["skill or requirement that is explicitly required"],
  "nice_to_have": ["skill or requirement explicitly preferred or optional"],
  "responsibilities": ["key responsibilities for the role"],
  "screening_criteria": ["likely filters a recruiter would use in first-pass screening"]
}

Rules:
- must_have: include items in sections labeled Required, Must have, Essential, Qualifications, etc.
- nice_to_have: include items in sections labeled Preferred, Nice to have, Bonus, Plus, etc.
- Keep each list item concise (3–8 words) and technical.
- responsibilities: include the 5 most important day-to-day duties.
- screening_criteria: infer 3–5 deal-breaker filters a recruiter might use.
- Omit HR/benefits text entirely.
""".strip()


def parse_jd(jd_text: str, *, force: bool = False) -> ParsedJD:
    """
    Parse a job description into structured must-have / nice-to-have etc.

    Returns an empty ParsedJD when no API key is set.
    """
    if not is_available():
        return ParsedJD()
    _check_length(jd_text, force=force)

    raw = _call_llm(_JD_PARSE_SYSTEM, jd_text, max_output_tokens=1024)
    try:
        data = json.loads(raw)
        return ParsedJD(
            must_have=data.get("must_have", []),
            nice_to_have=data.get("nice_to_have", []),
            responsibilities=data.get("responsibilities", []),
            screening_criteria=data.get("screening_criteria", []),
            raw=raw,
        )
    except json.JSONDecodeError:
        return ParsedJD(raw=raw)


# ---------------------------------------------------------------------------
# 2. Bullet quality grading
# ---------------------------------------------------------------------------

@dataclass
class BulletGrade:
    bullet: str
    action_verb: bool       # starts with a strong action verb?
    quantified: bool        # contains a number / metric / percentage?
    star_complete: bool     # has Situation/Task implied, Action, Result?
    jd_relevance: float     # 0–1 how relevant to the JD
    suggestions: list[str]  # concrete improvement suggestions
    score: float            # overall 0–10


@dataclass
class BulletGradeReport:
    grades: list[BulletGrade] = field(default_factory=list)
    mean_score: float = 0.0
    weak_bullets: list[str] = field(default_factory=list)


_BULLET_GRADE_SYSTEM = """
You are a resume coach grading experience bullets for ATS optimisation.
Return ONLY valid JSON, no markdown.

For each bullet in the list, return an object with:
{
  "bullet": "<exact bullet text>",
  "action_verb": true/false,
  "quantified": true/false,
  "star_complete": true/false,
  "jd_relevance": 0.0–1.0,
  "suggestions": ["concise improvement tip"],
  "score": 0.0–10.0
}

Return a JSON array — one element per bullet.  Score rubric:
  10 = strong action verb, quantified, clear impact, relevant to JD
   7 = good but missing one element
   5 = mediocre — generic or no metric
   3 = weak — no verb, vague, or irrelevant
""".strip()


def grade_bullets(
    bullets: list[str],
    jd_text: str,
    *,
    force: bool = False,
) -> BulletGradeReport:
    """
    Grade a list of resume bullets against the JD.

    Returns an empty report when no API key is set.
    """
    if not is_available() or not bullets:
        return BulletGradeReport()
    _check_length(jd_text, force=force)

    user = f"JD (excerpt):\n{jd_text[:3000]}\n\nBullets:\n" + "\n".join(
        f"- {b}" for b in bullets
    )
    raw = _call_llm(_BULLET_GRADE_SYSTEM, user, max_output_tokens=2048)
    try:
        data = json.loads(raw)
        grades: list[BulletGrade] = []
        for item in data:
            grades.append(BulletGrade(
                bullet=item.get("bullet", ""),
                action_verb=bool(item.get("action_verb", False)),
                quantified=bool(item.get("quantified", False)),
                star_complete=bool(item.get("star_complete", False)),
                jd_relevance=float(item.get("jd_relevance", 0)),
                suggestions=item.get("suggestions", []),
                score=float(item.get("score", 0)),
            ))
        mean = sum(g.score for g in grades) / len(grades) if grades else 0.0
        weak = [g.bullet for g in grades if g.score < 6.0]
        return BulletGradeReport(grades=grades, mean_score=round(mean, 1), weak_bullets=weak)
    except (json.JSONDecodeError, KeyError, TypeError):
        return BulletGradeReport()


# ---------------------------------------------------------------------------
# 3. Gap analysis
# ---------------------------------------------------------------------------

_GAP_ANALYSIS_SYSTEM = """
You are a professional resume coach specialising in software engineering roles.
Given a resume (plain text) and a job description, write a concise gap analysis.

Output exactly 3–5 bullet points (starting with •), each under 25 words, that:
1. Identify the most critical missing keywords or skills.
2. Suggest specific, actionable changes the candidate can make.
3. Note any framing or phrasing improvements.

Do NOT praise what is already good.  Focus only on gaps and improvements.
Be direct and technical.
""".strip()


def gap_analysis(
    resume_text: str,
    jd_text: str,
    *,
    force: bool = False,
) -> str:
    """
    Generate a concise gap analysis.

    Returns an empty string when no API key is set.
    """
    if not is_available():
        return ""
    _check_length(jd_text, force=force)
    _check_length(resume_text, force=force)

    user = (
        f"Job Description:\n{jd_text[:4000]}\n\n"
        f"Resume:\n{resume_text[:4000]}"
    )
    try:
        return _call_llm(_GAP_ANALYSIS_SYSTEM, user, max_output_tokens=512)
    except Exception as exc:
        return f"(LLM gap analysis failed: {exc})"
