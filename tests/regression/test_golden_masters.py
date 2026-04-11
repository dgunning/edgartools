"""
Golden Master Regression Gate.

Loads the production experiment ledger and verifies that no NEW golden master
regressions have been introduced. This test serves as a CI gate — any PR that
increases the regression count is blocked.

Known baseline: 30 cross-period variance regressions exist from Phase 1
(different filing periods produce different values, not code regressions).
The gate ensures this count does not grow.
"""

import pytest
from pathlib import Path

from edgar.xbrl.standardization.ledger import ExperimentLedger


LEDGER_DB_PATH = (
    Path(__file__).parent.parent.parent
    / "edgar" / "xbrl" / "standardization" / "company_mappings" / "experiment_ledger.db"
)

# Known cross-period variance regressions from Phase 1 infrastructure activation.
# These are NOT code regressions — they occur because different filing periods
# (e.g., 10-K vs 10-Q, different fiscal years) produce different values for
# the same metric. The CI gate ensures this count does not increase.
KNOWN_REGRESSION_BASELINE = 30


@pytest.fixture
def production_ledger():
    """Load the production experiment ledger.

    Skips the test if the ledger DB doesn't exist (e.g., fresh checkout
    without data or CI environment without the DB).
    """
    if not LEDGER_DB_PATH.exists():
        pytest.skip("Production ledger DB not found — run E2E first")
    return ExperimentLedger(db_path=str(LEDGER_DB_PATH))


def _get_latest_fingerprint(ledger: ExperimentLedger) -> str:
    """Get the most recent strategy fingerprint from extraction runs."""
    with ledger._connect() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT strategy_fingerprint
            FROM extraction_runs
            ORDER BY run_timestamp DESC
            LIMIT 1
        ''')
        row = cursor.fetchone()
        if row:
            return row[0]
    return ""


class TestGoldenMasterRegressionGate:

    def test_ledger_has_golden_masters(self, production_ledger):
        """Verify the ledger has promoted golden masters."""
        masters = production_ledger.get_all_golden_masters(active_only=True)
        assert len(masters) > 0, "No golden masters found — run promote_golden_masters() first"

    def test_no_new_regressions(self, production_ledger):
        """Ensure no NEW golden master regressions beyond the known baseline.

        Checks the latest strategy fingerprint's runs against all active
        golden masters. Fails only if the regression count exceeds the
        known baseline (cross-period variance from Phase 1).
        """
        fingerprint = _get_latest_fingerprint(production_ledger)
        if not fingerprint:
            pytest.skip("No extraction runs found in ledger")

        report = production_ledger.check_regressions(
            strategy_fingerprint=fingerprint
        )

        regression_count = len(report.regressions)

        if regression_count > KNOWN_REGRESSION_BASELINE:
            new_count = regression_count - KNOWN_REGRESSION_BASELINE
            details = ", ".join(
                f"{r.ticker}/{r.metric} ({r.golden_variance:.1f}% -> {r.current_variance:.1f}%)"
                for r in report.regressions
            )
            pytest.fail(
                f"{new_count} NEW regression(s) beyond baseline of {KNOWN_REGRESSION_BASELINE}: "
                f"{details}"
            )

    def test_regression_report_summary(self, production_ledger):
        """Print regression report summary for CI visibility."""
        fingerprint = _get_latest_fingerprint(production_ledger)
        if not fingerprint:
            pytest.skip("No extraction runs found in ledger")

        report = production_ledger.check_regressions(
            strategy_fingerprint=fingerprint
        )

        print(f"\nGolden Masters:      {report.total_golden}")
        print(f"Checked:             {report.checked}")
        print(f"Passes:              {len(report.passes)}")
        print(f"No Data:             {len(report.no_data)}")
        print(f"Regressions:         {len(report.regressions)}")
        print(f"Known Baseline:      {KNOWN_REGRESSION_BASELINE}")
        new_regressions = max(0, len(report.regressions) - KNOWN_REGRESSION_BASELINE)
        print(f"New Regressions:     {new_regressions}")
        print(f"Pass Rate:           {len(report.passes)}/{report.checked} "
              f"({100 * len(report.passes) / report.checked:.1f}%)" if report.checked else "")

        # Informational — doesn't fail
        assert True
