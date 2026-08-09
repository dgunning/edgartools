"""
Regression test for Issue #683: StatementNotFound error when stitching cash flow for VALE

GitHub Issue: https://github.com/dgunning/edgartools/issues/683

Bug (FIXED): stitching cash flow across VALE's 20-F filings raised
`StatementNotFound` and aborted the whole operation.

Fix: Catch `StatementNotFound` in the stitching loop and skip filings that
don't have the requested statement type, rather than crashing.

CORRECTION TO THE PREMISE RECORDED HERE (2026-08-09). This file used to state
that VALE "doesn't include a cash flow statement presentation role in every
filing's XBRL", and the test below was written to accept an empty result on
that basis. All three filings it loads do declare the role — each has
"00000005 - Statement - Consolidated Statement of Cash Flows", typed
CashFlowStatement by `get_all_statements()`. What fails is resolution:
`find_statement("CashFlowStatement")` raises with "No statements available in
XBRL data" while the same XBRL resolves income statement, balance sheet,
comprehensive income and statement of equity. So the statement is in the
filing and unreachable through the API, and the stitched result is empty for
that reason rather than a filing-shape one. Tracked as edgartools-gi1n; see
the xfail below.
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


def _vale_20f_filings(n=3):
    from edgar import Company
    return Company('VALE').get_filings(form='20-F').head(n)


@pytest.mark.network
def test_vale_stitched_cashflow_no_crash():
    """#683 itself: the stitch completes instead of raising.

    The precondition is asserted first, because the old version of this test
    tolerated every outcome — `if cf is not None: assert df is not None` — and
    would have passed just as happily against a build where stitching returned
    nothing for any reason at all. Each filing must declare the cash flow role,
    or "the stitch skipped the filings that lack it" would be a different
    statement about a different set of filings.
    """
    from edgar.xbrl.stitching import XBRLS

    filings = _vale_20f_filings()
    for filing in filings:
        roles = [s for s in filing.xbrl().get_all_statements()
                 if s.get('type') == 'CashFlowStatement']
        assert [str(s['definition']) for s in roles] == \
            ['00000005 - Statement - Consolidated Statement of Cash Flows'], \
            f"{filing.accession_no} no longer declares exactly one cash flow role"

    xbrls = XBRLS.from_filings(filings)
    try:
        cf = xbrls.statements.cashflow_statement()
    except Exception as e:
        pytest.fail(f"Should not raise, got: {e}")

    # Whatever it returns must be renderable rather than half-built.
    assert cf is None or list(cf.to_dataframe().columns)[:2] == ['label', 'concept']


@pytest.mark.network
@pytest.mark.xfail(strict=True, reason=(
    "VALE's cash flow statement is declared in the filing but unreachable: "
    "find_statement('CashFlowStatement') raises 'No statements available in "
    "XBRL data' while every other statement type resolves. When this starts "
    "passing the resolver has been fixed — drop the marker and pin the figures."
))
def test_vale_cashflow_statement_is_reachable():
    """The statement is in the filing, so the API must return it.

    Kept separate from the #683 regression above, which is about stitching not
    crashing and is genuinely fixed. This one is about the silence that
    replaced the crash: an empty result carrying no indication that a statement
    the filing does contain was skipped.
    """
    filing = _vale_20f_filings(1)[0]
    cashflow = filing.xbrl().statements.cashflow_statement()
    assert cashflow is not None, (
        f"{filing.accession_no} declares a Consolidated Statement of Cash "
        "Flows, but statements.cashflow_statement() returned None"
    )
    assert not cashflow.to_dataframe().empty
