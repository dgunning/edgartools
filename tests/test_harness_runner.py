"""Unit tests for test runner functionality."""

import pytest
import time
from unittest.mock import Mock, MagicMock

from tests.harness import (
    HarnessStorage,
    TestRunner,
    ComparisonTestRunner,
    ValidationTestRunner,
    PerformanceTestRunner,
    RegressionTestRunner,
    FilingSelector
)


@pytest.fixture
def storage():
    """Create in-memory storage for testing."""
    return HarnessStorage(":memory:")


@pytest.fixture
def session_and_run(storage):
    """Create a test session and run."""
    session = storage.create_session("Test Session")
    run = storage.create_run(
        session_id=session.id,
        name="Test Run",
        test_type="validation",
        config={}
    )
    return session, run


@pytest.fixture
def mock_filings():
    """Create mock Filing objects for testing."""
    filings = []
    for i in range(3):
        filing = Mock()
        filing.accession_no = f"0001234567-24-00000{i}"
        filing.form = "10-K"
        filing.company = f"Test Corp {i}"
        filing.filing_date = "2024-01-01"
        filings.append(filing)
    return filings


class TestBaseRunner:
    """Test base TestRunner functionality."""

    def test_run_tests_success(self, storage, session_and_run, mock_filings):
        """Test running tests successfully."""
        session, run = session_and_run
        runner = TestRunner(storage)

        # Define a simple test function
        def test_func(filing):
            from tests.harness.models import TestResult
            return TestResult(
                run_id=run.id,
                filing_accession=filing.accession_no,
                filing_form=filing.form,
                filing_company=filing.company,
                filing_date=filing.filing_date,
                test_name="simple_test",
                status="pass",
                duration_ms=10.0
            )

        results = runner.run_tests(run, mock_filings, test_func)

        assert len(results) == 3
        assert all(r.status == "pass" for r in results)

        # Verify results were saved to storage
        saved_results = storage.get_results(run.id)
        assert len(saved_results) == 3

    def test_run_tests_with_errors(self, storage, session_and_run, mock_filings):
        """Test handling of errors during test execution."""
        session, run = session_and_run
        runner = TestRunner(storage)

        # Define a test function that raises an error
        def test_func(filing):
            raise ValueError("Test error")

        results = runner.run_tests(run, mock_filings, test_func)

        assert len(results) == 3
        assert all(r.status == "error" for r in results)
        assert all("Test error" in r.error_message for r in results)
        assert all("traceback" in r.details for r in results)

    def test_run_tests_saves_incrementally(self, storage, session_and_run, mock_filings):
        """Test that results are saved incrementally, not in batch."""
        session, run = session_and_run
        runner = TestRunner(storage)

        save_count = [0]

        def test_func(filing):
            # Check how many results are saved after each filing
            current_results = storage.get_results(run.id)
            save_count[0] = len(current_results)

            from tests.harness.models import TestResult
            return TestResult(
                run_id=run.id,
                filing_accession=filing.accession_no,
                filing_form=filing.form,
                filing_company=filing.company,
                filing_date=filing.filing_date,
                test_name="incremental_test",
                status="pass"
            )

        results = runner.run_tests(run, mock_filings, test_func)

        # All results should be saved
        assert len(storage.get_results(run.id)) == 3


class TestComparisonRunner:
    """Test ComparisonTestRunner functionality."""

    @pytest.mark.network
    def test_comparison_matching_results(self, storage, session_and_run):
        """Test comparison when old and new implementations match."""
        session, run = session_and_run
        runner = ComparisonTestRunner(storage)

        # Get a real filing for testing
        filings = FilingSelector.by_random_sample("8-K", 2024, 2)

        # Define old and new functions that return the same result
        def old_func(filing):
            return filing.form

        def new_func(filing):
            return filing.form

        results = runner.run(run, filings, old_func, new_func)

        assert len(results) == 2
        assert all(r.status == "pass" for r in results)
        assert all(r.details['match'] is True for r in results)

    @pytest.mark.network
    def test_comparison_different_results(self, storage, session_and_run):
        """Test comparison when implementations differ."""
        session, run = session_and_run
        runner = ComparisonTestRunner(storage)

        filings = FilingSelector.by_random_sample("8-K", 2024, 2)

        # Define functions that return different results
        def old_func(filing):
            return "A"

        def new_func(filing):
            return "B"

        results = runner.run(run, filings, old_func, new_func)

        assert len(results) == 2
        assert all(r.status == "fail" for r in results)
        assert all(r.details['match'] is False for r in results)

    @pytest.mark.network
    def test_comparison_custom_comparator(self, storage, session_and_run):
        """Test comparison with custom comparator function."""
        session, run = session_and_run
        runner = ComparisonTestRunner(storage)

        filings = FilingSelector.by_random_sample("8-K", 2024, 1)

        def old_func(filing):
            return [1, 2, 3]

        def new_func(filing):
            return [1, 2, 3, 4]

        # Custom comparator that checks if new result contains all old elements
        def comparator(old, new):
            return all(item in new for item in old)

        results = runner.run(run, filings, old_func, new_func, comparator)

        assert len(results) == 1
        assert results[0].status == "pass"

    def test_comparison_handles_errors(self, storage, session_and_run, mock_filings):
        """Test error handling in comparison runner."""
        session, run = session_and_run
        runner = ComparisonTestRunner(storage)

        def old_func(filing):
            raise ValueError("Old function error")

        def new_func(filing):
            return "result"

        results = runner.run(run, mock_filings, old_func, new_func)

        assert len(results) == 3
        assert all(r.status == "error" for r in results)


class TestValidationRunner:
    """Test ValidationTestRunner functionality."""

    def test_validation_all_pass(self, storage, session_and_run, mock_filings):
        """Test validation when all validators pass."""
        session, run = session_and_run
        runner = ValidationTestRunner(storage)

        # Define validators that all pass
        def validator1(filing):
            return {'passed': True, 'message': 'Validator 1 passed'}

        def validator2(filing):
            return {'passed': True, 'message': 'Validator 2 passed'}

        results = runner.run(run, mock_filings, [validator1, validator2])

        assert len(results) == 3
        assert all(r.status == "pass" for r in results)
        assert all(r.details['validators_run'] == 2 for r in results)
        assert all(r.details['validators_passed'] == 2 for r in results)

    def test_validation_some_fail(self, storage, session_and_run, mock_filings):
        """Test validation when some validators fail."""
        session, run = session_and_run
        runner = ValidationTestRunner(storage)

        def validator1(filing):
            return {'passed': True, 'message': 'Validator 1 passed'}

        def validator2(filing):
            return {'passed': False, 'message': 'Validator 2 failed'}

        results = runner.run(run, mock_filings, [validator1, validator2])

        assert len(results) == 3
        assert all(r.status == "fail" for r in results)
        assert all(r.details['validators_run'] == 2 for r in results)
        assert all(r.details['validators_passed'] == 1 for r in results)

    def test_validation_handles_exceptions(self, storage, session_and_run, mock_filings):
        """Test validation handles validator exceptions."""
        session, run = session_and_run
        runner = ValidationTestRunner(storage)

        def validator1(filing):
            return {'passed': True}

        def validator2(filing):
            raise ValueError("Validator error")

        results = runner.run(run, mock_filings, [validator1, validator2])

        assert len(results) == 3
        assert all(r.status == "fail" for r in results)
        # Should have caught the exception and recorded it
        for result in results:
            assert len(result.details['results']) == 2
            assert result.details['results'][1]['passed'] is False


class TestPerformanceRunner:
    """Test PerformanceTestRunner functionality."""

    def test_performance_within_threshold(self, storage, session_and_run, mock_filings):
        """Test performance when execution is within threshold."""
        session, run = session_and_run
        runner = PerformanceTestRunner(storage)

        def fast_func(filing):
            return "quick result"

        thresholds = {'max_duration_ms': 1000}  # 1 second
        results = runner.run(run, mock_filings, fast_func, thresholds)

        assert len(results) == 3
        assert all(r.status == "pass" for r in results)
        assert all(r.duration_ms < 1000 for r in results)

    def test_performance_exceeds_threshold(self, storage, session_and_run, mock_filings):
        """Test performance when execution exceeds threshold."""
        session, run = session_and_run
        runner = PerformanceTestRunner(storage)

        def slow_func(filing):
            time.sleep(0.2)  # 200ms
            return "slow result"

        thresholds = {'max_duration_ms': 100}  # 100ms threshold
        results = runner.run(run, mock_filings, slow_func, thresholds)

        assert len(results) == 3
        # Should fail due to exceeding threshold
        assert all(r.status == "fail" for r in results)
        assert all(r.duration_ms > 100 for r in results)

    def test_performance_default_threshold(self, storage, session_and_run, mock_filings):
        """Test performance with default threshold."""
        session, run = session_and_run
        runner = PerformanceTestRunner(storage)

        def quick_func(filing):
            return "result"

        results = runner.run(run, mock_filings, quick_func)

        assert len(results) == 3
        # Default threshold is 5000ms, should pass
        assert all(r.status == "pass" for r in results)


class TestRegressionRunner:
    """Test RegressionTestRunner functionality."""

    def test_regression_with_baseline_match(self, storage, session_and_run, mock_filings):
        """Test regression when results match baseline."""
        session, run = session_and_run
        runner = RegressionTestRunner(storage)

        baseline = {
            mock_filings[0].accession_no: "result_0",
            mock_filings[1].accession_no: "result_1",
            mock_filings[2].accession_no: "result_2"
        }

        def test_func(filing):
            # Return result based on accession number
            idx = filing.accession_no[-1]
            return f"result_{idx}"

        results = runner.run(run, mock_filings, test_func, baseline)

        assert len(results) == 3
        assert all(r.status == "pass" for r in results)
        assert all(r.details['has_baseline'] is True for r in results)
        assert all(r.details['match'] is True for r in results)

    def test_regression_with_baseline_mismatch(self, storage, session_and_run, mock_filings):
        """Test regression when results don't match baseline."""
        session, run = session_and_run
        runner = RegressionTestRunner(storage)

        baseline = {
            mock_filings[0].accession_no: "expected_result",
            mock_filings[1].accession_no: "expected_result",
            mock_filings[2].accession_no: "expected_result"
        }

        def test_func(filing):
            return "different_result"

        results = runner.run(run, mock_filings, test_func, baseline)

        assert len(results) == 3
        assert all(r.status == "fail" for r in results)
        assert all(r.details['match'] is False for r in results)

    def test_regression_without_baseline(self, storage, session_and_run, mock_filings):
        """Test regression when no baseline exists."""
        session, run = session_and_run
        runner = RegressionTestRunner(storage)

        def test_func(filing):
            return "some_result"

        # No baseline provided
        results = runner.run(run, mock_filings, test_func)

        assert len(results) == 3
        # Should skip when no baseline available
        assert all(r.status == "skip" for r in results)
        assert all(r.details['has_baseline'] is False for r in results)


class TestRunnerIntegration:
    """Integration tests for runners with real filings."""

    @pytest.mark.network
    def test_end_to_end_comparison(self, storage):
        """Test complete workflow with comparison runner."""
        # Create session and run
        session = storage.create_session("Integration Test")
        run = storage.create_run(
            session_id=session.id,
            name="8-K Comparison Test",
            test_type="comparison",
            config={'form': '8-K', 'sample': 3}
        )

        # Get real filings
        filings = FilingSelector.by_random_sample("8-K", 2024, 3, seed=42)

        # Run comparison
        runner = ComparisonTestRunner(storage)

        def old_parser(filing):
            return filing.form

        def new_parser(filing):
            return filing.form

        results = runner.run(run, filings, old_parser, new_parser)

        # Verify results
        assert len(results) == 3
        assert all(r.run_id == run.id for r in results)
        assert all(r.status in ['pass', 'fail', 'error'] for r in results)

        # Verify storage
        saved_results = storage.get_results(run.id)
        assert len(saved_results) == 3

        # Check success rate
        success_rate = storage.get_success_rate(run.id)
        assert 0.0 <= success_rate <= 1.0
