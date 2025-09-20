"""
Regression test for GitHub issue #443: JSONDecodeError when fetching certain filings

This test ensures that corrupted submissions cache files are handled gracefully
by re-downloading the data automatically.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from edgar import find, set_identity
from edgar.entity.submissions import load_company_submissions_from_local
from edgar.storage import get_edgar_data_directory


class TestCorruptedSubmissionsCache:
    """Test cases for handling corrupted submissions cache files"""

    @pytest.fixture(autouse=True)
    def setup_identity(self):
        """Set up SEC API identity for tests"""
        set_identity("Test Suite test@edgartools.dev")

    def test_empty_cache_file_recovery(self):
        """Test that an empty cache file is detected and data re-downloaded"""
        # Get a test filing
        filing = find("0001949846-25-000489")
        cik = filing.cik

        # Create corrupted cache file (empty)
        submissions_dir = get_edgar_data_directory() / "submissions"
        submissions_dir.mkdir(exist_ok=True)
        submissions_file = submissions_dir / f"CIK{cik:010}.json"

        try:
            # Write empty content to simulate corruption
            submissions_file.write_text("")
            assert submissions_file.exists()
            assert submissions_file.stat().st_size == 0

            # Function should recover gracefully
            submissions = load_company_submissions_from_local(cik)

            # Should have successfully downloaded data
            assert submissions is not None
            assert isinstance(submissions, dict)
            assert "filings" in submissions

            # Cache file should now contain valid data
            assert submissions_file.exists()
            assert submissions_file.stat().st_size > 0

            # Should be valid JSON
            with open(submissions_file, 'r') as f:
                parsed = json.load(f)
                assert isinstance(parsed, dict)

        finally:
            # Clean up
            if submissions_file.exists():
                submissions_file.unlink()

    def test_invalid_json_cache_file_recovery(self):
        """Test that an invalid JSON cache file is detected and data re-downloaded"""
        filing = find("0001949846-25-000489")
        cik = filing.cik

        submissions_dir = get_edgar_data_directory() / "submissions"
        submissions_dir.mkdir(exist_ok=True)
        submissions_file = submissions_dir / f"CIK{cik:010}.json"

        try:
            # Write invalid JSON to simulate corruption
            submissions_file.write_text('{"invalid": json}')
            assert submissions_file.exists()

            # Function should recover gracefully
            submissions = load_company_submissions_from_local(cik)

            # Should have successfully downloaded data
            assert submissions is not None
            assert isinstance(submissions, dict)

            # Cache file should now contain valid data
            with open(submissions_file, 'r') as f:
                parsed = json.load(f)
                assert isinstance(parsed, dict)

        finally:
            # Clean up
            if submissions_file.exists():
                submissions_file.unlink()

    def test_end_to_end_corrupted_cache_recovery(self):
        """Test the full filing.related_filings() scenario with corrupted cache"""
        filing = find("0001949846-25-000489")
        cik = filing.cik

        submissions_dir = get_edgar_data_directory() / "submissions"
        submissions_dir.mkdir(exist_ok=True)
        submissions_file = submissions_dir / f"CIK{cik:010}.json"

        try:
            # Create corrupted cache file
            submissions_file.write_text("")

            # This should work without JSONDecodeError
            related = filing.related_filings()

            # Should return valid results
            assert related is not None
            assert hasattr(related, '__len__')

        finally:
            # Clean up
            if submissions_file.exists():
                submissions_file.unlink()

    def test_download_failure_cleanup(self):
        """Test that corrupted files are cleaned up when download fails"""
        filing = find("0001949846-25-000489")
        cik = filing.cik

        submissions_dir = get_edgar_data_directory() / "submissions"
        submissions_dir.mkdir(exist_ok=True)
        submissions_file = submissions_dir / f"CIK{cik:010}.json"

        try:
            # Create corrupted cache file
            submissions_file.write_text("")

            # Mock download failure
            with patch('edgar.entity.submissions.download_entity_submissions_from_sec') as mock_download:
                mock_download.side_effect = Exception("Network error")

                # Function should handle failure gracefully
                result = load_company_submissions_from_local(cik)
                assert result is None

                # Corrupted file should be cleaned up
                assert not submissions_file.exists()

        finally:
            # Clean up
            if submissions_file.exists():
                submissions_file.unlink()

    def test_unicode_decode_error_recovery(self):
        """Test recovery from UnicodeDecodeError in cache files"""
        filing = find("0001949846-25-000489")
        cik = filing.cik

        submissions_dir = get_edgar_data_directory() / "submissions"
        submissions_dir.mkdir(exist_ok=True)
        submissions_file = submissions_dir / f"CIK{cik:010}.json"

        try:
            # Write binary data that will cause UnicodeDecodeError
            submissions_file.write_bytes(b'\xff\xfe\x00\x00invalid binary data')

            # Function should recover gracefully
            submissions = load_company_submissions_from_local(cik)

            # Should have successfully downloaded data
            assert submissions is not None
            assert isinstance(submissions, dict)

        finally:
            # Clean up
            if submissions_file.exists():
                submissions_file.unlink()

    def test_normal_operation_unaffected(self):
        """Test that normal operation with valid cache files is unaffected"""
        filing = find("0001949846-25-000489")
        cik = filing.cik

        submissions_dir = get_edgar_data_directory() / "submissions"
        submissions_dir.mkdir(exist_ok=True)
        submissions_file = submissions_dir / f"CIK{cik:010}.json"

        try:
            # First, get valid data
            submissions1 = load_company_submissions_from_local(cik)
            assert submissions1 is not None

            # Cache file should exist and be valid
            assert submissions_file.exists()
            assert submissions_file.stat().st_size > 0

            # Second call should use cache (not download again)
            with patch('edgar.entity.submissions.download_entity_submissions_from_sec') as mock_download:
                submissions2 = load_company_submissions_from_local(cik)
                assert submissions2 is not None
                # Download should not be called for valid cache
                mock_download.assert_not_called()

        finally:
            # Clean up
            if submissions_file.exists():
                submissions_file.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])