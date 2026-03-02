import json
from unittest.mock import patch

import pandas as pd

from edgar.reference import cusip_ticker_mapping, get_ticker_from_cusip, describe_form
from edgar.reference.tickers import get_cik_tickers, find_cik, get_company_ticker_name_exchange, \
    get_companies_by_exchange, get_mutual_fund_tickers, find_mutual_fund_cik, get_company_tickers


def test_cusip_ticker_mapping():
    data = cusip_ticker_mapping()
    assert data.loc['15101T102'].Ticker == 'CLXX'


def test_get_ticker_from_cusip():
    assert get_ticker_from_cusip('000307108') == 'AACH'
    assert get_ticker_from_cusip('74349L108') == 'PGUCY'
    assert get_ticker_from_cusip('037833100') == 'AAPL'
    assert get_ticker_from_cusip('59021J679') == 'MNK'


def test_get_ticker_from_cusip_missing():
    """Missing CUSIPs return None instead of raising KeyError."""
    assert get_ticker_from_cusip('XXXXXXXXX') is None
    assert get_ticker_from_cusip('000000000') is None
    assert get_ticker_from_cusip('') is None
    assert get_ticker_from_cusip(None) is None


def test_get_ticker_from_cusip_with_multiple_tickers():
    data = cusip_ticker_mapping()
    tickers = data.loc['000307108']
    assert len(tickers) == 2
    assert tickers.Ticker.tolist() == ['AACH', 'AAC']
    assert get_ticker_from_cusip('000307108') == 'AACH'


def test_cusip_ticker_mapping_not_allowing_duplicates():
    data = cusip_ticker_mapping(allow_duplicate_cusips=False)
    tickers = data.loc['000307108']
    assert len(tickers) == 1

    data = cusip_ticker_mapping(allow_duplicate_cusips=True)
    tickers = data.loc['000307108']
    assert len(tickers) == 2


def test_describe_form():
    assert describe_form('10-K') == 'Form 10-K: Annual report for public companies'
    assert describe_form('10-K/A') == 'Form 10-K Amendment: Annual report for public companies'
    assert describe_form('15F-12B') == 'Form 15F-12B: Foreign private issuer equity securities termination'
    assert describe_form('NOMA') == 'Form NOMA'
    assert describe_form('3') == 'Form 3: Initial statement of beneficial ownership'

    assert describe_form('10-K', prepend_form=False) == 'Annual report for public companies'



def test_find_cik():
    assert find_cik('AAPL') == 320193
    assert find_cik('TSLA') == 1318605
    assert find_cik('MSFT') == 789019
    assert find_cik('GOOGL') == 1652044
    assert find_cik("BRK-B") == find_cik("BRK.B") == find_cik("BRK") == 1067983
    assert find_cik("BH-A") == find_cik("BH") == 1726173
    assert find_cik("NOTTHERE") is None



def test_find_mutual_fund_cik():
    assert find_mutual_fund_cik("ABNZX") == 3794
    assert find_mutual_fund_cik("NOTTHERE") is None


def test_company_ticker_name_exchange():
    data = get_company_ticker_name_exchange()
    assert ['cik', 'name', 'ticker', 'exchange'] == data.columns.tolist()
    print()


def test_get_companies_by_exchange():
    data = get_companies_by_exchange('NYSE')
    assert 'NYSE' in data.exchange.tolist()
    assert 'Nasdaq' not in data.exchange.tolist()

    data = get_companies_by_exchange(['NYSE', 'NASDAQ'])
    assert 'NYSE' in data.exchange.tolist()
    assert 'Nasdaq' in data.exchange.tolist()


def test_get_mutual_fund_tickers():
    data = get_mutual_fund_tickers()
    assert data.columns.tolist() == ['cik', 'seriesId', 'classId', 'ticker']

    assert not data.query("ticker == 'CRBRX'").empty


def test_get_cik_tickers_uses_bundled_data():
    """
    Test that get_cik_tickers() uses bundled parquet data by default.

    The bundled data provides instant offline access without network calls.
    This is the primary data source since ticker.txt is deprecated by SEC.
    """
    from edgar.reference.tickers import _get_company_tickers_raw

    # Clear the lru_cache to ensure we're not getting cached results
    get_cik_tickers.cache_clear()
    _get_company_tickers_raw.cache_clear()

    # Patch network calls to verify they're NOT called when bundled data exists
    with patch('edgar.reference.tickers.download_file') as mock_download_file, \
            patch('edgar.reference.tickers.download_json') as mock_download_json:

        data = get_cik_tickers()

        # Verify the result uses bundled data
        assert isinstance(data, pd.DataFrame), "Result should be a pandas DataFrame"
        assert set(data.columns) == {'ticker', 'cik'}, \
            f"Columns should be 'ticker' and 'cik', got {data.columns}"
        assert len(data) > 10000, \
            f"Bundled data should have >10000 entries, got {len(data)}"

        # Verify key tickers are present
        assert 'AAPL' in data['ticker'].values, "AAPL should be in the data"
        assert 'MSFT' in data['ticker'].values, "MSFT should be in the data"

        # Verify no network calls were made (bundled data was used)
        mock_download_file.assert_not_called()
        mock_download_json.assert_not_called()