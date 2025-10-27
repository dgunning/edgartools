"""
EdgarTools AI Skills - Skill discovery and management.

Skills are self-contained packages of documentation and helper functions
that enable AI agents to perform domain-specific tasks with EdgarTools.
"""

from edgar.ai.skills.base import BaseSkill
from edgar.ai.skills.sec_analysis import sec_analysis_skill, SECAnalysisSkill

__all__ = [
    'BaseSkill',
    'SECAnalysisSkill',
    'sec_analysis_skill',
    'list_skills',
    'get_skill',
]


def list_skills() -> list:
    """
    List all available skills (built-in + external).

    Returns:
        List of BaseSkill instances

    Example:
        >>> from edgar.ai.skills import list_skills
        >>> skills = list_skills()
        >>> for skill in skills:
        ...     print(f"{skill.name}: {skill.description}")
    """
    # Currently only one built-in skill
    # External packages can register additional skills here
    return [sec_analysis_skill]


def get_skill(name: str) -> BaseSkill:
    """
    Get skill by name.

    Args:
        name: Skill name (e.g., "SEC Filing Analysis")

    Returns:
        BaseSkill instance

    Raises:
        ValueError: If skill not found

    Example:
        >>> from edgar.ai.skills import get_skill
        >>> skill = get_skill("SEC Filing Analysis")
        >>> docs = skill.get_documents()
    """
    for skill in list_skills():
        if skill.name == name:
            return skill

    available = [s.name for s in list_skills()]
    raise ValueError(
        f"Skill '{name}' not found. Available skills: {', '.join(available)}"
    )
