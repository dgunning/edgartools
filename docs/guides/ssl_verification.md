# SSL and Network Configuration

This guide covers SSL verification, proxy configuration, and network troubleshooting for edgartools - especially useful for corporate environments with VPNs, SSL inspection, or proxy servers.

## Quick Fix: SSL Verification Errors

edgartools verifies SEC's certificate against your operating system's trust store, through the `truststore` library it ships with. Corporate networks that inspect HTTPS usually install their CA there, so most corporate setups work with no configuration.

If you still get certificate errors, the CA that signed the certificate you are seeing is missing from that store. In order of preference:

1. Ask IT to install your corporate root CA in the OS trust store (Keychain on macOS, the Windows certificate store, the `ca-certificates` package on Linux). No code change is needed afterwards.
2. Point `SSL_CERT_FILE` at a CA bundle that holds the corporate CA and the public roots (see [Option 2](#option-2-custom-ca-certificate)).
3. As a last resort, turn verification off with `configure_http(verify_ssl=False)`.

Run `diagnose_ssl()` to see which certificates are in use and what fails (see [Troubleshooting](#troubleshooting)).

!!! note "From 6.0 the OS store is the default"
    edgartools 6.0 makes its requests with `httpx2`, which verifies against your operating system's trust store by default; earlier releases used the `certifi` bundle unless you opted in. On 6.0, `use_system_certs=True` therefore matches what you already get, and stays available so existing code keeps working. `SSL_CERT_FILE` still overrides the default with a CA file of your choice. See [the upgrade guide](../upgrade/6.0.md#the-http-client-moved-from-httpx-to-httpx2).

## Understanding SSL Issues

### Common Causes

1. **Corporate VPN with SSL inspection** - Your organization intercepts HTTPS traffic and re-signs it with their own CA certificate, and that CA is not in your OS trust store
2. **Corporate proxy servers** - Traffic routed through a proxy that modifies certificates
3. **Self-signed certificates** - Development or testing environments
4. **Missing OS CA certificates** - A minimal container image without the `ca-certificates` package has no trust store to verify against

### Error Messages

You might see errors like:
- `SSL: CERTIFICATE_VERIFY_FAILED`
- `certificate verify failed`
- `unable to get local issuer certificate`

## Configuration Options

### Option 1: OS Certificate Store (the Default)

edgartools verifies against your operating system's native certificate store, which your IT department manages. There is nothing to turn on.

`SSL_CERT_FILE` and `SSL_CERT_DIR` replace the OS store when they are set. To verify against the OS store regardless of them, pass `use_system_certs=True`:

```python
from edgar import configure_http

configure_http(use_system_certs=True)
```

Or via environment variable (set **before** importing edgartools):

```bash
export EDGAR_USE_SYSTEM_CERTS=true
python your_script.py
```

### Option 2: Custom CA Certificate

If your IT department provides a CA certificate file and it cannot go into the OS store, point `SSL_CERT_FILE` at a bundle (set it **before** the first request):

```bash
export SSL_CERT_FILE="/path/to/company-ca-bundle.pem"
```

The file replaces the OS store, so it must hold the public roots that SEC.gov chains to as well as your corporate CA. The `certifi` package is a convenient source of those roots; it plays no other part in verification:

```bash
pip install certifi
cat "$(python -m certifi)" /path/to/corporate-ca.crt > ~/combined-bundle.pem
export SSL_CERT_FILE="$HOME/combined-bundle.pem"
```

`SSL_CERT_DIR` works the same way for a directory of hashed certificates. edgartools does not read `REQUESTS_CA_BUNDLE` or `CURL_CA_BUNDLE`.

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

# Nothing to configure when your IT department's CA is in the OS trust store.
# If it is not, add it there or point SSL_CERT_FILE at a bundle (Option 2).
company = Company("AAPL")
filings = company.get_filings(form="10-K")
```

### Scenario 2: Corporate Proxy Server

Traffic must go through a proxy:

```python
from edgar import configure_http, Company

configure_http(proxy="http://proxy.company.com:8080")

company = Company("AAPL")
```

### Scenario 3: VPN + Proxy + SSL Issues

Common in enterprise environments:

```python
from edgar import configure_http, Company

configure_http(
    proxy="http://proxy.company.com:8080",
    timeout=60.0  # Longer timeout for slow proxies
)

company = Company("AAPL")
```

### Scenario 4: Nothing Else Works

If neither the OS store nor an `SSL_CERT_FILE` bundle resolves the issue:

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
print(f"Certificates: {config['cert_source']}")  # e.g. 'os-store'
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
logging.getLogger("httpx2").setLevel(logging.DEBUG)
logging.getLogger("httpcore2").setLevel(logging.DEBUG)

from edgar import Company
company = Company("AAPL")  # Will show detailed HTTP logs
```

## Security Considerations

| Approach | Security | When to Use |
|----------|----------|-------------|
| OS certificate store (default) | Full SSL verification | Everywhere, including corporate networks whose CA is installed in the OS |
| `SSL_CERT_FILE` | Full SSL verification | When IT provides a cert file that cannot go into the OS store |
| `verify_ssl=False` | No SSL verification | Last resort only |

Disabling SSL verification makes connections vulnerable to man-in-the-middle attacks. Prefer adding the missing CA to the OS store or to an `SSL_CERT_FILE` bundle, which keeps verification active.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EDGAR_USE_SYSTEM_CERTS` | `false` | Verify against the OS store even when `SSL_CERT_FILE` / `SSL_CERT_DIR` is set (the OS store is already the default) |
| `SSL_CERT_FILE` | not set | CA bundle that replaces the OS store |
| `SSL_CERT_DIR` | not set | Directory of CA certificates that replaces the OS store |
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
- `use_system_certs`: Verify against the OS certificate store even when `SSL_CERT_FILE` / `SSL_CERT_DIR` is set; the OS store is already the default
- `verify_ssl`: Enable/disable SSL certificate verification (last resort)
- `proxy`: HTTP/HTTPS proxy URL (e.g., "http://proxy.company.com:8080")
- `timeout`: Request timeout in seconds

**Note:** `use_system_certs=True` takes precedence over `verify_ssl` when both are set.

### `get_http_config()`

```python
def get_http_config() -> dict
```

Returns current HTTP configuration as a dictionary with keys:
- `verify_ssl`: Whether SSL verification is on
- `cert_source`: Where verification takes its trusted CAs from: `"os-store"` (the default), `"SSL_CERT_FILE"`, `"SSL_CERT_DIR"`, `"custom"` (an `SSLContext` you passed) or `"disabled"`
- `use_system_certs`: Whether the OS certificate store is what verifies, which is `True` by default
- `proxy`: Current proxy URL (or None)
- `timeout`: Current timeout setting

## See Also

- [Troubleshooting](../resources/troubleshooting.md) - Common issues and solutions
