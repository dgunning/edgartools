import json
import os
import re
from enum import Enum
from functools import lru_cache
from io import StringIO
from typing import Any, Dict, List, Optional, Union

import pandas as pd
import pyarrow as pa
from httpx import HTTPStatusError

from edgar.core import get_edgar_data_directory, listify, log
from edgar.httprequests import download_file, download_json
from edgar.reference.data.common import read_csv_from_package, read_parquet_from_package

__all__ = ['cusip_ticker_mapping', 'get_ticker_from_cusip', 'get_company_tickers', 'get_icon_from_ticker', 'find_cik',
           'get_cik_tickers', 'get_company_ticker_name_exchange', 'get_companies_by_exchange', 'popular_us_stocks',
           'get_mutual_fund_tickers', 'find_mutual_fund_cik', 'list_all_tickers', 'find_ticker', 'find_ticker_safe', 'get_cik_ticker_lookup',
           'get_company_cik_lookup', 'get_cik_tickers_from_ticker_txt', 'get_cik_tickers', 'get_company_tickers',
           'Exchange'
           ]

from edgar.urls import (
    build_ticker_url,
    build_company_tickers_url,
    build_mutual_fund_tickers_url,
    build_company_tickers_exchange_url
)


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


def load_tickers_from_local() -> Optional[Dict[str, Any]]:
    """
    Load tickers from local data
    """
    reference_dir = get_edgar_data_directory() / "reference"
    if not reference_dir.exists():
        return None
    company_tickers_file = reference_dir / os.path.basename(build_company_tickers_url())
    if not company_tickers_file.exists():
        return None
    return json.loads(company_tickers_file.read_text())


@lru_cache(maxsize=1)
def get_company_tickers(
        as_dataframe: bool = True,
        clean_name: bool = True,
        clean_suffix: bool = False
) -> Union[pd.DataFrame, pa.Table]:
    """
    Fetch and process company ticker data from SEC.

    Args:
        as_dataframe (bool): If True, returns pandas DataFrame; if False, returns pyarrow Table
        clean_name (bool): If True, cleans company names
        clean_suffix (bool): If True, removes common company suffixes

    Returns:
        Union[pd.DataFrame, pa.Table]: Processed company data
    """

    # Pre-define schema for better performance
    SCHEMA = pa.schema([
        ('cik', pa.int64()),
        ('ticker', pa.string()),
        ('company', pa.string())
    ])

    try:
        if os.getenv("EDGAR_USE_LOCAL_DATA"):
            tickers_json = load_tickers_from_local()
            if not tickers_json:
                tickers_json = download_json(build_company_tickers_url())
        else:
            # Download JSON data
            tickers_json = download_json(build_company_tickers_url())

        # Pre-allocate lists for better memory efficiency
        ciks = []
        tickers = []
        companies = []

        # Process JSON data
        for item in tickers_json.values():
            company_name = item['title']

            # Apply name cleaning if requested
            if clean_name or clean_suffix:
                if clean_name:
                    company_name = clean_company_name(company_name)
                if clean_suffix:
                    company_name = clean_company_suffix(company_name)

            # Append to respective lists
            ciks.append(int(item['cik_str']))
            tickers.append(item['ticker'])
            companies.append(company_name)

        if as_dataframe:
            # Create DataFrame directly from lists
            return pd.DataFrame({
                'cik': ciks,
                'ticker': tickers,
                'company': companies
            })

        # Create pyarrow arrays
        cik_array = pa.array(ciks, type=pa.int64())
        ticker_array = pa.array(tickers, type=pa.string())
        company_array = pa.array(companies, type=pa.string())

        # Create and return pyarrow Table
        return pa.Table.from_arrays(
            [cik_array, ticker_array, company_array],
            schema=SCHEMA
        )

    except Exception as e:
        log.error(f"Error fetching company tickers from [{build_company_tickers_url()}]: {str(e)}")
        raise

def load_cik_tickers_from_local() -> Optional[str]:
    """
    Load tickers.txt from local data
    """
    reference_dir = get_edgar_data_directory() / "reference"
    if not reference_dir.exists():
        return None
    tickers_txt_file = reference_dir / os.path.basename(build_ticker_url())
    if not tickers_txt_file.exists():
        return None
    return tickers_txt_file.read_text()

def get_cik_tickers_from_ticker_txt():
    """Get CIK and ticker data from ticker.txt file"""
    try:
        if os.getenv("EDGAR_USE_LOCAL_DATA"):
            ticker_txt = load_cik_tickers_from_local()
            if not ticker_txt:
                ticker_txt = download_file(build_ticker_url(), as_text=True)
        else:
            ticker_txt = download_file(build_ticker_url(), as_text=True)
        source = StringIO(ticker_txt)
        data = pd.read_csv(source,
                           sep='\t',
                           header=None,
                           names=['ticker', 'cik']).dropna()
        data['ticker'] = data['ticker'].str.upper()
        return data
    except Exception as e:
        log.error(f"Error fetching company tickers from [{build_ticker_url()}]: {str(e)}")
        return None

@lru_cache(maxsize=1)
def get_cik_tickers():
    """Merge unique records from both sources"""
    txt_data = get_cik_tickers_from_ticker_txt()
    try:
        json_data = get_company_tickers(clean_name=False, clean_suffix=False)[['ticker', 'cik']]
    except Exception:
        json_data = None

    if txt_data is None and json_data is None:
        raise Exception("Both data sources are unavailable")

    if txt_data is None:
        return json_data

    if json_data is None:
        return txt_data

    # Merge both dataframes and keep unique records
    merged_data = pd.concat([txt_data, json_data], ignore_index=True)
    merged_data = merged_data.drop_duplicates(subset=['ticker', 'cik'])

    return merged_data

@lru_cache(maxsize=None)
def list_all_tickers():
    """List all tickers from the merged data"""
    return get_cik_tickers()['ticker'].tolist()


@lru_cache(maxsize=None)
def get_company_cik_lookup():
    df = get_cik_tickers()

    lookup = {}
    for ticker, cik in zip(df['ticker'], df['cik'], strict=False):
        # Add original ticker
        lookup[ticker] = cik

        # Add base ticker (part before '-')
        base_ticker = ticker.split('-')[0]
        if base_ticker not in lookup:
            lookup[base_ticker] = cik

    return lookup


@lru_cache(maxsize=None)
def get_cik_ticker_lookup():
    """Create a mapping of CIK to base ticker symbols.
    For CIKs with multiple tickers, uses the shortest ticker (usually the base symbol).
    """
    company_lookup = get_company_cik_lookup()
    cik_to_tickers = {}
    for ticker, cik in company_lookup.items():
        # Prefer the base ticker (without share class)
        base_ticker = ticker.split('-')[0]
        if cik not in cik_to_tickers or len(base_ticker) < len(cik_to_tickers[cik]):
            cik_to_tickers[cik] = base_ticker
    return cik_to_tickers


@lru_cache(maxsize=128)
def find_ticker(cik: Union[int, str]) -> str:
    """Find the ticker symbol for a given CIK.
    Returns empty string if no ticker is found.

    Args:
        cik: Central Index Key (CIK) as integer or string

    Returns:
        str: Ticker symbol or empty string if not found
    """
    try:
        # Ensure cik is an integer
        cik = int(str(cik).lstrip('0'))
        return get_cik_ticker_lookup().get(cik, "")
    except (ValueError, TypeError):
        return ""


def find_ticker_safe(cik: Union[int, str]) -> Optional[str]:
    """Find the ticker symbol for a given CIK without making network calls.
    Returns None if data is not already cached and would require a network call.
    Returns empty string if CIK is found but has no ticker.

    This function is designed for use cases where network calls should be avoided,
    such as in rich display methods that should be fast and not block on I/O.

    Args:
        cik: Central Index Key (CIK) as integer or string

    Returns:
        Optional[str]: Ticker symbol, empty string if no ticker found, or None if network call would be required
    """
    try:
        # Simple approach: check if all required cache functions have data
        # Only proceed if all the underlying data is already cached
        if (get_cik_ticker_lookup.cache_info().currsize > 0 and
            get_company_cik_lookup.cache_info().currsize > 0 and
            get_cik_tickers.cache_info().currsize > 0):

            # If we have cached data, try to use it
            cik = int(str(cik).lstrip('0'))

            # This should be fast since data is cached
            lookup_dict = get_cik_ticker_lookup()
            return lookup_dict.get(cik, "")
        else:
            # Not all required data is cached, return None to avoid network calls
            return None

    except Exception:
        # Any error (including potential network errors) returns None
        # This ensures we never trigger network calls
        return None

@lru_cache(maxsize=None)
def get_company_ticker_name_exchange():
    """
    Return a DataFrame with columns [cik	name	ticker	exchange]
    """
    data = download_json(build_company_tickers_exchange_url())
    return pd.DataFrame(data['data'], columns=data['fields'])


def get_companies_by_exchange(exchange: Union[List[str], str]):
    """
    Get companies listed on a specific exchange.

    :param exchange: String, like 'Nasdaq' or 'NYSE'
    :return: DataFrame with companies listed on the specified exchange
    with columns [cik	name	ticker	exchange]
    """
    df = get_company_ticker_name_exchange()
    exchanges = [ex.lower() for ex in listify(exchange)]
    return df[df['exchange'].str.lower().isin(exchanges)].reset_index(drop=True)


@lru_cache(maxsize=None)
def get_mutual_fund_tickers():
    """
    Get mutual fund tickers.
    This returns a dataframe with columns
        cik    seriesId     classId ticker
    """
    data = download_json(build_mutual_fund_tickers_url())
    return pd.DataFrame(data['data'], columns=['cik', 'seriesId', 'classId', 'ticker'])


@lru_cache(maxsize=None)
def get_mutual_fund_lookup():
    df = get_mutual_fund_tickers()
    return dict(zip(df['ticker'], df['cik'], strict=False))


def find_mutual_fund_cik(ticker):
    """
    Find the CIK for a given mutual fund or ETF ticker.

    :param ticker: String, the ticker symbol to look up
    :return: Integer, the CIK for the given ticker, or None if not found
    """
    lookup = get_mutual_fund_lookup()
    return lookup.get(ticker.upper())


def find_company_cik(ticker):
    lookup = get_company_cik_lookup()
    ticker = ticker.upper().replace('.', '-')
    return lookup.get(ticker)

def find_company_ticker(cik: Union[int, str]) -> Union[str, List[str], None]:
    """
    Find the ticker for a given CIK.

    :param cik (int or str):        The CIK to look up
    :return Union[str, List[str]]:  A single ticker string if only one ticker is found,
                                    a list of ticker strings if multiple tickers are found,
                                    or an empty list if no tickers are found.
    """
    try:
        # Ensure cik is a string without leading zeros, then convert to int
        cik = str(cik).lstrip('0')
        cik = int(cik)
    except (ValueError, TypeError):
        return None

    # Get DataFrame of CIK-Ticker mappings
    df = get_cik_tickers()

    # Ensure 'cik' and 'ticker' columns exist
    if 'cik' not in df.columns or 'ticker' not in df.columns:
        return None

    # Filter DataFrame for the given CIK
    ticker_series = df[df['cik'] == cik]['ticker']

    # If no tickers found, return None
    if ticker_series.empty:
        return None

    # Filter out None values from tickers
    tickers = [ticker for ticker in ticker_series.to_numpy() if ticker is not None]

    # Return a single ticker if only one found
    if len(tickers) == 1:
        return tickers[0]

    return tickers

def find_cik(ticker):
    """
    Find the CIK for a given ticker, checking both company and mutual fund/ETF data.

    :param ticker: String, the ticker symbol to look up
    :return: Integer, the CIK for the given ticker, or None if not found
    """
    # First, check company CIKs
    cik = find_company_cik(ticker)
    if cik is not None:
        return cik

    # If not found, check mutual fund/ETF CIKs
    return find_mutual_fund_cik(ticker)


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


def get_ticker_icon_url(ticker: str) -> str:
    """
    Get the URL for the icon of a company with the given ticker.
    """
    return f"https://raw.githubusercontent.com/nvstly/icons/main/ticker_icons/{ticker.upper()}.png"

@lru_cache(maxsize=4)
def get_icon_from_ticker(ticker: str) -> Optional[bytes]:
    """
    Download an icon for a given ticker as a PNG image, if available.

    WARNING: This function uses the nvstly/icons repository on GitHub to fetch the icons.
    The icons are not guaranteed to be available for all tickers.
    """

    if not isinstance(ticker, str):
        raise ValueError("The ticker must be a valid string.")

    if not ticker.isalpha():
        raise ValueError("The ticker must only contain alphabetic characters.")

    try:
        downloaded = download_file(
            f"https://raw.githubusercontent.com/nvstly/icons/main/ticker_icons/{ticker.upper()}.png", as_text=False)
        return downloaded
    except HTTPStatusError as e:
        # If the status code is 404, the icon is not available
        if e.response.status_code == 404:
            return None
        else:
            raise

def popular_us_stocks():
    df = (read_csv_from_package('popular_us_stocks.csv', dtype={'Cik': int})
          .set_index('Cik')
          )
    return df

class Exchange(Enum):

    Nasdaq = "Nasdaq"
    NYSE = "NYSE"
    OTC = "OTC"
    CBOE = "CBOE"

    def __str__(self):
        return self.value


