# EntityFilings

A collection of filings for a specific company with entity context preserved.

## Overview

`EntityFilings` extends the base `Filings` class with company-specific functionality. It maintains entity context (CIK and company name) throughout all operations and returns `EntityFiling` instances with enriched metadata.

## Quick Start

```python
from edgar import Company

# Get company filings
company = Company("AAPL")
filings = company.get_filings()

# Access entity context
print(filings.cik)            # Company CIK
print(filings.company_name)   # Company name

# Check if empty
if filings.empty:
    print("No filings found")

# Get latest filing
latest = filings.latest()

# Filter the collection
annual = filings.filter(form="10-K")
recent = filings.filter(filing_date="2024-01-01:")
```

## Common Actions

### Get Individual Filings

```python
# Most recent filing
latest = filings.latest()

# Multiple recent filings
latest_5 = filings.latest(5)

# By index
filing = filings[0]
filing = filings.get_filing_at(5)
```

### Filter the Collection

```python
# By form type
annual = filings.filter(form="10-K")
quarterly = filings.filter(form="10-Q")
multiple = filings.filter(form=["10-K", "10-Q"])

# By date
recent = filings.filter(filing_date="2024-01-01:")
date_range = filings.filter(filing_date="2023-01-01:2023-12-31")

# Exclude amendments
originals = filings.filter(amendments=False)

# Combined filters
filtered = filings.filter(
    form="10-Q",
    filing_date="2024-01-01:",
    amendments=False
)
```

### Select Subsets

```python
# First/last n filings
first_10 = filings.head(10)
last_10 = filings.tail(10)

# Random sample
sample = filings.sample(20)
```

### Convert to DataFrame

```python
# All columns
df = filings.to_pandas()

# Specific columns
df = filings.to_pandas('form', 'filing_date', 'accession_number')
```

## Properties

### Entity Context

Context is maintained throughout operations:

```python
filings = company.get_filings()

print(filings.cik)           # Company CIK
print(filings.company_name)  # Company name

# Context preserved after filtering
filtered = filings.filter(form="10-K")
print(filtered.cik)          # Same CIK
print(filtered.company_name) # Same name
```

### Collection Status

```python
# Check if empty
if filings.empty:
    print("No filings")

# Get count
count = len(filings)

# Get date range
start, end = filings.date_range
print(f"Filings from {start} to {end}")
```

## Methods

### latest(n=1)

Get most recent filing(s):

```python
# Single latest (returns EntityFiling)
latest = filings.latest()

# Multiple latest (returns EntityFilings)
latest_5 = filings.latest(5)
```

### filter()

Filter by multiple criteria:

```python
# By form
annual = filings.filter(form="10-K")
multiple = filings.filter(form=["10-K", "10-Q"])

# By date
recent = filings.filter(filing_date="2024-01-01:")
date_range = filings.filter(
    filing_date="2023-01-01:2023-12-31"
)

# Exclude amendments
originals = filings.filter(amendments=False)

# By accession number
specific = filings.filter(
    accession_number="0000320193-24-000123"
)

# By file number
related = filings.filter(file_number="001-36743")
```

Note: Unlike base `Filings.filter()`, `EntityFilings` doesn't accept `cik` or `ticker` parameters (already scoped to one entity).

### head() / tail()

Get first or last n filings:

```python
first_10 = filings.head(10)
last_10 = filings.tail(10)
```

### sample()

Get random sample:

```python
sample = filings.sample(20)
```

### Indexing

Direct access by position:

```python
first = filings[0]
tenth = filings[9]
```

## Pagination

For large collections, navigate through pages:

```python
# Check if paginated
print(filings)
# Shows: "Showing 1 to 50 of 250 filings"

# Navigate pages
page_2 = filings.next()
page_1 = page_2.previous()

# At boundaries
last_page = filings
while True:
    next_page = last_page.next()
    if next_page is None:
        break
    last_page = next_page
```

## Data Export

### to_pandas()

Convert to DataFrame:

```python
# All columns
df = filings.to_pandas()

# Specific columns
df = filings.to_pandas('form', 'filing_date', 'accession_number')

# Columns include:
# form, filing_date, reportDate, acceptanceDateTime,
# fileNumber, items, size, isXBRL, isInlineXBRL, etc.
```

### save_parquet()

Save to Parquet file:

```python
filings.save_parquet("company_filings.parquet")
```

### to_dict()

Convert to dictionary:

```python
data = filings.to_dict()
```

## Common Workflows

### Get Latest Annual Report

```python
company = Company("AAPL")
filings = company.get_filings(form="10-K")
latest = filings.latest()

print(f"Latest 10-K: {latest.filing_date}")
print(f"Period: {latest.report_date}")

if latest.is_xbrl:
    xbrl = latest.xbrl()
```

### Analyze Quarterly Trends

```python
# Get last 4 quarters
filings = company.get_filings(form="10-Q")
last_4 = filings.latest(4)

for filing in last_4:
    print(f"Quarter: {filing.report_date}")
    print(f"Filed: {filing.filing_date}")
```

### Find Earnings Announcements

```python
# Get all 8-K filings
filings = company.get_filings(form="8-K")

# Filter for earnings (Item 2.02)
for filing in filings:
    if filing.items and "2.02" in filing.items:
        print(f"Earnings: {filing.filing_date}")
```

### Export to CSV

```python
# Get specific forms
filings = company.get_filings(form=["10-K", "10-Q"])

# Filter by date
recent = filings.filter(filing_date="2024-01-01:")

# Convert and export
df = recent.to_pandas()
df.to_csv("company_filings.csv", index=False)
```

### Track Amendment Activity

```python
# Get all 10-K including amendments
all_10k = company.get_filings(form=["10-K", "10-K/A"])

# Separate
originals = all_10k.filter(amendments=False)
amendments = all_10k.filter(form="10-K/A")

print(f"Original: {len(originals)}")
print(f"Amended: {len(amendments)}")
```

## Display

### Rich Terminal Display

```python
print(filings)
```

Shows table with:
- Filing number, form, description
- Filing date, accession number
- Pagination info (if multiple pages)
- Panel title with company name and CIK
- Date range subtitle

### String Representation

Compact LLM-optimized format:

```python
str(filings)
# Filings: 250 | Apple Inc. | 2020-01-01 to 2024-12-31
#    #  Filed       Form
#   0. 2024-12-15  10-K
#   1. 2024-09-30  10-Q
#   ... (248 more)
```

## Type Preservation

All operations preserve `EntityFilings` type:

```python
# filter() returns EntityFilings
filtered = filings.filter(form="10-K")
print(type(filtered))  # EntityFilings

# head() returns EntityFilings
first_10 = filings.head(10)
print(type(first_10))  # EntityFilings

# latest(n) with n>1 returns EntityFilings
latest_5 = filings.latest(5)
print(type(latest_5))  # EntityFilings

# latest() with n=1 returns EntityFiling
latest = filings.latest()
print(type(latest))  # EntityFiling
```

## EntityFilings vs Base Filings

### When You Get Each Type

**EntityFilings** - from Company:

```python
company = Company("AAPL")
filings = company.get_filings()
# Type: EntityFilings
```

**Base Filings** - from general search:

```python
from edgar import get_filings
filings = get_filings(2024, 1, form="10-K")
# Type: Filings
```

### Feature Comparison

| Feature | Base Filings | EntityFilings |
|---------|--------------|---------------|
| Filter by form | ✓ | ✓ |
| Filter by date | ✓ | ✓ |
| Filter by cik/ticker | ✓ | ✗ (already scoped) |
| Returns EntityFiling | ✗ | ✓ |
| Entity context | ✗ | ✓ |
| Type preserved | Filings | EntityFilings |

## Best Practices

### Check if Empty

```python
filings = company.get_filings(form="RARE-FORM")

if filings.empty:
    print("No filings found")
else:
    latest = filings.latest()
```

### Use latest() for Single Filing

```python
# Good - returns single EntityFiling
filing = filings.latest()

# Less efficient - returns EntityFilings collection
one_filing = filings.head(1)
filing = one_filing[0]
```

### Filter Early

```python
# Good - filter at source
recent_10k = company.get_filings(
    form="10-K",
    filing_date="2024-01-01:"
)

# Less efficient - get all then filter
all_filings = company.get_filings()
recent_10k = [f for f in all_filings
              if f.form == "10-K"
              and f.filing_date >= "2024-01-01"]
```

### Preserve EntityFilings Type

```python
# All operations maintain type and context
filings = company.get_filings()
filtered = filings.filter(form="10-K")
recent = filtered.filter(filing_date="2024-01-01:")

# Context still available
print(recent.cik)           # ✓
print(recent.company_name)  # ✓
```

## Performance Tips

### Filter Before Processing

```python
# Good - filter first
xbrl_10k = company.get_filings(form="10-K")
for filing in xbrl_10k:
    if filing.is_xbrl:
        xbrl = filing.xbrl()
        # Process...

# Less efficient
all_filings = company.get_filings()
for filing in all_filings:
    if filing.form == "10-K" and filing.is_xbrl:
        xbrl = filing.xbrl()
```

### Use Pagination

For very large collections:

```python
page = company.get_filings()
while page:
    for filing in page:
        process(filing)
    page = page.next()
```

### Convert to DataFrame Only When Needed

```python
# Good - use EntityFilings methods
latest = filings.filter(form="10-K").latest()

# Less efficient - convert first
df = filings.to_pandas()
df_10k = df[df['form'] == '10-K']
# Now lost EntityFiling functionality
```

## Error Handling

### Empty Collections

```python
if filings.empty:
    print("No filings")
else:
    latest = filings.latest()
```

### Pagination Boundaries

```python
next_page = filings.next()
if next_page is None:
    print("No more pages")
```

### Invalid Index

```python
if len(filings) > 5:
    filing = filings[5]
else:
    print("Collection has fewer than 6 filings")
```

## See Also

- [EntityFiling](EntityFiling.md) - Working with individual filings
- [Company](Company.md) - Company class documentation
