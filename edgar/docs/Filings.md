# Filings

Efficient container for SEC filing collections with filtering, search, and pagination.

## Quick Start

```python
from edgar import get_filings, get_current_filings

# Historical filings (quarterly indexes)
filings = get_filings(2024, 1)
filtered = filings.filter(form="10-K")
latest = filtered.latest()

# Today's filings (real-time)
current = get_current_filings(form="8-K")

# Navigate
first_10 = filings.head(10)
filing = filings[0]
```

## Getting Filings

### get_filings()

Get historical filings from quarterly indexes.

```python
def get_filings(
    year: int | List[int] = None,       # Calendar year (NOT fiscal)
    quarter: int | List[int] = None,    # Calendar quarter (1-4)
    form: str | List[str] = None,       # Form type(s)
    amendments: bool = True,            # Include amendments
    filing_date: str = None             # Date filter
) -> Filings
```

**Important:** Year and quarter are **calendar year/quarter when filed**, not fiscal year.

**Examples:**

```python
# All filings for Q1 2024
filings = get_filings(2024, 1)

# 10-K filings for 2023
filings = get_filings(2023, form="10-K")

# Multiple quarters
filings = get_filings(2024, [1, 2])

# Multiple years
filings = get_filings([2023, 2024], form="10-Q")

# Date range
filings = get_filings(2024, filing_date="2024-01-15:2024-02-15")

# Exclude amendments
filings = get_filings(2024, form="10-K", amendments=False)
```

**Data freshness:** Uses quarterly indexes updated daily but typically lag by 1 business day. For today's filings, use `get_current_filings()`.

### get_current_filings()

Get today's filings in real-time (updated every few minutes).

```python
def get_current_filings(
    form: str = '',           # Form type to filter
    owner: str = 'include',   # 'include', 'exclude', or 'only'
    page_size: int = 40       # Filings per page (or None for all)
) -> CurrentFilings
```

**Examples:**

```python
# First page of today's 8-K filings
current = get_current_filings(form="8-K")

# All current NT 10-Q filings (all pages)
all_current = get_current_filings(form="NT 10-Q", page_size=None)

# First 100 current filings
current = get_current_filings(page_size=100)

# Exclude insider filings
current = get_current_filings(owner='exclude')
```

**Use when you need:**
- Today's filings
- Real-time monitoring
- Latest filings by acceptance time

### From Company

```python
from edgar import Company

company = Company("AAPL")
filings = company.get_filings(form="10-K")
```

## Properties

| Property | Type | Description |
|----------|------|-------------|
| `data` | pa.Table | PyArrow table with filing data |
| `date_range` | Tuple[datetime, datetime] | Start and end dates |
| `start_date` | str | Earliest filing date |
| `end_date` | str | Latest filing date |
| `empty` | bool | True if no filings |
| `summary` | str | Page and total count description |

## Methods

### Filtering

#### filter()

Filter filings by multiple criteria.

```python
def filter(
    *,
    form: str | List[str] = None,
    amendments: bool = None,
    filing_date: str = None,
    date: str = None,                    # Alias for filing_date
    cik: int | str | List = None,
    exchange: str | List[str] = None,
    ticker: str | List[str] = None,
    accession_number: str | List[str] = None
) -> Filings
```

**Examples:**

```python
# Single form
filings.filter(form="10-K")

# Multiple forms
filings.filter(form=["10-K", "10-Q"])

# Specific date
filings.filter(date="2024-01-15")

# Date range
filings.filter(date="2024-01-01:2024-03-31")

# From date onwards
filings.filter(date="2024-01-01:")

# Up to date
filings.filter(date=":2024-03-31")

# By CIK
filings.filter(cik=320193)
filings.filter(cik=[320193, 789019])

# By ticker
filings.filter(ticker="AAPL")
filings.filter(ticker=["AAPL", "MSFT"])

# By exchange
filings.filter(exchange="NASDAQ")
filings.filter(exchange=["NYSE", "NASDAQ"])

# Combined filters
filings.filter(
    form=["10-K", "10-Q"],
    date="2024-01-01:2024-12-31",
    ticker=["AAPL", "MSFT"],
    amendments=False
)
```

**Note:** Filter methods return new Filings objects and can be chained.

#### find()

Search for company and filter.

```python
# Find company filings
apple_filings = filings.find("Apple")
tesla_filings = filings.find("Tesla Inc")
```

### Selection

#### latest(n=1)

Get most recent filing(s).

```python
# Most recent filing
latest = filings.latest()

# Most recent 5 filings
latest_five = filings.latest(5)
```

Returns single Filing if n=1, otherwise Filings.

#### head(n)

Get first n filings.

```python
first_ten = filings.head(10)
```

#### tail(n)

Get last n filings.

```python
last_ten = filings.tail(10)
```

#### sample(n)

Get random sample of n filings.

```python
sample = filings.sample(20)
```

### Access

#### get(index_or_accession_number)

Get filing by index or accession number.

```python
# By index
filing = filings.get(0)
filing = filings[0]         # Alternative

# By accession number
filing = filings.get("0000320193-23-000106")
```

#### get_filing_at(index, enrich=True)

Get filing at specific index.

```python
filing = filings.get_filing_at(5)
```

**Parameters:**
- `enrich` - Include related entity information

### Pagination

#### next()

Navigate to next page.

```python
next_page = filings.next()
if next_page is None:
    print("End of data")
```

Returns None when no more pages.

#### previous()

Navigate to previous page.

```python
prev_page = filings.previous()
if prev_page is None:
    print("At first page")
```

Returns None when at first page.

#### current()

Get current page (returns self).

```python
current = filings.current()
```

### Export & Persistence

#### to_pandas(*columns)

Convert to pandas DataFrame.

```python
# All columns
df = filings.to_pandas()

# Specific columns
df = filings.to_pandas('form', 'company', 'filing_date')
```

#### save(location) / save_parquet(location)

Save as Parquet file.

```python
filings.save("filings.parquet")
filings.save_parquet("filings.parquet")
```

#### to_dict(max_rows=1000)

Convert to dictionary (limited rows).

```python
data = filings.to_dict(max_rows=500)
```

#### to_context(detail='standard')

Get AI-optimized text representation.

```python
context = filings.to_context('standard')
print(context)
```

**Detail levels:**
- `'minimal'` - Basic collection info (~100 tokens)
- `'standard'` - Adds sample entries (~250 tokens)
- `'full'` - Adds form breakdown (~400 tokens)

### Bulk Operations

#### download()

Download all filings in collection.

```python
def download(
    data_directory: str = None,
    compress: bool = True,
    compression_level: int = 6,
    upload_to_cloud: bool = False,
    disable_progress: bool = False
)
```

**Examples:**

```python
# Download to default directory
filings.download()

# Download to specific directory
filings.download("./my_filings/")

# Without compression
filings.download(compress=False)

# Custom compression
filings.download(compress=True, compression_level=9)
```

## Iteration

```python
# Iterate over all filings
for filing in filings:
    print(f"{filing.form} - {filing.company}")

# With index
for i, filing in enumerate(filings):
    print(f"{i}: {filing.accession_no}")
```

## Common Workflows

### Filter by Form and Date

```python
# Get 10-K filings from Q1 2024
filings = get_filings(2024, 1)
tenk = filings.filter(form="10-K", amendments=False)

# Get latest
latest = tenk.latest()
print(latest.company)
```

### Company-Specific Analysis

```python
# Find all Apple filings in quarter
filings = get_filings(2024, 1)
apple = filings.find("Apple Inc")

# Filter for major forms
major = apple.filter(form=["10-K", "10-Q", "8-K"])
```

### Monitor Recent Filings

```python
# Get today's 8-K filings
current = get_current_filings(form="8-K")

# Check for specific company
company_filings = current.filter(ticker="AAPL")
if not company_filings.empty:
    print(f"Apple filed {len(company_filings)} 8-Ks today")
```

### Bulk Analysis

```python
# Get year of filings
filings = get_filings(2024)
tenk = filings.filter(form="10-K", amendments=False)

# Convert to DataFrame for analysis
df = tenk.to_pandas('company', 'cik', 'filing_date')

# Group by month
df['month'] = pd.to_datetime(df['filing_date']).dt.month
monthly = df.groupby('month').size()
print(monthly)
```

### Download for Offline Analysis

```python
# Get specific filings
filings = get_filings(2024, 1, form="10-K")
aapl = filings.filter(ticker="AAPL")

# Download with compression
aapl.download(compress=True, compression_level=9)
```

### Page Through Results

```python
# Get large dataset
filings = get_filings(2024)

# Process first page
for filing in filings:
    process(filing)

# Next page
filings = filings.next()
if filings:
    for filing in filings:
        process(filing)
```

## Method Chaining

Filtering and selection methods return new Filings objects, enabling chains:

```python
result = (get_filings(2024, [1, 2])
    .filter(form=["10-K", "10-Q"])
    .filter(date="2024-01-01:2024-06-30")
    .filter(amendments=False)
    .filter(ticker=["AAPL", "MSFT", "GOOGL"])
    .latest(10))
```

## Performance Tips

### Use Specific Filters

```python
# Good - filter early
filings = get_filings(2024, 1, form="10-K")

# Less efficient - filter after loading
filings = get_filings(2024, 1).filter(form="10-K")
```

### Limit Data Loaded

```python
# Get only what you need
filings = get_filings(2024, 1).filter(form="10-K").head(10)

# Not: filings = get_filings(2024, 1).filter(form="10-K") then iterate 10
```

### Cache Large Datasets

```python
# Save for reuse
filings = get_filings(2024)
filings.save("filings_2024.parquet")

# Load later (fast)
import pyarrow.parquet as pq
from edgar import Filings
data = pq.read_table("filings_2024.parquet")
filings = Filings(data)
```

### Use PyArrow Directly

```python
# Access PyArrow table for fast operations
import pyarrow.compute as pc

# Fast filtering
mask = pc.equal(filings.data['form'], '10-K')
tenk_data = filings.data.filter(mask)
```

## Error Handling

### Empty Results

```python
filings = get_filings(2024, 1, form="RARE-FORM")
if filings.empty:
    print("No filings found")
```

### Invalid Date Format

```python
try:
    filings = get_filings(2024, filing_date="invalid")
except ValueError as e:
    print(f"Invalid date: {e}")
```

### No More Pages

```python
next_page = filings.next()
if next_page is None:
    print("Reached end of data")
```

## Data Freshness

### Quarterly Indexes (get_filings)

- Updated daily but typically lag 1 business day
- Best for historical analysis
- Efficient for bulk operations

### Current Filings (get_current_filings)

- Updated every few minutes
- Best for today's filings
- Real-time monitoring

**When to use each:**

```python
# Historical analysis (yesterday and earlier)
historical = get_filings(2024, 1, form="10-K")

# Today's filings
today = get_current_filings(form="10-K")
```

## Schema

The underlying PyArrow table contains:

| Column | Type | Description |
|--------|------|-------------|
| `form` | string | SEC form type |
| `company` | string | Company name |
| `cik` | int32 | Central Index Key |
| `filing_date` | date32 | Filing date |
| `accession_number` | string | SEC accession number |

Additional columns may be present in CurrentFilings:

| Column | Type | Description |
|--------|------|-------------|
| `accepted` | timestamp | Acceptance timestamp |

## See Also

- `filings.docs` - Display this documentation in terminal
- [Filing](Filing.md) - Working with individual filings
- [Company](../entity/docs/Company.md) - Company-level filing access
- [get_current_filings](../current_filings.md) - Real-time filings
