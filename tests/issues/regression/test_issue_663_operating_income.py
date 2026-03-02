"""
Regression test for GitHub discussion #663 / beads edgartools-m4tf.

Feature: Add get_operating_income() to Financials class.

Problem: Users couldn't find operating income via the natural path (get_financials()).
The EntityFacts path silently returns None for banks/energy companies.

Fix: Added get_operating_income() to Financials using XBRL concept-first lookup
with label fallback, following the same pattern as get_revenue().

Reporter: Michael Angelo
"""

import pytest
from edgar import Company


@pytest.mark.network
def test_aapl_operating_income():
    """
    Apple FY2024 10-K operating income ground truth.

    Source: Apple 10-K filed 2024-11-01, OperatingIncomeLoss = 123,216,000,000
    """
    company = Company("AAPL")
    financials = company.get_financials()

    operating_income = financials.get_operating_income()
    assert operating_income is not None, "Apple should have operating income"
    assert isinstance(operating_income, (int, float)), f"Should be numeric, got {type(operating_income)}"
    assert operating_income > 100_000_000_000, "Apple operating income should be > $100B"


@pytest.mark.network
def test_jpm_operating_income_no_error():
    """
    JPMorgan Chase — bank filer that doesn't report OperatingIncomeLoss.

    Banks use net interest income / noninterest income structure, so operating
    income is not a standard concept. Verify the method returns None gracefully
    (no crash), not that it finds a value.
    """
    company = Company("JPM")
    financials = company.get_financials()

    operating_income = financials.get_operating_income()
    # Banks may not have operating income; verify no crash and correct type
    assert operating_income is None or isinstance(operating_income, (int, float))


@pytest.mark.network
def test_msft_operating_income():
    """
    Microsoft — standard tech filer that reports OperatingIncomeLoss.

    Source: MSFT 10-K, OperatingIncomeLoss is a core line item.
    """
    company = Company("MSFT")
    financials = company.get_financials()

    operating_income = financials.get_operating_income()
    assert operating_income is not None, "MSFT should have operating income"
    assert isinstance(operating_income, (int, float)), f"Should be numeric, got {type(operating_income)}"
    assert operating_income > 50_000_000_000, "MSFT operating income should be > $50B"


@pytest.mark.network
def test_operating_income_in_financial_metrics():
    """
    Verify operating_income appears in get_financial_metrics() dict.
    """
    company = Company("AAPL")
    financials = company.get_financials()

    metrics = financials.get_financial_metrics()
    assert 'operating_income' in metrics, "operating_income should be in metrics dict"
    assert metrics['operating_income'] is not None, "Apple operating_income should not be None"
    assert isinstance(metrics['operating_income'], (int, float))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
