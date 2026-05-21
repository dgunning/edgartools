"""
Regression test for GitHub Issue #818:
Iterating ``viewer.financial_statements`` and reading ConceptRow data
returned wrong values for two pre-2020 10-K filings.

Bug A — ADI 2019 10-K Income Statement (acc 0000006281-19-000144):
The R*.htm includes 8 quarterly columns BEFORE the 3 annual columns.
``primary_period`` was set unconditionally to ``period_headers[0]`` — the
most recent quarter — so ``ConceptRow.numeric_value`` returned Q4 values
instead of FY values for every row.

Bug B — ADSK 2019 10-K Income Statement (acc 0000769397-19-000016):
Body rows include an empty ``class="th"`` spacer cell that was kept in
``value_cells``, shifting ``_data_cell_positions`` by one. The FY2019
column got nothing; FY2019 values were bound to the FY2018 label key;
and the FY2017 column data was dropped entirely.

Fixes (both in ``edgar/sgml/concept_extractor.py``):
- A: ``_pick_primary_period`` prefers the longest-duration period for
  annual forms (10-K, 20-F, 40-F); other forms keep the existing
  ``period_headers[0]`` behaviour.
- B: ``class="th"`` cells are filtered out of ``value_cells`` before
  position assignment.
"""

from pathlib import Path

import pytest

from edgar.sgml.concept_extractor import (
    _pick_primary_period,
    extract_concepts_from_report,
)

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "issues" / "regression" / "issue_818"


def _find_row(report, label_substr):
    for row in report.rows:
        if label_substr.lower() in row.label.lower() and row.values:
            return row
    return None


class TestPrimaryPeriodHeuristic:
    """Bug A — ``_pick_primary_period`` selection rules."""

    def test_no_headers_returns_none(self):
        assert _pick_primary_period([], "10-K") is None

    def test_no_form_keeps_default_behaviour(self):
        headers = ['3 Months Ended Nov. 02, 2019', '12 Months Ended Nov. 02, 2019']
        assert _pick_primary_period(headers, None) == headers[0]

    def test_10k_prefers_longest_duration(self):
        """ADI-shape: quarterly first, annual later. Annual wins for 10-K."""
        headers = [
            '3 Months Ended Nov. 02, 2019',
            '3 Months Ended Aug. 03, 2019',
            '12 Months Ended Nov. 02, 2019',
            '12 Months Ended Nov. 03, 2018',
        ]
        assert _pick_primary_period(headers, '10-K') == '12 Months Ended Nov. 02, 2019'

    def test_10q_keeps_first_column(self):
        """10-Q: most recent quarter should remain primary, even if a YTD
        cumulative column is also present."""
        headers = [
            '3 Months Ended Mar. 28, 2026',
            '3 Months Ended Mar. 29, 2025',
            '6 Months Ended Mar. 28, 2026',
            '6 Months Ended Mar. 29, 2025',
        ]
        assert _pick_primary_period(headers, '10-Q') == headers[0]

    def test_10k_balance_sheet_falls_back_to_first(self):
        """Balance-sheet headers have no 'X Months Ended' prefix —
        nothing matches the duration regex, so the first header wins."""
        headers = ['Sep. 27, 2025', 'Sep. 28, 2024']
        assert _pick_primary_period(headers, '10-K') == headers[0]

    def test_20f_treated_like_10k(self):
        headers = ['3 Months Ended Dec. 31, 2024', '12 Months Ended Dec. 31, 2024']
        assert _pick_primary_period(headers, '20-F') == '12 Months Ended Dec. 31, 2024'

    def test_amended_forms_treated_as_annual(self):
        headers = ['3 Months Ended Dec. 31, 2024', '12 Months Ended Dec. 31, 2024']
        assert _pick_primary_period(headers, '10-K/A') == '12 Months Ended Dec. 31, 2024'


class TestADI2019IncomeStatement:
    """Bug A — verified end-to-end against ADI's actual R2.htm."""

    @pytest.fixture(scope='class')
    def report(self):
        html = (FIXTURE_DIR / "adi_2019_R2.htm").read_text()
        return extract_concepts_from_report(html, form='10-K')

    def test_period_headers_include_quarterly_and_annual(self, report):
        ph = report.period_headers
        # ADI's R2.htm presents 8 quarterly columns + 3 annual columns.
        assert any('3 Months Ended' in h for h in ph)
        assert any('12 Months Ended' in h for h in ph)

    def test_revenue_primary_is_annual(self, report):
        """``ConceptRow.numeric_value`` for Revenue must be the FY value,
        not the most recent quarter (the GH #818 ADI symptom)."""
        revenue = _find_row(report, 'Revenue')
        assert revenue is not None
        assert revenue.primary_period == '12 Months Ended Nov. 02, 2019'
        assert revenue.numeric_value == 5991065.0

    def test_revenue_quarterly_values_still_available(self, report):
        """Fix should not drop quarterly values from numeric_values —
        they should remain accessible by their column key."""
        revenue = _find_row(report, 'Revenue')
        assert revenue is not None
        nv = revenue.numeric_values
        assert nv.get('3 Months Ended Nov. 02, 2019') == 1443219.0
        assert nv.get('12 Months Ended Nov. 02, 2019') == 5991065.0

    def test_without_form_falls_back_to_quarterly(self):
        """Sanity check: omitting the form preserves the old behaviour."""
        html = (FIXTURE_DIR / "adi_2019_R2.htm").read_text()
        report = extract_concepts_from_report(html)  # no form
        revenue = _find_row(report, 'Revenue')
        assert revenue.primary_period == '3 Months Ended Nov. 02, 2019'


class TestADSK2019IncomeStatement:
    """Bug B — leading ``class="th"`` cell consumed a column position,
    shifting all values one slot. Verified against ADSK's R2.htm."""

    @pytest.fixture(scope='class')
    def report(self):
        html = (FIXTURE_DIR / "adsk_2019_R2.htm").read_text()
        return extract_concepts_from_report(html, form='10-K')

    def test_period_headers_are_three_annual_columns(self, report):
        assert report.period_headers == [
            '12 Months Ended Jan. 31, 2019',
            '12 Months Ended Jan. 31, 2018',
            '12 Months Ended Jan. 31, 2017',
        ]

    def test_net_revenue_fy2019_value_present(self, report):
        """FY2019 column got nothing pre-fix; FY2019 value ($2,569.8M)
        was bound to the FY2018 label key."""
        net_revenue = _find_row(report, 'Net revenue')
        assert net_revenue is not None
        nv = net_revenue.numeric_values
        assert nv.get('12 Months Ended Jan. 31, 2019') == 2569.8
        assert nv.get('12 Months Ended Jan. 31, 2018') == 2056.6
        assert nv.get('12 Months Ended Jan. 31, 2017') == 2031.0

    def test_net_revenue_primary_value(self, report):
        net_revenue = _find_row(report, 'Net revenue')
        assert net_revenue.numeric_value == 2569.8

    def test_no_value_dropped_from_three_column_row(self, report):
        """All three annual columns must have a value for a fully-populated
        row like Net revenue. Pre-fix, the FY2017 value was dropped."""
        net_revenue = _find_row(report, 'Net revenue')
        assert len(net_revenue.numeric_values) == 3
