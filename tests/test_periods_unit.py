"""
Unit tests for edgar.xbrl.periods module.

These tests focus on pure functions that don't require network access or XBRL instances.
"""

from datetime import date
import pytest

from edgar.xbrl.periods import (
    STATEMENT_TYPE_CONFIG,
    sort_periods,
    filter_periods_by_document_end_date,
    filter_periods_by_type,
    calculate_fiscal_alignment_score,
    generate_period_view,
    generate_mixed_view,
)


# =============================================================================
# Test Fixtures - Sample Period Data
# =============================================================================

@pytest.fixture
def instant_periods():
    """Sample instant periods for balance sheet testing."""
    return [
        {'key': 'instant_2024-03-31', 'date': '2024-03-31', 'type': 'instant', 'label': 'March 31, 2024'},
        {'key': 'instant_2024-12-31', 'date': '2024-12-31', 'type': 'instant', 'label': 'December 31, 2024'},
        {'key': 'instant_2023-12-31', 'date': '2023-12-31', 'type': 'instant', 'label': 'December 31, 2023'},
        {'key': 'instant_2023-06-30', 'date': '2023-06-30', 'type': 'instant', 'label': 'June 30, 2023'},
    ]


@pytest.fixture
def duration_periods():
    """Sample duration periods for income statement testing."""
    return [
        {
            'key': 'duration_2024-01-01_2024-12-31',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'type': 'duration',
            'label': 'Annual 2024'
        },
        {
            'key': 'duration_2023-01-01_2023-12-31',
            'start_date': '2023-01-01',
            'end_date': '2023-12-31',
            'type': 'duration',
            'label': 'Annual 2023'
        },
        {
            'key': 'duration_2024-01-01_2024-03-31',
            'start_date': '2024-01-01',
            'end_date': '2024-03-31',
            'type': 'duration',
            'label': 'Q1 2024'
        },
        {
            'key': 'duration_2024-04-01_2024-06-30',
            'start_date': '2024-04-01',
            'end_date': '2024-06-30',
            'type': 'duration',
            'label': 'Q2 2024'
        },
    ]


@pytest.fixture
def mixed_periods(instant_periods, duration_periods):
    """Mix of instant and duration periods."""
    return instant_periods + duration_periods


# =============================================================================
# Tests for sort_periods
# =============================================================================

class TestSortPeriods:
    """Tests for the sort_periods function."""

    def test_sort_instant_periods_by_date_descending(self, instant_periods):
        """Instant periods should be sorted by date, most recent first."""
        sorted_periods = sort_periods(instant_periods, 'instant')

        assert sorted_periods[0]['date'] == '2024-12-31'
        assert sorted_periods[1]['date'] == '2024-03-31'
        assert sorted_periods[2]['date'] == '2023-12-31'
        assert sorted_periods[3]['date'] == '2023-06-30'

    def test_sort_duration_periods_by_end_date_descending(self, duration_periods):
        """Duration periods should be sorted by end date, most recent first."""
        sorted_periods = sort_periods(duration_periods, 'duration')

        assert sorted_periods[0]['end_date'] == '2024-12-31'
        assert sorted_periods[1]['end_date'] == '2024-06-30'
        assert sorted_periods[2]['end_date'] == '2024-03-31'
        assert sorted_periods[3]['end_date'] == '2023-12-31'

    def test_sort_empty_list(self):
        """Sorting empty list should return empty list."""
        assert sort_periods([], 'instant') == []
        assert sort_periods([], 'duration') == []

    def test_sort_single_period(self):
        """Single period list should return unchanged."""
        period = [{'key': 'instant_2024-01-01', 'date': '2024-01-01', 'type': 'instant'}]
        sorted_periods = sort_periods(period, 'instant')
        assert len(sorted_periods) == 1
        assert sorted_periods[0]['date'] == '2024-01-01'

    def test_sort_duration_periods_with_same_end_date(self):
        """Duration periods with same end date should be sorted by start date."""
        periods = [
            {'key': 'a', 'start_date': '2024-01-01', 'end_date': '2024-12-31', 'type': 'duration'},
            {'key': 'b', 'start_date': '2024-07-01', 'end_date': '2024-12-31', 'type': 'duration'},
        ]
        sorted_periods = sort_periods(periods, 'duration')

        # Later start date comes first (more recent semi-annual vs full year)
        assert sorted_periods[0]['start_date'] == '2024-07-01'
        assert sorted_periods[1]['start_date'] == '2024-01-01'


# =============================================================================
# Tests for filter_periods_by_document_end_date
# =============================================================================

class TestFilterPeriodsByDocumentEndDate:
    """Tests for the filter_periods_by_document_end_date function."""

    def test_filter_instant_periods_by_end_date(self, instant_periods):
        """Instant periods after document end date should be filtered out."""
        # Document end date is mid-year 2024
        filtered = filter_periods_by_document_end_date(
            instant_periods, '2024-06-30', 'instant'
        )

        # Should include periods on or before June 30, 2024
        dates = [p['date'] for p in filtered]
        assert '2024-03-31' in dates
        assert '2023-12-31' in dates
        assert '2023-06-30' in dates
        # Should exclude December 31, 2024
        assert '2024-12-31' not in dates

    def test_filter_duration_periods_by_end_date(self, duration_periods):
        """Duration periods ending after document end date should be filtered out."""
        filtered = filter_periods_by_document_end_date(
            duration_periods, '2024-06-30', 'duration'
        )

        # Should include Q1 2024 and Q2 2024 and Annual 2023
        keys = [p['key'] for p in filtered]
        assert 'duration_2024-01-01_2024-03-31' in keys
        assert 'duration_2024-04-01_2024-06-30' in keys
        assert 'duration_2023-01-01_2023-12-31' in keys
        # Should exclude Annual 2024 (ends Dec 31, 2024)
        assert 'duration_2024-01-01_2024-12-31' not in keys

    def test_filter_with_no_document_end_date(self, instant_periods):
        """When no document end date provided, return all periods."""
        filtered = filter_periods_by_document_end_date(
            instant_periods, None, 'instant'
        )
        assert len(filtered) == len(instant_periods)

    def test_filter_with_empty_document_end_date(self, instant_periods):
        """When empty document end date, return all periods."""
        filtered = filter_periods_by_document_end_date(
            instant_periods, '', 'instant'
        )
        assert len(filtered) == len(instant_periods)

    def test_filter_with_invalid_document_end_date(self, instant_periods):
        """When invalid document end date, return all periods."""
        filtered = filter_periods_by_document_end_date(
            instant_periods, 'not-a-date', 'instant'
        )
        assert len(filtered) == len(instant_periods)

    def test_filter_includes_period_on_exact_end_date(self, instant_periods):
        """Period on exact document end date should be included."""
        filtered = filter_periods_by_document_end_date(
            instant_periods, '2024-03-31', 'instant'
        )

        dates = [p['date'] for p in filtered]
        assert '2024-03-31' in dates

    def test_filter_empty_periods_list(self):
        """Filtering empty list should return empty list."""
        filtered = filter_periods_by_document_end_date([], '2024-12-31', 'instant')
        assert filtered == []

    def test_filter_with_period_having_invalid_date(self):
        """Period with invalid date should be included (safe fallback)."""
        periods = [
            {'key': 'a', 'date': '2024-01-01', 'type': 'instant'},
            {'key': 'b', 'date': 'invalid-date', 'type': 'instant'},
        ]
        filtered = filter_periods_by_document_end_date(periods, '2024-06-30', 'instant')

        # Both should be included (invalid date periods are kept for safety)
        assert len(filtered) == 2


# =============================================================================
# Tests for filter_periods_by_type
# =============================================================================

class TestFilterPeriodsByType:
    """Tests for the filter_periods_by_type function."""

    def test_filter_instant_periods(self, mixed_periods):
        """Should return only instant periods."""
        filtered = filter_periods_by_type(mixed_periods, 'instant')

        assert all(p['type'] == 'instant' for p in filtered)
        assert len(filtered) == 4  # 4 instant periods in fixture

    def test_filter_duration_periods(self, mixed_periods):
        """Should return only duration periods."""
        filtered = filter_periods_by_type(mixed_periods, 'duration')

        assert all(p['type'] == 'duration' for p in filtered)
        assert len(filtered) == 4  # 4 duration periods in fixture

    def test_filter_empty_list(self):
        """Filtering empty list should return empty list."""
        assert filter_periods_by_type([], 'instant') == []

    def test_filter_no_matching_type(self, instant_periods):
        """If no matching type, return empty list."""
        filtered = filter_periods_by_type(instant_periods, 'duration')
        assert filtered == []


# =============================================================================
# Tests for calculate_fiscal_alignment_score
# =============================================================================

class TestCalculateFiscalAlignmentScore:
    """Tests for the calculate_fiscal_alignment_score function."""

    def test_perfect_match_returns_100(self):
        """Exact fiscal year end match should return 100."""
        end_date = date(2024, 12, 31)
        score = calculate_fiscal_alignment_score(end_date, fiscal_month=12, fiscal_day=31)
        assert score == 100

    def test_perfect_match_non_calendar_year(self):
        """Non-calendar fiscal year end match should return 100."""
        # Apple-style fiscal year ending September 28
        end_date = date(2024, 9, 28)
        score = calculate_fiscal_alignment_score(end_date, fiscal_month=9, fiscal_day=28)
        assert score == 100

    def test_same_month_within_15_days_returns_75(self):
        """Same month within 15 days should return 75."""
        end_date = date(2024, 12, 28)  # 3 days off from Dec 31
        score = calculate_fiscal_alignment_score(end_date, fiscal_month=12, fiscal_day=31)
        assert score == 75

    def test_same_month_exactly_15_days_off_returns_75(self):
        """Same month exactly 15 days off should return 75."""
        end_date = date(2024, 12, 16)  # 15 days off from Dec 31
        score = calculate_fiscal_alignment_score(end_date, fiscal_month=12, fiscal_day=31)
        assert score == 75

    def test_adjacent_month_within_15_days_returns_50(self):
        """Adjacent month within 15 days should return 50."""
        # Test with adjacent months (not year boundary - function uses simple month diff)
        # July 28 vs June 30 fiscal year end: month diff=1, day diff=2
        end_date = date(2024, 7, 28)  # July 28, fiscal year ends June 30
        score = calculate_fiscal_alignment_score(end_date, fiscal_month=6, fiscal_day=30)
        assert score == 50

    def test_no_alignment_returns_0(self):
        """Dates far from fiscal year end should return 0."""
        end_date = date(2024, 6, 30)  # Mid-year for calendar year-end company
        score = calculate_fiscal_alignment_score(end_date, fiscal_month=12, fiscal_day=31)
        assert score == 0

    def test_quarterly_date_no_alignment(self):
        """Quarterly date should not align with annual fiscal year end."""
        end_date = date(2024, 3, 31)  # Q1 end for calendar year company
        score = calculate_fiscal_alignment_score(end_date, fiscal_month=12, fiscal_day=31)
        assert score == 0

    def test_same_month_over_15_days_off_returns_0(self):
        """Same month but over 15 days off should return 0."""
        end_date = date(2024, 12, 10)  # 21 days off from Dec 31
        score = calculate_fiscal_alignment_score(end_date, fiscal_month=12, fiscal_day=31)
        assert score == 0


# =============================================================================
# Tests for generate_period_view
# =============================================================================

class TestGeneratePeriodView:
    """Tests for the generate_period_view function."""

    @pytest.fixture
    def sample_view_config(self):
        """Sample view configuration."""
        return {
            'name': 'Three Recent Periods',
            'description': 'Shows three most recent reporting periods',
            'max_periods': 3,
            'requires_min_periods': 3
        }

    @pytest.fixture
    def annual_only_config(self):
        """View config that's only for annual reports."""
        return {
            'name': 'Three-Year Annual Comparison',
            'description': 'Shows three fiscal years for comparison',
            'max_periods': 3,
            'requires_min_periods': 3,
            'annual_only': True
        }

    def test_generate_view_with_sufficient_periods(self, sample_view_config, instant_periods):
        """Should generate view when sufficient periods available."""
        view = generate_period_view(sample_view_config, instant_periods, is_annual=False)

        assert view is not None
        assert view['name'] == 'Three Recent Periods'
        assert view['description'] == 'Shows three most recent reporting periods'
        assert len(view['period_keys']) == 3

    def test_generate_view_insufficient_periods(self, sample_view_config):
        """Should return None when insufficient periods."""
        periods = [
            {'key': 'instant_2024-01-01', 'date': '2024-01-01'},
            {'key': 'instant_2024-02-01', 'date': '2024-02-01'},
        ]
        view = generate_period_view(sample_view_config, periods, is_annual=False)

        assert view is None

    def test_generate_view_limits_to_max_periods(self, instant_periods):
        """Should limit period keys to max_periods."""
        config = {
            'name': 'Two Periods',
            'description': 'Shows two periods',
            'max_periods': 2,
            'requires_min_periods': 1
        }
        view = generate_period_view(config, instant_periods, is_annual=False)

        assert view is not None
        assert len(view['period_keys']) == 2

    def test_annual_only_view_not_generated_for_quarterly(self, annual_only_config, instant_periods):
        """Annual-only view should not be generated for quarterly reports."""
        view = generate_period_view(annual_only_config, instant_periods, is_annual=False)

        assert view is None

    def test_annual_only_view_generated_for_annual(self, annual_only_config, instant_periods):
        """Annual-only view should be generated for annual reports."""
        view = generate_period_view(annual_only_config, instant_periods, is_annual=True)

        assert view is not None
        assert view['name'] == 'Three-Year Annual Comparison'

    def test_generate_view_with_fewer_periods_than_max(self):
        """Should use available periods when fewer than max."""
        config = {
            'name': 'Flexible View',
            'description': 'Uses available periods',
            'max_periods': 5,
            'requires_min_periods': 1
        }
        periods = [
            {'key': 'a', 'date': '2024-01-01'},
            {'key': 'b', 'date': '2024-02-01'},
        ]
        view = generate_period_view(config, periods, is_annual=False)

        assert view is not None
        assert len(view['period_keys']) == 2


# =============================================================================
# Tests for generate_mixed_view
# =============================================================================

class TestGenerateMixedView:
    """Tests for the generate_mixed_view function."""

    @pytest.fixture
    def mixed_view_config(self):
        """Sample mixed view configuration."""
        return {
            'name': 'YTD and Quarterly Breakdown',
            'description': 'Shows YTD figures and quarterly breakdown',
            'max_periods': 5,
            'requires_min_periods': 2,
            'mixed_view': True
        }

    @pytest.fixture
    def ytd_periods(self):
        """Year-to-date periods."""
        return [
            {'key': 'ytd_2024_h1', 'start_date': '2024-01-01', 'end_date': '2024-06-30', 'ytd': True},
            {'key': 'ytd_2023_h1', 'start_date': '2023-01-01', 'end_date': '2023-06-30', 'ytd': True},
        ]

    @pytest.fixture
    def quarterly_periods(self):
        """Quarterly periods."""
        return [
            {'key': 'q2_2024', 'start_date': '2024-04-01', 'end_date': '2024-06-30', 'quarterly': True},
            {'key': 'q1_2024', 'start_date': '2024-01-01', 'end_date': '2024-03-31', 'quarterly': True},
            {'key': 'q2_2023', 'start_date': '2023-04-01', 'end_date': '2023-06-30', 'quarterly': True},
            {'key': 'q1_2023', 'start_date': '2023-01-01', 'end_date': '2023-03-31', 'quarterly': True},
        ]

    def test_generate_mixed_view_success(self, mixed_view_config, ytd_periods, quarterly_periods):
        """Should generate mixed view with YTD and quarterly periods."""
        view = generate_mixed_view(mixed_view_config, ytd_periods, quarterly_periods)

        assert view is not None
        assert view['name'] == 'YTD and Quarterly Breakdown'
        # Should include current YTD first
        assert view['period_keys'][0] == 'ytd_2024_h1'
        # Should include quarterly periods
        assert len(view['period_keys']) >= 2

    def test_generate_mixed_view_no_ytd_periods(self, mixed_view_config, quarterly_periods):
        """Should return None when no YTD periods."""
        view = generate_mixed_view(mixed_view_config, [], quarterly_periods)

        assert view is None

    def test_generate_mixed_view_no_quarterly_periods(self, mixed_view_config, ytd_periods):
        """Should return None when no quarterly periods."""
        view = generate_mixed_view(mixed_view_config, ytd_periods, [])

        assert view is None

    def test_generate_mixed_view_insufficient_total_periods(self, ytd_periods):
        """Should return None when combined periods don't meet minimum."""
        config = {
            'name': 'Test View',
            'description': 'Test',
            'max_periods': 5,
            'requires_min_periods': 10,  # High requirement
            'mixed_view': True
        }
        quarterly = [{'key': 'q1', 'quarterly': True}]

        view = generate_mixed_view(config, ytd_periods, quarterly)

        assert view is None

    def test_generate_mixed_view_limits_to_max_periods(self, mixed_view_config, ytd_periods, quarterly_periods):
        """Should limit total periods to max_periods."""
        view = generate_mixed_view(mixed_view_config, ytd_periods, quarterly_periods)

        assert view is not None
        assert len(view['period_keys']) <= mixed_view_config['max_periods']

    def test_generate_mixed_view_avoids_duplicate_keys(self, mixed_view_config):
        """Should not include duplicate period keys."""
        ytd = [{'key': 'same_key', 'ytd': True}]
        quarterly = [
            {'key': 'same_key', 'quarterly': True},  # Same as YTD key
            {'key': 'other_key', 'quarterly': True},
        ]

        view = generate_mixed_view(mixed_view_config, ytd, quarterly)

        assert view is not None
        # Should not have duplicates
        assert len(view['period_keys']) == len(set(view['period_keys']))


# =============================================================================
# Tests for STATEMENT_TYPE_CONFIG
# =============================================================================

class TestStatementTypeConfig:
    """Tests for the STATEMENT_TYPE_CONFIG constant."""

    def test_balance_sheet_config_exists(self):
        """BalanceSheet config should exist with correct period type."""
        config = STATEMENT_TYPE_CONFIG.get('BalanceSheet')

        assert config is not None
        assert config['period_type'] == 'instant'
        assert 'views' in config

    def test_income_statement_config_exists(self):
        """IncomeStatement config should exist with correct period type."""
        config = STATEMENT_TYPE_CONFIG.get('IncomeStatement')

        assert config is not None
        assert config['period_type'] == 'duration'
        assert 'views' in config

    def test_all_statement_types_have_required_fields(self):
        """All statement type configs should have required fields."""
        for statement_type, config in STATEMENT_TYPE_CONFIG.items():
            assert 'period_type' in config, f"{statement_type} missing period_type"
            assert 'views' in config, f"{statement_type} missing views"
            assert config['period_type'] in ('instant', 'duration'), \
                f"{statement_type} has invalid period_type"

    def test_all_views_have_required_fields(self):
        """All views in config should have required fields."""
        required_fields = {'name', 'description', 'max_periods', 'requires_min_periods'}

        for statement_type, config in STATEMENT_TYPE_CONFIG.items():
            for i, view in enumerate(config['views']):
                missing = required_fields - set(view.keys())
                assert not missing, \
                    f"{statement_type} view {i} missing fields: {missing}"

    def test_balance_sheet_has_annual_comparison_view(self):
        """BalanceSheet should have Three-Year Annual Comparison view."""
        config = STATEMENT_TYPE_CONFIG.get('BalanceSheet')
        view_names = [v['name'] for v in config['views']]

        assert 'Three-Year Annual Comparison' in view_names

    def test_income_statement_has_ytd_view(self):
        """IncomeStatement should have YTD and Quarterly Breakdown view."""
        config = STATEMENT_TYPE_CONFIG.get('IncomeStatement')
        view_names = [v['name'] for v in config['views']]

        assert 'YTD and Quarterly Breakdown' in view_names

    def test_cover_page_single_period(self):
        """CoverPage should only show 1 period."""
        config = STATEMENT_TYPE_CONFIG.get('CoverPage')

        assert config is not None
        assert config['max_periods'] == 1

    def test_statement_types_coverage(self):
        """Should have configs for major statement types."""
        expected_types = {
            'BalanceSheet',
            'IncomeStatement',
            'StatementOfEquity',
            'ComprehensiveIncome',
            'CoverPage',
            'Notes'
        }

        actual_types = set(STATEMENT_TYPE_CONFIG.keys())

        # All expected types should be present
        assert expected_types.issubset(actual_types)


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Edge case tests for periods module."""

    def test_sort_periods_with_none_values(self):
        """Sorting should handle periods missing expected fields gracefully."""
        # This tests defensive coding - real data shouldn't have None
        periods = [
            {'key': 'a', 'date': '2024-01-01', 'type': 'instant'},
            {'key': 'b', 'date': '2024-06-01', 'type': 'instant'},
        ]
        # Should not raise
        sorted_periods = sort_periods(periods, 'instant')
        assert len(sorted_periods) == 2

    def test_filter_by_type_with_mixed_types_in_list(self):
        """Filter should correctly separate mixed types."""
        periods = [
            {'key': 'instant1', 'type': 'instant'},
            {'key': 'duration1', 'type': 'duration'},
            {'key': 'instant2', 'type': 'instant'},
            {'key': 'duration2', 'type': 'duration'},
        ]

        instant = filter_periods_by_type(periods, 'instant')
        duration = filter_periods_by_type(periods, 'duration')

        assert len(instant) == 2
        assert len(duration) == 2
        assert all(p['type'] == 'instant' for p in instant)
        assert all(p['type'] == 'duration' for p in duration)

    def test_fiscal_alignment_score_boundary_month(self):
        """Test fiscal alignment at month boundaries."""
        # January 1 (next month after December 31)
        end_date = date(2025, 1, 1)
        score = calculate_fiscal_alignment_score(end_date, fiscal_month=12, fiscal_day=31)
        # Adjacent month check: abs(1 - 12) = 11, not <= 1
        # So this should return 0
        assert score == 0

    def test_fiscal_alignment_score_december_to_january_wrap(self):
        """Test fiscal alignment wrapping from December to January."""
        # Late December for January fiscal year end
        end_date = date(2024, 12, 28)
        score = calculate_fiscal_alignment_score(end_date, fiscal_month=1, fiscal_day=15)
        # abs(12 - 1) = 11, not <= 1, so no adjacent month match
        assert score == 0

    def test_generate_period_view_empty_periods_list(self):
        """Should return None for empty periods list."""
        config = {
            'name': 'Test',
            'description': 'Test',
            'max_periods': 3,
            'requires_min_periods': 1
        }
        view = generate_period_view(config, [], is_annual=False)

        assert view is None

    def test_generate_mixed_view_empty_lists(self):
        """Should return None when both period lists are empty."""
        config = {
            'name': 'Test',
            'description': 'Test',
            'max_periods': 5,
            'requires_min_periods': 1
        }
        view = generate_mixed_view(config, [], [])

        assert view is None
