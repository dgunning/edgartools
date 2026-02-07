"""
Agent-Based Evaluation Framework for EdgarTools MCP Tools.

This module provides a real agent-based evaluation where Claude has the 5 MCP tools
available, executes real tool calls against SEC EDGAR, and produces natural-language
answers evaluated for tool selection, answer quality, and efficiency.

Architecture:
    Test Case -> Claude Code SDK -> Tool Calls -> MCP Handlers -> SEC Data -> Answer -> Scoring

Uses the Claude Code Agent SDK (claude-code-sdk) so it works with your existing
Claude Code subscription — no separate API key needed.

Requirements:
    pip install claude-code-sdk

Example:
    >>> from edgar.ai.evaluation.agent import AgentTestRunner
    >>>
    >>> runner = AgentTestRunner()
    >>> result = await runner.run_single("TC001", with_skills=True)
    >>> print(f"Score: {result.score.overall}")
    >>>
    >>> # Full A/B comparison
    >>> comparison = await runner.run_ab_comparison(["TC001", "TC002"])
    >>> print(comparison.summary())
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from edgar.ai.evaluation.harness import (
    ABComparison,
    EvaluationReport,
    TestResult,
)
from edgar.ai.evaluation.evaluators import (
    CombinedEvaluation,
    ExecutionResult,
    PatternResult,
    TokenResult,
)
from edgar.ai.evaluation.test_cases import (
    SEC_TEST_SUITE,
    SECAnalysisTestCase,
    get_test_by_id,
)

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class ToolCall:
    """Record of a single tool call made by the agent."""
    name: str
    arguments: dict
    result: str
    success: bool


@dataclass
class AgentTrace:
    """Full trace of an agent's execution on a task."""
    tool_calls: List[ToolCall]
    final_answer: str
    total_turns: int
    model: str


@dataclass
class AgentScore:
    """Scoring breakdown for an agent evaluation."""
    tool_selection: float   # 0-1: did it pick the right tools?
    answer_quality: float   # 0-1: does the answer contain expected info?
    efficiency: float       # 0-1: how many tool calls vs budget?
    overall: float          # weighted combination

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_selection": round(self.tool_selection, 3),
            "answer_quality": round(self.answer_quality, 3),
            "efficiency": round(self.efficiency, 3),
            "overall": round(self.overall, 3),
        }


@dataclass
class AgentTestResult:
    """Result of running one test case through the agent."""
    test_id: str
    condition: str          # "with_skills" or "without_skills"
    trace: AgentTrace
    score: AgentScore
    timestamp: str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "condition": self.condition,
            "trace": {
                "tool_calls": [
                    {"name": tc.name, "arguments": tc.arguments,
                     "result": tc.result[:500], "success": tc.success}
                    for tc in self.trace.tool_calls
                ],
                "final_answer": self.trace.final_answer[:2000],
                "total_turns": self.trace.total_turns,
                "model": self.trace.model,
            },
            "score": self.score.to_dict(),
            "timestamp": self.timestamp,
        }


# =============================================================================
# TOOL → SKILL MAPPING
# =============================================================================

TOOL_SKILL_MAP: Dict[str, List[str]] = {
    "edgar_company": ["core/skill.yaml", "financials/skill.yaml"],
    "edgar_search": ["core/skill.yaml"],
    "edgar_filing": ["reports/skill.yaml"],
    "edgar_compare": ["financials/skill.yaml"],
    "edgar_ownership": ["ownership/skill.yaml", "holdings/skill.yaml"],
}

CATEGORY_SKILL_MAP: Dict[str, List[str]] = {
    "lookup": ["core/skill.yaml"],
    "filing": ["core/skill.yaml", "reports/skill.yaml"],
    "counting": ["core/skill.yaml"],
    "financial": ["financials/skill.yaml"],
    "ownership": ["ownership/skill.yaml"],
    "holdings": ["holdings/skill.yaml"],
    "reports": ["reports/skill.yaml"],
    "comparison": ["financials/skill.yaml"],
    "multi-step": ["core/skill.yaml"],
    "general": ["core/skill.yaml"],
}


# =============================================================================
# SKILL GAP DIAGNOSTICS
# =============================================================================


@dataclass
class SkillDiagnostic:
    """Diagnostic for a single test's skill gap analysis."""
    test_id: str
    failure_mode: str       # correct | wrong_tool | missing_tool | incomplete_answer | excessive_calls | tool_error
    skill_files: List[str]
    detail: str
    recommendation: str
    severity: str           # high | medium | low
    with_score: float
    without_score: float
    delta: float            # with - without (negative = skills hurting)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "failure_mode": self.failure_mode,
            "skill_files": self.skill_files,
            "detail": self.detail,
            "recommendation": self.recommendation,
            "severity": self.severity,
            "with_score": round(self.with_score, 3),
            "without_score": round(self.without_score, 3),
            "delta": round(self.delta, 3),
        }


@dataclass
class SkillGapReport:
    """Aggregated skill gap analysis across all tests."""
    diagnostics: List[SkillDiagnostic]
    by_skill_file: Dict[str, List[SkillDiagnostic]] = field(default_factory=dict)
    by_failure_mode: Dict[str, List[SkillDiagnostic]] = field(default_factory=dict)
    priority_fixes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "by_skill_file": {
                k: [d.to_dict() for d in v]
                for k, v in self.by_skill_file.items()
            },
            "by_failure_mode": {
                k: [d.to_dict() for d in v]
                for k, v in self.by_failure_mode.items()
            },
            "priority_fixes": self.priority_fixes,
        }

    def print_report(self):
        """Print human-readable skill gap report."""
        skill_file_count = len(self.by_skill_file)
        print()
        print("=" * 60)
        print("SKILL GAP ANALYSIS")
        print("=" * 60)
        print(f"{len(self.diagnostics)} diagnostics across "
              f"{skill_file_count} skill file(s)")

        # By Skill File
        print("\nBy Skill File:")
        for skill_file, diags in sorted(self.by_skill_file.items()):
            print(f"  {skill_file} ({len(diags)} issue(s)):")
            for d in diags:
                sev = d.severity.upper()
                if d.failure_mode == "correct":
                    extra = f"skills neutral, delta={d.delta:+.3f}" if d.delta == 0 else f"skills helping, delta={d.delta:+.3f}"
                    print(f"    [{sev:>4}] {d.test_id}: {d.failure_mode} ({extra})")
                else:
                    print(f"    [{sev:>4}] {d.test_id}: {d.failure_mode} — {d.detail}")

        # Priority Fixes
        if self.priority_fixes:
            print("\nPriority Fixes:")
            for i, fix in enumerate(self.priority_fixes, 1):
                print(f"  {i}. {fix}")

        print("=" * 60)


def _resolve_skill_files(
    test_case: SECAnalysisTestCase,
    trace_tools: List[str],
) -> List[str]:
    """Resolve which skill YAML files are relevant for a test."""
    skill_files: set = set()

    # Primary: map expected tools to skill files
    for tool in test_case.expected_tools:
        if tool in TOOL_SKILL_MAP:
            skill_files.update(TOOL_SKILL_MAP[tool])

    # Fallback: map category to skill files
    if not skill_files:
        cat = test_case.category
        if cat in CATEGORY_SKILL_MAP:
            skill_files.update(CATEGORY_SKILL_MAP[cat])

    # Final fallback
    if not skill_files:
        skill_files.add("core/skill.yaml")

    return sorted(skill_files)


def diagnose_trace(
    with_result: AgentTestResult,
    without_result: AgentTestResult,
    test_case: SECAnalysisTestCase,
) -> SkillDiagnostic:
    """
    Diagnose failure mode for a single test pair (with/without skills).

    Classifies the failure and generates an actionable recommendation.
    """
    w_score = with_result.score
    wo_score = without_result.score
    delta = w_score.overall - wo_score.overall

    called_tools = [tc.name for tc in with_result.trace.tool_calls]
    expected_tools = test_case.expected_tools
    skill_files = _resolve_skill_files(test_case, called_tools)
    category = test_case.category

    # Classify failure mode
    num_calls = len(with_result.trace.tool_calls)

    if num_calls == 0 and expected_tools:
        failure_mode = "tool_error"
        severity = "high"
        detail = "No tool calls made when tools were expected"
        recommendation = (
            f"In {skill_files[0]}, add clear example showing "
            f"{expected_tools[0]} for {category} tasks"
        )
    elif w_score.tool_selection < 1.0 and expected_tools:
        called_set = set(called_tools)
        expected_set = set(expected_tools)
        missing = expected_set - called_set
        extra = called_set - expected_set

        if missing:
            failure_mode = "missing_tool"
            severity = "high"
            missing_str = ", ".join(sorted(missing))
            detail = f"Missing tool(s): {missing_str}"
            recommendation = (
                f"In {skill_files[0]}, add example showing "
                f"{missing_str} for {category} tasks"
            )
        else:
            failure_mode = "wrong_tool"
            severity = "high"
            extra_str = ", ".join(sorted(extra))
            expected_str = ", ".join(sorted(expected_set))
            detail = f"Used {extra_str} instead of/in addition to {expected_str}"
            recommendation = (
                f"In {skill_files[0]}, add routing: use {expected_str} "
                f"(not {extra_str}) for {category} tasks"
            )
    elif w_score.answer_quality < 1.0:
        failure_mode = "incomplete_answer"
        severity = "medium"
        # Figure out which expected strings were missing
        answer_lower = with_result.trace.final_answer.lower()
        missing_answers = [
            s for s in test_case.expected_in_answer
            if s.lower() not in answer_lower
        ]
        missing_str = ", ".join(missing_answers[:3])
        detail = f"Missing in answer: {missing_str}" if missing_answers else "Answer quality below threshold"
        recommendation = (
            f"In {skill_files[0]}, add parameter guidance for "
            f"{category} queries to ensure complete responses"
        )
    elif w_score.efficiency < 1.0:
        failure_mode = "excessive_calls"
        severity = "low"
        detail = (
            f"{num_calls} tool calls vs budget of "
            f"{test_case.max_tool_calls}"
        )
        expected_str = ", ".join(expected_tools) if expected_tools else "relevant tool"
        recommendation = (
            f"In {skill_files[0]}, add 'avoid' pattern: single "
            f"{expected_str} call suffices for {category} tasks"
        )
    else:
        # All scores are 1.0
        failure_mode = "correct"
        severity = "low"
        if delta == 0:
            detail = "Skills neutral — same score with and without"
            recommendation = (
                f"Skills neutral for {category} — "
                f"tool descriptions alone suffice"
            )
        elif delta > 0:
            detail = f"Skills helping (delta={delta:+.3f})"
            recommendation = f"Skills helping for {category}"
        else:
            detail = f"Skills hurting (delta={delta:+.3f})"
            recommendation = (
                f"In {skill_files[0]}, review {category} guidance — "
                f"skills may be adding confusion"
            )

    # Bump severity if skills are hurting
    if delta < 0 and failure_mode != "correct":
        severity = "high"

    return SkillDiagnostic(
        test_id=with_result.test_id,
        failure_mode=failure_mode,
        skill_files=skill_files,
        detail=detail,
        recommendation=recommendation,
        severity=severity,
        with_score=w_score.overall,
        without_score=wo_score.overall,
        delta=delta,
    )


def analyze_skill_gaps(
    with_results: List[AgentTestResult],
    without_results: List[AgentTestResult],
) -> SkillGapReport:
    """
    Analyze skill gaps across paired with/without results.

    Pairs results by test_id, diagnoses each pair, and aggregates
    into a SkillGapReport with priority fixes.
    """
    # Pair results by test_id
    without_by_id = {r.test_id: r for r in without_results}

    diagnostics: List[SkillDiagnostic] = []
    for w_result in with_results:
        wo_result = without_by_id.get(w_result.test_id)
        if wo_result is None:
            continue
        test_case = get_test_by_id(w_result.test_id)
        if test_case is None:
            continue
        diag = diagnose_trace(w_result, wo_result, test_case)
        diagnostics.append(diag)

    # Group by skill file
    by_skill_file: Dict[str, List[SkillDiagnostic]] = {}
    for d in diagnostics:
        for sf in d.skill_files:
            by_skill_file.setdefault(sf, []).append(d)

    # Group by failure mode
    by_failure_mode: Dict[str, List[SkillDiagnostic]] = {}
    for d in diagnostics:
        by_failure_mode.setdefault(d.failure_mode, []).append(d)

    # Generate priority fixes sorted by severity then frequency
    severity_order = {"high": 0, "medium": 1, "low": 2}
    # Aggregate by (skill_file, failure_mode) for actionable summaries
    fix_entries: List[tuple] = []  # (severity_rank, count, fix_string)
    seen_fixes: set = set()

    for d in sorted(diagnostics, key=lambda x: severity_order.get(x.severity, 3)):
        if d.failure_mode == "correct" and d.delta >= 0:
            # No fix needed for correct/helping tests
            fix_key = (d.skill_files[0], "neutral")
            if fix_key not in seen_fixes:
                seen_fixes.add(fix_key)
                neutral_count = sum(
                    1 for dd in diagnostics
                    if dd.failure_mode == "correct" and dd.delta >= 0
                    and dd.skill_files[0] == d.skill_files[0]
                )
                fix_entries.append((
                    severity_order["low"],
                    neutral_count,
                    f"[LOW] {d.skill_files[0]}: Skills neutral for "
                    f"{neutral_count} test(s) — simplify or remove"
                ))
        else:
            fix_key = (d.skill_files[0], d.failure_mode)
            if fix_key not in seen_fixes:
                seen_fixes.add(fix_key)
                sev = d.severity.upper()
                mode_count = sum(
                    1 for dd in diagnostics
                    if dd.failure_mode == d.failure_mode
                    and dd.skill_files[0] == d.skill_files[0]
                )
                fix_entries.append((
                    severity_order.get(d.severity, 3),
                    mode_count,
                    f"[{sev}] {d.skill_files[0]}: {d.recommendation}"
                ))

    # Sort: severity asc (high first), then count desc
    fix_entries.sort(key=lambda x: (x[0], -x[1]))
    priority_fixes = [entry[2] for entry in fix_entries]

    return SkillGapReport(
        diagnostics=diagnostics,
        by_skill_file=by_skill_file,
        by_failure_mode=by_failure_mode,
        priority_fixes=priority_fixes,
    )


# =============================================================================
# MCP SERVER CONFIG
# =============================================================================


def _get_mcp_server_config() -> dict:
    """
    Get external MCP server config that runs our tools as a subprocess.

    Returns:
        Dict with MCP server name -> stdio config for Claude Code SDK.
    """
    import sys
    return {
        "edgar": {
            "type": "stdio",
            "command": sys.executable,
            "args": ["-m", "edgar.ai.evaluation.mcp_server"],
        }
    }


def _get_tool_names() -> list[str]:
    """Get the allowed tool names for the MCP server."""
    from edgar.ai.mcp.tools import company, search, filing, compare, ownership  # noqa: F401
    from edgar.ai.mcp.tools.base import TOOLS
    return [f"mcp__edgar__{name}" for name in TOOLS.keys()]


def mcp_to_anthropic_tools() -> list[dict]:
    """
    Get MCP tool definitions in a display-friendly format (for dry-run).

    Returns:
        List of tool definition dicts with name, description, input_schema.
    """
    from edgar.ai.mcp.tools import company, search, filing, compare, ownership  # noqa: F401
    from edgar.ai.mcp.tools.base import get_tool_definitions

    definitions = get_tool_definitions()
    return [
        {
            "name": d["name"],
            "description": d["description"],
            "input_schema": d["inputSchema"],
        }
        for d in definitions
    ]


# =============================================================================
# AGENT LOOP — Claude Code SDK
# =============================================================================


async def run_agent(
    task: str,
    system_prompt: str,
    model: str = "claude-haiku-4-5-20251001",
    max_turns: int = 10,
) -> AgentTrace:
    """
    Run the agent loop using Claude Code SDK.

    The SDK handles the tool execution loop internally — we provide our
    MCP tools as an SDK MCP server, and the SDK manages the conversation,
    tool calls, and final answer.

    Args:
        task: Natural language task for the agent
        system_prompt: System prompt with or without skill context
        model: Model to use
        max_turns: Maximum agent loop iterations

    Returns:
        AgentTrace with all tool calls and final answer
    """
    from claude_code_sdk import (
        query,
        ClaudeCodeOptions,
        AssistantMessage,
        UserMessage,
        ResultMessage,
        TextBlock,
        ToolUseBlock,
        ToolResultBlock,
    )

    mcp_servers = _get_mcp_server_config()
    tool_names = _get_tool_names()

    options = ClaudeCodeOptions(
        system_prompt=system_prompt,
        model=model,
        max_turns=max_turns,
        mcp_servers=mcp_servers,
        allowed_tools=tool_names,
        permission_mode="bypassPermissions",
    )

    tool_calls_made: List[ToolCall] = []
    text_parts: List[str] = []
    turns = 0

    async for message in query(prompt=task, options=options):
        if isinstance(message, AssistantMessage):
            turns += 1
            for block in message.content:
                if isinstance(block, TextBlock):
                    text_parts.append(block.text)
                elif isinstance(block, ToolUseBlock):
                    tool_calls_made.append(ToolCall(
                        name=block.name.replace("mcp__edgar__", ""),
                        arguments=block.input if isinstance(block.input, dict) else {},
                        result="(pending)",
                        success=False,
                    ))

        elif isinstance(message, UserMessage):
            # Tool results come back as UserMessage
            # Mark any pending tool calls as successful
            # (if the agent continued, the tool didn't error fatally)
            for tc in tool_calls_made:
                if tc.result == "(pending)":
                    tc.result = "(completed)"
                    tc.success = True

        elif isinstance(message, ResultMessage):
            pass

    # If agent produced a text response after tool calls, tools succeeded
    if text_parts:
        for tc in tool_calls_made:
            if tc.result == "(pending)":
                tc.success = True
                tc.result = "(completed)"

    final_answer = "\n".join(text_parts) if text_parts else "(no answer)"

    return AgentTrace(
        tool_calls=tool_calls_made,
        final_answer=final_answer,
        total_turns=turns,
        model=model,
    )


# =============================================================================
# EVALUATOR
# =============================================================================


def evaluate_agent(trace: AgentTrace, test_case: SECAnalysisTestCase) -> AgentScore:
    """
    Evaluate an agent trace against a test case.

    Scoring dimensions:
        - Tool Selection (35%): Did the agent use the right tools?
        - Answer Quality (45%): Does the answer contain expected info?
        - Efficiency (20%): How many tool calls vs budget?

    Args:
        trace: Agent execution trace
        test_case: Test case with expected_tools, expected_in_answer, max_tool_calls

    Returns:
        AgentScore with breakdown and overall score
    """
    # --- Tool Selection (35%) ---
    called_tools = set(tc.name for tc in trace.tool_calls)
    expected_tools = set(test_case.expected_tools)

    if expected_tools:
        # What fraction of expected tools were used?
        hits = len(expected_tools & called_tools)
        tool_recall = hits / len(expected_tools)

        # Penalty for extra tools (mild — 0.1 per extra tool, max 0.3)
        extra_tools = called_tools - expected_tools
        extra_penalty = min(0.3, len(extra_tools) * 0.1)

        tool_selection = max(0.0, tool_recall - extra_penalty)
    else:
        # No expected tools specified — score 1.0 if any tool was called
        tool_selection = 1.0 if called_tools else 0.5

    # --- Answer Quality (45%) ---
    expected_in_answer = test_case.expected_in_answer
    if expected_in_answer:
        answer_lower = trace.final_answer.lower()
        matches = sum(
            1 for s in expected_in_answer
            if s.lower() in answer_lower
        )
        answer_quality = matches / len(expected_in_answer)
    else:
        # No expected strings — score 1.0 if any tool succeeded
        any_success = any(tc.success for tc in trace.tool_calls)
        answer_quality = 1.0 if any_success else 0.0

    # --- Efficiency (20%) ---
    num_calls = len(trace.tool_calls)
    max_calls = test_case.max_tool_calls

    if num_calls == 0 and expected_tools:
        # Agent never used tools when it should have
        efficiency = 0.0
    elif num_calls <= max_calls:
        efficiency = 1.0
    else:
        # Linear decrease from 1.0 at budget to 0.0 at 2x budget
        overshoot = (num_calls - max_calls) / max_calls
        efficiency = max(0.0, 1.0 - overshoot)

    # --- Overall ---
    overall = 0.35 * tool_selection + 0.45 * answer_quality + 0.20 * efficiency

    return AgentScore(
        tool_selection=round(tool_selection, 3),
        answer_quality=round(answer_quality, 3),
        efficiency=round(efficiency, 3),
        overall=round(overall, 3),
    )


# =============================================================================
# AGENT TEST RUNNER
# =============================================================================


class AgentTestRunner:
    """
    Runs test cases through the agent loop with/without skill context.

    Uses the Claude Code Agent SDK — works with your existing Claude Code
    subscription, no separate API key needed.

    Example:
        >>> runner = AgentTestRunner()
        >>> result = await runner.run_single("TC001", with_skills=True)
        >>> print(result.score.overall)
    """

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        skill_context: Optional[str] = None,
    ):
        self.model = model
        self.skill_context = skill_context
        self._last_with_results: List[AgentTestResult] = []
        self._last_without_results: List[AgentTestResult] = []

    def _build_system_prompt(self, with_skills: bool) -> str:
        """Build system prompt for with/without skills condition."""
        if with_skills:
            from edgar.ai.evaluation.runner import load_skill_context
            context = self.skill_context or load_skill_context()
            return (
                "You are an expert SEC filing analyst using EdgarTools.\n\n"
                "You have access to tools for querying SEC EDGAR data. "
                "Use the provided tools to answer the user's question. "
                "Return a clear, complete answer.\n\n"
                f"Skill documentation:\n\n{context}"
            )
        else:
            from edgar.ai.evaluation.runner import get_minimal_context
            minimal = get_minimal_context()
            return (
                "You are an SEC filing analyst.\n\n"
                "You have access to tools for querying SEC EDGAR data. "
                "Use the provided tools to answer the user's question. "
                "Return a clear, complete answer.\n\n"
                f"Context:\n{minimal}"
            )

    async def run_single(
        self,
        test_id: str,
        with_skills: bool = True,
    ) -> AgentTestResult:
        """
        Run one test case through the agent loop.

        Args:
            test_id: Test case ID (e.g., "TC001")
            with_skills: Whether to include skill context

        Returns:
            AgentTestResult with trace and score
        """
        test_case = get_test_by_id(test_id)
        if not test_case:
            raise ValueError(f"Test case '{test_id}' not found")

        condition = "with_skills" if with_skills else "without_skills"
        system_prompt = self._build_system_prompt(with_skills)

        trace = await run_agent(
            task=test_case.task,
            system_prompt=system_prompt,
            model=self.model,
            max_turns=test_case.max_tool_calls + 3,  # some headroom
        )

        score = evaluate_agent(trace, test_case)

        return AgentTestResult(
            test_id=test_id,
            condition=condition,
            trace=trace,
            score=score,
        )

    def _build_report(
        self,
        results: List[AgentTestResult],
        condition: str,
    ) -> EvaluationReport:
        """
        Adapt AgentTestResults into an EvaluationReport for ABComparison.

        Maps AgentScore dimensions into the CombinedEvaluation structure
        so existing summary/comparison logic works.
        """
        test_results = []
        for r in results:
            evaluation = CombinedEvaluation(
                execution=ExecutionResult(
                    success=any(tc.success for tc in r.trace.tool_calls),
                    output=r.trace.final_answer[:500],
                ),
                pattern=PatternResult(
                    compliant=r.score.tool_selection >= 0.5,
                    expected_matches=[],
                    forbidden_violations=[],
                    score=r.score.tool_selection,
                ),
                efficiency=TokenResult(
                    token_count=len(r.trace.tool_calls),
                    within_budget=r.score.efficiency >= 0.5,
                    budget=get_test_by_id(r.test_id).max_tool_calls if get_test_by_id(r.test_id) else 10,
                    efficiency_score=r.score.efficiency,
                ),
                overall_score=r.score.overall,
            )

            test_results.append(TestResult(
                test_id=r.test_id,
                condition=condition,
                code=f"[agent trace: {len(r.trace.tool_calls)} tool calls]",
                evaluation=evaluation,
            ))

        return EvaluationReport(
            results=test_results,
            condition=condition,
        )

    async def run_ab_comparison(
        self,
        test_ids: Optional[List[str]] = None,
        delay_between_tests: float = 1.0,
    ) -> ABComparison:
        """
        Run all tests with/without skills, return ABComparison.

        Args:
            test_ids: Test IDs to run (defaults to all)
            delay_between_tests: Seconds to wait between tests (SEC rate limits)

        Returns:
            ABComparison with detailed results
        """
        if test_ids is None:
            test_ids = [t.id for t in SEC_TEST_SUITE]

        print("=" * 60)
        print("AGENT-BASED A/B SKILL COMPARISON")
        print(f"Model: {self.model}")
        print(f"Tests: {len(test_ids)}")
        print("=" * 60)

        # Run with skills
        print("\n[1/2] Running WITH skills...")
        with_results = []
        for tid in test_ids:
            print(f"  {tid}...", end=" ", flush=True)
            try:
                result = await self.run_single(tid, with_skills=True)
                with_results.append(result)
                tools_used = [tc.name for tc in result.trace.tool_calls]
                print(f"score={result.score.overall:.2f} tools={tools_used}")
            except Exception as e:
                print(f"ERROR: {e}")
            await asyncio.sleep(delay_between_tests)

        # Run without skills
        print("\n[2/2] Running WITHOUT skills...")
        without_results = []
        for tid in test_ids:
            print(f"  {tid}...", end=" ", flush=True)
            try:
                result = await self.run_single(tid, with_skills=False)
                without_results.append(result)
                tools_used = [tc.name for tc in result.trace.tool_calls]
                print(f"score={result.score.overall:.2f} tools={tools_used}")
            except Exception as e:
                print(f"ERROR: {e}")
            await asyncio.sleep(delay_between_tests)

        # Store raw results for diagnostics
        self._last_with_results = with_results
        self._last_without_results = without_results

        # Build reports and comparison
        with_report = self._build_report(with_results, "with_skills")
        without_report = self._build_report(without_results, "without_skills")

        comparison = ABComparison(
            with_skills=with_report,
            without_skills=without_report,
        )

        print("\n" + comparison.summary())

        # Also print agent-specific detail
        print("\nAgent-Specific Results:")
        print("-" * 60)
        print(f"{'Test':>6}  {'Condition':<15}  {'Tool':>5}  {'Answer':>6}  "
              f"{'Effic':>5}  {'Overall':>7}")
        print("-" * 60)
        for r in with_results:
            print(f"{r.test_id:>6}  {'with_skills':<15}  "
                  f"{r.score.tool_selection:>5.2f}  {r.score.answer_quality:>6.2f}  "
                  f"{r.score.efficiency:>5.2f}  {r.score.overall:>7.3f}")
        for r in without_results:
            print(f"{r.test_id:>6}  {'without_skills':<15}  "
                  f"{r.score.tool_selection:>5.2f}  {r.score.answer_quality:>6.2f}  "
                  f"{r.score.efficiency:>5.2f}  {r.score.overall:>7.3f}")

        return comparison

    async def run_and_save(
        self,
        test_ids: Optional[List[str]] = None,
        output_dir: str = "./agent_eval_results",
        diagnose: bool = False,
    ) -> Path:
        """Run A/B comparison and save results to JSON.

        Args:
            test_ids: Test IDs to run (defaults to all)
            output_dir: Directory to save results
            diagnose: If True, run skill gap analysis and include in output
        """
        comparison = await self.run_ab_comparison(test_ids)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filepath = output_path / f"agent_evaluation_{timestamp}.json"

        data: Dict[str, Any] = {
            "timestamp": timestamp,
            "model": self.model,
            "comparison": comparison.to_dict(),
        }

        # Run skill gap diagnostics if requested
        if diagnose and self._last_with_results and self._last_without_results:
            gap_report = analyze_skill_gaps(
                self._last_with_results,
                self._last_without_results,
            )
            gap_report.print_report()
            data["diagnostics"] = gap_report.to_dict()

        filepath.write_text(json.dumps(data, indent=2, default=str))
        print(f"\nResults saved to: {filepath}")

        return filepath


# =============================================================================
# CLI INTERFACE
# =============================================================================


def main():
    """CLI: python -m edgar.ai.evaluation.agent [options]"""
    import argparse

    parser = argparse.ArgumentParser(
        description="EdgarTools Agent-Based Evaluation Runner"
    )
    parser.add_argument(
        "--test-ids",
        nargs="+",
        help="Specific test IDs to run (default: all)",
    )
    parser.add_argument(
        "--model",
        default="claude-haiku-4-5-20251001",
        help="Model to use (default: claude-haiku-4-5-20251001)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show test plan without calling API",
    )
    parser.add_argument(
        "--output-dir",
        default="./agent_eval_results",
        help="Directory to save results",
    )
    parser.add_argument(
        "--single",
        type=str,
        help="Run a single test (e.g., --single TC001)",
    )
    parser.add_argument(
        "--with-skills",
        action="store_true",
        default=True,
        help="Include skill context (default: True)",
    )
    parser.add_argument(
        "--without-skills",
        action="store_true",
        help="Run without skill context",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Run skill gap analysis after A/B comparison",
    )
    args = parser.parse_args()

    if args.dry_run:
        test_ids = args.test_ids or [t.id for t in SEC_TEST_SUITE]
        tools = mcp_to_anthropic_tools()
        print("Agent Evaluation - Dry Run")
        print("=" * 60)
        print(f"Model: {args.model}")
        print(f"Available tools ({len(tools)}):")
        for t in tools:
            print(f"  - {t['name']}: {t['description'][:60]}...")
        print(f"\nTest cases ({len(test_ids)}):")
        for tid in test_ids:
            test = get_test_by_id(tid)
            if test:
                print(f"  {tid} [{test.difficulty}] [{test.category}]")
                print(f"    Task: {test.task[:60]}...")
                print(f"    Expected tools: {test.expected_tools}")
                print(f"    Expected in answer: {test.expected_in_answer}")
                print(f"    Max tool calls: {test.max_tool_calls}")
        print(f"\nOutput: {args.output_dir}")
        return

    if args.single:
        # Quick single-test mode
        with_skills = not args.without_skills

        async def _run_single():
            runner = AgentTestRunner(model=args.model)
            result = await runner.run_single(args.single, with_skills=with_skills)
            condition = "with_skills" if with_skills else "without_skills"
            print(f"\n{'=' * 60}")
            print(f"Test: {result.test_id} ({condition})")
            print(f"{'=' * 60}")
            print(f"Tool calls: {len(result.trace.tool_calls)}")
            for tc in result.trace.tool_calls:
                status = "OK" if tc.success else "FAIL"
                print(f"  [{status}] {tc.name}({json.dumps(tc.arguments)[:80]})")
            print(f"\nFinal answer ({len(result.trace.final_answer)} chars):")
            print(result.trace.final_answer[:1000])
            print(f"\nScores:")
            print(f"  Tool Selection: {result.score.tool_selection:.3f}")
            print(f"  Answer Quality: {result.score.answer_quality:.3f}")
            print(f"  Efficiency:     {result.score.efficiency:.3f}")
            print(f"  Overall:        {result.score.overall:.3f}")

        asyncio.run(_run_single())
        return

    # Full A/B comparison
    async def _run_ab():
        runner = AgentTestRunner(model=args.model)
        await runner.run_and_save(
            test_ids=args.test_ids,
            output_dir=args.output_dir,
            diagnose=args.diagnose,
        )

    asyncio.run(_run_ab())


if __name__ == "__main__":
    main()
