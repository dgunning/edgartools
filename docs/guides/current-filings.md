# Working with Current Filings

## Overview

Current filings represent the most recently submitted documents to the SEC, updated in real-time as companies file their reports. This guide shows you how to access, filter, and efficiently process current filings using edgartools.

## Quick Start

### Basic Usage

```python
from edgar import get_current_filings

# Get the most recent filings (default: 100 filings)
current = get_current_filings()
print(f"Found {len(current)} recent filings")

# Display the first few filings
for filing in current[:5]:
    print(f"{filing.form}: {filing.company} - {filing.filing_date}")
```

**Output:**
```plaintext
Found 100 recent filings
8-K: Apple Inc. - 2025-01-14
10-Q: Microsoft Corporation - 2025-01-14
4: BEZOS JEFFREY P - 2025-01-14
13F-HR: Berkshire Hathaway Inc - 2025-01-14
S-3: Tesla, Inc. - 2025-01-14
```

### Filter by Form Type

```python
# Get only Form 8-K current events
current_8k = get_current_filings(form='8-K')

# Get only insider trading forms (Forms 3, 4, 5)
current_insider = get_current_filings(form='4')

# Get quarterly and annual reports
current_reports = get_current_filings(form='10-K')
```

## Understanding Current Filings

### What Are Current Filings?

Current filings are the most recently submitted documents to the SEC, typically updated every few minutes during business hours. They include:

- **Form 8-K**: Current events and corporate changes
- **Forms 3, 4, 5**: Insider trading transactions
- **10-K/10-Q**: Annual and quarterly reports
- **13F**: Institutional investment manager holdings
- **S-1, S-3**: Registration statements
- **And many more...**

### Pagination System

Current filings are delivered in pages to manage large volumes:

```python
# Default: Get first 100 filings
current = get_current_filings(page_size=100)

# Get more filings per page (up to 100)
current = get_current_filings(page_size=80)

# Navigate to next page
next_page = current.next()
if next_page:
    print(f"Next page has {len(next_page)} filings")
```

## Core Functions

### `get_current_filings()`

Get a single page of current filings with filtering options.

```python
def get_current_filings(form: str = '', 
                       owner: str = 'include', 
                       page_size: int = 100) -> CurrentFilings:
```

**Parameters:**
- `form` (str): Filter by form type (e.g., "8-K", "10-K", "4")
- `owner` (str): Owner filter - "include", "exclude", or "only"
- `page_size` (int): Filings per page (10, 20, 40, 80, or 100)

**Returns:** `CurrentFilings` object with pagination capabilities

### `iter_current_filings_pages()`

Iterator that yields pages of current filings until exhausted.

```python
from edgar import iter_current_filings_pages

# Process all current 8-K filings page by page
for page in iter_current_filings_pages(form="8-K"):
    print(f"Processing {len(page)} 8-K filings")
    
    for filing in page:
        # Process each filing
        print(f"  {filing.company}: {filing.filing_date}")
    
    # Break after first few pages for demo
    if page.current_page >= 3:
        break
```

### `get_all_current_filings()`

Get ALL current filings by automatically iterating through all pages.

```python
from edgar import get_all_current_filings

# Get all current Form 4 filings (may be thousands)
all_form4 = get_all_current_filings(form="4")
print(f"Total Form 4 filings: {len(all_form4)}")

# Get all current filings (no form filter)
all_current = get_all_current_filings()
print(f"Total current filings: {len(all_current)}")
```

**⚠️ Performance Note:** This function downloads ALL available current filings, which can be thousands of documents. Use with appropriate filters.

## Filtering Options

### By Form Type

```python
# Specific form types
form_8k = get_current_filings(form="8-K")
form_10k = get_current_filings(form="10-K") 
form_4 = get_current_filings(form="4")

# Form families work too
quarterly_reports = get_current_filings(form="10-Q")
```

### By Owner Type

Control whether to include filings from investment managers:

```python
# Include all filings (default)
all_filings = get_current_filings(owner="include")

# Exclude ownership filings (e.g., Form 4, 144)
public_only = get_current_filings(owner="exclude")

# Only ownership filings (e.g., Form 4, 144)
managers_only = get_current_filings(owner="only")
```

### By Page Size

Choose how many filings to get per request:

```python
# Small batches for quick processing
small_batch = get_current_filings(page_size=20)

# Large batches for efficiency
large_batch = get_current_filings(page_size=100)  # Maximum
```

## Real-World Examples

### Example 1: Monitor Recent 8-K Events

```python
from edgar import get_all_current_filings
from datetime import datetime

def monitor_current_events():
    """Monitor recent 8-K filings for significant events."""
    
    # Get recent 8-K filings
    current_8k = get_all_current_filings(form="8-K")
    
    print(f"📈 Monitoring {len(current_8k)} recent 8-K filings")
    print(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)
    
    for filing in current_8k:
        # Show key information
        print(f"{filing.company}")
        print(f"  Form: {filing.form}")
        print(f"  Filed: {filing.filing_date}")
        print(f"  URL: {filing.document_url}")
        print()

monitor_current_events()
```

### Example 2: Track Insider Trading Activity

```python
from edgar import get_all_current_filings
import pandas as pd

def analyze_insider_activity():
    """Analyze current insider trading patterns."""
    
    # Get all current Form 4 filings
    print("📊 Downloading all current Form 4 filings...")
    insider_filings = get_all_current_filings(form="4")
    
    print(f"Found {len(insider_filings)} insider trading filings")
    
    # Convert to DataFrame for analysis
    df = insider_filings.to_pandas()
    
    # Analyze by company
    company_counts = df['company'].value_counts().head(10)
    
    print("\n🏢 Top 10 Companies by Filing Volume:")
    for company, count in company_counts.items():
        print(f"  {company}: {count} filings")
    
    # Analyze by filing date
    daily_counts = df['filing_date'].value_counts().sort_index()
    
    print(f"\n📅 Daily Filing Counts (last {len(daily_counts)} days):")
    for date, count in daily_counts.tail(7).items():
        print(f"  {date}: {count} filings")
    
    return df

# Run the analysis
insider_df = analyze_insider_activity()
```

### Example 3: Real-Time Filing Feed

```python
from edgar import get_current_filings
import time

def real_time_filing_feed(max_iterations=10):
    """Create a real-time feed of new filings."""
    
    seen_filings = set()
    iteration = 0
    
    print("🔄 Starting real-time filing feed...")
    print("Press Ctrl+C to stop\n")
    
    try:
        while iteration < max_iterations:
            # Get latest filings
            current = get_current_filings(page_size=20)
            new_filings = []
            
            for filing in current:
                filing_id = filing.accession_no
                if filing_id not in seen_filings:
                    new_filings.append(filing)
                    seen_filings.add(filing_id)
            
            if new_filings:
                print(f"🆕 {len(new_filings)} new filings detected:")
                for filing in new_filings:
                    print(f"  {filing.form}: {filing.company}")
                print()
            else:
                print("⏳ No new filings found, waiting...")
            
            # Wait before next check
            time.sleep(30)  # Check every 30 seconds
            iteration += 1
            
    except KeyboardInterrupt:
        print("\n✋ Feed stopped by user")

# Run the feed (limited iterations for demo)
real_time_filing_feed()
```

## Performance Considerations

### Memory Usage

```python
# Memory efficient: Process page by page
total_processed = 0
for page in iter_current_filings_pages(form="8-K"):
    # Process this page
    total_processed += len(page)
    
    # Page goes out of scope, memory is freed
    print(f"Processed {total_processed} total filings")

# Memory intensive: Load all at once
all_filings = get_all_current_filings()  # May use significant memory
```

### Network Efficiency

```python
# Efficient: Larger page sizes reduce requests
efficient = get_current_filings(page_size=100)  # 1 request

# Less efficient: Smaller pages mean more requests  
less_efficient = get_current_filings(page_size=10)  # May need 10 requests for same data
```

### Rate Limiting

The SEC imposes rate limits, so avoid rapid consecutive requests:

```python
import time

# Good: Natural pacing between requests
for page in iter_current_filings_pages():
    # Process page
    time.sleep(0.1)  # Brief pause between pages

# Bad: Rapid fire requests (may hit rate limits)
for i in range(100):
    page = get_current_filings()  # Don't do this!
```

## Choosing the Right Function

### Use `get_current_filings()` when:
- ✅ You want a quick sample of recent filings
- ✅ Building pagination in your own interface
- ✅ Memory usage is a concern
- ✅ You only need the first page or two

### Use `iter_current_filings_pages()` when:
- ✅ You want to process all filings but control memory usage
- ✅ You need page-by-page processing logic
- ✅ You want to limit total pages processed
- ✅ Building streaming or incremental processing

### Use `get_all_current_filings()` when:
- ✅ You need the complete dataset for analysis
- ✅ Memory usage is not a constraint
- ✅ You want to convert to pandas DataFrame
- ✅ Building bulk analysis or reporting

## Error Handling

### Common Issues and Solutions

```python
from edgar import get_current_filings
import time

def robust_current_filings(form="", max_retries=3):
    """Get current filings with error handling."""
    
    for attempt in range(max_retries):
        try:
            return get_current_filings(form=form)
            
        except ConnectionError as e:
            print(f"⚠️ Connection error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise
                
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            raise

# Usage
try:
    filings = robust_current_filings(form="8-K")
    print(f"✅ Successfully retrieved {len(filings)} filings")
except Exception as e:
    print(f"💥 Failed to get filings: {e}")
```

## Best Practices

### 1. Use Appropriate Filters

```python
# Good: Specific filtering reduces data and improves performance
insider_filings = get_current_filings(form="4")
corporate_events = get_current_filings(form="8-K")

# Okay: General purpose but processes more data
all_filings = get_current_filings()
```

### 2. Handle Pagination Properly

```python
# Good: Check for None before processing next page
current_page = get_current_filings()
while current_page is not None:
    # Process current page
    for filing in current_page:
        print(f"Processing {filing.company}")
    
    # Get next page
    current_page = current_page.next()

# Bad: Assuming next() always returns data
# This could cause infinite loops or errors
```

### 3. Be Respectful of SEC Resources

```python
# Good: Process in reasonable batches with pauses
for page in iter_current_filings_pages(page_size=100):
    # Process page
    time.sleep(0.1)  # Brief pause

# Good: Cache results when possible
cached_filings = get_all_current_filings(form="8-K")
# Reuse cached_filings instead of re-downloading
```

## Common Use Cases

### Research and Analysis
- **Market surveillance**: Monitor 8-K filings for material events
- **Insider tracking**: Analyze Form 4 patterns for trading insights  
- **Compliance monitoring**: Track filing compliance across companies

### Application Development
- **Filing alerts**: Build notifications for specific form types
- **Data pipelines**: Integrate current filings into larger workflows
- **Dashboard feeds**: Power real-time filing displays

### Academic Research
- **Event studies**: Analyze market reactions to filing events
- **Disclosure analysis**: Study timing and content patterns
- **Regulatory compliance**: Research filing behavior patterns

## Summary

Current filings provide real-time access to the latest SEC documents, enabling immediate analysis of corporate events, insider trading, and regulatory submissions. The three main functions offer flexibility for different use cases:

- **`get_current_filings()`**: Single page access with pagination control
- **`iter_current_filings_pages()`**: Memory-efficient iteration through all pages  
- **`get_all_current_filings()`**: Bulk access to complete current filing dataset

Choose the approach that best fits your memory constraints, processing requirements, and analysis goals.

## Next Steps

- **Guide**: [Working with Filings](working-with-filings.md)
- **API Reference**: [Filings API](../api/filings.md)