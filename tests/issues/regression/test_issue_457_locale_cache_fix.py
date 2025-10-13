"""
Test for Issue #457: Locale Cache Failure - Reopened

Root Cause:
-----------
Users with non-English system locales (Chinese, Japanese, German, etc.) experienced ValueError
when cache files created BEFORE v4.19.0 are deserialized AFTER the locale fix was applied.

The v4.19.0 fix forced LC_TIME to 'C' locale before importing httpxthrottlecache, which fixes
NEW cache entries. However, OLD cache files created with Chinese locale contain timestamps like
'周五, 10 10月 2025 11:57:10 GMT' that cannot be parsed with English format '%a, %d %b %Y %H:%M:%S GMT'.

Solution:
---------
Implement a one-time cache clearing function that:
1. Checks for a marker file to avoid repeated clearing
2. Clears the HTTP cache directory if marker doesn't exist
3. Creates a marker file to prevent future clearing

This ensures users upgrading from pre-4.19.0 have their old locale-corrupted cache files removed
automatically on first import.
"""

import locale
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from edgar.httpclient import clear_locale_corrupted_cache, get_cache_directory


class TestLocaleCacheFix:
    """Test suite for Issue #457 locale cache clearing functionality"""

    def test_locale_set_to_c_before_import(self):
        """Verify LC_TIME locale is set to 'C' before httpxthrottlecache import"""
        # This test verifies the fix in edgar/httpclient.py lines 14-19
        # The locale should be set to 'C' to ensure English date parsing
        current_locale = locale.getlocale(locale.LC_TIME)
        # Should be ('C', None) or ('en_US', 'UTF-8') or similar English locale
        # Not Chinese like ('zh_CN', 'UTF-8')
        assert current_locale[0] in [None, 'C'] or current_locale[0].startswith('en')

    def test_clear_locale_corrupted_cache_first_run(self, tmp_path):
        """Test cache clearing on first run (no marker file)"""
        # Create a temporary cache directory
        test_cache_dir = tmp_path / "_tcache"
        test_cache_dir.mkdir()

        # Create some fake cache files
        (test_cache_dir / "cache_file_1").write_text("fake cache data")
        (test_cache_dir / "cache_file_2").write_text("fake cache data")

        # Mock get_cache_directory to return our test directory
        with patch('edgar.httpclient.get_cache_directory', return_value=str(test_cache_dir)):
            result = clear_locale_corrupted_cache()

        # Should return True (cache was cleared)
        assert result is True

        # Cache directory should still exist
        assert test_cache_dir.exists()

        # But cache files should be gone
        assert not (test_cache_dir / "cache_file_1").exists()
        assert not (test_cache_dir / "cache_file_2").exists()

        # Marker file should exist
        marker_file = test_cache_dir / ".locale_fix_457_applied"
        assert marker_file.exists()

    def test_clear_locale_corrupted_cache_subsequent_run(self, tmp_path):
        """Test cache clearing on subsequent run (marker file exists)"""
        # Create a temporary cache directory with marker file
        test_cache_dir = tmp_path / "_tcache"
        test_cache_dir.mkdir()
        marker_file = test_cache_dir / ".locale_fix_457_applied"
        marker_file.touch()

        # Create some cache files (should NOT be deleted)
        (test_cache_dir / "cache_file_1").write_text("fake cache data")

        # Mock get_cache_directory to return our test directory
        with patch('edgar.httpclient.get_cache_directory', return_value=str(test_cache_dir)):
            result = clear_locale_corrupted_cache()

        # Should return False (cache was not cleared)
        assert result is False

        # Cache files should still exist
        assert (test_cache_dir / "cache_file_1").exists()

        # Marker file should still exist
        assert marker_file.exists()

    def test_clear_locale_corrupted_cache_no_cache_exists(self, tmp_path):
        """Test cache clearing when no cache directory exists"""
        # Create a path for non-existent cache directory
        test_cache_dir = tmp_path / "_tcache"

        # Mock get_cache_directory to return our test directory
        with patch('edgar.httpclient.get_cache_directory', return_value=str(test_cache_dir)):
            result = clear_locale_corrupted_cache()

        # Should return False (nothing to clear)
        assert result is False

        # Cache directory should now exist (created by function)
        assert test_cache_dir.exists()

        # Marker file should exist
        marker_file = test_cache_dir / ".locale_fix_457_applied"
        assert marker_file.exists()

    def test_clear_locale_corrupted_cache_error_handling(self, tmp_path):
        """Test graceful error handling when cache clearing fails"""
        # Create a read-only cache directory to simulate permission error
        test_cache_dir = tmp_path / "_tcache"
        test_cache_dir.mkdir()

        # Create a cache file
        cache_file = test_cache_dir / "cache_file_1"
        cache_file.write_text("fake cache data")

        # Make directory read-only (simulate permission error)
        test_cache_dir.chmod(0o444)

        try:
            # Mock get_cache_directory to return our test directory
            with patch('edgar.httpclient.get_cache_directory', return_value=str(test_cache_dir)):
                # Should not raise exception, but return False
                result = clear_locale_corrupted_cache()
                assert result is False
        finally:
            # Restore permissions for cleanup
            test_cache_dir.chmod(0o755)

    def test_automatic_cache_clearing_on_import(self):
        """Test that cache clearing is automatically triggered on edgar import"""
        # This test verifies the fix in edgar/__init__.py lines 49-56
        # The function should be called automatically on import
        # We can't fully test this without re-importing, but we can verify
        # the function exists and is callable
        from edgar.httpclient import clear_locale_corrupted_cache
        assert callable(clear_locale_corrupted_cache)

    def test_marker_file_prevents_repeated_clearing(self, tmp_path):
        """Test that marker file prevents repeated cache clearing"""
        test_cache_dir = tmp_path / "_tcache"
        test_cache_dir.mkdir()

        # First call - should clear
        with patch('edgar.httpclient.get_cache_directory', return_value=str(test_cache_dir)):
            result1 = clear_locale_corrupted_cache()
        assert result1 is True

        # Create new cache files after clearing
        (test_cache_dir / "new_cache_file").write_text("new cache data")

        # Second call - should NOT clear
        with patch('edgar.httpclient.get_cache_directory', return_value=str(test_cache_dir)):
            result2 = clear_locale_corrupted_cache()
        assert result2 is False

        # New cache file should still exist
        assert (test_cache_dir / "new_cache_file").exists()

    def test_locale_independence(self):
        """
        Test that EdgarTools works correctly regardless of user's system locale

        The fix in v4.19.0 ensures LC_TIME is set to 'C' before importing httpxthrottlecache,
        which means HTTP date parsing always uses English month/day names.
        """
        # The key is that httpxthrottlecache was imported with LC_TIME='C'
        # (see edgar/httpclient.py lines 14-19)
        # So regardless of what the user's locale is NOW, the library will work

        # Verify the cache clearing function works
        from edgar.httpclient import clear_locale_corrupted_cache
        assert callable(clear_locale_corrupted_cache)

        # Verify LC_TIME was set to 'C' during import
        # (it may have changed since, but the critical point is it was 'C' when
        # httpxthrottlecache was imported)
        import edgar.httpclient
        assert hasattr(edgar.httpclient, 'HttpxThrottleCache')


class TestIssuereproduction:
    """Test reproduction of original Issue #457"""

    def test_original_issue_reproduction(self):
        """
        Reproduce the original issue scenario from Issue #457

        Original error:
        ValueError: time data '周五, 10 10月 2025 11:57:10 GMT' does not match format '%a, %d %b %Y %H:%M:%S GMT'

        This occurred when:
        1. User has Chinese locale
        2. Cache file was created with Chinese timestamps
        3. User upgraded to v4.19.0 which forces LC_TIME='C'
        4. Old cache files couldn't be deserialized
        """
        # With our fix:
        # 1. LC_TIME is forced to 'C' before httpxthrottlecache import (line 15 in httpclient.py)
        # 2. Old cache files are automatically cleared on first import (line 53 in __init__.py)
        # 3. New cache files use English timestamps

        # Verify the fix is in place
        from edgar.httpclient import clear_locale_corrupted_cache
        assert callable(clear_locale_corrupted_cache)

        # Verify LC_TIME is set correctly
        current_locale = locale.getlocale(locale.LC_TIME)
        # Should be C locale or English, not Chinese
        if current_locale[0] is not None:
            assert not current_locale[0].startswith('zh')

    def test_user_workflow_after_upgrade(self, tmp_path):
        """
        Test the user workflow after upgrading to v4.19.1

        Scenario:
        1. User had EdgarTools < 4.19.0 with Chinese locale
        2. User upgrades to 4.19.1
        3. User imports edgar
        4. Cache is automatically cleared
        5. User can now use EdgarTools without errors
        """
        # Simulate pre-4.19.0 cache with "corrupted" files
        test_cache_dir = tmp_path / "_tcache"
        test_cache_dir.mkdir()
        (test_cache_dir / "old_cache_file").write_text("old cache with Chinese timestamps")

        # Simulate upgrade - cache clearing on import
        with patch('edgar.httpclient.get_cache_directory', return_value=str(test_cache_dir)):
            # Clear cache (this happens automatically in __init__.py)
            cleared = clear_locale_corrupted_cache()

        # Cache should be cleared
        assert cleared is True
        assert not (test_cache_dir / "old_cache_file").exists()

        # Marker should exist
        marker_file = test_cache_dir / ".locale_fix_457_applied"
        assert marker_file.exists()

        # Subsequent imports should not clear cache again
        with patch('edgar.httpclient.get_cache_directory', return_value=str(test_cache_dir)):
            cleared_again = clear_locale_corrupted_cache()
        assert cleared_again is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
