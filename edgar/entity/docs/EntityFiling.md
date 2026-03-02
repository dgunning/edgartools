# EntityFiling

A filing from a company with enriched metadata from the SEC submissions API.

## Overview

`EntityFiling` extends the base `Filing` class with entity-specific information like report dates, file numbers, 8-K items, and XBRL indicators. You get `EntityFiling` objects when accessing filings through a `Company`.

## Quick Start

```python
from edgar import Company

# Get company filings
company = Company("AAPL")
filings = company.get_filings(form="10-K")

# Access individual filing (returns EntityFiling)
filing = filings.latest()

# EntityFiling-specific attributes
print(filing.report_date)        # Period end date
print(filing.is_xbrl)            # Has XBRL data?
print(filing.file_number)        # SEC file number

# Find related filings
related = filing.related_filings()
```

## Properties

### Core Metadata

Inherited from base Filing:

```python
filing.form                # Form type (e.g., "10-K")
filing.filing_date         # When filed
filing.accession_no        # Unique identifier
filing.cik                 # Company CIK
filing.company             # Company name
```

### EntityFiling-Specific

Additional metadata from company submissions:

| Property | Type | Description |
|----------|------|-------------|
| `report_date` | str | Period end date (YYYY-MM-DD) |
| `acceptance_datetime` | str | SEC acceptance timestamp |
| `file_number` | str | SEC file number |
| `items` | str | 8-K items (e.g., "2.02,9.01") |
| `size` | int | Filing size in bytes |
| `primary_document` | str | Primary document filename |
| `primary_doc_description` | str | Document description |
| `is_xbrl` | bool | Has XBRL data |
| `is_inline_xbrl` | bool | Uses inline XBRL |

### parsed_items (for 8-K)

For 8-K filings, `parsed_items` extracts item numbers from the document text (not metadata):

```python
# SEC metadata (may be incorrect for legacy filings)
print(filing.items)  # "3"

# Parsed from actual filing document (accurate)
print(filing.parsed_items)  # "7"
```

This is useful for legacy SGML filings (1999-2004) where SEC metadata is often wrong.

## Methods

### related_filings()

Find all filings with the same file number (amendments, series).

```python
related = filing.related_filings()

# Find amendments
amendments = related.filter(form="10-K/A")

# Check if filing was amended
if len(amendments) > 0:
    print("Filing was amended")
    latest_amendment = amendments.latest()
```

### Content Access

Inherited from base Filing:

```python
# Get HTML content
html = filing.html()

# Get plain text
text = filing.text()

# Get markdown
markdown = filing.markdown()

# Get XBRL data
xbrl = filing.xbrl()

# Get form-specific object
report = filing.obj()  # Returns TenK, TenQ, EightK, etc.

# Open in browser
filing.open()
```

## Working with 8-K Items

8-K filings report specific events using item numbers:

### Common 8-K Items

| Item | Description |
|------|-------------|
| 2.02 | Results of Operations and Financial Condition |
| 5.02 | Departure/Election of Directors or Officers |
| 8.01 | Other Events |
| 9.01 | Financial Statements and Exhibits |

### Finding Earnings Announcements

```python
# Get all 8-K filings
filings_8k = company.get_filings(form="8-K")

# Filter for earnings (Item 2.02)
for filing in filings_8k:
    if filing.items and "2.02" in filing.items:
        print(f"Earnings 8-K: {filing.filing_date}")
```

### Handling Legacy Filings

For filings from 1999-2004, SEC metadata may be incorrect:

```python
filing_year = int(filing.filing_date[:4])

if filing_year < 2005:
    # Use parsed_items for accurate extraction
    items = filing.parsed_items
else:
    # Use metadata items
    items = filing.items
```

## XBRL Indicators

Check XBRL availability before parsing:

```python
if filing.is_xbrl:
    print("XBRL data available")

    if filing.is_inline_xbrl:
        print("Uses inline XBRL format")

    xbrl = filing.xbrl()
    statements = xbrl.statements
else:
    print("No XBRL data - must parse text")
```

### XBRL Adoption Timeline

```python
# Track when company adopted XBRL
filings = company.get_filings(form="10-K")

for filing in filings:
    status = "inline XBRL" if filing.is_inline_xbrl else \
             "XBRL" if filing.is_xbrl else \
             "no XBRL"
    print(f"{filing.filing_date}: {status}")
```

## Report Date vs Filing Date

- `report_date` - Period end date (what the report covers)
- `filing_date` - When submitted to SEC

```python
filing = company.get_filings(form="10-Q").latest()

print(f"Quarter Ended: {filing.report_date}")
print(f"Filed On: {filing.filing_date}")

# Calculate filing lag
from datetime import datetime
report_dt = datetime.strptime(filing.report_date, '%Y-%m-%d')
filing_dt = datetime.strptime(filing.filing_date, '%Y-%m-%d')
lag = (filing_dt - report_dt).days
print(f"Filing lag: {lag} days")
```

## Common Workflows

### Find and Parse Latest 10-K

```python
company = Company("TSLA")
filings = company.get_filings(form="10-K")
latest = filings.latest()

# Check XBRL
if latest.is_xbrl:
    xbrl = latest.xbrl()
    income = xbrl.statements.income_statement()
    print(income.to_dataframe())
```

### Track Amendment History

```python
# Get original filing
filing = company.get_filings(form="10-K").latest()

# Find related filings
related = filing.related_filings()

# Check for amendments
amendments = [f for f in related if '/A' in f.form]

if amendments:
    print(f"Filing has {len(amendments)} amendment(s)")
    for amendment in amendments:
        print(f"  {amendment.filing_date}")
```

### Analyze 8-K Pattern

```python
from collections import Counter

filings_8k = company.get_filings(form="8-K")

# Count item frequencies
item_counts = Counter()
for filing in filings_8k:
    if filing.items:
        for item in filing.items.split(','):
            item_counts[item.strip()] += 1

# Show most common topics
for item, count in item_counts.most_common(5):
    print(f"Item {item}: {count} filings")
```

## EntityFiling vs Base Filing

### When You Get Each Type

**EntityFiling** - from Company context:

```python
company = Company("AAPL")
filing = company.get_filings(form="10-K").latest()
# Type: EntityFiling (with entity metadata)
```

**Base Filing** - from general search:

```python
from edgar import get_filings
filings = get_filings(2024, 1, form="10-K")
filing = filings[0]
# Type: Filing (base class)
```

### Feature Comparison

| Feature | Base Filing | EntityFiling |
|---------|-------------|--------------|
| Content access (html, text, xbrl) | ✓ | ✓ |
| Report date | ✗ | ✓ |
| File number | ✗ | ✓ |
| 8-K items | ✗ | ✓ |
| XBRL indicators | ✗ | ✓ |
| related_filings() | ✗ | ✓ |

## Best Practices

### Check Data Availability

```python
# Items may be None or empty
items = filing.items if filing.items else "Not specified"

# XBRL may not exist
if filing.is_xbrl:
    xbrl = filing.xbrl()
```

### Use EntityFiling for Company Analysis

```python
# Good - get EntityFiling with metadata
company = Company("AAPL")
filing = company.get_filings(form="10-K").latest()
print(filing.report_date)  # Available

# Less ideal - get base Filing without metadata
from edgar import get_filings
filings = get_filings(2024, 1, form="10-K")
filing = filings[0]
# filing.report_date  # AttributeError!
```

### Handle XBRL Parsing Errors

```python
if filing.is_xbrl:
    try:
        xbrl = filing.xbrl()
        statements = xbrl.statements
    except Exception as e:
        print(f"XBRL parsing failed: {e}")
        text = filing.text()  # Fall back to text
```

## Troubleshooting

### Items Not Showing for 8-K

Check filing year:

```python
if not filing.items:
    year = int(filing.filing_date[:4])
    if year < 2005:
        print("Legacy filing - use parsed_items")
        items = filing.parsed_items
    else:
        print("Modern filing with no items specified")
```

### Related Filings Returns Empty

This is normal for standalone filings:

```python
related = filing.related_filings()

if related.empty:
    print("No related filings (normal for standalone)")
else:
    print(f"Found {len(related)} related filing(s)")
```

## See Also

- [EntityFilings](EntityFilings.md) - Working with filing collections
- [Company](Company.md) - Company class documentation
