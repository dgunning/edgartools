"""
EdgarTools AI skill exporters.

Provides functions to export skills in various formats for AI tool integration.
"""

from edgar.ai.exporters.claude_desktop import export_claude_desktop

__all__ = ['export_claude_desktop', 'export_skill']


def export_skill(skill, format: str = "claude-desktop", output_dir=None):
    """
    Export a skill in the specified format.

    Args:
        skill: BaseSkill instance to export
        format: Export format ("claude-desktop" currently supported)
        output_dir: Optional output directory (defaults to current directory)

    Returns:
        Path: Path to exported skill directory or archive

    Examples:
        >>> from edgar.ai.skills import sec_analysis_skill
        >>> export_skill(sec_analysis_skill, format="claude-desktop")
        PosixPath('sec-filing-analysis')
    """
    if format == "claude-desktop":
        return export_claude_desktop(skill, output_dir=output_dir)
    else:
        raise ValueError(f"Unknown export format: {format}")
