"""Unit tests for the MCP server's helper modules (mcp/folia/)."""
import sys
from pathlib import Path

MCP_DIR = str(Path(__file__).resolve().parents[1] / "mcp")
if MCP_DIR not in sys.path:
    sys.path.insert(0, MCP_DIR)

import pytest  # noqa: E402
import yaml  # noqa: E402

from folia import config, content, editor  # noqa: E402
from folia.models import clamp_threshold, overall_score  # noqa: E402


class TestOverallScore:
    def test_prefers_overall_line(self):
        report = "Keyword Match  64.2/100\nOverall CV Score  90.6/100  [A+]"
        assert overall_score(report) == 90.6

    def test_falls_back_to_last_score(self):
        report = "Keyword Match  64.2/100\nTitle Match  82.0/100"
        assert overall_score(report) == 82.0

    def test_no_score_returns_none(self):
        assert overall_score("no scores here") is None


class TestClampThreshold:
    def test_in_range_unchanged(self):
        assert clamp_threshold(70.0) == 70.0

    def test_clamps_out_of_range(self):
        assert clamp_threshold(-5.0) == 0.0
        assert clamp_threshold(250.0) == 100.0


class TestSlugify:
    def test_normalizes(self):
        assert content.slugify("Acme — Senior Fullstack!") == "acme-senior-fullstack"

    def test_rejects_garbage(self):
        assert content.slugify("///") == ""

    def test_caps_length(self):
        assert len(content.slugify("x" * 500)) <= config.MAX_NAME_CHARS


class TestResolveSavedJd:
    def test_multiline_is_raw_text(self):
        assert content.resolve_saved_jd("Senior role\nRequirements: ...") is None

    def test_traversal_is_blocked(self):
        assert content.resolve_saved_jd("../.env") is None
        assert content.resolve_saved_jd("/etc/hosts") is None

    def test_missing_name_is_none(self):
        assert content.resolve_saved_jd("no-such-jd-file") is None

    def test_saved_jd_resolves(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "JD_DIR", tmp_path)
        (tmp_path / "acme.txt").write_text("JD text")
        assert content.resolve_saved_jd("acme") == tmp_path / "acme.txt"
        assert content.resolve_saved_jd("acme.txt") == tmp_path / "acme.txt"


@pytest.fixture
def source_dir(tmp_path, monkeypatch):
    """A scratch source/ with minimal projects and experience files."""
    (tmp_path / "20-projects.yml").write_text(
        "projects:\n"
        "  - name: Existing\n"
        "    subtitle: Already here\n"
        "    items:\n"
        "      - Did a thing.\n"
        "\n"
        "#   - name: Commented Out\n"
        "#     subtitle: keep me\n",
        encoding="utf-8",
    )
    (tmp_path / "10-experience.yml").write_text(
        "positions:\n"
        "  - title: Software Engineer\n"
        "    company: Acme\n"
        "    location: Remote\n"
        "    dates: January 2020 - Present\n"
        "    items:\n"
        "      - Built things.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "SOURCE_DIR", tmp_path)
    return tmp_path


class TestAddProject:
    def test_inserts_at_top_and_stays_parseable(self, source_dir):
        editor.add_project(
            "Folia MCP",
            "Resume hub over MCP",
            ["Built an [[MCP]] server exposing the CV to agents."],
            ["Python", "MCP"],
            url="https://github.com/xianmalik/folia",
        )
        text = (source_dir / "20-projects.yml").read_text()
        data = yaml.safe_load(text)
        assert [p["name"] for p in data["projects"]] == ["Folia MCP", "Existing"]
        assert data["projects"][0]["urlLabel"] == "github.com/xianmalik/folia"
        assert "#   - name: Commented Out" in text  # comments preserved

    def test_duplicate_name_rejected(self, source_dir):
        with pytest.raises(ValueError, match="already exists"):
            editor.add_project("existing", "dup", ["Bullet."], [])

    def test_bad_url_rejected(self, source_dir):
        with pytest.raises(ValueError, match="http"):
            editor.add_project("New", "sub", ["Bullet."], [], url="ftp://x")

    def test_empty_items_rejected(self, source_dir):
        with pytest.raises(ValueError, match="at least one"):
            editor.add_project("New", "sub", ["   "], [])


class TestAddExperience:
    def test_inserts_and_parses(self, source_dir):
        editor.add_experience(
            "Staff Engineer", "Initech", "Remote", "May 2026 - Present", ["Led [[X]]."]
        )
        data = yaml.safe_load((source_dir / "10-experience.yml").read_text())
        assert data["positions"][0]["company"] == "Initech"
        assert len(data["positions"]) == 2

    def test_same_title_new_company_allowed(self, source_dir):
        editor.add_experience(
            "Software Engineer", "Initech", "Remote", "May 2026 - Present", ["Did Y."]
        )
        data = yaml.safe_load((source_dir / "10-experience.yml").read_text())
        assert len(data["positions"]) == 2

    def test_same_title_same_company_rejected(self, source_dir):
        with pytest.raises(ValueError, match="already exists"):
            editor.add_experience(
                "software engineer", "ACME", "Remote", "May 2026 - Present", ["Dup."]
            )

    def test_missing_field_rejected(self, source_dir):
        with pytest.raises(ValueError, match="dates"):
            editor.add_experience("Dev", "Initech", "Remote", "  ", ["Bullet."])


class TestContent:
    def test_sections_present_and_ordered(self):
        names = list(content.sections())
        assert names[0] == "summary"
        assert "experience" in names and "skills" in names

    def test_section_yaml_unknown_is_none(self):
        assert content.section_yaml("bogus") is None

    def test_contact_has_core_fields(self):
        info = content.contact()
        assert "@" in info.get("email", "")
        assert info.get("name")

    def test_resume_markdown_contains_all_sections(self):
        doc = content.resume_markdown()
        assert doc.startswith("# Contact")
        for name in content.sections():
            assert f"# Section: {name}" in doc
