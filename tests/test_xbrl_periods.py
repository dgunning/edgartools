from edgar.xbrl import *
from rich import print
from edgar import *
from edgar.xbrl.periods import determine_periods_to_display
import pytest

@pytest.fixture(scope="session")
def comcast_xbrl():
    filing = Filing(company='COMCAST CORP', cik=1166691, form='10-K', filing_date='2025-01-31', accession_no='0001166691-25-000011')
    return XBRL.from_filing(filing)

@pytest.fixture(scope="session")
def mara_xbrl():
    f = Filing(company='MARA Holdings, Inc.', cik=1507605, form='10-Q', filing_date='2025-07-29',
           accession_no='0001507605-25-000018')
    return XBRL.from_filing(f)

def test_get_periods_to_display_for_company_with_changed_fiscal_year():
    c = Company("MSFT")
    filings = c.get_filings(form="10-K", filing_date='2013-01-01:2015-12-31')
    for filing in filings:
        xb = filing.xbrl()
        print(xb.period_of_report)
    filing = Filing(company='MICROSOFT CORP', cik=789019, form='10-K', filing_date='2015-07-31', accession_no='0001193125-15-272806')

    xb = filing.xbrl()

    periods = determine_periods_to_display(xb, "IncomeStatement")
    print(periods)
    assert periods[0] ==(
        'duration_2014-07-01_2015-06-30',
        'Annual: July 01, 2014 to June 30, 2015'
    )
    assert periods[2] == (
        'duration_2012-07-01_2013-06-30',
        'Annual: July 01, 2012 to June 30, 2013'
    )


def test_quarterly_period_selection():
    c = Company("AVGO")
    f = Filing(company='Broadcom Inc.', cik=1730168, form='10-Q', filing_date='2025-03-12', accession_no='0001730168-25-000021')
    xb = f.xbrl()
    periods = determine_periods_to_display(xb, "IncomeStatement")
    assert periods[0][0] == 'duration_2024-11-04_2025-02-02'
    print(xb.statements.income_statement())

def test_annual_period_selection():
    filing = Filing(company='COMCAST CORP', cik=1166691, form='10-K', filing_date='2025-01-31',
                    accession_no='0001166691-25-000011')
    xb = filing.xbrl()
    print(xb.statements.balance_sheet())

def test_periods_for_quarterly_filing(mara_xbrl):
    """Test that quarterly filings select appropriate periods, not arbitrary short periods."""
    xb = mara_xbrl
    periods = determine_periods_to_display(xb, "IncomeStatement")
    print(periods)
    
    # Should have 3 periods
    assert len(periods) == 3
    
    # First period should be current quarter (Q2 2025)
    assert periods[0][0] == 'duration_2025-04-01_2025-06-30'
    assert 'Quarterly' in periods[0][1]
    
    # Second period should be prior year same quarter (Q2 2024) 
    assert periods[1][0] == 'duration_2024-04-01_2024-06-30'
    assert 'Quarterly' in periods[1][1]
    
    # Third period should be YTD (H1 2025)
    assert periods[2][0] == 'duration_2025-01-01_2025-06-30'
    assert 'Semi-Annual' in periods[2][1]
    
    # Verify no single-day or arbitrary short periods are selected
    for period_key, period_label in periods:
        # Extract dates from the key
        if period_key.startswith('duration_'):
            dates = period_key.replace('duration_', '').split('_')
            if len(dates) == 2:
                start_date = dates[0]
                end_date = dates[1]
                # Ensure start and end dates are different (no single-day periods)
                assert start_date != end_date, f"Single-day period found: {period_key}"


def test_ytd_indicator_in_column_headers(mara_xbrl):
    """Test that YTD periods show (YTD) indicator in column headers."""

    # Get the income statement
    income_stmt = mara_xbrl.statements.income_statement()
    assert income_stmt is not None

    # Convert to string and check headers
    stmt_str = str(income_stmt)
    lines = stmt_str.split('\n')

    # Find lines with period information - they may be split across multiple lines
    has_current_quarter = False
    has_prior_quarter = False
    has_ytd = False

    # Check first 10 lines for period indicators
    for line in lines[:10]:
        if 'Jun 30, 2025 (Q2)' in line:
            has_current_quarter = True
        if 'Jun 30, 2024 (Q2)' in line:
            has_prior_quarter = True
        if '(YTD)' in line:
            has_ytd = True

    # Debug: print first 10 lines to see structure
    print("\nFirst 10 lines of income statement:")
    for i, line in enumerate(lines[:10]):
        print(f"{i}: {line}")

    # Check that we have the expected column headers
    assert has_current_quarter, "Current quarter should have Q2 indicator"
    assert has_prior_quarter, "Prior year quarter should have Q2 indicator"
    assert has_ytd, "YTD period should have YTD indicator"

    # Verify the fiscal period indicator is correct
    assert 'Three Months Ended' in stmt_str, "Should show Three Months Ended for quarterly filing"

    print("✓ YTD indicator correctly displayed in column headers")