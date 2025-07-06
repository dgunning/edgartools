---
title: "SEC Rate Limits & Compliance"
description: "Understanding SEC EDGAR access requirements, rate limits, and how to ensure compliant usage of edgartools"
category: "resources"
difficulty: "beginner"
time_required: "10 minutes"
prerequisites: ["installation"]
related: ["performance", "troubleshooting"]
keywords: ["SEC", "rate limits", "compliance", "fair access", "robots.txt", "identity", "headers"]
---

# SEC Rate Limits & Compliance

The SEC EDGAR system is a valuable public resource that provides access to corporate filings. To ensure fair access for all users, the SEC has established guidelines and rate limits for automated access. This guide explains these requirements and how to use edgartools in a compliant manner.

## SEC EDGAR Access Requirements

### Fair Access Policy

The SEC maintains a [Fair Access Policy](https://www.sec.gov/os/accessing-edgar-data) that requires all automated EDGAR access to:

1. Identify the accessing user/organization in the HTTP request
2. Limit request rates to avoid overloading the system
3. Respect the `robots.txt` directives
4. Access data during appropriate hours

### Required Identity Information

When using automated tools to access EDGAR, you must identify yourself by providing:

- Your name or organization name
- Your email address

This allows the SEC to contact you if there are issues with your access patterns.

## Setting Your Identity in edgartools

edgartools makes it easy to comply with SEC requirements by providing a simple way to set your identity:

```python
from edgar import set_identity

# Set your identity information
set_identity(
    name="Your Name",
    email="your.email@example.com",
    organization="Your Organization"  # Optional
)
```

This identity information will be included in the `User-Agent` header of all requests made by edgartools.

### Default Behavior

If you don't explicitly set your identity, edgartools will:

1. Look for environment variables `EDGAR_NAME` and `EDGAR_EMAIL`
2. If not found, use a generic identity that indicates edgartools usage

However, it's strongly recommended to set your own identity to ensure compliance with SEC requirements.

## Understanding SEC Rate Limits

The SEC doesn't publish specific rate limits, but based on their guidelines and observed behavior, the following limits are recommended:

- No more than 10 requests per second
- Reasonable total volume per day
- Avoid excessive concurrent requests

### edgartools Default Rate Limiting

By default, edgartools implements conservative rate limiting:

- Maximum of 10 requests per second
- Built-in delays between requests
- Automatic retries with exponential backoff for 429 errors

This default configuration is designed to keep you compliant with SEC guidelines while still providing good performance.

## Customizing Rate Limits

You can adjust the rate limits in edgartools if needed:

```python
from edgar import set_rate_limit

# Set a more conservative rate limit (requests per second)
set_rate_limit(5)  # 5 requests per second
```

For high-volume or production use cases, consider being more conservative with your rate limits to avoid potential IP blocks.

## Signs of Exceeding Rate Limits

If you exceed SEC rate limits, you may experience:

1. HTTP 429 (Too Many Requests) responses
2. HTTP 403 (Forbidden) responses
3. Temporary IP blocks (typically 10 minutes to 24 hours)

edgartools will automatically handle 429 responses with retries, but persistent rate limit violations may result in longer blocks.

## Best Practices for Compliant Access

### 1. Always Set Your Identity

```python
from edgar import set_identity

set_identity(
    name="Your Name",
    email="your.email@example.com"
)
```

### 2. Use Local Storage

Reduce the number of requests by storing filings locally:

```python
from edgar import enable_local_storage

enable_local_storage("/path/to/storage")
```

### 3. Implement Appropriate Delays

For batch processing, add delays between operations:

```python
import time

for filing in filings:
    # Process filing
    process_filing(filing)
    # Add delay between filings
    time.sleep(0.2)  # 200ms delay
```

### 4. Use Efficient Query Patterns

Choose the most efficient access pattern for your needs:

```python
# For company-specific queries, use company.get_filings()
# (makes just one request for all filings)
company = Company("AAPL")
filings = company.get_filings(form="10-K")

# For form-specific queries across companies, use get_filings()
# (makes requests for quarterly indexes)
form4_filings = get_filings(form="4", year=2024)
```

### 5. Implement Exponential Backoff

For custom requests outside of edgartools:

```python
import time
import random

def request_with_backoff(url, max_retries=5):
    retries = 0
    while retries < max_retries:
        try:
            # Make request
            response = make_request(url)
            return response
        except Exception as e:
            if "429" in str(e) or "403" in str(e):
                # Calculate backoff time
                wait_time = (2 ** retries) + random.random()
                print(f"Rate limited. Waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time)
                retries += 1
            else:
                raise
    raise Exception("Max retries exceeded")
```

## Handling Rate Limit Errors

If you encounter rate limit errors despite following best practices:

1. **Reduce your request rate** by setting a lower rate limit
2. **Increase delays** between requests
3. **Implement circuit breakers** to pause requests when errors occur
4. **Spread requests** across a longer time period
5. **Use a different network** if your IP has been temporarily blocked

## SEC Access Hours

While the SEC EDGAR system is available 24/7, it's good practice to avoid peak hours:

- **Peak hours**: 9:30 AM - 4:00 PM Eastern Time (market hours)
- **Maintenance**: Occasionally on weekends

For large batch operations, consider running them during off-peak hours.

## Additional Compliance Considerations

### Terms of Service

The SEC provides EDGAR data as a public service. When using this data:

- Don't misrepresent the data or its source
- Don't claim affiliation with the SEC
- Provide proper attribution when republishing data

### Privacy Considerations

Some SEC filings contain personal information. Be mindful of privacy concerns when:

- Storing filings locally
- Processing personal information in filings
- Republishing or sharing filing data

## Monitoring Your Usage

To monitor your usage and ensure compliance:

```python
from edgar import get_request_stats

# Get statistics about your requests
stats = get_request_stats()
print(f"Requests made: {stats['total_requests']}")
print(f"Average rate: {stats['average_rate_per_second']:.2f} requests/second")
print(f"Rate limit errors: {stats['rate_limit_errors']}")
```

## Conclusion

Complying with SEC EDGAR access requirements is straightforward with edgartools. By setting your identity, respecting rate limits, and following best practices, you can ensure reliable and compliant access to SEC filing data.

Remember that the SEC provides this valuable data as a public service. Responsible usage helps ensure that EDGAR remains accessible to everyone.

## Additional Resources

- [SEC EDGAR Fair Access Policy](https://www.sec.gov/os/accessing-edgar-data)
- [SEC Developer Resources](https://www.sec.gov/developer)
- [SEC EDGAR Robots.txt](https://www.sec.gov/robots.txt)
