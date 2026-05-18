#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import deque
from pathlib import Path

_ONTOLOGY_PATH = Path(__file__).parent / "ontology.json"
_CACHED: dict | None = None


def load_ontology() -> dict:
    global _CACHED
    if _CACHED is None:
        _CACHED = json.loads(_ONTOLOGY_PATH.read_text(encoding="utf-8"))
    return _CACHED


def normalize(term: str) -> str:
    """Lowercase, collapse dots/hyphens/slashes, strip non-word chars, trim."""
    s = term.lower().strip()
    s = re.sub(r"[.\-/+]", "", s)
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def expand_skills(skill_list: list[str], ontology: dict) -> set[str]:
    """BFS transitive expansion: return all skills + everything they imply."""
    implies: dict[str, list[str]] = ontology.get("implies", {})
    aliases: dict[str, str] = ontology.get("aliases", {})

    norm_implies: dict[str, list[str]] = {normalize(k): v for k, v in implies.items()}

    result: set[str] = set()
    queue: deque[str] = deque()

    for skill in skill_list:
        canonical = aliases.get(normalize(skill), skill)
        if canonical not in result:
            result.add(canonical)
            queue.append(canonical)

    while queue:
        current = queue.popleft()
        for child in norm_implies.get(normalize(current), []):
            if child not in result:
                result.add(child)
                queue.append(child)

    return result


def resolve_alias(term: str, ontology: dict) -> str:
    aliases: dict[str, str] = ontology.get("aliases", {})
    return aliases.get(normalize(term), term)
