"""
Claude Code-native Skill Evaluation Runner.

Instead of calling the Anthropic API directly, this runner generates prompts
for Claude Code subagents (Task tool). Each subagent is a fresh context
with no bleed between tests.

Workflow (driven by Claude Code in conversation):
    1. prompts = runner.get_subagent_prompts(["TC001", "TC002"])
    2. For each prompt, Claude Code spawns a Task subagent
    3. Collect code strings from each subagent response
    4. result = runner.evaluate(with_code, without_code, diagnose=True)

Example:
    >>> from edgar.ai.evaluation.cc_runner import ClaudeCodeRunner
    >>>
    >>> runner = ClaudeCodeRunner()
    >>> prompts = runner.get_subagent_prompts(["TC001", "TC002"])
    >>> # ... Claude Code spawns subagents and collects code ...
    >>> comparison = runner.evaluate(with_code, without_code, diagnose=True)
"""

from typing import Callable, Dict, List, Optional, Tuple

from edgar.ai.evaluation.harness import ABComparison, SkillEvaluationHarness
from edgar.ai.evaluation.judge import (
    JudgeComparison,
    JudgeScore,
    build_judge_comparison,
    build_judge_prompt,
    format_judge_report,
)
from edgar.ai.evaluation.runner import (
    build_prompt,
    extract_code_from_response,
    load_skill_context,
    get_minimal_context,
)
from edgar.ai.evaluation.test_cases import (
    SEC_TEST_SUITE,
    get_test_by_id,
)


class ClaudeCodeRunner:
    """Skill evaluation runner for Claude Code sessions.

    Instead of calling the Anthropic API, this generates prompts
    that Claude Code subagents execute. Each subagent is a fresh
    context with no bleed between tests.
    """

    def __init__(
        self,
        skill_context: Optional[str] = None,
        execute_code: bool = False,
    ):
        """
        Initialize the runner.

        Args:
            skill_context: Custom skill context (uses default if None)
            execute_code: Whether harness should execute code (default: False)
        """
        self.skill_context = skill_context
        self.harness = SkillEvaluationHarness(execute_code=execute_code)

    def format_subagent_prompt(self, test_id: str, with_skills: bool) -> str:
        """
        Format a single subagent prompt for one test + condition.

        Combines the system context and user task into a single prompt
        string suitable for a Task subagent.

        Args:
            test_id: Test case ID (e.g., "TC001")
            with_skills: Whether to include full skill context

        Returns:
            Single prompt string for the subagent

        Raises:
            ValueError: If test_id not found
        """
        test_case = get_test_by_id(test_id)
        if not test_case:
            raise ValueError(f"Test case '{test_id}' not found")

        system_prompt, user_prompt = build_prompt(
            test_case, with_skills, self.skill_context
        )

        return (
            f"{system_prompt}\n\n"
            f"{user_prompt}\n\n"
            f"IMPORTANT: Respond with ONLY Python code. No explanations, "
            f"no markdown formatting, no tool calls. Just the raw Python code."
        )

    def get_subagent_prompts(
        self,
        test_ids: Optional[List[str]] = None,
    ) -> List[dict]:
        """
        Generate prompts for all test × condition combinations.

        Returns a list of dicts, each containing:
        - test_id: The test case ID
        - condition: "with_skills" or "without_skills"
        - prompt: The prompt string for the subagent

        Args:
            test_ids: Specific test IDs to generate prompts for.
                      Uses all tests if None.

        Returns:
            List of prompt dicts (2 entries per test)
        """
        if test_ids is None:
            test_ids = [t.id for t in SEC_TEST_SUITE]

        prompts = []
        for test_id in test_ids:
            test_case = get_test_by_id(test_id)
            if not test_case:
                continue

            for with_skills in [True, False]:
                condition = "with_skills" if with_skills else "without_skills"
                prompt = self.format_subagent_prompt(test_id, with_skills)
                prompts.append({
                    "test_id": test_id,
                    "condition": condition,
                    "prompt": prompt,
                })

        return prompts

    def evaluate(
        self,
        with_skills_code: Dict[str, str],
        without_skills_code: Dict[str, str],
        diagnose: bool = False,
    ) -> ABComparison:
        """
        Evaluate collected code from subagents.

        Args:
            with_skills_code: Dict mapping test_id → code (with skills)
            without_skills_code: Dict mapping test_id → code (without skills)
            diagnose: Whether to run constitution diagnostics

        Returns:
            ABComparison with detailed results
        """
        comparison = self.harness.compare_conditions(
            with_skills_code,
            without_skills_code,
        )

        if diagnose:
            from edgar.ai.evaluation.diagnostics import run_constitution_diagnostics

            diag_report = run_constitution_diagnostics(comparison)
            diag_report.print_report()

            if not hasattr(comparison, 'metadata') or not comparison.metadata:
                comparison.metadata = {}
            comparison.metadata["constitution_diagnostics"] = diag_report.to_dict()

        return comparison

    def run_full(
        self,
        test_ids: Optional[List[str]] = None,
        diagnose: bool = False,
    ) -> Tuple[List[dict], Callable[[Dict[str, str], Dict[str, str]], ABComparison]]:
        """
        Convenience method: returns prompts and an evaluate callback.

        Usage:
            prompts, evaluate = runner.run_full(["TC001", "TC002"])
            # ... spawn subagents, collect code ...
            comparison = evaluate(with_code, without_code)

        Args:
            test_ids: Test IDs to run (all if None)
            diagnose: Whether evaluate callback runs diagnostics

        Returns:
            Tuple of (prompts, evaluate_callback)
        """
        prompts = self.get_subagent_prompts(test_ids)

        def evaluate_callback(
            with_skills_code: Dict[str, str],
            without_skills_code: Dict[str, str],
        ) -> ABComparison:
            return self.evaluate(with_skills_code, without_skills_code, diagnose=diagnose)

        return prompts, evaluate_callback

    def get_judge_prompts(
        self,
        with_skills_code: Dict[str, str],
        without_skills_code: Dict[str, str],
    ) -> List[dict]:
        """Generate judge prompts for all code samples.

        Returns one entry per code sample (2 per test: with and without skills).

        Args:
            with_skills_code: test_id -> generated code (with skills)
            without_skills_code: test_id -> generated code (without skills)

        Returns:
            List of dicts with test_id, condition, and prompt keys
        """
        prompts = []
        all_test_ids = sorted(
            set(with_skills_code.keys()) | set(without_skills_code.keys())
        )

        for test_id in all_test_ids:
            test_case = get_test_by_id(test_id)
            if not test_case:
                continue

            if test_id in with_skills_code:
                prompts.append({
                    "test_id": test_id,
                    "condition": "with_skills",
                    "prompt": build_judge_prompt(
                        test_id, with_skills_code[test_id], test_case
                    ),
                })

            if test_id in without_skills_code:
                prompts.append({
                    "test_id": test_id,
                    "condition": "without_skills",
                    "prompt": build_judge_prompt(
                        test_id, without_skills_code[test_id], test_case
                    ),
                })

        return prompts

    def judge(
        self,
        with_scores: Dict[str, JudgeScore],
        without_scores: Dict[str, JudgeScore],
        print_report: bool = True,
    ) -> JudgeComparison:
        """Build and optionally print a judge comparison.

        Args:
            with_scores: test_id -> JudgeScore for with-skills condition
            without_scores: test_id -> JudgeScore for without-skills condition
            print_report: Whether to print the formatted report

        Returns:
            JudgeComparison with deltas and winner
        """
        comparison = build_judge_comparison(with_scores, without_scores)
        if print_report:
            print(format_judge_report(comparison))
        return comparison

    @staticmethod
    def extract_code(response_text: str) -> str:
        """Extract Python code from a subagent response.

        Delegates to the existing extract_code_from_response utility.

        Args:
            response_text: Raw text from subagent

        Returns:
            Extracted Python code
        """
        return extract_code_from_response(response_text)
