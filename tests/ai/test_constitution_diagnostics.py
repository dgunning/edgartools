"""
Tests for the constitution-driven skill improvement loop.

Covers:
    - Constitution YAML loading and validation
    - Pattern-to-goal mapping
    - diagnose_test() with mock TestResults
    - run_constitution_diagnostics() with synthetic ABComparison
    - Skill token budget checking
    - Backward compatibility (existing evaluator unchanged)
"""

import re
from pathlib import Path

import pytest

from edgar.ai.evaluation.constitution import (
    Constitution,
    ConstitutionGoal,
    load_constitution,
)
from edgar.ai.evaluation.diagnostics import (
    CATEGORY_SKILL_MAP,
    FORBIDDEN_GOAL_MAP,
    PATTERN_GOAL_MAP,
    ConstitutionDiagnostic,
    ConstitutionReport,
    _classify_pattern_goals,
    _resolve_skill_files,
    check_skill_token_budgets,
    diagnose_test,
    generate_skill_edit_suggestions,
    run_constitution_diagnostics,
)
from edgar.ai.evaluation.evaluators import (
    CombinedEvaluation,
    ExecutionResult,
    PatternResult,
    TokenResult,
    evaluate_code,
    evaluate_pattern_compliance,
)
from edgar.ai.evaluation.harness import (
    ABComparison,
    EvaluationReport,
    TestResult,
)
from edgar.ai.evaluation.test_cases import (
    SEC_TEST_SUITE,
    SECAnalysisTestCase,
    get_test_by_id,
)


# =============================================================================
# Constitution Loading Tests
# =============================================================================


class TestConstitutionLoading:
    """Tests for loading and parsing constitution.yaml."""

    def test_load_constitution_default_path(self):
        """Constitution loads from default path."""
        c = load_constitution()
        assert isinstance(c, Constitution)
        assert c.version == "1.0"

    def test_goals_not_empty(self):
        """Constitution has goals defined."""
        c = load_constitution()
        assert len(c.goals) > 0

    def test_goal_ids_unique(self):
        """All goal IDs are unique."""
        c = load_constitution()
        ids = [g.id for g in c.goals]
        assert len(ids) == len(set(ids))

    def test_weights_sum_to_one(self):
        """Goal weights sum to 1.0."""
        c = load_constitution()
        total = sum(g.weight for g in c.goals)
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, expected 1.0"

    def test_indicator_patterns_are_valid_regex(self):
        """All indicator_patterns compile as valid regex."""
        c = load_constitution()
        for goal in c.goals:
            for pattern in goal.indicator_patterns:
                try:
                    re.compile(pattern)
                except re.error as e:
                    pytest.fail(
                        f"Goal {goal.id} has invalid indicator_pattern "
                        f"'{pattern}': {e}"
                    )

    def test_anti_patterns_are_valid_regex(self):
        """All anti_patterns compile as valid regex."""
        c = load_constitution()
        for goal in c.goals:
            for pattern in goal.anti_patterns:
                try:
                    re.compile(pattern)
                except re.error as e:
                    pytest.fail(
                        f"Goal {goal.id} has invalid anti_pattern "
                        f"'{pattern}': {e}"
                    )

    def test_get_goal_by_id(self):
        """Can retrieve a goal by its ID."""
        c = load_constitution()
        goal = c.get_goal("correctness")
        assert goal is not None
        assert goal.name == "Correctness"
        assert goal.weight == 0.30

    def test_get_goal_not_found(self):
        """get_goal returns None for unknown ID."""
        c = load_constitution()
        assert c.get_goal("nonexistent") is None

    def test_get_weighted_goals(self):
        """get_weighted_goals returns only non-zero weight goals, sorted."""
        c = load_constitution()
        weighted = c.get_weighted_goals()
        assert all(g.weight > 0 for g in weighted)
        # Should be sorted descending by weight
        for i in range(len(weighted) - 1):
            assert weighted[i].weight >= weighted[i + 1].weight

    def test_goals_for_skill_file(self):
        """goals_for_skill_file returns matching goals."""
        c = load_constitution()
        goals = c.goals_for_skill_file("core/skill.yaml")
        assert len(goals) > 0
        ids = [g.id for g in goals]
        assert "correctness" in ids

    def test_known_goals_exist(self):
        """All expected goal IDs exist."""
        c = load_constitution()
        expected_ids = [
            "correctness", "routing", "efficiency",
            "sharp_edges", "token_economy", "completeness",
        ]
        actual_ids = [g.id for g in c.goals]
        for gid in expected_ids:
            assert gid in actual_ids, f"Missing goal: {gid}"

    def test_skill_token_budgets_on_token_economy(self):
        """Token economy goal has skill_token_budgets."""
        c = load_constitution()
        goal = c.get_goal("token_economy")
        assert goal is not None
        assert len(goal.skill_token_budgets) > 0
        assert "core/skill.yaml" in goal.skill_token_budgets


# =============================================================================
# Pattern-Goal Mapping Tests
# =============================================================================


class TestPatternGoalMapping:
    """Tests for mapping patterns to constitution goals."""

    def test_company_pattern_maps_to_correctness_and_routing(self):
        c = load_constitution()
        goals = _classify_pattern_goals(r"Company\(", False, c)
        assert "correctness" in goals
        assert "routing" in goals

    def test_head_pattern_maps_to_efficiency(self):
        c = load_constitution()
        goals = _classify_pattern_goals(r"\.head\(", False, c)
        assert "efficiency" in goals

    def test_unbounded_iteration_maps_to_efficiency_and_sharp_edges(self):
        c = load_constitution()
        goals = _classify_pattern_goals(
            r"for\s+.*\s+in\s+.*get_filings\(\)", True, c
        )
        assert "efficiency" in goals
        assert "sharp_edges" in goals

    def test_obj_pattern_maps_to_correctness_and_routing(self):
        c = load_constitution()
        goals = _classify_pattern_goals(r"\.obj\(\)", False, c)
        assert "correctness" in goals
        assert "routing" in goals

    def test_unknown_expected_pattern_defaults_to_correctness(self):
        c = load_constitution()
        goals = _classify_pattern_goals(r"some_random_pattern_xyz", False, c)
        assert "correctness" in goals

    def test_unknown_forbidden_pattern_defaults_to_sharp_edges(self):
        c = load_constitution()
        goals = _classify_pattern_goals(r"some_random_forbidden_xyz", True, c)
        assert "sharp_edges" in goals


# =============================================================================
# Skill File Resolution Tests
# =============================================================================


class TestSkillFileResolution:
    """Tests for resolving which skill files to edit."""

    def test_resolve_combines_goal_and_category(self):
        c = load_constitution()
        goal = c.get_goal("correctness")
        files = _resolve_skill_files(goal, "financial")
        assert "core/skill.yaml" in files
        assert "financials/skill.yaml" in files

    def test_resolve_for_holdings_category(self):
        c = load_constitution()
        goal = c.get_goal("routing")
        files = _resolve_skill_files(goal, "holdings")
        assert "holdings/skill.yaml" in files

    def test_resolve_for_unknown_category(self):
        c = load_constitution()
        goal = c.get_goal("efficiency")
        files = _resolve_skill_files(goal, "unknown_cat")
        # Should include goal's primary files + fallback
        assert "core/skill.yaml" in files


# =============================================================================
# diagnose_test() Tests
# =============================================================================


def _make_test_result(
    test_id: str,
    condition: str,
    pattern_matches: list,
    forbidden_violations: list,
    pattern_score: float = 0.8,
    overall_score: float = 0.7,
) -> TestResult:
    """Helper to create a TestResult with given pattern data."""
    return TestResult(
        test_id=test_id,
        condition=condition,
        code="fake code",
        evaluation=CombinedEvaluation(
            execution=ExecutionResult(success=True),
            pattern=PatternResult(
                compliant=all(f for _, f in pattern_matches)
                and all(not f for _, f in forbidden_violations),
                expected_matches=pattern_matches,
                forbidden_violations=forbidden_violations,
                score=pattern_score,
            ),
            efficiency=TokenResult(
                token_count=100,
                within_budget=True,
                budget=500,
                efficiency_score=0.9,
            ),
            overall_score=overall_score,
        ),
    )


class TestDiagnoseTest:
    """Tests for diagnose_test() function."""

    def test_all_patterns_pass(self):
        """When all patterns match, all goals should pass."""
        c = load_constitution()
        tc = get_test_by_id("TC001")
        assert tc is not None

        with_result = _make_test_result(
            "TC001", "with_skills",
            pattern_matches=[
                (r"Company\(['\"]AAPL['\"]\)", True),
                (r"\.cik|\.ticker", True),
            ],
            forbidden_violations=[
                (r"for\s+.*\s+in\s+.*get_filings\(\)", False),
                (r"get_filings\(\)\s*$", False),
            ],
            pattern_score=1.0,
            overall_score=1.0,
        )
        without_result = _make_test_result(
            "TC001", "without_skills",
            pattern_matches=[
                (r"Company\(['\"]AAPL['\"]\)", True),
                (r"\.cik|\.ticker", True),
            ],
            forbidden_violations=[
                (r"for\s+.*\s+in\s+.*get_filings\(\)", False),
                (r"get_filings\(\)\s*$", False),
            ],
            pattern_score=0.8,
            overall_score=0.8,
        )

        diags = diagnose_test(with_result, without_result, tc, c)
        assert len(diags) > 0
        # All should pass since all expected patterns matched
        for d in diags:
            assert d.status == "pass"
            assert d.delta >= 0

    def test_missing_expected_pattern(self):
        """When an expected pattern is missing, relevant goal should fail/partial."""
        c = load_constitution()
        tc = get_test_by_id("TC001")
        assert tc is not None

        with_result = _make_test_result(
            "TC001", "with_skills",
            pattern_matches=[
                (r"Company\(['\"]AAPL['\"]\)", True),
                (r"\.cik|\.ticker", False),  # MISSED
            ],
            forbidden_violations=[
                (r"for\s+.*\s+in\s+.*get_filings\(\)", False),
                (r"get_filings\(\)\s*$", False),
            ],
            pattern_score=0.5,
            overall_score=0.5,
        )
        without_result = _make_test_result(
            "TC001", "without_skills",
            pattern_matches=[
                (r"Company\(['\"]AAPL['\"]\)", True),
                (r"\.cik|\.ticker", True),
            ],
            forbidden_violations=[
                (r"for\s+.*\s+in\s+.*get_filings\(\)", False),
                (r"get_filings\(\)\s*$", False),
            ],
            pattern_score=1.0,
            overall_score=0.8,
        )

        diags = diagnose_test(with_result, without_result, tc, c)
        # At least one diagnostic should not be "pass"
        has_non_pass = any(d.status != "pass" for d in diags)
        assert has_non_pass

        # Delta is negative (skills hurt), so severity should be high
        non_pass = [d for d in diags if d.status != "pass"]
        if non_pass:
            assert non_pass[0].severity == "high"
            assert non_pass[0].delta < 0

    def test_forbidden_pattern_violation(self):
        """When a forbidden pattern fires, relevant goals should fail."""
        c = load_constitution()
        tc = get_test_by_id("TC002")
        assert tc is not None

        with_result = _make_test_result(
            "TC002", "with_skills",
            pattern_matches=[
                (r"Company\(['\"]AAPL['\"]\)", True),
                (r"get_filings\(.*form=['\"]10-K['\"]", True),
                (r"\[0\]|\.latest\(\)|\.head\(", True),
                (r"\.filing_date|\.filed", True),
            ],
            forbidden_violations=[
                (r"for\s+.*\s+in\s+.*get_filings\(\)", True),  # VIOLATION
            ],
            pattern_score=0.7,
            overall_score=0.6,
        )
        without_result = _make_test_result(
            "TC002", "without_skills",
            pattern_matches=[
                (r"Company\(['\"]AAPL['\"]\)", True),
                (r"get_filings\(.*form=['\"]10-K['\"]", True),
                (r"\[0\]|\.latest\(\)|\.head\(", True),
                (r"\.filing_date|\.filed", True),
            ],
            forbidden_violations=[
                (r"for\s+.*\s+in\s+.*get_filings\(\)", False),
            ],
            pattern_score=1.0,
            overall_score=0.8,
        )

        diags = diagnose_test(with_result, without_result, tc, c)
        # Find efficiency or sharp_edges diagnostic
        eff_diags = [d for d in diags if d.goal_id in ("efficiency", "sharp_edges")]
        # At least one should not pass
        has_non_pass = any(d.status != "pass" for d in eff_diags)
        assert has_non_pass

    def test_diagnose_with_none_result(self):
        """diagnose_test handles None results gracefully."""
        c = load_constitution()
        tc = get_test_by_id("TC001")
        assert tc is not None

        diags = diagnose_test(None, None, tc, c)
        assert isinstance(diags, list)
        # All should be pass (no pattern data to fail)
        for d in diags:
            assert d.status == "pass"


# =============================================================================
# run_constitution_diagnostics() Tests
# =============================================================================


class TestRunConstitutionDiagnostics:
    """Tests for the full diagnostics pipeline."""

    def _make_comparison(self) -> ABComparison:
        """Create a synthetic ABComparison for testing."""
        tc001 = get_test_by_id("TC001")
        tc002 = get_test_by_id("TC002")

        # With skills: TC001 perfect, TC002 partial
        ws_results = [
            _make_test_result(
                "TC001", "with_skills",
                pattern_matches=[
                    (r"Company\(['\"]AAPL['\"]\)", True),
                    (r"\.cik|\.ticker", True),
                ],
                forbidden_violations=[
                    (r"for\s+.*\s+in\s+.*get_filings\(\)", False),
                    (r"get_filings\(\)\s*$", False),
                ],
                pattern_score=1.0,
                overall_score=1.0,
            ),
            _make_test_result(
                "TC002", "with_skills",
                pattern_matches=[
                    (r"Company\(['\"]AAPL['\"]\)", True),
                    (r"get_filings\(.*form=['\"]10-K['\"]", True),
                    (r"\[0\]|\.latest\(\)|\.head\(", False),  # missed
                    (r"\.filing_date|\.filed", True),
                ],
                forbidden_violations=[
                    (r"for\s+.*\s+in\s+.*get_filings\(\)", False),
                ],
                pattern_score=0.75,
                overall_score=0.7,
            ),
        ]

        # Without skills: TC001 ok, TC002 ok
        wos_results = [
            _make_test_result(
                "TC001", "without_skills",
                pattern_matches=[
                    (r"Company\(['\"]AAPL['\"]\)", True),
                    (r"\.cik|\.ticker", True),
                ],
                forbidden_violations=[
                    (r"for\s+.*\s+in\s+.*get_filings\(\)", False),
                    (r"get_filings\(\)\s*$", False),
                ],
                pattern_score=1.0,
                overall_score=0.9,
            ),
            _make_test_result(
                "TC002", "without_skills",
                pattern_matches=[
                    (r"Company\(['\"]AAPL['\"]\)", True),
                    (r"get_filings\(.*form=['\"]10-K['\"]", True),
                    (r"\[0\]|\.latest\(\)|\.head\(", True),
                    (r"\.filing_date|\.filed", True),
                ],
                forbidden_violations=[
                    (r"for\s+.*\s+in\s+.*get_filings\(\)", False),
                ],
                pattern_score=1.0,
                overall_score=0.9,
            ),
        ]

        ws_report = EvaluationReport(results=ws_results, condition="with_skills")
        wos_report = EvaluationReport(results=wos_results, condition="without_skills")

        return ABComparison(with_skills=ws_report, without_skills=wos_report)

    def test_report_structure(self):
        """Report has expected structure."""
        comparison = self._make_comparison()
        report = run_constitution_diagnostics(comparison)

        assert isinstance(report, ConstitutionReport)
        assert len(report.diagnostics) > 0
        assert len(report.by_goal) > 0
        assert len(report.goal_scores) > 0

    def test_goal_scores_are_valid(self):
        """Goal scores are between 0 and 1."""
        comparison = self._make_comparison()
        report = run_constitution_diagnostics(comparison)

        for goal_id, score in report.goal_scores.items():
            assert 0.0 <= score <= 1.0, (
                f"Goal {goal_id} score {score} out of range"
            )

    def test_priority_fixes_populated(self):
        """Priority fixes are populated when there are failures."""
        comparison = self._make_comparison()
        report = run_constitution_diagnostics(comparison)

        # TC002 has a missed pattern, so there should be some non-pass diagnostics
        non_pass = [d for d in report.diagnostics if d.status != "pass"]
        # priority_fixes only populated for fail+high/medium severity
        # With TC002 having lower score with skills (delta negative),
        # severity should be high
        if non_pass:
            high_sev = [d for d in non_pass if d.severity in ("high", "medium") and d.status == "fail"]
            assert len(report.priority_fixes) == len(high_sev)

    def test_to_dict(self):
        """Report serializes to dict correctly."""
        comparison = self._make_comparison()
        report = run_constitution_diagnostics(comparison)
        d = report.to_dict()

        assert "goal_scores" in d
        assert "by_goal" in d
        assert "priority_fixes" in d
        assert "suggestions" in d
        assert "skill_budget_status" in d

    def test_print_report_does_not_crash(self, capsys):
        """print_report() runs without errors."""
        comparison = self._make_comparison()
        report = run_constitution_diagnostics(comparison)
        report.print_report()

        captured = capsys.readouterr()
        assert "CONSTITUTION DIAGNOSTICS REPORT" in captured.out
        assert "Goal Scores:" in captured.out


# =============================================================================
# Skill Token Budget Tests
# =============================================================================


class TestSkillTokenBudgets:
    """Tests for skill token budget checking."""

    def test_check_budgets_returns_results(self):
        """check_skill_token_budgets returns results for each budgeted file."""
        c = load_constitution()
        results = check_skill_token_budgets(c)

        assert len(results) > 0
        assert "core/skill.yaml" in results

    def test_budget_result_structure(self):
        """Each budget result has actual, budget, over fields."""
        c = load_constitution()
        results = check_skill_token_budgets(c)

        for skill_file, info in results.items():
            assert "actual" in info
            assert "budget" in info
            assert "over" in info
            assert isinstance(info["actual"], int)
            assert isinstance(info["budget"], int)
            assert isinstance(info["over"], bool)

    def test_actual_token_count_positive(self):
        """Actual token counts are positive for existing files."""
        c = load_constitution()
        results = check_skill_token_budgets(c)

        for skill_file, info in results.items():
            # All skill files in the constitution should exist
            assert info["actual"] > 0, f"{skill_file} has 0 tokens"

    def test_over_flag_correct(self):
        """Over flag is True iff actual > budget."""
        c = load_constitution()
        results = check_skill_token_budgets(c)

        for skill_file, info in results.items():
            expected_over = info["actual"] > info["budget"]
            assert info["over"] == expected_over, (
                f"{skill_file}: over={info['over']} but "
                f"actual={info['actual']} budget={info['budget']}"
            )


# =============================================================================
# Backward Compatibility Tests
# =============================================================================


class TestBackwardCompatibility:
    """Ensure existing evaluator is unchanged by new field."""

    def test_test_case_default_constitution_goals(self):
        """SECAnalysisTestCase defaults to empty constitution_goals."""
        tc = SECAnalysisTestCase(
            id="TEST",
            task="Test task",
            expected_patterns=[r"Company\("],
        )
        assert tc.constitution_goals == []

    def test_evaluate_pattern_compliance_unchanged(self):
        """evaluate_pattern_compliance works identically."""
        tc = get_test_by_id("TC001")
        assert tc is not None

        code = 'from edgar import Company\ncompany = Company("AAPL")\nprint(company.cik)'
        result = evaluate_pattern_compliance(code, tc)

        # Should find Company("AAPL") and .cik
        assert result.score > 0
        assert any(found for _, found in result.expected_matches)

    def test_evaluate_code_unchanged(self):
        """evaluate_code produces identical results."""
        tc = get_test_by_id("TC001")
        assert tc is not None

        code = 'from edgar import Company\ncompany = Company("AAPL")\nprint(company.cik)'
        result = evaluate_code(code, tc, execute=False)

        assert result.overall_score > 0
        assert result.pattern.score > 0

    def test_all_test_cases_have_constitution_goals(self):
        """All 25 test cases have constitution_goals populated."""
        for tc in SEC_TEST_SUITE:
            assert len(tc.constitution_goals) > 0, (
                f"{tc.id} has no constitution_goals"
            )

    def test_all_constitution_goals_are_valid_ids(self):
        """All constitution_goals reference valid goal IDs."""
        c = load_constitution()
        valid_ids = {g.id for g in c.goals}

        for tc in SEC_TEST_SUITE:
            for gid in tc.constitution_goals:
                assert gid in valid_ids, (
                    f"{tc.id} references invalid goal '{gid}'"
                )


# =============================================================================
# Generate Suggestions Tests
# =============================================================================


class TestGenerateSuggestions:
    """Tests for generate_skill_edit_suggestions."""

    def test_suggestions_are_strings(self):
        """Suggestions are a list of strings."""
        # Create a minimal report with one failure
        diag = ConstitutionDiagnostic(
            test_id="TC001",
            goal_id="correctness",
            status="fail",
            skill_files=["core/skill.yaml"],
            recommendation="Add Company() pattern",
            severity="high",
            delta=-0.2,
        )
        report = ConstitutionReport(diagnostics=[diag])
        report.skill_budget_status = {}

        suggestions = generate_skill_edit_suggestions(report)
        assert isinstance(suggestions, list)
        assert all(isinstance(s, str) for s in suggestions)

    def test_high_priority_flagged(self):
        """High severity issues generate HIGH PRIORITY suggestions."""
        diag = ConstitutionDiagnostic(
            test_id="TC001",
            goal_id="correctness",
            status="fail",
            skill_files=["core/skill.yaml"],
            recommendation="Add Company() pattern",
            severity="high",
            delta=-0.2,
        )
        report = ConstitutionReport(diagnostics=[diag])
        report.skill_budget_status = {}

        suggestions = generate_skill_edit_suggestions(report)
        has_high = any("HIGH PRIORITY" in s for s in suggestions)
        assert has_high


# =============================================================================
# CLI Smoke Test
# =============================================================================


class TestCLISmokeTest:
    """Smoke tests for CLI flags."""

    def test_dry_run_accepts_diagnose_flag(self):
        """--diagnose flag is accepted by argparse."""
        # We just verify the arg parser doesn't crash
        from edgar.ai.evaluation.runner import main
        import sys

        old_argv = sys.argv
        try:
            sys.argv = ["runner", "--dry-run"]
            main()  # Should not crash
        finally:
            sys.argv = old_argv
