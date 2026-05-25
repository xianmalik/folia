#!/usr/bin/env python3
"""
ATS checker for folia resumes.

Reads resume content directly from data/*.yml (no PDF extraction needed)
and scores it either as a standalone CV health check or against a job description.

Usage:
  python3 scripts/ats_check.py                      # CV health check
  python3 scripts/ats_check.py --jd jd.txt          # score against JD
  python3 scripts/ats_check.py --jd -               # JD from stdin
  python3 scripts/ats_check.py --validate-pdf        # check PDF is ATS-extractable
  make ats                                           # via Makefile
  make ats-jd JD=jd.txt                             # via Makefile
  make ats-pdf-check                                 # via Makefile
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add repo root to path so `from ats import ...` finds ats/ at root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ats import loader, health, renderer  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ATS checker — score your folia CV against real ATS criteria.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python3 scripts/ats_check.py                      # CV health check\n"
            "  python3 scripts/ats_check.py --jd jd.txt          # score against JD\n"
            "  cat jd.txt | python3 scripts/ats_check.py --jd -  # JD from stdin\n"
            "  python3 scripts/ats_check.py --validate-pdf        # PDF extraction check\n"
            "  make ats                                           # via Makefile\n"
            "  make ats-jd JD=jd.txt                             # via Makefile\n"
            "  make ats-pdf-check                                 # via Makefile"
        ),
    )
    parser.add_argument(
        "--jd",
        metavar="FILE",
        default=None,
        help="path to job description text file, or '-' to read from stdin",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=70.0,
        metavar="SCORE",
        help="minimum passing score 0-100 (default: 70)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="disable ANSI colour output",
    )
    parser.add_argument(
        "--validate-pdf",
        action="store_true",
        help="validate that dist/resume.pdf is cleanly extractable by ATS parsers",
    )
    parser.add_argument(
        "--pdf",
        metavar="PATH",
        default=None,
        help="PDF path for --validate-pdf (default: dist/resume.pdf)",
    )
    sem_group = parser.add_mutually_exclusive_group()
    sem_group.add_argument(
        "--semantic",
        action="store_true",
        default=None,
        help="enable semantic (embedding) matching; auto-detected when sentence-transformers is installed",
    )
    sem_group.add_argument(
        "--no-semantic",
        action="store_true",
        help="disable semantic matching even when sentence-transformers is available",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="enable LLM gap analysis (requires ANTHROPIC_API_KEY or OPENAI_API_KEY)",
    )
    return parser.parse_args()


def _run_pdf_validation(pdf_path: Path, resume_name: str, no_color: bool) -> int:
    from ats.pdf_validator import validate_pdf, _is_available

    if not _is_available():
        print(
            "pdfminer.six not installed.\n"
            "Install with: pip install pdfminer.six\n"
            "Or: make deps",
            file=sys.stderr,
        )
        return 1

    result = validate_pdf(pdf_path, expected_name=resume_name)

    GREEN = "\033[32m" if not no_color else ""
    RED = "\033[31m" if not no_color else ""
    YELLOW = "\033[33m" if not no_color else ""
    BOLD = "\033[1m" if not no_color else ""
    NC = "\033[0m" if not no_color else ""

    print()
    print(f"{BOLD}PDF ATS Extraction Validator{NC}")
    print(f"  File: {pdf_path}")
    print()

    status = f"{GREEN}✓ PASS{NC}" if result.ok else f"{RED}✗ FAIL{NC}"
    print(f"  Status           : {status}")
    print(f"  Word count       : {result.word_count}")
    print(f"  Garbled chars    : {'YES ← bad' if result.has_garbled_chars else 'none ✓'}")
    print(f"  Name found       : {'yes ✓' if result.has_name else 'NO ← check header'}")
    print(f"  Experience section: {'yes ✓' if result.has_experience_section else 'NO'}")
    print(f"  Skills section   : {'yes ✓' if result.has_skills_section else 'NO'}")

    if result.warnings:
        print()
        for w in result.warnings:
            print(f"  {YELLOW}⚠  {w}{NC}")

    if result.extracted_preview:
        print()
        print(f"  {BOLD}Extracted text preview (first 300 chars):{NC}")
        print(f"  {result.extracted_preview!r}")

    print()
    return 0 if result.ok else 1


def main() -> int:
    args = _parse_args()

    if args.validate_pdf:
        pdf_path = Path(args.pdf) if args.pdf else REPO_ROOT / "dist" / "resume.pdf"
        # Try to get the person's name from the resume for the name-presence check
        try:
            resume = loader.load()
            resume_name = resume.contact.full_name
        except Exception:
            resume_name = ""
        return _run_pdf_validation(pdf_path, resume_name, no_color=args.no_color)

    resume = loader.load()

    if args.jd is not None:
        from ats import jd_matcher

        if args.jd == "-":
            jd_text = sys.stdin.read()
        else:
            jd_path = Path(args.jd)
            if not jd_path.exists():
                print(f"ats_check: JD file not found: {jd_path}", file=sys.stderr)
                return 1
            jd_text = jd_path.read_text(encoding="utf-8")

        if not jd_text.strip():
            print("ats_check: JD text is empty", file=sys.stderr)
            return 1

        # Resolve semantic flag: None = auto-detect, True = force on, False = force off
        use_semantic: bool | None = None
        if getattr(args, "no_semantic", False):
            use_semantic = False
        elif getattr(args, "semantic", None):
            use_semantic = True

        result = jd_matcher.run(resume, jd_text, threshold=args.threshold, use_semantic=use_semantic)
    else:
        result = health.run(resume, threshold=args.threshold)

    renderer.render(result, no_color=args.no_color)

    # Optional LLM gap analysis (M4 Phase 3)
    if getattr(args, "llm", False) and getattr(args, "jd", None):
        from ats import llm as _llm
        if not _llm.is_available():
            print(
                "⚠  LLM gap analysis skipped — set ANTHROPIC_API_KEY or OPENAI_API_KEY.",
                file=sys.stderr,
            )
        else:
            use_color = not args.no_color
            BOLD = "\033[1m" if use_color else ""
            CYAN = "\033[0;36m" if use_color else ""
            NC = "\033[0m" if use_color else ""
            print(f"\n  {BOLD}{CYAN}💡 LLM Gap Analysis ({_llm.provider()}){NC}\n")
            resume_all = " ".join([
                resume.summary,
                " ".join(f"{p.title} {p.company} {' '.join(p.items)}" for p in resume.positions),
                " ".join(f"{s.category} {' '.join(s.items)}" for s in resume.skills),
            ])
            analysis = _llm.gap_analysis(resume_all, jd_text)
            for line in analysis.split("\n"):
                print(f"  {line}")
            print()

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
