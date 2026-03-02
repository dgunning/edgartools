---
description: Extract executive compensation, board composition, and shareholder proposals from SEC proxy statement filings.
---

# Proxy Statements (DEF 14A): Parse Executive Compensation and Governance Data

Form DEF 14A is a definitive proxy statement filed by public companies before annual shareholder meetings. It contains critical information about executive compensation, board composition, shareholder voting matters, and corporate governance. This guide details all data available from the `ProxyStatement` class for building views.

---

## Overview

| Property | Type | Description |
|----------|------|-------------|
| Class Name | `ProxyStatement` | |
| Forms Handled | `DEF 14A`, `DEFA14A`, `DEFM14A`, `DEF 14A/A` | |
| Module | `edgar.proxy` | |
| Source Data | XBRL (primary) + HTML (secondary) | |

### Form Type Descriptions

| Form | Description |
|------|-------------|
| `DEF 14A` | Definitive Proxy Statement - standard proxy filing |
| `DEFA14A` | Definitive Additional Proxy Soliciting Materials |
| `DEFM14A` | Definitive Proxy Statement relating to Merger or Acquisition |
| `DEF 14A/A` | Amendment to Definitive Proxy Statement |

### Data Source Reliability

| Source | Reliability | Description |
|--------|-------------|-------------|
| XBRL | High | Executive compensation, pay vs performance - standardized across all companies |
| HTML | Medium | Beneficial ownership, board info, proposals - requires parsing |

---

## Basic Metadata

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `form` | `str` | Form type | `"DEF 14A"` |
| `filing_date` | `str` | Date filed with SEC | `"2025-01-10"` |
| `fiscal_year_end` | `str` | Fiscal year end date | `"2024-09-28"` |
| `company_name` | `str` | Company legal name | `"Apple Inc."` |
| `cik` | `str` | Central Index Key | `"0000320193"` |
| `accession_number` | `str` | SEC accession number | `"0001308179-25-000008"` |

---

## Executive Compensation (XBRL - High Reliability)

Executive compensation data is extracted from XBRL using the SEC's Executive Compensation Disclosure (ECD) taxonomy. This data is highly standardized and available for all companies.

### PEO (Principal Executive Officer / CEO)

| Property | Type | XBRL Concept | Description | Example |
|----------|------|--------------|-------------|---------|
| `peo_name` | `str` | `ecd:PeoName` | CEO name | `"Mr. Cook"` |
| `peo_total_comp` | `Decimal` | `ecd:PeoTotalCompAmt` | Total compensation from Summary Compensation Table | `74,609,802` |
| `peo_actually_paid_comp` | `Decimal` | `ecd:PeoActuallyPaidCompAmt` | Compensation Actually Paid (CAP) | `168,980,568` |

### Non-PEO Named Executive Officers (NEOs)

| Property | Type | XBRL Concept | Description | Example |
|----------|------|--------------|-------------|---------|
| `neo_avg_total_comp` | `Decimal` | `ecd:NonPeoNeoAvgTotalCompAmt` | Average NEO total compensation | `27,178,896` |
| `neo_avg_actually_paid_comp` | `Decimal` | `ecd:NonPeoNeoAvgCompActuallyPaidAmt` | Average NEO compensation actually paid | `58,633,525` |

### Compensation Time Series (5 Years)

The `executive_compensation` property returns a DataFrame with 5 years of compensation data:

```python
proxy = filing.obj()
comp_df = proxy.executive_compensation  # pd.DataFrame
```

| Column | Type | Description |
|--------|------|-------------|
| `fiscal_year_end` | `date` | End of fiscal year |
| `peo_total_comp` | `Decimal` | PEO total from SCT |
| `peo_actually_paid_comp` | `Decimal` | PEO compensation actually paid |
| `neo_avg_total_comp` | `Decimal` | Non-PEO NEO average total |
| `neo_avg_actually_paid_comp` | `Decimal` | Non-PEO NEO average CAP |

### Example Output

```python
# Apple Inc. Executive Compensation (5 years)
fiscal_year_end  peo_total_comp  peo_actually_paid_comp  neo_avg_total_comp  neo_avg_actually_paid
2024-09-28       74,609,802      168,980,568             27,178,896          58,633,525
2023-09-30       63,209,845      106,643,588             26,938,240          48,892,163
2022-09-24       99,420,097      128,833,021             26,929,095          35,842,114
2021-09-25       98,734,394      311,845,801             26,989,456          89,764,231
2020-09-26       14,769,259       4,567,123              23,976,158          12,589,743
```

### Named Executives (Dimensional Data)

Some companies tag individual executive data using dimensional XBRL. When available:

```python
# Check if individual executive data is available
if proxy.has_individual_executive_data:
    executives = proxy.named_executives  # list of executive dicts
    for exec in executives:
        print(f"{exec['name']}: ${exec['actually_paid_comp']:,}")
```

| Property | Type | Description |
|----------|------|-------------|
| `has_individual_executive_data` | `bool` | Whether individual executive dimensions are available |
| `named_executives` | `list[dict]` | Individual executive compensation details (when available) |

**Note**: Only ~60% of companies use dimensional tagging (AAPL, JPM, JNJ). Others aggregate to PEO vs Non-PEO NEO averages (MSFT, XOM).

---

## Pay vs Performance (XBRL - High Reliability)

Pay vs Performance disclosures correlate executive compensation with company performance metrics.

### Primary Metrics

| Property | Type | XBRL Concept | Description | Example |
|----------|------|--------------|-------------|---------|
| `total_shareholder_return` | `Decimal` | `ecd:TotalShareholderRtnAmt` | Company TSR (cumulative %) | `207.6` |
| `peer_group_tsr` | `Decimal` | `ecd:PeerGroupTotalShareholderRtnAmt` | Peer group TSR | `189.3` |
| `net_income` | `Decimal` | `us-gaap:NetIncomeLoss` | Net income (USD) | `93,736,000,000` |

### Company-Selected Performance Measure

| Property | Type | XBRL Concept | Description | Example |
|----------|------|--------------|-------------|---------|
| `company_selected_measure` | `str` | `ecd:CoSelectedMeasureName` | Company's chosen KPI name | `"Operating Cash Flow"` |
| `company_selected_measure_value` | `Decimal` | `ecd:CoSelectedMeasureAmt` | KPI value | `118,254,000,000` |

### Most Important Performance Measures

| Property | Type | XBRL Concept | Description |
|----------|------|--------------|-------------|
| `performance_measures` | `list[str]` | `ecd:MeasureName` | List of performance measures used |

Example values: `["Revenue", "Operating Income", "Free Cash Flow", "Total Shareholder Return"]`

### Pay vs Performance DataFrame

```python
pvp_df = proxy.pay_vs_performance  # pd.DataFrame
```

| Column | Type | Description |
|--------|------|-------------|
| `fiscal_year_end` | `date` | End of fiscal year |
| `peo_actually_paid_comp` | `Decimal` | CEO compensation actually paid |
| `neo_avg_actually_paid_comp` | `Decimal` | NEO average CAP |
| `total_shareholder_return` | `Decimal` | Company TSR |
| `peer_group_tsr` | `Decimal` | Peer group TSR |
| `net_income` | `Decimal` | Net income |
| `company_selected_measure_value` | `Decimal` | Company KPI value |

---

## Governance Indicators (XBRL)

| Property | Type | XBRL Concept | Description | Example |
|----------|------|--------------|-------------|---------|
| `insider_trading_policy_adopted` | `bool` | `ecd:InsiderTrdPoliciesProcAdoptedFlag` | Has adopted insider trading policy | `True` |

---

## XBRL Concept Reference

### Universal Concepts (Present in ALL Companies)

These 25 concepts are available across all sampled DEF 14A filings (100% coverage):

#### Executive Compensation

| Concept | Description |
|---------|-------------|
| `ecd:PeoTotalCompAmt` | PEO total compensation from Summary Compensation Table |
| `ecd:PeoActuallyPaidCompAmt` | PEO compensation actually paid |
| `ecd:NonPeoNeoAvgTotalCompAmt` | Non-PEO NEO average total compensation |
| `ecd:NonPeoNeoAvgCompActuallyPaidAmt` | Non-PEO NEO average compensation actually paid |
| `ecd:AdjToCompAmt` | Adjustments to compensation (reconciliation) |
| `ecd:PeoName` | Name of Principal Executive Officer |

#### Performance Metrics

| Concept | Description |
|---------|-------------|
| `ecd:TotalShareholderRtnAmt` | Company total shareholder return |
| `ecd:PeerGroupTotalShareholderRtnAmt` | Peer group total shareholder return |
| `us-gaap:NetIncomeLoss` | Net income (GAAP) |
| `ecd:CoSelectedMeasureAmt` | Company-selected performance measure value |
| `ecd:CoSelectedMeasureName` | Company-selected performance measure name |
| `ecd:MeasureName` | Names of most important performance measures |

#### Text Blocks and Footnotes

| Concept | Description |
|---------|-------------|
| `ecd:PvpTableTextBlock` | Pay vs Performance table text block |
| `ecd:TabularListTableTextBlock` | Tabular list of performance measures |
| `ecd:NamedExecutiveOfficersFnTextBlock` | Named executives footnote |
| `ecd:PeerGroupIssuersFnTextBlock` | Peer group issuers footnote |
| `ecd:AdjToPeoCompFnTextBlock` | PEO compensation adjustment footnote |
| `ecd:AdjToNonPeoNeoCompFnTextBlock` | Non-PEO NEO adjustment footnote |
| `ecd:CompActuallyPaidVsTotalShareholderRtnTextBlock` | CAP vs TSR discussion |
| `ecd:CompActuallyPaidVsNetIncomeTextBlock` | CAP vs Net Income discussion |
| `ecd:CompActuallyPaidVsCoSelectedMeasureTextBlock` | CAP vs company measure discussion |

#### Governance

| Concept | Description |
|---------|-------------|
| `ecd:InsiderTrdPoliciesProcAdoptedFlag` | Insider trading policy adoption flag |

---

## Code Examples

### Example 1: Extract Executive Compensation

```python
from edgar import Company

# Get company and filing
company = Company("AAPL")
filing = company.get_filings(form="DEF 14A").latest()

# Get proxy statement object
proxy = filing.obj()

# Access executive compensation
print(f"CEO: {proxy.peo_name}")
print(f"CEO Total Compensation: ${proxy.peo_total_comp:,}")
print(f"CEO Compensation Actually Paid: ${proxy.peo_actually_paid_comp:,}")
print(f"NEO Average Compensation: ${proxy.neo_avg_actually_paid_comp:,}")
```

### Example 2: Pay vs Performance Analysis

```python
from edgar import Company

company = Company("MSFT")
filing = company.get_filings(form="DEF 14A").latest()
proxy = filing.obj()

# Get pay vs performance DataFrame
pvp = proxy.pay_vs_performance

# Calculate pay-for-performance correlation
correlation = pvp['peo_actually_paid_comp'].corr(pvp['total_shareholder_return'])
print(f"CEO Pay vs TSR Correlation: {correlation:.2f}")

# Compare to peer group
print(f"Company TSR: {proxy.total_shareholder_return}%")
print(f"Peer Group TSR: {proxy.peer_group_tsr}%")
print(f"Outperformance: {proxy.total_shareholder_return - proxy.peer_group_tsr:.1f}%")
```

### Example 3: Governance Check

```python
from edgar import Company

company = Company("JPM")
filing = company.get_filings(form="DEF 14A").latest()
proxy = filing.obj()

# Check governance indicators
if proxy.insider_trading_policy_adopted:
    print("Insider Trading Policy: Adopted")
else:
    print("Insider Trading Policy: Not Adopted (flag for review)")

# List performance measures used
print("Performance Measures:")
for measure in proxy.performance_measures:
    print(f"  - {measure}")
```

### Example 4: Multi-Company Comparison

```python
from edgar import Company
import pandas as pd

tickers = ["AAPL", "MSFT", "GOOGL", "META", "AMZN"]
data = []

for ticker in tickers:
    company = Company(ticker)
    filing = company.get_filings(form="DEF 14A").latest()
    proxy = filing.obj()

    data.append({
        'company': company.name,
        'ceo': proxy.peo_name,
        'ceo_total_comp': proxy.peo_total_comp,
        'ceo_actually_paid': proxy.peo_actually_paid_comp,
        'tsr': proxy.total_shareholder_return,
        'peer_tsr': proxy.peer_group_tsr
    })

comparison_df = pd.DataFrame(data)
print(comparison_df.to_string())
```

### Example 5: Access Board and Director Information

The `ProxyStatement` class focuses on XBRL-based executive compensation data. Board composition, director details, and shareholder proposals live in the HTML body of the filing and are not yet extracted into structured properties. However, you can access this information today using the `Filing` object's built-in search and HTML capabilities.

```python
from edgar import Company

# Get a DEF 14A filing
company = Company("AAPL")
filing = company.get_filings(form="DEF 14A").latest()

# Search the filing HTML for board-related sections
results = filing.search("board of directors")
for section in results[:3]:
    print(section[:200])  # Preview matching sections
```

```python
# Search for specific governance topics
director_sections = filing.search("director nominees")
ownership_sections = filing.search("beneficial ownership")
proposal_sections = filing.search("proposal")
audit_sections = filing.search("audit fees")
```

```python
# Get the full HTML for manual inspection or custom parsing
html_content = filing.html()

# Or access the filing document directly
doc = filing.document()
```

> **Note**: Board composition, director bios, beneficial ownership tables, and shareholder proposals are available in the filing HTML but require custom parsing. Structured `Director` and `Proposal` objects are planned for a future release. See the [HTML-Based Data](#html-based-data-future-features) section below for details on what data is available and extraction patterns.

---

## View Design Recommendations

### Primary View Components

1. **Header Section**
   - Company name (prominent)
   - Form type with amendment indicator
   - Filing date and fiscal year end
   - Annual meeting date (if available)

2. **Compensation Dashboard**
   - CEO compensation card (Total SCT vs Actually Paid)
   - NEO average compensation card
   - 5-year trend sparkline or chart
   - Year-over-year change indicators

3. **Pay vs Performance Panel**
   - TSR comparison chart (company vs peer group)
   - Compensation vs TSR correlation visualization
   - Net income trend overlay
   - Company-selected performance measure

4. **Governance Indicators**
   - Insider trading policy status badge
   - Performance measures list

5. **Key Metrics Cards**
   - Total Shareholder Return
   - Peer Group TSR
   - Net Income
   - Company KPI with label

### Data Priority for Display

| Priority | Data | Reason |
|----------|------|--------|
| High | CEO compensation (both SCT and CAP) | Primary user interest |
| High | Total Shareholder Return | Key performance metric |
| High | Peer group comparison | Benchmark context |
| Medium | NEO average compensation | Executive team context |
| Medium | Net income | Financial performance |
| Medium | Company-selected measure | Company's chosen KPI |
| Medium | 5-year compensation trends | Historical context |
| Low | Adjustment details | Technical reconciliation |
| Low | Footnote text blocks | Reference material |

### Value Formatting

| Data Type | Format | Example |
|-----------|--------|---------|
| Compensation | Currency with commas | `$168,980,568` |
| Large values (>$1B) | Abbreviated | `$93.7B` |
| TSR | Percentage with 1 decimal | `207.6%` |
| Year-over-year change | Signed percentage | `+12.5%` or `-8.3%` |

### Visual Indicators (Suggested)

| Condition | Visual Treatment |
|-----------|------------------|
| Amendment (`/A`) | Yellow "Amendment" badge |
| TSR > Peer TSR | Green upward arrow |
| TSR < Peer TSR | Red downward arrow |
| Insider policy adopted | Green checkmark |
| Insider policy not adopted | Red warning icon |
| Compensation increase >25% YoY | Orange highlight |
| Compensation decrease | Blue highlight |

### Compensation Card Layout

```
+----------------------------------+
|  CEO Compensation                |
|  Mr. Tim Cook                    |
+----------------------------------+
|  Summary Comp Table              |
|  $74,609,802                     |
|  +18.0% vs prior year            |
+----------------------------------+
|  Compensation Actually Paid      |
|  $168,980,568                    |
|  +58.4% vs prior year            |
+----------------------------------+
```

---

## Example Data Structure

```python
{
    # Metadata
    "form": "DEF 14A",
    "filing_date": "2025-01-10",
    "fiscal_year_end": "2024-09-28",
    "company_name": "Apple Inc.",
    "cik": "0000320193",
    "accession_number": "0001308179-25-000008",

    # Executive Compensation
    "peo_name": "Mr. Cook",
    "peo_total_comp": 74609802,
    "peo_actually_paid_comp": 168980568,
    "neo_avg_total_comp": 27178896,
    "neo_avg_actually_paid_comp": 58633525,

    # Pay vs Performance
    "total_shareholder_return": 207.6,
    "peer_group_tsr": 189.3,
    "net_income": 93736000000,
    "company_selected_measure": "Operating Cash Flow",
    "company_selected_measure_value": 118254000000,

    # Performance Measures
    "performance_measures": [
        "Net Sales",
        "Operating Income",
        "Total Shareholder Return",
        "Operating Cash Flow"
    ],

    # Governance
    "insider_trading_policy_adopted": True,

    # Named Executives (when dimensional data available)
    "has_individual_executive_data": True,
    "named_executives": [
        {
            "id": "aapl:CookMember",
            "name": "Mr. Cook",
            "role": "PEO",
            "total_comp": 74609802,
            "actually_paid_comp": 168980568
        },
        {
            "id": "aapl:MaestriMember",
            "name": "Luca Maestri",
            "role": "NEO",
            "total_comp": 27178896,
            "actually_paid_comp": 58633525
        }
    ],

    # Time Series (5 years)
    "executive_compensation": [
        {
            "fiscal_year_end": "2024-09-28",
            "peo_total_comp": 74609802,
            "peo_actually_paid_comp": 168980568,
            "neo_avg_total_comp": 27178896,
            "neo_avg_actually_paid_comp": 58633525
        },
        {
            "fiscal_year_end": "2023-09-30",
            "peo_total_comp": 63209845,
            "peo_actually_paid_comp": 106643588,
            "neo_avg_total_comp": 26938240,
            "neo_avg_actually_paid_comp": 48892163
        }
        # ... 3 more years
    ],

    # Pay vs Performance Series
    "pay_vs_performance": [
        {
            "fiscal_year_end": "2024-09-28",
            "peo_actually_paid_comp": 168980568,
            "neo_avg_actually_paid_comp": 58633525,
            "total_shareholder_return": 207.6,
            "peer_group_tsr": 189.3,
            "net_income": 93736000000
        }
        # ... more years
    ]
}
```

---

## HTML-Based Data (Future Features)

The following data is available in DEF 14A HTML sections but not yet extracted into structured properties. You can access these sections today using `filing.search()` to find relevant content.

### Beneficial Ownership

| Section | Description |
|---------|-------------|
| Principal Shareholders | Shareholders owning >5% of shares |
| Director/Executive Ownership | Shares owned by insiders |

**How to access today**:
```python
results = filing.search("beneficial ownership")
# or
results = filing.search("security ownership")
```

### Board of Directors

| Data | Description |
|------|-------------|
| Director Names | Full list of board members |
| Director Ages | Ages of directors |
| Director Tenure | Years on board |
| Independence Status | Independent vs non-independent |
| Committee Memberships | Audit, Compensation, Governance |

**How to access today**:
```python
results = filing.search("board of directors")
# or
results = filing.search("director nominees")
```

### Director Compensation

| Data | Description |
|------|-------------|
| Director Fees | Annual retainer and meeting fees |
| Stock Awards | Equity compensation |
| Total Compensation | Sum of all compensation |

**How to access today**:
```python
results = filing.search("director compensation")
```

### Voting Proposals

| Proposal Type | Description |
|---------------|-------------|
| Election of Directors | Board member elections |
| Ratification of Auditors | Audit firm approval |
| Say-on-Pay | Executive compensation advisory vote |
| Shareholder Proposals | Proposals submitted by shareholders |
| Equity Plan Amendments | Stock compensation plan changes |

**How to access today**:
```python
results = filing.search("proposal")
```

### Audit Information

| Data | Description |
|------|-------------|
| Auditor Name | Independent auditor firm |
| Audit Fees | Fees for audit services |
| Tax Fees | Fees for tax services |
| Other Fees | Other professional fees |

**How to access today**:
```python
results = filing.search("audit fees")
```

---

## Notes for Implementation

1. **XBRL Namespace**: The primary namespace for proxy data is `ecd:` (Executive Compensation Disclosure), introduced by SEC in 2022 for fiscal years ending on or after December 16, 2022.

2. **Dimensional Tagging Variation**:
   - ~60% of companies tag individual executive data using `dim_ecd_IndividualAxis`
   - ~40% only provide aggregate data (PEO and Non-PEO NEO averages)
   - Always check `has_individual_executive_data` before accessing individual executives

3. **Time Series Data**: Pay vs Performance tables include 5 years of historical data per SEC requirements. This enables robust trend analysis.

4. **Compensation Actually Paid (CAP)**: This SEC-mandated metric differs from Summary Compensation Table totals due to adjustments for:
   - Change in pension value
   - Stock/option awards fair value changes
   - Vesting date fair values

5. **Company-Selected Measure**: Each company chooses one performance measure they consider most important. Common choices include:
   - Revenue or Net Sales
   - Operating Income
   - Free Cash Flow
   - Adjusted EBITDA
   - Return on Invested Capital

6. **Peer Group**: Companies define their own peer groups for TSR comparison. The peer group composition is disclosed in the filing but not structured in XBRL.

7. **Amendment Handling**: DEF 14A/A filings contain corrections or updates. Always use the most recent filing for a given fiscal year.

8. **Form Variants**:
   - `DEF 14A`: Standard proxy statement
   - `DEFA14A`: Additional soliciting materials (may have limited data)
   - `DEFM14A`: Merger-related proxy (may have different structure)

9. **Fiscal Year Alignment**: Match compensation periods with company fiscal year ends, which vary by company (e.g., Apple uses September, Microsoft uses June).

10. **Large Cap Coverage**: XBRL data is highly reliable for S&P 500 companies. Smaller companies may have less complete tagging.
