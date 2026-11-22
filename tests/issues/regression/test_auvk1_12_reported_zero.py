"""
Regression: a reported zero shows as 0, in the rendered table and in the DataFrame.

Bead: edgartools-auvk1.12

Two symptoms, both against the SEC page (R*.htm):

- The rendered table printed nothing for a reported 0. The formatter's empty-value
  check was ``if not value``, and 0 is falsy, so a zero looked like a fact that was
  never filed. Digi International 10-K, 0000854775-20-000032, comprehensive income:
  the page shows 0 for FY2020 unrealized holding gain on securities (19 and (31)
  for the two years before). Entergy 10-Q, 0000065984-24-000112, cash flows: the
  page shows 0 for 2023 year-to-date noncash pension expense.
- A negated label turned a filed 0 into -0.0 (0.0 * -1). The SEC renderer never
  negates a zero. Entergy 10-Q, cash flows: Entergy New Orleans' 2024 year-to-date
  other investing activities show 0 on the page.
"""
import math
from types import SimpleNamespace

import pandas as pd
import pytest

from edgar.xbrl.rendering import _format_value_for_display_as_string, apply_presentation_sign
from edgar.xbrl.statements import Statement
from tests.xbrl.statement_fidelity_fixtures import fixture_viewer_and_xbrl

OTHER_INVESTING = 'us-gaap_PaymentsForProceedsFromOtherInvestingActivities'
PENSION_NONCASH = 'us-gaap_PensionExpenseReversalOfExpenseNoncash'
NEW_ORLEANS = 'Entergy New Orleans'


def _is_negative_zero(value):
    return isinstance(value, float) and value == 0 and math.copysign(1.0, value) < 0


@pytest.fixture(scope='module')
def entergy_cash_flow():
    _, xbrl = fixture_viewer_and_xbrl('0000065984-24-000112')
    return xbrl.statements.cash_flow_statement()


@pytest.mark.fast
def test_negated_label_leaves_a_zero_unsigned():
    signs = {'duration_2024-01-01_2024-09-30': -1}
    assert not _is_negative_zero(apply_presentation_sign(0.0, signs, 'duration_2024-01-01_2024-09-30'))
    assert apply_presentation_sign(0, signs, 'duration_2024-01-01_2024-09-30') == 0
    assert apply_presentation_sign(5.0, signs, 'duration_2024-01-01_2024-09-30') == -5.0
    # a zero filed with a minus sign shows as 0 under a negated label (Nocopi
    # 0001683168-26-003002 goodwill impairment) and keeps the sign without one: the
    # page shows (0.00) for a loss per share that rounds to zero (0001493152-24-046709)
    assert not _is_negative_zero(apply_presentation_sign(-0.0, signs, 'duration_2024-01-01_2024-09-30'))
    assert _is_negative_zero(apply_presentation_sign(-0.0, {}, 'duration_2024-01-01_2024-09-30'))
    assert _is_negative_zero(apply_presentation_sign(-0.0, None, None))


@pytest.mark.fast
def test_dataframe_zero_under_a_negated_label_shows_as_zero():
    df = pd.DataFrame({
        'concept': ['a', 'b', 'c', 'd'],
        'label': ['a', 'b', 'c', 'd'],
        '2025-12-31 (FY)': [-0.0, 0.0, 7.0, -0.0],
        'preferred_sign': [None, -1, -1, -1],
    })
    out = Statement._apply_presentation(SimpleNamespace(), df)['2025-12-31 (FY)'].tolist()
    assert out == [0.0, 0.0, -7.0, 0.0]
    # no label sign: the filed -0 stays, as the page's (0.00); negated: 0
    assert [_is_negative_zero(v) for v in out] == [True, False, False, False]
    # a note column with text keeps its text; a negated zero still shows as 0
    df['2025-12-31 (FY)'] = pd.Series(['narrative', -0.0, 7.0, None], dtype=object)
    out = Statement._apply_presentation(SimpleNamespace(), df)['2025-12-31 (FY)'].tolist()
    assert out[0] == 'narrative' and out[2] == -7.0 and out[3] is None
    assert out[1] == 0 and not _is_negative_zero(out[1])


@pytest.mark.fast
def test_zero_formats_as_zero_and_none_as_blank():
    item = {'concept': 'us-gaap_Revenues', 'decimals': {'p': -6}}
    assert _format_value_for_display_as_string(0.0, item, 'p', True, -6, None) == '$0'
    assert _format_value_for_display_as_string(0, item, 'p', True, -6, None) == '$0'
    assert _format_value_for_display_as_string(None, item, 'p', True, -6, None) == ''
    assert _format_value_for_display_as_string('', item, 'p', True, 3, None) == ''


def test_entergy_new_orleans_zero_is_not_negative_in_the_dataframe(entergy_cash_flow):
    df = entergy_cash_flow.to_dataframe()
    rows = df[(df['concept'] == OTHER_INVESTING) & df['dimension_label'].fillna('').str.contains(NEW_ORLEANS)]
    values = rows['2024-09-30 (YTD)'].tolist()
    assert values and all(v == 0 for v in values)
    assert not any(_is_negative_zero(v) for v in values)
    # every cell of the statement: no presented value is -0.0
    period_cols = [c for c in df.columns if str(c)[:4].isdigit()]
    assert not any(_is_negative_zero(v) for c in period_cols for v in df[c].tolist())


def test_entergy_reported_zero_renders_as_zero(entergy_cash_flow):
    rendered = entergy_cash_flow.render()
    period = rendered.periods.index(next(p for p in rendered.periods if p.key == 'duration_2023-01-01_2023-09-30'))
    row = next(r for r in rendered.rows if r.metadata.get('concept') == PENSION_NONCASH and not r.is_dimension)
    cell = row.cells[period]
    assert cell.value == 0
    assert cell.get_formatted_value() == '$0'  # the page: $ 0, the first row of its section


@pytest.mark.network
def test_digi_reported_zero_renders_as_zero():
    from edgar import find
    xbrl = find('0000854775-20-000032').xbrl()
    statement = xbrl.statements['http://www.digi.com/role/ConsolidatedStatementsofComprehensiveIncome']
    concept = 'us-gaap_OtherComprehensiveIncomeUnrealizedHoldingGainLossOnSecuritiesArisingDuringPeriodBeforeTax'
    row = next(r for r in statement.render().rows if r.metadata.get('concept') == concept and not r.is_dimension)
    assert [c.get_formatted_value() for c in row.cells] == ['0', '19', '(31)']
