# ProxyStatement Class Documentation

## Overview

The `ProxyStatement` class provides structured access to DEF 14A (Proxy Statement) filings from the SEC. It extracts executive compensation, pay vs performance metrics, and governance information from XBRL data using the SEC's Executive Compensation Disclosure (ECD) taxonomy.

**Key Features:**
- Access CEO (PEO) and NEO compensation data
- Retrieve Pay vs Performance metrics (TSR, peer group TSR, net income)
- Get 5-year time series DataFrames for compensation and performance
- Access governance indicators (insider trading policy)
- Support for individual executive data when dimensionally tagged

**Supported Forms:**
- `DEF 14A` - Definitive Proxy Statement
- `DEF 14A/A` - Amendment to Definitive Proxy Statement
- `DEFA14A` - Additional Definitive Proxy Materials
- `DEFM14A` - Definitive Proxy Statement (Merger)

## Common Actions

Quick reference for the most frequently used ProxyStatement methods:

### Get a Proxy Statement
```python
from edgar import Company

# Get latest proxy statement
company = Company("AAPL")
filing = company.get_filings(form="DEF 14A").latest()
proxy = filing.obj()

# Access CEO information
print(f"CEO: {proxy.peo_name}")
print(f"CEO Compensation: ${proxy.peo_total_comp:,}")
```

### Access Compensation Data
```python
# Single values (most recent year)
print(f"CEO Total Comp: ${proxy.peo_total_comp:,}")
print(f"CEO Actually Paid: ${proxy.peo_actually_paid_comp:,}")
print(f"NEO Avg Total: ${proxy.neo_avg_total_comp:,}")

# 5-year DataFrame
df = proxy.executive_compensation
print(df)
```

### Access Pay vs Performance
```python
# Key metrics
print(f"Company TSR: {proxy.total_shareholder_return}%")
print(f"Peer Group TSR: {proxy.peer_group_tsr}%")
print(f"Net Income: ${proxy.net_income:,}")

# 5-year DataFrame
pvp_df = proxy.pay_vs_performance
print(pvp_df)
```

### Check XBRL Availability
```python
if proxy.has_xbrl:
    # Full data available
    print(proxy.executive_compensation)
else:
    # Limited data (SRCs, EGCs, SPACs, funds)
    print("No XBRL data - company may be exempt from Pay vs Performance rules")
```

## Getting a Proxy Statement

### From a Company
```python
from edgar import Company

company = Company("MSFT")
filing = company.get_filings(form="DEF 14A").latest()
proxy = filing.obj()
```

### From a Filing Directly
```python
from edgar import Filing

# If you have the accession number
filing = Filing(company="AAPL", accession_number="0000320193-24-000005")
proxy = filing.obj()
```

### Multiple Years
```python
company = Company("AAPL")
proxy_filings = company.get_filings(form="DEF 14A").latest(5)

for filing in proxy_filings:
    proxy = filing.obj()
    print(f"{proxy.fiscal_year_end}: CEO Comp = ${proxy.peo_total_comp:,}")
```

## Core Properties

### Metadata Properties

| Property | Type | Description |
|----------|------|-------------|
| `form` | str | Form type (DEF 14A, DEFA14A, etc.) |
| `filing_date` | str | Date filed with SEC |
| `company_name` | str | Company legal name |
| `cik` | str | Central Index Key |
| `accession_number` | str | SEC accession number |
| `fiscal_year_end` | str | Fiscal year end date |
| `filing` | Filing | The source Filing object |
| `has_xbrl` | bool | Whether XBRL data is available |

### Executive Compensation Properties

| Property | Type | Description |
|----------|------|-------------|
| `peo_name` | str | Principal Executive Officer (CEO) name |
| `peo_total_comp` | Decimal | PEO total compensation from Summary Compensation Table |
| `peo_actually_paid_comp` | Decimal | PEO Compensation Actually Paid (CAP) |
| `neo_avg_total_comp` | Decimal | Non-PEO NEO average total compensation |
| `neo_avg_actually_paid_comp` | Decimal | Non-PEO NEO average CAP |

### Pay vs Performance Properties

| Property | Type | Description |
|----------|------|-------------|
| `total_shareholder_return` | Decimal | Company Total Shareholder Return (%) |
| `peer_group_tsr` | Decimal | Peer Group Total Shareholder Return (%) |
| `net_income` | Decimal | Net Income |
| `company_selected_measure` | str | Company-selected performance measure name |
| `company_selected_measure_value` | Decimal | Company-selected measure value |
| `performance_measures` | List[str] | List of all performance measures used |

### Governance Properties

| Property | Type | Description |
|----------|------|-------------|
| `insider_trading_policy_adopted` | bool | Whether company has adopted insider trading policy |

### DataFrame Properties

| Property | Type | Description |
|----------|------|-------------|
| `executive_compensation` | DataFrame | 5-year executive compensation time series |
| `pay_vs_performance` | DataFrame | 5-year pay vs performance metrics |

### Named Executive Properties

| Property | Type | Description |
|----------|------|-------------|
| `has_individual_executive_data` | bool | Whether individual executive dimensions available |
| `named_executives` | List[NamedExecutive] | Individual NEO data (when dimensionally tagged) |

## Working with DataFrames

### Executive Compensation DataFrame

The `executive_compensation` property returns a 5-year time series:

```python
df = proxy.executive_compensation
print(df)
```

**Columns:**
- `fiscal_year_end` - End of fiscal year
- `peo_total_comp` - PEO total from Summary Compensation Table
- `peo_actually_paid_comp` - PEO Compensation Actually Paid
- `neo_avg_total_comp` - Non-PEO NEO average total
- `neo_avg_actually_paid_comp` - Non-PEO NEO average CAP

**Example Output:**
```
  fiscal_year_end  peo_total_comp  peo_actually_paid_comp  neo_avg_total_comp  neo_avg_actually_paid_comp
0      2019-09-28      11555466.0             -828597148.0          7938224.0                -191302388.0
1      2020-09-26      14769259.0              281935670.0          9420983.0                   67386753.0
2      2021-09-25      98734394.0              474068485.0         26807144.0                  137823587.0
3      2022-09-24      99420097.0              -5907221.0          26856814.0                    4975574.0
4      2023-09-30      63209914.0              143466695.0         22013346.0                   49778878.0
```

### Pay vs Performance DataFrame

The `pay_vs_performance` property returns performance metrics aligned with compensation:

```python
pvp_df = proxy.pay_vs_performance
print(pvp_df)
```

**Columns:**
- `fiscal_year_end` - End of fiscal year
- `peo_actually_paid_comp` - CEO Compensation Actually Paid
- `neo_avg_actually_paid_comp` - NEO average CAP
- `total_shareholder_return` - Company TSR (cumulative)
- `peer_group_tsr` - Peer group TSR (cumulative)
- `net_income` - Net income
- `company_selected_measure_value` - Company KPI value

## Named Executives

When companies use dimensional XBRL tagging (~60% of filers), individual executive data is available:

```python
if proxy.has_individual_executive_data:
    for exec in proxy.named_executives:
        print(f"{exec.name} ({exec.role})")
        if exec.total_comp:
            print(f"  Total Comp: ${exec.total_comp:,}")
```

**NamedExecutive Fields:**
- `name` - Executive name
- `member_id` - XBRL member identifier
- `role` - Role (PEO, NEO, etc.)
- `total_comp` - Total compensation
- `actually_paid_comp` - Compensation actually paid
- `fiscal_year_end` - Fiscal year

## Common Workflows

### Compare CEO Pay Across Companies

```python
from edgar import Company

tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
results = []

for ticker in tickers:
    company = Company(ticker)
    filing = company.get_filings(form="DEF 14A").latest()

    if filing:
        proxy = filing.obj()
        if proxy.has_xbrl:
            results.append({
                'company': proxy.company_name,
                'ceo': proxy.peo_name,
                'total_comp': proxy.peo_total_comp,
                'actually_paid': proxy.peo_actually_paid_comp,
                'tsr': proxy.total_shareholder_return
            })

import pandas as pd
df = pd.DataFrame(results)
print(df.sort_values('total_comp', ascending=False))
```

### Analyze Pay vs Performance Trend

```python
company = Company("AAPL")
filing = company.get_filings(form="DEF 14A").latest()
proxy = filing.obj()

pvp = proxy.pay_vs_performance

# Calculate pay-for-performance alignment
pvp['pay_ratio'] = pvp['peo_actually_paid_comp'] / pvp['total_shareholder_return']

print("Pay vs Performance Analysis:")
print(pvp[['fiscal_year_end', 'peo_actually_paid_comp', 'total_shareholder_return', 'pay_ratio']])
```

### Track Compensation Over Time

```python
company = Company("MSFT")
filing = company.get_filings(form="DEF 14A").latest()
proxy = filing.obj()

comp_df = proxy.executive_compensation

# Calculate year-over-year changes
comp_df['peo_yoy_change'] = comp_df['peo_total_comp'].pct_change() * 100

print("CEO Compensation Trend:")
for _, row in comp_df.iterrows():
    change = f" ({row['peo_yoy_change']:+.1f}%)" if pd.notna(row['peo_yoy_change']) else ""
    print(f"{row['fiscal_year_end']}: ${row['peo_total_comp']:,.0f}{change}")
```

### Export Proxy Data

```python
company = Company("AAPL")
filing = company.get_filings(form="DEF 14A").latest()
proxy = filing.obj()

# Export compensation data
proxy.executive_compensation.to_csv("apple_exec_comp.csv", index=False)

# Export pay vs performance
proxy.pay_vs_performance.to_csv("apple_pvp.csv", index=False)
```

## Understanding XBRL Availability

Not all proxy statements contain XBRL data. The SEC's Pay vs Performance rules require XBRL for:
- Large accelerated filers
- Accelerated filers

Exempt from XBRL requirements:
- Smaller Reporting Companies (SRCs)
- Emerging Growth Companies (EGCs)
- SPACs
- Registered Investment Companies

```python
proxy = filing.obj()

if proxy.has_xbrl:
    # Full structured data available
    print(f"CEO: {proxy.peo_name}")
    print(f"Total Comp: ${proxy.peo_total_comp:,}")
else:
    # Must parse HTML for compensation data
    print("No XBRL - company likely exempt from Pay vs Performance rules")
    print(f"Filing available at: {proxy.filing.homepage_url}")
```

## Display and Representation

### Rich Display

ProxyStatement has a rich display showing key information:

```python
proxy = filing.obj()
print(proxy)
```

Shows:
- Form type and company name
- Filing date and fiscal year end
- Executive compensation table (PEO and NEO averages)
- Pay vs performance metrics (TSR, peer TSR, net income)
- Governance indicators
- Performance measures used

### String Representation

```python
str(proxy)  # Returns "DEF 14A: Apple Inc. - 2023-09-30"
```

## Error Handling

### No XBRL Data

```python
proxy = filing.obj()

if not proxy.has_xbrl:
    print("No structured compensation data available")
    # Fall back to manual review of filing
```

### Missing Values

```python
# Properties return None when data is not available
if proxy.peo_total_comp is not None:
    print(f"CEO Comp: ${proxy.peo_total_comp:,}")
else:
    print("CEO compensation not disclosed in XBRL")
```

### Empty DataFrames

```python
comp_df = proxy.executive_compensation

if comp_df.empty:
    print("No compensation time series data available")
else:
    print(comp_df)
```

## Best Practices

### 1. Check XBRL Availability First

```python
proxy = filing.obj()
if proxy.has_xbrl:
    # Process structured data
    pass
else:
    # Handle gracefully or skip
    pass
```

### 2. Use DataFrames for Analysis

```python
# Good - use DataFrame for multi-year analysis
df = proxy.executive_compensation
trend = df['peo_total_comp'].pct_change()

# Less efficient - query individual years manually
```

### 3. Handle Decimal Values

```python
# Properties return Decimal for precision
comp = proxy.peo_total_comp

# Convert to float for calculations if needed
if comp is not None:
    comp_float = float(comp)
```

### 4. Cache Proxy Objects

```python
# Good - reuse proxy object
proxy = filing.obj()
comp = proxy.executive_compensation
pvp = proxy.pay_vs_performance
ceo = proxy.peo_name

# Less efficient - creates proxy multiple times
comp = filing.obj().executive_compensation
pvp = filing.obj().pay_vs_performance
```

## Performance Considerations

### Lazy Loading

XBRL data is loaded lazily on first access:

```python
proxy = filing.obj()  # Fast - no XBRL loaded yet
print(proxy.peo_name)  # Triggers XBRL parsing
```

### Caching

Properties are cached after first access:

```python
# First call parses XBRL
comp = proxy.executive_compensation

# Subsequent calls use cache
comp2 = proxy.executive_compensation  # Instant
```

## Glossary

| Term | Definition |
|------|------------|
| **PEO** | Principal Executive Officer (typically CEO) |
| **NEO** | Named Executive Officer (top 5 highest-paid executives) |
| **SCT** | Summary Compensation Table |
| **CAP** | Compensation Actually Paid |
| **TSR** | Total Shareholder Return |
| **ECD** | Executive Compensation Disclosure (SEC taxonomy) |
| **SRC** | Smaller Reporting Company |
| **EGC** | Emerging Growth Company |
