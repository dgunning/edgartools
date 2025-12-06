# Cloud Storage Testing Plan

Testing plan for the cloud storage feature (`feature/cloud-storage` branch).

## Overview

The cloud storage feature provides:
- Native cloud storage via fsspec (`use_cloud_storage()`)
- Batch upload from local to cloud (`sync_to_cloud()`)
- Download with automatic cloud upload (`download_filings(upload_to_cloud=True)`)
- Support for S3, GCS, Azure, R2, MinIO

**Key files:**
- `edgar/filesystem.py` - Core implementation
- `edgar/storage.py` - Integration with download_filings()
- `tests/test_filesystem.py` - Test suite (27+ tests)

---

## Phase 1: Run Existing Tests

```bash
# Run the filesystem test suite
pytest tests/test_filesystem.py -v

# Check what's covered
pytest tests/test_filesystem.py --collect-only
```

**Existing coverage:** 27+ tests covering local operations, configuration, sync_to_cloud mocking

---

## Phase 2: Local Integration Tests (No Cloud Required)

| Test | Command | What It Validates |
|------|---------|-------------------|
| Local EdgarPath ops | `pytest tests/test_filesystem.py::TestEdgarPathLocal -v` | File I/O, gzip, paths |
| Cloud config validation | `pytest tests/test_filesystem.py::TestUseCloudStorage -v` | URI parsing, errors |
| Sync dry-run | `pytest tests/test_filesystem.py::TestSyncToCloud -v` | Batch logic, patterns |

---

## Phase 3: Manual Cloud Provider Testing

### Prerequisites

**Pre-release testing (from local checkout):**
```bash
# From the edgartools project directory
pip install -e ".[s3]"    # For S3/R2/MinIO
pip install -e ".[gcs]"   # For Google Cloud
pip install -e ".[azure]" # For Azure

# Or install all cloud extras at once
pip install -e ".[s3,gcs,azure]"
```

**After release:**
```bash
pip install "edgartools[s3]"    # For S3/R2/MinIO
pip install "edgartools[gcs]"   # For Google Cloud
pip install "edgartools[azure]" # For Azure
```

### 3a. MinIO (Local Docker - Recommended First)

Start MinIO locally:
```bash
docker run -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```

Create bucket via console at http://localhost:9001 (login: minioadmin/minioadmin)

Test script:
```python
import edgar

# Configure for MinIO
edgar.use_cloud_storage(
    's3://edgar-test/',
    client_kwargs={
        'endpoint_url': 'http://localhost:9000',
        'aws_access_key_id': 'minioadmin',
        'aws_secret_access_key': 'minioadmin'
    }
)

# Test 1: Check configuration
assert edgar.is_cloud_storage_enabled()

# Test 2: Sync existing local filings (dry run)
result = edgar.sync_to_cloud(dry_run=True)
print(f"Would upload: {result['uploaded']} files")

# Test 3: Actual sync (small batch)
result = edgar.sync_to_cloud(pattern='filings/2025*', batch_size=5)
print(result)

# Test 4: Download with cloud upload
edgar.download_filings('2025-01-20', upload_to_cloud=True)
```

### 3b. AWS S3

```python
import edgar

# Using default credentials (~/.aws/credentials or env vars)
edgar.use_cloud_storage('s3://your-bucket/edgar/')

# Or with explicit credentials
edgar.use_cloud_storage(
    's3://your-bucket/edgar/',
    client_kwargs={
        'aws_access_key_id': 'YOUR_KEY',
        'aws_secret_access_key': 'YOUR_SECRET',
        'region_name': 'us-east-1'
    }
)
```

### 3c. Cloudflare R2

```python
import edgar

edgar.use_cloud_storage(
    's3://your-r2-bucket/edgar/',
    client_kwargs={
        'endpoint_url': 'https://ACCOUNT_ID.r2.cloudflarestorage.com',
        'aws_access_key_id': 'YOUR_R2_ACCESS_KEY',
        'aws_secret_access_key': 'YOUR_R2_SECRET_KEY',
        'region_name': 'auto'  # Required for R2
    }
)
```

### 3d. Google Cloud Storage

```python
import edgar

# Using default credentials (gcloud auth)
edgar.use_cloud_storage('gs://your-bucket/edgar/')

# Or with project specification
edgar.use_cloud_storage(
    'gs://your-bucket/edgar/',
    client_kwargs={'project': 'your-project-id'}
)
```

### 3e. Azure Blob Storage

```python
import edgar

edgar.use_cloud_storage(
    'az://container/edgar/',
    client_kwargs={
        'account_name': 'your-account',
        'account_key': 'YOUR_ACCOUNT_KEY'
    }
)
```

---

## Phase 4: Critical Path Tests

| Scenario | Steps | Expected Result |
|----------|-------|-----------------|
| **Read after write** | `sync_to_cloud()` then `Company("AAPL").get_filings()` | Reads from cloud |
| **Gzip transparency** | Upload `.nc.gz` file, read via EdgarPath | Decompresses automatically |
| **Overwrite behavior** | `sync_to_cloud(overwrite=False)` twice | Second run skips existing |
| **Error handling** | Invalid credentials | Clear error message, no crash |
| **Disable cloud** | `use_cloud_storage(disable=True)` | Falls back to local |

### Test Script

```python
import edgar
from edgar.filesystem import reset_filesystem, EdgarPath

def test_read_after_write():
    """Verify data written to cloud can be read back"""
    # Sync some filings
    result = edgar.sync_to_cloud(pattern='filings/2025-01*')
    assert result['uploaded'] > 0 or result['skipped'] > 0

    # Read back via Company API
    company = edgar.Company("AAPL")
    filings = company.get_filings(form="10-K")
    assert len(filings) > 0
    print("✓ Read after write works")

def test_overwrite_skip():
    """Verify overwrite=False skips existing files"""
    # First sync
    result1 = edgar.sync_to_cloud(pattern='filings/2025-01-15*')

    # Second sync should skip
    result2 = edgar.sync_to_cloud(pattern='filings/2025-01-15*', overwrite=False)
    assert result2['skipped'] >= result1['uploaded']
    assert result2['uploaded'] == 0
    print("✓ Skip existing works")

def test_disable_cloud():
    """Verify cloud can be disabled"""
    edgar.use_cloud_storage(disable=True)
    assert not edgar.is_cloud_storage_enabled()
    print("✓ Disable works")
```

---

## Phase 5: Edge Cases

```python
import edgar

# 1. Empty pattern - should handle gracefully
result = edgar.sync_to_cloud(pattern='nonexistent/*')
assert result['uploaded'] == 0
assert result['failed'] == 0

# 2. Large batch - test concurrency
result = edgar.sync_to_cloud(batch_size=50)

# 3. Invalid URI scheme
try:
    edgar.use_cloud_storage('ftp://invalid/')
except ValueError as e:
    print(f"✓ Invalid scheme rejected: {e}")

# 4. Missing credentials
try:
    edgar.use_cloud_storage('s3://bucket-without-access/')
    edgar.sync_to_cloud()
except Exception as e:
    print(f"✓ Auth error handled: {e}")

# 5. Thread safety - concurrent access
import threading
results = []

def sync_worker():
    r = edgar.sync_to_cloud(pattern='filings/2025-01-15*', dry_run=True)
    results.append(r)

threads = [threading.Thread(target=sync_worker) for _ in range(5)]
for t in threads:
    t.start()
for t in threads:
    t.join()

assert len(results) == 5
print("✓ Thread safety works")
```

---

## Phase 6: Performance Benchmarks

```python
import time
import edgar

def benchmark_sync(pattern='filings/2025*'):
    """Measure upload performance"""
    start = time.time()
    result = edgar.sync_to_cloud(pattern=pattern)
    elapsed = time.time() - start

    total_files = result['uploaded'] + result['skipped']
    if elapsed > 0 and result['uploaded'] > 0:
        rate = result['uploaded'] / elapsed
        print(f"Uploaded: {result['uploaded']} files in {elapsed:.1f}s ({rate:.1f} files/sec)")

    return result, elapsed

def benchmark_read_latency():
    """Compare local vs cloud read latency"""
    from edgar.filesystem import EdgarPath

    # Pick a known file
    test_path = 'filings/2025-01-15/0000320193-25-000001.nc'

    # Cloud read
    start = time.time()
    path = EdgarPath(test_path)
    content = path.read_text()
    cloud_time = time.time() - start

    print(f"Cloud read: {cloud_time*1000:.0f}ms for {len(content)/1024:.0f}KB")

# Run benchmarks
benchmark_sync('filings/2025-01*')
benchmark_read_latency()
```

---

## Test Script Template

Save as `scripts/test_cloud_storage.py`:

```python
#!/usr/bin/env python3
"""
Cloud storage manual testing script.

Usage:
    python scripts/test_cloud_storage.py minio    # Test with local MinIO
    python scripts/test_cloud_storage.py s3       # Test with AWS S3
    python scripts/test_cloud_storage.py r2       # Test with Cloudflare R2
"""
import sys
import edgar
from edgar.filesystem import reset_filesystem

def setup_minio():
    """Configure for local MinIO"""
    reset_filesystem()
    edgar.use_cloud_storage(
        's3://edgar-test/',
        client_kwargs={
            'endpoint_url': 'http://localhost:9000',
            'aws_access_key_id': 'minioadmin',
            'aws_secret_access_key': 'minioadmin'
        }
    )
    print("Configured for MinIO (localhost:9000)")

def setup_s3():
    """Configure for AWS S3 (uses default credentials)"""
    reset_filesystem()
    bucket = input("Enter S3 bucket name: ")
    edgar.use_cloud_storage(f's3://{bucket}/edgar/')
    print(f"Configured for S3 ({bucket})")

def setup_r2():
    """Configure for Cloudflare R2"""
    reset_filesystem()
    account_id = input("Enter R2 account ID: ")
    bucket = input("Enter R2 bucket name: ")
    access_key = input("Enter R2 access key: ")
    secret_key = input("Enter R2 secret key: ")

    edgar.use_cloud_storage(
        f's3://{bucket}/edgar/',
        client_kwargs={
            'endpoint_url': f'https://{account_id}.r2.cloudflarestorage.com',
            'aws_access_key_id': access_key,
            'aws_secret_access_key': secret_key,
            'region_name': 'auto'
        }
    )
    print(f"Configured for R2 ({bucket})")

def run_tests():
    """Run basic validation tests"""
    print("\n--- Running Tests ---\n")

    # Test 1: Configuration
    assert edgar.is_cloud_storage_enabled(), "Cloud storage not enabled"
    print("✓ Cloud storage enabled")

    # Test 2: Dry run sync
    result = edgar.sync_to_cloud(dry_run=True)
    print(f"✓ Dry run: would upload {result['uploaded']} files")

    # Test 3: Small actual sync
    result = edgar.sync_to_cloud(pattern='filings/2025-01*', batch_size=5)
    print(f"✓ Sync complete: {result['uploaded']} uploaded, {result['skipped']} skipped, {result['failed']} failed")

    if result['failed'] > 0:
        print(f"  Errors: {result['errors']}")

    # Test 4: Disable and re-enable
    edgar.use_cloud_storage(disable=True)
    assert not edgar.is_cloud_storage_enabled()
    print("✓ Cloud storage disabled")

    print("\n--- All Tests Passed ---")

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    provider = sys.argv[1].lower()

    if provider == 'minio':
        setup_minio()
    elif provider == 's3':
        setup_s3()
    elif provider == 'r2':
        setup_r2()
    else:
        print(f"Unknown provider: {provider}")
        print("Supported: minio, s3, r2")
        sys.exit(1)

    run_tests()

if __name__ == '__main__':
    main()
```

---

## Summary

| Phase | Effort | Cloud Required | Priority |
|-------|--------|----------------|----------|
| 1. Existing tests | 5 min | No | High |
| 2. Local integration | 10 min | No | High |
| 3. MinIO (Docker) | 30 min | Local only | High |
| 4. Critical paths | 30 min | Yes | High |
| 5. Edge cases | 30 min | Yes | Medium |
| 6. Performance | 15 min | Yes | Low |

**Recommended order:** 1 → 2 → 3 (MinIO) → 4 → 5 → 6

**Pass criteria:**
- All existing tests pass
- MinIO integration works end-to-end
- At least one real cloud provider tested
- No data corruption (read matches write)
