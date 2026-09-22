"""
Consolidated standardization integration tests (network required).

Tests EntityFacts standardized concept access (get_revenue, get_net_income, etc.)
against real SEC data with specific value thresholds.

Consolidated from: test_standardized_concepts.py, test_standardized_concepts_groups.py
"""

import pytest
from edgar import Company


class TestStandardizedConceptAccess:
    """EntityFacts high-level standardized methods against real company data."""

    @pytest.mark.network
    def test_apple_revenue(self):
        """AAPL get_revenue() returns > $200B."""
        facts = Company("AAPL").get_facts()
        revenue = facts.get_revenue()
        assert revenue is not None, "Apple should have revenue data"
        assert revenue > 200_000_000_000, f"Apple revenue ${revenue/1e9:.1f}B should be > $200B"

    @pytest.mark.network
    def test_tesla_revenue(self):
        """TSLA get_revenue() returns > $35B."""
        facts = Company("TSLA").get_facts()
        revenue = facts.get_revenue()
        assert revenue is not None, "Tesla should have revenue data"
        assert revenue > 35_000_000_000, f"Tesla revenue ${revenue/1e9:.1f}B should be > $35B"

    @pytest.mark.network
    def test_apple_accounting_equation(self):
        """All 6 AAPL metrics consistent: gross >= net, assets ≈ liab + equity."""
        facts = Company("AAPL").get_facts()

        revenue = facts.get_revenue()
        gross_profit = facts.get_gross_profit()
        net_income = facts.get_net_income()
        assets = facts.get_total_assets()
        liabilities = facts.get_total_liabilities()
        equity = facts.get_shareholders_equity()

        # All should exist
        for name, val in [("revenue", revenue), ("gross_profit", gross_profit),
                          ("net_income", net_income), ("assets", assets),
                          ("liabilities", liabilities), ("equity", equity)]:
            assert val is not None, f"Apple {name} should not be None"

        assert gross_profit <= revenue, "Gross profit should be <= revenue"
        assert net_income <= gross_profit, "Net income should be <= gross profit"

        balance_diff = abs(assets - (liabilities + equity))
        assert balance_diff / assets < 0.01, (
            f"Assets ${assets/1e9:.0f}B should ≈ Liab ${liabilities/1e9:.0f}B + Equity ${equity/1e9:.0f}B"
        )

    @pytest.mark.network
    def test_missing_concepts_return_none(self):
        """Non-existent period and incompatible unit type return None."""
        facts = Company("AAPL").get_facts()
        assert facts.get_revenue(period="1990-FY") is None, "Non-existent period should return None"
        assert facts.get_revenue(unit="shares") is None, "Incompatible unit type should return None"

    @pytest.mark.network
    def test_edge_cases_empty_and_invalid_concepts(self):
        """Empty concept list and non-existent concept name return None."""
        facts = Company("AAPL").get_facts()
        assert facts._get_standardized_concept_value([]) is None
        assert facts._get_standardized_concept_value(['NonExistentConcept']) is None

    @pytest.mark.network
    @pytest.mark.slow
    def test_multi_company_consistency(self):
        """AAPL/MSFT/GOOGL all have revenue > $10B and assets > $50B."""
        for ticker in ["AAPL", "MSFT", "GOOGL"]:
            facts = Company(ticker).get_facts()

            revenue = facts.get_revenue()
            assets = facts.get_total_assets()

            assert revenue is not None, f"{ticker} should have revenue"
            assert revenue > 10_000_000_000, f"{ticker} revenue should be > $10B"
            assert assets is not None, f"{ticker} should have assets"
            assert assets > 50_000_000_000, f"{ticker} assets should be > $50B"
