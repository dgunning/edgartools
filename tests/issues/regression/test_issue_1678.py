"""Regression: a 10-Q whose dei:DocumentFiscalPeriodFocus is FY got annual
periods, so its income and cash-flow getters returned None.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1678

``_select_duration_periods`` took the annual branch when fiscal_period == 'FY',
whatever the document type. BXP's Q2 2026 10-Q (DocumentType 10-Q,
DocumentQuarterlyReport true) mis-tags its focus FY and also carries note-only
annual durations (2025-01-01 to 2025-12-31 and a 303-day period), so the income
statement showed only those columns and revenue, net income, operating cash
flow and both share counts came back None. The FY tag no longer overrides a
quarterly document type, mirroring the #600 rule for a 10-K tagged Q4.
"""
import pytest

from edgar.xbrl.period_selector import _select_duration_periods

PERIODS = [
    {'type': 'duration', 'start_date': '2026-04-01', 'end_date': '2026-06-30', 'key': 'q2_2026', 'label': 'Q2 2026'},
    {'type': 'duration', 'start_date': '2025-04-01', 'end_date': '2025-06-30', 'key': 'q2_2025', 'label': 'Q2 2025'},
    {'type': 'duration', 'start_date': '2026-01-01', 'end_date': '2026-06-30', 'key': 'h1_2026', 'label': 'H1 2026'},
    {'type': 'duration', 'start_date': '2025-01-01', 'end_date': '2025-12-31', 'key': 'fy_2025', 'label': 'FY 2025'},
    {'type': 'duration', 'start_date': '2025-02-15', 'end_date': '2025-12-15', 'key': 'odd_2025', 'label': '303 days'},
]


@pytest.mark.fast
def test_a_quarterly_document_tagged_fy_gets_quarterly_periods():
    entity_info = {'fiscal_period': 'FY', 'document_type': '10-Q',
                   'quarterly_report': True, 'annual_report': False}
    keys = [key for key, _ in _select_duration_periods(PERIODS, entity_info, 4, '2026-06-30')]
    assert 'q2_2026' in keys
    assert 'fy_2025' not in keys and 'odd_2025' not in keys


@pytest.mark.fast
@pytest.mark.parametrize("entity_info", [
    {'fiscal_period': 'FY', 'document_type': '10-K', 'quarterly_report': False, 'annual_report': True},
    {'fiscal_period': 'Q4', 'document_type': '10-K', 'quarterly_report': False, 'annual_report': True},  # #600
    {'fiscal_period': 'FY'},  # no document type at all: the focus tag still decides
])
def test_annual_documents_still_get_annual_periods(entity_info):
    keys = [key for key, _ in _select_duration_periods(PERIODS, entity_info, 4, '2025-12-31')]
    assert keys[0] in ('fy_2025', 'odd_2025')
    assert 'q2_2026' not in keys


def _balance_sheet_views(fiscal_period, quarterly_report):
    """get_period_views for a balance sheet with four year-end instants and the
    quarter-end, on a filer whose fiscal year ends 12-31."""
    from types import SimpleNamespace

    from edgar.xbrl.periods import get_period_views

    instants = [{'type': 'instant', 'date': d, 'key': f'instant_{d}', 'label': d}
                for d in ('2026-06-30', '2025-12-31', '2024-12-31', '2023-12-31')]
    xbrl = SimpleNamespace(
        entity_info={'fiscal_period': fiscal_period, 'quarterly_report': quarterly_report,
                     'fiscal_year_end_month': 12, 'fiscal_year_end_day': 31},
        reporting_periods=instants, period_of_report='2026-06-30')
    return [view['name'] for view in get_period_views(xbrl, 'BalanceSheet')]


@pytest.mark.fast
def test_named_views_do_not_treat_a_quarterly_document_tagged_fy_as_annual():
    """The named-view path (period_view=) applied the same FY-only test."""
    assert 'Three-Year Annual Comparison' in _balance_sheet_views('FY', False)
    assert 'Three-Year Annual Comparison' not in _balance_sheet_views('FY', True)
    assert 'Three-Year Annual Comparison' not in _balance_sheet_views('Q2', True)


def _xbrl_only(**filing):
    """The filing's XBRL, read from the documents its index page lists
    (FilingSGML.from_homepage), so the cassette holds only the files parsed."""
    from edgar import Filing
    from edgar.sgml.sgml_common import FilingSGML

    filing = Filing(**filing)
    filing._sgml = FilingSGML.from_homepage(filing.homepage)
    return filing.xbrl()


@pytest.mark.network
@pytest.mark.vcr
def test_bxp_quarter_tagged_fy_reports_its_quarter():
    """BXP 10-Q 2026-06-30, 0001037540-26-000034: Revenues 895,699 (f-215), net income
    attributable 68,564 (f-295), six-month operating cash flow 602,524 (f-599),
    weighted average shares 159,167 basic and 159,629 diluted ($K / thousands)."""
    from edgar.financials import Financials

    xbrl = _xbrl_only(form='10-Q', filing_date='2026-08-06', company='BXP, Inc.',
                      cik=1037540, accession_no='0001037540-26-000034')
    assert xbrl.entity_info['fiscal_period'] == 'FY'
    assert xbrl.entity_info['quarterly_report'] is True

    bxp = Financials(xbrl)
    assert bxp.get_revenue() == 895699000
    assert bxp.get_net_income() == 68564000
    assert bxp.get_operating_cash_flow() == 602524000
    assert bxp.get_shares_outstanding_basic() == 159167000
    assert bxp.get_shares_outstanding_diluted() == 159629000
