#!/usr/bin/env python3
"""LLM backend for ATS keyword extraction and semantic resume matching."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

try:
    from groq import Groq as _GroqClient
    _HAS_LLM = True
except ImportError:
    _HAS_LLM = False

from . import config as _cfg
from .loader import ResumeData

_LC = _cfg.get().get("llm", {})
_DEFAULT_MODEL = _LC.get("model", "llama-3.3-70b-versatile")
_TEMPERATURE = _LC.get("temperature", 0.1)
_MAX_TOKENS = _LC.get("max_tokens", 4096)


@dataclass
class LLMKeywordMatch:
    keyword: str
    found_in: list[str]
    match_type: str  # "direct" | "semantic" | "implied"


@dataclass
class LLMAnalysis:
    jd_keywords: list[str] = field(default_factory=list)
    matched: list[LLMKeywordMatch] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    role_fit: str = ""


def is_available() -> bool:
    """Return True if the LLM client is installed and an API key is set."""
    return _HAS_LLM and bool(os.environ.get("GROQ_API_KEY"))


def _get_client() -> "_GroqClient":
    if not _HAS_LLM:
        raise RuntimeError("LLM client not installed — run: pip install groq")
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable not set")
    return _GroqClient(api_key=api_key)


def _chat(client: "_GroqClient", system: str, user: str, model: str) -> dict:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=_TEMPERATURE,
        max_tokens=_MAX_TOKENS,
    )
    raw = response.choices[0].message.content
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"LLM returned invalid JSON: {e}\n\nRaw response:\n{raw}") from e


def extract_jd_keywords(jd_text: str, model: str = _DEFAULT_MODEL) -> list[str]:
    """Extract technical ATS keywords from a job description using the LLM."""
    client = _get_client()
    system = (
        "You are an ATS keyword extraction specialist. "
        "Always respond with valid JSON containing exactly one key: 'keywords'."
    )
    user = (
        "Extract technical keywords from this job description for ATS resume matching.\n\n"
        "Rules:\n"
        "- Include: programming languages, frameworks, libraries, tools, cloud services, "
        "databases, platforms, methodologies, certifications, domain-specific technical terms.\n"
        "- Include multi-word terms as single entries (e.g. 'machine learning', 'REST API', 'CI/CD').\n"
        "- Exclude: soft skills, company culture, benefits, location, and generic English words.\n"
        "- Return 15-40 keywords covering the core technical requirements.\n\n"
        f"Job Description:\n{jd_text}\n\n"
        'Return: {"keywords": ["keyword1", "keyword2", ...]}'
    )
    data = _chat(client, system, user, model)
    keywords = data.get("keywords", [])
    if not isinstance(keywords, list):
        raise RuntimeError(f"LLM keyword response missing 'keywords' list: {data}")
    return [str(k).strip() for k in keywords if k]


def _format_resume(resume: ResumeData) -> str:
    parts: list[str] = []
    parts.append(f"Name: {resume.contact.full_name}")
    if resume.contact.position:
        parts.append(f"Current Title: {resume.contact.position}")
    if resume.summary:
        parts.append(f"\nSUMMARY:\n{resume.summary}")
    if resume.positions or resume.internships:
        parts.append("\nEXPERIENCE:")
        for pos in resume.positions + resume.internships:
            parts.append(f"  {pos.title} at {pos.company} ({pos.dates})")
            for item in pos.items:
                parts.append(f"    • {item}")
    if resume.projects:
        parts.append("\nPROJECTS:")
        for proj in resume.projects:
            tech_str = ", ".join(proj.tech) if proj.tech else ""
            parts.append(f"  {proj.name}: {proj.subtitle}")
            if tech_str:
                parts.append(f"    Tech: {tech_str}")
            for item in proj.items:
                parts.append(f"    • {item}")
    if resume.skills:
        parts.append("\nSKILLS:")
        for sc in resume.skills:
            parts.append(f"  {sc.category}: {', '.join(sc.items)}")
    if resume.schools:
        parts.append("\nEDUCATION:")
        for school in resume.schools:
            parts.append(f"  {school.degree}, {school.institution} ({school.dates})")
    return "\n".join(parts)


def analyze_resume_match(
    resume: ResumeData,
    jd_text: str,
    jd_keywords: list[str],
    model: str = _DEFAULT_MODEL,
) -> LLMAnalysis:
    """Semantically match resume content against JD keywords using the LLM."""
    client = _get_client()
    resume_text = _format_resume(resume)
    keywords_str = ", ".join(f'"{k}"' for k in jd_keywords)

    system = (
        "You are an expert ATS matching specialist. "
        "Always respond with valid JSON."
    )
    user = (
        "Analyze how well this resume matches the JD keywords. "
        "For each keyword, determine if the resume covers it directly, semantically, or by implication.\n\n"
        f"JD Keywords to check: [{keywords_str}]\n\n"
        f"Resume:\n{resume_text}\n\n"
        "Rules for match_type:\n"
        '- "direct": exact or near-exact term appears in the resume\n'
        '- "semantic": different words but same concept (e.g. "ML" = "machine learning")\n'
        '- "implied": resume demonstrates the skill indirectly or as a prerequisite\n\n'
        "found_in must only contain values from: "
        '"summary", "experience", "projects", "skills", "education"\n\n'
        "Return JSON:\n"
        "{\n"
        '  "matched": [\n'
        '    {"keyword": "...", "found_in": ["experience"], "match_type": "direct"}\n'
        "  ],\n"
        '  "missing": ["keyword1", "keyword2"],\n'
        '  "suggestions": ["Specific actionable suggestion 1", "..."],\n'
        '  "role_fit": "1-2 sentence assessment of overall role fit"\n'
        "}"
    )
    data = _chat(client, system, user, model)

    matched_raw = data.get("matched", [])
    matched = []
    for m in matched_raw:
        if not isinstance(m, dict):
            continue
        kw = str(m.get("keyword", "")).strip()
        found_in = m.get("found_in", [])
        match_type = str(m.get("match_type", "direct")).strip()
        if isinstance(found_in, str):
            found_in = [found_in]
        if kw and match_type in ("direct", "semantic", "implied"):
            matched.append(LLMKeywordMatch(keyword=kw, found_in=list(found_in), match_type=match_type))

    missing = [str(k).strip() for k in data.get("missing", []) if k]
    suggestions = [str(s).strip() for s in data.get("suggestions", []) if s]
    role_fit = str(data.get("role_fit", "")).strip()

    return LLMAnalysis(
        jd_keywords=jd_keywords,
        matched=matched,
        missing=missing,
        suggestions=suggestions,
        role_fit=role_fit,
    )


def generate_bullet_rewrites(
    resume: ResumeData,
    missing_keywords: list[str],
    jd_text: str,
    max_rewrites: int = 5,
    model: str = _DEFAULT_MODEL,
) -> list[dict]:
    """Generate humanlike bullet rewrites that naturally incorporate missing keywords.

    Returns a list of raw dicts with keys: keyword, role, original, rewritten.
    """
    if not missing_keywords:
        return []

    client = _get_client()

    # Build the experience text with role headers so the LLM knows which role each bullet belongs to
    exp_lines: list[str] = []
    for pos in resume.positions + resume.internships:
        exp_lines.append(f"\n[{pos.title} at {pos.company} · {pos.dates}]")
        for item in pos.items:
            exp_lines.append(f"  • {item}")
    for proj in resume.projects:
        tech_str = ", ".join(proj.tech) if proj.tech else ""
        exp_lines.append(f"\n[Project: {proj.name} · Tech: {tech_str}]")
        for item in proj.items:
            exp_lines.append(f"  • {item}")
    experience_text = "\n".join(exp_lines)

    # Collect a few style-representative bullets for the LLM to learn from
    sample_bullets = [
        item
        for pos in (resume.positions or resume.internships)[:2]
        for item in pos.items[:3]
    ]
    style_samples = "\n".join(f"  • {b}" for b in sample_bullets)

    missing_list = ", ".join(f'"{k}"' for k in missing_keywords[:max_rewrites + 3])

    system = (
        "You are a professional resume coach who writes in a natural, human voice. "
        "Always respond with valid JSON."
    )
    user = (
        f"Suggest up to {max_rewrites} targeted rewrites of existing resume bullets "
        "that naturally incorporate missing keywords from a job description.\n\n"
        "CRITICAL RULES:\n"
        "- Match the candidate's writing voice, tone, and sentence structure EXACTLY — "
        "study the style samples below\n"
        "- Integrate keywords naturally into the context of real work done, "
        "not bolted on as a list\n"
        "- Preserve ALL specific metrics, percentages, company names, and technical details\n"
        "- Use the same action verb style (past tense, strong verbs) as the originals\n"
        "- Keep approximately the same sentence length as the original\n"
        "- NEVER add a keyword if the candidate clearly never did that type of work\n"
        "- Target bullets where the skill is implied by the work but not explicitly named\n"
        "- The rewrite must sound like the candidate wrote it from real experience, "
        "not like AI inserted a keyword\n\n"
        f"CANDIDATE'S WRITING STYLE (match this exactly):\n{style_samples}\n\n"
        f"MISSING KEYWORDS TO INCORPORATE: [{missing_list}]\n\n"
        f"RESUME EXPERIENCE & PROJECTS:\n{experience_text}\n\n"
        f"JD CONTEXT (for understanding what each keyword means in this role):\n"
        f"{jd_text[:1500]}\n\n"
        f"Return JSON with up to {max_rewrites} rewrites — only where integration is "
        "natural and credible:\n"
        "{{\n"
        '  "rewrites": [\n'
        '    {{\n'
        '      "keyword": "the primary keyword being added",\n'
        '      "role": "Job Title at Company Name",\n'
        '      "original": "exact original bullet text verbatim",\n'
        '      "rewritten": "human-sounding rewrite that naturally uses the keyword"\n'
        "    }}\n"
        "  ]\n"
        "}}"
    )
    data = _chat(client, system, user, model)
    rewrites = data.get("rewrites", [])
    if not isinstance(rewrites, list):
        return []
    return [
        r for r in rewrites
        if isinstance(r, dict) and r.get("original") and r.get("rewritten")
    ]
