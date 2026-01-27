# edgar.bdc - Business Development Company Module

Access SEC data for Business Development Companies (BDCs), including reference data, portfolio investments, and bulk DERA datasets.

## Overview

Business Development Companies (BDCs) are closed-end investment companies that invest in small and mid-sized private companies. They file with the SEC under the Investment Company Act of 1940 and have file numbers starting with "814-".

This module provides:
- **Reference Data**: Access to the SEC's authoritative list of ~196 BDCs
- **Portfolio Investments**: Individual investment holdings from Schedule of Investments
- **Bulk Datasets**: SEC DERA quarterly extracts for cross-BDC analysis
- **Search**: Fuzzy search for BDCs by name or ticker

## Quick Start

```python
from edgar.bdc import (
    # Reference data
    get_bdc_list, find_bdc, is_bdc_cik,
    # Bulk datasets
    fetch_bdc_dataset,
    # Individual investments
    PortfolioInvestments,
)

# List all BDCs (~196 entities)
bdcs = get_bdc_list()

# Search for a BDC by name or ticker
results = find_bdc("Ares")
arcc = bdcs.get_by_ticker("ARCC")

# Cross-BDC portfolio search
dataset = fetch_bdc_dataset(2024, 3)
soi = dataset.schedule_of_investments
soi.search("Ivy Hill")  # Which BDCs hold this company?

# Single BDC investments
investments = arcc.portfolio_investments()
```

## Module Components

### 1. Reference Data (`edgar.bdc.reference`)

#### `get_bdc_list(year=None) -> BDCEntities`

Returns all BDCs from the SEC BDC Report.

```python
from edgar.bdc import get_bdc_list

bdcs = get_bdc_list()
len(bdcs)  # ~196

# Filter by state
ny_bdcs = bdcs.filter(state='NY')

# Filter by active status (filed within 18 months)
active_bdcs = bdcs.filter(active=True)

# Get all CIKs
bdcs.ciks  # [17313, 81955, 701571, ...]
```

#### `BDCEntity`

Represents a single BDC with methods to access filings and investments.

```python
arcc = bdcs.get_by_ticker("ARCC")
# or
arcc = bdcs.get_by_cik(1287750)

# Properties
arcc.name          # "ARES CAPITAL CORP"
arcc.cik           # 1287750
arcc.file_number   # "814-00663"
arcc.is_active     # True
arcc.last_filing_date  # date(2024, 11, 5)

# Methods
arcc.get_company()              # -> Company object
arcc.get_filings(form="10-K")   # -> Filings
arcc.schedule_of_investments()  # -> Statement
arcc.portfolio_investments()    # -> PortfolioInvestments
arcc.has_detailed_investments() # -> bool
```

#### `find_bdc(query, top_n=10) -> BDCSearchResults`

Fuzzy search for BDCs by name or ticker.

```python
from edgar.bdc import find_bdc

results = find_bdc("Ares")
results[0].name  # "ARES CAPITAL CORP"

results = find_bdc("MAIN")
results[0].name  # "MAIN STREET CAPITAL CORP"
```

#### `is_bdc_cik(cik) -> bool`

Check if a CIK belongs to a BDC.

```python
from edgar.bdc import is_bdc_cik

is_bdc_cik(1287750)  # True (ARCC)
is_bdc_cik(320193)   # False (Apple)
```

### 2. Bulk Datasets (`edgar.bdc.datasets`)

#### `fetch_bdc_dataset(year, quarter) -> BDCDataset`

Fetch SEC DERA bulk extract for a quarter.

```python
from edgar.bdc import fetch_bdc_dataset

dataset = fetch_bdc_dataset(2024, 3)

# Properties
dataset.period           # "2024Q3"
dataset.num_companies    # ~148
dataset.num_submissions  # ~159
dataset.num_soi_entries  # ~106,715

# Raw DataFrames
dataset.submissions  # Filing metadata
dataset.numbers      # Numeric XBRL facts
dataset.soi          # Schedule of Investments
```

#### `ScheduleOfInvestmentsData`

Wrapper for SOI data with search and subsetting capabilities.

```python
soi = dataset.schedule_of_investments

# Basic info
len(soi)           # 106,715 rows
soi.num_companies  # 148 BDCs
soi.ciks           # List of BDC CIKs

# Subset by BDC
arcc_soi = soi[1287750]       # By CIK
arcc_soi = soi[arcc]          # By BDCEntity

# Search for portfolio companies
results = soi.search("Ivy Hill")
# Returns DataFrame: company | bdc_name | bdc_cik | fair_value | form

# Top companies across all BDCs
top = soi.top_companies(25)
# Returns DataFrame: company | num_bdcs | total_fair_value | bdc_names

# Convert to DataFrame
df = soi.to_dataframe(clean=True)  # Simplified column names
```

### 3. Portfolio Investments (`edgar.bdc.investments`)

#### `PortfolioInvestments`

Collection of individual investment positions from XBRL.

```python
investments = arcc.portfolio_investments()

# Properties
len(investments)                 # 1,256
investments.total_fair_value     # Decimal('26800000000')
investments.total_cost           # Decimal('25100000000')

# Filtering
first_lien = investments.filter(investment_type="First lien")
large = investments.filter(min_fair_value=Decimal('100000000'))

# Iteration
for inv in investments:
    print(f"{inv.company_name}: ${inv.fair_value:,}")

# Convert to DataFrame
df = investments.to_dataframe()

# Data quality metrics
quality = investments.data_quality
quality.fair_value_coverage  # 0.95 (95% have fair value)
quality.debt_count           # 800
quality.equity_count         # 456
```

#### `PortfolioInvestment`

Single investment position.

```python
inv = investments[0]

# Core fields
inv.company_name      # "ABC Software, LLC"
inv.investment_type   # "First lien senior secured loan"
inv.fair_value        # Decimal('25000000')
inv.cost              # Decimal('24500000')
inv.unrealized_gain_loss  # Decimal('500000')

# Rate info
inv.interest_rate     # 0.1175 (11.75%)
inv.pik_rate          # 0.02 (2% PIK)
inv.spread            # 0.0575 (5.75%)

# Classification
inv.is_debt           # True
inv.is_equity         # False

# Position details
inv.principal_amount  # Decimal('25000000')
inv.shares            # None (debt investment)
inv.percent_of_net_assets  # 0.012 (1.2%)
```

## Common Use Cases

### 1. Cross-BDC Company Exposure

Find which BDCs hold investments in a specific private company:

```python
dataset = fetch_bdc_dataset(2024, 3)
soi = dataset.schedule_of_investments

results = soi.search("MRI Software")
print(f"MRI Software held by {len(results)} BDC positions")
print(f"Total exposure: ${results['fair_value'].sum():,.0f}")
print(f"BDCs: {results['bdc_name'].unique().tolist()}")
```

### 2. Most Commonly Held Private Companies

Find the most popular private credit investments:

```python
dataset = fetch_bdc_dataset(2024, 3)
soi = dataset.schedule_of_investments

top = soi.top_companies(25)
for _, row in top.iterrows():
    print(f"{row['company']}: {row['num_bdcs']} BDCs, ${row['total_fair_value']:,.0f}")
```

### 3. Single BDC Portfolio Analysis

Analyze a specific BDC's portfolio:

```python
bdcs = get_bdc_list()
arcc = bdcs.get_by_ticker("ARCC")
investments = arcc.portfolio_investments()

# Summary stats
print(f"Positions: {len(investments)}")
print(f"Total Fair Value: ${investments.total_fair_value:,.0f}")

# By investment type
df = investments.to_dataframe()
print(df.groupby('investment_type')['fair_value'].sum().sort_values(ascending=False))

# Debt vs equity mix
quality = investments.data_quality
print(f"Debt: {quality.debt_count}, Equity: {quality.equity_count}")
```

### 4. Industry Concentration

Analyze industry exposure across BDCs:

```python
dataset = fetch_bdc_dataset(2024, 3)
summary = dataset.summary_by_industry()
print(summary.head(10))
```

### 5. BDC Screening

Find BDCs by location and activity:

```python
bdcs = get_bdc_list()

# Active BDCs in New York
ny_active = bdcs.filter(state='NY', active=True)
for bdc in ny_active:
    print(f"{bdc.name} (CIK: {bdc.cik})")
```

### 6. Check if Company is a BDC

Validate before BDC-specific operations:

```python
from edgar.bdc import is_bdc_cik

if is_bdc_cik(company.cik):
    investments = company.portfolio_investments()
```

## Data Sources

### SEC BDC Report (Entity List)

The SEC maintains an authoritative list of all entities with 814- file numbers.

**URL:** https://www.sec.gov/about/opendatasetsshtmlbdc

**Files:** `business-development-company-{year}.csv` (2016-2025)

### SEC BDC Data Sets (DERA)

Pre-extracted XBRL data from SEC's Division of Economic and Risk Analysis.

**URL:** https://www.sec.gov/data-research/sec-markets-data/bdc-data-sets

**Download pattern:**
```
https://www.sec.gov/files/structureddata/data/business-development-company-bdc-data-sets/{year}q{quarter}_bdc.zip
```

**Files in ZIP:**

| File | Description | Key Fields |
|------|-------------|------------|
| `sub.tsv` | Submissions | adsh, cik, name, form, filed |
| `num.tsv` | Numeric facts | adsh, tag, value, uom |
| `pre.tsv` | Presentation | adsh, stmt, line, tag |
| `soi.tsv` | Schedule of Investments | company, industry, fair_value |

## Two Data Approaches

| Source | Coverage | Granularity | Best For |
|--------|----------|-------------|----------|
| **DERA Bulk Datasets** | All BDCs | Company-level | Cross-BDC search |
| **XBRL Individual** | One BDC | Investment-level | Deep dive analysis |

The DERA bulk datasets provide broad coverage across all BDCs but with company-level aggregation. Individual XBRL extraction provides detailed per-investment data including interest rates, maturity dates, and PIK rates.

## Performance Notes

| Operation | Time | Notes |
|-----------|------|-------|
| `get_bdc_list()` | ~1s | Cached after first call |
| `fetch_bdc_dataset()` | ~5-10s | Downloads ~15MB ZIP |
| `soi.search()` | <100ms | In-memory filtering |
| `soi.top_companies()` | ~500ms | Groupby aggregation |
| `portfolio_investments()` | ~3-5s | XBRL parsing |

## API Reference

### Exports

```python
from edgar.bdc import (
    # Data sets (DERA bulk extracts)
    BDCDataset,
    ScheduleOfInvestmentsData,
    fetch_bdc_dataset,
    fetch_bdc_dataset_monthly,
    get_available_quarters,
    list_bdc_datasets,
    # Reference data
    BDCEntities,
    BDCEntity,
    fetch_bdc_report,
    get_active_bdc_ciks,
    get_bdc_list,
    get_latest_bdc_report_year,
    is_bdc_cik,
    # Investments
    DataQuality,
    PortfolioInvestment,
    PortfolioInvestments,
    # Search
    BDCSearchIndex,
    BDCSearchResults,
    find_bdc,
)
```

## File Structure

| Component | File |
|-----------|------|
| Reference data | `edgar/bdc/reference.py` |
| Bulk datasets | `edgar/bdc/datasets.py` |
| Portfolio investments | `edgar/bdc/investments.py` |
| Search | `edgar/bdc/search.py` |
