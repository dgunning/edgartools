"""
Quick verification test for Issue #464 fix with COIN 10-Q Q3 2024

User Report (Issue #465):
- COIN 10-Q Q3 2024 Cash Flow had 26-34 missing values
- COIN 10-Q Q3 2024 Income Statement had 15-16 missing values
- Balance Sheets were complete after v4.20.1

This test verifies the fix resolves the issue.
"""
import pytest
from edgar import Company


@pytest.mark.network
def test_coin_10q_q3_2024_cash_flow_has_comparative_periods():
    """Verify COIN 10-Q Q3 2024 Cash Flow has comparative periods (no missing values)."""
    company = Company("COIN")
    filings = company.get_filings(form="10-Q")

    # Get latest 10-Q (should be Q3 2024 filed around Nov 2024)
    filing = filings.latest(1)
    print(f"Testing filing: {filing.form} filed {filing.filing_date}")

    xbrl = filing.xbrl()

    # Test Cash Flow Statement
    cash_flow = xbrl.statements.cashflow_statement()
    assert cash_flow is not None, "Cash Flow Statement not found"

    df = cash_flow.to_dataframe()
    print(f"\nCash Flow Statement shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()}")

    # Check for missing values
    missing_count = df.isnull().sum().sum()
    print(f"Missing values in Cash Flow: {missing_count}")

    # Get period columns (exclude concept/label columns)
    period_columns = [col for col in df.columns if col not in ['concept', 'label']]
    print(f"Number of period columns: {len(period_columns)}")
    print(f"Period columns: {period_columns}")

    # Assertions
    assert len(period_columns) >= 2, (
        f"Expected at least 2 periods for YoY comparison, got {len(period_columns)}"
    )
    assert missing_count == 0, (
        f"Cash Flow has {missing_count} missing values (expected 0)"
    )

    print("\n✅ Cash Flow Statement test PASSED")


@pytest.mark.network
def test_coin_10q_q3_2024_income_statement_has_comparative_periods():
    """Verify COIN 10-Q Q3 2024 Income Statement has comparative periods (no missing values)."""
    company = Company("COIN")
    filings = company.get_filings(form="10-Q")
    filing = filings.latest(1)

    xbrl = filing.xbrl()

    # Test Income Statement
    income = xbrl.statements.income_statement()
    assert income is not None, "Income Statement not found"

    df = income.to_dataframe()
    print(f"\nIncome Statement shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()}")

    missing_count = df.isnull().sum().sum()
    print(f"Missing values in Income Statement: {missing_count}")

    period_columns = [col for col in df.columns if col not in ['concept', 'label']]
    print(f"Number of period columns: {len(period_columns)}")
    print(f"Period columns: {period_columns}")

    assert len(period_columns) >= 2, (
        f"Expected at least 2 periods for YoY comparison, got {len(period_columns)}"
    )
    assert missing_count == 0, (
        f"Income Statement has {missing_count} missing values (expected 0)"
    )

    print("\n✅ Income Statement test PASSED")


@pytest.mark.network
def test_coin_10q_q3_2024_balance_sheet_still_works():
    """Verify Balance Sheet still works (regression check for v4.20.1 fix)."""
    company = Company("COIN")
    filings = company.get_filings(form="10-Q")
    filing = filings.latest(1)

    xbrl = filing.xbrl()

    # Test Balance Sheet (should still work from v4.20.1)
    balance_sheet = xbrl.statements.balance_sheet()
    assert balance_sheet is not None, "Balance Sheet not found"

    df = balance_sheet.to_dataframe()
    print(f"\nBalance Sheet shape: {df.shape}")

    period_columns = [col for col in df.columns if col not in ['concept', 'label']]
    print(f"Number of period columns: {len(period_columns)}")

    assert len(period_columns) >= 2, (
        f"Expected at least 2 periods, got {len(period_columns)}"
    )

    print("\n✅ Balance Sheet test PASSED")


if __name__ == "__main__":
    # Run tests directly
    print("=" * 80)
    print("Testing COIN 10-Q Q3 2024 - Issue #464 Verification")
    print("=" * 80)

    test_coin_10q_q3_2024_cash_flow_has_comparative_periods()
    test_coin_10q_q3_2024_income_statement_has_comparative_periods()
    test_coin_10q_q3_2024_balance_sheet_still_works()

    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED - Issue #464 fix verified!")
    print("=" * 80)
