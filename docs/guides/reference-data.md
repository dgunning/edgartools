---
description: Access SEC reference data with edgartools — ticker-to-CIK mappings, exchange listings, industry codes, CUSIP lookups, form descriptions, and more.
---

# SEC Reference Data

EdgarTools ships with a comprehensive set of SEC reference data — ticker-to-CIK mappings, exchange listings, industry classifications, CUSIP lookups, place codes, and form descriptions. Most of this data is **bundled with the package** and works offline with zero configuration.

## What's Included

| Data | Source | Network? | Function / Location |
|------|--------|----------|---------------------|
| **~10,600 tickers with CIK and exchange** | Bundled parquet | No | `Company("AAPL")`, `find_cik("AAPL")` |
| **CUSIP-to-ticker mapping** | Bundled parquet | No | `cusip_ticker_mapping()`, `get_ticker_from_cusip()` |
| **SEC form descriptions** | Bundled CSV | No | `describe_form("10-K")` |
| **Place codes (states/countries)** | Bundled CSV | No | `get_place_name()`, `get_filer_type()` |
| **Popular stock lists** | Bundled CSV | No | `get_popular_companies()`, `get_faang_companies()` |
| **Full SEC ticker universe** | SEC API / local download | Yes (once) | `download_edgar_data(reference=True)` |

All bundled data lives in `edgar/reference/data/` inside the installed package and is loaded automatically.

## Ticker-to-CIK Resolution

The most common use of reference data is resolving ticker symbols to SEC CIK numbers. This happens automatically when you call `Company()`.

### How It Works

When you call `Company("AAPL")`, edgartools resolves the ticker using a three-level waterfall:

1. **Bundled parquet** (instant, no network) — ~10,600 exchange-listed tickers ship with the package
2. **Local downloaded data** (if configured) — the full SEC ticker universe including recent IPOs
3. **Live SEC API** (fallback) — fetched once per session and cached in memory

This means **`Company()` lookups work offline by default** for established tickers.

```python
from edgar import Company

# Works offline — no internet needed
company = Company("AAPL")
print(f"{company.name} (CIK: {company.cik})")
```

### Lightweight CIK Lookup

If you just need the CIK number without loading the full company object:

```python
from edgar.reference.tickers import find_cik

cik = find_cik("NVDA")
print(f"NVDA CIK: {cik}")  # 1045810
```

### What's in the Bundled Data

```python
from edgar.reference.tickers import load_company_tickers_from_package

bundled = load_company_tickers_from_package()
print(f"Tickers: {len(bundled):,}")
print(f"Columns: {list(bundled.columns)}")
print(f"Exchanges: {sorted(bundled['exchange'].dropna().unique())}")
```

Output:
```
Tickers: 10,652
Columns: ['cik', 'ticker', 'company', 'exchange']
Exchanges: ['CBOE', 'NYSE', 'Nasdaq', 'OTC']
```

## Companies by Exchange

Get all companies listed on a specific stock exchange:

```python
from edgar.reference import get_companies_by_exchanges

# Single exchange
nyse = get_companies_by_exchanges("NYSE")
print(f"NYSE companies: {len(nyse):,}")

# Multiple exchanges
major = get_companies_by_exchanges(["NYSE", "Nasdaq"])
print(f"NYSE + Nasdaq: {len(major):,}")
```

Returns a DataFrame with columns `[cik, ticker, name, exchange]`.

## Companies by Industry

The SEC classifies companies using SIC (Standard Industrial Classification) codes:

```python
from edgar.reference import get_companies_by_industry

# Software companies (SIC 7372)
software = get_companies_by_industry(sic=7372)
print(f"Software companies: {len(software)}")
```

### Industry Convenience Functions

Common industries have dedicated functions:

```python
from edgar.reference import (
    get_banking_companies,
    get_pharmaceutical_companies,
    get_software_companies,
    get_semiconductor_companies,
    get_oil_gas_companies,
    get_real_estate_companies,
    get_insurance_companies,
    get_retail_companies,
    get_biotechnology_companies,
    get_investment_companies,
)

banks = get_banking_companies()
pharma = get_pharmaceutical_companies()
```

## Companies by State

Find companies by their state of incorporation:

```python
from edgar.reference import get_companies_by_state

delaware = get_companies_by_state("DE")
print(f"Delaware companies: {len(delaware):,}")

california = get_companies_by_state("CA")
print(f"California companies: {len(california):,}")
```

## Popular Company Lists

Curated lists useful for demos, testing, and quick analysis:

```python
from edgar.reference import (
    get_popular_companies,
    get_faang_companies,
    get_tech_giants,
    get_dow_jones_sample,
    PopularityTier,
)

# All popular companies
popular = get_popular_companies()

# By popularity tier
mega_cap = get_popular_companies(PopularityTier.MEGA_CAP)       # Top 10
top_50 = get_popular_companies(PopularityTier.POPULAR)          # Top 50
mainstream = get_popular_companies(PopularityTier.MAINSTREAM)    # Top 100

# Named groups
faang = get_faang_companies()         # Meta, Apple, Amazon, Netflix, Google
tech = get_tech_giants()              # Major tech companies
dow = get_dow_jones_sample()          # Dow Jones sample
```

## Form Descriptions

Look up what any SEC form type means:

```python
from edgar.reference import describe_form

print(describe_form("10-K"))
# Form 10-K: Annual report for public companies

print(describe_form("DEF 14A"))
# Form DEF 14A: Definitive proxy statement

print(describe_form("SC 13D"))
# Form SC 13D: Beneficial ownership report (>5%)

# Without the "Form" prefix
print(describe_form("8-K", prepend_form=False))
# Current report
```

## CUSIP-to-Ticker Mapping

A CUSIP is a 9-character identifier used in securities trading. EdgarTools includes a CUSIP-to-ticker mapping, primarily used by the 13F institutional holdings parser:

```python
from edgar.reference import cusip_ticker_mapping, get_ticker_from_cusip

# Single lookup
ticker = get_ticker_from_cusip("037833100")  # Apple's CUSIP
print(f"037833100 -> {ticker}")  # AAPL

# Full mapping as DataFrame (indexed by CUSIP)
mapping = cusip_ticker_mapping()
print(f"Total CUSIP mappings: {len(mapping):,}")
```

## Place Codes and Filer Classification

The SEC uses internal codes for states and countries. EdgarTools decodes these and classifies filers:

```python
from edgar.reference import (
    get_place_name,
    get_filer_type,
    is_us_company,
    is_foreign_company,
    is_canadian_company,
)

# Decode place codes
get_place_name("DE")    # "Delaware"
get_place_name("X0")    # "United Kingdom"
get_place_name("A6")    # "Alberta, Canada"

# Classify filer type
get_filer_type("DE")    # "Domestic"
get_filer_type("X0")    # "Foreign"
get_filer_type("A6")    # "Canadian"

# Boolean checks
is_us_company("DE")         # True
is_foreign_company("X0")    # True
is_canadian_company("A6")   # True
```

## Building Research Datasets

The `CompanySubset` class provides a fluent interface for building precise company selections:

```python
from edgar.reference import CompanySubset

# 50 random NYSE/Nasdaq companies (reproducible)
research_set = (CompanySubset()
    .from_exchange(["NYSE", "Nasdaq"])
    .sample(50, random_state=42)
    .get())

print(f"Research set: {len(research_set)} companies")
```

### Stratified Sampling

Maintain exchange proportions in your sample:

```python
from edgar.reference import get_stratified_sample

sample = get_stratified_sample(n=100, stratify_by="exchange", random_state=42)
print(sample["exchange"].value_counts(normalize=True))
```

### Filtering and Combining

```python
from edgar.reference import (
    filter_companies,
    exclude_companies,
    combine_company_sets,
    intersect_company_sets,
    get_all_companies,
)

all_companies = get_all_companies()

# Include specific tickers
faang = filter_companies(all_companies, ticker_list=["META", "AAPL", "AMZN", "NFLX", "GOOGL"])

# Exclude specific companies
non_tech = exclude_companies(all_companies, ticker_list=["AAPL", "MSFT", "GOOGL"])

# Set operations
nyse = get_companies_by_exchanges("NYSE")
popular = get_popular_companies()
nyse_popular = intersect_company_sets([nyse, popular])
```

For the full CompanySubset API, see the [Company Subsets](../company-subsets.md) guide.

## Offline Setup

The bundled parquet covers ~10,600 exchange-listed tickers. For the **full SEC ticker universe** — including recent IPOs, mutual funds, and non-exchange filers — download reference data locally:

```python
from edgar import download_edgar_data, use_local_storage

# One-time download (~50 MB, takes a few seconds)
download_edgar_data(submissions=False, facts=False, reference=True)

# Enable local storage
use_local_storage()

# Now all lookups use the complete local data
company = Company("AAPL")
```

!!! info "What gets downloaded"

    | File | Content |
    |------|---------|
    | `company_tickers.json` | All SEC-registered tickers with CIK |
    | `company_tickers_exchange.json` | Tickers with exchange information |
    | `mutual_fund_tickers.json` | Mutual fund ticker-to-CIK mappings |

    Downloaded files are stored in `~/.edgar/reference/` (or your configured data directory).

For full offline capabilities beyond reference data (submissions, facts, filing documents), see the [Local Storage](local-storage.md) guide.

## Quick Reference

```python
from edgar import Company, download_edgar_data, use_local_storage
from edgar.reference import *
from edgar.reference.tickers import find_cik

# ── Ticker / CIK ──
Company("AAPL")                             # Ticker -> full company object
find_cik("AAPL")                            # Ticker -> CIK only (lightweight)

# ── By exchange ──
get_companies_by_exchanges("NYSE")          # Single exchange
get_companies_by_exchanges(["NYSE", "Nasdaq"])  # Multiple

# ── By industry / state ──
get_companies_by_industry(sic=7372)         # By SIC code
get_companies_by_state("DE")                # By incorporation state

# ── Popular companies ──
get_popular_companies()                     # All popular
get_faang_companies()                       # FAANG
get_tech_giants()                           # Major tech
get_banking_companies()                     # Banks (+ pharma, software, etc.)

# ── Form descriptions ──
describe_form("10-K")                       # "Form 10-K: Annual report..."

# ── CUSIP ──
get_ticker_from_cusip("037833100")          # CUSIP -> ticker
cusip_ticker_mapping()                      # Full mapping DataFrame

# ── Place codes ──
get_place_name("DE")                        # "Delaware"
get_filer_type("DE")                        # "Domestic"
is_us_company("DE")                         # True

# ── Research datasets ──
CompanySubset().from_exchange("NYSE").sample(100).get()
get_stratified_sample(n=100, stratify_by="exchange")
get_random_sample(n=50)

# ── Full offline setup ──
download_edgar_data(submissions=False, facts=False, reference=True)
use_local_storage()
```

## Related

- **[Find a Company](finding-companies.md)** — Ticker lookup, CIK, name search, screening
- **[Company Subsets](../company-subsets.md)** — Full CompanySubset API and advanced dataset creation
- **[Company Classification](company-classification.md)** — Filer types, business categories, SIC codes
- **[Local Storage](local-storage.md)** — Full offline setup for submissions, facts, and filings
