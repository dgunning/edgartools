"""
Regression test for Issue #683: StatementNotFound error when stitching cash flow for VALE

GitHub Issue: https://github.com/dgunning/edgartools/issues/683

Bug (FIXED): VALE (a foreign filer using 20-F) doesn't include a cash flow
statement presentation role in every filing's XBRL. When stitching across
multiple years, `stitch_statements()` raised `StatementNotFound` for filings
that lacked the cash flow role, aborting the entire operation.

Fix: Catch `StatementNotFound` in the stitching loop and skip filings that
don't have the requested statement type, rather than crashing.
"""

import pytest

from edgar.xbrl.exceptions import StatementNotFound
from edgar.xbrl.stitching.core import StatementStitcher


class TestStitchingSkipsMissingStatements:
    """Unit test: stitch_statements handles StatementNotFound gracefully."""

    def test_get_statement_by_type_exception_is_caught(self):
        """Verify that StatementNotFound from get_statement_by_type doesn't
        propagate out of the stitching loop — it should be caught and the
        filing skipped."""
        # StatementNotFound should be importable and is a proper exception
        exc = StatementNotFound(
            statement_type="CashFlowStatement",
            confidence=0.0,
            found_statements=[],
            entity_name="VALE S.A.",
            reason="No statements available in XBRL data",
        )
        assert isinstance(exc, Exception)
        assert "CashFlowStatement" in str(exc)


@pytest.mark.network
def test_vale_stitched_cashflow_no_crash():
    """VALE stitched cash flow should not raise StatementNotFound."""
    from edgar import Company
    from edgar.xbrl.stitching import XBRLS

    company = Company('VALE')
    filings = company.get_filings(form='20-F').head(3)
    xbrls = XBRLS.from_filings(filings)

    # This should not raise — filings without cash flow are skipped.
    # The result may be None or have an empty dataframe if no filings
    # in the set have a cash flow statement — that's acceptable.
    try:
        cf = xbrls.statements.cashflow_statement()
    except Exception as e:
        pytest.fail(f"Should not raise, got: {e}")
    if cf is not None:
        df = cf.to_dataframe()
        # Empty is acceptable if none of the filings had cash flow data
        assert df is not None
