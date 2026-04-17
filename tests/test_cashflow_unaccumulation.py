"""
Tests for CashFlowStatement YTD → discrete quarter unaccumulation.

The SEC requires 10-Q cash flow statements to report year-to-date (YTD) cumulative
values. The unaccumulation feature derives discrete quarter values by subtracting
adjacent YTD periods:
    Q2_discrete = YTD_6M - Q1
    Q3_discrete = YTD_9M - YTD_6M
    Q4_discrete = FY - YTD_9M
"""

from collections import defaultdict

import pytest

from edgar.xbrl.stitching.core import StatementStitcher


def _make_cashflow_stitcher(periods, concepts):
    """Build a StatementStitcher pre-loaded with synthetic cashflow data.

    Args:
        periods: list of period_id strings (ordered newest-first as the stitcher expects)
        concepts: list of dicts with keys:
            key: concept key string
            values: dict of {period_id: numeric_value}
            label: display label (optional)
    """
    stitcher = StatementStitcher()
    stitcher.periods = list(periods)
    stitcher.period_dates = {pid: pid for pid in periods}
    stitcher.data = defaultdict(dict)
    stitcher.concept_metadata = {}

    for c in concepts:
        key = c['key']
        for pid, val in c['values'].items():
            stitcher.data[key][pid] = {'value': val, 'decimals': -3}
        stitcher.concept_metadata[key] = {
            'level': 0,
            'is_abstract': False,
            'is_total': c.get('is_total', False),
            'original_concept': key,
            'latest_label': c.get('label', key),
            'standard_concept': None,
        }
    return stitcher


class TestUnaccumulateCashflowYTD:
    """Unit tests for _unaccumulate_cashflow_ytd on StatementStitcher."""

    def test_q2_derived_from_ytd6_minus_q1(self):
        """Q2 discrete = 6-month YTD minus Q1 (3-month)."""
        # Q1: 90 days, YTD_6M: 181 days (same fiscal year start)
        q1_pid = 'duration_2024-01-01_2024-03-31'       # 90 days
        ytd6_pid = 'duration_2024-01-01_2024-06-30'     # 181 days

        stitcher = _make_cashflow_stitcher(
            periods=[ytd6_pid, q1_pid],
            concepts=[
                {'key': 'us-gaap_OperatingCashFlow', 'values': {
                    q1_pid: 100,
                    ytd6_pid: 350,   # cumulative 6-month
                }},
                {'key': 'us-gaap_CapitalExpenditure', 'values': {
                    q1_pid: -50,
                    ytd6_pid: -120,  # cumulative 6-month
                }},
            ],
        )

        stitcher._unaccumulate_cashflow_ytd()

        # YTD_6M period should now hold Q2 discrete values
        assert stitcher.data['us-gaap_OperatingCashFlow'][ytd6_pid]['value'] == 250   # 350 - 100
        assert stitcher.data['us-gaap_CapitalExpenditure'][ytd6_pid]['value'] == -70  # -120 - (-50)
        # Q1 values should be unchanged
        assert stitcher.data['us-gaap_OperatingCashFlow'][q1_pid]['value'] == 100
        assert stitcher.data['us-gaap_CapitalExpenditure'][q1_pid]['value'] == -50

    def test_q3_derived_from_ytd9_minus_ytd6(self):
        """Q3 discrete = 9-month YTD minus 6-month YTD."""
        q1_pid = 'duration_2024-01-01_2024-03-31'       # 90 days
        ytd6_pid = 'duration_2024-01-01_2024-06-30'     # 181 days
        ytd9_pid = 'duration_2024-01-01_2024-09-30'     # 273 days

        stitcher = _make_cashflow_stitcher(
            periods=[ytd9_pid, ytd6_pid, q1_pid],
            concepts=[
                {'key': 'us-gaap_OperatingCashFlow', 'values': {
                    q1_pid: 100,
                    ytd6_pid: 350,
                    ytd9_pid: 600,   # cumulative 9-month
                }},
            ],
        )

        stitcher._unaccumulate_cashflow_ytd()

        # Q3 discrete: 600 - 350 = 250
        assert stitcher.data['us-gaap_OperatingCashFlow'][ytd9_pid]['value'] == 250
        # Q2 discrete: 350 - 100 = 250
        assert stitcher.data['us-gaap_OperatingCashFlow'][ytd6_pid]['value'] == 250
        # Q1 unchanged
        assert stitcher.data['us-gaap_OperatingCashFlow'][q1_pid]['value'] == 100

    def test_q4_derived_from_fy_minus_ytd9(self):
        """Q4 discrete = FY (annual) minus 9-month YTD."""
        ytd9_pid = 'duration_2024-01-01_2024-09-30'     # 273 days
        fy_pid = 'duration_2024-01-01_2024-12-31'       # 365 days

        stitcher = _make_cashflow_stitcher(
            periods=[fy_pid, ytd9_pid],
            concepts=[
                {'key': 'us-gaap_OperatingCashFlow', 'values': {
                    ytd9_pid: 600,
                    fy_pid: 900,     # full year
                }},
            ],
        )

        stitcher._unaccumulate_cashflow_ytd()

        # Q4 discrete: 900 - 600 = 300
        assert stitcher.data['us-gaap_OperatingCashFlow'][fy_pid]['value'] == 300
        # YTD9 unchanged (no shorter YTD to subtract from it in this set)
        assert stitcher.data['us-gaap_OperatingCashFlow'][ytd9_pid]['value'] == 600

    def test_full_year_all_four_quarters(self):
        """Full chain: Q1 + Q2 YTD + Q3 YTD + FY → four discrete quarters."""
        q1_pid = 'duration_2024-01-01_2024-03-31'       # 90 days
        ytd6_pid = 'duration_2024-01-01_2024-06-30'     # 181 days
        ytd9_pid = 'duration_2024-01-01_2024-09-30'     # 273 days
        fy_pid = 'duration_2024-01-01_2024-12-31'       # 365 days

        stitcher = _make_cashflow_stitcher(
            periods=[fy_pid, ytd9_pid, ytd6_pid, q1_pid],
            concepts=[
                {'key': 'us-gaap_OperatingCashFlow', 'values': {
                    q1_pid: 100,     # Q1 discrete
                    ytd6_pid: 350,   # Q1 + Q2
                    ytd9_pid: 600,   # Q1 + Q2 + Q3
                    fy_pid: 1000,    # Q1 + Q2 + Q3 + Q4
                }},
            ],
        )

        stitcher._unaccumulate_cashflow_ytd()

        assert stitcher.data['us-gaap_OperatingCashFlow'][q1_pid]['value'] == 100   # unchanged
        assert stitcher.data['us-gaap_OperatingCashFlow'][ytd6_pid]['value'] == 250  # 350-100
        assert stitcher.data['us-gaap_OperatingCashFlow'][ytd9_pid]['value'] == 250  # 600-350
        assert stitcher.data['us-gaap_OperatingCashFlow'][fy_pid]['value'] == 400    # 1000-600

    def test_concept_missing_in_shorter_period_kept_as_is(self):
        """If a concept has no value in the shorter period, the longer value is kept unchanged."""
        q1_pid = 'duration_2024-01-01_2024-03-31'
        ytd6_pid = 'duration_2024-01-01_2024-06-30'

        stitcher = _make_cashflow_stitcher(
            periods=[ytd6_pid, q1_pid],
            concepts=[
                # This concept only appears in YTD_6M, not Q1
                {'key': 'us-gaap_SpecialItem', 'values': {
                    ytd6_pid: 42,
                }},
            ],
        )

        stitcher._unaccumulate_cashflow_ytd()

        # Should be kept as-is since there's nothing to subtract
        assert stitcher.data['us-gaap_SpecialItem'][ytd6_pid]['value'] == 42

    def test_different_fiscal_year_starts_handled_independently(self):
        """Periods from different fiscal years don't interfere with each other."""
        # FY2023 Q1 and YTD_6M
        fy23_q1 = 'duration_2023-01-01_2023-03-31'
        fy23_ytd6 = 'duration_2023-01-01_2023-06-30'
        # FY2024 Q1 and YTD_6M
        fy24_q1 = 'duration_2024-01-01_2024-03-31'
        fy24_ytd6 = 'duration_2024-01-01_2024-06-30'

        stitcher = _make_cashflow_stitcher(
            periods=[fy24_ytd6, fy24_q1, fy23_ytd6, fy23_q1],
            concepts=[
                {'key': 'us-gaap_Revenue', 'values': {
                    fy23_q1: 200,
                    fy23_ytd6: 500,
                    fy24_q1: 300,
                    fy24_ytd6: 700,
                }},
            ],
        )

        stitcher._unaccumulate_cashflow_ytd()

        # FY2023: Q2 = 500 - 200 = 300
        assert stitcher.data['us-gaap_Revenue'][fy23_ytd6]['value'] == 300
        assert stitcher.data['us-gaap_Revenue'][fy23_q1]['value'] == 200
        # FY2024: Q2 = 700 - 300 = 400
        assert stitcher.data['us-gaap_Revenue'][fy24_ytd6]['value'] == 400
        assert stitcher.data['us-gaap_Revenue'][fy24_q1]['value'] == 300

    def test_period_label_ytd_stripped(self):
        """Display labels should have 'YTD' removed after unaccumulation."""
        q1_pid = 'duration_2024-01-01_2024-03-31'
        ytd6_pid = 'duration_2024-01-01_2024-06-30'

        stitcher = _make_cashflow_stitcher(
            periods=[ytd6_pid, q1_pid],
            concepts=[
                {'key': 'us-gaap_X', 'values': {q1_pid: 10, ytd6_pid: 30}},
            ],
        )
        stitcher.period_dates[ytd6_pid] = 'Q2 YTD Jun 30, 2024'
        stitcher.period_dates[q1_pid] = 'Q1 Mar 31, 2024'

        stitcher._unaccumulate_cashflow_ytd()

        assert stitcher.period_dates[ytd6_pid] == 'Q2 Jun 30, 2024'
        # Q1 label untouched
        assert stitcher.period_dates[q1_pid] == 'Q1 Mar 31, 2024'

    def test_instant_periods_ignored(self):
        """Instant periods (balance sheet style) should not be touched."""
        instant_pid = 'instant_2024-06-30'
        q1_pid = 'duration_2024-01-01_2024-03-31'

        stitcher = _make_cashflow_stitcher(
            periods=[instant_pid, q1_pid],
            concepts=[
                {'key': 'us-gaap_Cash', 'values': {
                    instant_pid: 5000,
                    q1_pid: 100,
                }},
            ],
        )

        stitcher._unaccumulate_cashflow_ytd()

        # Instant value untouched
        assert stitcher.data['us-gaap_Cash'][instant_pid]['value'] == 5000

    def test_single_period_no_op(self):
        """With only one duration period, nothing should change."""
        q1_pid = 'duration_2024-01-01_2024-03-31'

        stitcher = _make_cashflow_stitcher(
            periods=[q1_pid],
            concepts=[
                {'key': 'us-gaap_X', 'values': {q1_pid: 100}},
            ],
        )

        stitcher._unaccumulate_cashflow_ytd()

        assert stitcher.data['us-gaap_X'][q1_pid]['value'] == 100


class TestDiscreteQuartersFlag:
    """Test that discrete_quarters=False (default) does NOT unaccumulate."""

    def test_default_false_preserves_ytd_values(self):
        """stitch_statements with default discrete_quarters=False should leave YTD values intact."""
        q1_pid = 'duration_2024-01-01_2024-03-31'
        ytd6_pid = 'duration_2024-01-01_2024-06-30'

        statements = [{
            'statement_type': 'CashFlowStatement',
            'periods': {
                q1_pid: {'label': 'Q1 Mar 31, 2024'},
                ytd6_pid: {'label': 'Q2 YTD Jun 30, 2024'},
            },
            'data': [{
                'concept': 'us-gaap_OperatingCashFlow',
                'label': 'Operating Cash Flow',
                'level': 0,
                'is_abstract': False,
                'is_total': True,
                'values': {q1_pid: 100, ytd6_pid: 350},
                'decimals': {q1_pid: 0, ytd6_pid: 0},
            }],
        }]

        stitcher = StatementStitcher()
        result = stitcher.stitch_statements(
            statements,
            period_type=StatementStitcher.PeriodType.ALL_PERIODS,
            max_periods=10,
            standard=False,
            discrete_quarters=False,  # default
        )

        # Find the operating cash flow row
        row = next(r for r in result['statement_data']
                   if r['concept'] == 'us-gaap_OperatingCashFlow')

        # YTD value should be preserved (NOT subtracted)
        assert row['values'][ytd6_pid] == 350
        assert row['values'][q1_pid] == 100

    def test_true_unaccumulates_ytd_values(self):
        """stitch_statements with discrete_quarters=True should convert YTD to discrete."""
        q1_pid = 'duration_2024-01-01_2024-03-31'
        ytd6_pid = 'duration_2024-01-01_2024-06-30'

        statements = [{
            'statement_type': 'CashFlowStatement',
            'periods': {
                q1_pid: {'label': 'Q1 Mar 31, 2024'},
                ytd6_pid: {'label': 'Q2 YTD Jun 30, 2024'},
            },
            'data': [{
                'concept': 'us-gaap_OperatingCashFlow',
                'label': 'Operating Cash Flow',
                'level': 0,
                'is_abstract': False,
                'is_total': True,
                'values': {q1_pid: 100, ytd6_pid: 350},
                'decimals': {q1_pid: 0, ytd6_pid: 0},
            }],
        }]

        stitcher = StatementStitcher()
        result = stitcher.stitch_statements(
            statements,
            period_type=StatementStitcher.PeriodType.ALL_PERIODS,
            max_periods=10,
            standard=False,
            discrete_quarters=True,
        )

        row = next(r for r in result['statement_data']
                   if r['concept'] == 'us-gaap_OperatingCashFlow')

        # YTD should now be Q2 discrete: 350 - 100 = 250
        assert row['values'][ytd6_pid] == 250
        assert row['values'][q1_pid] == 100

    def test_flag_ignored_for_non_cashflow(self):
        """discrete_quarters=True on IncomeStatement should have no effect."""
        q1_pid = 'duration_2024-01-01_2024-03-31'
        ytd6_pid = 'duration_2024-01-01_2024-06-30'

        statements = [{
            'statement_type': 'IncomeStatement',
            'periods': {
                q1_pid: {'label': 'Q1 Mar 31, 2024'},
                ytd6_pid: {'label': 'Q2 YTD Jun 30, 2024'},
            },
            'data': [{
                'concept': 'us-gaap_Revenue',
                'label': 'Revenue',
                'level': 0,
                'is_abstract': False,
                'is_total': False,
                'values': {q1_pid: 100, ytd6_pid: 350},
                'decimals': {q1_pid: 0, ytd6_pid: 0},
            }],
        }]

        stitcher = StatementStitcher()
        result = stitcher.stitch_statements(
            statements,
            period_type=StatementStitcher.PeriodType.ALL_PERIODS,
            max_periods=10,
            standard=False,
            discrete_quarters=True,  # should be ignored
        )

        row = next(r for r in result['statement_data']
                   if r['concept'] == 'us-gaap_Revenue')

        # Values should be unchanged — not a CashFlowStatement
        assert row['values'][ytd6_pid] == 350
        assert row['values'][q1_pid] == 100


class TestClassifyDiscreteQuarter:
    """Unit tests for the static _classify_discrete_quarter method."""

    def test_q2_classification(self):
        longer = {'duration_days': 181}
        shorter = {'duration_days': 90}
        assert StatementStitcher._classify_discrete_quarter(longer, shorter) == 'Q2'

    def test_q3_classification(self):
        longer = {'duration_days': 273}
        shorter = {'duration_days': 181}
        assert StatementStitcher._classify_discrete_quarter(longer, shorter) == 'Q3'

    def test_q4_classification(self):
        longer = {'duration_days': 365}
        shorter = {'duration_days': 273}
        assert StatementStitcher._classify_discrete_quarter(longer, shorter) == 'Q4'

    def test_unrecognized_pair_returns_none(self):
        # Two quarterly periods — doesn't match any pattern
        longer = {'duration_days': 91}
        shorter = {'duration_days': 90}
        assert StatementStitcher._classify_discrete_quarter(longer, shorter) is None

    def test_non_standard_fiscal_year_q2(self):
        """Companies with non-calendar fiscal years (e.g. Apple ending Sep)."""
        # Apple FY: Oct 1 - Sep 30. Q1 = Oct-Dec (92d), Q2 YTD = Oct-Mar (182d)
        longer = {'duration_days': 182}
        shorter = {'duration_days': 92}
        assert StatementStitcher._classify_discrete_quarter(longer, shorter) == 'Q2'
