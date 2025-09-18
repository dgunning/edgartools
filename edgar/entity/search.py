"""
Search functionality for SEC entities.
This module provides functions and classes for searching for SEC entities.
"""
from functools import lru_cache
from typing import Any, Dict, List

import pandas as pd
from rich import box
from rich.table import Column, Table

from edgar.entity import Company
from edgar.entity.tickers import get_company_tickers
from edgar.richtools import repr_rich
from edgar.search.datasearch import FastSearch, company_ticker_preprocess, company_ticker_score

__all__ = [
    'find_company',
    'CompanySearchResults',
    'CompanySearchIndex'
]


class CompanySearchResults:
    """
    Results from a company search.
    """
    def __init__(self, query: str,
                 search_results: List[Dict[str, Any]]):
        self.query: str = query
        self.results: pd.DataFrame = pd.DataFrame(search_results, columns=['cik', 'ticker', 'company', 'score'])

    @property
    def tickers(self):
        return self.results.ticker.tolist()

    @property
    def ciks(self):
        return self.results.cik.tolist()

    @property
    def empty(self):
        return self.results.empty

    def __len__(self):
        return len(self.results)

    def __getitem__(self, item):
        if 0 <= item < len(self):
            row = self.results.iloc[item]
            cik: int = int(row.cik)
            return Company(cik)

    def __rich__(self):
        table = Table(Column(""),
                      Column("Ticker", justify="left"),
                      Column("Name", justify="left"),
                      Column("Score", justify="left"),
                      title=f"Search results for '{self.query}'",
                      box=box.SIMPLE)
        for index, row in enumerate(self.results.itertuples()):
            table.add_row(str(index), row.ticker.rjust(6), row.company, f"{int(row.score)}%")
        return table

    def __repr__(self):
        return repr_rich(self.__rich__())


class CompanySearchIndex(FastSearch):
    """
    Search index for companies.
    """
    def __init__(self):
        data = get_company_tickers(as_dataframe=False)
        super().__init__(data, ['company', 'ticker'],
                         preprocess_func=company_ticker_preprocess,
                         score_func=company_ticker_score)

    def search(self, query: str, top_n: int = 10, threshold: float = 60) -> CompanySearchResults:
        results = super().search(query, top_n, threshold)
        return CompanySearchResults(query=query, search_results=results)

    def __len__(self):
        return len(self.data)

    def __hash__(self):
        # Combine column names and last 10 values in the 'company' column to create a hash
        column_names = tuple(self.data[0].keys())
        last_10_companies = tuple(entry['company'] for entry in self.data[-10:])
        return hash((column_names, last_10_companies))

    def __eq__(self, other):
        if not isinstance(other, CompanySearchIndex):
            return False
        return (self.data[-10:], tuple(self.data[0].keys())) == (other.data[-10:], tuple(other.data[0].keys()))


@lru_cache(maxsize=1)
def _get_company_search_index():
    """Get the company search index."""
    return CompanySearchIndex()


@lru_cache(maxsize=16)
def find_company(company: str, top_n: int = 10):
    """
    Find a company by name.

    Args:
        company: The company name or ticker to search for
        top_n: The maximum number of results to return

    Returns:
        CompanySearchResults: The search results
    """
    return _get_company_search_index().search(company, top_n=top_n)
