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
