"""Each statement gets the period type it needs (GH #429).

WHAT #429 WAS. ``current_period`` handed every statement the same period, so a
balance sheet — a snapshot at a date — was rendered against a duration, and a
cash flow statement against an instant. A statement asked for the wrong period
type comes back empty or wrong, not loudly broken.

WHY THIS FILE LOOKS NEW. It is not. It was
``reproductions/xbrl-parsing/test_multiple_companies_429.py``, a 113-line
script that walked four companies inside ``try: ... except Exception``, built a
Rich table of the results, printed "✅ Fixed" or "❌ Issue" per row, and ended
in ``return success_count == total_count``. It carried ``@pytest.mark.regression``
so pytest collected it — and a test that returns instead of asserting always
passes, so the printed ❌ was never a failure. Nothing in the file asserted
anything at all (edgartools-8m2n).

It was printing a ❌ on every run, too. Its Tesla row failed, and the reason
was not #429: ``get_filings(form="10-K").latest()`` returns 10-K/A amendments
alongside originals, and Tesla's newest is an amendment carrying the cover page
and two certification exhibits — 37 facts, no financial statements, so every
statement lookup on it fails. The script reported that as a Tesla data problem.
Filtering to unamended 10-Ks is what makes the assertions below possible, and
it is the same trap that had ``test_mcp_fpi_support`` testing BioNTech
amendments.

GROUND TRUTH: a balance sheet is an instant; income and cash flow are
durations. That holds for every filer and every year, which is why it is
asserted directly rather than pinned to figures that move.
"""
import pytest

from edgar import Company

COMPANIES = ['AAPL', 'MSFT', 'GOOGL', 'TSLA']


def latest_original_10k(ticker):
    """The newest 10-K that is not an amendment.

    ``filings[0]`` is not "the latest 10-K": the form filter admits 10-K/A, and
    an amendment carries only the parts being amended.
    """
    filings = Company(ticker).get_filings(form="10-K")
    originals = [f for f in filings if f.form == "10-K"]
    assert originals, f"{ticker} has no unamended 10-K among {len(filings)} filings"
    return originals[0]


@pytest.mark.network
@pytest.mark.regression
@pytest.mark.parametrize("ticker", COMPANIES)
class TestCurrentPeriodStatementTypes:

    @pytest.fixture
    def current_period(self, ticker):
        return latest_original_10k(ticker).xbrl().current_period

    def test_balance_sheet_uses_an_instant(self, current_period, ticker):
        """The bug itself: a snapshot cannot be reported over a duration."""
        period = current_period._get_appropriate_period_for_statement('BalanceSheet')
        assert period.startswith('instant_'), (
            f"{ticker} balance sheet resolved to {period!r}; a balance sheet is "
            "a position at a date, and rendering it over a duration is #429"
        )

    @pytest.mark.parametrize("statement_type", ['IncomeStatement', 'CashFlowStatement'])
    def test_flow_statements_use_a_duration(self, current_period, ticker, statement_type):
        period = current_period._get_appropriate_period_for_statement(statement_type)
        assert period.startswith('duration_'), (
            f"{ticker} {statement_type} resolved to {period!r}; a flow is "
            "measured over a period, not at an instant"
        )

    def test_all_three_statements_render_rows(self, current_period, ticker):
        """The period type being right is worth nothing if nothing renders.

        The floor is the script's own threshold (>10 rows). Exact counts move
        with each filing — these four ran 19-38 rows when this was written — so
        the assertion is that a real statement came back, not its size.
        """
        for name in ('balance_sheet', 'income_statement', 'cashflow_statement'):
            statement = getattr(current_period, name)()
            assert statement is not None, f"{ticker} {name}() returned None"
            rows = len(statement.get_dataframe())
            assert rows > 10, (
                f"{ticker} {name} rendered {rows} rows; a 10-K statement with "
                "ten or fewer lines means the period selection found almost no facts"
            )
