"""
Tests for storage management functionality
"""

import pytest
from pathlib import Path
from edgar.storage_management import storage_info, StorageInfo, _scan_storage
from edgar.core import get_edgar_data_directory
import time

@pytest.mark.fast
def test_storage_info_returns_valid_data():
    """Test that storage_info returns StorageInfo with valid data"""
    info = storage_info()

    assert isinstance(info, StorageInfo)
    assert info.total_size_bytes >= 0
    assert info.total_size_compressed >= 0
    assert info.file_count >= 0
    assert info.filing_count >= 0
    assert 0.0 <= info.compression_ratio <= 1.0
    assert isinstance(info.by_type, dict)
    assert isinstance(info.storage_path, Path)


@pytest.mark.fast
def test_storage_info_caching():
    """Test that storage_info caches results"""
    # Clear cache
    import edgar.storage_management
    edgar.storage_management._storage_cache = None

    # First call
    info1 = storage_info()
    timestamp1 = info1.last_updated

    time.sleep(0.1)  # Small delay

    # Second call should return cached result
    info2 = storage_info()
    timestamp2 = info2.last_updated

    assert timestamp1 == timestamp2  # Same object from cache


@pytest.mark.fast
def test_storage_info_force_refresh():
    """Test that force_refresh bypasses cache"""
    info1 = storage_info()
    timestamp1 = info1.last_updated

    time.sleep(0.1)

    info2 = storage_info(force_refresh=True)
    timestamp2 = info2.last_updated

    assert timestamp1 != timestamp2  # Different scan

@pytest.mark.fast
def test_storage_info_rich_display():
    """Test that StorageInfo has working __rich__ method"""
    from rich.console import Console
    from io import StringIO

    info = storage_info()

    # Render to string
    console = Console(file=StringIO(), width=80)
    console.print(info)

    output = console.file.getvalue()
    assert "EdgarTools Local Storage" in output
    assert "Total Size" in output or "GB" in output


# Phase 2: Filing Availability Checks

@pytest.mark.fast
def test_check_filing_not_exists():
    """Test check_filing returns False for non-existing filing"""
    from edgar._filings import Filing
    from edgar.storage_management import check_filing

    filing = Filing(
        cik=9999999,
        company="Nonexistent Company",
        form="10-K",
        filing_date="2099-12-31",
        accession_no="9999999999-99-999999"
    )

    assert check_filing(filing) is False

@pytest.mark.fast
def test_check_filings_batch():
    """Test check_filings_batch returns dict with availability"""
    from edgar import get_filings
    from edgar.storage_management import check_filings_batch
    import time

    # Get some filings
    filings = list(get_filings(filing_date="2025-01-15").head(10))

    start = time.time()
    availability = check_filings_batch(filings)
    elapsed = time.time() - start

    # Check results
    assert len(availability) == 10
    assert all(isinstance(v, bool) for v in availability.values())
    # Should be fast
    assert elapsed < 1.0  # Under 1 second for 10 filings

@pytest.mark.fast
def test_availability_summary():
    """Test availability_summary returns formatted string"""
    from edgar import get_filings
    from edgar.storage_management import availability_summary


    filings = list(get_filings(filing_date="2025-01-15").head(10))
    summary = availability_summary(filings)

    assert isinstance(summary, str)
    assert "of 10 filings" in summary
    assert "offline" in summary
    assert "%" in summary


# Phase 3: Storage Analysis

@pytest.mark.fast
def test_analyze_storage_returns_analysis():
    """Test that analyze_storage returns StorageAnalysis"""
    from edgar.storage_management import analyze_storage, StorageAnalysis

    analysis = analyze_storage()

    assert isinstance(analysis, StorageAnalysis)
    assert hasattr(analysis, 'storage_info')
    assert hasattr(analysis, 'issues')
    assert hasattr(analysis, 'recommendations')
    assert hasattr(analysis, 'potential_savings_bytes')
    assert isinstance(analysis.issues, list)
    assert isinstance(analysis.recommendations, list)
    assert analysis.potential_savings_bytes >= 0

@pytest.mark.fast
def test_analyze_storage_rich_display():
    """Test that StorageAnalysis has working __rich__ method"""
    from rich.console import Console
    from io import StringIO
    from edgar.storage_management import analyze_storage

    analysis = analyze_storage()

    # Render to string
    console = Console(file=StringIO(), width=80)
    console.print(analysis)

    output = console.file.getvalue()
    assert "Storage Analysis" in output
    assert "Current Size" in output or "GB" in output


# Phase 4: Storage Optimization

@pytest.mark.fast
def test_optimize_storage_dry_run():
    """Test optimize_storage with dry_run=True"""
    from edgar.storage_management import optimize_storage

    result = optimize_storage(dry_run=True)

    assert isinstance(result, dict)
    assert 'files_compressed' in result
    assert 'bytes_saved' in result
    assert 'errors' in result
    assert result['files_compressed'] >= 0
    assert result['bytes_saved'] >= 0
    assert result['errors'] >= 0

@pytest.mark.fast
def test_cleanup_storage_dry_run():
    """Test cleanup_storage with dry_run=True"""
    from edgar.storage_management import cleanup_storage

    result = cleanup_storage(days=365, dry_run=True)

    assert isinstance(result, dict)
    assert 'files_deleted' in result
    assert 'bytes_freed' in result
    assert 'errors' in result
    assert result['files_deleted'] >= 0
    assert result['bytes_freed'] >= 0
    assert result['errors'] >= 0

@pytest.mark.fast
def test_clear_cache_dry_run():
    """Test clear_cache with dry_run=True"""
    from edgar.storage_management import clear_cache

    result = clear_cache(dry_run=True)

    assert isinstance(result, dict)
    assert 'files_deleted' in result
    assert 'bytes_freed' in result
    assert 'errors' in result
    assert result['files_deleted'] >= 0
    assert result['bytes_freed'] >= 0
    assert result['errors'] >= 0


@pytest.mark.fast
def test_clear_cache_obsolete_only():
    """Test clear_cache with obsolete_only parameter"""
    from edgar.storage_management import clear_cache

    # Test dry run with obsolete_only
    result = clear_cache(dry_run=True, obsolete_only=True)

    assert isinstance(result, dict)
    assert 'files_deleted' in result
    assert 'bytes_freed' in result
    assert 'errors' in result
    assert result['files_deleted'] >= 0
    assert result['bytes_freed'] >= 0
    assert result['errors'] >= 0


@pytest.mark.fast
def test_analyze_storage_detects_obsolete_cache(tmp_path):
    """Test that analyze_storage detects obsolete _pcache directory"""
    from edgar.storage_management import analyze_storage
    from edgar.core import get_edgar_data_directory
    import os

    # Create a temporary _pcache directory with a test file
    storage_path = get_edgar_data_directory()
    pcache_dir = storage_path / '_pcache'
    pcache_dir.mkdir(parents=True, exist_ok=True)
    test_file = pcache_dir / 'test_cache_file.txt'
    test_file.write_text('test content')

    try:
        # Run analysis
        analysis = analyze_storage(force_refresh=True)

        # Should detect the obsolete cache
        issue_found = any('_pcache' in issue for issue in analysis.issues)
        recommendation_found = any('obsolete_only=True' in rec for rec in analysis.recommendations)

        assert issue_found, "Should detect obsolete _pcache directory"
        assert recommendation_found, "Should recommend clearing obsolete cache"

    finally:
        # Cleanup
        if test_file.exists():
            test_file.unlink()
        if pcache_dir.exists() and not list(pcache_dir.iterdir()):
            pcache_dir.rmdir()


@pytest.mark.fast
def test_storage_info_cache_labels():
    """Test that StorageInfo displays descriptive labels for cache directories"""
    from rich.console import Console
    from io import StringIO
    from edgar.storage_management import storage_info

    info = storage_info()

    # Render to string
    console = Console(file=StringIO(), width=120)
    console.print(info)

    output = console.file.getvalue()

    # Check for descriptive cache labels if cache directories exist
    if '_tcache' in info.by_type:
        assert 'HTTP cache' in output or '_tcache' in output
    if '_pcache' in info.by_type:
        assert 'obsolete' in output or '_pcache' in output


# Phase 5: Compression/Decompression Tests

@pytest.mark.fast
def test_compress_decompress_filing(tmp_path):
    """Test compressing and decompressing a filing file"""
    from edgar.storage import compress_filing, decompress_filing, is_compressed_file

    # Create a test file
    test_file = tmp_path / "test_filing.nc"
    test_content = b"Test filing content " * 100  # Make it worth compressing
    test_file.write_bytes(test_content)

    # Compress the file
    compressed_path = compress_filing(test_file, delete_original=False)

    assert compressed_path.exists()
    assert compressed_path.name == "test_filing.nc.gz"
    assert is_compressed_file(compressed_path)
    # Compressed should be smaller than original
    assert compressed_path.stat().st_size < test_file.stat().st_size

    # Decompress the file to a different location to avoid conflict
    decompressed_path = decompress_filing(compressed_path,
                                          output_path=tmp_path / "decompressed_filing.nc",
                                          delete_original=False)

    assert decompressed_path.exists()
    assert decompressed_path.read_bytes() == test_content

    # Cleanup
    test_file.unlink()
    compressed_path.unlink()
    decompressed_path.unlink()


@pytest.mark.fast
def test_compress_already_compressed_raises_error(tmp_path):
    """Test that compressing an already compressed file raises ValueError"""
    from edgar.storage import compress_filing
    import pytest

    # Create and compress a test file
    test_file = tmp_path / "test.nc"
    test_file.write_text("test content")
    compressed_path = compress_filing(test_file, delete_original=True)

    # Try to compress again - should raise ValueError
    with pytest.raises(ValueError, match="already compressed"):
        compress_filing(compressed_path)

    # Cleanup
    compressed_path.unlink()


@pytest.mark.fast
def test_decompress_uncompressed_raises_error(tmp_path):
    """Test that decompressing an uncompressed file raises ValueError"""
    from edgar.storage import decompress_filing
    import pytest

    # Create an uncompressed test file
    test_file = tmp_path / "test.nc"
    test_file.write_text("test content")

    # Try to decompress - should raise ValueError
    with pytest.raises(ValueError, match="not compressed"):
        decompress_filing(test_file)

    # Cleanup
    test_file.unlink()


@pytest.mark.integration
def test_load_filing_from_compressed_storage():
    """
    Test that filings can be loaded from compressed .nc.gz files in local storage.
    This is the critical end-to-end test for compression functionality.
    """
    from edgar import Filing
    from edgar.storage import local_filing_path, compress_filing, is_compressed_file
    from edgar.sgml.sgml_common import read_content_as_string
    import os

    # Use a known filing
    filing = Filing(
        form='10-Q',
        filing_date='2025-01-08',
        company='ANGIODYNAMICS INC',
        cik=1275187,
        accession_no='0001275187-25-000005'
    )

    # Get the local filing path
    filing_path = local_filing_path(
        filing_date=filing.filing_date,
        accession_number=filing.accession_no
    )

    # Skip test if filing doesn't exist locally
    if not filing_path.exists():
        pytest.skip("Filing not available in local storage")

    # Get the uncompressed path for comparison
    if is_compressed_file(filing_path):
        # If already compressed, skip (we can't test the compression workflow)
        pytest.skip("Filing is already compressed")

    # Read original content
    original_content = read_content_as_string(filing_path)
    assert len(original_content) > 0

    # Compress the filing
    compressed_path = compress_filing(filing_path, delete_original=False)

    try:
        # Verify compression worked
        assert compressed_path.exists()
        assert is_compressed_file(compressed_path)

        # Now test that we can load from the compressed file
        # This simulates what happens when local_filing_path returns a .gz file
        compressed_content = read_content_as_string(compressed_path)

        # Content should be identical
        assert compressed_content == original_content

        # Also test that the filing can still be loaded through the Filing object
        # by temporarily removing the uncompressed version
        original_path_backup = filing_path.with_suffix('.nc.backup')
        filing_path.rename(original_path_backup)

        try:
            # Now local_filing_path should return the compressed version
            path_returned = local_filing_path(
                filing_date=filing.filing_date,
                accession_number=filing.accession_no
            )
            assert path_returned == compressed_path
            assert is_compressed_file(path_returned)

            # Verify we can still read through the path
            content_from_compressed = read_content_as_string(path_returned)
            assert content_from_compressed == original_content

        finally:
            # Restore the original file
            original_path_backup.rename(filing_path)

    finally:
        # Cleanup: remove compressed file
        if compressed_path.exists():
            compressed_path.unlink()
