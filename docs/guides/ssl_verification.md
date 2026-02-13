# SSL and Network Configuration

This guide covers SSL verification, proxy configuration, and network troubleshooting for edgartools - especially useful for corporate environments with VPNs, SSL inspection, or proxy servers.

## Quick Fix: SSL Verification Errors

If you're getting SSL certificate errors, the best solution is to use your OS certificate store:

```python
from edgar import configure_http

# Use your OS certificate store (recommended)
configure_http(use_system_certs=True)

# Now use edgartools normally
from edgar import Company
company = Company("AAPL")
```

This works because corporate networks add their CA certificates to your operating system's trust store. The `truststore` library (included with edgartools) lets Python use those certificates instead of its own bundled ones.

## Understanding SSL Issues

### Common Causes

1. **Corporate VPN with SSL inspection** - Your organization intercepts HTTPS traffic and re-signs it with their own CA certificate
2. **Corporate proxy servers** - Traffic routed through a proxy that modifies certificates
3. **Self-signed certificates** - Development or testing environments
4. **Outdated CA certificates** - Python's bundled certificate store is outdated

### Error Messages

You might see errors like:
- `SSL: CERTIFICATE_VERIFY_FAILED`
- `certificate verify failed`
- `unable to get local issuer certificate`

## Configuration Options

### Option 1: Use OS Certificate Store (Recommended)

The most secure fix for corporate environments. Uses your operating system's native certificate store, which your IT department manages:

```python
from edgar import configure_http

configure_http(use_system_certs=True)
```

Or via environment variable (set **before** importing edgartools):

```bash
export EDGAR_USE_SYSTEM_CERTS=true
python your_script.py
```

```python
import os
os.environ['EDGAR_USE_SYSTEM_CERTS'] = 'true'

# IMPORTANT: Set env var BEFORE this import!
from edgar import Company
```

### Option 2: Custom CA Certificate

If your IT department provides a specific CA certificate file:

```bash
export REQUESTS_CA_BUNDLE="/path/to/company-ca-bundle.crt"
export SSL_CERT_FILE="/path/to/company-ca-bundle.crt"
```

### Option 3: Disable SSL Verification (Last Resort)

Only use this if Options 1 and 2 don't work. Disabling SSL verification removes protection against man-in-the-middle attacks:

```python
from edgar import configure_http

# WARNING: Reduces security. Use only on trusted networks.
configure_http(verify_ssl=False)
```

Or via environment variable:

```bash
export EDGAR_VERIFY_SSL=false
```

### Option 4: Proxy Configuration

If your network requires a proxy:

```python
from edgar import configure_http

configure_http(proxy="http://proxy.company.com:8080")
```

Standard proxy environment variables are also respected:

```bash
export HTTP_PROXY="http://proxy.company.com:8080"
export HTTPS_PROXY="http://proxy.company.com:8080"
export NO_PROXY="localhost,127.0.0.1"
```

For authenticated proxies:
```bash
export HTTPS_PROXY="http://username:password@proxy.company.com:8080"
```

## Corporate Network Scenarios

### Scenario 1: VPN with SSL Inspection

Your IT department inspects HTTPS traffic, causing certificate errors:

```python
from edgar import configure_http, Company

# Use OS certs — your IT department's CA is already trusted by your OS
configure_http(use_system_certs=True)

company = Company("AAPL")
filings = company.get_filings(form="10-K")
```

### Scenario 2: Corporate Proxy Server

Traffic must go through a proxy:

```python
from edgar import configure_http, Company

configure_http(
    use_system_certs=True,
    proxy="http://proxy.company.com:8080"
)

company = Company("AAPL")
```

### Scenario 3: VPN + Proxy + SSL Issues

Common in enterprise environments:

```python
from edgar import configure_http, Company

configure_http(
    use_system_certs=True,
    proxy="http://proxy.company.com:8080",
    timeout=60.0  # Longer timeout for slow proxies
)

company = Company("AAPL")
```

### Scenario 4: Nothing Else Works

If system certs and custom CA bundles don't resolve the issue:

```python
from edgar import configure_http, Company

# Last resort — disables SSL verification entirely
configure_http(
    verify_ssl=False,
    proxy="http://proxy.company.com:8080",
    timeout=60.0
)

company = Company("AAPL")
```

## Troubleshooting

### Run SSL Diagnostics

EdgarTools includes a built-in diagnostic tool:

```python
from edgar import diagnose_ssl

# Displays a comprehensive report
result = diagnose_ssl()

# Or get structured data for programmatic use
result = diagnose_ssl(display=False)
if not result.ssl_ok:
    print(result.diagnosis)
    for rec in result.recommendations:
        print(f"- {rec.title}")
```

### Check Current Configuration

```python
from edgar import get_http_config

config = get_http_config()
print(f"SSL Verification: {config['verify_ssl']}")
print(f"System Certs: {config['use_system_certs']}")
print(f"Proxy: {config['proxy']}")
print(f"Timeout: {config['timeout']}")
```

### Test Connectivity

```python
from edgar import Company

try:
    company = Company("AAPL")
    print(f"Success! Connected to SEC EDGAR")
    print(f"Company: {company.name}")
except Exception as e:
    print(f"Connection failed: {e}")
```

### Enable Debug Logging

For detailed connection information:

```python
import logging

# Enable HTTP debug logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("httpcore").setLevel(logging.DEBUG)

from edgar import Company
company = Company("AAPL")  # Will show detailed HTTP logs
```

## Security Considerations

| Approach | Security | When to Use |
|----------|----------|-------------|
| `use_system_certs=True` | Full SSL verification | Corporate networks (recommended) |
| `REQUESTS_CA_BUNDLE` | Full SSL verification | When IT provides a cert file |
| `verify_ssl=False` | No SSL verification | Last resort only |

Disabling SSL verification makes connections vulnerable to man-in-the-middle attacks. Always prefer `use_system_certs=True` — it keeps SSL verification active while using the certificates your OS trusts.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EDGAR_USE_SYSTEM_CERTS` | `false` | Use OS native certificate store |
| `EDGAR_VERIFY_SSL` | `true` | Enable/disable SSL verification |
| `EDGAR_RATE_LIMIT_PER_SEC` | `9` | Request rate limit |

`EDGAR_USE_SYSTEM_CERTS=true` takes precedence over `EDGAR_VERIFY_SSL` when both are set.

## API Reference

### `configure_http()`

```python
def configure_http(
    verify_ssl: bool = None,
    use_system_certs: bool = None,
    proxy: str = None,
    timeout: float = None,
) -> None
```

Configure HTTP client settings at runtime.

**Parameters:**
- `use_system_certs`: Use OS native certificate store (recommended for corporate networks)
- `verify_ssl`: Enable/disable SSL certificate verification (last resort)
- `proxy`: HTTP/HTTPS proxy URL (e.g., "http://proxy.company.com:8080")
- `timeout`: Request timeout in seconds

**Note:** `use_system_certs=True` takes precedence over `verify_ssl` when both are set.

### `get_http_config()`

```python
def get_http_config() -> dict
```

Returns current HTTP configuration as a dictionary with keys:
- `verify_ssl`: Current SSL verification setting
- `use_system_certs`: Whether OS certificate store is active
- `proxy`: Current proxy URL (or None)
- `timeout`: Current timeout setting

## See Also

- [Troubleshooting](../resources/troubleshooting.md) - Common issues and solutions
