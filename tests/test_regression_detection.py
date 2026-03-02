"""
Tests for the Regression Detection System.

Covers:
- Golden master promotion (Stage 1)
- Regression detection (Stage 2)
- Cohort reactor from E2E results (Stage 3)

All tests use in-memory SQLite via ExperimentLedger(db_path=":memory:").
"""

import pytest
from edgar.xbrl.standardization.ledger import (
    ExperimentLedger,
    ExtractionRun,
    RegressionResult,
    RegressionReport,
)
from edgar.xbrl.standardization.reactor.cohort_reactor import (
    CohortReactor,
    CohortDefinition,
)


# =============================================================================
# HELPERS
# =============================================================================

def make_run(
    ticker="AAPL",
    metric="Revenue",
    fiscal_period="2024-FY",
    form_type="10-K",
    strategy_name="tree",
    strategy_fingerprint="fp_abc123",
    extracted_value=100.0,
    reference_value=100.0,
    is_valid=True,
    archetype="A",
):
    """Helper to create an ExtractionRun with sensible defaults."""
    run = ExtractionRun(
        ticker=ticker,
        metric=metric,
        fiscal_period=fiscal_period,
        form_type=form_type,
        archetype=archetype,
        strategy_name=strategy_name,
        strategy_fingerprint=strategy_fingerprint,
        extracted_value=extracted_value,
        reference_value=reference_value,
    )
    # Override is_valid if caller explicitly wants invalid with 0 variance
    if not is_valid and run.is_valid:
        run.is_valid = False
        run.variance_pct = 50.0  # Force invalid variance
    return run


def seed_valid_runs(ledger, ticker, metric, periods, strategy_name="tree", fingerprint="fp_abc123"):
    """Seed multiple valid runs for different fiscal periods."""
    for period in periods:
        run = make_run(
            ticker=ticker,
            metric=metric,
            fiscal_period=period,
            strategy_name=strategy_name,
            strategy_fingerprint=fingerprint,
            extracted_value=100.0,
            reference_value=100.0,
        )
        ledger.record_run(run)


# =============================================================================
# GOLDEN MASTER PROMOTION TESTS
# =============================================================================

class TestGoldenMasterPromotion:

    def test_promote_with_3_valid_periods(self):
        """3 valid periods for same (ticker, metric, strategy) -> promoted."""
        ledger = ExperimentLedger(db_path=":memory:")
        seed_valid_runs(ledger, "AAPL", "Revenue", ["2022-FY", "2023-FY", "2024-FY"])

        promoted = ledger.promote_golden_masters()

        assert len(promoted) == 1
        gm = promoted[0]
        assert gm.ticker == "AAPL"
        assert gm.metric == "Revenue"
        assert gm.validation_count == 3
        assert set(gm.validated_periods) == {"2022-FY", "2023-FY", "2024-FY"}

    def test_no_promote_with_2_periods(self):
        """2 valid periods -> not promoted (need 3)."""
        ledger = ExperimentLedger(db_path=":memory:")
        seed_valid_runs(ledger, "AAPL", "Revenue", ["2023-FY", "2024-FY"])

        promoted = ledger.promote_golden_masters()

        assert len(promoted) == 0

    def test_promote_idempotent(self):
        """Calling promote twice doesn't duplicate golden masters."""
        ledger = ExperimentLedger(db_path=":memory:")
        seed_valid_runs(ledger, "AAPL", "Revenue", ["2022-FY", "2023-FY", "2024-FY"])

        first = ledger.promote_golden_masters()
        second = ledger.promote_golden_masters()

        assert len(first) == 1
        assert len(second) == 1  # Same promotion, INSERT OR REPLACE

        # Only 1 golden master in DB
        all_gm = ledger.get_all_golden_masters()
        assert len(all_gm) == 1

    def test_promote_filters_by_fingerprint(self):
        """Only promotes runs matching the given fingerprint."""
        ledger = ExperimentLedger(db_path=":memory:")

        # 3 periods with fingerprint A
        seed_valid_runs(ledger, "AAPL", "Revenue", ["2022-FY", "2023-FY", "2024-FY"],
                        fingerprint="fp_aaa")
        # 3 periods with fingerprint B
        seed_valid_runs(ledger, "MSFT", "Revenue", ["2022-FY", "2023-FY", "2024-FY"],
                        fingerprint="fp_bbb")

        promoted = ledger.promote_golden_masters(strategy_fingerprint="fp_aaa")

        assert len(promoted) == 1
        assert promoted[0].ticker == "AAPL"

    def test_promote_ignores_invalid_runs(self):
        """Invalid runs don't count toward 3-period threshold."""
        ledger = ExperimentLedger(db_path=":memory:")

        # 2 valid + 1 invalid = only 2 qualifying periods
        seed_valid_runs(ledger, "AAPL", "Revenue", ["2022-FY", "2023-FY"])

        invalid_run = make_run(
            ticker="AAPL",
            metric="Revenue",
            fiscal_period="2024-FY",
            extracted_value=200.0,
            reference_value=100.0,  # 100% variance -> invalid
        )
        ledger.record_run(invalid_run)

        promoted = ledger.promote_golden_masters()

        assert len(promoted) == 0


# =============================================================================
# REGRESSION DETECTION TESTS
# =============================================================================

class TestRegressionDetection:

    def _setup_golden_master(self, ledger, ticker="AAPL", metric="Revenue"):
        """Seed runs + promote to get a golden master."""
        seed_valid_runs(ledger, ticker, metric, ["2022-FY", "2023-FY", "2024-FY"],
                        fingerprint="fp_old")
        ledger.promote_golden_masters(strategy_fingerprint="fp_old")

    def test_regression_detected(self):
        """Golden pass + new fail = REGRESSION."""
        ledger = ExperimentLedger(db_path=":memory:")
        self._setup_golden_master(ledger)

        # New run that fails
        new_run = make_run(
            strategy_fingerprint="fp_new",
            extracted_value=200.0,
            reference_value=100.0,
            is_valid=False,
        )
        ledger.record_run(new_run)

        report = ledger.check_regressions(strategy_fingerprint="fp_new")

        assert report.has_regressions
        assert len(report.regressions) == 1
        assert report.regressions[0].status == "REGRESSION"
        assert report.regressions[0].ticker == "AAPL"

    def test_no_regression(self):
        """Golden pass + new pass = PASS."""
        ledger = ExperimentLedger(db_path=":memory:")
        self._setup_golden_master(ledger)

        # New valid run
        new_run = make_run(
            strategy_fingerprint="fp_new",
            extracted_value=100.0,
            reference_value=100.0,
        )
        ledger.record_run(new_run)

        report = ledger.check_regressions(strategy_fingerprint="fp_new")

        assert not report.has_regressions
        assert len(report.passes) == 1
        assert report.passes[0].status == "PASS"

    def test_no_data_for_golden(self):
        """Golden exists, no new run = NO_DATA."""
        ledger = ExperimentLedger(db_path=":memory:")
        self._setup_golden_master(ledger)

        report = ledger.check_regressions(strategy_fingerprint="fp_new")

        assert not report.has_regressions
        assert len(report.no_data) == 1
        assert report.no_data[0].status == "NO_DATA"

    def test_empty_goldens(self):
        """No golden masters -> empty report."""
        ledger = ExperimentLedger(db_path=":memory:")

        report = ledger.check_regressions(strategy_fingerprint="fp_new")

        assert not report.has_regressions
        assert report.total_golden == 0
        assert report.checked == 0

    def test_exit_code(self):
        """exit_code: 0 for clean, 1 for regressions."""
        ledger = ExperimentLedger(db_path=":memory:")
        self._setup_golden_master(ledger)

        # Clean report (no new runs -> all NO_DATA)
        clean_report = ledger.check_regressions(strategy_fingerprint="fp_new")
        assert clean_report.exit_code == 0

        # Add a failing run
        failing_run = make_run(
            strategy_fingerprint="fp_new",
            extracted_value=200.0,
            reference_value=100.0,
            is_valid=False,
        )
        ledger.record_run(failing_run)

        regression_report = ledger.check_regressions(strategy_fingerprint="fp_new")
        assert regression_report.exit_code == 1


# =============================================================================
# COHORT REACTOR TESTS
# =============================================================================

class TestCohortFromE2EResults:

    def _make_reactor(self, ledger):
        """Create a CohortReactor with a test cohort."""
        reactor = CohortReactor(ledger=ledger, config_path=None)
        reactor.cohorts['TestCohort'] = CohortDefinition(
            name='TestCohort',
            members=['AAPL', 'MSFT'],
            archetype='A',
            metrics=['Revenue'],
        )
        return reactor

    def test_cohort_from_e2e_results(self):
        """Correctly classifies IMPROVED/NEUTRAL/REGRESSED."""
        ledger = ExperimentLedger(db_path=":memory:")

        # Seed baseline with old fingerprint — AAPL had 10% variance
        baseline_aapl = make_run(
            ticker="AAPL", metric="Revenue",
            strategy_fingerprint="fp_old",
            extracted_value=110.0, reference_value=100.0,
        )
        ledger.record_run(baseline_aapl)

        # MSFT had 15% variance
        baseline_msft = make_run(
            ticker="MSFT", metric="Revenue",
            strategy_fingerprint="fp_old",
            extracted_value=115.0, reference_value=100.0,
        )
        ledger.record_run(baseline_msft)

        reactor = self._make_reactor(ledger)

        # E2E results: AAPL improved (2% variance), MSFT worsened (25% variance)
        e2e_results = [
            {
                'ticker': 'AAPL',
                'ledger_runs': [
                    {'metric': 'Revenue', 'extracted_value': 102.0, 'reference_value': 100.0},
                ],
            },
            {
                'ticker': 'MSFT',
                'ledger_runs': [
                    {'metric': 'Revenue', 'extracted_value': 125.0, 'reference_value': 100.0},
                ],
            },
        ]

        summary = reactor.test_from_e2e_results(
            cohort_name='TestCohort',
            e2e_results=e2e_results,
            strategy_name='tree',
            strategy_fingerprint='fp_new',
        )

        # AAPL: 10% -> 2% = IMPROVED (delta -8%)
        aapl_result = next(r for r in summary.company_results if r.ticker == 'AAPL')
        assert aapl_result.impact == "IMPROVED"

        # MSFT: 15% -> 25% = REGRESSED (delta +10%)
        msft_result = next(r for r in summary.company_results if r.ticker == 'MSFT')
        assert msft_result.impact == "REGRESSED"

        assert summary.improved_count == 1
        assert summary.regressed_count == 1
        assert not summary.is_passing

    def test_cohort_records_to_ledger(self):
        """CohortTestResult written to DB."""
        ledger = ExperimentLedger(db_path=":memory:")
        reactor = self._make_reactor(ledger)

        e2e_results = [
            {
                'ticker': 'AAPL',
                'ledger_runs': [
                    {'metric': 'Revenue', 'extracted_value': 100.0, 'reference_value': 100.0},
                ],
            },
            {
                'ticker': 'MSFT',
                'ledger_runs': [
                    {'metric': 'Revenue', 'extracted_value': 100.0, 'reference_value': 100.0},
                ],
            },
        ]

        summary = reactor.test_from_e2e_results(
            cohort_name='TestCohort',
            e2e_results=e2e_results,
            strategy_name='tree',
            strategy_fingerprint='fp_new',
        )

        # Verify it was recorded in the ledger
        tests = ledger.get_cohort_tests('TestCohort')
        assert len(tests) == 1
        assert tests[0].cohort_name == 'TestCohort'

    def test_cohort_excludes_current_fingerprint_from_baseline(self):
        """Baseline lookup doesn't compare against itself."""
        ledger = ExperimentLedger(db_path=":memory:")

        # Record a run with the SAME fingerprint as the E2E
        same_fp_run = make_run(
            ticker="AAPL", metric="Revenue",
            strategy_fingerprint="fp_new",
            extracted_value=110.0, reference_value=100.0,
        )
        ledger.record_run(same_fp_run)

        # And one with a different fingerprint (true baseline)
        old_run = make_run(
            ticker="AAPL", metric="Revenue",
            strategy_fingerprint="fp_old",
            extracted_value=120.0, reference_value=100.0,
        )
        ledger.record_run(old_run)

        reactor = self._make_reactor(ledger)

        e2e_results = [
            {
                'ticker': 'AAPL',
                'ledger_runs': [
                    {'metric': 'Revenue', 'extracted_value': 105.0, 'reference_value': 100.0},
                ],
            },
            {
                'ticker': 'MSFT',
                'ledger_runs': [],
            },
        ]

        summary = reactor.test_from_e2e_results(
            cohort_name='TestCohort',
            e2e_results=e2e_results,
            strategy_name='tree',
            strategy_fingerprint='fp_new',
        )

        # Baseline should be from fp_old (20% variance), not fp_new (10% variance)
        aapl_result = next(r for r in summary.company_results if r.ticker == 'AAPL')
        assert aapl_result.baseline_variance == pytest.approx(20.0, abs=0.1)

    def test_cohort_with_no_baseline(self):
        """First run -> all NEUTRAL impacts (no baseline to compare against)."""
        ledger = ExperimentLedger(db_path=":memory:")
        reactor = self._make_reactor(ledger)

        e2e_results = [
            {
                'ticker': 'AAPL',
                'ledger_runs': [
                    {'metric': 'Revenue', 'extracted_value': 105.0, 'reference_value': 100.0},
                ],
            },
            {
                'ticker': 'MSFT',
                'ledger_runs': [
                    {'metric': 'Revenue', 'extracted_value': 110.0, 'reference_value': 100.0},
                ],
            },
        ]

        summary = reactor.test_from_e2e_results(
            cohort_name='TestCohort',
            e2e_results=e2e_results,
            strategy_name='tree',
            strategy_fingerprint='fp_new',
        )

        # No baseline -> NEUTRAL impact classification for all
        assert summary.neutral_count == 2
        assert summary.improved_count == 0
        assert summary.regressed_count == 0
        # Note: is_passing may be False because variance_delta > 0
        # (total_variance_after > 0 with no baseline). This is expected
        # for first runs — the cohort gate only fully passes when
        # there's a comparable baseline showing no regression.
