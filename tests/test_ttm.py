"""Tests for edgar.ttm module - TTM calculations, Q4 derivation, and stock splits."""
from datetime import date

import pytest

from edgar.entity.models import FinancialFact
from edgar.ttm import (
    TTMCalculator,
    TTMStatementBuilder,
    detect_splits,
    apply_split_adjustments,
)


def make_fact(
    *,
    concept: str,
    value: float,
    unit: str,
    period_start: date,
    period_end: date,
    fiscal_year: int,
    fiscal_period: str,
    statement_type: str = "IncomeStatement",
    period_type: str = "duration",
    filing_date: date | None = None,
) -> FinancialFact:
    return FinancialFact(
        concept=concept,
        taxonomy="us-gaap",
        label=concept.split(":")[-1],
        value=value,
        numeric_value=value,
        unit=unit,
        period_start=period_start,
        period_end=period_end,
        period_type=period_type,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        filing_date=filing_date or period_end,
        form_type="10-K",
        accession="0000000000-00-000000",
        statement_type=statement_type,
    )


class TestTTMCalculator:
    """Tests for TTMCalculator class."""

    def test_calculate_ttm_from_quarters(self):
        """Test basic TTM calculation from 4 discrete quarters."""
        facts = [
            make_fact(
                concept="us-gaap:Revenues",
                value=100,
                unit="USD",
                period_start=date(2023, 1, 1),
                period_end=date(2023, 3, 31),
                fiscal_year=2023,
                fiscal_period="Q1",
            ),
            make_fact(
                concept="us-gaap:Revenues",
                value=110,
                unit="USD",
                period_start=date(2023, 4, 1),
                period_end=date(2023, 6, 30),
                fiscal_year=2023,
                fiscal_period="Q2",
            ),
            make_fact(
                concept="us-gaap:Revenues",
                value=120,
                unit="USD",
                period_start=date(2023, 7, 1),
                period_end=date(2023, 9, 30),
                fiscal_year=2023,
                fiscal_period="Q3",
            ),
            make_fact(
                concept="us-gaap:Revenues",
                value=130,
                unit="USD",
                period_start=date(2023, 10, 1),
                period_end=date(2023, 12, 31),
                fiscal_year=2023,
                fiscal_period="Q4",
            ),
        ]

        calc = TTMCalculator(facts)
        ttm = calc.calculate_ttm()

        assert ttm.value == 460
        assert len(ttm.periods) == 4
        assert ttm.has_gaps is False

    def test_quarterize_derives_q2_q3_q4(self):
        """Test Q4 derivation from YTD and annual facts."""
        facts = [
            make_fact(
                concept="us-gaap:Revenues",
                value=100,
                unit="USD",
                period_start=date(2023, 1, 1),
                period_end=date(2023, 3, 31),
                fiscal_year=2023,
                fiscal_period="Q1",
            ),
            make_fact(
                concept="us-gaap:Revenues",
                value=300,
                unit="USD",
                period_start=date(2023, 1, 1),
                period_end=date(2023, 6, 30),
                fiscal_year=2023,
                fiscal_period="YTD_6M",
            ),
            make_fact(
                concept="us-gaap:Revenues",
                value=450,
                unit="USD",
                period_start=date(2023, 1, 1),
                period_end=date(2023, 9, 30),
                fiscal_year=2023,
                fiscal_period="YTD_9M",
            ),
            make_fact(
                concept="us-gaap:Revenues",
                value=600,
                unit="USD",
                period_start=date(2023, 1, 1),
                period_end=date(2023, 12, 31),
                fiscal_year=2023,
                fiscal_period="FY",
            ),
        ]

        calc = TTMCalculator(facts)
        quarterly = calc._quarterize_facts()

        q2 = next(q for q in quarterly if q.fiscal_period == "Q2")
        q3 = next(q for q in quarterly if q.fiscal_period == "Q3")
        q4 = next(q for q in quarterly if q.fiscal_period == "Q4")

        assert q2.numeric_value == 200
        assert q3.numeric_value == 150
        assert q4.numeric_value == 150
        assert "derived_q4" in (q4.calculation_context or "")


class TestStockSplits:
    """Tests for stock split detection and adjustment."""

    def test_detect_splits_filters_long_lag(self):
        """Test that stale split facts (>280 day lag) are filtered out."""
        split = make_fact(
            concept="us-gaap:StockSplitConversionRatio",
            value=10,
            unit="ratio",
            period_start=date(2024, 6, 1),
            period_end=date(2024, 6, 30),
            fiscal_year=2024,
            fiscal_period="Q2",
            filing_date=date(2024, 7, 1),
        )
        stale_split = make_fact(
            concept="us-gaap:StockSplitConversionRatio",
            value=2,
            unit="ratio",
            period_start=date(2020, 1, 1),
            period_end=date(2020, 1, 31),
            fiscal_year=2020,
            fiscal_period="Q1",
            filing_date=date(2024, 7, 1),
        )

        splits = detect_splits([split, stale_split])
        assert len(splits) == 1
        assert splits[0]["ratio"] == 10

    def test_apply_split_adjustments_eps_and_shares(self):
        """Test that EPS is divided and shares are multiplied by split ratio."""
        split = {"date": date(2024, 1, 1), "ratio": 2.0}
        eps = make_fact(
            concept="us-gaap:EarningsPerShareBasic",
            value=10,
            unit="USD/share",
            period_start=date(2023, 1, 1),
            period_end=date(2023, 12, 31),
            fiscal_year=2023,
            fiscal_period="FY",
        )
        shares = make_fact(
            concept="us-gaap:WeightedAverageNumberOfSharesOutstandingBasic",
            value=100,
            unit="shares",
            period_start=date(2023, 1, 1),
            period_end=date(2023, 12, 31),
            fiscal_year=2023,
            fiscal_period="FY",
        )

        adjusted = apply_split_adjustments([eps, shares], [split])
        assert adjusted[0].numeric_value == 5  # EPS divided by 2
        assert adjusted[1].numeric_value == 200  # Shares multiplied by 2


class TestEPSDerivation:
    """Tests for EPS derivation from Net Income and Shares."""

    def test_derive_q4_eps_from_net_income_and_shares(self):
        """Test Q4 EPS calculation from derived Q4 Net Income and share counts."""
        net_income_facts = [
            make_fact(
                concept="us-gaap:NetIncomeLoss",
                value=300,
                unit="USD",
                period_start=date(2023, 1, 1),
                period_end=date(2023, 9, 30),
                fiscal_year=2023,
                fiscal_period="YTD_9M",
            ),
            make_fact(
                concept="us-gaap:NetIncomeLoss",
                value=400,
                unit="USD",
                period_start=date(2023, 1, 1),
                period_end=date(2023, 12, 31),
                fiscal_year=2023,
                fiscal_period="FY",
            ),
        ]

        shares_facts = [
            make_fact(
                concept="us-gaap:WeightedAverageNumberOfSharesOutstandingBasic",
                value=900,
                unit="shares",
                period_start=date(2023, 1, 1),
                period_end=date(2023, 9, 30),
                fiscal_year=2023,
                fiscal_period="YTD_9M",
            ),
            make_fact(
                concept="us-gaap:WeightedAverageNumberOfSharesOutstandingBasic",
                value=1000,
                unit="shares",
                period_start=date(2023, 1, 1),
                period_end=date(2023, 12, 31),
                fiscal_year=2023,
                fiscal_period="FY",
            ),
        ]

        calc = TTMCalculator(net_income_facts)
        derived_eps = calc.derive_eps_for_quarter(
            net_income_facts,
            shares_facts,
            eps_concept="us-gaap:EarningsPerShareBasic",
        )

        assert derived_eps, "Expected derived EPS for Q4"
        q4_eps = derived_eps[0]
        assert q4_eps.fiscal_period == "Q4"
        # Q4 NI = 400 - 300 = 100
        # Q4 Shares = 4 * 1000 - 3 * 900 = 4000 - 2700 = 1300
        # Q4 EPS = 100 / 1300
        assert pytest.approx(q4_eps.numeric_value, rel=1e-6) == (100 / 1300)


class TestListConcepts:
    """Tests for Company.list_concepts() method."""

    def test_list_concepts_with_mock_facts(self):
        """Test list_concepts logic with mock data."""
        from unittest.mock import MagicMock, PropertyMock
        from edgar import Company

        # Create mock facts
        mock_facts = [
            MagicMock(
                concept="us-gaap:Revenues",
                label="Revenues",
                statement_type="IncomeStatement"
            ),
            MagicMock(
                concept="us-gaap:Revenues",
                label="Revenues",
                statement_type="IncomeStatement"
            ),
            MagicMock(
                concept="us-gaap:NetIncomeLoss",
                label="Net Income (Loss)",
                statement_type="IncomeStatement"
            ),
            MagicMock(
                concept="us-gaap:Assets",
                label="Assets",
                statement_type="BalanceSheet"
            ),
        ]

        # Create mock company with mock facts
        company = MagicMock(spec=Company)
        company.facts = MagicMock()
        company.facts._facts = mock_facts

        # Call the actual method (need to bind it)
        from edgar.entity.core import Company as RealCompany
        result = RealCompany.list_concepts(company, search="revenue")

        assert len(result) == 1
        assert result[0]['concept'] == "us-gaap:Revenues"
        assert result[0]['fact_count'] == 2

    def test_list_concepts_filters_by_statement(self):
        """Test filtering by statement type."""
        from unittest.mock import MagicMock
        from edgar import Company
        from edgar.entity.core import Company as RealCompany

        mock_facts = [
            MagicMock(concept="us-gaap:Revenues", label="Revenues", statement_type="IncomeStatement"),
            MagicMock(concept="us-gaap:Assets", label="Assets", statement_type="BalanceSheet"),
            MagicMock(concept="us-gaap:CashFlows", label="Cash Flows", statement_type="CashFlowStatement"),
        ]

        company = MagicMock(spec=Company)
        company.facts = MagicMock()
        company.facts._facts = mock_facts

        result = RealCompany.list_concepts(company, statement="IncomeStatement")

        assert len(result) == 1
        assert result[0]['concept'] == "us-gaap:Revenues"

    def test_list_concepts_returns_dataframe(self):
        """Test as_dataframe option."""
        import pandas as pd
        from unittest.mock import MagicMock
        from edgar import Company
        from edgar.entity.core import Company as RealCompany

        mock_facts = [
            MagicMock(concept="us-gaap:Revenues", label="Revenues", statement_type="IncomeStatement"),
        ]

        company = MagicMock(spec=Company)
        company.facts = MagicMock()
        company.facts._facts = mock_facts

        result = RealCompany.list_concepts(company, as_dataframe=True)

        assert isinstance(result, pd.DataFrame)
        assert 'concept' in result.columns
        assert 'label' in result.columns
        assert 'fact_count' in result.columns
