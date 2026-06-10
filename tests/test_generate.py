from __future__ import annotations

import generate


def test_escape_special_characters():
    assert generate.latex_escape("50% & #1 _x_") == "50\\% \\& \\#1 \\_x\\_"
    assert generate.latex_escape("$100") == "\\$100"
    assert generate.latex_escape("{a}") == "\\{a\\}"


def test_bold_markers_become_textbf():
    assert generate.latex_escape("[[bold]] rest") == "\\textbf{bold} rest"


def test_specials_inside_bold_are_escaped():
    assert generate.latex_escape("[[100%]]") == "\\textbf{100\\%}"


def test_multiple_bold_segments():
    out = generate.latex_escape("a [[b]] c [[d]]")
    assert out == "a \\textbf{b} c \\textbf{d}"


def test_gen_summary():
    tex = generate.gen_summary({"summary": "Hello world"})
    assert "\\cvsection{ABOUT ME}" in tex
    assert "Hello world" in tex


def test_gen_summary_empty_returns_none():
    assert generate.gen_summary(None) is None
    assert generate.gen_summary({}) is None


def test_gen_experience_with_internships():
    data = {
        "positions": [
            {"title": "Engineer", "company": "Acme", "location": "X",
             "dates": "2020 - 2021", "items": ["Did [[things]]"]},
        ],
        "internships": [
            {"title": "Intern", "company": "Initech", "location": "Y",
             "dates": "2019 - 2020", "items": ["Learned"]},
        ],
    }
    tex = generate.gen_experience(data)
    assert "PROFESSIONAL EXPERIENCE" in tex
    assert "INTERNSHIPS" in tex
    assert "\\textbf{things}" in tex


def test_gen_projects_url_rendering():
    data = {
        "projects": [
            {"name": "folia", "subtitle": "CV gen", "items": ["x"],
             "tech": ["Python"], "url": "https://example.com", "urlLabel": "example"},
        ]
    }
    tex = generate.gen_projects(data)
    assert "\\href{https://example.com}{example}" in tex


def test_gen_skills():
    data = {"skills": [{"category": "Langs", "items": ["A", "B"]}]}
    tex = generate.gen_skills(data)
    assert "\\cvskill {Langs} {A, B}" in tex
