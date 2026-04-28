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
import random
import time
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
    score: float = 0.0
    file_type: Optional[str] = None
    file_description: Optional[str] = None
    document_id: Optional[str] = None
    items: List[str] = field(default_factory=list)
    sic: Optional[str] = None
    location: Optional[str] = None
    state: Optional[str] = None
    inc_state: Optional[str] = None

    def __repr__(self):
        parts = []
        if self.score:
            parts.append(f"{self.score:.1f}")
        parts.append(self.form)
        if self.file_type:
            parts.append(self.file_type)
        if self.company:
            parts.append(self.company)
        parts.append(self.filed)
        return f"EFTSResult({' | '.join(parts)})"

    def get_filing(self):
        """Load the full Filing object for this result."""
        from edgar import get_by_accession_number
        return get_by_accession_number(self.accession_number)


@dataclass
class Aggregation:
    """A single facet bucket from EFTS aggregations."""
    key: str
    count: int

    def __repr__(self):
        return f"Aggregation({self.key!r}, {self.count:,})"


@dataclass
class EFTSAggregations:
    """Faceted counts from an EFTS search."""
    entities: List[Aggregation] = field(default_factory=list)
    sics: List[Aggregation] = field(default_factory=list)
    states: List[Aggregation] = field(default_factory=list)
    forms: List[Aggregation] = field(default_factory=list)

    def __repr__(self):
        parts = []
        if self.entities:
            parts.append(f"entities={len(self.entities)}")
        if self.sics:
            parts.append(f"sics={len(self.sics)}")
        if self.states:
            parts.append(f"states={len(self.states)}")
        if self.forms:
            parts.append(f"forms={len(self.forms)}")
        return f"EFTSAggregations({', '.join(parts)})"

    def __rich__(self):
        from rich.table import Table
        from rich.columns import Columns
        from rich.panel import Panel

        tables = []
        facets = [
            ("Entities", self.entities),
            ("Forms", self.forms),
            ("SICs", self.sics),
            ("States", self.states),
        ]
        for title, buckets in facets:
            if not buckets:
                continue
            t = Table(title=title, show_header=True, header_style="bold", padding=(0, 1))
            t.add_column("Key", style="cyan")
            t.add_column("Count", style="dim", justify="right")
            for b in buckets[:5]:
                t.add_row(b.key, f"{b.count:,}")
            tables.append(t)

        if not tables:
            return Panel("[dim]No aggregations[/dim]", title="Aggregations")

        return Panel(Columns(tables, padding=(0, 2)), title="Aggregations")


@dataclass
class EFTSSearch:
    """Results from an EFTS full-text search."""
    query: str
    total: int
    results: List[EFTSResult] = field(default_factory=list)
    aggregations: Optional[EFTSAggregations] = None
    _params: dict = field(default_factory=dict, repr=False)
    _offset: int = field(default=0, repr=False)

    def __len__(self):
        return len(self.results)

    def __iter__(self):
        return iter(self.results)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return self._with_results(self.results[index])
        return self.results[index]

    def __repr__(self):
        return f"EFTSSearch(query='{self.query}', total={self.total}, showing={len(self.results)})"

    def _with_results(self, results: List[EFTSResult]) -> 'EFTSSearch':
        """Create a new EFTSSearch sharing this search's metadata but with different results."""
        return EFTSSearch(
            query=self.query,
            total=self.total,
            results=results,
            aggregations=self.aggregations,
            _params=self._params,
            _offset=self._offset,
        )

    def filter(
        self,
        *,
        form=None,
        sic=None,
        items=None,
        file_type=None,
        min_score=None,
        start_date=None,
        end_date=None,
        state=None,
    ) -> 'EFTSSearch':
        """Filter results. Returns new EFTSSearch with matching results.

        Args:
            form: Form type(s) to keep. String or list of strings. Exact match.
            sic: SIC code(s) to keep. String or list of strings. Exact match.
            items: 8-K item number(s) to keep. String or list of strings.
                   Matches if the result's items list contains any of the given items.
            file_type: File type prefix to match. E.g. "EX-10" matches "EX-10.1", "EX-10.05".
            min_score: Minimum score threshold (inclusive).
            start_date: Earliest filed date (YYYY-MM-DD, inclusive).
            end_date: Latest filed date (YYYY-MM-DD, inclusive).
            state: Business state code(s). String or list of strings. Exact match.
        """
        filtered = list(self.results)

        if form is not None:
            forms_set = {form} if isinstance(form, str) else set(form)
            filtered = [r for r in filtered if r.form in forms_set]

        if sic is not None:
            sics_set = {sic} if isinstance(sic, str) else set(sic)
            filtered = [r for r in filtered if r.sic in sics_set]

        if items is not None:
            items_set = {items} if isinstance(items, str) else set(items)
            filtered = [r for r in filtered if items_set & set(r.items)]

        if file_type is not None:
            filtered = [r for r in filtered if r.file_type and r.file_type.startswith(file_type)]

        if min_score is not None:
            filtered = [r for r in filtered if r.score >= min_score]

        if start_date is not None:
            filtered = [r for r in filtered if r.filed >= start_date]

        if end_date is not None:
            filtered = [r for r in filtered if r.filed <= end_date]

        if state is not None:
            states_set = {state} if isinstance(state, str) else set(state)
            filtered = [r for r in filtered if r.state in states_set]

        return self._with_results(filtered)

    def head(self, n: int) -> 'EFTSSearch':
        """Return a new EFTSSearch with only the first n results."""
        return self._with_results(self.results[:n])

    def tail(self, n: int) -> 'EFTSSearch':
        """Return a new EFTSSearch with only the last n results."""
        return self._with_results(self.results[-n:] if n else [])

    def sample(self, n: int) -> 'EFTSSearch':
        """Return a new EFTSSearch with n randomly sampled results."""
        n = min(n, len(self.results))
        sampled = random.sample(self.results, n) if n > 0 else []
        return self._with_results(sampled)

    def sort_by(self, field: str = "score", reverse: bool = True) -> 'EFTSSearch':
        """Sort results. Fields: score, filed, company, sic."""
        key_map = {
            "score": lambda r: r.score,
            "filed": lambda r: r.filed or "",
            "company": lambda r: (r.company or "").lower(),
            "sic": lambda r: r.sic or "",
        }
        key_fn = key_map.get(field)
        if key_fn is None:
            raise ValueError(f"Unknown sort field {field!r}. Choose from: {', '.join(key_map)}")
        sorted_results = sorted(self.results, key=key_fn, reverse=reverse)
        return self._with_results(sorted_results)

    @property
    def empty(self) -> bool:
        return len(self.results) == 0

    def next(self) -> Optional['EFTSSearch']:
        """Fetch next page of results. Returns None if exhausted."""
        if not self._params:
            return None
        next_offset = self._offset + len(self.results)
        if next_offset >= self.total:
            return None
        results, total, aggregations = _fetch_page(
            self._params, offset=next_offset, limit=min(100, self.total - next_offset)
        )
        return EFTSSearch(
            query=self.query,
            total=total,
            results=results,
            aggregations=aggregations,
            _params=self._params,
            _offset=next_offset,
        )

    def fetch_more(self, n: int = 100) -> 'EFTSSearch':
        """Fetch up to n more results, append to current. Returns new EFTSSearch with combined results.

        EFTS caps deep pagination at ~10,000; this method caps at 5,000 additional results.
        """
        if not self._params:
            return self

        n = min(n, 5000)
        all_results = list(self.results)
        collected = 0
        current_offset = self._offset + len(self.results)

        while collected < n and current_offset < self.total:
            page_size = min(100, n - collected, self.total - current_offset)
            if page_size <= 0:
                break
            results, total, aggregations = _fetch_page(
                self._params, offset=current_offset, limit=page_size
            )
            if not results:
                break
            all_results.extend(results)
            collected += len(results)
            current_offset += len(results)
            # Rate-limit between requests
            if collected < n and current_offset < self.total:
                time.sleep(0.1)

        return EFTSSearch(
            query=self.query,
            total=self.total,
            results=all_results,
            aggregations=self.aggregations,
            _params=self._params,
            _offset=self._offset,
        )

    def __rich__(self):
        from rich.table import Table
        from rich.panel import Panel

        table = Table(show_header=True, header_style="bold", padding=(0, 1))
        table.add_column("Score", style="dim", justify="right", width=6)
        table.add_column("Form", style="bold", width=10)
        table.add_column("Document", style="cyan", width=12)
        table.add_column("Company", min_width=30)
        table.add_column("Filed", width=12)
        table.add_column("Items", style="dim", width=15)
        table.add_column("Accession", width=22)

        for r in self.results:
            table.add_row(
                f"{r.score:.1f}" if r.score else "",
                r.form,
                r.file_type or "",
                r.company or "",
                r.filed,
                ", ".join(r.items) if r.items else "",
                r.accession_number,
            )

        title = f"EFTS: '{self.query}' ({self.total:,} total, showing {len(self.results)})"
        return Panel(table, title=title)

    def to_context(self, detail: str = 'standard') -> str:
        """AI-optimized context string.

        Args:
            detail: 'minimal' (~1 line), 'standard' (results table), 'full' (+ aggregations)
        """
        if detail == 'minimal':
            return f"EFTS: '{self.query}' — {self.total:,} total, {len(self.results)} shown"

        lines = [f"EFTS: '{self.query}' — {self.total:,} total, {len(self.results)} shown"]
        for r in self.results:
            items_str = f" | Items: {', '.join(r.items)}" if r.items else ""
            lines.append(
                f"  {r.score:.1f} | {r.form} | {r.file_type or ''} | {r.company or ''} | {r.filed}{items_str}"
            )
        remaining = self.total - len(self.results) - self._offset
        if remaining > 0:
            lines.append(f"  ... {remaining:,} more. Use .next() or .fetch_more(n)")

        if detail == 'full' and self.aggregations:
            aggs = self.aggregations
            if aggs.entities:
                top = ", ".join(f"{a.key}({a.count})" for a in aggs.entities[:5])
                lines.append(f"  Top entities: {top}")
            if aggs.sics:
                top = ", ".join(f"{a.key}({a.count})" for a in aggs.sics[:5])
                lines.append(f"  Top SICs: {top}")

        return "\n".join(lines)

    def __str__(self):
        return self.to_context()

    def __repr_html__(self):
        """HTML representation for Jupyter notebooks."""
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_page(params: dict, offset: int = 0, limit: int = 100):
    """Fetch a single page from EFTS. Returns (results, total, aggregations)."""
    from edgar.httprequests import get_with_retry
    import orjson

    request_params = dict(params)
    if offset > 0:
        request_params["from"] = offset

    response = get_with_retry(EFTS_BASE_URL, params=request_params)
    data = orjson.loads(response.content)

    hits = data.get("hits", {})
    total = hits.get("total", {}).get("value", 0)
    results = []

    for hit in hits.get("hits", []):
        result = _parse_hit(hit)
        results.append(result)
        if len(results) >= limit:
            break

    aggregations = _parse_aggregations(data.get("aggregations", {}))

    return results, total, aggregations


def _parse_hit(hit: dict) -> EFTSResult:
    """Parse a single EFTS hit into an EFTSResult."""
    source = hit.get("_source", {})

    names = source.get("display_names", [])
    ciks = source.get("ciks", [])
    sics = source.get("sics", [])
    biz_locations = source.get("biz_locations", [])
    biz_states = source.get("biz_states", [])
    inc_states = source.get("inc_states", [])

    # Extract document_id from _id (format: "accession:document_filename")
    raw_id = hit.get("_id", "")
    document_id = raw_id.split(":", 1)[1] if ":" in raw_id else None

    return EFTSResult(
        accession_number=_format_accession(source.get("adsh", "")),
        form=source.get("form", ""),
        filed=source.get("file_date", ""),
        company=names[0] if names else None,
        cik=str(ciks[0]) if ciks else None,
        period=source.get("period_ending"),
        score=hit.get("_score", 0.0) or 0.0,
        file_type=source.get("file_type"),
        file_description=source.get("file_description"),
        document_id=document_id,
        items=source.get("items", []) or [],
        sic=str(sics[0]) if sics else None,
        location=biz_locations[0] if biz_locations else None,
        state=biz_states[0] if biz_states else None,
        inc_state=inc_states[0] if inc_states else None,
    )


def _parse_aggregations(aggs_data: dict) -> EFTSAggregations:
    """Parse EFTS aggregation buckets into EFTSAggregations."""
    def _parse_buckets(filter_key: str) -> List[Aggregation]:
        filter_data = aggs_data.get(filter_key, {})
        return [
            Aggregation(key=b.get("key", ""), count=b.get("doc_count", 0))
            for b in filter_data.get("buckets", [])
        ]

    return EFTSAggregations(
        entities=_parse_buckets("entity_filter"),
        sics=_parse_buckets("sic_filter"),
        states=_parse_buckets("biz_states_filter"),
        forms=_parse_buckets("form_filter"),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_filings(
    query: str = "",
    *,
    forms: Optional[Union[str, List[str]]] = None,
    items: Optional[Union[str, List[str]]] = None,
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
        query: Search query string (searches filing text content). May be
               empty when ``items`` is provided, for a pure structured
               lookup (e.g. all 8-K filings with Item 1.05 in a date range).
        forms: Form type filter. Single string or list of strings.
               Examples: "10-K", ["10-K", "10-Q"], ["8-K"]
        items: 8-K item filter. Single item or list of items.
               Examples: "1.05", ["1.05", "2.02"]. Sent server-side to EFTS
               so the long tail isn't lost to client-side pagination caps.
        cik: CIK number to scope results to a specific filer.
             Accepts int or string (with or without leading zeros).
        ticker: Company ticker to scope results. Resolved to CIK internally.
        start_date: Start of filing date range (YYYY-MM-DD)
        end_date: End of filing date range (YYYY-MM-DD)
        limit: Maximum results to return (default 20, max 100)

    Returns:
        EFTSSearch object containing results

    Raises:
        ValueError: If neither ``query`` nor ``items`` is provided.

    Examples:
        >>> from edgar import search_filings
        >>> # Search all filings for a topic
        >>> results = search_filings("artificial intelligence")
        >>> # Scoped to form type
        >>> results = search_filings("cybersecurity incident", forms="8-K")
        >>> # Structured: all 8-K Item 1.05 (cybersecurity) filings in a range
        >>> results = search_filings(forms="8-K", items="1.05",
        ...                          start_date="2023-12-01", end_date="2024-12-31")
        >>> # Scoped to a company
        >>> results = search_filings("supply chain", ticker="AAPL")
        >>> # Date range
        >>> results = search_filings("tariff", forms=["10-K"], start_date="2024-01-01")
        >>> # Access results
        >>> for r in results:
        ...     print(r.form, r.company, r.filed)
        >>> # Load full filing
        >>> filing = results[0].get_filing()
        >>> # Filter results client-side
        >>> results.filter(form="10-K", min_score=5.0)
        >>> # Pagination
        >>> page2 = results.next()
        >>> all_results = results.fetch_more(200)
    """
    query = (query or "").strip()
    has_query = bool(query)
    has_items = bool(items)

    if not has_query and not has_items:
        raise ValueError(
            "Provide a search query, or an items filter (e.g. items='1.05')."
        )

    limit = min(max(limit, 1), 100)

    # Build request parameters. EFTS accepts q="" when other filters are set.
    params: dict = {"q": query}

    # Form type filter
    if forms:
        if isinstance(forms, str):
            forms = [forms]
        params["forms"] = ",".join(forms)

    # 8-K item filter (server-side)
    if items:
        if isinstance(items, str):
            items = [items]
        params["items"] = ",".join(items)

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

    # Fetch results via internal helper
    results, total, aggregations = _fetch_page(params, offset=0, limit=limit)

    return EFTSSearch(
        query=query,
        total=total,
        results=results,
        aggregations=aggregations,
        _params=params,
        _offset=0,
    )


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
