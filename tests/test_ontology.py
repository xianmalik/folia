from __future__ import annotations

from ats import ontology as ont


def test_normalize_basic():
    assert ont.normalize("  Node.js ") == "nodejs"
    assert ont.normalize("CI/CD") == "cicd"
    assert ont.normalize("REST   API") == "rest api"


def test_normalize_preserves_special_languages():
    assert ont.normalize("C++") == "cpp"
    assert ont.normalize("c#") == "csharp"
    assert ont.normalize("F#") == "fsharp"


def test_expand_skills_transitive():
    ontology = {
        "implies": {"React": ["JavaScript"], "JavaScript": ["Programming"]},
        "aliases": {"reactjs": "React"},
    }
    expanded = ont.expand_skills(["ReactJS"], ontology)
    assert {"React", "JavaScript", "Programming"} <= expanded


def test_expand_skills_handles_cycles():
    ontology = {
        "implies": {"A": ["B"], "B": ["A"]},
        "aliases": {},
    }
    expanded = ont.expand_skills(["A"], ontology)
    assert expanded == {"A", "B"}


def test_resolve_alias():
    ontology = {"implies": {}, "aliases": {"nodejs": "Node.js"}}
    assert ont.resolve_alias("node.js", ontology) == "Node.js"
    assert ont.resolve_alias("unknown-skill", ontology) == "unknown-skill"


def test_real_ontology_loads_and_has_required_keys():
    data = ont.load_ontology()
    assert "implies" in data and "aliases" in data
