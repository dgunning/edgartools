"""
Regression test for GitHub issue #553.

Bug: TypeError in get_financial_metrics() due to string instead of float for operating_cf

Problem: _get_standardized_concept_value() returned empty string '' when a pattern
matched a row with no value (e.g., "Adjustments to reconcile net income to net cash
from operations"). This caused TypeError when arithmetic was performed in
get_free_cash_flow().

Fix:
1. Skip empty/NA values and continue to next pattern
2. Improved operating cash flow patterns to prioritize totals over adjustments

Reporter: miruddfan
Ticker: MSFT
"""

import pytest
from edgar import Company


@pytest.mark.network
def test_msft_get_financial_metrics_no_typeerror():
    """
    Test that get_financial_metrics() works for MSFT without TypeError.

    This was the original failing case - MSFT cash flow statement has an
    "Adjustments to reconcile..." row that matched before the actual total.
    """
    company = Company("MSFT")
    financials = company.get_financials()

    # This should not raise TypeError
    metrics = financials.get_financial_metrics()

    # Verify we got numeric values (not strings)
    operating_cf = metrics.get('operating_cash_flow')
    assert operating_cf is not None, "Should find operating cash flow"
    assert isinstance(operating_cf, (int, float)), f"Operating CF should be numeric, got {type(operating_cf)}"
    assert operating_cf > 0, "MSFT should have positive operating cash flow"


@pytest.mark.network
def test_operating_cash_flow_returns_numeric():
    """
    Test that get_operating_cash_flow() returns numeric values, not strings.
    """
    company = Company("MSFT")
    financials = company.get_financials()

    ocf = financials.get_operating_cash_flow()

    assert ocf is not None, "Should find operating cash flow for MSFT"
    assert isinstance(ocf, (int, float)), f"Should be numeric, got {type(ocf)}: {ocf!r}"


@pytest.mark.network
def test_free_cash_flow_calculation():
    """
    Test that free cash flow calculation works without TypeError.

    FCF = Operating Cash Flow - |CapEx|
    """
    company = Company("MSFT")
    financials = company.get_financials()

    # These should all return numeric values
    ocf = financials.get_operating_cash_flow()
    capex = financials.get_capital_expenditures()
    fcf = financials.get_free_cash_flow()

    assert ocf is not None, "Should have operating cash flow"
    assert capex is not None, "Should have capital expenditures"
    assert fcf is not None, "Should have free cash flow"

    # Verify FCF calculation
    expected_fcf = ocf - abs(capex)
    assert fcf == expected_fcf, f"FCF should equal OCF - |CapEx|: {fcf} != {expected_fcf}"


@pytest.mark.network
def test_standardized_concept_value_skips_empty_values():
    """
    Test that _get_standardized_concept_value skips empty/NA values.

    When a pattern matches a row with empty value, it should continue
    to the next pattern instead of returning the empty string.
    """
    company = Company("AAPL")
    financials = company.get_financials()

    metrics = financials.get_financial_metrics()

    # All values should be None or numeric - never empty string
    for key, value in metrics.items():
        if value is not None:
            assert isinstance(value, (int, float)), \
                f"Metric '{key}' should be numeric, got {type(value)}: {value!r}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])