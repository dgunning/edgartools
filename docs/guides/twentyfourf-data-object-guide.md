---
description: Parse SEC Form 24F-2NT annual fund fee notices with Python. Extract aggregate sales, redemptions, net sales, and SEC registration fees from investment company filings using edgartools.
---

# Form 24F-2NT: Parse Annual Fund Fee Notices with Python

Every registered investment company (mutual fund, ETF, closed-end fund) must file a Form 24F-2NT each year reporting how much it sold and how much it owes the SEC in registration fees. EdgarTools parses these XML filings into a structured `FundFeeNotice` object so you can extract sales volumes, redemption credits, and fee calculations in a few lines of Python.

```python
from edgar import find

filing = find("0002048251-26-002390")   # Advisors' Inner Circle Fund
notice = filing.obj()
notice
```

<!-- screenshot: docs/images/twentyfourf-notice.webp -->
<!-- capture: python scripts/snapshot_rich.py "from edgar import find; filing = find('0002048251-26-002390'); filing.obj()" -o docs/images/twentyfourf-notice.webp --width 80 --title "FundFeeNotice" -->

---

## Read the Fee Calculation

The financial data lives in Item 5. These are the numbers that determine how much the fund owes the SEC for the fiscal year:

```python
notice = filing.obj()

print(f"Aggregate sales:        ${notice.aggregate_sales:>15,.2f}")
print(f"Redemption credits:     ${notice.total_redemption_credits:>15,.2f}")
print(f"Net sales:              ${notice.net_sales:>15,.2f}")
print(f"Fee multiplier:                  {notice.fee_multiplier}")
print(f"Registration fee:       ${notice.registration_fee:>15,.2f}")
print(f"Interest due:           ${notice.interest_due:>15,.2f}")
print(f"Total due:              ${notice.total_due:>15,.2f}")
```

```
Aggregate sales:        $418,915,624.00
Redemption credits:     $309,040,895.54
Net sales:              $109,874,728.46
Fee multiplier:                  0.0001381
Registration fee:            $15,173.70
Interest due:                     $0.00
Total due:                    $15,173.70
```

The fee formula is straightforward: `net_sales * fee_multiplier = registration_fee`. Net sales are aggregate sales minus redemption credits. The multiplier is set annually by the SEC.

Redemptions reduce the taxable base. A fund with high turnover may owe far less than its gross sales figure suggests.

---

## Identify the Fund and Series

```python
print(notice.fund_name)                           # "ADVISORS' INNER CIRCLE FUND"
print(notice.investment_company_act_file_number)  # "811-06400"
print(notice.fiscal_year_end)                     # "12/31/2025"
print(notice.is_filed_late)                       # False
print(notice.is_final_filing)                     # False

# Address
addr = notice.fund_address
print(f"{addr['street1']}, {addr['city']}, {addr['state']}")
```

The `is_final_filing` flag is worth tracking. When it's `True`, the fund is closing or deregistering and this will be its last 24F-2NT.

### Fund Series

Multi-series funds report each series separately in Item 2:

```python
for s in notice.series:
    print(s.series_id, s.series_name)
```

```
S000036634    Hamlin High Dividend Equity Fund
S000066843    Rockefeller Climate Solutions Fund
...
```

Each `SeriesInfo` object has:

| Property | Type | Description |
|----------|------|-------------|
| `series_id` | `str` | EDGAR series identifier (`S000XXXXXX`) |
| `series_name` | `str` | Human-readable series name |
| `include_all_classes` | `bool` | Whether all share classes are included |

---

## Search Recent 24F-2NT Filings

To find recent filings across all funds:

```python
from edgar import get_filings

filings = get_filings(form="24F-2NT", year=2026, quarter=1)
filings
```

You can also look up a specific fund's history:

```python
from edgar import Company

# Use the fund's CIK or name
company = Company("ADVISORS INNER CIRCLE FUND")
filing = company.get_filings(form="24F-2NT").latest(1)
notice = filing.obj()
```

---

## Scan for Largest Fund Flows

To compare aggregate sales across a batch of recent filings, loop over the results and collect the financial data:

```python
from edgar import get_filings

filings = get_filings(form="24F-2NT", year=2025, quarter=4)

rows = []
for filing in filings.head(50):
    notice = filing.obj()
    if notice and notice.aggregate_sales:
        rows.append({
            "fund":         notice.fund_name or filing.company,
            "sales":        notice.aggregate_sales,
            "net_sales":    notice.net_sales,
            "fee":          notice.registration_fee,
            "fiscal_end":   notice.fiscal_year_end,
        })

import pandas as pd
df = pd.DataFrame(rows).sort_values("sales", ascending=False)
df.head(10)
```

This gives you a table of the biggest gross-sales funds for the quarter -- useful for tracking fund flows or identifying active distribution channels.

---

## Track Registration Fees Over Time

A single fund's fee history reveals how sales volumes (and therefore fee obligations) change year to year:

```python
from edgar import Company
import pandas as pd

company = Company("VANGUARD INDEX FUNDS")
filings = company.get_filings(form="24F-2NT").head(5)

records = []
for filing in filings:
    n = filing.obj()
    if n:
        records.append({
            "fiscal_year_end": n.fiscal_year_end,
            "filed":           filing.filing_date,
            "aggregate_sales": n.aggregate_sales,
            "net_sales":       n.net_sales,
            "registration_fee": n.registration_fee,
        })

pd.DataFrame(records)
```

---

## View the SEC-Rendered Form

The SEC provides an XSLT-rendered HTML version of every 24F-2NT, formatted exactly as it appears on EDGAR:

```python
html = notice.to_html()   # Returns HTML string
```

This is the same output you would see at `https://www.sec.gov/Archives/edgar/...`. Useful for building display views or verification.

---

## Access Raw XML Data

For data not exposed as typed properties, use dict-style access into the full parsed XML:

```python
# Deep key lookup (searches the entire XML tree)
notice['nameOfIssuer']           # "ADVISORS' INNER CIRCLE FUND"
notice['lastDayOfFiscalYear']    # "12/31/2025"

# Full form_data dict
notice.form_data                 # nested dict of the entire <formData> element
```

The `[]` operator does a recursive key search across the entire XML tree. If you know the exact XML field name, this is faster than navigating the nested dict manually.

---

## Quick Reference

### Identity Properties

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `fund_name` | `str` | Investment company name | `"ADVISORS' INNER CIRCLE FUND"` |
| `fund_address` | `dict` | Address with street1, city, state, zipCode | `{"city": "Philadelphia", ...}` |
| `investment_company_act_file_number` | `str` | ICA file number | `"811-06400"` |
| `fiscal_year_end` | `str` | Last day of fiscal year | `"12/31/2025"` |
| `is_filed_late` | `bool` | Filed after deadline | `False` |
| `is_final_filing` | `bool` | Last 24F-2NT for this fund | `False` |
| `series` | `list[SeriesInfo]` | Fund series covered | See SeriesInfo |

### Financial Properties (Item 5)

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `aggregate_sales` | `float` | Total gross securities sold | `418915624.0` |
| `redemptions_current_year` | `float` | Redemptions in fiscal year | `309040895.54` |
| `redemptions_prior_years` | `float` | Unused credits from prior years | `0.0` |
| `total_redemption_credits` | `float` | Current + prior redemptions | `309040895.54` |
| `net_sales` | `float` | Aggregate sales minus credits | `109874728.46` |
| `unused_redemption_credits` | `float` | Credits carried to next year | `0.0` |
| `fee_multiplier` | `float` | SEC-set multiplier | `0.0001381` |
| `registration_fee` | `float` | Fee due to SEC | `15173.7` |
| `interest_due` | `float` | Late payment interest | `0.0` |
| `total_due` | `float` | Registration fee + interest | `15173.7` |

### Inherited from XmlFiling

| Property/Method | Returns | Description |
|-----------------|---------|-------------|
| `form` | `str` | Form type (`"24F-2NT"`) |
| `company` | `str` | Company name from filing header |
| `filing_date` | `str` | Date filed with SEC |
| `accession_number` | `str` | SEC accession number |
| `is_amendment` | `bool` | Whether this is a `/A` amendment |
| `form_data` | `dict` | Full parsed XML as nested dict |
| `notice['key']` | `Any` | Deep key lookup into form_data |
| `notice.to_html()` | `str` | SEC XSLT-rendered HTML |

---

## Things to Know

**Redemption credits reduce the fee base.** The registration fee applies to net sales, not gross sales. A fund that sold $1B but redeemed $900M owes fees only on $100M. Unused redemption credits can carry forward to the next fiscal year.

**`aggregate_sales` is in dollars, not thousands.** Unlike 13F filings, 24F-2NT reports full dollar amounts. `$418,915,624.0` is $418 million, not $418 billion.

**Multi-series funds file one 24F-2NT.** The `series` list covers all series included in that filing. The financial figures in Item 5 are the aggregate for the entire company, not per-series.

**The fee multiplier changes annually.** The SEC adjusts the multiplier each year based on appropriations. Check `notice.fee_multiplier` rather than hard-coding a constant.

**`is_final_filing` signals deregistration.** When this is `True`, the fund is exiting the market or has merged. It's a useful signal when screening for fund closures.

---

## Related

- [Working with Filings](working-with-filing.md) -- general patterns for finding and navigating SEC filings
- [Fund Holdings: N-PORT](npx-data-object-guide.md) -- monthly fund portfolio data
