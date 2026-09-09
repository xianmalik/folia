"""Prompt registrations: canonical resume workflows."""
from __future__ import annotations

from .app import mcp


@mcp.prompt(title="Tailor resume to a job description")
def tailor_resume(jd_text: str) -> str:
    """Score the CV against a JD and propose concrete source/*.yml edits."""
    return (
        "Tailor my resume to the job description below.\n\n"
        "1. Call ats_match_jd with the JD to get the current score, missing "
        "keywords, and bullet-rewrite suggestions.\n"
        "2. Call get_resume to see the full current content.\n"
        "3. Propose concrete edits to the YAML files in source/ — reworded "
        "bullets, added skills, summary tweaks — that close the gaps honestly "
        "(never invent experience I don't have). Use [[text]] for bold.\n"
        "4. After I approve edits, rebuild with build_resume and re-run "
        "ats_match_jd to confirm the score improved.\n\n"
        f"Job description:\n{jd_text}"
    )


@mcp.prompt(title="Write a cover letter")
def cover_letter(company: str, role: str, jd_text: str = "") -> str:
    """Draft a cover letter grounded in the resume content."""
    jd_block = f"\n\nJob description:\n{jd_text}" if jd_text.strip() else ""
    return (
        f"Write a cover letter for the {role} position at {company}.\n\n"
        "Call get_resume first and ground every claim in my actual experience, "
        "projects, and skills — no invented accomplishments. Keep it under 350 "
        "words, specific and direct, no clichés ('passionate', 'fast-paced'). "
        "Match the strongest overlaps between my background and what the role "
        f"needs.{jd_block}"
    )


@mcp.prompt(title="Add current project to resume")
def log_project_work(kind: str = "project") -> str:
    """Capture the current repo and the user's contribution as a resume entry."""
    target = "add_experience" if kind.strip().lower() in ("work", "experience", "job") else "add_project"
    return (
        "Add the project in the current working directory to my resume.\n\n"
        "1. Get the gist: read the README, manifest (package.json / pyproject / "
        "etc.), and top-level structure to understand what this project is and "
        "what it's built with.\n"
        "2. Find MY contribution, not the whole team's: check git log/shortlog "
        "for my commits (git config user.email, or mzubayeruh@gmail.com) and "
        "what those commits actually changed.\n"
        "3. Read get_section('projects') to match the house style, then draft "
        "the entry: name, one-line subtitle, 2-4 bullets (past-tense action "
        "verb first, [[tech]] bolded, honest metrics only — never inflate), "
        "and the tech list.\n"
        "4. Show me the draft and wait for my approval.\n"
        f"5. On approval, call {target}, then build_resume, and report the "
        "resume_status.\n"
    )


@mcp.prompt(title="Write a portfolio bio")
def portfolio_bio(tone: str = "professional", length: str = "short") -> str:
    """Generate an about/bio blurb from the resume for a website or profile."""
    return (
        f"Write a {length}, {tone} bio for my portfolio site or profile page.\n\n"
        "Call get_resume and get_contact for the raw material. Write in first "
        "person, lead with what I build (not job titles), and mention only the "
        "technologies that appear in my resume."
    )
