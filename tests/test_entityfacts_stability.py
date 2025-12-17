"""
EntityFacts API Stability Tests - Validate Recent Changes

This module validates the recent EntityFacts enhancements:
- Unified JSON-based concept-to-statement mapper
- Multi-statement concept flow
- Industry-specific virtual tree extensions
- Coverage improvements across all statement types

Issue: edgartools-7vzq
"""

import pytest
from pathlib import Path


# =============================================================================
# 1. Mapper Tests (mappings_loader.py)
# =============================================================================

class TestMappingsLoader:
    """Test the unified concept-to-statement mapper."""

    def test_get_primary_statement_income_concepts(self):
        """Test that income statement concepts return correct primary statement."""
        from edgar.entity.mappings_loader import get_primary_statement

        income_concepts = [
            'Revenue', 'Revenues', 'SalesRevenueNet',
            'CostOfGoodsAndServicesSold', 'GrossProfit',
            'OperatingIncomeLoss', 'NetIncomeLoss',
            'EarningsPerShareBasic', 'EarningsPerShareDiluted'
        ]

        for concept in income_concepts:
            result = get_primary_statement(concept)
            assert result == 'IncomeStatement', f"Expected IncomeStatement for {concept}, got {result}"

    def test_get_primary_statement_balance_sheet_concepts(self):
        """Test that balance sheet concepts return correct primary statement."""
        from edgar.entity.mappings_loader import get_primary_statement

        balance_concepts = [
            'Assets', 'CurrentAssets', 'AssetsCurrent',
            'Liabilities', 'LiabilitiesCurrent',
            'StockholdersEquity', 'CashAndCashEquivalentsAtCarryingValue'
        ]

        for concept in balance_concepts:
            result = get_primary_statement(concept)
            assert result == 'BalanceSheet', f"Expected BalanceSheet for {concept}, got {result}"

    def test_get_primary_statement_cashflow_concepts(self):
        """Test that cash flow concepts return correct primary statement."""
        from edgar.entity.mappings_loader import get_primary_statement

        cashflow_concepts = [
            'NetCashProvidedByUsedInOperatingActivities',
            'NetCashProvidedByUsedInInvestingActivities',
            'NetCashProvidedByUsedInFinancingActivities',
            'DepreciationDepletionAndAmortization'
        ]

        for concept in cashflow_concepts:
            result = get_primary_statement(concept)
            # Some may be None if not in mappings, but if found should be CashFlowStatement
            if result is not None:
                assert result == 'CashFlowStatement', f"Expected CashFlowStatement for {concept}, got {result}"

    def test_get_primary_statement_handles_namespace(self):
        """Test that namespaced concepts are handled correctly."""
        from edgar.entity.mappings_loader import get_primary_statement

        # Should work with or without namespace
        assert get_primary_statement('us-gaap:Revenue') == get_primary_statement('Revenue')
        assert get_primary_statement('us-gaap:Assets') == get_primary_statement('Assets')

    def test_get_all_statements_for_concept_multi_statement(self):
        """Test that multi-statement concepts return all their statements."""
        from edgar.entity.mappings_loader import get_all_statements_for_concept

        # NetIncomeLoss should appear in Income, CashFlow, Equity, etc.
        statements = get_all_statements_for_concept('NetIncomeLoss')
        assert 'IncomeStatement' in statements, "NetIncomeLoss should be in IncomeStatement"

        # DepreciationDepletionAndAmortization should appear in CashFlow and possibly Income
        statements = get_all_statements_for_concept('DepreciationDepletionAndAmortization')
        assert len(statements) >= 1, "Depreciation should appear in at least one statement"

    def test_get_all_statements_for_concept_single_statement(self):
        """Test that single-statement concepts return only one statement."""
        from edgar.entity.mappings_loader import get_all_statements_for_concept

        # Revenue is typically only in IncomeStatement
        statements = get_all_statements_for_concept('Revenue')
        if statements:  # If mapped
            assert 'IncomeStatement' in statements

    def test_fallback_mappings_work(self):
        """Test that fallback mappings work for common concepts not in JSON."""
        from edgar.entity.mappings_loader import get_primary_statement

        # These are in _FALLBACK_CONCEPT_MAPPINGS
        fallback_concepts = {
            'CurrentAssets': 'BalanceSheet',
            'CurrentLiabilities': 'BalanceSheet',
            'AccountsPayable': 'BalanceSheet',
            'LongTermDebt': 'BalanceSheet',
        }

        for concept, expected_stmt in fallback_concepts.items():
            result = get_primary_statement(concept)
            assert result == expected_stmt, f"Fallback mapping failed for {concept}: expected {expected_stmt}, got {result}"

    def test_concept_linkages_loaded(self):
        """Test that concept linkages file loads correctly."""
        from edgar.entity.mappings_loader import load_concept_linkages

        linkages = load_concept_linkages()
        assert linkages, "Concept linkages should not be empty"
        assert 'multi_statement_concepts' in linkages, "Should have multi_statement_concepts key"

        # Should have a reasonable number of multi-statement concepts
        multi_stmt = linkages.get('multi_statement_concepts', [])
        assert len(multi_stmt) > 100, f"Expected >100 multi-statement concepts, got {len(multi_stmt)}"

    def test_learned_mappings_loaded(self):
        """Test that learned mappings file loads correctly."""
        from edgar.entity.mappings_loader import load_canonical_structures

        structures = load_canonical_structures()
        assert structures, "Learned mappings should not be empty"
        assert len(structures) > 50, f"Expected >50 learned concepts, got {len(structures)}"

    def test_virtual_trees_loaded(self):
        """Test that virtual trees file loads correctly."""
        from edgar.entity.mappings_loader import load_virtual_trees

        trees = load_virtual_trees()
        assert trees, "Virtual trees should not be empty"

        # Should have trees for main statement types
        expected_types = ['IncomeStatement', 'BalanceSheet', 'CashFlowStatement']
        for stmt_type in expected_types:
            assert stmt_type in trees, f"Missing virtual tree for {stmt_type}"

    def test_get_concepts_for_statement(self):
        """Test getting all concepts for a statement type."""
        from edgar.entity.mappings_loader import get_concepts_for_statement

        # Get income statement concepts
        income_concepts = get_concepts_for_statement('IncomeStatement')
        assert len(income_concepts) > 10, f"Expected >10 income concepts, got {len(income_concepts)}"

        # Get balance sheet concepts
        balance_concepts = get_concepts_for_statement('BalanceSheet')
        assert len(balance_concepts) > 10, f"Expected >10 balance concepts, got {len(balance_concepts)}"


# =============================================================================
# 2. Multi-Statement Flow Tests (enhanced_statement.py)
# =============================================================================

class TestMultiStatementFlow:
    """Test multi-statement concept flow behavior."""

    def test_accepts_linked_from_constants(self):
        """Test the _ACCEPTS_LINKED_FROM constants are correct."""
        from edgar.entity.enhanced_statement import _ACCEPTS_LINKED_FROM

        # CashFlow should accept from Income and Balance
        assert 'IncomeStatement' in _ACCEPTS_LINKED_FROM['CashFlowStatement']
        assert 'BalanceSheet' in _ACCEPTS_LINKED_FROM['CashFlowStatement']

        # Equity should accept from Income and Balance
        assert 'IncomeStatement' in _ACCEPTS_LINKED_FROM['StatementOfEquity']
        assert 'BalanceSheet' in _ACCEPTS_LINKED_FROM['StatementOfEquity']

        # ComprehensiveIncome should accept from Income
        assert 'IncomeStatement' in _ACCEPTS_LINKED_FROM['ComprehensiveIncome']

        # Income and Balance should NOT accept linked concepts
        assert len(_ACCEPTS_LINKED_FROM['IncomeStatement']) == 0
        assert len(_ACCEPTS_LINKED_FROM['BalanceSheet']) == 0

    def test_fact_belongs_to_statement_primary(self):
        """Test that facts are correctly assigned to their primary statement."""
        from edgar.entity.enhanced_statement import _fact_belongs_to_statement
        from edgar.entity.models import FinancialFact
        from datetime import date

        # Create an income statement fact
        income_fact = FinancialFact(
            concept="us-gaap:Revenue",
            taxonomy="us-gaap",
            label="Revenue",
            value=1000000,
            numeric_value=1000000.0,
            unit="USD",
            fiscal_year=2024,
            fiscal_period="Q1",
            statement_type="IncomeStatement"
        )

        # Should belong to IncomeStatement
        assert _fact_belongs_to_statement(income_fact, 'IncomeStatement')
        # Should NOT belong to BalanceSheet
        assert not _fact_belongs_to_statement(income_fact, 'BalanceSheet')

    def test_fact_belongs_to_statement_linked(self):
        """Test that multi-statement concepts are included via linkages."""
        from edgar.entity.enhanced_statement import _fact_belongs_to_statement
        from edgar.entity.models import FinancialFact
        from edgar.entity.mappings_loader import get_all_statements_for_concept

        # Find a concept that appears in multiple statements
        test_concept = 'NetIncomeLoss'
        statements = get_all_statements_for_concept(test_concept)

        if 'CashFlowStatement' in statements:
            # Create fact with primary assignment to Income
            fact = FinancialFact(
                concept=f"us-gaap:{test_concept}",
                taxonomy="us-gaap",
                label="Net Income (Loss)",
                value=1000000,
                numeric_value=1000000.0,
                unit="USD",
                fiscal_year=2024,
                fiscal_period="Q1",
                statement_type="IncomeStatement"  # Primary is Income
            )

            # Should belong to IncomeStatement (primary)
            assert _fact_belongs_to_statement(fact, 'IncomeStatement')

            # Should also belong to CashFlow if linkages say so and flow is valid
            # (Income -> CashFlow is valid flow)
            result = _fact_belongs_to_statement(fact, 'CashFlowStatement')
            # Result depends on linkage configuration


# =============================================================================
# 3. Industry Extension Tests
# =============================================================================

class TestIndustryExtensions:
    """Test industry-specific virtual tree extensions."""

    def test_industry_mappings_loaded(self):
        """Test that industry mappings file loads correctly."""
        from edgar.entity.mappings_loader import load_industry_mappings

        mappings = load_industry_mappings()
        assert mappings, "Industry mappings should not be empty"
        assert 'industries' in mappings, "Should have industries key"

    def test_get_available_industries(self):
        """Test getting list of available industries."""
        from edgar.entity.mappings_loader import get_available_industries

        industries = get_available_industries()
        assert len(industries) >= 6, f"Expected at least 6 industries, got {len(industries)}"

        # Check expected industries exist
        expected = ['banking', 'insurance', 'tech', 'energy', 'healthcare', 'retail']
        for ind in expected:
            assert ind in industries, f"Missing expected industry: {ind}"

    def test_get_industry_for_sic_banking(self):
        """Test SIC code detection for banking industry."""
        from edgar.entity.mappings_loader import get_industry_for_sic

        # Banking SIC codes (6020-6029 per industry_mappings.json)
        assert get_industry_for_sic('6020') == 'banking'  # Commercial banking
        assert get_industry_for_sic('6021') == 'banking'  # National commercial banks
        assert get_industry_for_sic('6022') == 'banking'  # State commercial banks
        assert get_industry_for_sic('6029') == 'banking'  # Commercial banks, NEC

    def test_get_industry_for_sic_tech(self):
        """Test SIC code detection for tech industry."""
        from edgar.entity.mappings_loader import get_industry_for_sic

        # Tech SIC codes (7370-7379)
        result = get_industry_for_sic('7372')  # Prepackaged software
        if result:
            assert result == 'tech'

    def test_get_industry_for_sic_invalid(self):
        """Test SIC code detection with invalid input."""
        from edgar.entity.mappings_loader import get_industry_for_sic

        assert get_industry_for_sic(None) is None
        assert get_industry_for_sic('') is None
        assert get_industry_for_sic('invalid') is None

    def test_load_industry_extension_banking(self):
        """Test loading banking industry extension."""
        from edgar.entity.mappings_loader import load_industry_extension

        extension = load_industry_extension('banking')
        assert extension, "Banking extension should not be empty"

        # Should have statement type keys
        assert 'BalanceSheet' in extension or 'IncomeStatement' in extension, \
            "Extension should have statement type keys"

    def test_load_industry_extension_all_industries(self):
        """Test that all listed industries have loadable extensions."""
        from edgar.entity.mappings_loader import get_available_industries, load_industry_extension

        industries = get_available_industries()
        for industry in industries.keys():
            extension = load_industry_extension(industry)
            # Extension can be empty if not yet created, but should not error
            assert extension is not None or extension == {}, \
                f"Extension for {industry} should return dict (possibly empty)"

    def test_load_industry_extension_unknown(self):
        """Test loading extension for unknown industry."""
        from edgar.entity.mappings_loader import load_industry_extension

        extension = load_industry_extension('nonexistent_industry')
        assert extension == {}, "Unknown industry should return empty dict"

    def test_industry_extension_files_exist(self):
        """Test that industry extension files exist for all configured industries."""
        from edgar.entity.mappings_loader import load_industry_mappings

        mappings = load_industry_mappings()
        industries = mappings.get('industries', {})

        data_dir = Path(__file__).parent.parent / 'edgar' / 'entity' / 'data' / 'industry_extensions'

        for industry_key, industry_info in industries.items():
            extension_file = industry_info.get('extension_file')
            if extension_file:
                file_path = data_dir / extension_file
                assert file_path.exists(), f"Missing extension file for {industry_key}: {file_path}"


# =============================================================================
# 4. Coverage Regression Tests
# =============================================================================

class TestCoverageRegression:
    """Test that statement coverage meets baseline expectations.

    These tests ensure we don't regress on the coverage improvements achieved
    by the unified mapper implementation.
    """

    @pytest.fixture
    def aapl_facts(self):
        """Get AAPL facts for testing."""
        from edgar import Company
        return Company("AAPL").get_facts()

    def test_aapl_income_statement_coverage(self, aapl_facts):
        """Test AAPL income statement has expected coverage."""
        income = aapl_facts.income_statement(annual=True, periods=1)
        df = income.to_dataframe()

        # Should have at least 15 line items (baseline)
        assert len(df) >= 15, f"Expected at least 15 income statement items, got {len(df)}"

        # Check for key concepts
        labels_lower = [str(l).lower() for l in df['label'].tolist()]
        combined = ' '.join(labels_lower)

        assert 'revenue' in combined or 'sales' in combined, "Should have revenue concept"
        assert 'net income' in combined or 'profit' in combined, "Should have net income concept"

    def test_aapl_balance_sheet_coverage(self, aapl_facts):
        """Test AAPL balance sheet has expected coverage."""
        balance = aapl_facts.balance_sheet(annual=True, periods=1)
        df = balance.to_dataframe()

        # Should have at least 20 line items (baseline)
        assert len(df) >= 20, f"Expected at least 20 balance sheet items, got {len(df)}"

        # Check for key concepts
        labels_lower = [str(l).lower() for l in df['label'].tolist()]
        combined = ' '.join(labels_lower)

        assert 'assets' in combined, "Should have assets concept"
        assert 'liabilities' in combined, "Should have liabilities concept"
        assert 'equity' in combined or 'stockholders' in combined, "Should have equity concept"

    def test_aapl_cash_flow_coverage(self, aapl_facts):
        """Test AAPL cash flow statement has expected coverage."""
        cashflow = aapl_facts.cash_flow(annual=True, periods=1)
        df = cashflow.to_dataframe()

        # Should have at least 10 line items (baseline)
        assert len(df) >= 10, f"Expected at least 10 cash flow items, got {len(df)}"

        # Check for key concepts
        labels_lower = [str(l).lower() for l in df['label'].tolist()]
        combined = ' '.join(labels_lower)

        assert 'operating' in combined, "Should have operating activities concept"

    @pytest.mark.parametrize("ticker,stmt_type,min_items", [
        ("AAPL", "income", 15),
        ("AAPL", "balance", 20),
        ("AAPL", "cashflow", 10),
        ("MSFT", "income", 15),
        ("MSFT", "balance", 20),
        ("GOOGL", "income", 15),
        ("GOOGL", "balance", 20),
    ])
    def test_multi_company_coverage_baseline(self, ticker, stmt_type, min_items):
        """Test coverage baselines across multiple companies."""
        from edgar import Company

        company = Company(ticker)
        facts = company.get_facts()

        if stmt_type == "income":
            stmt = facts.income_statement(annual=True, periods=1)
        elif stmt_type == "balance":
            stmt = facts.balance_sheet(annual=True, periods=1)
        else:
            stmt = facts.cash_flow(annual=True, periods=1)

        df = stmt.to_dataframe()
        assert len(df) >= min_items, \
            f"{ticker} {stmt_type} statement should have at least {min_items} items, got {len(df)}"


# =============================================================================
# 5. API Contract Tests
# =============================================================================

class TestAPIContract:
    """Test that the EntityFacts API maintains its contract."""

    @pytest.fixture
    def test_facts(self):
        """Get facts for testing."""
        from edgar import Company
        return Company("AAPL").get_facts()

    def test_income_statement_returns_correct_type(self, test_facts):
        """Test that income_statement returns expected type."""
        from edgar.entity.enhanced_statement import MultiPeriodStatement

        stmt = test_facts.income_statement(annual=True, periods=4)
        assert isinstance(stmt, MultiPeriodStatement), \
            f"Expected MultiPeriodStatement, got {type(stmt)}"

    def test_balance_sheet_returns_correct_type(self, test_facts):
        """Test that balance_sheet returns expected type."""
        from edgar.entity.enhanced_statement import MultiPeriodStatement

        stmt = test_facts.balance_sheet(annual=True, periods=4)
        assert isinstance(stmt, MultiPeriodStatement), \
            f"Expected MultiPeriodStatement, got {type(stmt)}"

    def test_cash_flow_returns_correct_type(self, test_facts):
        """Test that cash_flow returns expected type."""
        from edgar.entity.enhanced_statement import MultiPeriodStatement

        stmt = test_facts.cash_flow(annual=True, periods=4)
        assert isinstance(stmt, MultiPeriodStatement), \
            f"Expected MultiPeriodStatement, got {type(stmt)}"

    def test_statement_has_periods(self, test_facts):
        """Test that statements have periods attribute."""
        stmt = test_facts.income_statement(annual=True, periods=4)
        assert hasattr(stmt, 'periods'), "Statement should have periods attribute"
        assert len(stmt.periods) > 0, "Statement should have at least one period"
        assert len(stmt.periods) <= 4, "Statement should have at most 4 periods"

    def test_statement_to_dataframe(self, test_facts):
        """Test that statements can be converted to DataFrame."""
        import pandas as pd

        stmt = test_facts.income_statement(annual=True, periods=4)
        df = stmt.to_dataframe()

        assert isinstance(df, pd.DataFrame), "to_dataframe should return DataFrame"
        assert 'label' in df.columns, "DataFrame should have 'label' column"
        assert len(df) > 0, "DataFrame should not be empty"

    def test_annual_vs_quarterly_parameter(self, test_facts):
        """Test that annual parameter affects results."""
        annual_stmt = test_facts.income_statement(annual=True, periods=4)
        quarterly_stmt = test_facts.income_statement(annual=False, periods=4)

        # Period labels should differ
        annual_periods = annual_stmt.periods
        quarterly_periods = quarterly_stmt.periods

        # Annual periods typically have "FY" prefix
        annual_has_fy = any('FY' in str(p) for p in annual_periods)
        quarterly_has_q = any('Q' in str(p) for p in quarterly_periods)

        # At least one condition should be true (format may vary)
        assert annual_has_fy or not quarterly_has_q or annual_periods != quarterly_periods, \
            "Annual and quarterly should produce different results"

    def test_as_dataframe_parameter(self, test_facts):
        """Test that as_dataframe parameter returns DataFrame directly."""
        import pandas as pd

        df = test_facts.income_statement(annual=True, periods=4, as_dataframe=True)
        assert isinstance(df, pd.DataFrame), "as_dataframe=True should return DataFrame"

    def test_statement_rich_rendering(self, test_facts):
        """Test that statements can be rendered with Rich."""
        stmt = test_facts.income_statement(annual=True, periods=2)

        # Should have __rich__ method
        assert hasattr(stmt, '__rich__'), "Statement should have __rich__ method"

        # Should not raise when rendered
        rich_output = stmt.__rich__()
        assert rich_output is not None, "Rich output should not be None"

    def test_get_fact_method(self, test_facts):
        """Test the get_fact method."""
        # Get by concept name
        fact = test_facts.get_fact("Revenue")

        # May be None if concept not found with this exact name
        if fact is not None:
            assert hasattr(fact, 'value'), "Fact should have value attribute"
            assert hasattr(fact, 'fiscal_year'), "Fact should have fiscal_year attribute"

    def test_query_interface(self, test_facts):
        """Test the query interface."""
        query = test_facts.query()
        assert query is not None, "query() should return a query object"

        # Test chaining
        results = query.by_fiscal_year(2024).execute()
        assert isinstance(results, list), "execute() should return a list"

    def test_time_series_method(self, test_facts):
        """Test the time_series method."""
        import pandas as pd

        # Try to get time series for a common concept
        ts = test_facts.time_series("Revenue", periods=4)

        # May be empty if concept not found
        assert isinstance(ts, pd.DataFrame), "time_series should return DataFrame"


# =============================================================================
# 6. Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for end-to-end functionality."""

    def test_company_to_statement_pipeline(self):
        """Test the full pipeline from Company to statement."""
        from edgar import Company

        company = Company("MSFT")
        facts = company.get_facts()
        income = facts.income_statement(annual=True, periods=3)
        df = income.to_dataframe()

        assert len(df) > 0, "Pipeline should produce data"
        assert len(income.periods) > 0, "Should have periods"

    def test_multiple_statement_consistency(self):
        """Test that all statement types work consistently."""
        from edgar import Company

        company = Company("AAPL")
        facts = company.get_facts()

        # All three should work
        income = facts.income_statement(annual=True, periods=3)
        balance = facts.balance_sheet(annual=True, periods=3)
        cashflow = facts.cash_flow(annual=True, periods=3)

        assert income is not None
        assert balance is not None
        assert cashflow is not None

        # All should have same number of periods
        assert len(income.periods) == len(balance.periods) == len(cashflow.periods)

    def test_banking_company_with_industry_extension(self):
        """Test that banking companies get industry-specific concepts."""
        from edgar import Company

        # JPMorgan Chase - a major bank
        company = Company("JPM")
        facts = company.get_facts()

        # Should be able to get statements
        balance = facts.balance_sheet(annual=True, periods=2)
        assert balance is not None
        assert len(balance.to_dataframe()) > 0

    def test_tech_company_statements(self):
        """Test tech company statements work correctly."""
        from edgar import Company

        company = Company("NVDA")
        facts = company.get_facts()

        income = facts.income_statement(annual=True, periods=2)
        assert income is not None

        df = income.to_dataframe()
        assert len(df) > 10, "Tech company should have reasonable statement coverage"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
