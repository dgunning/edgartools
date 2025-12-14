#!/usr/bin/env python3
"""
Cloud storage manual testing script.

Usage:
    python scripts/check_cloud_storage.py minio    # Test with local MinIO
    python scripts/check_cloud_storage.py s3       # Test with AWS S3
    python scripts/check_cloud_storage.py r2       # Test with Cloudflare R2

Prerequisites:
    pip install "edgartools[s3]"

For MinIO, start Docker container first:
    docker run -p 9000:9000 -p 9001:9001 \\
      -e MINIO_ROOT_USER=minioadmin \\
      -e MINIO_ROOT_PASSWORD=minioadmin \\
      minio/minio server /data --console-address ":9001"

    Then create bucket 'edgar-test' via http://localhost:9001
"""
import sys
import time

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


def test_configuration():
    """Test 1: Verify cloud storage is configured"""
    assert edgar.is_cloud_storage_enabled(), "Cloud storage not enabled"
    print("✓ Cloud storage enabled")


def test_dry_run():
    """Test 2: Dry run sync"""
    result = edgar.sync_to_cloud(dry_run=True)
    print(f"✓ Dry run: would upload {result['uploaded']} files")
    return result


def test_small_sync():
    """Test 3: Small actual sync"""
    result = edgar.sync_to_cloud(pattern='filings/2025-01*', batch_size=5)
    print(f"✓ Sync complete: {result['uploaded']} uploaded, {result['skipped']} skipped, {result['failed']} failed")

    if result['failed'] > 0:
        print(f"  Errors: {result['errors'][:3]}")  # Show first 3 errors

    return result


def test_skip_existing():
    """Test 4: Verify skip-existing behavior"""
    # Run sync twice - second should skip
    result1 = edgar.sync_to_cloud(pattern='filings/2025-01-15*', batch_size=5)
    result2 = edgar.sync_to_cloud(pattern='filings/2025-01-15*', batch_size=5, overwrite=False)

    if result1['uploaded'] > 0:
        assert result2['skipped'] >= result1['uploaded'], "Should skip previously uploaded files"
        print(f"✓ Skip existing: {result2['skipped']} files skipped")
    else:
        print("✓ Skip existing: (no files to test with)")


def test_disable():
    """Test 5: Disable and verify"""
    edgar.use_cloud_storage(disable=True)
    assert not edgar.is_cloud_storage_enabled()
    print("✓ Cloud storage disabled successfully")


def benchmark_sync(pattern='filings/2025-01*'):
    """Benchmark upload performance"""
    print(f"\n--- Benchmarking sync (pattern={pattern}) ---")

    start = time.time()
    result = edgar.sync_to_cloud(pattern=pattern)
    elapsed = time.time() - start

    if result['uploaded'] > 0:
        rate = result['uploaded'] / elapsed
        print(f"  Uploaded: {result['uploaded']} files in {elapsed:.1f}s ({rate:.1f} files/sec)")
    else:
        print(f"  No files uploaded ({result['skipped']} skipped)")

    return result, elapsed


def run_tests(skip_benchmark=False):
    """Run all validation tests"""
    print("\n" + "=" * 50)
    print("Running Cloud Storage Tests")
    print("=" * 50 + "\n")

    test_configuration()
    test_dry_run()
    test_small_sync()
    test_skip_existing()

    if not skip_benchmark:
        benchmark_sync()

    # Re-enable for disable test, then disable
    # (need to reconfigure since disable clears state)
    print("\n--- Cleanup ---")
    test_disable()

    print("\n" + "=" * 50)
    print("All Tests Passed!")
    print("=" * 50)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    provider = sys.argv[1].lower()
    skip_benchmark = '--skip-benchmark' in sys.argv

    providers = {
        'minio': setup_minio,
        's3': setup_s3,
        'r2': setup_r2,
    }

    if provider not in providers:
        print(f"Unknown provider: {provider}")
        print(f"Supported: {', '.join(providers.keys())}")
        sys.exit(1)

    try:
        providers[provider]()
        run_tests(skip_benchmark=skip_benchmark)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
