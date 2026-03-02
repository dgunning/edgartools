---
description: Search SEC EDGAR filings by form type, date range, company, and keywords.
---

# Search and Filter SEC Filings by Form, Date, and Company

Learn how to find the exact SEC filings you need using various search criteria and filtering methods.

## Prerequisites

- Understanding of SEC filing types (10-K, 10-Q, 8-K, etc.)

## Basic Filing Search

### Get Recent Filings

Start with the most recent filings across all companies:

```python
from edgar import get_filings

# Get the 50 most recent filings
recent_filings = get_filings()

# Display basic information
for filing in recent_filings[:5]:
    print(f"{filing.form}: {filing.company_name} ({filing.filing_date})")
```

**Output:**
```plaintext
10-Q: Apple Inc. (2024-05-02)
8-K: Microsoft Corporation (2024-05-01)
10-K: Amazon.com Inc (2024-04-30)
13F-HR: Berkshire Hathaway Inc (2024-04-29)
4: Tesla Inc (2024-04-28)
```

### Search by Filing Type

Find specific types of SEC forms:

```python
# Get recent 10-K annual reports
annual_reports = get_filings(form="10-K").head(20)

# Get multiple form types
quarterly_and_annual = get_filings(form=["10-K", "10-Q"])

# Exclude amendments (filings ending in /A)
original_filings = get_filings(form="10-K", amendments=False).head(20)

print(f"Found {len(annual_reports)} annual reports")
```

## Search by Date Range

### Specific Date
```python
# Get all filings from a specific date
filings_jan_1 = get_filings(filing_date="2024-01-01")

print(f"Found {len(filings_jan_1)} filings on 2024-01-01")
```

### Date Ranges
```python
# Get filings from a date range
q1_filings = get_filings(filing_date="2024-01-01:2024-03-31")

# Get filings after a specific date
recent_filings = get_filings(filing_date="2024-01-01:")

# Get filings before a specific date
older_filings = get_filings(filing_date=":2023-12-31")

print(f"Q1 2024 filings: {len(q1_filings)}")
```

### Year and Quarter Search

!!! note "Calendar Year vs Fiscal Year"

    The `year` and `quarter` parameters refer to **when the filing was submitted to the SEC** (calendar year),
    **not** the fiscal year the filing covers.

    For example, a company with a fiscal year ending March 31, 2024 would file their annual 10-K in
    May or June 2024. Using `get_filings(2024)` would find this filing because it was **filed** in
    calendar year 2024, even though the 10-K covers fiscal year 2024.

    To find filings by fiscal year, use the company's `get_filings()` method and filter by the
    filing's fiscal period information available in the XBRL data.

```python
# Get filings for entire calendar year (by filing date)
filings_2023 = get_filings(2023)

# Get filings for specific calendar quarter
q4_2023 = get_filings(2023, 4)

# Get multiple quarters
q3_q4_2023 = get_filings(2023, [3, 4])

# Get multiple years
multi_year = get_filings([2022, 2023])

# Get range of years (excludes end year)
decade_filings = get_filings(range(2010, 2021))

print(f"2023 filings: {len(filings_2023)}")
print(f"Q4 2023 filings: {len(q4_2023)}")
```

## Company-Specific Filing Search

### Get All Company Filings
```python
from edgar import Company

# Get all filings for a company
apple = Company("AAPL")
all_apple_filings = apple.get_filings()

print(f"Apple has {len(all_apple_filings)} total filings")
```

### Filter Company Filings
```python
# Get specific form types for a company
apple_10k = apple.get_filings(form="10-K")
apple_quarterly = apple.get_filings(form=["10-Q", "10-K"])

# Get XBRL filings only
apple_xbrl = apple.get_filings(is_xbrl=True)

# Get inline XBRL filings
apple_ixbrl = apple.get_filings(is_inline_xbrl=True)

print(f"Apple 10-K filings: {len(apple_10k)}")
print(f"Apple XBRL filings: {len(apple_xbrl)}")
```

### Get Latest Filing
```python
# Get the most recent filing of a specific type
latest_10k = apple.get_filings(form="10-K").latest()
latest_10q = apple.get_filings(form="10-Q").latest()

print(f"Latest 10-K: {latest_10k.filing_date}")
print(f"Latest 10-Q: {latest_10q.filing_date}")

# Chain the calls for conciseness
latest_annual = Company("MSFT").get_filings(form="10-K").latest()
```

## Advanced Filtering

### Filter by Multiple Criteria
```python
# Get Apple's 10-K filings from 2023 that are XBRL
apple_filtered = apple.get_filings(
    form="10-K",
    is_xbrl=True
).filter(filing_date="2023-01-01:2023-12-31")

print(f"Filtered results: {len(apple_filtered)}")
```

### Filter by Accession Number
```python
# Find specific filing by accession number
specific_filing = apple.get_filings(
    accession_number="0000320193-23-000106"
)

print(f"Found filing: {specific_filing[0].form}")
```

### Filter by File Number
```python
# Filter by SEC file number
file_filtered = apple.get_filings(
    file_number="001-36743"
)

print(f"Filings with file number: {len(file_filtered)}")
```

## Cross-Company Search

### Search by Industry
```python
# Get recent filings and filter by company characteristics
all_filings = get_filings()

# Filter for technology companies (requires loading each company)
tech_filings = []
for filing in all_filings[:100]:  # Limit for performance
    try:
        company = Company(filing.cik)
        if "software" in company.industry.lower() or "computer" in company.industry.lower():
            tech_filings.append(filing)
    except:
        continue

print(f"Found {len(tech_filings)} filings from tech companies")
```

### Search by Exchange
```python
# Filter existing filings by exchange
nasdaq_filings = all_filings.filter(exchange="NASDAQ")
nyse_filings = all_filings.filter(exchange="NYSE")

print(f"NASDAQ filings: {len(nasdaq_filings)}")
print(f"NYSE filings: {len(nyse_filings)}")
```

### Search by Ticker List
```python
# Get filings for multiple specific companies
tickers = ["AAPL", "MSFT", "GOOGL", "AMZN"]
ticker_filings = all_filings.filter(ticker=tickers)

print(f"Filings from specified tickers: {len(ticker_filings)}")
```

## Specialized Filing Searches

### Insider Trading Filings
```python
# Get recent insider trading filings
insider_filings = get_filings(form=["3", "4", "5"])

print("Recent insider filings:")
for filing in insider_filings[:10]:
    print(f"  Form {filing.form}: {filing.company_name} ({filing.filing_date})")
```

### Fund Holdings (13F)
```python
# Get recent 13F filings (institutional investment managers)
fund_filings = get_filings(form="13F-HR")

print("Recent fund holdings filings:")
for filing in fund_filings:
    print(f"  {filing.company_name}: {filing.filing_date}")
```

### Material Events (8-K)
```python
# Get recent 8-K filings (material corporate events)
event_filings = get_filings(form="8-K")

print("Recent material events:")
for filing in event_filings[:10]:
    print(f"  {filing.company_name}: {filing.filing_date}")
```

### IPO and Registration Statements
```python
# Get S-1 filings (IPO registrations)
ipo_filings = get_filings(form="S-1")

print("Recent IPO filings:")
for filing in ipo_filings:
    print(f"  {filing.company_name}: {filing.filing_date}")
```

## Working with Search Results

### Subset and Sample
```python
filings = get_filings(form="10-K")

# Get first 10 results
first_ten = filings.head(10)

# Get last 10 results
last_ten = filings.tail(10)

# Get random sample of 5 results
random_sample = filings.sample(5)

print(f"Total: {len(filings)}, Sample: {len(random_sample)}")
```

### Convert to Pandas DataFrame
```python
import pandas as pd

# Convert filings to DataFrame for analysis
filings_df = filings.to_pandas()

# Analyze filing patterns
filing_counts = filings_df.groupby(['form', 'company_name']).size()
print("Filing counts by company and form:")
print(filing_counts.head(10))
```

### Access Underlying Data
```python
# Access the PyArrow table directly
import pyarrow as pa

filings = get_filings(form="10-K")
data_table: pa.Table = filings.data

# Convert to Pandas for advanced analysis
df = data_table.to_pandas()
print(f"Columns available: {df.columns.tolist()}")
```

## Performance Optimization

### Efficient Searching
```python
# More efficient: Use specific parameters in get_filings()
efficient = get_filings(form="10-K", filing_date="2023-01-01:")

# Less efficient: Get all then filter
inefficient = get_filings().filter(form="10-K").filter(filing_date="2023-01-01:")

print(f"Efficient approach found: {len(efficient)} filings")
```

### Caching Results
```python
# Store frequently used searches
apple = Company("AAPL")
apple_10k_cache = apple.get_filings(form="10-K")

# Reuse cached results for different analyses
recent_10k = apple_10k_cache.head(5)
oldest_10k = apple_10k_cache.tail(5)
```

## Error Handling

### Handle Missing Data
```python
try:
    filings = get_filings(form="INVALID-FORM")
    print(f"Found {len(filings)} filings")
except Exception as e:
    print(f"Error searching filings: {e}")
```

### Validate Search Results
```python
filings = get_filings(form="10-K", limit=10)

if len(filings) == 0:
    print("No filings found matching criteria")
else:
    print(f"Found {len(filings)} filings")
    # Verify first result
    first_filing = filings[0]
    print(f"First result: {first_filing.form} from {first_filing.company_name}")
```

## Common Search Patterns

### Earnings Season Analysis
```python
# Find quarterly reports filed in typical earnings periods
earnings_dates = [
    "2024-01-15:2024-02-15",  # Q4 earnings
    "2024-04-15:2024-05-15",  # Q1 earnings
    "2024-07-15:2024-08-15",  # Q2 earnings
    "2024-10-15:2024-11-15"   # Q3 earnings
]

earnings_filings = []
for date_range in earnings_dates:
    filings = get_filings(form="10-Q", filing_date=date_range)
    earnings_filings.extend(filings)

print(f"Found {len(earnings_filings)} earnings period filings")
```

### M&A Activity Monitoring
```python
# Look for 8-K filings that might indicate M&A activity
ma_filings = get_filings(form="8-K")

# Filter for potential M&A keywords (requires examining filing content)
potential_ma = []
for filing in ma_filings[:50]:  # Limit for performance
    try:
        text = filing.text()
        if any(keyword in text.lower() for keyword in 
               ['acquisition', 'merger', 'tender offer', 'purchase agreement']):
            potential_ma.append(filing)
    except:
        continue

print(f"Found {len(potential_ma)} potential M&A filings")
```

## Next Steps

Now that you can search for filings effectively, learn how to:

- **[Filter Filings by Date/Type](filtering-filings.md)** - Advanced filtering techniques
- **[Access Filing Attachments](filing-attachments.md)** - Get supporting documents

## Related Documentation

- **[Filing API Reference](../api/filing.md)** - Complete Filing class documentation
- **[Filings API Reference](../api/filings.md)** - Filings collection methods
- **[Working with Filings](working-with-filing.md)** - Original filing documentation