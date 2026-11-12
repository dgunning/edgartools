"""Regression: ``get_financial_metrics()`` gave no dates, so a caller could not
see that a 10-Q's metrics cover different periods.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1656

Each statement's value comes from its own current column. On a Q2 or Q3 10-Q
that files a year-to-date cash flow statement, income metrics cover the quarter
while operating cash flow, capex and free cash flow cover the year to date, and
the balance sheet is at the quarter end. The values are right; dividing across
the dictionary mixed periods because nothing said which period each was for.

``get_financial_metrics(include_periods=True)`` adds a ``periods`` mapping that
gives every metric the period its value came from, or None. The default result
is unchanged.

Values and dates were read from the fixture instance documents:

- Apple 10-Q for 2023-07-01, accession 0000320193-23-000077
  (tests/fixtures/xbrl/aapl/10q_2023): revenue f-65 and net income f-113 on
  context c-21 (2023-04-02..2023-07-01); operating cash flow f-327 and PP&E
  purchases f-335 on c-1 (2022-09-25..2023-07-01); Assets f-195 on c-24
  (instant 2023-07-01).
- Tesla 10-Q for 2024-06-30, accession 0001628280-24-032662
  (tests/fixtures/xbrl/tsla): revenue f-140 and net income f-220 on c-33
  (2024-04-01..2024-06-30); operating cash flow f-448 and PP&E purchases f-450
  on c-1 (2024-01-01..2024-06-30); Assets f-60 on c-3 (instant 2024-06-30).
- Exxon Mobil 10-K for 2022, accession 0000034088-23-000020
  (tests/fixtures/xbrl/xom/10k_2023): Revenues 413,680M, NetIncomeLoss 55,740M,
  operating cash flow 76,797M and PP&E purchases 18,407M for
  2022-01-01..2022-12-31; Assets 369,067M at 2022-12-31.
"""
from functools import lru_cache
from pathlib import Path

import pytest

import edgar.financials as financials_module
from edgar.financials import Financials
from edgar.xbrl import XBRL

FIXTURES = Path(__file__).resolve().parents[2] / 'fixtures' / 'xbrl'

METRIC_KEYS = {
    'revenue', 'operating_income', 'net_income', 'total_assets', 'total_liabilities',
    'stockholders_equity', 'current_assets', 'current_liabilities', 'operating_cash_flow',
    'capital_expenditures', 'free_cash_flow', 'shares_outstanding_basic',
    'shares_outstanding_diluted', 'current_ratio', 'debt_to_assets',
}


def duration(start, end):
    return {'period_type': 'duration', 'start_date': start, 'end_date': end}


def instant(end):
    return {'period_type': 'instant', 'start_date': None, 'end_date': end}


@lru_cache(maxsize=None)
def _xbrl(name):
    return XBRL.from_directory(FIXTURES / name)


APPLE_Q3_2023 = 'aapl/10q_2023'
TESLA_Q2_2024 = 'tsla'
EXXON_FY2022 = 'xom/10k_2023'


@pytest.mark.fast
def test_apple_q3_income_is_the_quarter_and_cash_flow_the_nine_months():
    metrics = Financials(_xbrl(APPLE_Q3_2023)).get_financial_metrics(include_periods=True)
    periods = metrics['periods']

    quarter = duration('2023-04-02', '2023-07-01')
    nine_months = duration('2022-09-25', '2023-07-01')

    assert metrics['revenue'] == 81_797_000_000
    assert periods['revenue'] == quarter
    assert metrics['net_income'] == 19_881_000_000
    assert periods['net_income'] == quarter
    assert periods['shares_outstanding_basic'] == quarter

    assert metrics['operating_cash_flow'] == 88_945_000_000
    assert periods['operating_cash_flow'] == nine_months
    assert metrics['capital_expenditures'] == 8_796_000_000
    assert periods['capital_expenditures'] == nine_months
    assert metrics['free_cash_flow'] == 88_945_000_000 - 8_796_000_000
    assert periods['free_cash_flow'] == nine_months

    assert metrics['total_assets'] == 335_038_000_000
    assert periods['total_assets'] == instant('2023-07-01')
    assert periods['current_ratio'] == instant('2023-07-01')
    assert periods['debt_to_assets'] == instant('2023-07-01')


@pytest.mark.fast
def test_tesla_q2_income_is_the_quarter_and_cash_flow_the_six_months():
    metrics = Financials(_xbrl(TESLA_Q2_2024)).get_financial_metrics(include_periods=True)
    periods = metrics['periods']

    quarter = duration('2024-04-01', '2024-06-30')
    six_months = duration('2024-01-01', '2024-06-30')

    assert metrics['revenue'] == 25_500_000_000
    assert periods['revenue'] == quarter
    assert metrics['net_income'] == 1_478_000_000
    assert periods['net_income'] == quarter

    assert metrics['operating_cash_flow'] == 3_854_000_000
    assert metrics['capital_expenditures'] == 5_043_000_000
    assert metrics['free_cash_flow'] == -1_189_000_000
    # Free cash flow carries exactly its two operands' shared period.
    assert periods['operating_cash_flow'] == periods['capital_expenditures'] == six_months
    assert periods['free_cash_flow'] == six_months

    # A balance-sheet metric is an instant: no start date, never the income one.
    assert metrics['total_assets'] == 112_832_000_000
    assert periods['total_assets'] == instant('2024-06-30')
    assert periods['total_assets']['start_date'] is None


@pytest.mark.fast
def test_annual_control_every_duration_is_the_fiscal_year():
    metrics = Financials(_xbrl(EXXON_FY2022)).get_financial_metrics(include_periods=True)
    periods = metrics['periods']
    year = duration('2022-01-01', '2022-12-31')

    assert metrics['revenue'] == 413_680_000_000
    assert metrics['net_income'] == 55_740_000_000
    assert metrics['operating_cash_flow'] == 76_797_000_000
    assert metrics['capital_expenditures'] == 18_407_000_000
    for key in ('revenue', 'net_income', 'operating_cash_flow', 'capital_expenditures', 'free_cash_flow'):
        assert periods[key] == year, key
    assert metrics['total_assets'] == 369_067_000_000
    assert periods['total_assets'] == instant('2022-12-31')

    # A metric with no value has no period. Exxon presents no operating
    # income subtotal.
    assert metrics['operating_income'] is None
    assert periods['operating_income'] is None


@pytest.mark.fast
@pytest.mark.parametrize('fixture', [APPLE_Q3_2023, TESLA_Q2_2024, EXXON_FY2022])
def test_default_is_unchanged_and_opting_in_only_adds_periods(fixture):
    financials = Financials(_xbrl(fixture))
    default = financials.get_financial_metrics()
    assert set(default) == METRIC_KEYS
    assert 'periods' not in default

    with_periods = financials.get_financial_metrics(include_periods=True)
    assert set(with_periods) == METRIC_KEYS | {'periods'}
    assert set(with_periods['periods']) == METRIC_KEYS
    assert {k: v for k, v in with_periods.items() if k != 'periods'} == default

    # Per-call state is gone afterwards.
    assert financials._statement_frame_memo is None
    assert financials._period_trace is None


class _NoConceptLookups(Financials):
    """Concept lookups on one statement find nothing, so the getters take their fallbacks."""
    statement = None

    def _get_standardized_concept_by_xbrl(self, statement_type, names, period_offset=0):
        if statement_type == self.statement:
            return None
        return super()._get_standardized_concept_by_xbrl(statement_type, names, period_offset)


@pytest.mark.fast
def test_label_fallback_reports_the_column_it_read():
    class CashFlowByLabel(_NoConceptLookups):
        statement = 'cashflow'

    metrics = CashFlowByLabel(_xbrl(TESLA_Q2_2024)).get_financial_metrics(include_periods=True)
    # "Net cash provided by operating activities", read by label.
    assert metrics['operating_cash_flow'] == 3_854_000_000
    assert metrics['periods']['operating_cash_flow'] == duration('2024-01-01', '2024-06-30')


@pytest.mark.fast
def test_raw_revenue_fallback_reports_the_dates_it_filtered_on():
    class BankLayout(_NoConceptLookups):
        statement = 'income'

        def _is_bank_income_statement(self):
            return True

    metrics = BankLayout(_xbrl(TESLA_Q2_2024)).get_financial_metrics(include_periods=True)
    # us-gaap:Revenues f-1114 on c-33, read from the facts, not a statement row.
    assert metrics['revenue'] == 25_500_000_000
    assert metrics['periods']['revenue'] == duration('2024-04-01', '2024-06-30')


@pytest.mark.fast
def test_derived_net_income_reports_its_operands_period():
    class ProfitLossOnly(Financials):
        def _get_standardized_concept_by_xbrl(self, statement_type, names, period_offset=0):
            if 'Net Income' in names:
                return None
            return super()._get_standardized_concept_by_xbrl(statement_type, names, period_offset)

    metrics = ProfitLossOnly(_xbrl(TESLA_Q2_2024)).get_financial_metrics(include_periods=True)
    # ProfitLoss 1,494M (f-212) less the noncontrolling interest's 16M (f-216).
    assert metrics['net_income'] == 1_478_000_000
    assert metrics['periods']['net_income'] == duration('2024-04-01', '2024-06-30')


@pytest.mark.fast
def test_unknown_period_keeps_the_value(monkeypatch):
    monkeypatch.setattr(financials_module, '_column_period_descriptor', lambda rendered, column: None)
    metrics = Financials(_xbrl(TESLA_Q2_2024)).get_financial_metrics(include_periods=True)
    assert metrics['revenue'] == 25_500_000_000
    assert metrics['periods']['revenue'] is None
    # Neither operand's period is known, so free cash flow's is not either.
    assert metrics['free_cash_flow'] == -1_189_000_000
    assert metrics['periods']['free_cash_flow'] is None
    assert metrics['periods']['current_ratio'] is None


@pytest.mark.fast
def test_a_column_name_shared_by_two_periods_has_no_period():
    class Period:
        def __init__(self, start, end):
            self.start_date, self.end_date = start, end
            self.is_duration, self.quarter, self.label = True, None, end

    class Rendered:
        periods = [Period('2024-04-01', '2024-06-30'), Period('2024-01-01', '2024-06-30')]

    assert financials_module._column_period_descriptor(Rendered(), '2024-06-30') is None
    Rendered.periods = Rendered.periods[:1]
    assert financials_module._column_period_descriptor(Rendered(), '2024-06-30') == duration('2024-04-01', '2024-06-30')


@pytest.mark.fast
def test_state_is_cleared_when_a_getter_raises():
    class Failing(Financials):
        def get_capital_expenditures(self, period_offset=0):
            raise RuntimeError('boom')

    financials = Failing(_xbrl(TESLA_Q2_2024))
    with pytest.raises(RuntimeError):
        financials.get_financial_metrics(include_periods=True)
    assert financials._statement_frame_memo is None
    assert financials._period_trace is None
