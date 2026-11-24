"""Each statement gets the period it needs (GH #429).

WHAT #429 WAS. ``current_period`` handed every statement the same period, so a
cash flow statement was rendered against the balance sheet's instant and came
back with two rows. The fix gave each statement type its own period kind.

WHAT THE FIX MISSED, and the tests here pin:

1. The statement of equity was put on the instant side. It is a roll-forward
   over the year, so under the year-end instant it lost every flow row (net
   income, dividends, buybacks) and showed the closing balance as the opening
   one: Apple FY2023 read 62,146M on both rows instead of 50,672M and 62,146M.
2. A cash flow statement preferred the quarter. A 10-Q files cash flows year to
   date, so Tesla's Q2 2024 cash flow statement came back with the same two
   rows #429 reported, against 36 for the six months.
3. ``CurrentPeriodStatement.get_dataframe()`` and the ``as_statement=False``
   path read ``values[period]`` directly, a third copy of the rule
   ``Statement.to_dataframe()`` and the rendered table share
   (``balance_cell_key``). Under a duration every instant balance row dropped
   out: beginning and ending cash, and the equity roll-forward's balances.

WHY THE OLD TESTS DID NOT SEE IT. They read ``get_filings(form="10-K")``'s
newest original for AAPL, MSFT, GOOGL and TSLA, so they never saw a 10-Q, and
they asserted that the statement of equity used an instant, which pinned bug 1.
Every statement here is now read from XBRL committed under
``data/xbrl/datafiles``, and the values are the filers' own facts:

- AAPL 10-K FY2023, 0000320193-23-000106 (``aapl``)
- TSLA 10-Q Q2 2024, 0001628280-24-032662 (``tsla``)
- UNP 10-K FY2012, 0001193125-13-045658 (``unp``)

GitHub Issue: https://github.com/dgunning/edgartools/issues/429
"""
from pathlib import Path

import pytest

from edgar.xbrl import XBRL

pytestmark = [pytest.mark.fast, pytest.mark.regression]

DATAFILES = Path(__file__).resolve().parents[3] / 'data' / 'xbrl' / 'datafiles'

STATEMENT_METHODS = {
    'BalanceSheet': 'balance_sheet',
    'IncomeStatement': 'income_statement',
    'CashFlowStatement': 'cash_flow_statement',
    'StatementOfEquity': 'statement_of_equity',
    'ComprehensiveIncome': 'comprehensive_income',
}

_LOADED = {}


def _current(name):
    if name not in _LOADED:
        _LOADED[name] = XBRL.from_directory(DATAFILES / name).current_period
    return _LOADED[name]


def _frame(filing, statement_type, as_statement):
    method = getattr(_current(filing), STATEMENT_METHODS[statement_type])
    if as_statement:
        return method().get_dataframe()
    return method(as_statement=False)


def _values(df, label):
    return df.loc[df['label'] == label, 'value'].tolist()


PERIODS = [
    # AAPL's 52/53-week year ends 2023-09-30
    ('aapl', 'BalanceSheet', 'instant_2023-09-30'),
    ('aapl', 'IncomeStatement', 'duration_2022-09-25_2023-09-30'),
    ('aapl', 'CashFlowStatement', 'duration_2022-09-25_2023-09-30'),
    ('aapl', 'StatementOfEquity', 'duration_2022-09-25_2023-09-30'),
    ('aapl', 'ComprehensiveIncome', 'duration_2022-09-25_2023-09-30'),
    # A 10-Q: the quarter for income and equity, six months for cash flows
    ('tsla', 'BalanceSheet', 'instant_2024-06-30'),
    ('tsla', 'IncomeStatement', 'duration_2024-04-01_2024-06-30'),
    ('tsla', 'CashFlowStatement', 'duration_2024-01-01_2024-06-30'),
    ('tsla', 'StatementOfEquity', 'duration_2024-04-01_2024-06-30'),
    ('unp', 'BalanceSheet', 'instant_2012-12-31'),
    ('unp', 'StatementOfEquity', 'duration_2012-01-01_2012-12-31'),
]


@pytest.mark.parametrize('filing, statement_type, period', PERIODS)
def test_each_statement_gets_its_period(filing, statement_type, period):
    assert _current(filing)._get_appropriate_period_for_statement(statement_type) == period


def test_unknown_statement_type_falls_back_to_the_current_period():
    cp = _current('aapl')
    assert cp._get_appropriate_period_for_statement('UnknownStatementType') == cp.period_key


# (filing, opening label, opening, closing label, closing, net income)
EQUITY_ROLL_FORWARDS = [
    ('aapl', 'Beginning balances', 50_672_000_000, 'Ending balances', 62_146_000_000, 96_995_000_000),
    ('unp', "Shareholders' equity, beginning balance", 18_578_000_000,
     "Shareholders' equity, ending balance", 19_877_000_000, 3_943_000_000),
]


@pytest.mark.parametrize('as_statement', [True, False], ids=['statement', 'dataframe'])
@pytest.mark.parametrize('filing, open_label, opening, close_label, closing, net_income', EQUITY_ROLL_FORWARDS)
def test_statement_of_equity_rolls_forward(as_statement, filing, open_label, opening,
                                           close_label, closing, net_income):
    """Bug 1: the opening balance is the prior year end, and the flows are there."""
    df = _frame(filing, 'StatementOfEquity', as_statement)
    assert _values(df, open_label) == [opening]
    assert _values(df, close_label) == [closing]
    assert _values(df, 'Net income') == [net_income]


def test_apple_equity_shows_dividends():
    df = _frame('aapl', 'StatementOfEquity', True)
    assert _values(df, 'Dividends and dividend equivalents declared') == [14_996_000_000]


def test_tesla_quarterly_equity_opens_at_the_quarter_start():
    """Total stockholders' equity, 2024-03-31 then 2024-06-30, in Tesla's Q2 10-Q."""
    totals = _values(_frame('tsla', 'StatementOfEquity', True), 'Total Stockholders’ Equity')
    assert totals[0] == 64_378_000_000
    assert totals[-1] == 66_468_000_000


@pytest.mark.parametrize('as_statement', [True, False], ids=['statement', 'dataframe'])
def test_ten_q_cash_flow_is_year_to_date(as_statement):
    """Bug 2: #429's own symptom, still there for a 10-Q. The quarter has 2 rows."""
    df = _frame('tsla', 'CashFlowStatement', as_statement)
    assert len(df) == 36
    assert _values(df, 'Net income') == [2_638_000_000]


# (filing, opening label, opening, closing label, closing)
CASH_BALANCES = [
    ('aapl', 'Cash, cash equivalents and restricted cash, beginning balances', 24_977_000_000,
     'Cash, cash equivalents and restricted cash, ending balances', 30_737_000_000),
    ('tsla', 'Cash and cash equivalents and restricted cash, beginning of period', 17_189_000_000,
     'Cash and cash equivalents and restricted cash, end of period', 15_354_000_000),
]


@pytest.mark.parametrize('as_statement', [True, False], ids=['statement', 'dataframe'])
@pytest.mark.parametrize('filing, open_label, opening, close_label, closing', CASH_BALANCES)
def test_cash_flow_keeps_its_cash_balances(as_statement, filing, open_label, opening,
                                           close_label, closing):
    """Bug 3: instant balances under a duration column used to drop out."""
    df = _frame(filing, 'CashFlowStatement', as_statement)
    assert _values(df, open_label) == [opening]
    assert _values(df, close_label) == [closing]


@pytest.mark.parametrize('statement_type, rows', [
    ('BalanceSheet', 30), ('IncomeStatement', 19), ('CashFlowStatement', 30),
    ('StatementOfEquity', 24), ('ComprehensiveIncome', 10),
])
def test_apple_statements_render_every_row_with_a_value(statement_type, rows):
    """The issue's report was empty statements. Every row shown carries a value."""
    df = _frame('aapl', statement_type, True)
    assert len(df) == rows
    assert df['value'].notna().all()
