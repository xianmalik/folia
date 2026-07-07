"""Tool registrations: resume content plus the build and ATS flows."""
from __future__ import annotations

import tempfile
from pathlib import Path

from . import config, content, editor, runner
from .app import mcp
from .models import AtsResult, ResumeStatus, clamp_threshold, overall_score


def _truncated_report(output: str) -> str:
    if len(output) <= config.MAX_REPORT_CHARS:
        return output
    return f"[report truncated to last {config.MAX_REPORT_CHARS} chars]\n" + output[
        -config.MAX_REPORT_CHARS :
    ]


# ── content tools ────────────────────────────────────────────────────────────

@mcp.tool(annotations=config.READ)
def get_resume() -> str:
    """Full resume: contact details plus every section's YAML content.

    The one-stop tool when you need the complete CV — for cover letters,
    portfolio pages, bios, or referencing work history from another project.
    """
    return content.resume_markdown()


@mcp.tool(annotations=config.READ)
def list_sections() -> str:
    """List the resume's sections (name and source file, in render order)."""
    lines = [f"- {name}  ({path.name})" for name, path in content.sections().items()]
    return "Resume sections in source/:\n" + "\n".join(lines)


@mcp.tool(annotations=config.READ)
def get_section(section: str) -> str:
    """Get one resume section's YAML content.

    Args:
        section: Section name — one of summary, experience, projects, skills,
            education, languages (see list_sections).
    """
    text = content.section_yaml(section)
    if text is None:
        return f"Unknown section '{section}'. Available: {', '.join(content.sections())}"
    return text


@mcp.tool(annotations=config.READ)
def get_contact() -> dict[str, str]:
    """Contact details: name, title, location, phone, email, github, linkedin, homepage."""
    return content.contact()


@mcp.tool(annotations=config.READ)
def resume_status() -> ResumeStatus:
    """Build status: version, whether the PDF exists, and if it's stale
    (any source/*.yml newer than the built PDF — if so, run build_resume)."""
    pdf = config.DIST_DIR / "resume.pdf"
    built = pdf.exists()
    stale_sources: list[str] = []
    if built:
        pdf_mtime = pdf.stat().st_mtime
        stale_sources = [
            p.name for p in content.sections().values() if p.stat().st_mtime > pdf_mtime
        ]
    return ResumeStatus(
        version=content.version(),
        repo=str(config.REPO_ROOT),
        pdf_path=str(pdf),
        pdf_built=built,
        stale=not built or bool(stale_sources),
        stale_sources=stale_sources,
    )


# ── flow tools ───────────────────────────────────────────────────────────────

@mcp.tool(annotations=config.BUILD)
def build_resume() -> str:
    """Rebuild the PDF: generate TeX from source/*.yml and compile with XeLaTeX.

    Writes dist/resume.pdf (and a versioned copy). Takes ~10-30s.
    """
    code, output = runner.run([runner.python(), str(config.SCRIPTS_DIR / "build.py")])
    pdf = config.DIST_DIR / "resume.pdf"
    if code == 0 and pdf.exists():
        return f"Build succeeded: {pdf}\n\n{output[-2000:]}"
    return f"Build FAILED (exit {code}):\n\n{output[-config.MAX_BUILD_TAIL :]}"


@mcp.tool(annotations=config.BUILD)
def ats_health_check(threshold: float = 70.0) -> AtsResult:
    """Run the standalone ATS health check on the built resume PDF
    (sections, contact, dates, bullets, skills, summary, quantification, grammar).
    Builds the PDF first if it is missing.

    Args:
        threshold: Minimum passing score, 0-100 (default 70).
    """
    threshold = clamp_threshold(threshold)
    code, output = runner.run(
        [
            runner.python(),
            str(config.SCRIPTS_DIR / "ats_check.py"),
            "--no-color",
            "--threshold",
            str(threshold),
        ]
    )
    return AtsResult(
        passed=code == 0,
        score=overall_score(output),
        threshold=threshold,
        report=_truncated_report(output),
    )


@mcp.tool(annotations=config.LLM)
def ats_match_jd(jd: str, threshold: float = 70.0, no_llm: bool = False) -> AtsResult:
    """Score the resume against a job description (keyword match, title,
    experience, education) and get bullet-rewrite suggestions.

    Args:
        jd: The job description — either raw pasted text, or the name of a
            saved JD from list_job_descriptions (e.g. 'upwork-senior-frontend').
        threshold: Minimum passing score, 0-100 (default 70).
        no_llm: Force the local NLP backend even if a Groq API key is configured.
    """
    if not jd.strip():
        raise ValueError("jd is empty — pass JD text or a saved JD name.")
    if len(jd) > config.MAX_JD_CHARS:
        raise ValueError(f"jd is too large ({len(jd)} chars; max {config.MAX_JD_CHARS}).")
    threshold = clamp_threshold(threshold)

    saved = content.resolve_saved_jd(jd)
    if saved is not None:
        jd_path, cleanup = saved, False
    else:
        tmp = tempfile.NamedTemporaryFile(
            "w", suffix=".txt", delete=False, encoding="utf-8"
        )
        tmp.write(jd)
        tmp.close()
        jd_path, cleanup = Path(tmp.name), True

    args = [
        runner.python(),
        str(config.SCRIPTS_DIR / "ats_check.py"),
        "--no-color",
        "--jd",
        str(jd_path),
        "--threshold",
        str(threshold),
    ]
    if no_llm:
        args.append("--no-llm")
    try:
        code, output = runner.run(args)
    finally:
        if cleanup:
            jd_path.unlink(missing_ok=True)
    return AtsResult(
        passed=code == 0,
        score=overall_score(output),
        threshold=threshold,
        report=_truncated_report(output),
    )


# ── write-back tools ─────────────────────────────────────────────────────────

@mcp.tool(annotations=config.ADD)
def add_project(
    name: str,
    subtitle: str,
    items: list[str],
    tech: list[str],
    url: str = "",
    url_label: str = "",
) -> str:
    """Add a new project to the resume (top of the projects section).

    Use this to capture work from whatever repo you're currently in: summarize
    the project and the user's actual contribution (check git log/blame for
    their commits), draft resume-style bullets, get the user's approval, then
    call this. Append-only — it refuses names that already exist. Follow up
    with build_resume to regenerate the PDF.

    Args:
        name: Project name, e.g. 'Folia'.
        subtitle: Short descriptor, e.g. 'YAML → LaTeX resume pipeline'.
        items: 2-4 resume bullets. Past-tense action verb first; wrap key tech
            in [[double brackets]] for bold; include honest metrics.
        tech: Technology list, e.g. ['Python', 'LaTeX', 'GitHub Actions'].
        url: Optional project URL (must be http/https).
        url_label: Optional display label for the URL (defaults to the bare domain/path).
    """
    return editor.add_project(name, subtitle, items, tech, url, url_label)


@mcp.tool(annotations=config.ADD)
def add_experience(
    title: str,
    company: str,
    location: str,
    dates: str,
    items: list[str],
) -> str:
    """Add a new position to the resume (top of the experience section).

    For paid roles/engagements; use add_project for side or open-source work.
    Same flow: summarize the user's contribution from the repo they're in,
    draft bullets, confirm with the user, then call this. Append-only — it
    refuses title+company pairs that already exist. Follow up with
    build_resume to regenerate the PDF.

    Args:
        title: Role title, e.g. 'Senior Software Engineer'.
        company: Company or client name.
        location: e.g. 'Remote - Dhaka, Bangladesh'.
        dates: e.g. 'January 2025 - Present' (month-name format, matching the file).
        items: 2-6 resume bullets. Past-tense action verb first; wrap key tech
            in [[double brackets]] for bold; include honest metrics.
    """
    return editor.add_experience(title, company, location, dates, items)


@mcp.tool(annotations=config.READ)
def list_job_descriptions() -> str:
    """List job descriptions saved in the jd/ directory, usable by name with ats_match_jd."""
    files = sorted(config.JD_DIR.glob("*.txt")) if config.JD_DIR.exists() else []
    if not files:
        return "No saved job descriptions in jd/."
    return "Saved JDs (pass the name to ats_match_jd):\n" + "\n".join(
        f"- {p.stem}" for p in files
    )


@mcp.tool(annotations=config.WRITE)
def save_job_description(name: str, text: str) -> str:
    """Save a job description to jd/<name>.txt for reuse with ats_match_jd.

    Args:
        name: Filename slug, e.g. 'acme-senior-fullstack'.
        text: The full job description text.
    """
    slug = content.slugify(name)
    if not slug:
        return "Invalid name — use letters, digits, and dashes."
    if not text.strip():
        return "Refusing to save an empty job description."
    if len(text) > config.MAX_JD_CHARS:
        return f"JD too large ({len(text)} chars; max {config.MAX_JD_CHARS})."
    config.JD_DIR.mkdir(exist_ok=True)
    path = config.JD_DIR / f"{slug}.txt"
    existed = path.exists()
    path.write_text(text, encoding="utf-8")
    note = " (overwrote existing)" if existed else ""
    return (
        f"Saved {path.relative_to(config.REPO_ROOT)}{note} — "
        f"match it with ats_match_jd('{slug}')."
    )
