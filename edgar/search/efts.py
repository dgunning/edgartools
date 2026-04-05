"""
EDGAR Full-Text Search (EFTS)

Search the actual text content of SEC filings using EDGAR's
full-text search index at efts.sec.gov.

Unlike get_filings() which searches filing metadata (form type, date, CIK),
this searches the text inside filings — find filings that mention specific
topics, products, risks, legal terms, etc.

Usage:
    >>> from edgar import search_filings
    >>> results = search_filings("artificial intelligence", forms=["10-K"])
    >>> results = search_filings("cybersecurity incident", forms=["8-K"], start_date="2024-01-01")
    >>> results = search_filings("tariff impact", cik="320193")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Union

logger = logging.getLogger(__name__)

EFTS_BASE_URL = "https://efts.sec.gov/LATEST/search-index"


@dataclass
class EFTSResult:
    """A single filing result from EFTS full-text search."""
    accession_number: str
    form: str
    filed: str
    company: Optional[str] = None
    cik: Optional[str] = None
    period: Optional[str] = None

    def __repr__(self):
        parts = [f"{self.form}"]
        if self.company:
            parts.append(self.company)
        parts.append(self.filed)
        return f"EFTSResult({' | '.join(parts)})"

    def get_filing(self):
        """Load the full Filing object for this result."""
        from edgar import get_by_accession_number
        return get_by_accession_number(self.accession_number)


@dataclass
class EFTSSearch:
    """Results from an EFTS full-text search."""
    query: str
    total: int
    results: List[EFTSResult] = field(default_factory=list)

    def __len__(self):
        return len(self.results)

    def __iter__(self):
        return iter(self.results)

    def __getitem__(self, index):
        return self.results[index]

    def __repr__(self):
        return f"EFTSSearch(query='{self.query}', total={self.total}, showing={len(self.results)})"

    def __rich__(self):
        from rich.table import Table
        from rich.panel import Panel

        table = Table(show_header=True, header_style="bold", padding=(0, 1))
        table.add_column("Form", style="bold", width=10)
        table.add_column("Company", min_width=30)
        table.add_column("Filed", width=12)
        table.add_column("Accession", width=22)

        for r in self.results:
            table.add_row(
                r.form,
                r.company or "",
                r.filed,
                r.accession_number,
            )

        title = f"EFTS: '{self.query}' ({self.total:,} matches, showing {len(self.results)})"
        return Panel(table, title=title)

    def __repr_html__(self):
        """HTML representation for Jupyter notebooks."""
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())


def search_filings(
    query: str,
    *,
    forms: Optional[Union[str, List[str]]] = None,
    cik: Optional[Union[str, int]] = None,
    ticker: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 20,
) -> EFTSSearch:
    """
    Full-text search across SEC filing content via EDGAR EFTS.

    Searches the actual text of filings — not just metadata. Find filings
    that mention specific topics, products, risks, legal terms, etc.

    Args:
        query: Search query string (searches filing text content)
        forms: Form type filter. Single string or list of strings.
               Examples: "10-K", ["10-K", "10-Q"], ["8-K"]
        cik: CIK number to scope results to a specific filer.
             Accepts int or string (with or without leading zeros).
        ticker: Company ticker to scope results. Resolved to CIK internally.
        start_date: Start of filing date range (YYYY-MM-DD)
        end_date: End of filing date range (YYYY-MM-DD)
        limit: Maximum results to return (default 20, max 100)

    Returns:
        EFTSSearch object containing results

    Raises:
        ValueError: If query is empty

    Examples:
        >>> from edgar import search_filings
        >>> # Search all filings for a topic
        >>> results = search_filings("artificial intelligence")
        >>> # Scoped to form type
        >>> results = search_filings("cybersecurity incident", forms="8-K")
        >>> # Scoped to a company
        >>> results = search_filings("supply chain", ticker="AAPL")
        >>> # Date range
        >>> results = search_filings("tariff", forms=["10-K"], start_date="2024-01-01")
        >>> # Access results
        >>> for r in results:
        ...     print(r.form, r.company, r.filed)
        >>> # Load full filing
        >>> filing = results[0].get_filing()
    """
    if not query or not query.strip():
        raise ValueError("Search query cannot be empty")

    limit = min(max(limit, 1), 100)

    # Build request parameters
    params: dict = {
        "q": query.strip(),
    }

    # Form type filter
    if forms:
        if isinstance(forms, str):
            forms = [forms]
        params["forms"] = ",".join(forms)

    # Date range
    if start_date or end_date:
        params["dateRange"] = "custom"
        if start_date:
            params["startdt"] = start_date
        if end_date:
            params["enddt"] = end_date

    # Resolve CIK from ticker if given
    resolved_cik = None
    if ticker:
        resolved_cik = _resolve_cik_from_ticker(ticker)
    elif cik is not None:
        resolved_cik = str(cik).strip().zfill(10)

    if resolved_cik:
        params["ciks"] = resolved_cik

    # Make the EFTS API request using EdgarTools HTTP infrastructure
    from edgar.httprequests import get_with_retry
    import orjson

    response = get_with_retry(EFTS_BASE_URL, params=params)
    data = orjson.loads(response.content)

    # Parse results
    hits = data.get("hits", {})
    total = hits.get("total", {}).get("value", 0)
    results = []

    for hit in hits.get("hits", []):
        source = hit.get("_source", {})

        names = source.get("display_names", [])
        ciks = source.get("ciks", [])

        result = EFTSResult(
            accession_number=_format_accession(source.get("adsh", "")),
            form=source.get("form", ""),
            filed=source.get("file_date", ""),
            company=names[0] if names else None,
            cik=str(ciks[0]) if ciks else None,
            period=source.get("period_ending"),
        )
        results.append(result)

        if len(results) >= limit:
            break

    return EFTSSearch(query=query, total=total, results=results)


def _resolve_cik_from_ticker(ticker: str) -> str:
    """Resolve a ticker symbol to a zero-padded 10-digit CIK."""
    from edgar import Company

    company = Company(ticker)
    return str(company.cik).zfill(10)


def _format_accession(adsh: str) -> str:
    """Format EFTS accession number (no dashes) to standard format (with dashes)."""
    adsh = adsh.replace("-", "")
    if len(adsh) == 18:
        return f"{adsh[:10]}-{adsh[10:12]}-{adsh[12:]}"
    return adsh
