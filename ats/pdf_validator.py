#!/usr/bin/env python3
"""
ats/pdf_validator.py — ATS PDF text-extraction validator.

Checks that the compiled resume PDF can be read cleanly by ATS parsers.
Uses pdfminer.six (pure Python, no system binary required).

Usage:
    from ats.pdf_validator import validate_pdf
    result = validate_pdf(Path("dist/resume.pdf"), expected_name="Malik Zubayer")
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

try:
    from pdfminer.high_level import extract_text as _pdf_extract
    from pdfminer.pdfparser import PDFParser
    from pdfminer.pdfdocument import PDFDocument
    from pdfminer.pdfpage import PDFPage
    _HAS_PDFMINER = True
except ImportError:
    _HAS_PDFMINER = False


# Replacement / private-use characters that signal broken glyph mapping
_GARBLE_RE = re.compile(r"[�-\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass
class PDFValidationResult:
    ok: bool
    word_count: int
    has_garbled_chars: bool
    has_name: bool
    has_experience_section: bool
    has_skills_section: bool
    warnings: list[str] = field(default_factory=list)
    extracted_preview: str = ""  # first 300 chars of extracted text

    def __str__(self) -> str:
        status = "✓ PASS" if self.ok else "✗ FAIL"
        lines = [
            f"PDF Validation: {status}",
            f"  Word count       : {self.word_count}",
            f"  Garbled chars    : {'YES (bad)' if self.has_garbled_chars else 'none'}",
            f"  Name found       : {'yes' if self.has_name else 'no'}",
            f"  Experience section: {'yes' if self.has_experience_section else 'no'}",
            f"  Skills section   : {'yes' if self.has_skills_section else 'no'}",
        ]
        for w in self.warnings:
            lines.append(f"  ⚠  {w}")
        if self.extracted_preview:
            lines.append(f"\n  Preview (first 300 chars):\n  {self.extracted_preview!r}")
        return "\n".join(lines)


def _is_available() -> bool:
    return _HAS_PDFMINER


def validate_pdf(
    pdf_path: Path,
    expected_name: str = "",
    min_word_count: int = 150,
) -> PDFValidationResult:
    """
    Parse *pdf_path* and run a battery of ATS-readability checks.

    Args:
        pdf_path: path to the compiled PDF
        expected_name: person's name — checked for presence in extracted text
        min_word_count: minimum word count to pass (default 150)

    Returns:
        PDFValidationResult with ok=True if all critical checks pass.
    """
    if not _HAS_PDFMINER:
        return PDFValidationResult(
            ok=False,
            word_count=0,
            has_garbled_chars=False,
            has_name=False,
            has_experience_section=False,
            has_skills_section=False,
            warnings=["pdfminer.six not installed — run: pip install pdfminer.six"],
        )

    if not pdf_path.exists():
        return PDFValidationResult(
            ok=False,
            word_count=0,
            has_garbled_chars=False,
            has_name=False,
            has_experience_section=False,
            has_skills_section=False,
            warnings=[f"PDF not found: {pdf_path}"],
        )

    warnings: list[str] = []

    # Extract raw text
    try:
        text = _pdf_extract(str(pdf_path))
    except Exception as exc:
        return PDFValidationResult(
            ok=False,
            word_count=0,
            has_garbled_chars=True,
            has_name=False,
            has_experience_section=False,
            has_skills_section=False,
            warnings=[f"PDF parse error: {exc}"],
        )

    text_lower = text.lower()
    word_count = len(text.split())
    preview = text[:300].replace("\n", " ").strip()

    # Check 1: garbled / private-use characters
    garble_matches = _GARBLE_RE.findall(text)
    has_garbled = len(garble_matches) > 5  # small count tolerated
    if has_garbled:
        warnings.append(
            f"Found {len(garble_matches)} garbled/private-use chars — "
            "ATS text extraction may be broken (possible font encoding issue)"
        )

    # Check 2: word count
    if word_count < min_word_count:
        warnings.append(
            f"Only {word_count} words extracted (expected ≥{min_word_count}) — "
            "PDF may not be text-selectable"
        )

    # Check 3: name presence
    has_name = False
    if expected_name:
        parts = [p.lower() for p in expected_name.split() if len(p) > 1]
        has_name = any(p in text_lower for p in parts)
        if not has_name:
            warnings.append(
                f"Name '{expected_name}' not found in extracted text — "
                "header may be non-extractable (image or glyph issue)"
            )
    else:
        has_name = True  # can't check without a name — assume ok

    # Check 4: experience section
    has_exp = any(kw in text_lower for kw in ("experience", "employment", "work history"))
    if not has_exp:
        warnings.append(
            "No 'Experience' section heading found in extracted text — "
            "ATS may not identify your work history"
        )

    # Check 5: skills section
    has_skills = "skills" in text_lower or "technical" in text_lower
    if not has_skills:
        warnings.append(
            "No 'Skills' section heading found in extracted text"
        )

    ok = (
        not has_garbled
        and word_count >= min_word_count
        and has_name
        and has_exp
    )

    return PDFValidationResult(
        ok=ok,
        word_count=word_count,
        has_garbled_chars=has_garbled,
        has_name=has_name,
        has_experience_section=has_exp,
        has_skills_section=has_skills,
        warnings=warnings,
        extracted_preview=preview,
    )
