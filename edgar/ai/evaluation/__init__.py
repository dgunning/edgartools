"""
Skill Evaluation Framework for EdgarTools.

This package provides tools for testing and measuring the effectiveness of
EdgarTools AI skills. It enables A/B testing between with-skills and
without-skills conditions to quantify improvement.

Components:
    - test_cases: SECAnalysisTestCase dataclass and predefined test suites
    - harness: SkillEvaluationHarness for running evaluations
    - evaluators: Automated evaluation functions for code correctness and patterns
    - runner: SkillTestRunner for automated code generation via Anthropic API

Usage:
    >>> from edgar.ai.evaluation import SkillTestRunner
    >>>
    >>> # Run A/B comparison (requires ANTHROPIC_API_KEY)
    >>> runner = SkillTestRunner()
    >>> comparison = runner.run_ab_comparison(["TC001", "TC002", "TC003"])
    >>> print(comparison.summary())
    >>>
    >>> # Get improvement suggestions
    >>> suggestions = runner.analyze_for_improvements(comparison)
    >>> for s in suggestions:
    ...     print(f"- {s}")
"""

from edgar.ai.evaluation.test_cases import (
    SECAnalysisTestCase,
    SEC_TEST_SUITE,
    get_test_by_id,
    get_tests_by_category,
    get_tests_by_difficulty,
)
from edgar.ai.evaluation.harness import (
    ABComparison,
    EvaluationReport,
    SkillEvaluationHarness,
    TestResult,
)
from edgar.ai.evaluation.evaluators import (
    count_tokens,
    evaluate_code_execution,
    evaluate_pattern_compliance,
    evaluate_token_efficiency,
)
from edgar.ai.evaluation.runner import (
    GenerationResult,
    SkillTestRunner,
    extract_code_from_response,
    load_skill_context,
)
from edgar.ai.evaluation.constitution import (
    Constitution,
    ConstitutionGoal,
    load_constitution,
)
from edgar.ai.evaluation.diagnostics import (
    ConstitutionDiagnostic,
    ConstitutionReport,
    generate_skill_edit_suggestions,
    run_constitution_diagnostics,
)
from edgar.ai.evaluation.agent import (
    AgentScore,
    AgentTestResult,
    AgentTestRunner,
    AgentTrace,
)
from edgar.ai.evaluation.judge import (
    JudgeComparison,
    JudgeScore,
    build_judge_comparison,
    build_judge_prompt,
    format_judge_report,
    parse_judge_response,
)
from edgar.ai.evaluation.cc_runner import ClaudeCodeRunner

__all__ = [
    # Test cases
    "SECAnalysisTestCase",
    "SEC_TEST_SUITE",
    "get_test_by_id",
    "get_tests_by_category",
    "get_tests_by_difficulty",
    # Harness
    "ABComparison",
    "EvaluationReport",
    "SkillEvaluationHarness",
    "TestResult",
    # Evaluators
    "count_tokens",
    "evaluate_code_execution",
    "evaluate_pattern_compliance",
    "evaluate_token_efficiency",
    # Runner (code-gen)
    "GenerationResult",
    "SkillTestRunner",
    "extract_code_from_response",
    "load_skill_context",
    # Constitution & diagnostics
    "Constitution",
    "ConstitutionGoal",
    "load_constitution",
    "ConstitutionDiagnostic",
    "ConstitutionReport",
    "run_constitution_diagnostics",
    "generate_skill_edit_suggestions",
    # Agent-based evaluation
    "AgentScore",
    "AgentTestResult",
    "AgentTestRunner",
    "AgentTrace",
    # LLM Judge
    "JudgeScore",
    "JudgeComparison",
    "build_judge_prompt",
    "parse_judge_response",
    "build_judge_comparison",
    "format_judge_report",
    # Claude Code runner
    "ClaudeCodeRunner",
]
