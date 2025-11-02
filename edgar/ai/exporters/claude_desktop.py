"""
Claude Desktop skill exporter.

Exports EdgarTools skills for Claude Desktop upload:
- Creates ZIP file with SKILL.md at root (required by Claude Desktop)
- Validates YAML frontmatter structure
- Includes all supporting markdown files and API reference
"""

import shutil
import zipfile
from pathlib import Path
from typing import Optional
import re


def export_claude_desktop(skill, output_dir: Optional[Path] = None, create_zip: bool = True) -> Path:
    """
    Export a skill for Claude Desktop upload.

    Creates a ZIP file with SKILL.md at the root level, as required by Claude Desktop's
    upload interface. The ZIP includes all supporting markdown files and API reference.

    Args:
        skill: BaseSkill instance to export
        output_dir: Optional output directory (defaults to current directory)
        create_zip: If True (default), create a zip archive; if False, create directory

    Returns:
        Path: Path to exported ZIP file (or directory if create_zip=False)

    Examples:
        >>> from edgar.ai.skills import edgartools_skill

        >>> # Create ZIP for Claude Desktop upload (default)
        >>> export_claude_desktop(edgartools_skill)
        PosixPath('edgartools.zip')

        >>> # Create directory for manual installation
        >>> export_claude_desktop(edgartools_skill, create_zip=False)
        PosixPath('edgartools')
    """
    from edgar.ai.skills.base import BaseSkill

    if not isinstance(skill, BaseSkill):
        raise TypeError(f"Expected BaseSkill instance, got {type(skill)}")

    # Determine output directory
    if output_dir is None:
        output_dir = Path.cwd()
    else:
        output_dir = Path(output_dir)

    # Create skill-specific directory name (kebab-case from skill name)
    skill_dir_name = skill.name.lower().replace(' ', '-')
    skill_output_dir = output_dir / skill_dir_name

    # Remove existing directory if present
    if skill_output_dir.exists():
        shutil.rmtree(skill_output_dir)

    skill_output_dir.mkdir(parents=True, exist_ok=True)

    # Get markdown files from skill content directory
    content_dir = skill.content_dir
    markdown_files = list(content_dir.glob("*.md"))

    if not markdown_files:
        raise ValueError(f"No markdown files found in {content_dir}")

    # Copy and validate each markdown file
    # Claude Desktop requires SKILL.md (uppercase) at root
    for md_file in markdown_files:
        _copy_and_validate_markdown(md_file, skill_output_dir)

    # Copy centralized object documentation (API reference)
    object_docs = skill.get_object_docs()
    if object_docs:
        api_ref_dir = skill_output_dir / "api-reference"
        api_ref_dir.mkdir(exist_ok=True)

        for doc_path in object_docs:
            if doc_path.exists():
                shutil.copy2(doc_path, api_ref_dir / doc_path.name)
            # Silently skip missing docs (allows for optional docs)

    # Create zip archive if requested
    if create_zip:
        zip_path = output_dir / f"{skill_dir_name}.zip"
        _create_zip_archive(skill_output_dir, zip_path)
        # Clean up directory after zipping
        shutil.rmtree(skill_output_dir)
        return zip_path

    return skill_output_dir


def _copy_and_validate_markdown(source: Path, destination_dir: Path) -> None:
    """
    Copy markdown file and validate YAML frontmatter.

    Args:
        source: Source markdown file path
        destination_dir: Destination directory

    Raises:
        ValueError: If YAML frontmatter is invalid or missing in SKILL.md
    """
    dest_file = destination_dir / source.name

    # Read and validate
    content = source.read_text(encoding='utf-8')

    # Only require frontmatter for SKILL.md
    if source.name == 'SKILL.md':
        # Check for YAML frontmatter
        if not content.startswith('---'):
            raise ValueError(f"Missing YAML frontmatter in {source.name}")

        # Extract frontmatter
        parts = content.split('---', 2)
        if len(parts) < 3:
            raise ValueError(f"Invalid YAML frontmatter structure in {source.name}")

        frontmatter = parts[1].strip()

        # Validate required frontmatter fields
        _validate_skill_frontmatter(frontmatter, source.name)
    else:
        # Optional: validate frontmatter if present in supporting files
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) < 3:
                raise ValueError(f"Invalid YAML frontmatter structure in {source.name}")

    # Copy file
    shutil.copy2(source, dest_file)


def _validate_skill_frontmatter(frontmatter: str, filename: str) -> None:
    """
    Validate required fields in skill.md frontmatter.

    Args:
        frontmatter: YAML frontmatter content
        filename: Source filename (for error messages)

    Raises:
        ValueError: If required fields are missing
    """
    # Only require essential fields (name and description)
    # version and author are optional
    required_fields = ['name', 'description']

    for field in required_fields:
        # Simple regex check (not full YAML parsing to avoid dependencies)
        if not re.search(rf'^{field}:', frontmatter, re.MULTILINE):
            raise ValueError(f"Missing required field '{field}' in {filename} frontmatter")


def _create_zip_archive(source_dir: Path, zip_path: Path) -> None:
    """
    Create a zip archive of the skill directory.

    Args:
        source_dir: Source directory to zip
        zip_path: Output zip file path
    """
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in source_dir.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(source_dir.parent)
                zipf.write(file_path, arcname)
