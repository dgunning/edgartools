# Storage Management Guide

EdgarTools provides comprehensive tools to manage, analyze, and optimize your local SEC filing storage.

## Overview

The storage management module provides:

- **📊 Storage Analytics**: View size, file counts, compression ratios
- **🔍 Filing Availability**: Check which filings are available offline
- **💡 Smart Analysis**: Get optimization recommendations
- **🛠️ Optimization Tools**: Compress files, clear caches, remove old data

All functions are available from the main `edgar` package:

```python
from edgar import (
    storage_info,           # View storage statistics
    check_filing,           # Check single filing availability
    check_filings_batch,    # Check multiple filings
    availability_summary,   # Get availability summary
    analyze_storage,        # Analyze with recommendations
    optimize_storage,       # Compress uncompressed files
    cleanup_storage,        # Remove old filings
    clear_cache,           # Clear HTTP caches
)
```

## Storage Analytics

### View Storage Information

Get an overview of your local EdgarTools storage:

```python
from edgar import storage_info

# Get storage statistics
info = storage_info()
print(info)  # Beautiful Rich panel display
```

Output:
```
┌─────────────────────────────────────────────────────────────┐
│                   EdgarTools Local Storage                   │
├─────────────────────────────────────────────────────────────┤
│ 📊 Total Size:        179.23 GB (uncompressed)              │
│ 💾 Disk Usage:        53.77 GB (compressed)                 │
│ 🗜️ Space Saved:       125.46 GB (70.0%)                     │
│ 📁 Total Files:       22,847                                │
│ 📄 Filings:           18,234                                │
│ 📍 Location:          /Users/you/.edgar                     │
│                                                             │
│   filings:            18,234 files                          │
│   companyfacts:       3,456 files                           │
│   submissions:        892 files                             │
│   _cache:             265 files                             │
└─────────────────────────────────────────────────────────────┘
```

### Access Storage Data Programmatically

```python
from edgar import storage_info

info = storage_info()

# Check size
if info.total_size_compressed > 50e9:  # More than 50 GB
    print(f"Storage is large: {info.total_size_compressed / 1e9:.1f} GB")

# Check compression ratio
print(f"Compression savings: {info.compression_ratio:.1%}")

# Check file counts by type
print(f"Filings: {info.by_type.get('filings', 0):,}")
print(f"Company facts: {info.by_type.get('companyfacts', 0):,}")
```

### Force Refresh

Storage info is cached for 60 seconds for performance. To force a fresh scan:

```python
info = storage_info(force_refresh=True)
```

## Filing Availability

### Check Single Filing

Check if a specific filing is available in local storage:

```python
from edgar import Company, check_filing

# Get a filing
company = Company("AAPL")
filing = company.latest("10-K")

# Check availability
if check_filing(filing):
    print("✓ Available offline")
else:
    print("✗ Need to download")
```

### Check Multiple Filings

Efficiently check availability for many filings:

```python
from edgar import get_filings, check_filings_batch

# Get some filings
filings = get_filings(form="10-K", filing_date="2024-01-01").sample(100)

# Check availability
availability = check_filings_batch(filings)

# Filter to available filings
available_filings = [f for f in filings if availability[f.accession_no]]
print(f"Found {len(available_filings)} filings offline")
```

### Get Availability Summary

Get a quick summary string:

```python
from edgar import get_filings, availability_summary

filings = get_filings(filing_date="2024-01-15").head(100)
print(availability_summary(filings))
# Output: "45 of 100 filings available offline (45%)"
```

## Storage Analysis

### Analyze Storage with Recommendations

Get intelligent analysis and optimization suggestions:

```python
from edgar import analyze_storage

analysis = analyze_storage()
print(analysis)
```

Output:
```
┌─────────────────────────────────────────────────────────────┐
│                      Storage Analysis                        │
├─────────────────────────────────────────────────────────────┤
│ 📊 Current Size:      53.77 GB                              │
│ 💾 Total Files:       22,847                                │
│ 💰 Potential Savings: 12.34 GB                              │
│                                                             │
│ ⚠️  Issues Found:                                           │
│   • Found 1,234 uncompressed files (17.63 GB)              │
│   • Cache directories contain 265 files (2.15 GB)          │
│                                                             │
│ 💡 Recommendations:                                         │
│   • Run optimize_storage() to compress files (~12.3 GB)    │
│   • Run clear_cache() to free up 2.2 GB                    │
│   • Consider cleanup_storage(days=365) to remove           │
│     456 old filings (8.9 GB)                               │
└─────────────────────────────────────────────────────────────┘
```

### Use Analysis Programmatically

```python
from edgar import analyze_storage

analysis = analyze_storage()

# Check for issues
if analysis.issues:
    print("Issues found:")
    for issue in analysis.issues:
        print(f"  - {issue}")

# Check potential savings
if analysis.potential_savings_bytes > 1e9:  # More than 1 GB
    print(f"Can save {analysis.potential_savings_bytes / 1e9:.1f} GB")

# Follow recommendations
for rec in analysis.recommendations:
    print(f"✓ {rec}")
```

## Storage Optimization

### Compress Files

Compress uncompressed files to save disk space:

```python
from edgar import optimize_storage

# First, see what would happen (dry run)
result = optimize_storage(dry_run=True)
print(f"Would compress {result['files_compressed']} files")
print(f"Would save {result['bytes_saved'] / 1e9:.1f} GB")

# Then do it for real
result = optimize_storage(dry_run=False)
print(f"Compressed {result['files_compressed']} files")
print(f"Saved {result['bytes_saved'] / 1e9:.1f} GB")
```

**Note**: The library transparently handles compressed files, so `.json.gz` files are read exactly like `.json` files.

### Clear Caches

Clear HTTP cache directories to free up space:

```python
from edgar import clear_cache

# Preview what would be cleared
result = clear_cache(dry_run=True)
print(f"Would free {result['bytes_freed'] / 1e9:.1f} GB")

# Clear the cache
result = clear_cache(dry_run=False)
print(f"Cleared {result['files_deleted']} cache files")
print(f"Freed {result['bytes_freed'] / 1e9:.1f} GB")
```

**Note**: Cache is automatically rebuilt on demand, so this is safe to run anytime.

### Remove Old Filings

Remove filings older than a specified number of days:

```python
from edgar import cleanup_storage

# Preview what would be deleted (1 year old)
result = cleanup_storage(days=365, dry_run=True)
print(f"Would delete {result['files_deleted']} files")
print(f"Would free {result['bytes_freed'] / 1e9:.1f} GB")

# Remove filings older than 2 years
result = cleanup_storage(days=730, dry_run=False)
print(f"Deleted {result['files_deleted']} old filings")
print(f"Freed {result['bytes_freed'] / 1e9:.1f} GB")
```

**Note**: This only removes filings from the `filings/` directory. Company facts and submissions are not affected.

## Complete Workflows

### Weekly Maintenance Routine

```python
from edgar import analyze_storage, optimize_storage, clear_cache

# Analyze storage
analysis = analyze_storage()
print(analysis)

# Optimize if savings are substantial
if analysis.potential_savings_bytes > 5e9:  # More than 5 GB
    print("\nOptimizing storage...")
    optimize_storage(dry_run=False)

# Clear cache if it's large
cache_info = analysis.storage_info.by_type.get('_cache', 0)
if cache_info > 1e9:  # More than 1 GB
    print("\nClearing cache...")
    clear_cache(dry_run=False)

print("\n✓ Maintenance complete!")
```

### Before Large Download

Check available space before downloading many filings:

```python
from edgar import storage_info, get_filings, download_filings

# Check current storage
info = storage_info()
print(f"Current usage: {info.total_size_compressed / 1e9:.1f} GB")

# Estimate download size (rough: 50 KB per filing)
filings = get_filings(form="10-K", filing_date="2024-01-01")
estimated_size = len(filings) * 50_000  # 50 KB per filing

print(f"Estimated download: {estimated_size / 1e9:.1f} GB")

# Download if there's space
if estimated_size < 10e9:  # Less than 10 GB
    download_filings(filings)
else:
    print("⚠️  Large download - consider filtering filings")
```

### Offline Research Workflow

```python
from edgar import Company, check_filing, availability_summary

# Research a company offline
company = Company("TSLA")
filings = company.get_filings(form="10-K")

# Check what's available offline
print(availability_summary(list(filings)))

# Work with available filings only
available = [f for f in filings if check_filing(f)]
for filing in available:
    print(f"✓ {filing.form} - {filing.filing_date}")
    # Process filing...
```

### Automated Cleanup Script

```python
from edgar import analyze_storage, cleanup_storage, clear_cache
from datetime import datetime

def auto_cleanup(max_age_days=365, max_cache_gb=2):
    """
    Automatic cleanup based on policies.
    """
    print(f"Running storage cleanup - {datetime.now()}")

    # Analyze first
    analysis = analyze_storage()
    print(f"Current size: {analysis.storage_info.total_size_compressed / 1e9:.1f} GB")

    # Clear large caches
    cache_size = sum(
        size for name, size in analysis.storage_info.by_type.items()
        if name.startswith('_')
    )
    if cache_size > max_cache_gb * 1e9:
        print(f"\nClearing {cache_size / 1e9:.1f} GB cache...")
        result = clear_cache(dry_run=False)
        print(f"✓ Freed {result['bytes_freed'] / 1e9:.1f} GB")

    # Remove old filings
    print(f"\nRemoving filings older than {max_age_days} days...")
    result = cleanup_storage(days=max_age_days, dry_run=False)
    print(f"✓ Deleted {result['files_deleted']} files")
    print(f"✓ Freed {result['bytes_freed'] / 1e9:.1f} GB")

    # Final summary
    info = storage_info(force_refresh=True)
    print(f"\nFinal size: {info.total_size_compressed / 1e9:.1f} GB")

# Run weekly
auto_cleanup(max_age_days=365, max_cache_gb=2)
```

## Safety Features

All destructive operations default to **dry-run mode** for safety:

```python
# These are all safe by default (no changes made)
optimize_storage()              # dry_run=True by default
cleanup_storage()               # dry_run=True by default
clear_cache()                   # dry_run=True by default

# Explicitly enable changes
optimize_storage(dry_run=False)
cleanup_storage(dry_run=False)
clear_cache(dry_run=False)
```

## Performance Notes

- **storage_info()**: Results cached for 60 seconds to avoid repeated filesystem scans
- **check_filings_batch()**: Much faster than checking filings individually
- **analyze_storage()**: Can take a few seconds on large storage directories

## Best Practices

1. **Always dry-run first**: Preview changes before making them
2. **Regular analysis**: Run `analyze_storage()` weekly to catch issues early
3. **Compress files**: Run `optimize_storage()` after bulk downloads
4. **Clear caches**: Safe to run anytime, cache rebuilds automatically
5. **Careful with cleanup**: Set appropriate `days` parameter for your needs
6. **Monitor size**: Check `storage_info()` regularly if doing bulk downloads

## FAQ

**Q: Will compressed files still work with the library?**
A: Yes! EdgarTools transparently handles `.gz` files. You won't notice any difference.

**Q: How much space does compression save?**
A: Typically 70% savings on text-based files (.json, .xml, .txt, .nc).

**Q: Is it safe to clear the cache?**
A: Yes, cache rebuilds automatically on demand. No data loss.

**Q: What happens if I accidentally delete important filings?**
A: Filings can be re-downloaded from SEC. Use `dry_run=True` first to preview.

**Q: Can I undo cleanup_storage()?**
A: No, deleted files cannot be recovered. Use dry-run mode first!

**Q: How often should I run maintenance?**
A: Weekly `analyze_storage()` is sufficient for most users. Monthly optimization recommended.

**Q: Does this affect downloaded company facts or submissions?**
A: `cleanup_storage()` only affects filings. Company facts and submissions are preserved.

## API Reference

See individual function docstrings for complete API details:

```python
help(storage_info)
help(check_filing)
help(check_filings_batch)
help(availability_summary)
help(analyze_storage)
help(optimize_storage)
help(cleanup_storage)
help(clear_cache)
```
