"""
Tests for standardized financial concept access methods (FEAT-411).

This module tests the new .get_revenue(), .get_net_income(), etc. methods
that provide consistent access to key financial concepts across all companies.
"""

import pytest
from datetime import date
from edgar import Company
from edgar.core import set_identity


# Set identity for SEC API requests
set_identity("EdgarTools Test Suite test@edgartools.dev")


class TestStandardizedConcepts:
    """Test standardized financial concept access methods."""

    def test_get_revenue_apple(self):
        """Test revenue standardization with Apple (uses RevenueFromContractWithCustomerExcludingAssessedTax)."""
        company = Company("AAPL")
        facts = company.get_facts()

        revenue = facts.get_revenue()
        assert revenue is not None, "Apple should have revenue data"
        assert revenue > 200_000_000_000, "Apple revenue should be > $200B"

        # Test with specific period
        revenue_2023 = facts.get_revenue(period="2023-FY")
        if revenue_2023:
            assert revenue_2023 > 200_000_000_000, "Apple 2023 revenue should be > $200B"

    def test_get_revenue_tesla(self):
        """Test revenue standardization with Tesla (may use different concept)."""
        company = Company("TSLA")
        facts = company.get_facts()

        revenue = facts.get_revenue()
        assert revenue is not None, "Tesla should have revenue data"
        assert revenue > 35_000_000_000, "Tesla revenue should be > $35B"

    def test_get_net_income_apple(self):
        """Test net income standardization with Apple."""
        company = Company("AAPL")
        facts = company.get_facts()

        net_income = facts.get_net_income()
        assert net_income is not None, "Apple should have net income data"
        assert net_income > 80_000_000_000, "Apple net income should be > $80B"

    def test_get_total_assets_apple(self):
        """Test total assets standardization with Apple."""
        company = Company("AAPL")
        facts = company.get_facts()

        assets = facts.get_total_assets()
        assert assets is not None, "Apple should have total assets data"
        assert assets > 350_000_000_000, "Apple assets should be > $350B"

    def test_get_total_liabilities_apple(self):
        """Test total liabilities standardization with Apple."""
        company = Company("AAPL")
        facts = company.get_facts()

        liabilities = facts.get_total_liabilities()
        assert liabilities is not None, "Apple should have total liabilities data"
        assert liabilities > 100_000_000_000, "Apple liabilities should be > $100B"

    def test_get_shareholders_equity_apple(self):
        """Test shareholders equity standardization with Apple."""
        company = Company("AAPL")
        facts = company.get_facts()

        equity = facts.get_shareholders_equity()
        assert equity is not None, "Apple should have shareholders equity data"
        assert equity > 50_000_000_000, "Apple equity should be > $50B"

    def test_get_operating_income_apple(self):
        """Test operating income standardization with Apple."""
        company = Company("AAPL")
        facts = company.get_facts()

        op_income = facts.get_operating_income()
        assert op_income is not None, "Apple should have operating income data"
        assert op_income > 100_000_000_000, "Apple operating income should be > $100B"

    def test_get_gross_profit_apple(self):
        """Test gross profit standardization with Apple."""
        company = Company("AAPL")
        facts = company.get_facts()

        gross_profit = facts.get_gross_profit()
        assert gross_profit is not None, "Apple should have gross profit data"
        assert gross_profit > 100_000_000_000, "Apple gross profit should be > $100B"

    def test_concept_consistency_apple(self):
        """Test that concepts are consistent and make financial sense."""
        company = Company("AAPL")
        facts = company.get_facts()

        revenue = facts.get_revenue()
        gross_profit = facts.get_gross_profit()
        net_income = facts.get_net_income()
        assets = facts.get_total_assets()
        liabilities = facts.get_total_liabilities()
        equity = facts.get_shareholders_equity()

        # Basic financial statement relationships
        if revenue and gross_profit:
            assert gross_profit <= revenue, "Gross profit should be <= revenue"

        if gross_profit and net_income:
            assert net_income <= gross_profit, "Net income should be <= gross profit"

        if assets and liabilities and equity:
            # Assets = Liabilities + Equity (accounting equation)
            # Allow for some rounding differences
            balance_diff = abs(assets - (liabilities + equity))
            assert balance_diff / assets < 0.01, "Assets should equal Liabilities + Equity"

    def test_period_specific_access(self):
        """Test accessing data for specific periods."""
        company = Company("AAPL")
        facts = company.get_facts()

        # Test quarterly access
        q4_revenue = facts.get_revenue(period="2023-Q4")
        annual_revenue = facts.get_revenue(period="2023-FY")

        if q4_revenue and annual_revenue:
            assert q4_revenue < annual_revenue, "Q4 revenue should be less than annual revenue"

    def test_unit_filtering(self):
        """Test unit filtering functionality."""
        company = Company("AAPL")
        facts = company.get_facts()

        # Test USD unit (default)
        revenue_usd = facts.get_revenue(unit="USD")
        revenue_default = facts.get_revenue()

        if revenue_usd and revenue_default:
            assert revenue_usd == revenue_default, "USD and default should return same value"

    def test_missing_concepts_return_none(self):
        """Test that missing concepts return None rather than throwing errors."""
        company = Company("AAPL")
        facts = company.get_facts()

        # Test with non-existent period
        missing_revenue = facts.get_revenue(period="1990-FY")
        assert missing_revenue is None, "Non-existent period should return None"

        # Test with impossible unit
        missing_unit = facts.get_revenue(unit="EUR")
        assert missing_unit is None, "Non-matching unit should return None"

    def test_concept_mapping_info(self):
        """Test the concept mapping info helper method."""
        company = Company("AAPL")
        facts = company.get_facts()

        revenue_concepts = [
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'SalesRevenueNet',
            'Revenues',
            'Revenue'
        ]

        info = facts.get_concept_mapping_info(revenue_concepts)

        assert 'available' in info
        assert 'missing' in info
        assert 'fact_details' in info
        assert len(info['available']) > 0, "Apple should have at least one revenue concept"

        # Check that fact details are complete
        for concept in info['available']:
            details = info['fact_details'][concept]
            assert 'label' in details
            assert 'unit' in details
            assert 'latest_value' in details

    def test_multiple_companies_consistency(self):
        """Test that standardized methods work consistently across different companies."""
        companies = ["AAPL", "MSFT", "GOOGL"]

        for ticker in companies:
            company = Company(ticker)
            facts = company.get_facts()

            # Each company should have revenue
            revenue = facts.get_revenue()
            assert revenue is not None, f"{ticker} should have revenue data"
            assert revenue > 10_000_000_000, f"{ticker} revenue should be > $10B"

            # Each company should have assets
            assets = facts.get_total_assets()
            assert assets is not None, f"{ticker} should have assets data"
            assert assets > 50_000_000_000, f"{ticker} assets should be > $50B"

    def test_fallback_calculations(self):
        """Test that fallback calculations work when primary concepts are missing."""
        company = Company("AAPL")
        facts = company.get_facts()

        # Test gross profit fallback calculation
        # Even if gross profit concept exists, test the calculation logic
        revenue = facts.get_revenue()

        if revenue:
            # Get cost of revenue to test calculation
            cost_fact = facts.get_fact('CostOfRevenue')
            if cost_fact and cost_fact.numeric_value:
                calculated_gross = revenue - cost_fact.numeric_value
                # This should be positive for profitable companies
                assert calculated_gross > 0, "Calculated gross profit should be positive"

    def test_edge_cases(self):
        """Test edge cases and error handling."""
        company = Company("AAPL")
        facts = company.get_facts()

        # Test with empty concept variants (this shouldn't happen in practice)
        result = facts._get_standardized_concept_value([])
        assert result is None, "Empty concept list should return None"

        # Test with invalid concept names
        result = facts._get_standardized_concept_value(['NonExistentConcept'])
        assert result is None, "Non-existent concept should return None"


class TestRealWorldScenarios:
    """Test real-world usage scenarios from FEAT-411."""

    def test_user_example_from_issue(self):
        """Test the exact example from the GitHub issue."""
        # This tests the specific use case that led to FEAT-411
        companies = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

        results = {}
        for ticker in companies:
            company = Company(ticker)
            facts = company.get_facts()

            results[ticker] = {
                'revenue': facts.get_revenue(),
                'net_income': facts.get_net_income(),
                'assets': facts.get_total_assets()
            }

        # Verify all companies have data
        for ticker, data in results.items():
            assert data['revenue'] is not None, f"{ticker} should have revenue"
            assert data['net_income'] is not None, f"{ticker} should have net income"
            assert data['assets'] is not None, f"{ticker} should have assets"

            # Basic sanity checks
            assert data['revenue'] > 0, f"{ticker} revenue should be positive"
            assert data['assets'] > 0, f"{ticker} assets should be positive"

    def test_multi_company_analysis_workflow(self):
        """Test a typical multi-company analysis workflow."""
        companies = ["AAPL", "MSFT"]
        metrics = []

        for ticker in companies:
            company = Company(ticker)
            facts = company.get_facts()

            revenue = facts.get_revenue()
            net_income = facts.get_net_income()
            assets = facts.get_total_assets()

            if revenue and net_income and assets:
                metrics.append({
                    'company': ticker,
                    'revenue': revenue,
                    'net_income': net_income,
                    'assets': assets,
                    'profit_margin': (net_income / revenue) * 100,
                    'roa': (net_income / assets) * 100
                })

        # Should have data for both companies
        assert len(metrics) == 2, "Should have metrics for both companies"

        # Verify calculated metrics make sense
        for metric in metrics:
            assert 0 < metric['profit_margin'] < 50, "Profit margin should be reasonable"
            assert 0 < metric['roa'] < 30, "ROA should be reasonable"

    def test_period_comparison_analysis(self):
        """Test period-over-period comparison analysis."""
        company = Company("AAPL")
        facts = company.get_facts()

        current_revenue = facts.get_revenue(period="2023-FY")
        prior_revenue = facts.get_revenue(period="2022-FY")

        if current_revenue and prior_revenue:
            growth_rate = ((current_revenue - prior_revenue) / prior_revenue) * 100
            # Apple should have some growth, but not more than 50%
            assert -20 < growth_rate < 50, "Revenue growth rate should be reasonable"

    def test_standardized_vs_direct_access(self):
        """Test that standardized methods return same values as direct fact access when possible."""
        company = Company("AAPL")
        facts = company.get_facts()

        # Get revenue using standardized method
        standardized_revenue = facts.get_revenue()

        # Get revenue using direct fact access
        direct_revenue = None
        for concept in ['RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues', 'Revenue']:
            fact = facts.get_fact(concept)
            if fact and fact.numeric_value:
                direct_revenue = fact.numeric_value
                break

        if standardized_revenue and direct_revenue:
            assert standardized_revenue == direct_revenue, "Standardized and direct access should return same value"