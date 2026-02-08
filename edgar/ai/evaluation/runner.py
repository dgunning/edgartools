"""
Automated Skill Test Runner.

This module provides the SkillTestRunner class that automatically generates
code for test cases using the Anthropic API, then evaluates the results.

This enables the full iteration loop:
    1. Generate code with skills → evaluate
    2. Generate code without skills → evaluate
    3. Compare results → identify weak spots
    4. Adjust skills → repeat

Requirements:
    pip install anthropic

Example:
    >>> from edgar.ai.evaluation import SkillTestRunner
    >>>
    >>> runner = SkillTestRunner()
    >>> comparison = runner.run_ab_comparison(["TC001", "TC002", "TC003"])
    >>> print(comparison.summary())
    >>>
    >>> # Get improvement suggestions
    >>> suggestions = runner.analyze_for_improvements(comparison)
    >>> for s in suggestions:
    ...     print(f"- {s}")
"""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from edgar.ai.evaluation.harness import (
    ABComparison,
    EvaluationReport,
    SkillEvaluationHarness,
    TestResult,
)
from edgar.ai.evaluation.test_cases import (
    SEC_TEST_SUITE,
    SECAnalysisTestCase,
    get_test_by_id,
)


# =============================================================================
# Skill Context Loading
# =============================================================================


def load_skill_context() -> str:
    """
    Load the EdgarTools skill context from all skill.yaml files.

    Loads core skill first, then all specialized skills (financials,
    holdings, ownership, reports, xbrl) so the "with skills" condition
    has access to the full skill library.

    Returns:
        Combined skill context as a string
    """
    from pathlib import Path

    skill_dir = Path(__file__).parent.parent / "skills"
    parts = []

    # Load core skill first
    core_skill = skill_dir / "core" / "skill.yaml"
    if core_skill.exists():
        parts.append(core_skill.read_text())

    # Load all other skill subdirectories
    for subdir in sorted(skill_dir.iterdir()):
        if subdir.is_dir() and subdir.name != "core":
            skill_file = subdir / "skill.yaml"
            if skill_file.exists():
                parts.append(skill_file.read_text())

    return "\n\n".join(parts)


def get_minimal_context() -> str:
    """
    Get realistic minimal context for the without-skills baseline.

    Provides basic object descriptions so the baseline measures the marginal
    value of full skill patterns, not "skills vs nothing."

    Returns:
        Minimal but realistic EdgarTools context
    """
    return """EdgarTools is a Python library for SEC filing analysis.

Key objects:
- Company(ticker_or_cik): Look up a company. Properties: .cik, .name, .tickers, .sic
- company.get_filings(form=...) -> Filings: Get filings, filterable by form type.
  Use [0] for most recent. Use .head(n) for first n.
- company.get_facts() -> EntityFacts: Get XBRL facts.
  .income_statement(periods=N, annual=True/False)
  .balance_sheet(periods=N, annual=True/False)
  .cash_flow(periods=N, annual=True/False)
- filing.obj() -> typed object (TenK, TenQ, EightK, etc.)
- get_filings(form=...) -> recent filings across all companies
- get_current_filings() -> today's filings, use .filter(form=...)
- find(search_id=accession_number) -> Filing

Imports: from edgar import Company, get_filings, get_current_filings, find"""


# =============================================================================
# Code Extraction
# =============================================================================


def extract_code_from_response(response: str) -> str:
    """
    Extract Python code from an LLM response.

    Handles:
    - Code blocks with ```python ... ```
    - Code blocks with ``` ... ```
    - Raw code (no markdown)

    Args:
        response: Raw LLM response text

    Returns:
        Extracted Python code
    """
    # Try to find ```python code blocks first
    python_blocks = re.findall(r'```python\n(.*?)```', response, re.DOTALL)
    if python_blocks:
        return '\n'.join(python_blocks).strip()

    # Try generic code blocks
    code_blocks = re.findall(r'```\n?(.*?)```', response, re.DOTALL)
    if code_blocks:
        return '\n'.join(code_blocks).strip()

    # Look for lines that look like code (imports, assignments, function calls)
    lines = response.split('\n')
    code_lines = []
    in_code = False

    for line in lines:
        stripped = line.strip()
        # Heuristics for code lines
        if (stripped.startswith('from ') or
            stripped.startswith('import ') or
            stripped.startswith('company') or
            stripped.startswith('filing') or
            stripped.startswith('Company(') or
            '=' in stripped and not stripped.startswith('#') or
            stripped.startswith('print(') or
            stripped.startswith('for ') or
            stripped.startswith('if ')):
            code_lines.append(line)
            in_code = True
        elif in_code and stripped and not stripped.startswith('#'):
            # Continue collecting if we're in a code block
            if stripped[0].isalpha() or stripped[0] in '([':
                code_lines.append(line)

    if code_lines:
        return '\n'.join(code_lines).strip()

    # Fallback: return as-is
    return response.strip()


# =============================================================================
# Prompt Construction
# =============================================================================


def build_prompt(
    test_case: SECAnalysisTestCase,
    with_skills: bool,
    skill_context: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Build system and user prompts for code generation.

    Args:
        test_case: The test case to generate code for
        with_skills: Whether to include skill context
        skill_context: Custom skill context (uses default if None)

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    if with_skills:
        context = skill_context or load_skill_context()
        system_prompt = f"""You are an expert Python developer using the EdgarTools library for SEC filing analysis.

Here is the EdgarTools skill documentation:

{context}

Write concise, correct Python code. Only output the code, no explanations.
Use the patterns from the documentation. Be efficient - avoid unnecessary loops or API calls."""
    else:
        minimal = get_minimal_context()
        system_prompt = f"""You are a Python developer. You have access to the EdgarTools library.

Available imports: {minimal}

Write Python code to complete the task. Only output the code, no explanations."""

    user_prompt = f"""Task: {test_case.task}

Write Python code to accomplish this task. Output only the code."""

    return system_prompt, user_prompt


# =============================================================================
# LLM Client
# =============================================================================


@dataclass
class GenerationResult:
    """Result from generating code for a test case."""

    test_id: str
    condition: str  # "with_skills" or "without_skills"
    code: str
    raw_response: str
    model: str
    tokens_used: int
    generation_time_ms: float
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "condition": self.condition,
            "code": self.code,
            "raw_response": self.raw_response,
            "model": self.model,
            "tokens_used": self.tokens_used,
            "generation_time_ms": self.generation_time_ms,
            "error": self.error,
        }


class SkillTestRunner:
    """
    Automated test runner that generates code via Anthropic API.

    This class handles:
    - Generating code for test cases with/without skill context
    - Running A/B comparisons
    - Analyzing results for improvement opportunities

    Example:
        >>> runner = SkillTestRunner(api_key="sk-...")
        >>>
        >>> # Run single test
        >>> result = runner.generate_code("TC001", with_skills=True)
        >>> print(result.code)
        >>>
        >>> # Run A/B comparison
        >>> comparison = runner.run_ab_comparison(["TC001", "TC002"])
        >>> print(comparison.summary())
        >>>
        >>> # Get improvement suggestions
        >>> suggestions = runner.analyze_for_improvements(comparison)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 1024,
        skill_context: Optional[str] = None,
    ):
        """
        Initialize the test runner.

        Args:
            api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)
            model: Model to use for code generation
            max_tokens: Maximum tokens for generation
            skill_context: Custom skill context (uses default if None)
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self.max_tokens = max_tokens
        self.skill_context = skill_context
        self.harness = SkillEvaluationHarness()

        self._client = None

    @property
    def client(self):
        """Lazy-load Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package required. Install with: pip install anthropic"
                )
        return self._client

    def generate_code(
        self,
        test_id: str,
        with_skills: bool,
    ) -> GenerationResult:
        """
        Generate code for a single test case.

        Args:
            test_id: Test case ID (e.g., "TC001")
            with_skills: Whether to include skill context

        Returns:
            GenerationResult with generated code
        """
        import time

        test_case = get_test_by_id(test_id)
        if not test_case:
            return GenerationResult(
                test_id=test_id,
                condition="with_skills" if with_skills else "without_skills",
                code="",
                raw_response="",
                model=self.model,
                tokens_used=0,
                generation_time_ms=0,
                error=f"Test case '{test_id}' not found",
            )

        system_prompt, user_prompt = build_prompt(
            test_case, with_skills, self.skill_context
        )

        condition = "with_skills" if with_skills else "without_skills"

        try:
            start = time.time()

            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            elapsed_ms = (time.time() - start) * 1000
            raw_response = response.content[0].text
            code = extract_code_from_response(raw_response)

            tokens_used = response.usage.input_tokens + response.usage.output_tokens

            return GenerationResult(
                test_id=test_id,
                condition=condition,
                code=code,
                raw_response=raw_response,
                model=self.model,
                tokens_used=tokens_used,
                generation_time_ms=elapsed_ms,
            )

        except Exception as e:
            return GenerationResult(
                test_id=test_id,
                condition=condition,
                code="",
                raw_response="",
                model=self.model,
                tokens_used=0,
                generation_time_ms=0,
                error=str(e),
            )

    def generate_for_suite(
        self,
        test_ids: Optional[List[str]] = None,
        with_skills: bool = True,
    ) -> Dict[str, GenerationResult]:
        """
        Generate code for multiple test cases.

        Args:
            test_ids: List of test IDs (uses all if None)
            with_skills: Whether to include skill context

        Returns:
            Dict mapping test_id to GenerationResult
        """
        if test_ids is None:
            test_ids = [t.id for t in SEC_TEST_SUITE]

        results = {}
        for test_id in test_ids:
            print(f"  Generating {test_id}...", end=" ", flush=True)
            result = self.generate_code(test_id, with_skills)
            results[test_id] = result
            status = "OK" if not result.error else f"ERROR: {result.error}"
            print(status)

        return results

    def run_ab_comparison(
        self,
        test_ids: Optional[List[str]] = None,
        runs_per_condition: int = 1,
        diagnose: bool = False,
    ) -> ABComparison:
        """
        Run A/B comparison between with-skills and without-skills.

        Args:
            test_ids: List of test IDs to test (uses all if None)
            runs_per_condition: Number of runs per condition (for variance)
            diagnose: Whether to run constitution diagnostics after evaluation

        Returns:
            ABComparison with detailed results
        """
        if test_ids is None:
            test_ids = [t.id for t in SEC_TEST_SUITE]

        print("=" * 60)
        print("A/B SKILL COMPARISON")
        print("=" * 60)

        # Generate with skills
        print("\n[1/2] Generating code WITH skills...")
        with_skills_gen = self.generate_for_suite(test_ids, with_skills=True)
        with_skills_code = {
            tid: r.code for tid, r in with_skills_gen.items() if not r.error
        }

        # Generate without skills
        print("\n[2/2] Generating code WITHOUT skills...")
        without_skills_gen = self.generate_for_suite(test_ids, with_skills=False)
        without_skills_code = {
            tid: r.code for tid, r in without_skills_gen.items() if not r.error
        }

        # Evaluate both
        print("\n[Evaluating...]")
        comparison = self.harness.compare_conditions(
            with_skills_code,
            without_skills_code,
        )

        # Attach generation metadata
        comparison.metadata = {
            "with_skills_generation": {
                tid: r.to_dict() for tid, r in with_skills_gen.items()
            },
            "without_skills_generation": {
                tid: r.to_dict() for tid, r in without_skills_gen.items()
            },
        }

        print("\n" + comparison.summary())

        # Run constitution diagnostics if requested
        if diagnose:
            from edgar.ai.evaluation.diagnostics import run_constitution_diagnostics

            print("\n[Running constitution diagnostics...]")
            diag_report = run_constitution_diagnostics(comparison)
            diag_report.print_report()

            # Attach to comparison metadata
            if not hasattr(comparison, 'metadata') or comparison.metadata is None:
                comparison.metadata = {}
            comparison.metadata["constitution_diagnostics"] = diag_report.to_dict()

        return comparison

    def analyze_for_improvements(
        self,
        comparison: ABComparison,
    ) -> List[str]:
        """
        Analyze comparison results and suggest skill improvements.

        Args:
            comparison: ABComparison from run_ab_comparison

        Returns:
            List of improvement suggestions
        """
        suggestions = []

        ws = comparison.with_skills
        wos = comparison.without_skills

        # Check if skills actually help
        if not comparison.improvement.get("skills_better", False):
            suggestions.append(
                "WARNING: Skills did NOT improve performance. Review skill content for correctness."
            )

        # Identify weak categories
        ws_cats = ws.summary_stats.get("by_category", {})
        for cat, score in ws_cats.items():
            if score < 0.7:
                suggestions.append(
                    f"Category '{cat}' scores low ({score:.2f}). "
                    f"Add more patterns/examples for {cat} tasks."
                )

        # Identify weak difficulties
        ws_diffs = ws.summary_stats.get("by_difficulty", {})
        for diff, score in ws_diffs.items():
            if score < 0.6:
                suggestions.append(
                    f"Difficulty '{diff}' scores low ({score:.2f}). "
                    f"Consider adding more guidance for complex tasks."
                )

        # Analyze pattern compliance per test
        for result in ws.results:
            if not result.evaluation.pattern.compliant:
                test = get_test_by_id(result.test_id)
                if test:
                    # Find which patterns were missed
                    missed = [
                        p for p, found in result.evaluation.pattern.expected_matches
                        if not found
                    ]
                    if missed:
                        suggestions.append(
                            f"{result.test_id}: Missing patterns {missed[:2]}. "
                            f"Add examples showing these patterns."
                        )

                    # Find forbidden pattern violations
                    violations = [
                        p for p, found in result.evaluation.pattern.forbidden_violations
                        if found
                    ]
                    if violations:
                        suggestions.append(
                            f"{result.test_id}: Anti-pattern violations {violations[:2]}. "
                            f"Add 'avoid' section warning against these."
                        )

        # Compare improvement by category
        for cat, imp in comparison.improvement.get("by_category", {}).items():
            if imp < 0:
                suggestions.append(
                    f"Category '{cat}' performs WORSE with skills ({imp:+.2f}). "
                    f"Review skill patterns for this category."
                )
            elif imp < 0.1:
                suggestions.append(
                    f"Category '{cat}' shows minimal improvement ({imp:+.2f}). "
                    f"Consider adding more specific patterns."
                )

        if not suggestions:
            suggestions.append(
                "Skills performing well across all categories. "
                "Consider adding more test cases for edge cases."
            )

        return suggestions

    def save_results(
        self,
        comparison: ABComparison,
        output_dir: Path | str,
    ) -> Path:
        """
        Save comparison results to a timestamped JSON file.

        Args:
            comparison: ABComparison to save
            output_dir: Directory to save results

        Returns:
            Path to saved file
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"skill_evaluation_{timestamp}.json"
        filepath = output_dir / filename

        data = {
            "timestamp": timestamp,
            "comparison": comparison.to_dict(),
            "suggestions": self.analyze_for_improvements(comparison),
        }

        # Include constitution diagnostics if present
        if hasattr(comparison, 'metadata') and comparison.metadata:
            diag = comparison.metadata.get("constitution_diagnostics")
            if diag:
                data["constitution_diagnostics"] = diag

        filepath.write_text(json.dumps(data, indent=2))
        print(f"\nResults saved to: {filepath}")

        return filepath


# =============================================================================
# CLI Interface
# =============================================================================


def main():
    """CLI entry point for running skill evaluations."""
    import argparse

    parser = argparse.ArgumentParser(
        description="EdgarTools Skill Test Runner"
    )
    parser.add_argument(
        "--test-ids",
        nargs="+",
        help="Specific test IDs to run (default: all)",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-20250514",
        help="Model to use for generation",
    )
    parser.add_argument(
        "--output-dir",
        default="./skill_evaluation_results",
        help="Directory to save results",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Run constitution diagnostics after evaluation",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be run without calling API",
    )
    args = parser.parse_args()

    if args.dry_run:
        test_ids = args.test_ids or [t.id for t in SEC_TEST_SUITE]
        print("Would run A/B comparison for:")
        for tid in test_ids:
            test = get_test_by_id(tid)
            if test:
                print(f"  {tid}: {test.task[:50]}...")
        print(f"\nModel: {args.model}")
        print(f"Output: {args.output_dir}")
        return

    runner = SkillTestRunner(model=args.model)
    comparison = runner.run_ab_comparison(
        test_ids=args.test_ids,
        diagnose=args.diagnose,
    )

    # Show improvement suggestions
    print("\n" + "=" * 60)
    print("IMPROVEMENT SUGGESTIONS")
    print("=" * 60)
    suggestions = runner.analyze_for_improvements(comparison)
    for i, s in enumerate(suggestions, 1):
        print(f"{i}. {s}")

    # Save results
    runner.save_results(comparison, args.output_dir)


if __name__ == "__main__":
    main()
