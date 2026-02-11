# Filings API Reference — Filter and Navigate SEC Filing Collections

The `Filings` class represents a collection of SEC filings with powerful filtering, navigation, and batch processing capabilities.

**Quick example:**
```python
from edgar import get_filings

# Get Q1 2024 10-K filings
filings = get_filings(2024, 1, form="10-K")
print(f"Found {len(filings)} filings")

# Filter to NASDAQ companies
nasdaq = filings.filter(exchange="NASDAQ")

# Get latest 10
latest = nasdaq.latest(10)

# Export to DataFrame
df = latest.to_pandas()
```

## Getting Filings

### get_filings()

```python
def get_filings(
    year: int | List[int] = None,
    quarter: int | List[int] = None,
    form: str | List[str] = None,
    amendments: bool = True,
    filing_date: str = None
) -> Filings
```

**Parameters:**
- `year` (int | List[int]): Calendar year(s) — NOT fiscal year
- `quarter` (int | List[int]): Calendar quarter(s) 1-4
- `form` (str | List[str]): Form type(s)
- `amendments` (bool): Include amendments (default: True)
- `filing_date` (str): Date filter (YYYY-MM-DD or YYYY-MM-DD:YYYY-MM-DD)

**Returns:** `Filings` collection

**Important:** There is **no `limit` parameter**. Use `.head(n)` or `.latest(n)` on the result to limit.

**Examples:**
```python
from edgar import get_filings

# Q1 2024 filings
filings = get_filings(2024, 1)

# All 2023 10-K filings
filings = get_filings(2023, form="10-K")

# Multiple years
filings = get_filings([2022, 2023, 2024])

# Multiple quarters
filings = get_filings(2024, [1, 2], form="10-Q")

# Date range
filings = get_filings(2024, 1, filing_date="2024-01-01:2024-01-31")

# Multiple forms
filings = get_filings(2024, 1, form=["10-K", "10-Q"])

# Exclude amendments
filings = get_filings(2024, 1, form="10-K", amendments=False)
```

## Core Properties

### Collection Information

| Property | Type | Description |
|----------|------|-------------|
| `empty` | bool | Whether collection contains any filings |
| `date_range` | Tuple[str, str] | (start_date, end_date) |
| `start_date` | str | Earliest filing date |
| `end_date` | str | Latest filing date |
| `summary` | str | Summary description of collection |

**Example:**
```python
if filings.empty:
    print("No filings found")
else:
    start, end = filings.date_range
    print(f"Filings from {start} to {end}")
    print(f"Total: {len(filings)}")
```

## Collection Operations

### Size and Access

#### len()
```python
len(filings) -> int
```
Number of filings in collection.

**Example:**
```python
print(f"Collection contains {len(filings)} filings")
```

#### Indexing
```python
filings[index] -> Filing
```
Access individual filings by index.

**Example:**
```python
first = filings[0]
last = filings[-1]

# Slicing works but returns list, not Filings
first_five = filings[:5]  # List of Filing objects
```

#### Iteration
```python
for filing in filings:
    ...
```
Iterate through collection.

**Example:**
```python
for filing in filings:
    print(f"{filing.form}: {filing.company} ({filing.filing_date})")
```

#### get()
```python
def get(self, index_or_accession_number: Union[int, str]) -> Filing
```
Get filing by index or accession number.

**Parameters:**
- `index_or_accession_number`: Integer index or accession number string

**Returns:** `Filing` object

**Example:**
```python
# By index
filing = filings.get(0)

# By accession number
filing = filings.get("0001234567-24-000001")
```

### Subset Operations

#### latest()
```python
def latest(self, n: int = 1) -> Union[Filing, Filings]
```
Get most recent filing(s).

**Parameters:**
- `n` (int): Number of filings (default: 1)

**Returns:**
- Single `Filing` if n=1
- `Filings` collection if n>1

**Example:**
```python
# Single latest filing
latest_filing = filings.latest()

# Latest 10 filings
latest_10 = filings.latest(10)
```

#### head()
```python
def head(self, n: int) -> Filings
```
Get first n filings.

**Example:**
```python
first_20 = filings.head(20)
```

#### tail()
```python
def tail(self, n: int) -> Filings
```
Get last n filings.

**Example:**
```python
last_20 = filings.tail(20)
```

#### sample()
```python
def sample(self, n: int) -> Filings
```
Get random sample of n filings.

**Example:**
```python
random_sample = filings.sample(10)
```

## Filtering and Search

### filter()
```python
def filter(
    self,
    *,
    form: Optional[Union[str, List[str]]] = None,
    amendments: bool = None,
    filing_date: Optional[str] = None,
    date: Optional[str] = None,
    cik: Union[int, str, List[Union[int, str]]] = None,
    exchange: Union[str, List[str]] = None,
    ticker: Union[str, List[str]] = None,
    accession_number: Union[str, List[str]] = None
) -> Filings
```

Filter collection by multiple criteria.

**Parameters:**
- `form`: Form type(s) — e.g., "10-K", ["10-K", "10-Q"]
- `amendments`: Include/exclude amendments
- `filing_date` / `date`: Date filter (YYYY-MM-DD or range)
- `cik`: Central Index Key(s)
- `exchange`: Exchange(s) — "NASDAQ", "NYSE", "CBOE", "OTC"
- `ticker`: Stock ticker(s)
- `accession_number`: Accession number(s)

**Returns:** Filtered `Filings` collection

**Examples:**

#### Filter by form
```python
# Single form
annual = filings.filter(form="10-K")

# Multiple forms
financial = filings.filter(form=["10-K", "10-Q"])

# Exclude amendments
original_only = filings.filter(form="10-K", amendments=False)
```

#### Filter by date
```python
# Specific date
jan_1 = filings.filter(date="2024-01-01")

# Date range
q1 = filings.filter(date="2024-01-01:2024-03-31")

# From date onwards
recent = filings.filter(date="2024-01-01:")

# Up to date
older = filings.filter(date=":2023-12-31")
```

#### Filter by company
```python
# By ticker
apple = filings.filter(ticker="AAPL")

# By CIK
apple = filings.filter(cik=320193)
apple = filings.filter(cik="0000320193")

# Multiple companies
faang = filings.filter(ticker=["AAPL", "MSFT", "GOOGL"])
```

#### Filter by exchange
```python
# Single exchange
nasdaq = filings.filter(exchange="NASDAQ")

# Multiple exchanges
major = filings.filter(exchange=["NASDAQ", "NYSE"])
```

#### Chain filters
```python
result = (filings
    .filter(form="10-K")
    .filter(exchange="NASDAQ")
    .filter(date="2024-01-01:")
    .latest(50))
```

### find()
```python
def find(self, company_search_str: str) -> Filings
```
Search for filings by company name.

**Parameters:**
- `company_search_str` (str): Company name search string

**Returns:** Matching `Filings` collection

**Example:**
```python
# Find technology companies
tech = filings.find("Technology")

# Find specific company
apple = filings.find("Apple")
```

## Navigation and Pagination

### current()
```python
def current(self) -> Filings
```
Get current page of filings.

**Returns:** Current `Filings` page

### next()
```python
def next(self) -> Optional[Filings]
```
Navigate to next page.

**Returns:** Next page `Filings` or None

**Example:**
```python
next_page = filings.next()
if next_page:
    print(f"Next page has {len(next_page)} filings")
```

### previous()
```python
def previous(self) -> Optional[Filings]
```
Navigate to previous page.

**Returns:** Previous page `Filings` or None

**Example:**
```python
prev_page = filings.previous()
if prev_page:
    print(f"Previous page has {len(prev_page)} filings")
```

## Data Export and Persistence

### to_pandas()
```python
def to_pandas(self, *columns: str) -> pd.DataFrame
```
Convert to pandas DataFrame.

**Parameters:**
- `*columns`: Specific columns to include (optional)

**Returns:** DataFrame with filing data

**Example:**
```python
# All columns
df = filings.to_pandas()
print(df.columns.tolist())

# Specific columns
df = filings.to_pandas('form', 'company', 'filing_date', 'cik')
print(df.head())
```

### save_parquet() / save()
```python
def save_parquet(self, location: str)
def save(self, location: str)  # Alias
```
Save collection as Parquet file.

**Parameters:**
- `location` (str): File path

**Example:**
```python
filings.save_parquet("my_filings.parquet")

# Load later
import pandas as pd
df = pd.read_parquet("my_filings.parquet")
```

### to_dict()
```python
def to_dict(self, max_rows: int = 1000) -> Dict[str, Any]
```
Convert to dictionary.

**Parameters:**
- `max_rows` (int): Maximum rows (default: 1000)

**Returns:** Dictionary representation

### to_context()
```python
def to_context(self, detail: str) -> str
```
Generate context string for LLM/AI use.

**Parameters:**
- `detail` (str): Level of detail

**Returns:** Context string

### download()
```python
def download(
    self,
    data_directory: Optional[str] = None,
    compress: bool = True,
    compression_level: int = 6,
    upload_to_cloud: bool = False,
    disable_progress: bool = False
)
```
Download all filings in collection to local storage.

**Parameters:**
- `data_directory`: Download directory (defaults to Edgar data directory)
- `compress`: Compress files (default: True)
- `compression_level`: gzip level 1-9 (default: 6)
- `upload_to_cloud`: Upload to cloud after download
- `disable_progress`: Disable progress display

**Example:**
```python
# Download with defaults
filings.download()

# Custom directory
filings.download(data_directory="./raw_data/", compress=False)
```

## Common Recipes

### Get latest 10-K filings from major exchanges

```python
from edgar import get_filings

filings = get_filings(2024, 1, form="10-K")

major_exchange = filings.filter(exchange=["NASDAQ", "NYSE"])
latest_20 = major_exchange.latest(20)

print(f"Found {len(latest_20)} recent 10-K filings")

for filing in latest_20:
    print(f"{filing.company}: {filing.filing_date}")
```

### Analyze filing trends

```python
from edgar import get_filings
import pandas as pd

filings = get_filings(2023, form=["10-K", "10-Q"])
df = filings.to_pandas()

# Form distribution
form_counts = df.groupby('form').size().sort_values(ascending=False)
print("Form distribution:")
print(form_counts)

# Monthly trends
df['filing_date'] = pd.to_datetime(df['filing_date'])
monthly = df.groupby(df['filing_date'].dt.to_period('M')).size()
print("\nMonthly filing counts:")
print(monthly)
```

### Batch process filings

```python
from edgar import get_filings

filings = get_filings(2024, 1, form="8-K")

# Process in batches using pagination
current_page = filings
total_processed = 0

while current_page and not current_page.empty:
    for filing in current_page:
        # Process each filing
        text = filing.text()
        # ... analysis logic

    total_processed += len(current_page)
    print(f"Processed {total_processed} filings")

    # Move to next page
    current_page = current_page.next()

print(f"Total processed: {total_processed}")
```

### Filter and export for analysis

```python
from edgar import get_filings

# Get filings
filings = get_filings(2023, form="10-K")

# Filter to tech companies on NASDAQ
nasdaq_tech = filings.filter(exchange="NASDAQ")

# Export to DataFrame
df = nasdaq_tech.to_pandas('company', 'filing_date', 'cik', 'accession_no')

# Save for later analysis
nasdaq_tech.save_parquet("nasdaq_tech_10k_2023.parquet")
```

### Extract financial data from multiple filings

```python
from edgar import get_filings

filings = get_filings(2024, 1, form="10-K").head(50)

results = []

for filing in filings:
    try:
        tenk = filing.obj()
        if tenk and tenk.financials:
            income = tenk.financials.income_statement
            # Extract data
            results.append({
                'company': filing.company,
                'filing_date': filing.filing_date,
                'has_financials': True
            })
    except Exception as e:
        print(f"Error processing {filing.company}: {e}")

print(f"Successfully processed {len(results)} filings")
```

## Advanced Patterns

### Chaining filters

```python
# Build complex filters
result = (get_filings(2024, 1)
    .filter(form=["10-K", "10-Q"])
    .filter(exchange="NASDAQ")
    .filter(date="2024-01-01:2024-01-31")
    .latest(100))
```

### Processing with pagination

```python
def process_all_pages(filings):
    """Process all pages in a filings collection"""
    current = filings
    all_results = []

    while current and not current.empty:
        # Process current page
        for filing in current:
            # Extract data
            all_results.append(filing.to_dict())

        print(f"Processed page with {len(current)} filings")

        # Move to next page
        current = current.next()

    return all_results

# Use it
filings = get_filings(2023, form="10-K")
results = process_all_pages(filings)
```

## Performance Tips

1. **Filter early** - Use `get_filings()` parameters instead of filtering later
2. **Limit results** - Use `.head(n)` or `.latest(n)` to avoid processing unnecessary filings
3. **Use pagination** - Process large datasets in pages with `.next()`
4. **Convert once** - Call `.to_pandas()` once and work with DataFrame

**Efficient:**
```python
filings = get_filings(2024, 1, form="10-K").head(100)
```

**Less efficient:**
```python
filings = get_filings(2024, 1).filter(form="10-K").head(100)
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
        filtered = filings.filter(exchange="NASDAQ")

        if filtered.empty:
            print("No NASDAQ filings")
        else:
            # Process
            for filing in filtered:
                try:
                    text = filing.text()
                except Exception as e:
                    print(f"Error processing {filing.accession_no}: {e}")
                    continue

except Exception as e:
    print(f"Error: {e}")
```

## Specialized Collections

### EntityFilings

Company-specific filings with additional properties:

```python
from edgar import Company

company = Company("AAPL")
entity_filings = company.get_filings()

print(type(entity_filings))  # edgar.entity.filings.EntityFilings

# Additional properties
print(entity_filings.cik)
print(entity_filings.company_name)

# Methods return EntityFilings
filtered = entity_filings.filter(form="10-K")  # EntityFilings
```

### CurrentFilings

Real-time filings with enhanced pagination:

```python
from edgar import get_current_filings

current = get_current_filings()
print(type(current))  # edgar._filings.CurrentFilings

# Filter
eightk = current.filter(form="8-K")

# Navigate
next_page = current.next()
```

## See Also

- **[Filing API Reference](filing.md)** - Individual filing operations
- **[Company API Reference](company.md)** - Company-specific filing access
- **[Filtering Filings Guide](../guides/filtering-filings.md)** - Advanced filtering techniques
- **[Current Filings Guide](../guides/current-filings.md)** - Real-time filing access
- **[Search Filings Guide](../guides/searching-filings.md)** - Finding specific filings
