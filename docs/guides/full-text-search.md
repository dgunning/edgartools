---
description: Search the text content of SEC filings across EDGAR and grep for exact matches within individual filings.
---

# Full-Text Search & Grep

EdgarTools provides two complementary tools for searching the **text content** of SEC filings:

| Tool | Purpose | Scope |
|------|---------|-------|
| `search_filings()` | Find filings that mention a topic | All of EDGAR |
| `filing.grep()` | Find exact text within a filing | One filing's documents |

`search_filings()` answers "which filings talk about this?" using SEC's full-text search index.
`grep()` answers "where exactly does this text appear?" within a specific filing.

!!! note "How this relates to other search features"
    - **[Search & Filter](searching-filings.md)** — find filings by metadata (form type, date, company)
    - **[Advanced Search](../advanced-search.md)** — BM25-ranked search within a single parsed document
    - **This page** — search filing *text content* across EDGAR, and grep within filings

## Full-Text Search

`search_filings()` queries SEC's EFTS (EDGAR Full-Text Search) index — the same engine behind
the search box on sec.gov. It searches the actual text inside filings, not just metadata.

### Basic Usage

```python
from edgar import search_filings

# Find filings mentioning artificial intelligence
results = search_filings("artificial intelligence", forms=["10-K"])

# Scoped to a company
results = search_filings("supply chain risk", ticker="AAPL")

# Date range
results = search_filings("tariff impact", forms=["8-K"], start_date="2024-01-01")

# Use quotes for phrase matching
results = search_filings('"exclusive license" "trade secret"', forms=["8-K"])
```

Each result includes relevance score, document type, and metadata:

```python
r = results[0]
r.score           # 21.45 — relevance from EFTS
r.form            # '8-K'
r.company         # 'PyroTec, Inc.'
r.filed           # '2012-09-20'
r.file_type       # 'EX-10.05' — which document matched
r.items           # ['1.01', '2.01'] — 8-K item numbers
r.sic             # '6770' — SIC code
r.location        # 'Foster City, CA'
r.accession_number  # '0001193125-12-400000'
```

### Filtering Results

Filter the fetched results client-side without re-querying:

```python
results = search_filings('"going concern"', forms=["8-K", "10-K"])

# By SIC code (e.g. shell companies)
shells = results.filter(sic="6770")

# By 8-K item number
material = results.filter(items="1.01")  # Material agreements

# By relevance score
strong = results.filter(min_score=15.0)

# By document type (prefix match)
exhibits = results.filter(file_type="EX-10")  # Matches EX-10.1, EX-10.05, etc.

# By date range
recent = results.filter(start_date="2024-01-01", end_date="2024-12-31")

# By state
california = results.filter(state="CA")

# Chain filters
targeted = results.filter(sic="6770").filter(items="1.01").filter(min_score=10.0)
```

Sort, slice, and sample:

```python
# Sort by score (default), date, company, or SIC
by_date = results.sort_by("filed", reverse=False)  # Oldest first
by_score = results.sort_by("score")                  # Highest relevance first

# Slice and sample
top5 = results.head(5)
last5 = results.tail(5)
random10 = results.sample(10)

# Python slicing
page = results[5:15]
```

### Aggregations

Every search returns faceted counts — a summary of who and what matched without downloading filings:

```python
results = search_filings('"exclusive license" "trade secret"', forms=["8-K"])

# Top entities by hit count
for a in results.aggregations.entities[:5]:
    print(f"{a.key}: {a.count} filings")

# Top SIC codes
for a in results.aggregations.sics[:5]:
    print(f"SIC {a.key}: {a.count} filings")

# Also available: .states, .forms
```

This is useful for exploratory analysis — understand the landscape before drilling into individual filings.

### Pagination

`search_filings()` returns one page of results (default 20, max 100 per call). Paginate to get more:

```python
# Get first 100 results
results = search_filings("cybersecurity incident", forms=["8-K"], limit=100)
print(f"{results.total:,} total matches, showing {len(results)}")

# Fetch the next page
page2 = results.next()  # Returns None when exhausted

# Or fetch many more at once (up to 5,000 additional)
all_results = results.fetch_more(500)  # Accumulates 500 more, rate-limited
print(f"Now have {len(all_results)} results")
```

### Loading a Filing

Each result can load its full Filing object for deeper analysis:

```python
r = results[0]
filing = r.get_filing()  # Loads the full Filing
tenk = filing.obj()       # Parse as TenK, EightK, etc.
```

## Grep

`grep()` is the universal exact-match search for content within a filing. It searches all
documents (primary filing + exhibits) by default, like `grep -ri` on a directory.

Every AI agent has grep semantics burned into its training. Zero learning curve.

### Filing.grep()

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="10-K").latest(1)

# Search all documents in the filing
matches = filing.grep("going concern")
print(f"{len(matches)} matches found")

for m in matches:
    print(m)
    # primary:  ...substantial doubt about the entity's ability to continue as a going concern...
    # EX-99.1:  ...the report includes a going concern qualification...
```

Each match includes:

```python
m = matches[0]
m.location   # "primary", "EX-10.1", "EX-99.1", etc.
m.match      # The matched text
m.context    # Surrounding text (~100 chars each side)
```

#### Search a Specific Document

```python
# Only the primary filing document
filing.grep("risk factor", document="primary")

# Only a specific exhibit
filing.grep("intellectual property", document="EX-10.1")
```

#### Regex Support

```python
# Regex for flexible matching
filing.grep(r"Level\s+3", regex=True)              # "Level 3", "Level  3"
filing.grep(r"(?:right|option) of first refusal", regex=True)
```

### Notes.grep()

`Notes.search()` matches note **titles**. `Notes.grep()` searches note **content** — the full
narrative text of each note.

```python
tenk = filing.obj()

# Search all note content
matches = tenk.notes.grep("going concern")
for m in matches:
    print(m)
    # Note 1 - Organization:  ...conditions raise substantial doubt about going concern...

# Fair value hierarchy
matches = tenk.notes.grep("Level 3")

# Regex in notes
matches = tenk.notes.grep(r"intangible\s+asset", regex=True)
```

### Report Object grep (TenK, TenQ, EightK)

Report objects delegate to their underlying filing:

```python
tenk = filing.obj()

# Same as filing.grep() — searches all documents
tenk.grep("going concern")

# Narrow to primary document
tenk.grep("going concern", document="primary")
```

### grep vs search

Both coexist — they serve different purposes:

| | `grep()` | `search()` |
|---|---|---|
| **Mode** | Exact match (string or regex) | BM25 fuzzy ranking |
| **Returns** | Every match with location + context | Best sections ranked by relevance |
| **Case** | Case-insensitive by default | Case-insensitive |
| **Use case** | "Does this filing mention 'going concern'?" | "What does this filing say about debt?" |
| **Agent use** | Verification, due diligence checks | Exploration, topic discovery |

An agent checking for "Level 3" or "right of first refusal" wants grep.
A human exploring "what about debt?" wants search (it also finds "borrowings", "credit facility").

## Putting It Together

A typical analytical workflow uses both tools:

```python
from edgar import search_filings, Company

# Step 1: Find filings across EDGAR
results = search_filings('"exclusive license" "trade secret"', forms=["8-K"])
print(f"{results.total:,} filings mention these terms")

# Step 2: Triage from metadata
material = results.filter(items="1.01")       # Material agreements
high_score = results.filter(min_score=15.0)    # Strong matches

# Step 3: Check who shows up most
for a in results.aggregations.entities[:5]:
    print(f"{a.key}: {a.count} filings")

# Step 4: Deep dive on an interesting hit
filing = results[0].get_filing()
tenk = Company(results[0].cik).get_filings(form="10-K").latest(1).obj()

# Step 5: Grep the 10-K for related terms
tenk.grep("going concern")
tenk.grep("Level 3")
tenk.notes.grep("intangible asset")
```

## API Reference

### search_filings()

```python
search_filings(
    query: str,                    # Search text (supports quoted phrases)
    *,
    forms: str | list = None,      # Form type filter: "10-K", ["8-K", "10-K"]
    cik: str | int = None,         # CIK number
    ticker: str = None,            # Ticker symbol (resolved to CIK)
    start_date: str = None,        # Filing date start (YYYY-MM-DD)
    end_date: str = None,          # Filing date end (YYYY-MM-DD)
    limit: int = 20,               # Results per page (max 100)
) -> EFTSSearch
```

### EFTSSearch

| Method | Returns | Description |
|--------|---------|-------------|
| `filter(...)` | `EFTSSearch` | Filter by form, sic, items, file_type, min_score, dates, state |
| `sort_by(field)` | `EFTSSearch` | Sort by "score", "filed", "company", or "sic" |
| `head(n)` | `EFTSSearch` | First n results |
| `tail(n)` | `EFTSSearch` | Last n results |
| `sample(n)` | `EFTSSearch` | Random n results |
| `next()` | `EFTSSearch \| None` | Next page from EFTS |
| `fetch_more(n)` | `EFTSSearch` | Fetch up to n more results (max 5,000) |
| `.aggregations` | `EFTSAggregations` | Faceted counts (.entities, .sics, .states, .forms) |
| `.total` | `int` | Total matches on EFTS server |
| `.empty` | `bool` | True if no results |

### EFTSResult

| Field | Type | Description |
|-------|------|-------------|
| `accession_number` | `str` | Filing accession number |
| `form` | `str` | Form type |
| `filed` | `str` | Filing date (YYYY-MM-DD) |
| `company` | `str` | Company name |
| `cik` | `str` | CIK number |
| `score` | `float` | EFTS relevance score |
| `file_type` | `str` | Document type that matched (EX-10.1, 8-K, etc.) |
| `file_description` | `str` | Human-readable document description |
| `document_id` | `str` | Specific document filename within the filing |
| `items` | `list[str]` | 8-K item numbers |
| `sic` | `str` | Primary SIC code |
| `location` | `str` | Business location |
| `state` | `str` | Business state code |
| `get_filing()` | `Filing` | Load the full Filing object |

### grep()

```python
# On Filing
filing.grep(
    pattern: str,              # Text to search for
    *,
    regex: bool = False,       # Treat pattern as regex
    document: str = None,      # "primary", "EX-10.1", etc.
) -> GrepResult

# On Notes
notes.grep(
    pattern: str,
    *,
    regex: bool = False,
) -> GrepResult

# On TenK, TenQ, EightK (delegates to filing.grep)
tenk.grep(pattern, *, regex=False, document=None) -> GrepResult
```

### GrepResult / GrepMatch

`GrepResult` is list-like (`len()`, iteration, indexing, `bool()`).

| GrepMatch field | Type | Description |
|-----------------|------|-------------|
| `location` | `str` | "primary", "EX-10.1", note title, etc. |
| `match` | `str` | The matched text |
| `context` | `str` | Surrounding text (~100 chars each side) |
