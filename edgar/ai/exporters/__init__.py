"""
EdgarTools AI skill exporters.

Provides functions to export skills in various formats for AI tool integration.
"""

from edgar.ai.exporters.claude_desktop import export_claude_desktop
from edgar.ai.exporters.claude_skills import export_claude_skills

__all__ = ['export_claude_desktop', 'export_claude_skills', 'export_skill']


def export_skill(skill, format: str = "claude-skills", output_dir=None, **kwargs):
    """
    Export a skill in the specified format.

    Args:
        skill: BaseSkill instance to export
        format: Export format:
            - "claude-skills": Official Claude Skills format (default, ~/.claude/skills/)
            - "claude-desktop": Portable format (current directory)
        output_dir: Optional output directory (format-specific defaults)
        **kwargs: Additional format-specific parameters:
            - claude-skills: install (bool, default True)
            - claude-desktop: create_zip (bool, default False)

    Returns:
        Path: Path to exported skill directory or archive

    Examples:
        >>> from edgar.ai.skills import edgartools_skill

        >>> # Export to ~/.claude/skills/ (default)
        >>> export_skill(edgartools_skill, format="claude-skills")
        PosixPath('/Users/username/.claude/skills/edgartools')

        >>> # Export to current directory (portable)
        >>> export_skill(edgartools_skill, format="claude-desktop")
        PosixPath('edgartools')

        >>> # Export as zip archive
        >>> export_skill(edgartools_skill, format="claude-desktop", create_zip=True)
        PosixPath('edgartools.zip')
    """
    if format == "claude-skills":
        return export_claude_skills(skill, output_dir=output_dir, **kwargs)
    elif format == "claude-desktop":
        return export_claude_desktop(skill, output_dir=output_dir, **kwargs)
    else:
        raise ValueError(
            f"Unknown export format: {format}. "
            f"Supported formats: 'claude-skills', 'claude-desktop'"
        )
