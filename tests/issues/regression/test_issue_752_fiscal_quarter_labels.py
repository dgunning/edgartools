"""Regression test for GitHub issues #752 and #753.

#752: Quarter labels used hardcoded calendar-month ranges instead of the
company's fiscal year end month, producing wrong Q labels for companies
with non-calendar fiscal years (e.g. AAPL FY ends September showed Q2
instead of Q3 for a June period).

#753: to_dataframe() only added (Qn)/(YTD)/(FY) suffixes when end dates
collided. Q1 filings (where quarterly = YTD) got no suffix at all.
Now all duration periods consistently get period-type suffixes.
"""
import pytest
from edgar import Filing


def _date_cols(df):
    """Extract columns that look like date strings (YYYY-...)."""
    return [c for c in df.columns if c[:4].isdigit()]


@pytest.mark.network
class TestFiscalQuarterLabels:
    """Quarter labels must respect fiscal year end month, not calendar months."""

    def test_aapl_q3_filing_shows_q3_not_q2(self):
        """AAPL FY ends Sep. A Jun-period 10-Q should label as Q3, not Q2."""
        # AAPL Q3 FY2025 10-Q filed 2025-08-01
        filing = Filing(form='10-Q', filing_date='2025-08-01', company='Apple Inc.',
                        cik=320193, accession_no='0000320193-25-000073')
        stmt = filing.xbrl().statements.income_statement()
        df = stmt.to_dataframe()
        q_cols = [c for c in df.columns if '(Q3)' in c]
        assert len(q_cols) >= 1, f"Expected Q3 column for AAPL Jun period, got columns: {_date_cols(df)}"

    def test_aapl_q1_filing_has_q1_suffix(self):
        """Q1 filings should get (Q1) suffix even without end-date collisions."""
        # AAPL Q1 FY2026 10-Q filed 2026-01-30
        filing = Filing(form='10-Q', filing_date='2026-01-30', company='Apple Inc.',
                        cik=320193, accession_no='0000320193-26-000006')
        stmt = filing.xbrl().statements.income_statement()
        df = stmt.to_dataframe()
        q1_cols = [c for c in df.columns if '(Q1)' in c]
        assert len(q1_cols) >= 1, f"Expected Q1 suffix on columns, got: {_date_cols(df)}"

    def test_annual_filing_has_fy_suffix(self):
        """10-K annual periods should get (FY) suffix."""
        # AAPL FY2025 10-K filed 2025-10-31
        filing = Filing(form='10-K', filing_date='2025-10-31', company='Apple Inc.',
                        cik=320193, accession_no='0000320193-25-000079')
        stmt = filing.xbrl().statements.income_statement()
        df = stmt.to_dataframe()
        fy_cols = [c for c in df.columns if '(FY)' in c]
        assert len(fy_cols) >= 1, f"Expected FY suffix on annual columns, got: {_date_cols(df)}"
