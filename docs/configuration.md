# Configuration

EdgarTools provides extensive configuration options through environment variables and programmatic settings to customize behavior, optimize performance, and ensure SEC compliance.

## Quick Setup

For most users, you only need to set your identity:

```bash
export EDGAR_IDENTITY="Your Name your.email@company.com"
```

Or in Python:
```python
from edgar import set_identity
set_identity("Your Name your.email@company.com")
```

## Environment Variables

### Required Configuration

#### EDGAR_IDENTITY
**Required for all SEC requests**

Sets the User-Agent string for SEC EDGAR requests. Required by SEC to identify your application.

```bash
export EDGAR_IDENTITY="John Doe john.doe@company.com"
```

**Format Options:**
- `"Name email@domain.com"` - Full name and email (recommended)
- `"email@domain.com"` - Email only (acceptable)
- `"Company Name contact@company.com"` - Company identification

**Python Alternative:**
```python
from edgar import set_identity
set_identity("John Doe john.doe@company.com")
```

### Performance and Access Control

#### EDGAR_ACCESS_MODE
Controls HTTP request behavior and connection limits to manage SEC server load.

```bash
export EDGAR_ACCESS_MODE="NORMAL"
```

**Available Modes:**

| Mode | Timeout | Max Connections | Retries | Use Case |
|------|---------|----------------|---------|----------|
| `NORMAL` | 15s | 10 | 3 | Default - balanced performance |
| `CAUTION` | 20s | 5 | 3 | Conservative - reduces server load |
| `CRAWL` | 25s | 2 | 2 | Minimal impact - bulk processing |

**Examples:**
```bash
# High-performance research (default)
export EDGAR_ACCESS_MODE="NORMAL"

# Conservative access for production
export EDGAR_ACCESS_MODE="CAUTION"

# Bulk data processing with minimal server impact
export EDGAR_ACCESS_MODE="CRAWL"
```

### Local Data Storage

#### EDGAR_USE_LOCAL_DATA
Enables local caching of SEC data for improved performance and reduced API calls.

```bash
export EDGAR_USE_LOCAL_DATA="True"
```

**Values:**
- `"True"`, `"true"`, `"1"` - Enable local storage
- `"False"`, `"false"`, `"0"` - Disable local storage (default)

**Benefits of Local Storage:**
- Faster repeated access to same data
- Reduced SEC API calls
- Offline access to cached data
- Better performance for bulk operations

**Python Alternative:**
```python
from edgar import use_local_storage
use_local_storage(True)
```

#### EDGAR_LOCAL_DATA_DIR
Sets the directory for local data storage.

```bash
export EDGAR_LOCAL_DATA_DIR="/path/to/your/edgar/data"
```

**Default:** `~/.edgar` (user's home directory)

**Directory Structure:**
```
~/.edgar/                    # Root data directory
├── requestcache/            # HTTP response cache
├── filings/                 # Downloaded filing data
│   └── YYYYMMDD/            # Organized by date
├── submissions/             # Company submissions data
├── companyfacts/            # Company facts data
└── reference/               # Reference data (tickers, etc.)
```

**Example Setup:**
```bash
# Custom data directory for project
export EDGAR_LOCAL_DATA_DIR="/project/edgar_data"
export EDGAR_USE_LOCAL_DATA="True"
```

### Security and SSL

#### EDGAR_VERIFY_SSL
Controls SSL certificate verification for HTTPS requests.

```bash
export EDGAR_VERIFY_SSL="true"
```

**Values:**
- `"true"` (default) - Verify SSL certificates (recommended)
- `"false"`, `"0"`, `"no"`, `"n"`, `"off"` - Disable SSL verification

**⚠️ Security Warning:** Only disable SSL verification in controlled environments. This reduces security by allowing man-in-the-middle attacks.

**Use Cases for Disabling:**
- Corporate proxy environments with custom certificates
- Development environments with self-signed certificates
- Network environments with SSL inspection

### HTTP Rate Limiting
Rate limiting is implemented in `httpclient_ratelimiting`. 

The default rate limit is 9 requests per second. SEC has a maximum of 10 requests per second. To change the rate limit, call: `httpclient.update_rate_limiter(requests_per_second: int)`.

### Advanced: Distributed Rate Limiting
Distributed Rate Limiting: rate limiting is implemented using [pyrate_limiter](https://pypi.org/project/pyrate-limiter/). To use a distributed rate limiter, such as for multiprocessing, define an httpclient._RATE_LIMITER. See the pyrate_limiter documentation and examples for details.

## Enterprise Configuration

EdgarTools v4.28.0+ supports enterprise-grade configuration for custom SEC data sources and flexible rate limiting, enabling deployment with private mirrors, academic institutions, and high-volume applications.

### Configurable Rate Limiting

#### EDGAR_RATE_LIMIT_PER_SEC
Control the maximum number of requests per second to SEC servers or custom mirrors.

```bash
export EDGAR_RATE_LIMIT_PER_SEC="9"
```

**Default:** `9` requests/second (SEC's official limit)

**Typical Values:**
- `9` - SEC's standard limit (default, recommended for official SEC servers)
- `10` - SEC's maximum allowed limit
- Higher values (e.g., `20`, `50`) - Only for authorized custom mirrors with relaxed rate restrictions

**Use Cases:**
- **Custom mirrors**: Higher rate limits for private infrastructure with different restrictions
- **Authorized applications**: High-volume applications with special SEC authorization
- **Testing environments**: Flexible rate limits for development and testing
- **International mirrors**: Optimized rates for regional mirrors

**Example:**
```bash
# Standard SEC access (default)
export EDGAR_RATE_LIMIT_PER_SEC="9"

# Custom mirror with relaxed limits
export EDGAR_RATE_LIMIT_PER_SEC="50"
export EDGAR_BASE_URL="https://sec-mirror.company.com"
```

**Python Alternative:**
```python
from edgar import httpclient

# Update rate limiter programmatically
httpclient.update_rate_limiter(requests_per_second=20)
```

**⚠️ Important:** Only use rate limits higher than 10 req/sec with custom mirrors or when authorized by SEC. Exceeding SEC's 10 req/sec limit may result in IP blocking.

### Custom SEC Data Sources

Configure EdgarTools to use custom SEC mirrors, private data sources, or testing servers instead of the official SEC website.

#### EDGAR_BASE_URL
Sets the base URL for SEC EDGAR website access.

```bash
export EDGAR_BASE_URL="https://www.sec.gov"
```

**Default:** `https://www.sec.gov`

**Use Cases:**
- Corporate SEC mirrors for compliance workflows
- Academic research institutions with local mirrors
- Regional mirrors for reduced latency (international users)
- Testing environments with mock servers

**Example:**
```bash
# Corporate mirror
export EDGAR_BASE_URL="https://sec-mirror.company.com"

# Academic institution mirror
export EDGAR_BASE_URL="https://sec.university.edu"

# Regional mirror (example)
export EDGAR_BASE_URL="https://sec-eu.example.com"
```

#### EDGAR_DATA_URL
Sets the base URL for SEC data archives (filing documents, submissions, company facts).

```bash
export EDGAR_DATA_URL="https://data.sec.gov"
```

**Default:** `https://data.sec.gov`

**Use Cases:**
- Separate data server from website server
- CDN acceleration for filing downloads
- Private data repositories
- Bandwidth optimization

**Example:**
```bash
# Use CDN for data downloads
export EDGAR_DATA_URL="https://cdn.sec-data.company.com"

# Corporate data repository
export EDGAR_DATA_URL="https://sec-data.company.com"
```

#### EDGAR_XBRL_URL
Sets the base URL for XBRL-specific data and services.

```bash
export EDGAR_XBRL_URL="https://www.sec.gov"
```

**Default:** `https://www.sec.gov`

**Use Cases:**
- Specialized XBRL processing servers
- XBRL validation and parsing services
- Enhanced XBRL data repositories

**Example:**
```bash
# Dedicated XBRL server
export EDGAR_XBRL_URL="https://xbrl.sec-mirror.company.com"
```

### Complete Enterprise Configuration Example

#### Corporate Mirror Setup
```bash
# Corporate SEC mirror with higher rate limits
export EDGAR_IDENTITY="Corporate Compliance compliance@company.com"
export EDGAR_BASE_URL="https://sec-mirror.company.com"
export EDGAR_DATA_URL="https://sec-data.company.com"
export EDGAR_XBRL_URL="https://sec-xbrl.company.com"
export EDGAR_RATE_LIMIT_PER_SEC="50"
export EDGAR_ACCESS_MODE="NORMAL"
export EDGAR_USE_LOCAL_DATA="True"
export EDGAR_LOCAL_DATA_DIR="/var/lib/edgar"
```

#### Academic Research Institution
```bash
# University research mirror with custom rate limits
export EDGAR_IDENTITY="Research Lab research@university.edu"
export EDGAR_BASE_URL="https://sec.university.edu"
export EDGAR_DATA_URL="https://sec-data.university.edu"
export EDGAR_RATE_LIMIT_PER_SEC="25"
export EDGAR_USE_LOCAL_DATA="True"
export EDGAR_LOCAL_DATA_DIR="/research/edgar_data"
```

#### Regional Mirror (International Users)
```bash
# Regional mirror for reduced latency
export EDGAR_IDENTITY="International Analyst analyst@company.com"
export EDGAR_BASE_URL="https://sec-eu.example.com"
export EDGAR_DATA_URL="https://sec-data-eu.example.com"
export EDGAR_RATE_LIMIT_PER_SEC="15"
export EDGAR_ACCESS_MODE="NORMAL"
```

#### Development/Testing Environment
```bash
# Mock SEC server for testing
export EDGAR_IDENTITY="Developer dev@company.com"
export EDGAR_BASE_URL="http://localhost:8080"
export EDGAR_DATA_URL="http://localhost:8080/data"
export EDGAR_XBRL_URL="http://localhost:8080/xbrl"
export EDGAR_RATE_LIMIT_PER_SEC="100"  # No limits for testing
export EDGAR_VERIFY_SSL="false"  # Self-signed certificates in dev
export EDGAR_USE_RICH_LOGGING="1"
```

### Python Configuration API

Configure enterprise settings programmatically:

```python
import os

# Set custom SEC mirror
os.environ['EDGAR_BASE_URL'] = "https://sec-mirror.company.com"
os.environ['EDGAR_DATA_URL'] = "https://sec-data.company.com"
os.environ['EDGAR_RATE_LIMIT_PER_SEC'] = "50"

# Now import and use EdgarTools
from edgar import Company

company = Company("AAPL")  # Uses custom mirror
filings = company.get_filings(form="10-K")
```

**Note:** Environment variables must be set before importing EdgarTools modules, as configuration is evaluated at import time.

### Docker/Container Configuration

For containerized deployments with custom SEC mirrors:

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install EdgarTools
RUN pip install edgartools

# Configure enterprise SEC access
ENV EDGAR_IDENTITY="Container App app@company.com"
ENV EDGAR_BASE_URL="https://sec-mirror.company.com"
ENV EDGAR_DATA_URL="https://sec-data.company.com"
ENV EDGAR_RATE_LIMIT_PER_SEC="50"
ENV EDGAR_ACCESS_MODE="CAUTION"
ENV EDGAR_USE_LOCAL_DATA="True"
ENV EDGAR_LOCAL_DATA_DIR="/app/edgar_data"

# Create data directory
RUN mkdir -p /app/edgar_data
VOLUME /app/edgar_data

WORKDIR /app
```

**Docker Compose Example:**
```yaml
version: '3.8'
services:
  edgar-app:
    image: your-edgar-app:latest
    environment:
      - EDGAR_IDENTITY=Service app@company.com
      - EDGAR_BASE_URL=https://sec-mirror.company.com
      - EDGAR_DATA_URL=https://sec-data.company.com
      - EDGAR_RATE_LIMIT_PER_SEC=50
      - EDGAR_USE_LOCAL_DATA=True
      - EDGAR_LOCAL_DATA_DIR=/data
    volumes:
      - edgar-data:/data

volumes:
  edgar-data:
```

### Validation and Testing

Verify your enterprise configuration:

```python
import os
from edgar import Company

def validate_enterprise_config():
    """Validate enterprise EdgarTools configuration."""
    print("Enterprise Configuration:")
    print(f"  Base URL: {os.getenv('EDGAR_BASE_URL', 'https://www.sec.gov')}")
    print(f"  Data URL: {os.getenv('EDGAR_DATA_URL', 'https://data.sec.gov')}")
    print(f"  XBRL URL: {os.getenv('EDGAR_XBRL_URL', 'https://www.sec.gov')}")
    print(f"  Rate Limit: {os.getenv('EDGAR_RATE_LIMIT_PER_SEC', '9')} req/sec")

    # Test basic functionality
    try:
        company = Company("AAPL")
        print(f"\n✓ Successfully connected: {company.name}")

        # Test filing access
        filings = company.get_filings(form="10-K").head(1)
        if filings:
            print(f"✓ Successfully retrieved filings from: {filings[0].accession_number}")

        return True
    except Exception as e:
        print(f"\n❌ Configuration test failed: {e}")
        return False

# Run validation
validate_enterprise_config()
```

### Troubleshooting Enterprise Configuration

#### Custom Mirror Connection Issues
```python
# Test connectivity to custom mirror
import requests

base_url = os.getenv('EDGAR_BASE_URL')
try:
    response = requests.get(f"{base_url}/cgi-bin/browse-edgar")
    print(f"✓ Mirror accessible: {response.status_code}")
except Exception as e:
    print(f"❌ Mirror connection failed: {e}")
```

#### Rate Limit Verification
```python
# Verify rate limiter is using correct setting
from edgar import httpclient

print(f"Current rate limit: {os.getenv('EDGAR_RATE_LIMIT_PER_SEC', '9')} req/sec")

# Monitor rate limiting in action
import time
start = time.time()
for i in range(20):
    # Make 20 requests
    company = Company("AAPL")
elapsed = time.time() - start
actual_rate = 20 / elapsed
print(f"Actual request rate: {actual_rate:.2f} req/sec")
```

#### SSL Certificate Issues with Custom Mirrors
```bash
# If custom mirror uses self-signed certificates
export EDGAR_VERIFY_SSL="false"

# Or configure SSL certificate bundle
export REQUESTS_CA_BUNDLE="/path/to/company-ca-bundle.crt"
```

### Best Practices for Enterprise Deployment

1. **Always set EDGAR_IDENTITY** - Include company/team identification
2. **Test mirror connectivity** - Validate URLs before production deployment
3. **Monitor rate limits** - Ensure compliance with mirror's rate restrictions
4. **Use local data storage** - Enable caching for improved performance
5. **Secure credentials** - Use environment variables, not hardcoded values
6. **Document configuration** - Maintain configuration profiles for different environments
7. **Version control** - Use `.env.example` files to document required variables
8. **Health checks** - Implement validation functions to verify configuration

### Environment Variables Summary

| Variable | Default | Purpose | Enterprise Use Case |
|----------|---------|---------|---------------------|
| `EDGAR_RATE_LIMIT_PER_SEC` | `9` | Request rate limit | Custom mirrors, authorized high-volume apps |
| `EDGAR_BASE_URL` | `https://www.sec.gov` | SEC website base URL | Corporate mirrors, regional mirrors |
| `EDGAR_DATA_URL` | `https://data.sec.gov` | Data archives URL | CDN acceleration, private repositories |
| `EDGAR_XBRL_URL` | `https://www.sec.gov` | XBRL services URL | Specialized XBRL servers |

### Backward Compatibility

All enterprise configuration features are **fully backward compatible**:
- Default values point to official SEC servers
- Zero configuration needed for standard users
- Existing code continues to work without changes
- Environment variables are optional

### HTTP Caching 
Web requests are cached by default, according to the rules defined in httpclient_cache. 

#### Cache Directory

The cache directory is set in `httpclient.CACHE_DIRECTORY`, set to `_cache` by default. Set CACHE_DIRECTORY=None to disable cache. Call `httpclient.close_client()` after any changes to the CACHE_DIRECTORY variable. 

#### Caching Rules
The SEC marks all requests as either NO-STORE or NO-CACHE, therefore a custom cache controller was implemented with the following rules: 
- `/submissions` URLs for up to 10 minutes by default, set in `MAX_SUBMISSIONS_AGE_SECONDS`
- `.*index/.*` URLs for up to 30 minutes by default, set in `MAX_INDEX_AGE_SECONDS`
- `/Archives/edgar/data` URLs indefinitely (forever)

See `httpclient_cache` for implementation. 

#### Advanced: Alternative Storage Caches
- The underlying cache is a FileStorage cache. While not implemented, it's feasible to replace this with a S3Storage cache by overriding get_transport and get_async_storage. See S3Storage and AsyncS3Storage at https://hishel.com/ for details.

#### EDGAR_USE_RICH_LOGGING
Enables enhanced console logging with rich formatting.

```bash
export EDGAR_USE_RICH_LOGGING="1"
```

**Values:**
- `"1"` - Enable rich logging with colors and formatting
- `"0"` (default) - Standard logging

**Benefits:**
- Color-coded log levels
- Enhanced readability
- Progress bars and status indicators
- Better debugging information

## Programmatic Configuration

### Setting Identity

```python
from edgar import set_identity

# Set identity programmatically
set_identity("Research Team research@university.edu")

# Verify identity is set
from edgar.core import get_identity
print(f"Current identity: {get_identity()}")
```

### Local Storage Control

```python
from edgar import use_local_storage

# Enable local storage
use_local_storage(True)

# Disable local storage
use_local_storage(False)

# Check current setting
from edgar.storage import using_local_storage
print(f"Using local storage: {using_local_storage()}")
```

### HTTP Client Configuration

```python
from edgar.core import EdgarSettings

# Custom access mode
custom_settings = EdgarSettings(
    http_timeout=30,        # 30 second timeout
    max_connections=3,      # Maximum 3 concurrent connections
    retries=5              # 5 retry attempts
)

# Apply custom settings (requires restarting client)
```

## Configuration Profiles

### Research Profile
Optimized for interactive research and analysis:

```bash
export EDGAR_IDENTITY="Researcher researcher@university.edu"
export EDGAR_ACCESS_MODE="NORMAL"
export EDGAR_USE_LOCAL_DATA="True"
export EDGAR_USE_RICH_LOGGING="1"
```

### Production Profile
Conservative settings for production environments:

```bash
export EDGAR_IDENTITY="Production System api@company.com"
export EDGAR_ACCESS_MODE="CAUTION"
export EDGAR_USE_LOCAL_DATA="True"
export EDGAR_LOCAL_DATA_DIR="/var/lib/edgar"
export EDGAR_VERIFY_SSL="true"
```

### Bulk Processing Profile
Minimal server impact for large-scale data processing:

```bash
export EDGAR_IDENTITY="Bulk Processor batch@company.com"
export EDGAR_ACCESS_MODE="CRAWL"
export EDGAR_USE_LOCAL_DATA="True"
export EDGAR_LOCAL_DATA_DIR="/data/edgar"
```

### Development Profile
Flexible settings for development and testing:

```bash
export EDGAR_IDENTITY="Developer dev@company.com"
export EDGAR_ACCESS_MODE="NORMAL"
export EDGAR_USE_LOCAL_DATA="True"
export EDGAR_USE_RICH_LOGGING="1"
export EDGAR_VERIFY_SSL="false"  # Only if needed for proxy
```

### Enterprise Mirror Profile
For custom SEC mirrors with higher rate limits (see [Enterprise Configuration](#enterprise-configuration)):

```bash
export EDGAR_IDENTITY="Corporate Compliance compliance@company.com"
export EDGAR_BASE_URL="https://sec-mirror.company.com"
export EDGAR_DATA_URL="https://sec-data.company.com"
export EDGAR_RATE_LIMIT_PER_SEC="50"
export EDGAR_USE_LOCAL_DATA="True"
export EDGAR_LOCAL_DATA_DIR="/var/lib/edgar"
```

## Configuration File Setup

### .env File
Create a `.env` file in your project root:

```bash
# .env file
EDGAR_IDENTITY=John Doe john.doe@company.com
EDGAR_ACCESS_MODE=NORMAL
EDGAR_USE_LOCAL_DATA=True
EDGAR_LOCAL_DATA_DIR=./edgar_data
EDGAR_USE_RICH_LOGGING=1
```

Load with python-dotenv:
```python
from dotenv import load_dotenv
load_dotenv()

# Now EdgarTools will use the environment variables
from edgar import Company
company = Company("AAPL")
```

### Shell Configuration
Add to your shell profile (`.bashrc`, `.zshrc`, etc.):

```bash
# Edgar Tools Configuration
export EDGAR_IDENTITY="Your Name your.email@company.com"
export EDGAR_ACCESS_MODE="NORMAL"
export EDGAR_USE_LOCAL_DATA="True"
export EDGAR_LOCAL_DATA_DIR="$HOME/.edgar"
```

## Data Management

### Local Storage Benefits

When `EDGAR_USE_LOCAL_DATA="True"`:

1. **Caching**: HTTP responses cached locally
2. **Offline Access**: Previously accessed data available offline
3. **Performance**: Faster subsequent access to same data
4. **Reduced API Calls**: Less load on SEC servers

### Storage Space Considerations

Typical storage usage:
- **Company submissions**: ~100MB for major companies
- **Company facts**: ~50MB for major companies  
- **HTTP cache**: Varies based on usage
- **Individual filings**: 1-10MB each

## Troubleshooting Configuration

### Check Current Configuration

```python
import os
from edgar.core import get_identity

# Check identity
print(f"Identity: {get_identity()}")

# Check access mode
print(f"Access Mode: {os.getenv('EDGAR_ACCESS_MODE', 'NORMAL')}")

# Check local data settings
print(f"Use Local Data: {os.getenv('EDGAR_USE_LOCAL_DATA', 'False')}")
print(f"Data Directory: {os.getenv('EDGAR_LOCAL_DATA_DIR', '~/.edgar')}")

# Check SSL verification
print(f"Verify SSL: {os.getenv('EDGAR_VERIFY_SSL', 'true')}")
```

### Common Issues

#### Identity Not Set
```python
# Error: No identity set
# Solution:
set_identity("Your Name your.email@company.com")
```

#### Permission Errors
```bash
# Error: Permission denied writing to ~/.edgar
# Solution: Check directory permissions or use custom directory
export EDGAR_LOCAL_DATA_DIR="/tmp/edgar"
```

#### SSL Verification Errors
```bash
# Error: SSL certificate verification failed
# Solution: Disable SSL verification (only if safe)
export EDGAR_VERIFY_SSL="false"
```

#### Connection Timeouts
```bash
# Error: Connection timeouts in slow network
# Solution: Use more conservative settings
export EDGAR_ACCESS_MODE="CAUTION"
```

## Security Best Practices

1. **Always set EDGAR_IDENTITY** - Required for SEC compliance
2. **Keep SSL verification enabled** - Only disable in controlled environments
3. **Secure data directory** - Ensure appropriate file permissions
4. **Use least-privilege access** - Don't run with unnecessary elevated permissions
5. **Monitor data usage** - Be aware of local storage space consumption

## Docker Configuration

For containerized deployments:

```dockerfile
# Dockerfile
ENV EDGAR_IDENTITY="Container App app@company.com"
ENV EDGAR_ACCESS_MODE="CAUTION"
ENV EDGAR_USE_LOCAL_DATA="True"
ENV EDGAR_LOCAL_DATA_DIR="/app/edgar_data"

# Create data directory
RUN mkdir -p /app/edgar_data
VOLUME /app/edgar_data
```

## Configuration Validation

Validate your configuration before running analysis:

```python
from edgar import Company
import os

def validate_config():
    """Validate EdgarTools configuration."""
    issues = []
    
    # Check identity
    try:
        from edgar.core import get_identity
        identity = get_identity()
        if not identity:
            issues.append("EDGAR_IDENTITY not set")
        elif "@" not in identity:
            issues.append("EDGAR_IDENTITY should include email")
    except:
        issues.append("Cannot retrieve EDGAR_IDENTITY")
    
    # Check data directory
    if os.getenv('EDGAR_USE_LOCAL_DATA', 'False').lower() in ['true', '1']:
        data_dir = os.getenv('EDGAR_LOCAL_DATA_DIR', '~/.edgar')
        expanded_dir = os.path.expanduser(data_dir)
        if not os.path.exists(expanded_dir):
            try:
                os.makedirs(expanded_dir, exist_ok=True)
            except:
                issues.append(f"Cannot create data directory: {data_dir}")
    
    # Test basic functionality
    try:
        company = Company("AAPL")
        print(f"✓ Successfully created company: {company.name}")
    except Exception as e:
        issues.append(f"Basic functionality test failed: {e}")
    
    if issues:
        print("Configuration Issues:")
        for issue in issues:
            print(f"  ❌ {issue}")
        return False
    else:
        print("✓ Configuration validated successfully")
        return True

# Run validation
validate_config()
```

## See Also

- **[Installation Guide](installation.md)** - Getting started with EdgarTools
- **[Quick Start](quickstart.md)** - Your first analysis
- **[Performance Best Practices](resources/performance.md)** - Optimization tips
- **[Troubleshooting](resources/troubleshooting.md)** - Common issues and solutions