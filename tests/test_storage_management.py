"""
Tests for storage management functionality
"""

import pytest
from pathlib import Path
from edgar.storage_management import storage_info, StorageInfo, _scan_storage
from edgar.core import get_edgar_data_directory
import time


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


def test_storage_info_force_refresh():
    """Test that force_refresh bypasses cache"""
    info1 = storage_info()
    timestamp1 = info1.last_updated

    time.sleep(0.1)

    info2 = storage_info(force_refresh=True)
    timestamp2 = info2.last_updated

    assert timestamp1 != timestamp2  # Different scan


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
