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
    
    # Smart period selection may return fewer periods if data is insufficient
    # The first period should still be the most recent year
    assert periods[0] == (
        'duration_2014-07-01_2015-06-30',
        'Annual: July 01, 2014 to June 30, 2015'
    )
    
    # Smart selection filters out periods with insufficient data
    # We should have at least 2 periods for trend analysis
    assert len(periods) >= 2
    
    # Second period should be previous year
    assert periods[1] == (
        'duration_2013-07-01_2014-06-30',
        'Annual: July 01, 2013 to June 30, 2014'
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
    
    # Smart period selection now defaults to 4 periods for better investor context
    assert len(periods) == 4
    
    # First period should be current quarter (Q2 2025)
    assert periods[0][0] == 'duration_2025-04-01_2025-06-30'
    assert 'Quarterly' in periods[0][1]
    
    # Second period should be prior year same quarter (Q2 2024) 
    assert periods[1][0] == 'duration_2024-04-01_2024-06-30'
    assert 'Quarterly' in periods[1][1]
    
    # Third period should be YTD (H1 2025)
    assert periods[2][0] == 'duration_2025-01-01_2025-06-30'
    assert 'Semi-Annual' in periods[2][1]
    
    # Fourth period should be prior year YTD (H1 2024)
    assert periods[3][0] == 'duration_2024-01-01_2024-06-30'
    assert 'Semi-Annual' in periods[3][1]
    
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

