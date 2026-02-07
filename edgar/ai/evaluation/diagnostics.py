"""
Constitution-driven diagnostics for skill improvement.

Maps pattern failures from A/B evaluation results to constitution goals
and skill files, producing actionable recommendations for skill edits.

Example:
    >>> from edgar.ai.evaluation.diagnostics import run_constitution_diagnostics
    >>> # After running an ABComparison via SkillTestRunner...
    >>> report = run_constitution_diagnostics(comparison)
    >>> report.print_report()
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from edgar.ai.evaluation.constitution import (
    Constitution,
    ConstitutionGoal,
    load_constitution,
)
from edgar.ai.evaluation.evaluators import count_tokens
from edgar.ai.evaluation.harness import ABComparison, TestResult
from edgar.ai.evaluation.test_cases import SECAnalysisTestCase, get_test_by_id


# =============================================================================
# Pattern-to-Goal Mapping Tables
# =============================================================================

# Maps expected patterns to the constitution goals they measure
PATTERN_GOAL_MAP: Dict[str, List[str]] = {
    r"Company\(": ["correctness", "routing"],
    r"get_financials\(\)": ["correctness", "routing"],
    r"get_filings\(": ["correctness", "routing"],
    r"\.head\(": ["efficiency"],
    r"\[0\]": ["efficiency"],
    r"\.latest\(\)": ["efficiency"],
    r"\.obj\(\)": ["correctness", "routing"],
    r"find\(": ["correctness", "routing"],
    r"get_current_filings\(\)": ["correctness", "routing"],
    r"get_revenue\(": ["correctness", "routing", "efficiency"],
    r"income_statement": ["correctness", "routing"],
    r"balance_sheet": ["correctness", "routing"],
    r"cash_flow": ["correctness", "routing"],
    r"get_facts\(\)": ["correctness", "routing"],
    r"form=": ["correctness"],
    r"risk_factors|item_1a": ["correctness"],
    r"mda|item_7|item7": ["correctness"],
    r"\.holdings": ["correctness"],
    r"\.cik|\.ticker": ["correctness"],
    r"\.sic|sic_description": ["correctness"],
    r"\.filing_date|\.filed": ["correctness"],
    r"len\(|\.shape|count": ["correctness"],
    r"sort|max|largest": ["correctness"],
    r"net_income|total_assets": ["correctness"],
    r"gross|margin": ["correctness"],
    r"filter\(": ["correctness", "routing"],
}

# Maps forbidden patterns to the goals they violate
FORBIDDEN_GOAL_MAP: Dict[str, List[str]] = {
    r"for\s+.*\s+in\s+.*get_filings\(\)": ["efficiency", "sharp_edges"],
    r"list\(.*get_filings": ["efficiency", "sharp_edges"],
    r"get_filings\(\)\s*$": ["efficiency"],
    r"for\s+f\s+in\s+.*:\s*.*\+=\s*1": ["efficiency"],
    r"for\s+.*\s+in\s+range\(.*3\)": ["efficiency"],
    r"\.xbrl\(\).*\.xbrl\(\)": ["efficiency"],
    r"Filing\s*\(.*cik": ["sharp_edges"],
    r"repr\s*\(": ["sharp_edges"],
    r"for\s+filing\s+in\s+company\.get_filings\(\):": ["efficiency", "sharp_edges"],
}

# Maps test categories to relevant skill files
CATEGORY_SKILL_MAP: Dict[str, List[str]] = {
    "lookup": ["core/skill.yaml"],
    "filing": ["core/skill.yaml"],
    "counting": ["core/skill.yaml"],
    "financial": ["financials/skill.yaml", "core/skill.yaml"],
    "ownership": ["ownership/skill.yaml", "core/skill.yaml"],
    "holdings": ["holdings/skill.yaml", "core/skill.yaml"],
    "reports": ["reports/skill.yaml", "core/skill.yaml"],
    "comparison": ["core/skill.yaml", "financials/skill.yaml"],
    "multi-step": ["core/skill.yaml", "reports/skill.yaml"],
    "general": ["core/skill.yaml"],
}


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class PatternDiagnosis:
    """Diagnosis for a single pattern match/miss."""

    pattern: str
    expected: bool  # True = expected pattern, False = forbidden pattern
    matched: bool  # True = pattern was found in code
    goal_ids: List[str]


@dataclass
class ConstitutionDiagnostic:
    """Per-test, per-goal diagnosis."""

    test_id: str
    goal_id: str
    status: str  # "pass", "fail", "partial"
    skill_files: List[str]
    recommendation: str
    severity: str  # "low", "medium", "high"
    delta: float  # with_skills score - without_skills score for this test
    pattern_details: List[PatternDiagnosis] = field(default_factory=list)


@dataclass
class ConstitutionReport:
    """Aggregated diagnostics report."""

    diagnostics: List[ConstitutionDiagnostic]
    by_goal: Dict[str, List[ConstitutionDiagnostic]] = field(default_factory=dict)
    by_skill_file: Dict[str, List[ConstitutionDiagnostic]] = field(default_factory=dict)
    by_category: Dict[str, List[ConstitutionDiagnostic]] = field(default_factory=dict)
    goal_scores: Dict[str, float] = field(default_factory=dict)
    priority_fixes: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    skill_budget_status: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self):
        if self.diagnostics and not self.by_goal:
            self._aggregate()

    def _aggregate(self):
        # Group by goal
        for d in self.diagnostics:
            self.by_goal.setdefault(d.goal_id, []).append(d)
            for sf in d.skill_files:
                self.by_skill_file.setdefault(sf, []).append(d)
            test = get_test_by_id(d.test_id)
            if test:
                self.by_category.setdefault(test.category, []).append(d)

        # Calculate goal scores
        for goal_id, diags in self.by_goal.items():
            passes = sum(1 for d in diags if d.status == "pass")
            partials = sum(1 for d in diags if d.status == "partial")
            total = len(diags)
            if total > 0:
                self.goal_scores[goal_id] = round(
                    (passes + partials * 0.5) / total, 3
                )
            else:
                self.goal_scores[goal_id] = 1.0

        # Build priority fixes from high-severity failures
        for d in self.diagnostics:
            if d.status == "fail" and d.severity in ("high", "medium"):
                self.priority_fixes.append({
                    "severity": d.severity,
                    "test_id": d.test_id,
                    "goal_id": d.goal_id,
                    "skill_files": d.skill_files,
                    "recommendation": d.recommendation,
                })

        # Sort priority fixes: high before medium, then by goal weight
        severity_order = {"high": 0, "medium": 1, "low": 2}
        self.priority_fixes.sort(key=lambda x: severity_order.get(x["severity"], 2))

    def print_report(self):
        """Print a formatted diagnostics report."""
        lines = [
            "",
            "CONSTITUTION DIAGNOSTICS REPORT",
            "=" * 50,
            "",
            "Goal Scores:",
        ]

        for goal_id, score in sorted(
            self.goal_scores.items(), key=lambda x: x[1]
        ):
            bar = "#" * int(score * 20)
            lines.append(f"  {goal_id:<18} {score:.3f}  {bar}")

        lines.append("")
        lines.append("By Goal:")
        for goal_id, diags in self.by_goal.items():
            passes = sum(1 for d in diags if d.status == "pass")
            fails = sum(1 for d in diags if d.status == "fail")
            lines.append(f"  {goal_id}: {passes} pass, {fails} fail")
            for d in diags:
                if d.status != "pass":
                    sev = d.severity.upper()
                    lines.append(f"    [{sev}] {d.test_id}: {d.recommendation}")

        if self.skill_budget_status:
            lines.append("")
            lines.append("Skill Token Budgets:")
            for skill_file, info in self.skill_budget_status.items():
                actual = info["actual"]
                budget = info["budget"]
                status = "OVER" if info["over"] else "OK"
                diff = f" (+{actual - budget} tokens)" if info["over"] else ""
                lines.append(f"  {skill_file:<30} {actual:>5} / {budget:<5}  {status}{diff}")

        if self.priority_fixes:
            lines.append("")
            lines.append("Priority Fixes:")
            for i, fix in enumerate(self.priority_fixes, 1):
                sev = fix["severity"].upper()
                files = ", ".join(fix["skill_files"][:2])
                lines.append(
                    f"  {i}. [{sev}] {files} ({fix['goal_id']}): "
                    f"{fix['recommendation']}"
                )

        lines.append("")
        print("\n".join(lines))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "goal_scores": self.goal_scores,
            "by_goal": {
                gid: [
                    {
                        "test_id": d.test_id,
                        "status": d.status,
                        "severity": d.severity,
                        "recommendation": d.recommendation,
                        "skill_files": d.skill_files,
                        "delta": d.delta,
                    }
                    for d in diags
                ]
                for gid, diags in self.by_goal.items()
            },
            "priority_fixes": self.priority_fixes,
            "suggestions": self.suggestions,
            "skill_budget_status": self.skill_budget_status,
        }


# =============================================================================
# Core Functions
# =============================================================================


def _classify_pattern_goals(
    pattern: str,
    is_forbidden: bool,
    constitution: Constitution,
) -> List[str]:
    """Classify which goals a pattern relates to.

    Uses mapping tables first, then falls back to constitution
    indicator_patterns / anti_patterns.
    """
    mapping = FORBIDDEN_GOAL_MAP if is_forbidden else PATTERN_GOAL_MAP

    # Check mapping tables
    for map_pattern, goal_ids in mapping.items():
        try:
            if re.search(re.escape(map_pattern), re.escape(pattern)):
                return goal_ids
            # Also try direct substring match
            if map_pattern in pattern or pattern in map_pattern:
                return goal_ids
        except re.error:
            if map_pattern in pattern or pattern in map_pattern:
                return goal_ids

    # Fallback: check constitution indicator/anti patterns
    for goal in constitution.goals:
        patterns_to_check = goal.anti_patterns if is_forbidden else goal.indicator_patterns
        for indicator in patterns_to_check:
            try:
                if re.search(re.escape(indicator), re.escape(pattern)):
                    return [goal.id]
                if indicator in pattern or pattern in indicator:
                    return [goal.id]
            except re.error:
                if indicator in pattern or pattern in indicator:
                    return [goal.id]

    # Default: correctness for expected, sharp_edges for forbidden
    return ["sharp_edges"] if is_forbidden else ["correctness"]


def _resolve_skill_files(
    goal: ConstitutionGoal,
    category: str,
) -> List[str]:
    """Combine goal's primary_skill_files with category mapping."""
    files = set(goal.primary_skill_files)
    files.update(CATEGORY_SKILL_MAP.get(category, ["core/skill.yaml"]))
    return sorted(files)


def diagnose_test(
    with_result: Optional[TestResult],
    without_result: Optional[TestResult],
    test_case: SECAnalysisTestCase,
    constitution: Constitution,
) -> List[ConstitutionDiagnostic]:
    """Diagnose a single test's results against constitution goals.

    Args:
        with_result: TestResult from with-skills condition (or None)
        without_result: TestResult from without-skills condition (or None)
        test_case: The test case definition
        constitution: Loaded constitution

    Returns:
        List of ConstitutionDiagnostic, one per relevant goal
    """
    diagnostics = []

    # Calculate delta
    ws_score = with_result.score if with_result else 0.0
    wos_score = without_result.score if without_result else 0.0
    delta = ws_score - wos_score

    # Determine which goals to check
    goal_ids = test_case.constitution_goals
    if not goal_ids:
        # Infer from patterns
        goal_ids = _infer_goals_from_patterns(test_case, constitution)

    for goal_id in goal_ids:
        goal = constitution.get_goal(goal_id)
        if not goal:
            continue

        # Find relevant pattern failures for this goal
        pattern_details = _get_pattern_details_for_goal(
            with_result, test_case, goal_id, constitution
        )

        # Classify status
        failures = [
            pd for pd in pattern_details
            if (pd.expected and not pd.matched) or (not pd.expected and pd.matched)
        ]
        n_failures = len(failures)

        if n_failures == 0:
            status = "pass"
        elif n_failures == 1:
            status = "partial"
        else:
            status = "fail"

        # Determine severity
        if delta < 0 and status != "pass":
            severity = "high"  # Skills are hurting
        elif status == "fail":
            severity = "medium"
        else:
            severity = "low"

        # Generate recommendation
        skill_files = _resolve_skill_files(goal, test_case.category)
        recommendation = _generate_recommendation(
            goal, test_case, failures, skill_files
        )

        diagnostics.append(ConstitutionDiagnostic(
            test_id=test_case.id,
            goal_id=goal_id,
            status=status,
            skill_files=skill_files,
            recommendation=recommendation,
            severity=severity,
            delta=delta,
            pattern_details=pattern_details,
        ))

    return diagnostics


def _infer_goals_from_patterns(
    test_case: SECAnalysisTestCase,
    constitution: Constitution,
) -> List[str]:
    """Infer goal IDs from a test case's patterns when not explicitly set."""
    goal_ids = set()
    goal_ids.add("correctness")  # All tests get correctness

    for pattern in test_case.expected_patterns:
        goals = _classify_pattern_goals(pattern, False, constitution)
        goal_ids.update(goals)

    for pattern in test_case.forbidden_patterns:
        goals = _classify_pattern_goals(pattern, True, constitution)
        goal_ids.update(goals)

    return sorted(goal_ids)


def _get_pattern_details_for_goal(
    result: Optional[TestResult],
    test_case: SECAnalysisTestCase,
    goal_id: str,
    constitution: Constitution,
) -> List[PatternDiagnosis]:
    """Get pattern match details filtered to a specific goal."""
    details = []

    if result is None:
        return details

    # Check expected patterns
    for pattern, matched in result.evaluation.pattern.expected_matches:
        goals = _classify_pattern_goals(pattern, False, constitution)
        if goal_id in goals:
            details.append(PatternDiagnosis(
                pattern=pattern,
                expected=True,
                matched=matched,
                goal_ids=goals,
            ))

    # Check forbidden patterns
    for pattern, found in result.evaluation.pattern.forbidden_violations:
        goals = _classify_pattern_goals(pattern, True, constitution)
        if goal_id in goals:
            details.append(PatternDiagnosis(
                pattern=pattern,
                expected=False,
                matched=found,
                goal_ids=goals,
            ))

    return details


def _generate_recommendation(
    goal: ConstitutionGoal,
    test_case: SECAnalysisTestCase,
    failures: List[PatternDiagnosis],
    skill_files: List[str],
) -> str:
    """Generate a human-readable recommendation."""
    if not failures:
        return "OK"

    primary_file = skill_files[0] if skill_files else "core/skill.yaml"

    missed_expected = [f for f in failures if f.expected and not f.matched]
    forbidden_violations = [f for f in failures if not f.expected and f.matched]

    parts = []
    if missed_expected:
        patterns = ", ".join(f.pattern[:40] for f in missed_expected[:2])
        parts.append(f"In {primary_file}, add patterns for: {patterns}")
    if forbidden_violations:
        patterns = ", ".join(f.pattern[:40] for f in forbidden_violations[:2])
        parts.append(f"In {primary_file}, add warning against: {patterns}")

    return "; ".join(parts) if parts else "Review skill patterns"


def run_constitution_diagnostics(
    comparison: ABComparison,
    constitution: Optional[Constitution] = None,
) -> ConstitutionReport:
    """Run full constitution diagnostics on an A/B comparison.

    Args:
        comparison: ABComparison from SkillTestRunner
        constitution: Optional pre-loaded constitution

    Returns:
        ConstitutionReport with aggregated diagnostics
    """
    if constitution is None:
        constitution = load_constitution()

    all_diagnostics = []

    # Build lookup maps for results
    ws_results = {r.test_id: r for r in comparison.with_skills.results}
    wos_results = {r.test_id: r for r in comparison.without_skills.results}

    # Get all test IDs from both conditions
    test_ids = set(ws_results.keys()) | set(wos_results.keys())

    for test_id in sorted(test_ids):
        test_case = get_test_by_id(test_id)
        if not test_case:
            continue

        with_result = ws_results.get(test_id)
        without_result = wos_results.get(test_id)

        diags = diagnose_test(
            with_result, without_result, test_case, constitution
        )
        all_diagnostics.extend(diags)

    report = ConstitutionReport(diagnostics=all_diagnostics)

    # Add skill token budget check
    report.skill_budget_status = check_skill_token_budgets(constitution)

    # Generate suggestions from the report
    report.suggestions = generate_skill_edit_suggestions(report)

    return report


def generate_skill_edit_suggestions(
    report: ConstitutionReport,
    skills_dir: Optional[str] = None,
) -> List[str]:
    """Generate specific skill edit suggestions from a diagnostics report.

    Args:
        report: ConstitutionReport with diagnostics
        skills_dir: Path to skills directory (auto-detected if None)

    Returns:
        List of actionable suggestion strings
    """
    suggestions = []

    # Collect suggestions by skill file
    file_issues: Dict[str, List[str]] = {}
    for d in report.diagnostics:
        if d.status == "pass":
            continue
        for sf in d.skill_files:
            file_issues.setdefault(sf, []).append(
                f"{d.test_id} ({d.goal_id}, {d.severity}): {d.recommendation}"
            )

    for sf, issues in sorted(file_issues.items()):
        high_count = sum(1 for i in issues if "high" in i)
        if high_count > 0:
            suggestions.append(
                f"HIGH PRIORITY: {sf} has {high_count} high-severity issues"
            )
        for issue in issues[:3]:  # Cap at 3 per file
            suggestions.append(f"  - {issue}")

    # Budget suggestions
    for sf, info in report.skill_budget_status.items():
        if info["over"]:
            over_by = info["actual"] - info["budget"]
            suggestions.append(
                f"TOKEN BUDGET: {sf} is {over_by} tokens over budget "
                f"({info['actual']}/{info['budget']}). Trim examples."
            )

    # Goal-level suggestions
    for goal_id, score in report.goal_scores.items():
        if score < 0.5:
            suggestions.append(
                f"GOAL AT RISK: {goal_id} scores {score:.3f}. "
                f"Needs significant skill improvements."
            )

    return suggestions


def check_skill_token_budgets(
    constitution: Constitution,
    skills_dir: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Check each skill YAML against its token budget from the constitution.

    Args:
        constitution: Loaded constitution
        skills_dir: Path to skills directory (auto-detected if None)

    Returns:
        Dict mapping skill file path to {actual, budget, over} info
    """
    if skills_dir is None:
        skills_dir = str(
            Path(__file__).parent.parent / "skills"
        )

    # Find the token_economy goal
    token_goal = constitution.get_goal("token_economy")
    if not token_goal or not token_goal.skill_token_budgets:
        return {}

    results = {}
    for skill_file, budget in token_goal.skill_token_budgets.items():
        full_path = Path(skills_dir) / skill_file
        if full_path.exists():
            content = full_path.read_text()
            actual = count_tokens(content)
            results[skill_file] = {
                "actual": actual,
                "budget": budget,
                "over": actual > budget,
            }
        else:
            results[skill_file] = {
                "actual": 0,
                "budget": budget,
                "over": False,
            }

    return results
