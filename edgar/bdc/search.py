"""
Search functionality for BDC (Business Development Company) entities.

Provides fuzzy search across BDC names with ticker enrichment from SEC data.
"""
import logging
from functools import lru_cache
from typing import Any, Dict, List, Optional

import pandas as pd
import pyarrow as pa
from rich import box
from rich.table import Column, Table

from edgar.richtools import repr_rich
from edgar.search.datasearch import FastSearch

log = logging.getLogger(__name__)

__all__ = [
    'find_bdc',
    'BDCSearchResults',
    'BDCSearchIndex',
]


def _bdc_preprocess(text: str) -> str:
    """
    Preprocess BDC names for search indexing.

    Removes common company suffixes and normalizes text.
    """
    from unidecode import unidecode
    import re

    text = unidecode(text.lower())
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # Remove common BDC/company terms
    common_terms = [
        'llc', 'inc', 'corp', 'corporation', 'ltd', 'limited',
        'company', 'co', 'lp', 'bdc', 'capital', 'investment',
        'investments', 'fund', 'partners', 'holdings'
    ]
    words = [w for w in text.split() if w not in common_terms]
    return ' '.join(words) if words else text


def _bdc_score(query: str, value: str, column: str) -> float:
    """
    Calculate match score between query and BDC field value.

    Uses different scoring strategies for tickers vs names.
    """
    from rapidfuzz import fuzz

    query = query.upper()
    value = value.upper()

    # For short queries (likely tickers), use exact/prefix matching
    if len(query) <= 5 and column == 'ticker':
        if query == value:
            return 100  # Exact match
        elif value.startswith(query):
            return 90 + (10 * len(query) / len(value))
        else:
            return 0

    # For names, match on words rather than on the whole string. A BDC's name
    # is longer than the part of it anyone types, and `fuzz.ratio` charges the
    # query for that difference: "ARES" against "ARES CORE INFRASTRUCTURE"
    # scores 28.6 and falls under the 50 threshold, while "BLACKSTONE" against
    # "BLACKSTONE PRIVATE CREDIT" scores 57.1 and survives — so whether a search
    # worked depended on how long the query happened to be relative to the name,
    # not on whether it matched. The candidate set is already built from an
    # exact word index, so a name that reaches scoring has matched a whole word.
    #
    # `token_set_ratio` and not `partial_ratio`: the latter scores "ARES"
    # against "ANTARES PRIVATE CREDIT" at 100, since ARES is a substring of
    # ANTARES. Token matching gives that pair 30.8 and keeps it out.
    score = fuzz.token_set_ratio(query, value)
    if score < 100:
        return score

    # Every exact word hit scores 100, which leaves ranking to chance. Break the
    # tie toward the closer whole name — "ARES" should rank ARES CAPITAL CORP,
    # which preprocesses to exactly "ARES", above ARES CORE INFRASTRUCTURE. The
    # nudge stays under a point and only ever applies at 100, so it cannot move
    # a match across the threshold.
    return 100 - (100 - fuzz.ratio(query, value)) / 100


class BDCSearchResults:
    """
    Results from a BDC search.

    Provides easy access to BDCEntity objects from search results.
    """

    def __init__(self, query: str, search_results: List[Dict[str, Any]]):
        self.query = query
        self.results = pd.DataFrame(
            search_results,
            columns=['cik', 'ticker', 'name', 'state', 'is_active', 'score']
        )

    @property
    def ciks(self) -> List[int]:
        """Get list of CIKs from search results."""
        return self.results['cik'].tolist()

    @property
    def tickers(self) -> List[str]:
        """Get list of tickers from search results."""
        return self.results['ticker'].tolist()

    @property
    def empty(self) -> bool:
        """Check if results are empty."""
        return self.results.empty

    def __len__(self) -> int:
        return len(self.results)

    def __getitem__(self, item):
        """Get BDCEntity by index."""
        if 0 <= item < len(self):
            from edgar.bdc.reference import get_bdc_list, lookup_bdc
            row = self.results.iloc[item]
            cik = int(row['cik'])
            # A row from a lookback-year index (find_bdc(..., lookback_years=N))
            # is absent from the latest report; resolve it the way the index
            # found it rather than returning None.
            return get_bdc_list().get_by_cik(cik) or lookup_bdc(cik=cik)
        raise IndexError(f"Index {item} out of range")

    def __iter__(self):
        """Iterate over BDCEntity objects."""
        for i in range(len(self)):
            yield self[i]

    def __rich__(self):
        table = Table(
            Column(""),
            Column("Ticker", justify="left"),
            Column("Name", justify="left"),
            Column("State", justify="center"),
            Column("Status", justify="center"),
            Column("Score", justify="right"),
            title=f"BDC Search: '{self.query}'",
            box=box.SIMPLE
        )

        for index, row in enumerate(self.results.itertuples()):
            ticker = row.ticker if row.ticker else ""
            status = "[green]Active[/green]" if row.is_active else "[red]Inactive[/red]"
            name = row.name if row.is_active else f"[dim]{row.name}[/dim]"

            table.add_row(
                str(index),
                ticker.rjust(6),
                name,
                row.state or "",
                status,
                f"{int(row.score)}%"
            )

        return table

    def __repr__(self):
        return repr_rich(self.__rich__())


class BDCSearchIndex(FastSearch):
    """
    Search index for Business Development Companies.

    Indexes BDC names and enriches with ticker symbols from SEC data.
    """

    def __init__(self, lookback_years: int = 0):
        """
        Build the index.

        Args:
            lookback_years: Also index this many report years before the
                latest one (default 0: the latest report only). The SEC's
                annual BDC Report can drop an active BDC from one year's
                snapshot (Ares Capital Corp is in 2024 and 2025 but not 2026),
                so a name search that should agree with `lookup_bdc` must
                cover the same years. One row per CIK; the latest year's row
                wins.
        """
        # Get BDC list (across report years) and enrich with tickers
        bdcs = _bdcs_across_report_years(lookback_years)
        ticker_map = self._get_ticker_map()

        # Build records with ticker enrichment
        records = []
        for bdc in bdcs:
            ticker = ticker_map.get(bdc.cik, "")
            records.append({
                'cik': bdc.cik,
                'ticker': ticker,
                'name': bdc.name,
                'state': bdc.state or "",
                'is_active': bdc.is_active,
            })

        # Create PyArrow table
        data = pa.table({
            'cik': pa.array([r['cik'] for r in records], type=pa.int64()),
            'ticker': pa.array([r['ticker'] for r in records], type=pa.string()),
            'name': pa.array([r['name'] for r in records], type=pa.string()),
            'state': pa.array([r['state'] for r in records], type=pa.string()),
            'is_active': pa.array([r['is_active'] for r in records], type=pa.bool_()),
        })

        # Index on name and ticker
        super().__init__(
            data,
            ['name', 'ticker'],
            preprocess_func=_bdc_preprocess,
            score_func=_bdc_score
        )

    @staticmethod
    def _get_ticker_map() -> Dict[int, str]:
        """
        Get CIK to ticker mapping from SEC data.

        Returns:
            Dictionary mapping CIK to ticker symbol.
        """
        try:
            from edgar.reference.tickers import get_company_tickers
            df = get_company_tickers(as_dataframe=True)
            return dict(zip(df['cik'].astype(int), df['ticker']))
        except Exception:
            return {}

    def search(self, query: str, top_n: int = 10, threshold: float = 50) -> BDCSearchResults:
        """
        Search for BDCs by name or ticker.

        Args:
            query: Search query (name or ticker)
            top_n: Maximum number of results
            threshold: Minimum score threshold (0-100)

        Returns:
            BDCSearchResults with matching BDCs
        """
        results = super().search(query, top_n, threshold)
        return BDCSearchResults(query=query, search_results=results)

    def __len__(self):
        return len(self.data)


def _bdcs_across_report_years(lookback_years: int = 0) -> list:
    """BDCs from the latest report plus `lookback_years` prior years, one per CIK.

    Walks the same years, in the same order, as `lookup_bdc` (latest first,
    the latest via the bare `get_bdc_list()` so it shares that call's cache
    entry), keeping the first -- i.e. the most recent -- row seen for each
    CIK. A prior year that cannot be fetched is skipped with a warning, as
    `lookup_bdc` does; the latest year is required.
    """
    from edgar.bdc.reference import get_bdc_list, get_latest_bdc_report_year

    bdcs = list(get_bdc_list())
    if lookback_years <= 0:
        return bdcs

    seen = {bdc.cik for bdc in bdcs}
    latest_year = get_latest_bdc_report_year()
    for year in range(latest_year - 1, latest_year - lookback_years - 1, -1):
        try:
            prior = get_bdc_list(year)
        except Exception as e:
            log.warning(
                "Could not fetch the %d BDC report for the search index (%s: %s); skipping.",
                year, type(e).__name__, e,
            )
            continue
        for bdc in prior:
            if bdc.cik not in seen:
                seen.add(bdc.cik)
                bdcs.append(bdc)
    return bdcs


@lru_cache(maxsize=4)
def _get_bdc_search_index(lookback_years: int = 0) -> BDCSearchIndex:
    """Get cached BDC search index (one per `lookback_years`)."""
    return BDCSearchIndex(lookback_years=lookback_years)


@lru_cache(maxsize=16)
def find_bdc(query: str, top_n: int = 10, lookback_years: int = 0) -> BDCSearchResults:
    """
    Search for a BDC by name or ticker.

    Supports fuzzy matching on BDC names and exact/prefix matching on tickers.

    Args:
        query: The BDC name or ticker to search for
        top_n: Maximum number of results to return
        lookback_years: Also search this many report years before the latest
            (default 0: latest report only). Use the same value as
            `lookup_bdc`'s `lookback_years` to find BDCs the latest SEC BDC
            Report omits; each CIK appears once, from its most recent year.

    Returns:
        BDCSearchResults with matching BDCs

    Example:
        >>> from edgar.bdc import find_bdc
        >>> results = find_bdc("Ares")
        >>> results[0]
        BDCEntity(name='ARES CAPITAL CORP', ...)

        >>> results = find_bdc("ARCC")
        >>> results[0].name
        'ARES CAPITAL CORP'
    """
    return _get_bdc_search_index(lookback_years).search(query, top_n=top_n)
