"""
Automated Evaluators for Skill Testing.

This module provides functions to automatically evaluate generated code
for correctness, pattern compliance, and token efficiency.

Evaluation is fully automated (no LLM-as-judge) using:
    - Code execution with error capture
    - Regex pattern matching for API compliance
    - Simple token counting heuristic

Example:
    >>> from edgar.ai.evaluation.evaluators import (
    ...     evaluate_code_execution,
    ...     evaluate_pattern_compliance,
    ...     evaluate_token_efficiency
    ... )
    >>>
    >>> code = '''
    ... from edgar import Company
    ... company = Company("AAPL")
    ... print(company.cik)
    ... '''
    >>>
    >>> exec_result = evaluate_code_execution(code)
    >>> print(f"Executed: {exec_result['success']}")
"""

import re
import sys
import traceback
from dataclasses import dataclass, field
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

from edgar.ai.evaluation.test_cases import SECAnalysisTestCase


@dataclass
class ExecutionResult:
    """Result of code execution evaluation."""

    success: bool
    output: str = ""
    error: Optional[str] = None
    error_type: Optional[str] = None
    execution_time_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "error_type": self.error_type,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class PatternResult:
    """Result of pattern compliance evaluation."""

    compliant: bool
    expected_matches: List[Tuple[str, bool]]  # (pattern, found)
    forbidden_violations: List[Tuple[str, bool]]  # (pattern, found)
    score: float  # 0.0 to 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "compliant": self.compliant,
            "expected_matches": [
                {"pattern": p, "found": f} for p, f in self.expected_matches
            ],
            "forbidden_violations": [
                {"pattern": p, "found": f} for p, f in self.forbidden_violations
            ],
            "score": self.score,
        }


@dataclass
class TokenResult:
    """Result of token efficiency evaluation."""

    token_count: int
    within_budget: bool
    budget: int
    efficiency_score: float  # 0.0 to 1.0 (1.0 = very efficient)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "token_count": self.token_count,
            "within_budget": self.within_budget,
            "budget": self.budget,
            "efficiency_score": self.efficiency_score,
        }


# =============================================================================
# Token Counting
# =============================================================================


def count_tokens(text: str) -> int:
    """
    Estimate token count using simple character-based heuristic.

    Uses the approximation: ~4 characters per token.
    This avoids dependencies on tiktoken while providing reasonable estimates.

    Args:
        text: Text to count tokens for

    Returns:
        Estimated token count

    Example:
        >>> count_tokens("from edgar import Company")
        6
    """
    # Simple heuristic: ~4 chars per token on average
    return max(1, len(text) // 4)


# =============================================================================
# Code Execution Evaluator
# =============================================================================


def evaluate_code_execution(
    code: str,
    timeout_seconds: float = 30.0,
    capture_output: bool = True,
) -> ExecutionResult:
    """
    Execute code and check for errors.

    IMPORTANT: This executes arbitrary code. Only use with trusted inputs.

    Args:
        code: Python code to execute
        timeout_seconds: Maximum execution time (not enforced, for future use)
        capture_output: Whether to capture stdout/stderr

    Returns:
        ExecutionResult with success status and any output/errors

    Example:
        >>> result = evaluate_code_execution("print(1 + 1)")
        >>> print(result.success)
        True
        >>> print(result.output.strip())
        '2'
    """
    import time

    start_time = time.time()

    # Capture stdout/stderr
    old_stdout = sys.stdout
    old_stderr = sys.stderr

    if capture_output:
        sys.stdout = StringIO()
        sys.stderr = StringIO()

    try:
        # Create isolated namespace with common imports
        namespace: Dict[str, Any] = {}

        # Execute the code
        exec(code, namespace)

        # Capture output
        if capture_output:
            output = sys.stdout.getvalue()
            stderr = sys.stderr.getvalue()
            if stderr:
                output += f"\nSTDERR:\n{stderr}"
        else:
            output = ""

        elapsed_ms = (time.time() - start_time) * 1000

        return ExecutionResult(
            success=True,
            output=output,
            execution_time_ms=elapsed_ms,
        )

    except Exception as e:
        if capture_output:
            output = sys.stdout.getvalue()
        else:
            output = ""

        elapsed_ms = (time.time() - start_time) * 1000
        tb = traceback.format_exc()

        return ExecutionResult(
            success=False,
            output=output,
            error=str(e),
            error_type=type(e).__name__,
            execution_time_ms=elapsed_ms,
        )

    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


# =============================================================================
# Pattern Compliance Evaluator
# =============================================================================


def evaluate_pattern_compliance(
    code: str,
    test_case: SECAnalysisTestCase,
) -> PatternResult:
    """
    Check if code matches expected patterns and avoids forbidden patterns.

    Args:
        code: Generated code to evaluate
        test_case: Test case with expected/forbidden patterns

    Returns:
        PatternResult with compliance status and detailed matches

    Example:
        >>> from edgar.ai.evaluation.test_cases import get_test_by_id
        >>> test = get_test_by_id("TC001")
        >>> code = 'from edgar import Company; c = Company("AAPL"); print(c.cik)'
        >>> result = evaluate_pattern_compliance(code, test)
        >>> print(f"Compliant: {result.compliant}, Score: {result.score}")
    """
    expected_matches: List[Tuple[str, bool]] = []
    forbidden_violations: List[Tuple[str, bool]] = []

    # Check expected patterns (should be present)
    for pattern in test_case.expected_patterns:
        try:
            found = bool(re.search(pattern, code, re.IGNORECASE | re.MULTILINE))
        except re.error:
            # Invalid regex - treat as not found
            found = False
        expected_matches.append((pattern, found))

    # Check forbidden patterns (should NOT be present)
    for pattern in test_case.forbidden_patterns:
        try:
            found = bool(re.search(pattern, code, re.IGNORECASE | re.MULTILINE))
        except re.error:
            # Invalid regex - treat as not found (safe assumption)
            found = False
        forbidden_violations.append((pattern, found))

    # Calculate score
    # Expected: +1 for each match
    # Forbidden: -1 for each violation
    expected_score = sum(1 for _, found in expected_matches if found)
    expected_max = len(expected_matches) if expected_matches else 1

    forbidden_penalty = sum(1 for _, found in forbidden_violations if found)
    forbidden_max = len(forbidden_violations) if forbidden_violations else 0

    # Score: percentage of expected patterns found, minus penalty for violations
    if expected_max > 0:
        base_score = expected_score / expected_max
    else:
        base_score = 1.0

    if forbidden_max > 0 and forbidden_penalty > 0:
        penalty = forbidden_penalty / forbidden_max * 0.5  # Max 50% penalty
        score = max(0.0, base_score - penalty)
    else:
        score = base_score

    # Compliant if all expected found and no forbidden found
    all_expected_found = all(found for _, found in expected_matches)
    no_forbidden_found = all(not found for _, found in forbidden_violations)
    compliant = all_expected_found and no_forbidden_found

    return PatternResult(
        compliant=compliant,
        expected_matches=expected_matches,
        forbidden_violations=forbidden_violations,
        score=round(score, 3),
    )


# =============================================================================
# Token Efficiency Evaluator
# =============================================================================


def evaluate_token_efficiency(
    code: str,
    test_case: SECAnalysisTestCase,
) -> TokenResult:
    """
    Evaluate token efficiency of generated code against budget.

    Args:
        code: Generated code to evaluate
        test_case: Test case with max_tokens budget

    Returns:
        TokenResult with token count and efficiency score

    Example:
        >>> from edgar.ai.evaluation.test_cases import get_test_by_id
        >>> test = get_test_by_id("TC001")  # max_tokens=300
        >>> code = 'from edgar import Company\\nCompany("AAPL").cik'
        >>> result = evaluate_token_efficiency(code, test)
        >>> print(f"Tokens: {result.token_count}, Efficient: {result.within_budget}")
    """
    token_count = count_tokens(code)
    budget = test_case.max_tokens
    within_budget = token_count <= budget

    # Efficiency score: 1.0 if at 50% of budget, linearly decreasing
    # This rewards concise code while not penalizing slightly over budget
    if budget > 0:
        ratio = token_count / budget
        if ratio <= 0.5:
            efficiency_score = 1.0
        elif ratio <= 1.0:
            # Linear from 1.0 at 50% to 0.7 at 100%
            efficiency_score = 1.0 - (ratio - 0.5) * 0.6
        else:
            # Over budget: linear decrease from 0.7 to 0.0
            efficiency_score = max(0.0, 0.7 - (ratio - 1.0) * 0.35)
    else:
        efficiency_score = 1.0 if token_count == 0 else 0.0

    return TokenResult(
        token_count=token_count,
        within_budget=within_budget,
        budget=budget,
        efficiency_score=round(efficiency_score, 3),
    )


# =============================================================================
# Combined Evaluation
# =============================================================================


@dataclass
class CombinedEvaluation:
    """Combined results from all evaluators."""

    execution: ExecutionResult
    pattern: PatternResult
    efficiency: TokenResult
    overall_score: float  # Weighted combination

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "execution": self.execution.to_dict(),
            "pattern": self.pattern.to_dict(),
            "efficiency": self.efficiency.to_dict(),
            "overall_score": self.overall_score,
        }


def evaluate_code(
    code: str,
    test_case: SECAnalysisTestCase,
    execute: bool = False,
    weights: Optional[Dict[str, float]] = None,
) -> CombinedEvaluation:
    """
    Run all evaluations on generated code.

    Args:
        code: Generated code to evaluate
        test_case: Test case for evaluation criteria
        execute: Whether to actually execute the code (default: False for safety)
        weights: Custom weights for overall score calculation
            Default: {"execution": 0.4, "pattern": 0.4, "efficiency": 0.2}

    Returns:
        CombinedEvaluation with all results and overall score

    Example:
        >>> from edgar.ai.evaluation.test_cases import get_test_by_id
        >>> test = get_test_by_id("TC001")
        >>> code = '''
        ... from edgar import Company
        ... company = Company("AAPL")
        ... print(f"CIK: {company.cik}")
        ... '''
        >>> result = evaluate_code(code, test, execute=False)
        >>> print(f"Overall score: {result.overall_score}")
    """
    if weights is not None:
        effective_weights = weights
    elif execute:
        # When executing: execution matters
        effective_weights = {"execution": 0.4, "pattern": 0.4, "efficiency": 0.2}
    else:
        # When not executing: redistribute execution weight to pattern/efficiency
        effective_weights = {"execution": 0.0, "pattern": 0.7, "efficiency": 0.3}

    # Pattern evaluation (always run)
    pattern_result = evaluate_pattern_compliance(code, test_case)

    # Efficiency evaluation (always run)
    efficiency_result = evaluate_token_efficiency(code, test_case)

    # Execution evaluation (optional)
    if execute:
        execution_result = evaluate_code_execution(code)
    else:
        # Assume success if not executing
        execution_result = ExecutionResult(success=True, output="(not executed)")

    # Calculate overall score
    execution_score = 1.0 if execution_result.success else 0.0
    pattern_score = pattern_result.score
    efficiency_score = efficiency_result.efficiency_score

    overall = (
        effective_weights["execution"] * execution_score
        + effective_weights["pattern"] * pattern_score
        + effective_weights["efficiency"] * efficiency_score
    )

    return CombinedEvaluation(
        execution=execution_result,
        pattern=pattern_result,
        efficiency=efficiency_result,
        overall_score=round(overall, 3),
    )
