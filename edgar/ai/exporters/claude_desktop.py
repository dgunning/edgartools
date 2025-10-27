"""
Claude Desktop skill exporter.

Exports EdgarTools skills in Claude Desktop format:
- Copies markdown files with YAML frontmatter
- Validates frontmatter structure
- Creates portable skill packages
"""

import shutil
import zipfile
from pathlib import Path
from typing import Optional
import re


def export_claude_desktop(skill, output_dir: Optional[Path] = None, create_zip: bool = False) -> Path:
    """
    Export a skill in Claude Desktop format.

    Copies all markdown files from the skill's content directory to an output directory,
    validating YAML frontmatter and creating a portable skill package.

    Args:
        skill: BaseSkill instance to export
        output_dir: Optional output directory (defaults to current directory)
        create_zip: If True, create a zip archive of the exported skill

    Returns:
        Path: Path to exported skill directory (or zip file if create_zip=True)

    Examples:
        >>> from edgar.ai.skills import sec_analysis_skill
        >>> export_claude_desktop(sec_analysis_skill)
        PosixPath('sec-filing-analysis')

        >>> export_claude_desktop(sec_analysis_skill, create_zip=True)
        PosixPath('sec-filing-analysis.zip')
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
    for md_file in markdown_files:
        _copy_and_validate_markdown(md_file, skill_output_dir)

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
        ValueError: If YAML frontmatter is invalid or missing in skill.md
    """
    dest_file = destination_dir / source.name

    # Read and validate
    content = source.read_text(encoding='utf-8')

    # Only require frontmatter for skill.md
    if source.name == 'skill.md':
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
