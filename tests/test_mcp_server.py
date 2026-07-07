"""Unit tests for the MCP server's helper modules (mcp/folia/)."""
import sys
from pathlib import Path

MCP_DIR = str(Path(__file__).resolve().parents[1] / "mcp")
if MCP_DIR not in sys.path:
    sys.path.insert(0, MCP_DIR)

from folia import config, content  # noqa: E402
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
