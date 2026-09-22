"""
Tests for Issue #669: to_dataframe() should apply preferred_sign by default.

The Rich rendering path already applied preferred_sign, but to_dataframe() returned
raw XBRL instance values by default (e.g., Interest Paid = +1,313M instead of -1,313M).

This fix:
1. Changes Statement.to_dataframe() default from presentation=False to presentation=True
2. Preserves preferred_sign through stitching so StitchedStatement.to_dataframe() also works
3. Adds BalanceSheet to _apply_presentation() for contra accounts (Treasury Stock)

GitHub Issue: https://github.com/dgunning/edgartools/issues/669
"""

import re

import pandas as pd
import pytest

from edgar import Company


# Period columns are "2023-12-31 (FY)" -- a date followed by the fiscal period.
#
# This used to anchor on `^\d{4}-\d{2}-\d{2}$`, an exact match against the bare
# date. When the " (FY)" suffix was added the pattern stopped matching anything,
# get_period_columns() returned [], and the two tests below skipped on "No
# period columns" in every run from then on. Nothing was verified and nothing
# said so (edgartools-07lk.24 finding 3). Match the date as a prefix so a later
# change to the suffix cannot silence these again.
PERIOD_COLUMN = re.compile(r'^\d{4}-\d{2}-\d{2}(\s|$)')


def get_period_columns(df):
    """Get period columns (a YYYY-MM-DD date, optionally suffixed) from DataFrame."""
    return [col for col in df.columns if PERIOD_COLUMN.match(str(col))]


@pytest.mark.network
class TestIssue669PreferredSignInDataFrame:
    """Verify that to_dataframe() applies preferred_sign by default."""

    @pytest.fixture(scope="class")
    def azn_filing(self):
        """AstraZeneca 2024 10-K filing (uses InterestPaidNet with preferred_sign=-1)."""
        return Company("AZN").get_filings(form="20-F", year=2024).latest()

    def test_default_applies_preferred_sign(self, azn_filing):
        """Default to_dataframe() should apply preferred_sign (negate raw values)."""
        xbrl = azn_filing.xbrl()
        cf = xbrl.statements.cashflow_statement()
        assert cf is not None, "AZN 20-F should have a cash flow statement"
        df_pres = cf.to_dataframe()  # presentation=True is default
        df_raw = cf.to_dataframe(presentation=False)

        assert 'preferred_sign' in df_pres.columns, (
            f"to_dataframe() should carry preferred_sign; got {list(df_pres.columns)}"
        )

        period_cols = get_period_columns(df_pres)
        assert period_cols, (
            f"no period column matched {PERIOD_COLUMN.pattern} in {list(df_pres.columns)}"
        )

        neg_mask = df_pres['preferred_sign'] == -1
        assert neg_mask.any(), "AZN's cash flow has rows with preferred_sign=-1"

        col = period_cols[0]
        pres_val = df_pres.loc[neg_mask, col].dropna()
        raw_val = df_raw.loc[neg_mask, col].dropna()
        assert not pres_val.empty and not raw_val.empty, (
            f"column {col} has no non-null values on preferred_sign=-1 rows"
        )

        # The key invariant: presentation flips the sign relative to raw, on
        # EVERY such row rather than just the first one the frame happens to
        # order first. 18 rows qualify on this filing.
        mismatched = [(p, r) for p, r in zip(pres_val, raw_val) if p != -r]
        assert not mismatched, (
            f"presentation=True should negate raw values for preferred_sign=-1. "
            f"{len(mismatched)} of {len(pres_val)} rows disagree, e.g. {mismatched[:3]}"
        )

    def test_presentation_false_returns_raw(self, azn_filing):
        """presentation=False should return unmodified XBRL instance values."""
        xbrl = azn_filing.xbrl()
        cf = xbrl.statements.cashflow_statement()
        assert cf is not None, "AZN 20-F should have a cash flow statement"
        df_pres = cf.to_dataframe(presentation=True)
        df_raw = cf.to_dataframe(presentation=False)

        assert 'preferred_sign' in df_pres.columns, (
            f"to_dataframe() should carry preferred_sign; got {list(df_pres.columns)}"
        )

        period_cols = get_period_columns(df_pres)
        assert period_cols, (
            f"no period column matched {PERIOD_COLUMN.pattern} in {list(df_pres.columns)}"
        )

        neg_mask = df_pres['preferred_sign'] == -1
        assert neg_mask.any(), "AZN's cash flow has rows with preferred_sign=-1"

        col = period_cols[0]
        pres_val = df_pres.loc[neg_mask, col].dropna()
        raw_val = df_raw.loc[neg_mask, col].dropna()
        assert not pres_val.empty and not raw_val.empty, (
            f"column {col} has no non-null values on preferred_sign=-1 rows"
        )

        # Raw and presentation differ on every qualifying row. A zero would be
        # its own negation and break this, but none of AZN's 18 are zero.
        same = [(p, r) for p, r in zip(pres_val, raw_val) if p == r]
        assert not same, (
            f"presentation=True and False should produce different values. "
            f"{len(same)} of {len(pres_val)} rows are identical, e.g. {same[:3]}"
        )


@pytest.mark.network
class TestIssue669StitchedPreferredSign:
    """Verify that stitched statements also apply preferred_sign."""

    def test_stitched_dataframe_has_preferred_sign(self):
        """StitchedStatement.to_dataframe() should include preferred_sign column."""
        company = Company("AAPL")
        financials = company.get_financials()
        assert financials is not None, "AAPL should have financials"
        cf = financials.cashflow_statement()
        assert cf is not None, "AAPL financials should have a cash flow statement"
        df = cf.to_dataframe()
        assert 'preferred_sign' in df.columns, "Stitched DataFrame should include preferred_sign column"

    def test_stitched_dataframe_applies_signs(self):
        """StitchedStatement.to_dataframe() should apply preferred_sign by default."""
        company = Company("AAPL")
        financials = company.get_financials()
        assert financials is not None, "AAPL should have financials"
        cf = financials.cashflow_statement()
        assert cf is not None, "AAPL financials should have a cash flow statement"

        df_pres = cf.to_dataframe(presentation=True)
        df_raw = cf.to_dataframe(presentation=False)

        # The whole comparison used to sit inside `if` guards, so any unmet
        # condition passed the test having asserted nothing at all -- not even a
        # skip to say so. Each condition is now its own assertion.
        assert 'preferred_sign' in df_pres.columns, (
            f"stitched to_dataframe() should carry preferred_sign; got {list(df_pres.columns)}"
        )
        period_cols = get_period_columns(df_pres)
        assert period_cols, (
            f"no period column matched {PERIOD_COLUMN.pattern} in {list(df_pres.columns)}"
        )
        neg_mask = df_pres['preferred_sign'] == -1
        assert neg_mask.any(), "AAPL's stitched cash flow has rows with preferred_sign=-1"

        col = period_cols[0]
        pres_val = df_pres.loc[neg_mask, col].dropna()
        raw_val = df_raw.loc[neg_mask, col].dropna()
        assert not pres_val.empty and not raw_val.empty, (
            f"column {col} has no non-null values on preferred_sign=-1 rows"
        )

        mismatched = [(p, r) for p, r in zip(pres_val, raw_val) if p != -r]
        assert not mismatched, (
            f"Stitched presentation values should be negated vs raw. "
            f"{len(mismatched)} of {len(pres_val)} rows disagree, e.g. {mismatched[:3]}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
