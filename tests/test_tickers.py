
from edgar.reference.tickers import cusip_ticker_mapping, get_ticker_from_cusip, get_company_tickers, clean_company_suffix
import pandas as pd
import pyarrow as pa


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