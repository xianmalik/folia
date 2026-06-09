#!/usr/bin/env python3
"""Groq LLM backend for ATS keyword extraction and semantic resume matching."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

try:
    from groq import Groq
    _HAS_GROQ = True
except ImportError:
    _HAS_GROQ = False

from . import config as _cfg
from .loader import ResumeData

_GC = _cfg.get().get("groq", {})
_DEFAULT_MODEL = _GC.get("model", "llama-3.3-70b-versatile")
_TEMPERATURE = _GC.get("temperature", 0.1)
_MAX_TOKENS = _GC.get("max_tokens", 4096)


@dataclass
class GroqKeywordMatch:
    keyword: str
    found_in: list[str]
    match_type: str  # "direct" | "semantic" | "implied"


@dataclass
class GroqAnalysis:
    jd_keywords: list[str] = field(default_factory=list)
    matched: list[GroqKeywordMatch] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    role_fit: str = ""


def is_available() -> bool:
    """Return True if the groq package is installed and GROQ_API_KEY is set."""
    return _HAS_GROQ and bool(os.environ.get("GROQ_API_KEY"))


def _get_client() -> "Groq":
    if not _HAS_GROQ:
        raise RuntimeError("groq package not installed — run: pip install groq")
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable not set")
    return Groq(api_key=api_key)


def _chat(client: "Groq", system: str, user: str, model: str) -> dict:
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
        raise RuntimeError(f"Groq returned invalid JSON: {e}\n\nRaw response:\n{raw}") from e


def extract_jd_keywords(jd_text: str, model: str = _DEFAULT_MODEL) -> list[str]:
    """Use Groq to extract technical ATS keywords from a job description."""
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
        raise RuntimeError(f"Groq keyword response missing 'keywords' list: {data}")
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
) -> GroqAnalysis:
    """Semantically match resume content against JD keywords using Groq."""
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
            matched.append(GroqKeywordMatch(keyword=kw, found_in=list(found_in), match_type=match_type))

    missing = [str(k).strip() for k in data.get("missing", []) if k]
    suggestions = [str(s).strip() for s in data.get("suggestions", []) if s]
    role_fit = str(data.get("role_fit", "")).strip()

    return GroqAnalysis(
        jd_keywords=jd_keywords,
        matched=matched,
        missing=missing,
        suggestions=suggestions,
        role_fit=role_fit,
    )
