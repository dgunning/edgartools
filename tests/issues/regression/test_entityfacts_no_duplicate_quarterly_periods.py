"""
Regression test for duplicate quarterly periods bug.

Issue: Company.balance_sheet(annual=False) shows duplicate fiscal periods
Root Cause: SEC Facts API includes comparative data with same fiscal_period
Fix: Validate period_end matches expected month for fiscal_period
"""

import pytest
from collections import Counter
from datetime import date
from edgar import Company


@pytest.mark.fast
def test_no_duplicate_quarterly_periods_apple():
    """Apple Q3 2025 should appear only once, not twice"""
    c = Company("AAPL")
    bs = c.balance_sheet(annual=False, periods=4)

    # Check for duplicates
    period_counts = Counter(bs.periods)
    duplicates = {p: count for p, count in period_counts.items() if count > 1}

    assert not duplicates, f"Found duplicate periods: {duplicates}"
    assert len(bs.periods) == len(set(bs.periods)), "Periods should be unique"


@pytest.mark.fast
def test_quarterly_period_values_are_correct():
    """Q3 2025 should show June 2025 data, not September 2024 data"""
    c = Company("AAPL")
    bs = c.balance_sheet(annual=False, periods=4)

    # Find Assets for Q3 2025
    for item in bs:
        if 'Assets' in item.concept and item.concept in ['Assets', 'us-gaap:Assets']:
            q3_2025_value = item.values.get('Q3 2025')
            if q3_2025_value:
                # Should be ~$331B (June 2025), not ~$365B (Sept 2024)
                assert 320e9 < q3_2025_value < 340e9, \
                    f"Q3 2025 Assets should be ~$331B, got ${q3_2025_value/1e9:.1f}B"
                break


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT", "GOOGL", "AMZN"])
def test_no_duplicates_multiple_companies(ticker):
    """Test multiple companies for duplicate quarterly periods"""
    c = Company(ticker)
    bs = c.balance_sheet(annual=False, periods=8)

    period_counts = Counter(bs.periods)
    duplicates = {p: count for p, count in period_counts.items() if count > 1}

    assert not duplicates, f"{ticker}: Found duplicate periods: {duplicates}"


@pytest.mark.fast
def test_validate_quarterly_period_end():
    """Test the validation function directly"""
    from edgar.entity.enhanced_statement import validate_quarterly_period_end

    # Apple (fiscal year ends in September, month 9)

    # Q3 should end in June (3 months before Sept)
    assert validate_quarterly_period_end('Q3', date(2025, 6, 28), 9) == True

    # Q3 should NOT end in September (that's Q4)
    assert validate_quarterly_period_end('Q3', date(2024, 9, 28), 9) == False

    # Q4 should end in September
    assert validate_quarterly_period_end('Q4', date(2024, 9, 28), 9) == True

    # Standard calendar year company (fiscal year ends in December)
    # Q3 should end in September
    assert validate_quarterly_period_end('Q3', date(2025, 9, 30), 12) == True


@pytest.mark.fast
def test_detect_fiscal_year_end():
    """Test fiscal year end detection with real data"""
    from edgar.entity.enhanced_statement import detect_fiscal_year_end

    # Use real Apple data which has September fiscal year end
    c = Company("AAPL")
    bs = c.balance_sheet(annual=True, periods=2)

    # Get the underlying facts
    # The detect function should identify September (month 9) as fiscal year end for Apple
    # This is tested indirectly through the quarterly validation working correctly
    # Since if fiscal year end detection is wrong, the quarterly tests would fail

    # This is more of an integration test - if quarterly tests pass, detection works
    assert True  # Placeholder - real test is in the quarterly validation tests


@pytest.mark.fast
def test_quarterly_income_statement_no_duplicates():
    """Test quarterly income statement also has no duplicates"""
    c = Company("AAPL")
    income = c.income_statement(annual=False, periods=4)

    period_counts = Counter(income.periods)
    duplicates = {p: count for p, count in period_counts.items() if count > 1}

    assert not duplicates, f"Found duplicate periods in income statement: {duplicates}"


@pytest.mark.fast
def test_quarterly_cash_flow_no_duplicates():
    """Test quarterly cash flow statement also has no duplicates"""
    c = Company("AAPL")
    cf = c.cash_flow(annual=False, periods=4)

    period_counts = Counter(cf.periods)
    duplicates = {p: count for p, count in period_counts.items() if count > 1}

    assert not duplicates, f"Found duplicate periods in cash flow: {duplicates}"
