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


def read_parquet_from_package(parquet_filename:str):
    package_name = 'edgar.reference'

    with resources.path(package_name, parquet_filename) as parquet_path:
        df = pd.read_parquet(parquet_path)

    return df


@lru_cache(maxsize=1)
def cusip_ticker_mapping():
    """
    Download the CUSIP to Ticker mapping data from the SEC website.
    """
    df = read_parquet_from_package('ct.pq')
    return df