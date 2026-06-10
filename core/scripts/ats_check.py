#!/usr/bin/env python3
"""
ATS checker for folia resumes.

Extracts resume content from the compiled dist/resume.pdf (building it first
if needed) and scores it either as a standalone CV health check or against a
job description. If GROQ_API_KEY is set, the LLM backend is used automatically
for JD matching.

Usage:
  python3 core/scripts/ats_check.py                         # CV health check
  python3 core/scripts/ats_check.py --jd jd.txt             # JD match (LLM if key set, else NLP)
  python3 core/scripts/ats_check.py --jd -                  # JD from stdin
  python3 core/scripts/ats_check.py --jd jd.txt --no-llm   # force NLP backend
  make ats                                              # via Makefile
  make ats JD=jd.txt                                   # via Makefile with JD
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ats import health, llm_analyzer, loader, renderer, term  # noqa: E402
from ats.llm_analyzer import RateLimitError  # noqa: E402


def _notify_model_fallback(primary: str, fallback: str) -> None:
    print(
        f"\n  {term.CYAN}⚡ Groq rate limit on {primary} — switching to {fallback}{term.NC}",
        file=sys.stderr, flush=True,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ATS checker — score your folia CV against real ATS criteria.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python3 core/scripts/ats_check.py                             # CV health check\n"
            "  python3 core/scripts/ats_check.py --jd jd.txt                # JD match (auto LLM if key set)\n"
            "  cat jd.txt | python3 core/scripts/ats_check.py --jd -        # JD from stdin\n"
            "  python3 core/scripts/ats_check.py --jd jd.txt --no-llm      # force NLP backend\n"
            "  make ats                                                  # health check\n"
            "  make ats JD=jd.txt                                       # JD match (auto LLM if key set)"
        ),
    )
    parser.add_argument(
        "--jd",
        metavar="FILE",
        default=None,
        help="path to job description text file, or '-' to read from stdin",
    )
    llm_group = parser.add_mutually_exclusive_group()
    llm_group.add_argument(
        "--llm",
        action="store_true",
        default=False,
        help="force LLM backend (requires GROQ_API_KEY)",
    )
    llm_group.add_argument(
        "--no-llm",
        action="store_true",
        default=False,
        help="force NLP backend even if GROQ_API_KEY is set",
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


def _resolve_llm(args) -> bool:
    """Determine whether to use the LLM backend for JD matching.

    Priority: --no-llm > --llm > auto-detect from GROQ_API_KEY.
    """
    if args.no_llm:
        return False
    if args.llm:
        return True
    from ats.llm_analyzer import is_available
    return is_available()


def main() -> int:
    args = _parse_args()

    loader.ensure_pdf()

    if args.jd is not None:
        from ats import jd_matcher

        term.step("Loading resume data…")
        resume = loader.load()
        term.done()

        renderer.render_jd_header(
            resume.contact.full_name, resume.contact.email, no_color=args.no_color
        )

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

        use_llm = _resolve_llm(args)
        llm_analyzer.on_model_fallback = _notify_model_fallback
        print()
        try:
            result = jd_matcher.run(
                resume, jd_text, threshold=args.threshold, use_llm=use_llm, progress=term
            )
        except RateLimitError:
            print(
                f"\n  {term.CYAN}⚡ LLM rate limit hit — falling back to local NLP check{term.NC}\n",
                file=sys.stderr, flush=True,
            )
            result = jd_matcher.run(
                resume, jd_text, threshold=args.threshold, use_llm=False, progress=term
            )
            result.llm_fallback = True
        print()
    else:
        term.step("Loading resume data…")
        resume = loader.load()
        term.done()

        term.step("Running ATS health checks…")
        result = health.run(resume, threshold=args.threshold)
        term.done()

        term.step("Generating report…")
        term.done()
        print()

    renderer.render(result, no_color=args.no_color)
    return 0 if result.passed else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RateLimitError as e:
        c = term.make_resolver(True)  # color always on for error output
        print(file=sys.stderr)
        b = term.Box(color=term.RED, c=c)
        b.open()
        msg = f"✗  {e} — aborting check."
        b.raw_row(f"{term.BOLD}{msg}{term.NC}", len(msg))
        b.close()
        print(file=sys.stderr)
        sys.exit(1)
