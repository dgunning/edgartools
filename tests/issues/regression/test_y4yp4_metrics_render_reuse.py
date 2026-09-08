"""
Regression tests for edgartools-y4yp.4 (GH #1283): `get_financial_metrics()`
rendered and converted the same three statements once per getter.

Every scalar getter funnels into one of THREE sibling helpers --
`_get_standardized_concept_by_xbrl`, `_get_standardized_concept_value` and
`_get_concept_value` -- and each carried its own copy of the same four steps:
pick the statement for a type, `render(standard=True)`, `to_dataframe(
presentation=False)`, drop abstract rows. So one metrics call did the whole
rendering pipeline once per metric, over only THREE distinct configurations.

Re-measured on the fixtures below AFTER y4yp.1/.2/.3 landed (PR #1299), because
those changed which lookups run:

    filing              renders/to_dataframe before   after
    aapl/10k_2023                        14 / 14        3 / 3
    jpm/10k_2024                         18 / 18        3 / 3
    ko/10k_2024                          15 / 15        3 / 3
    nflx/10k_2024                        14 / 14        3 / 3

(The bead recorded 14 for Coca-Cola; it is 15 on current main, which is why the
re-measurement was the first step.) Warm medians per call fell 32.3->13.2 ms
(AAPL), 95.2->24.8 (JPM), 43.0->15.1 (KO), 27.9->11.8 (NFLX).

The three helpers now share `_render_statement_frame()`, and
`get_financial_metrics()` installs a memo for the duration of ONE call. The
scoping is the whole safety argument: a statement's rendering depends on the view
and periods in force, so a cache outliving the call would answer a later question
with an earlier call's configuration. The tests below pin that scoping as hard as
they pin the work count -- every metric value is asserted unchanged, including
JPMorgan's six legitimate `None`s, which a memo bug could quietly turn into
numbers borrowed from another statement.
"""

from pathlib import Path

import pytest

from edgar.financials import Financials
from edgar.xbrl import XBRL
from edgar.xbrl.rendering import RenderedStatement
from edgar.xbrl.statements import Statement

AAPL = Path('tests/fixtures/xbrl/aapl/10k_2023')
JPM = Path('tests/fixtures/xbrl/jpm/10k_2024')

# Apple FY2023, as filed. The three-statement spread is deliberate: revenue and
# net income come from the income statement, total assets from the balance sheet,
# operating cash flow and capex from the cash flow statement, so a memo that
# handed back the wrong statement's frame would move at least one of them.
AAPL_METRICS = {
    'revenue': 383285000000.0,
    'operating_income': 114301000000.0,
    'net_income': 96995000000.0,
    'total_assets': 352583000000.0,
    'total_liabilities': 290437000000.0,
    'stockholders_equity': 62146000000.0,
    'current_assets': 143566000000.0,
    'current_liabilities': 145308000000.0,
    'operating_cash_flow': 110543000000.0,
    'capital_expenditures': 10959000000.0,
    'free_cash_flow': 99584000000.0,
    'shares_outstanding_basic': 15744231000.0,
    'shares_outstanding_diluted': 15812547000.0,
}

# JPMorgan files no current/noncurrent split and no capex line, so these are
# genuinely absent rather than missed.
JPM_NONE_METRICS = ['operating_income', 'current_assets', 'current_liabilities',
                    'capital_expenditures', 'free_cash_flow', 'current_ratio']
JPM_VALUES = {
    'revenue': 68837000000.0,
    'net_income': 49552000000.0,
    'total_assets': 3875393000000.0,
    'total_liabilities': 3547515000000.0,
    'stockholders_equity': 327878000000.0,
    'operating_cash_flow': 12974000000.0,
}


@pytest.fixture(scope='module')
def aapl():
    return Financials(XBRL.from_directory(AAPL))


@pytest.fixture(scope='module')
def jpm():
    return Financials(XBRL.from_directory(JPM))


@pytest.fixture
def work_counter(monkeypatch):
    """Count ACTUAL executions of render()/to_dataframe(), and their configurations.

    monkeypatch restores the class attributes itself; both methods are defined on
    the classes patched here, so nothing is left behind on a subclass.
    """
    calls = {'render': [], 'to_dataframe': []}
    original_render = Statement.render
    original_to_dataframe = RenderedStatement.to_dataframe

    def render(self, *args, **kwargs):
        calls['render'].append((self.role_or_type, kwargs.get('standard')))
        return original_render(self, *args, **kwargs)

    def to_dataframe(self, *args, **kwargs):
        calls['to_dataframe'].append((getattr(self, 'title', ''), kwargs.get('presentation')))
        return original_to_dataframe(self, *args, **kwargs)

    monkeypatch.setattr(Statement, 'render', render)
    monkeypatch.setattr(RenderedStatement, 'to_dataframe', to_dataframe)
    return calls


def test_one_metrics_call_renders_each_statement_once(aapl, work_counter):
    aapl.get_financial_metrics()

    assert len(work_counter['render']) == 3, \
        f"expected 3 renders, got {len(work_counter['render'])}"
    assert len(work_counter['to_dataframe']) == 3
    assert len(set(work_counter['render'])) == 3, "the three must be distinct statements"


def test_a_bank_with_more_missing_metrics_also_renders_three(jpm, work_counter):
    """JPMorgan took 18 renders: a getter that finds nothing still did the work."""
    jpm.get_financial_metrics()
    assert len(work_counter['render']) == 3
    assert len(work_counter['to_dataframe']) == 3


def test_every_metric_value_is_unchanged(aapl):
    metrics = aapl.get_financial_metrics()
    for name, expected in AAPL_METRICS.items():
        assert metrics[name] == expected, name
    assert metrics['current_ratio'] == pytest.approx(0.988012, abs=1e-6)
    assert metrics['debt_to_assets'] == pytest.approx(0.823741, abs=1e-6)


def test_metrics_that_are_legitimately_absent_stay_absent(jpm):
    """The failure mode a shared frame invites: a missing metric silently
    acquiring another statement's number."""
    metrics = jpm.get_financial_metrics()
    for name in JPM_NONE_METRICS:
        assert metrics[name] is None, f"{name} should be None for this filer"
    for name, expected in JPM_VALUES.items():
        assert metrics[name] == expected, name


def test_the_memo_does_not_outlive_the_call(aapl, work_counter):
    """A second call must do the work again, not reuse the first call's rendering."""
    aapl.get_financial_metrics()
    first = len(work_counter['render'])
    aapl.get_financial_metrics()
    second = len(work_counter['render']) - first

    assert first == 3
    assert second == 3, "a later call reused a rendering from an earlier one"


def test_the_memo_is_absent_outside_a_metrics_call(aapl):
    assert aapl._statement_frame_memo is None
    aapl.get_financial_metrics()
    assert aapl._statement_frame_memo is None


def test_the_memo_is_discarded_when_a_getter_raises(aapl, monkeypatch):
    """Left installed, it would leak a stale rendering into every later call."""
    class Boom(Exception):
        pass

    def explode(self, *args, **kwargs):
        raise Boom()

    monkeypatch.setattr(Financials, 'get_revenue', explode)
    with pytest.raises(Boom):
        aapl.get_financial_metrics()
    assert aapl._statement_frame_memo is None


def test_a_standalone_getter_is_not_memoized(aapl, work_counter):
    """Outside a metrics call there is no memo, so each getter renders for itself
    and cannot serve a caller a rendering made for a different question."""
    assert aapl.get_revenue() == 383285000000.0
    first = len(work_counter['render'])
    assert aapl.get_revenue() == 383285000000.0
    second = len(work_counter['render']) - first

    assert first == 1
    assert second == 1
