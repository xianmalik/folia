#!/usr/bin/env python3
"""
Validate source/*.yml files against expected schemas.
Exits non-zero if any validation error is found.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "source"

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
NC = "\033[0m"


def load(filename: str, errors: list[str], data_dir: Path = DATA_DIR) -> dict | None:
    path = data_dir / filename
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        errors.append(f"{filename}: YAML parse error — {e}")
        return None


def require_list(
    data: dict | None,
    filename: str,
    key: str,
    item_keys: list[str],
    errors: list[str],
) -> None:
    if data is None:
        return
    items = data.get(key)
    if not isinstance(items, list):
        errors.append(f"{filename}: '{key}' must be a list")
        return
    for i, item in enumerate(items):
        for k in item_keys:
            if not item.get(k):
                errors.append(f"{filename}: {key}[{i}] missing required field '{k}'")


def collect_errors(data_dir: Path = DATA_DIR) -> list[str]:
    """Validate every source YAML file; return all errors found."""
    errors: list[str] = []

    summary = load("00-summary.yml", errors, data_dir)
    if summary is not None and not summary.get("summary"):
        errors.append("00-summary.yml: missing required field 'summary'")

    experience = load("10-experience.yml", errors, data_dir)
    require_list(experience, "10-experience.yml", "positions",
                 ["title", "company", "location", "dates"], errors)
    if experience and isinstance(experience.get("internships"), list):
        require_list(experience, "10-experience.yml", "internships",
                     ["title", "company", "location", "dates"], errors)

    projects = load("20-projects.yml", errors, data_dir)
    require_list(projects, "20-projects.yml", "projects",
                 ["name", "subtitle", "items", "tech"], errors)

    skills = load("30-skills.yml", errors, data_dir)
    require_list(skills, "30-skills.yml", "skills", ["category", "items"], errors)

    education = load("40-education.yml", errors, data_dir)
    require_list(education, "40-education.yml", "schools",
                 ["degree", "institution", "location", "dates"], errors)

    languages = load("50-languages.yml", errors, data_dir)
    require_list(languages, "50-languages.yml", "languages", ["name", "level"], errors)

    return errors


def main() -> int:
    if yaml is None:
        print("PyYAML not installed. Run: pip install -r requirements.txt")
        return 1

    errors = collect_errors()
    if errors:
        print(f"{RED}Validation failed:{NC}")
        for e in errors:
            print(f"  {YELLOW}✗{NC} {e}")
        return 1

    print(f"{GREEN}✓ All data files valid{NC}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
