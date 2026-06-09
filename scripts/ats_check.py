#!/usr/bin/env python3
"""
ATS checker for folia resumes.

Reads resume content directly from data/*.yml (no PDF extraction needed)
and scores it either as a standalone CV health check or against a job description.
If GROQ_API_KEY is set, Groq LLM is used automatically for JD matching.

Usage:
  python3 scripts/ats_check.py                      # CV health check
  python3 scripts/ats_check.py --jd jd.txt          # score against JD (Groq if key set, else spaCy)
  python3 scripts/ats_check.py --jd -               # JD from stdin
  python3 scripts/ats_check.py --jd jd.txt --no-groq  # force spaCy even if key is set
  make ats                                           # via Makefile
  make ats JD=jd.txt                                # via Makefile with JD
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add repo root to path so `from ats import ...` finds ats/ at root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ats import loader, health, renderer  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ATS checker — score your folia CV against real ATS criteria.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python3 scripts/ats_check.py                              # CV health check\n"
            "  python3 scripts/ats_check.py --jd jd.txt                 # JD match (auto Groq if key set)\n"
            "  cat jd.txt | python3 scripts/ats_check.py --jd -         # JD from stdin\n"
            "  python3 scripts/ats_check.py --jd jd.txt --no-groq       # force spaCy backend\n"
            "  make ats                                                   # health check\n"
            "  make ats JD=jd.txt                                        # JD match (auto Groq if key set)"
        ),
    )
    parser.add_argument(
        "--jd",
        metavar="FILE",
        default=None,
        help="path to job description text file, or '-' to read from stdin",
    )
    groq_group = parser.add_mutually_exclusive_group()
    groq_group.add_argument(
        "--groq",
        action="store_true",
        default=False,
        help="force Groq LLM backend (requires GROQ_API_KEY)",
    )
    groq_group.add_argument(
        "--no-groq",
        action="store_true",
        default=False,
        help="force spaCy backend even if GROQ_API_KEY is set",
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
    return parser.parse_args()


def _resolve_groq(args) -> bool:
    """Determine whether to use the Groq backend for JD matching.

    Priority: --no-groq flag > --groq flag > auto-detect from GROQ_API_KEY.
    """
    if args.no_groq:
        return False
    if args.groq:
        return True
    from ats.groq_analyzer import is_available
    return is_available()


def main() -> int:
    args = _parse_args()
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

        use_groq = _resolve_groq(args)
        result = jd_matcher.run(resume, jd_text, threshold=args.threshold, use_groq=use_groq)
    else:
        result = health.run(resume, threshold=args.threshold)

    renderer.render(result, no_color=args.no_color)
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
