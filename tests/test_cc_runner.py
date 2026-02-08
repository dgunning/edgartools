"""Tests for the Claude Code-native skill evaluation runner."""

import pytest

from edgar.ai.evaluation.cc_runner import ClaudeCodeRunner
from edgar.ai.evaluation.harness import ABComparison
from edgar.ai.evaluation.test_cases import SEC_TEST_SUITE, get_test_by_id


@pytest.fixture
def runner():
    return ClaudeCodeRunner()


class TestGetSubagentPrompts:
    """Tests for get_subagent_prompts()."""

    def test_returns_two_entries_per_test(self, runner):
        prompts = runner.get_subagent_prompts(["TC001"])
        assert len(prompts) == 2

    def test_returns_correct_structure(self, runner):
        prompts = runner.get_subagent_prompts(["TC001"])
        for p in prompts:
            assert "test_id" in p
            assert "condition" in p
            assert "prompt" in p

    def test_conditions_are_with_and_without(self, runner):
        prompts = runner.get_subagent_prompts(["TC001"])
        conditions = {p["condition"] for p in prompts}
        assert conditions == {"with_skills", "without_skills"}

    def test_multiple_tests(self, runner):
        prompts = runner.get_subagent_prompts(["TC001", "TC002", "TC003"])
        assert len(prompts) == 6

    def test_none_uses_all_tests(self, runner):
        prompts = runner.get_subagent_prompts()
        assert len(prompts) == 2 * len(SEC_TEST_SUITE)

    def test_skips_invalid_test_ids(self, runner):
        prompts = runner.get_subagent_prompts(["TC001", "INVALID", "TC002"])
        assert len(prompts) == 4  # 2 valid tests × 2 conditions


class TestFormatSubagentPrompt:
    """Tests for format_subagent_prompt()."""

    def test_with_skills_contains_skill_context(self, runner):
        prompt = runner.format_subagent_prompt("TC001", with_skills=True)
        assert "EdgarTools skill documentation" in prompt

    def test_without_skills_contains_minimal_context(self, runner):
        prompt = runner.format_subagent_prompt("TC001", with_skills=False)
        assert "EdgarTools is a Python library" in prompt

    def test_contains_task_text(self, runner):
        test = get_test_by_id("TC001")
        prompt = runner.format_subagent_prompt("TC001", with_skills=True)
        assert test.task in prompt

    def test_contains_isolation_instruction(self, runner):
        prompt = runner.format_subagent_prompt("TC001", with_skills=True)
        assert "ONLY Python code" in prompt

    def test_invalid_test_id_raises(self, runner):
        with pytest.raises(ValueError, match="not found"):
            runner.format_subagent_prompt("INVALID", with_skills=True)

    def test_without_skills_does_not_contain_skill_docs(self, runner):
        prompt = runner.format_subagent_prompt("TC001", with_skills=False)
        assert "skill documentation" not in prompt


class TestEvaluate:
    """Tests for evaluate()."""

    def test_produces_valid_ab_comparison(self, runner):
        with_code = {
            "TC001": 'from edgar import Company\ncompany = Company("AAPL")\nprint(company.cik)',
        }
        without_code = {
            "TC001": 'import edgar\nprint("hello")',
        }
        comparison = runner.evaluate(with_code, without_code)
        assert isinstance(comparison, ABComparison)
        assert comparison.with_skills is not None
        assert comparison.without_skills is not None

    def test_with_skills_scores_higher(self, runner):
        with_code = {
            "TC001": 'from edgar import Company\ncompany = Company("AAPL")\nprint(company.cik)',
        }
        without_code = {
            "TC001": 'print("hello world")',
        }
        comparison = runner.evaluate(with_code, without_code)
        ws_score = comparison.with_skills.summary_stats.get("mean_score", 0)
        wos_score = comparison.without_skills.summary_stats.get("mean_score", 0)
        assert ws_score > wos_score

    def test_diagnose_adds_metadata(self, runner):
        with_code = {
            "TC001": 'from edgar import Company\ncompany = Company("AAPL")\nprint(company.cik)',
        }
        without_code = {
            "TC001": 'print("hello")',
        }
        comparison = runner.evaluate(with_code, without_code, diagnose=True)
        assert hasattr(comparison, 'metadata')
        assert comparison.metadata is not None
        assert "constitution_diagnostics" in comparison.metadata

    def test_multiple_tests(self, runner):
        with_code = {
            "TC001": 'from edgar import Company\ncompany = Company("AAPL")\nprint(company.cik)',
            "TC002": 'from edgar import Company\ncompany = Company("AAPL")\nfiling = company.get_filings(form="10-K")[0]\nprint(filing.filing_date)',
        }
        without_code = {
            "TC001": 'print("hello")',
            "TC002": 'print("world")',
        }
        comparison = runner.evaluate(with_code, without_code)
        assert comparison.with_skills.summary_stats["total_tests"] == 2
        assert comparison.without_skills.summary_stats["total_tests"] == 2


class TestRunFull:
    """Tests for run_full()."""

    def test_returns_prompts_and_callback(self, runner):
        prompts, callback = runner.run_full(["TC001"])
        assert len(prompts) == 2
        assert callable(callback)

    def test_callback_produces_comparison(self, runner):
        _, callback = runner.run_full(["TC001"])
        with_code = {
            "TC001": 'from edgar import Company\ncompany = Company("AAPL")\nprint(company.cik)',
        }
        without_code = {
            "TC001": 'print("hello")',
        }
        comparison = callback(with_code, without_code)
        assert isinstance(comparison, ABComparison)


class TestExtractCode:
    """Tests for extract_code() static method."""

    def test_extracts_from_markdown(self):
        response = '```python\nfrom edgar import Company\nprint("hello")\n```'
        code = ClaudeCodeRunner.extract_code(response)
        assert "from edgar import Company" in code

    def test_extracts_raw_code(self):
        response = 'from edgar import Company\ncompany = Company("AAPL")'
        code = ClaudeCodeRunner.extract_code(response)
        assert "Company" in code
