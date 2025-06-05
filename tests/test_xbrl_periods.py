from edgar.xbrl import *
from rich import print
from edgar import *
from edgar.xbrl.periods import determine_periods_to_display
import pytest

@pytest.fixture(scope="session")
def comcast_xbrl():
    filing = Filing(company='COMCAST CORP', cik=1166691, form='10-K', filing_date='2025-01-31', accession_no='0001166691-25-000011')
    return XBRL.from_filing(filing)

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