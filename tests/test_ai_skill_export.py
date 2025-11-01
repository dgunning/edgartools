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
def test_edgartools_skill_exists():
    """Test that the EdgarTools skill is available."""
    from edgar.ai.skills.core import edgartools_skill

    assert edgartools_skill is not None
    assert edgartools_skill.name == "EdgarTools"
    assert len(edgartools_skill.description) > 0
    assert edgartools_skill.content_dir.exists()


@pytest.mark.fast
def test_skill_has_markdown_files():
    """Test that skill content directory contains required markdown files."""
    from edgar.ai.skills.core import edgartools_skill

    content_dir = edgartools_skill.content_dir

    # Check for main skill file
    skill_md = content_dir / "SKILL.md"
    assert skill_md.exists(), "SKILL.md should exist"

    # Check for supporting files
    readme = content_dir / "readme.md"
    objects_md = content_dir / "objects.md"
    workflows_md = content_dir / "workflows.md"

    # At least SKILL.md should exist
    assert skill_md.exists()


@pytest.mark.fast
def test_skill_markdown_has_frontmatter():
    """Test that SKILL.md has valid YAML frontmatter."""
    from edgar.ai.skills.core import edgartools_skill

    skill_md = edgartools_skill.content_dir / "SKILL.md"
    content = skill_md.read_text(encoding='utf-8')

    # Check frontmatter structure
    assert content.startswith('---'), "SKILL.md should start with ---"

    # Extract frontmatter
    parts = content.split('---', 2)
    assert len(parts) >= 3, "SKILL.md should have complete frontmatter"

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
    assert any(s.name == "EdgarTools" for s in skills)


@pytest.mark.fast
def test_get_skill():
    """Test getting specific skill by name."""
    from edgar.ai import get_skill

    skill = get_skill("EdgarTools")

    assert skill is not None
    assert skill.name == "EdgarTools"


@pytest.mark.fast
def test_get_skill_not_found():
    """Test that getting non-existent skill raises error."""
    from edgar.ai import get_skill

    with pytest.raises(ValueError, match="not found"):
        get_skill("Non-Existent Skill")


@pytest.mark.fast
def test_export_skill_to_directory():
    """Test exporting skill to a directory (create_zip=False)."""
    from edgar.ai import edgartools_skill, export_skill

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Export skill as directory (not ZIP)
        skill_dir = export_skill(edgartools_skill, format="claude-desktop", output_dir=output_dir, create_zip=False)

        # Check that directory was created
        assert skill_dir.exists()
        assert skill_dir.is_dir()

        # Check that SKILL.md was copied (uppercase)
        skill_md = skill_dir / "SKILL.md"
        assert skill_md.exists()

        # Verify content was copied correctly
        content = skill_md.read_text(encoding='utf-8')
        assert content.startswith('---')
        assert 'name:' in content


@pytest.mark.fast
def test_export_skill_default_zip():
    """Test exporting skill as ZIP (default for claude-desktop)."""
    from edgar.ai import edgartools_skill, export_skill

    # Export to current directory as ZIP (default)
    zip_path = export_skill(edgartools_skill, format="claude-desktop")

    try:
        # Check that ZIP was created
        assert zip_path.exists()
        assert zip_path.suffix == ".zip"
        assert zip_path.name == "edgartools.zip"

        # Verify ZIP contents
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            namelist = zipf.namelist()
            # Check for SKILL.md at root
            assert any("SKILL.md" in name for name in namelist)

    finally:
        # Clean up
        if zip_path.exists():
            zip_path.unlink()


@pytest.mark.fast
def test_export_skill_validates_frontmatter():
    """Test that export validates YAML frontmatter."""
    from edgar.ai import edgartools_skill, export_skill

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # This should succeed with valid frontmatter (directory export)
        skill_dir = export_skill(edgartools_skill, format="claude-desktop", output_dir=output_dir, create_zip=False)

        assert skill_dir.exists()


@pytest.mark.fast
def test_export_skill_unknown_format():
    """Test that unknown export format raises error."""
    from edgar.ai import edgartools_skill, export_skill

    with pytest.raises(ValueError, match="Unknown export format"):
        export_skill(edgartools_skill, format="unknown-format")


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
    from edgar.ai.skills.core import edgartools_skill

    helpers = edgartools_skill.get_helpers()

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
    from edgar.ai.skills.core import edgartools_skill

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Use the skill's export method directly (directory export)
        skill_dir = edgartools_skill.export(format="claude-desktop", output_dir=output_dir, create_zip=False)

        assert skill_dir.exists()
        assert (skill_dir / "SKILL.md").exists()


@pytest.mark.fast
def test_export_skill_includes_object_docs():
    """Test that exported skill includes centralized object documentation."""
    from edgar.ai import edgartools_skill, export_skill

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Export skill as directory
        skill_dir = export_skill(edgartools_skill, format="claude-desktop", output_dir=output_dir, create_zip=False)

        # Check that api-reference directory was created
        api_ref_dir = skill_dir / "api-reference"
        assert api_ref_dir.exists(), "api-reference directory should exist"
        assert api_ref_dir.is_dir()

        # Check that expected object docs are present
        expected_docs = [
            "Company.md",
            "EntityFiling.md",
            "EntityFilings.md",
            "XBRL.md",
            "Statement.md",
        ]

        for doc_name in expected_docs:
            doc_path = api_ref_dir / doc_name
            assert doc_path.exists(), f"{doc_name} should exist in api-reference/"

            # Verify file has content
            content = doc_path.read_text(encoding='utf-8')
            assert len(content) > 100, f"{doc_name} should have substantial content"

            # Verify it's markdown documentation
            assert "##" in content or "#" in content, f"{doc_name} should contain markdown headers"


@pytest.mark.fast
def test_export_skill_with_zip_includes_object_docs():
    """Test that zipped skill export includes object documentation."""
    from edgar.ai import edgartools_skill, export_skill

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Export skill as zip
        zip_path = export_skill(
            edgartools_skill,
            format="claude-desktop",
            output_dir=output_dir,
            create_zip=True
        )

        # Check that zip file was created
        assert zip_path.exists()
        assert zip_path.suffix == ".zip"

        # Verify contents of zip
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            namelist = zipf.namelist()

            # Check for api-reference files
            assert any("api-reference/Company.md" in name for name in namelist)
            assert any("api-reference/XBRL.md" in name for name in namelist)
            assert any("api-reference/Statement.md" in name for name in namelist)


# ============================================================================
# Claude Skills Format Tests (Official Anthropic Format)
# ============================================================================


@pytest.mark.fast
def test_export_claude_skills_custom_location():
    """Test exporting skill to custom location (install=False)."""
    from edgar.ai import edgartools_skill, export_skill

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Export to custom location
        skill_dir = export_skill(
            edgartools_skill,
            format="claude-skills",
            output_dir=output_dir,
            install=False
        )

        # Check that directory was created
        assert skill_dir.exists()
        assert skill_dir.is_dir()
        assert skill_dir.name == "edgartools"

        # Check for SKILL.md (uppercase)
        skill_md = skill_dir / "SKILL.md"
        assert skill_md.exists(), "SKILL.md (uppercase) should exist"

        # Verify that the actual filename is SKILL.md (not skill.md)
        # Note: On case-insensitive filesystems (macOS/Windows), both paths point to same file
        # So we check the actual filename in the directory listing
        md_files = list(skill_dir.glob("*.md"))
        md_filenames = [f.name for f in md_files]

        # SKILL.md should exist in directory listing
        assert "SKILL.md" in md_filenames, "SKILL.md should exist in directory"

        # skill.md should NOT exist as a separate file (check actual names)
        # Count how many times we see a file that could be skill.md or SKILL.md
        skill_variants = [name for name in md_filenames if name.lower() == "skill.md"]
        assert len(skill_variants) == 1, f"Should have exactly 1 skill file, found: {skill_variants}"
        assert skill_variants[0] == "SKILL.md", f"Skill file should be SKILL.md, not {skill_variants[0]}"

        # Verify supporting markdown files exist
        assert (skill_dir / "workflows.md").exists()
        assert (skill_dir / "objects.md").exists()

        # Verify API reference directory exists
        api_ref_dir = skill_dir / "api-reference"
        assert api_ref_dir.exists()
        assert (api_ref_dir / "Company.md").exists()


@pytest.mark.fast
def test_claude_skills_skill_md_content():
    """Test that SKILL.md has valid YAML frontmatter and content."""
    from edgar.ai import edgartools_skill, export_skill

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        skill_dir = export_skill(
            edgartools_skill,
            format="claude-skills",
            output_dir=output_dir,
            install=False
        )

        skill_md = skill_dir / "SKILL.md"
        content = skill_md.read_text(encoding='utf-8')

        # Check frontmatter structure
        assert content.startswith('---'), "SKILL.md should start with ---"

        # Extract frontmatter
        parts = content.split('---', 2)
        assert len(parts) >= 3, "SKILL.md should have complete frontmatter"

        frontmatter = parts[1].strip()

        # Check required fields per Anthropic spec
        assert 'name:' in frontmatter, "SKILL.md must have 'name' field"
        assert 'description:' in frontmatter, "SKILL.md must have 'description' field"

        # Verify main content exists
        main_content = parts[2].strip()
        assert len(main_content) > 100, "SKILL.md should have substantial content"


@pytest.mark.fast
def test_claude_skills_includes_all_markdown():
    """Test that all supporting markdown files are exported."""
    from edgar.ai import edgartools_skill, export_skill

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        skill_dir = export_skill(
            edgartools_skill,
            format="claude-skills",
            output_dir=output_dir,
            install=False
        )

        # Expected markdown files
        expected_files = [
            "SKILL.md",  # Main skill file (renamed from skill.md)
            "workflows.md",
            "objects.md",
            "data-objects.md",
            "quickstart-by-task.md",
            "form-types-reference.md",
            "readme.md",
        ]

        for filename in expected_files:
            file_path = skill_dir / filename
            assert file_path.exists(), f"{filename} should exist"


@pytest.mark.fast
def test_claude_desktop_uses_uppercase_skill():
    """Test that claude-desktop format now uses SKILL.md (uppercase) per Claude Desktop requirements."""
    from edgar.ai import edgartools_skill, export_skill

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Export using claude-desktop format (directory, not ZIP)
        skill_dir = export_skill(
            edgartools_skill,
            format="claude-desktop",
            output_dir=output_dir,
            create_zip=False
        )

        # Check that it works
        assert skill_dir.exists()
        assert skill_dir.is_dir()

        # Claude Desktop format now requires SKILL.md (uppercase)
        skill_md = skill_dir / "SKILL.md"
        assert skill_md.exists(), "claude-desktop format should have SKILL.md (uppercase)"

        # Verify the actual filename is SKILL.md (not skill.md)
        # On case-insensitive filesystems, check the actual directory listing
        md_files = list(skill_dir.glob("*.md"))
        md_filenames = [f.name for f in md_files]

        # SKILL.md should exist in directory listing
        assert "SKILL.md" in md_filenames, "SKILL.md should exist in directory"

        # Should have exactly one skill file and it should be uppercase
        skill_variants = [name for name in md_filenames if name.lower() == "skill.md"]
        assert len(skill_variants) == 1, f"Should have exactly 1 skill file, found: {skill_variants}"
        assert skill_variants[0] == "SKILL.md", f"Skill file should be SKILL.md, not {skill_variants[0]}"


@pytest.mark.fast
def test_claude_skills_invalid_format():
    """Test that invalid format raises error."""
    from edgar.ai import edgartools_skill, export_skill

    with pytest.raises(ValueError, match="Unknown export format"):
        export_skill(edgartools_skill, format="invalid-format")


# ============================================================================
# Convenience Functions Tests (Delightful API)
# ============================================================================


@pytest.mark.fast
def test_install_skill_default():
    """Test install_skill() with defaults (auto-detects edgartools_skill)."""
    from edgar.ai import install_skill

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Install to custom location
        skill_dir = install_skill(to=output_dir)

        # Check installation
        assert skill_dir.exists()
        assert skill_dir.is_dir()
        assert skill_dir.name == "edgartools"
        assert (skill_dir / "SKILL.md").exists()


@pytest.mark.fast
def test_package_skill_default():
    """Test package_skill() with defaults (creates ZIP in current directory)."""
    from edgar.ai import package_skill

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Create ZIP in custom location
        zip_path = package_skill(output=output_dir)

        # Check ZIP was created
        assert zip_path.exists()
        assert zip_path.suffix == ".zip"
        assert zip_path.name == "edgartools.zip"

        # Verify ZIP contents
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            namelist = zipf.namelist()
            assert any("SKILL.md" in name for name in namelist)


@pytest.mark.fast
def test_install_skill_custom_location():
    """Test install_skill() with custom location."""
    from edgar.ai import install_skill

    with tempfile.TemporaryDirectory() as tmpdir:
        custom_dir = Path(tmpdir) / "my-skills"

        # Install to custom location
        skill_dir = install_skill(to=custom_dir)

        # Check installation
        assert skill_dir.exists()
        assert skill_dir.parent == custom_dir
        assert (skill_dir / "SKILL.md").exists()


@pytest.mark.fast
def test_package_skill_custom_output():
    """Test package_skill() with custom output directory."""
    from edgar.ai import package_skill

    with tempfile.TemporaryDirectory() as tmpdir:
        custom_output = Path(tmpdir) / "output"
        custom_output.mkdir()

        # Create ZIP in custom location
        zip_path = package_skill(output=custom_output)

        # Check ZIP was created in correct location
        assert zip_path.exists()
        assert zip_path.parent == custom_output
        assert zip_path.name == "edgartools.zip"
