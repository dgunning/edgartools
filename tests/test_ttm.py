"""Tests for edgar.ttm module - TTM calculations, Q4 derivation, and stock splits."""
from datetime import date

import pandas as pd
import pytest

from edgar.entity.models import FinancialFact
from edgar.ttm import (
    DurationBucket,
    TTMCalculator,
    TTMMetric,
    TTMStatement,
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
        from unittest.mock import MagicMock
        from edgar import Company
        from edgar.entity.core import Company as RealCompany, ConceptList

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
        company.name = "Test Company"
        company.facts = MagicMock()
        company.facts._facts = mock_facts

        # Call the actual method (need to bind it)
        result = RealCompany.list_concepts(company, search="revenue")

        assert isinstance(result, ConceptList)
        assert len(result) == 1
        assert result[0]['concept'] == "us-gaap:Revenues"
        assert result[0]['fact_count'] == 2

    def test_list_concepts_filters_by_statement(self):
        """Test filtering by statement type."""
        from unittest.mock import MagicMock
        from edgar import Company
        from edgar.entity.core import Company as RealCompany, ConceptList

        mock_facts = [
            MagicMock(concept="us-gaap:Revenues", label="Revenues", statement_type="IncomeStatement"),
            MagicMock(concept="us-gaap:Assets", label="Assets", statement_type="BalanceSheet"),
            MagicMock(concept="us-gaap:CashFlows", label="Cash Flows", statement_type="CashFlowStatement"),
        ]

        company = MagicMock(spec=Company)
        company.name = "Test Company"
        company.facts = MagicMock()
        company.facts._facts = mock_facts

        result = RealCompany.list_concepts(company, statement="IncomeStatement")

        assert isinstance(result, ConceptList)
        assert len(result) == 1
        assert result[0]['concept'] == "us-gaap:Revenues"

    def test_list_concepts_to_dataframe(self):
        """Test to_dataframe() method."""
        import pandas as pd
        from unittest.mock import MagicMock
        from edgar import Company
        from edgar.entity.core import Company as RealCompany

        mock_facts = [
            MagicMock(concept="us-gaap:Revenues", label="Revenues", statement_type="IncomeStatement"),
        ]

        company = MagicMock(spec=Company)
        company.name = "Test Company"
        company.facts = MagicMock()
        company.facts._facts = mock_facts

        result = RealCompany.list_concepts(company)
        df = result.to_dataframe()

        assert isinstance(df, pd.DataFrame)
        assert 'concept' in df.columns
        assert 'label' in df.columns
        assert 'fact_count' in df.columns

    def test_list_concepts_iteration(self):
        """Test that ConceptList is iterable."""
        from unittest.mock import MagicMock
        from edgar import Company
        from edgar.entity.core import Company as RealCompany

        mock_facts = [
            MagicMock(concept="us-gaap:Revenues", label="Revenues", statement_type="IncomeStatement"),
            MagicMock(concept="us-gaap:Assets", label="Assets", statement_type="BalanceSheet"),
        ]

        company = MagicMock(spec=Company)
        company.name = "Test Company"
        company.facts = MagicMock()
        company.facts._facts = mock_facts

        result = RealCompany.list_concepts(company)

        # Test iteration
        concepts = [c['concept'] for c in result]
        assert "us-gaap:Revenues" in concepts
        assert "us-gaap:Assets" in concepts

    def test_list_concepts_to_list(self):
        """Test to_list() method."""
        from unittest.mock import MagicMock
        from edgar import Company
        from edgar.entity.core import Company as RealCompany

        mock_facts = [
            MagicMock(concept="us-gaap:Revenues", label="Revenues", statement_type="IncomeStatement"),
        ]

        company = MagicMock(spec=Company)
        company.name = "Test Company"
        company.facts = MagicMock()
        company.facts._facts = mock_facts

        result = RealCompany.list_concepts(company)
        as_list = result.to_list()

        assert isinstance(as_list, list)
        assert len(as_list) == 1
        assert as_list[0]['concept'] == "us-gaap:Revenues"


class TestTTMMetric:
    """Tests for TTMMetric dataclass."""

    def test_ttm_metric_repr(self):
        """Test TTMMetric string representation."""
        metric = TTMMetric(
            concept="us-gaap:Revenues",
            label="Revenues",
            value=460_000_000,
            unit="USD",
            as_of_date=date(2024, 12, 31),
            periods=[(2024, "Q1"), (2024, "Q2"), (2024, "Q3"), (2024, "Q4")],
            period_facts=[],
            has_gaps=False,
            has_calculated_q4=True,
            warning="Some quarters were derived"
        )

        repr_str = repr(metric)
        assert "us-gaap:Revenues" in repr_str
        assert "460,000,000" in repr_str
        assert "Q1 2024" in repr_str or "Q4 2024" in repr_str

    def test_ttm_metric_with_gaps(self):
        """Test TTMMetric with has_gaps=True."""
        metric = TTMMetric(
            concept="us-gaap:NetIncome",
            label="Net Income",
            value=100_000_000,
            unit="USD",
            as_of_date=date(2024, 12, 31),
            periods=[(2024, "Q1"), (2024, "Q3")],  # Gap - missing Q2
            period_facts=[],
            has_gaps=True
        )

        assert metric.has_gaps is True
        assert metric.has_calculated_q4 is False  # Default
        assert metric.warning is None  # Default


class TestDurationBucket:
    """Tests for DurationBucket classification."""

    def test_duration_bucket_constants(self):
        """Test DurationBucket constant values."""
        assert DurationBucket.QUARTER == "QUARTER"
        assert DurationBucket.YTD_6M == "YTD_6M"
        assert DurationBucket.YTD_9M == "YTD_9M"
        assert DurationBucket.ANNUAL == "ANNUAL"
        assert DurationBucket.OTHER == "OTHER"


class TestClassifyDuration:
    """Tests for TTMCalculator._classify_duration()."""

    def test_classify_quarter(self):
        """Test classification of quarterly period (70-120 days)."""
        fact = make_fact(
            concept="us-gaap:Revenues",
            value=100,
            unit="USD",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 3, 31),  # 90 days
            fiscal_year=2024,
            fiscal_period="Q1",
        )

        calc = TTMCalculator([fact])
        bucket = calc._classify_duration(fact)

        assert bucket == DurationBucket.QUARTER

    def test_classify_ytd_6m(self):
        """Test classification of 6-month YTD period (140-229 days)."""
        fact = make_fact(
            concept="us-gaap:Revenues",
            value=200,
            unit="USD",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 6, 30),  # 181 days
            fiscal_year=2024,
            fiscal_period="YTD_6M",
        )

        calc = TTMCalculator([fact])
        bucket = calc._classify_duration(fact)

        assert bucket == DurationBucket.YTD_6M

    def test_classify_ytd_9m(self):
        """Test classification of 9-month YTD period (230-329 days)."""
        fact = make_fact(
            concept="us-gaap:Revenues",
            value=300,
            unit="USD",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 9, 30),  # 273 days
            fiscal_year=2024,
            fiscal_period="YTD_9M",
        )

        calc = TTMCalculator([fact])
        bucket = calc._classify_duration(fact)

        assert bucket == DurationBucket.YTD_9M

    def test_classify_annual(self):
        """Test classification of annual period (330-420 days)."""
        fact = make_fact(
            concept="us-gaap:Revenues",
            value=400,
            unit="USD",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),  # 365 days
            fiscal_year=2024,
            fiscal_period="FY",
        )

        calc = TTMCalculator([fact])
        bucket = calc._classify_duration(fact)

        assert bucket == DurationBucket.ANNUAL

    def test_classify_other_short(self):
        """Test classification of very short period as OTHER."""
        fact = make_fact(
            concept="us-gaap:Revenues",
            value=50,
            unit="USD",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 15),  # 14 days
            fiscal_year=2024,
            fiscal_period="Other",
        )

        calc = TTMCalculator([fact])
        bucket = calc._classify_duration(fact)

        assert bucket == DurationBucket.OTHER

    def test_classify_missing_dates(self):
        """Test classification returns OTHER when dates are missing."""
        fact = FinancialFact(
            concept="us-gaap:Revenues",
            taxonomy="us-gaap",
            label="Revenues",
            value=100,
            numeric_value=100,
            unit="USD",
            period_start=None,  # Missing start
            period_end=date(2024, 3, 31),
            period_type="duration",
            fiscal_year=2024,
            fiscal_period="Q1",
            filing_date=date(2024, 4, 15),
            form_type="10-Q",
            accession="0000000000-00-000000",
            statement_type="IncomeStatement",
        )

        calc = TTMCalculator([fact])
        bucket = calc._classify_duration(fact)

        assert bucket == DurationBucket.OTHER


class TestFilterByDuration:
    """Tests for TTMCalculator._filter_by_duration()."""

    def test_filter_quarters_only(self):
        """Test filtering to get only quarterly facts."""
        facts = [
            make_fact(
                concept="us-gaap:Revenues",
                value=100,
                unit="USD",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 3, 31),  # Q1
                fiscal_year=2024,
                fiscal_period="Q1",
            ),
            make_fact(
                concept="us-gaap:Revenues",
                value=200,
                unit="USD",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 6, 30),  # YTD_6M
                fiscal_year=2024,
                fiscal_period="YTD_6M",
            ),
            make_fact(
                concept="us-gaap:Revenues",
                value=400,
                unit="USD",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 12, 31),  # FY
                fiscal_year=2024,
                fiscal_period="FY",
            ),
        ]

        calc = TTMCalculator(facts)
        quarters = calc._filter_by_duration(DurationBucket.QUARTER)

        assert len(quarters) == 1
        assert quarters[0].fiscal_period == "Q1"

    def test_filter_annual_only(self):
        """Test filtering to get only annual facts."""
        facts = [
            make_fact(
                concept="us-gaap:Revenues",
                value=100,
                unit="USD",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 3, 31),  # Q1
                fiscal_year=2024,
                fiscal_period="Q1",
            ),
            make_fact(
                concept="us-gaap:Revenues",
                value=400,
                unit="USD",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 12, 31),  # FY
                fiscal_year=2024,
                fiscal_period="FY",
            ),
        ]

        calc = TTMCalculator(facts)
        annual = calc._filter_by_duration(DurationBucket.ANNUAL)

        assert len(annual) == 1
        assert annual[0].fiscal_period == "FY"


class TestFilterAnnualFacts:
    """Tests for TTMCalculator._filter_annual_facts()."""

    def test_filter_annual_facts_strict_range(self):
        """Test filtering annual facts with 350-380 day range."""
        facts = [
            make_fact(
                concept="us-gaap:Revenues",
                value=100,
                unit="USD",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 3, 31),  # 90 days
                fiscal_year=2024,
                fiscal_period="Q1",
            ),
            make_fact(
                concept="us-gaap:Revenues",
                value=400,
                unit="USD",
                period_start=date(2023, 1, 1),
                period_end=date(2023, 12, 31),  # 364 days
                fiscal_year=2023,
                fiscal_period="FY",
            ),
        ]

        calc = TTMCalculator(facts)
        annual = calc._filter_annual_facts()

        assert len(annual) == 1
        assert annual[0].fiscal_year == 2023

    def test_filter_annual_skips_instant_facts(self):
        """Test that instant facts are skipped."""
        facts = [
            FinancialFact(
                concept="us-gaap:Assets",
                taxonomy="us-gaap",
                label="Assets",
                value=1000,
                numeric_value=1000,
                unit="USD",
                period_start=None,
                period_end=date(2024, 12, 31),
                period_type="instant",  # Instant, not duration
                fiscal_year=2024,
                fiscal_period="FY",
                filing_date=date(2025, 2, 15),
                form_type="10-K",
                accession="0000000000-00-000000",
                statement_type="BalanceSheet",
            ),
        ]

        calc = TTMCalculator(facts)
        annual = calc._filter_annual_facts()

        assert len(annual) == 0


class TestIsAdditiveConcept:
    """Tests for TTMCalculator._is_additive_concept()."""

    def test_duration_monetary_is_additive(self):
        """Test that duration monetary facts are additive."""
        fact = make_fact(
            concept="us-gaap:Revenues",
            value=100,
            unit="USD",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 3, 31),
            fiscal_year=2024,
            fiscal_period="Q1",
        )

        calc = TTMCalculator([fact])
        assert calc._is_additive_concept(fact) is True

    def test_instant_fact_not_additive(self):
        """Test that instant facts are not additive."""
        fact = FinancialFact(
            concept="us-gaap:Assets",
            taxonomy="us-gaap",
            label="Assets",
            value=1000,
            numeric_value=1000,
            unit="USD",
            period_start=None,
            period_end=date(2024, 12, 31),
            period_type="instant",
            fiscal_year=2024,
            fiscal_period="FY",
            filing_date=date(2025, 2, 15),
            form_type="10-K",
            accession="0000000000-00-000000",
            statement_type="BalanceSheet",
        )

        calc = TTMCalculator([fact])
        assert calc._is_additive_concept(fact) is False

    def test_shares_unit_not_additive(self):
        """Test that share counts are not additive."""
        fact = make_fact(
            concept="us-gaap:CommonStockSharesOutstanding",
            value=1_000_000,
            unit="shares",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 3, 31),
            fiscal_year=2024,
            fiscal_period="Q1",
        )

        calc = TTMCalculator([fact])
        assert calc._is_additive_concept(fact) is False


class TestIsPositiveConcept:
    """Tests for TTMCalculator._is_positive_concept()."""

    def test_revenue_is_positive_concept(self):
        """Test that revenue concepts should be positive."""
        calc = TTMCalculator([])
        assert calc._is_positive_concept("us-gaap:Revenues") is True
        assert calc._is_positive_concept("us-gaap:SalesRevenueNet") is True

    def test_assets_is_positive_concept(self):
        """Test that asset concepts should be positive."""
        calc = TTMCalculator([])
        assert calc._is_positive_concept("us-gaap:Assets") is True
        assert calc._is_positive_concept("us-gaap:TotalAssets") is True

    def test_income_can_be_negative(self):
        """Test that income/loss concepts can be negative."""
        calc = TTMCalculator([])
        assert calc._is_positive_concept("us-gaap:NetIncomeLoss") is False
        assert calc._is_positive_concept("us-gaap:OperatingIncome") is False

    def test_expense_can_be_negative(self):
        """Test that expense concepts can be negative."""
        calc = TTMCalculator([])
        assert calc._is_positive_concept("us-gaap:InterestExpense") is False
        assert calc._is_positive_concept("us-gaap:DepreciationExpense") is False


class TestFindPriorQuarter:
    """Tests for TTMCalculator._find_prior_quarter()."""

    def test_find_prior_quarter(self):
        """Test finding the most recent quarter before a date."""
        q1 = make_fact(
            concept="us-gaap:Revenues",
            value=100,
            unit="USD",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 3, 31),
            fiscal_year=2024,
            fiscal_period="Q1",
        )
        q2 = make_fact(
            concept="us-gaap:Revenues",
            value=110,
            unit="USD",
            period_start=date(2024, 4, 1),
            period_end=date(2024, 6, 30),
            fiscal_year=2024,
            fiscal_period="Q2",
        )

        calc = TTMCalculator([q1, q2])
        result = calc._find_prior_quarter([q1, q2], before=date(2024, 6, 30))

        assert result == q1

    def test_find_prior_quarter_none_found(self):
        """Test finding prior quarter when none exist before date."""
        q1 = make_fact(
            concept="us-gaap:Revenues",
            value=100,
            unit="USD",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 3, 31),
            fiscal_year=2024,
            fiscal_period="Q1",
        )

        calc = TTMCalculator([q1])
        result = calc._find_prior_quarter([q1], before=date(2024, 1, 1))

        assert result is None


class TestFindPriorYTD6:
    """Tests for TTMCalculator._find_prior_ytd6()."""

    def test_find_prior_ytd6(self):
        """Test finding the most recent YTD_6M before a date."""
        ytd6 = make_fact(
            concept="us-gaap:Revenues",
            value=200,
            unit="USD",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 6, 30),
            fiscal_year=2024,
            fiscal_period="YTD_6M",
        )

        calc = TTMCalculator([ytd6])
        result = calc._find_prior_ytd6([ytd6], before=date(2024, 9, 30))

        assert result == ytd6

    def test_find_prior_ytd6_none_found(self):
        """Test finding prior YTD6 when none exist before date."""
        ytd6 = make_fact(
            concept="us-gaap:Revenues",
            value=200,
            unit="USD",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 6, 30),
            fiscal_year=2024,
            fiscal_period="YTD_6M",
        )

        calc = TTMCalculator([ytd6])
        result = calc._find_prior_ytd6([ytd6], before=date(2024, 3, 1))

        assert result is None


class TestFindMatchingYTD9:
    """Tests for TTMCalculator._find_matching_ytd9()."""

    def test_find_matching_ytd9_exact_match(self):
        """Test finding YTD_9M with matching period_start."""
        ytd9 = make_fact(
            concept="us-gaap:Revenues",
            value=300,
            unit="USD",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 9, 30),
            fiscal_year=2024,
            fiscal_period="YTD_9M",
        )

        calc = TTMCalculator([ytd9])
        result = calc._find_matching_ytd9(
            [ytd9],
            period_start=date(2024, 1, 1),
            before=date(2024, 12, 31)
        )

        assert result == ytd9

    def test_find_matching_ytd9_fallback(self):
        """Test finding YTD_9M with fallback when no exact match."""
        ytd9_2023 = make_fact(
            concept="us-gaap:Revenues",
            value=280,
            unit="USD",
            period_start=date(2023, 1, 1),
            period_end=date(2023, 9, 30),
            fiscal_year=2023,
            fiscal_period="YTD_9M",
        )

        calc = TTMCalculator([ytd9_2023])
        # Looking for 2024 but only 2023 exists
        result = calc._find_matching_ytd9(
            [ytd9_2023],
            period_start=date(2024, 1, 1),  # Different year
            before=date(2024, 12, 31)
        )

        assert result == ytd9_2023  # Fallback to latest before date


class TestCheckForGaps:
    """Tests for TTMCalculator._check_for_gaps()."""

    def test_consecutive_quarters_no_gaps(self):
        """Test that consecutive quarters are detected as no gaps."""
        quarters = [
            make_fact(
                concept="us-gaap:Revenues",
                value=100,
                unit="USD",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 3, 31),
                fiscal_year=2024,
                fiscal_period="Q1",
            ),
            make_fact(
                concept="us-gaap:Revenues",
                value=110,
                unit="USD",
                period_start=date(2024, 4, 1),
                period_end=date(2024, 6, 30),
                fiscal_year=2024,
                fiscal_period="Q2",
            ),
        ]

        calc = TTMCalculator(quarters)
        assert calc._check_for_gaps(quarters) is False

    def test_non_consecutive_quarters_has_gaps(self):
        """Test that non-consecutive quarters are detected as gaps."""
        quarters = [
            make_fact(
                concept="us-gaap:Revenues",
                value=100,
                unit="USD",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 3, 31),
                fiscal_year=2024,
                fiscal_period="Q1",
            ),
            make_fact(
                concept="us-gaap:Revenues",
                value=120,
                unit="USD",
                period_start=date(2024, 7, 1),
                period_end=date(2024, 9, 30),  # Gap: missing Q2
                fiscal_year=2024,
                fiscal_period="Q3",
            ),
        ]

        calc = TTMCalculator(quarters)
        assert calc._check_for_gaps(quarters) is True

    def test_single_quarter_no_gaps(self):
        """Test that single quarter returns no gaps."""
        quarters = [
            make_fact(
                concept="us-gaap:Revenues",
                value=100,
                unit="USD",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 3, 31),
                fiscal_year=2024,
                fiscal_period="Q1",
            ),
        ]

        calc = TTMCalculator(quarters)
        assert calc._check_for_gaps(quarters) is False


class TestGenerateWarning:
    """Tests for TTMCalculator._generate_warning()."""

    def test_warning_for_calculated_q4(self):
        """Test warning generated when quarters are derived."""
        calc = TTMCalculator([])
        warning = calc._generate_warning(
            all_quarterly=[],
            ttm_quarters=[],
            has_calculated_q4=True
        )

        assert warning is not None
        assert "derived" in warning.lower()

    def test_warning_for_insufficient_quarters(self):
        """Test warning when less than 8 quarters available."""
        quarters = [
            make_fact(
                concept="us-gaap:Revenues",
                value=100,
                unit="USD",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 3, 31),
                fiscal_year=2024,
                fiscal_period="Q1",
            ),
        ]

        calc = TTMCalculator(quarters)
        warning = calc._generate_warning(
            all_quarterly=quarters,
            ttm_quarters=quarters,
            has_calculated_q4=False
        )

        assert warning is not None
        assert "1 quarters" in warning

    def test_no_warning_when_all_good(self):
        """Test no warning when data quality is good."""
        quarters = [
            make_fact(
                concept="us-gaap:Revenues",
                value=100 + i * 10,
                unit="USD",
                period_start=date(2023 + i // 4, ((i % 4) * 3) + 1, 1),
                period_end=date(2023 + i // 4, ((i % 4) + 1) * 3, 28),
                fiscal_year=2023 + i // 4,
                fiscal_period=f"Q{(i % 4) + 1}",
            )
            for i in range(8)
        ]

        calc = TTMCalculator(quarters)
        warning = calc._generate_warning(
            all_quarterly=quarters,
            ttm_quarters=quarters[:4],
            has_calculated_q4=False
        )

        # Should be None since all conditions met
        assert warning is None


class TestDeduplicateByPeriodEnd:
    """Tests for TTMCalculator._deduplicate_by_period_end()."""

    def test_deduplicate_keeps_latest_filing(self):
        """Test that deduplication keeps the most recently filed fact."""
        old_filing = make_fact(
            concept="us-gaap:Revenues",
            value=100,
            unit="USD",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 3, 31),
            fiscal_year=2024,
            fiscal_period="Q1",
            filing_date=date(2024, 4, 15),
        )
        new_filing = make_fact(
            concept="us-gaap:Revenues",
            value=105,  # Amended value
            unit="USD",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 3, 31),
            fiscal_year=2024,
            fiscal_period="Q1",
            filing_date=date(2024, 5, 20),  # Later filing
        )

        calc = TTMCalculator([old_filing, new_filing])
        dedup = calc._deduplicate_by_period_end([old_filing, new_filing])

        assert len(dedup) == 1
        assert dedup[0].numeric_value == 105  # Newer value

    def test_deduplicate_different_periods(self):
        """Test that different periods are all kept."""
        q1 = make_fact(
            concept="us-gaap:Revenues",
            value=100,
            unit="USD",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 3, 31),
            fiscal_year=2024,
            fiscal_period="Q1",
        )
        q2 = make_fact(
            concept="us-gaap:Revenues",
            value=110,
            unit="USD",
            period_start=date(2024, 4, 1),
            period_end=date(2024, 6, 30),
            fiscal_year=2024,
            fiscal_period="Q2",
        )

        calc = TTMCalculator([q1, q2])
        dedup = calc._deduplicate_by_period_end([q1, q2])

        assert len(dedup) == 2


class TestSelectTTMWindow:
    """Tests for TTMCalculator._select_ttm_window()."""

    def test_select_ttm_window_no_as_of(self):
        """Test selecting TTM window with no as_of date (most recent)."""
        quarters = [
            make_fact(
                concept="us-gaap:Revenues",
                value=100 + i * 10,
                unit="USD",
                period_start=date(2024, ((i % 4) * 3) + 1, 1),
                period_end=date(2024, ((i % 4) + 1) * 3, 28 if (i % 4) < 3 else 31),
                fiscal_year=2024,
                fiscal_period=f"Q{(i % 4) + 1}",
            )
            for i in range(4)
        ]

        calc = TTMCalculator(quarters)
        window = calc._select_ttm_window(quarters, as_of=None)

        assert len(window) == 4
        # Should be in chronological order (oldest to newest)
        assert window[0].fiscal_period == "Q1"
        assert window[-1].fiscal_period == "Q4"

    def test_select_ttm_window_with_as_of(self):
        """Test selecting TTM window with specific as_of date."""
        quarters = [
            make_fact(
                concept="us-gaap:Revenues",
                value=100,
                unit="USD",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 3, 31),
                fiscal_year=2024,
                fiscal_period="Q1",
            ),
            make_fact(
                concept="us-gaap:Revenues",
                value=110,
                unit="USD",
                period_start=date(2024, 4, 1),
                period_end=date(2024, 6, 30),
                fiscal_year=2024,
                fiscal_period="Q2",
            ),
            make_fact(
                concept="us-gaap:Revenues",
                value=120,
                unit="USD",
                period_start=date(2024, 7, 1),
                period_end=date(2024, 9, 30),
                fiscal_year=2024,
                fiscal_period="Q3",
            ),
        ]

        calc = TTMCalculator(quarters)
        # Only get Q1 and Q2 (as_of June 30)
        window = calc._select_ttm_window(quarters, as_of=date(2024, 6, 30))

        assert len(window) == 2
        assert all(f.period_end <= date(2024, 6, 30) for f in window)


class TestCalculateTTMErrors:
    """Tests for TTMCalculator.calculate_ttm() error cases."""

    def test_calculate_ttm_insufficient_data(self):
        """Test that calculate_ttm raises ValueError with < 4 quarters."""
        facts = [
            make_fact(
                concept="us-gaap:Revenues",
                value=100,
                unit="USD",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 3, 31),
                fiscal_year=2024,
                fiscal_period="Q1",
            ),
            make_fact(
                concept="us-gaap:Revenues",
                value=110,
                unit="USD",
                period_start=date(2024, 4, 1),
                period_end=date(2024, 6, 30),
                fiscal_year=2024,
                fiscal_period="Q2",
            ),
        ]

        calc = TTMCalculator(facts)

        with pytest.raises(ValueError, match="Insufficient quarterly data"):
            calc.calculate_ttm()


class TestCalculateTTMTrend:
    """Tests for TTMCalculator.calculate_ttm_trend()."""

    def test_calculate_ttm_trend_basic(self):
        """Test basic TTM trend calculation."""
        # Create 8 quarters of data
        quarters = [
            make_fact(
                concept="us-gaap:Revenues",
                value=100 + i * 5,
                unit="USD",
                period_start=date(2023 + (i // 4), ((i % 4) * 3) + 1, 1),
                period_end=date(2023 + (i // 4), ((i % 4) + 1) * 3, 28 if (i % 4) < 3 else 31),
                fiscal_year=2023 + (i // 4),
                fiscal_period=f"Q{(i % 4) + 1}",
            )
            for i in range(8)
        ]

        calc = TTMCalculator(quarters)
        trend = calc.calculate_ttm_trend(periods=4)

        assert isinstance(trend, pd.DataFrame)
        assert len(trend) == 4
        assert 'ttm_value' in trend.columns
        assert 'yoy_growth' in trend.columns

    def test_calculate_ttm_trend_invalid_periods(self):
        """Test that invalid periods raises ValueError."""
        calc = TTMCalculator([])

        with pytest.raises(ValueError, match="periods must be between"):
            calc.calculate_ttm_trend(periods=0)

        with pytest.raises(ValueError, match="periods must be between"):
            calc.calculate_ttm_trend(periods=101)

    def test_calculate_ttm_trend_insufficient_data(self):
        """Test that insufficient data raises ValueError."""
        facts = [
            make_fact(
                concept="us-gaap:Revenues",
                value=100,
                unit="USD",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 3, 31),
                fiscal_year=2024,
                fiscal_period="Q1",
            ),
        ]

        calc = TTMCalculator(facts)

        with pytest.raises(ValueError, match="Insufficient data for TTM trend"):
            calc.calculate_ttm_trend(periods=4)


class TestTTMStatement:
    """Tests for TTMStatement class."""

    def test_ttm_statement_to_dataframe(self):
        """Test converting TTMStatement to DataFrame."""
        statement = TTMStatement(
            statement_type="IncomeStatement",
            as_of_date=date(2024, 12, 31),
            items=[
                {
                    'label': 'Revenue',
                    'values': {'Q4 2024': 100_000_000, 'Q3 2024': 95_000_000},
                    'concept': 'us-gaap:Revenues',
                    'depth': 0,
                    'is_total': False
                },
                {
                    'label': 'Net Income',
                    'values': {'Q4 2024': 10_000_000, 'Q3 2024': 9_000_000},
                    'concept': 'us-gaap:NetIncome',
                    'depth': 0,
                    'is_total': True
                },
            ],
            company_name="Test Corp",
            cik="1234567",
            periods=[(2024, "Q4"), (2024, "Q3")]
        )

        df = statement.to_dataframe()

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert 'label' in df.columns
        assert 'depth' in df.columns
        assert 'is_total' in df.columns

    def test_ttm_statement_to_dataframe_single_value(self):
        """Test DataFrame with single TTM value (no periods)."""
        statement = TTMStatement(
            statement_type="IncomeStatement",
            as_of_date=date(2024, 12, 31),
            items=[
                {
                    'label': 'Revenue',
                    'value': 100_000_000,
                    'concept': 'us-gaap:Revenues',
                    'depth': 0,
                    'is_total': False
                },
            ],
            company_name="Test Corp",
            cik="1234567",
            periods=None
        )

        df = statement.to_dataframe()

        assert 'TTM' in df.columns
        assert df['TTM'].iloc[0] == 100_000_000

    def test_ttm_statement_repr(self):
        """Test TTMStatement string representation."""
        statement = TTMStatement(
            statement_type="IncomeStatement",
            as_of_date=date(2024, 12, 31),
            items=[
                {
                    'label': 'Revenue',
                    'values': {'TTM': 100_000_000},
                    'concept': 'us-gaap:Revenues',
                    'depth': 0,
                    'is_total': False
                },
            ],
            company_name="Test Corp",
            cik="1234567",
            periods=[(2024, "Q4")]
        )

        repr_str = repr(statement)
        # Should produce rich formatted output
        assert isinstance(repr_str, str)

    def test_ttm_statement_rich(self):
        """Test TTMStatement __rich__ method."""
        from rich.panel import Panel

        statement = TTMStatement(
            statement_type="IncomeStatement",
            as_of_date=date(2024, 12, 31),
            items=[
                {
                    'label': 'Revenue',
                    'values': {'Q4 2024': 100_000_000_000},  # $100B
                    'concept': 'us-gaap:Revenues',
                    'depth': 0,
                    'is_total': False
                },
                {
                    'label': 'Net Income',
                    'values': {'Q4 2024': -5_000_000},  # Negative value
                    'concept': 'us-gaap:NetIncome',
                    'depth': 1,
                    'is_total': True
                },
            ],
            company_name="Test Corp",
            cik="1234567",
            periods=[(2024, "Q4")]
        )

        rich_output = statement.__rich__()
        assert isinstance(rich_output, Panel)


class TestStockSplitsEdgeCases:
    """Additional edge case tests for stock splits."""

    def test_detect_splits_filters_long_duration(self):
        """Test that long duration facts are filtered out."""
        # Split fact with 90-day duration (quarterly) should be filtered
        quarterly_split = make_fact(
            concept="us-gaap:StockSplitConversionRatio",
            value=2,
            unit="ratio",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 3, 31),  # 90 days
            fiscal_year=2024,
            fiscal_period="Q1",
            filing_date=date(2024, 4, 15),
        )

        splits = detect_splits([quarterly_split])
        assert len(splits) == 0

    def test_detect_splits_accepts_instant(self):
        """Test that instant facts (no period_start) are accepted."""
        instant_split = FinancialFact(
            concept="us-gaap:StockSplitConversionRatio",
            taxonomy="us-gaap",
            label="Stock Split Conversion Ratio",
            value=10,
            numeric_value=10,
            unit="ratio",
            period_start=None,  # Instant
            period_end=date(2024, 6, 7),
            period_type="instant",
            fiscal_year=2024,
            fiscal_period="Q2",
            filing_date=date(2024, 6, 15),
            form_type="8-K",
            accession="0000000000-00-000000",
            statement_type=None,
        )

        splits = detect_splits([instant_split])
        assert len(splits) == 1
        assert splits[0]['ratio'] == 10

    def test_detect_splits_deduplicates(self):
        """Test that duplicate splits (same year/ratio) are deduplicated."""
        split1 = FinancialFact(
            concept="us-gaap:StockSplitConversionRatio",
            taxonomy="us-gaap",
            label="Stock Split",
            value=10,
            numeric_value=10,
            unit="ratio",
            period_start=None,
            period_end=date(2024, 6, 7),
            period_type="instant",
            fiscal_year=2024,
            fiscal_period="Q2",
            filing_date=date(2024, 6, 15),
            form_type="8-K",
            accession="0000000000-00-000001",
            statement_type=None,
        )
        split2 = FinancialFact(
            concept="us-gaap:StockSplitConversionRatio",
            taxonomy="us-gaap",
            label="Stock Split",
            value=10,
            numeric_value=10,
            unit="ratio",
            period_start=None,
            period_end=date(2024, 6, 10),  # Same year, same ratio
            period_type="instant",
            fiscal_year=2024,
            fiscal_period="Q2",
            filing_date=date(2024, 6, 20),
            form_type="10-Q",
            accession="0000000000-00-000002",
            statement_type=None,
        )

        splits = detect_splits([split1, split2])
        assert len(splits) == 1

    def test_apply_split_adjustments_no_unit(self):
        """Test that facts with no unit are passed through unchanged."""
        fact = FinancialFact(
            concept="us-gaap:SomeMetric",
            taxonomy="us-gaap",
            label="Some Metric",
            value=100,
            numeric_value=100,
            unit=None,  # No unit
            period_start=date(2023, 1, 1),
            period_end=date(2023, 12, 31),
            period_type="duration",
            fiscal_year=2023,
            fiscal_period="FY",
            filing_date=date(2024, 2, 15),
            form_type="10-K",
            accession="0000000000-00-000000",
            statement_type="IncomeStatement",
        )
        split = {"date": date(2024, 1, 1), "ratio": 2.0}

        adjusted = apply_split_adjustments([fact], [split])
        assert len(adjusted) == 1
        assert adjusted[0].numeric_value == 100  # Unchanged

    def test_apply_split_adjustments_non_share_unit(self):
        """Test that non-share/non-per-share facts are unchanged."""
        fact = make_fact(
            concept="us-gaap:Revenues",
            value=1_000_000,
            unit="USD",  # Not shares or per-share
            period_start=date(2023, 1, 1),
            period_end=date(2023, 12, 31),
            fiscal_year=2023,
            fiscal_period="FY",
        )
        split = {"date": date(2024, 1, 1), "ratio": 2.0}

        adjusted = apply_split_adjustments([fact], [split])
        assert len(adjusted) == 1
        assert adjusted[0].numeric_value == 1_000_000  # Unchanged

    def test_apply_split_adjustments_restated_filing(self):
        """Test that restated filings (filed after split) are not adjusted."""
        # EPS filed AFTER the split (already adjusted by company)
        eps = make_fact(
            concept="us-gaap:EarningsPerShareBasic",
            value=5,
            unit="USD/share",
            period_start=date(2023, 1, 1),
            period_end=date(2023, 12, 31),
            fiscal_year=2023,
            fiscal_period="FY",
            filing_date=date(2024, 6, 15),  # After split
        )
        split = {"date": date(2024, 6, 1), "ratio": 2.0}

        adjusted = apply_split_adjustments([eps], [split])
        assert len(adjusted) == 1
        assert adjusted[0].numeric_value == 5  # Unchanged (already restated)


class TestCreateDerivedQuarter:
    """Tests for TTMCalculator._create_derived_quarter()."""

    def test_create_derived_quarter_basic(self):
        """Test creating a derived quarter fact."""
        source = make_fact(
            concept="us-gaap:Revenues",
            value=600,
            unit="USD",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
            fiscal_year=2024,
            fiscal_period="FY",
        )

        calc = TTMCalculator([source])
        derived = calc._create_derived_quarter(
            source,
            derived_value=150,
            derivation_method="derived_q4_fy_minus_ytd9",
            target_period="Q4",
            period_start=date(2024, 10, 1)
        )

        assert derived.numeric_value == 150
        assert derived.fiscal_period == "Q4"
        assert derived.calculation_context == "derived_q4_fy_minus_ytd9"
        assert derived.period_start == date(2024, 10, 1)
