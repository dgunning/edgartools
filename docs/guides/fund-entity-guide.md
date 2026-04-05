---
description: Look up mutual funds and ETFs by ticker, series ID, or CIK. Navigate fund hierarchies and access portfolio reports with Python using edgartools.
---

# Fund Entities: Look Up Mutual Funds and ETFs with Python

The `Fund` class is the single entry point for working with investment funds. Give it a ticker, series ID, or CIK, and it resolves the full fund hierarchy -- company, series, and share classes -- in one call.

```python
from edgar import Fund

fund = Fund("VFINX")
fund
```

Three lines to get a fully resolved fund entity with company, series, share class, and ticker information.

---

## Create a Fund

Pass any identifier to `Fund()`:

```python
from edgar import Fund

fund = Fund("VFINX")           # Mutual fund ticker
fund = Fund("SPY")             # ETF ticker
fund = Fund("S000002277")      # Series ID
fund = Fund("0000102909")      # CIK
```

`Fund()` determines the identifier type automatically, resolves it to the appropriate entity (share class, series, or company), and wires up the full hierarchy.

---

## Search for Funds

Use `find_funds()` to search by name fragment:

```python
from edgar import find_funds

find_funds("vanguard")                         # Search fund series (default)
find_funds("growth", search_type="series")     # Explicit series search
find_funds("vanguard", search_type="company")  # Search fund companies
find_funds("admiral", search_type="class")     # Search share classes
```

`find_funds()` returns a list of matching records (not `Fund` objects). Each record includes an identifier you can pass to `Fund()` for full resolution.

---

## Navigate the Hierarchy

SEC funds have a three-level hierarchy: **Company** > **Series** > **Share Class**. `Fund` exposes all three levels:

```python
fund = Fund("VFINX")

fund.company       # FundCompany -- the registered investment company
fund.series        # FundSeries -- the specific fund within the company
fund.share_class   # FundClass -- the specific share class (has the ticker)

fund.name          # Name of the resolved entity
fund.ticker        # Ticker symbol (only for share classes)
fund.identifier    # Primary identifier (class ID, series ID, or CIK)
```

### List all series in a company

```python
fund = Fund("0000102909")      # Vanguard by CIK
for series in fund.list_series():
    print(series.series_id, series.name)
```

### List all share classes in a series

```python
fund = Fund("VFINX")
for cls in fund.list_classes():
    print(cls.class_id, cls.ticker, cls.name)
```

---

## Get Filings

Retrieve filings for the fund entity:

```python
fund = Fund("VFINX")

# All filings for the parent company
filings = fund.get_filings(form="NPORT-P")

# Series-specific filings via EFTS full-text search
filings = fund.get_filings(series_only=True, form="NPORT-P")
```

The `series_only=True` parameter uses EFTS to search for filings mentioning this fund's specific series ID, which filters more precisely than company-level filings.

---

## Get the Latest Report

Get a parsed report object from the latest filing:

```python
fund = Fund("VFINX")

report = fund.get_latest_report()                  # Latest NPORT-P (default)
report = fund.get_latest_report(form="N-MFP3")     # Latest money market report
report = fund.get_latest_report(form="N-CEN")      # Latest fund census
report = fund.get_latest_report(form="N-CSR")      # Latest shareholder report
```

This chains `get_filings()` -> first filing -> `filing.obj()` in a single call.

---

## Get Portfolio Holdings

Get the latest portfolio holdings as a DataFrame in one line:

```python
fund = Fund("VFINX")
df = fund.get_portfolio()
```

This is a convenience method that chains: latest NPORT-P filing -> `FundReport` -> `investment_data()`.

---

## Common Analysis Patterns

### Top holdings for a fund

```python
fund = Fund("VFINX")
df = fund.get_portfolio()
if df is not None:
    print(df[['name', 'ticker', 'value_usd', 'pct_value']].head(10))
```

### Compare share classes

```python
fund = Fund("VFINX")
for cls in fund.list_classes():
    print(f"{cls.ticker or cls.class_id:10s} {cls.name}")
```

### Get the series for a ticker

```python
fund = Fund("VFINX")
series = fund.get_series()
print(series.name, series.series_id)
```

---

## Properties Quick Reference

| Property | Returns | Description |
|----------|---------|-------------|
| `name` | `str` | Name of the resolved entity |
| `ticker` | `str` or `None` | Ticker symbol (share classes only) |
| `identifier` | `str` | Primary identifier (class ID, series ID, or CIK) |
| `company` | `FundCompany` or `None` | Parent investment company |
| `series` | `FundSeries` or `None` | Fund series |
| `share_class` | `FundClass` or `None` | Specific share class |

---

## Methods Quick Reference

| Method | Returns | Description |
|--------|---------|-------------|
| `get_filings(**kwargs)` | `Filings` | Filings for this fund entity |
| `get_filings(series_only=True, form=...)` | `Filings` | Series-specific filings via EFTS |
| `get_latest_report(form='NPORT-P')` | report object or `None` | Latest parsed report |
| `get_portfolio()` | `DataFrame` or `None` | Latest NPORT-P portfolio holdings |
| `get_series()` | `FundSeries` or `None` | Specific series for ticker |
| `list_series()` | `list[FundSeries]` | All series in the company |
| `list_classes()` | `list[FundClass]` | All share classes in the series |
| `get_resolution_diagnostics()` | `dict` | How the identifier was resolved |

---

## Things to Know

**Cached resolution.** After the first `Fund()` call, reference data is cached in memory. Subsequent lookups are instant (0 HTTP calls for warm cache).

**ETF synthetic series IDs.** ETFs often lack formal SEC series IDs. EdgarTools creates synthetic IDs (e.g., `ETF_12345`) for internal tracking. These work with `Fund()` but won't appear in SEC filings.

**EFTS 100-result limit.** When using `series_only=True`, EFTS returns at most 100 results per request. For funds with hundreds of filings, omit `series_only` to get the full history from the company's filing index.

**`find_funds()` returns raw records.** The search function returns `FundSeriesRecord`, `FundCompanyRecord`, or `FundClassRecord` objects -- not `Fund` instances. Use an identifier from the record to create a `Fund`.

**Company vs Fund.** Use `Company()` for operating companies (Apple, Microsoft). Use `Fund()` for investment funds and ETFs (VFINX, SPY). `Fund()` understands the company-series-class hierarchy that `Company()` does not.

---

## Related

- [Fund Portfolio Holdings (N-PORT)](nport-data-object-guide.md) -- monthly portfolio positions
- [Money Market Funds (N-MFP)](moneymarketfund-data-object-guide.md) -- money market holdings and yields
- [Fund Census (N-CEN)](fundcensus-data-object-guide.md) -- annual operational census
- [Fund Shareholder Reports (N-CSR)](fundshareholderreport-data-object-guide.md) -- expense ratios and performance
- [Fund Voting Records (N-PX)](npx-data-object-guide.md) -- proxy voting records
