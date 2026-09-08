"""The release-time changelog assembler: fragments land in [Unreleased] and nowhere else."""

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release" / "assemble_changelog.py"
spec = importlib.util.spec_from_file_location("assemble_changelog", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

CHANGELOG = """# Changelog

## [Unreleased]

### Fixed

- **Existing unreleased fix.** Detail.

## [5.56.0] - 2026-09-02

### Fixed

- **Shipped fix.** Must not move.
"""


def frag(section, *bullets):
    return {section: [(Path(f"{i}.{section.lower()}.md"), f"- {b}") for i, b in enumerate(bullets)]}


def unreleased(text):
    start = text.index("## [Unreleased]")
    return text[start:text.index("## [5.56.0]")]


def test_fragment_goes_to_top_of_existing_section():
    out = mod.merge_into_unreleased(CHANGELOG, frag("Fixed", "**New fix.** Detail."))
    block = unreleased(out)
    assert block.index("**New fix.**") < block.index("**Existing unreleased fix.**")
    # The dated section is byte-identical.
    assert out[out.index("## [5.56.0]"):] == CHANGELOG[CHANGELOG.index("## [5.56.0]"):]


def test_missing_section_is_created_in_canonical_order():
    fragments = {**frag("Added", "**A feature.**"), **frag("Performance", "**Faster.**")}
    block = unreleased(mod.merge_into_unreleased(CHANGELOG, fragments))
    assert block.index("### Added") < block.index("### Fixed") < block.index("### Performance")
    assert block.count("### Fixed") == 1


def test_empty_unreleased_section_gets_heading_and_single_trailing_blank():
    text = CHANGELOG.replace("### Fixed\n\n- **Existing unreleased fix.** Detail.\n\n## [5.56.0]", "## [5.56.0]")
    out = mod.merge_into_unreleased(text, frag("Fixed", "**Only fix.**"))
    assert "## [Unreleased]\n\n### Fixed\n\n- **Only fix.**\n\n## [5.56.0]" in out


def test_load_fragments_rejects_bad_names_and_empty_bodies(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "FRAGMENT_DIR", tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    (tmp_path / "abcd.fixed.md").write_text("**Good.** Body.\n")
    (tmp_path / "wxyz.md").write_text("no section")
    with pytest.raises(SystemExit, match="wxyz.md"):
        mod.load_fragments()
    (tmp_path / "wxyz.md").unlink()
    (tmp_path / "efgh.fixed.md").write_text("   \n")
    with pytest.raises(SystemExit, match="efgh.fixed.md \\(empty\\)"):
        mod.load_fragments()
    (tmp_path / "efgh.fixed.md").write_text("**Long.** " + "x" * mod.MAX_FRAGMENT_CHARS)
    with pytest.raises(SystemExit, match="efgh.fixed.md \\(51\\d chars, limit 500\\)"):
        mod.load_fragments()


def test_load_fragments_strips_optional_dash_and_ignores_readme(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "FRAGMENT_DIR", tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    (tmp_path / "README.md").write_text("# how to")
    (tmp_path / "abcd.fixed.md").write_text("- **Dashed.** Body.\n")
    (tmp_path / "efgh.added.md").write_text("**Plain.** Body.\n")
    got = mod.load_fragments()
    assert [b for _, b in got["Fixed"]] == ["- **Dashed.** Body."]
    assert [b for _, b in got["Added"]] == ["- **Plain.** Body."]
