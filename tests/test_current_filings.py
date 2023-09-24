
from edgar._filings import get_current_filings, parse_summary, CurrentFilings


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
    form='3'
    filings:CurrentFilings = get_current_filings(form=form)
    for i in range(4):
        filings = filings.next()
        if not filings:
            break
        assert all(f.startswith(form) for f in set(filings.filing_index['form'].to_pylist()))



def test_parse_summary():
    summary1 = '<b>Filed:</b> 2023-09-13 <b>AccNo:</b> 0001714174-23-000114 <b>Size:</b> 668 KB'

    filing_date, accession_number = parse_summary(summary1)
    assert (filing_date, accession_number) == ('2023-09-13', '0001714174-23-000114')

    summary2 = '<b>Film#:</b> 23003229  <b>Filed:</b> 2023-08-17 <b>AccNo:</b> 9999999997-23-004141 <b>Size:</b> 1 KB'
    assert parse_summary(summary2) == ('2023-08-17', '9999999997-23-004141')
