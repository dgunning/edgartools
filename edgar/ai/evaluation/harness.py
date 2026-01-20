"""
Skill Evaluation Harness for A/B Testing.

This module provides the SkillEvaluationHarness class for running
skill effectiveness evaluations with A/B comparison between
with-skills and without-skills conditions.

Example:
    >>> from edgar.ai.evaluation import SkillEvaluationHarness, SEC_TEST_SUITE
    >>>
    >>> harness = SkillEvaluationHarness()
    >>> # Evaluate some generated code
    >>> results = harness.evaluate_code("TC001", code_sample)
    >>> print(results.overall_score)
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from edgar.ai.evaluation.evaluators import (
    CombinedEvaluation,
    evaluate_code,
)
from edgar.ai.evaluation.test_cases import (
    SECAnalysisTestCase,
    SEC_TEST_SUITE,
    get_test_by_id,
)


@dataclass
class TestResult:
    """
    Result of evaluating a single test case.

    Attributes:
        test_id: ID of the test case
        condition: "with_skills" or "without_skills"
        code: Generated code that was evaluated
        evaluation: Detailed evaluation results
        run_timestamp: When the evaluation was run
        metadata: Optional additional data
    """

    test_id: str
    condition: str
    code: str
    evaluation: CombinedEvaluation
    run_timestamp: str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Whether the test passed (execution + pattern compliance)."""
        return (
            self.evaluation.execution.success
            and self.evaluation.pattern.compliant
        )

    @property
    def score(self) -> float:
        """Overall score from 0.0 to 1.0."""
        return self.evaluation.overall_score

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "test_id": self.test_id,
            "condition": self.condition,
            "code": self.code,
            "evaluation": self.evaluation.to_dict(),
            "run_timestamp": self.run_timestamp,
            "metadata": self.metadata,
            "success": self.success,
            "score": self.score,
        }


@dataclass
class EvaluationReport:
    """
    Summary report from running multiple test evaluations.

    Attributes:
        results: Individual test results
        condition: Evaluation condition used
        run_timestamp: When the evaluation suite was run
        summary_stats: Aggregate statistics
    """

    results: List[TestResult]
    condition: str = "unknown"
    run_timestamp: str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    summary_stats: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Calculate summary statistics after initialization."""
        if self.results and not self.summary_stats:
            self._calculate_stats()

    def _calculate_stats(self):
        """Calculate aggregate statistics from results."""
        if not self.results:
            self.summary_stats = {}
            return

        scores = [r.score for r in self.results]
        successes = sum(1 for r in self.results if r.success)

        # Group by category
        by_category: Dict[str, List[float]] = {}
        for r in self.results:
            test = get_test_by_id(r.test_id)
            if test:
                cat = test.category
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(r.score)

        # Group by difficulty
        by_difficulty: Dict[str, List[float]] = {}
        for r in self.results:
            test = get_test_by_id(r.test_id)
            if test:
                diff = test.difficulty
                if diff not in by_difficulty:
                    by_difficulty[diff] = []
                by_difficulty[diff].append(r.score)

        self.summary_stats = {
            "total_tests": len(self.results),
            "passed": successes,
            "failed": len(self.results) - successes,
            "pass_rate": round(successes / len(self.results), 3),
            "mean_score": round(sum(scores) / len(scores), 3),
            "min_score": round(min(scores), 3),
            "max_score": round(max(scores), 3),
            "by_category": {
                cat: round(sum(s) / len(s), 3)
                for cat, s in by_category.items()
            },
            "by_difficulty": {
                diff: round(sum(s) / len(s), 3)
                for diff, s in by_difficulty.items()
            },
        }

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "=" * 60,
            f"EVALUATION REPORT - {self.condition}",
            f"Run: {self.run_timestamp}",
            "=" * 60,
            "",
            f"Tests: {self.summary_stats.get('total_tests', 0)}",
            f"Passed: {self.summary_stats.get('passed', 0)}",
            f"Failed: {self.summary_stats.get('failed', 0)}",
            f"Pass Rate: {self.summary_stats.get('pass_rate', 0) * 100:.1f}%",
            f"Mean Score: {self.summary_stats.get('mean_score', 0):.3f}",
            "",
            "By Category:",
        ]

        for cat, score in self.summary_stats.get("by_category", {}).items():
            lines.append(f"  {cat}: {score:.3f}")

        lines.append("")
        lines.append("By Difficulty:")
        for diff, score in self.summary_stats.get("by_difficulty", {}).items():
            lines.append(f"  {diff}: {score:.3f}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "condition": self.condition,
            "run_timestamp": self.run_timestamp,
            "summary_stats": self.summary_stats,
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: Path | str):
        """Save report to JSON file."""
        path = Path(path)
        path.write_text(self.to_json())


@dataclass
class ABComparison:
    """
    Comparison between with-skills and without-skills conditions.

    Attributes:
        with_skills: Report from with-skills condition
        without_skills: Report from without-skills condition
        improvement: Calculated improvement metrics
    """

    with_skills: EvaluationReport
    without_skills: EvaluationReport
    improvement: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Calculate improvement metrics."""
        if not self.improvement:
            self._calculate_improvement()

    def _calculate_improvement(self):
        """Calculate improvement from without-skills to with-skills."""
        ws = self.with_skills.summary_stats
        wos = self.without_skills.summary_stats

        if not ws or not wos:
            self.improvement = {}
            return

        # Absolute improvements
        score_diff = ws.get("mean_score", 0) - wos.get("mean_score", 0)
        pass_rate_diff = ws.get("pass_rate", 0) - wos.get("pass_rate", 0)

        # Relative improvements
        wos_score = wos.get("mean_score", 0)
        if wos_score > 0:
            score_pct = (score_diff / wos_score) * 100
        else:
            score_pct = float("inf") if score_diff > 0 else 0

        self.improvement = {
            "score_absolute": round(score_diff, 3),
            "score_relative_pct": round(score_pct, 1),
            "pass_rate_absolute": round(pass_rate_diff, 3),
            "pass_rate_relative_pct": round(pass_rate_diff * 100, 1),
            "skills_better": score_diff > 0,
        }

        # Category-level improvements
        cat_improvements = {}
        for cat in ws.get("by_category", {}):
            if cat in wos.get("by_category", {}):
                diff = ws["by_category"][cat] - wos["by_category"][cat]
                cat_improvements[cat] = round(diff, 3)
        self.improvement["by_category"] = cat_improvements

    def summary(self) -> str:
        """Generate human-readable comparison summary."""
        lines = [
            "=" * 60,
            "A/B COMPARISON: WITH SKILLS vs WITHOUT SKILLS",
            "=" * 60,
            "",
            "                    Without Skills    With Skills    Improvement",
            "                    --------------    -----------    -----------",
        ]

        ws = self.with_skills.summary_stats
        wos = self.without_skills.summary_stats

        lines.append(
            f"Mean Score:         {wos.get('mean_score', 0):>14.3f}"
            f"    {ws.get('mean_score', 0):>11.3f}"
            f"    {self.improvement.get('score_absolute', 0):>+11.3f}"
        )
        lines.append(
            f"Pass Rate:          {wos.get('pass_rate', 0) * 100:>13.1f}%"
            f"    {ws.get('pass_rate', 0) * 100:>10.1f}%"
            f"    {self.improvement.get('pass_rate_relative_pct', 0):>+10.1f}%"
        )

        lines.append("")
        lines.append("Category Improvements:")
        for cat, imp in self.improvement.get("by_category", {}).items():
            indicator = "+" if imp > 0 else ""
            lines.append(f"  {cat}: {indicator}{imp:.3f}")

        lines.append("")
        verdict = "WITH SKILLS" if self.improvement.get("skills_better") else "WITHOUT SKILLS"
        lines.append(f"Winner: {verdict}")
        lines.append("=" * 60)

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "with_skills": self.with_skills.to_dict(),
            "without_skills": self.without_skills.to_dict(),
            "improvement": self.improvement,
        }


class SkillEvaluationHarness:
    """
    Main harness for running skill effectiveness evaluations.

    This class provides methods to:
    - Evaluate individual code samples against test cases
    - Run full test suites
    - Compare A/B conditions

    Example:
        >>> harness = SkillEvaluationHarness()
        >>>
        >>> # Evaluate a single code sample
        >>> result = harness.evaluate_code("TC001", sample_code, condition="with_skills")
        >>>
        >>> # Run a full suite (with provided code samples)
        >>> code_samples = {"TC001": code1, "TC002": code2}
        >>> report = harness.run_suite(code_samples, condition="with_skills")
        >>> print(report.summary())
    """

    def __init__(
        self,
        test_suite: Optional[List[SECAnalysisTestCase]] = None,
        execute_code: bool = False,
    ):
        """
        Initialize the evaluation harness.

        Args:
            test_suite: Custom test suite (defaults to SEC_TEST_SUITE)
            execute_code: Whether to actually execute code (default: False)
        """
        self.test_suite = test_suite or SEC_TEST_SUITE
        self.execute_code = execute_code
        self._test_map = {t.id: t for t in self.test_suite}

    def evaluate_code(
        self,
        test_id: str,
        code: str,
        condition: str = "unknown",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TestResult:
        """
        Evaluate a code sample against a specific test case.

        Args:
            test_id: Test case ID (e.g., "TC001")
            code: Generated code to evaluate
            condition: Condition label (e.g., "with_skills", "without_skills")
            metadata: Optional additional metadata

        Returns:
            TestResult with detailed evaluation

        Raises:
            ValueError: If test_id not found

        Example:
            >>> harness = SkillEvaluationHarness()
            >>> result = harness.evaluate_code(
            ...     "TC001",
            ...     'from edgar import Company; Company("AAPL").cik',
            ...     condition="with_skills"
            ... )
            >>> print(f"Score: {result.score}")
        """
        test = self._test_map.get(test_id)
        if not test:
            raise ValueError(f"Test case '{test_id}' not found in suite")

        evaluation = evaluate_code(
            code=code,
            test_case=test,
            execute=self.execute_code,
        )

        return TestResult(
            test_id=test_id,
            condition=condition,
            code=code,
            evaluation=evaluation,
            metadata=metadata or {},
        )

    def run_suite(
        self,
        code_samples: Dict[str, str],
        condition: str = "unknown",
        test_ids: Optional[List[str]] = None,
    ) -> EvaluationReport:
        """
        Run evaluation suite with provided code samples.

        Args:
            code_samples: Dict mapping test_id to generated code
            condition: Condition label for this run
            test_ids: Optional list of specific test IDs to run

        Returns:
            EvaluationReport with all results and statistics

        Example:
            >>> harness = SkillEvaluationHarness()
            >>> samples = {
            ...     "TC001": 'from edgar import Company; Company("AAPL").cik',
            ...     "TC002": 'from edgar import Company; Company("AAPL").get_filings(form="10-K")[0]',
            ... }
            >>> report = harness.run_suite(samples, condition="with_skills")
            >>> print(report.summary())
        """
        results: List[TestResult] = []

        # Determine which tests to run
        if test_ids:
            tests_to_run = [self._test_map[tid] for tid in test_ids if tid in self._test_map]
        else:
            tests_to_run = [t for t in self.test_suite if t.id in code_samples]

        for test in tests_to_run:
            if test.id not in code_samples:
                continue

            code = code_samples[test.id]
            result = self.evaluate_code(
                test_id=test.id,
                code=code,
                condition=condition,
            )
            results.append(result)

        return EvaluationReport(
            results=results,
            condition=condition,
        )

    def compare_conditions(
        self,
        with_skills_samples: Dict[str, str],
        without_skills_samples: Dict[str, str],
    ) -> ABComparison:
        """
        Compare with-skills vs without-skills conditions.

        Args:
            with_skills_samples: Code samples generated WITH skills
            without_skills_samples: Code samples generated WITHOUT skills

        Returns:
            ABComparison with detailed comparison metrics

        Example:
            >>> harness = SkillEvaluationHarness()
            >>> with_skills = {"TC001": good_code}
            >>> without_skills = {"TC001": bad_code}
            >>> comparison = harness.compare_conditions(with_skills, without_skills)
            >>> print(comparison.summary())
        """
        with_report = self.run_suite(
            with_skills_samples,
            condition="with_skills",
        )
        without_report = self.run_suite(
            without_skills_samples,
            condition="without_skills",
        )

        return ABComparison(
            with_skills=with_report,
            without_skills=without_report,
        )

    def get_test(self, test_id: str) -> Optional[SECAnalysisTestCase]:
        """Get a test case by ID."""
        return self._test_map.get(test_id)

    def list_tests(self) -> List[str]:
        """List all test IDs in the suite."""
        return [t.id for t in self.test_suite]


# =============================================================================
# CLI Interface
# =============================================================================


def main():
    """CLI entry point for running evaluations."""
    import argparse

    parser = argparse.ArgumentParser(
        description="EdgarTools Skill Evaluation Harness"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List test cases without running evaluations",
    )
    parser.add_argument(
        "--list-tests",
        action="store_true",
        help="List all available test cases",
    )
    args = parser.parse_args()

    if args.list_tests or args.dry_run:
        print("Available Test Cases:")
        print("-" * 60)
        for test in SEC_TEST_SUITE:
            print(f"{test.id} [{test.difficulty}] [{test.category}]")
            print(f"  Task: {test.task}")
            print()
        return

    print("Skill Evaluation Harness")
    print("Use --list-tests to see available tests")
    print("Use --dry-run to verify configuration")


if __name__ == "__main__":
    main()
