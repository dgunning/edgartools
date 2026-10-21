---
title: "Common Issues & Solutions"
description: "Troubleshooting guide for common issues encountered when using edgartools"
category: "resources"
difficulty: "all-levels"
time_required: "varies"
prerequisites: ["installation"]
related: ["sec-compliance", "performance"]
keywords: ["troubleshooting", "errors", "issues", "solutions", "problems", "fixes"]
---

# Common Issues & Solutions

This guide addresses the most common issues users encounter when working with edgartools and provides practical solutions.

## Connection and Access Issues

### SEC EDGAR Access Denied

**Symptom**: Receiving `403 Forbidden` errors when accessing SEC EDGAR.

**Causes**:
- Missing or incorrect identity information
- Exceeding SEC rate limits
- IP address blocked by SEC

**Solutions**:

1. **Set proper identity information**:

Use `set_identity` to provide your identity as required by the SEC.
This requires your **name** and **email**, or just your **email**.

```python
from edgar import set_identity
   
set_identity("Mike McCalum mcallum@gmail.com")

```

2. **Implement rate limiting**:
```python
import time
   
# Add delay between requests
for filing in filings:
    # Process filing
    time.sleep(0.1)  # 100ms delay
```

3. **Use a different network** if your IP has been temporarily blocked.

### Timeout Errors

**Symptom**: Requests to SEC EDGAR time out.

**Solutions**:

- Try again during off-peak hours (SEC EDGAR can be slow during market hours)

### SSL Certificate Errors

**Symptom**: Errors like `SSL: CERTIFICATE_VERIFY_FAILED`, `certificate verify failed`, or `unable to get local issuer certificate`.

**Common Causes**:
- Corporate VPN with SSL inspection
- Corporate proxy server
- Self-signed certificates in development environments

**Solutions** (in order of preference):

edgartools already verifies against your OS certificate store, so the error means the CA that signed the certificate you are seeing is missing from it.

1. **Add your corporate root CA to the OS trust store (Recommended)**: ask IT to install it (Keychain on macOS, the Windows certificate store, the `ca-certificates` package on Linux). No code change is needed afterwards.

2. **Point `SSL_CERT_FILE` at a CA bundle** holding the corporate CA and the public roots, set before the first request:
```bash
pip install certifi   # only a source of the public roots
cat "$(python -m certifi)" /path/to/corporate-ca.crt > ~/combined-bundle.pem
export SSL_CERT_FILE="$HOME/combined-bundle.pem"
```

3. **Disable SSL verification (Last resort)**:
```python
from edgar import configure_http

# WARNING: Reduces security. Only use on trusted networks.
configure_http(verify_ssl=False)
```

4. **Configure a proxy** if your network requires it:
```python
from edgar import configure_http
configure_http(proxy="http://proxy.company.com:8080")
```

Run `diagnose_ssl()` to see which certificates are in use. See the [SSL Configuration Guide](../guides/ssl_verification.md) for detailed instructions.

## Data Retrieval Issues

### Filing Not Found

**Symptom**: `FilingNotFoundError` when trying to access a specific filing.

**Solutions**:

1. **Verify the filing exists**:
```python
# Check if the filing exists first
filings = company.get_filings(form="10-K")
if filings:
    filing = filings.latest()
else:
    print("No 10-K filings found")
```

2. **Check for alternative form types**:
```python
 # Some companies use variant form types
filings = company.get_filings(form=["10-K", "10-K/A", "10KSB"])
```

3. **Expand your date range**:
```python
filings = company.get_filings(
       form="10-K",
       start_date="2010-01-01",  # Try a wider date range
       end_date="2023-12-31"
   )
```

### Company Not Found

**Symptom**: `CompanyNotFoundError` when trying to access a company.

**Solutions**:

1. **Check ticker symbol or CIK**:
```python
# Try using CIK instead of ticker
company = Company("0000320193")  # Apple Inc. CIK
   
# Or search for the company
from edgar import search_companies
results = search_companies("Apple")
for r in results:
    print(f"{r.name} - {r.ticker} - {r.cik}")
```

2. **For delisted companies**, try using the CIK number directly.

### Inconsistent Financial Data Signs

**Symptom**: Expense values appear negative for some companies but positive for others in cross-company analysis.

**Solution**: This was resolved in edgartools 4.9.2+ through enhanced calculation weight handling. Update to the latest version:

```python
pip install --upgrade edgartools
```

Major expense categories (R&D, SG&A, Marketing) are now consistently positive across companies, matching SEC CompanyFacts API behavior while preserving calculation relationships for cash flow items.

### Missing Financial Data

**Symptom**: Financial statements are empty or missing expected values.

**Solutions**:

1. **Check if the filing has XBRL data**:
```python
from edgar.financials import Financials

filing = company.get_filings(form="10-K").latest()
if filing.xbrl():
    financials = Financials.extract(filing)
else:
    print("Filing does not contain XBRL data")
```

2. **Try different concept names**:
```python
# Try alternative concept names
df = income_stmt.to_dataframe()
period = max(c for c in df.columns if c.startswith("20"))  # most recent period
for concept in ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"]:
    rows = df[df["concept"] == f"us-gaap_{concept}"]
    if not rows.empty:
        revenue = rows.iloc[0][period]
        break
```

3. **For older filings** (pre-2009), XBRL data may not be available.

## Parsing Issues

### HTML Parsing Errors

**Symptom**: Errors when trying to extract sections from filings.

**Solutions**:

1. **Access raw text instead**:
```python
   # Fall back to raw text
   filing_text = filing.text
```

2. **Try a different filing**:
```python
# Try the previous filing
filings = company.get_filings(form="10-K")
if len(filings) > 1:
    previous_filing = filings[1]
```

### XBRL Parsing Errors

**Symptom**: Errors when trying to access XBRL data.

**Solutions**:

1. **Check if the filing has valid XBRL**:
```python
xbrl = filing.xbrl()
if xbrl:
    try:
        print("XBRL entity:", xbrl.entity_name)
    except Exception as e:
        print(f"XBRL parsing error: {e}")
```


## Performance Issues

### Slow Data Retrieval

**Symptom**: Operations take a long time to complete.

**Solutions**:

1. **Use local storage**:
```python
from edgar import use_local_storage
   
# Store filings locally
use_local_storage()
```

2. **Limit the number of filings**:
```python
# Only get the 5 most recent filings
filings = company.get_filings(form="10-K").head(5)
```

3. **Use batch processing** for large datasets.

### Memory Issues

**Symptom**: Program crashes with memory errors when processing many filings.

**Solutions**:

1. **Process filings one at a time**:
```python
for filing in filings:
    # Process each filing
    result = process_filing(filing)
    # Save result and free memory
    save_result(result)
    del result
```

2. **Use generators instead of lists**:
```python
def process_filings_generator(filings):
    for filing in filings:
        yield process_filing(filing)
   
# Process one filing at a time
for result in process_filings_generator(filings):
    save_result(result)
```

## Installation Issues

### Dependency Conflicts

**Symptom**: Errors related to dependencies when installing or using edgartools.

**Solutions**:

1. **Use a virtual environment**:

```bash
# Create a new virtual environment
python -m venv edgar_env
   
# Activate it
source edgar_env/bin/activate  # On Windows: edgar_env\Scripts\activate
   
# Install edgartools
pip install edgartools
```

2. **Update dependencies**:
```bash
pip install --upgrade edgartools
```


### Import Errors

**Symptom**: `ImportError` or `ModuleNotFoundError` when importing edgartools.

**Solutions**:

1. **Verify installation**:
```bash
pip show edgartools
```

2. **Reinstall the package**:
```bash
pip uninstall -y edgartools
pip install edgartools
```


2. **Access the raw filing content**:
```python
# Access the raw content instead
html = filing.html
text = filing.text
```


## SEC Rate Limiting

### Too Many Requests


1. **Spread requests over time**:
```python
companies = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
results = {}
   
for ticker in companies:
    company = Company(ticker)
    results[ticker] = company.get_filings(form="10-K").latest()
    time.sleep(1)  # Wait 1 second between companies
```

## Debugging Tips

### Enable Logging

Turn on logging to get more information about what's happening:

```python
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# For even more detailed logs
logging.getLogger('edgar').setLevel(logging.DEBUG)
```

### Check SEC EDGAR Status

The SEC EDGAR system occasionally experiences downtime or performance issues:

1. Visit the [SEC EDGAR Status page](https://www.sec.gov/edgar/filer-information/current-edgar-technical-specifications) to check for any announced issues.


### Verify Your Data

Always verify the data you're working with:

```python
from edgar.financials import Financials

# Print filing metadata to verify
print(f"Filing: {filing.accession_number}")
print(f"Form Type: {filing.form}")
print(f"Filing Date: {filing.filing_date}")
print(f"Has XBRL: {filing.xbrl() is not None}")

# Check financial statement structure
financials = Financials.extract(filing)
print(financials)
```

## Getting Help

If you're still experiencing issues:

1. **Check the documentation**: Make sure you're using the API correctly.

2. **Search GitHub Issues**: Your issue may have been reported and solved already.

3. **Ask the community**: Post your question on Stack Overflow with the `edgartools` tag.

4. **Report a bug**: If you believe you've found a bug, report it on the GitHub repository with a minimal reproducible example.

## Common Error Messages and Their Meanings

| Error Message | Likely Cause | Solution |
|---------------|--------------|----------|
| `CompanyNotFoundError` | Invalid ticker or CIK | Verify the ticker or try using CIK |
| `FilingNotFoundError` | Filing doesn't exist or is not accessible | Check form type and date range |
| `XBRLNotFoundError` | Filing doesn't contain XBRL data | Try a different filing or use text extraction |
| `ParsingError` | Issue parsing the filing content | Try accessing raw content instead |
| `HTTPError 403` | SEC has blocked your requests | Set proper identity and respect rate limits |
| `HTTPError 429` | Too many requests in a short time | Implement rate limiting and backoff |
| `ConnectionError` | Network issues | Check your internet connection |
| `SSLVerificationError` | Corporate VPN/proxy with SSL inspection | Add the corporate CA to the OS trust store, or set `SSL_CERT_FILE` |
| `CERTIFICATE_VERIFY_FAILED` | SSL certificate issues | Run `diagnose_ssl()`; add the missing CA to the OS store or `SSL_CERT_FILE` |
| `UnsupportedFilingTypeError` | Data Object not available for this filing type | Use generic access methods |

Remember that SEC filings can vary significantly in structure and content, especially across different years and companies. Always implement robust error handling in your code to deal with these variations.
