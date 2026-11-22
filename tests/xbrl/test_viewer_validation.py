"""
Tests for cross-validation between SEC Viewer and XBRL parser.

Unit tests use fixture data and mock XBRL objects.
"""
import copy
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from edgar.sgml.concept_extractor import extract_concepts_from_report
from edgar.sgml.filing_summary import Report
from edgar.sgml.metalinks import MetaLinks
from edgar.xbrl.viewer import FilingViewer, ViewerReport
from edgar.xbrl.viewer_validation import (
    MATCHED,
    MISMATCHED,
    MISSING,
    NOT_COMPARABLE,
    ComparisonResult,
    ComparisonResults,
    _match_xbrl_period,
    _normalize_concept_id,
    _parse_viewer_period,
    compare_viewer_to_xbrl,
)
from tests.paths import FIXTURES_DIR


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


# ---------------------------------------------------------------------------
# Harness fidelity on real filings (offline). Fixtures are trimmed verbatim
# R*.htm pages, the filing's facts for the concepts on them, and its
# MetaLinks entries: see tests/fixtures/viewer-harness/README.md.
# ---------------------------------------------------------------------------


HARNESS_DIR = FIXTURES_DIR / "viewer-harness"

SPIRIT = "0001628280-20-002543"
IREN = "0001878848-25-000063"
QUOIN = "0001410578-23-001531"
AZURE = "0001174947-24-000443"
CHINDATA = "0001564590-22-016827"
COMSTOCK = "0001299969-24-000010"
BHE = "0001081316-24-000016"
SELECTQUOTE = "0001794783-26-000012"
TRILOGY = "0001558370-20-011395"
BRIXMOR = "0001581068-21-000012"
DIAMONDROCK = "0001298946-24-000052"
GRANITESHARES = "0001493152-26-037707"
GRAYSCALE_XLM = "0000950170-23-065631"
ZSCALER = "0001713683-20-000163"
CASH_RC = 'us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents'


def _facts(accession):
    return json.loads((HARNESS_DIR / accession / "facts.json").read_text())


class _FixtureQuery:
    def __init__(self, facts):
        self._facts = facts
        self._concept = None

    def by_concept(self, concept, exact=False):
        self._concept = concept.replace('_', ':', 1)
        return self

    def execute(self):
        return [f for f in self._facts if f['concept'] == self._concept]


class _FixtureFacts:
    def __init__(self, facts):
        self._facts = facts

    def to_dataframe(self):
        return pd.DataFrame(self._facts)

    def query(self):
        return _FixtureQuery(self._facts)


class _FixtureXBRL:
    """The parts of XBRL the viewer and the harness read, from fixture facts."""

    def __init__(self, facts, metalinks, presentation=None, namespaces=None, labels=None, dimensions=None):
        self.facts = _FixtureFacts(facts)
        self.element_catalog = {eid: SimpleNamespace(labels=dict(by_role)) for eid, by_role in (labels or {}).items()}
        dimensions = dimensions or {}
        self._role_axes = {role: {eid: SimpleNamespace(**a) for eid, a in axes.items()}
                           for role, axes in dimensions.items() if role != 'merged'}
        self.axes = {eid: SimpleNamespace(**a) for eid, a in dimensions.get('merged', {}).items()}
        self.contexts = {f['context_ref']: SimpleNamespace(dimensions=f['dimensions']) for f in facts}
        namespaces = namespaces or {}
        self.parser = SimpleNamespace(namespace_prefixes=dict(namespaces.get('namespace_prefixes', {})),
                                      typed_dimensions=set(namespaces.get('typed_dimensions', [])))
        presentation = presentation or {}
        self.presentation_trees = {}
        for r in metalinks.reports.values():
            tree = presentation.get(r.role, {})
            arcs = tree.get('nodes', {})
            nodes = {tag_id: SimpleNamespace(depth=0, children=[], child_preferred_labels=[])
                     for tag_id in metalinks.tags}
            for eid, node in arcs.items():
                nodes[eid] = SimpleNamespace(depth=0, children=node['children'],
                                             child_preferred_labels=node['child_preferred_labels'])
            # The role's network as filed, when the fixture records it (as live trees carry it).
            relationships = [SimpleNamespace(parent_id=parent, child_id=child, order=order, preferred_label=label)
                             for parent, child, order, label in tree.get('relationships', [])]
            self.presentation_trees[r.role] = SimpleNamespace(
                all_nodes=nodes, root_element_ids=tree.get('roots', []), root_element_id=None,
                relationships=relationships)

    def axes_for_role(self, role):
        return self._role_axes.get(role, {})


def _presentation(accession):
    path = HARNESS_DIR / accession / "presentation.json"
    return json.loads(path.read_text()) if path.exists() else {}


def _rewrite_arc_roles(presentation, rewrite):
    """Apply ``rewrite(child, role) -> role`` to every arc, in the tree nodes and in the recorded network."""
    for tree in presentation.values():
        for node in tree['nodes'].values():
            node['child_preferred_labels'] = [rewrite(child, role) for child, role in
                                              zip(node['children'], node['child_preferred_labels'], strict=True)]
        for rel in tree.get('relationships', []):
            rel[3] = rewrite(rel[1], rel[3])
    return presentation


def _fixture_json(accession, name):
    path = HARNESS_DIR / accession / name
    return json.loads(path.read_text()) if path.exists() else {}


def _namespaces(accession):
    path = HARNESS_DIR / accession / "namespaces.json"
    return json.loads(path.read_text()) if path.exists() else {}


def _fixture_viewer(accession, facts=None, presentation=None, namespaces=None, pages=None):
    """A FilingViewer over the fixture pages, with XBRL wired in.

    XBRL is attached so that any decimals-based scale inference runs on the
    filing's real decimals, as it does for ``filing.viewer``. ``pages``
    replaces the content of named pages.
    """
    d = HARNESS_DIR / accession
    metalinks = MetaLinks.parse((d / "MetaLinks.json").read_text())
    sgml = MagicMock()
    pages = pages or {}
    sgml.get_content = lambda name: pages[name] if name in pages else (
        (d / name).read_text() if (d / name).exists() else None)
    reports = []
    for rkey, meta in sorted(metalinks.reports.items(), key=lambda kv: kv[1].order):
        report = Report(instance=None, is_default=False, has_embedded_reports=False,
                        html_file_name=f"{rkey}.htm", long_name=meta.long_name, report_type=None,
                        role=meta.role, parent_role=None, short_name=meta.short_name,
                        menu_category=meta.menu_cat, position=str(meta.order), reports=None)
        report._reports = MagicMock()
        report._reports._filing_summary._filing_sgml = sgml
        reports.append(report)
    filing_summary = MagicMock()
    filing_summary.reports = reports
    viewer = FilingViewer(sgml, filing_summary, metalinks)
    xbrl = _FixtureXBRL(_facts(accession) if facts is None else facts, metalinks,
                        _presentation(accession) if presentation is None else presentation,
                        _namespaces(accession) if namespaces is None else namespaces,
                        _fixture_json(accession, "labels.json"), _fixture_json(accession, "dimensions.json"))
    viewer._xbrl = xbrl
    viewer._xbrl_loaded = True
    return viewer, xbrl


def _compare(accession, facts=None, presentation=None, namespaces=None):
    viewer, xbrl = _fixture_viewer(accession, facts, presentation, namespaces)
    return compare_viewer_to_xbrl(viewer, xbrl)


def _cells(results, concept, period=None, report=None):
    return [r for r in results.results
            if r.concept_id == concept
            and (period is None or r.period == period)
            and (report is None or report in r.report)]


def _cell(results, concept, period, label=None, report=None):
    cells = [r for r in _cells(results, concept, period, report) if label is None or r.label == label]
    assert len(cells) == 1, f"expected one {concept} cell at {period!r}, got {cells}"
    return cells[0]


def _statement(viewer, name):
    return next(vr for vr in viewer.financial_statements if name in vr.short_name)


class TestDisplayScaleIsThePageDeclaredScale:
    """Defect 1: the display scale was inferred from XBRL decimals."""

    def test_spirit_page_in_millions_with_decimals_minus_5(self):
        # R2.htm: "Consolidated Statements of Operations - USD ($) $ in Millions",
        # net revenues "$ 1,959.3" for the quarter ended Dec. 31, 2019; the fact
        # us-gaap:Revenues duration_2019-09-27_2019-12-31 is 1,959,300,000 at decimals=-5.
        viewer, _ = _fixture_viewer(SPIRIT)
        assert _statement(viewer, "Operations").currency_scaling == 1_000_000
        cell = _cell(_compare(SPIRIT), 'us-gaap:Revenues', '3 Months Ended Dec. 31, 2019')
        assert (cell.status, cell.viewer_value, cell.xbrl_value) == (MATCHED, 1959.3, 1959.3)

    def test_iren_scale_differs_per_statement(self):
        # R3.htm is "$ in Thousands"; R5.htm says only "USD ($)" and shows total
        # revenue "$ 501,023,000" in whole dollars, though the fact
        # (duration_2024-07-01_2025-06-30 = 501,023,000) is at decimals=-3.
        viewer, _ = _fixture_viewer(IREN)
        assert _statement(viewer, "Balance Sheets").currency_scaling == 1_000
        assert _statement(viewer, "Operations").currency_scaling == 1
        # The total, then the two product/service members below it.
        cells = _cells(_compare(IREN), 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
                       '12 Months Ended Jun. 30, 2025')
        assert [(c.status, c.xbrl_value) for c in cells] == [
            (MATCHED, 501_023_000), (MATCHED, 484_629_000), (MATCHED, 16_394_000)]

    def test_quoin_page_in_whole_dollars(self):
        # R2.htm: "USD ($)" with no scale statement; cash "$ 4,759,129" at Jun. 30, 2023.
        viewer, _ = _fixture_viewer(QUOIN)
        assert _statement(viewer, "Balance Sheets").currency_scaling == 1
        cell = _cell(_compare(QUOIN), 'us-gaap:CashAndCashEquivalentsAtCarryingValue', 'Jun. 30, 2023')
        assert (cell.status, cell.xbrl_value) == (MATCHED, 4_759_129)

    def test_declared_scale_is_not_replaced_by_decimals_inference(self):
        html = (HARNESS_DIR / SPIRIT / "R2.htm").read_text()
        cr = extract_concepts_from_report(html)
        viewer = MagicMock()
        viewer._resolve_currency_scaling.return_value = 1_000
        report = Report(instance=None, is_default=False, has_embedded_reports=False,
                        html_file_name="R2.htm", long_name='', report_type=None, role='r',
                        parent_role=None, short_name='Ops', menu_category='Statements',
                        position='2', reports=None)
        assert ViewerReport(report, None, cr, viewer=viewer).currency_scaling == 1_000_000
        viewer._resolve_currency_scaling.assert_not_called()

    def test_scale_statements_per_currency(self):
        cr = extract_concepts_from_report((HARNESS_DIR / AZURE / "R2.htm").read_text())
        assert cr.header_found
        assert cr.unit_scales == {'₨': 1_000_000, '$': 1_000_000}
        assert cr.column_units == ['INR (₨)', 'USD ($)', 'INR (₨)']
        assert cr.currency_scaling == 1_000_000

    def test_whole_unit_page_declares_no_scale(self):
        cr = extract_concepts_from_report((HARNESS_DIR / QUOIN / "R2.htm").read_text())
        assert (cr.header_found, cr.header_unit, cr.unit_scales, cr.currency_scaling) == (
            True, 'USD ($)', {}, 1)


    def test_title_word_ending_in_capitals_is_not_a_unit(self):
        # Accenture 0001467373-26-000049 R3.htm is titled
        # "CONSOLIDATED BALANCE SHEETS (Parenthetical)": "ETS (Parenthetical)" is not a unit.
        html = ('<table class="report"><tr><th class="tl"><strong>CONSOLIDATED BALANCE SHEETS '
                '(Parenthetical)<br></strong></th><th class="th"><div>Aug. 31, 2026</div></th></tr></table>')
        cr = extract_concepts_from_report(html)
        assert (cr.header_found, cr.header_unit, cr.currency_scaling) == (True, None, 1)


class TestOpeningAndClosingBalances:
    """Defect 2: an instant concept in a duration column was looked up as a duration."""

    def test_azure_opening_and_closing_cash(self):
        # R7.htm, "12 Months Ended Mar. 31, 2023" (duration_2022-04-01_2023-03-31):
        # beginning cash ₨ 23,306 = instant 2022-03-31 23,306,000,000 INR;
        # ending cash ₨ 20,967 = instant 2023-03-31 20,967,000,000 INR.
        results = _compare(AZURE)
        concept = 'us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents'
        opening = _cell(results, concept, '12 Months Ended Mar. 31, 2023',
                        label='Cash and cash equivalents and restricted cash at the beginning of the period')
        closing = _cell(results, concept, '12 Months Ended Mar. 31, 2023',
                        label='Cash and cash equivalents and restricted cash at the end of the period')
        assert (opening.status, opening.viewer_value, opening.xbrl_value) == (MATCHED, 23306, 23306)
        assert (closing.status, closing.viewer_value, closing.xbrl_value) == (MATCHED, 20967, 20967)

    def test_azure_usd_convenience_column_opening_balance(self):
        # The USD column of the same period: opening $ 283.6 = instant 2022-03-31
        # 283,600,000 USD (decimals=-5).
        results = _compare(AZURE)
        cell = _cell(results, 'us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
                     '12 Months Ended Mar. 31, 2023 (1)',
                     label='Cash and cash equivalents and restricted cash at the beginning of the period')
        assert (cell.status, cell.xbrl_value) == (MATCHED, 283.6)

    def test_every_opening_and_closing_cell_is_compared(self):
        results = _compare(AZURE)
        cells = _cells(results, 'us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents')
        assert len(cells) == 8  # 4 columns x (opening, closing)
        assert {c.status for c in cells} == {MATCHED}


class TestMemberContext:
    """Defect 3: rows under a member header were looked up without dimensions."""

    def test_chindata_shares_by_class(self):
        # R3.htm: "Class A Ordinary Shares" header, shares authorized 4,500,000,000;
        # "Class B Ordinary Shares", 500,000,000 (us-gaap:StatementClassOfStockAxis).
        results = _compare(CHINDATA)
        authorized = [c for c in _cells(results, 'us-gaap:CommonStockSharesAuthorized', 'Dec. 31, 2021')]
        assert [(c.status, c.xbrl_value) for c in authorized] == [
            (MATCHED, 4_500_000_000), (MATCHED, 500_000_000)]

    def test_chindata_two_member_header_is_not_comparable(self):
        # "VIEs | Nonrecourse" names only the VIE member by QName; the facts sit
        # under VIE x Nonrecourse, which the page gives by label only.
        results = _compare(CHINDATA)
        cells = _cells(results, 'us-gaap:LiabilitiesCurrent', 'Dec. 31, 2021')
        assert [c.status for c in cells] == [MATCHED, MATCHED, NOT_COMPARABLE]
        assert 'VIEs | Nonrecourse' in cells[2].reason
        assert results.not_comparable == 3

    def test_comstock_common_stock_value_by_class(self):
        # R3.htm ($ in Thousands): Class A common stock 94 = 94,000; Class B $ 2 = 2,000.
        results = _compare(COMSTOCK)
        cells = _cells(results, 'us-gaap:CommonStockValue', 'Dec. 31, 2023')
        assert [(c.status, c.xbrl_value) for c in cells] == [(MATCHED, 94), (MATCHED, 2)]

    def test_bhe_combined_filing_rows_per_registrant(self):
        # R4.htm ($ in Millions): consolidated cash $ 3,265, then under the
        # PacifiCorp member header 1,289, at Jun. 30, 2024.
        results = _compare(BHE)
        cells = _cells(results, 'us-gaap:CashAndCashEquivalentsAtCarryingValue', 'Jun. 30, 2024')
        assert [(c.status, c.xbrl_value) for c in cells] == [(MATCHED, 3265), (MATCHED, 1289)]


class TestUnitsAndDuplicates:
    """Defect 4: one value per (concept, period), unit-blind, last fact wins."""

    def test_azure_each_currency_column_reads_its_own_unit(self):
        # AssetsCurrent at Mar. 31, 2023: INR 27,851,000,000 and USD 339,000,000.
        results = _compare(AZURE)
        inr = _cell(results, 'us-gaap:AssetsCurrent', 'Mar. 31, 2023')
        usd = _cell(results, 'us-gaap:AssetsCurrent', 'Mar. 31, 2023 (2)')
        assert (inr.status, inr.xbrl_value) == (MATCHED, 27851)
        assert (usd.status, usd.xbrl_value) == (MATCHED, 339)

    def test_azure_rupee_prefixed_values_are_parsed(self):
        results = _compare(AZURE)
        cell = _cell(results, 'us-gaap:CashAndCashEquivalentsAtCarryingValue', 'Mar. 31, 2023')
        assert (cell.viewer_value, cell.status) == (12724, MATCHED)

    def test_selectquote_goodwill_most_precise_duplicate(self):
        # Goodwill at Dec. 31, 2025 is filed as 29,438,000 (decimals=-3) and
        # 29,400,000 (decimals=-5); the page shows 29,438.
        cell = _cell(_compare(SELECTQUOTE), 'us-gaap:Goodwill', 'Dec. 31, 2025')
        assert (cell.status, cell.xbrl_value) == (MATCHED, 29438)

    def test_inconsistent_duplicates_compare_the_chosen_fact_with_a_note(self):
        # The decimals=-5 duplicate is moved to 29,000,000, which disagrees
        # with 29,438,000 beyond its own precision. The cell is still compared,
        # against the fact statements use (the decimals=-3 one), and the
        # disagreement is carried as a note rather than as an outcome.
        facts = _facts(SELECTQUOTE)
        for f in facts:
            if f['period_key'] == 'instant_2025-12-31' and f['decimals'] == '-5':
                f['value'] = '29000000'
                f['numeric_value'] = 29_000_000.0
        cell = _cell(_compare(SELECTQUOTE, facts), 'us-gaap:Goodwill', 'Dec. 31, 2025')
        assert (cell.status, cell.xbrl_value, cell.reason) == (MATCHED, 29438, None)
        assert 'disagree' in cell.note and '29438000' in cell.note


class TestHarnessStillCatchesErrors:
    """The fixes must make the comparison more exact, never more lenient."""

    def test_wrong_value_is_a_mismatch(self):
        facts = _facts(SELECTQUOTE)
        for f in facts:
            f['numeric_value'] += 100_000.0
        cell = _cell(_compare(SELECTQUOTE, facts), 'us-gaap:Goodwill', 'Dec. 31, 2025')
        assert (cell.status, cell.xbrl_value) == (MISMATCHED, 29538)

    def test_wrong_unit_is_a_mismatch(self):
        # The INR amount reported under the USD unit: the USD column must not
        # match it, and the INR column must not borrow it.
        facts = [f for f in _facts(AZURE)
                 if not (f['concept'] == 'us-gaap:AssetsCurrent'
                         and f['period_key'] == 'instant_2023-03-31' and f['currency'] == 'INR')]
        for f in facts:
            if f['concept'] == 'us-gaap:AssetsCurrent' and f['period_key'] == 'instant_2023-03-31':
                f['numeric_value'] = 27_851_000_000.0
        results = _compare(AZURE, facts)
        assert _cell(results, 'us-gaap:AssetsCurrent', 'Mar. 31, 2023 (2)').status == MISMATCHED
        assert _cell(results, 'us-gaap:AssetsCurrent', 'Mar. 31, 2023').status == MISSING

    def test_thousandfold_scale_error_is_a_mismatch(self):
        facts = copy.deepcopy(_facts(SPIRIT))
        for f in facts:
            if f['concept'] == 'us-gaap:Revenues':
                f['numeric_value'] *= 1000
        cell = _cell(_compare(SPIRIT, facts), 'us-gaap:Revenues', '3 Months Ended Dec. 31, 2019')
        assert cell.status == MISMATCHED

    def test_swapped_opening_and_closing_balances_are_mismatches(self):
        facts = _facts(AZURE)
        concept = 'us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents'
        by_key = {(f['period_key'], f['currency']): f for f in facts if f['concept'] == concept}
        opening, closing = by_key[('instant_2022-03-31', 'INR')], by_key[('instant_2023-03-31', 'INR')]
        opening['numeric_value'], closing['numeric_value'] = closing['numeric_value'], opening['numeric_value']
        results = _compare(AZURE, facts)
        for label in ('Cash and cash equivalents and restricted cash at the beginning of the period',
                      'Cash and cash equivalents and restricted cash at the end of the period'):
            cell = _cell(results, concept, '12 Months Ended Mar. 31, 2023', label=label)
            assert cell.status == MISMATCHED, label

    def test_dimensioned_fact_never_stands_in_for_a_plain_row(self):
        # Drop the consolidated (no-dimension) fact: the consolidated row must be
        # missing, not matched to a registrant's fact.
        facts = [f for f in _facts(BHE) if not (f['period_key'] == 'instant_2024-06-30' and not f['dimensions'])]
        cells = _cells(_compare(BHE, facts), 'us-gaap:CashAndCashEquivalentsAtCarryingValue', 'Jun. 30, 2024')
        assert [c.status for c in cells] == [MISSING, MATCHED]

    def test_superset_dimensions_do_not_match_a_member_row(self):
        # Without the Class A fact, the Parent-company x Class A fact (same value)
        # must not stand in for it.
        facts = [f for f in _facts(CHINDATA)
                 if f['dimensions'] != {'us-gaap:StatementClassOfStockAxis': 'us-gaap:CommonClassAMember'}]
        cells = _cells(_compare(CHINDATA, facts), 'us-gaap:CommonStockSharesAuthorized', 'Dec. 31, 2021')
        assert [c.status for c in cells] == [NOT_COMPARABLE, MATCHED]
        assert cells[0].xbrl_value is None


class TestOutcomeCounting:

    def test_not_comparable_is_counted_separately(self):
        cr = ComparisonResults(results=[
            ComparisonResult('a', 'A', 'p1', 100, 100, 0, True, 'R'),
            ComparisonResult('b', 'B', 'p1', 200, 205, -5, False, 'R'),
            ComparisonResult('c', 'C', 'p1', 300, None, None, False, 'R'),
            ComparisonResult('d', 'D', 'p1', 400, None, None, False, 'R',
                             status=NOT_COMPARABLE, reason='why'),
        ])
        assert (cr.matched, cr.mismatched, cr.missing, cr.not_comparable) == (1, 1, 1, 1)
        assert cr.match_rate == 0.5
        df = cr.to_dataframe()
        assert list(df.status) == [MATCHED, MISMATCHED, MISSING, NOT_COMPARABLE]
        assert 'not_comparable=1' in str(cr)


class TestEveryNumericCellIsCounted:
    """Round 2, item 2: cells that were skipped now end in a counted outcome."""

    def test_equity_member_column_cells_are_counted_with_a_reason(self):
        # Spirit R7.htm (trimmed: no labels or axes to resolve its columns):
        # net income 354,900,000 / 617,000,000.0 / 530,100,000 sits in the
        # Total and Stockholders' Equity, Total [Member] columns.
        results = _compare(SPIRIT)
        cells = _cells(results, 'us-gaap:NetIncomeLoss', report='Changes in Shareholders Equity')
        assert [(c.period, c.viewer_value) for c in cells] == [
            ('Total', 354_900_000), ("Stockholders' Equity, Total [Member]", 354_900_000),
            ('Total', 617_000_000), ("Stockholders' Equity, Total [Member]", 617_000_000),
            ('Total', 530_100_000), ("Stockholders' Equity, Total [Member]", 530_100_000)]
        assert {c.status for c in cells} == {NOT_COMPARABLE}
        assert all(c.reason for c in cells)
        # The trimmed fixture keeps no labels or axis defaults, so neither heading resolves.
        assert [c.reason for c in cells[:2]] == [
            "column heading 'Total' does not name a member of us-gaap_StatementEquityComponentsAxis, "
            "which has no default member",
            "column heading \"Stockholders' Equity, Total [Member]\": \"Stockholders' Equity, Total [Member]\" "
            "is not the label of any member on the statement's column axes"]
        assert [c.reason for c in cells[2:]] == [c.reason for c in cells[:2]] * 2

    def test_coverage_is_compared_over_all_numeric_cells(self):
        # 25 compared cells; 6 net-income cells in member columns and the 4
        # "Balance, shares at ..." (rc) cells of R7.htm are counted too.
        results = _compare(SPIRIT)
        compared = results.matched + results.mismatched
        assert (compared, results.total) == (25, 35)
        assert results.coverage == pytest.approx(25 / 35)
        assert 'coverage=71.4%' in str(results)

    def test_unreadable_numeric_cell_is_not_comparable(self):
        # Quoin R2.htm shows cash "$ 4,759,129"; the same cell made unreadable
        # must be counted, not dropped.
        viewer, xbrl = _fixture_viewer(QUOIN)
        report = _statement(viewer, "Balance Sheets")
        for row in report.concept_report.rows:
            if row.concept_id == 'us-gaap_CashAndCashEquivalentsAtCarryingValue':
                row.values['Jun. 30, 2023'] = 'n/a'  # noqa: PD011 (ConceptRow.values is a dict)
        cell = _cell(compare_viewer_to_xbrl(viewer, xbrl),
                     'us-gaap:CashAndCashEquivalentsAtCarryingValue', 'Jun. 30, 2023')
        assert (cell.status, cell.viewer_value) == (NOT_COMPARABLE, None)
        assert "'n/a'" in cell.reason

    @pytest.mark.parametrize('display, expected', [
        ('R$ 10', 10.0), ('US$ 5', 5.0), ('CHF 10', 10.0), ('(CHF 1,234)', -1234.0),
        ('HK$ 3.5', 3.5), ('$ 95,359', 95359.0), ('₨ 12,724', 12724.0), ('No 5', None), ('n/a', None)])
    def test_letter_currency_prefixes_are_read(self, display, expected):
        from edgar.sgml.concept_extractor import parse_numeric
        assert parse_numeric(display) == expected


class TestToleranceIsTheDisplayedPrecision:
    """Round 2, item 3: half a unit in the last displayed digit, not a flat 1.0."""

    def test_sub_unit_per_share_error_is_a_mismatch(self):
        # Spirit R2.htm: basic EPS "$ 0.65" for the quarter ended Dec. 31, 2019
        # (fact 0.65). A fact of 0.70 is off by 0.05, which a flat 1.0 hid.
        facts = _facts(SPIRIT)
        for f in facts:
            if f['concept'] == 'us-gaap:EarningsPerShareBasic' and f['numeric_value'] == 0.65:
                f['numeric_value'] = 0.70
        cell = _cell(_compare(SPIRIT, facts), 'us-gaap:EarningsPerShareBasic', '3 Months Ended Dec. 31, 2019')
        assert (cell.status, cell.viewer_value, cell.xbrl_value) == (MISMATCHED, 0.65, 0.70)

    def test_sub_unit_percent_error_is_a_mismatch(self):
        # GraniteShares R8.htm: total return "22.27%" = 0.2227. A fact of
        # 0.2257 shows as 22.57, off by 0.3.
        facts = _facts(GRANITESHARES)
        for f in facts:
            if f['concept'] == 'us-gaap:InvestmentCompanyTotalReturn' and f['numeric_value'] == 0.2227:
                f['numeric_value'] = 0.2257
        cell = _cell(_compare(GRANITESHARES, facts), 'us-gaap:InvestmentCompanyTotalReturn',
                     '12 Months Ended Jun. 30, 2026')
        assert cell.status == MISMATCHED
        assert cell.xbrl_value == pytest.approx(22.57)

    def test_rounding_within_the_last_displayed_digit_matches(self):
        # Spirit revenue 1,959,300,000 shown "$ 1,959.3" in millions; a fact of
        # 1,959,340,000 still rounds to 1,959.3.
        facts = _facts(SPIRIT)
        for f in facts:
            if f['concept'] == 'us-gaap:Revenues' and f['period_key'] == 'duration_2019-09-27_2019-12-31':
                f['numeric_value'] = 1_959_340_000.0
        cell = _cell(_compare(SPIRIT, facts), 'us-gaap:Revenues', '3 Months Ended Dec. 31, 2019')
        assert cell.status == MATCHED


class TestColumnPeriodIsPerConcept:
    """Round 2, item 4: one stray fact must not decide the period of a whole column."""

    def test_trilogy_nine_months_with_a_stray_duration(self):
        # Trilogy R6.htm "9 Months Ended Aug. 31, 2020": net income
        # "$ 164,993,000" = duration_2019-12-01_2020-08-31. Three other facts are
        # dated 2019-12-02 to 2020-08-31; they used to take the column over.
        results = _compare(TRILOGY)
        cell = _cell(results, 'us-gaap:NetIncomeLoss', '9 Months Ended Aug. 31, 2020')
        assert (cell.status, cell.xbrl_value) == (MATCHED, 164_993_000)
        # The opening balance is the instant before the column's period: 2019-11-30.
        opening = _cell(results, 'us-gaap:CashAndCashEquivalentsAtCarryingValue', '9 Months Ended Aug. 31, 2020',
                        label='Cash and cash equivalents - beginning of period')
        assert (opening.status, opening.xbrl_value) == (MATCHED, 19_174_000)

    def test_stray_duration_does_not_hide_a_wrong_value(self):
        facts = _facts(TRILOGY)
        for f in facts:
            if (f['concept'] == 'us-gaap:NetIncomeLoss' and not f['dimensions']
                    and f['period_key'] == 'duration_2019-12-01_2020-08-31'):
                f['numeric_value'] = 165_993_000.0
        cell = _cell(_compare(TRILOGY, facts), 'us-gaap:NetIncomeLoss', '9 Months Ended Aug. 31, 2020')
        assert (cell.status, cell.xbrl_value) == (MISMATCHED, 165_993_000)

    def test_period_of_clearly_different_length_never_pairs(self):
        # Only a six-month fact with the page's value: the nine-month cell is missing.
        facts = [f for f in _facts(TRILOGY)
                 if not (f['concept'] == 'us-gaap:NetIncomeLoss'
                         and f['period_key'] == 'duration_2019-12-01_2020-08-31')]
        facts.append(dict(facts[0], concept='us-gaap:NetIncomeLoss', context_ref='six',
                          period_key='duration_2020-03-01_2020-08-31', period_type='duration',
                          value='164993000', numeric_value=164_993_000.0, decimals='-3', dimensions={}))
        cell = _cell(_compare(TRILOGY, facts), 'us-gaap:NetIncomeLoss', '9 Months Ended Aug. 31, 2020')
        assert cell.status == MISSING

    @pytest.mark.parametrize('start, end, months', [
        ('2019-12-01', '2020-08-31', 9), ('2019-12-02', '2020-08-31', 9),
        ('2021-01-13', '2021-12-31', 12),   # a SPAC's short first year (the renderer rounds)
        ('2020-03-01', '2020-08-31', 6), ('2024-09-29', '2025-09-27', 12),   # 52-week year
        ('2023-10-01', '2024-09-28', 12), ('2024-06-30', '2024-10-05', 3),   # 14-week quarter
        ('2021-01-17', '2021-12-31', 11), ('2021-01-16', '2021-12-31', 12)])  # the 15-day threshold
    def test_rendered_month_count(self, start, end, months):
        from edgar.xbrl.viewer_validation import _rendered_months
        assert _rendered_months(start, end) == months


class TestRepeatedAndSingleBalances:
    """Round 2, items 5 and 9: instants in duration columns, decided by the presentation arc."""

    def test_brixmor_third_occurrence_is_not_comparable(self):
        # Brixmor R8.htm shows the cash concept three times: beginning (21,523 in
        # 2020), end (370,087), and a reconciliation total whose 2020 cell is
        # 21,523 though its arc is a totalLabel. That third row is undecidable.
        results = _compare(BRIXMOR)
        cells = _cells(results, CASH_RC, '12 Months Ended Dec. 31, 2020')
        assert [(c.status, c.viewer_value, c.xbrl_value) for c in cells[:3]] == [
            (MATCHED, 21523, 21523), (MATCHED, 370087, 370087), (NOT_COMPARABLE, 21523, None)]
        assert 'totalLabel' in cells[2].reason

    def test_zscaler_opening_closing_and_total(self):
        # Zscaler R8.htm, "12 Months Ended Jul. 31, 2020": beginning 78,484
        # (instant 2019-07-31), end 141,851 (2020-07-31); the total row (141,851
        # here, but 136,147 = the opening balance in the 2019 column) is undecidable.
        cells = _cells(_compare(ZSCALER), CASH_RC, '12 Months Ended Jul. 31, 2020')
        assert [(c.status, c.xbrl_value) for c in cells] == [
            (MATCHED, 78484), (MATCHED, 141851), (NOT_COMPARABLE, None)]

    def test_single_instant_in_duration_column_is_the_closing_balance(self):
        # Grayscale XLM R3.htm (parenthetical, "12 Months Ended Sep. 30, 2023"):
        # cost of investment "$ 18,479" = instant 2023-09-30 18,479,000; the arc
        # is a terseLabel, so the renderer shows the end-of-period instant.
        cell = _cell(_compare(GRAYSCALE_XLM), 'us-gaap:InvestmentOwnedAtCost', '12 Months Ended Sep. 30, 2023')
        assert (cell.status, cell.xbrl_value) == (MATCHED, 18479)

    def test_order_fallback_without_arcs_or_period_labels(self):
        # Azure R7.htm with no presentation arcs and the period labels removed:
        # the concept shown twice is the opening/closing pair in that order,
        # and swapped balances are still caught.
        viewer, xbrl = _fixture_viewer(AZURE, presentation={})
        tag = viewer._metalinks.get_tag('us-gaap_CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents')
        for role in ('periodStartLabel', 'periodEndLabel'):
            tag.role_labels.pop(role, None)
        cells = _cells(compare_viewer_to_xbrl(viewer, xbrl), CASH_RC, '12 Months Ended Mar. 31, 2023')
        assert [(c.status, c.xbrl_value) for c in cells] == [(MATCHED, 23306), (MATCHED, 20967)]

        facts = _facts(AZURE)
        by_key = {(f['period_key'], f['currency']): f for f in facts if f['concept'] == CASH_RC}
        opening, closing = by_key[('instant_2022-03-31', 'INR')], by_key[('instant_2023-03-31', 'INR')]
        opening['numeric_value'], closing['numeric_value'] = closing['numeric_value'], opening['numeric_value']
        viewer, xbrl = _fixture_viewer(AZURE, facts, presentation={})
        tag = viewer._metalinks.get_tag('us-gaap_CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents')
        for role in ('periodStartLabel', 'periodEndLabel'):
            tag.role_labels.pop(role, None)
        cells = _cells(compare_viewer_to_xbrl(viewer, xbrl), CASH_RC, '12 Months Ended Mar. 31, 2023')
        assert [c.status for c in cells] == [MISMATCHED, MISMATCHED]


class TestUnitDrivenScaleAndPercent:
    """Round 2, items 6, 7 and 8."""

    def test_percent_type_is_shown_times_100(self):
        # DiamondRock R3.htm: dividend rate "8.25%" = 0.0825 (percentItemType).
        cell = _cell(_compare(DIAMONDROCK), 'us-gaap:PreferredStockDividendRatePercentage',
                     '3 Months Ended Mar. 31, 2024')
        assert (cell.status, cell.viewer_value) == (MATCHED, 8.25)
        assert cell.xbrl_value == pytest.approx(8.25)

    def test_ounces_are_not_divided_by_the_currency_scale(self):
        # GraniteShares R4.htm is "$ in Thousands"; gold "331,344.906" oz = 331,344.906.
        cells = _cells(_compare(GRANITESHARES), 'us-gaap:InvestmentOwnedBalanceOtherMeasure', 'Jun. 30, 2026')
        assert [(c.status, c.xbrl_value) for c in cells] == [(MATCHED, 331_344.906)] * 2

    def test_tokens_are_not_divided_by_the_currency_scale(self):
        # Grayscale XLM R4.htm ("$ in Thousands"): 73,100,101.0441121 lumens.
        cell = _cell(_compare(GRAYSCALE_XLM), 'gxlm:QuantityOfLumens', 'Sep. 30, 2023')
        assert (cell.status, cell.xbrl_value) == (MATCHED, 73_100_101.0441121)

    def test_thousandfold_error_on_ounces_is_a_mismatch(self):
        facts = _facts(GRANITESHARES)
        for f in facts:
            if f['concept'] == 'us-gaap:InvestmentOwnedBalanceOtherMeasure':
                f['numeric_value'] *= 1000
        cells = _cells(_compare(GRANITESHARES, facts), 'us-gaap:InvestmentOwnedBalanceOtherMeasure', 'Jun. 30, 2026')
        assert {c.status for c in cells} == {MISMATCHED}

    def test_scale_is_read_per_currency_column(self):
        # Azure R2.htm declares "₨ in Millions, $ in Millions". Declared instead
        # as "$ in Thousands", the INR columns are still compared in millions
        # and the USD column (339 shown, 339,000,000 filed) becomes a mismatch.
        viewer, xbrl = _fixture_viewer(AZURE)
        report = _statement(viewer, "Balance Sheets")
        report.concept_report.unit_scales = {'₨': 1_000_000, '$': 1_000}
        results = compare_viewer_to_xbrl(viewer, xbrl)
        inr = _cell(results, 'us-gaap:AssetsCurrent', 'Mar. 31, 2023')
        usd = _cell(results, 'us-gaap:AssetsCurrent', 'Mar. 31, 2023 (2)')
        assert (inr.status, inr.xbrl_value) == (MATCHED, 27851)
        assert (usd.status, usd.xbrl_value) == (MISMATCHED, 339_000)

    def test_only_currencies_count_as_currency_scales(self):
        from edgar.sgml.concept_extractor import declared_currency_scales
        assert declared_currency_scales({'$': 1_000, 'oz': 1, 'shares': 1_000_000, '$ / shares': 1}) == {1_000}
        assert declared_currency_scales({'R$': 1_000, 'CHF': 1_000_000}) == {1_000, 1_000_000}


class TestScalingFactors:
    """Round 2, item 10."""

    def test_capitalised_shares_statement(self):
        html = ('<table class="report"><tr><th class="tl"><strong>Balance Sheets - USD ($)<br>'
                ' Shares in Thousands, $ in Millions</strong></th><th class="th"><div>Dec. 31, 2024</div>'
                '</th></tr></table>')
        cr = extract_concepts_from_report(html)
        assert (cr.shares_scaling, cr.currency_scaling) == (1_000, 1_000_000)

    def test_scaling_factor_is_none_when_statements_differ(self):
        # IREN: R3.htm is "$ in Thousands", R5.htm is in whole dollars.
        results = _compare(IREN)
        assert results.scaling_factor is None
        assert sorted(results.scaling_factors.values()) == [1, 1_000]

    def test_scaling_factor_when_statements_agree(self):
        # SelectQuote R2.htm is the only statement, "$ in Thousands".
        results = _compare(SELECTQUOTE)
        assert (results.scaling_factor, list(results.scaling_factors.values())) == (1_000, [1_000])


class TestMoreGuards:
    """Round 2, item 11: guards that the round-2 changes did not make the harness lenient."""

    def test_wrong_value_in_the_chosen_duplicate_is_a_mismatch(self):
        # The decimals=-3 Goodwill fact (the one statements use) moved to 29,538,000.
        facts = _facts(SELECTQUOTE)
        for f in facts:
            if f['period_key'] == 'instant_2025-12-31' and f['decimals'] == '-3':
                f['numeric_value'] = 29_538_000.0
        cell = _cell(_compare(SELECTQUOTE, facts), 'us-gaap:Goodwill', 'Dec. 31, 2025')
        assert (cell.status, cell.xbrl_value) == (MISMATCHED, 29538)

    def test_thousandfold_error_on_a_cell_filed_twice_is_a_mismatch(self):
        facts = _facts(SELECTQUOTE)
        for f in facts:
            if f['period_key'] == 'instant_2025-12-31':
                f['numeric_value'] *= 1000
        cell = _cell(_compare(SELECTQUOTE, facts), 'us-gaap:Goodwill', 'Dec. 31, 2025')
        assert (cell.status, cell.xbrl_value) == (MISMATCHED, 29_438_000)

    def test_swapped_member_values_are_mismatches(self):
        # Chindata: Class A authorized 4,500,000,000 and Class B 500,000,000,
        # filed the other way round.
        facts = _facts(CHINDATA)
        for f in facts:
            if f['concept'] == 'us-gaap:CommonStockSharesAuthorized' and f['period_key'] == 'instant_2021-12-31':
                f['numeric_value'] = 5_000_000_000.0 - f['numeric_value']
        cells = _cells(_compare(CHINDATA, facts), 'us-gaap:CommonStockSharesAuthorized', 'Dec. 31, 2021')
        assert [(c.status, c.xbrl_value) for c in cells] == [
            (MISMATCHED, 500_000_000), (MISMATCHED, 4_500_000_000)]


SPAC = "0001193125-22-052373"


class TestRound3:
    """Round 3: renderer month counts, counted extraction gaps, summary counts, units, roles, percent."""

    def test_short_first_period_is_the_twelve_months_column(self):
        # Virgin Group Acquisition Corp. II R4.htm "12 Months Ended Dec. 31, 2021":
        # net income $ 2,698,369; the only facts are at duration_2021-01-13_2021-12-31
        # (incorporated in January), which the renderer heads "12 Months Ended".
        results = _compare(SPAC)
        assert [(c.status, c.xbrl_value) for c in _cells(results, 'us-gaap:NetIncomeLoss',
                                                          '12 Months Ended Dec. 31, 2021')] == [
            (MATCHED, 2_698_369), (MATCHED, 2_698_369)]
        cell = _cell(results, 'us-gaap:NetCashProvidedByUsedInOperatingActivities', '12 Months Ended Dec. 31, 2021')
        assert (cell.status, cell.xbrl_value) == (MATCHED, -1_922_242)

    def test_qualifying_periods_that_disagree_are_not_comparable(self):
        # A second Trilogy net-income fact for 2019-12-02..2020-08-31 (also
        # "9 Months Ended") with another value: the page cannot say which it shows.
        facts = _facts(TRILOGY)
        base = next(f for f in facts if f['concept'] == 'us-gaap:NetIncomeLoss' and not f['dimensions']
                    and f['period_key'] == 'duration_2019-12-01_2020-08-31')
        facts.append(dict(base, context_ref='stray', period_key='duration_2019-12-02_2020-08-31',
                          numeric_value=160_000_000.0, value='160000000'))
        cell = _cell(_compare(TRILOGY, facts), 'us-gaap:NetIncomeLoss', '9 Months Ended Aug. 31, 2020')
        assert cell.status == NOT_COMPARABLE and 'disagree' in cell.reason

    def test_qualifying_periods_that_agree_are_compared(self):
        facts = _facts(TRILOGY)
        base = next(f for f in facts if f['concept'] == 'us-gaap:NetIncomeLoss' and not f['dimensions']
                    and f['period_key'] == 'duration_2019-12-01_2020-08-31')
        facts.append(dict(base, context_ref='stray', period_key='duration_2019-12-02_2020-08-31'))
        cell = _cell(_compare(TRILOGY, facts), 'us-gaap:NetIncomeLoss', '9 Months Ended Aug. 31, 2020')
        assert (cell.status, cell.xbrl_value) == (MATCHED, 164_993_000)

    def test_rc_cells_are_in_the_denominator(self):
        # Spirit R7.htm "Balance, shares at Dec. 31, 2016" 121,642,556 (Common Stock column).
        results = _compare(SPIRIT)
        rc = [r for r in results.results if r.concept_id == 'us-gaap:CommonStockSharesOutstanding'
              and r.label.startswith('Balance, shares at')]
        assert [(r.concept_id, r.viewer_value) for r in rc] == [
            ('us-gaap:CommonStockSharesOutstanding', 121_642_556),
            ('us-gaap:CommonStockSharesOutstanding', 114_447_605),
            ('us-gaap:CommonStockSharesOutstanding', 105_461_817),
            ('us-gaap:CommonStockSharesOutstanding', 104_882_379)]
        assert {r.status for r in rc} == {NOT_COMPARABLE}
        assert all(r.reason for r in rc)

    def test_extractor_rows_are_unchanged_by_the_unextracted_cells(self):
        cr = extract_concepts_from_report((HARNESS_DIR / SPIRIT / "R7.htm").read_text())
        assert [r.concept_id for r in cr.rows] == ['us-gaap_NetIncomeLoss'] * 3
        assert [(c.row_class, c.value, c.column) for c in cr.unextracted_cells][:1] == [('rc', '121,642,556', 1)]

    def test_unread_statement_is_reported(self):
        viewer, xbrl = _fixture_viewer(SELECTQUOTE)
        report = viewer.financial_statements[0]
        report._concept_report = None
        results = compare_viewer_to_xbrl(viewer, xbrl)
        assert results.unread_statements == [report.short_name]
        assert 'unread_statements=1' in str(results)

    def test_disagreeing_duplicate_is_counted_in_the_summary(self):
        # Goodwill copies 29,438,000 (decimals=-3) and 25,000,000 (decimals=-5).
        facts = _facts(SELECTQUOTE)
        for f in facts:
            if f['period_key'] == 'instant_2025-12-31' and f['decimals'] == '-5':
                f['numeric_value'] = 25_000_000.0
        results = _compare(SELECTQUOTE, facts)
        assert results.noted == 1
        assert 'noted=1' in str(results)
        from rich.console import Console
        console = Console(record=True, width=120)
        console.print(results.__rich__())
        assert 'Noted: 1' in console.export_text()

    def test_sign_only_matches_are_counted(self):
        # Quoin R2.htm cash $ 4,759,129 and one more cell; every fact negated.
        facts = _facts(QUOIN)
        for f in facts:
            f['numeric_value'] = -f['numeric_value']
        results = _compare(QUOIN, facts)
        # Since round 7 the rows' label roles are known (plain), so a fact
        # with the wrong sign is a mismatch, not a sign-only match.
        assert (results.matched, results.mismatched, results.sign_only_matches) == (0, 2, 0)
        assert [(r.viewer_value, r.xbrl_value, r.negated) for r in results.results][0] == (
            4_759_129, -4_759_129, False)
        assert '(exact=0, sign_unverified=0)' in str(results)
        plain = _compare(QUOIN)
        assert (plain.exact_matches, plain.sign_only_matches) == (2, 0)

    def test_facts_without_currency_in_mixed_units_are_not_comparable(self):
        # Azure AssetsCurrent at Mar. 31, 2023 is filed in INR and USD; with the
        # currency blanked, the INR column must not be compared with the USD fact.
        facts = _facts(AZURE)
        for f in facts:
            if f['concept'] == 'us-gaap:AssetsCurrent':
                f['currency'] = None
        results = _compare(AZURE, facts)
        for period in ('Mar. 31, 2023', 'Mar. 31, 2023 (2)'):
            cell = _cell(results, 'us-gaap:AssetsCurrent', period)
            assert cell.status == NOT_COMPARABLE and 'units' in cell.reason

    def test_negated_period_start_arc_is_the_opening_balance(self):
        # Azure R7.htm with its periodStartLabel arc rewritten as negatedPeriodStartLabel
        # and the row labels removed from MetaLinks, so only the arc can decide.
        presentation = _rewrite_arc_roles(_presentation(AZURE), lambda _child, pl: (
            'http://www.xbrl.org/2009/role/negatedPeriodStartLabel' if (pl or '').endswith('/periodStartLabel') else pl))
        viewer, xbrl = _fixture_viewer(AZURE, presentation=presentation)
        tag = viewer._metalinks.get_tag('us-gaap_CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents')
        for role in ('periodStartLabel', 'periodEndLabel'):
            tag.role_labels.pop(role, None)
        cells = _cells(compare_viewer_to_xbrl(viewer, xbrl), CASH_RC, '12 Months Ended Mar. 31, 2023')
        # The opening balance is still the one compared (23,306, not 20,967).
        # Since round 7 the sign is checked too: the rewritten arc negates,
        # so the renderer would print (23,306) and the page's 23,306 is a
        # mismatch on sign.
        assert [(c.status, c.xbrl_value, c.negated) for c in cells] == [
            (MISMATCHED, 23306, True), (MATCHED, 20967, False)]

    def test_negated_period_start_label_text_is_the_opening_balance(self):
        viewer, xbrl = _fixture_viewer(AZURE, presentation={})
        tag = viewer._metalinks.get_tag('us-gaap_CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents')
        tag.role_labels['negatedPeriodStartLabel'] = tag.role_labels.pop('periodStartLabel')
        cells = _cells(compare_viewer_to_xbrl(viewer, xbrl), CASH_RC, '12 Months Ended Mar. 31, 2023')
        assert [(c.status, c.xbrl_value) for c in cells] == [(MATCHED, 23306), (MATCHED, 20967)]

    def test_arcs_ordered_differently_from_the_page_are_not_comparable(self):
        # Swap the two arc roles: presentation order then says closing first,
        # while the row labels say opening first. No cell may be read by the arcs.
        swap = {'http://www.xbrl.org/2003/role/periodStartLabel': 'http://www.xbrl.org/2003/role/periodEndLabel',
                'http://www.xbrl.org/2003/role/periodEndLabel': 'http://www.xbrl.org/2003/role/periodStartLabel'}
        presentation = _rewrite_arc_roles(_presentation(AZURE), lambda _child, pl: swap.get(pl, pl))
        cells = _cells(_compare(AZURE, presentation=presentation), CASH_RC, '12 Months Ended Mar. 31, 2023')
        assert [c.status for c in cells] == [NOT_COMPARABLE, NOT_COMPARABLE]
        assert 'do not line up' in cells[0].reason

    def test_percent_shown_without_percent_sign_is_not_multiplied(self):
        # DiamondRock R3.htm shows "8.25%" for 0.0825. Shown as "0.0825", a fact
        # of 0.000825 must not match (x100 applies only to a percentage).
        viewer, xbrl = _fixture_viewer(DIAMONDROCK)
        for row in viewer.financial_statements[0].concept_report.rows:
            if row.concept_id == 'us-gaap_PreferredStockDividendRatePercentage':
                row.values['3 Months Ended Mar. 31, 2024'] = '0.0825'  # noqa: PD011 (dict)
        for f in xbrl.facts._facts:
            if f['concept'] == 'us-gaap:PreferredStockDividendRatePercentage':
                f['numeric_value'] = 0.000825
        cell = _cell(compare_viewer_to_xbrl(viewer, xbrl), 'us-gaap:PreferredStockDividendRatePercentage',
                     '3 Months Ended Mar. 31, 2024')
        assert (cell.status, cell.xbrl_value) == (MISMATCHED, 0.000825)

    def test_percent_shown_without_percent_sign_matches_the_raw_fact(self):
        viewer, xbrl = _fixture_viewer(DIAMONDROCK)
        for row in viewer.financial_statements[0].concept_report.rows:
            if row.concept_id == 'us-gaap_PreferredStockDividendRatePercentage':
                row.values['3 Months Ended Mar. 31, 2024'] = '0.0825'  # noqa: PD011 (dict)
        cell = _cell(compare_viewer_to_xbrl(viewer, xbrl), 'us-gaap:PreferredStockDividendRatePercentage',
                     '3 Months Ended Mar. 31, 2024')
        assert (cell.status, cell.xbrl_value) == (MATCHED, 0.0825)

    @pytest.mark.parametrize('display, expected', [('ABC 12', None), ('XYZ 4', None), ('EUR -5', -5.0),
                                                   ('AB$ 3', 3.0), ('ABC%', None)])
    def test_only_real_currency_prefixes_are_stripped(self, display, expected):
        from edgar.sgml.concept_extractor import parse_numeric
        assert parse_numeric(display) == expected

    def test_large_value_tolerance_has_no_relative_slack(self):
        from edgar.xbrl.viewer_validation import _display_tolerance
        # A page value of 1,234,567,890,123 allows half a unit, not 1,235.
        assert _display_tolerance('1,234,567,890,123', 1_234_567_890_123.0, 1_234_567_890_123.0) < 0.51
        assert _display_tolerance('$ 0.65', 0.65, 0.65) == pytest.approx(0.005)


GLOBAL_TECH = "0001214659-22-006372"  # 10-Q, quarter ended 2022-03-29; the instance binds srt to pf0
AMH = "0001562401-24-000082"  # 10-Q, quarter ended 2024-09-30; L.P. statements by legal entity
SRT_2022 = 'http://fasb.org/srt/2022'
UNIT_CONCEPTS = ['us-gaap:CommonUnitIssued', 'us-gaap:CommonUnitOutstanding',
                 'us-gaap:PreferredUnitsOutstanding', 'us-gaap:PreferredUnitsIssued']


class TestRound4DimensionLookup:
    """Round 4: axes and members compare by namespace; a context the page does not identify."""

    def test_axis_prefix_bound_by_the_filer_resolves_by_namespace(self):
        ns = _namespaces(GLOBAL_TECH)
        assert ns['namespace_prefixes'][SRT_2022] == 'pf0'
        service = [f for f in _facts(GLOBAL_TECH)
                   if f['concept'] == 'us-gaap:Revenues' and f['period_key'] == 'duration_2021-12-29_2022-03-29'
                   and f['dimensions'] == {'pf0:ProductOrServiceAxis': 'us-gaap:ServiceMember'}]
        assert [f['numeric_value'] for f in service] == [33364000.0]
        cells = _cells(_compare(GLOBAL_TECH), 'us-gaap:Revenues', '3 Months Ended Mar. 29, 2022')
        restaurant = [c for c in cells if c.viewer_value == 33364.0]
        assert [(c.status, c.xbrl_value) for c in restaurant] == [(MATCHED, 33364.0)]
        assert not [c for c in _compare(GLOBAL_TECH).results if c.status == MISSING]

    def test_same_local_name_in_another_namespace_does_not_match(self):
        # Rebind pf0 to a namespace that is not srt: the page's srt axis is no
        # longer the facts' axis, although the local names are the same.
        ns = copy.deepcopy(_namespaces(GLOBAL_TECH))
        ns['namespace_prefixes'] = {('http://example.com/other/2022' if uri == SRT_2022 else uri): p
                                    for uri, p in ns['namespace_prefixes'].items()}
        cells = _cells(_compare(GLOBAL_TECH, namespaces=ns), 'us-gaap:Revenues', '3 Months Ended Mar. 29, 2022')
        restaurant = [c for c in cells if c.viewer_value == 33364.0]
        assert len(restaurant) == 1
        assert restaurant[0].status != MATCHED and restaurant[0].xbrl_value is None

    def test_member_header_naming_fewer_dimensions_is_not_comparable(self):
        facts = _facts(AMH)
        wider = [f for f in facts if f['concept'] == 'us-gaap:CommonUnitIssued'
                 and f['period_key'] == 'instant_2024-09-30' and f['numeric_value'] == 366520263.0]
        assert wider and all('us-gaap:PartnerTypeOfPartnersCapitalAccountAxis' in f['dimensions'] for f in wider)
        results = _compare(AMH)
        cells = [c for concept in UNIT_CONCEPTS for c in _cells(results, concept)]
        assert len(cells) == 12
        assert {c.status for c in cells} == {NOT_COMPARABLE}
        assert all(c.xbrl_value is None for c in cells)
        first = [c for c in _cells(results, 'us-gaap:CommonUnitIssued', 'Sep. 30, 2024')
                 if c.viewer_value == 366520263.0]
        assert len(first) == 1
        first = first[0]
        assert 'PartnerTypeOfPartnersCapitalAccountAxis' in first.reason
        assert 'does not say which context' in first.reason

    def test_wrong_value_in_a_wider_context_fact_does_not_become_a_match(self):
        facts = copy.deepcopy(_facts(AMH))
        for f in facts:
            if f['concept'] == 'us-gaap:CommonUnitIssued':
                f['numeric_value'] = 1.0
                f['value'] = '1'
        cells = _cells(_compare(AMH, facts), 'us-gaap:CommonUnitIssued')
        assert cells and {c.status for c in cells} == {NOT_COMPARABLE}

    def test_no_fact_under_the_stated_dimensions_or_any_extension_stays_missing(self):
        facts = [f for f in _facts(AMH) if f['concept'] != 'us-gaap:CommonUnitIssued'
                 or 'dei:LegalEntityAxis' not in f['dimensions']]
        cells = _cells(_compare(AMH, facts), 'us-gaap:CommonUnitIssued')
        assert cells and {c.status for c in cells} == {MISSING}


PLAYTIKA = "0001828016-23-000023"  # 10-Q, quarter ended 2023-03-31; R5 statement of stockholders' deficit
DRDGOLD = "0001562762-22-000397"   # 20-F, year ended 2022-06-30; R4, IFRS, amounts in rand
INNOVAGE = "0001834376-26-000049"  # 10-K, year ended 2026-06-30; R6, rows after a movement's closing rows
CGI = "0001193125-21-361301"       # 40-F, year ended 2021-09-30; R5, IFRS, a restatement member in a row label
DEFICIT = "STOCKHOLDERS"


def _equity_cells(results, concept, label=None, column=None):
    return [r for r in results.results if r.concept_id == concept
            and (label is None or r.label == label) and (column is None or r.period == column)]


def _equity_cell(results, concept, label, column):
    cells = _equity_cells(results, concept, label, column)
    assert len(cells) == 1, cells
    return cells[0]


class TestEquityStatements:
    """Round 5: statement-of-equity cells compared by member column and period block."""

    def test_playtika_every_equity_cell_is_matched(self):
        results = _compare(PLAYTIKA)
        cells = [r for r in results.results if DEFICIT in r.report]
        assert len(cells) == 48
        assert {r.status for r in cells} == {MATCHED}

    def test_playtika_member_columns_and_balances(self):
        results = _compare(PLAYTIKA)
        # Net income 83.2 (Q1 2022) under "Total" (no dimension) and "Retained earnings".
        assert [(c.period, c.viewer_value, c.xbrl_value) for c in _equity_cells(results, 'us-gaap:NetIncomeLoss')] == [
            ('Total', 83.2, 83.2), ('Retained earnings (Accumulated deficit)', 83.2, 83.2),
            ('Total', 84.1, 84.1), ('Retained earnings (Accumulated deficit)', 84.1, 84.1)]
        shares = _equity_cell(results, 'us-gaap:SharesOutstanding', 'Beginning balance (in shares) at Dec. 31, 2021',
                              'Share capital')
        assert (shares.status, shares.xbrl_value) == (MATCHED, 411.1)
        total = _equity_cell(results, 'us-gaap:StockholdersEquity', 'Beginning balance at Dec. 31, 2021', 'Total')
        assert (total.status, total.xbrl_value) == (MATCHED, -377.7)

    def test_amh_two_line_headings_name_component_and_share_class(self):
        # "Common shares / Class A common shares" and ".../ Class B ...": 352,881,826 and 635,075 shares.
        results = _compare(AMH)
        cells = _equity_cells(results, 'us-gaap:CommonStockSharesOutstanding',
                              'Beginning balances, common stock (in shares) at Dec. 31, 2022')
        assert [(c.viewer_value, c.status) for c in cells][:2] == [(352_881_826, MATCHED), (635_075, MATCHED)]
        equity = [r for r in results.results if r.report == 'Condensed Consolidated Statements of Equity']
        assert len(equity) == 338 and {r.status for r in equity} == {MATCHED}

    def test_amh_movement_opened_by_the_previous_closing_rows(self):
        # The Q2 2023 movement's opening rows are hidden; it opens on the
        # "Ending balances ... at Mar. 31, 2023" rows above it.
        results = _compare(AMH)
        closing = _equity_cells(results, 'us-gaap:CommonStockSharesOutstanding',
                                'Ending balances, common stock (in shares) at Jun. 30, 2023')
        assert [(c.viewer_value, c.status) for c in closing] == [(361_365_692, MATCHED), (635_075, MATCHED)]

    def test_drdgold_ifrs_components_and_rand_amounts(self):
        results = _compare(DRDGOLD)
        cell = _equity_cell(results, 'ifrs-full:Equity', 'Beginning balance at Jun. 30, 2019', 'Total')
        assert (cell.status, cell.viewer_value, cell.xbrl_value) == (MATCHED, 2688.6, 2688.6)
        cell = _equity_cell(results, 'ifrs-full:Equity', 'Ending balance at Jun. 30, 2021', 'Retained earnings [member]')
        assert (cell.status, cell.xbrl_value) == (MATCHED, -1337.5)

    def test_innovage_row_after_the_closing_rows_belongs_to_its_movement(self):
        # "Net Loss" (ProfitLoss) is presented after the closing balance rows:
        # -35,343 is fiscal 2025, -683 fiscal 2026. The nearest balance rows
        # would have put the first in fiscal 2026.
        cells = _equity_cells(_compare(INNOVAGE), 'us-gaap:ProfitLoss')
        assert [(c.viewer_value, c.xbrl_value, c.status) for c in cells] == [
            (-35_343, -35_343, MATCHED), (-683, -683, MATCHED)]

    def test_cgi_row_label_names_a_restatement_member(self):
        results = _compare(CGI)
        stated = _equity_cell(results, 'ifrs-full:Equity', 'Beginning balance (Previously stated) at Sep. 30, 2019', 'Total')
        adoption = _equity_cell(results, 'ifrs-full:Equity', 'Beginning balance (Adoption of IFRS 16) at Sep. 30, 2019',
                                'Total')
        restated = _equity_cell(results, 'ifrs-full:Equity', 'Beginning balance at Sep. 30, 2019', 'Total')
        assert [(c.xbrl_value, c.status) for c in (stated, adoption, restated)] == [
            (6_884_103, MATCHED), (-93_873, MATCHED), (6_790_230, MATCHED)]

    # Guards: the harness still catches errors on equity pages.

    def test_wrong_value_under_the_right_component(self):
        facts = copy.deepcopy(_facts(PLAYTIKA))
        for f in facts:
            if (f['concept'] == 'us-gaap:NetIncomeLoss' and f['period_key'] == 'duration_2022-01-01_2022-03-31'
                    and f['dimensions']):
                f['numeric_value'] = 80_000_000.0
        cells = _equity_cells(_compare(PLAYTIKA, facts), 'us-gaap:NetIncomeLoss')
        assert [(c.period, c.status) for c in cells][:2] == [
            ('Total', MATCHED), ('Retained earnings (Accumulated deficit)', MISMATCHED)]
        assert cells[1].xbrl_value == 80.0

    def test_right_values_under_swapped_components(self):
        viewer, xbrl = _fixture_viewer(PLAYTIKA)
        cr = _statement(viewer, DEFICIT).concept_report
        apic = cr.period_headers.index('Additional paid-in capital')
        retained = cr.period_headers.index('Retained earnings (Accumulated deficit)')
        parts = cr.column_heading_parts
        parts[apic], parts[retained] = parts[retained], parts[apic]
        results = compare_viewer_to_xbrl(viewer, xbrl)
        opening = _equity_cells(results, 'us-gaap:StockholdersEquity', 'Beginning balance at Dec. 31, 2021')
        swapped = [c for c in opening if c.period in ('Additional paid-in capital', 'Retained earnings (Accumulated deficit)')]
        assert [(c.viewer_value, c.xbrl_value, c.status) for c in swapped] == [
            (1032.9, -1417.9, MISMATCHED), (-1417.9, 1032.9, MISMATCHED)]
        net_income = _equity_cells(results, 'us-gaap:NetIncomeLoss', column='Retained earnings (Accumulated deficit)')
        assert MATCHED not in {c.status for c in net_income}

    def test_flow_value_from_the_wrong_period_block(self):
        viewer, xbrl = _fixture_viewer(PLAYTIKA)
        cr = _statement(viewer, DEFICIT).concept_report
        first = next(r for r in cr.rows if r.concept_id == 'us-gaap_NetIncomeLoss')
        first.values['Total'] = '84.1'  # noqa: PD011 (dict) -- the Q1 2023 value, in the Q1 2022 block
        cell = _equity_cells(compare_viewer_to_xbrl(viewer, xbrl), 'us-gaap:NetIncomeLoss', column='Total')[0]
        assert (cell.status, cell.viewer_value, cell.xbrl_value) == (MISMATCHED, 84.1, 83.2)

    def test_opening_balance_compared_with_the_closing_one(self):
        viewer, xbrl = _fixture_viewer(PLAYTIKA)
        cr = _statement(viewer, DEFICIT).concept_report
        total = cr.period_headers.index('Total')
        cell = next(c for c in cr.unextracted_cells
                    if c.label == 'Beginning balance at Dec. 31, 2021' and c.column == total)
        cell.value = '(240.0)'  # the closing balance at Mar. 31, 2022
        result = _equity_cell(compare_viewer_to_xbrl(viewer, xbrl), 'us-gaap:StockholdersEquity',
                              'Beginning balance at Dec. 31, 2021', 'Total')
        assert (result.status, result.viewer_value, result.xbrl_value) == (MISMATCHED, -240.0, -377.7)

    def test_column_label_that_matches_two_members_is_not_comparable(self):
        viewer, xbrl = _fixture_viewer(PLAYTIKA)
        xbrl.element_catalog['us-gaap_AdditionalPaidInCapitalMember'].labels[
            'http://www.xbrl.org/2003/role/terseLabel'] = 'Treasury stock'
        results = compare_viewer_to_xbrl(viewer, xbrl)
        cells = [r for r in results.results if r.period == 'Treasury stock']
        assert cells and {c.status for c in cells} == {NOT_COMPARABLE}
        assert all('several members' in c.reason for c in cells)
        apic = [r for r in results.results if r.period == 'Additional paid-in capital']
        assert apic and {c.status for c in apic} == {NOT_COMPARABLE}

    def test_extractor_rows_are_unchanged_on_a_whole_equity_page(self):
        cr = extract_concepts_from_report((HARNESS_DIR / PLAYTIKA / "R5.htm").read_text())
        assert cr.period_headers[:2] == ['Total', 'Share capital']
        assert cr.column_heading_parts[:2] == [['Total'], ['Share capital']]
        rc = [c for c in cr.unextracted_cells if c.row_class == 'rc']
        assert (rc[0].label, rc[0].value, rc[0].row_index) == ('Beginning balance (in shares) at Dec. 31, 2021', '411.1', 0)


SPAC_NIL = "0001104659-21-109339"  # 10-Q (Roth CH Acquisition III), R5; the Q2 2020 flows are nil facts
DIGI = "0000854775-20-000032"      # 10-K, fiscal 2020, R7; an instant row inside every movement
HUBC = "0001213900-26-079236"      # 20-F, 2025, R5; IFRS, two columns headed "Total"
CIBC = "0001193125-24-271105"      # 40-F, fiscal 2024, R7; IFRS on https, footnote cells
BILIBILI = "0001193125-25-061847"  # 20-F, 2024, R2; balance sheet in CNY thousands, consistent duplicates


class TestRound6:
    """Round 6: namespace fallback, placement without cascades, column order, duplicates."""

    # Item 1: a prefix the merged bindings give two namespaces.

    def test_prefix_bound_to_two_namespaces_compares_prefixed_names(self):
        # A schema binding us-gaap to srt-sup (0001663577-23-000279 and
        # 0001493152-23-009799 do) leaves the instance's binding unknown:
        # names under it compare as written, on both sides.
        namespaces = copy.deepcopy(_namespaces(PLAYTIKA))
        namespaces['namespace_prefixes']['http://fasb.org/srt-sup/2022q3'] = 'us-gaap'
        cells = [r for r in _compare(PLAYTIKA, namespaces=namespaces).results if DEFICIT in r.report]
        assert len(cells) == 48 and {r.status for r in cells} == {MATCHED}
        apic = _equity_cell(_compare(PLAYTIKA, namespaces=namespaces), 'us-gaap:StockholdersEquity',
                            'Beginning balance at Dec. 31, 2021', 'Additional paid-in capital')
        assert (apic.xbrl_value, apic.xbrl_dimensions) == (
            1032.9, {'us-gaap:StatementEquityComponentsAxis': 'us-gaap:AdditionalPaidInCapitalMember'})

    def test_ambiguous_prefix_never_matches_by_local_name(self):
        # Under the ambiguous prefix a fact whose axis is another namespace's
        # same local name is not the cell's.
        namespaces = copy.deepcopy(_namespaces(PLAYTIKA))
        namespaces['namespace_prefixes']['http://fasb.org/srt-sup/2022q3'] = 'us-gaap'
        facts = copy.deepcopy(_facts(PLAYTIKA))
        for f in facts:
            f['dimensions'] = {k.replace('us-gaap:', 'srt:'): v for k, v in f['dimensions'].items()}
        cell = _equity_cell(_compare(PLAYTIKA, facts, namespaces=namespaces), 'us-gaap:StockholdersEquity',
                            'Beginning balance at Dec. 31, 2021', 'Additional paid-in capital')
        assert cell.status == MISSING

    # Item 2: one unplaceable block does not take the statement with it.

    def test_dropped_opening_instant_leaves_its_cells_missing_and_the_rest_compared(self):
        facts = [f for f in _facts(PLAYTIKA) if f['period_key'] != 'instant_2021-12-31']
        cells = [r for r in _compare(PLAYTIKA, facts).results if DEFICIT in r.report]
        missing = [c for c in cells if c.status == MISSING]
        assert {c.label for c in missing} == {'Beginning balance at Dec. 31, 2021',
                                              'Beginning balance (in shares) at Dec. 31, 2021'}
        assert len(missing) == 6
        assert {c.status for c in cells if c not in missing} == {MATCHED}
        net_income = _equity_cells(_compare(PLAYTIKA, facts), 'us-gaap:NetIncomeLoss', column='Total')
        assert [(c.xbrl_value, c.xbrl_period_key) for c in net_income] == [
            (83.2, 'duration_2022-01-01_2022-03-31'), (84.1, 'duration_2023-01-01_2023-03-31')]

    def test_misdated_movement_leaves_its_flows_missing(self):
        facts = copy.deepcopy(_facts(PLAYTIKA))
        for f in facts:
            if f['period_key'] == 'duration_2022-01-01_2022-03-31':
                f['period_key'] = 'duration_2022-01-02_2022-03-31'
        cells = [r for r in _compare(PLAYTIKA, facts).results if DEFICIT in r.report]
        missing = [c for c in cells if c.status == MISSING]
        assert len(missing) == 11
        assert {c.reason for c in missing} <= {'no fact for duration_2022-01-01_2022-03-31 without dimensions'} | {
            c.reason for c in missing if c.reason.startswith('no fact for duration_2022-01-01_2022-03-31 with ')}
        assert {c.status for c in cells if c not in missing} == {MATCHED}

    def test_nil_facts_give_a_movement(self):
        # Roth CH: the Q2 2020 net loss is filed as nil facts only, and the
        # page still prints the block (closing at Jun. 30, 2020).
        from edgar.xbrl.viewer_validation import _FactIndex, _statement_periods
        _viewer, xbrl = _fixture_viewer(SPAC_NIL)
        index = _FactIndex(xbrl)
        concepts = {f['concept'] for f in _facts(SPAC_NIL)}
        keys = [p['key'] for p in _statement_periods(index, concepts)]
        assert 'duration_2020-04-01_2020-06-30' in keys
        cells = _equity_cells(_compare(SPAC_NIL), 'us-gaap:StockholdersEquity', 'Balance at the end at Jun. 30, 2020')
        assert [(c.period, c.xbrl_value, c.status) for c in cells] == [
            ('Non-redeemable common stock', 288, MATCHED), ('Additional Paid-in Capital', 24_712, MATCHED),
            ('Accumulated Deficit', -1_310, MATCHED), ('Total', 23_690, MATCHED)]

    def test_row_that_fits_several_blocks_is_not_comparable(self):
        # A page showing only the half-year movement of a 10-Q whose facts
        # also give the two quarters: the flow row fits all three.
        from edgar.xbrl.viewer_validation import _place_rows, _statement_periods
        contexts = {('SE', f'instant_{d}'): {frozenset()} for d in ('2023-12-31', '2024-03-31', '2024-06-30')}
        contexts.update({('NI', f'duration_{a}_{b}'): {frozenset()} for a, b in (
            ('2024-01-01', '2024-03-31'), ('2024-04-01', '2024-06-30'), ('2024-01-01', '2024-06-30'))})
        periods = _statement_periods(SimpleNamespace(period_contexts=contexts), {'SE', 'NI'})
        entries = [dict(kind='balance', date='2023-12-31', options=[(0, 'start', frozenset())]),
                   dict(kind='row', period_type='duration', options=[(1, 'plain', frozenset())]),
                   dict(kind='balance', date='2024-06-30', options=[(2, 'end', frozenset())])]
        groups = _place_rows(entries, periods)
        assert sorted(periods[g]['key'] for g in groups[1]) == [
            'duration_2024-01-01_2024-03-31', 'duration_2024-01-01_2024-06-30', 'duration_2024-04-01_2024-06-30']

    def test_row_with_no_block_does_not_empty_the_others(self):
        from edgar.xbrl.viewer_validation import _place_rows, _statement_periods
        contexts = {('SE', f'instant_{d}'): {frozenset()} for d in ('2021-12-31', '2022-12-31')}
        contexts[('NI', 'duration_2022-01-01_2022-12-31')] = {frozenset()}
        periods = _statement_periods(SimpleNamespace(period_contexts=contexts), {'SE', 'NI'})
        entries = [dict(kind='balance', date='2021-12-31', options=[(0, 'start', frozenset())]),
                   dict(kind='row', period_type='duration', options=[(1, 'plain', frozenset())]),
                   dict(kind='balance', date='2022-12-31', options=[(3, 'end', frozenset())]),
                   dict(kind='balance', date='2030-06-30', options=[(3, 'end', frozenset())])]
        groups = _place_rows(entries, periods)
        assert [sorted(periods[g]['key'] for g in g_) for g_ in groups] == [
            ['duration_2022-01-01_2022-12-31']] * 3 + [[]]

    def test_unresolved_row_axis_member_is_not_comparable(self):
        viewer, xbrl = _fixture_viewer(CGI)
        cr = _statement(viewer, 'EQUITY').concept_report if any(
            'EQUITY' in vr.short_name for vr in viewer.financial_statements) else viewer.financial_statements[0].concept_report
        label = 'Beginning balance (Previously stated) at Sep. 30, 2019'
        for cell in cr.unextracted_cells:
            if cell.label == label:
                cell.label = 'Beginning balance (Not a member) at Sep. 30, 2019'
        results = compare_viewer_to_xbrl(viewer, xbrl)
        cells = [r for r in results.results if r.label == 'Beginning balance (Not a member) at Sep. 30, 2019']
        assert cells and {c.status for c in cells} == {NOT_COMPARABLE}
        assert all('row-axis member' in c.reason for c in cells)
        restated = _equity_cell(results, 'ifrs-full:Equity', 'Beginning balance at Sep. 30, 2019', 'Total')
        assert (restated.xbrl_value, restated.status) == (6_790_230, MATCHED)

    def test_instant_row_inside_a_movement(self):
        # Digi: the "Cumulative-effect adjustment" row prints the adoption
        # adjustment at Sep. 30, 2017 (19) and equity at the movement's
        # closing or opening; where both instants are filed the page does not say which.
        results = _compare(DIGI)
        rows = _equity_cells(results, 'us-gaap:StockholdersEquity',
                             'Cumulative-effect adjustment from adoption of ASU 2016-09')
        adoption = [c for c in rows if c.period == 'Cumulative Effect, Period of Adoption, Adjustment [Member]']
        assert [(c.viewer_value, c.status, c.xbrl_period_key) for c in adoption] == [
            (19, MATCHED, 'instant_2017-09-30'), (19, MATCHED, 'instant_2017-09-30')]
        totals = [c for c in rows if c.period == 'Total']
        assert [(c.viewer_value, c.status) for c in totals][:2] == [(319_029, MATCHED), (330_493, NOT_COMPARABLE)]
        assert 'facts exist for both' in totals[1].reason
        assert MISMATCHED not in {c.status for c in results.results}

    # Routing.

    @pytest.mark.parametrize("headers,classes,expected", [
        (['Total', 'Common Stock'], ['rc', 'ro'], True),
        (['Dec. 31, 2021', 'Dec. 31, 2020'], ['rc'], False),   # dated columns: the period path
        (['Total', 'Common Stock'], ['ro'], False),            # member columns without rc rows
    ])
    def test_equity_routing(self, headers, classes, expected):
        from edgar.xbrl.viewer_validation import _is_equity_layout
        cr = SimpleNamespace(period_headers=headers,
                             unextracted_cells=[SimpleNamespace(row_class=c) for c in classes])
        assert _is_equity_layout(cr) is expected

    def test_member_columns_without_balance_rows_state_no_period(self):
        # A statement of equity without start/end labels (BankUnited's 10-K,
        # 0001504008-21-000016) prints no date anywhere; its cells are
        # compared nowhere, each with the reason.
        viewer, xbrl = _fixture_viewer(PLAYTIKA)
        cr = _statement(viewer, DEFICIT).concept_report
        cr.unextracted_cells = [c for c in cr.unextracted_cells if c.row_class != 'rc']
        cells = [r for r in compare_viewer_to_xbrl(viewer, xbrl).results if DEFICIT in r.report]
        assert cells and {c.status for c in cells} == {NOT_COMPARABLE}
        assert MATCHED not in {c.status for c in cells}

    # Item 3: headings.

    def test_two_total_columns_follow_the_renderer_column_order(self):
        # HUBC: "Total" is ParentMember's terse label, and the column on every
        # default is "Total" too; the domain is presented last, so the parent
        # column comes first: 6,413 then 8,810 (equity at Dec. 31, 2022).
        cells = [c for c in _equity_cells(_compare(HUBC), 'ifrs-full:Equity', 'Balance at Dec. 31, 2022')
                 if c.period == 'Total']
        assert [(c.viewer_value, c.status, c.xbrl_dimensions) for c in cells] == [
            (6_413, MATCHED, {'ifrs-full:ComponentsOfEquityAxis': 'ifrs-full:ParentMember'}),
            (8_810, MATCHED, {})]

    def test_swapped_total_columns_are_mismatches(self):
        viewer, xbrl = _fixture_viewer(HUBC)
        cr = _statement(viewer, 'Changes In Equity').concept_report
        first, second = [i for i, h in enumerate(cr.period_headers) if h.startswith('Total')]
        for cell in cr.unextracted_cells:
            if cell.label == 'Balance at Dec. 31, 2022' and cell.column == first:
                cell.value = '8,810'
            elif cell.label == 'Balance at Dec. 31, 2022' and cell.column == second:
                cell.value = '6,413'
        cells = [c for c in _equity_cells(compare_viewer_to_xbrl(viewer, xbrl), 'ifrs-full:Equity',
                                          'Balance at Dec. 31, 2022') if c.period.startswith('Total')]
        assert [(c.viewer_value, c.xbrl_value, c.status) for c in cells] == [
            (8_810, 6_413, MISMATCHED), (6_413, 8_810, MISMATCHED)]

    def test_identical_headings_without_enough_filed_columns_are_not_comparable(self):
        facts = [f for f in _facts(HUBC) if 'ifrs-full:ParentMember' not in f['dimensions'].values()]
        cells = [c for c in _compare(HUBC, facts).results if c.period.startswith('Total')]
        assert cells and {c.status for c in cells} == {NOT_COMPARABLE}
        assert all('column order does not tell' in c.reason for c in cells)

    def test_blank_heading_is_not_the_total_column(self):
        viewer, xbrl = _fixture_viewer(PLAYTIKA)
        cr = _statement(viewer, DEFICIT).concept_report
        total = cr.period_headers.index('Total')
        cr.column_heading_parts[total] = []
        cells = [r for r in compare_viewer_to_xbrl(viewer, xbrl).results
                 if DEFICIT in r.report and r.period == 'Total']
        assert cells and {c.status for c in cells} == {NOT_COMPARABLE}
        assert all(c.reason.startswith('column heading is blank') for c in cells)

    def test_ifrs_https_namespace_row_axis_and_footnote_cells(self):
        results = _compare(CIBC)
        stated = _equity_cell(results, 'ifrs-full:Equity',
                              'Balance at beginning of year (Previously stated [member]) at Oct. 31, 2022',
                              'Retained earnings [member]')
        assert (stated.viewer_value, stated.status) == (28_823, MATCHED)
        assert stated.xbrl_dimensions['ifrs-full:RetrospectiveApplicationAndRetrospectiveRestatementAxis'] == \
            'ifrs-full:PreviouslyStatedMember'
        # 21 footnote-reference cells ("[1]") on the page are not cells of the statement.
        assert not [r for r in results.results if r.viewer_value is None]
        assert {r.status for r in results.results} == {MATCHED}

    # Item 4: duplicates.

    def test_page_printing_the_less_precise_consistent_duplicate_matches_with_a_note(self):
        # Bilibili: -27,661,459,000 (decimals -3) and -27,661,500,000 (-5); the page prints (27,661,500).
        cell = _cell(_compare(BILIBILI), 'us-gaap:RetainedEarningsUnappropriated', 'Dec. 31, 2024')
        assert (cell.viewer_value, cell.xbrl_value, cell.status) == (-27_661_500, -27_661_500, MATCHED)
        assert cell.note.startswith('the page shows a less precise duplicate: -27661500000 (decimals=-5)')
        prior = _cell(_compare(BILIBILI), 'us-gaap:RetainedEarningsUnappropriated', 'Dec. 31, 2023')
        assert (prior.xbrl_value, prior.note) == (-26_310_766, None)  # the precise copy, printed as filed

    def test_corrupted_duplicate_is_still_a_mismatch(self):
        facts = copy.deepcopy(_facts(BILIBILI))
        for f in facts:
            if (f['concept'] == 'us-gaap:RetainedEarningsUnappropriated' and f['context_ref'] == 'PAsOn12_31_2024'
                    and f['unit_ref'] == 'Unit_CNY' and f['decimals'] == '-3'):
                f['numeric_value'] = -27_600_000_000.0
        cell = _cell(_compare(BILIBILI, facts), 'us-gaap:RetainedEarningsUnappropriated', 'Dec. 31, 2024')
        assert (cell.status, cell.xbrl_value) == (MISMATCHED, -27_600_000)
        assert cell.note.startswith('duplicate facts disagree beyond their stated precision')

    # Item 6: the paired fact.

    def test_paired_fact_is_reported(self):
        results = _compare(PLAYTIKA)
        cell = _equity_cell(results, 'us-gaap:StockholdersEquity', 'Beginning balance at Dec. 31, 2021', 'Total')
        assert (cell.xbrl_period_key, cell.xbrl_dimensions) == ('instant_2021-12-31', {})
        assert cell.xbrl_unit
        df = results.to_dataframe()
        assert {'xbrl_period_key', 'xbrl_dimensions', 'xbrl_unit'} <= set(df.columns)
        unmatched = [r for r in results.results if r.status in (MISSING, NOT_COMPARABLE)]
        assert all(r.xbrl_period_key is None for r in unmatched)


# ---------------------------------------------------------------------------
# Round 7: the sign each row's label role gives a fact, and a "$" scale
# shared by two currencies. Values read from the filings' R pages and
# instance documents.

SWIFTMERGE = "0001193125-24-083443"  # 10-K FY2023; R4 earnings per share on negatedLabel arcs, filed sign="-"
NORTHERN_DYNASTY = "0001654954-22-004500"  # 40-F FY2021 in CAD; "$ in Thousands" names USD's scale on R2
INNOVAGE_CASH = 'Consolidated Statements of Cash Flows'
CAPEX = 'us-gaap:PaymentsToAcquirePropertyPlantAndEquipment'
NEGATED = 'http://www.xbrl.org/2009/role/negatedLabel'


def _with_fact(accession, concept, change, **match):
    facts = copy.deepcopy(_facts(accession))
    for f in facts:
        if f['concept'] == concept and all(f.get(k) == v for k, v in match.items()):
            change(f)
    return facts


def _with_extra_arc(accession, concept, role):
    """The presentation with ``concept`` presented a second time, under the same parent, on ``role``."""
    presentation = copy.deepcopy(_presentation(accession))
    element_id = concept.replace(':', '_')
    for tree in presentation.values():
        for parent, node in tree['nodes'].items():
            if element_id in node['children']:
                node['children'].append(element_id)
                node['child_preferred_labels'].append(role)
                rels = tree.get('relationships', [])
                if rels:
                    last = max(r[2] for r in rels if r[0] == parent)
                    rels.append([parent, element_id, last + 1, role])
                return presentation
    raise AssertionError(f"{concept} is not presented")


class TestRound7Sign:

    # Filed values: the renderer prints a fact negated when its row's arc has a negated label role.

    def test_negated_cash_flow_row_matches_the_negated_fact(self):
        # InnovAge R7: "Purchases of property and equipment" (14,309), fact 14,309,000, negatedLabel.
        results = _compare(INNOVAGE)
        cell = _cell(results, CAPEX, '12 Months Ended Jun. 30, 2026', report=INNOVAGE_CASH)
        assert (cell.viewer_value, cell.xbrl_value, cell.status, cell.sign_only) == (-14_309, 14_309, MATCHED, False)
        assert (cell.negated, cell.label_role) == (True, NEGATED)
        # A negative fact on a negated row prints positive: receivables fell 11,210 in FY2025.
        receivables = _cell(results, 'us-gaap:IncreaseDecreaseInAccountsReceivable', '12 Months Ended Jun. 30, 2025',
                            report=INNOVAGE_CASH)
        assert (receivables.viewer_value, receivables.xbrl_value, receivables.status) == (11_210, -11_210, MATCHED)

    def test_negated_income_statement_row_matches_the_negated_fact(self):
        # Swiftmerge R4: Class B basic EPS printed 0.22; the instance tags it sign="-" (-0.22) on a negatedLabel arc.
        results = _compare(SWIFTMERGE)
        cells = [c for c in _cells(results, 'us-gaap:EarningsPerShareBasic', '12 Months Ended Dec. 31, 2023')
                 if c.xbrl_dimensions == {'us-gaap:StatementClassOfStockAxis': 'us-gaap:CommonClassBMember'}]
        assert [(c.viewer_value, c.xbrl_value, c.status, c.negated, c.sign_only) for c in cells] == [
            (0.22, -0.22, MATCHED, True, False)]

    def test_negated_equity_row_matches_the_negated_fact(self):
        # InnovAge R6: "Shares repurchased at cost" (7,321) in Total, fact 7,321,000, negatedTerseLabel.
        cell = _equity_cell(_compare(INNOVAGE), 'us-gaap:TreasuryStockValueAcquiredCostMethod',
                            'Shares repurchased at cost', 'Total')
        assert (cell.viewer_value, cell.xbrl_value, cell.status, cell.negated) == (-7_321, 7_321, MATCHED, True)
        assert cell.label_role == 'http://www.xbrl.org/2009/role/negatedTerseLabel'

    def test_positive_row_matches_its_positive_fact(self):
        cell = _cell(_compare(INNOVAGE), 'us-gaap:NetCashProvidedByUsedInOperatingActivities',
                     '12 Months Ended Jun. 30, 2026', report=INNOVAGE_CASH)
        assert (cell.viewer_value, cell.xbrl_value, cell.status, cell.negated) == (64_714, 64_714, MATCHED, False)
        assert cell.label_role == 'http://www.xbrl.org/2003/role/totalLabel'

    # Guards.

    def test_wrong_sign_under_a_negated_role_is_a_mismatch(self):
        facts = _with_fact(INNOVAGE, CAPEX, lambda f: f.update(numeric_value=-f['numeric_value']))
        cell = _cell(_compare(INNOVAGE, facts), CAPEX, '12 Months Ended Jun. 30, 2026', report=INNOVAGE_CASH)
        # The renderer would print 14,309 for -14,309,000 on this row; the page shows (14,309).
        assert (cell.status, cell.viewer_value, cell.xbrl_value, cell.difference) == (
            MISMATCHED, -14_309, -14_309, -28_618)

    def test_wrong_sign_under_a_plain_role_is_a_mismatch(self):
        concept = 'us-gaap:NetCashProvidedByUsedInOperatingActivities'
        facts = _with_fact(INNOVAGE, concept, lambda f: f.update(numeric_value=-f['numeric_value']))
        cell = _cell(_compare(INNOVAGE, facts), concept, '12 Months Ended Jun. 30, 2026', report=INNOVAGE_CASH)
        assert (cell.status, cell.negated, cell.sign_only) == (MISMATCHED, False, False)

    def test_wrong_sign_on_an_equity_row_is_a_mismatch(self):
        concept = 'us-gaap:TreasuryStockValueAcquiredCostMethod'
        facts = _with_fact(INNOVAGE, concept, lambda f: f.update(numeric_value=-f['numeric_value']))
        cell = _equity_cell(_compare(INNOVAGE, facts), concept, 'Shares repurchased at cost', 'Total')
        assert (cell.status, cell.xbrl_value) == (MISMATCHED, -7_321)

    def test_quoin_with_every_fact_negated_has_no_matches(self):
        facts = copy.deepcopy(_facts(QUOIN))
        for f in facts:
            f['numeric_value'] = -f['numeric_value']
        results = _compare(QUOIN, facts)
        assert (results.matched, results.sign_only_matches) == (0, 0)
        assert results.mismatched == results.total

    def test_unidentifiable_arc_is_sign_unverified_not_exact(self):
        # Capital expenditure presented twice under the same parent, once negated and once with a
        # terse label whose text is also the row's label: the page's one row could be either arc.
        presentation = _with_extra_arc(INNOVAGE, CAPEX, 'http://www.xbrl.org/2003/role/terseLabel')
        viewer, xbrl = _fixture_viewer(INNOVAGE, presentation=presentation)
        viewer._metalinks.get_tag(CAPEX.replace(':', '_')).role_labels['terseLabel'] = (
            'Purchases of property and equipment')
        results = compare_viewer_to_xbrl(viewer, xbrl)
        cell = _cell(results, CAPEX, '12 Months Ended Jun. 30, 2026', report=INNOVAGE_CASH)
        assert (cell.status, cell.sign_only, cell.negated, cell.label_role) == (MATCHED, True, None, None)
        assert cell.reason == ("sign not verified: the row may be any of the concept's arcs (negatedLabel, "
                               "terseLabel); some negate and some do not, and the page does not tell which this row is")
        assert results.sign_only_matches == 2 and results.exact_matches == results.matched - 2
        assert [r.label for r in results.sign_unverified] == ['Purchases of property and equipment'] * 2
        assert 'sign_unverified=2' in str(results)
        from rich.console import Console
        console = Console(record=True, width=160)
        console.print(results.__rich__())
        assert 'sign unverified 2' in console.export_text()
        df = results.to_dataframe()
        row = df[(df.concept_id == CAPEX) & (df.period == '12 Months Ended Jun. 30, 2026')].iloc[0]
        assert (bool(row.sign_only), row.negated, row.reason.startswith('sign not verified')) == (True, None, True)

    def test_unidentifiable_arc_still_checks_the_magnitude(self):
        presentation = _with_extra_arc(INNOVAGE, CAPEX, 'http://www.xbrl.org/2003/role/terseLabel')
        facts = _with_fact(INNOVAGE, CAPEX, lambda f: f.update(numeric_value=f['numeric_value'] + 1_000_000))
        viewer, xbrl = _fixture_viewer(INNOVAGE, facts=facts, presentation=presentation)
        viewer._metalinks.get_tag(CAPEX.replace(':', '_')).role_labels['terseLabel'] = (
            'Purchases of property and equipment')
        cell = _cell(compare_viewer_to_xbrl(viewer, xbrl), CAPEX, '12 Months Ended Jun. 30, 2026',
                     report=INNOVAGE_CASH)
        assert (cell.status, cell.sign_only) == (MISMATCHED, False)

    def test_label_text_identifies_the_arc_when_only_one_matches(self):
        # The second arc's label text is not the row's label, so the row is the negated arc.
        presentation = _with_extra_arc(INNOVAGE, CAPEX, '')
        viewer, xbrl = _fixture_viewer(INNOVAGE, presentation=presentation)
        cell = _cell(compare_viewer_to_xbrl(viewer, xbrl), CAPEX, '12 Months Ended Jun. 30, 2026',
                     report=INNOVAGE_CASH)
        assert (cell.status, cell.sign_only, cell.negated) == (MATCHED, False, True)

    def test_role_the_renderer_and_the_library_read_differently_is_sign_unverified(self):
        # A filer role ".../NegatedLabel": the library's rule negates it (local name starts with
        # "negated", case-insensitive); EdgarRenderer's ('negated' in role, case-sensitive) does not.
        role = 'http://www.innovage.com/role/NegatedLabel'
        presentation = _rewrite_arc_roles(copy.deepcopy(_presentation(INNOVAGE)), lambda child, pl: (
            role if (pl == NEGATED and child == CAPEX.replace(':', '_')) else pl))
        cell = _cell(_compare(INNOVAGE, presentation=presentation), CAPEX, '12 Months Ended Jun. 30, 2026',
                     report=INNOVAGE_CASH)
        assert (cell.status, cell.sign_only) == (MATCHED, True)
        assert cell.reason == (f"sign not verified: label role {role!r}: the library's negated-role rule "
                               "and the renderer's disagree on it")


class TestRound7SharedCurrencySymbol:

    def test_dollar_scale_that_is_usds_leaves_cad_in_units(self):
        # R2 "$ in Thousands": USD's facts there are all at decimals -3, CAD has decimals-0 facts
        # (Equity at Dec. 31, 2020 = 172,306,000), so the renderer scales USD only and prints CAD whole.
        results = _compare(NORTHERN_DYNASTY)
        cell = _cell(results, 'ifrs-full:RestrictedCashAndCashEquivalents', 'Dec. 31, 2021')
        assert (cell.viewer_value, cell.xbrl_value, cell.status, cell.xbrl_unit) == (785_000, 785_000, MATCHED, 'CAD')

    def test_same_header_means_cad_where_cad_is_scaled(self):
        # R3: every CAD fact is at decimals -3; net loss 31,542,000 prints 31,542.
        results = _compare(NORTHERN_DYNASTY)
        cell = _cell(results, 'ndm:NetLoss', '12 Months Ended Dec. 31, 2021', report='Comprehensive')
        assert (cell.viewer_value, cell.xbrl_value, cell.status) == (31_542, 31_542, MATCHED)
        assert results.mismatched == 0

    def test_report_currency_scaling_is_the_declared_one(self):
        viewer, _ = _fixture_viewer(NORTHERN_DYNASTY)
        assert [(r.short_name, r.currency_scaling) for r in viewer.financial_statements] == [
            ('Consolidated Statements of Financial Position', 1000),
            ('Consolidated Statements of Comprehensive Loss', 1000)]

    def test_cad_at_minus_three_everywhere_makes_r2_a_mismatch(self):
        # Guard: with every CAD fact at decimals -3 the rule scales CAD too, and R2's whole numbers no longer fit.
        facts = copy.deepcopy(_facts(NORTHERN_DYNASTY))
        for f in facts:
            if f['unit_ref'] == 'CAD':
                f['decimals'] = '-3'
        cell = _cell(_compare(NORTHERN_DYNASTY, facts), 'ifrs-full:RestrictedCashAndCashEquivalents', 'Dec. 31, 2021')
        assert (cell.status, cell.xbrl_value) == (MISMATCHED, 785)

    def test_rule_that_does_not_produce_the_declaration_is_not_comparable(self):
        # With USD's facts at decimals 0 as well, no "$" unit would be scaled, yet the page says "$ in Thousands".
        facts = copy.deepcopy(_facts(NORTHERN_DYNASTY))
        for f in facts:
            if f['unit_ref'] == 'USD':
                f['decimals'] = '0'
        cell = _cell(_compare(NORTHERN_DYNASTY, facts), 'ifrs-full:RestrictedCashAndCashEquivalents', 'Dec. 31, 2021')
        assert cell.status == NOT_COMPARABLE
        assert cell.reason == ("page declares '$ in ...' (1000) and CAD, USD all print as '$'; the renderer's rule "
                               "gives {'CAD': 1, 'USD': 1}, which does not produce the page's declaration, so which "
                               "unit is scaled is not settled")

    def test_thousandfold_error_on_a_single_currency_page_is_still_a_mismatch(self):
        facts = _with_fact(INNOVAGE, CAPEX, lambda f: f.update(numeric_value=f['numeric_value'] * 1000))
        cell = _cell(_compare(INNOVAGE, facts), CAPEX, '12 Months Ended Jun. 30, 2026', report=INNOVAGE_CASH)
        assert (cell.status, cell.xbrl_value) == (MISMATCHED, 14_309_000)


# ---------------------------------------------------------------------------
# Round 8.

ENTERGY = "0000065984-24-000112"  # 10-Q, nine months to 2024-09-30; R3 cash flows, one concept on two arcs
BLACKSTONE = "0001803498-26-000014"  # 10-K FY2025 BDC; R9 schedule of investments (parenthetical)
OTHER_INVESTING = 'us-gaap:PaymentsForProceedsFromOtherInvestingActivities'
ENTERGY_CASH = 'Consolidated Statements Of Cash Flows'
COMMITMENT = 'us-gaap:InvestmentCompanyFinancialCommitmentToInvesteeFutureAmount'
REVOLVERS = 'Delayed Draw Term Loans And Revolvers'


def _linkbase_trees(accession):
    """Presentation trees parsed from the fixture's presentation linkbase by the library's own parser."""
    from edgar.xbrl.parsers.presentation import PresentationParser
    trees = {}
    PresentationParser({}, trees, {}).parse_presentation_content(
        (HARNESS_DIR / accession / 'presentation_linkbase.xml').read_text())
    return trees


def _entergy(facts=None, linkbase=True):
    """Entergy compared on the parsed linkbase, or (``linkbase=False``) on tree nodes alone,
    as the library's nodes give them: one arc per child under a parent."""
    presentation = None if linkbase else {
        role: {k: v for k, v in tree.items() if k != 'relationships'}
        for role, tree in _presentation(ENTERGY).items()}
    viewer, xbrl = _fixture_viewer(ENTERGY, facts=facts, presentation=presentation)
    if linkbase:
        xbrl.presentation_trees = _linkbase_trees(ENTERGY)
    return compare_viewer_to_xbrl(viewer, xbrl)


class TestRound8:

    # Item 1: one currency under two unit ids does not share a symbol.

    def test_second_unit_id_for_one_currency_reads_the_declared_scale(self):
        # InnovAge R7 "$ in Thousands": capex refiled under unit U_USD at decimals 0, 1000x too small.
        def move(f):
            f.update(unit_ref='U_USD', decimals='0', numeric_value=f['numeric_value'] / 1000)
        cell = _cell(_compare(INNOVAGE, _with_fact(INNOVAGE, CAPEX, move)), CAPEX,
                     '12 Months Ended Jun. 30, 2026', report=INNOVAGE_CASH)
        assert (cell.status, cell.xbrl_value, cell.xbrl_unit, cell.note) == (MISMATCHED, 14.309, 'U_USD', None)

    def test_second_unit_id_for_one_currency_with_the_right_value_matches(self):
        def move(f):
            f.update(unit_ref='U_USD', decimals='0')
        cell = _cell(_compare(INNOVAGE, _with_fact(INNOVAGE, CAPEX, move)), CAPEX,
                     '12 Months Ended Jun. 30, 2026', report=INNOVAGE_CASH)
        assert (cell.status, cell.xbrl_value) == (MATCHED, 14_309)

    # Item 2: a concept presented twice under one parent with different label roles.

    def test_library_tree_nodes_keep_one_of_the_two_arcs(self):
        tree = next(iter(_linkbase_trees(ENTERGY).values()))
        element = OTHER_INVESTING.replace(':', '_')
        parent = next(n for n in tree.all_nodes.values() if element in n.children)
        assert parent.children.count(element) == 1
        arcs = sorted((r.order, r.preferred_label.rsplit('/', 1)[-1])
                      for r in tree.relationships if r.child_id == element)
        assert [role for _order, role in arcs] == ['negatedLabel', 'terseLabel']

    def test_both_arcs_from_the_linkbase_give_each_row_its_sign(self):
        # Entergy R3: the negatedLabel row prints 3,812 / (4,998), the terseLabel row (3,812) / 4,998;
        # the facts are -3,812,000 (sign="-") and 4,998,000.
        cells = _cells(_entergy(), OTHER_INVESTING, report=ENTERGY_CASH)
        consolidated = [c for c in cells if c.xbrl_dimensions == {}]
        assert [(c.period, c.viewer_value, c.xbrl_value, c.status, c.negated, c.sign_only) for c in consolidated] == [
            ('9 Months Ended Sep. 30, 2024', 3_812, -3_812, MATCHED, True, False),
            ('9 Months Ended Sep. 30, 2023', -4_998, 4_998, MATCHED, True, False),
            ('9 Months Ended Sep. 30, 2024', -3_812, -3_812, MATCHED, False, False),
            ('9 Months Ended Sep. 30, 2023', 4_998, 4_998, MATCHED, False, False)]
        assert all(c.status == MATCHED and not c.sign_only for c in cells) and len(cells) == 28

    def test_wrong_sign_on_either_arc_is_a_mismatch(self):
        facts = _with_fact(ENTERGY, OTHER_INVESTING, lambda f: f.update(numeric_value=-f['numeric_value']),
                           context_ref='c-1')
        cells = [c for c in _cells(_entergy(facts), OTHER_INVESTING, '9 Months Ended Sep. 30, 2024')
                 if c.xbrl_dimensions == {}]
        assert [(c.status, c.negated) for c in cells] == [(MISMATCHED, True), (MISMATCHED, False)]

    def test_more_rows_than_visible_arcs_is_sign_unverified_never_known(self):
        # The trees as the library's nodes give them (one arc): each row's sign is unverified.
        cells = [c for c in _cells(_entergy(linkbase=False), OTHER_INVESTING) if c.viewer_value]
        assert cells and all((c.status, c.sign_only, c.negated) == (MATCHED, True, None) for c in cells)
        assert cells[0].reason == ("sign not verified: the page shows 2 rows of the concept here and the "
                                   "presentation has 1 arc(s) for it, so which arc each row is cannot be told")

    # Item 3: a less precise duplicate must be the precise value rounded to its decimals.

    @pytest.mark.parametrize('precise, other_decimals, other', [
        (54_309_000.0, '-8', 14_309_000.0),   # 14,309,000 is not stated to decimals -8
        (14_800_000.0, '-6', 14_309_000.0),   # nor to decimals -6
        (14_800_000.0, '-6', 14_000_000.0),   # a multiple of 1e6, but 14,800,000 rounds to 15,000,000
    ])
    def test_duplicate_that_is_not_a_rounding_disagrees(self, precise, other_decimals, other):
        facts = []
        for f in _facts(INNOVAGE):
            if f['concept'] == CAPEX and f['period_key'] == 'duration_2025-07-01_2026-06-30':
                g = copy.deepcopy(f)
                g.update(decimals=other_decimals, numeric_value=other)
                f = dict(f, numeric_value=precise)
                facts += [f, g]
            else:
                facts.append(f)
        cell = _cell(_compare(INNOVAGE, facts), CAPEX, '12 Months Ended Jun. 30, 2026', report=INNOVAGE_CASH)
        assert (cell.status, cell.xbrl_value) == (MISMATCHED, precise / 1000)
        assert cell.note.startswith('duplicate facts disagree beyond their stated precision')

    def test_duplicate_that_is_a_rounding_is_still_interchangeable(self):
        facts = []
        for f in _facts(INNOVAGE):
            facts.append(f)
            if f['concept'] == CAPEX and f['period_key'] == 'duration_2025-07-01_2026-06-30':
                facts.append(dict(copy.deepcopy(f), decimals='-6', numeric_value=14_000_000.0))
        cell = _cell(_compare(INNOVAGE, facts), CAPEX, '12 Months Ended Jun. 30, 2026', report=INNOVAGE_CASH)
        assert (cell.status, cell.xbrl_value, cell.note) == (MATCHED, 14_309, None)

    # Item 4: numeric types by local name.

    @pytest.mark.parametrize('xbrltype, numeric', [
        ('candidateCountItemType', True), ('abc:tokenAmountItemType', True), ('ndm:durationRatioItemType', True),
        ('monetaryItemType', True), ('dtr-types:perShareItemType', True),
        ('dateItemType', False), ('xbrli:tokenItemType', False), ('nonnum:textBlockItemType', False),
        ('stringItemType', False), ('durationItemType', False), ('nonnum:extensibleListItemType', False),
        ('enumerationSetItemType', False), ('', False)])
    def test_numeric_type_is_read_from_the_local_name(self, xbrltype, numeric):
        from edgar.xbrl.viewer_validation import _is_numeric_type
        assert _is_numeric_type(xbrltype) is numeric

    def test_unreadable_cell_of_a_numeric_type_named_like_date_is_counted(self):
        page = (HARNESS_DIR / INNOVAGE / 'R7.htm').read_text()
        assert page.count('<td class="num">(14,309)<span></span>') == 1
        page = page.replace('<td class="num">(14,309)<span>', '<td class="num">n/a<span>')
        viewer, xbrl = _fixture_viewer(INNOVAGE, pages={'R7.htm': page})
        viewer._metalinks.get_tag(CAPEX.replace(':', '_')).xbrltype = 'candidateCountItemType'
        results = compare_viewer_to_xbrl(viewer, xbrl)
        cell = _cell(results, CAPEX, '12 Months Ended Jun. 30, 2026', report=INNOVAGE_CASH)
        assert (cell.status, cell.viewer_value) == (NOT_COMPARABLE, None)

    # Item 5: typed-dimension values.

    def test_typed_value_with_a_trailing_space_on_the_page_matches(self):
        # R9 heads the rows "Delayed Draw Term Loans And Revolvers " (trailing space); the facts,
        # 13,400,000,000 and 10,800,000,000, carry the value without it. The page is in thousands.
        results = _compare(BLACKSTONE)
        cells = [c for c in _cells(results, COMMITMENT)
                 if c.xbrl_dimensions == {'us-gaap:InvestmentIdentifierAxis': REVOLVERS}]
        assert [(c.period, c.viewer_value, c.xbrl_value, c.status) for c in cells] == [
            ('12 Months Ended Dec. 31, 2025', 13_400_000, 13_400_000, MATCHED),
            ('12 Months Ended Dec. 31, 2024', 10_800_000, 10_800_000, MATCHED)]

    def test_typed_value_differing_in_inner_whitespace_does_not_match(self):
        # The same filing has distinct contexts "Investment Three  Verdelite JV LP" and
        # "Investment Three Verdelite JV LP": inner whitespace is part of the value.
        facts = copy.deepcopy(_facts(BLACKSTONE))
        for f in facts:
            if f['concept'] == COMMITMENT and f['dimensions'].get('us-gaap:InvestmentIdentifierAxis') == REVOLVERS:
                f['dimensions']['us-gaap:InvestmentIdentifierAxis'] = 'Delayed Draw Term  Loans And Revolvers'
        results = _compare(BLACKSTONE, facts)
        cells = [c for c in _cells(results, COMMITMENT) if c.viewer_value in (13_400_000, 10_800_000)]
        assert [c.status for c in cells] == [MISSING, MISSING]


PHENIXFIN = "0001213900-25-120913"  # 10-K FY2025 BDC; R8 schedule of investments, a typed value with a colon
GENASYS = "0001437749-23-033895"    # 10-K FY2023; R6 equity, a concept on a negatedLabel and a label arc
THRYV = 'Thryv Holdings, Inc. - Media: Broadcasting & Subscription - Senior Secured First Lien Term Loan'
INVESTMENT_AXIS = 'us-gaap:InvestmentIdentifierAxis'
TAX_WITHHOLDING = 'us-gaap:AdjustmentsRelatedToTaxWithholdingForShareBasedCompensation'


def _thryv_cells(results):
    return [(c.concept_id, c.period, c.viewer_value, c.xbrl_value, c.status, c.sign_only) for c in results.results
            if c.xbrl_dimensions == {INVESTMENT_AXIS: THRYV}]


class TestRound9:
    """Round 9: typed values as the renderer writes them, equal duplicates, arcs by position."""

    # Item 1: the header id writes ':' as '_' (Common.xslt translate); the label keeps it.

    def test_typed_value_with_a_colon_matches(self):
        # R8 heads the rows "Investment, Identifier [Axis]: Thryv Holdings, Inc. - Media: Broadcasting &
        # Subscription - ..." with id "...Media_ Broadcasting...". Cost 2,009,375 at Sep. 30, 2025.
        assert _thryv_cells(_compare(PHENIXFIN)) == [
            ('us-gaap:InvestmentOwnedBalancePrincipalAmount', 'Sep. 30, 2025', 2_025_000, 2_025_000, MATCHED, False),
            ('us-gaap:InvestmentOwnedAtCost', 'Sep. 30, 2025', 2_009_375, 2_009_375, MATCHED, False),
            ('us-gaap:InvestmentOwnedAtFairValue', 'Sep. 30, 2025', 2_027_531, 2_027_531, MATCHED, False)]

    def test_underscore_value_is_not_the_colon_header(self):
        # A fact value with a literal '_' has the header's id form, but the label shows ':'.
        facts = copy.deepcopy(_facts(PHENIXFIN))
        for f in facts:
            if f['dimensions'].get(INVESTMENT_AXIS) == THRYV:
                f['dimensions'][INVESTMENT_AXIS] = THRYV.replace(':', '_')
        results = _compare(PHENIXFIN, facts)
        # 2,009,375 is printed twice: under the issuer's subtotal header "Thryv Holdings, Inc."
        # (matched) and under the loan's header, which the '_' value does not fit.
        cells = [c for c in _cells(results, 'us-gaap:InvestmentOwnedAtCost', 'Sep. 30, 2025')
                 if c.viewer_value == 2_009_375]
        assert [(c.status, c.xbrl_dimensions) for c in cells] == [
            (MATCHED, {INVESTMENT_AXIS: 'Thryv Holdings, Inc.'}), (NOT_COMPARABLE, None)]
        assert 'is not what its label shows' in cells[1].reason

    def test_colon_value_is_taken_beside_an_underscore_value(self):
        # Both values on the axis: only the ':' one fits the label too.
        facts = copy.deepcopy(_facts(PHENIXFIN))
        facts += [dict(copy.deepcopy(f), numeric_value=1.0, context_ref=f['context_ref'] + '_underscore',
                       dimensions={**f['dimensions'], INVESTMENT_AXIS: THRYV.replace(':', '_')})
                  for f in facts if f['dimensions'].get(INVESTMENT_AXIS) == THRYV]
        assert [cell[4] for cell in _thryv_cells(_compare(PHENIXFIN, facts))] == [MATCHED] * 3

    def test_typed_header_value_needs_both_forms(self):
        from edgar.xbrl.viewer_validation import _typed_header_value
        label = 'Investment, Identifier [Axis]: A: B'
        assert _typed_header_value('A_ B', label, {'A: B', 'A_ B'}) == ('A: B', None)
        assert _typed_header_value('A_ B', 'Investment, Identifier [Axis]: A_ B', {'A: B', 'A_ B'}) == ('A_ B', None)
        # No value fits either form: the id's value, which names no fact (the rows are missing).
        assert _typed_header_value('C ', 'Investment, Identifier [Axis]: C', {'A: B'}) == ('C', None)
        value, reason = _typed_header_value('A_ B', label, {'A_ B'})
        assert value is None and 'is not what its label shows' in reason

    # Item 2: an identical duplicate agrees whatever decimals it states.

    def test_identical_duplicate_at_coarser_decimals_agrees(self):
        # InnovAge capex 14,309,000 at decimals -3, and an identical copy at -6.
        facts = []
        for f in _facts(INNOVAGE):
            facts.append(f)
            if f['concept'] == CAPEX and f['period_key'] == 'duration_2025-07-01_2026-06-30':
                assert (f['numeric_value'], f['decimals']) == (14_309_000.0, '-3')
                facts.append(dict(copy.deepcopy(f), decimals='-6'))
        cell = _cell(_compare(INNOVAGE, facts), CAPEX, '12 Months Ended Jun. 30, 2026', report=INNOVAGE_CASH)
        assert (cell.status, cell.xbrl_value, cell.note) == (MATCHED, 14_309, None)

    def test_identical_values_are_a_rounding(self):
        from edgar.xbrl.viewer_validation import _is_rounding_of
        coarse = SimpleNamespace(numeric_value=14_309_000.0, decimals='-6')
        precise = SimpleNamespace(numeric_value=14_309_000.0, decimals='-3')
        assert _is_rounding_of(coarse, precise)

    # Item 3: fixtures carry the presentation network, as live trees do.

    def test_every_fixture_records_its_relationships(self):
        missing = [d.name for d in HARNESS_DIR.iterdir() if (d / 'presentation.json').exists()
                   for role, tree in _presentation(d.name).items() if 'relationships' not in tree]
        assert missing == []

    # Item 4: a concept on two arcs under one parent, read by its place in the period block.

    def test_each_row_takes_the_sign_of_its_arc(self):
        # Genasys R6: "Shares retained for payment of taxes..." is presented first on a negatedLabel
        # arc, then on a label arc. Each year's block prints one row at each: (70) then 70 for fiscal
        # 2022, (45) then 45 for fiscal 2023; the facts are 70,000 and 45,000, shown in thousands.
        cells = _cells(_compare(GENASYS), TAX_WITHHOLDING)
        assert [(c.viewer_value, c.xbrl_value, c.negated, c.status, c.sign_only) for c in cells] == [
            (-70, 70, True, MATCHED, False), (-70, 70, True, MATCHED, False),
            (70, 70, False, MATCHED, False), (70, 70, False, MATCHED, False),
            (-45, 45, True, MATCHED, False), (-45, 45, True, MATCHED, False),
            (45, 45, False, MATCHED, False), (45, 45, False, MATCHED, False)]

    def test_a_row_on_the_wrong_arc_role_is_a_sign_mismatch(self):
        # Rewrite the plain arc as negated: the renderer would print (70), so the page's 70 is wrong.
        rewritten = _rewrite_arc_roles(_presentation(GENASYS), lambda child, pl: (
            NEGATED if child == TAX_WITHHOLDING.replace(':', '_') else pl))
        cells = _cells(_compare(GENASYS, presentation=rewritten), TAX_WITHHOLDING)
        assert [(c.viewer_value, c.status) for c in cells] == [
            (-70, MATCHED), (-70, MATCHED), (70, MISMATCHED), (70, MISMATCHED),
            (-45, MATCHED), (-45, MATCHED), (45, MISMATCHED), (45, MISMATCHED)]
