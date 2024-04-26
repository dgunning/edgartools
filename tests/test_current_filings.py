
from edgar._filings import get_current_filings, parse_summary, CurrentFilings
import datetime
import pytest

def test_get_current_entries():
    print()
    filings = get_current_filings()
    print(filings)
    # previous should be None
    assert filings.previous() is None

    next_filings = filings.next()
    assert next_filings is not None
    print(next_filings)
    previous_filings = next_filings.previous()
    print(previous_filings)
    assert previous_filings.previous() is None


def test_get_current_filings_by_form():
    form='4'
    filings:CurrentFilings = get_current_filings(form=form)

    # Check that all filings are start with 4. This matches the behavior of the SEC website

    for i in range(4):
        filings = filings.next()
        if not filings:
            break
        assert all(f.startswith(form) for f in set(filings.data['form'].to_pylist()))


def test_current_filings_to_pandas():
    filings:CurrentFilings = get_current_filings()
    filing_pandas = filings.to_pandas()
    assert filings[0].accession_no == filing_pandas['accession_number'][0]
    accession_number_on_page0 = filings[0].accession_no

    # Get the next page
    filings_page2 = filings.next()
    filing_page2_pandas = filings_page2.to_pandas()
    assert filing_page2_pandas is not None
    #assert filings_page2[0].accession_no == filing_page2_pandas['accession_number'][0]
    #accession_number_on_page1 = filings_page2[0].accession_no
    #assert accession_number_on_page0 != accession_number_on_page1


def test_current_filings_get_by_index_on_page1():
    print()
    filings: CurrentFilings = get_current_filings()
    filing = filings.get(20)
    assert filing
    assert filings[20]

    # Find the filing on page2
    filing_page2 = filings.next()
    print(filing_page2)

def test_current_filings_get_by_index_on_page2():
    filings: CurrentFilings = get_current_filings()
    # Find the filing on page2
    filing_page2 = filings.next()
    print(filing_page2)
    # Get the first filing on page2 which should be index 40
    filing = filing_page2.get(40)
    # Get the first row of the data
    accession_number = filing_page2.data['accession_number'].to_pylist()[0]
    assert filing
    assert filing.accession_no == accession_number
    assert filing_page2[79]

    with pytest.raises(AssertionError):
        # The boundary is 80
        filing_page2[80]


def test_current_filings_get_accession_number():
    filings:CurrentFilings = get_current_filings().next()
    accession_number = filings.data['accession_number'].to_pylist()[0]
    print(accession_number)
    filings = filings.prev()
    filing = filings.get(accession_number)
    assert filing
    assert filing.accession_no == accession_number


def test_current_filings_get_accession_number_not_found():
    filings:CurrentFilings = get_current_filings().next()
    accession_number = '0000000900-24-000000'
    filings = filings.prev()
    filing = filings.get(accession_number)
    assert not filing


def test_parse_summary():
    summary1 = '<b>Filed:</b> 2023-09-13 <b>AccNo:</b> 0001714174-23-000114 <b>Size:</b> 668 KB'

    filing_date, accession_number = parse_summary(summary1)
    assert (filing_date, accession_number) == (datetime.date(2023, 9, 13), '0001714174-23-000114')

    summary2 = '<b>Film#:</b> 23003229  <b>Filed:</b> 2023-08-17 <b>AccNo:</b> 9999999997-23-004141 <b>Size:</b> 1 KB'
    assert parse_summary(summary2) == (datetime.date(2023, 8, 17), '9999999997-23-004141')

def test_current_filings_with_no_results():

    filings = get_current_filings(form='4000')
    assert filings.empty
    assert isinstance(filings, CurrentFilings)
    assert filings.start_date is None
    assert filings.end_date is None
