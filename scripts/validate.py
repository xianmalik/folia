#!/usr/bin/env python3
"""
Validate data/*.yml files against expected schemas.
Exits non-zero on the first validation error.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
NC = "\033[0m"

errors: list[str] = []


def load(filename: str) -> dict | None:
    path = DATA_DIR / filename
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        errors.append(f"{filename}: YAML parse error — {e}")
        return None


def require_list(data: dict | None, filename: str, key: str, item_keys: list[str]) -> None:
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


# 00-summary.yml
summary = load("00-summary.yml")
if summary is not None and not summary.get("summary"):
    errors.append("00-summary.yml: missing required field 'summary'")

# 10-experience.yml
experience = load("10-experience.yml")
require_list(experience, "10-experience.yml", "positions",
             ["title", "company", "location", "dates"])
if experience and isinstance(experience.get("internships"), list):
    require_list(experience, "10-experience.yml", "internships",
                 ["title", "company", "location", "dates"])

# 20-education.yml
education = load("20-education.yml")
require_list(education, "20-education.yml", "schools",
             ["degree", "institution", "location", "dates"])

# 30-projects.yml
projects = load("30-projects.yml")
require_list(projects, "30-projects.yml", "projects", ["name", "subtitle", "items", "tech"])

# 40-skills.yml
skills = load("40-skills.yml")
require_list(skills, "40-skills.yml", "skills", ["category", "items"])

# 50-languages.yml
languages = load("50-languages.yml")
require_list(languages, "50-languages.yml", "languages", ["name", "level"])

if errors:
    print(f"{RED}Validation failed:{NC}")
    for e in errors:
        print(f"  {YELLOW}✗{NC} {e}")
    sys.exit(1)

print(f"{GREEN}✓ All data files valid{NC}")
sys.exit(0)
