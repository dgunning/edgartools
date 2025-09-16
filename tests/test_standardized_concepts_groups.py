"""
Test standardized financial concepts using the company group testing framework.

This demonstrates the new elegant way to test features across curated company groups.
"""

import pytest
from tests.test_company_groups import (
    test_on_company_group,
    test_on_tech_giants,
    test_on_nasdaq_top20,
    test_on_diverse_sample
)


class TestStandardizedConceptsWithGroups:
    """Test standardized financial concept API using company groups."""

    @test_on_tech_giants(max_failures=2)
    def test_revenue_across_tech_companies(self, company):
        """Test revenue standardization across major tech companies."""
        facts = company.get_facts()
        revenue = facts.get_revenue()

        assert revenue is not None, f"{company.ticker} should have revenue data"
        assert revenue > 5_000_000_000, f"{company.ticker} should have > $5B revenue (tech giant)"

    @test_on_nasdaq_top20(max_failures=3)
    def test_core_metrics_nasdaq_top20(self, company):
        """Test core financial metrics on top 20 NASDAQ companies."""
        facts = company.get_facts()

        # Test the main standardized methods
        revenue = facts.get_revenue()
        net_income = facts.get_net_income()
        assets = facts.get_total_assets()

        # At least revenue should be available for top companies
        assert revenue is not None, f"{company.ticker} (top NASDAQ) should have revenue"

        # If we have both revenue and net income, check basic relationship
        if revenue and net_income:
            # Net income should be reasonable relative to revenue
            margin = (net_income / revenue) * 100
            assert -50 < margin < 60, f"{company.ticker} profit margin {margin:.1f}% seems unrealistic"

    @test_on_company_group("mega_cap", max_failures=1)
    def test_complete_financials_mega_cap(self, company):
        """Test that mega-cap companies have complete financial data."""
        facts = company.get_facts()

        # Mega-cap companies should have all core metrics
        revenue = facts.get_revenue()
        net_income = facts.get_net_income()
        assets = facts.get_total_assets()
        liabilities = facts.get_total_liabilities()
        equity = facts.get_shareholders_equity()

        assert revenue is not None, f"{company.ticker} (mega-cap) missing revenue"
        assert net_income is not None, f"{company.ticker} (mega-cap) missing net income"
        assert assets is not None, f"{company.ticker} (mega-cap) missing assets"

        # Test basic accounting equation if we have all components
        if assets and liabilities and equity:
            balance_diff = abs(assets - (liabilities + equity))
            balance_ratio = balance_diff / assets if assets != 0 else 0
            assert balance_ratio < 0.02, f"{company.ticker} balance sheet doesn't balance (diff: {balance_ratio:.1%})"

    @test_on_company_group("faang", max_failures=0)  # FAANG should all work
    def test_faang_standardization(self, company):
        """Test that standardized methods work perfectly on FAANG companies."""
        facts = company.get_facts()

        # FAANG companies should have comprehensive data
        revenue = facts.get_revenue()
        net_income = facts.get_net_income()
        operating_income = facts.get_operating_income()
        gross_profit = facts.get_gross_profit()

        assert revenue is not None, f"{company.ticker} (FAANG) missing revenue"
        assert net_income is not None, f"{company.ticker} (FAANG) missing net income"

        # Test relationships between metrics
        if gross_profit and revenue:
            gross_margin = (gross_profit / revenue) * 100
            assert 0 < gross_margin < 100, f"{company.ticker} unrealistic gross margin: {gross_margin:.1f}%"

        if operating_income and revenue:
            op_margin = (operating_income / revenue) * 100
            assert -20 < op_margin < 80, f"{company.ticker} unrealistic operating margin: {op_margin:.1f}%"

    @test_on_diverse_sample(max_failures=6)
    def test_concept_mapping_coverage(self, company):
        """Test concept mapping coverage across diverse companies."""
        facts = company.get_facts()

        # Test concept mapping info functionality
        revenue_concepts = [
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'SalesRevenueNet',
            'Revenues',
            'Revenue',
            'TotalRevenues',
            'NetSales'
        ]

        info = facts.get_concept_mapping_info(revenue_concepts)

        # Should get valid mapping info
        assert isinstance(info, dict), "Should return concept mapping info dict"
        assert 'available' in info, "Should have 'available' key"
        assert 'missing' in info, "Should have 'missing' key"
        assert 'fact_details' in info, "Should have 'fact_details' key"

        # Total should equal input concepts
        total_concepts = len(info['available']) + len(info['missing'])
        assert total_concepts == len(revenue_concepts), "Should account for all input concepts"

    @test_on_company_group("dow_sample", max_failures=3)
    def test_period_specific_access(self, company):
        """Test period-specific access on Dow Jones sample."""
        facts = company.get_facts()

        # Test current and prior year access
        current_revenue = facts.get_revenue(period="2024-FY")
        prior_revenue = facts.get_revenue(period="2023-FY")

        # At least one period should have data
        has_current = current_revenue is not None
        has_prior = prior_revenue is not None

        assert has_current or has_prior, f"{company.ticker} should have revenue for 2023 or 2024"

        # If both available, test growth calculation
        if has_current and has_prior and prior_revenue != 0:
            growth_rate = ((current_revenue - prior_revenue) / prior_revenue) * 100
            # Reasonable growth rate check (-50% to +100%)
            assert -50 < growth_rate < 100, f"{company.ticker} unrealistic growth: {growth_rate:.1f}%"

    def test_user_workflow_example(self):
        """Test the exact user workflow from FEAT-411 using groups."""
        from edgar.reference.company_subsets import filter_companies, get_all_companies

        # Create the exact group from the user's issue
        user_companies = filter_companies(
            get_all_companies(),
            ticker_list=["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
        )

        @test_on_company_group(user_companies, max_failures=0)
        def test_user_example(company):
            facts = company.get_facts()

            # The exact methods the user wanted
            revenue = facts.get_revenue()
            net_income = facts.get_net_income()
            assets = facts.get_total_assets()

            assert revenue is not None, f"{company.ticker} should have revenue"
            assert net_income is not None, f"{company.ticker} should have net income"
            assert assets is not None, f"{company.ticker} should have assets"

            # All should be positive for these profitable companies
            assert revenue > 0, f"{company.ticker} revenue should be positive"
            assert assets > 0, f"{company.ticker} assets should be positive"

        # Run the test
        result = test_user_example()
        assert result.success_rate == 100.0, "User example should work 100% for these companies"


# Additional convenience tests for different scenarios
class TestStandardizedConceptsEdgeCases:
    """Test edge cases and error handling with company groups."""

    @test_on_company_group("diverse_sample", max_failures=8)
    def test_missing_concepts_return_none(self, company):
        """Test that missing concepts return None rather than errors."""
        facts = company.get_facts()

        # Test with period that definitely doesn't exist
        old_revenue = facts.get_revenue(period="1990-FY")
        assert old_revenue is None, f"{company.ticker} should return None for 1990 data"

        # Test with non-matching unit
        eur_revenue = facts.get_revenue(unit="EUR")
        assert eur_revenue is None, f"{company.ticker} should return None for EUR currency"

    @test_on_company_group("tech_giants", max_failures=3)
    def test_unit_consistency(self, company):
        """Test that returned values have consistent units."""
        facts = company.get_facts()

        revenue = facts.get_revenue()
        assets = facts.get_total_assets()

        if revenue and assets:
            # Both should be in dollars (large numbers)
            assert revenue > 1_000_000, f"{company.ticker} revenue seems too small (unit issue?)"
            assert assets > 1_000_000, f"{company.ticker} assets seem too small (unit issue?)"

            # Assets should generally be larger than annual revenue
            # (This is true for most mature companies)
            if revenue > 10_000_000_000:  # Only check for companies with >$10B revenue
                # Allow some flexibility as this isn't universally true
                ratio = assets / revenue
                assert 0.5 < ratio < 20, f"{company.ticker} asset/revenue ratio {ratio:.1f} seems unusual"


if __name__ == "__main__":
    # Run a quick demo
    test_instance = TestStandardizedConceptsWithGroups()
    print("Running FAANG standardization test...")
    try:
        test_instance.test_faang_standardization()
        print("✅ FAANG test passed!")
    except Exception as e:
        print(f"❌ FAANG test failed: {e}")

    print("\nRunning user workflow example...")
    try:
        test_instance.test_user_workflow_example()
        print("✅ User workflow test passed!")
    except Exception as e:
        print(f"❌ User workflow test failed: {e}")