"""Write-side helpers: insert new entries into the resume source YAML.

Entries are inserted textually (right after the top-level list key) rather
than by round-tripping the whole file through PyYAML — that preserves the
existing formatting and the commented-out entries the source files carry.
The composed file is parsed before being written, so an insertion can never
leave a source file syntactically broken.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from . import config

MAX_ITEMS = 10
MAX_ITEM_CHARS = 500
MAX_FIELD_CHARS = 200
MAX_TECH = 20


class _IndentDumper(yaml.Dumper):
    """Indent block sequences under their key, matching the source files."""

    def increase_indent(self, flow: bool = False, indentless: bool = False):
        return super().increase_indent(flow, False)


def _validate_common(name: str, items: list[str]) -> None:
    if not name.strip():
        raise ValueError("name must not be empty.")
    if len(name) > MAX_FIELD_CHARS:
        raise ValueError(f"name is too long (max {MAX_FIELD_CHARS} chars).")
    cleaned = [i.strip() for i in items if i.strip()]
    if not cleaned:
        raise ValueError("items must contain at least one bullet.")
    if len(cleaned) > MAX_ITEMS:
        raise ValueError(f"too many bullets ({len(cleaned)}; max {MAX_ITEMS}).")
    for item in cleaned:
        if len(item) > MAX_ITEM_CHARS:
            raise ValueError(f"bullet too long (max {MAX_ITEM_CHARS} chars): {item[:60]}…")


def _entry_block(entry: dict) -> str:
    """Render one entry as an indented YAML list item block."""
    text = yaml.dump(
        [entry],
        Dumper=_IndentDumper,
        sort_keys=False,
        allow_unicode=True,
        width=100_000,  # keep bullets on one line, like the existing files
        default_flow_style=False,
    )
    return "\n".join(f"  {line}" if line else "" for line in text.rstrip().splitlines())


def _identity(entry: dict, keys: tuple[str, ...]) -> str:
    """Case-insensitive identity of an entry, e.g. name, or title+company."""
    return "|".join(str(entry.get(k, "")).strip().lower() for k in keys)


def _insert_entry(path: Path, list_key: str, id_keys: tuple[str, ...], entry: dict) -> None:
    """Insert *entry* at the top of the *list_key* list in *path*.

    Raises ValueError on duplicate identity (*id_keys*), a missing list key,
    or if the composed file fails to parse.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace")) or {}
    existing = [e for e in (data.get(list_key) or []) if isinstance(e, dict)]
    if _identity(entry, id_keys) in (_identity(e, id_keys) for e in existing):
        label = ", ".join(str(entry.get(k, "")) for k in id_keys)
        raise ValueError(
            f"'{label}' already exists in {path.name}. Edit the file directly to "
            "update an existing entry — this tool only adds new ones."
        )

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    try:
        key_index = next(
            i for i, ln in enumerate(lines) if ln.rstrip() == f"{list_key}:"
        )
    except StopIteration:
        raise ValueError(f"could not find the top-level '{list_key}:' key in {path.name}.")

    block = _entry_block(entry)
    composed = lines[: key_index + 1] + block.splitlines() + [""] + lines[key_index + 1 :]
    new_text = "\n".join(composed).rstrip() + "\n"

    parsed = yaml.safe_load(new_text)
    entries = (parsed or {}).get(list_key) or []
    if len(entries) != len(existing) + 1:
        raise ValueError("insertion produced an unexpected structure — aborted, file unchanged.")

    path.write_text(new_text, encoding="utf-8")


def add_project(
    name: str,
    subtitle: str,
    items: list[str],
    tech: list[str],
    url: str = "",
    url_label: str = "",
) -> str:
    """Insert a new project at the top of source/20-projects.yml."""
    _validate_common(name, items)
    tech = [t.strip() for t in tech if t.strip()]
    if len(tech) > MAX_TECH:
        raise ValueError(f"too many tech entries ({len(tech)}; max {MAX_TECH}).")
    if url and not url.startswith(("http://", "https://")):
        raise ValueError("url must start with http:// or https://")

    entry: dict = {
        "name": name.strip(),
        "subtitle": subtitle.strip(),
        "items": [i.strip() for i in items if i.strip()],
    }
    if tech:
        entry["tech"] = tech
    if url:
        entry["url"] = url.strip()
        entry["urlLabel"] = url_label.strip() or url.strip().split("://", 1)[1].rstrip("/")

    path = config.SOURCE_DIR / "20-projects.yml"
    _insert_entry(path, "projects", ("name",), entry)
    return f"Added project '{entry['name']}' to {path.name}."


def add_experience(
    title: str,
    company: str,
    location: str,
    dates: str,
    items: list[str],
) -> str:
    """Insert a new position at the top of source/10-experience.yml."""
    _validate_common(title, items)
    for field, value in (("company", company), ("location", location), ("dates", dates)):
        if not value.strip():
            raise ValueError(f"{field} must not be empty.")
        if len(value) > MAX_FIELD_CHARS:
            raise ValueError(f"{field} is too long (max {MAX_FIELD_CHARS} chars).")

    entry = {
        "title": title.strip(),
        "company": company.strip(),
        "location": location.strip(),
        "dates": dates.strip(),
        "items": [i.strip() for i in items if i.strip()],
    }
    path = config.SOURCE_DIR / "10-experience.yml"
    _insert_entry(path, "positions", ("title", "company"), entry)
    return f"Added position '{entry['title']}' at {entry['company']} to {path.name}."
