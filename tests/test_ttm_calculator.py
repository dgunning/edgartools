"""Tests for TTM calculator core logic."""
import pytest
from datetime import date, timedelta
from edgar.entity.ttm import TTMCalculator, TTMMetric
from edgar.entity.models import FinancialFact


def create_quarterly_fact(
    concept: str = 'us-gaap:Revenue',
    label: str = 'Revenue',
    value: float = 100_000_000,
    fiscal_year: int = 2024,
    fiscal_period: str = 'Q1',
    period_end: date = date(2024, 3, 30),
    duration_days: int = 91
) -> FinancialFact:
    """Helper to create a quarterly FinancialFact for testing."""
    period_start = period_end - timedelta(days=duration_days)

    return FinancialFact(
        concept=concept,
        taxonomy='us-gaap',
        label=label,
        value=value,
        numeric_value=float(value),
        unit='USD',
        scale=None,
        period_start=period_start,
        period_end=period_end,
        period_type='duration',
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        filing_date=period_end + timedelta(days=30),
        form_type='10-Q',
        accession='0000000000-24-000001',
        data_quality='high',
        is_audited=False,
        is_restated=False,
        is_estimated=False,
        confidence_score=0.9,
        semantic_tags=[],
        business_context='',
        statement_type='IncomeStatement',
        depth=0,
        parent_concept=None,
        section=None,
        is_abstract=False,
        is_total=False
    )


class TestTTMCalculatorBasic:
    """Test basic TTM calculation functionality."""

    def test_calculate_ttm_with_4_quarters(self):
        """Test basic TTM calculation with exactly 4 clean quarters."""
        facts = [
            create_quarterly_fact(
                value=100_000_000,
                fiscal_year=2023,
                fiscal_period='Q3',
                period_end=date(2023, 9, 30)
            ),
            create_quarterly_fact(
                value=110_000_000,
                fiscal_year=2023,
                fiscal_period='Q4',
                period_end=date(2023, 12, 31)
            ),
            create_quarterly_fact(
                value=105_000_000,
                fiscal_year=2024,
                fiscal_period='Q1',
                period_end=date(2024, 3, 30)
            ),
            create_quarterly_fact(
                value=115_000_000,
                fiscal_year=2024,
                fiscal_period='Q2',
                period_end=date(2024, 6, 30)
            ),
        ]

        calc = TTMCalculator(facts)
        result = calc.calculate_ttm()

        assert isinstance(result, TTMMetric)
        assert result.value == 430_000_000  # Sum of 4 quarters
        assert len(result.periods) == 4
        assert result.periods == [(2023, 'Q3'), (2023, 'Q4'), (2024, 'Q1'), (2024, 'Q2')]
        assert not result.has_gaps
        assert result.as_of_date == date(2024, 6, 30)
        assert result.concept == 'us-gaap:Revenue'
        assert result.label == 'Revenue'
        assert result.unit == 'USD'

    def test_calculate_ttm_with_8_quarters(self):
        """Test TTM calculation with 8 quarters (should use most recent 4)."""
        facts = []
        base_value = 100_000_000

        # Create 8 quarters
        for i in range(8):
            year = 2023 + (i // 4)
            quarter = (i % 4) + 1
            month = quarter * 3
            day = 30 if month in [6, 9] else 31

            facts.append(create_quarterly_fact(
                value=base_value + (i * 5_000_000),
                fiscal_year=year,
                fiscal_period=f'Q{quarter}',
                period_end=date(year, month, day)
            ))

        calc = TTMCalculator(facts)
        result = calc.calculate_ttm()

        # Should use Q1 2024, Q2 2024, Q3 2024, Q4 2024 (last 4)
        assert len(result.periods) == 4
        assert result.periods[-1][0] == 2024  # Most recent year
        assert result.warning is None  # No warning with 8+ quarters

    def test_calculate_ttm_as_of_specific_date(self):
        """Test TTM calculation as of a specific date."""
        facts = []

        # Create 6 quarters
        quarters_data = [
            (2023, 'Q3', date(2023, 9, 30), 100_000_000),
            (2023, 'Q4', date(2023, 12, 31), 110_000_000),
            (2024, 'Q1', date(2024, 3, 30), 105_000_000),
            (2024, 'Q2', date(2024, 6, 30), 115_000_000),
            (2024, 'Q3', date(2024, 9, 30), 120_000_000),
            (2024, 'Q4', date(2024, 12, 31), 125_000_000),
        ]

        for fy, fp, end_date, value in quarters_data:
            facts.append(create_quarterly_fact(
                value=value,
                fiscal_year=fy,
                fiscal_period=fp,
                period_end=end_date
            ))

        calc = TTMCalculator(facts)

        # Calculate TTM as of Q2 2024 (should include Q3 2023 - Q2 2024)
        result = calc.calculate_ttm(as_of=date(2024, 6, 30))

        assert result.value == 430_000_000  # 100 + 110 + 105 + 115
        assert result.periods == [(2023, 'Q3'), (2023, 'Q4'), (2024, 'Q1'), (2024, 'Q2')]
        assert result.as_of_date == date(2024, 6, 30)


class TestTTMCalculatorErrors:
    """Test error handling in TTM calculator."""

    def test_insufficient_data_no_quarters(self):
        """Test error when no quarterly data available."""
        facts = []

        calc = TTMCalculator(facts)

        with pytest.raises(ValueError, match="Insufficient quarterly data"):
            calc.calculate_ttm()

    def test_insufficient_data_only_3_quarters(self):
        """Test error when only 3 quarters available."""
        facts = [
            create_quarterly_fact(fiscal_year=2024, fiscal_period='Q1', period_end=date(2024, 3, 30)),
            create_quarterly_fact(fiscal_year=2024, fiscal_period='Q2', period_end=date(2024, 6, 30)),
            create_quarterly_fact(fiscal_year=2024, fiscal_period='Q3', period_end=date(2024, 9, 30)),
        ]

        calc = TTMCalculator(facts)

        with pytest.raises(ValueError, match="found 3 quarters, need at least 4"):
            calc.calculate_ttm()

    def test_insufficient_data_only_annual(self):
        """Test error when only annual data (no quarterly)."""
        # Create annual fact (365 days duration)
        fact = create_quarterly_fact(
            fiscal_period='FY',
            period_end=date(2024, 12, 31),
            duration_days=365
        )

        calc = TTMCalculator([fact])

        with pytest.raises(ValueError, match="Insufficient quarterly data"):
            calc.calculate_ttm()


class TestTTMCalculatorWarnings:
    """Test warning generation in TTM calculator."""

    def test_warning_with_few_quarters(self):
        """Test warning when <8 quarters available."""
        facts = []

        # Create only 5 unique quarters (Q1-Q4 2024 + Q1 2025)
        for i in range(5):
            if i < 4:
                quarter = i + 1
                fiscal_year = 2024
                period_end = date(2024, quarter * 3, 30)
            else:
                quarter = 1
                fiscal_year = 2025
                period_end = date(2025, 3, 30)

            facts.append(create_quarterly_fact(
                fiscal_year=fiscal_year,
                fiscal_period=f'Q{quarter}',
                period_end=period_end
            ))

        calc = TTMCalculator(facts)
        result = calc.calculate_ttm()

        assert result.warning is not None
        assert "Only 5 quarters available" in result.warning
        assert "Minimum 8 quarters recommended" in result.warning

    def test_warning_with_gaps(self):
        """Test warning when gaps detected in quarterly data."""
        facts = [
            create_quarterly_fact(fiscal_year=2023, fiscal_period='Q3', period_end=date(2023, 9, 30)),
            create_quarterly_fact(fiscal_year=2023, fiscal_period='Q4', period_end=date(2023, 12, 31)),
            # Missing Q1 2024 (gap)
            create_quarterly_fact(fiscal_year=2024, fiscal_period='Q2', period_end=date(2024, 6, 30)),
            create_quarterly_fact(fiscal_year=2024, fiscal_period='Q3', period_end=date(2024, 9, 30)),
        ]

        calc = TTMCalculator(facts)
        result = calc.calculate_ttm()

        assert result.has_gaps
        assert result.warning is not None
        assert "Gaps detected" in result.warning

    def test_no_warning_with_8_clean_quarters(self):
        """Test no warning with 8+ clean consecutive quarters."""
        facts = []

        # Create 8 consecutive quarters
        for i in range(8):
            year = 2023 + (i // 4)
            quarter = (i % 4) + 1
            month = quarter * 3

            facts.append(create_quarterly_fact(
                fiscal_year=year,
                fiscal_period=f'Q{quarter}',
                period_end=date(year, month, 30)
            ))

        calc = TTMCalculator(facts)
        result = calc.calculate_ttm()

        assert not result.has_gaps
        assert result.warning is None


class TestTTMCalculatorPeriodFiltering:
    """Test quarterly period filtering logic."""

    def test_filter_excludes_instant_facts(self):
        """Test that instant (point-in-time) facts are excluded."""
        facts = [
            create_quarterly_fact(fiscal_period='Q1', period_end=date(2024, 3, 30)),
            create_quarterly_fact(fiscal_period='Q2', period_end=date(2024, 6, 30)),
            create_quarterly_fact(fiscal_period='Q3', period_end=date(2024, 9, 30)),
            create_quarterly_fact(fiscal_period='Q4', period_end=date(2024, 12, 31)),
        ]

        # Add instant fact (balance sheet item)
        instant_fact = create_quarterly_fact(period_end=date(2024, 12, 31), duration_days=0)
        instant_fact.period_type = 'instant'
        instant_fact.period_start = None
        facts.append(instant_fact)

        calc = TTMCalculator(facts)
        quarterly = calc._filter_quarterly_facts()

        # Should have 4 quarterly facts (instant excluded)
        assert len(quarterly) == 4
        assert all(f.period_type == 'duration' for f in quarterly)

    def test_filter_excludes_annual_facts(self):
        """Test that annual facts (>100 days) are excluded."""
        facts = [
            create_quarterly_fact(fiscal_period='Q1', period_end=date(2024, 3, 30), duration_days=90),
            create_quarterly_fact(fiscal_period='Q2', period_end=date(2024, 6, 30), duration_days=92),
            create_quarterly_fact(fiscal_period='Q3', period_end=date(2024, 9, 30), duration_days=91),
            create_quarterly_fact(fiscal_period='Q4', period_end=date(2024, 12, 31), duration_days=90),
        ]

        # Add annual fact (365 days)
        annual_fact = create_quarterly_fact(
            fiscal_period='FY',
            period_end=date(2024, 12, 31),
            duration_days=365
        )
        facts.append(annual_fact)

        calc = TTMCalculator(facts)
        quarterly = calc._filter_quarterly_facts()

        # Should have 4 quarterly facts (annual excluded)
        assert len(quarterly) == 4
        assert all(80 <= (f.period_end - f.period_start).days <= 100 for f in quarterly)

    def test_filter_accepts_variation_in_quarter_length(self):
        """Test that 89-92 day quarters are accepted."""
        facts = [
            create_quarterly_fact(period_end=date(2024, 3, 30), duration_days=89),  # Q1 - Shorter quarter
            create_quarterly_fact(period_end=date(2024, 6, 30), duration_days=90),  # Q2 - Standard
            create_quarterly_fact(period_end=date(2024, 9, 30), duration_days=91),  # Q3 - Standard
            create_quarterly_fact(period_end=date(2024, 12, 31), duration_days=92),  # Q4 - Longer quarter
        ]

        calc = TTMCalculator(facts)
        quarterly = calc._filter_quarterly_facts()

        # All should be accepted (70-120 day range in QUARTER bucket)
        assert len(quarterly) == 4


class TestTTMCalculatorGapDetection:
    """Test gap detection in quarterly data."""

    def test_no_gaps_consecutive_quarters(self):
        """Test no gaps detected for consecutive quarters."""
        facts = [
            create_quarterly_fact(period_end=date(2023, 9, 30)),
            create_quarterly_fact(period_end=date(2023, 12, 31)),
            create_quarterly_fact(period_end=date(2024, 3, 30)),
            create_quarterly_fact(period_end=date(2024, 6, 30)),
        ]

        calc = TTMCalculator(facts)
        has_gaps = calc._check_for_gaps(facts)

        assert not has_gaps

    def test_gap_detected_missing_quarter(self):
        """Test gap detected when a quarter is missing."""
        facts = [
            create_quarterly_fact(period_end=date(2023, 9, 30)),
            create_quarterly_fact(period_end=date(2023, 12, 31)),
            # Missing Q1 2024
            create_quarterly_fact(period_end=date(2024, 6, 30)),
        ]

        calc = TTMCalculator(facts)
        has_gaps = calc._check_for_gaps(facts)

        assert has_gaps

    def test_gap_detection_allows_calendar_variation(self):
        """Test that normal calendar variations don't trigger gap detection."""
        # Some quarters are 89 days, some 92 days
        # Gaps should be in 70-110 day range
        facts = [
            create_quarterly_fact(period_end=date(2024, 3, 31)),   # 91 days
            create_quarterly_fact(period_end=date(2024, 6, 30)),   # 91 days (90 days after)
            create_quarterly_fact(period_end=date(2024, 9, 30)),   # 92 days (92 days after)
            create_quarterly_fact(period_end=date(2024, 12, 31)),  # 92 days (92 days after)
        ]

        calc = TTMCalculator(facts)
        has_gaps = calc._check_for_gaps(facts)

        # Should not detect gaps for normal calendar variations
        assert not has_gaps


class TestTTMCalculatorTrend:
    """Test TTM trend calculation."""

    def test_calculate_ttm_trend_basic(self):
        """Test basic TTM trend calculation."""
        facts = []

        # Create 11 quarters to get 8 TTM values
        for i in range(11):
            year = 2022 + (i // 4)
            quarter = (i % 4) + 1
            value = 100_000_000 + (i * 5_000_000)  # Increasing revenue

            facts.append(create_quarterly_fact(
                value=value,
                fiscal_year=year,
                fiscal_period=f'Q{quarter}',
                period_end=date(year, quarter * 3, 30)
            ))

        calc = TTMCalculator(facts)
        trend = calc.calculate_ttm_trend(periods=8)

        assert len(trend) == 8
        assert 'as_of_quarter' in trend.columns
        assert 'ttm_value' in trend.columns
        assert 'fiscal_year' in trend.columns
        assert 'fiscal_period' in trend.columns
        assert 'yoy_growth' in trend.columns
        assert 'periods_included' in trend.columns

    def test_ttm_trend_most_recent_first(self):
        """Test that TTM trend has most recent quarter first."""
        facts = []

        for i in range(11):
            year = 2022 + (i // 4)
            quarter = (i % 4) + 1

            facts.append(create_quarterly_fact(
                fiscal_year=year,
                fiscal_period=f'Q{quarter}',
                period_end=date(year, quarter * 3, 30)
            ))

        calc = TTMCalculator(facts)
        trend = calc.calculate_ttm_trend(periods=8)

        # Most recent quarter should be first row
        first_year = trend.iloc[0]['fiscal_year']
        last_year = trend.iloc[-1]['fiscal_year']

        assert first_year >= last_year  # Most recent year first

    def test_ttm_trend_yoy_growth_calculation(self):
        """Test YoY growth calculation in trend."""
        facts = []

        # Create 11 quarters with known values
        # First 4 quarters: 100M each (400M TTM)
        # Last 4 quarters: 125M each (500M TTM)
        # YoY growth should be 25%
        for i in range(11):
            year = 2022 + (i // 4)
            quarter = (i % 4) + 1
            value = 100_000_000 if i < 4 else 125_000_000

            facts.append(create_quarterly_fact(
                value=value,
                fiscal_year=year,
                fiscal_period=f'Q{quarter}',
                period_end=date(year, quarter * 3, 30)
            ))

        calc = TTMCalculator(facts)
        trend = calc.calculate_ttm_trend(periods=8)

        # First row (most recent) should have YoY growth (comparing to 4 quarters earlier)
        # After reversing, iloc[0] is the most recent quarter
        first_yoy = trend.iloc[0]['yoy_growth']
        assert first_yoy is not None
        # YoY growth should be positive (125M quarters vs 100M quarters)
        assert first_yoy > 0

    def test_ttm_trend_insufficient_data(self):
        """Test error when insufficient data for trend."""
        facts = []

        # Create only 5 quarters (need 8+3=11 for 8 TTM values)
        quarters_data = [
            (2023, 'Q3', date(2023, 9, 30)),
            (2023, 'Q4', date(2023, 12, 31)),
            (2024, 'Q1', date(2024, 3, 30)),
            (2024, 'Q2', date(2024, 6, 30)),
            (2024, 'Q3', date(2024, 9, 30)),
        ]

        for fy, fp, end_date in quarters_data:
            facts.append(create_quarterly_fact(
                fiscal_year=fy,
                fiscal_period=fp,
                period_end=end_date
            ))

        calc = TTMCalculator(facts)

        with pytest.raises(ValueError, match="Insufficient data for TTM trend"):
            calc.calculate_ttm_trend(periods=8)


class TestTTMMetricRepresentation:
    """Test TTMMetric string representation and display."""

    def test_ttm_metric_repr(self):
        """Test TTMMetric __repr__ method."""
        metric = TTMMetric(
            concept='us-gaap:Revenue',
            label='Revenue',
            value=391_035_000_000,
            unit='USD',
            as_of_date=date(2024, 6, 30),
            periods=[(2023, 'Q3'), (2023, 'Q4'), (2024, 'Q1'), (2024, 'Q2')],
            period_facts=[],
            has_gaps=False,
            warning=None
        )

        repr_str = repr(metric)

        assert 'TTMMetric' in repr_str
        assert 'us-gaap:Revenue' in repr_str
        assert '391,035,000,000' in repr_str
        assert 'Q3 2023' in repr_str
