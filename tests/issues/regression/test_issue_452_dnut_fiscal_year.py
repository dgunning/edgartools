"""
Regression test for Issue #452: DNUT FY 2023 revenue incorrect value

GitHub Issue: https://github.com/dgunning/edgartools/issues/452

Problem:
--------
EdgarTools was returning $1.530B for DNUT's FY 2023 revenue instead of the correct $1.686B.

Root Cause:
-----------
When Krispy Kreme (DNUT) changed their fiscal year-end from January to December,
the SEC Facts API provided duplicate periods with inconsistent fiscal_year values:
- Period ending Jan 1, 2023: Had fiscal_year=2022 (correct) AND fiscal_year=2023 (wrong)
- Period ending Dec 31, 2023: Had fiscal_year=2023 (correct)

EdgarTools was selecting the wrong period (Jan 1, 2023 with fiscal_year=2023)
which had $1.530B revenue instead of the correct period (Dec 31, 2023) with $1.686B.

Fix:
----
Added fiscal year validation in enhanced_statement.py to filter out mislabeled
comparative data where fiscal_year doesn't align with period_end.

Test Strategy:
--------------
This test verifies that DNUT's FY 2023 revenue matches the official SEC filing value
of $1.686B, confirming that the correct period (Dec 31, 2023) is now selected.
"""

import pytest
from edgar import Company


@pytest.mark.network
def test_dnut_fy2023_revenue_issue_452():
    """
    Test that DNUT FY 2023 revenue is correct after fiscal year-end change.

    This verifies the fix for Issue #452 where EdgarTools was selecting the wrong
    period when a company changed fiscal year-ends, resulting in incorrect revenue values.
    """
    company = Company("DNUT")

    # Get 5 annual periods to ensure we have FY 2023
    income_stmt = company.income_statement(periods=5, annual=True)

    assert income_stmt is not None, "Should be able to get income statement for DNUT"

    # Convert to DataFrame for easier analysis
    df = income_stmt.to_dataframe()

    # Find the FY 2023 column
    fy_2023_col = None
    for col in df.columns:
        if 'FY 2023' in str(col) or '2023' in str(col):
            fy_2023_col = col
            break

    assert fy_2023_col is not None, "Could not find FY 2023 column in income statement"

    # Get revenue value for FY 2023
    # Try different possible row labels for revenue (both friendly names and XBRL concepts)
    revenue_row_labels = [
        'Revenue', 'Total Revenue', 'Revenues', 'Total Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax'  # XBRL concept name
    ]
    revenue_2023 = None

    for label in revenue_row_labels:
        if label in df.index:
            revenue_2023 = df.loc[label, fy_2023_col]
            break

    assert revenue_2023 is not None, f"Could not find revenue row. Available rows: {list(df.index)}"

    # Expected value from SEC filing: $1.686104B
    # Source: https://www.sec.gov/ix?doc=/Archives/edgar/data/0001857154/000185715425000013/dnut-20241229.htm
    expected = 1_686_104_000

    # Allow 1% tolerance for rounding differences
    tolerance = expected * 0.01

    # The bug was showing $1.530B (the wrong period), we expect $1.686B
    assert abs(revenue_2023 - expected) < tolerance, (
        f"DNUT FY 2023 revenue should be ~${expected/1e9:.3f}B (from Dec 31, 2023 period), "
        f"but got ${revenue_2023/1e9:.3f}B. "
        f"This may indicate the wrong period (Jan 1, 2023 with $1.530B) was selected. "
        f"See Issue #452 for details."
    )

    # Also verify we're NOT getting the wrong value
    wrong_value = 1_530_000_000  # The incorrect value from Jan 1, 2023 period
    assert abs(revenue_2023 - wrong_value) > tolerance, (
        f"DNUT FY 2023 revenue is ${revenue_2023/1e9:.3f}B, which is the WRONG value "
        f"from the Jan 1, 2023 period. Should be ${expected/1e9:.3f}B from Dec 31, 2023 period. "
        f"The fiscal year validation fix may not be working correctly."
    )


@pytest.mark.fast
def test_fiscal_year_validation_helper():
    """
    Test the validate_fiscal_year_period_end() helper function directly.

    This ensures the validation logic correctly handles:
    - Early January periods (52/53-week calendars)
    - Late December periods (year-end shifts)
    - Normal periods
    """
    from datetime import date
    from edgar.entity.enhanced_statement import validate_fiscal_year_period_end

    # Early January periods (Jan 1-7): Allow year-1 or year
    assert validate_fiscal_year_period_end(2022, date(2023, 1, 1)) is True  # 52/53-week calendar
    assert validate_fiscal_year_period_end(2023, date(2023, 1, 1)) is True  # Edge case
    assert validate_fiscal_year_period_end(2024, date(2023, 1, 1)) is False  # Invalid
    assert validate_fiscal_year_period_end(2021, date(2023, 1, 1)) is False  # Too far back

    # Late December periods (Dec 25-31): Allow year or year+1
    assert validate_fiscal_year_period_end(2023, date(2023, 12, 31)) is True  # Normal
    assert validate_fiscal_year_period_end(2024, date(2023, 12, 31)) is True  # Year-end shift
    assert validate_fiscal_year_period_end(2022, date(2023, 12, 31)) is False  # Too far back
    assert validate_fiscal_year_period_end(2025, date(2023, 12, 31)) is False  # Too far forward

    # Normal periods (anything else): Must match exactly
    assert validate_fiscal_year_period_end(2023, date(2023, 6, 30)) is True  # Q2
    assert validate_fiscal_year_period_end(2023, date(2023, 9, 30)) is True  # Q3
    assert validate_fiscal_year_period_end(2022, date(2023, 6, 30)) is False  # Wrong year
    assert validate_fiscal_year_period_end(2024, date(2023, 6, 30)) is False  # Wrong year
    assert validate_fiscal_year_period_end(2025, date(2023, 6, 30)) is False  # Way off


if __name__ == "__main__":
    # Allow running this test directly for debugging
    print("Running DNUT FY 2023 revenue test (Issue #452)...")
    test_dnut_fy2023_revenue_issue_452()
    print("✓ Test passed! DNUT FY 2023 revenue is correct.")

    print("\nRunning fiscal year validation helper test...")
    test_fiscal_year_validation_helper()
    print("✓ Test passed! Fiscal year validation logic is correct.")
