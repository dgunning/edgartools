"""
Regression test for GitHub Issue #412:
Historical periods in entity statements showed sparse data.

Periods 3rd and 4th should have comprehensive balance sheet data,
not just cash values.
"""
import pytest
from edgar import Company


@pytest.mark.network
def test_historical_periods_have_comprehensive_data():
    """Historical periods (3rd, 4th) should have >35% completeness and key balance sheet items."""
    company = Company("TSLA")
    balance_sheet = company.balance_sheet(annual=True, periods=6)
    df = balance_sheet.to_dataframe()

    periods = balance_sheet.periods

    for period_index in [2, 3]:
        if period_index < len(periods):
            period = periods[period_index]

            if period in df.columns:
                completeness = df[period].count() / len(df)
                assert completeness > 0.35, (
                    f"Historical period {period} (index {period_index}) should have "
                    f"comprehensive data. Got {completeness:.1%}, expected >35%"
                )

                non_null_data = df[df[period].notna()]
                key_items_present = 0

                for _, row in non_null_data.iterrows():
                    label_lower = row['label'].lower()
                    if any(keyword in label_lower for keyword in
                           ['assets', 'liabilities', 'equity', 'stockholders']):
                        key_items_present += 1

                assert key_items_present >= 3, (
                    f"Historical period {period} should have key balance sheet items, "
                    f"not just cash. Found {key_items_present} key items."
                )
