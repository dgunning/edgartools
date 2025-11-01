# SEC Form Types Reference

Quick reference guide for mapping natural language queries to SEC form codes.

## Overview

The SEC uses **over 300 different form types** for various filing requirements. This guide organizes the most common forms by use case and provides natural language mappings to help you quickly find the right form code.

**Programmatic Access:**
```python
from edgar.reference import describe_form

# Get description of any form
describe_form("C")       # Form C: Offering statement
describe_form("10-K")    # Form 10-K: Annual report for public companies
describe_form("S-1")     # Form S-1: Securities registration
```

---

## Quick Lookup by Use Case

### Corporate Reporting (Public Companies)

| Form | Description | When Filed | Use For |
|------|-------------|------------|---------|
| **10-K** | Annual report for public companies | Annually | Full year financials, MD&A, audited statements |
| **10-Q** | Quarterly report for public companies | Quarterly | Unaudited quarterly financials |
| **8-K** | Current report | As events occur | Material events, CEO changes, M&A |
| **10-KT** | Transition report | Fiscal year change | Transition period reporting |
| **10-QT** | Quarterly transition report | Fiscal year change | Quarterly transition periods |

**Common Questions:**
- "Annual report" → **10-K**
- "Quarterly earnings" → **10-Q**
- "Current events" → **8-K**
- "CEO change announcement" → **8-K** (Item 5.02)

---

### Capital Raising & Offerings

| Form | Description | Offering Type | Use For |
|------|-------------|---------------|---------|
| **S-1** | Securities registration | Public offering (IPO) | Traditional IPO filings |
| **S-3** | Simplified securities registration | Shelf registration | Established companies |
| **C** | Offering statement | Crowdfunding | Regulation Crowdfunding (< $5M) |
| **D** | Notice of exempt offering | Private placement | Regulation D offerings |
| **1-A** | Offering statement | Regulation A | Mini-IPOs ($20M-$75M) |
| **F-1** | Foreign issuer registration | Foreign IPO | Non-US companies |

**Common Questions:**
- "IPO filings" → **S-1** (US) or **F-1** (Foreign)
- "Crowdfunding" → **C**
- "Private placement" → **D**
- "Regulation A" / "Mini-IPO" → **1-A**
- "Shelf registration" → **S-3**

---

### Ownership & Insider Trading

| Form | Description | When Filed | Use For |
|------|-------------|------------|---------|
| **3** | Initial statement of beneficial ownership | First time insider | New insider registration |
| **4** | Statement of changes in beneficial ownership | Transaction occurs | Insider buy/sell transactions |
| **5** | Annual statement of ownership changes | Annually | Small transactions |
| **13F-HR** | Institutional holdings report | Quarterly | Institutional investor holdings (>$100M AUM) |
| **13D** | Schedule 13D | 5%+ ownership | Activist investors |
| **13G** | Schedule 13G | 5%+ ownership | Passive investors |

**Common Questions:**
- "Insider trading" → **4**
- "Insider transactions" → **4**
- "CEO stock sales" → **4**
- "Institutional holdings" → **13F-HR**
- "Hedge fund holdings" → **13F-HR**
- "Activist investor" → **13D**

---

### Proxy Statements & Governance

| Form | Description | When Used | Use For |
|------|-------------|-----------|---------|
| **DEF 14A** | Definitive proxy statement | Before shareholder meeting | Voting matters, executive comp |
| **PRE 14A** | Preliminary proxy statement | Draft version | Initial proxy filing |
| **DEFA14A** | Additional proxy materials | Supplemental info | Additional solicitation |
| **DEFR14A** | Revised proxy statement | Amendments | Corrected proxy |

**Common Questions:**
- "Proxy statement" → **DEF 14A**
- "Executive compensation" → **DEF 14A**
- "Shareholder vote" → **DEF 14A**
- "Board elections" → **DEF 14A**

---

### Mergers & Acquisitions

| Form | Description | Transaction Type | Use For |
|------|-------------|-----------------|---------|
| **S-4** | Registration for business combinations | Merger/acquisition | Stock-for-stock deals |
| **SC 13D** | Schedule 13D | Beneficial ownership | Acquisition disclosure |
| **SC 14D1** | Tender offer | Takeover attempt | Tender offer filing |
| **DEFM14A** | Merger proxy | Shareholder approval | Merger vote |

**Common Questions:**
- "Merger announcement" → **8-K** (Item 1.01) or **DEFM14A**
- "Tender offer" → **SC 14D1**
- "Acquisition filing" → **S-4** or **8-K**

---

### Foreign & International

| Form | Description | Issuer Type | Use For |
|------|-------------|-------------|---------|
| **20-F** | Annual report | Foreign private issuer | Annual reporting (non-US) |
| **6-K** | Current report | Foreign private issuer | Material events (non-US) |
| **F-1** | Registration statement | Foreign IPO | IPO by foreign company |
| **F-3** | Simplified registration | Foreign issuer | Shelf registration |

**Common Questions:**
- "Foreign company annual report" → **20-F**
- "International company filing" → **20-F** or **6-K**
- "Foreign IPO" → **F-1**

---

### Investment Companies & Funds

| Form | Description | Fund Type | Use For |
|------|-------------|-----------|---------|
| **N-CSR** | Certified shareholder report | Mutual funds | Semi-annual/annual reports |
| **N-Q** | Quarterly schedule of holdings | Mutual funds | Quarterly holdings |
| **NPORT-P** | Portfolio holdings | Mutual funds | Monthly holdings |
| **497** | Definitive prospectus | Mutual funds | Final prospectus |
| **485BPOS** | Post-effective amendment | Mutual funds | Updated registration |

**Common Questions:**
- "Mutual fund holdings" → **N-Q** or **NPORT-P**
- "Fund prospectus" → **497**
- "Fund annual report" → **N-CSR**

---

### Other Common Forms

| Form | Description | Use For |
|------|-------------|---------|
| **144** | Notice of proposed sale | Restricted stock sales |
| **SC 13G** | Passive ownership | 5%+ beneficial ownership (passive) |
| **11-K** | Employee stock plan report | ESOP annual reports |
| **RW** | Registration withdrawal | Withdraw registration |
| **15-12G** | Termination of registration | Deregistration |

---

## Natural Language Search Index

### By Keyword

**A-C**
- "Annual report" → 10-K, 20-F (foreign), N-CSR (funds)
- "Activist investor" → 13D
- "Beneficial ownership" → 3, 4, 5, 13D, 13G
- "Board elections" → DEF 14A
- "CEO changes" → 8-K
- "Crowdfunding" → C

**D-F**
- "Deregistration" → 15-12G
- "Earnings" → 10-Q, 10-K
- "Executive compensation" → DEF 14A
- "Foreign company" → 20-F, 6-K, F-1

**G-I**
- "Governance" → DEF 14A
- "Hedge fund" → 13F-HR
- "Holdings" → 13F-HR, N-Q, NPORT-P
- "IPO" → S-1, F-1
- "Insider trading" → 4
- "Institutional investor" → 13F-HR

**M-Q**
- "Merger" → S-4, DEFM14A, 8-K
- "Mini-IPO" → 1-A
- "Mutual fund" → N-CSR, N-Q, 497
- "Offering" → S-1, S-3, C, D, 1-A
- "Proxy" → DEF 14A
- "Quarterly report" → 10-Q

**R-Z**
- "Registration" → S-1, S-3, F-1
- "Regulation A" → 1-A
- "Regulation D" → D
- "Restricted stock" → 144
- "Shareholder vote" → DEF 14A
- "Shelf registration" → S-3
- "Tender offer" → SC 14D1

---

## Form Categories

### By Frequency (Most Common First)

1. **Very Common** (thousands per year)
   - 10-K, 10-Q, 8-K, 4, 13F-HR, DEF 14A

2. **Common** (hundreds per year)
   - S-1, S-3, D, 3, 5, 20-F, 6-K

3. **Occasional** (dozens per year)
   - C, 1-A, F-1, SC 13D, DEFM14A

4. **Specialized** (as needed)
   - N-CSR, 11-K, 144, Various amendments

### By Reporting Obligation

**Periodic (Required Schedule)**
- 10-K (annual)
- 10-Q (quarterly)
- 20-F (annual, foreign)
- 13F-HR (quarterly, institutional)
- N-CSR (semi-annual/annual, funds)

**Event-Driven (As Needed)**
- 8-K (material events)
- 4 (insider transactions)
- SC 13D (ownership changes)
- DEFM14A (mergers)

**Transaction-Based (One-Time)**
- S-1, F-1 (IPOs)
- C, D (offerings)
- SC 14D1 (tender offers)

---

## Programming Examples

### Check if Form Exists
```python
from edgar.reference import describe_form

try:
    description = describe_form("C")
    print(f"Found: {description}")
except:
    print("Form not found")
```

### Get Filings by Form Type
```python
from edgar import get_filings

# Get all crowdfunding filings from Q1 2024
crowdfunding = get_filings(2024, 1, form="C")

# Get all IPOs
ipos = get_filings(2024, 1, form="S-1")

# Get insider transactions
insider = get_filings(2024, 1, form="4")
```

### Filter by Multiple Forms
```python
from edgar import get_filings

# Get all corporate reports (10-K and 10-Q)
filings = get_filings(2024, 1)
reports = filings.filter(form=["10-K", "10-Q"])

# Get all ownership filings
ownership = filings.filter(form=["3", "4", "5", "13D", "13G"])
```

---

## Special Form Types

### Amendments

Forms ending in `/A` indicate amendments:
- `10-K/A` - Amended 10-K
- `S-1/A` - Amended S-1
- `4/A` - Amended Form 4

```python
from edgar import get_filings

# Include amendments
all_10k = get_filings(form="10-K", amendments=True)

# Exclude amendments (default)
original_only = get_filings(form="10-K", amendments=False)
```

### Combined Forms

Some forms combine multiple types:
- `8-K/A` - Amended 8-K
- `10-K/T` - Transition 10-K
- `S-1/A` - Amended S-1

---

## Full Form List

For a complete list of all 311 SEC form types, see the reference data:

**Programmatically:**
```python
import pandas as pd
from edgar.reference.data.common import read_csv_from_package

forms_df = read_csv_from_package('secforms.csv')
print(f"Total forms: {len(forms_df)}")
print(forms_df)
```

**File Location:**
```
edgar/reference/data/secforms.csv
```

---

## Additional Resources

- **SEC Form Types**: https://www.sec.gov/forms
- **EDGAR Filing Manual**: https://www.sec.gov/info/edgar/edgarfm.htm
- **EdgarTools describe_form()**: Programmatic access to form descriptions
- **Full catalog**: 311 forms documented in `secforms.csv`

---

## Quick Reference Card

**Most Common Forms (90% of queries)**:

| Query | Form | Example |
|-------|------|---------|
| Annual report | 10-K | `form="10-K"` |
| Quarterly report | 10-Q | `form="10-Q"` |
| Current event | 8-K | `form="8-K"` |
| IPO | S-1 | `form="S-1"` |
| Crowdfunding | C | `form="C"` |
| Insider trading | 4 | `form="4"` |
| Institutional holdings | 13F-HR | `form="13F-HR"` |
| Proxy statement | DEF 14A | `form="DEF 14A"` |
| Private placement | D | `form="D"` |
| Foreign annual | 20-F | `form="20-F"` |

---

**Last Updated:** Auto-generated from `edgar/reference/data/secforms.csv`
**Total Forms Documented:** 311
**Data Source:** SEC EDGAR Filing System
