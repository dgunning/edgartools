# SSL Verification Configuration in edgartools

## Overview
This document outlines the design and recommendations for configuring SSL verification in the edgartools library, particularly useful for corporate environments with SSL inspection or similar network configurations.

## Implementation

### 1. Environment Variable Control
The primary method is using the `EDGAR_VERIFY_SSL` environment variable:

```python
verify = os.environ.get("EDGAR_VERIFY_SSL", "true").lower() != "false"
```

- Default: SSL verification enabled (safer default)
- To disable: Set `EDGAR_VERIFY_SSL=false`

### 2. Internal Configuration
The library's HTTP client layer can be configured to disable SSL verification when needed. This is handled internally by the library and doesn't require direct interaction with the HTTP clients.

## Usage Examples

### Using Environment Variable
```bash
# Disable SSL verification
export EDGAR_VERIFY_SSL=false
python your_script.py

# Enable SSL verification (default)
export EDGAR_VERIFY_SSL=true
python your_script.py
```

### Using Direct Configuration
```python
from edgar import httpclient

# Disable SSL verification for specific client
with httpclient.http_client(verify=False) as client:
    # Make requests...
    ...
```

## Security Considerations

1. **Default Security**: SSL verification is enabled by default to maintain security.
2. **Targeted Usage**: Disable SSL verification only in controlled environments where necessary (e.g., corporate networks with SSL inspection).
3. **Risk Awareness**: Disabling SSL verification makes HTTPS connections potentially insecure. Only use when you understand the security implications.

## Best Practices

1. **Prefer Environment Variables**: Use environment variables for global configuration to avoid hardcoding security settings.
2. **Configuration Scope**: The SSL verification setting applies globally to all HTTP requests made by the library.
3. **Documentation**: Always document when and why SSL verification is disabled in your code.
4. **Security Review**: Have your security team review any permanent SSL verification disablement.
