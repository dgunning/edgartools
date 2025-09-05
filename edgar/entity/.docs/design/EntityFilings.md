# EntityFilings Class Documentation

## Overview

The `EntityFilings` class is a specialized collection for SEC filings associated with a specific entity/company. It extends the base `Filings` class with entity-specific functionality, maintaining the company context and providing enhanced filing objects with additional metadata.

## Key Differences from Filings

- **Entity Context**: Maintains CIK and company name throughout operations
- **Enhanced Filing Objects**: Returns `EntityFiling` objects with additional metadata
- **Entity-Specific Methods**: Tailored functionality for single-entity analysis
- **Rich Display**: Customized console output showing company information

## Getting Filings

```python
c = Company("AAPL")  # Create a Company object
entity_filings = c.get_filings()  # Get filings for the company
```


### Data Selection Methods
```python
# Get latest filings
latest_filing = entity_filings.latest()       # Most recent (single filing)
latest_five = entity_filings.latest(5)        # Most recent 5 (EntityFilings)

# Get first/last n filings
first_ten = entity_filings.head(10)           # First 10 filings
last_ten = entity_filings.tail(10)            # Last 10 filings

# Random sampling
sample = entity_filings.sample(20)            # Random 20 filings
```

## Filtering

The `filter()` method returns `EntityFilings` objects maintaining the company context:

```python
# Filter by form type
annual_reports = entity_filings.filter(form="10-K")
quarterlies = entity_filings.filter(form=["10-Q", "10-K"])

# Filter by date
recent_filings = entity_filings.filter(date="2023-01-01:")
q1_filings = entity_filings.filter(date="2023-01-01:2023-03-31")

# Include/exclude amendments
original_only = entity_filings.filter(amendments=False)
with_amendments = entity_filings.filter(amendments=True)

# Filter by accession number
specific_filing = entity_filings.filter(accession_number="0000320193-23-000077")
```

### Date Filtering Formats
- **Specific date**: `date="2023-06-15"`
- **From date**: `date="2023-01-01:"`
- **Up to date**: `date=":2023-12-31"`
- **Date range**: `date="2023-01-01:2023-12-31"`

## Pagination

Navigate through large filing collections while maintaining entity context:

```python
# Navigate pages
next_page = entity_filings.next()             # Next page of filings
prev_page = entity_filings.previous()         # Previous page of filings

# Check pagination status
is_empty = entity_filings.empty               # No filings available
```

## EntityFiling Enhanced Methods

### Related Filings
```python
# Get all filings with the same file number
filing = entity_filings[0]
related = filing.related_filings()            # All filings for same file number
```

### Entity Integration
```python
# Access parent entity
entity = filing.get_entity()                  # Get Entity/Company object
```

## Rich Console Display

EntityFilings provides enhanced console display with:
- Company name and CIK in the title
- Filing form descriptions
- Date range subtitle
- Pagination information
- Navigation hints

```python
# Display in console
print(entity_filings)                         # Rich formatted table
entity_filings.view()                         # Alternative display

# Console output includes:
# - Company name and CIK prominently displayed
# - Form types with descriptions
# - Filing dates and accession numbers
# - Page navigation instructions
```

## Data Export & Analysis

### Summarize Filings
```python
# Get summary DataFrame
summary_df = EntityFilings.summarize(entity_filings.to_pandas())
# Contains: form, filed, accession_number, xbrl columns
```

### DataFrame Conversion
```python
# Convert to pandas for analysis
df = entity_filings.to_pandas()
forms_df = df['form'].value_counts()           # Count by form type
```

## Common Usage Patterns

### Company Filing Analysis
```python
# Get company and analyze filing patterns
company = Entity("AAPL")
filings = company.get_filings()

# Analyze recent annual reports
annual_reports = filings.filter(form="10-K", amendments=False)
latest_10k = annual_reports.latest()

# Check XBRL availability
xbrl_filings = [f for f in filings if f.is_xbrl]
print(f"XBRL filings: {len(xbrl_filings)}")
```

### Form-Specific Analysis
```python
# Analyze 8-K filings and their items
eight_k_filings = filings.filter(form="8-K")
for filing in eight_k_filings.head(10):
    print(f"Date: {filing.filing_date}, Items: {filing.items}")

# Find earnings announcements (Item 2.02)
earnings = [f for f in eight_k_filings if "2.02" in (f.items or "")]
```

### Financial Reporting Timeline
```python
# Track quarterly reporting
quarterly_reports = filings.filter(form="10-Q", amendments=False)
for filing in quarterly_reports.latest(4):
    print(f"Q{filing.filing_date[5:7]} {filing.filing_date[:4]}: {filing.report_date}")

# Compare filing vs report dates
for filing in quarterly_reports.head(5):
    filing_date = filing.filing_date
    report_date = filing.report_date
    days_diff = (pd.to_datetime(filing_date) - pd.to_datetime(report_date)).days
    print(f"Filing delay: {days_diff} days")
```


## Performance Considerations

- **Entity Context Preservation**: All operations maintain CIK and company name
- **PyArrow Backend**: Efficient filtering and selection operations
- **Lazy Evaluation**: Filing content loaded only when accessed
- **Enhanced Metadata**: Additional fields available without extra API calls
- **Pagination**: Large filing collections handled efficiently

## Integration with Entity Package

### Company Objects
```python
# EntityFilings integrates seamlessly with Entity objects
company = Entity("AAPL")
filings = company.get_filings()               # Returns EntityFilings
latest_filing = filings.latest()             # Returns EntityFiling

# Convert back to company context
entity = latest_filing.get_entity()          # Get parent Entity
```

## Error Handling

EntityFilings handles various scenarios gracefully:

- **Empty Results**: Returns empty EntityFilings with `empty=True`
- **Invalid Indices**: Raises IndexError with helpful message
- **Missing Metadata**: Handles None values appropriately
- **Pagination Boundaries**: Warns when at start/end of data

## Backward Compatibility

For backward compatibility, the following aliases are available:
- `CompanyFilings` → `EntityFilings`
- `CompanyFiling` → `EntityFiling`
- `CompanyFacts` → `EntityFacts`

This allows existing code to continue working while transitioning to the new entity-focused naming.

The EntityFilings class provides a specialized, entity-aware interface for working with SEC filing collections, making it ideal for company-specific financial analysis and research workflows.