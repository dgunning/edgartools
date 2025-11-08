"""Unit tests for reporting and analytics functionality."""

import pytest
import json
import csv
from pathlib import Path
from datetime import datetime, timedelta

from tests.harness import (
    HarnessStorage,
    ResultReporter,
    TrendAnalyzer,
    TestResult
)


@pytest.fixture
def storage():
    """Create in-memory storage for testing."""
    return HarnessStorage(":memory:")


@pytest.fixture
def populated_storage(storage):
    """Create storage with sample data."""
    # Create session
    session = storage.create_session("Test Session")

    # Create run
    run = storage.create_run(
        session_id=session.id,
        name="Test Run",
        test_type="validation",
        config={'form': '10-K', 'sample': 10}
    )

    # Create test results
    results = [
        TestResult(
            run_id=run.id,
            filing_accession=f"0001234567-24-00000{i}",
            filing_form="10-K",
            filing_company=f"Company {i}",
            filing_date="2024-01-01",
            test_name="validation_test",
            status="pass" if i < 7 else "fail",
            duration_ms=100.0 + i * 10
        )
        for i in range(10)
    ]

    for result in results:
        storage.save_result(result)

    return storage, run.id


class TestResultReporter:
    """Test ResultReporter functionality."""

    def test_generate_summary(self, populated_storage):
        """Test summary generation."""
        storage, run_id = populated_storage
        reporter = ResultReporter(storage)

        summary = reporter.generate_summary(run_id)

        assert summary['total'] == 10
        assert summary['passed'] == 7
        assert summary['failed'] == 3
        assert summary['errors'] == 0
        assert summary['success_rate'] == 0.7
        assert summary['avg_duration_ms'] > 0

    def test_generate_summary_empty_run(self, storage):
        """Test summary with no results."""
        session = storage.create_session("Empty Session")
        run = storage.create_run(session.id, "Empty Run", "validation", {})

        reporter = ResultReporter(storage)
        summary = reporter.generate_summary(run.id)

        assert summary['total'] == 0
        assert summary['success_rate'] == 0.0

    def test_export_csv(self, populated_storage, tmp_path):
        """Test CSV export."""
        storage, run_id = populated_storage
        reporter = ResultReporter(storage)

        output_file = tmp_path / "results.csv"
        reporter.export_csv(run_id, output_file)

        assert output_file.exists()

        # Verify CSV content
        with open(output_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 10
        assert 'accession' in rows[0]
        assert 'company' in rows[0]
        assert 'status' in rows[0]

    def test_export_json(self, populated_storage, tmp_path):
        """Test JSON export."""
        storage, run_id = populated_storage
        reporter = ResultReporter(storage)

        output_file = tmp_path / "results.json"
        reporter.export_json(run_id, output_file)

        assert output_file.exists()

        # Verify JSON content
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert 'run' in data
        assert 'summary' in data
        assert 'results' in data
        assert len(data['results']) == 10
        assert data['summary']['total'] == 10

    def test_export_json_with_details(self, populated_storage, tmp_path):
        """Test JSON export with detailed data."""
        storage, run_id = populated_storage
        reporter = ResultReporter(storage)

        output_file = tmp_path / "results_detailed.json"
        reporter.export_json(run_id, output_file, include_details=True)

        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Check that details are included
        assert 'details' in data['results'][0]

    def test_generate_markdown_report(self, populated_storage, tmp_path):
        """Test markdown report generation."""
        storage, run_id = populated_storage
        reporter = ResultReporter(storage)

        output_file = tmp_path / "report.md"
        reporter.generate_markdown_report(run_id, output_file)

        assert output_file.exists()

        # Verify markdown content
        content = output_file.read_text()

        assert "# Test Report:" in content
        assert "## Summary" in content
        assert "Total Tests" in content
        assert "Passed" in content
        assert "## Results by Status" in content

    def test_generate_form_breakdown(self, storage):
        """Test form breakdown generation."""
        session = storage.create_session("Test Session")
        run = storage.create_run(session.id, "Test Run", "validation", {})

        # Create results for different forms
        forms = ['10-K', '10-K', '10-K', '10-Q', '10-Q', '8-K']
        for i, form in enumerate(forms):
            result = TestResult(
                run_id=run.id,
                filing_accession=f"000123456-24-00000{i}",
                filing_form=form,
                filing_company=f"Company {i}",
                filing_date="2024-01-01",
                test_name="test",
                status="pass" if i % 2 == 0 else "fail",
                duration_ms=100.0
            )
            storage.save_result(result)

        reporter = ResultReporter(storage)
        breakdown = reporter.generate_form_breakdown(run.id)

        assert '10-K' in breakdown
        assert '10-Q' in breakdown
        assert '8-K' in breakdown

        assert breakdown['10-K']['total'] == 3
        assert breakdown['10-Q']['total'] == 2
        assert breakdown['8-K']['total'] == 1


class TestTrendAnalyzer:
    """Test TrendAnalyzer functionality."""

    def create_trend_data(self, storage, test_name, success_rates):
        """Helper to create trend data."""
        session = storage.create_session("Trend Session")

        for i, rate in enumerate(success_rates):
            run = storage.create_run(
                session.id,
                f"Run {i}",
                "validation",
                {}
            )

            # Create results matching the success rate
            total = 10
            passed = int(total * rate)
            failed = total - passed

            for j in range(passed):
                storage.save_result(TestResult(
                    run_id=run.id,
                    filing_accession=f"pass-{i}-{j}",
                    filing_form="10-K",
                    filing_company="Test",
                    filing_date="2024-01-01",
                    test_name=test_name,
                    status="pass",
                    duration_ms=100.0
                ))

            for j in range(failed):
                storage.save_result(TestResult(
                    run_id=run.id,
                    filing_accession=f"fail-{i}-{j}",
                    filing_form="10-K",
                    filing_company="Test",
                    filing_date="2024-01-01",
                    test_name=test_name,
                    status="fail",
                    duration_ms=100.0
                ))

    def test_detect_regressions(self, storage):
        """Test regression detection."""
        # Create trend: 100% -> 90% -> 70% (regressions)
        self.create_trend_data(storage, "regression_test", [1.0, 0.9, 0.7])

        analyzer = TrendAnalyzer(storage)
        regressions = analyzer.detect_regressions("regression_test", threshold=0.05)

        # Should detect 2 regressions
        assert len(regressions) >= 1
        assert all('severity' in r for r in regressions)
        assert all('drop' in r for r in regressions)

    def test_detect_improvements(self, storage):
        """Test improvement detection."""
        # Create trend: 60% -> 80% -> 90% (improvements)
        self.create_trend_data(storage, "improvement_test", [0.6, 0.8, 0.9])

        analyzer = TrendAnalyzer(storage)
        improvements = analyzer.detect_improvements("improvement_test", threshold=0.05)

        # Should detect 2 improvements
        assert len(improvements) >= 1
        assert all('improvement' in i for i in improvements)

    def test_analyze_stability_stable(self, storage):
        """Test stability analysis for stable tests."""
        # Create stable trend: 90% -> 90% -> 90% -> 90%
        self.create_trend_data(storage, "stable_test", [0.9, 0.9, 0.9, 0.9])

        analyzer = TrendAnalyzer(storage)
        stability = analyzer.analyze_stability("stable_test")

        assert stability['stable'] is True
        assert stability['variance'] < 0.01
        assert stability['trend'] in ['stable', 'improving', 'degrading']

    def test_analyze_stability_unstable(self, storage):
        """Test stability analysis for unstable tests."""
        # Create unstable trend: 50% -> 90% -> 60% -> 95%
        self.create_trend_data(storage, "unstable_test", [0.5, 0.9, 0.6, 0.95])

        analyzer = TrendAnalyzer(storage)
        stability = analyzer.analyze_stability("unstable_test")

        assert stability['stable'] is False
        assert stability['variance'] > 0.01

    def test_analyze_stability_insufficient_data(self, storage):
        """Test stability analysis with insufficient data."""
        analyzer = TrendAnalyzer(storage)
        stability = analyzer.analyze_stability("nonexistent_test")

        assert stability['trend'] == 'insufficient_data'
        assert stability['data_points'] == 0

    def test_compare_periods(self, storage):
        """Test period comparison."""
        # Create trend showing improvement over time
        # Older: 60%, 65%, 70%
        # Recent: 85%, 90%, 90%
        self.create_trend_data(
            storage,
            "period_test",
            [0.6, 0.65, 0.7, 0.85, 0.9, 0.9]  # Oldest to newest (created in time order)
        )

        analyzer = TrendAnalyzer(storage)
        comparison = analyzer.compare_periods("period_test", period1_runs=3, period2_runs=3)

        assert comparison['period1_avg'] > comparison['period2_avg']
        assert comparison['comparison'] in ['improved', 'stable', 'degraded']
        assert comparison['change'] > 0  # Improvement

    def test_severity_classification(self, storage):
        """Test regression severity classification."""
        analyzer = TrendAnalyzer(storage)

        assert analyzer._classify_severity(0.25) == 'critical'
        assert analyzer._classify_severity(0.15) == 'high'
        assert analyzer._classify_severity(0.07) == 'medium'
        assert analyzer._classify_severity(0.03) == 'low'


class TestReporterIntegration:
    """Integration tests for reporters."""

    @pytest.mark.network
    def test_full_workflow(self, storage, tmp_path):
        """Test complete reporting workflow."""
        from tests.harness import FilingSelector, ValidationTestRunner

        # Create session and run
        session = storage.create_session("Integration Test")
        run = storage.create_run(
            session.id,
            "10-K Validation",
            "validation",
            {'form': '10-K', 'sample': 3}
        )

        # Get filings and run tests
        filings = FilingSelector.by_random_sample("10-K", 2024, 3, seed=42)
        runner = ValidationTestRunner(storage)

        validators = [
            lambda f: {'passed': f.form == '10-K', 'message': 'Form check'},
            lambda f: {'passed': len(f.company) > 0, 'message': 'Company check'}
        ]

        runner.run(run, filings, validators)

        # Generate all report types
        reporter = ResultReporter(storage)

        # CSV
        csv_file = tmp_path / "results.csv"
        reporter.export_csv(run.id, csv_file)
        assert csv_file.exists()

        # JSON
        json_file = tmp_path / "results.json"
        reporter.export_json(run.id, json_file)
        assert json_file.exists()

        # Markdown
        md_file = tmp_path / "report.md"
        reporter.generate_markdown_report(run.id, md_file)
        assert md_file.exists()

        # Summary
        summary = reporter.generate_summary(run.id)
        assert summary['total'] == 3

        # Form breakdown
        breakdown = reporter.generate_form_breakdown(run.id)
        assert '10-K' in breakdown
