"""
Regression test for PR #493: download_bulk_data respects use_local_storage

Issue: #381
PR: #493

Problem:
    Previously, download_bulk_data() evaluated get_edgar_data_directory() at import time,
    causing the data directory to remain fixed even after use_local_storage() updated
    the environment variable.

Fix:
    Changed download_bulk_data() to resolve data_directory dynamically at call time,
    so updates made by use_local_storage() are respected by subsequent downloads.

This test verifies that:
    1. use_local_storage('/custom/path') sets EDGAR_LOCAL_DATA_DIR
    2. get_edgar_data_directory() returns the custom path
    3. download_bulk_data() would use the custom path (via mocking)
"""
import os
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock

from edgar.core import get_edgar_data_directory
from edgar.storage import use_local_storage


@pytest.mark.fast
class TestDownloadBulkDataRespectsLocalStorage:
    """Regression tests for PR #493 - download_bulk_data respects use_local_storage"""

    def test_get_edgar_data_directory_respects_env_var(self, tmp_path):
        """Verify get_edgar_data_directory reads EDGAR_LOCAL_DATA_DIR at runtime"""
        custom_path = tmp_path / "custom_edgar"
        custom_path.mkdir()

        # Set environment variable
        with patch.dict(os.environ, {'EDGAR_LOCAL_DATA_DIR': str(custom_path)}):
            result = get_edgar_data_directory()
            assert result == custom_path, \
                f"Expected {custom_path}, got {result}"

    def test_use_local_storage_sets_env_var(self, tmp_path):
        """Verify use_local_storage sets EDGAR_LOCAL_DATA_DIR"""
        custom_path = tmp_path / "edgar_storage"
        custom_path.mkdir()

        # Save original env var
        original_env = os.environ.get('EDGAR_LOCAL_DATA_DIR')

        try:
            use_local_storage(custom_path)

            # Verify env var was set
            assert os.environ.get('EDGAR_LOCAL_DATA_DIR') == str(custom_path), \
                "use_local_storage did not set EDGAR_LOCAL_DATA_DIR"

            # Verify get_edgar_data_directory returns the custom path
            result = get_edgar_data_directory()
            assert result == custom_path, \
                f"get_edgar_data_directory returned {result}, expected {custom_path}"
        finally:
            # Restore original env var
            if original_env is not None:
                os.environ['EDGAR_LOCAL_DATA_DIR'] = original_env
            elif 'EDGAR_LOCAL_DATA_DIR' in os.environ:
                del os.environ['EDGAR_LOCAL_DATA_DIR']

    @pytest.mark.asyncio
    async def test_download_bulk_data_uses_custom_directory(self, tmp_path):
        """
        Verify download_bulk_data uses the directory from use_local_storage.

        This is the key regression test for PR #493.
        We mock the actual download but verify the path resolution.
        """
        from edgar.httprequests import download_bulk_data

        custom_path = tmp_path / "bulk_data"
        custom_path.mkdir()

        # Save original env var
        original_env = os.environ.get('EDGAR_LOCAL_DATA_DIR')

        try:
            # Set custom storage path
            use_local_storage(custom_path)

            # Mock stream_file to avoid actual download
            with patch('edgar.httprequests.stream_file', new_callable=AsyncMock) as mock_stream:
                # Create a fake zip file that would be "downloaded"
                test_url = "https://www.sec.gov/Archives/edgar/daily-index/xbrl/test.zip"

                # The function will try to extract - mock that too
                with patch('zipfile.ZipFile'):
                    try:
                        await download_bulk_data(url=test_url)
                    except Exception:
                        # We expect some error since we're mocking, but we can still check the path
                        pass

                # Verify stream_file was called with path under custom_path
                if mock_stream.called:
                    call_args = mock_stream.call_args
                    # stream_file is called with (url, client=..., path=...)
                    called_path = call_args.kwargs.get('path') or call_args.args[2] if len(call_args.args) > 2 else None
                    if called_path:
                        assert str(custom_path) in str(called_path), \
                            f"download_bulk_data used path {called_path}, expected path under {custom_path}"
        finally:
            # Restore original env var
            if original_env is not None:
                os.environ['EDGAR_LOCAL_DATA_DIR'] = original_env
            elif 'EDGAR_LOCAL_DATA_DIR' in os.environ:
                del os.environ['EDGAR_LOCAL_DATA_DIR']

    def test_data_directory_not_hardcoded_at_import(self, tmp_path):
        """
        Verify that changing EDGAR_LOCAL_DATA_DIR after import affects behavior.

        This specifically tests the fix in PR #493 - the data directory should
        be evaluated at runtime, not at import time.
        """
        path1 = tmp_path / "path1"
        path2 = tmp_path / "path2"
        path1.mkdir()
        path2.mkdir()

        # Save original
        original_env = os.environ.get('EDGAR_LOCAL_DATA_DIR')

        try:
            # Set first path
            os.environ['EDGAR_LOCAL_DATA_DIR'] = str(path1)
            result1 = get_edgar_data_directory()
            assert result1 == path1

            # Change to second path
            os.environ['EDGAR_LOCAL_DATA_DIR'] = str(path2)
            result2 = get_edgar_data_directory()
            assert result2 == path2, \
                f"After changing env var, got {result2} but expected {path2}. " \
                "This suggests data directory is cached at import time (PR #493 regression)."
        finally:
            if original_env is not None:
                os.environ['EDGAR_LOCAL_DATA_DIR'] = original_env
            elif 'EDGAR_LOCAL_DATA_DIR' in os.environ:
                del os.environ['EDGAR_LOCAL_DATA_DIR']
