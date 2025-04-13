"""
Ticker-related functionality for the entity package.
This module re-exports ticker-related functions from edgar.reference.tickers.
"""

from edgar.reference.tickers import (
    get_icon_from_ticker,
    get_company_tickers,
    find_cik,
    find_ticker
)

# We need to create our own implementation of these functions
from functools import lru_cache
import pandas as pd
from edgar.httprequests import download_text

@lru_cache(maxsize=1)
def get_ticker_to_cik_lookup():
    """
    Create a dictionary that maps from ticker symbol to CIK.
    """
    df = get_company_tickers()
    ticker_to_cik = {}
    for _, row in df.iterrows():
        ticker_to_cik[row['ticker']] = row['cik']
    return ticker_to_cik


def _parse_cik_lookup_data(content):
    """Parse CIK lookup data from content."""
    return [
        {
            # for companies with : in the name
            'name': ":".join(line.split(':')[:-2]),
            'cik': int(line.split(':')[-2])
        } for line in content.split("\n") if line != '']


@lru_cache(maxsize=1)
def get_cik_lookup_data() -> pd.DataFrame:
    """
    Get a dataframe of company/entity names and their cik
    or a Dict of int(cik) to str(name)
    DECADE CAPITAL MANAGEMENT LLC:0001426822:
    DECADE COMPANIES INCOME PROPERTIES:0000775840:
    """
    content = download_text("https://www.sec.gov/Archives/edgar/cik-lookup-data.txt")
    cik_lookup_df = pd.DataFrame(_parse_cik_lookup_data(content))
    return cik_lookup_df

__all__ = [
    'get_icon_from_ticker',
    'get_company_tickers',
    'get_ticker_to_cik_lookup',
    'get_cik_lookup_data',
    'find_cik',
    'find_ticker'
]