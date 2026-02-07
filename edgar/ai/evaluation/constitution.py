"""
Constitution loader for skill quality goals.

Loads and parses the constitution YAML that defines formal quality goals
for EdgarTools skills. Each goal has a weight, indicator patterns, and
maps to specific skill files that should be improved when the goal fails.

Example:
    >>> from edgar.ai.evaluation.constitution import load_constitution
    >>> constitution = load_constitution()
    >>> for goal in constitution.get_weighted_goals():
    ...     print(f"{goal.id}: {goal.weight}")
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class ConstitutionGoal:
    """A single quality goal from the constitution.

    Attributes:
        id: Unique identifier (e.g., "correctness")
        name: Human-readable name
        weight: Scoring weight (0.0-1.0, all goals sum to 1.0)
        description: What this goal measures
        passing_criteria: List of criteria for passing
        primary_skill_files: Skill files responsible for this goal
        indicator_patterns: Regex patterns that indicate this goal
        anti_patterns: Regex patterns that violate this goal
        skill_token_budgets: Token budgets per skill file (token_economy only)
    """

    id: str
    name: str
    weight: float
    description: str
    passing_criteria: List[str] = field(default_factory=list)
    primary_skill_files: List[str] = field(default_factory=list)
    indicator_patterns: List[str] = field(default_factory=list)
    anti_patterns: List[str] = field(default_factory=list)
    skill_token_budgets: Dict[str, int] = field(default_factory=dict)


@dataclass
class Constitution:
    """Parsed constitution with helper methods.

    Attributes:
        version: Constitution version string
        goals: List of quality goals
    """

    version: str
    goals: List[ConstitutionGoal]

    def get_goal(self, goal_id: str) -> Optional[ConstitutionGoal]:
        """Get a goal by its ID."""
        for goal in self.goals:
            if goal.id == goal_id:
                return goal
        return None

    def get_weighted_goals(self) -> List[ConstitutionGoal]:
        """Get goals that have non-zero weight, sorted by weight descending."""
        return sorted(
            [g for g in self.goals if g.weight > 0],
            key=lambda g: g.weight,
            reverse=True,
        )

    def goals_for_skill_file(self, skill_path: str) -> List[ConstitutionGoal]:
        """Get all goals that reference a given skill file."""
        return [
            g for g in self.goals
            if skill_path in g.primary_skill_files
        ]


def load_constitution(path: Optional[str] = None) -> Constitution:
    """Load constitution from YAML file.

    Args:
        path: Path to constitution YAML. Defaults to
              edgar/ai/skills/constitution.yaml

    Returns:
        Parsed Constitution object
    """
    if path is None:
        default_path = (
            Path(__file__).parent.parent / "skills" / "constitution.yaml"
        )
        path = str(default_path)

    with open(path) as f:
        data = yaml.safe_load(f)

    goals = []
    for g in data.get("goals", []):
        goals.append(ConstitutionGoal(
            id=g["id"],
            name=g["name"],
            weight=g["weight"],
            description=g["description"],
            passing_criteria=g.get("passing_criteria", []),
            primary_skill_files=g.get("primary_skill_files", []),
            indicator_patterns=g.get("indicator_patterns", []),
            anti_patterns=g.get("anti_patterns", []),
            skill_token_budgets=g.get("skill_token_budgets", {}),
        ))

    return Constitution(
        version=data.get("version", "unknown"),
        goals=goals,
    )
