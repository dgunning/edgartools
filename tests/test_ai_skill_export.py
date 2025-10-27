"""
Tests for AI skill export functionality.

Tests the ability to export EdgarTools skills in Claude Desktop format
and the extensibility framework for external skills.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import zipfile


@pytest.mark.fast
def test_sec_analysis_skill_exists():
    """Test that the SEC Analysis skill is available."""
    from edgar.ai.skills.sec_analysis import sec_analysis_skill

    assert sec_analysis_skill is not None
    assert sec_analysis_skill.name == "SEC Filing Analysis"
    assert len(sec_analysis_skill.description) > 0
    assert sec_analysis_skill.content_dir.exists()


@pytest.mark.fast
def test_skill_has_markdown_files():
    """Test that skill content directory contains required markdown files."""
    from edgar.ai.skills.sec_analysis import sec_analysis_skill

    content_dir = sec_analysis_skill.content_dir

    # Check for main skill file
    skill_md = content_dir / "skill.md"
    assert skill_md.exists(), "skill.md should exist"

    # Check for supporting files
    readme = content_dir / "readme.md"
    objects_md = content_dir / "objects.md"
    workflows_md = content_dir / "workflows.md"

    # At least skill.md should exist
    assert skill_md.exists()


@pytest.mark.fast
def test_skill_markdown_has_frontmatter():
    """Test that skill.md has valid YAML frontmatter."""
    from edgar.ai.skills.sec_analysis import sec_analysis_skill

    skill_md = sec_analysis_skill.content_dir / "skill.md"
    content = skill_md.read_text(encoding='utf-8')

    # Check frontmatter structure
    assert content.startswith('---'), "skill.md should start with ---"

    # Extract frontmatter
    parts = content.split('---', 2)
    assert len(parts) >= 3, "skill.md should have complete frontmatter"

    frontmatter = parts[1].strip()

    # Check required fields
    assert 'name:' in frontmatter
    assert 'description:' in frontmatter


@pytest.mark.fast
def test_list_skills():
    """Test skill discovery with list_skills()."""
    from edgar.ai import list_skills

    skills = list_skills()

    assert len(skills) > 0, "Should have at least one skill"
    assert any(s.name == "SEC Filing Analysis" for s in skills)


@pytest.mark.fast
def test_get_skill():
    """Test getting specific skill by name."""
    from edgar.ai import get_skill

    skill = get_skill("SEC Filing Analysis")

    assert skill is not None
    assert skill.name == "SEC Filing Analysis"


@pytest.mark.fast
def test_get_skill_not_found():
    """Test that getting non-existent skill raises error."""
    from edgar.ai import get_skill

    with pytest.raises(ValueError, match="not found"):
        get_skill("Non-Existent Skill")


@pytest.mark.fast
def test_export_skill_to_directory():
    """Test exporting skill to a directory."""
    from edgar.ai import sec_analysis_skill, export_skill

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Export skill
        skill_dir = export_skill(sec_analysis_skill, format="claude-desktop", output_dir=output_dir)

        # Check that directory was created
        assert skill_dir.exists()
        assert skill_dir.is_dir()

        # Check that markdown files were copied
        skill_md = skill_dir / "skill.md"
        assert skill_md.exists()

        # Verify content was copied correctly
        content = skill_md.read_text(encoding='utf-8')
        assert content.startswith('---')
        assert 'name:' in content


@pytest.mark.fast
def test_export_skill_default_directory():
    """Test exporting skill to current directory (default)."""
    from edgar.ai import sec_analysis_skill, export_skill

    # Export to current directory
    skill_dir = export_skill(sec_analysis_skill, format="claude-desktop")

    try:
        # Check that directory was created
        assert skill_dir.exists()
        assert skill_dir.is_dir()
        assert skill_dir.name == "sec-filing-analysis"

        # Check files
        skill_md = skill_dir / "skill.md"
        assert skill_md.exists()

    finally:
        # Clean up
        if skill_dir.exists():
            shutil.rmtree(skill_dir)


@pytest.mark.fast
def test_export_skill_validates_frontmatter():
    """Test that export validates YAML frontmatter."""
    from edgar.ai import sec_analysis_skill, export_skill

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # This should succeed with valid frontmatter
        skill_dir = export_skill(sec_analysis_skill, format="claude-desktop", output_dir=output_dir)

        assert skill_dir.exists()


@pytest.mark.fast
def test_export_skill_unknown_format():
    """Test that unknown export format raises error."""
    from edgar.ai import sec_analysis_skill, export_skill

    with pytest.raises(ValueError, match="Unknown export format"):
        export_skill(sec_analysis_skill, format="unknown-format")


@pytest.mark.fast
def test_base_skill_interface():
    """Test BaseSkill abstract class interface."""
    from edgar.ai.skills.base import BaseSkill

    # BaseSkill should be abstract
    with pytest.raises(TypeError):
        BaseSkill()


@pytest.mark.fast
def test_skill_get_helpers():
    """Test that skill provides helper functions."""
    from edgar.ai.skills.sec_analysis import sec_analysis_skill

    helpers = sec_analysis_skill.get_helpers()

    assert isinstance(helpers, dict)
    assert len(helpers) > 0

    # Check for expected helper functions
    expected_helpers = [
        'get_filings_by_period',
        'get_today_filings',
        'get_revenue_trend',
    ]

    for helper_name in expected_helpers:
        assert helper_name in helpers, f"Helper '{helper_name}' should be available"
        assert callable(helpers[helper_name])


@pytest.mark.fast
def test_skill_export_method():
    """Test BaseSkill.export() method."""
    from edgar.ai.skills.sec_analysis import sec_analysis_skill

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Use the skill's export method directly
        skill_dir = sec_analysis_skill.export(format="claude-desktop", output_dir=output_dir)

        assert skill_dir.exists()
        assert (skill_dir / "skill.md").exists()
