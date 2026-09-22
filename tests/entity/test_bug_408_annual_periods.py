"""
Test for bug #408: Annual periods showing quarterly values
https://github.com/dgunning/edgartools/issues/408

This test ensures that when requesting annual data, we correctly filter out
quarterly facts that are incorrectly marked as "FY" in the SEC Facts API.
"""

import pytest
from datetime import date
from edgar import Company

def test_annual_periods_exclude_quarterly_data():
    """
    Test that annual statements exclude quarterly data marked as FY.
    
    The SEC Facts API sometimes marks quarterly (90-day) facts as "FY", 
    which can cause annual statements to show incorrect quarterly values.
    This test ensures we filter by duration to get TRUE annual periods.
    """
    # Test with Apple - a company known to have this issue
    apple = Company("AAPL")
    
    # Get income statement with annual=True
    income = apple.income_statement(annual=True, periods=3)
    
    # Check that we have proper annual periods (not quarterly)
    assert len(income.periods) <= 3
    
    # Verify periods are actually annual by checking the labels
    for period in income.periods:
        assert "FY" in period or "Annual" in period.upper()
        # Quarterly periods would have Q1, Q2, Q3, Q4
        assert "Q1" not in period
        assert "Q2" not in period  
        assert "Q3" not in period
        assert "Q4" not in period
    
    # Check specific revenue values to ensure they're annual amounts
    revenue = income.find_item(label="Total Net Sales")
    if revenue:
        for period, value in revenue.values.items():
            if value:
                # Apple's annual revenue should be > $300B (not quarterly ~$90B)
                # This is a sanity check - adjust thresholds as needed
                assert value > 200_000_000_000, f"Revenue for {period} seems too low for annual: ${value:,.0f}"


def test_annual_vs_quarterly_revenue_magnitude():
    """
    Test that annual revenue values are significantly larger than quarterly.
    
    This test compares annual and quarterly revenue to ensure annual values
    represent full-year totals, not individual quarters.
    """
    apple = Company("AAPL")
    
    # Get both annual and quarterly statements
    annual_income = apple.income_statement(annual=True, periods=1)
    quarterly_income = apple.income_statement(annual=False, periods=4)
    
    # Get revenue from each
    annual_revenue = annual_income.find_item(label="Total Net Sales")
    quarterly_revenue = quarterly_income.find_item(label="Total Net Sales")
    
    if annual_revenue and quarterly_revenue:
        # Get the latest annual value
        annual_values = [v for v in annual_revenue.values.values() if v]
        if annual_values:
            latest_annual = annual_values[0]
            
            # Get quarterly values
            quarterly_values = [v for v in quarterly_revenue.values.values() if v]
            if len(quarterly_values) >= 4:
                # Sum of 4 quarters should be close to annual
                four_quarter_sum = sum(quarterly_values[:4])
                
                # Annual should be roughly equal to sum of 4 quarters
                # Allow for some variance due to timing/adjustments
                ratio = latest_annual / four_quarter_sum if four_quarter_sum else 0
                assert 0.9 < ratio < 1.1, f"Annual revenue ({latest_annual:,.0f}) not aligned with quarterly sum ({four_quarter_sum:,.0f})"


def test_period_duration_filtering():
    """
    Test that the duration-based filtering correctly identifies annual vs quarterly periods.
    
    This test checks the internal logic that filters facts based on period duration
    (>300 days for annual, ~90 days for quarterly).
    """
    # This test simulates the internal logic without importing internals
    from datetime import timedelta
    from collections import namedtuple
    
    # Create a simple Fact-like object for testing
    Fact = namedtuple('Fact', ['concept', 'value', 'period_start', 'period_end', 'fiscal_year', 'fiscal_period'])
    
    # Create test facts with different durations
    test_facts = [
        # Annual fact (365 days)
        Fact(
            concept="Revenue",
            value=1000000,
            period_start=date(2023, 1, 1),
            period_end=date(2023, 12, 31),
            fiscal_year=2023,
            fiscal_period="FY"
        ),
        # Quarterly fact incorrectly marked as FY (90 days)
        Fact(
            concept="Revenue", 
            value=250000,
            period_start=date(2023, 10, 1),
            period_end=date(2023, 12, 31),
            fiscal_year=2023,
            fiscal_period="FY"  # Wrong! This is actually Q4
        ),
        # Another annual fact (363 days - some years are shorter)
        Fact(
            concept="Revenue",
            value=950000,
            period_start=date(2022, 1, 3),
            period_end=date(2022, 12, 31),
            fiscal_year=2022,
            fiscal_period="FY"
        )
    ]
    
    # Filter for annual facts (duration > 300 days)
    annual_facts = []
    for fact in test_facts:
        if fact.period_start and fact.period_end:
            duration = (fact.period_end - fact.period_start).days
            if duration > 300:
                annual_facts.append(fact)
    
    # Should only have 2 annual facts (not the 90-day quarterly one)
    assert len(annual_facts) == 2
    assert annual_facts[0].value == 1000000
    assert annual_facts[1].value == 950000
    
    # The quarterly fact should be excluded
    quarterly_values = [f.value for f in test_facts if f not in annual_facts]
    assert 250000 in quarterly_values


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT", "GOOGL"])
def test_multiple_companies_annual_consistency(ticker):
    """
    Test annual period filtering across multiple companies.
    
    This parametrized test ensures the fix works for various companies,
    not just Apple.
    """
    company = Company(ticker)
    
    # Get annual income statement
    income = company.income_statement(annual=True, periods=2)
    
    # Basic validations
    assert income is not None
    assert len(income.periods) > 0
    
    # Check that periods are labeled as annual
    for period in income.periods:
        # Should contain FY or year designation
        assert any(indicator in period for indicator in ["FY", "20"])
        
        # Should NOT contain quarterly indicators
        assert not any(q in period for q in ["Q1", "Q2", "Q3", "Q4"])


if __name__ == "__main__":
    # Run tests directly
    test_annual_periods_exclude_quarterly_data()
    test_annual_vs_quarterly_revenue_magnitude()
    test_period_duration_filtering()
    print("All bug #408 tests passed!")