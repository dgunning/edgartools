# Filings Class Documentation

## Overview

The `Filings` class is a powerful container for SEC filing data that provides comprehensive functionality for filtering, searching, pagination, and data manipulation. It's built on PyArrow tables for efficient processing of large datasets and offers an intuitive interface for working with collections of SEC filings.

## Getting Filings

```python
filings = get_filings()
```
- **Parameters**: 
  - `year`: Year of filings (optional)
  - `quarter`: Quarter of filings (optional)
  - `amendments`: Include amended filings (default: True)
  - `ticker`: Company ticker symbol (optional)
  - `filing_date`: Date or date range for filtering (optional)

## Core Properties

| Property | Type | Description |
|----------|------|-------------|
| `data` | pa.Table | PyArrow table with filing information |
| `date_range` | Tuple[str, str] | Start and end dates of filings |
| `start_date` | str | Earliest filing date in collection |
| `end_date` | str | Latest filing date in collection |
| `empty` | bool | True if collection contains no filings |
| `summary` | str | Description of current page/total filings |

## Data Access & Conversion

### DataFrame Conversion
```python
# Convert to pandas DataFrame
df = filings.to_pandas()                    # All columns
df = filings.to_pandas('form', 'company')   # Specific columns
```

### Individual Filing Access
```python
# Get filing by index
filing = filings.get_filing_at(0)          # First filing
filing = filings[0]                        # Alternative syntax

# Get filing by accession number
filing = filings.get("0000320193-23-000077")

# Get filing by index or accession
filing = filings.get(5)                    # By index
filing = filings.get("0000320193-23-000077")  # By accession
```

### Export & Persistence
```python
# Save as Parquet file
filings.save_parquet("filings_data.parquet")
filings.save("filings_data.parquet")      # Alternative

# Convert to dictionary
data_dict = filings.to_dict(max_rows=1000)
```

## Filtering & Search

### Form-based Filtering
```python
# Single form type
filings.filter(form="10-K")
filings.filter(form="8-K")

# Multiple form types
filings.filter(form=["10-K", "10-Q"])
filings.filter(form=["8-K", "DEF 14A"])

# Include/exclude amendments
filings.filter(form="10-K", amendments=True)   # Include amendments
filings.filter(form="10-K", amendments=False)  # Exclude amendments
```

### Date Filtering
```python
# Specific date
filings.filter(date="2023-06-15")
filings.filter(filing_date="2023-06-15")     # Alternative

# Date ranges
filings.filter(date="2023-01-01:2023-03-31") # Between dates
filings.filter(date="2023-01-01:")           # From date onwards
filings.filter(date=":2023-03-31")           # Up to date
```

### Company-based Filtering
```python
# By CIK (Central Index Key)
filings.filter(cik=320193)                   # Single CIK
filings.filter(cik=[320193, 789019])         # Multiple CIKs

# By ticker symbol
filings.filter(ticker="AAPL")
filings.filter(ticker=["AAPL", "MSFT"])

# By exchange
filings.filter(exchange="NASDAQ")
filings.filter(exchange=["NYSE", "NASDAQ"])

# By accession number
filings.filter(accession_number="0000320193-23-000077")
```

### Company Search
```python
# Search for company and filter
apple_filings = filings.find("Apple")
microsoft_filings = filings.find("Microsoft Corporation")
```

### Combined Filtering
```python
# Complex filtering example
filtered = filings.filter(
    form=["10-K", "10-Q"],
    date="2023-01-01:2023-12-31",
    ticker=["AAPL", "MSFT", "GOOGL"],
    amendments=False
)
```

## Data Selection & Sampling

### Latest Filings
```python
# Get most recent filings
latest_filing = filings.latest()           # Most recent (default n=1)
latest_five = filings.latest(5)            # Most recent 5
```

### Head & Tail
```python
# Get first/last n filings
first_ten = filings.head(10)               # First 10 filings
last_ten = filings.tail(10)                # Last 10 filings
```

### Random Sampling
```python
# Get random sample
sample = filings.sample(20)                # Random 20 filings
```

## Pagination

### Navigation
```python
# Navigate through pages
current_page = filings.current()           # Current page info
next_page = filings.next()                 # Next page
prev_page = filings.previous()             # Previous page
```

### Page Information
```python
# Check pagination status
print(filings.summary)                     # "Page 1 of 50 (total: 12,543 filings)"
is_empty = filings.empty                   # Check if no results
```

## File Operations

### Download Filings
```python
# Download all filings in collection
filings.download()                         # Download to default directory
filings.download("./my_filings/")          # Download to specific directory
```

## Integration with Other Classes

### Filing Objects
```python
# Each item returns a Filing object
for filing in filings:
    print(f"Form: {filing.form}")
    print(f"Company: {filing.company}")
    print(f"Date: {filing.filing_date}")
    
    # Access filing content
    html_content = filing.html()
    attachments = filing.attachments
    xbrl_data = filing.xbrl()
```

### Company Integration
```python
# Convert filing to company context
filing = filings[0]
company = filing.get_entity()              # Get Company object
company_filing = filing.as_company_filing() # Enhanced filing with company data
```

## Rich Console Display

The Filings class provides formatted console output showing:
- Filing table with Form, CIK, Ticker, Company, Filing Date, Accession Number
- Pagination information
- Navigation hints

```python
# Display in console
print(filings)                             # Rich formatted table
filings.view()                             # Alternative display method
```

## Common Usage Patterns

### Quarterly Filing Analysis
```python
# Get all 10-K filings for 2023
annual_reports = get_filings(2023).filter(form="10-K", amendments=False)

# Find latest 10-Q for major tech companies
tech_quarterlies = get_filings(2023, 4).filter(
    form="10-Q",
    ticker=["AAPL", "MSFT", "GOOGL", "TSLA"]
).latest(4)
```

### Company-Specific Research
```python
# Get all Apple filings from Q1 2023
apple_filings = get_filings(2023, 1).find("Apple Inc")

# Filter for specific forms
apple_major_filings = apple_filings.filter(
    form=["10-K", "10-Q", "8-K"],
    amendments=False
)
```

### Event-Driven Analysis
```python
# Find 8-K filings around specific dates
event_filings = get_filings(2023, 2).filter(
    form="8-K",
    date="2023-02-01:2023-02-28"
)

# Sample for analysis
sample_events = event_filings.sample(50)
```

### Bulk Data Processing
```python
# Get large dataset and save for later
all_2023_filings = get_filings(2023)
all_2023_filings.save_parquet("2023_filings.parquet")

# Convert to pandas for analysis
df = all_2023_filings.to_pandas(['form', 'company', 'filing_date'])
```

## Performance Considerations

- **PyArrow Backend**: Efficient columnar data processing
- **Lazy Evaluation**: Filters are applied efficiently without loading full documents
- **Pagination**: Large datasets are handled through pagination
- **Caching**: Network requests are cached for improved performance
- **Parallel Processing**: Some operations support concurrent execution

## Error Handling

The Filings class handles various scenarios gracefully:

- **Empty Results**: Returns empty Filings object with `empty=True`
- **Invalid Filters**: Raises informative ValueError with guidance
- **Network Issues**: Propagates HTTP errors with context
- **Data Type Mismatches**: Automatic type conversion where possible

## Method Chaining

Most filtering and selection methods return new Filings objects, enabling method chaining:

```python
# Chain multiple operations
result = (filings
    .filter(form=["10-K", "10-Q"])
    .filter(date="2023-01-01:2023-06-30")
    .filter(amendments=False)
    .latest(10))
```

## Schema Information

The underlying PyArrow table contains these key columns:
- `form`: SEC form type
- `cik`: Company Central Index Key
- `ticker`: Stock ticker symbol
- `company`: Company name
- `filing_date`: Date of filing
- `accession_number`: Unique SEC identifier
- Additional metadata columns for enhanced functionality

This comprehensive API makes the Filings class the primary interface for working with collections of SEC filing data in edgartools, providing both power and ease of use for financial data analysis.