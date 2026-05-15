"""
Regression test for GH #810: ``ConceptRow.numeric_value`` silently returns a
prior-year value when the primary reporting period has no fact for the row.

Original behavior: ``numeric_value`` returned ``parse_numeric(next(iter(
self.values.values())))`` — the first entry of the values dict, which is
populated only for periods that had a non-empty cell. For rows where the
primary period (the leftmost column of the report) had no value, this
silently returned the value for whichever period happened to be first in
the dict.

Reporter (mpreiss9) observed this on ABT 2019 10-K income statement,
``concept_rows[16]`` (``us-gaap_IncomeLossFromDiscontinuedOperationsNetOfTax``):
ABT had no 2019 fact for that concept, so ``numeric_value`` returned ``34.0``
(the 2018 value).

The fix tracks ``primary_period`` on ``ConceptRow`` (populated from
``period_headers[0]`` by the parser) and resolves ``numeric_value`` against
it explicitly, returning ``None`` when the primary period has no value.
"""
from __future__ import annotations

import pytest

from edgar import find
from edgar.sgml.concept_extractor import ConceptRow


# ---------------------------------------------------------------------------
# Unit tests (no network) — guard the contract
# ---------------------------------------------------------------------------

class TestNumericValueContract:

    def test_primary_period_present_returns_value(self):
        row = ConceptRow(
            concept_id='us-gaap_Revenues',
            label='Revenues',
            values={'FY2024': '100', 'FY2023': '90'},
            is_abstract=False, is_total=False, is_header=False,
            level=0, css_class='re',
            primary_period='FY2024',
        )
        assert row.numeric_value == 100.0

    def test_primary_period_missing_returns_none(self):
        # The bug case: primary period has no value, but later periods do.
        row = ConceptRow(
            concept_id='us-gaap_IncomeLossFromDiscontinuedOperationsNetOfTax',
            label='Discontinued ops',
            values={'FY2023': '34', 'FY2022': '124'},  # FY2024 absent
            is_abstract=False, is_total=False, is_header=False,
            level=0, css_class='re',
            primary_period='FY2024',
        )
        assert row.numeric_value is None, (
            "numeric_value must return None when the primary period has no "
            "value, not silently fall back to a prior period"
        )

    def test_numeric_values_dict_unaffected(self):
        # The full period→value map keeps returning everything available.
        row = ConceptRow(
            concept_id='us-gaap_IncomeLossFromDiscontinuedOperationsNetOfTax',
            label='Discontinued ops',
            values={'FY2023': '34', 'FY2022': '124'},
            is_abstract=False, is_total=False, is_header=False,
            level=0, css_class='re',
            primary_period='FY2024',
        )
        assert row.numeric_values == {'FY2023': 34.0, 'FY2022': 124.0}

    def test_no_primary_period_returns_none(self):
        # Hand-built rows without primary_period get None (not legacy
        # "first dict entry") to guarantee the bug cannot recur via that path.
        row = ConceptRow(
            concept_id='us-gaap_Revenues',
            label='Revenues',
            values={'FY2024': '100'},
            is_abstract=False, is_total=False, is_header=False,
            level=0, css_class='re',
        )
        assert row.primary_period is None
        assert row.numeric_value is None

    def test_empty_values_returns_none(self):
        row = ConceptRow(
            concept_id='us-gaap_Abstract',
            label='Header',
            values={},
            is_abstract=True, is_total=False, is_header=False,
            level=0, css_class='re',
            primary_period='FY2024',
        )
        assert row.numeric_value is None


class TestParserPlumbsPrimaryPeriod:
    """The R*.htm parser must populate ``ConceptRow.primary_period`` from
    ``period_headers[0]`` for every row it emits. Without this the bug
    recurs through the normal viewer path."""

    def test_parser_sets_primary_period(self):
        from edgar.sgml.concept_extractor import extract_concepts_from_report

        # Minimal synthetic R*.htm-shaped table: two periods, one row with
        # the primary period empty (the GH #810 shape).
        html = """
        <html><body><table class="report">
          <tr>
            <th class="tl"><strong>Synthetic Statement</strong></th>
            <th class="th"><div>FY2024</div></th>
            <th class="th"><div>FY2023</div></th>
          </tr>
          <tr class="re">
            <td class="pl"><a onclick="Show.showAR(this, 'defref_us-gaap_DiscontinuedOps', window)">Discontinued ops</a></td>
            <td class="text"></td>
            <td class="nump">$ 34</td>
          </tr>
        </table></body></html>
        """
        report = extract_concepts_from_report(html)
        assert report.period_headers == ['FY2024', 'FY2023']
        assert len(report.rows) == 1
        row = report.rows[0]
        assert row.primary_period == 'FY2024'
        assert row.numeric_value is None  # FY2024 cell was empty
        assert row.numeric_values == {'FY2023': 34.0}


# ---------------------------------------------------------------------------
# Pinned network regression — the reporter's exact filing
# ---------------------------------------------------------------------------

ABT_2019_10K = '0001104659-20-023904'


@pytest.mark.network
class TestAbt2019IncomeStatement:
    """ABT 2019 10-K Consolidated Statement of Earnings.

    Concept at concept_rows[16] is
    ``us-gaap_IncomeLossFromDiscontinuedOperationsNetOfTax``. ABT had no
    2019 fact for this concept; the row's values dict only contains 2018
    ($34M) and 2017 ($124M). The continuing-operations row at index 15 is
    the inverse control: it has all three years and the 2019 value is
    $3,687M.
    """

    @pytest.fixture(scope='class')
    def income_statement(self):
        filing = find(ABT_2019_10K)
        viewer = filing.viewer
        return viewer.financial_statements[0]

    def test_period_headers_have_2019_first(self, income_statement):
        # Sanity-check the report structure the bug depends on.
        assert income_statement.period_headers[0] == '12 Months Ended Dec. 31, 2019'

    def test_row_16_is_discontinued_operations(self, income_statement):
        row = income_statement.concept_rows[16]
        assert row.concept_id == 'us-gaap_IncomeLossFromDiscontinuedOperationsNetOfTax'

    def test_row_16_numeric_value_is_none_not_2018_value(self, income_statement):
        # GH #810 regression: must NOT return 34.0 (the 2018 value).
        row = income_statement.concept_rows[16]
        assert row.numeric_value is None, (
            f"concept_rows[16].numeric_value returned {row.numeric_value}; "
            f"expected None because the primary period "
            f"({income_statement.period_headers[0]}) has no fact for "
            f"discontinued operations on ABT 2019. The 2018 fallback "
            f"(34.0) was the original GH #810 bug."
        )

    def test_row_16_numeric_values_dict_still_has_prior_years(self, income_statement):
        # The full period→value map must continue to expose the 2018 and 2017
        # values so callers can opt in to multi-year reads.
        row = income_statement.concept_rows[16]
        nv = row.numeric_values
        assert nv.get('12 Months Ended Dec. 31, 2018') == 34.0
        assert nv.get('12 Months Ended Dec. 31, 2017') == 124.0
        assert '12 Months Ended Dec. 31, 2019' not in nv

    def test_row_15_continuing_operations_returns_2019_value(self, income_statement):
        # Control: the adjacent row has all three years; numeric_value must
        # return the 2019 (primary period) value, not 2018.
        row = income_statement.concept_rows[15]
        assert row.concept_id == (
            'us-gaap_IncomeLossFromContinuingOperationsIncludingPortionAttributableToNoncontrollingInterest'
        )
        assert row.numeric_value == 3687.0
