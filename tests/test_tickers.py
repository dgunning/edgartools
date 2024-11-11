
from edgar.reference.tickers import popular_us_stocks, get_ticker_from_cusip, get_company_tickers, get_icon_from_ticker, clean_company_suffix
import pandas as pd
import pyarrow as pa
import pytest


def test_get_tickers():
    tickers = get_company_tickers()
    assert isinstance(tickers, pd.DataFrame)
    assert tickers.columns.tolist() == ['cik', 'ticker', 'company']
    print(tickers.head())

    tickers = get_company_tickers(as_dataframe=False)
    assert isinstance(tickers, pa.Table)

def test_clean_company_suffix():
    assert clean_company_suffix('JPMORGAN CHASE & CO') == 'JPMORGAN CHASE'
    assert clean_company_suffix('ELI LILLY & Co') == 'ELI LILLY'
    assert clean_company_suffix('ASTRAZENECA PLC') == 'ASTRAZENECA'
    assert clean_company_suffix('HDFC BANK LTD') == 'HDFC BANK'
    assert clean_company_suffix('SOUTHERN COPPER CORP/') == 'SOUTHERN COPPER'
    assert clean_company_suffix('SOUTHERN COPPER CORP') == 'SOUTHERN COPPER'
    assert clean_company_suffix('ANZ GROUP HOLDINGS LIMITED') == 'ANZ GROUP HOLDINGS'
    #assert clean_company_suffix('ENTERPRISE PRODUCTS PARTNERS L.P.') == 'ENTERPRISE PRODUCTS PARTNERS'

def test_get_icon_valid_ticker():
    icon = get_icon_from_ticker("AAPL")
    assert icon is not None
    assert isinstance(icon, bytes)
    assert icon[:8] == b"\x89PNG\r\n\x1a\n"

def test_get_icon_invalid_ticker():
    icon = get_icon_from_ticker("INVALID")
    assert icon is None

def test_get_icon_bad_ticker():
    with pytest.raises(ValueError):
        icon = get_icon_from_ticker("A.!@#$%^&*()")

    with pytest.raises(ValueError):
        icon = get_icon_from_ticker("AAPL 123")

    with pytest.raises(ValueError):
        icon = get_icon_from_ticker("")

    with pytest.raises(ValueError):
        icon = get_icon_from_ticker(None)

    with pytest.raises(ValueError):
        icon = get_icon_from_ticker(123)


def test_popular_us_stocks():
    stocks = popular_us_stocks()
    assert not stocks.empty
    assert stocks[stocks.Ticker=='WDAY'].index.item() ==1327811