"""Unit tests for the LLM-as-Judge evaluator module."""

import pytest

from edgar.ai.evaluation.judge import (
    JudgeComparison,
    JudgeScore,
    build_judge_comparison,
    build_judge_prompt,
    format_judge_report,
    parse_judge_response,
)
from edgar.ai.evaluation.test_cases import get_test_by_id


class TestJudgeScore:
    """Tests for JudgeScore dataclass."""

    def test_overall_weighted_score(self):
        score = JudgeScore(
            test_id="TC001",
            condition="with_skills",
            correctness=5,
            api_usage=5,
            conciseness=5,
            efficiency=5,
        )
        assert score.overall == 1.0

    def test_overall_minimum_score(self):
        score = JudgeScore(
            test_id="TC001",
            condition="without_skills",
            correctness=1,
            api_usage=1,
            conciseness=1,
            efficiency=1,
        )
        assert score.overall == 0.2

    def test_overall_weights_api_usage_highest(self):
        # Changing api_usage by 2 should have more impact than changing
        # any single other dimension by 2 (because api_usage has 0.4 weight)
        base = JudgeScore(
            test_id="TC001", condition="with_skills",
            correctness=3, api_usage=3, conciseness=3, efficiency=3,
        )
        bump_api = JudgeScore(
            test_id="TC001", condition="with_skills",
            correctness=3, api_usage=5, conciseness=3, efficiency=3,
        )
        bump_correctness = JudgeScore(
            test_id="TC001", condition="with_skills",
            correctness=5, api_usage=3, conciseness=3, efficiency=3,
        )
        api_delta = bump_api.overall - base.overall
        correctness_delta = bump_correctness.overall - base.overall
        assert api_delta > correctness_delta

    def test_overall_mixed_scores(self):
        score = JudgeScore(
            test_id="TC001",
            condition="with_skills",
            correctness=4,
            api_usage=5,
            conciseness=3,
            efficiency=4,
        )
        # (4*0.2 + 5*0.4 + 3*0.2 + 4*0.2) / 5.0 = (0.8+2.0+0.6+0.8)/5 = 4.2/5 = 0.84
        assert score.overall == 0.84


class TestBuildJudgePrompt:
    """Tests for build_judge_prompt function."""

    def test_includes_task(self):
        test_case = get_test_by_id("TC001")
        prompt = build_judge_prompt("TC001", "print('hello')", test_case)
        assert test_case.task in prompt

    def test_includes_reference_code(self):
        test_case = get_test_by_id("TC001")
        prompt = build_judge_prompt("TC001", "print('hello')", test_case)
        assert 'Company("AAPL")' in prompt

    def test_includes_generated_code(self):
        test_case = get_test_by_id("TC001")
        code = "from edgar import Company\nc = Company('AAPL')\nprint(c.cik)"
        prompt = build_judge_prompt("TC001", code, test_case)
        assert "c = Company('AAPL')" in prompt

    def test_includes_scoring_rubric(self):
        test_case = get_test_by_id("TC001")
        prompt = build_judge_prompt("TC001", "x=1", test_case)
        assert "correctness" in prompt
        assert "api_usage" in prompt
        assert "conciseness" in prompt
        assert "efficiency" in prompt

    def test_handles_no_reference_code(self):
        from edgar.ai.evaluation.test_cases import SECAnalysisTestCase
        test_case = SECAnalysisTestCase(
            id="TCXX",
            task="Do something",
            expected_patterns=[],
            difficulty="easy",
            category="lookup",
            reference_code=None,
        )
        prompt = build_judge_prompt("TCXX", "x=1", test_case)
        assert "No reference code provided" in prompt


class TestParseJudgeResponse:
    """Tests for parse_judge_response function."""

    def test_parse_valid_json(self):
        response = '{"correctness": 5, "api_usage": 4, "conciseness": 3, "efficiency": 5, "rationale": "good"}'
        score = parse_judge_response(response, "TC001", "with_skills")
        assert score.correctness == 5
        assert score.api_usage == 4
        assert score.conciseness == 3
        assert score.efficiency == 5
        assert score.rationale == "good"
        assert score.test_id == "TC001"
        assert score.condition == "with_skills"

    def test_parse_markdown_wrapped_json(self):
        response = """Here are my scores:
```json
{"correctness": 4, "api_usage": 5, "conciseness": 4, "efficiency": 3, "rationale": "clean code"}
```
"""
        score = parse_judge_response(response, "TC002", "without_skills")
        assert score.correctness == 4
        assert score.api_usage == 5
        assert score.conciseness == 4
        assert score.efficiency == 3

    def test_parse_markdown_without_json_tag(self):
        response = """```
{"correctness": 2, "api_usage": 3, "conciseness": 4, "efficiency": 5, "rationale": "ok"}
```"""
        score = parse_judge_response(response, "TC001", "with_skills")
        assert score.correctness == 2
        assert score.api_usage == 3

    def test_returns_defaults_on_garbage(self):
        score = parse_judge_response("this is not json at all!", "TC001", "with_skills")
        assert score.correctness == 3
        assert score.api_usage == 3
        assert score.conciseness == 3
        assert score.efficiency == 3
        assert "[parse error]" in score.rationale

    def test_returns_defaults_on_empty_string(self):
        score = parse_judge_response("", "TC001", "with_skills")
        assert score.correctness == 3
        assert "[parse error]" in score.rationale

    def test_clamps_out_of_range_scores_to_default(self):
        response = '{"correctness": 10, "api_usage": 0, "conciseness": 3, "efficiency": -1}'
        score = parse_judge_response(response, "TC001", "with_skills")
        assert score.correctness == 3  # 10 out of range -> default 3
        assert score.api_usage == 3    # 0 out of range -> default 3
        assert score.conciseness == 3  # valid
        assert score.efficiency == 3   # -1 out of range -> default 3

    def test_handles_missing_dimensions(self):
        response = '{"correctness": 5}'
        score = parse_judge_response(response, "TC001", "with_skills")
        assert score.correctness == 5
        assert score.api_usage == 3     # missing -> default
        assert score.conciseness == 3   # missing -> default
        assert score.efficiency == 3    # missing -> default

    def test_handles_float_scores(self):
        response = '{"correctness": 4.0, "api_usage": 3.5, "conciseness": 5.0, "efficiency": 2.0}'
        score = parse_judge_response(response, "TC001", "with_skills")
        assert score.correctness == 4
        assert score.api_usage == 3  # 3.5 is valid (1<=3.5<=5), truncated to int 3
        assert score.conciseness == 5
        assert score.efficiency == 2


class TestBuildJudgeComparison:
    """Tests for build_judge_comparison function."""

    def test_computes_per_test_deltas(self):
        with_scores = {
            "TC001": JudgeScore("TC001", "with_skills", 5, 5, 4, 5),
        }
        without_scores = {
            "TC001": JudgeScore("TC001", "without_skills", 4, 2, 3, 3),
        }
        comp = build_judge_comparison(with_scores, without_scores)
        deltas = comp.per_test_deltas["TC001"]
        assert deltas["correctness"] == 1
        assert deltas["api_usage"] == 3
        assert deltas["conciseness"] == 1
        assert deltas["efficiency"] == 2

    def test_determines_winner_with_skills(self):
        with_scores = {
            "TC001": JudgeScore("TC001", "with_skills", 5, 5, 5, 5),
        }
        without_scores = {
            "TC001": JudgeScore("TC001", "without_skills", 1, 1, 1, 1),
        }
        comp = build_judge_comparison(with_scores, without_scores)
        assert comp.winner == "with_skills"

    def test_determines_winner_without_skills(self):
        with_scores = {
            "TC001": JudgeScore("TC001", "with_skills", 1, 1, 1, 1),
        }
        without_scores = {
            "TC001": JudgeScore("TC001", "without_skills", 5, 5, 5, 5),
        }
        comp = build_judge_comparison(with_scores, without_scores)
        assert comp.winner == "without_skills"

    def test_determines_tie(self):
        with_scores = {
            "TC001": JudgeScore("TC001", "with_skills", 3, 3, 3, 3),
        }
        without_scores = {
            "TC001": JudgeScore("TC001", "without_skills", 3, 3, 3, 3),
        }
        comp = build_judge_comparison(with_scores, without_scores)
        assert comp.winner == "tie"

    def test_mean_deltas_across_multiple_tests(self):
        with_scores = {
            "TC001": JudgeScore("TC001", "with_skills", 5, 5, 5, 5),
            "TC002": JudgeScore("TC002", "with_skills", 3, 3, 3, 3),
        }
        without_scores = {
            "TC001": JudgeScore("TC001", "without_skills", 3, 3, 3, 3),
            "TC002": JudgeScore("TC002", "without_skills", 3, 3, 3, 3),
        }
        comp = build_judge_comparison(with_scores, without_scores)
        # TC001: deltas are all +2; TC002: deltas are all 0
        # Mean delta per dimension = (2+0)/2 = 1.0
        assert comp.mean_deltas["correctness"] == 1.0
        assert comp.mean_deltas["api_usage"] == 1.0

    def test_handles_non_overlapping_test_ids(self):
        with_scores = {
            "TC001": JudgeScore("TC001", "with_skills", 5, 5, 5, 5),
        }
        without_scores = {
            "TC002": JudgeScore("TC002", "without_skills", 3, 3, 3, 3),
        }
        comp = build_judge_comparison(with_scores, without_scores)
        # No common test IDs -> no deltas
        assert len(comp.per_test_deltas) == 0
        assert comp.winner == "tie"


class TestFormatJudgeReport:
    """Tests for format_judge_report function."""

    def test_produces_readable_output(self):
        with_scores = {
            "TC001": JudgeScore("TC001", "with_skills", 5, 5, 4, 5),
        }
        without_scores = {
            "TC001": JudgeScore("TC001", "without_skills", 3, 2, 3, 3),
        }
        comp = build_judge_comparison(with_scores, without_scores)
        report = format_judge_report(comp)
        assert "LLM JUDGE A/B COMPARISON" in report
        assert "TC001" in report
        assert "correctness" in report
        assert "api_usage" in report
        assert "Mean Deltas" in report
        assert "Winner" in report

    def test_shows_winner(self):
        with_scores = {
            "TC001": JudgeScore("TC001", "with_skills", 5, 5, 5, 5),
        }
        without_scores = {
            "TC001": JudgeScore("TC001", "without_skills", 1, 1, 1, 1),
        }
        comp = build_judge_comparison(with_scores, without_scores)
        report = format_judge_report(comp)
        assert "WITH SKILLS" in report


class TestClaudeCodeRunnerJudge:
    """Tests for ClaudeCodeRunner judge methods."""

    def test_get_judge_prompts_structure(self):
        from edgar.ai.evaluation.cc_runner import ClaudeCodeRunner
        runner = ClaudeCodeRunner()
        with_code = {"TC001": "from edgar import Company\nCompany('AAPL').cik"}
        without_code = {"TC001": "import requests\nrequests.get('https://sec.gov')"}
        prompts = runner.get_judge_prompts(with_code, without_code)
        assert len(prompts) == 2
        assert prompts[0]["test_id"] == "TC001"
        assert prompts[0]["condition"] in ("with_skills", "without_skills")
        assert "prompt" in prompts[0]

    def test_get_judge_prompts_skips_unknown_test_ids(self):
        from edgar.ai.evaluation.cc_runner import ClaudeCodeRunner
        runner = ClaudeCodeRunner()
        with_code = {"TCXXX": "x=1"}
        without_code = {"TCXXX": "y=2"}
        prompts = runner.get_judge_prompts(with_code, without_code)
        assert len(prompts) == 0

    def test_get_judge_prompts_multiple_tests(self):
        from edgar.ai.evaluation.cc_runner import ClaudeCodeRunner
        runner = ClaudeCodeRunner()
        with_code = {"TC001": "code1", "TC002": "code2"}
        without_code = {"TC001": "code3", "TC002": "code4"}
        prompts = runner.get_judge_prompts(with_code, without_code)
        assert len(prompts) == 4  # 2 tests x 2 conditions

    def test_judge_returns_comparison(self):
        from edgar.ai.evaluation.cc_runner import ClaudeCodeRunner
        runner = ClaudeCodeRunner()
        with_scores = {
            "TC001": JudgeScore("TC001", "with_skills", 5, 5, 5, 5),
        }
        without_scores = {
            "TC001": JudgeScore("TC001", "without_skills", 3, 3, 3, 3),
        }
        comp = runner.judge(with_scores, without_scores, print_report=False)
        assert isinstance(comp, JudgeComparison)
        assert comp.winner == "with_skills"
