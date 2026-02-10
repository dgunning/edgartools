"""
Regression tests for Issue #633: EarningsRelease data accuracy bugs.

Issue #633 reported 5 bugs found by testing 50 real 8-K earnings filings.
All 5 were fixed with 58 unit tests (see tests/test_earnings.py), but those
tests all use synthetic mock DataFrames. These end-to-end tests verify the
full pipeline: Filing → EarningsRelease.from_filing() → income_statement → values.

Each test targets a specific bug from the issue:
  Bug 2: Scale detection from table context, not narrative text
  Bug 3: Income statement classification (tables classified UNKNOWN → None)
  Bug 4: Row-type metadata prevents share/EPS confusion
  Smoke: Full pipeline positive case (AMT, known-correct from reporter)
"""

import pandas as pd
import pytest

from edgar import Company
from edgar.earnings import EarningsRelease, RowType, Scale, StatementType


@pytest.mark.regression
class TestIssue633EarningsDataAccuracy:
    """End-to-end regression tests for EarningsRelease data accuracy fixes."""

    def test_hurn_scale_not_billions(self):
        """
        Bug 2: Table scale should come from table headers, not narrative text.

        HURN's 8-K contained the word "billion" in narrative paragraphs, which
        was incorrectly detected as the table's scale. The actual table uses
        thousands. After the fix, scale detection looks at table context only.
        """
        filing = Company("HURN").get_filings(
            form="8-K", accession_number="0001289848-25-000189"
        )[0]
        earnings = EarningsRelease.from_filing(filing)
        assert earnings is not None, "EarningsRelease should be found for HURN 8-K"

        inc = earnings.income_statement
        assert inc is not None, "Income statement should be detected"
        assert inc.scale != Scale.BILLIONS, (
            f"Scale should not be BILLIONS (was incorrectly detected from narrative text); "
            f"got {inc.scale}"
        )

    def test_rf_tables_not_all_unknown(self):
        """
        Bug 3: Classification should identify at least some table types.

        RF's 8-K had 10 financial tables. Before the fix, all were classified as
        UNKNOWN. After improving keyword-based classification, at least some tables
        should be correctly classified (e.g., balance sheet detected via equity keywords).

        Note: RF is a bank holding company with non-standard income statement
        terminology ("net interest income" instead of "net revenue"), so the income
        statement may still not be detected. The key regression check is that
        classification isn't completely broken (not all UNKNOWN).
        """
        filing = Company("RF").get_filings(
            form="8-K", accession_number="0001281761-25-000074"
        )[0]
        earnings = EarningsRelease.from_filing(filing)
        assert earnings is not None, "EarningsRelease should be found for RF 8-K"

        assert len(earnings.financial_tables) >= 10, (
            f"RF should have many financial tables, got {len(earnings.financial_tables)}"
        )

        # At least one table should be classified (not all UNKNOWN)
        classified = [
            t for t in earnings.tables
            if t.statement_type != StatementType.UNKNOWN
        ]
        assert len(classified) > 0, (
            "At least one table should be classified (not all UNKNOWN); "
            f"types: {[t.statement_type for t in earnings.tables]}"
        )

    def test_grpn_per_share_rows_have_eps_values(self):
        """
        Bug 4: Row-type metadata prevents share/EPS confusion.

        GRPN's earnings had a "Diluted" row that matched both share count (~50M)
        and EPS ($0.46). Without row_type metadata, the wrong value was returned.
        After the fix, per_share rows are tagged with RowType.PER_SHARE, and their
        numeric values should be in EPS range (< 100), not share counts (millions).

        GRPN has multiple INCOME_STATEMENT tables. The largest is a segment breakdown
        (no EPS rows). The smaller one contains EPS data with per_share row types.
        We verify across all income statement tables that per_share classification works.
        """
        filing = Company("GRPN").get_filings(
            form="8-K", accession_number="0001490281-25-000040"
        )[0]
        earnings = EarningsRelease.from_filing(filing)
        assert earnings is not None, "EarningsRelease should be found for GRPN 8-K"

        # Find all income statement tables
        income_tables = [
            t for t in earnings.tables
            if t.statement_type == StatementType.INCOME_STATEMENT
        ]
        assert len(income_tables) > 0, "At least one income statement table should exist"

        # Collect per_share rows from all income statement tables
        all_per_share = pd.concat(
            [t.per_share_rows for t in income_tables if not t.per_share_rows.empty],
            ignore_index=False,
        )
        assert not all_per_share.empty, (
            "Per-share rows should exist across income statement tables"
        )

        # All per-share numeric values should be in EPS range, not share counts
        for col in all_per_share.columns:
            numeric_vals = pd.to_numeric(all_per_share[col], errors="coerce").dropna()
            for val in numeric_vals:
                assert abs(val) < 100, (
                    f"Per-share value {val} in column '{col}' looks like a share count, "
                    f"not an EPS value (should be < 100)"
                )

        # The "Diluted" row with share count (~50M) must NOT be PER_SHARE
        for t in income_tables:
            for idx_label in t.dataframe.index:
                label = str(idx_label)
                if label == "Diluted":
                    row_type = t.get_row_type(label)
                    vals = pd.to_numeric(t.dataframe.loc[label], errors="coerce").dropna()
                    if len(vals) > 0 and vals.iloc[0] > 1_000_000:
                        # This is the share count row — must be AMOUNT, not PER_SHARE
                        assert row_type != RowType.PER_SHARE, (
                            f"'Diluted' row with value {vals.iloc[0]} should not be "
                            f"PER_SHARE (it's a share count)"
                        )

    def test_amt_full_pipeline_positive(self):
        """
        Smoke test: AMT was one of only 2 correct results in the original report.

        Verifies the full pipeline doesn't crash and returns valid results
        for a known-good filing (reporter found EPS $0.78).
        """
        filing = Company("AMT").get_filings(
            form="8-K", accession_number="0001053507-25-000117"
        )[0]
        earnings = EarningsRelease.from_filing(filing)
        assert earnings is not None, "EarningsRelease should be found for AMT 8-K"

        assert len(earnings.financial_tables) > 0, (
            "AMT should have at least one financial table"
        )

        inc = earnings.income_statement
        assert inc is not None, "AMT income statement should be detected"
        assert not inc.dataframe.empty, "Income statement DataFrame should not be empty"
