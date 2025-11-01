"""
Claude Skills exporter.

Exports EdgarTools skills in official Anthropic Claude Skills format:
- Installs to ~/.claude/skills/ by default
- Main file: SKILL.md (uppercase, per Anthropic spec)
- Keeps all supporting markdown files
- Validates YAML frontmatter structure
"""

import shutil
from pathlib import Path
from typing import Optional
import re


def export_claude_skills(skill, output_dir: Optional[Path] = None, install: bool = True) -> Path:
    """
    Export a skill in official Claude Skills format.

    Exports to ~/.claude/skills/ by default, creating SKILL.md (uppercase) as the
    main skill file per Anthropic's specification. All supporting markdown files
    are preserved.

    Args:
        skill: BaseSkill instance to export
        output_dir: Optional output directory (defaults to ~/.claude/skills/)
        install: If True (default), install to ~/.claude/skills/;
                if False, use output_dir or current directory

    Returns:
        Path: Path to exported skill directory

    Examples:
        >>> from edgar.ai.skills import edgartools_skill
        >>> export_claude_skills(edgartools_skill)
        PosixPath('/Users/username/.claude/skills/edgartools')

        >>> # Export to custom location
        >>> export_claude_skills(edgartools_skill,
        ...                      output_dir="./my-skills",
        ...                      install=False)
        PosixPath('./my-skills/edgartools')
    """
    from edgar.ai.skills.base import BaseSkill

    if not isinstance(skill, BaseSkill):
        raise TypeError(f"Expected BaseSkill instance, got {type(skill)}")

    # Determine output directory
    if install and output_dir is None:
        # Default: Install to ~/.claude/skills/
        output_dir = Path.home() / ".claude" / "skills"
    elif output_dir is None:
        # No install flag, no output_dir: use current directory
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

    # Copy markdown files
    skill_md_found = False
    for md_file in markdown_files:
        if md_file.name == 'SKILL.md':
            # Validate and copy SKILL.md
            _copy_and_validate_skill_md(md_file, skill_output_dir)
            skill_md_found = True
        else:
            # Copy supporting markdown files as-is
            dest_file = skill_output_dir / md_file.name
            shutil.copy2(md_file, dest_file)

    if not skill_md_found:
        raise ValueError("No SKILL.md found in skill content directory")

    # Copy centralized object documentation (API reference)
    object_docs = skill.get_object_docs()
    if object_docs:
        api_ref_dir = skill_output_dir / "api-reference"
        api_ref_dir.mkdir(exist_ok=True)

        for doc_path in object_docs:
            if doc_path.exists():
                shutil.copy2(doc_path, api_ref_dir / doc_path.name)
            # Silently skip missing docs (allows for optional docs)

    return skill_output_dir


def _copy_and_validate_skill_md(source: Path, destination_dir: Path) -> None:
    """
    Copy SKILL.md and validate YAML frontmatter.

    Args:
        source: Source SKILL.md file path
        destination_dir: Destination directory

    Raises:
        ValueError: If YAML frontmatter is invalid or missing
    """
    dest_file = destination_dir / source.name

    # Read and validate
    content = source.read_text(encoding='utf-8')

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

    # Copy file
    dest_file.write_text(content, encoding='utf-8')


def _validate_skill_frontmatter(frontmatter: str, filename: str) -> None:
    """
    Validate required fields in SKILL.md frontmatter.

    Per Anthropic spec, SKILL.md must have:
    - name: skill identifier (lowercase with hyphens)
    - description: clear description of what skill does

    Args:
        frontmatter: YAML frontmatter content
        filename: Source filename (for error messages)

    Raises:
        ValueError: If required fields are missing
    """
    required_fields = ['name', 'description']

    for field in required_fields:
        # Simple regex check (not full YAML parsing to avoid dependencies)
        if not re.search(rf'^{field}:', frontmatter, re.MULTILINE):
            raise ValueError(
                f"Missing required field '{field}' in {filename} frontmatter. "
                f"Claude Skills require both 'name' and 'description' fields."
            )
