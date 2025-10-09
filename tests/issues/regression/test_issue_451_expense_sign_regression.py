"""
Regression test for Issue #451: Inconsistent sign for cost/expense metrics

This test ensures that expense and cost metrics consistently show positive values
across different filing types (10-K and 10-Q), resolving the issue where:
- Income Tax Expense was showing negative values
- Cost of Goods and Services Sold was showing negative values

The fix adds these concepts to the consistent_positive_concepts list in the
XBRL parser to preserve their original positive values regardless of calculation
weight structure in different companies' XBRL filings.

Related Issues:
- Issue #451: Inconsistent sign for cost/expense metrics (Apple)
- Issue #290: Cost of Revenue sign inconsistency (IBM)
- Issue #334: R&D expense sign inconsistency (resolved with same pattern)

Reporter: @Velikolay
"""

import pytest
from edgar import Company
from edgar.xbrl.xbrl import XBRL


@pytest.fixture(scope="module")
def apple_10k_2020():
    """Apple 10-K for fiscal year 2020."""
    company = Company("AAPL")
    filing = company.get_filings(accession_number="0000320193-20-000062").latest()
    return XBRL.from_filing(filing)


@pytest.fixture(scope="module")
def apple_10q_2020_q2():
    """Apple 10-Q for Q2 2020."""
    company = Company("AAPL")
    filing = company.get_filings(accession_number="0000320193-20-000052").latest()
    return XBRL.from_filing(filing)


class TestIssue451ExpenseSignConsistency:
    """Test that expense and cost metrics have consistent positive signs."""

    def test_income_tax_expense_positive_in_10k(self, apple_10k_2020):
        """Test that Income Tax Expense is positive in 10-K."""
        stmt = apple_10k_2020.statements.income_statement()
        df = stmt.to_dataframe()

        # Find Income Tax Expense (non-dimensional, non-abstract)
        rows = df[df['concept'].str.contains('IncomeTaxExpense', case=False, na=False)]
        rows = rows[(rows['dimension'] == False) & (rows['abstract'] == False)]

        assert not rows.empty, "Income Tax Expense not found in income statement"

        row = rows.iloc[0]
        value = row['2020-06-27']

        assert value > 0, f"Income Tax Expense should be positive, got {value}"
        assert value == pytest.approx(7452000000.0), f"Expected 7,452,000,000, got {value}"

    def test_income_tax_expense_positive_in_10q(self, apple_10q_2020_q2):
        """Test that Income Tax Expense is positive in 10-Q."""
        stmt = apple_10q_2020_q2.statements.income_statement()
        df = stmt.to_dataframe()

        # Find Income Tax Expense (non-dimensional, non-abstract)
        rows = df[df['concept'].str.contains('IncomeTaxExpense', case=False, na=False)]
        rows = rows[(rows['dimension'] == False) & (rows['abstract'] == False)]

        assert not rows.empty, "Income Tax Expense not found in income statement"

        row = rows.iloc[0]
        value = row['2020-03-28']

        assert value > 0, f"Income Tax Expense should be positive, got {value}"
        assert value == pytest.approx(5568000000.0), f"Expected 5,568,000,000, got {value}"

    def test_cost_of_goods_and_services_positive_in_10k(self, apple_10k_2020):
        """Test that Cost of Goods and Services Sold is positive in 10-K."""
        stmt = apple_10k_2020.statements.income_statement()
        df = stmt.to_dataframe()

        # Find Cost of Goods and Services Sold (non-dimensional, non-abstract)
        rows = df[df['concept'].str.contains('CostOfGoodsAndServicesSold', case=False, na=False)]
        rows = rows[(rows['dimension'] == False) & (rows['abstract'] == False)]

        assert not rows.empty, "Cost of Goods and Services Sold not found in income statement"

        row = rows.iloc[0]
        value = row['2020-06-27']

        assert value > 0, f"Cost of Goods and Services Sold should be positive, got {value}"
        assert value == pytest.approx(129550000000.0), f"Expected 129,550,000,000, got {value}"

    def test_cost_of_goods_and_services_positive_in_10q(self, apple_10q_2020_q2):
        """Test that Cost of Goods and Services Sold is positive in 10-Q."""
        stmt = apple_10q_2020_q2.statements.income_statement()
        df = stmt.to_dataframe()

        # Find Cost of Goods and Services Sold (non-dimensional, non-abstract)
        rows = df[df['concept'].str.contains('CostOfGoodsAndServicesSold', case=False, na=False)]
        rows = rows[(rows['dimension'] == False) & (rows['abstract'] == False)]

        assert not rows.empty, "Cost of Goods and Services Sold not found in income statement"

        row = rows.iloc[0]
        value = row['2020-03-28']

        assert value > 0, f"Cost of Goods and Services Sold should be positive, got {value}"
        assert value == pytest.approx(92545000000.0), f"Expected 92,545,000,000, got {value}"

    def test_operating_expenses_remain_positive(self, apple_10k_2020):
        """Test that Operating Expenses remain positive (should already be positive)."""
        stmt = apple_10k_2020.statements.income_statement()
        df = stmt.to_dataframe()

        # Find Operating Expenses (non-dimensional, non-abstract)
        rows = df[df['concept'].str.contains('OperatingExpenses', case=False, na=False)]
        rows = rows[(rows['dimension'] == False) & (rows['abstract'] == False)]

        if not rows.empty:
            row = rows.iloc[0]
            value = row['2020-06-27']

            if value is not None and isinstance(value, (int, float)):
                assert value > 0, f"Operating Expenses should be positive, got {value}"

    def test_sign_consistency_across_filing_types(self, apple_10k_2020, apple_10q_2020_q2):
        """Test that expense signs are consistent between 10-K and 10-Q."""
        # Check Income Tax Expense
        stmt_k = apple_10k_2020.statements.income_statement()
        df_k = stmt_k.to_dataframe()

        stmt_q = apple_10q_2020_q2.statements.income_statement()
        df_q = stmt_q.to_dataframe()

        # Income Tax Expense
        rows_k = df_k[df_k['concept'].str.contains('IncomeTaxExpense', case=False, na=False)]
        rows_k = rows_k[(rows_k['dimension'] == False) & (rows_k['abstract'] == False)]

        rows_q = df_q[df_q['concept'].str.contains('IncomeTaxExpense', case=False, na=False)]
        rows_q = rows_q[(rows_q['dimension'] == False) & (rows_q['abstract'] == False)]

        if not rows_k.empty and not rows_q.empty:
            value_k = rows_k.iloc[0]['2020-06-27']
            value_q = rows_q.iloc[0]['2020-03-28']

            # Both should have the same sign (positive)
            assert (value_k > 0) == (value_q > 0), \
                "Income Tax Expense sign should be consistent across filing types"

        # Cost of Goods and Services Sold
        rows_k = df_k[df_k['concept'].str.contains('CostOfGoodsAndServicesSold', case=False, na=False)]
        rows_k = rows_k[(rows_k['dimension'] == False) & (rows_k['abstract'] == False)]

        rows_q = df_q[df_q['concept'].str.contains('CostOfGoodsAndServicesSold', case=False, na=False)]
        rows_q = rows_q[(rows_q['dimension'] == False) & (rows_q['abstract'] == False)]

        if not rows_k.empty and not rows_q.empty:
            value_k = rows_k.iloc[0]['2020-06-27']
            value_q = rows_q.iloc[0]['2020-03-28']

            # Both should have the same sign (positive)
            assert (value_k > 0) == (value_q > 0), \
                "Cost of Goods and Services Sold sign should be consistent across filing types"
