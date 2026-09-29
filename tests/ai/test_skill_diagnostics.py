"""Tests for the skill gap diagnostics in agent.py."""
import json
import pytest

from edgar.ai.evaluation.agent import (
    AgentScore,
    AgentTestResult,
    AgentTrace,
    CATEGORY_SKILL_MAP,
    SkillDiagnostic,
    SkillGapReport,
    TOOL_SKILL_MAP,
    ToolCall,
    _resolve_skill_files,
    analyze_skill_gaps,
    diagnose_trace,
)
from edgar.ai.evaluation.test_cases import get_test_by_id, SEC_TEST_SUITE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_trace(tool_calls=None, answer="test answer", turns=1):
    """Build an AgentTrace with sensible defaults."""
    return AgentTrace(
        tool_calls=tool_calls or [],
        final_answer=answer,
        total_turns=turns,
        model="test",
    )


def _make_result(test_id, condition, trace, score):
    """Build an AgentTestResult."""
    return AgentTestResult(
        test_id=test_id,
        condition=condition,
        trace=trace,
        score=score,
    )


def _perfect_score():
    return AgentScore(
        tool_selection=1.0, answer_quality=1.0,
        efficiency=1.0, overall=1.0,
    )


def _zero_score():
    return AgentScore(
        tool_selection=0.0, answer_quality=0.0,
        efficiency=0.0, overall=0.0,
    )


# ---------------------------------------------------------------------------
# Mapping constants
# ---------------------------------------------------------------------------

class TestToolSkillMap:
    """Verify the lookup tables are well-formed."""

    def test_tool_skill_map_keys_are_known_tools(self):
        expected_tools = {
            "edgar_company", "edgar_search", "edgar_filing",
            "edgar_compare", "edgar_ownership",
        }
        assert set(TOOL_SKILL_MAP.keys()) == expected_tools

    def test_tool_skill_map_values_are_nonempty(self):
        for tool, files in TOOL_SKILL_MAP.items():
            assert len(files) > 0, f"{tool} has no skill files"
            for f in files:
                assert f.endswith("/skill.yaml"), f"{f} doesn't end with /skill.yaml"

    def test_category_skill_map_covers_test_suite_categories(self):
        categories_in_tests = {t.category for t in SEC_TEST_SUITE}
        mapped_categories = set(CATEGORY_SKILL_MAP.keys())
        missing = categories_in_tests - mapped_categories
        assert not missing, f"Categories in test suite not in CATEGORY_SKILL_MAP: {missing}"


# ---------------------------------------------------------------------------
# _resolve_skill_files
# ---------------------------------------------------------------------------

class TestResolveSkillFiles:

    def test_resolves_from_expected_tools(self):
        tc = get_test_by_id("TC001")  # expects edgar_company
        files = _resolve_skill_files(tc, ["edgar_company"])
        assert "core/skill.yaml" in files
        assert "financials/skill.yaml" in files

    def test_falls_back_to_category(self):
        tc = get_test_by_id("TC008")  # category=reports, expects edgar_filing
        files = _resolve_skill_files(tc, [])
        assert "reports/skill.yaml" in files

    def test_final_fallback_to_core(self):
        """If a test has no expected_tools and no TOOL_SKILL_MAP match, use category fallback."""
        from edgar.ai.evaluation.test_cases import SECAnalysisTestCase
        # Use 'general' category (valid) with no expected_tools
        fake = SECAnalysisTestCase(
            id="FAKE", task="test", expected_patterns=[],
            category="general",
        )
        files = _resolve_skill_files(fake, [])
        assert files == ["core/skill.yaml"]


# ---------------------------------------------------------------------------
# diagnose_trace — failure mode classification
# ---------------------------------------------------------------------------

class TestDiagnoseTrace:

    def test_correct_neutral(self):
        """Both score 1.0, delta=0 → correct, neutral."""
        tc = get_test_by_id("TC001")
        trace = _make_trace(
            tool_calls=[ToolCall("edgar_company", {"ticker": "AAPL"}, "(completed)", True)],
            answer="Apple Inc. (AAPL) has CIK 320193",
        )
        score = _perfect_score()
        w = _make_result("TC001", "with_skills", trace, score)
        wo = _make_result("TC001", "without_skills", trace, score)

        diag = diagnose_trace(w, wo, tc)
        assert diag.failure_mode == "correct"
        assert diag.severity == "low"
        assert diag.delta == 0.0
        assert "neutral" in diag.recommendation.lower()

    def test_correct_helping(self):
        """With-skills scores higher → correct, helping."""
        tc = get_test_by_id("TC001")
        trace = _make_trace(
            tool_calls=[ToolCall("edgar_company", {"ticker": "AAPL"}, "(completed)", True)],
            answer="Apple Inc. (AAPL) has CIK 320193",
        )
        w = _make_result("TC001", "with_skills", trace, _perfect_score())
        wo = _make_result(
            "TC001", "without_skills", trace,
            AgentScore(tool_selection=1.0, answer_quality=0.8, efficiency=1.0, overall=0.91),
        )

        diag = diagnose_trace(w, wo, tc)
        assert diag.failure_mode == "correct"
        assert diag.delta > 0
        assert "helping" in diag.recommendation.lower()

    def test_correct_hurting(self):
        """With-skills scores lower on overall but all sub-scores 1.0 somehow...
        Actually this requires the 'correct' branch with delta < 0."""
        tc = get_test_by_id("TC001")
        trace = _make_trace(
            tool_calls=[ToolCall("edgar_company", {"ticker": "AAPL"}, "(completed)", True)],
            answer="Apple Inc. (AAPL) has CIK 320193",
        )
        w_score = AgentScore(tool_selection=1.0, answer_quality=1.0, efficiency=1.0, overall=0.95)
        wo_score = _perfect_score()
        w = _make_result("TC001", "with_skills", trace, w_score)
        wo = _make_result("TC001", "without_skills", trace, wo_score)

        diag = diagnose_trace(w, wo, tc)
        assert diag.failure_mode == "correct"
        assert diag.delta < 0
        assert "confusion" in diag.recommendation.lower() or "hurting" in diag.detail.lower()

    def test_tool_error(self):
        """No tool calls when expected → tool_error."""
        tc = get_test_by_id("TC001")
        trace = _make_trace(tool_calls=[], answer="I cannot help")
        w = _make_result("TC001", "with_skills", trace, _zero_score())
        wo = _make_result("TC001", "without_skills", trace, _zero_score())

        diag = diagnose_trace(w, wo, tc)
        assert diag.failure_mode == "tool_error"
        assert diag.severity == "high"

    def test_missing_tool(self):
        """Used wrong tool, expected tool missing → missing_tool."""
        tc = get_test_by_id("TC008")  # expects edgar_filing
        trace = _make_trace(
            tool_calls=[ToolCall("edgar_search", {"query": "AAPL 10-K"}, "(completed)", True)],
            answer="Apple risk factors risk",
        )
        score = AgentScore(tool_selection=0.0, answer_quality=1.0, efficiency=1.0, overall=0.65)
        w = _make_result("TC008", "with_skills", trace, score)
        wo = _make_result("TC008", "without_skills", trace, score)

        diag = diagnose_trace(w, wo, tc)
        assert diag.failure_mode == "missing_tool"
        assert diag.severity == "high"
        assert "edgar_filing" in diag.detail
        assert "reports/skill.yaml" in diag.skill_files

    def test_wrong_tool(self):
        """Called expected tool PLUS extra tools → wrong_tool."""
        tc = get_test_by_id("TC008")  # expects edgar_filing
        trace = _make_trace(
            tool_calls=[
                ToolCall("edgar_filing", {"filing_id": "123"}, "(completed)", True),
                ToolCall("edgar_search", {"query": "AAPL"}, "(completed)", True),
                ToolCall("edgar_company", {"ticker": "AAPL"}, "(completed)", True),
            ],
            answer="Apple risk factors risk",
        )
        # tool_selection < 1.0 due to extra tool penalty, but all expected present
        score = AgentScore(tool_selection=0.8, answer_quality=1.0, efficiency=1.0, overall=0.88)
        w = _make_result("TC008", "with_skills", trace, score)
        wo = _make_result("TC008", "without_skills", trace, score)

        diag = diagnose_trace(w, wo, tc)
        assert diag.failure_mode == "wrong_tool"
        assert diag.severity == "high"

    def test_incomplete_answer(self):
        """Tool selection OK but answer missing expected strings."""
        tc = get_test_by_id("TC001")  # expects "Apple" and "320193"
        trace = _make_trace(
            tool_calls=[ToolCall("edgar_company", {"ticker": "AAPL"}, "(completed)", True)],
            answer="Got company data successfully",  # missing Apple and 320193
        )
        score = AgentScore(tool_selection=1.0, answer_quality=0.0, efficiency=1.0, overall=0.55)
        w = _make_result("TC001", "with_skills", trace, score)
        wo = _make_result("TC001", "without_skills", trace, score)

        diag = diagnose_trace(w, wo, tc)
        assert diag.failure_mode == "incomplete_answer"
        assert diag.severity == "medium"
        assert "Apple" in diag.detail or "320193" in diag.detail

    def test_excessive_calls(self):
        """Too many tool calls → excessive_calls."""
        tc = get_test_by_id("TC001")  # max_tool_calls=2
        calls = [ToolCall("edgar_company", {"ticker": "AAPL"}, "(completed)", True)] * 5
        trace = _make_trace(
            tool_calls=calls,
            answer="Apple Inc. (AAPL) has CIK 320193",
        )
        score = AgentScore(tool_selection=1.0, answer_quality=1.0, efficiency=0.5, overall=0.9)
        w = _make_result("TC001", "with_skills", trace, score)
        wo = _make_result("TC001", "without_skills", trace, score)

        diag = diagnose_trace(w, wo, tc)
        assert diag.failure_mode == "excessive_calls"
        assert diag.severity == "low"
        assert "5 tool calls" in diag.detail

    def test_severity_bumped_when_skills_hurt(self):
        """If delta < 0 and not 'correct', severity is bumped to high."""
        tc = get_test_by_id("TC001")
        trace = _make_trace(
            tool_calls=[ToolCall("edgar_company", {"ticker": "AAPL"}, "(completed)", True)],
            answer="Got company data successfully",  # incomplete
        )
        w_score = AgentScore(tool_selection=1.0, answer_quality=0.0, efficiency=1.0, overall=0.55)
        wo_score = AgentScore(tool_selection=1.0, answer_quality=0.5, efficiency=1.0, overall=0.775)
        w = _make_result("TC001", "with_skills", trace, w_score)
        wo = _make_result("TC001", "without_skills", trace, wo_score)

        diag = diagnose_trace(w, wo, tc)
        assert diag.failure_mode == "incomplete_answer"
        assert diag.severity == "high"  # bumped because delta < 0
        assert diag.delta < 0


# ---------------------------------------------------------------------------
# analyze_skill_gaps — aggregation
# ---------------------------------------------------------------------------

class TestAnalyzeSkillGaps:

    def _build_paired_results(self):
        """Build 3 paired results for testing aggregation."""
        tc1 = get_test_by_id("TC001")
        tc4 = get_test_by_id("TC004")
        tc8 = get_test_by_id("TC008")

        # TC001: correct, neutral
        t1 = _make_trace(
            tool_calls=[ToolCall("edgar_company", {}, "(completed)", True)],
            answer="Apple Inc. (AAPL) has CIK 320193",
        )
        s1 = _perfect_score()
        w1 = _make_result("TC001", "with_skills", t1, s1)
        wo1 = _make_result("TC001", "without_skills", t1, s1)

        # TC004: incomplete_answer
        t4 = _make_trace(
            tool_calls=[ToolCall("edgar_company", {}, "(completed)", True)],
            answer="Microsoft data retrieved",  # missing 'Revenue'
        )
        s4 = AgentScore(tool_selection=1.0, answer_quality=0.5, efficiency=1.0, overall=0.775)
        w4 = _make_result("TC004", "with_skills", t4, s4)
        wo4 = _make_result("TC004", "without_skills", t4, s4)

        # TC008: missing_tool
        t8 = _make_trace(
            tool_calls=[ToolCall("edgar_search", {}, "(completed)", True)],
            answer="Apple risk factors risk",
        )
        s8 = AgentScore(tool_selection=0.0, answer_quality=1.0, efficiency=1.0, overall=0.65)
        w8 = _make_result("TC008", "with_skills", t8, s8)
        wo8 = _make_result("TC008", "without_skills", t8, s8)

        return [w1, w4, w8], [wo1, wo4, wo8]

    def test_returns_correct_number_of_diagnostics(self):
        with_r, without_r = self._build_paired_results()
        report = analyze_skill_gaps(with_r, without_r)
        assert len(report.diagnostics) == 3

    def test_groups_by_skill_file(self):
        with_r, without_r = self._build_paired_results()
        report = analyze_skill_gaps(with_r, without_r)
        assert len(report.by_skill_file) > 0
        # reports/skill.yaml should have TC008
        assert "reports/skill.yaml" in report.by_skill_file
        tc8_diags = report.by_skill_file["reports/skill.yaml"]
        assert any(d.test_id == "TC008" for d in tc8_diags)

    def test_groups_by_failure_mode(self):
        with_r, without_r = self._build_paired_results()
        report = analyze_skill_gaps(with_r, without_r)
        assert "correct" in report.by_failure_mode
        assert "missing_tool" in report.by_failure_mode
        assert "incomplete_answer" in report.by_failure_mode

    def test_priority_fixes_sorted_by_severity(self):
        with_r, without_r = self._build_paired_results()
        report = analyze_skill_gaps(with_r, without_r)
        assert len(report.priority_fixes) > 0
        # First fix should be HIGH severity
        assert report.priority_fixes[0].startswith("[HIGH]")

    def test_handles_unpaired_results(self):
        """If a with_result has no matching without_result, skip it."""
        t = _make_trace(
            tool_calls=[ToolCall("edgar_company", {}, "(completed)", True)],
            answer="Apple Inc. (AAPL) has CIK 320193",
        )
        w = [_make_result("TC001", "with_skills", t, _perfect_score())]
        wo = []  # no matching without result
        report = analyze_skill_gaps(w, wo)
        assert len(report.diagnostics) == 0

    def test_handles_empty_inputs(self):
        report = analyze_skill_gaps([], [])
        assert len(report.diagnostics) == 0
        assert len(report.priority_fixes) == 0


# ---------------------------------------------------------------------------
# SkillGapReport
# ---------------------------------------------------------------------------

class TestSkillGapReport:

    def test_to_dict_is_json_serializable(self):
        with_r, without_r = TestAnalyzeSkillGaps()._build_paired_results()
        report = analyze_skill_gaps(with_r, without_r)
        d = report.to_dict()
        # Should serialize to JSON without error
        result = json.dumps(d, indent=2)
        assert len(result) > 0

    def test_to_dict_structure(self):
        with_r, without_r = TestAnalyzeSkillGaps()._build_paired_results()
        report = analyze_skill_gaps(with_r, without_r)
        d = report.to_dict()
        assert "diagnostics" in d
        assert "by_skill_file" in d
        assert "by_failure_mode" in d
        assert "priority_fixes" in d
        assert isinstance(d["diagnostics"], list)
        assert isinstance(d["priority_fixes"], list)

    def test_print_report_runs_without_error(self, capsys):
        with_r, without_r = TestAnalyzeSkillGaps()._build_paired_results()
        report = analyze_skill_gaps(with_r, without_r)
        report.print_report()
        captured = capsys.readouterr()
        assert "SKILL GAP ANALYSIS" in captured.out
        assert "Priority Fixes:" in captured.out
        assert "By Skill File:" in captured.out

    def test_print_report_empty(self, capsys):
        report = SkillGapReport(diagnostics=[])
        report.print_report()
        captured = capsys.readouterr()
        assert "SKILL GAP ANALYSIS" in captured.out
        assert "0 diagnostics" in captured.out


# ---------------------------------------------------------------------------
# SkillDiagnostic
# ---------------------------------------------------------------------------

class TestSkillDiagnostic:

    def test_to_dict(self):
        d = SkillDiagnostic(
            test_id="TC001",
            failure_mode="correct",
            skill_files=["core/skill.yaml"],
            detail="test detail",
            recommendation="test rec",
            severity="low",
            with_score=1.0,
            without_score=1.0,
            delta=0.0,
        )
        result = d.to_dict()
        assert result["test_id"] == "TC001"
        assert result["failure_mode"] == "correct"
        assert result["delta"] == 0.0
        assert isinstance(result["skill_files"], list)
