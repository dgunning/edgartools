# SSL and Network Configuration

This guide covers SSL verification, proxy configuration, and network troubleshooting for edgartools - especially useful for corporate environments with VPNs, SSL inspection, or proxy servers.

## Quick Fix: SSL Verification Errors

If you're getting SSL certificate errors, use `configure_http()`:

```python
from edgar import configure_http

# Disable SSL verification (use only in trusted networks)
configure_http(verify_ssl=False)

# Now use edgartools normally
from edgar import Company
company = Company("AAPL")
```

## Understanding SSL Issues

### Common Causes

1. **Corporate VPN with SSL inspection** - Your organization intercepts HTTPS traffic
2. **Corporate proxy servers** - Traffic routed through a proxy that modifies certificates
3. **Self-signed certificates** - Development or testing environments
4. **Outdated CA certificates** - System certificate store is outdated

### Error Messages

You might see errors like:
- `SSL: CERTIFICATE_VERIFY_FAILED`
- `certificate verify failed`
- `unable to get local issuer certificate`

## Configuration Options

### Option 1: Runtime Configuration (Recommended)

Use `configure_http()` to change settings at any time, even after importing:

```python
from edgar import configure_http, get_http_config

# Disable SSL verification
configure_http(verify_ssl=False)

# Configure a proxy
configure_http(proxy="http://proxy.company.com:8080")

# Configure both at once
configure_http(verify_ssl=False, proxy="http://proxy:8080")

# Check current configuration
print(get_http_config())
# {'verify_ssl': False, 'proxy': 'http://proxy:8080', 'timeout': ...}
```

### Option 2: Environment Variable (Before Import)

Set the environment variable **before** importing edgartools:

```python
import os
os.environ['EDGAR_VERIFY_SSL'] = 'false'

# IMPORTANT: Set env var BEFORE this import!
from edgar import Company
```

Or in your shell:
```bash
export EDGAR_VERIFY_SSL=false
python your_script.py
```

**Common Mistake**: Setting the environment variable *after* importing edgar has no effect because the HTTP client is initialized at import time. Use `configure_http()` instead if you've already imported.

### Option 3: System Proxy Environment Variables

Edgartools respects standard proxy environment variables:

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

# Disable SSL verification for corporate VPN
configure_http(verify_ssl=False)

company = Company("AAPL")
filings = company.get_filings(form="10-K")
```

### Scenario 2: Corporate Proxy Server

Traffic must go through a proxy:

```python
from edgar import configure_http, Company

# Configure proxy
configure_http(proxy="http://proxy.company.com:8080")

company = Company("AAPL")
```

### Scenario 3: VPN + Proxy + SSL Issues

Common in enterprise environments:

```python
from edgar import configure_http, Company

# Configure everything
configure_http(
    verify_ssl=False,
    proxy="http://proxy.company.com:8080",
    timeout=60.0  # Longer timeout for slow proxies
)

company = Company("AAPL")
```

### Scenario 4: Custom CA Certificates

If your organization uses custom CA certificates, you can configure the system:

```bash
# Add your organization's CA certificate to the system trust store
# Then set the certificate bundle path
export REQUESTS_CA_BUNDLE="/path/to/company-ca-bundle.crt"
export SSL_CERT_FILE="/path/to/company-ca-bundle.crt"
```

## Troubleshooting

### Check Current Configuration

```python
from edgar import get_http_config

config = get_http_config()
print(f"SSL Verification: {config['verify_ssl']}")
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

Disabling SSL verification reduces security by making connections vulnerable to man-in-the-middle attacks. Only use these options when:

1. You're on a **trusted corporate network**
2. You understand the security implications
3. You have no alternative (e.g., can't install corporate CA certificates)

**Best Practice**: Work with your IT department to properly install corporate CA certificates rather than disabling SSL verification.

## API Reference

### `configure_http()`

```python
def configure_http(
    verify_ssl: bool = None,
    proxy: str = None,
    timeout: float = None,
) -> None
```

Configure HTTP client settings at runtime.

**Parameters:**
- `verify_ssl`: Enable/disable SSL certificate verification
- `proxy`: HTTP/HTTPS proxy URL (e.g., "http://proxy.company.com:8080")
- `timeout`: Request timeout in seconds

### `get_http_config()`

```python
def get_http_config() -> dict
```

Returns current HTTP configuration as a dictionary with keys:
- `verify_ssl`: Current SSL verification setting
- `proxy`: Current proxy URL (or None)
- `timeout`: Current timeout setting

## See Also

- [Configuration Guide](../configuration.md) - Full configuration options
- [Troubleshooting](../resources/troubleshooting.md) - Common issues and solutions
