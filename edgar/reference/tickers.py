import re
from functools import lru_cache
from typing import Union

import pandas as pd
import pyarrow as pa

from edgar.httprequests import download_json
from edgar.reference.data.common import read_parquet_from_package

__all__ = ['cusip_ticker_mapping', 'get_ticker_from_cusip', 'get_company_tickers']


@lru_cache(maxsize=1)
def cusip_ticker_mapping(allow_duplicate_cusips: bool = True) -> pd.DataFrame:
    """
    Download the Cusip to Ticker mapping data from the SEC website.
    This provides a Dataframe with Cusip as the index and Ticker as the column.

    CUSIP can be duplicate to get non duplicate Cusips set allow_duplicate_cusips to False.
    This will return only the first occurrence of the Cusip.
    The first occurrence of the Cusip will also be most likely to be mapped to a Ticker that is linked to a cik
    """
    df = read_parquet_from_package('ct.pq').set_index('Cusip')
    if not allow_duplicate_cusips:
        df = df[~df.index.duplicated(keep='first')]
    return df


@lru_cache(maxsize=128)
def get_ticker_from_cusip(cusip: str):
    """
    Get the ticker symbol for a given Cusip.
    """
    data = cusip_ticker_mapping()
    results = data.loc[cusip]
    if len(results) == 1:
        return results.iloc[0]
    elif len(results) > 1:
        return results.iloc[0].Ticker


def clean_company_name(name: str) -> str:
    # Regular expression to match unwanted patterns at the end of the company name
    cleaned_name = re.sub(r'[/\\][A-Z]+[/\\]?$', '', name)
    return cleaned_name.strip()


def clean_company_suffix(name: str) -> str:
    """Remove common suffixes from the company name, taking care of special cases."""
    # Remove trailing slashes
    name = name.rstrip('/')
    # Handle cases like "JPMORGAN CHASE & CO" or "ELI LILLY & Co"
    name = re.sub(r'\s*&\s*CO\b\.?', '', name, flags=re.IGNORECASE).strip()
    # Remove other common suffixes, including "PLC", "LTD", "LIMITED", and combinations like "LTD CO"
    name = re.sub(r'\b(?:Inc\.?|CO|CORP|PLC|LTD|LIMITED|L\.P\.)\b\.?$', '', name, flags=re.IGNORECASE).strip()
    return name


@lru_cache(maxsize=1)
def get_company_tickers(as_dataframe: bool = True,
                        clean_name: bool = True,
                        clean_suffix: bool = False) -> Union[pd.DataFrame, pa.Table]:
    # Function to download JSON data

    tickers_json = download_json("https://www.sec.gov/files/company_tickers.json")

    # Extract the data into a list of dictionaries
    data = []
    for item in tickers_json.values():
        company_name = item['title']
        if clean_name:
            company_name = clean_company_name(company_name)
        if clean_suffix:
            company_name = clean_company_suffix(company_name)
        data.append({'cik': int(item['cik_str']), 'ticker': item['ticker'], 'company': company_name})

    if as_dataframe:
        return pd.DataFrame(data)

    # Create a pyarrow schema
    schema = pa.schema([
        ('cik', pa.int64()),
        ('ticker', pa.string()),
        ('company', pa.string())
    ])

    # Convert the data to a pyarrow Table
    table = pa.Table.from_pylist(data, schema=schema)

    return table
