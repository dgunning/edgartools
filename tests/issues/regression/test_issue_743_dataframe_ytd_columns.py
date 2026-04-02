"""Regression test for GitHub issue #743.

Statement.to_dataframe() on 10-Q filings only showed YTD columns because
quarterly and YTD periods shared the same end date, causing column name
collisions. Now disambiguated with (Q2)/(YTD) suffixes.
"""
import re

import pytest
from edgar import Filing


@pytest.mark.network
def test_10q_dataframe_has_quarterly_and_ytd_columns():
    """10-Q Q2/Q3 income statement should have both quarterly and YTD columns in DataFrame."""
    # AAPL Q3 2024 10-Q — a Q3 filing that has both quarterly and YTD periods
    filing = Filing(form='10-Q', filing_date='2024-08-02', company='Apple Inc.',
                    cik=320193, accession_no='0000320193-24-000081')

    stmt = filing.obj().financials.income_statement()
    df = stmt.to_dataframe()

    # Find date columns (may have suffixes like (Q3), (YTD))
    date_cols = [c for c in df.columns if re.match(r'^\d{4}-\d{2}-\d{2}', c)]

    # Should have 4 date columns: Q current, Q prior, YTD current, YTD prior
    assert len(date_cols) >= 4, f"Expected at least 4 date columns, got {len(date_cols)}: {date_cols}"

    # Should have both quarterly and YTD suffixes
    q_cols = [c for c in date_cols if '(Q' in c]
    ytd_cols = [c for c in date_cols if '(YTD)' in c]
    assert len(q_cols) >= 2, f"Expected at least 2 quarterly columns, got {q_cols}"
    assert len(ytd_cols) >= 2, f"Expected at least 2 YTD columns, got {ytd_cols}"

    # Revenue should be different between Q and YTD
    revenue = df[df['label'].str.contains('Net sales|Revenue', case=False, na=False)]
    if len(revenue) > 0:
        row = revenue.iloc[0]
        q_val = row[q_cols[0]]
        ytd_val = row[ytd_cols[0]]
        # YTD should be larger than quarterly
        assert ytd_val > q_val, f"YTD ({ytd_val}) should be larger than quarterly ({q_val})"
