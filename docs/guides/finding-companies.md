# Find Companies by Name/Ticker

Learn how to locate companies in the SEC database using tickers, CIKs, or company names.


## Method 1: Find by Ticker Symbol

The most common way to find a company is by its stock ticker symbol:

```python
from edgar import Company

# Find Apple by ticker (case-insensitive)
apple = Company("AAPL")
print(apple)
```

**Output:**
```plaintext
Company(AAPL - Apple Inc.)
  CIK: 0000320193
  Industry: ELECTRONIC COMPUTERS
  Website: https://www.apple.com
  Location: Cupertino, CA
```

**Key points:**
- Tickers are case-insensitive: `Company("aapl")` works the same as `Company("AAPL")`
- This performs a ticker lookup then loads the company data
- Some companies have multiple tickers for the same entity

## Method 2: Find by CIK (Central Index Key)

The CIK uniquely identifies every SEC filer and is more reliable than tickers:

```python
# Using numeric CIK
apple = Company(320193)

# Using string CIK (with or without zero padding)
apple = Company("320193")
apple = Company("0000320193")

print(apple)
```

**Why use CIK:**
- **Unique**: Every company has exactly one CIK
- **Permanent**: CIKs don't change like tickers might
- **Faster**: Direct lookup without ticker resolution

## Method 3: Search by Company Name

When you don't know the exact ticker or CIK:

```python
from edgar import find

# Search for companies by name
results = find("Apple")
print(f"Found {len(results)} companies:")
for company in results:
    print(f"  {company.ticker}: {company.name}")
```

**Output:**
```plaintext
Found 3 companies:
  AAPL: Apple Inc.
  APPL: Apple Hospitality REIT Inc
  APOG: Apogee Enterprises Inc
```

**Then select the right one:**
```python
# Get the first result
apple = results[0]

# Or be more specific
apple = Company("AAPL")  # If you know the ticker from search
```

## Working with Company Objects

Once you have a Company object, you can access detailed information:

```python
company = Company("MSFT")

# Basic information
print(f"Name: {company.name}")
print(f"CIK: {company.cik}")
print(f"Ticker: {company.ticker}")
print(f"Industry: {company.industry}")
print(f"Website: {company.website}")
print(f"Location: {company.city}, {company.state}")

# SEC-specific information
print(f"SIC Code: {company.sic}")
print(f"Fiscal Year End: {company.fiscal_year_end}")
print(f"Exchange: {company.exchange}")
```

**Output:**
```plaintext
Name: Microsoft Corporation
CIK: 0000789019
Ticker: MSFT
Industry: SERVICES-PREPACKAGED SOFTWARE
Website: https://www.microsoft.com
Location: Redmond, WA
SIC Code: 7372
Fiscal Year End: 0630
Exchange: Nasdaq
```

## Handling Edge Cases

### Company Not Found
```python
try:
    company = Company("INVALID")
except Exception as e:
    print(f"Company not found: {e}")
    # Fallback to search
    results = find("Invalid Corp")
    if results:
        company = results[0]
    else:
        print("No companies found matching that name")
```

### Multiple Tickers for Same Company
```python
# Berkshire Hathaway has multiple share classes
brk_a = Company("BRK-A")  # Class A shares
brk_b = Company("BRK-B")  # Class B shares

# Both point to the same CIK and SEC filings
print(f"BRK-A CIK: {brk_a.cik}")
print(f"BRK-B CIK: {brk_b.cik}")
# Both will show: 0001067983
```

### Historical Tickers
```python
# Some companies change tickers over time
# The Company object will find the current entity
try:
    company = Company("FB")  # Meta's old ticker
    print(f"Found: {company.name}")  # May find Meta Platforms Inc
except:
    # Try the new ticker
    company = Company("META")
    print(f"Found: {company.name}")
```

## Batch Company Lookup

For analyzing multiple companies efficiently:

```python
from edgar import Company

# List of tickers to analyze
tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
companies = []

for ticker in tickers:
    try:
        company = Company(ticker)
        companies.append({
            'ticker': ticker,
            'name': company.name,
            'cik': company.cik,
            'industry': company.industry,
            'market_cap': company.market_cap  # If available
        })
        print(f"✓ Found {ticker}: {company.name}")
    except Exception as e:
        print(f"✗ Error with {ticker}: {e}")

# Convert to DataFrame for analysis
import pandas as pd
df = pd.DataFrame(companies)
print(df)
```

## Advanced Search Techniques

### Search by Industry
```python
from edgar import get_filings

# Get recent filings and filter by industry keywords
filings = get_filings()
tech_companies = []

for filing in filings:
    if filing.company_name and any(keyword in filing.company_name.lower() 
                                  for keyword in ['tech', 'software', 'computer']):
        try:
            company = Company(filing.cik)
            tech_companies.append(company)
        except:
            continue

# Remove duplicates
unique_companies = {c.cik: c for c in tech_companies}
print(f"Found {len(unique_companies)} unique tech companies")
```

### Search by Filing Activity
```python
# Find companies that filed 8-K forms recently
recent_8k_filings = get_filings(form="8-K", limit=100)

active_companies = []
for filing in recent_8k_filings:
    try:
        company = Company(filing.cik)
        active_companies.append({
            'ticker': company.ticker,
            'name': company.name,
            'filing_date': filing.filing_date,
            'cik': company.cik
        })
    except:
        continue

# Show most recently active companies
df = pd.DataFrame(active_companies)
recent_activity = df.sort_values('filing_date', ascending=False).head(10)
print(recent_activity)
```

## Performance Tips

1. **Use CIK when possible**: Faster than ticker lookup
2. **Cache company objects**: If analyzing the same companies repeatedly
3. **Batch processing**: Handle errors gracefully in loops
4. **Check data availability**: Not all companies have all fields populated

## Common Issues

### Ticker vs Company Name Confusion
```python
# This will fail - searching for ticker in name search
results = find("AAPL")  # Returns companies with "AAPL" in name, not ticker

# Use Company() for ticker lookup
company = Company("AAPL")  # Correct for ticker lookup
```

### International Companies
```python
# Some foreign companies trade on US exchanges
try:
    company = Company("ASML")  # Dutch company on NASDAQ
    print(f"Found: {company.name} in {company.country}")
except:
    print("Company not found or not SEC-registered")
```

### Delisted Companies
```python
# Some companies may be delisted but still have SEC filings
try:
    company = Company("1234567")  # Use CIK for delisted companies
    print(f"Company: {company.name}")
    print(f"Status: {'Active' if company.ticker else 'Possibly delisted'}")
except:
    print("Company not found in SEC database")
```

## Next Steps

Now that you can find companies, learn how to:

- **[Search for Specific Filings](searching-filings.md)** - Find the documents you need
- **[Extract Financial Statements](extract-statements.md)** - Get financial data
- **[Filter Filings by Date/Type](filtering-filings.md)** - Narrow down your search

## Related Documentation

- **[Company API Reference](../api/company.md)** - Complete Company class documentation
- **[Working with Companies](../company.md)** - Original company documentation