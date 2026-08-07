"""
Regression test for GH #812: R*.htm header parser mislabels multi-row headers
when the leaf row mixes ``colspan=2`` date cells with ``colspan=1`` date +
``[1]`` footnote-marker pairs.

Original behavior (``edgar/sgml/concept_extractor.py``): the parser
flat-iterated ``<th class="th">`` cells in document order. Anything with
``colspan > 1`` went into ``group_headers`` regardless of whether it was a
true grouping header (``"3 Months Ended"``) or a leaf date with a wide
column (``"Nov. 02, 2019"`` cs=2). Footnote markers (``[1]``, ``[2]``)
parsed as their own period columns. Three failure modes compounded so that
for ADI's 2019 10-K Consolidated Statements of Income, all 13 emitted
period headers were prefixed ``"3 Months Ended"``, including the columns
that were actually ``"12 Months Ended"`` (FY19/FY18/FY17 annual).

The fix walks the header section row by row, builds a virtual grid that
honors both ``colspan`` and ``rowspan``, classifies cells as title /
group / leaf by where their rowspan reaches, and maps each non-footnote
leaf to its column-position range. Value extraction then matches data
cells to semantic columns by column position rather than by cell index,
which is the only way to align correctly when a row mixes colspan-1 and
colspan-2 cells (ADI's annual columns).

The network test pins the ADI 2019 10-K; the offline tests guard the
fix's contract with synthetic table HTML so the unit-level behavior
can't quietly regress when SEC R*.htm rendering shifts.
"""
from __future__ import annotations

import pytest

from edgar import Filing
from edgar.sgml.concept_extractor import extract_concepts_from_report


# ---------------------------------------------------------------------------
# Offline unit tests — guard the parser contract with synthetic HTML.
# Each test pins one variant of the header-shape variation surface.
# ---------------------------------------------------------------------------

class TestSingleRowHeader:
    """Simple comparative balance sheet — one header row, no group cells."""

    def test_two_instant_dates(self):
        html = """
        <table class="report">
          <tr>
            <th class="tl"><strong>Balance Sheet</strong></th>
            <th class="th"><div>Dec. 31, 2024</div></th>
            <th class="th"><div>Dec. 31, 2023</div></th>
          </tr>
          <tr class="re">
            <td class="pl"><a onclick="Show.showAR(this, 'defref_us-gaap_Assets', window)">Assets</a></td>
            <td class="nump">100</td>
            <td class="nump">90</td>
          </tr>
        </table>
        """
        r = extract_concepts_from_report(html)
        assert r.period_headers == ['Dec. 31, 2024', 'Dec. 31, 2023']
        row = r.rows[0]
        assert row.values == {'Dec. 31, 2024': '100', 'Dec. 31, 2023': '90'}
        assert row.primary_period == 'Dec. 31, 2024'
        assert row.numeric_value == 100.0


class TestGroupHeaderRow:
    """Typical annual income statement — group "12 Months Ended" over
    three date leaves (AAPL R3.htm shape)."""

    def test_group_prefix_applies_to_leaves(self):
        html = """
        <table class="report">
          <tr>
            <th class="tl" rowspan="2"><strong>Income Statement</strong></th>
            <th class="th" colspan="3"><div>12 Months Ended</div></th>
          </tr>
          <tr>
            <th class="th"><div>Sep. 27, 2025</div></th>
            <th class="th"><div>Sep. 28, 2024</div></th>
            <th class="th"><div>Sep. 30, 2023</div></th>
          </tr>
          <tr class="re">
            <td class="pl"><a onclick="Show.showAR(this, 'defref_us-gaap_Revenues', window)">Revenue</a></td>
            <td class="nump">390</td>
            <td class="nump">385</td>
            <td class="nump">383</td>
          </tr>
        </table>
        """
        r = extract_concepts_from_report(html)
        assert r.period_headers == [
            '12 Months Ended Sep. 27, 2025',
            '12 Months Ended Sep. 28, 2024',
            '12 Months Ended Sep. 30, 2023',
        ]
        row = r.rows[0]
        assert row.values == {
            '12 Months Ended Sep. 27, 2025': '390',
            '12 Months Ended Sep. 28, 2024': '385',
            '12 Months Ended Sep. 30, 2023': '383',
        }
        assert row.primary_period == '12 Months Ended Sep. 27, 2025'


class TestFootnoteMarkersDropped:
    """Date columns with ``[1]`` footnote-marker companion cells. The
    markers must NOT become their own period columns — they're typographic
    annotations on the date next to them."""

    def test_footnote_markers_filtered(self):
        html = """
        <table class="report">
          <tr>
            <th class="tl" rowspan="2"><strong>Income Statement</strong></th>
            <th class="th" colspan="4"><div>12 Months Ended</div></th>
          </tr>
          <tr>
            <th class="th"><div>Dec. 31, 2024</div></th>
            <th class="th"><div>[1]</div></th>
            <th class="th"><div>Dec. 31, 2023</div></th>
            <th class="th"><div>[1]</div></th>
          </tr>
          <tr class="re">
            <td class="pl"><a onclick="Show.showAR(this, 'defref_us-gaap_Revenues', window)">Revenue</a></td>
            <td class="nump">100</td>
            <td class="fn"></td>
            <td class="nump">90</td>
            <td class="fn"></td>
          </tr>
        </table>
        """
        r = extract_concepts_from_report(html)
        # Two semantic columns — the [1] markers don't get their own.
        assert r.period_headers == [
            '12 Months Ended Dec. 31, 2024',
            '12 Months Ended Dec. 31, 2023',
        ]
        row = r.rows[0]
        # Values still align: 100 with 2024, 90 with 2023.
        assert row.values == {
            '12 Months Ended Dec. 31, 2024': '100',
            '12 Months Ended Dec. 31, 2023': '90',
        }


class TestMultiGroupStackedHeader:
    """The ADI 2019 R2.htm shape, stripped to a minimal reproduction: a
    leaf row that mixes ``colspan=2`` date cells (no footnote sub-cell)
    with ``colspan=1`` date + ``[1]`` footnote-marker pairs, AND nests
    under two different groups (``3 Months Ended`` and
    ``12 Months Ended``). This is the case the original parser got wrong
    in three different ways."""

    HTML = """
    <table class="report">
      <tr>
        <th class="tl" rowspan="2"><strong>Income Statement</strong></th>
        <th class="th" colspan="4"><div>3 Months Ended</div></th>
        <th class="th" colspan="3"><div>12 Months Ended</div></th>
      </tr>
      <tr>
        <th class="th" colspan="2"><div>Nov. 02, 2019</div></th>
        <th class="th"><div>Nov. 03, 2018</div></th>
        <th class="th"><div>[1]</div></th>
        <th class="th"><div>Nov. 02, 2019</div></th>
        <th class="th"><div>Nov. 03, 2018</div></th>
        <th class="th"><div>[2]</div></th>
      </tr>
      <tr class="re">
        <td class="pl"><a onclick="Show.showAR(this, 'defref_us-gaap_Revenues', window)">Revenue</a></td>
        <td class="nump">1443</td>
        <td class="fn"></td>
        <td class="nump">1480</td>
        <td class="fn"></td>
        <td class="nump">5991</td>
        <td class="nump">6224</td>
        <td class="fn"></td>
      </tr>
    </table>
    """

    def test_period_headers_label_both_groups(self):
        r = extract_concepts_from_report(self.HTML)
        # 4 semantic columns: 2 quarterly + 2 annual.
        assert r.period_headers == [
            '3 Months Ended Nov. 02, 2019',
            '3 Months Ended Nov. 03, 2018',
            '12 Months Ended Nov. 02, 2019',
            '12 Months Ended Nov. 03, 2018',
        ]

    def test_values_align_to_semantic_columns(self):
        r = extract_concepts_from_report(self.HTML)
        row = r.rows[0]
        # The Q4 FY19 value (1443) sits at col 0 (cs=2 leaf above it);
        # the Q4 FY18 value (1480) sits at col 2 (cs=1 leaf + cs=1 [1]).
        # The annuals (5991, 6224) sit at cols 4 and 5.
        assert row.values == {
            '3 Months Ended Nov. 02, 2019': '1443',
            '3 Months Ended Nov. 03, 2018': '1480',
            '12 Months Ended Nov. 02, 2019': '5991',
            '12 Months Ended Nov. 03, 2018': '6224',
        }

    def test_primary_period_is_first_semantic_column(self):
        r = extract_concepts_from_report(self.HTML)
        row = r.rows[0]
        assert row.primary_period == '3 Months Ended Nov. 02, 2019'
        assert row.numeric_value == 1443.0


class TestSegmentDimensionalHeader:
    """Statement of Shareholders' Equity uses dimensional axis members as
    column headers, all in a single row (no group prefix). This must not
    regress when the parser is more grid-aware."""

    def test_dimensional_headers_passthrough(self):
        html = """
        <table class="report">
          <tr>
            <th class="tl"><strong>Statement of Equity</strong></th>
            <th class="th"><div>Total</div></th>
            <th class="th"><div>Common Stock</div></th>
            <th class="th"><div>Retained Earnings</div></th>
          </tr>
          <tr class="re">
            <td class="pl"><a onclick="Show.showAR(this, 'defref_us-gaap_StockholdersEquity', window)">Equity</a></td>
            <td class="nump">1000</td>
            <td class="nump">100</td>
            <td class="nump">900</td>
          </tr>
        </table>
        """
        r = extract_concepts_from_report(html)
        assert r.period_headers == ['Total', 'Common Stock', 'Retained Earnings']
        row = r.rows[0]
        assert row.values == {
            'Total': '1000',
            'Common Stock': '100',
            'Retained Earnings': '900',
        }


class TestWideAnnualValueCells:
    """ADI also uses ``colspan=2`` cells on the value row for annual
    columns (when the equivalent quarterly column had a date+footnote
    pair). Value extraction must use column position, not cell index, or
    these annuals will be mapped to the wrong semantic column."""

    def test_cs2_value_cells_align(self):
        html = """
        <table class="report">
          <tr>
            <th class="tl" rowspan="2"><strong>Income Statement</strong></th>
            <th class="th" colspan="3"><div>12 Months Ended</div></th>
          </tr>
          <tr>
            <th class="th"><div>Dec. 31, 2024</div></th>
            <th class="th"><div>Dec. 31, 2023</div></th>
            <th class="th"><div>Dec. 31, 2022</div></th>
          </tr>
          <tr class="re">
            <td class="pl"><a onclick="Show.showAR(this, 'defref_us-gaap_Revenues', window)">Revenue</a></td>
            <td class="nump" colspan="1">100</td>
            <td class="nump" colspan="1">90</td>
            <td class="nump" colspan="1">80</td>
          </tr>
        </table>
        """
        r = extract_concepts_from_report(html)
        row = r.rows[0]
        assert row.values == {
            '12 Months Ended Dec. 31, 2024': '100',
            '12 Months Ended Dec. 31, 2023': '90',
            '12 Months Ended Dec. 31, 2022': '80',
        }


# ---------------------------------------------------------------------------
# Pinned network regression — the reporter's exact filing
# ---------------------------------------------------------------------------

ADI_CIK = 6281
ADI_2019_ACC = "0000006281-19-000144"


@pytest.mark.network
class TestAdi2019IncomeStatement:
    """ADI's FY2019 10-K Consolidated Statements of Income (R2.htm). The
    table mixes 8 quarterly columns (with assorted footnote-marker
    layouts) and 3 annual columns under stacked ``3 Months Ended`` /
    ``12 Months Ended`` group headers."""

    @pytest.fixture(scope="class")
    def income_statement(self):
        filing = Filing(
            form="10-K", filing_date="2019-11-26",
            company="Analog Devices Inc.", cik=ADI_CIK,
            accession_no=ADI_2019_ACC,
        )
        return filing.viewer.financial_statements[0]

    def test_period_headers_have_both_3m_and_12m_groups(self, income_statement):
        headers = income_statement.concept_report.period_headers
        # 8 quarterly + 3 annual = 11 semantic columns.
        assert len(headers) == 11, (
            f"Expected 11 period headers (8 quarterly + 3 annual), got "
            f"{len(headers)}: {headers}"
        )
        assert any('12 Months Ended' in h for h in headers), (
            "Pre-fix bug: every header was prefixed '3 Months Ended'; "
            "the '12 Months Ended' group was never applied to its leaves."
        )
        # Three annual columns specifically.
        annual = [h for h in headers if h.startswith('12 Months Ended')]
        assert len(annual) == 3, f"Expected 3 annual columns, got {annual}"

    def test_fy19_annual_revenue_is_six_billion(self, income_statement):
        cr = income_statement.concept_report
        rev = next(
            (r for r in cr.rows
             if r.concept_id.endswith('RevenueFromContractWithCustomerExcludingAssessedTax')),
            None,
        )
        assert rev is not None, (
            "Revenue concept not found in ADI 2019 income statement"
        )
        # FY19 annual column — must report the 12M value (~$6.0B in
        # thousands), not a quarterly value (~$1.5B).
        fy19_key = '12 Months Ended Nov. 02, 2019'
        assert fy19_key in rev.values, (
            f"FY19 annual column key {fy19_key!r} missing from Revenue "
            f"values. Got: {list(rev.values)}"
        )
        # Display string is "$ 5,991,065" (in thousands → $5.99B).
        assert '5,991,065' in rev.values[fy19_key], (
            f"Expected FY19 revenue ≈ $5,991,065 (thousands), got "
            f"{rev.values[fy19_key]!r}"
        )

    def test_primary_period_is_q4_fy19_not_q4_fy18(self, income_statement):
        # Pre-fix, primary_period resolved to a Q4 FY18 column because
        # the cs=2 Q4 FY19 leaf cell was misclassified as a group header
        # and dropped from period_headers.
        cr = income_statement.concept_report
        assert cr.period_headers[0] == '3 Months Ended Nov. 02, 2019'
