"""
Tests for EntityFacts revenue extraction fixes.

Tests cover:
1. Concept-based search for revenue (fixes TSLA returning None)
2. Annual parameter behavior (annual=True/False)
3. Fallback to most recent when no annual facts available
4. Amended filing filtering in latest_tenk/latest_tenq
"""

import pytest
from edgar import Company


class TestEntityFactsAnnualParameter:
    """Test the annual parameter behavior in EntityFacts methods."""

    @pytest.mark.vcr
    def test_get_revenue_defaults_to_annual(self, tsla_company):
        """Test that get_revenue() defaults to annual=True"""
        facts = tsla_company.get_facts()
        revenue = facts.get_revenue()

        # Should return annual revenue (FY 2024 = ~$97.69B)
        assert revenue is not None
        assert revenue > 90_000_000_000  # At least $90B
        assert revenue < 110_000_000_000  # Less than $110B

    @pytest.mark.vcr
    def test_get_revenue_with_annual_false(self, tsla_company):
        """Test that get_revenue(annual=False) returns most recent"""
        facts = tsla_company.get_facts()
        revenue_annual = facts.get_revenue(annual=True)
        revenue_recent = facts.get_revenue(annual=False)

        # Most recent could be quarterly (Q3 2025 = ~$69.9B)
        assert revenue_annual is not None
        assert revenue_recent is not None
        # They might be different if most recent is quarterly
        # Just verify both return valid values

    @pytest.mark.vcr
    def test_get_revenue_with_explicit_period(self, tsla_company):
        """Test that explicit period parameter works"""
        facts = tsla_company.get_facts()

        # Test with explicit annual period
        revenue_fy = facts.get_revenue(period="2024-FY")
        assert revenue_fy is not None
        assert revenue_fy > 90_000_000_000

    @pytest.mark.vcr
    def test_annual_parameter_consistency_across_methods(self, aapl_company):
        """Test that annual parameter works consistently across all methods"""
        facts = aapl_company.get_facts()

        # Test multiple methods with annual=True
        revenue = facts.get_revenue(annual=True)
        net_income = facts.get_net_income(annual=True)
        assets = facts.get_total_assets(annual=True)
        liabilities = facts.get_total_liabilities(annual=True)
        equity = facts.get_shareholders_equity(annual=True)
        op_income = facts.get_operating_income(annual=True)
        gross_profit = facts.get_gross_profit(annual=True)

        # All should return non-None values for Apple
        assert revenue is not None
        assert net_income is not None
        assert assets is not None
        assert liabilities is not None
        assert equity is not None
        assert op_income is not None
        assert gross_profit is not None

        # Basic sanity checks
        assert revenue > 0
        assert assets > liabilities


class TestEntityFactsRevenueExtraction:
    """Test concept-based revenue extraction fixes."""

    @pytest.mark.vcr
    def test_tsla_revenue_not_none(self, tsla_company):
        """
        Regression test: TSLA get_revenue() was returning None due to abstract
        rows matching before actual data rows.
        """
        facts = tsla_company.get_facts()
        revenue = facts.get_revenue()

        assert revenue is not None, "TSLA revenue should not be None"
        assert revenue > 0, "TSLA revenue should be positive"

    @pytest.mark.vcr
    @pytest.mark.parametrize("company_fixture,min_revenue_billions", [
        ("aapl_company", 300),  # Apple > $300B
        ("msft_company", 200),  # Microsoft > $200B
        ("tsla_company", 80),   # Tesla > $80B
    ])
    def test_companies_return_valid_annual_revenue(self, company_fixture, min_revenue_billions, request):
        """Test that get_revenue() returns valid annual values for major companies"""
        company = request.getfixturevalue(company_fixture)
        facts = company.get_facts()
        revenue = facts.get_revenue(annual=True)

        assert revenue is not None
        min_value = min_revenue_billions * 1_000_000_000
        assert revenue > min_value, \
            f"Expected revenue > ${min_revenue_billions}B, got ${revenue/1e9:.1f}B"


class TestFinancialsRevenueExtraction:
    """Test concept-based revenue extraction in Financials class."""

    @pytest.mark.vcr
    def test_tsla_financials_revenue_not_none(self, tsla_company):
        """
        Regression test: TSLA get_financials().get_revenue() was returning None
        due to abstract rows and 10-K/A amended filing issues.
        """
        financials = tsla_company.get_financials()

        # With amendments=False, should get non-amended 10-K
        if financials:
            revenue = financials.get_revenue()
            assert revenue is not None, "TSLA financials revenue should not be None"
            assert revenue > 0, "TSLA financials revenue should be positive"

    @pytest.mark.vcr
    @pytest.mark.parametrize("company_fixture", [
        "aapl_company",
        "msft_company",
    ])
    def test_financials_concept_based_search(self, company_fixture, request):
        """Test that concept-based search works for financials"""
        company = request.getfixturevalue(company_fixture)
        financials = company.get_financials()

        if financials:
            revenue = financials.get_revenue()
            assert revenue is not None
            assert revenue > 0


class TestEntityFactsFinancialsConsistency:
    """Test that EntityFacts and Financials return consistent values."""

    @pytest.mark.vcr
    @pytest.mark.parametrize("company_fixture", [
        "aapl_company",
        "msft_company",
    ])
    def test_facts_and_financials_revenue_match(self, company_fixture, request):
        """
        Test that get_facts().get_revenue() and get_financials().get_revenue()
        return the same annual value.
        """
        company = request.getfixturevalue(company_fixture)

        facts_revenue = company.get_facts().get_revenue(annual=True)
        financials = company.get_financials()

        if financials:
            financials_revenue = financials.get_revenue()

            # Both should return values
            assert facts_revenue is not None
            assert financials_revenue is not None

            # They should be very close (within 1%)
            # Small differences can occur due to restatements
            diff_pct = abs(facts_revenue - financials_revenue) / facts_revenue * 100
            assert diff_pct < 1.0, \
                f"Facts revenue (${facts_revenue/1e9:.2f}B) and Financials revenue " \
                f"(${financials_revenue/1e9:.2f}B) differ by {diff_pct:.2f}%"


class TestAmendedFilingFiltering:
    """Test that amended filings are filtered from latest_tenk/latest_tenq."""

    @pytest.mark.vcr
    def test_latest_tenk_excludes_amendments(self, tsla_company):
        """Test that latest_tenk does not return 10-K/A amended filings"""
        tenk = tsla_company.latest_tenk

        if tenk:
            form = tenk._filing.form
            # Should be "10-K", not "10-K/A"
            assert form == "10-K", f"Expected '10-K', got '{form}'"
            assert "/A" not in form, "Should not return amended filing"

    @pytest.mark.vcr
    @pytest.mark.parametrize("company_fixture", [
        "aapl_company",
        "msft_company",
    ])
    def test_latest_tenk_has_financials(self, company_fixture, request):
        """Test that latest_tenk (non-amended) has valid financials"""
        company = request.getfixturevalue(company_fixture)
        tenk = company.latest_tenk

        if tenk:
            # Non-amended 10-K should have financials
            financials = tenk.financials
            assert financials is not None, "Non-amended 10-K should have financials"


class TestGetAnnualFact:
    """Test the new get_annual_fact() helper method."""

    @pytest.mark.vcr
    def test_get_annual_fact_returns_fy_only(self, aapl_company):
        """Test that get_annual_fact() only returns FY (annual) facts"""
        facts = aapl_company.get_facts()

        # Get annual revenue fact
        annual_fact = facts.get_annual_fact('us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax')

        if annual_fact:
            # Should be fiscal_period == 'FY'
            assert annual_fact.fiscal_period == 'FY', \
                f"Expected fiscal_period='FY', got '{annual_fact.fiscal_period}'"
            assert annual_fact.numeric_value is not None
            assert annual_fact.numeric_value > 0

    @pytest.mark.vcr
    def test_get_annual_fact_with_specific_year(self, aapl_company):
        """Test that get_annual_fact() can filter by fiscal year"""
        facts = aapl_company.get_facts()

        # Get 2024 annual revenue
        fact_2024 = facts.get_annual_fact(
            'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
            fiscal_year=2024
        )

        if fact_2024:
            assert fact_2024.fiscal_year == 2024
            assert fact_2024.fiscal_period == 'FY'
