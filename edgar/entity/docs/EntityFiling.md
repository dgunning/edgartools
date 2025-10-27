# EntityFiling Class Documentation

## Overview

The `EntityFiling` class extends the base `Filing` class with additional entity-specific metadata and functionality. When you access filings through a `Company` object, you get `EntityFiling` instances that include enriched information from the SEC's company submissions API.

**Key Differences from Base Filing:**
- Additional metadata (items, acceptance datetime, file number, etc.)
- `related_filings()` method to find filings by file number
- XBRL format indicators (is_xbrl, is_inline_xbrl)
- Report date separate from filing date
- Access to entity context

## Getting EntityFilings

### From Company

```python
from edgar import Company

# Get company
company = Company("AAPL")

# Get filings - returns EntityFiling instances
filings = company.get_filings(form="10-K")
filing = filings.latest()

# filing is now an EntityFiling, not base Filing
print(type(filing))  # <class 'edgar.entity.filings.EntityFiling'>
```

### Automatic Enhancement

When you call `company.get_filings()`, the filings are automatically EntityFiling instances with additional metadata.

## Common Actions

Quick reference for the most frequently used EntityFiling methods:

### Access Filing Content
```python
# Get HTML content
html = filing.html()

# Get plain text
text = filing.text()

# Get markdown formatted content
markdown = filing.markdown()
```

### Get Structured Data
```python
# Get form-specific object (10-K, 10-Q, 8-K, etc.)
report = filing.obj()

# Get XBRL financial data
xbrl = filing.xbrl()
```

### Entity-Specific Features
```python
# Find related filings (amendments, etc.)
related = filing.related_filings()

# Check XBRL availability
if filing.is_xbrl:
    xbrl = filing.xbrl()

# Access entity-specific metadata
print(filing.report_date)        # Period end date
print(filing.items)               # 8-K items
print(filing.file_number)         # SEC file number
```

### View in Browser
```python
# Open filing in web browser
filing.open()
```

### Get Attachments
```python
# Access all filing attachments
attachments = filing.attachments
```

## EntityFiling-Specific Attributes

### Additional Metadata

| Attribute | Type | Description |
|-----------|------|-------------|
| `report_date` | str | Period end date for the report (YYYY-MM-DD) |
| `acceptance_datetime` | str | SEC acceptance timestamp |
| `file_number` | str | SEC file number for tracking related filings |
| `items` | str | 8-K items (e.g., "2.02,9.01") |
| `size` | int | Filing size in bytes |
| `primary_document` | str | Primary document filename |
| `primary_doc_description` | str | Description of primary document |
| `is_xbrl` | bool | Whether filing has XBRL data |
| `is_inline_xbrl` | bool | Whether filing uses inline XBRL |

### Accessing Additional Metadata

```python
filing = company.get_filings(form="10-K").latest()

# Entity-specific attributes
print(f"Report Date: {filing.report_date}")
print(f"Accepted: {filing.acceptance_datetime}")
print(f"File Number: {filing.file_number}")
print(f"Has XBRL: {filing.is_xbrl}")
print(f"Inline XBRL: {filing.is_inline_xbrl}")
print(f"Size: {filing.size:,} bytes")
```

## Working with 8-K Items

The `items` attribute is especially useful for 8-K current reports, which can cover multiple topics.

### Understanding 8-K Items

8-K items indicate what events or information the filing reports:
- **2.02** - Results of Operations and Financial Condition
- **5.02** - Departure/Election of Directors or Officers
- **8.01** - Other Events
- **9.01** - Financial Statements and Exhibits

```python
# Get 8-K filings
filings_8k = company.get_filings(form="8-K")

# Filter by items
for filing in filings_8k:
    if filing.items and "2.02" in filing.items:
        print(f"Earnings 8-K: {filing.filing_date}")
        print(f"  Items: {filing.items}")
```

### Important Note on Legacy Filings

**Data Source Limitation**: The `items` value comes from SEC metadata, not from parsing the filing document.

**For Legacy SGML Filings (1999-2001)**: The SEC's historical metadata may be incorrect or incomplete. Modern XML filings (2005+) have accurate metadata.

**Workaround**: For accurate item extraction from legacy SGML 8-K filings, parse the filing text directly:

```python
# For legacy filings, parse the document
filing_text = filing.text()

# Use regex to find items (adjust pattern as needed)
import re
items_pattern = r'Item\s+(\d+\.\d+)'
found_items = re.findall(items_pattern, filing_text, re.IGNORECASE)
```

## Related Filings

### Finding Related Filings by File Number

Use the `file_number` to find amendments, related documents, or filings from the same series:

```python
# Get original filing
filing = company.get_filings(form="10-K").latest()

# Find all related filings (amendments, etc.)
related = filing.related_filings()

print(f"Original filing: {filing.accession_no}")
print(f"Related filings: {len(related)}")

for f in related:
    print(f"  {f.form} - {f.filing_date}")
```

### Use Cases for Related Filings

**1. Find Amendments:**
```python
# Get original 10-K
filing_10k = company.get_filings(form="10-K").latest()

# Find any amendments
related = filing_10k.related_filings()
amendments = related.filter(form="10-K/A")

if len(amendments) > 0:
    print("Filing was amended:")
    for amendment in amendments:
        print(f"  {amendment.filing_date}: {amendment.accession_no}")
```

**2. Track Filing Series:**
```python
# Get S-1 registration
s1 = company.get_filings(form="S-1").latest()

# Find all related S-1 amendments
series = s1.related_filings()
print(f"Registration series: {len(series)} filings")
```

## XBRL Indicators

The `is_xbrl` and `is_inline_xbrl` attributes help determine if structured financial data is available.

### Checking XBRL Availability

```python
filing = company.get_filings(form="10-K").latest()

if filing.is_xbrl:
    print("Filing has XBRL data")

    if filing.is_inline_xbrl:
        print("  Uses inline XBRL format")
        xbrl = filing.xbrl()  # Parse XBRL data
    else:
        print("  Uses traditional XBRL format")
else:
    print("No XBRL data available")
```

### Filtering by XBRL

```python
# Get only filings with XBRL data
filings = company.get_filings(form="10-Q")

xbrl_filings = [f for f in filings if f.is_xbrl]
print(f"{len(xbrl_filings)} of {len(filings)} have XBRL")

# Check inline XBRL adoption
inline_count = sum(1 for f in xbrl_filings if f.is_inline_xbrl)
print(f"{inline_count} use inline XBRL format")
```

## Report Date vs Filing Date

EntityFiling provides both `report_date` and `filing_date`:

- **`report_date`**: Period end date (what the filing reports on)
- **`filing_date`**: When the filing was submitted to SEC

```python
filing = company.get_filings(form="10-Q").latest()

print(f"Period Ended: {filing.report_date}")
print(f"Filed On: {filing.filing_date}")

# Calculate filing lag
from datetime import datetime
report_dt = datetime.strptime(filing.report_date, '%Y-%m-%d')
filing_dt = datetime.strptime(filing.filing_date, '%Y-%m-%d')
lag_days = (filing_dt - report_dt).days

print(f"Filing lag: {lag_days} days")
```

## Common Workflows

### Analyzing 8-K Patterns

```python
# Get all 8-K filings
filings_8k = company.get_filings(form="8-K")

# Categorize by item
from collections import Counter
item_counts = Counter()

for filing in filings_8k:
    if filing.items:
        for item in filing.items.split(','):
            item_counts[item.strip()] += 1

# Show most common 8-K topics
print("Most common 8-K items:")
for item, count in item_counts.most_common(5):
    print(f"  Item {item}: {count} filings")
```

### Track Amendment Activity

```python
# Get all 10-K filings including amendments
all_10k = company.get_filings(form=["10-K", "10-K/A"])

# Group by year
from collections import defaultdict
by_year = defaultdict(list)

for filing in all_10k:
    year = filing.report_date[:4]
    by_year[year].append(filing)

# Check which years had amendments
for year in sorted(by_year.keys(), reverse=True):
    filings = by_year[year]
    has_amendment = any('/A' in f.form for f in filings)
    status = "amended" if has_amendment else "original"
    print(f"{year}: {len(filings)} filing(s) - {status}")
```

### Find Earnings Announcements

```python
# Find 8-K filings with earnings (Item 2.02)
earnings_8k = []

for filing in company.get_filings(form="8-K"):
    if filing.items and "2.02" in filing.items:
        earnings_8k.append(filing)

print(f"Found {len(earnings_8k)} earnings 8-K filings")

# Show filing timeline
for filing in earnings_8k[-5:]:  # Last 5
    print(f"{filing.report_date}: {filing.filing_date}")
```

### Check XBRL Adoption Timeline

```python
# Track when company started using XBRL
filings = company.get_filings(form="10-K")

for filing in filings:
    xbrl_status = "inline XBRL" if filing.is_inline_xbrl else "XBRL" if filing.is_xbrl else "no XBRL"
    print(f"{filing.filing_date}: {xbrl_status}")
```

## Integration with Base Filing Features

EntityFiling inherits all methods from the base Filing class:

```python
filing = company.get_filings(form="10-K").latest()

# All base Filing methods work
html = filing.html()
text = filing.text()
markdown = filing.markdown()
xbrl = filing.xbrl()
filing.open()

# PLUS entity-specific features
related = filing.related_filings()
print(f"8-K items: {filing.items}")
print(f"Has XBRL: {filing.is_xbrl}")
```

## Comparison: EntityFiling vs Base Filing

### When You Get Each Type

**EntityFiling** - From Company context:
```python
company = Company("AAPL")
filing = company.get_filings(form="10-K").latest()
# Type: EntityFiling (with extra metadata)
```

**Base Filing** - From general search:
```python
from edgar import get_filings
filings = get_filings(2024, 3, form="10-K")
filing = filings[0]
# Type: Filing (base class)
```

### Feature Comparison

| Feature | Base Filing | EntityFiling |
|---------|-------------|--------------|
| Basic metadata | ✅ | ✅ |
| Content access (html, text) | ✅ | ✅ |
| XBRL parsing | ✅ | ✅ |
| Report date | ❌ | ✅ |
| Acceptance datetime | ❌ | ✅ |
| File number | ❌ | ✅ |
| 8-K items | ❌ | ✅ |
| XBRL indicators | ❌ | ✅ |
| related_filings() | ❌ | ✅ |

## Best Practices

### 1. Use EntityFiling for Company Analysis

When working with a specific company, always access filings through the Company object to get EntityFiling benefits:

```python
# Good - get EntityFiling with metadata
company = Company("AAPL")
filing = company.get_filings(form="10-K").latest()

# Less ideal - get base Filing without metadata
filings = get_filings(2024, 3, form="10-K").filter(ticker="AAPL")
filing = filings[0]
```

### 2. Check XBRL Availability Before Parsing

```python
filing = company.get_filings(form="10-K").latest()

if filing.is_xbrl:
    xbrl = filing.xbrl()
    statements = xbrl.statements
else:
    print("No structured financial data available")
```

### 3. Handle Missing Items Gracefully

```python
# Items may be None or empty string
if filing.items:
    items_list = filing.items.split(',')
else:
    items_list = []
```

### 4. Use Related Filings to Track Changes

```python
# Find if filing was amended
filing = company.get_filings(form="10-K").latest()
related = filing.related_filings()

amendments = [f for f in related if '/A' in f.form]
if amendments:
    print(f"This filing has {len(amendments)} amendment(s)")
    latest_amendment = amendments[-1]
    print(f"Most recent: {latest_amendment.filing_date}")
```

## Error Handling

### Missing Attributes

Not all filings have all attributes populated:

```python
filing = company.get_filings(form="8-K").latest()

# Some filings may not have items
items = filing.items if filing.items else "Not specified"

# File number should always be present for EntityFiling
if filing.file_number:
    print(f"File number: {filing.file_number}")
```

### XBRL Parsing Failures

Even if `is_xbrl` is True, parsing can fail:

```python
if filing.is_xbrl:
    try:
        xbrl = filing.xbrl()
        statements = xbrl.statements
    except Exception as e:
        print(f"XBRL parsing failed: {e}")
        # Fall back to text parsing
        text = filing.text()
```

## Performance Considerations

### Efficient Filtering

Use EntityFiling metadata to filter before expensive operations:

```python
# Filter by XBRL availability first
filings = company.get_filings(form="10-Q")
xbrl_filings = [f for f in filings if f.is_xbrl]

# Then parse only those with XBRL
for filing in xbrl_filings:
    xbrl = filing.xbrl()
    # Process XBRL data...
```

### Batch Operations

When processing many filings, check size first:

```python
filings = company.get_filings()

# Process smaller filings first
sorted_filings = sorted(filings, key=lambda f: f.size)

for filing in sorted_filings[:10]:  # Process 10 smallest
    html = filing.html()
    # Process content...
```

## Troubleshooting

### "EntityFiling has no attribute 'X'"

You're trying to use EntityFiling-specific features on a base Filing object:

```python
# Problem: Base filing doesn't have entity attributes
filings = get_filings(2024, 3)
filing = filings[0]
# filing.report_date  # AttributeError!

# Solution: Get from company for EntityFiling
company = Company(filing.cik)
entity_filing = company.get_filings(
    accession_number=filing.accession_no
)[0]
# entity_filing.report_date  # Works!
```

### Related Filings Returns Empty

The file number might not link to other filings:

```python
related = filing.related_filings()

if len(related) == 0:
    print("No related filings found")
    # This is normal for standalone filings
else:
    print(f"Found {len(related)} related filing(s)")
```

### Items Not Showing for 8-K

Check if it's a legacy filing:

```python
filing = company.get_filings(form="8-K")[0]

if not filing.items or filing.items == "":
    # Check filing year
    filing_year = int(filing.filing_date[:4])

    if filing_year < 2005:
        print("Legacy SGML filing - items may be missing from metadata")
        print("Parse filing text for accurate item identification")
    else:
        print("Modern filing with no items specified")
```

This comprehensive guide covers the unique features and workflows available when working with EntityFiling objects in edgartools.
