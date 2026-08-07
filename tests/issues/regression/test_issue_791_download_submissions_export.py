"""
Regression test for Issue #791.

Error messages in edgar/reference/company_dataset.py instruct users to:

    from edgar.storage import download_submissions
    download_submissions()

But `download_submissions` was defined in edgar/storage/_local.py without
being added to that module's __all__ list. Since edgar/storage/__init__.py
uses `from edgar.storage._local import *`, the function was not re-exported.
The error message therefore pointed users at an import that always failed
with ImportError.

This test verifies that the import path advertised in error messages works.
"""

import pytest


@pytest.mark.fast
def test_download_submissions_importable_from_edgar_storage():
    """The exact import suggested by error messages must succeed."""
    from edgar.storage import download_submissions  # noqa: F401
    assert callable(download_submissions)


@pytest.mark.fast
def test_download_submissions_async_importable_from_edgar_storage():
    """Async variant should also be exposed for advanced/library usage."""
    from edgar.storage import download_submissions_async  # noqa: F401
    assert callable(download_submissions_async)


@pytest.mark.fast
def test_download_submissions_in_storage_dir():
    """Star-import surface should advertise download_submissions."""
    import edgar.storage
    assert 'download_submissions' in dir(edgar.storage)
    assert 'download_submissions_async' in dir(edgar.storage)


@pytest.mark.fast
def test_error_message_advertised_import_path_is_valid():
    """
    The error message in edgar.reference.company_dataset.build_company_dataset_parquet
    instructs users to run exactly this. It must not raise ImportError.
    """
    # The literal sequence emitted by the error message
    from edgar.storage import download_submissions
    assert download_submissions.__name__ == 'download_submissions'
