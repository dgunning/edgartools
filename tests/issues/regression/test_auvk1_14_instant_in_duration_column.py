"""
Regression: an instant balance under a duration column is placed by one rule on both surfaces.

Bead: edgartools-auvk1.14

Statement.to_dataframe() and render() each decided which instant a balance row
shows under a duration column, by different rules:

- A dimension (member) row took the role of its concept's last presentation arc
  instead of its own parent reference's, so a member row under a beginning
  balance (periodStartLabel) was read as a closing balance. Brixmor's operating
  partnership row showed 360,073,000 for 2020 in the DataFrame where the SEC page
  shows the opening 21,507 (thousands); the rendered table showed nothing.
- The rendered table placed an instant under a duration column only for
  period-start/period-end roles or statements of equity, so Entergy's cash
  total, on a terseLabel arc, was blank while the DataFrame showed it.

Ground truth, from the SEC pages (R*.htm) of the filings in the offline fixtures
(tests/fixtures/statement-fidelity):

- Brixmor Property Group 10-K, 0001581068-21-000012, cash flows: Brixmor
  Operating Partnership LP under "Cash, cash equivalents and restricted cash at
  beginning of period": 21,507 / 50,639 / 110,747 for 2020 / 2019 / 2018; under
  "at end of period": 360,073 / 21,507 / 50,639.
- Entergy 10-Q, 0000065984-24-000112, cash flows: cash, cash equivalents and
  restricted cash at the end of the period, 1,411,812 for nine months 2024.
"""
import pytest

from edgar.xbrl.core import balance_cell_key
from tests.xbrl.statement_fidelity_fixtures import fixture_viewer_and_xbrl

CASH = 'us-gaap_CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents'
START = 'http://www.xbrl.org/2003/role/periodStartLabel'
END = 'http://www.xbrl.org/2003/role/periodEndLabel'
TERSE = 'http://www.xbrl.org/2003/role/terseLabel'
FY = 'duration_2020-01-01_2020-12-31'
VALUES = {'instant_2019-12-31': 21_507, 'instant_2020-12-31': 360_073}

BRIXMOR_OPENING = [21_507_000, 50_639_000, 110_747_000]
BRIXMOR_CLOSING = [360_073_000, 21_507_000, 50_639_000]


@pytest.fixture(scope='module')
def brixmor_cash_flow():
    _, xbrl = fixture_viewer_and_xbrl('0001581068-21-000012')
    return xbrl.statements.cash_flow_statement()


def _member_rows(frame):
    rows = frame[(frame['concept'] == CASH) & frame['dimension']]
    return [list(values) for values in rows[['2020-12-31 (FY)', '2019-12-31 (FY)', '2018-12-31 (FY)']].values]


def test_dataframe_member_row_under_the_opening_balance_shows_the_opening_balance(brixmor_cash_flow):
    opening, closing, *rest = _member_rows(brixmor_cash_flow.to_dataframe())
    assert opening == BRIXMOR_OPENING
    assert closing == BRIXMOR_CLOSING


def test_rendered_member_row_under_the_opening_balance_is_not_blank(brixmor_cash_flow):
    rendered = brixmor_cash_flow.render()
    members = [[cell.value for cell in row.cells] for row in rendered.rows
               if row.metadata.get('concept') == CASH and row.is_dimension]
    assert members[0] == BRIXMOR_OPENING
    assert members[1] == BRIXMOR_CLOSING


def test_rendered_cash_total_on_a_terse_arc_shows_the_closing_balance():
    _, xbrl = fixture_viewer_and_xbrl('0000065984-24-000112')
    rendered = xbrl.statements.cash_flow_statement().render()
    [total] = [row for row in rendered.rows if row.metadata.get('concept') == CASH and not row.is_dimension]
    assert rendered.header.period_keys[0] == 'duration_2024-01-01_2024-09-30'
    assert total.cells[0].value == 1_411_812_000
    assert total.cells[0].get_formatted_value() == '$1,411,812'


@pytest.mark.parametrize('role,expected', [
    (START, 'instant_2019-12-31'),
    (END, 'instant_2020-12-31'),
    (TERSE, 'instant_2020-12-31'),
    (None, 'instant_2020-12-31'),
])
def test_the_arc_role_decides_opening_or_closing(role, expected):
    assert balance_cell_key(VALUES, FY, role) == expected


def test_a_period_start_row_never_falls_back_to_the_closing_balance():
    assert balance_cell_key({'instant_2020-12-31': 360_073}, FY, START) is None
    assert balance_cell_key({'instant_2020-01-01': 7}, FY, START) == 'instant_2020-01-01'


def test_the_column_own_value_wins_and_an_instant_column_reads_only_itself():
    assert balance_cell_key({FY: 5, **VALUES}, FY, START) == FY
    assert balance_cell_key(VALUES, 'instant_2020-12-31', START) == 'instant_2020-12-31'
    assert balance_cell_key(VALUES, 'instant_2018-12-31', None) is None


def test_equity_position_fallback_applies_only_without_a_boundary_role():
    assert balance_cell_key(VALUES, FY, None, opening_by_position=True) == 'instant_2019-12-31'
    assert balance_cell_key(VALUES, FY, END, opening_by_position=True) == 'instant_2020-12-31'
    # an opening row by position with no opening instant shows the closing balance, as before
    assert balance_cell_key({'instant_2020-12-31': 360_073}, FY, None, opening_by_position=True) == 'instant_2020-12-31'
