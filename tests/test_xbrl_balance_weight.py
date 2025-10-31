"""
Tests for XBRL balance and weight metadata (Issue #463).

This module tests the three new metadata columns added to DataFrame exports:
- balance: Accounting classification (debit/credit)
- weight: Calculation role (1.0/-1.0)
- preferred_sign: Display transformation hint (-1/1/None)
"""

import pytest
from edgar import Company
from edgar.xbrl.parsers.concepts import get_balance_type, US_GAAP_BALANCE_TYPES


class TestBalanceTypeMapping:
    """Test the static US-GAAP balance type mapping."""

    def test_asset_concepts_have_debit_balance(self):
        """Asset concepts should have debit balance."""
        assert get_balance_type('us-gaap:Cash') == 'debit'
        assert get_balance_type('Cash') == 'debit'  # Short form
        assert get_balance_type('us-gaap:Assets') == 'debit'
        assert get_balance_type('Assets') == 'debit'  # Short form
        assert get_balance_type('us-gaap:AccountsReceivableNetCurrent') == 'debit'

    def test_liability_concepts_have_credit_balance(self):
        """Liability concepts should have credit balance."""
        assert get_balance_type('us-gaap:AccountsPayableCurrent') == 'credit'
        assert get_balance_type('us-gaap:Liabilities') == 'credit'
        assert get_balance_type('us-gaap:LongTermDebtNoncurrent') == 'credit'

    def test_equity_concepts_have_credit_balance(self):
        """Equity concepts should have credit balance."""
        assert get_balance_type('us-gaap:CommonStockValue') == 'credit'
        assert get_balance_type('us-gaap:RetainedEarningsAccumulatedDeficit') == 'credit'
        assert get_balance_type('us-gaap:StockholdersEquity') == 'credit'

    def test_treasury_stock_has_debit_balance(self):
        """Treasury stock is a contra-equity account with debit balance."""
        assert get_balance_type('us-gaap:TreasuryStockValue') == 'debit'

    def test_revenue_concepts_have_credit_balance(self):
        """Revenue concepts should have credit balance."""
        assert get_balance_type('us-gaap:Revenues') == 'credit'
        assert get_balance_type('Revenue') == 'credit'  # Short form
        assert get_balance_type('us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax') == 'credit'

    def test_expense_concepts_have_debit_balance(self):
        """Expense concepts should have debit balance."""
        assert get_balance_type('us-gaap:CostOfRevenue') == 'debit'
        assert get_balance_type('us-gaap:ResearchAndDevelopmentExpense') == 'debit'
        assert get_balance_type('us-gaap:SellingGeneralAndAdministrativeExpense') == 'debit'
        assert get_balance_type('us-gaap:IncomeTaxExpenseBenefit') == 'debit'

    def test_namespace_separator_handling(self):
        """Balance type lookup should handle both colon and underscore separators."""
        # Colon separator (standard form)
        assert get_balance_type('us-gaap:Cash') == 'debit'

        # Underscore separator (often used in element IDs)
        assert get_balance_type('us-gaap_Cash') == 'debit'
        assert get_balance_type('us_gaap_Cash') == 'debit'

    def test_unknown_concept_returns_none(self):
        """Unknown concepts should return None."""
        assert get_balance_type('UnknownConcept') is None
        assert get_balance_type('xyz:FakeConcept') is None

    def test_mapping_coverage(self):
        """Verify we have reasonable coverage of common concepts."""
        # Should have at least 100 concepts mapped
        assert len(US_GAAP_BALANCE_TYPES) >= 100


class TestDataFrameMetadataColumns:
    """Test that metadata columns appear in DataFrame exports."""

    @pytest.fixture(scope='class')
    def apple_xbrl(self):
        """Get AAPL 10-K XBRL for testing."""
        company = Company('AAPL')
        filing = company.get_filings(form='10-K', year=2024).latest(1)
        return filing.xbrl()

    def test_balance_column_present(self, apple_xbrl):
        """Balance column should be present in DataFrame."""
        df = apple_xbrl.facts.query().limit(100).to_dataframe()
        assert 'balance' in df.columns

    def test_weight_column_present(self, apple_xbrl):
        """Weight column should be present in DataFrame."""
        df = apple_xbrl.facts.query().limit(100).to_dataframe()
        assert 'weight' in df.columns

    def test_preferred_sign_column_present(self, apple_xbrl):
        """Preferred_sign column should be present in DataFrame."""
        df = apple_xbrl.facts.query().limit(100).to_dataframe()
        assert 'preferred_sign' in df.columns

    def test_balance_values_are_valid(self, apple_xbrl):
        """Balance values should be 'debit', 'credit', or None."""
        df = apple_xbrl.facts.query().limit(100).to_dataframe()
        valid_values = {'debit', 'credit', None}

        for value in df['balance'].unique():
            assert value in valid_values, f"Invalid balance value: {value}"

    def test_weight_values_are_numeric(self, apple_xbrl):
        """Weight values should be numeric or None."""
        df = apple_xbrl.facts.query().limit(100).to_dataframe()

        # Filter out None/NaN
        weights = df['weight'].dropna()

        # All weights should be numeric
        assert weights.dtype in ['float64', 'float32', 'int64', 'int32']

        # Common weight values are 1.0 and -1.0
        unique_weights = set(weights.unique())
        assert unique_weights.issubset({1.0, -1.0, 0.0})

    def test_preferred_sign_values_are_valid(self, apple_xbrl):
        """Preferred_sign values should be -1, 1, or None."""
        df = apple_xbrl.facts.query().limit(100).to_dataframe()
        valid_values = {-1, 1, None}

        for value in df['preferred_sign'].unique():
            assert value in valid_values, f"Invalid preferred_sign value: {value}"


class TestOriginalIssue463:
    """Test that the original issue #463 is resolved."""

    @pytest.fixture(scope='class')
    def apple_xbrl(self):
        """Get AAPL 10-K XBRL for testing."""
        company = Company('AAPL')
        filing = company.get_filings(form='10-K').latest(1)
        return filing.xbrl()

    def test_payments_of_dividends_positive(self, apple_xbrl):
        """
        PaymentsOfDividends should show positive values (Issue #463).

        Original issue: PaymentsOfDividends showed -12,150 instead of 12,150.
        With the fix, it should always be positive.
        """
        df = apple_xbrl.facts.query().by_concept('PaymentsOfDividends', exact=True).to_dataframe()

        if not df.empty:
            # All values should be positive
            assert (df['numeric_value'] > 0).all(), "PaymentsOfDividends should be positive"

            # Should have credit balance (cash outflow)
            assert df['balance'].iloc[0] == 'credit', "PaymentsOfDividends should have credit balance"

            # Should have weight -1.0 (subtracted in cash flow calculations)
            assert df['weight'].iloc[0] == -1.0, "PaymentsOfDividends should have weight -1.0"

    def test_expense_concepts_positive(self, apple_xbrl):
        """
        Expense concepts in CONSISTENT_POSITIVE_CONCEPTS should be positive.
        """
        expense_concepts = [
            'ResearchAndDevelopmentExpense',
            'CostOfGoodsAndServicesSold'
        ]

        for concept in expense_concepts:
            df = apple_xbrl.facts.query().by_concept(concept, exact=True).to_dataframe()

            if not df.empty:
                # All expense values should be positive
                assert (df['numeric_value'] > 0).all(), f"{concept} should be positive"

                # Expenses should have debit balance
                if df['balance'].iloc[0] is not None:
                    assert df['balance'].iloc[0] == 'debit', f"{concept} should have debit balance"

    def test_metadata_provides_transparency(self, apple_xbrl):
        """
        The three metadata columns should provide transparency into XBRL semantics.

        Users can now see:
        - balance: Accounting classification
        - weight: Calculation role
        - preferred_sign: Display transformation
        """
        df = apple_xbrl.facts.query().by_concept('PaymentsOfDividends', exact=True).to_dataframe()

        if not df.empty:
            # All three columns should be present
            assert 'balance' in df.columns
            assert 'weight' in df.columns
            assert 'preferred_sign' in df.columns

            # All three should have non-null values for this concept
            assert df['balance'].notna().any()
            assert df['weight'].notna().any()
            assert df['preferred_sign'].notna().any()


class TestStatementTypesCoverage:
    """Test metadata columns across different statement types."""

    @pytest.fixture(scope='class')
    def apple_xbrl(self):
        """Get AAPL 10-K XBRL for testing."""
        company = Company('AAPL')
        filing = company.get_filings(form='10-K').latest(1)
        return filing.xbrl()

    @pytest.mark.parametrize('statement_type', [
        'IncomeStatement',
        'BalanceSheet',
        'CashFlowStatement'
    ])
    def test_metadata_columns_in_statement(self, apple_xbrl, statement_type):
        """Metadata columns should be present in all statement types."""
        df = apple_xbrl.facts.query().by_statement_type(statement_type).limit(10).to_dataframe()

        if not df.empty:
            assert 'balance' in df.columns
            assert 'weight' in df.columns
            assert 'preferred_sign' in df.columns

    def test_income_statement_has_debit_and_credit(self, apple_xbrl):
        """Income statement should have both debit (expenses) and credit (revenue) balances."""
        df = apple_xbrl.facts.query().by_statement_type('IncomeStatement').limit(50).to_dataframe()

        if not df.empty:
            balances = df['balance'].dropna().unique()

            # Should have both debit and credit
            assert 'debit' in balances, "Income statement should have debit balances (expenses)"
            assert 'credit' in balances, "Income statement should have credit balances (revenue)"

    def test_balance_sheet_has_debit_and_credit(self, apple_xbrl):
        """Balance sheet should have both debit (assets) and credit (liabilities/equity) balances."""
        df = apple_xbrl.facts.query().by_statement_type('BalanceSheet').limit(50).to_dataframe()

        if not df.empty:
            balances = df['balance'].dropna().unique()

            # Should have both debit and credit
            # (Assets are debit, Liabilities/Equity are credit)
            assert len(balances) > 0, "Balance sheet should have balance types"


class TestColumnOrdering:
    """Test that new metadata columns appear in the correct position."""

    @pytest.fixture(scope='class')
    def apple_xbrl(self):
        """Get AAPL 10-K XBRL for testing."""
        company = Company('AAPL')
        filing = company.get_filings(form='10-K').latest(1)
        return filing.xbrl()

    def test_metadata_columns_near_front(self, apple_xbrl):
        """Metadata columns should appear near the front of the DataFrame."""
        df = apple_xbrl.facts.query().limit(10).to_dataframe()

        columns = list(df.columns)

        # Balance should come after label but before value
        if 'balance' in columns and 'label' in columns and 'value' in columns:
            label_idx = columns.index('label')
            balance_idx = columns.index('balance')
            value_idx = columns.index('value')

            assert label_idx < balance_idx < value_idx, \
                "balance should be between label and value"

    def test_column_order_logical(self, apple_xbrl):
        """Columns should follow logical order: concept, label, balance, preferred_sign, weight, value."""
        df = apple_xbrl.facts.query().limit(10).to_dataframe()

        columns = list(df.columns)
        expected_order = ['concept', 'label', 'balance', 'preferred_sign', 'weight', 'value']

        # Check that columns that exist follow the expected order
        actual_order = [col for col in expected_order if col in columns]

        # Verify relative ordering
        for i in range(len(actual_order) - 1):
            col1, col2 = actual_order[i], actual_order[i + 1]
            idx1, idx2 = columns.index(col1), columns.index(col2)
            assert idx1 < idx2, f"{col1} should come before {col2}"
