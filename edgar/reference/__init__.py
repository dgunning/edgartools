import sys
import pandas as pd

# Dynamic import based on Python version
if sys.version_info >= (3, 9):
    from importlib import resources
else:
    import importlib_resources as resources

from functools import lru_cache

__all__ = ['states']

# A dict of state abbreviations and their full names
states = {

    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
}


def read_parquet_from_package(parquet_filename: str):
    package_name = 'edgar.reference'

    with resources.path(package_name, parquet_filename) as parquet_path:
        df = pd.read_parquet(parquet_path)

    return df


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
