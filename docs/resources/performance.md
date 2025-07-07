---
title: "Performance Optimization"
description: "Strategies and best practices for optimizing performance when working with SEC data using edgartools"
category: "resources"
difficulty: "intermediate"
time_required: "15 minutes"
prerequisites: ["installation"]
related: ["troubleshooting", "local-data"]
keywords: ["performance", "optimization", "speed", "efficiency", "rate limits", "local storage", "batch processing"]
---

# Performance Optimization

Working with SEC data can be resource-intensive due to the volume of data, network latency, and SEC's rate limits. This guide provides strategies to optimize your edgartools workflows for better performance.

## Understanding How edgartools Fetches Data

To optimize performance, it's important to understand how edgartools retrieves data from the SEC EDGAR system.

### How `get_filings()` Works

The global `get_filings()` function operates as follows:

- It fetches quarterly filing indexes to cover the requested time period
- For the current year, it fetches complete data for the year to date
- For multiple years, it fetches quarterly indexes for each year
- Each quarterly index requires a separate HTTP request

For example, requesting filings for 2024 requires 4 HTTP requests (one for each quarter), while requesting filings for 2020-2024 requires 20 HTTP requests.

```python
# This makes 4 HTTP requests (one per quarter)
filings_2024 = get_filings(year=2024)

# This makes 20 HTTP requests (5 years × 4 quarters)
filings_multi_year = get_filings(start_date="2020-01-01", end_date="2024-12-31")
```

### How `company.get_filings()` Works

The `company.get_filings()` method works differently:

- It fetches the company's submission JSON file, which contains all available filings for that company
- This requires just one HTTP request, regardless of the date range
- The data is then filtered client-side based on your criteria

```python
# This makes just 1 HTTP request, regardless of date range
company = Company("AAPL")
company_filings = company.get_filings(form="10-K")
```

### Filing Content Retrieval

Both methods above only return filing metadata (indexes). When you access the actual content of a filing, an additional HTTP request is made:

```python
# This makes an additional HTTP request when you access the filing
filing = filings.latest()
filing_text = filing.text  # HTTP request happens here
```

## Choosing the Right Access Pattern

Based on your specific use case, choose the most efficient access pattern:

| If your query is... | Use this approach | Why |
|---------------------|-------------------|-----|
| Focused on specific form types across companies | `get_filings(form="4")` | Efficiently filters by form type |
| Focused on a single company | `company.get_filings()` | Makes just one HTTP request |
| Across multiple specific companies | `get_filings().filter(cik=["0000320193", "0000789019"])` | Allows precise filtering |
| Limited to a specific year | `get_filings(year=2024)` | Minimizes the number of index requests |
| Focused on recent filings | `get_filings().latest(100)` | Gets only the most recent filings |

## Rate Limiting Considerations

By default, edgartools limits requests to a maximum of 10 per second to comply with SEC EDGAR's rate limits. Exceeding these limits can result in your IP being temporarily blocked.

```python
# Default rate limit is 10 requests per second
# You can adjust it if needed (use with caution)
from edgar import set_rate_limit

# Decrease rate limit for more conservative approach
set_rate_limit(5)  # 5 requests per second
```

## Using Local Storage for Performance

One of the most effective ways to improve performance is to use local storage. This allows you to:

1. Cache filings locally to avoid repeated HTTP requests
2. Process filings offline without network latency
3. Batch download filings for later analysis

### Setting Up Local Storage

```python
from edgar import enable_local_storage

# Enable local storage
enable_local_storage("/path/to/storage")

# Now filings will be stored locally
company = Company("MSFT")
filings = company.get_filings(form="10-K")
filing = filings.latest()

# This will use the local copy if available, or download and cache it if not
text = filing.text
```

### Batch Downloading Filings

For large-scale analysis, batch download filings first, then process them offline:

```python
from edgar import download_filings

# Get filing metadata
companies = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
all_filings = []

for ticker in companies:
    company = Company(ticker)
    filings = company.get_filings(form="10-K").head(5)  # Last 5 10-Ks
    all_filings.extend(filings)

# Batch download all filings (this makes HTTP requests efficiently)
download_filings(all_filings, "/path/to/storage")

# Now process them offline (no HTTP requests)
for filing in all_filings:
    # Process filing without network latency
    text = filing.text  # Uses local copy
```

## Memory Optimization

When working with many filings or large filings, memory usage can become a concern.

### Processing Large Datasets

For large datasets, use generators and process filings one at a time:

```python
def process_filings_generator(filings):
    for filing in filings:
        # Process one filing at a time
        result = process_filing(filing)
        yield result
        # Free memory
        del filing

# Process filings one at a time
for result in process_filings_generator(all_filings):
    save_or_analyze(result)
```

### Working with Large Filings

For large filings (like 10-Ks), process sections individually:

```python
filing = company.get_latest_filing("10-K").obj()

# Process one section at a time
sections = ["business", "risk_factors", "management_discussion"]
for section_name in sections:
    if hasattr(filing, section_name):
        section = getattr(filing, section_name)
        # Process section
        process_section(section_name, section)
        # Free memory
        del section
```

## Parallel Processing

For computationally intensive tasks, consider parallel processing:

```python
from concurrent.futures import ThreadPoolExecutor
import time

def process_filing_with_delay(filing):
    # Add delay to respect rate limits
    time.sleep(0.1)
    # Process filing
    return {"accession": filing.accession_number, "text_length": len(filing.text)}

# Process filings in parallel with a thread pool
with ThreadPoolExecutor(max_workers=5) as executor:
    results = list(executor.map(process_filing_with_delay, all_filings))
```

## Caching Strategies

Implement caching for expensive operations:

```python
import functools

@functools.lru_cache(maxsize=128)
def get_filing_sentiment(filing_accession):
    # Expensive operation to calculate sentiment
    filing = get_filing_by_accession(filing_accession)
    text = filing.text
    # Calculate sentiment (expensive operation)
    return calculate_sentiment(text)

# This will be cached after the first call
sentiment = get_filing_sentiment("0000320193-20-000096")
```

## Performance Benchmarks

Here are some typical performance benchmarks to help you plan your workflows:

| Operation | Typical Time | Notes |
|-----------|--------------|-------|
| `get_filings(year=2024)` | 2-5 seconds | Fetches 4 quarterly indexes |
| `company.get_filings()` | 1-2 seconds | Single HTTP request |
| Downloading a 10-K filing | 1-3 seconds | Depends on filing size |
| Parsing a 10-K as Data Object | 2-5 seconds | First-time parsing |
| Accessing a locally stored filing | < 0.1 seconds | From disk cache |
| Processing 100 filings sequentially | 3-10 minutes | With rate limiting |
| Processing 100 filings in parallel | 1-3 minutes | With proper rate limiting |

## Best Practices Summary

1. **Choose the right access pattern** based on your specific use case
2. **Use `company.get_filings()`** when focusing on a single company
3. **Enable local storage** to avoid repeated HTTP requests
4. **Batch download filings** before processing them
5. **Process filings one at a time** for large datasets
6. **Respect SEC rate limits** to avoid being blocked
7. **Implement caching** for expensive operations
8. **Use parallel processing** carefully with appropriate delays
9. **Filter filings early** in your pipeline to reduce the number of filings to process
10. **Monitor memory usage** when working with large filings or datasets

By following these guidelines, you can significantly improve the performance of your edgartools workflows while respecting SEC EDGAR's rate limits and your system's resources.

## Advanced Techniques

### Custom Indexing

For repeated analysis of the same dataset, consider creating your own indexes:

```python
import pandas as pd

# Create a custom index of filings
filings = get_filings(form=["10-K", "10-Q"], year=2024)
index_data = []

for filing in filings:
    index_data.append({
        "accession": filing.accession_number,
        "cik": filing.cik,
        "company": filing.company_name,
        "form": filing.form_type,
        "date": filing.filing_date,
        "path": filing.get_local_path() if filing.is_local() else None
    })

# Save as CSV for quick loading
index_df = pd.DataFrame(index_data)
index_df.to_csv("filings_index_2024.csv", index=False)

# Later, load the index instead of fetching again
loaded_index = pd.read_csv("filings_index_2024.csv")
```

### Incremental Updates

For ongoing analysis, implement incremental updates:

```python
import datetime

# Get the date of your last update
last_update = datetime.date(2024, 6, 1)
today = datetime.date.today()

# Only fetch filings since your last update
new_filings = get_filings(start_date=last_update, end_date=today)

# Process only the new filings
for filing in new_filings:
    process_filing(filing)

# Update your last update date
last_update = today
```

By implementing these performance optimization strategies, you can make your edgartools workflows more efficient, faster, and more resilient.
