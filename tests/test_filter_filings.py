from edgar import *
from edgar.reference.tickers import get_company_ticker_name_exchange
import pytest
from datetime import datetime, date

@pytest.fixture(scope="module")
def filings():
    return get_filings(2024, 4)

@pytest.mark.fast
def test_filter_by_cik(filings):
    filtered = filings.filter(cik=320193)
    assert filtered.data['cik'].unique().to_pylist() == [320193]

@pytest.mark.fast
def test_filter_by_exchange(filings):
    filtered = filings.filter(exchange="NYSE")
    df = get_company_ticker_name_exchange()
    nyse_ciks = df[df.exchange.isin(['NYSE'])].cik.to_list()
    ciks = filtered.data['cik'].unique().to_pylist()
    assert all(cik in nyse_ciks for cik in ciks)

    # Check for Upper case exchange name
    filtered = filings.filter(exchange="NASDAQ")
    nasdaq_ciks = df[df.exchange.isin(['Nasdaq'])].cik.to_list()
    ciks = filtered.data['cik'].unique().to_pylist()
    assert all(cik in nasdaq_ciks for cik in ciks)

@pytest.mark.fast
def test_filter_by_multiple_exchanges(filings):
    filtered = filings.filter(exchange=["Nasdaq", "NYSE"])
    df = get_company_ticker_name_exchange()
    exchange_ciks = df[df.exchange.isin(["Nasdaq", 'NYSE'])].cik.to_list()
    ciks = filtered.data['cik'].unique().to_pylist()
    assert all(cik in exchange_ciks for cik in ciks)

@pytest.mark.fast
def test_filter_by_form(filings):
    filtered = filings.filter(form="10-K")
    assert filtered.data['form'].unique().to_pylist() == ['10-K']

    filtered = filings.filter(form=["10-K", "10-Q"])
    assert sorted(filtered.data['form'].unique().to_pylist()) == ['10-K', '10-Q']

@pytest.mark.fast
def test_filter_by_filing_date(filings):
    filtered = filings.filter(filing_date="2024-12-05")
    filing_dates = filtered.data['filing_date'].unique().to_pylist()
    assert filing_dates == [date(2024, 12, 5)]

    filtered = filings.filter(date="2024-12-05")
    filing_dates = filtered.data['filing_date'].unique().to_pylist()
    assert filing_dates == [date(2024, 12, 5)]
