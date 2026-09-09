"""Resource registrations: the resume as addressable content."""
from __future__ import annotations

from . import content
from .app import mcp


@mcp.resource("resume://full")
def resume_full() -> str:
    """The complete resume: contact info plus all section YAML."""
    return content.resume_markdown()


@mcp.resource("resume://section/{name}")
def resume_section(name: str) -> str:
    """A single resume section's YAML (summary, experience, projects, skills, education, languages)."""
    text = content.section_yaml(name)
    if text is None:
        return f"Unknown section '{name}'. Available: {', '.join(content.sections())}"
    return text
