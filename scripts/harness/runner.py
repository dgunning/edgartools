"""Test runner framework for executing tests on SEC filings."""

import time
import traceback
from typing import List, Callable, Optional, Dict, Any
from datetime import datetime

from tqdm import tqdm
from edgar import Filing

from .models import TestRun, TestResult
from .storage import HarnessStorage


class TestRunner:
    """Base test runner for harness.

    Provides common functionality for executing tests on filings:
    - Progress tracking with tqdm
    - Real-time result storage
    - Error handling and logging
    - Performance measurement
    """

    def __init__(self, storage: HarnessStorage):
        """Initialize test runner.

        Args:
            storage: HarnessStorage instance for persisting results
        """
        self.storage = storage

    def run_tests(
        self,
        run: TestRun,
        filings: List[Filing],
        test_func: Callable[[Filing], TestResult]
    ) -> List[TestResult]:
        """Execute tests on filings with progress tracking.

        Args:
            run: TestRun object defining the test run
            filings: List of Filing objects to test
            test_func: Function that takes a Filing and returns a TestResult

        Returns:
            List of TestResult objects
        """
        results = []

        with tqdm(total=len(filings), desc=f"Running {run.name}") as pbar:
            for filing in filings:
                try:
                    result = test_func(filing)
                    results.append(result)
                    self.storage.save_result(result)
                except Exception as e:
                    # Create error result
                    result = TestResult(
                        run_id=run.id,
                        filing_accession=filing.accession_no,
                        filing_form=filing.form,
                        filing_company=filing.company,
                        filing_date=filing.filing_date,
                        test_name=run.name,
                        status='error',
                        error_message=str(e),
                        details={'traceback': traceback.format_exc()}
                    )
                    results.append(result)
                    self.storage.save_result(result)
                finally:
                    pbar.update(1)

        return results


class ComparisonTestRunner(TestRunner):
    """Runs comparison tests between old and new implementations.

    Useful for validating that refactored code produces the same results
    as the original implementation.
    """

    def run(
        self,
        run: TestRun,
        filings: List[Filing],
        old_func: Callable[[Filing], Any],
        new_func: Callable[[Filing], Any],
        comparator: Optional[Callable[[Any, Any], bool]] = None
    ) -> List[TestResult]:
        """Run comparison tests.

        Args:
            run: TestRun object defining the test run
            filings: List of Filing objects to test
            old_func: Function representing old implementation
            new_func: Function representing new implementation
            comparator: Optional custom comparison function (default: ==)

        Returns:
            List of TestResult objects
        """
        if comparator is None:
            comparator = lambda a, b: a == b

        def compare_filing(filing: Filing) -> TestResult:
            start = time.time()

            try:
                # Run old implementation
                old_result = old_func(filing)

                # Run new implementation
                new_result = new_func(filing)

                # Compare results
                match = comparator(old_result, new_result)
                duration = (time.time() - start) * 1000

                return TestResult(
                    run_id=run.id,
                    filing_accession=filing.accession_no,
                    filing_form=filing.form,
                    filing_company=filing.company,
                    filing_date=filing.filing_date,
                    test_name=f'{run.name}_comparison',
                    status='pass' if match else 'fail',
                    duration_ms=duration,
                    details={
                        'old_result': str(old_result)[:500],  # Truncate for storage
                        'new_result': str(new_result)[:500],
                        'match': match
                    }
                )
            except Exception as e:
                duration = (time.time() - start) * 1000
                return TestResult(
                    run_id=run.id,
                    filing_accession=filing.accession_no,
                    filing_form=filing.form,
                    filing_company=filing.company,
                    filing_date=filing.filing_date,
                    test_name=f'{run.name}_comparison',
                    status='error',
                    duration_ms=duration,
                    error_message=str(e),
                    details={'traceback': traceback.format_exc()}
                )

        return self.run_tests(run, filings, compare_filing)


class ValidationTestRunner(TestRunner):
    """Runs validation tests to check data structure and quality.

    Executes multiple validation checks on each filing and aggregates
    the results.
    """

    def run(
        self,
        run: TestRun,
        filings: List[Filing],
        validators: List[Callable[[Filing], Dict[str, Any]]]
    ) -> List[TestResult]:
        """Run validation tests.

        Args:
            run: TestRun object defining the test run
            filings: List of Filing objects to test
            validators: List of validation functions that return
                       {'passed': bool, 'message': str, ...}

        Returns:
            List of TestResult objects
        """
        def validate_filing(filing: Filing) -> TestResult:
            start = time.time()
            all_passed = True
            validation_results = []

            try:
                # Run all validators
                for validator in validators:
                    try:
                        result = validator(filing)
                        validation_results.append(result)
                        if not result.get('passed', False):
                            all_passed = False
                    except Exception as e:
                        validation_results.append({
                            'passed': False,
                            'validator': validator.__name__,
                            'error': str(e)
                        })
                        all_passed = False

                duration = (time.time() - start) * 1000

                return TestResult(
                    run_id=run.id,
                    filing_accession=filing.accession_no,
                    filing_form=filing.form,
                    filing_company=filing.company,
                    filing_date=filing.filing_date,
                    test_name=f'{run.name}_validation',
                    status='pass' if all_passed else 'fail',
                    duration_ms=duration,
                    details={
                        'validators_run': len(validators),
                        'validators_passed': sum(1 for r in validation_results if r.get('passed', False)),
                        'results': validation_results
                    }
                )
            except Exception as e:
                duration = (time.time() - start) * 1000
                return TestResult(
                    run_id=run.id,
                    filing_accession=filing.accession_no,
                    filing_form=filing.form,
                    filing_company=filing.company,
                    filing_date=filing.filing_date,
                    test_name=f'{run.name}_validation',
                    status='error',
                    duration_ms=duration,
                    error_message=str(e),
                    details={'traceback': traceback.format_exc()}
                )

        return self.run_tests(run, filings, validate_filing)


class PerformanceTestRunner(TestRunner):
    """Runs performance benchmarks against thresholds.

    Measures execution time and memory usage, comparing against
    defined performance thresholds.
    """

    def run(
        self,
        run: TestRun,
        filings: List[Filing],
        test_func: Callable[[Filing], Any],
        thresholds: Optional[Dict[str, float]] = None
    ) -> List[TestResult]:
        """Run performance tests.

        Args:
            run: TestRun object defining the test run
            filings: List of Filing objects to test
            test_func: Function to benchmark
            thresholds: Optional dict with 'max_duration_ms' and other thresholds

        Returns:
            List of TestResult objects
        """
        if thresholds is None:
            thresholds = {'max_duration_ms': 5000}  # 5 seconds default

        def benchmark_filing(filing: Filing) -> TestResult:
            start = time.time()

            try:
                # Run the test function
                result = test_func(filing)
                duration = (time.time() - start) * 1000

                # Check against thresholds
                passed = True
                threshold_results = {}

                if 'max_duration_ms' in thresholds:
                    max_duration = thresholds['max_duration_ms']
                    threshold_results['duration_check'] = {
                        'threshold': max_duration,
                        'actual': duration,
                        'passed': duration <= max_duration
                    }
                    if duration > max_duration:
                        passed = False

                return TestResult(
                    run_id=run.id,
                    filing_accession=filing.accession_no,
                    filing_form=filing.form,
                    filing_company=filing.company,
                    filing_date=filing.filing_date,
                    test_name=f'{run.name}_performance',
                    status='pass' if passed else 'fail',
                    duration_ms=duration,
                    details={
                        'thresholds': thresholds,
                        'threshold_results': threshold_results,
                        'result_summary': str(result)[:200] if result else None
                    }
                )
            except Exception as e:
                duration = (time.time() - start) * 1000
                return TestResult(
                    run_id=run.id,
                    filing_accession=filing.accession_no,
                    filing_form=filing.form,
                    filing_company=filing.company,
                    filing_date=filing.filing_date,
                    test_name=f'{run.name}_performance',
                    status='error',
                    duration_ms=duration,
                    error_message=str(e),
                    details={'traceback': traceback.format_exc()}
                )

        return self.run_tests(run, filings, benchmark_filing)


class RegressionTestRunner(TestRunner):
    """Runs regression tests against known good results.

    Compares current output against previously stored baseline results
    to detect regressions.
    """

    def run(
        self,
        run: TestRun,
        filings: List[Filing],
        test_func: Callable[[Filing], Any],
        baseline_results: Optional[Dict[str, Any]] = None
    ) -> List[TestResult]:
        """Run regression tests.

        Args:
            run: TestRun object defining the test run
            filings: List of Filing objects to test
            test_func: Function to test
            baseline_results: Optional dict mapping accession_no to expected results

        Returns:
            List of TestResult objects
        """
        if baseline_results is None:
            baseline_results = {}

        def check_regression(filing: Filing) -> TestResult:
            start = time.time()

            try:
                # Run current implementation
                current_result = test_func(filing)
                duration = (time.time() - start) * 1000

                # Check against baseline if available
                accession = filing.accession_no
                if accession in baseline_results:
                    baseline = baseline_results[accession]
                    match = current_result == baseline
                    status = 'pass' if match else 'fail'
                    details = {
                        'has_baseline': True,
                        'baseline': str(baseline)[:500],
                        'current': str(current_result)[:500],
                        'match': match
                    }
                else:
                    # No baseline - just record current result
                    status = 'skip'
                    details = {
                        'has_baseline': False,
                        'current': str(current_result)[:500],
                        'note': 'No baseline available for comparison'
                    }

                return TestResult(
                    run_id=run.id,
                    filing_accession=filing.accession_no,
                    filing_form=filing.form,
                    filing_company=filing.company,
                    filing_date=filing.filing_date,
                    test_name=f'{run.name}_regression',
                    status=status,
                    duration_ms=duration,
                    details=details
                )
            except Exception as e:
                duration = (time.time() - start) * 1000
                return TestResult(
                    run_id=run.id,
                    filing_accession=filing.accession_no,
                    filing_form=filing.form,
                    filing_company=filing.company,
                    filing_date=filing.filing_date,
                    test_name=f'{run.name}_regression',
                    status='error',
                    duration_ms=duration,
                    error_message=str(e),
                    details={'traceback': traceback.format_exc()}
                )

        return self.run_tests(run, filings, check_regression)
