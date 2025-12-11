# EdgarTools Company Dataset & Subset System
## Technical Guide for edgar.tools SAAS Integration

**Version**: 1.0
**Last Updated**: 2025-11-23
**Target Audience**: Developers building on edgartools for edgar.tools SAAS platform

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Data Sources & Schema](#data-sources--schema)
4. [The Build Process](#the-build-process)
5. [Company Subsets](#company-subsets)
6. [Integration Patterns](#integration-patterns)
7. [Database Migration Guide](#database-migration-guide)
8. [Use Cases](#use-cases)
9. [Performance Considerations](#performance-considerations)
10. [API Reference](#api-reference)

---

## Overview

The company dataset and subset system provides a high-performance, filterable catalog of all SEC-registered companies (~562K entities) with rich metadata. It's designed for applications requiring fast company selection, watchlist management, and workflow filtering.

### Key Features

- **Comprehensive Coverage**: ~562,413 companies (after filtering ~40% individual filers)
- **Rich Metadata**: CIK, ticker, name, exchange, SIC code, state of incorporation, fiscal year end, entity type, EIN
- **Dual Storage Formats**:
  - Parquet (5-20 MB) - PyArrow compute API, <100ms load
  - DuckDB (287 MB) - SQL interface, <1ms queries with indexes
- **Smart Filtering**: Individual filer detection to focus on companies vs. persons
- **Flexible Subsets**: Pre-built functions for industry, exchange, popularity, state-based filtering
- **Build Performance**: ~30 seconds from raw submissions data

### Design Philosophy

1. **Lazy Loading**: Dataset builds on first access, then caches
2. **Two Modes**:
   - Standard (13K companies with tickers) - fast, minimal metadata
   - Comprehensive (562K companies) - full SEC submissions data with rich metadata
3. **Fluent API**: Chainable `CompanySubset` builder for complex filters
4. **DataFrame Output**: Pandas-compatible for easy integration

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    edgar.tools SAAS                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │ Watchlists │  │ Workflows  │  │  Alerts    │            │
│  └──────┬─────┘  └──────┬─────┘  └──────┬─────┘            │
└─────────┼────────────────┼────────────────┼─────────────────┘
          │                │                │
          └────────────────┴────────────────┘
                           │
┌──────────────────────────┼─────────────────────────────────┐
│         EdgarTools Library│                                 │
│                           ▼                                 │
│  ┌───────────────────────────────────────┐                 │
│  │    edgar.reference.company_subsets    │                 │
│  │  ┌─────────────────────────────────┐  │                 │
│  │  │  CompanySubset (Fluent API)     │  │                 │
│  │  │  - from_exchange()              │  │                 │
│  │  │  - from_industry()              │  │                 │
│  │  │  - from_state()                 │  │                 │
│  │  │  - filter_by() / sample()       │  │                 │
│  │  └─────────────────────────────────┘  │                 │
│  │  ┌─────────────────────────────────┐  │                 │
│  │  │  Selection Functions            │  │                 │
│  │  │  - get_companies_by_exchanges() │  │                 │
│  │  │  - get_companies_by_industry()  │  │                 │
│  │  │  - get_popular_companies()      │  │                 │
│  │  └─────────────────────────────────┘  │                 │
│  └───────────────┬───────────────────────┘                 │
│                  │                                          │
│  ┌───────────────▼───────────────────────┐                 │
│  │  edgar.reference.company_dataset      │                 │
│  │  ┌─────────────────────────────────┐  │                 │
│  │  │  get_company_dataset()          │  │                 │
│  │  │  - In-memory cache              │  │                 │
│  │  │  - Lazy builds on first access  │  │                 │
│  │  └─────────────────────────────────┘  │                 │
│  │  ┌─────────────────────────────────┐  │                 │
│  │  │  Build Functions                │  │                 │
│  │  │  - build_company_dataset_*()    │  │                 │
│  │  │  - is_individual_from_json()    │  │                 │
│  │  └─────────────────────────────────┘  │                 │
│  └───────────────┬───────────────────────┘                 │
│                  │                                          │
│  ┌───────────────▼───────────────────────┐                 │
│  │         Storage Layer                 │                 │
│  │  ~/.edgar/                            │                 │
│  │    ├── companies.pq    (Parquet)      │                 │
│  │    ├── companies.duckdb (optional)    │                 │
│  │    └── submissions/    (source data)  │                 │
│  │         ├── CIK0000001.json           │                 │
│  │         ├── CIK0000002.json           │                 │
│  │         └── ... (~937K files)         │                 │
│  └───────────────┬───────────────────────┘                 │
└──────────────────┼─────────────────────────────────────────┘
                   │
┌──────────────────▼─────────────────────────────────────────┐
│              SEC EDGAR Data Source                         │
│  https://www.sec.gov/Archives/edgar/daily-index/bulkdata/  │
│    - submissions.zip (~500 MB compressed)                  │
└────────────────────────────────────────────────────────────┘
```

### Data Flow

```
1. Initial Download
   SEC submissions.zip → edgar.storage.download_submissions()
   → ~/.edgar/submissions/ (937K CIK*.json files)

2. Dataset Build (first use or rebuild)
   ~/.edgar/submissions/*.json → build_company_dataset_parquet()
   → ~/.edgar/companies.pq (5-20 MB Parquet)
   → In-memory cache (PyArrow Table)

3. Query/Filter
   get_company_dataset() → PyArrow Table
   → CompanySubset operations → Filtered DataFrame
```

---

## Data Sources & Schema

### Source: SEC Submissions Data

**Location**: `https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip`

**Format**: JSON files, one per CIK (Central Index Key)

**Sample Submission JSON** (`CIK0001318605.json` - Tesla):
```json
{
  "cik": "0001318605",
  "name": "Tesla, Inc.",
  "tickers": ["TSLA"],
  "exchanges": ["Nasdaq"],
  "sic": "3711",
  "sicDescription": "MOTOR VEHICLES & PASSENGER CAR BODIES",
  "stateOfIncorporation": "DE",
  "stateOfIncorporationDescription": "DE",
  "fiscalYearEnd": "1231",
  "entityType": "operating",
  "ein": "912197729",
  "filings": {
    "recent": {
      "form": ["10-K", "10-Q", "8-K", ...],
      "filingDate": ["2024-01-26", ...],
      ...
    }
  }
}
```

### Processed Schema

**Standard Mode** (13K companies, ticker-based):
```
cik                 string    - CIK with leading zeros
ticker              string    - Primary ticker symbol
name                string    - Company name
exchange            string    - Primary exchange (NYSE, Nasdaq, etc.)
```

**Comprehensive Mode** (562K companies, submissions-based):
```
cik                                     string    - CIK with leading zeros
ticker                                  string    - Primary ticker (from tickers[0])
name                                    string    - Company name
exchange                                string    - Primary exchange (from exchanges[0])
sic                                     int32     - Standard Industrial Classification code (nullable)
sic_description                         string    - Industry description
state_of_incorporation                  string    - Two-letter state code (e.g., 'DE')
state_of_incorporation_description      string    - Full state name
fiscal_year_end                         string    - MMDD format (e.g., '1231' for Dec 31)
entity_type                             string    - 'operating', 'other', etc.
ein                                     string    - Employer Identification Number
```

**Storage Details**:
- Tickers/exchanges stored pipe-delimited in source (e.g., `"AAPL|APPLE"`)
- Primary ticker/exchange extracted as first value
- SIC codes nullable (some companies lack SIC assignment)
- CIK stored as string to preserve leading zeros (e.g., `"0001318605"`)

---

## The Build Process

### Overview

The build process transforms SEC submissions data into a high-performance queryable dataset. Understanding this process is critical for customization in edgar.tools.

### Step-by-Step Walkthrough

#### 1. Download Submissions

**Function**: `edgar.storage.download_submissions()`

**Source**: `edgar/storage.py:176`

```python
def download_submissions() -> Path:
    """Download company submissions from SEC"""
    from edgar.config import SEC_ARCHIVE_URL
    url = f"{SEC_ARCHIVE_URL}/daily-index/bulkdata/submissions.zip"
    return asyncio.run(download_bulk_data(client=None, url=url))
```

**What it does**:
- Downloads `submissions.zip` (~500 MB compressed, ~3 GB uncompressed)
- Extracts to `~/.edgar/submissions/`
- Creates ~937,000 individual `CIK*.json` files (one per entity)
- One-time operation (unless rebuilding)

**Download Details**:
- Uses `httpx` async client with SEC User-Agent compliance
- Includes progress bar via `tqdm`
- Automatic retry logic for network failures
- Rate-limited to respect SEC guidelines

#### 2. Build Parquet Dataset

**Function**: `build_company_dataset_parquet()`

**Source**: `edgar/reference/company_dataset.py:128`

**Signature**:
```python
def build_company_dataset_parquet(
    submissions_dir: Path,
    output_path: Path,
    filter_individuals: bool = True,
    show_progress: bool = True
) -> pa.Table
```

**Process Flow**:

```
┌─────────────────────────────────────────────────────────┐
│  1. Scan Submissions Directory                          │
│     - Find all CIK*.json files (~937K files)            │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│  2. Load & Parse Each JSON File                         │
│     - Uses orjson for 1.55x faster parsing              │
│     - Falls back to stdlib json if orjson unavailable   │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│  3. Filter Individual Filers (if enabled)               │
│     - Apply is_individual_from_json() logic             │
│     - Skip ~40% individual filers (375K entities)       │
│     - Keep ~562K companies                              │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│  4. Extract Company Fields                              │
│     - Map JSON keys to schema columns                   │
│     - Handle nullable SIC codes                         │
│     - Extract primary ticker/exchange from pipe-delim   │
│     - Preserve CIK as string with leading zeros         │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│  5. Build PyArrow Table                                 │
│     - Create from list of dicts                         │
│     - Apply COMPANY_SCHEMA typing                       │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│  6. Write Compressed Parquet                            │
│     - Compression: zstd level 9                         │
│     - Dictionary encoding: enabled                      │
│     - Output: ~/.edgar/companies.pq (5-20 MB)           │
└─────────────────────────────────────────────────────────┘
```

**Key Implementation Details**:

```python
# Individual detection logic (company_dataset.py:71)
def is_individual_from_json(data: dict) -> bool:
    """
    Determine if entity is individual vs company.

    Companies typically have:
    - Tickers or exchanges
    - State of incorporation (with exceptions like Reed Hastings)
    - Entity type other than '' or 'other'
    - Company-specific filings (10-K, 10-Q, 8-K)
    """
    # Has ticker or exchange → company
    if data.get('tickers') or data.get('exchanges'):
        return False

    # Has state of incorporation → company (with exception)
    state = data.get('stateOfIncorporation', '')
    if state and state != '':
        if data.get('cik') == '0001033331':  # Reed Hastings exception
            return True
        return False

    # Has entity type (not '' or 'other') → company
    entity_type = data.get('entityType', '')
    if entity_type and entity_type not in ['', 'other']:
        return False

    # Files company forms → company
    filings = data.get('filings', {})
    if filings:
        recent = filings.get('recent', {})
        forms = recent.get('form', [])
        company_forms = {'10-K', '10-Q', '8-K', '10-K/A', '10-Q/A', '20-F', 'S-1'}
        if any(form in company_forms for form in forms):
            return False

    # Default: individual
    return True
```

**Performance Characteristics**:
- **Time**: ~30 seconds (with orjson + filtering)
- **Memory**: ~100-200 MB during build
- **Output Size**: 5-20 MB (highly compressed)
- **Records**: ~562,413 companies (after filtering)

#### 3. Optional: Build DuckDB

**Function**: `build_company_dataset_duckdb()`

**Source**: `edgar/reference/company_dataset.py:253`

For users wanting SQL query capabilities:

```python
def build_company_dataset_duckdb(
    submissions_dir: Path,
    output_path: Path,
    filter_individuals: bool = True,
    create_indexes: bool = True,
    show_progress: bool = True
) -> None
```

**Process**:
1. Same extraction as Parquet build
2. Convert to pandas DataFrame
3. Create DuckDB connection
4. `CREATE TABLE companies AS SELECT * FROM df`
5. Create indexes on `cik`, `sic`, `name` (if enabled)
6. Add metadata table with build statistics

**Output**: `~/.edgar/companies.duckdb` (287 MB)

**Query Performance**: <1ms with indexes

**Use Case**: Power users preferring SQL, database integrations

#### 4. Conversion Utility

**Function**: `to_duckdb(parquet_path, duckdb_path)`

**Source**: `edgar/reference/company_dataset.py:436`

Converts existing Parquet → DuckDB without re-processing submissions:

```python
# Quick conversion
from edgar.reference import to_duckdb
from pathlib import Path

parquet = Path.home() / '.edgar' / 'companies.pq'
duckdb = Path.home() / '.edgar' / 'companies.duckdb'
to_duckdb(parquet, duckdb)
```

---

## Company Subsets

### Overview

The `edgar.reference.company_subsets` module provides high-level functions and a fluent API for selecting company groups. This is the primary interface for edgar.tools features.

### Two Operating Modes

**Standard Mode** (default):
- Source: Ticker-based reference data
- Records: ~13K companies with tickers
- Columns: `cik`, `ticker`, `name`, `exchange`
- Use: Fast, sufficient for ticker-based workflows

**Comprehensive Mode** (opt-in):
- Source: Full submissions dataset
- Records: ~562K companies
- Columns: All standard + SIC, state, entity type, etc.
- Use: Industry filtering, state filtering, research

### Fluent API: CompanySubset

**Source**: `edgar/reference/company_subsets.py:82`

Chainable builder pattern for complex selections:

```python
from edgar.reference import CompanySubset

# Example: 50 random NYSE pharmaceuticals
pharma = (CompanySubset()
          .from_exchange('NYSE')
          .from_industry(sic=2834)
          .sample(50, random_state=42)
          .get())

# Example: Popular tech giants excluding FAANG
tech = (CompanySubset()
        .from_popular()
        .from_industry(sic_range=(7370, 7379))
        .exclude_tickers(['AAPL', 'GOOGL', 'META', 'AMZN', 'NFLX'])
        .get())

# Example: Delaware software companies, top 100 alphabetically
de_software = (CompanySubset(use_comprehensive=True)
               .from_state('DE')
               .from_industry(sic_range=(7371, 7379))
               .top(100, by='name')
               .get())
```

**Methods**:

| Method | Description | Example |
|--------|-------------|---------|
| `from_exchange(exchanges)` | Filter by exchange(s) | `.from_exchange(['NYSE', 'Nasdaq'])` |
| `from_popular(tier)` | Popular companies | `.from_popular(PopularityTier.MEGA_CAP)` |
| `from_industry(...)` | SIC-based filtering | `.from_industry(sic_range=(2833, 2836))` |
| `from_state(states)` | State of incorporation | `.from_state(['DE', 'NV'])` |
| `filter_by(fn)` | Custom filter function | `.filter_by(lambda df: df[df['name'].str.contains('Tech')])` |
| `exclude_tickers(list)` | Exclude specific tickers | `.exclude_tickers(['AAPL'])` |
| `include_tickers(list)` | Include only specific tickers | `.include_tickers(['MSFT', 'GOOGL'])` |
| `sample(n, seed)` | Random sample | `.sample(100, random_state=42)` |
| `top(n, by)` | Top N by column | `.top(50, by='ticker')` |
| `combine_with(other)` | Union with another subset | `.combine_with(other_subset)` |
| `intersect_with(other)` | Intersection | `.intersect_with(other_subset)` |
| `get()` | Get final DataFrame | `.get()` |

### Core Selection Functions

#### Exchange-Based Selection

```python
from edgar.reference import get_companies_by_exchanges

# Single exchange
nyse = get_companies_by_exchanges('NYSE')
# Multiple exchanges
major = get_companies_by_exchanges(['NYSE', 'Nasdaq'])
```

**Available Exchanges**: NYSE, Nasdaq, OTC, CBOE

#### Popularity-Based Selection

```python
from edgar.reference import get_popular_companies, PopularityTier

# All popular stocks (~300 companies)
popular = get_popular_companies()

# Top 10 mega-cap
mega_cap = get_popular_companies(PopularityTier.MEGA_CAP)

# Top 50
top_50 = get_popular_companies(PopularityTier.POPULAR)
```

**Popularity Tiers**:
- `MEGA_CAP`: Top 10 by market cap
- `POPULAR`: Top 50
- `MAINSTREAM`: Top 100
- `EMERGING` or `None`: All popular companies

#### Industry-Based Selection

**Requires comprehensive mode** (auto-enabled):

```python
from edgar.reference import get_companies_by_industry

# Exact SIC code
pharma = get_companies_by_industry(sic=2834)

# SIC range
biotech = get_companies_by_industry(sic_range=(2833, 2836))

# Description search
software = get_companies_by_industry(sic_description_contains='software')

# Multiple SICs
healthcare = get_companies_by_industry(sic=[2834, 2835, 2836])
```

**Common SIC Ranges**:
- 0100-0999: Agriculture, Forestry, Fishing
- 1000-1499: Mining
- 1500-1799: Construction
- 2000-3999: Manufacturing
- 4000-4999: Transportation, Communications, Utilities
- 5000-5199: Wholesale Trade
- 5200-5999: Retail Trade
- 6000-6799: Finance, Insurance, Real Estate
- 7000-8999: Services
- 9100-9729: Public Administration

#### State-Based Selection

**Requires comprehensive mode** (auto-enabled):

```python
from edgar.reference import get_companies_by_state

# Delaware corporations (most common for public companies)
de_corps = get_companies_by_state('DE')

# Multiple states
de_nv = get_companies_by_state(['DE', 'NV'])
```

**Common States**:
- DE: Delaware (most public companies)
- NV: Nevada (tax benefits)
- CA: California
- NY: New York
- TX: Texas

#### Convenience Functions

Pre-built selections for common use cases:

```python
from edgar.reference import (
    get_faang_companies,
    get_tech_giants,
    get_dow_jones_sample,
    # Industry-specific (comprehensive mode)
    get_pharmaceutical_companies,
    get_biotechnology_companies,
    get_software_companies,
    get_semiconductor_companies,
    get_banking_companies,
    get_investment_companies,
    get_insurance_companies,
    get_real_estate_companies,
    get_oil_gas_companies,
    get_retail_companies
)

faang = get_faang_companies()  # META, AAPL, AMZN, NFLX, GOOGL
tech = get_tech_giants()       # 13 major tech companies
pharma = get_pharmaceutical_companies()  # SIC 2834
```

### Sampling and Filtering

#### Random Sampling

```python
from edgar.reference import get_random_sample

# 100 random companies from all companies
random_100 = get_random_sample(n=100, random_state=42)

# 50 random from a subset
nasdaq_sample = get_random_sample(
    get_companies_by_exchanges('Nasdaq'),
    n=50,
    random_state=42
)
```

#### Stratified Sampling

Maintains proportions by category:

```python
from edgar.reference import get_stratified_sample

# 200 companies maintaining exchange proportions
stratified = get_stratified_sample(
    n=200,
    stratify_by='exchange',
    random_state=42
)
```

#### Custom Filtering

```python
from edgar.reference import filter_companies, exclude_companies

# Include specific tickers
faang = filter_companies(
    companies,
    ticker_list=['META', 'AAPL', 'AMZN', 'NFLX', 'GOOGL']
)

# Name search
inc_companies = filter_companies(companies, name_contains='Inc')

# Exclude companies
non_financial = exclude_companies(
    companies,
    ticker_list=['JPM', 'GS', 'C', 'BAC']
)
```

### Set Operations

```python
from edgar.reference import combine_company_sets, intersect_company_sets

# Union (combine)
nyse = get_companies_by_exchanges('NYSE')
popular = get_popular_companies()
combined = combine_company_sets([nyse, popular])  # Deduplicates by CIK

# Intersection
nyse_popular = intersect_company_sets([nyse, popular])
```

---

## Integration Patterns

### Pattern 1: Simple Watchlist Selection

**Use Case**: User creates watchlist by selecting from exchange

```python
from edgar.reference import get_companies_by_exchanges

def create_watchlist(user_id: str, exchange: str, name: str):
    """Create watchlist from exchange selection"""
    companies = get_companies_by_exchanges(exchange)

    # Store in database
    for _, company in companies.iterrows():
        db.insert_watchlist_item(
            user_id=user_id,
            watchlist_name=name,
            cik=company['cik'],
            ticker=company['ticker'],
            name=company['name']
        )

    return len(companies)
```

### Pattern 2: Industry-Based Workflow Filtering

**Use Case**: Alert workflow for "all pharmaceutical companies"

```python
from edgar.reference import get_pharmaceutical_companies

def setup_industry_workflow(user_id: str, industry: str, form_types: list):
    """Create workflow monitoring industry filings"""
    # Get companies
    if industry == 'pharmaceutical':
        companies = get_pharmaceutical_companies()
    elif industry == 'biotech':
        companies = get_biotechnology_companies()
    # ... more industries

    # Store workflow config
    ciks = companies['cik'].tolist()
    db.create_workflow(
        user_id=user_id,
        name=f"{industry} {form_types[0]} Monitor",
        ciks=ciks,
        form_types=form_types
    )

    return len(ciks)
```

### Pattern 3: Dynamic Subset Builder

**Use Case**: UI for building custom company subsets

```python
from edgar.reference import CompanySubset

def build_custom_subset(criteria: dict):
    """Build subset from user criteria"""
    subset = CompanySubset(use_comprehensive=criteria.get('use_sic', False))

    # Apply filters based on criteria
    if criteria.get('exchanges'):
        subset = subset.from_exchange(criteria['exchanges'])

    if criteria.get('popularity_tier'):
        subset = subset.from_popular(criteria['popularity_tier'])

    if criteria.get('sic_range'):
        min_sic, max_sic = criteria['sic_range']
        subset = subset.from_industry(sic_range=(min_sic, max_sic))

    if criteria.get('states'):
        subset = subset.from_state(criteria['states'])

    if criteria.get('exclude_tickers'):
        subset = subset.exclude_tickers(criteria['exclude_tickers'])

    if criteria.get('sample_size'):
        subset = subset.sample(criteria['sample_size'], random_state=42)

    return subset.get()
```

### Pattern 4: Cached Subset Management

**Use Case**: Pre-compute subsets for performance

```python
from functools import lru_cache
from edgar.reference import get_pharmaceutical_companies, get_tech_giants

@lru_cache(maxsize=50)
def get_cached_subset(subset_name: str):
    """Cache frequently-used subsets"""
    subsets = {
        'pharma': get_pharmaceutical_companies,
        'tech_giants': get_tech_giants,
        'nyse': lambda: get_companies_by_exchanges('NYSE'),
        # ... more subsets
    }

    if subset_name in subsets:
        return subsets[subset_name]()

    raise ValueError(f"Unknown subset: {subset_name}")

# Usage
pharma = get_cached_subset('pharma')  # Fast on repeated calls
```

### Pattern 5: Combining Multiple Filters

**Use Case**: "Show me popular NYSE tech companies"

```python
from edgar.reference import (
    CompanySubset,
    PopularityTier,
    intersect_company_sets
)

# Method 1: Fluent API
popular_nyse_tech = (
    CompanySubset(use_comprehensive=True)
    .from_exchange('NYSE')
    .from_popular(PopularityTier.POPULAR)
    .from_industry(sic_range=(7370, 7379))
    .get()
)

# Method 2: Set intersection
nyse = get_companies_by_exchanges('NYSE')
popular = get_popular_companies(PopularityTier.POPULAR)
tech = get_software_companies()
result = intersect_company_sets([nyse, popular, tech])
```

---

## Database Migration Guide

### Overview

For edgar.tools, you may want to extract submissions data directly to a database instead of using the Parquet file approach. This section explains how to modify the build process.

### Architecture Options

#### Option 1: Parquet + Database Sync

**Keep edgartools behavior, sync to database:**

```python
from edgar.reference import get_company_dataset
import sqlalchemy as sa

def sync_companies_to_db(engine):
    """Sync Parquet dataset to database"""
    # Get dataset (builds/loads Parquet)
    companies = get_company_dataset()
    df = companies.to_pandas()

    # Write to database (upsert by CIK)
    df.to_sql(
        'companies',
        engine,
        if_exists='replace',
        index=False,
        method='multi',
        chunksize=10000
    )

# Usage
engine = sa.create_engine('postgresql://...')
sync_companies_to_db(engine)
```

**Pros**:
- Minimal code changes
- Leverages existing edgartools caching
- Can use both Parquet and database

**Cons**:
- Two storage layers
- Requires periodic sync

#### Option 2: Direct Database Build

**Skip Parquet, build directly to database:**

```python
from pathlib import Path
from edgar.reference.company_dataset import load_json, is_individual_from_json
from edgar.core import get_edgar_data_directory
from tqdm import tqdm
import sqlalchemy as sa
import pandas as pd

def build_companies_to_database(
    engine,
    filter_individuals: bool = True,
    batch_size: int = 10000
):
    """Build companies directly to database"""
    # Get submissions directory
    submissions_dir = get_edgar_data_directory() / 'submissions'
    json_files = list(submissions_dir.glob("CIK*.json"))

    companies_batch = []

    for json_file in tqdm(json_files, desc="Processing submissions"):
        try:
            data = load_json(json_file)

            # Skip individuals
            if filter_individuals and is_individual_from_json(data):
                continue

            # Extract SIC
            sic = data.get('sic')
            sic_int = int(sic) if sic and sic != '' else None

            # Extract tickers/exchanges
            tickers = data.get('tickers', [])
            exchanges = data.get('exchanges', [])

            companies_batch.append({
                'cik': data.get('cik'),
                'name': data.get('name'),
                'ticker': tickers[0] if tickers else None,
                'exchange': exchanges[0] if exchanges else None,
                'sic': sic_int,
                'sic_description': data.get('sicDescription'),
                'state_of_incorporation': data.get('stateOfIncorporation'),
                'state_of_incorporation_description': data.get('stateOfIncorporationDescription'),
                'fiscal_year_end': data.get('fiscalYearEnd'),
                'entity_type': data.get('entityType'),
                'ein': data.get('ein'),
            })

            # Batch insert
            if len(companies_batch) >= batch_size:
                df = pd.DataFrame(companies_batch)
                df.to_sql('companies', engine, if_exists='append', index=False)
                companies_batch = []

        except Exception as e:
            continue

    # Insert remaining
    if companies_batch:
        df = pd.DataFrame(companies_batch)
        df.to_sql('companies', engine, if_exists='append', index=False)

# Usage
engine = sa.create_engine('postgresql://...')

# Create table
engine.execute("""
CREATE TABLE IF NOT EXISTS companies (
    cik VARCHAR(10) PRIMARY KEY,
    name TEXT,
    ticker VARCHAR(10),
    exchange VARCHAR(50),
    sic INTEGER,
    sic_description TEXT,
    state_of_incorporation VARCHAR(2),
    state_of_incorporation_description TEXT,
    fiscal_year_end VARCHAR(4),
    entity_type VARCHAR(50),
    ein VARCHAR(20)
)
""")

# Create indexes
engine.execute("CREATE INDEX idx_ticker ON companies(ticker)")
engine.execute("CREATE INDEX idx_sic ON companies(sic)")
engine.execute("CREATE INDEX idx_exchange ON companies(exchange)")

# Build
build_companies_to_database(engine)
```

**Pros**:
- Single source of truth (database)
- No Parquet intermediate
- Direct control over schema

**Cons**:
- Bypasses edgartools caching
- Need custom query layer
- Breaks compatibility with edgartools subset functions (need adapters)

#### Option 3: Hybrid - Custom Loader

**Use edgartools subset API with database backend:**

```python
from edgar.reference import get_all_companies
import sqlalchemy as sa

# Monkey-patch get_all_companies to use database
_original_get_all_companies = get_all_companies

def get_all_companies_from_db(use_comprehensive: bool = False):
    """Override to load from database"""
    engine = sa.create_engine('postgresql://...')

    if use_comprehensive:
        query = "SELECT * FROM companies"
    else:
        query = """
            SELECT cik, ticker, name, exchange
            FROM companies
            WHERE ticker IS NOT NULL
        """

    df = pd.read_sql(query, engine)
    return df

# Replace in module
import edgar.reference.company_subsets as subsets_module
subsets_module.get_all_companies = get_all_companies_from_db

# Now all subset functions use database
from edgar.reference import get_pharmaceutical_companies
pharma = get_pharmaceutical_companies()  # Loads from DB
```

**Pros**:
- Full compatibility with edgartools API
- Database-backed
- Minimal changes to calling code

**Cons**:
- Monkey-patching fragile
- Need to maintain override
- Database must match schema exactly

### Recommended Approach for edgar.tools

**Use Option 1 (Parquet + Database Sync) for now**:

1. Let edgartools handle the build/cache (Parquet)
2. Sync to database periodically (nightly job)
3. Application queries database for performance
4. Subset API remains available for exploration

**Migration path**:
1. Start with Parquet
2. Add database sync
3. Benchmark database performance
4. If needed, migrate to direct database build (Option 2)

### Database Schema Design

**Recommended PostgreSQL Schema**:

```sql
-- Companies table
CREATE TABLE companies (
    cik VARCHAR(10) PRIMARY KEY,
    name TEXT NOT NULL,
    ticker VARCHAR(10),
    exchange VARCHAR(50),
    sic INTEGER,
    sic_description TEXT,
    state_of_incorporation VARCHAR(2),
    state_of_incorporation_description TEXT,
    fiscal_year_end VARCHAR(4),
    entity_type VARCHAR(50),
    ein VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_companies_ticker ON companies(ticker) WHERE ticker IS NOT NULL;
CREATE INDEX idx_companies_sic ON companies(sic) WHERE sic IS NOT NULL;
CREATE INDEX idx_companies_exchange ON companies(exchange) WHERE exchange IS NOT NULL;
CREATE INDEX idx_companies_state ON companies(state_of_incorporation) WHERE state_of_incorporation IS NOT NULL;
CREATE INDEX idx_companies_name_trgm ON companies USING gin(name gin_trgm_ops);  -- For name search

-- Denormalize tickers (if companies have multiple)
CREATE TABLE company_tickers (
    cik VARCHAR(10) REFERENCES companies(cik) ON DELETE CASCADE,
    ticker VARCHAR(10) NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (cik, ticker)
);

-- Denormalize exchanges
CREATE TABLE company_exchanges (
    cik VARCHAR(10) REFERENCES companies(cik) ON DELETE CASCADE,
    exchange VARCHAR(50) NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (cik, exchange)
);
```

---

## Use Cases

### Use Case 1: Industry Watchlist

**Scenario**: User wants to track all pharmaceutical company filings

```python
from edgar.reference import get_pharmaceutical_companies

# Get companies
pharma = get_pharmaceutical_companies()
print(f"Tracking {len(pharma)} pharmaceutical companies")

# Store in watchlist table
for _, company in pharma.iterrows():
    db.insert_watchlist(
        user_id=user_id,
        watchlist_name="Pharma Watch",
        cik=company['cik'],
        ticker=company['ticker'],
        company_name=company['name']
    )

# Query filings for watchlist CIKs
ciks = pharma['cik'].tolist()
recent_filings = get_filings(
    form=['10-K', '10-Q'],
    cik=ciks,
    filing_date_gte='2024-01-01'
)
```

### Use Case 2: Exchange-Based Alert

**Scenario**: Alert on all 8-K filings from Nasdaq companies

```python
from edgar.reference import get_companies_by_exchanges

# Get Nasdaq companies
nasdaq = get_companies_by_exchanges('Nasdaq')
nasdaq_ciks = nasdaq['cik'].tolist()

# Set up alert workflow
workflow = {
    'name': 'Nasdaq 8-K Monitor',
    'ciks': nasdaq_ciks,
    'forms': ['8-K'],
    'schedule': 'real-time'
}

# Check for new filings periodically
new_filings = get_filings(
    form='8-K',
    cik=nasdaq_ciks,
    filing_date=today
)

# Send alerts
for filing in new_filings:
    send_alert(
        user=user,
        subject=f"8-K filed: {filing.company}",
        filing=filing
    )
```

### Use Case 3: Geographic Analysis

**Scenario**: Compare Delaware vs. Nevada corporations

```python
from edgar.reference import get_companies_by_state

# Get companies by state
de_corps = get_companies_by_state('DE')
nv_corps = get_companies_by_state('NV')

print(f"Delaware corporations: {len(de_corps)}")
print(f"Nevada corporations: {len(nv_corps)}")

# Analyze industries
de_industries = de_corps.groupby('sic_description').size().sort_values(ascending=False)
nv_industries = nv_corps.groupby('sic_description').size().sort_values(ascending=False)

# Compare filing patterns
de_filings = get_filings(cik=de_corps['cik'].tolist(), year=2024)
nv_filings = get_filings(cik=nv_corps['cik'].tolist(), year=2024)
```

### Use Case 4: Portfolio Simulator

**Scenario**: Create simulated portfolios from company subsets

```python
from edgar.reference import CompanySubset, PopularityTier

# Create portfolio: 20 popular NYSE companies, exclude financials
portfolio = (
    CompanySubset()
    .from_exchange('NYSE')
    .from_popular(PopularityTier.POPULAR)
    .from_industry(sic_range=(6000, 6799))  # Finance
    .exclude_tickers([])  # Then invert via set difference
    .sample(20, random_state=42)
    .get()
)

# Backtest: Get financials for portfolio companies
for _, company in portfolio.iterrows():
    company_obj = Company(company['cik'])
    filings = company_obj.get_filings(form='10-K', year=2023)

    if not filings.empty:
        filing = filings[0]
        xbrl = filing.xbrl()

        # Extract metrics
        revenue = xbrl.statements.income.get('Revenue')
        net_income = xbrl.statements.income.get('NetIncomeLoss')

        # Analyze...
```

### Use Case 5: Competitive Intelligence

**Scenario**: Monitor competitors in specific industry

```python
from edgar.reference import get_companies_by_industry

# Get semiconductor companies
semiconductors = get_companies_by_industry(sic=3674)

# Exclude own company
competitors = semiconductors[semiconductors['ticker'] != 'MYCO']

# Monitor for specific filing events
for _, competitor in competitors.iterrows():
    # Set up alerts for:
    # - Form 8-K (material events)
    # - Form 10-K (annual reports)
    # - Form 4 (insider trading)

    setup_alert(
        cik=competitor['cik'],
        forms=['8-K', '10-K', '4'],
        keywords=['acquisition', 'partnership', 'revenue guidance']
    )
```

### Use Case 6: Research Sample Selection

**Scenario**: Academic research on tech companies

```python
from edgar.reference import CompanySubset

# Research sample: 100 public software companies
# - Listed on NYSE or Nasdaq
# - Stratified by market cap (using popular tier as proxy)
# - Reproducible (fixed random seed)

research_sample = (
    CompanySubset(use_comprehensive=True)
    .from_exchange(['NYSE', 'Nasdaq'])
    .from_industry(sic_range=(7371, 7379))  # Software
    .sample(100, random_state=12345)  # Reproducible
    .get()
)

# Export for analysis
research_sample.to_csv('research_sample.csv', index=False)

# Collect data
for _, company in research_sample.iterrows():
    # Download 10-Ks, extract financials, etc.
    pass
```

---

## Performance Considerations

### Build Time Optimization

**Factor 1: JSON Parser**

Install `orjson` for 1.55x faster parsing:

```bash
pip install orjson
```

Without orjson: ~47 seconds
With orjson: ~30 seconds

**Factor 2: Individual Filtering**

Filtering individuals reduces dataset by 40%:

```python
# With filtering (default)
table = build_company_dataset_parquet(
    submissions_dir,
    output_path,
    filter_individuals=True  # 562K companies, ~30 sec
)

# Without filtering
table = build_company_dataset_parquet(
    submissions_dir,
    output_path,
    filter_individuals=False  # 937K entities, ~35 sec
)
```

Trade-off: Build time vs. dataset size

**Factor 3: Parallel Processing**

Current implementation is single-threaded. For faster builds:

```python
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

def process_json_batch(json_files: list) -> list:
    """Process batch of JSON files in parallel"""
    companies = []
    for json_file in json_files:
        data = load_json(json_file)
        if not is_individual_from_json(data):
            # Extract company data
            companies.append(extract_company(data))
    return companies

def build_company_dataset_parallel(submissions_dir: Path, workers: int = 4):
    """Build dataset with parallel processing"""
    json_files = list(submissions_dir.glob("CIK*.json"))

    # Split into batches
    batch_size = len(json_files) // workers
    batches = [json_files[i:i+batch_size] for i in range(0, len(json_files), batch_size)]

    # Process in parallel
    with ProcessPoolExecutor(max_workers=workers) as executor:
        results = executor.map(process_json_batch, batches)

    # Combine results
    all_companies = [c for batch in results for c in batch]

    # Create table...
```

Expected improvement: ~4x speedup with 4 workers

### Query Performance

**Parquet**:
- Load time: <100ms
- Filter time: <50ms (PyArrow compute)
- Total query: <150ms

**DuckDB**:
- Load time: N/A (persistent connection)
- Query time: <1ms with indexes
- Best for: Complex SQL queries, large result sets

**PostgreSQL** (for edgar.tools):
- Query time: <5ms with proper indexes
- Best for: Multi-user, concurrent access, ACID transactions

### Caching Strategy

**In-Memory Cache**:

```python
# edgar/reference/company_dataset.py:516
_CACHE = {}

def get_company_dataset(rebuild: bool = False) -> pa.Table:
    # Check in-memory cache first
    if not rebuild and 'companies' in _CACHE:
        return _CACHE['companies']

    # Load from disk or build
    # ...

    _CACHE['companies'] = table
    return table
```

**Cache Invalidation**:

```python
# Force rebuild (e.g., after SEC data update)
from edgar.reference import get_company_dataset

companies = get_company_dataset(rebuild=True)
```

**Disk Cache**:
- Location: `~/.edgar/companies.pq`
- Size: 5-20 MB
- TTL: Indefinite (manual rebuild)

### Memory Usage

| Operation | Memory |
|-----------|--------|
| Build process | 100-200 MB |
| Parquet file loaded | 20-50 MB |
| DataFrame operations | 50-100 MB |
| Total typical | <300 MB |

Safe for production environments.

---

## API Reference

### Company Dataset Functions

#### `get_company_dataset(rebuild: bool = False) -> pa.Table`

Get company dataset, building from submissions if needed.

**Parameters**:
- `rebuild` (bool): Force rebuild even if cache exists

**Returns**: PyArrow Table with ~562K companies

**Example**:
```python
from edgar.reference import get_company_dataset
companies = get_company_dataset()
```

#### `build_company_dataset_parquet(...)`

Build PyArrow Parquet dataset from submissions.

**Parameters**:
- `submissions_dir` (Path): Directory with CIK*.json files
- `output_path` (Path): Where to save .pq file
- `filter_individuals` (bool): Skip individual filers
- `show_progress` (bool): Show progress bar

**Returns**: PyArrow Table

#### `build_company_dataset_duckdb(...)`

Build DuckDB database from submissions.

**Parameters**:
- `submissions_dir` (Path): Directory with CIK*.json files
- `output_path` (Path): Where to save .duckdb file
- `filter_individuals` (bool): Skip individual filers
- `create_indexes` (bool): Create indexes on key columns
- `show_progress` (bool): Show progress bar

#### `to_duckdb(parquet_path, duckdb_path, create_indexes=True)`

Convert Parquet dataset to DuckDB.

**Parameters**:
- `parquet_path` (Path): Source .pq file
- `duckdb_path` (Path): Output .duckdb file
- `create_indexes` (bool): Create indexes

#### `is_individual_from_json(data: dict) -> bool`

Determine if entity is individual vs. company.

**Parameters**:
- `data` (dict): Parsed JSON submission data

**Returns**: True if individual, False if company

### Company Subset Functions

#### `get_all_companies(use_comprehensive: bool = False) -> pd.DataFrame`

Get all companies in standardized format.

**Parameters**:
- `use_comprehensive` (bool): Load full dataset with metadata

**Returns**: DataFrame with columns `[cik, ticker, name, exchange, ...]`

#### `get_companies_by_exchanges(exchanges: Union[str, List[str]]) -> pd.DataFrame`

Get companies by exchange(s).

**Parameters**:
- `exchanges`: Single exchange or list ('NYSE', 'Nasdaq', 'OTC', 'CBOE')

**Returns**: Filtered DataFrame

#### `get_popular_companies(tier: Optional[PopularityTier] = None) -> pd.DataFrame`

Get popular companies by tier.

**Parameters**:
- `tier` (PopularityTier): MEGA_CAP, POPULAR, MAINSTREAM, EMERGING, or None

**Returns**: DataFrame with popular companies

#### `get_companies_by_industry(...) -> pd.DataFrame`

Get companies by SIC code (requires comprehensive mode).

**Parameters**:
- `sic` (int or list): Exact SIC code(s)
- `sic_range` (tuple): (min_sic, max_sic)
- `sic_description_contains` (str): Search in description

**Returns**: DataFrame with matching companies

#### `get_companies_by_state(states: Union[str, List[str]]) -> pd.DataFrame`

Get companies by state of incorporation (requires comprehensive mode).

**Parameters**:
- `states`: State code(s) (e.g., 'DE', ['DE', 'NV'])

**Returns**: DataFrame with matching companies

#### `filter_companies(...) -> pd.DataFrame`

Filter companies by criteria.

**Parameters**:
- `companies` (DataFrame): Input DataFrame
- `ticker_list` (list): Specific tickers to include
- `name_contains` (str): Name must contain string
- `cik_list` (list): Specific CIKs to include
- `custom_filter` (callable): Custom function

**Returns**: Filtered DataFrame

#### `exclude_companies(...) -> pd.DataFrame`

Exclude companies by criteria.

**Parameters**:
- `companies` (DataFrame): Input DataFrame
- `ticker_list` (list): Tickers to exclude
- `name_contains` (str): Exclude if name contains
- `cik_list` (list): CIKs to exclude

**Returns**: Filtered DataFrame

### CompanySubset Class

Fluent API for building subsets.

**Methods**: See [Fluent API section](#fluent-api-companysubset)

---

## Appendix

### Common SIC Codes

| Range | Industry |
|-------|----------|
| 2834 | Pharmaceutical Preparations |
| 2833-2836 | Biotechnology |
| 3674 | Semiconductors |
| 6020-6029 | Commercial Banking |
| 6200-6299 | Investment Companies |
| 6300-6399 | Insurance |
| 6500-6599 | Real Estate |
| 7371-7379 | Software & Computer Programming |
| 1300-1399 | Oil & Gas Extraction |
| 5200-5999 | Retail Trade |

### State Codes

Common states of incorporation:

| Code | State | Notes |
|------|-------|-------|
| DE | Delaware | Most common for public companies |
| NV | Nevada | Tax advantages |
| CA | California | Tech companies |
| NY | New York | Financial companies |
| TX | Texas | Energy companies |

### File Locations

**Default Paths**:
- Submissions: `~/.edgar/submissions/`
- Companies dataset: `~/.edgar/companies.pq`
- DuckDB (optional): `~/.edgar/companies.duckdb`

**Override**:
```python
import os
os.environ['EDGAR_LOCAL_DATA_DIR'] = '/custom/path'
```

### Dependencies

**Required**:
- pyarrow
- pandas
- tqdm

**Optional**:
- orjson (faster JSON parsing)
- duckdb (SQL interface)

### Build Statistics

| Metric | Value |
|--------|-------|
| Total submissions files | ~937,000 |
| Individual filers (filtered) | ~375,000 (40%) |
| Company records | ~562,413 (60%) |
| Build time (with orjson) | ~30 seconds |
| Output size (Parquet) | 5-20 MB |
| Output size (DuckDB) | 287 MB |
| Load time (Parquet) | <100ms |
| Query time (DuckDB) | <1ms (with indexes) |

---

## Support & Feedback

For questions or issues:
- **GitHub Issues**: https://github.com/dgunning/edgartools/issues
- **Documentation**: https://github.com/dgunning/edgartools
- **Community**: Join discussions on GitHub

---

**Document Version**: 1.0
**Last Updated**: 2025-11-23
**Maintained By**: EdgarTools Team
