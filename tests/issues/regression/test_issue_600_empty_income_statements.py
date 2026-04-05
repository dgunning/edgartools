"""
Regression test for Issue #600: Certain income statements are almost empty.

The issue was caused by the period selector using quarterly periods instead of annual
periods for 10-K filings when the XBRL metadata had fiscal_period='Q4' instead of 'FY'.

This test verifies that income statements for affected 10-K filings have sufficient
data density (>50%) indicating the correct annual periods are being selected.

Fix: edgar/xbrl/period_selector.py now checks document_type and annual_report flag
in addition to fiscal_period to correctly identify annual reports.

GitHub Issue: https://github.com/dgunning/edgartools/issues/600
"""
import pytest
from edgar import Filing


@pytest.mark.network
@pytest.mark.parametrize("ticker,year,accession,filing_date,cik,company_name,min_density", [
    # GE FY2015 - the original problem filing
    ("GE", 2015, "0000040545-16-000145", "2016-02-26", 40545, "GENERAL ELECTRIC CO", 50.0),
    # GE FY2016
    ("GE", 2016, "0000040545-17-000010", "2017-02-24", 40545, "GENERAL ELECTRIC CO", 50.0),
])
def test_income_statement_data_density(ticker, year, accession, filing_date, cik, company_name, min_density):
    """
    Verify income statements have sufficient data density.

    Issue #600: Income statements were returning almost empty data (4-7% density)
    because the period selector was choosing quarterly periods instead of annual
    periods for 10-K filings with fiscal_period='Q4' in XBRL metadata.
    """
    filing = Filing(form="10-K", company=company_name, cik=cik,
                   accession_no=accession, filing_date=filing_date)

    xbrl = filing.xbrl()
    assert xbrl is not None, f"Failed to load XBRL for {ticker} {year}"

    income = xbrl.statements.income_statement()
    assert income is not None, f"Income statement not found for {ticker} {year}"

    df = income.to_dataframe()
    assert not df.empty, f"Empty DataFrame for {ticker} {year}"

    # Identify period columns (exclude metadata columns)
    meta_cols = {'concept', 'label', 'standard_concept', 'level', 'abstract', 'dimension',
                 'is_breakdown', 'dimension_axis', 'dimension_member', 'dimension_member_label',
                 'dimension_label', 'balance', 'weight', 'preferred_sign', 'parent_concept',
                 'parent_abstract_concept'}
    period_cols = [c for c in df.columns if c not in meta_cols]

    assert len(period_cols) > 0, f"No period columns found for {ticker} {year}"

    # Calculate data density
    total_cells = df.shape[0] * len(period_cols)
    non_empty = df[period_cols].notna().sum().sum()
    density = non_empty / total_cells * 100 if total_cells > 0 else 0

    assert density >= min_density, (
        f"{ticker} {year} income statement has only {density:.1f}% data density "
        f"(expected >= {min_density}%). This indicates the period selector may be "
        f"choosing quarterly periods instead of annual periods."
    )


@pytest.mark.network
def test_annual_detection_with_q4_fiscal_period():
    """
    Test that 10-K filings are correctly identified as annual reports
    even when fiscal_period='Q4' in XBRL metadata.

    Issue #600: GE's 2015 10-K had fiscal_period='Q4' which caused the
    period selector to treat it as a quarterly filing.
    """
    # GE FY2015 - has fiscal_period='Q4' but is a 10-K
    filing = Filing(form="10-K", company="GENERAL ELECTRIC CO", cik=40545,
                   accession_no="0000040545-16-000145", filing_date="2016-02-26")

    xbrl = filing.xbrl()
    entity_info = xbrl.entity_info

    # Verify the problematic condition exists
    assert entity_info.get('fiscal_period') == 'Q4', (
        "Test setup invalid: GE 2015 10-K should have fiscal_period='Q4'"
    )

    # Verify the document_type is correctly identified
    assert entity_info.get('document_type') == '10-K', (
        "Document type should be '10-K'"
    )

    # Verify the period selector returns annual periods
    from edgar.xbrl.periods import determine_periods_to_display
    periods = determine_periods_to_display(xbrl, 'IncomeStatement')

    assert len(periods) > 0, "No periods returned"

    # Check that the first period is annual (duration > 300 days)
    from datetime import datetime
    first_period_key = periods[0][0]
    assert first_period_key.startswith('duration_'), f"Expected duration period, got {first_period_key}"

    parts = first_period_key.split('_')
    start_date = datetime.strptime(parts[1], '%Y-%m-%d')
    end_date = datetime.strptime(parts[2], '%Y-%m-%d')
    duration_days = (end_date - start_date).days

    assert duration_days > 300, (
        f"First period has only {duration_days} days. Expected annual period (>300 days). "
        f"The fix for issue #600 may not be working correctly."
    )
