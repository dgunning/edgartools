# Local Storage Guide

**edgartools** is designed for interactive queries against **SEC Edgar**, which means it normally makes HTTP requests to the SEC website to retrieve data. For example, when you call `company.submissions` or `filing.attachments`, it makes a request to the SEC.

There are times when you want to minimize or eliminate these requests:

1. **Performance**: Speed up processing by avoiding network requests
2. **Offline usage**: Work without internet access or in restricted environments
3. **Bandwidth efficiency**: Reduce data usage and respect SEC rate limits
4. **Development**: Use cached data for testing and development

**edgartools** provides comprehensive local storage capabilities to address these needs.

## Supported Local Data Types

| Data Type               | Description                                                        |
|-------------------------|--------------------------------------------------------------------|
| **Company Submissions** | Company metadata and their 1000 most recent filings              |
| **Company Facts**       | Standardized company financial facts from XBRL filings            |
| **Filing Attachments**  | Complete filing documents with all attachments                    |
| **Reference Data**      | Company and mutual fund tickers, exchanges, and other lookups     |

## Local Data Directory

### Default Location
The default local data directory is:
```
<USER_HOME>/.edgar
```

### Setting the Directory

You can set the local data directory in several ways:

**Method 1: Environment Variable**
```bash
export EDGAR_LOCAL_DATA_DIR="/path/to/local/data"
```

**Method 2: Programmatic (New)**
```python
from edgar import set_local_storage_path
import os

# Create the directory first
os.makedirs("/tmp/edgar_data", exist_ok=True)

# Set the path
set_local_storage_path("/tmp/edgar_data")
```

**Method 3: One-Step Setup (New)**
```python
from edgar import use_local_storage
import os

# Create and set directory, enable local storage in one call
os.makedirs("/tmp/edgar_data", exist_ok=True)
use_local_storage("/tmp/edgar_data")
```

## Enabling Local Storage

### Basic Usage

```python
from edgar import use_local_storage
import os

# Create directory
os.makedirs("~/Documents/edgar", exist_ok=True)

# Set path and enable in one call
use_local_storage("~/Documents/edgar")
```

### All Supported Patterns

```python
# 1. BACKWARD COMPATIBLE
use_local_storage(True)    # Enable
use_local_storage(False)   # Disable  
use_local_storage()        # Enable (default)

# 2. NEW INTUITIVE SYNTAX
use_local_storage("/tmp/edgar_data")        # Path as string
use_local_storage("~/Documents/edgar")      # Tilde expansion
use_local_storage(Path.home() / "edgar")    # Path object

# 3. ADVANCED CONTROL
use_local_storage("/tmp/edgar", True)       # Set path and enable
use_local_storage("/tmp/edgar", False)      # Set path but keep disabled
```

### Checking Status

```python
from edgar import is_using_local_storage

if is_using_local_storage():
    print("Local storage is enabled")
else:
    print("Using remote SEC data")
```

## Downloading Data to Local Storage

### Download Bulk SEC Data

You can download bulk SEC data using the `download_edgar_data()` function:

```python
from edgar import download_edgar_data

# Download all data types (submissions, facts, reference data)
download_edgar_data()

# Download only specific data types
download_edgar_data(
    submissions=True,   # Company metadata and recent filings
    facts=True,        # Company financial facts
    reference=True     # Tickers, exchanges, etc.
)
```

### Download Complete Filings

Download individual filings with all attachments using `download_filings()`:

```python
from edgar import download_filings

# Download all filings for a specific date
download_filings("2025-01-15")

# Download filings for a date range
download_filings("2025-01-01:2025-01-15")

# Download from a start date onwards
download_filings("2025-01-01:")

# Download up to an end date
download_filings(":2025-01-15")
```

**Note:** Downloaded filings are stored in `EDGAR_LOCAL_DATA_DIR/filings/YYYYMMDD/`. When local storage is enabled, edgartools automatically checks local storage first before making SEC requests.

## Complete Workflow Examples

### Example 1: Quick Setup for Development

```python
from edgar import use_local_storage, download_edgar_data
import os

# Setup local storage in one command
os.makedirs("~/edgar_dev", exist_ok=True)
use_local_storage("~/edgar_dev")

# Download essential data
download_edgar_data(submissions=True, reference=True)

# Now all queries use local data when available
from edgar import Company
apple = Company("AAPL")  # Uses local data
```

### Example 2: High-Performance Analysis Setup

```python
from edgar import use_local_storage, download_filings, get_filings
import os

# Setup high-performance storage
os.makedirs("/tmp/edgar_fast", exist_ok=True)
use_local_storage("/tmp/edgar_fast")

# Download specific filings for analysis
filings = get_filings(form="10-K", year=2024)
download_filings(filings=filings)

# All subsequent operations are lightning fast
for filing in filings:
    financial_data = filing.xbrl()  # Instant from local storage
```

### Example 3: Offline Research Environment

```python
from edgar import use_local_storage, download_edgar_data, download_filings
import os

# Setup offline-capable environment
os.makedirs("~/research/edgar_offline", exist_ok=True)
use_local_storage("~/research/edgar_offline")

# Download comprehensive dataset
download_edgar_data()  # All bulk data
download_filings("2024-01-01:2024-12-31")  # Full year of filings

# Now works completely offline
from edgar import Company, get_filings
companies = get_filings(form="10-K", year=2024)  # From local storage
```

## Filtering Downloads

### Download Specific Filings

Instead of downloading all filings, you can filter to download only what you need:

```python
from edgar import get_filings, download_filings

# Get filings with filters
filings = get_filings(form="10-K", year=2024).filter(exchange="NYSE")

# Download only these filtered filings
download_filings(filings=filings)
```

### Advanced Filtering Examples

```python
# Download only tech companies' 10-K filings
tech_filings = (get_filings(form="10-K", year=2024)
                .filter(exchange=["NASDAQ", "NYSE"])
                
download_filings(filings=tech_filings)

# Download recent 8-K filings for specific analysis
recent_8k = get_filings(form="8-K", filing_date="2025-01-01:")
download_filings(filings=recent_8k)
```

## Performance Considerations

### Storage Space

Different data types require different amounts of storage:

| Data Type        | Typical Size | Description                    |
|------------------|--------------|--------------------------------|
| Reference Data   | ~50 MB       | Tickers, exchanges, mappings   |
| Company Facts    | ~2 GB        | Compressed financial facts     |
| Submissions      | ~5 GB        | Company metadata and filings   |
| Daily Filings    | ~100-500 MB  | All filings for one day        |

### Download Times

- **Reference data**: 1-2 seconds
- **Company facts**: 2-3 minutes
- **Company submissions**: 2-3 minutes 
- **Daily filings**: 3-15 minutes depending on volume and time of day

### Compression

Filings are automatically compressed to save space. The default compression level is set to 6, but you can adjust it to 9 for maximum compression:

```python
# Enable compression during download
download_filings("2025-01-15", compression_level=9)
```

## Directory Structure

When using local storage, data is organized as follows:

```
EDGAR_LOCAL_DATA_DIR/
├── reference/              # Ticker and exchange data
│   ├── company_tickers.json
│   ├── ticker.txt
│   └── ...
├── companyfacts/           # Company financial facts
│   └── CIK[0-9]*.json
├── submissions/            # Company submission data  
│   └── CIK[0-9]*.json
└── filings/               # Individual filing documents
    ├── 20250115/          # Filings by date
    │   ├── filing1.nc     # SGML filing documents
    │   └── filing2.nc.gz  # Compressed filings
    └── ...
```

## Best Practices

### 1. Start Small

```python
# Begin with reference data only
use_local_storage("~/edgar_test")
download_edgar_data(submissions=False, facts=False, reference=True)
```

### 2. Use Appropriate Storage

```python
# Fast SSD for high-performance analysis
use_local_storage("/fast_ssd/edgar_data")

# Network storage for shared team access
use_local_storage("/shared/team/edgar_data")
```

### 3. Monitor Storage Usage

```python
from edgar.core import get_edgar_data_directory
import shutil

storage_path = get_edgar_data_directory()
total, used, free = shutil.disk_usage(storage_path)
print(f"Storage usage: {used // (1024**3)} GB used, {free // (1024**3)} GB free")
```

### 4. Incremental Updates

```python
# Download only recent filings regularly
from datetime import datetime, timedelta

recent_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
download_filings(f"{recent_date}:")
```

## Troubleshooting

### Common Issues

**Path doesn't exist:**
```python
# ❌ This will fail
use_local_storage("/nonexistent/path")

# ✅ Create directory first
import os
os.makedirs("/tmp/edgar", exist_ok=True)
use_local_storage("/tmp/edgar")
```

**Insufficient space:**
```python
# Check available space before large downloads
import shutil
_, _, free = shutil.disk_usage("/tmp")
if free < 10 * (1024**3):  # 10 GB
    print("Warning: Less than 10 GB free space")
```

**Mixed local/remote data:**
```python
# Ensure consistent data source
from edgar import is_using_local_storage

if is_using_local_storage():
    print("Using local storage")
else:
    print("Using remote SEC data")
    # Enable if needed: use_local_storage(True)
```

## Migration and Backup

### Moving Local Storage

```python
# Old location
old_path = "~/old_edgar"

# New location  
new_path = "/new/location/edgar"
os.makedirs(new_path, exist_ok=True)

# Move data (outside Python)
# cp -r ~/old_edgar/* /new/location/edgar/

# Update edgartools
use_local_storage(new_path)
```

### Backup Strategy

```python
# Create backup of critical data
import shutil
from datetime import datetime

backup_name = f"edgar_backup_{datetime.now().strftime('%Y%m%d')}"
shutil.copytree(get_edgar_data_directory(), f"/backups/{backup_name}")
```

## Summary

The enhanced local storage system in edgartools provides:

### Key Functions
- **`use_local_storage()`**: Enable/disable local storage with optional path setting
- **`set_local_storage_path()`**: Set storage directory path  
- **`is_using_local_storage()`**: Check current status
- **`download_edgar_data()`**: Download bulk SEC data
- **`download_filings()`**: Download individual filings

### Benefits
- **Dramatic performance improvements**: 10-100x faster than remote requests
- **Offline capability**: Work without internet connectivity
- **Bandwidth efficiency**: Reduce network usage and respect SEC limits
- **Flexible configuration**: Multiple ways to configure and use
- **Comprehensive data**: Support for all major SEC data types

### Quick Start
```python
import os
from edgar import use_local_storage, download_edgar_data

# Setup in one line
os.makedirs("~/edgar", exist_ok=True)
use_local_storage("~/edgar")

# Download essential data
download_edgar_data()

# All subsequent operations use local storage when available
```

This comprehensive local storage system makes edgartools significantly more efficient for both development and production use cases.

