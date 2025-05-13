from edgar.xbrl import *
from rich import print
from edgar import *
from edgar.xbrl.periods import determine_periods_to_display


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
