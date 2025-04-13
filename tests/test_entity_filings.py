from edgar import *


def test_equality_of_filings():
    c = Company("AAPL")
    filings = c.get_filings().filter(form="10-K")

    filings2 = c.get_filings().filter(form="10-K")

    assert filings == filings2
    filings2 = filings2.filter(filing_date="2023-01-01:2024-12-31")
    assert filings != filings2

    filings3 = c.get_filings().filter(form="10-Q")
    assert filings != filings3


def test_filings_hash():
    c = Company("AAPL")
    filings = c.get_filings()
    _hash = hash(filings)
    assert _hash