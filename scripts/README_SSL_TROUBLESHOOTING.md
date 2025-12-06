# SSL Troubleshooting Scripts

These scripts help diagnose and fix SSL/certificate issues when connecting to SEC.gov, particularly in corporate network environments with VPNs or SSL inspection proxies.

## Quick Start

### If you're having SSL errors:

1. **Run the diagnostic first** to understand your network configuration:
   ```bash
   python scripts/test_edgar_diagnostic.py
   ```

2. **Then test your configuration** to verify it works:
   ```bash
   python scripts/test_edgar_ssl.py
   ```

## Scripts

### test_edgar_diagnostic.py

**When to use:**
- You're getting SSL certificate errors
- You want to understand your network configuration
- You need to troubleshoot VPN/proxy issues
- You want to verify your `configure_http()` settings are working

**What it does:**
- Checks Python environment and installed packages
- Tests DNS resolution and TCP connectivity
- Performs SSL handshake analysis
- Detects corporate proxy/SSL inspection
- Compares configured vs actual HTTP client settings
- Provides specific recommendations for your situation

**Example output scenarios:**
- "Corporate proxy detected" → Explains SSL inspection is interfering
- "Client settings mismatch" → Shows `configure_http()` called too late
- "DNS resolution failed" → Network connectivity issue

### test_edgar_ssl.py

**When to use:**
- After running the diagnostic
- To verify your configuration works
- As a template for your own scripts
- To test without Jupyter notebook state issues

**What it does:**
- Demonstrates correct import order
- Calls `configure_http(verify_ssl=False)` before other imports
- Tests fetching real data from SEC.gov
- Provides clear success/failure output

**Why use this instead of Jupyter?**
- Fresh Python process (no hidden state)
- Clear execution order (no cell execution confusion)
- Reproducible results
- Easy to share output with support

## Common Issues and Solutions

### Issue: "Certificate verification failed"

**Cause:** Corporate VPN/proxy is replacing SEC.gov's certificate

**Solution:**
```python
from edgar import configure_http
configure_http(verify_ssl=False)
```

### Issue: "Client settings mismatch detected"

**Cause:** `configure_http()` called after HTTP client was already created

**Solution:** Call `configure_http()` FIRST, before any other edgar imports or operations:

```python
# ✓ CORRECT
from edgar import configure_http
configure_http(verify_ssl=False)
from edgar import Company  # Import after configuring

# ✗ WRONG
from edgar import Company, configure_http
configure_http(verify_ssl=False)  # Too late!
```

### Issue: "DNS resolution failed"

**Cause:** Network connectivity problem or DNS configuration issue

**Solution:**
- Check internet connection
- Verify `www.sec.gov` is accessible
- Contact IT if on corporate network

### Issue: "TCP connection failed"

**Cause:** Firewall blocking port 443 to SEC.gov

**Solution:**
- Contact IT department
- Ask if SEC.gov is blocked by firewall
- May need proxy configuration

## Using in Your Code

### Python Scripts

```python
# my_script.py
from edgar import configure_http
configure_http(verify_ssl=False)

from edgar import Company

company = Company("AAPL")
print(company.name)
```

### Jupyter Notebooks

```python
# First cell - run this FIRST
from edgar import configure_http
configure_http(verify_ssl=False)

# Second cell - now use edgar normally
from edgar import Company

company = Company("AAPL")
company
```

### Proxy Configuration

If your network requires a proxy:

```python
from edgar import configure_http
configure_http(
    verify_ssl=False,
    proxy="http://proxy.company.com:8080"
)
```

## Advanced Diagnostics

For programmatic diagnostic checks:

```python
from edgar import diagnose_ssl

result = diagnose_ssl(display=False)  # Don't display, just return data

# Check if SSL is working
if result.network_tests.ssl_handshake.success:
    print("SSL handshake successful")
else:
    print(f"SSL failed: {result.network_tests.ssl_handshake.error_message}")

# Check for corporate proxy
if result.network_tests.ssl_handshake.is_corporate_proxy:
    print("Corporate SSL inspection detected")

# Check configuration
if result.http_client_state.settings_match:
    print("Settings applied correctly")
else:
    print("Settings mismatch - call configure_http() earlier")
```

## Additional Resources

- [SSL Verification Guide](../docs/guides/ssl_verification.md)
- [EdgarTools Documentation](https://github.com/dgunning/edgartools)
- [Report Issues](https://github.com/dgunning/edgartools/issues)

## Troubleshooting Workflow

If you're having SSL issues:

1. **Start fresh** - Close Jupyter, restart your Python session
2. **Run diagnostic**: `python scripts/test_edgar_diagnostic.py`
3. **Read the output** - It will tell you exactly what's wrong
4. **Run test**: `python scripts/test_edgar_ssl.py`
5. **If it works** - Use the same pattern in your code (configure FIRST)
6. **If it fails** - Share the diagnostic output with support

The key insight: In Jupyter notebooks, cells can run out of order. These standalone scripts eliminate that confusion.