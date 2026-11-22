"""
Regression: a statement requested for one duration period keeps its balance rows.

Bead: edgartools-auvk1.21

``to_dataframe(period_filter=<duration key>)`` and ``render(period_filter=...)``
collected only facts whose period key equalled the filter. Instant facts
(opening and closing balances, par values on a parenthetical page) were
dropped before ``balance_cell_key`` could place them under the duration
column, so a balance total showed blank and its member rows disappeared.
The default view, which shows the same column, had them.

Ground truth, from the SEC page (R*.htm) of the filing in the offline fixtures
(tests/fixtures/statement-fidelity):

- Brixmor Property Group 10-K, 0001581068-21-000012, cash flows, 12 months
  ended 2020-12-31 (thousands): cash, cash equivalents and restricted cash at
  beginning of period 21,523, Brixmor Operating Partnership LP 21,507; at end
  of period 370,087, Brixmor Operating Partnership LP 360,073.
"""
import pytest

from edgar.xbrl.core import balance_cell_key, balance_cell_keys
from tests.xbrl.statement_fidelity_fixtures import fixture_viewer_and_xbrl

CASH = 'us-gaap_CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents'
FY2020 = 'duration_2020-01-01_2020-12-31'
COLUMN = '2020-12-31 (FY)'

# (consolidated, operating partnership) per balance, in the page's order
OPENING = [21_523_000, 21_507_000]
CLOSING = [370_087_000, 360_073_000]


@pytest.fixture(scope='module')
def brixmor_cash_flow():
    _, xbrl = fixture_viewer_and_xbrl('0001581068-21-000012')
    return xbrl.statements.cash_flow_statement()


def test_dataframe_for_one_period_shows_opening_and_closing_cash(brixmor_cash_flow):
    frame = brixmor_cash_flow.to_dataframe(period_filter=FY2020)
    assert [c for c in frame.columns if c[:4].isdigit()] == [COLUMN]
    cash = [float(v) for v in frame.loc[frame['concept'] == CASH, COLUMN]]
    assert cash[:2] == OPENING
    assert cash[2:4] == CLOSING


def test_rendered_for_one_period_shows_opening_and_closing_cash(brixmor_cash_flow):
    rendered = brixmor_cash_flow.render(period_filter=FY2020)
    cash = [row.cells[0].value for row in rendered.rows if row.metadata.get('concept') == CASH]
    assert cash[:2] == OPENING
    assert cash[2:4] == CLOSING


def test_one_period_request_agrees_with_the_default_view(brixmor_cash_flow):
    default = brixmor_cash_flow.to_dataframe()
    single = brixmor_cash_flow.to_dataframe(period_filter=FY2020)
    assert list(default.loc[default['concept'] == CASH, COLUMN]) == list(single.loc[single['concept'] == CASH, COLUMN])


def test_balance_cell_keys_cover_every_choice_of_balance_cell_key():
    keys = balance_cell_keys(FY2020)
    assert keys == {FY2020, 'instant_2020-12-31', 'instant_2020-01-01', 'instant_2019-12-31'}
    every_instant = {key: 1 for key in keys if key.startswith('instant_')}
    for role in (None, 'http://www.xbrl.org/2003/role/periodStartLabel',
                 'http://www.xbrl.org/2003/role/periodEndLabel'):
        for by_position in (False, True):
            assert balance_cell_key(every_instant, FY2020, role, by_position) in keys


def test_an_instant_filter_keeps_only_itself():
    assert balance_cell_keys('instant_2020-12-31') == {'instant_2020-12-31'}
