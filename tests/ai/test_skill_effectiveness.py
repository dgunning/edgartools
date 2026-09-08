"""
Tests for the Skill Evaluation Framework.

These tests verify the evaluation harness, test cases, and evaluators
function correctly for measuring skill effectiveness.
"""

import pytest
from dataclasses import asdict


class TestSECAnalysisTestCase:
    """Test the SECAnalysisTestCase dataclass."""

    def test_test_case_creation(self):
        """Test creating a valid test case."""
        from edgar.ai.evaluation.test_cases import SECAnalysisTestCase

        test = SECAnalysisTestCase(
            id="TC999",
            task="Test task",
            expected_patterns=[r"Company\("],
            max_tokens=500,
            difficulty="easy",
            category="lookup",
        )
        assert test.id == "TC999"
        assert test.task == "Test task"
        assert test.difficulty == "easy"
        assert test.category == "lookup"
        assert test.max_tokens == 500

    def test_invalid_difficulty_raises(self):
        """Test that invalid difficulty raises ValueError."""
        from edgar.ai.evaluation.test_cases import SECAnalysisTestCase

        with pytest.raises(ValueError, match="difficulty must be one of"):
            SECAnalysisTestCase(
                id="TC999",
                task="Test task",
                expected_patterns=[],
                difficulty="very_hard",  # Invalid
                category="lookup",
            )

    def test_invalid_category_raises(self):
        """Test that invalid category raises ValueError."""
        from edgar.ai.evaluation.test_cases import SECAnalysisTestCase

        with pytest.raises(ValueError, match="category must be one of"):
            SECAnalysisTestCase(
                id="TC999",
                task="Test task",
                expected_patterns=[],
                difficulty="easy",
                category="unknown_category",  # Invalid
            )


class TestTestSuiteHelpers:
    """Test the test suite helper functions."""

    def test_get_test_by_id(self):
        """Test retrieving test by ID."""
        from edgar.ai.evaluation.test_cases import get_test_by_id

        test = get_test_by_id("TC001")
        assert test is not None
        assert test.id == "TC001"
        assert "Apple" in test.task or "AAPL" in test.task

    def test_get_test_by_id_not_found(self):
        """Test that missing ID returns None."""
        from edgar.ai.evaluation.test_cases import get_test_by_id

        test = get_test_by_id("NONEXISTENT")
        assert test is None

    def test_get_tests_by_category(self):
        """Test filtering tests by category."""
        from edgar.ai.evaluation.test_cases import get_tests_by_category

        financial_tests = get_tests_by_category("financial")
        assert len(financial_tests) >= 2
        assert all(t.category == "financial" for t in financial_tests)

    def test_get_tests_by_difficulty(self):
        """Test filtering tests by difficulty."""
        from edgar.ai.evaluation.test_cases import get_tests_by_difficulty

        easy_tests = get_tests_by_difficulty("easy")
        assert len(easy_tests) >= 3
        assert all(t.difficulty == "easy" for t in easy_tests)

    def test_sec_test_suite_coverage(self):
        """Test that SEC_TEST_SUITE has expected coverage."""
        from edgar.ai.evaluation.test_cases import SEC_TEST_SUITE

        # Check we have at least 10 tests
        assert len(SEC_TEST_SUITE) >= 10

        # Check difficulty distribution
        difficulties = {t.difficulty for t in SEC_TEST_SUITE}
        assert "easy" in difficulties
        assert "medium" in difficulties
        assert "hard" in difficulties

        # Check category coverage
        categories = {t.category for t in SEC_TEST_SUITE}
        assert "lookup" in categories
        assert "financial" in categories
        assert "filing" in categories


class TestTokenCounting:
    """Test token counting functionality."""

    def test_count_tokens(self):
        """Test basic token counting."""
        from edgar.ai.evaluation.evaluators import count_tokens

        # Simple string
        text = "from edgar import Company"
        tokens = count_tokens(text)
        # ~25 chars / 4 = ~6 tokens
        assert 5 <= tokens <= 8

    def test_count_tokens_empty(self):
        """Test token counting for empty string."""
        from edgar.ai.evaluation.evaluators import count_tokens

        assert count_tokens("") == 1  # Minimum of 1

    def test_count_tokens_long(self):
        """Test token counting for longer text."""
        from edgar.ai.evaluation.evaluators import count_tokens

        # 400 characters should be ~100 tokens
        text = "x" * 400
        tokens = count_tokens(text)
        assert tokens == 100


class TestCodeExecution:
    """Test code execution evaluator."""

    def test_execute_simple_code(self):
        """Test executing simple Python code."""
        from edgar.ai.evaluation.evaluators import evaluate_code_execution

        result = evaluate_code_execution("print(1 + 1)")
        assert result.success is True
        assert "2" in result.output
        assert result.error is None

    def test_execute_syntax_error(self):
        """Test handling syntax errors."""
        from edgar.ai.evaluation.evaluators import evaluate_code_execution

        result = evaluate_code_execution("print(")
        assert result.success is False
        assert result.error is not None
        assert result.error_type == "SyntaxError"

    def test_execute_runtime_error(self):
        """Test handling runtime errors."""
        from edgar.ai.evaluation.evaluators import evaluate_code_execution

        result = evaluate_code_execution("x = 1 / 0")
        assert result.success is False
        assert result.error is not None
        assert result.error_type == "ZeroDivisionError"

    def test_execution_result_to_dict(self):
        """Test ExecutionResult serialization."""
        from edgar.ai.evaluation.evaluators import ExecutionResult

        result = ExecutionResult(
            success=True,
            output="test output",
            error=None,
            error_type=None,
            execution_time_ms=10.5,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["output"] == "test output"
        assert d["execution_time_ms"] == 10.5


class TestPatternCompliance:
    """Test pattern compliance evaluator."""

    def test_pattern_match_found(self):
        """Test matching expected patterns."""
        from edgar.ai.evaluation.evaluators import evaluate_pattern_compliance
        from edgar.ai.evaluation.test_cases import get_test_by_id

        test = get_test_by_id("TC001")
        code = '''
from edgar import Company
company = Company("AAPL")
print(company.cik)
'''
        result = evaluate_pattern_compliance(code, test)
        assert result.compliant is True
        assert result.score > 0.5

    def test_pattern_forbidden_violation(self):
        """Test detection of forbidden patterns."""
        from edgar.ai.evaluation.evaluators import evaluate_pattern_compliance
        from edgar.ai.evaluation.test_cases import SECAnalysisTestCase

        test = SECAnalysisTestCase(
            id="TEST",
            task="Test",
            expected_patterns=[r"Company\("],
            forbidden_patterns=[r"for\s+.*\s+in\s+.*get_filings\(\)"],
            difficulty="easy",
            category="lookup",
        )
        code = '''
for f in company.get_filings():
    print(f)
'''
        result = evaluate_pattern_compliance(code, test)
        # Should have violation
        assert any(found for _, found in result.forbidden_violations)
        assert result.score < 1.0

    def test_pattern_result_to_dict(self):
        """Test PatternResult serialization."""
        from edgar.ai.evaluation.evaluators import PatternResult

        result = PatternResult(
            compliant=True,
            expected_matches=[("pattern1", True), ("pattern2", False)],
            forbidden_violations=[("bad_pattern", False)],
            score=0.75,
        )
        d = result.to_dict()
        assert d["compliant"] is True
        assert len(d["expected_matches"]) == 2
        assert d["score"] == 0.75


class TestTokenEfficiency:
    """Test token efficiency evaluator."""

    def test_efficiency_under_budget(self):
        """Test code well under budget."""
        from edgar.ai.evaluation.evaluators import evaluate_token_efficiency
        from edgar.ai.evaluation.test_cases import SECAnalysisTestCase

        test = SECAnalysisTestCase(
            id="TEST",
            task="Test",
            expected_patterns=[],
            max_tokens=1000,
            difficulty="easy",
            category="lookup",
        )
        code = "Company('AAPL').cik"  # ~20 chars = ~5 tokens

        result = evaluate_token_efficiency(code, test)
        assert result.within_budget is True
        assert result.efficiency_score == 1.0  # Very efficient

    def test_efficiency_over_budget(self):
        """Test code over budget."""
        from edgar.ai.evaluation.evaluators import evaluate_token_efficiency
        from edgar.ai.evaluation.test_cases import SECAnalysisTestCase

        test = SECAnalysisTestCase(
            id="TEST",
            task="Test",
            expected_patterns=[],
            max_tokens=10,  # Very tight budget
            difficulty="easy",
            category="lookup",
        )
        code = "x" * 100  # ~25 tokens, well over budget

        result = evaluate_token_efficiency(code, test)
        assert result.within_budget is False
        assert result.efficiency_score < 0.7


class TestCombinedEvaluation:
    """Test combined evaluation function."""

    def test_evaluate_code_without_execution(self):
        """Test combined evaluation without executing code."""
        from edgar.ai.evaluation.evaluators import evaluate_code
        from edgar.ai.evaluation.test_cases import get_test_by_id

        test = get_test_by_id("TC001")
        code = '''
from edgar import Company
company = Company("AAPL")
print(f"CIK: {company.cik}")
'''
        result = evaluate_code(code, test, execute=False)

        assert result.execution.success is True  # Assumed success
        assert result.pattern.score > 0
        assert result.efficiency.within_budget is True
        assert 0 <= result.overall_score <= 1

    def test_combined_evaluation_to_dict(self):
        """Test CombinedEvaluation serialization."""
        from edgar.ai.evaluation.evaluators import evaluate_code
        from edgar.ai.evaluation.test_cases import get_test_by_id

        test = get_test_by_id("TC001")
        code = 'Company("AAPL").cik'

        result = evaluate_code(code, test, execute=False)
        d = result.to_dict()

        assert "execution" in d
        assert "pattern" in d
        assert "efficiency" in d
        assert "overall_score" in d


class TestSkillEvaluationHarness:
    """Test the main evaluation harness."""

    def test_harness_creation(self):
        """Test creating evaluation harness."""
        from edgar.ai.evaluation.harness import SkillEvaluationHarness

        harness = SkillEvaluationHarness()
        assert len(harness.list_tests()) >= 10

    def test_evaluate_single_code(self):
        """Test evaluating a single code sample."""
        from edgar.ai.evaluation.harness import SkillEvaluationHarness

        harness = SkillEvaluationHarness()
        code = '''
from edgar import Company
company = Company("AAPL")
print(company.cik)
'''
        result = harness.evaluate_code("TC001", code, condition="test")

        assert result.test_id == "TC001"
        assert result.condition == "test"
        assert 0 <= result.score <= 1

    def test_evaluate_invalid_test_id(self):
        """Test that invalid test ID raises error."""
        from edgar.ai.evaluation.harness import SkillEvaluationHarness

        harness = SkillEvaluationHarness()

        with pytest.raises(ValueError, match="not found"):
            harness.evaluate_code("INVALID", "print('hi')")

    def test_run_suite(self):
        """Test running a suite of evaluations."""
        from edgar.ai.evaluation.harness import SkillEvaluationHarness

        harness = SkillEvaluationHarness()
        samples = {
            "TC001": 'Company("AAPL").cik',
            "TC002": 'Company("AAPL").get_filings(form="10-K")[0].filing_date',
            "TC003": 'len(Company("AAPL").get_filings(form="10-K"))',
        }

        report = harness.run_suite(samples, condition="test_run")

        assert report.condition == "test_run"
        assert len(report.results) == 3
        assert "mean_score" in report.summary_stats
        assert report.summary_stats["total_tests"] == 3

    def test_report_summary(self):
        """Test report summary generation."""
        from edgar.ai.evaluation.harness import SkillEvaluationHarness

        harness = SkillEvaluationHarness()
        samples = {
            "TC001": 'Company("AAPL").cik',
        }

        report = harness.run_suite(samples, condition="summary_test")
        summary = report.summary()

        assert "EVALUATION REPORT" in summary
        assert "summary_test" in summary
        assert "Mean Score" in summary

    def test_compare_conditions(self):
        """Test A/B comparison between conditions."""
        from edgar.ai.evaluation.harness import SkillEvaluationHarness

        harness = SkillEvaluationHarness()

        # Simulated "with skills" - correct pattern
        with_skills = {
            "TC001": 'Company("AAPL").cik',
        }

        # Simulated "without skills" - less correct pattern
        without_skills = {
            "TC001": 'get_filings()',  # Missing key patterns
        }

        comparison = harness.compare_conditions(with_skills, without_skills)

        assert comparison.with_skills.condition == "with_skills"
        assert comparison.without_skills.condition == "without_skills"
        assert "score_absolute" in comparison.improvement

    def test_comparison_summary(self):
        """Test A/B comparison summary generation."""
        from edgar.ai.evaluation.harness import SkillEvaluationHarness

        harness = SkillEvaluationHarness()
        comparison = harness.compare_conditions(
            {"TC001": 'Company("AAPL").cik'},
            {"TC001": 'print("hello")'},
        )

        summary = comparison.summary()
        assert "A/B COMPARISON" in summary
        assert "Without Skills" in summary
        assert "With Skills" in summary


class TestReportSerialization:
    """Test report JSON serialization."""

    def test_test_result_to_dict(self):
        """Test TestResult serialization."""
        from edgar.ai.evaluation.harness import SkillEvaluationHarness

        harness = SkillEvaluationHarness()
        result = harness.evaluate_code("TC001", 'Company("AAPL").cik')

        d = result.to_dict()
        assert "test_id" in d
        assert "evaluation" in d
        assert "success" in d
        assert "score" in d

    def test_report_to_json(self):
        """Test EvaluationReport JSON export."""
        import json
        from edgar.ai.evaluation.harness import SkillEvaluationHarness

        harness = SkillEvaluationHarness()
        report = harness.run_suite({"TC001": 'Company("AAPL").cik'})

        json_str = report.to_json()
        parsed = json.loads(json_str)

        assert "condition" in parsed
        assert "results" in parsed
        assert "summary_stats" in parsed


class TestCLIInterface:
    """Test CLI interface."""

    def test_harness_main_dry_run(self, capsys):
        """Test CLI dry run mode."""
        import sys
        from unittest.mock import patch

        from edgar.ai.evaluation.harness import main

        with patch.object(sys, "argv", ["harness", "--dry-run"]):
            main()

        captured = capsys.readouterr()
        assert "TC001" in captured.out
        assert "[easy]" in captured.out or "easy" in captured.out


class TestCodeExtraction:
    """Test code extraction from LLM responses."""

    def test_extract_python_code_block(self):
        """Test extracting code from ```python blocks."""
        from edgar.ai.evaluation.runner import extract_code_from_response

        response = """Here's the code:

```python
from edgar import Company
company = Company("AAPL")
print(company.cik)
```

This will print Apple's CIK."""

        code = extract_code_from_response(response)
        assert "from edgar import Company" in code
        assert "Company(\"AAPL\")" in code
        assert "print(company.cik)" in code
        assert "Here's the code" not in code

    def test_extract_generic_code_block(self):
        """Test extracting code from generic ``` blocks."""
        from edgar.ai.evaluation.runner import extract_code_from_response

        response = """
```
company = Company("MSFT")
```
"""
        code = extract_code_from_response(response)
        assert 'Company("MSFT")' in code

    def test_extract_raw_code(self):
        """Test extracting code without markdown blocks."""
        from edgar.ai.evaluation.runner import extract_code_from_response

        response = """from edgar import Company
company = Company("AAPL")
print(company.cik)"""

        code = extract_code_from_response(response)
        assert "from edgar import Company" in code

    def test_extract_multiple_blocks(self):
        """Test extracting from multiple code blocks."""
        from edgar.ai.evaluation.runner import extract_code_from_response

        response = """First part:
```python
from edgar import Company
```

Second part:
```python
company = Company("AAPL")
```
"""
        code = extract_code_from_response(response)
        assert "from edgar import Company" in code
        assert "Company(\"AAPL\")" in code


class TestSkillContextLoading:
    """Test skill context loading."""

    def test_load_skill_context(self):
        """Test loading skill context from yaml files."""
        from edgar.ai.evaluation.runner import load_skill_context

        context = load_skill_context()
        # Should have some content from skill.yaml
        assert len(context) > 100
        assert "Company" in context or "edgar" in context.lower()

    def test_get_minimal_context(self):
        """Test minimal context for without-skills condition."""
        from edgar.ai.evaluation.runner import get_minimal_context

        context = get_minimal_context()
        assert "from edgar import" in context
        assert "Company" in context


class TestPromptConstruction:
    """Test prompt building for LLM."""

    def test_build_prompt_with_skills(self):
        """Test building prompt with skill context."""
        from edgar.ai.evaluation.runner import build_prompt
        from edgar.ai.evaluation.test_cases import get_test_by_id

        test = get_test_by_id("TC001")
        system, user = build_prompt(test, with_skills=True)

        assert "EdgarTools" in system
        assert test.task in user
        assert "Write" in user or "code" in user.lower()

    def test_build_prompt_without_skills(self):
        """Test building prompt without skill context."""
        from edgar.ai.evaluation.runner import build_prompt
        from edgar.ai.evaluation.test_cases import get_test_by_id

        test = get_test_by_id("TC001")
        system, user = build_prompt(test, with_skills=False)

        # Should have minimal context
        assert "from edgar import" in system
        assert test.task in user
        # Should NOT have full skill documentation
        assert "patterns:" not in system


class TestGenerationResult:
    """Test GenerationResult dataclass."""

    def test_generation_result_to_dict(self):
        """Test GenerationResult serialization."""
        from edgar.ai.evaluation.runner import GenerationResult

        result = GenerationResult(
            test_id="TC001",
            condition="with_skills",
            code='Company("AAPL").cik',
            raw_response="Here is the code...",
            model="claude-sonnet-4-20250514",
            tokens_used=150,
            generation_time_ms=1234.5,
        )

        d = result.to_dict()
        assert d["test_id"] == "TC001"
        assert d["condition"] == "with_skills"
        assert d["tokens_used"] == 150
        assert d["error"] is None

    def test_generation_result_with_error(self):
        """Test GenerationResult with error."""
        from edgar.ai.evaluation.runner import GenerationResult

        result = GenerationResult(
            test_id="TC001",
            condition="with_skills",
            code="",
            raw_response="",
            model="claude-sonnet-4-20250514",
            tokens_used=0,
            generation_time_ms=0,
            error="API error: rate limited",
        )

        d = result.to_dict()
        assert d["error"] == "API error: rate limited"


class TestSkillTestRunner:
    """Test SkillTestRunner class."""

    def test_runner_creation(self):
        """Test creating runner instance."""
        from edgar.ai.evaluation.runner import SkillTestRunner

        # Should work without API key for testing
        runner = SkillTestRunner(api_key="test-key")
        assert runner.model == "claude-sonnet-4-20250514"
        assert runner.harness is not None

    def test_runner_custom_model(self):
        """Test runner with custom model."""
        from edgar.ai.evaluation.runner import SkillTestRunner

        runner = SkillTestRunner(
            api_key="test-key",
            model="claude-haiku-4-20250514",
            max_tokens=512,
        )
        assert runner.model == "claude-haiku-4-20250514"
        assert runner.max_tokens == 512


class TestAnalysisForImprovements:
    """Test improvement analysis functionality."""

    def test_analyze_improvements_skills_worse(self):
        """Test analysis when skills perform worse."""
        from edgar.ai.evaluation.runner import SkillTestRunner
        from edgar.ai.evaluation.harness import ABComparison, EvaluationReport

        runner = SkillTestRunner(api_key="test-key")

        # Create mock comparison where skills are worse
        with_report = runner.harness.run_suite(
            {"TC001": 'print("wrong")'},  # Bad code
            condition="with_skills",
        )
        without_report = runner.harness.run_suite(
            {"TC001": 'Company("AAPL").cik'},  # Good code
            condition="without_skills",
        )

        comparison = ABComparison(
            with_skills=with_report,
            without_skills=without_report,
        )

        suggestions = runner.analyze_for_improvements(comparison)

        # Should warn that skills didn't help
        assert any("WARNING" in s or "NOT" in s for s in suggestions)

    def test_analyze_identifies_weak_categories(self):
        """Test that analysis identifies weak categories."""
        from edgar.ai.evaluation.runner import SkillTestRunner

        runner = SkillTestRunner(api_key="test-key")

        # Create comparison with low scores
        samples = {"TC001": 'print("hello")'}  # Wrong patterns

        with_report = runner.harness.run_suite(samples, condition="with_skills")
        without_report = runner.harness.run_suite(samples, condition="without_skills")

        from edgar.ai.evaluation.harness import ABComparison
        comparison = ABComparison(
            with_skills=with_report,
            without_skills=without_report,
        )

        suggestions = runner.analyze_for_improvements(comparison)

        # Should have some suggestions
        assert len(suggestions) > 0


class TestRunnerCLI:
    """Test runner CLI interface."""

    def test_runner_cli_dry_run(self, capsys):
        """Test runner CLI dry run mode."""
        import sys
        from unittest.mock import patch

        from edgar.ai.evaluation.runner import main

        with patch.object(sys, "argv", ["runner", "--dry-run"]):
            main()

        captured = capsys.readouterr()
        assert "TC001" in captured.out
        assert "Model:" in captured.out
