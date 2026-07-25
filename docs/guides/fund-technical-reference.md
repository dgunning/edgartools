# Fund Classes Technical Reference

Technical reference for the edgartools fund API. This guide covers every class, method, property, and DataFrame schema an agent needs to build fund analysis features.

---

## Architecture Overview

```
Fund("VFINX")
  |
  +-- FundCompany (CIK 102909)          # Registered investment company
  |     +-- FundSeries (S000002277)     # Investment strategy
  |           +-- FundClass (C000006293, VFINX)   # Share class with ticker
  |           +-- FundClass (C000006294, VFIAX)   # Admiral shares
  |
  +-- get_filings(form="NPORT-P") --> Filing --> filing.obj() --> FundReport
  +-- get_filings(form="N-MFP3")  --> Filing --> filing.obj() --> MoneyMarketFund
  +-- get_filings(form="N-CEN")   --> Filing --> filing.obj() --> FundCensus
  +-- get_filings(form="N-CSR")   --> Filing --> filing.obj() --> FundShareholderReport
```

Four filing types, four data objects. Each has a `from_filing()` classmethod and returns DataFrames via purpose-specific methods.

---

## Entry Points

```python
from edgar import Fund, find_funds, find_fund
from edgar import FundReport, MoneyMarketFund, FundCensus, FundShareholderReport
```

| Function | Input | Returns | Notes |
|----------|-------|---------|-------|
| `Fund(identifier)` | ticker, series ID, class ID, or CIK | `Fund` | Smart resolver; caches after first call |
| `find_fund(identifier)` | any identifier | `FundCompany`, `FundSeries`, or `FundClass` | Lower-level; returns the raw entity |
| `find_funds(name, search_type)` | name fragment | `list` of records | `search_type`: `"series"` (default), `"company"`, `"class"` |

---

## Fund (the universal entry point)

**Location:** `edgar/funds/core.py`

### Constructor

```python
fund = Fund("VFINX")     # Mutual fund ticker
fund = Fund("SPY")        # ETF ticker
fund = Fund("S000002277") # Series ID
fund = Fund("C000006293") # Class ID
fund = Fund(102909)        # CIK (int or str)
```

Resolution is automatic. Tickers resolve via cached mutual fund tickers (zero HTTP on warm cache). ETFs get synthetic series IDs (`ETF_{cik}`).

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Name of the resolved entity |
| `ticker` | `str` or `None` | Ticker (only when a FundClass was resolved) |
| `identifier` | `str` | Primary ID: class_id, series_id, or CIK string |
| `company` | `FundCompany` or `None` | Parent investment company |
| `series` | `FundSeries` or `None` | Fund series |
| `share_class` | `FundClass` or `None` | Specific share class |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_filings(**kwargs)` | `Filings` | Company-level filings; supports `form=`, `amendments=` |
| `get_filings(series_only=True, form=...)` | `Filings` | Series-scoped via SEC browse-edgar; empty if the series has no such filings |
| `get_latest_report(form='NPORT-P')` | report object or `None` | Shortcut: first filing -> `obj()` |
| `get_portfolio()` | `DataFrame` or `None` | Latest NPORT-P -> `investment_data()` |
| `get_series()` | `FundSeries` or `None` | The series for this ticker |
| `list_series()` | `list[FundSeries]` | All series in the company |
| `list_classes()` | `list[FundClass]` | All share classes in the series |
| `get_resolution_diagnostics()` | `dict` | Debug info: how identifier was resolved |

### Hierarchy Classes

**FundCompany** extends `Entity`. Has `all_series: list[FundSeries]`, `list_series()`, and all inherited Entity methods (`get_filings()`, `get_facts()`, etc.).

**FundSeries** has `series_id`, `name`, `fund_classes: list[FundClass]`, `fund_company: FundCompany`, `get_classes()`, `get_filings()`.

**FundClass** has `class_id`, `name`, `ticker`, `series: FundSeries`, `get_classes()` (returns sibling classes in the series).

---

## FundReport (N-PORT-P)

**Location:** `edgar/funds/reports.py`
**Forms:** `NPORT-P`, `NPORT-EX`, `N-PORT`, `N-PORT/A`

Monthly portfolio holdings filed by mutual funds and ETFs. The richest fund data source -- contains every position with fair value, asset type, derivatives, and fund-level metrics.

### Access

```python
fund = Fund("VFINX")
report = fund.get_latest_report()              # default is NPORT-P
report = fund.get_latest_report(form="NPORT-P")

# Or from a filing directly
filing = fund.get_filings(form="NPORT-P")[0]
report = filing.obj()                          # returns FundReport
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | `"{registrant} - {series_name}"` |
| `cik` | `int` | Fund company CIK |
| `series_id` | `str` | SEC series ID |
| `reporting_period` | `str` | e.g., `"2024-12-31"` |
| `general_info` | `GeneralInfo` | Registrant, series, LEI, fiscal year end |
| `fund_info` | `FundInfo` | Total assets, liabilities, net assets, returns, flows |
| `investments` | `list[InvestmentOrSecurity]` | All portfolio positions |
| `derivatives` | `list[InvestmentOrSecurity]` | Positions where `is_derivative=True` |
| `non_derivatives` | `list[InvestmentOrSecurity]` | Non-derivative positions |
| `filing` | `Filing` | Back-reference to the source filing |

### DataFrame Methods

#### `investment_data(include_derivatives=True, include_ticker_metadata=False)` -> DataFrame

All portfolio positions sorted by absolute USD value descending.

| Column | Type | Description |
|--------|------|-------------|
| `name` | str | Security name |
| `title` | str | Security title |
| `lei` | str | LEI of issuer |
| `cusip` | str | CUSIP |
| `ticker` | str | Ticker (if resolvable) |
| `isin` | str | ISIN |
| `balance` | float | Quantity held |
| `units` | str | Unit type (e.g., "NS" for number of shares) |
| `value_usd` | float | Fair value in USD |
| `pct_value` | float | Percentage of net assets |
| `payoff_profile` | str | Long/Short/N/A |
| `asset_category` | str | EC (equity common), DBT (debt), etc. |
| `issuer_category` | str | CORP, UST, MUN, etc. |
| `currency_code` | str | ISO currency code |
| `investment_country` | str | Country of investment |
| `is_derivative` | bool | Whether this is a derivative position |
| `maturity_date` | str | For debt securities |
| `annualized_rate` | float | Coupon/interest rate |
| `is_default` | bool | Whether in default |
| `derivative_type` | str | FWD/SWP/FUT/OPT/SWO or None |
| `notional_amount` | float | Derivative notional |
| `counterparty` | str | Derivative counterparty |

When `include_ticker_metadata=True`, adds `ticker_resolution_method` and `ticker_resolution_confidence`.

#### `securities_data()` -> DataFrame

Same as `investment_data(include_derivatives=False)`. Non-derivative positions only.

#### `derivatives_data()` -> DataFrame

All derivative positions with columns: name, title, cusip, value_usd, pct_value, derivative_type, notional_amount, counterparty, reference, unrealized_pnl.

#### Specialized Derivative DataFrames

| Method | Returns | Key Columns |
|--------|---------|-------------|
| `swaps_data()` | DataFrame | notional, currency, receive/pay leg fields (fixed_rate, floating_index, spread, tenor), unrealized_appreciation |
| `swaptions_data()` | DataFrame | put_or_call, exercise_price, expiration_date, delta, nested swap info |
| `options_data()` | DataFrame | put_or_call, written_or_purchased, share_number, exercise_price, expiration_date, reference fields |
| `forwards_data()` | DataFrame | currency_sold/purchased, amount_sold/purchased, settlement_date |
| `futures_data()` | DataFrame | reference_entity, expiration_date, notional_amount |

### Sub-Models

**GeneralInfo** -- `registrant_name`, `registrant_cik`, `series_name`, `series_id`, `series_lei`, `rep_period_date`, `fiscal_year_end`.

**FundInfo** -- `total_assets`, `total_liabilities`, `net_assets`, `monthly_returns` (list of 3), `monthly_flows` (list of 3), credit spread risk metrics, interest rate risk DV01/DV100 by period.

**InvestmentOrSecurity** -- Full position record. Key fields: `name`, `title`, `cusip`, `lei`, `balance`, `units`, `value_usd`, `pct_value`, `payoff_profile`, `asset_category`, `issuer_category`, `currency_code`, `investment_country`, `is_derivative`, `deriv_info` (optional `DerivativeInfo`).

---

## MoneyMarketFund (N-MFP2/N-MFP3)

**Location:** `edgar/funds/nmfp3.py`
**Forms:** `N-MFP2`, `N-MFP2/A`, `N-MFP3`, `N-MFP3/A`

Monthly money market fund reports. N-MFP3 replaced N-MFP2 in June 2024. Both are handled transparently.

### Access

```python
fund = Fund("VMFXX")
mmf = fund.get_latest_report(form="N-MFP3")

# Or from filing
filing = fund.get_filings(form="N-MFP3")[0]
mmf = filing.obj()   # returns MoneyMarketFund
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Series name |
| `cik` | `int` | Fund company CIK |
| `series_id` | `str` | SEC series ID |
| `report_date` | `str` | e.g., `"2024-12-31"` |
| `fund_category` | `str` | e.g., `"Prime"`, `"Government"` |
| `net_assets` | `float` | Total net assets |
| `num_securities` | `int` | Number of portfolio securities |
| `num_share_classes` | `int` | Number of share classes |
| `average_maturity_wam` | `int` | Weighted average maturity (days) |
| `average_maturity_wal` | `int` | Weighted average life (days) |
| `filing` | `Filing` | Back-reference |

### DataFrame Methods

| Method | Returns | Key Columns |
|--------|---------|-------------|
| `portfolio_data()` | DataFrame | issuer, title, cusip, isin, category, maturity_wam, maturity_wal, yield, market_value, amortized_cost, pct_of_nav, daily_liquid, weekly_liquid, has_repo |
| `share_class_data()` | DataFrame | class_name, class_id, min_investment, net_assets, shares_outstanding |
| `yield_history()` | DataFrame | date, gross_yield (7-day gross yield time series) |
| `nav_history()` | DataFrame | Daily NAV per share time series |
| `liquidity_history()` | DataFrame | Daily/weekly liquid percentage time series |
| `collateral_data()` | DataFrame | Repurchase agreement collateral (security + collateral issuer fields) |
| `holdings_by_category()` | DataFrame | investment_category, count, total_market_value, total_pct |

### Sub-Models

**PortfolioSecurity** -- `issuer`, `title`, `cusip`, `isin`, `lei`, `investment_category`, `maturity_date_wam`, `maturity_date_wal`, `final_maturity_date`, `coupon_or_yield`, `market_value`, `amortized_cost`, `pct_of_nav`, `is_daily_liquid`, `is_weekly_liquid`, credit `ratings`, optional `repurchase_agreement`.

**ShareClassInfo** -- `class_name`, `class_id`, `min_investment`, `net_assets`, `shares_outstanding`, time series for daily NAV, flows, and 7-day net yields.

**SeriesLevelInfo** -- `fund_category`, `wam_days`, `wal_days`, `net_assets`, `shares_outstanding`, time series for 7-day gross yields, daily NAV, and liquidity ratios.

---

## FundCensus (N-CEN)

**Location:** `edgar/funds/ncen.py`
**Forms:** `N-CEN`, `N-CEN/A`

Annual fund census covering operational structure: advisers, custodians, transfer agents, broker-dealers, ETF authorized participants, and board of directors.

### Access

```python
fund = Fund("VFINX")
census = fund.get_latest_report(form="N-CEN")

filing = fund.get_filings(form="N-CEN")[0]
census = filing.obj()   # returns FundCensus
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Registrant name |
| `cik` | `int` | CIK |
| `lei` | `str` | LEI |
| `report_date` | `str` | Filing date |
| `series_ids` | `list[str]` | All series IDs |
| `series_id` | `str` | First series ID |
| `num_series` | `int` | Number of series in this filing |
| `total_series` | `int` | Total series from registrant info |
| `classification_type` | `str` | Company classification |
| `is_etf_company` | `bool` | Whether any series is an ETF |
| `filing` | `Filing` | Back-reference |

### DataFrame Methods

| Method | Returns | Key Columns |
|--------|---------|-------------|
| `series_data()` | DataFrame | name, series_id, lei, fund_type, avg_net_assets, aggregate_commission, num_advisers, num_custodians, has_etf |
| `service_providers()` | DataFrame | series_name, role, provider_name, lei, affiliated |
| `broker_data()` | DataFrame | Broker-dealer and commission records by series |
| `director_data()` | DataFrame | Board of directors with CRD numbers and interested-person flag |
| `etf_data()` | DataFrame | ETF-specific: exchange, ticker, creation_unit_size, in_kind_purchase_pct, authorized participants |

### Sub-Models

**RegistrantInfo** -- name, CIK, LEI, address, classification, total_series, directors, CCO, accountant, underwriter.

**FundSeriesInfo** -- name, series_id, LEI, fund_type, is_diversified, avg_net_assets, lists of advisers/custodians/transfer_agents/admins/pricing_services/shareholder_agents, broker dealers, securities lending info, optional ETFInfo.

**ETFInfo** -- exchange, ticker, creation_unit_size, in_kind_purchase_pct, in_kind_redemption_pct, list of `AuthorizedParticipant`.

---

## FundShareholderReport (N-CSR/N-CSRS)

**Location:** `edgar/funds/ncsr.py`
**Forms:** `N-CSR`, `N-CSR/A`, `N-CSRS`, `N-CSRS/A`

Annual (N-CSR) and semiannual (N-CSRS) shareholder reports. Parsed from Inline XBRL using the `oef:` (Open-End Fund) taxonomy. Contains expense ratios, performance returns, and top holdings per share class.

### Access

```python
fund = Fund("VFINX")
report = fund.get_latest_report(form="N-CSR")

filing = fund.get_filings(form="N-CSR")[0]
report = filing.obj()   # returns FundShareholderReport
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `fund_name` | `str` | Fund name |
| `report_type` | `str` | `"N-CSR"` or `"N-CSRS"` |
| `is_annual` | `bool` | `True` for N-CSR |
| `net_assets` | `float` | Fund net assets |
| `portfolio_turnover` | `float` | Turnover ratio |
| `num_share_classes` | `int` | Number of share classes |
| `share_classes` | `list[ShareClassInfo]` | Per-class data |
| `cik` | `int` | CIK |
| `series_id` | `str` | Series ID |
| `filing` | `Filing` | Back-reference |

### DataFrame Methods

| Method | Returns | Key Columns |
|--------|---------|-------------|
| `performance_data()` | DataFrame | class_name, ticker, period, return_pct, inception_date (one row per annual return per class) |
| `expense_data()` | DataFrame | class_name, ticker, expense_ratio_pct, expenses_paid, advisory_fees_paid |
| `holdings_data()` | DataFrame | class_name, holding, pct_of_nav, pct_of_total_inv |

### Sub-Models

**ShareClassInfo** -- `class_name`, `class_ticker`, `expense_ratio_pct`, `expenses_paid_amt`, `advisory_fees_paid`, `annual_returns: list[AnnualReturn]`, `holdings: list[Holding]`, `holdings_count`.

**AnnualReturn** -- `period_label`, `return_pct`, `inception_date`.

**Holding** -- `name`, `pct_of_nav`, `pct_of_total_inv`.

---

## Common Patterns

### Get top holdings for any fund

```python
fund = Fund("VFINX")
df = fund.get_portfolio()
top10 = df[['name', 'ticker', 'value_usd', 'pct_value']].head(10)
```

### Compare expense ratios across share classes

```python
fund = Fund("VFINX")
report = fund.get_latest_report(form="N-CSR")
report.expense_data()
# class_name | ticker | expense_ratio_pct | expenses_paid | advisory_fees_paid
```

### Money market yield and liquidity

```python
fund = Fund("VMFXX")
mmf = fund.get_latest_report(form="N-MFP3")
mmf.yield_history()       # 7-day gross yield time series
mmf.liquidity_history()   # daily/weekly liquid percentages
mmf.holdings_by_category()  # portfolio breakdown by type
```

### Fund service provider analysis

```python
fund = Fund("VFINX")
census = fund.get_latest_report(form="N-CEN")
census.service_providers()   # all providers across all series
census.etf_data()            # ETF-specific: exchange, APs, creation units
```

### Derivative exposure analysis

```python
fund = Fund("PIMIX")
report = fund.get_latest_report()
report.derivatives_data()    # all derivatives summary
report.swaps_data()          # interest rate / credit swaps with leg details
report.options_data()        # options with strike, expiry, delta
report.forwards_data()       # FX forwards with currency pairs
report.futures_data()        # futures with expiration
```

### Navigate from report back to filing

```python
report = fund.get_latest_report()
report.filing                # Filing object
report.filing.accession_no   # accession number
report.cik                   # fund company CIK
report.series_id             # series ID
```

### Fund hierarchy traversal

```python
fund = Fund("VFINX")

# Up: share class -> series -> company
fund.share_class.series.fund_company.cik

# Down: company -> series -> classes
for series in fund.list_series():
    print(series.name)
    for cls in series.get_classes():
        print(f"  {cls.ticker} - {cls.name}")
```

---

## Reference Data

### FundReferenceData

**Location:** `edgar/funds/reference.py`

Bulk SEC fund data cached in memory. Normalized into company, series, and class indexes.

```python
from edgar.funds.reference import get_fund_reference_data

ref = get_fund_reference_data()
ref.get_company(cik)                     # -> FundCompanyRecord
ref.get_series(series_id)                # -> FundSeriesRecord
ref.get_class(class_id)                  # -> FundClassRecord
ref.get_class_by_ticker(ticker)          # -> FundClassRecord
ref.get_series_for_company(cik)          # -> list[FundSeriesRecord]
ref.get_classes_for_series(series_id)    # -> list[FundClassRecord]
ref.get_hierarchical_info(identifier)    # -> (company, series, class_record)
ref.find_by_name(name_fragment, search_type)  # substring search
ref.to_dataframe()                       # full flat DataFrame
```

### Record Types

**FundCompanyRecord** -- `cik`, `name`, `state`, `country`.

**FundSeriesRecord** -- `series_id`, `name`, `cik`, `status`.

**FundClassRecord** -- `class_id`, `name`, `ticker`, `series_id`, `cik`, `status`.

---

## Ticker Resolution

**Location:** `edgar/funds/series_resolution.py`, `edgar/funds/ticker_resolution.py`

| Function | Purpose |
|----------|---------|
| `is_fund_ticker(ticker)` | O(1) check against cached frozenset of mutual fund tickers |
| `TickerSeriesResolver.resolve_ticker_to_series(ticker)` | Ticker -> list of `SeriesInfo` (cached, 1000 entries) |
| `TickerSeriesResolver.get_primary_series(ticker)` | Ticker -> first series ID |
| `resolve_fund_identifier(identifier)` | Any identifier -> CIK int |

ETFs without formal series IDs get synthetic `ETF_{cik}` identifiers.

---

## Caching

All resolution and reference data is LRU-cached. After the first call, subsequent lookups are instant with zero HTTP overhead.

| Cache | Scope | Size |
|-------|-------|------|
| `get_fund_object()` | Fund hierarchy builder | 16 entries |
| `get_bulk_fund_data()` | SEC CSV download | 1 entry (singleton) |
| `get_fund_reference_data()` | Reference data index | 1 entry (singleton) |
| `TickerSeriesResolver.resolve_ticker_to_series()` | Ticker resolution | 1000 entries |
| `_fund_ticker_set()` | Ticker existence check | 1 entry (singleton) |
| `FundReport.investment_data()` | Per-report DataFrame | Keyed by `(include_derivatives, include_ticker_metadata)` |

---

## Form Type Constants

Import these for filtering:

```python
from edgar import NPORT_FORMS, MONEY_MARKET_FORMS, NCEN_FORMS, NCSR_FORMS
```

| Constant | Forms | Data Object |
|----------|-------|-------------|
| `NPORT_FORMS` | `NPORT-P`, `NPORT-EX`, `N-PORT`, `N-PORT/A` | `FundReport` |
| `MONEY_MARKET_FORMS` | `N-MFP2`, `N-MFP2/A`, `N-MFP3`, `N-MFP3/A` | `MoneyMarketFund` |
| `NCEN_FORMS` | `N-CEN`, `N-CEN/A` | `FundCensus` |
| `NCSR_FORMS` | `N-CSR`, `N-CSR/A`, `N-CSRS`, `N-CSRS/A` | `FundShareholderReport` |

---

## Key Constraints

**`series_only=True` is series-scoped, not registrant-scoped.** It resolves the series through SEC browse-edgar with the series ID as the CIK parameter, so the result contains only that series' filings; omitting it returns the registrant's filings, which for a multi-series trust includes sibling series. The target series is resolved from a ticker, series ID, or class ID alike. A series with no matching filings yields an empty `Filings`, never a fallback to the registrant.

**ETF synthetic series IDs.** `ETF_{cik}` identifiers work within edgartools but are not real SEC series IDs.

**N-MFP version differences.** N-MFP2 uses weekly Friday snapshots for time series; N-MFP3 uses daily entries. Both are parsed transparently into the same model, but N-MFP2 yield/NAV histories will have fewer data points.

**N-CSR XBRL dependency.** `FundShareholderReport.from_filing()` calls `filing.xbrl()`, not `filing.xml()`. Filings without Inline XBRL will return `None` from `get_latest_report(form="N-CSR")`.

**Use `Fund()`, not `Company()`.** `Company("VFINX")` does not understand the fund hierarchy. Always use `Fund()` for investment funds and ETFs.
