"""
Tests for cross-validation between SEC Viewer and XBRL parser.

Unit tests use fixture data and mock XBRL objects.
"""
import pytest
from edgar.xbrl.viewer_validation import (
    _parse_viewer_period,
    _normalize_concept_id,
    _match_xbrl_period,
    ComparisonResult,
    ComparisonResults,
    compare_viewer_to_xbrl,
)


class TestParseViewerPeriod:

    def test_instant_date(self):
        result = _parse_viewer_period('Mar. 29, 2025')
        assert result is not None
        assert result['end'] == '2025-03-29'
        assert result['duration_hint'] is None

    def test_3_months_ended(self):
        result = _parse_viewer_period('3 Months Ended Mar. 29, 2025')
        assert result['end'] == '2025-03-29'
        assert result['duration_hint'] == 90  # 3 * 30

    def test_6_months_ended(self):
        result = _parse_viewer_period('6 Months Ended Mar. 29, 2025')
        assert result['end'] == '2025-03-29'
        assert result['duration_hint'] == 180

    def test_12_months_ended(self):
        result = _parse_viewer_period('12 Months Ended Sep. 28, 2024')
        assert result['end'] == '2024-09-28'
        assert result['duration_hint'] == 360

    def test_september(self):
        result = _parse_viewer_period('Sep. 28, 2024')
        assert result['end'] == '2024-09-28'

    def test_december(self):
        result = _parse_viewer_period('Dec. 31, 2024')
        assert result['end'] == '2024-12-31'

    def test_invalid_returns_none(self):
        assert _parse_viewer_period('not a date') is None
        assert _parse_viewer_period('') is None

    def test_full_month_name(self):
        result = _parse_viewer_period('March 29, 2025')
        assert result is not None
        assert result['end'] == '2025-03-29'


class TestNormalizeConceptId:

    def test_standard_concept(self):
        """XBRL facts use colon format."""
        assert _normalize_concept_id('us-gaap_Assets') == 'us-gaap:Assets'

    def test_custom_concept(self):
        assert _normalize_concept_id('aapl_MacRevenue') == 'aapl:MacRevenue'

    def test_no_namespace(self):
        assert _normalize_concept_id('Assets') == 'Assets'


class TestMatchXbrlPeriod:

    def test_instant_match(self):
        columns = ['2025-03-29', '2024-09-28']
        result = _match_xbrl_period('2025-03-29', None, columns)
        assert result == '2025-03-29'

    def test_duration_match_3_months(self):
        columns = [
            '2024-12-29_2025-03-29',  # ~90 days (3 months)
            '2024-09-29_2025-03-29',  # ~180 days (6 months)
        ]
        result = _match_xbrl_period('2025-03-29', 90, columns)
        assert result == '2024-12-29_2025-03-29'

    def test_duration_match_6_months(self):
        columns = [
            '2024-12-29_2025-03-29',  # ~90 days
            '2024-09-29_2025-03-29',  # ~180 days
        ]
        result = _match_xbrl_period('2025-03-29', 180, columns)
        assert result == '2024-09-29_2025-03-29'

    def test_no_match_returns_none(self):
        columns = ['2024-09-28']
        result = _match_xbrl_period('2025-03-29', None, columns)
        assert result is None

    def test_duration_with_no_hint_picks_shortest(self):
        columns = [
            '2024-12-29_2025-03-29',  # 90 days
            '2024-09-29_2025-03-29',  # 180 days
        ]
        result = _match_xbrl_period('2025-03-29', None, columns)
        assert result == '2024-12-29_2025-03-29'

    def test_end_date_column_preferred(self):
        """XBRL DataFrames typically use just end dates as columns."""
        columns = ['2025-03-29', '2024-12-29_2025-03-29']
        # End date match takes priority
        result = _match_xbrl_period('2025-03-29', 90, columns)
        assert result == '2025-03-29'

    def test_falls_back_to_duration_when_no_end_date(self):
        columns = ['2024-12-29_2025-03-29', '2024-09-29_2025-03-29']
        result = _match_xbrl_period('2025-03-29', 90, columns)
        assert result == '2024-12-29_2025-03-29'


class TestComparisonResult:

    def test_basic_match(self):
        r = ComparisonResult(
            concept_id='us-gaap:Assets',
            label='Total assets',
            period='Mar. 29, 2025',
            viewer_value=352583.0,
            xbrl_value=352583.0,
            difference=0.0,
            match=True,
            report='Balance Sheet',
        )
        assert r.match is True
        assert r.difference == 0.0

    def test_mismatch(self):
        r = ComparisonResult(
            concept_id='us-gaap:Revenue',
            label='Net sales',
            period='3 Months Ended Mar. 29, 2025',
            viewer_value=95359.0,
            xbrl_value=95360.0,
            difference=-1.0,
            match=True,  # within tolerance
            report='Income Statement',
        )
        assert r.difference == -1.0


class TestComparisonResults:

    def test_empty_results(self):
        cr = ComparisonResults()
        assert cr.total == 0
        assert cr.matched == 0
        assert cr.match_rate == 0.0

    def test_all_matched(self):
        cr = ComparisonResults(results=[
            ComparisonResult('a', 'A', 'p1', 100, 100, 0, True, 'R'),
            ComparisonResult('b', 'B', 'p1', 200, 200, 0, True, 'R'),
        ])
        assert cr.total == 2
        assert cr.matched == 2
        assert cr.match_rate == 1.0
        assert cr.mismatched == 0

    def test_with_mismatch(self):
        cr = ComparisonResults(results=[
            ComparisonResult('a', 'A', 'p1', 100, 100, 0, True, 'R'),
            ComparisonResult('b', 'B', 'p1', 200, 205, -5, False, 'R'),
        ])
        assert cr.matched == 1
        assert cr.mismatched == 1
        assert cr.match_rate == 0.5
        assert len(cr.mismatches) == 1

    def test_with_missing(self):
        cr = ComparisonResults(results=[
            ComparisonResult('a', 'A', 'p1', 100, 100, 0, True, 'R'),
            ComparisonResult('b', 'B', 'p1', 200, None, None, False, 'R'),
        ])
        assert cr.missing == 1
        assert cr.match_rate == 1.0  # 1/1 compared (missing excluded)

    def test_str(self):
        cr = ComparisonResults(results=[
            ComparisonResult('a', 'A', 'p1', 100, 100, 0, True, 'R'),
        ])
        s = str(cr)
        assert 'total=1' in s
        assert 'matched=1' in s

    def test_to_dataframe(self):
        import pandas as pd
        cr = ComparisonResults(results=[
            ComparisonResult('a', 'A', 'p1', 100, 100, 0, True, 'R'),
            ComparisonResult('b', 'B', 'p1', 200, 205, -5, False, 'R'),
        ])
        df = cr.to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert 'viewer_value' in df.columns
        assert 'xbrl_value' in df.columns

    def test_rich_display(self):
        cr = ComparisonResults(results=[
            ComparisonResult('a', 'A', 'p1', 100, 105, -5, False, 'R'),
        ])
        panel = cr.__rich__()
        assert panel is not None
