# EntityFilings Class Documentation

## Overview

The `EntityFilings` class extends the base `Filings` class with entity-specific functionality. When you access filings through a `Company` object, you get an `EntityFilings` collection that maintains entity context (CIK and company name) and returns `EntityFiling` instances with enriched metadata.

**Key Differences from Base Filings:**
- Maintains entity context (CIK, company name)
- Returns `EntityFiling` instances (not base `Filing`)
- All filtering/selection methods preserve `EntityFilings` type
- Additional metadata from SEC company submissions API
- Direct access to entity-specific features

## Getting EntityFilings

### From Company

```python
from edgar import Company

# Get company
company = Company("AAPL")

# Get filings - returns EntityFilings collection
filings = company.get_filings()

# filings is EntityFilings, not base Filings
print(type(filings))  # <class 'edgar.entity.filings.EntityFilings'>

# Each filing in the collection is EntityFiling
filing = filings[0]
print(type(filing))  # <class 'edgar.entity.filings.EntityFiling'>
```

### With Form Filters

```python
# Get specific form types
filings_10k = company.get_filings(form="10-K")
filings_8k = company.get_filings(form="8-K")
filings_multi = company.get_filings(form=["10-K", "10-Q"])
```

## Common Actions

Quick reference for the most frequently used EntityFilings methods:

### Get Individual Filings
```python
# Get most recent filing
latest = filings.latest()

# Get multiple recent filings
latest_5 = filings.latest(5)

# Get filing by index
filing = filings[0]
filing = filings.get_filing_at(5)
```

### Filter the Collection
```python
# Filter by form type
annual_reports = filings.filter(form="10-K")

# Filter by date
recent = filings.filter(filing_date="2024-01-01:")

# Exclude amendments
originals_only = filings.filter(amendments=False)

# Combined filters
filtered = filings.filter(
    form=["10-K", "10-Q"],
    filing_date="2023-01-01:2023-12-31",
    amendments=False
)
```

### Navigate Pages
```python
# For large collections (multiple pages)
next_page = filings.next()
prev_page = filings.previous()
```

### Convert to DataFrame
```python
# Export to pandas
df = filings.to_pandas()

# Select specific columns
df = filings.to_pandas('form', 'filing_date', 'accession_number')
```

### Select Subsets
```python
# Get first/last n filings
first_10 = filings.head(10)
last_10 = filings.tail(10)

# Random sample
sample = filings.sample(20)
```

## EntityFilings-Specific Features

### Entity Context

EntityFilings maintains the entity context throughout operations:

```python
filings = company.get_filings()

# Access entity information
print(filings.cik)           # Company CIK
print(filings.company_name)  # Company name

# Context preserved through operations
filtered = filings.filter(form="10-K")
print(filtered.cik)          # Same CIK
print(filtered.company_name) # Same company name
```

### Returns EntityFiling Instances

All methods that return individual filings return `EntityFiling` (not base `Filing`):

```python
# Get latest returns EntityFiling
filing = filings.latest()
print(type(filing))  # EntityFiling

# Indexing returns EntityFiling
filing = filings[0]
print(type(filing))  # EntityFiling

# Access EntityFiling-specific attributes
print(filing.report_date)    # Period end date
print(filing.items)          # 8-K items
print(filing.is_xbrl)        # XBRL indicator
```

### Type Preservation

All collection methods preserve the `EntityFilings` type:

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
```

## Core Methods

### latest(n=1)

Get the most recent filing(s):

```python
# Get single latest filing (returns EntityFiling)
latest = filings.latest()
print(f"Most recent: {latest.form} on {latest.filing_date}")

# Get multiple latest filings (returns EntityFilings)
latest_5 = filings.latest(5)
for filing in latest_5:
    print(f"{filing.form}: {filing.filing_date}")
```

### filter()

Filter filings by various criteria:

```python
# Filter by form type
filings_10k = filings.filter(form="10-K")
filings_8k = filings.filter(form="8-K")
filings_annual = filings.filter(form=["10-K", "10-K/A"])

# Filter by date
recent = filings.filter(filing_date="2024-01-01:")
date_range = filings.filter(filing_date="2023-01-01:2023-12-31")
specific_date = filings.filter(filing_date="2024-03-15")

# Exclude amendments
no_amendments = filings.filter(amendments=False)

# Filter by accession number
specific = filings.filter(accession_number="0000320193-24-000123")

# Combined filters
filtered = filings.filter(
    form="10-Q",
    filing_date="2024-01-01:",
    amendments=False
)
```

**Note**: Unlike base `Filings.filter()`, `EntityFilings.filter()` doesn't support `cik` or `ticker` parameters since the collection is already scoped to a single entity.

### head(n) / tail(n)

Get first or last n filings:

```python
# Get first 10 filings
first_10 = filings.head(10)

# Get last 10 filings
last_10 = filings.tail(10)

# Both return EntityFilings collections
print(type(first_10))  # EntityFilings
print(type(last_10))   # EntityFilings
```

### sample(n)

Get random sample of filings:

```python
# Get random sample of 20 filings
sample = filings.sample(20)

# Returns EntityFilings collection
print(type(sample))  # EntityFilings
```

### Access by Index

```python
# Direct indexing
first_filing = filings[0]
tenth_filing = filings[9]

# Explicit method
filing = filings.get_filing_at(5)

# All return EntityFiling instances
```

## Pagination

For large filing collections, EntityFilings supports pagination:

### next() / previous()

```python
# Display shows page info if multiple pages
print(filings)
# Shows: "Showing 1 to 50 of 250 filings. Page using ← prev() and next() →"

# Navigate to next page
next_page = filings.next()

# Navigate to previous page
prev_page = filings.previous()

# Both return EntityFilings with new page of data
```

### Page Navigation Example

```python
# Start with first page
current_page = company.get_filings()
print(current_page)

# Move through pages
page_2 = current_page.next()
page_3 = page_2.next()

# Go back
page_2_again = page_3.previous()

# At end of pages
last_page = current_page
while True:
    next_page = last_page.next()
    if next_page is None:
        break
    last_page = next_page
```

## Data Conversion & Export

### to_pandas()

Convert to pandas DataFrame:

```python
# All columns
df = filings.to_pandas()

# Specific columns
df = filings.to_pandas('form', 'filing_date', 'accession_number')

# Shows entity-specific columns:
# form, filing_date, reportDate, acceptanceDateTime, fileNumber,
# items, size, primaryDocument, isXBRL, isInlineXBRL, etc.
```

### to_dict()

Convert to dictionary:

```python
# Convert to dict
data = filings.to_dict()

# Limit rows
data = filings.to_dict(max_rows=100)
```

### save() / save_parquet()

Save to Parquet file:

```python
# Save as Parquet
filings.save_parquet("company_filings.parquet")

# Alternative
filings.save("company_filings.parquet")
```

## Common Workflows

### Get Most Recent Annual Report

```python
company = Company("AAPL")

# Get all 10-K filings
filings_10k = company.get_filings(form="10-K")

# Get most recent
latest_10k = filings_10k.latest()

print(f"Latest 10-K: {latest_10k.filing_date}")
print(f"Period: {latest_10k.report_date}")

# Access XBRL if available
if latest_10k.is_xbrl:
    xbrl = latest_10k.xbrl()
```

### Analyze Quarterly Reports

```python
# Get all 10-Q filings
filings_10q = company.get_filings(form="10-Q")

# Get last 4 quarters
last_4_quarters = filings_10q.latest(4)

# Analyze each quarter
for filing in last_4_quarters:
    print(f"Quarter ending {filing.report_date}:")
    print(f"  Filed: {filing.filing_date}")
    print(f"  XBRL: {filing.is_xbrl}")
```

### Find 8-K Earnings Announcements

```python
# Get all 8-K filings
filings_8k = company.get_filings(form="8-K")

# Filter for earnings-related items
earnings_filings = []
for filing in filings_8k:
    if filing.items and "2.02" in filing.items:
        earnings_filings.append(filing)

print(f"Found {len(earnings_filings)} earnings 8-Ks")

# Show recent earnings dates
for filing in earnings_filings[:5]:
    print(f"{filing.filing_date}: Items {filing.items}")
```

### Track Amendment Activity

```python
# Get all 10-K filings including amendments
all_10k = company.get_filings(form=["10-K", "10-K/A"])

# Separate originals from amendments
originals = all_10k.filter(amendments=False)
amendments = all_10k.filter(form="10-K/A")

print(f"Original 10-Ks: {len(originals)}")
print(f"Amended 10-Ks: {len(amendments)}")

# Show amendment details
for amendment in amendments:
    print(f"{amendment.filing_date}: {amendment.accession_no}")
```

### Export Filings to DataFrame

```python
# Get recent filings
filings = company.get_filings(form=["10-K", "10-Q"])

# Filter to recent year
recent = filings.filter(filing_date="2024-01-01:")

# Convert to DataFrame
df = recent.to_pandas()

# Analyze
print(f"Total filings: {len(df)}")
print(f"Forms: {df['form'].value_counts()}")
print(f"XBRL filings: {df['isXBRL'].sum()}")

# Export
df.to_csv("aapl_recent_filings.csv", index=False)
```

### Compare XBRL Adoption

```python
# Get all annual reports
filings_10k = company.get_filings(form="10-K")

# Convert to DataFrame
df = filings_10k.to_pandas()

# Group by year
df['year'] = pd.to_datetime(df['filing_date']).dt.year

# Check XBRL adoption by year
xbrl_by_year = df.groupby('year').agg({
    'isXBRL': 'sum',
    'isInlineXBRL': 'sum',
    'form': 'count'
}).rename(columns={'form': 'total'})

print(xbrl_by_year)
```

## Display & Representation

### Rich Display

EntityFilings displays as a rich table with pagination info:

```python
print(filings)
```

Shows:
- Table of filings with: #, Form, Description, Filing Date, Accession Number
- Pagination info (if multiple pages): "Showing 1 to 50 of 250 filings"
- Panel title: "Filings for [Company Name] [CIK]"
- Panel subtitle: Date range of filings

### Properties

```python
# Check if empty
if filings.empty:
    print("No filings found")

# Get date range
start, end = filings.date_range
print(f"Filings from {start} to {end}")

# Get summary
print(filings.summary)
```

## Comparison: EntityFilings vs Base Filings

### When You Get Each Type

**EntityFilings** - From Company context:
```python
company = Company("AAPL")
filings = company.get_filings()
# Type: EntityFilings (with entity context)
```

**Base Filings** - From general search:
```python
from edgar import get_filings
filings = get_filings(2024, 1, form="10-K")
# Type: Filings (base class)
```

### Feature Comparison

| Feature | Base Filings | EntityFilings |
|---------|-------------|---------------|
| Filter by form | ✅ | ✅ |
| Filter by date | ✅ | ✅ |
| Filter by CIK/ticker | ✅ | ❌ (already scoped to entity) |
| Returns EntityFiling | ❌ | ✅ |
| Entity context (CIK, name) | ❌ | ✅ |
| Type preserved in operations | Filings | EntityFilings |
| From Company.get_filings() | ❌ | ✅ |

## Best Practices

### 1. Use EntityFilings for Company Analysis

When working with a specific company, always use `Company.get_filings()`:

```python
# Good - get EntityFilings with context
company = Company("AAPL")
filings = company.get_filings(form="10-K")

# Less ideal - get base Filings, requires filtering
from edgar import get_filings
all_filings = get_filings(2024, 1, form="10-K")
apple_filings = all_filings.filter(ticker="AAPL")
```

### 2. Check Empty Collections

```python
filings = company.get_filings(form="RARE-FORM")

if filings.empty:
    print("No filings found")
else:
    latest = filings.latest()
```

### 3. Use latest() for Single Most Recent

```python
# Get single filing
filing = filings.latest()

# Not this (gets collection of 1)
filings_one = filings.head(1)
filing = filings_one[0]
```

### 4. Preserve Type Through Operations

```python
# All these return EntityFilings
filtered = filings.filter(form="10-K")
recent = filtered.filter(filing_date="2024-01-01:")
sample = recent.sample(10)

# All maintain entity context
print(sample.cik)           # Still accessible
print(sample.company_name)  # Still accessible
```

## Error Handling

### Empty Collections

```python
filings = company.get_filings(form="NONEXISTENT")

if filings.empty:
    print("No filings found")
else:
    # Safe to access
    latest = filings.latest()
```

### Pagination at Boundaries

```python
# At end of pages
last_page = filings
while True:
    next_page = last_page.next()
    if next_page is None:
        print("Reached end of filings")
        break
    last_page = next_page
```

### Invalid Index

```python
# Check length first
if len(filings) > 5:
    filing = filings[5]
else:
    print("Collection has fewer than 6 filings")
```

## Performance Considerations

### Efficient Filtering

Filter early to reduce data size:

```python
# Good: filter first, then process
recent_10k = company.get_filings(form="10-K", filing_date="2023-01-01:")
for filing in recent_10k:
    process(filing)

# Less efficient: get all, then filter in Python
all_filings = company.get_filings()
for filing in all_filings:
    if filing.form == "10-K" and filing.filing_date >= "2023-01-01":
        process(filing)
```

### Use Pagination

For very large collections, use pagination:

```python
# Process page by page
current_page = company.get_filings()
while current_page:
    # Process current page
    for filing in current_page:
        process(filing)

    # Move to next page
    current_page = current_page.next()
```

### DataFrame Conversion

Only convert to pandas when needed:

```python
# Good: operate on EntityFilings directly
filings_10k = filings.filter(form="10-K")
latest = filings_10k.latest()

# Less efficient: convert to DataFrame first
df = filings.to_pandas()
df_10k = df[df['form'] == '10-K']
# Now you've lost EntityFiling functionality
```

## Integration with Company

EntityFilings is the primary interface between Company and Filing objects:

```python
company = Company("AAPL")

# Company.get_filings() returns EntityFilings
filings = company.get_filings()

# EntityFilings contains EntityFiling instances
filing = filings[0]

# EntityFiling knows its entity
entity = filing.get_entity()
# entity is the same Company object
```

This creates a seamless workflow for entity-focused analysis while maintaining proper type separation and functionality at each level.
