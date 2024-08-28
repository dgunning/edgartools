from edgar.reference import cusip_ticker_mapping, get_ticker_from_cusip, describe_form
from edgar.reference.tickers import get_cik_tickers, find_cik, get_company_ticker_name_exchange, \
    get_companies_by_exchange, get_mutual_fund_tickers, find_mutual_fund_cik


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


def test_describe_form():
    assert describe_form('10-K') == 'Form 10-K: Annual report for public companies'
    assert describe_form('10-K/A') == 'Form 10-K Amendment: Annual report for public companies'
    assert describe_form('15F-12B') == 'Form 15F-12B: Foreign private issuer equity securities termination'
    assert describe_form('NOMA') == 'Form NOMA'
    assert describe_form('3') == 'Form 3: Initial statement of beneficial ownership'

    assert describe_form('10-K', prepend_form=False) == 'Annual report for public companies'


def test_cik_tickers():
    tickers = get_cik_tickers()
    assert tickers.loc[tickers.ticker == 'ATVI'].cik.iloc[0] == 718877


def test_find_cik():
    assert find_cik('ATVI') == 718877
    assert find_cik('AAPL') == 320193
    assert find_cik('TSLA') == 1318605
    assert find_cik('MSFT') == 789019
    assert find_cik('GOOGL') == 1652044
    assert find_cik("BRK-B") == find_cik("BRK.B") == find_cik("BRK") == 1067983
    assert find_cik("BH-A") == find_cik("BH") == 1726173

    # ETF Ticker
    assert find_cik("CGIC") == 2008516


def test_find_mutual_fund_cik():
    assert find_mutual_fund_cik("CGIC") == 2008516
    assert find_mutual_fund_cik("ABNZX") == 3794


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
    print()
    print(data)
