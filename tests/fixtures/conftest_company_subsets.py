"""
Fixtures for company_subsets metadata tests.

This module provides fixtures for testing comprehensive company subset features
using a 5% sample of the full dataset (~28K companies) stored in companies_sample.pq.
"""

import pytest
from pathlib import Path
from unittest.mock import patch
import pyarrow.parquet as pq


@pytest.fixture(scope="session")
def company_sample_fixture_path():
    """Path to the sample company dataset fixture."""
    return Path(__file__).parent / 'companies_sample.pq'


@pytest.fixture(scope="session")
def company_sample_table(company_sample_fixture_path):
    """Load the sample company dataset as PyArrow Table."""
    if not company_sample_fixture_path.exists():
        pytest.skip(
            f"Sample data not found at {company_sample_fixture_path}. "
            "Run: python -c 'from edgar.reference import get_company_dataset; get_company_dataset()' "
            "to generate the full dataset first."
        )
    return pq.read_table(company_sample_fixture_path)


@pytest.fixture
def mock_comprehensive_dataset(company_sample_table):
    """
    Mock get_company_dataset() to return sample data instead of full dataset.

    This allows testing comprehensive features without requiring the full
    ~562K company dataset (~30 second build time).

    Usage:
        def test_something(mock_comprehensive_dataset):
            # get_company_dataset() will return sample data
            companies = get_all_companies(use_comprehensive=True)
            assert len(companies) > 0
    """
    with patch('edgar.reference.company_dataset.get_company_dataset') as mock:
        mock.return_value = company_sample_table
        yield mock


@pytest.fixture(scope="session")
def check_full_dataset_available():
    """
    Check if full submissions dataset is available.

    Skip tests that require the full dataset if submissions not downloaded.
    This is for integration tests marked with @pytest.mark.slow that need
    the real 562K company dataset.
    """
    from edgar.core import get_edgar_data_directory

    submissions_dir = get_edgar_data_directory() / 'submissions'

    # Skip if submissions not downloaded
    if not submissions_dir.exists() or len(list(submissions_dir.glob('CIK*.json'))) < 100000:
        pytest.skip(
            "Full submissions data not downloaded - required for integration tests. "
            "Run: from edgar.storage import download_submissions; download_submissions()"
        )
