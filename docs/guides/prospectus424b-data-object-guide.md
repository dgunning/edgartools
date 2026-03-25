---
description: Extract offering terms, pricing, underwriting economics, and dilution from SEC 424B prospectus supplement filings.
---

# Prospectus Supplements (424B): Parse Offering Terms from SEC Filings

## Overview

**424B filings** are prospectus supplements that companies file when they sell securities off a shelf registration (S-3/F-3). They contain the final deal terms: price, shares, proceeds, underwriting fees, and dilution impact. EdgarTools parses all 424B variants into a `Prospectus424B` object, with a `Deal` property that normalizes everything into clean numeric values.

| Form | Typical Use |
|------|-------------|
| 424B2 | Structured notes, debt (large banks) |
| 424B3 | Resale prospectuses (PIPE resales) |
| 424B4 | Final priced prospectuses (IPOs) |
| 424B5 | Shelf takedowns (ATM, firm commitment, PIPE) |

## Quick Start

```python
from edgar import Company

company = Company("ALZN")
filing = company.get_filings(form="424B5")[0]
prospectus = filing.obj()          # Prospectus424B
deal = prospectus.deal             # Deal: normalized summary

deal.price                         # 2.48
deal.shares                        # 1_500_000
deal.gross_proceeds                # 3_720_000.0
deal.lead_bookrunner               # "H.C. Wainwright & Co."
```

## The Deal Object

Access via `prospectus.deal`. Always returns a `Deal` object (never `None`). Individual properties return `None` when data is unavailable.

### Core Deal Terms

| Property | Type | Description |
|----------|------|-------------|
| `price` | `float \| None` | Per-unit offering price |
| `shares` | `int \| None` | Number of shares offered |
| `gross_proceeds` | `float \| None` | Total offering amount (before fees) |
| `net_proceeds` | `float \| None` | Proceeds after underwriting fees |
| `security_type` | `str \| None` | Security description ("Common Stock", "Senior Notes") |
| `offering_type` | `OfferingType` | Enum: `FIRM_COMMITMENT`, `ATM`, `BEST_EFFORTS`, etc. |
| `is_atm` | `bool` | Whether this is an at-the-market offering |

### Underwriting Economics

| Property | Type | Description |
|----------|------|-------------|
| `fee_per_share` | `float \| None` | Per-unit underwriting discount |
| `total_fees` | `float \| None` | Total underwriting fees |
| `discount_rate` | `float \| None` | Fee as fraction of price (0.05 = 5%) |
| `fee_type` | `str \| None` | `"underwriting_discount"` or `"placement_agent_fees"` |
| `lead_bookrunner` | `str \| None` | Lead underwriter or placement agent |
| `underwriter_count` | `int` | Number of underwriters in syndicate |

### Dilution (Equity Offerings Only)

| Property | Type | Description |
|----------|------|-------------|
| `dilution_per_share` | `float \| None` | Dilution to new investors |
| `dilution_pct` | `float \| None` | Dilution as percentage |
| `shares_before` | `int \| None` | Shares outstanding before offering |
| `shares_after` | `int \| None` | Shares outstanding after offering |
| `ntbv_before` | `float \| None` | Net tangible book value per share before |
| `ntbv_after` | `float \| None` | Net tangible book value per share after |

### Serialization

```python
deal.to_dict()        # Flat dict of all non-None values (good for DataFrames)
deal.to_context()     # Markdown-KV text for LLM prompts
```

## Offering Classification

The `offering_type` property classifies the deal:

| Value | Description | Price/Shares Available? |
|-------|-------------|------------------------|
| `FIRM_COMMITMENT` | Bank buys all shares, resells | Yes |
| `ATM` | At-the-market (sold gradually) | Usually no (market price) |
| `BEST_EFFORTS` | Agent sells on best-efforts basis | Yes |
| `PIPE_RESALE` | Resale of privately placed shares | Varies |
| `STRUCTURED_NOTE` | Bank-issued structured product | Different meaning |
| `DEBT_OFFERING` | Corporate bonds / notes | Usually percentage |

```python
if deal.is_atm:
    # Price and shares are typically None for ATM offerings
    print(f"ATM program: up to ${deal.gross_proceeds:,.0f}")
else:
    print(f"{deal.shares:,} shares @ ${deal.price:.2f}")
```

## Prospectus Sub-Objects

The `Prospectus424B` exposes the raw extracted data that the Deal synthesizes:

```python
prospectus.cover_page          # CoverPageData: company, registration, flags
prospectus.pricing             # PricingData: per-unit and total columns
prospectus.underwriting        # UnderwritingInfo: syndicate, fee type
prospectus.offering_terms      # OfferingTerms: shares, warrants, use of proceeds
prospectus.selling_stockholders  # SellingStockholdersData: PIPE resale tables
prospectus.dilution            # DilutionData: NTBV impact table
prospectus.capitalization      # CapitalizationData: actual vs. as-adjusted
prospectus.structured_note_terms  # StructuredNoteTerms: CUSIP, maturity (424B2)
prospectus.filing_fees         # FilingFeesData: from XBRL exhibit
```

## Selling Stockholders (PIPE Resale Filings)

For PIPE resale prospectuses (typically 424B3), the selling stockholders table lists investors reselling privately placed shares:

```python
ss = prospectus.selling_stockholders   # SellingStockholdersData or None
if ss:
    ss.count                           # Number of selling stockholders
    for entry in ss.stockholders:
        entry.name                     # "Lincoln Park Capital Fund, LLC"
        entry.shares                   # 1500000 (parsed int, None on failure)
        entry.shares_before            # 2000000
        entry.shares_after             # 500000
        entry.pct_before               # 9.5 (parsed float)
        entry.pct_after                # 2.8
        entry.warrants                 # 750000 (warrants/convertibles, if present)
```

Raw string values are always preserved (`shares_offered`, `shares_before_offering`, etc.). The numeric properties (`shares`, `shares_before`, etc.) parse them to `int`/`float`, returning `None` on failure.

### DataFrame Output

```python
df = ss.to_dataframe()
# Returns DataFrame with numeric columns:
#   name | shares_before | pct_before | shares_offered | shares_after | pct_after | warrants
```

### Offering Type Check

```python
if prospectus.offering_type.has_selling_stockholders:
    # This is a PIPE_RESALE or BASE_PROSPECTUS_UPDATE
    ss = prospectus.selling_stockholders
```

## Shelf Lifecycle

Track where a prospectus sits in its shelf registration lifecycle:

```python
lc = prospectus.lifecycle          # ShelfLifecycle
lc.takedown_number                 # 3 (this is the 3rd offering)
lc.total_takedowns                 # 5
lc.shelf_expires                   # date(2027, 8, 2)
lc.avg_days_between_takedowns      # 180.0
lc.shelf_registration              # Filing object for the S-3
```

To navigate the other direction -- from the S-3 shelf forward to its 424B takedowns -- use the `RegistrationS3` data object. `filing.obj()` returns it automatically for S-3, S-3/A, S-3ASR, S-3D, and S-3DPOS filings.

```python
from edgar import Company

company = Company("ALZN")
s3_filing = company.get_filings(form="S-3")[0]
s3 = s3_filing.obj()                   # RegistrationS3

s3.total_offering                      # total registered amount in dollars
s3.takedowns                           # Filings with all 424B forms from this shelf
s3.offering_type.display_name          # "Resale Registration"
```

See the [S-3 Registration Statement guide](registration-s3-data-object-guide.md) for the full API.

## Working with Multiple Offerings

Build a DataFrame of a company's offering history:

```python
import pandas as pd
from edgar import Company

company = Company("ALZN")
filings = company.get_filings(form="424B5")

rows = []
for filing in filings:
    prospectus = filing.obj()
    d = prospectus.deal.to_dict()
    d['filing_date'] = str(filing.filing_date)
    rows.append(d)

df = pd.DataFrame(rows)
```

## Rich Display

Both `Prospectus424B` and `Deal` render as Rich panels in terminals and notebooks:

```python
prospectus          # Shows cover page, pricing table, underwriting
prospectus.deal     # Compact deal summary panel
```
