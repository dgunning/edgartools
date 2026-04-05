"""
LLM-as-Judge Evaluator for Skill A/B Testing.

Instead of regex-based pattern matching (which can't distinguish a clean
6-line get_financials() call from a 20-line manual XBRL approach), this
module uses an LLM judge to score generated code on quality dimensions:
correctness, API usage, conciseness, and efficiency.

Two-phase workflow (mirrors code generation):
    1. build_judge_prompt() creates prompts for judge subagents
    2. parse_judge_response() extracts JSON scores from responses
    3. build_judge_comparison() aggregates into an A/B comparison

Example:
    >>> from edgar.ai.evaluation.judge import (
    ...     build_judge_prompt, parse_judge_response, build_judge_comparison
    ... )
    >>> from edgar.ai.evaluation.test_cases import get_test_by_id
    >>>
    >>> test = get_test_by_id("TC001")
    >>> prompt = build_judge_prompt("TC001", "from edgar import Company\\nc = Company('AAPL')", test)
    >>> # ... send to LLM judge, get response ...
    >>> score = parse_judge_response(response_text, "TC001", "with_skills")
    >>> print(score.overall)
"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, Optional

from edgar.ai.evaluation.test_cases import SECAnalysisTestCase


@dataclass
class JudgeScore:
    """LLM judge scores for a single code sample."""

    test_id: str
    condition: str  # "with_skills" or "without_skills"
    correctness: int  # 1-5
    api_usage: int  # 1-5
    conciseness: int  # 1-5
    efficiency: int  # 1-5
    rationale: str = ""

    @property
    def overall(self) -> float:
        """Weighted overall score (0.0-1.0).

        api_usage weighted highest -- it's what skills should improve most.
        """
        raw = (
            self.correctness * 0.2
            + self.api_usage * 0.4
            + self.conciseness * 0.2
            + self.efficiency * 0.2
        )
        return round(raw / 5.0, 3)


@dataclass
class JudgeComparison:
    """A/B comparison from LLM judge scores."""

    with_skills: Dict[str, JudgeScore]  # test_id -> score
    without_skills: Dict[str, JudgeScore]  # test_id -> score
    per_test_deltas: Dict[str, Dict[str, float]] = field(default_factory=dict)
    mean_deltas: Dict[str, float] = field(default_factory=dict)
    winner: str = ""  # "with_skills" or "without_skills" or "tie"


# =============================================================================
# Prompt Building
# =============================================================================

_JUDGE_PROMPT_TEMPLATE = """\
You are an expert code reviewer evaluating Python code that uses the \
EdgarTools library for SEC filing analysis.

## Task
{task}

## Reference Code (ideal solution)
```python
{reference_code}
```

## Code to Evaluate
```python
{generated_code}
```

## Scoring Rubric
Score each dimension from 1 to 5:

**correctness** (1-5): Does the code correctly accomplish the task?
  5: Perfectly solves the task
  3: Mostly correct with minor issues
  1: Wrong approach or major errors

**api_usage** (1-5): Does it use the best EdgarTools APIs?
  5: Uses the ideal API methods (matches or improves on reference)
  3: Uses correct but suboptimal APIs
  1: Uses wrong APIs or reinvents existing functionality

**conciseness** (1-5): Is the code minimal and clean?
  5: Minimal code, no unnecessary lines
  3: Some unnecessary code
  1: Very verbose or cluttered

**efficiency** (1-5): Does it avoid wasteful patterns?
  5: No unnecessary loops, API calls, or memory usage
  3: Minor inefficiencies
  1: Unbounded iteration, repeated API calls, etc.

Respond with ONLY a JSON object, no other text:
{{"correctness": N, "api_usage": N, "conciseness": N, "efficiency": N, \
"rationale": "one sentence explanation"}}"""


def build_judge_prompt(
    test_id: str,
    generated_code: str,
    test_case: SECAnalysisTestCase,
) -> str:
    """Create a judge prompt for one code sample.

    Args:
        test_id: Test case ID (for traceability)
        generated_code: The code to evaluate
        test_case: Test case with task description and reference code

    Returns:
        Formatted prompt string for the judge LLM
    """
    reference = test_case.reference_code or "# No reference code provided"
    return _JUDGE_PROMPT_TEMPLATE.format(
        task=test_case.task,
        reference_code=reference.strip(),
        generated_code=generated_code.strip(),
    )


# =============================================================================
# Response Parsing
# =============================================================================

_DIMENSIONS = ("correctness", "api_usage", "conciseness", "efficiency")


def parse_judge_response(
    response_text: str,
    test_id: str,
    condition: str,
) -> JudgeScore:
    """Extract JSON scores from a judge LLM response.

    Handles raw JSON, markdown-wrapped JSON (```json ... ```), and
    falls back to default scores on parse failure.

    Args:
        response_text: Raw text from the judge LLM
        test_id: Test case ID
        condition: "with_skills" or "without_skills"

    Returns:
        JudgeScore with extracted or default scores
    """
    # Try to extract JSON from the response
    json_str = _extract_json(response_text)
    if json_str is None:
        return _default_score(test_id, condition, f"No JSON found in response: {response_text[:200]}")

    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return _default_score(test_id, condition, f"Invalid JSON: {json_str[:200]}")

    if not isinstance(data, dict):
        return _default_score(test_id, condition, f"Expected JSON object, got {type(data).__name__}")

    # Extract and validate scores
    scores = {}
    for dim in _DIMENSIONS:
        val = data.get(dim)
        if isinstance(val, (int, float)) and 1 <= val <= 5:
            scores[dim] = int(val)
        else:
            scores[dim] = 3  # default for missing/invalid dimension

    rationale = str(data.get("rationale", ""))

    return JudgeScore(
        test_id=test_id,
        condition=condition,
        correctness=scores["correctness"],
        api_usage=scores["api_usage"],
        conciseness=scores["conciseness"],
        efficiency=scores["efficiency"],
        rationale=rationale,
    )


def _extract_json(text: str) -> Optional[str]:
    """Extract JSON string from text, handling markdown code blocks."""
    text = text.strip()

    # Try markdown code block: ```json ... ``` or ``` ... ```
    md_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if md_match:
        return md_match.group(1).strip()

    # Try raw JSON object
    brace_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if brace_match:
        return brace_match.group(0)

    return None


def _default_score(test_id: str, condition: str, error_msg: str) -> JudgeScore:
    """Return a default score (all 3s) when parsing fails."""
    return JudgeScore(
        test_id=test_id,
        condition=condition,
        correctness=3,
        api_usage=3,
        conciseness=3,
        efficiency=3,
        rationale=f"[parse error] {error_msg}",
    )


# =============================================================================
# Comparison Building
# =============================================================================


def build_judge_comparison(
    with_scores: Dict[str, JudgeScore],
    without_scores: Dict[str, JudgeScore],
) -> JudgeComparison:
    """Build an A/B comparison from judge scores.

    Args:
        with_scores: test_id -> JudgeScore for with-skills condition
        without_scores: test_id -> JudgeScore for without-skills condition

    Returns:
        JudgeComparison with per-test deltas, mean deltas, and winner
    """
    common_ids = sorted(set(with_scores.keys()) & set(without_scores.keys()))

    per_test_deltas: Dict[str, Dict[str, float]] = {}
    dim_sums: Dict[str, float] = {dim: 0.0 for dim in _DIMENSIONS}
    overall_sum = 0.0

    for test_id in common_ids:
        ws = with_scores[test_id]
        wos = without_scores[test_id]
        deltas: Dict[str, float] = {}
        for dim in _DIMENSIONS:
            delta = getattr(ws, dim) - getattr(wos, dim)
            deltas[dim] = delta
            dim_sums[dim] += delta
        deltas["overall"] = ws.overall - wos.overall
        overall_sum += deltas["overall"]
        per_test_deltas[test_id] = deltas

    n = len(common_ids) if common_ids else 1
    mean_deltas = {dim: round(dim_sums[dim] / n, 3) for dim in _DIMENSIONS}
    mean_deltas["overall"] = round(overall_sum / n, 3)

    if mean_deltas["overall"] > 0:
        winner = "with_skills"
    elif mean_deltas["overall"] < 0:
        winner = "without_skills"
    else:
        winner = "tie"

    return JudgeComparison(
        with_skills=with_scores,
        without_skills=without_scores,
        per_test_deltas=per_test_deltas,
        mean_deltas=mean_deltas,
        winner=winner,
    )


# =============================================================================
# Report Formatting
# =============================================================================


def format_judge_report(comparison: JudgeComparison) -> str:
    """Pretty-print an A/B comparison from judge scores.

    Args:
        comparison: JudgeComparison to format

    Returns:
        Multi-line formatted report string
    """
    lines = [
        "",
        "LLM JUDGE A/B COMPARISON",
        "=" * 60,
    ]

    common_ids = sorted(set(comparison.with_skills.keys()) & set(comparison.without_skills.keys()))

    for test_id in common_ids:
        ws = comparison.with_skills[test_id]
        wos = comparison.without_skills[test_id]
        deltas = comparison.per_test_deltas.get(test_id, {})

        lines.append(f"\n{test_id}:")
        lines.append(f"  {'':20s} {'Without':>10s}  {'With':>10s}  {'Delta':>8s}")
        lines.append(f"  {'':20s} {'-------':>10s}  {'----':>10s}  {'-----':>8s}")

        for dim in _DIMENSIONS:
            wos_val = getattr(wos, dim)
            ws_val = getattr(ws, dim)
            delta = deltas.get(dim, 0)
            sign = "+" if delta > 0 else ""
            lines.append(f"  {dim:20s} {wos_val:>10d}  {ws_val:>10d}  {sign}{delta:>7.0f}")

        # Overall
        delta_overall = deltas.get("overall", 0)
        sign = "+" if delta_overall > 0 else ""
        lines.append(f"  {'overall':20s} {wos.overall:>10.3f}  {ws.overall:>10.3f}  {sign}{delta_overall:>7.3f}")

    # Mean deltas
    lines.append(f"\n{'Mean Deltas':}")
    lines.append("-" * 40)
    for dim in _DIMENSIONS:
        val = comparison.mean_deltas.get(dim, 0)
        sign = "+" if val > 0 else ""
        lines.append(f"  {dim:20s}  {sign}{val:.3f}")
    overall_mean = comparison.mean_deltas.get("overall", 0)
    sign = "+" if overall_mean > 0 else ""
    lines.append(f"  {'overall':20s}  {sign}{overall_mean:.3f}")

    # Winner
    lines.append("")
    if comparison.winner == "with_skills":
        lines.append(f"Winner: WITH SKILLS ({sign}{overall_mean:.3f} mean delta)")
    elif comparison.winner == "without_skills":
        lines.append(f"Winner: WITHOUT SKILLS ({sign}{overall_mean:.3f} mean delta)")
    else:
        lines.append("Winner: TIE (0.000 mean delta)")
    lines.append("=" * 60)

    return "\n".join(lines)
