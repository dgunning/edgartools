from edgar.entities import *
from edgar.reference.tickers import get_cik_tickers
from typing import Iterable

__all__ = ['public_companies']

def public_companies() -> Iterable[Company]:
    """
    Iterate over all companies in the CIK tickers dataset
    """
    for row in get_cik_tickers().itertuples():
        yield Company(row.cik)