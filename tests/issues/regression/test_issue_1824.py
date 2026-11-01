"""Bounded 6-K HTML income-statement fallback, with the reported TSM amounts.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1824

SEC originals downloaded unchanged on 2026-11-01, before the implementation:
TSM 6-K 0001046179-26-000726, a3q26e_withguidancexfinal.htm (2026-10-15):
net income TWD 763,064 million, net sales TWD 1,494,243 million, EPS NT$29.43.
Comparison amounts: 2Q26 net income 706,562 million, 3Q25 452,302 million.
The latest 6-K 0001046179-26-000728 is a monthly notice, not this release.
"""
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup

from edgar._html_financials import _extract_6k_income_statement
from edgar.earnings import RowType, Scale
from edgar.entity import Company
from edgar.financials import Financials
from edgar.xbrl import XBRL

FIXTURES = Path(__file__).parents[2] / 'fixtures' / 'html' / 'issue1824'
EARNINGS = '0001046179-26-000726'
MONTHLY = '0001046179-26-000728'


class Attachment:
    def __init__(self, name, content, accession=EARNINGS):
        self.document = name
        self.document_type = 'EX-99.1'
        self.description = 'Press release'
        self.content = content
        self.url = f'https://www.sec.gov/Archives/edgar/data/1046179/{accession.replace("-", "")}/{name}'

    def is_html(self):
        return True


class Filings(list):
    def head(self, count):
        return self[:count]


def filing(accession, attachments):
    return SimpleNamespace(form='6-K', accession_no=accession, filing_date=date(2026, 10, 22),
                           attachments=attachments)


def company(filings):
    class ForeignCompany:
        latest_tenq = None

        def get_filings(self, **kwargs):
            assert kwargs == dict(form='6-K', amendments=False, trigger_full_load=False)
            return Filings(filings)

    return ForeignCompany()


@pytest.fixture
def release():
    # Discover the exhibit through the actual primary document's links.
    primary = BeautifulSoup((FIXTURES / 'tsm-20261015x6k.htm').read_text(), 'lxml')
    links = {a['href'] for a in primary.select('a[href]')}
    exhibit = 'a3q26e_withguidancexfinal.htm'
    assert exhibit in links
    return filing(EARNINGS, [Attachment(exhibit, (FIXTURES / exhibit).read_text())])


@pytest.fixture
def monthly():
    name = 'tsm-monthend6kx20261022.htm'
    # Even treating the whole monthly notice as an exhibit must not accept it.
    return filing(MONTHLY, [Attachment(name, (FIXTURES / name).read_text(), MONTHLY)])


@pytest.fixture
def no_xbrl(monkeypatch):
    monkeypatch.setattr(XBRL, 'from_filing', lambda f: None)


def test_tsm_reported_values_periods_units_and_caveat(release):
    result = _extract_6k_income_statement(release)
    assert isinstance(result, Financials)
    assert result.xb is None
    assert result.source_filing.accession_no == EARNINGS
    assert result.currency == 'TWD'
    assert result.get_currency_symbol() == 'NT$'
    assert result.get_net_income() == 763_064_000_000
    assert result.get_net_income(1) == 706_562_000_000
    assert result.get_net_income(2) == 452_302_000_000
    assert result.get_net_income(3) is None
    assert result.get_revenue() == 1_494_243_000_000
    assert result.get_gross_profit() == 992_379_000_000
    assert result.get_operating_income() == 876_445_000_000
    statement = result.income_statement()
    assert statement.scale is Scale.MILLIONS
    assert list(statement.dataframe.columns) == ['3Q26\nAmounta', '2Q26\nAmount', '3Q25\nAmount']
    assert statement.dataframe.loc['EPS (NT$)'].tolist() == [29.43, 27.25, 17.44]
    assert statement.get_row_type('EPS (NT$)', 5) is RowType.PER_SHARE
    frame = statement.to_dataframe().set_index('label')
    assert frame.loc['EPS (NT$)'].tolist() == [29.43, 27.25, 17.44]
    assert frame.loc['Net income'].tolist() == [763_064_000_000, 706_562_000_000, 452_302_000_000]
    assert frame.attrs['currency'] == 'TWD'
    exported = json.loads(statement.to_json())
    assert exported['metadata']['currency'] == 'TWD'
    assert exported['metadata']['source'] == 'HTML'
    assert any('Board of Directors' in note for note in exported['metadata']['notes'])
    with pytest.raises(NotImplementedError, match='do not synthesize XBRL facts'):
        statement.to_facts_dataframe()
    assert any('not been approved by Board of Directors' in note for note in result.notes)
    assert any('25,932 million' in note for note in result.notes)
    assert 'HTML' in str(result) and 'HTML' in result.to_context()
    assert 'actual USD' not in statement.to_context()
    assert 'not been approved by Board of Directors' in statement.to_context()
    assert result.source_url.endswith('a3q26e_withguidancexfinal.htm')
    assert result.balance_sheet() is None
    assert result.cash_flow_statement() is None
    assert result.get_total_assets() is None
    assert result.get_financial_metrics()['net_income'] == 763_064_000_000


def test_monthly_notice_is_not_a_quarterly_income_statement(monthly):
    assert _extract_6k_income_statement(monthly) is None


def test_company_passes_monthly_to_reach_real_earnings_release(release, monthly, no_xbrl):
    result = Company.get_quarterly_financials(company([monthly, release]))
    assert result.source_filing.accession_no == EARNINGS
    assert result.get_net_income() == 763_064_000_000


def test_search_is_bounded(release, monthly, no_xbrl):
    assert Company.get_quarterly_financials(company([monthly, release]), max_6k_filings=1) is None
    assert Company.get_quarterly_financials(company([])) is None


def test_xbrl_still_wins_and_does_not_download_html(release, monkeypatch):
    expected = Financials(object())
    monkeypatch.setattr(Financials, 'extract', lambda f: expected)
    release.attachments = None  # Access would fail if the HTML fallback runs.
    assert Company.get_quarterly_financials(company([release])) is expected


def test_tenq_still_wins():
    expected = object()
    c = SimpleNamespace(latest_tenq=SimpleNamespace(financials=expected))
    assert Company.get_quarterly_financials(c) is expected


@pytest.mark.parametrize('bound', [0, -1, True, 1.5, '10'])
def test_invalid_search_bound_raises(bound):
    with pytest.raises(ValueError, match='positive integer'):
        Company.get_quarterly_financials(company([]), max_6k_filings=bound)


def test_transport_failure_is_not_swallowed(release, monkeypatch):
    def fail(f):
        raise ConnectionError('SEC unavailable')

    monkeypatch.setattr(XBRL, 'from_filing', fail)
    with pytest.raises(ConnectionError, match='SEC unavailable'):
        Company.get_quarterly_financials(company([release]))


def test_unknown_currency_remains_unsupported(release):
    content = release.attachments[0].content
    release.attachments[0].content = content.replace('NT$ million', 'million')
    assert _extract_6k_income_statement(release) is None


def test_annual_or_ambiguous_periods_are_not_presented_as_quarterly(release):
    content = release.attachments[0].content
    # No quarter labels remains an annual/unknown-period table.
    release.attachments[0].content = content.replace('3Q26', '2026').replace('3Q25', '2025').replace('2Q26', '2026')
    assert _extract_6k_income_statement(release) is None
    # Two amount columns for the same quarter could be separate segments or currencies.
    release.attachments[0].content = content.replace('2Q26', '3Q26')
    assert _extract_6k_income_statement(release) is None


def test_compact_ytd_headers_are_not_quarters(release):
    content = release.attachments[0].content
    for label in ['3Q26', '3Q25', '2Q26']:
        content = content.replace(label, 'YTD ' + label)
    release.attachments[0].content = content
    assert _extract_6k_income_statement(release) is None


def test_narrative_currency_is_not_a_table_unit_declaration(release):
    original = release.attachments[0].content
    release.attachments[0].content = original.replace(
        '(Unit&#58; NT$ million, except for EPS)', 'Forecast profit in NT$ million')
    assert release.attachments[0].content != original
    assert _extract_6k_income_statement(release) is None


def test_exhibit_download_failure_is_not_swallowed(release):
    class UnavailableAttachment(Attachment):
        @property
        def content(self):
            raise ConnectionError('exhibit download failed')

    attachment = object.__new__(UnavailableAttachment)
    attachment.document = 'ex99.htm'
    attachment.document_type = 'EX-99.1'
    attachment.description = 'earnings'
    release.attachments = [attachment]
    with pytest.raises(ConnectionError, match='exhibit download failed'):
        _extract_6k_income_statement(release)


@pytest.mark.parametrize('offset', [-1, 1.5])
def test_invalid_period_offset_raises(release, offset):
    result = _extract_6k_income_statement(release)
    with pytest.raises(ValueError, match='non-negative integer'):
        result.get_net_income(offset)
