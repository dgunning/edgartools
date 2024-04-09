from edgar.reference import cusip_ticker_mapping, get_ticker_from_cusip
from edgar import *


def test_cusip_ticker_mapping():
    data = cusip_ticker_mapping()
    assert data.loc['15101T102'].Ticker == 'CLXX'


def test_get_ticker_from_cusip():
    assert get_ticker_from_cusip('000307108') == 'AACH'
    assert get_ticker_from_cusip('74349L108') == 'PGUCY'
    assert get_ticker_from_cusip('037833100') == 'AAPL'
    assert get_ticker_from_cusip('59021J679') == 'MNK'


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
