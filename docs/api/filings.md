# Filings API Reference

The `Filings` class represents a collection of SEC filings with powerful filtering, navigation, and data manipulation capabilities. It serves as the primary interface for working with multiple filings in EdgarTools.

## Class Overview

```python
from edgar import Filings, get_filings

class Filings:
    """Collection of SEC filings with filtering and pagination capabilities."""
```

**Backend:** Uses PyArrow tables for efficient data handling

## Constructor

### Filings(filing_index, original_state=None)

Create a Filings collection from a PyArrow table.

```python
Filings(
    filing_index: pa.Table,
    original_state: Optional[PagingState] = None)
```

**Parameters:**
- `filing_index` (pa.Table): PyArrow table containing filing data
- `original_state` (Optional[PagingState]): Pagination state for navigation

**Note:** Typically created via `get_filings()` function rather than direct instantiation.

**Example:**
```python
from edgar import get_filings

# Get filings collection
filings = get_filings(year=2023, quarter=1)
print(type(filings))  # <class 'edgar._filings.Filings'>
```

## Core Properties

### Collection Information

#### empty
```python
@property
def empty(self) -> bool:
```
Whether the collection contains any filings.

```python
filings = get_filings(form="INVALID")
if filings.empty:
    print("No filings found")
```

#### date_range
```python
@property
def date_range(self) -> Tuple[str, str]:
```
Start and end dates for filings in the collection.

```python
start_date, end_date = filings.date_range
print(f"Filings from {start_date} to {end_date}")
```

#### start_date / end_date
```python
@property
def start_date(self) -> str:
    ...

@property  
def end_date(self) -> str:
    ...
```
Individual start and end dates.

```python
print(f"Collection spans from {filings.start_date} to {filings.end_date}")
```

#### summary
```python
@property
def summary(self) -> str:
```
Summary string describing the current page/collection.

```python
print(filings.summary)
# "Page 1 of 10 filings from 2023-01-01 to 2023-03-31"
```

## Collection Operations

### Size and Access

#### len() / count
```python
def __len__(self) -> int:
```
Number of filings in the current collection/page.

```python
print(f"Collection contains {len(filings)} filings")
```

#### Indexing and Iteration
```python
def __getitem__(self, item: int) -> Filing:
    ...
def __iter__(self) -> Iterator[Filing]:
    ...
```
Access individual filings by index or iterate through collection.

```python
# Index access
first_filing = filings[0]
last_filing = filings[-1]

# Iteration
for filing in filings:
    print(f"{filing.form}: {filing.company} ({filing.filing_date})")

# Slicing
first_five = filings[:5]
```

#### get()
```python
def get(self, index_or_accession_number: Union[int, str]) -> Filing
```
Get a filing by index or accession number.

**Parameters:**
- `index_or_accession_number`: Integer index or accession number string

**Returns:** `Filing` object

**Example:**
```python
# Get by index
filing = filings.get(0)

# Get by accession number
filing = filings.get("0001234567-23-000001")
```

### Subset Operations

#### latest()
```python
def latest(self, n: int = 1) -> Union[Filing, 'Filings']
```
Get the most recent filing(s).

**Parameters:**
- `n` (int): Number of latest filings to return (default: 1)

**Returns:**
- Single `Filing` if n=1
- `Filings` collection if n>1

**Example:**
```python
# Get latest single filing
latest_filing = filings.latest()

# Get latest 5 filings
latest_five = filings.latest(5)
print(f"Latest 5 filings: {len(latest_five)}")
```

#### head()
```python
def head(self, n: int) -> 'Filings'
```
Get the first n filings from the collection.

**Parameters:**
- `n` (int): Number of filings to return

**Returns:** `Filings` collection

**Example:**
```python
first_ten = filings.head(10)
print(f"First 10 filings: {len(first_ten)}")
```

#### tail()
```python
def tail(self, n: int) -> 'Filings'
```
Get the last n filings from the collection.

**Parameters:**
- `n` (int): Number of filings to return

**Returns:** `Filings` collection

**Example:**
```python
last_ten = filings.tail(10)
print(f"Last 10 filings: {len(last_ten)}")
```

#### sample()
```python
def sample(self, n: int) -> 'Filings'
```
Get a random sample of n filings.

**Parameters:**
- `n` (int): Number of filings to sample

**Returns:** `Filings` collection

**Example:**
```python
random_sample = filings.sample(5)
print(f"Random sample: {len(random_sample)} filings")
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
) -> 'Filings'
```

Filter the collection by various criteria.

**Parameters:**
- `form`: SEC form type(s) - e.g., "10-K", ["10-K", "10-Q"]
- `amendments`: Include/exclude amendments (default: include)
- `filing_date` / `date`: Date filter (YYYY-MM-DD or YYYY-MM-DD:YYYY-MM-DD)
- `cik`: Central Index Key(s)
- `exchange`: Stock exchange(s) - "NASDAQ", "NYSE", "CBOE", "OTC"
- `ticker`: Stock ticker symbol(s)
- `accession_number`: SEC accession number(s)

**Returns:** Filtered `Filings` collection

**Examples:**
```python
# Filter by form type
annual_reports = filings.filter(form="10-K")
financial_reports = filings.filter(form=["10-K", "10-Q"])

# Filter by date range
q1_filings = filings.filter(date="2023-01-01:2023-03-31")
recent_filings = filings.filter(date="2023-01-01:")

# Filter by company
apple_filings = filings.filter(ticker="AAPL")
apple_by_cik = filings.filter(cik=320193)

# Filter by exchange
nasdaq_filings = filings.filter(exchange="NASDAQ")
major_exchanges = filings.filter(exchange=["NASDAQ", "NYSE"])

# Exclude amendments
original_only = filings.filter(amendments=False)

# Chain filters
filtered = filings.filter(form="10-K").filter(exchange="NASDAQ").filter(date="2023-01-01:")
```

### find()
```python
def find(self, company_search_str: str) -> 'Filings'
```
Search for filings by company name.

**Parameters:**
- `company_search_str` (str): Company name search string

**Returns:** `Filings` collection matching the search

**Example:**
```python
# Search for companies with "Apple" in name
apple_filings = filings.find("Apple")

# Search for technology companies
tech_filings = filings.find("Technology")
```

## Navigation and Pagination

### current()
```python
def current(self) -> 'Filings'
```
Get the current page of filings.

**Returns:** Current `Filings` page

### next()
```python
def next(self) -> Optional['Filings']
```
Navigate to the next page of filings.

**Returns:** Next page `Filings` or None if no more pages

**Example:**
```python
# Navigate through pages
current_page = filings.current()
next_page = filings.next()

if next_page:
    print(f"Next page has {len(next_page)} filings")
else:
    print("No more pages available")
```

### previous()
```python
def previous(self) -> Optional['Filings']
```
Navigate to the previous page of filings.

**Returns:** Previous page `Filings` or None if on first page

**Example:**
```python
# Go back to previous page
prev_page = filings.previous()

if prev_page:
    print(f"Previous page has {len(prev_page)} filings")
else:
    print("Already on first page")
```

## Data Export and Persistence

### to_pandas()
```python
def to_pandas(self, *columns: str) -> pd.DataFrame
```
Convert the collection to a pandas DataFrame.

**Parameters:**
- `*columns`: Specific columns to include (optional)

**Returns:** `pd.DataFrame` with filing data

**Example:**
```python
# Convert all data
df = filings.to_pandas()
print(df.columns.tolist())

# Convert specific columns only
summary_df = filings.to_pandas('form', 'company', 'filing_date')
print(summary_df.head())
```

### save_parquet() / save()
```python
def save_parquet(self, location: str)
def save(self, location: str)  # Alias
```
Save the collection as a Parquet file.

**Parameters:**
- `location` (str): File path to save to

**Example:**
```python
# Save collection
filings.save_parquet("my_filings.parquet")

# Load back later
import pandas as pd
df = pd.read_parquet("my_filings.parquet")
```

### to_dict()
```python
def to_dict(self, max_rows: int = 1000) -> Dict[str, Any]
```
Convert to dictionary representation.

**Parameters:**
- `max_rows` (int): Maximum number of rows to include (default: 1000)

**Returns:** Dictionary with filing data

**Example:**
```python
filings_dict = filings.to_dict(max_rows=100)
print(filings_dict.keys())
```

### download()
```python
def download(self, data_directory: Optional[str] = None)
```
Download all filings in the collection to local storage.

**Parameters:**
- `data_directory` (Optional[str]): Directory to save files (optional)

**Example:**
```python
# Download to current directory
filings.download()

# Download to specific directory
filings.download("./edgar_data/")
```

## Specialized Filing Collections

### EntityFilings

Enhanced filings collection for company-specific filings:

```python
from edgar import Company

company = Company("AAPL")
entity_filings = company.get_filings()

print(type(entity_filings))  # <class 'edgar.entity.filings.EntityFilings'>

# Additional properties
print(entity_filings.cik)          # Company CIK
print(entity_filings.company_name) # Company name

# Enhanced methods return EntityFilings
filtered = entity_filings.filter(form="10-K")  # Returns EntityFilings
latest = entity_filings.latest(3)              # Returns EntityFilings
```

### CurrentFilings

Real-time filings with enhanced pagination:

```python
from edgar import get_current_filings

current = get_current_filings()
print(type(current))  # <class 'edgar._filings.CurrentFilings'>

# Additional properties
print(current.form)   # Form filter
print(current.owner)  # Owner filter

# Real-time pagination
next_page = current.next()
```

## Advanced Usage Patterns

### Chaining Operations

```python
# Complex filtering and processing pipeline
result = (filings
    .filter(form=["10-K", "10-Q"])
    .filter(exchange="NASDAQ") 
    .filter(date="2023-01-01:")
    .latest(50)
)

print(f"Final result: {len(result)} filings")
```

### Batch Processing

```python
# Process filings in batches
batch_size = 100
total_processed = 0

while not filings.empty:
    batch = filings.head(batch_size)
    
    # Process each filing in batch
    for filing in batch:
        # Extract data, analyze, etc.
        text = filing.text()
        # ... processing logic
        
    total_processed += len(batch)
    
    # Move to next batch
    filings = filings.tail(len(filings) - batch_size)
    
print(f"Processed {total_processed} filings")
```

### Data Analysis

```python
# Convert to DataFrame for analysis
df = filings.to_pandas()

# Analyze filing patterns
form_counts = df.groupby('form').size().sort_values(ascending=False)
print("Most common forms:")
print(form_counts.head())

# Monthly filing trends
df['filing_date'] = pd.to_datetime(df['filing_date'])
monthly_filings = df.groupby(df['filing_date'].dt.to_period('M')).size()
print("Monthly filing counts:")
print(monthly_filings)

# Company analysis
top_filers = df.groupby('company').size().sort_values(ascending=False)
print("Top 10 filing companies:")
print(top_filers.head(10))
```

## Performance Optimization

### Efficient Filtering

```python
# More efficient: specific filtering upfront
efficient = get_filings(
    year=2023,
    form="10-K",
    limit=100
)

# Less efficient: get all then filter
inefficient = get_filings(year=2023, limit=10000).filter(form="10-K")
```

### Pagination Strategies

```python
# Process large datasets with pagination
def process_all_filings(filings):
    current_page = filings
    total_processed = 0
    
    while current_page and not current_page.empty:
        # Process current page
        for filing in current_page:
            # Process individual filing
            pass
            
        total_processed += len(current_page)
        print(f"Processed {total_processed} filings so far...")
        
        # Move to next page
        current_page = current_page.next()
    
    return total_processed

# Usage
filings = get_filings(year=2023)
total = process_all_filings(filings)
```

## Error Handling

```python
try:
    # Filter operations
    filtered = filings.filter(form="10-K", date="2023-01-01:")
    
    if filtered.empty:
        print("No filings match the criteria")
    else:
        # Process results
        for filing in filtered:
            try:
                text = filing.text()
                # Process text
            except Exception as e:
                print(f"Error processing filing {filing.accession_no}: {e}")
                continue
                
except Exception as e:
    print(f"Error filtering filings: {e}")

# Navigation error handling
next_page = filings.next()
if next_page is None:
    print("No more pages available")
```

## Complete Example

```python
from edgar import get_filings
import pandas as pd

# Get filings for analysis
filings = get_filings(year=2023, quarter=1)
print(f"Initial collection: {len(filings)} filings")

# Filter to focus on annual reports from major exchanges
annual_reports = filings.filter(
    form="10-K",
    exchange=["NASDAQ", "NYSE"]
)
print(f"Annual reports from major exchanges: {len(annual_reports)}")

# Get latest 20 for detailed analysis
latest_reports = annual_reports.latest(20)

# Convert to DataFrame for analysis
df = latest_reports.to_pandas()

# Analyze companies and dates
print("\nCompanies with recent 10-K filings:")
for _, row in df.iterrows():
    print(f"  {row['company']}: {row['filing_date']}")

# Export for further analysis
latest_reports.save_parquet("annual_reports_q1_2023.parquet")

# Process individual filings
for filing in latest_reports:
    try:
        # Extract structured data
        tenk = filing.obj()
        if tenk and tenk.financials:
            financials = tenk.financials
            revenue = financials.income.loc['Revenue'].iloc[0] if 'Revenue' in financials.income.index else None
            if revenue:
                print(f"{filing.company}: Revenue ${revenue/1e9:.1f}B")
    except Exception as e:
        print(f"Error processing {filing.company}: {e}")

# Navigate through additional pages if needed
next_page = filings.next()
if next_page:
    print(f"\nNext page available with {len(next_page)} more filings")
```

## See Also

- **[Filing API Reference](filing.md)** - Working with individual filings
- **[Company API Reference](company.md)** - Company-specific filing collections
- **[Filtering Filings Guide](../guides/filtering-filings.md)** - Advanced filtering techniques
- **[Search Filings Guide](../guides/searching-filings.md)** - Finding specific filings