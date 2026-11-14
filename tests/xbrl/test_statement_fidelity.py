"""
Statement fidelity (``compare_statements_to_viewer``) on trimmed real filings, offline.

The fixtures under tests/fixtures/statement-fidelity are trimmed, verbatim SEC
files (see that directory's README). Each fixture's outcomes were checked to be
identical, outcome for outcome, to the same page's outcomes on the live filing.

Most tests here pin findings: library behaviour the check observed on a real
filing that it must keep reporting. They assert what the check reports today,
not what the library should do. When the library changes, a finding test fails
and the bead that tracks the behaviour says whether that was the fix.
"""
import copy
import json
import math
from collections import Counter
from types import SimpleNamespace

import pytest

from edgar.xbrl import statement_fidelity as sf
from edgar.xbrl import viewer_validation as vv
from edgar.xbrl.statement_fidelity import (
    DISAGREEMENT,
    FAMILIES,
    KINDS,
    MATCHED,
    NOT_COMPARABLE,
    PRESENTATION,
    StatementFidelityResults,
)
from tests.xbrl.statement_fidelity_fixtures import FIXTURE_DIR, fixture_viewer_and_xbrl

ENTERGY = "0000065984-24-000112"
BHE = "0001081316-24-000016"
DRDGOLD = "0001562762-22-000397"
GRANITESHARES = "0001493152-26-037707"
BRIXMOR = "0001581068-21-000012"
CHINDATA = "0001564590-22-016827"
GOOD_TIMES = "0001214659-22-006372"
DIAMONDROCK = "0001298946-24-000052"

_RESULTS = {}


def results(accession) -> StatementFidelityResults:
    if accession not in _RESULTS:
        viewer, xbrl = fixture_viewer_and_xbrl(accession)
        _RESULTS[accession] = viewer.compare_statements(xbrl)
    return _RESULTS[accession]


def find(res, kind, surface=None, **fields):
    return [r for r in res.of_kind(kind, surface) if all(getattr(r, k) == v for k, v in fields.items())]


# ---------------------------------------------------------------------------
# The kinds and families

def test_every_kind_is_in_one_family():
    families = [kind for kinds in FAMILIES.values() for kind in kinds]
    assert sorted(families) == sorted(KINDS)
    assert set(FAMILIES) == {MATCHED, DISAGREEMENT, PRESENTATION, NOT_COMPARABLE}


def test_unknown_kind_or_surface_raises():
    res = results(GOOD_TIMES)
    with pytest.raises(ValueError, match="unknown kind 'cell_ok'"):
        res.of_kind('cell_ok')
    with pytest.raises(ValueError, match="unknown surface 'html'"):
        res.value_rate('html')


@pytest.mark.parametrize("accession", sorted(p.name for p in FIXTURE_DIR.iterdir() if p.is_dir()))
def test_fixture_reaches_the_page_statement_as_live(accession):
    """The trimmed XBRL resolves the page's statement the way the live filing does."""
    manifest = json.loads((FIXTURE_DIR / accession / "manifest.json").read_text())
    pages = results(accession).pages
    assert [(p.page, p.access, p.compared) for p in pages] == [(manifest["short_name"], manifest["access"], True)]


# ---------------------------------------------------------------------------
# A clean statement

def test_clean_statement_good_times_cash_flows():
    """Good Times 10-Q (0001214659-22-006372), cash flows: every cell and row matches, both surfaces."""
    res = results(GOOD_TIMES)
    assert res.facts.total == 54
    for surface in ('dataframe', 'rendered'):
        assert res.compared_cells(surface) == 54
        assert res.value_rate(surface) == 1.0
        assert res.coverage(surface) == 1.0
        assert len(res.of_kind('row_matched', surface)) == 32
    assert {r.family for r in res.results} == {MATCHED}
    net_income = find(res, 'cell_matched', 'dataframe', concept='us-gaap:ProfitLoss',
                      period_key='duration_2021-09-29_2022-03-29')
    # R6.htm prints "$ (670)" (thousands) for the six months ended Mar. 29, 2022
    assert [(r.page_value, r.fact_value, r.library_value) for r in net_income] == [(-670.0, -670000.0, -670000.0)]


# ---------------------------------------------------------------------------
# Findings the check must keep reporting. When a bead is fixed, its test changes to
# assert the matched outcome; it must not be deleted.

def test_finding_entergy_second_row_of_a_concept_is_dropped():
    """Entergy 10-Q (0000065984-24-000112), cash flows: the page shows
    PaymentsForProceedsFromOtherInvestingActivities twice in every entity's
    section (two presentation arcs); the library shows it once.
    Bead: edgartools-auvk1.7."""
    res = results(ENTERGY)
    for surface in ('dataframe', 'rendered'):
        dropped = find(res, 'row_dropped', surface, concept='us-gaap:PaymentsForProceedsFromOtherInvestingActivities')
        assert len(dropped) == 7
        assert {r.occurrence for r in dropped} == {1}
        assert {} in [r.dimensions for r in dropped]
        assert {'dei:LegalEntityAxis': 'etr:EntergyNewOrleansMember'} in [r.dimensions for r in dropped]


def test_finding_entergy_negative_zero():
    """Entergy 10-Q, cash flows: Entergy New Orleans' 2024 year-to-date other investing
    activities are 0 on the page and -0.0 in the library, on both surfaces. Bead: edgartools-auvk1.12."""
    res = results(ENTERGY)
    for surface in ('dataframe', 'rendered'):
        [cell] = find(res, 'negative_zero', surface, concept='us-gaap:PaymentsForProceedsFromOtherInvestingActivities',
                      period_key='duration_2024-01-01_2024-09-30')
        assert cell.dimensions == {'dei:LegalEntityAxis': 'etr:EntergyNewOrleansMember'}
        assert cell.page_value == 0.0
        assert cell.library_value == 0.0 and math.copysign(1.0, cell.library_value) == -1.0


def test_finding_entergy_zero_rendered_blank():
    """Entergy 10-Q, cash flows: the page shows 0 for 2023 year-to-date noncash pension
    expense; the rendered table prints nothing. Bead: edgartools-auvk1.12."""
    res = results(ENTERGY)
    [cell] = find(res, 'zero_rendered_blank', 'rendered', concept='us-gaap:PensionExpenseReversalOfExpenseNoncash',
                  period_key='duration_2023-01-01_2023-09-30', dimensions={})
    assert cell.page_value == 0.0
    assert cell.library_value == 0.0
    assert cell.library_text == ''
    assert not find(res, 'zero_rendered_blank', 'dataframe')


def test_finding_entergy_period_not_in_default_view():
    """Entergy 10-Q, cash flows: the page's Dec. 31, 2023 cash balance column is not in
    the DataFrame's default view; requested alone, the library shows the value. Bead: none (presentation difference, not a defect)."""
    res = results(ENTERGY)
    kw = dict(concept='us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
              period_key='instant_2023-12-31', dimensions={})
    [missing] = find(res, 'period_not_in_default_view', 'dataframe', **kw)
    assert missing.default_view is False and missing.page_value == 132548.0
    [matched] = find(res, 'cell_matched', 'dataframe', **kw)
    assert matched.default_view is False
    assert matched.library_value == 132548000.0


def test_entergy_headline():
    res = results(ENTERGY)
    assert res.facts.total == 560
    assert res.compared_cells('dataframe') == 546
    assert len(res.of_kind('cell_matched', 'dataframe')) == 542
    assert len(res.of_kind('cell_matched', 'rendered')) == 528


def test_finding_bhe_parenthetical_sign():
    """Berkshire Hathaway Energy 10-Q (0001081316-24-000016), comprehensive income
    (parenthetical), reached through comprehensive_income(parenthetical=True): the page
    shows the Q2 2024 pension OCI tax as 1 (a negated label); the library shows
    -1,000,000. Bead: edgartools-auvk1.13."""
    res = results(BHE)
    for surface in ('dataframe', 'rendered'):
        [cell] = find(res, 'sign_differs', surface,
                      concept='us-gaap:OtherComprehensiveIncomeLossPensionAndOtherPostretirementBenefitPlansTax',
                      period_key='duration_2024-04-01_2024-06-30')
        assert (cell.page_value, cell.fact_value, cell.library_value) == (1.0, -1000000.0, -1000000.0)
        assert cell.reason == 'label role http://www.xbrl.org/2009/role/negatedTerseLabel'


def test_finding_drdgold_access_path_sign():
    """DRDGOLD 20-F (0001562762-22-000397): income_statement() shows FY2022 cost of sales
    as -3,741,500,000, as the page signs it; the same statement by role shows
    +3,741,500,000. Bead: edgartools-auvk1.13."""
    res = results(DRDGOLD)
    kw = dict(concept='ifrs-full:CostOfSales', period_key='duration_2021-07-01_2022-06-30')
    [cell] = find(res, 'access_path_disagrees', 'dataframe', **kw)
    assert (cell.page_value, cell.library_value) == (-3741.5, -3741500000.0)
    assert cell.reason == 'statements[role] shows 3741500000.0'
    assert find(res, 'cell_matched', 'dataframe', **kw)
    assert res.pages[0].access == 'income_statement()'


def test_finding_graniteshares_label():
    """GraniteShares Gold Trust 10-K (0001493152-26-037707), assets and liabilities: the page
    labels InvestmentInPhysicalCommodities "Investment in gold bullion, at fair value";
    the library "Long-Term Investments". Bead: edgartools-b4a12."""
    res = results(GRANITESHARES)
    for surface in ('dataframe', 'rendered'):
        [row] = find(res, 'label_differs', surface, concept='us-gaap:InvestmentInPhysicalCommodities')
        assert row.page_label == 'Investment in gold bullion, at fair value'
        assert row.library_label == 'Long-Term Investments'


def test_finding_brixmor_beginning_balance_shows_closing_balance():
    """Brixmor 10-K (0001581068-21-000012), cash flows: under the beginning-of-period row,
    the Brixmor Operating Partnership row shows 360,073,000 for 2020 where the page
    shows the opening 21,507; for 2019 it shows 21,507,000, the page's 2020 opening
    balance (the 2019 closing balance). Bead: edgartools-auvk1.14."""
    res = results(BRIXMOR)
    kw = dict(concept='us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
              dimensions={'srt:ConsolidatedEntitiesAxis': 'srt:SubsidiariesMember'})
    [y2020] = find(res, 'value_differs', 'dataframe', period_key='duration_2020-01-01_2020-12-31', **kw)
    assert (y2020.page_value, y2020.fact_value, y2020.library_value) == (21507.0, 21507000.0, 360073000.0)
    assert y2020.page_label == 'Cash, cash equivalents and restricted cash at beginning of period'
    [y2019] = find(res, 'value_differs', 'dataframe', period_key='duration_2019-01-01_2019-12-31', **kw)
    assert (y2019.page_value, y2019.library_value) == (50639.0, 21507000.0)


def test_finding_chindata_unit_column():
    """Chindata 20-F (0001564590-22-016827), balance sheet: the page's USD convenience column
    shows cash of 688,933 (thousands of USD); the library's row for that date shows the
    RMB fact. Bead: none (presentation difference, not a defect)."""
    res = results(CHINDATA)
    for surface in ('dataframe', 'rendered'):
        [cell] = find(res, 'unit_column_not_shown', surface, concept='us-gaap:CashAndCashEquivalentsAtCarryingValue',
                      column='Dec. 31, 2021 (1)')
        assert (cell.page_value, cell.fact_value, cell.library_value) == (688933.0, 688933000.0, 4390293000.0)
        assert cell.reason == 'page unit U_iso4217USD, library row unit U_iso4217CNY'


def test_cell_is_judged_under_its_column_period_with_the_fact_period_beside():
    """DiamondRock 10-Q (0001298946-24-000052), balance sheet parenthetical: R3 heads the first column
    "3 Months Ended / Mar. 31, 2024" and prints 210,064,433 common shares issued, a fact for the instant
    Mar. 31, 2024. Requesting the column's period (duration 2024-01-01 to 2024-03-31) the library shows
    no value: value_not_shown. Beside it, the library shows the fact under its own instant."""
    res = results(DIAMONDROCK)
    for surface in ('dataframe', 'rendered'):
        [blank] = find(res, 'value_not_shown', surface, concept='us-gaap:CommonStockSharesIssued',
                       column='3 Months Ended Mar. 31, 2024')
        assert (blank.period_key, blank.page_value, blank.fact_value) == (
            'duration_2024-01-01_2024-03-31', 210064433.0, 210064433.0)
        assert not find(res, 'cell_matched', surface, concept='us-gaap:CommonStockSharesIssued',
                        column='3 Months Ended Mar. 31, 2024')
        [beside] = find(res, 'shown_under_fact_period', surface, concept='us-gaap:CommonStockSharesIssued',
                        column='3 Months Ended Mar. 31, 2024')
        assert (beside.period_key, beside.library_value) == ('instant_2024-03-31', 210064433.0)
    # The Dec. 31, 2023 column is the fact's own instant: matched.
    [dec] = find(res, 'cell_matched', 'dataframe', concept='us-gaap:CommonStockSharesIssued',
                 column='Dec. 31, 2023')
    assert dec.library_value == 209627197.0


# ---------------------------------------------------------------------------
# The facts check's new fields

def test_facts_check_cell_fields():
    """compare() cells carry their row, the column's own period and the paired fact's value;
    the new DataFrame columns follow the existing ones."""
    res = results(CHINDATA)
    frame = res.facts.to_dataframe()
    assert list(frame.columns[-4:]) == ['row_index', 'row_occurrence', 'column_period_key', 'xbrl_fact_value']
    [cell] = [r for r in res.facts.results
              if r.concept_id == 'us-gaap:CashAndCashEquivalentsAtCarryingValue' and r.period == 'Dec. 31, 2021 (1)']
    assert (cell.column_period_key, cell.xbrl_fact_value, cell.row_occurrence) == (
        'instant_2021-12-31', 688933000.0, 0)


# ---------------------------------------------------------------------------
# Mutation tests: a library error injected into what the check reads must come out
# as a disagreement. Each mutates the rows a surface reads from the real Statement.


PROFIT_LOSS = 'us-gaap:ProfitLoss'
DEPRECIATION = 'us-gaap:DepreciationAndAmortization'
CASH = 'us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents'
SUBSIDIARIES = {'srt:ConsolidatedEntitiesAxis': 'srt:SubsidiariesMember'}


def mutated(monkeypatch, accession, mutate, surfaces=('dataframe',)):
    """Results with ``mutate(rows, kind, period_filter)`` applied to every read of the named surfaces."""
    originals = {'dataframe': sf._Surface._read_dataframe, 'rendered': sf._Surface._read_rendered}

    def wrap(kind):
        def read(self, statement, names, tree_ids, period_filter):
            originals[kind](self, statement, names, tree_ids, period_filter)
            mutate(self.rows, kind, period_filter)
        return read

    for kind in surfaces:
        monkeypatch.setattr(sf._Surface, f'_read_{kind}', wrap(kind))
    viewer, xbrl = fixture_viewer_and_xbrl(accession)
    return viewer.compare_statements(xbrl), xbrl


def rows_of(rows, concept, dims=frozenset()):
    return [r for r in rows if r['concept'] == concept and r['dims'] == dims and not r['abstract']]


def disagreements(res, surface='dataframe', concept=None):
    return Counter(r.kind for r in res.results
                   if r.family == DISAGREEMENT and r.surface == surface and (concept is None or r.concept == concept))



def test_mutation_wrong_value(monkeypatch):
    def mutate(rows, kind, period_filter):
        [row] = rows_of(rows, PROFIT_LOSS)
        row['values'] = {k: (v * 2 if sf._number(v) else v) for k, v in row['values'].items()}
    res, _ = mutated(monkeypatch, GOOD_TIMES, mutate)
    assert disagreements(res, concept=PROFIT_LOSS) == Counter(value_differs=2)
    assert res.value_rate('dataframe') == 52 / 54


def test_mutation_wrong_sign(monkeypatch):
    def mutate(rows, kind, period_filter):
        [row] = rows_of(rows, PROFIT_LOSS)
        row['values'] = {k: (-v if sf._number(v) else v) for k, v in row['values'].items()}
    res, _ = mutated(monkeypatch, GOOD_TIMES, mutate)
    assert disagreements(res, concept=PROFIT_LOSS) == Counter(sign_differs=2)


def test_mutation_swapped_columns(monkeypatch):
    def mutate(rows, kind, period_filter):
        if period_filter:
            return  # the default view's two columns are swapped; a single-period request has one
        [row] = rows_of(rows, DEPRECIATION)
        first, second = list(row['values'])
        row['values'] = {first: row['values'][second], second: row['values'][first]}
    res, _ = mutated(monkeypatch, GOOD_TIMES, mutate)
    assert disagreements(res, concept=DEPRECIATION) == Counter(value_differs=2)


def test_mutation_dropped_row(monkeypatch):
    def mutate(rows, kind, period_filter):
        rows.remove(rows_of(rows, PROFIT_LOSS)[0])
    res, _ = mutated(monkeypatch, GOOD_TIMES, mutate)
    assert disagreements(res, concept=PROFIT_LOSS) == Counter(row_dropped=1)


@pytest.mark.parametrize('position', ['before', 'after'])
def test_mutation_duplicated_row(monkeypatch, position):
    def mutate(rows, kind, period_filter):
        [row] = rows_of(rows, DEPRECIATION)
        i = rows.index(row)
        rows.insert(i if position == 'before' else i + 1, copy.deepcopy(row))
    res, _ = mutated(monkeypatch, GOOD_TIMES, mutate)
    assert disagreements(res, concept=DEPRECIATION) == Counter(duplicate_library_row=1)


def test_mutation_swapped_rows_of_a_repeated_concept(monkeypatch):
    """Brixmor shows plain cash at the beginning and the end of the period: swap the library's two rows."""
    def mutate(rows, kind, period_filter):
        first, second = rows_of(rows, CASH)[:2]
        i, j = rows.index(first), rows.index(second)
        rows[i], rows[j] = second, first
    res, _ = mutated(monkeypatch, BRIXMOR, mutate)
    assert disagreements(res, concept=CASH) == Counter(value_differs=9, label_differs=2)


def test_mutation_same_currency_other_unit_id_1000x(monkeypatch):
    """A row in USD under another unit id and 1000x off is a value difference, not a unit column."""
    def mutate(rows, kind, period_filter):
        [row] = rows_of(rows, PROFIT_LOSS)
        if kind == 'rendered':
            row['units'] = {k: 'U_USD_other' for k in row['units']}
        else:
            row['values'] = {k: (v * 1000 if sf._number(v) else v) for k, v in row['values'].items()}
    originals = sf._Surface._read_dataframe, sf._Surface._read_rendered
    res, xbrl = mutated(monkeypatch, GOOD_TIMES, mutate, surfaces=('dataframe', 'rendered'))
    assert originals  # the surfaces were wrapped
    [cell] = [r for r in res.of_kind('value_differs', 'dataframe') if r.concept == PROFIT_LOSS][:1]
    paired_unit = cell.fact.xbrl_unit
    # The new unit id measures what the paired fact's unit measures.
    xbrl.units['U_USD_other'] = dict(xbrl.units[paired_unit])
    viewer, _ = fixture_viewer_and_xbrl(GOOD_TIMES)
    res = sf.compare_statements_to_viewer(viewer, xbrl)
    assert disagreements(res, concept=PROFIT_LOSS)['value_differs'] == 2
    assert not [r for r in res.of_kind('unit_column_not_shown') if r.concept == PROFIT_LOSS]


def test_mutation_blank_under_a_column_outside_the_default_view(monkeypatch):
    """Entergy's Dec. 31, 2023 cash is requested with period_filter; blank it there."""
    def mutate(rows, kind, period_filter):
        if period_filter == 'instant_2023-12-31':
            [row] = rows_of(rows, CASH)[:1]
            row['values'] = {k: None for k in row['values']}
    res, _ = mutated(monkeypatch, ENTERGY, mutate)
    blank = find(res, 'value_not_shown', 'dataframe', concept=CASH, period_key='instant_2023-12-31', dimensions={})
    assert len(blank) == 1
    assert not find(res, 'cell_matched', 'dataframe', concept=CASH, period_key='instant_2023-12-31', dimensions={})


def test_mutation_unaligned_first_row_does_not_shift_the_rows_after_it(monkeypatch):
    """Brixmor, Operating Partnership cash: when the facts check matches none of the beginning row's
    cells, the end-of-period row still aligns with the library's end row (occurrence 1), not with its
    beginning row (which shows the closing balance, bead edgartools-auvk1.14)."""
    original = vv._facts_check

    def facts_check(viewer, xbrl, tolerance=None):
        check = original(viewer, xbrl, tolerance)
        rows = sorted({r.row_index for r in check.results.results
                       if r.concept_id == CASH and r.xbrl_dimensions == SUBSIDIARIES})
        for r in check.results.results:
            if r.row_index == rows[0]:
                r.status = vv.NOT_COMPARABLE
        return check

    monkeypatch.setattr(vv, '_facts_check', facts_check)
    viewer, xbrl = fixture_viewer_and_xbrl(BRIXMOR)
    res = viewer.compare_statements(xbrl)
    matched = {r.occurrence for r in find(res, 'row_matched', 'dataframe', concept=CASH, dimensions=SUBSIDIARIES)}
    assert 0 not in matched and 1 in matched
    not_comparable = [r.occurrence for r in res.of_kind('row_not_comparable')
                      if r.concept == CASH and r.dimensions == SUBSIDIARIES]
    assert 0 in not_comparable and 1 not in not_comparable
    assert not [r for r in res.results if r.concept == CASH and r.dimensions == SUBSIDIARIES
                and r.kind in ('extra_row_in_role', 'duplicate_library_row')]


def test_guide_example_value_differs_offline():
    """The guide's Brixmor example (docs/guides/sec-viewer-guide.md). The fixture holds only the cash
    flow page, so the rate and coverage lines (all pages) are not reproducible offline; its first
    value_differs, which is on that page, is."""
    res = results(BRIXMOR)
    r = res.of_kind('value_differs', 'dataframe')[0]
    assert (r.page, r.page_label, r.library_label) == (
        'CONSOLIDATED STATEMENTS OF CASH FLOWS', 'Cash, cash equivalents and restricted cash at beginning of period',
        'Brixmor Operating Partnership LP')
    assert (r.column, r.page_value, r.fact_value, r.library_value) == (
        '12 Months Ended Dec. 31, 2020', 21507.0, 21507000.0, 360073000.0)


def test_merged_rows_names_the_row_the_library_kept():
    """CSC 10-K (0001688568-20-000032) files "Property and equipment, net" as a dxc: extension for
    2020 and as us-gaap:PropertyPlantAndEquipmentNet for 2019; the page shows two rows and the library
    merges them (_merge_complementary_rows). Replayed here on the two rows' shape."""
    label = 'Property and equipment, net'
    items = [
        {'concept': 'dxc_PropertyPlantandEquipmentNet', 'label': label, 'level': 2, 'is_abstract': False,
         'is_dimension': False, 'values': {'instant_2020-03-31': 3547000000.0},
         'period_types': {'instant_2020-03-31': 'instant'}},
        {'concept': 'us-gaap_PropertyPlantAndEquipmentNet', 'label': label, 'level': 2, 'is_abstract': False,
         'is_dimension': False, 'values': {'instant_2019-03-31': 3179000000.0},
         'period_types': {'instant_2019-03-31': 'instant'}},
    ]
    calls = []

    def get_statement(identifier, *args, **kwargs):
        calls.append((identifier, args, kwargs))
        return items
    statement = SimpleNamespace(canonical_type='BalanceSheet', role_or_type='role', _view=None,
                                xbrl=SimpleNamespace(get_statement=get_statement))
    expected = {'us-gaap:PropertyPlantAndEquipmentNet': 'dxc:PropertyPlantandEquipmentNet'}
    assert sf._merged_rows(statement, 'dataframe') == expected
    assert sf._merged_rows(statement, 'rendered', 'instant_2020-03-31') == expected
    # Each surface's replay reads the line items as that surface does: its view and period.
    from edgar.xbrl.presentation import StatementView
    assert calls == [('BalanceSheet', (), {'period_filter': None, 'view': StatementView.DETAILED}),
                     ('BalanceSheet', ('instant_2020-03-31', True), {'view': StatementView.STANDARD})]


def _raising(message, only_period_requests=False):
    from edgar.xbrl.statements import Statement
    original = Statement.to_dataframe

    def to_dataframe(self, *args, **kwargs):
        if not only_period_requests or kwargs.get('period_filter'):
            raise TypeError(message)
        return original(self, *args, **kwargs)
    return to_dataframe


def test_library_raised_on_the_page_counts_in_value_rate(monkeypatch):
    """A Statement whose to_dataframe() raises (as Photozou 0001599916-23-000056's balance sheet does,
    auvk1.19) is a disagreement on every cell the check would have looked up, never not comparable."""
    from edgar.xbrl.statements import Statement
    rendered_rate = results(GOOD_TIMES).value_rate('rendered')
    monkeypatch.setattr(Statement, 'to_dataframe', _raising('boom'))
    viewer, xbrl = fixture_viewer_and_xbrl(GOOD_TIMES)
    res = viewer.compare_statements(xbrl)
    raised = res.of_kind('statement_raised', 'dataframe')
    # The typed getter's statement, and the statement by role read for access_path_disagrees.
    assert [r.reason for r in raised] == [
        'statements[role].to_dataframe() raised TypeError: boom; the page is compared through '
        'cash_flow_statement(), and access_path_disagrees is not checked',
        'to_dataframe() raised TypeError: boom']
    assert raised[0].family == DISAGREEMENT and raised[0].level == 'page'
    cells = res.of_kind('library_raised', 'dataframe')
    assert len(cells) == 54 and {r.reason for r in cells} == {'to_dataframe() raised TypeError: boom'}
    assert res.compared_cells('dataframe') == 54
    assert res.value_rate('dataframe') == 0.0
    assert not res.of_kind('page_not_compared', 'dataframe')
    # The rendered table does not call to_dataframe(): its outcomes are the fixture's own.
    assert res.value_rate('rendered') == rendered_rate


def test_library_raised_on_a_period_request(monkeypatch):
    """DiamondRock 10-K (0001298946-24-000052): 10 of its 19 compared DataFrame cells are under periods the
    default view leaves out. When requesting a period alone raises, those 10 are library_raised and the 9
    in the default view are still compared there."""
    from edgar.xbrl.statements import Statement
    monkeypatch.setattr(Statement, 'to_dataframe', _raising('period boom', only_period_requests=True))
    viewer, xbrl = fixture_viewer_and_xbrl(DIAMONDROCK)
    res = viewer.compare_statements(xbrl)
    cells = res.of_kind('library_raised', 'dataframe')
    assert len(cells) == 10
    assert all(r.reason == f"to_dataframe(period_filter={r.period_key}) raised TypeError: period boom" for r in cells)
    assert [r.default_view for r in res.of_kind('cell_matched', 'dataframe')] == [True] * 9
    assert res.compared_cells('dataframe') == 19
    assert res.value_rate('dataframe') == 9 / 19


def test_default_view_is_read_before_a_period_request(monkeypatch):
    """Good Times shows every compared period in the default view: a period request that raises is never made."""
    from edgar.xbrl.statements import Statement
    monkeypatch.setattr(Statement, 'to_dataframe', _raising('period boom', only_period_requests=True))
    viewer, xbrl = fixture_viewer_and_xbrl(GOOD_TIMES)
    res = viewer.compare_statements(xbrl)
    assert not res.of_kind('library_raised')
    assert len(res.of_kind('cell_matched', 'dataframe')) == 54 and res.value_rate('dataframe') == 1.0


def test_dataframe_column_names_match_the_library():
    """The check's replay of to_dataframe()'s column naming, against the library on every period it shows."""
    checked, raised = 0, []
    for accession in (DIAMONDROCK, ENTERGY, GOOD_TIMES):
        viewer, xbrl = fixture_viewer_and_xbrl(accession)
        keys = [p['key'] for p in xbrl.reporting_periods]
        for page in results(accession).pages:
            if not page.compared:
                continue
            statement = xbrl.statements[page.role]
            for key in keys:
                try:
                    frame = statement.to_dataframe(period_filter=key)
                except TypeError:
                    raised.append((accession, page.page, key))  # a library error, not the naming
                    continue
                columns = [c for c in frame.columns if c not in sf._DATAFRAME_METADATA] if len(frame) else []
                if len(columns) == 1:
                    assert columns[0] == sf._dataframe_column(xbrl, key), (accession, page.page, key)
                    checked += 1
    assert checked == 28
    # Requesting an instant alone on Good Times' cash-flow statement raises TypeError in the library.
    assert raised == [(GOOD_TIMES, 'Condensed Consolidated Statements of Cash Flows (Unaudited)', 'instant_2022-05-05')]


def test_getter_raised_is_reported_and_the_role_statement_used(monkeypatch):
    """A typed getter that raises is a disagreement; the page is still compared, through statements[role]."""
    from edgar.xbrl.statements import Statements
    rate = results(GOOD_TIMES).value_rate('dataframe')

    def raising(self, *args, **kwargs):
        raise RuntimeError('getter boom')
    monkeypatch.setattr(Statements, 'cash_flow_statement', raising)
    viewer, xbrl = fixture_viewer_and_xbrl(GOOD_TIMES)
    res = viewer.compare_statements(xbrl)
    assert [(r.reason, r.family, r.level) for r in res.of_kind('getter_raised')] == [
        ('cash_flow_statement() raised RuntimeError: getter boom', DISAGREEMENT, 'filing'),
        ('cash_flow_statement(parenthetical=True) raised RuntimeError: getter boom', DISAGREEMENT, 'filing')]
    assert [p.access for p in res.pages if p.compared] == ['statements[role]']
    assert res.value_rate('dataframe') == rate == 1.0


def test_statement_by_role_raising_is_reported(monkeypatch):
    """When the role's own Statement cannot give a DataFrame, access_path_disagrees cannot be checked:
    that is reported, and the typed getter's statement is compared as before."""
    from edgar.xbrl.statements import Statements
    original = Statements.__getitem__

    class RaisingDataFrame:
        def __init__(self, statement):
            self._statement = statement

        def __getattr__(self, name):
            return getattr(self._statement, name)

        def to_dataframe(self, *args, **kwargs):
            raise TypeError('role boom')

    def getitem(self, item):
        statement = original(self, item)
        return RaisingDataFrame(statement) if statement is not None else None
    rate = results(GOOD_TIMES).value_rate('dataframe')
    monkeypatch.setattr(Statements, '__getitem__', getitem)
    viewer, xbrl = fixture_viewer_and_xbrl(GOOD_TIMES)
    res = viewer.compare_statements(xbrl)
    assert [r.reason for r in res.of_kind('statement_raised')] == [
        'statements[role].to_dataframe() raised TypeError: role boom; the page is compared through '
        'cash_flow_statement(), and access_path_disagrees is not checked']
    assert not res.of_kind('library_raised') and res.value_rate('dataframe') == rate


def test_library_calls_while_reading_the_rendered_table_are_library_raised(monkeypatch):
    """A cell's printed text is the library's: if get_formatted_value() raises, the table cannot be read by a
    user, so it is statement_raised, not page_not_compared."""
    from edgar.xbrl.rendering import StatementCell

    def raising(self, *args, **kwargs):
        raise ValueError('text boom')
    monkeypatch.setattr(StatementCell, 'get_formatted_value', raising)
    viewer, xbrl = fixture_viewer_and_xbrl(GOOD_TIMES)
    res = viewer.compare_statements(xbrl)
    assert [r.reason for r in res.of_kind('statement_raised', 'rendered')] == ['render() raised ValueError: text boom']
    assert len(res.of_kind('library_raised', 'rendered')) == 54 and res.value_rate('rendered') == 0.0
    assert not res.of_kind('page_not_compared', 'rendered')


def test_a_dataframe_that_cannot_be_read_is_library_raised(monkeypatch):
    """to_dataframe() returning a frame whose records cannot be read is the library's failure too."""
    from edgar.xbrl.statements import Statement

    class Unreadable:
        columns = ['concept', 'label']

        def to_dict(self, orient):
            raise TypeError('records boom')
    monkeypatch.setattr(Statement, 'to_dataframe', lambda self, *args, **kwargs: Unreadable())
    viewer, xbrl = fixture_viewer_and_xbrl(GOOD_TIMES)
    res = viewer.compare_statements(xbrl)
    assert {r.reason for r in res.of_kind('statement_raised', 'dataframe')} >= {'to_dataframe() raised TypeError: records boom'}
    assert len(res.of_kind('library_raised', 'dataframe')) == 54
    assert not res.of_kind('page_not_compared', 'dataframe')


def test_default_view_column_name_is_verified(monkeypatch):
    """If the library ever names a period's column differently from the check's replay, the cell is not compared
    under a guessed column: it is cell_not_comparable, with the names in reason."""
    monkeypatch.setattr(sf, '_named_alone', lambda ctx, key: 'renamed')
    viewer, xbrl = fixture_viewer_and_xbrl(GOOD_TIMES)
    res = viewer.compare_statements(xbrl)
    assert res.compared_cells('dataframe') == 0
    reasons = [r.reason for r in res.of_kind('cell_not_comparable', 'dataframe') if 'names its column' in r.reason]
    assert len(reasons) == 54 and all("names its column 'renamed', not '" in r for r in reasons)
