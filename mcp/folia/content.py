"""Read-side helpers: resume sections, contact info, versions, saved JDs."""
from __future__ import annotations

import re
from pathlib import Path

from . import config


def sections() -> dict[str, Path]:
    """Map section name (e.g. 'experience') to its YAML file, in render order."""
    result: dict[str, Path] = {}
    for path in sorted(config.SOURCE_DIR.glob("*.yml")):
        name = re.sub(r"^\d+-", "", path.stem)
        result[name] = path
    return result


def section_yaml(section: str) -> str | None:
    """One section's YAML content, or None if the name is unknown."""
    path = sections().get(section.strip().lower())
    if path is None:
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def contact() -> dict[str, str]:
    """Parse the personal-information block from core/resume.tex."""
    try:
        text = config.RESUME_TEX.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    fields = {}
    name = re.search(r"\\name\{(.*?)\}\{(.*?)\}", text)
    if name:
        fields["name"] = f"{name.group(1)} {name.group(2)}"
    for key in ("position", "address", "mobile", "email", "github", "linkedin", "homepage"):
        match = re.search(r"\\" + key + r"\{(.*?)\}", text)
        if match:
            fields[key] = match.group(1)
    return fields


def version() -> str:
    version_file = config.REPO_ROOT / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


def resume_markdown() -> str:
    """Contact details plus every section's YAML, as one markdown document."""
    parts = ["# Contact"]
    parts.extend(f"{key}: {value}" for key, value in contact().items())
    for name, path in sections().items():
        parts.append(f"\n# Section: {name} ({path.name})")
        parts.append(path.read_text(encoding="utf-8", errors="replace").strip())
    return "\n".join(parts)


def slugify(name: str) -> str:
    """Filename slug for saved JDs: lowercase letters, digits, dashes."""
    slug = re.sub(r"[^a-z0-9-]+", "-", name.strip().lower()).strip("-")
    return slug[: config.MAX_NAME_CHARS]


def resolve_saved_jd(jd: str) -> Path | None:
    """Resolve a saved-JD name to its file inside jd/, or None.

    Returns None for multiline input (raw JD text) and for anything that
    escapes the jd/ directory (absolute paths, ../ traversal).
    """
    if "\n" in jd.strip():
        return None
    candidate = (config.JD_DIR / (jd if jd.endswith(".txt") else f"{jd}.txt")).resolve()
    if not candidate.is_relative_to(config.JD_DIR.resolve()):
        return None
    return candidate if candidate.exists() else None
