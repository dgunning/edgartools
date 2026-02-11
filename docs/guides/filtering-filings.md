# Filter SEC Filings — By Form Type, Date, Ticker, Exchange, and CIK

Learn how to filter SEC filings by multiple criteria to find exactly what you need.

## Two Ways to Filter

You can filter filings in two ways:

1. **Filter while getting** - Use `get_filings()` parameters to filter from all SEC filings
2. **Filter after getting** - Use `.filter()` method to refine an existing `Filings` collection

Both approaches work similarly, but filtering while getting is more efficient when you know the criteria upfront.

## Filter While Getting Filings

### Filter by Form Type

Get filings of a specific SEC form:

```python
from edgar import get_filings

# Single form type
tenk = get_filings(2024, 1, form="10-K")

# Multiple form types
financial = get_filings(2024, 1, form=["10-K", "10-Q"])

# Proxy statements
proxies = get_filings(2024, 1, form="DEF 14A")
```

### Include or Exclude Amendments

By default, amendments are included. Exclude them with `amendments=False`:

```python
# Include amendments (default)
all_10k = get_filings(2024, 1, form="10-K", amendments=True)

# Exclude amendments
original_only = get_filings(2024, 1, form="10-K", amendments=False)
```

### Filter by Date

#### Specific Date

```python
# Filings on a specific date
jan_15 = get_filings(2024, 1, filing_date="2024-01-15")
```

#### Date Range

```python
# Filings between two dates
jan_filings = get_filings(2024, 1, filing_date="2024-01-01:2024-01-31")

# Q1 2024
q1 = get_filings(2024, filing_date="2024-01-01:2024-03-31")
```

#### Open-Ended Ranges

```python
# From date onwards
recent = get_filings(2024, 1, filing_date="2024-01-15:")

# Up to a date
older = get_filings(2024, 1, filing_date=":2024-01-15")
```

### Combine Filters

```python
# 10-K filings from January 2024, no amendments
filings = get_filings(
    year=2024,
    quarter=1,
    form="10-K",
    filing_date="2024-01-01:2024-01-31",
    amendments=False
)
```

## Filter After Getting Filings

Use the `.filter()` method to refine an existing collection:

### Filter by Form

```python
filings = get_filings(2024, 1)

# Filter to 10-K only
tenk = filings.filter(form="10-K")

# Multiple forms
financial = filings.filter(form=["10-K", "10-Q"])
```

### Filter by Date

```python
filings = get_filings(2024, 1)

# Specific date
jan_1 = filings.filter(date="2024-01-01")

# Date range
jan_range = filings.filter(date="2024-01-01:2024-01-31")

# From date onwards
recent = filings.filter(date="2024-01-15:")
```

### Filter by Company (CIK)

```python
filings = get_filings(2024, 1)

# Filter by CIK (integer)
apple = filings.filter(cik=320193)

# Filter by CIK (string)
apple = filings.filter(cik="0000320193")

# Multiple companies
faang = filings.filter(cik=[320193, 1318605, 1652044])
```

### Filter by Ticker

```python
filings = get_filings(2024, 1)

# Single ticker
apple = filings.filter(ticker="AAPL")

# Multiple tickers
tech = filings.filter(ticker=["AAPL", "MSFT", "GOOGL", "AMZN"])
```

**Note:** Ticker filtering performs a CIK lookup first. If you know the CIK, use it directly for better performance.

### Filter by Exchange

```python
filings = get_filings(2024, 1)

# Single exchange
nasdaq = filings.filter(exchange="NASDAQ")

# Multiple exchanges
major = filings.filter(exchange=["NASDAQ", "NYSE"])
```

**Available exchanges:**
- NASDAQ
- NYSE
- CBOE
- OTC

### Filter by Accession Number

```python
filings = get_filings(2024, 1)

# Single accession number
filing = filings.filter(accession_number="0000320193-24-000001")

# Multiple accession numbers
specific = filings.filter(accession_number=[
    "0000320193-24-000001",
    "0001318605-24-000001"
])
```

### Filter Amendments

```python
filings = get_filings(2024, 1, form="10-K")

# Exclude amendments
original_only = filings.filter(amendments=False)

# Only amendments
amendments_only = filings.filter(amendments=True)
```

## Chain Filters

Build complex queries by chaining multiple filters:

```python
from edgar import get_filings

# Start with all Q1 2024 filings
filings = get_filings(2024, 1)

# Chain filters for specificity
result = (filings
    .filter(form="10-K")
    .filter(exchange="NASDAQ")
    .filter(date="2024-01-01:2024-01-31")
    .filter(amendments=False))

print(f"Found {len(result)} filings matching all criteria")
```

Alternatively, combine multiple criteria in one filter:

```python
result = filings.filter(
    form="10-K",
    exchange="NASDAQ",
    date="2024-01-01:2024-01-31",
    amendments=False
)
```

## Use head, tail, and sample

Limit results after filtering:

### head()

Get the first n filings:

```python
filings = get_filings(2024, 1, form="10-K")

# Get first 10
first_10 = filings.head(10)
```

### tail()

Get the last n filings:

```python
# Get last 10
last_10 = filings.tail(10)
```

### sample()

Get a random sample:

```python
# Get random sample of 10
random_10 = filings.sample(10)
```

### latest()

Get most recent filings:

```python
# Get latest single filing
latest = filings.latest()

# Get latest 20 filings
latest_20 = filings.latest(20)
```

## Search by Company Name

Use `.find()` to search by company name:

```python
filings = get_filings(2024, 1)

# Find companies with "Technology" in name
tech = filings.find("Technology")

# Find specific company
apple = filings.find("Apple")

# Case-insensitive partial match
results = filings.find("tesla")
```

## Common Filtering Patterns

### Get Latest 10-K for NASDAQ Companies

```python
from edgar import get_filings

filings = get_filings(2024, 1, form="10-K")
nasdaq = filings.filter(exchange="NASDAQ")
latest_20 = nasdaq.latest(20)

for filing in latest_20:
    print(f"{filing.company}: {filing.filing_date}")
```

### Get All 8-K Filings for Specific Companies

```python
filings = get_filings(2024, 1, form="8-K")

# Filter to FAANG companies
faang = filings.filter(ticker=["AAPL", "AMZN", "NFLX", "GOOGL", "META"])

print(f"Found {len(faang)} 8-K filings from FAANG")
```

### Get Financial Reports from Tech Companies in January

```python
# Get all Q1 filings
filings = get_filings(2024, 1)

# Filter to financial reports
financial = filings.filter(form=["10-K", "10-Q"])

# Filter to NASDAQ (proxy for tech-heavy)
nasdaq = financial.filter(exchange="NASDAQ")

# Filter to January only
jan = nasdaq.filter(date="2024-01-01:2024-01-31")

print(f"Found {len(jan)} NASDAQ financial reports in January")
```

### Get Original 10-K Filings (No Amendments)

```python
filings = get_filings(2024, 1, form="10-K", amendments=False)

# Or filter an existing collection
all_10k = get_filings(2024, 1, form="10-K")
original = all_10k.filter(amendments=False)
```

### Get Filings by Year and Quarter Combinations

```python
# Single year, single quarter
q1_2024 = get_filings(2024, 1)

# Single year, multiple quarters
h1_2024 = get_filings(2024, [1, 2])

# Multiple years, single quarter
q4_multi_year = get_filings([2022, 2023, 2024], 4)

# Multiple years, all quarters
multi_year = get_filings([2022, 2023, 2024])

# Year range
range_2020_2024 = get_filings(range(2020, 2025))  # 2020-2024
```

## Export Filtered Results

### To DataFrame

```python
filings = get_filings(2024, 1, form="10-K")
nasdaq = filings.filter(exchange="NASDAQ")

# Convert to DataFrame
df = nasdaq.to_pandas()

# Or select specific columns
df = nasdaq.to_pandas('company', 'filing_date', 'cik', 'accession_no')

print(df.head())
```

### To Parquet

```python
filings = get_filings(2024, 1, form="10-K")
nasdaq = filings.filter(exchange="NASDAQ")

# Save as parquet
nasdaq.save_parquet("nasdaq_10k_q1_2024.parquet")
```

## Performance Tips

### Filter Early

**Efficient:**
```python
# Filter using get_filings parameters
filings = get_filings(2024, 1, form="10-K")
```

**Less Efficient:**
```python
# Get everything then filter
filings = get_filings(2024, 1).filter(form="10-K")
```

### Use CIK Instead of Ticker

**Efficient:**
```python
# Filter by CIK (direct lookup)
filings = filings.filter(cik=320193)
```

**Less Efficient:**
```python
# Filter by ticker (requires CIK lookup first)
filings = filings.filter(ticker="AAPL")
```

### Limit Results Early

```python
# Get only what you need
filings = get_filings(2024, 1, form="10-K").head(50)

# Better than processing all then limiting
all_filings = get_filings(2024, 1, form="10-K")
# ... process all ...
limited = all_filings.head(50)
```

## Error Handling

```python
from edgar import get_filings

try:
    filings = get_filings(2024, 1, form="10-K")

    if filings.empty:
        print("No filings found")
    else:
        # Filter
        nasdaq = filings.filter(exchange="NASDAQ")

        if nasdaq.empty:
            print("No NASDAQ filings")
        else:
            print(f"Found {len(nasdaq)} NASDAQ 10-K filings")

except Exception as e:
    print(f"Error: {e}")
```

## See Also

- **[Filings API Reference](../api/filings.md)** - Complete Filings class documentation
- **[Filing API Reference](../api/filing.md)** - Individual filing operations
- **[Search Filings Guide](searching-filings.md)** - Finding specific filings
- **[Current Filings Guide](current-filings.md)** - Access today's filings
- **[Working with Filings](working-with-filing.md)** - Extract data from filings
