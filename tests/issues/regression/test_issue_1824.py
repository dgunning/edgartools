"""Bounded 6-K HTML income-statement fallback, with the reported TSM amounts.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1824

SEC originals downloaded unchanged on 2026-11-01, before the implementation:
TSM 6-K 0001046179-26-000726, a3q26e_withguidancexfinal.htm (2026-10-15):
net income TWD 763,064 million, net sales TWD 1,494,243 million, EPS NT$29.43.
Comparison amounts: 2Q26 net income 706,562 million, 3Q25 452,302 million.
The latest 6-K 0001046179-26-000728 is a monthly notice, not this release.
"""
import inspect
import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from lxml import html

from edgar import QuarterlyIncome
from edgar._html_financials import (
    _extract_6k_income_statement,
    _quarter_column_positions,
)
from edgar.earnings import FinancialTable, RowType, Scale
from edgar.entity import Company
from edgar.financials import Financials
from edgar.xbrl import XBRL
from edgar.xbrl.presentation import StatementView
from edgar.xbrl.statements import Statement

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
    def latest(self, count=1):
        recent = sorted(self, key=lambda f: f.filing_date, reverse=True)[:count]
        return recent[0] if len(recent) == 1 else recent or None


class SearchDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 11, 3)


@pytest.fixture(autouse=True)
def stable_search_date(monkeypatch):
    monkeypatch.setattr('edgar._html_financials.date', SearchDate)


def filing(accession, attachments, filed=date(2026, 10, 22)):
    return SimpleNamespace(form='6-K', accession_no=accession, filing_date=filed,
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
    primary = html.fromstring((FIXTURES / 'tsm-20261015x6k.htm').read_bytes())
    links = set(primary.xpath('//a/@href'))
    exhibit = 'a3q26e_withguidancexfinal.htm'
    assert exhibit in links
    return filing(EARNINGS, [Attachment(exhibit, (FIXTURES / exhibit).read_text())], date(2026, 10, 15))


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
    assert isinstance(result, QuarterlyIncome)
    assert not isinstance(result, Financials)
    assert result.source_filing.accession_no == EARNINGS
    assert result.currency == 'TWD'
    assert result.get_net_income() == 763_064_000_000
    assert result.get_net_income(1) == 706_562_000_000
    assert result.get_net_income(2) == 452_302_000_000
    assert result.get_net_income(3) is None
    assert result.get_revenue() == 1_494_243_000_000
    assert result.get_gross_profit() == 992_379_000_000
    assert result.get_operating_income() == 876_445_000_000
    statement = result
    assert statement.scale is Scale.MILLIONS
    assert list(statement.dataframe.columns) == ['3Q26\nAmounta', '2Q26\nAmount', '3Q25\nAmount']
    assert statement.dataframe.loc['EPS (NT$)'].tolist() == [29.43, 27.25, 17.44]
    assert statement.get_row_type('EPS (NT$)', 5) is RowType.PER_SHARE
    frame = statement.to_dataframe().set_index('label')
    assert frame.loc['EPS (NT$)', statement.periods].tolist() == [29.43, 27.25, 17.44]
    assert frame.loc['Net income', statement.periods].tolist() == [763_064_000_000, 706_562_000_000, 452_302_000_000]
    assert frame.attrs['currency'] == 'TWD'
    exported = json.loads(statement.to_json())
    assert exported['metadata']['currency'] == 'TWD'
    assert exported['metadata']['source'] == 'HTML'
    assert any('Board of Directors' in note for note in exported['metadata']['notes'])
    with pytest.raises(NotImplementedError, match='do not synthesize XBRL facts'):
        statement.to_facts_dataframe()
    assert any('not been approved by Board of Directors' in note for note in result.notes)
    assert any('25,932 million' in note for note in result.notes)
    assert 'actual USD' not in statement.to_context()
    assert 'TWD' in statement.to_context()
    assert result.source_url.endswith('a3q26e_withguidancexfinal.htm')
    assert isinstance(result, FinancialTable)
    assert not hasattr(result, 'balance_sheet')
    assert not hasattr(result, 'cash_flow_statement')


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


@pytest.mark.parametrize('offset', [-1, 1.5, True, '1', None])
def test_invalid_period_offset_raises(release, offset):
    result = _extract_6k_income_statement(release)
    with pytest.raises(ValueError, match='non-negative integer'):
        result.get_net_income(offset)


@pytest.fixture(scope='module')
def nvda_statement():
    # Existing, unmodified SEC XBRL fixture: 0001045810-26-000021. This pins
    # the public Statement schema, not a claim of matching TSM's fiscal dates.
    return XBRL.from_directory(Path('tests/fixtures/xbrl/nvda/10k_2026')).statements.income_statement()


def test_html_and_xbrl_share_dataframe_parameters(release):
    statement = _extract_6k_income_statement(release)
    html_params = inspect.signature(type(statement).to_dataframe).parameters
    xbrl_params = inspect.signature(Statement.to_dataframe).parameters
    assert list(html_params) == list(xbrl_params)
    assert [(p.kind, p.default) for p in html_params.values()] == [
        (p.kind, p.default) for p in xbrl_params.values()
    ]


@pytest.mark.parametrize('options', [
    {}, {'include_unit': True}, {'include_point_in_time': True},
    {'include_unit': True, 'include_point_in_time': True},
    {'standard': False}, {'include_standardization': True},
    {'standard': False, 'include_standardization': True},
    {'include_metadata': False},
])
def test_real_tsm_and_nvda_share_columns_and_standard_flag(release, nvda_statement, options):
    statement = _extract_6k_income_statement(release)
    html = statement.to_dataframe(**options)
    xbrl = nvda_statement.to_dataframe(**options)
    html_periods = set(statement.periods)
    xbrl_periods = {col for col in xbrl if col.startswith(('2026-', '2025-', '2024-'))}
    assert [col for col in html if col not in html_periods] == [col for col in xbrl if col not in xbrl_periods]
    # Source identity remains XBRL only; HTML label mappings are not source tags.
    assert html['concept'].isna().all()
    assert 'us-gaap_Revenues' in xbrl['concept'].to_numpy()
    if options.get('standard', True):
        assert set(html['standard_concept'].dropna()) <= set(xbrl['standard_concept'].dropna())
    for frame, label in [(html, 'Net sales'), (xbrl, 'Revenue')]:
        revenue = frame.loc[frame['label'] == label].iloc[0]
        if options.get('standard', True):
            assert revenue['standard_concept'] == 'Revenue'
        else:
            assert pd.isna(revenue['standard_concept'])


def test_html_units_provenance_and_missing_xbrl_metadata(release):
    statement = _extract_6k_income_statement(release)
    frame = statement.to_dataframe(include_unit=True, include_point_in_time=True).set_index('label')
    assert frame['unit'].tolist() == ['twd'] * 5 + ['twdPerShare']
    assert frame['point_in_time'].tolist() == [False] * 6
    assert frame['standard_concept'].iloc[:4].tolist() == [
        'Revenue', 'GrossProfit', 'OperatingIncomeLoss', 'PretaxIncomeLoss',
    ]
    assert frame['standard_concept'].iloc[4:].isna().all()
    # Generic net income does not establish attribution, nor EPS basic/diluted.
    assert frame.loc['Net income', '3Q26\nAmounta'] == 763_064_000_000
    assert frame.loc['EPS (NT$)', '3Q26\nAmounta'] == 29.43
    for column in ('concept', 'level', 'abstract', 'dimension', 'is_breakdown',
                   'dimension_axis', 'dimension_member', 'dimension_member_label',
                   'dimension_label', 'balance', 'weight', 'preferred_sign',
                   'parent_concept', 'parent_abstract_concept'):
        assert frame[column].isna().all(), column
    assert frame.attrs['source'] == 'HTML'
    assert frame.attrs['standardization_source'] == 'HTML exact labels'
    assert frame.attrs['period_columns'] == statement.periods
    assert frame.attrs['reported_scale'] == 1_000_000
    assert frame.attrs['source_url'].endswith('a3q26e_withguidancexfinal.htm')
    assert any('Board of Directors' in note for note in frame.attrs['notes'])


def test_period_filter_selects_reported_comparative_column_without_mutation(release):
    statement = _extract_6k_income_statement(release)
    original = statement.dataframe.copy(deep=True)
    periods = list(statement.periods)
    frame = statement.to_dataframe(period_filter='3Q25\nAmount', include_unit=True).set_index('label')
    assert frame.attrs['period_columns'] == ['3Q25\nAmount']
    assert not set(periods[:2]).intersection(frame.columns)
    assert frame.loc['Net income', '3Q25\nAmount'] == 452_302_000_000
    assert frame.loc['EPS (NT$)', '3Q25\nAmount'] == 17.44
    frame.loc['Net income', '3Q25\nAmount'] = 0
    pd.testing.assert_frame_equal(statement.dataframe, original)
    assert statement.periods == periods
    assert statement.to_dataframe().attrs['period_columns'] == periods


@pytest.mark.parametrize('value', ['', 'Q3 2025', 'duration_2025-07-01_2025-09-30', 1, True])
def test_invalid_html_period_filter_is_not_silently_ignored(release, value):
    statement = _extract_6k_income_statement(release)
    with pytest.raises(ValueError, match='period_filter.*reported columns'):
        statement.to_dataframe(period_filter=value)


@pytest.mark.parametrize('options, message', [
    ({'period_view': 'Quarterly Comparison'}, 'period_view'),
    ({'view': 'summary'}, 'view.*XBRL dimensions'),
    ({'view': StatementView.STANDARD}, 'view.*XBRL dimensions'),
    ({'presentation': False}, 'presentation=False'),
    ({'matrix': True}, 'matrix=True'),
])
def test_unavailable_xbrl_operations_raise_explicitly(release, options, message):
    statement = _extract_6k_income_statement(release)
    with pytest.raises(NotImplementedError, match=message):
        statement.to_dataframe(**options)


def test_html_table_rejects_misspelled_view(release):
    result = _extract_6k_income_statement(release)
    with pytest.raises(ValueError, match='Invalid view'):
        result.to_dataframe(view='misspelled')


@pytest.mark.parametrize('name', [
    'standard', 'include_unit', 'include_point_in_time',
    'include_standardization', 'presentation', 'matrix',
])
def test_html_boolean_parameters_reject_non_booleans(release, name):
    statement = _extract_6k_income_statement(release)
    with pytest.raises(ValueError, match=f'{name} must be a boolean'):
        statement.to_dataframe(**{name: 1})


def test_html_period_view_type_and_unknown_keywords_raise(release):
    statement = _extract_6k_income_statement(release)
    with pytest.raises(ValueError, match='period_view must be a string'):
        statement.to_dataframe(period_view=1)
    with pytest.raises(TypeError, match='unexpected keyword argument.*include_unt'):
        statement.to_dataframe(include_unt=True)


def test_explicit_concept_labels_map_but_ambiguous_and_adjusted_labels_do_not(release):
    # In-memory mutations test the inference boundary; SEC fixture bytes stay intact.
    statement = _extract_6k_income_statement(release)
    statement.dataframe.index = [
        'Adjusted revenue', 'Revenue growth', 'Net income attributable to owners of the parent',
        'Unrecognized income', 'Profit (loss)', 'Diluted EPS (NT$)',
    ]
    frame = statement.to_dataframe()
    assert frame['standard_concept'].iloc[[0, 1, 3]].isna().all()
    assert frame['standard_concept'].iloc[[2, 4, 5]].tolist() == ['NetIncome', 'ProfitLoss', 'EarningsPerShareDiluted']
    assert frame['concept'].isna().all()
    statement.dataframe.index = [*statement.dataframe.index[:-1], 'Basic earnings per share (NT$)']
    assert statement.to_dataframe()['standard_concept'].iloc[-1] == 'EarningsPerShareBasic'
    assert frame['label'].iloc[-1] == 'Diluted EPS (NT$)'


def test_row_types_and_explicit_row_currency_determine_units(release):
    statement = _extract_6k_income_statement(release)
    statement.row_types = [RowType.AMOUNT, RowType.SHARES, RowType.PERCENTAGE,
                           RowType.OTHER, RowType.AMOUNT, RowType.PER_SHARE]
    statement.dataframe.index = [*statement.dataframe.index[:-1], 'EPS (US$)']
    frame = statement.to_dataframe(include_unit=True)
    assert frame['unit'].iloc[[0, 1, 2, 4, 5]].tolist() == ['twd', 'shares', 'percent', 'twd', 'usdPerShare']
    assert pd.isna(frame['unit'].iloc[3])
    assert frame['3Q26\nAmounta'].tolist() == [1_494_243_000_000, 992_379, 876_445, 911_039, 763_064_000_000, 29.43]


@pytest.mark.parametrize('label', ['Basic EPS (non-GAAP)', 'Diluted EPS (adjusted)', 'Adjusted diluted EPS (NT$)'])
def test_adjusted_eps_qualifiers_do_not_become_standard_gaap_eps(release, label):
    statement = _extract_6k_income_statement(release)
    statement.dataframe.index = [*statement.dataframe.index[:-1], label]
    frame = statement.to_dataframe()
    assert pd.isna(frame['standard_concept'].iloc[-1])
    assert frame['3Q26\nAmounta'].iloc[-1] == 29.43


@pytest.mark.parametrize('label', ['EPS (NT$ / US$)', 'EPS (GBP)', 'EPS ($)'])
def test_uncertain_row_currency_stays_null(release, label):
    statement = _extract_6k_income_statement(release)
    statement.dataframe.index = [*statement.dataframe.index[:-1], label]
    frame = statement.to_dataframe(include_unit=True)
    assert pd.isna(frame['unit'].iloc[-1])
    assert frame['3Q26\nAmounta'].iloc[-1] == 29.43


def test_newest_earnings_wins_even_when_filings_are_unsorted(release, monkeypatch):
    older = filing('older', [], date(2026, 9, 1))
    probed = []

    def extract(candidate):
        probed.append(candidate.accession_no)
        return Financials(object())

    monkeypatch.setattr(Financials, 'extract', extract)
    assert Company.get_quarterly_financials(company([older, release]), max_6k_filings=1) is not None
    assert probed == [EARNINGS]


def test_single_filing_return_from_latest_is_supported(release, no_xbrl):
    c = company([])
    c.get_filings = lambda **kwargs: SimpleNamespace(latest=lambda n=1: release)
    assert Company.get_quarterly_financials(c, max_6k_filings=1).get_net_income() == 763_064_000_000


@pytest.mark.parametrize('age, expected_probes', [(183, 1), (184, 0), (550, 0), (-1, 0)])
def test_search_age_boundary_before_any_download(release, monkeypatch, age, expected_probes):
    release.filing_date = SearchDate.today() - timedelta(days=age)
    probed = []
    monkeypatch.setattr(Financials, 'extract', lambda candidate: probed.append(candidate))
    # No attachments can be inspected for expired/future filings.
    release.attachments = [] if expected_probes else None
    assert Company.get_quarterly_financials(company([release])) is None
    assert len(probed) == expected_probes


def test_known_untagged_monthly_notice_is_screened_using_index(release, monthly, monkeypatch):
    monthly.is_xbrl = False
    monthly.attachments = []
    probed = []

    def extract(candidate):
        probed.append(candidate.accession_no)
        return None

    monkeypatch.setattr(Financials, 'extract', extract)
    result = Company.get_quarterly_financials(company([release, monthly]))
    assert result.get_net_income() == 763_064_000_000
    assert probed == [EARNINGS]


def test_attachment_index_can_skip_monthly_notice_without_loading_submission(release, monkeypatch):
    class IndexedNotice:
        form = '6-K'
        accession_no = MONTHLY
        filing_date = date(2026, 10, 22)
        is_xbrl = False
        homepage = SimpleNamespace(attachments=[])

        @property
        def attachments(self):
            raise AssertionError('Monthly notice must not download the full SGML submission')

    probed = []
    monkeypatch.setattr(Financials, 'extract', lambda candidate: probed.append(candidate.accession_no))
    result = Company.get_quarterly_financials(company([release, IndexedNotice()]))
    assert result.get_net_income() == 763_064_000_000
    assert probed == [EARNINGS]


def test_attachment_index_download_error_is_not_swallowed():
    class UnavailableIndex:
        accession_no = MONTHLY
        filing_date = date(2026, 10, 22)
        is_xbrl = False

        @property
        def homepage(self):
            raise ConnectionError('attachment index unavailable')

    with pytest.raises(ConnectionError, match='attachment index unavailable'):
        Company.get_quarterly_financials(company([UnavailableIndex()]))


def test_xbrl_data_files_are_not_screened_out_by_negative_flag(release, monkeypatch):
    class Index(list):
        data_files = ['instance.xml']

    release.is_xbrl = '0'
    release.attachments = Index()
    expected = Financials(object())
    monkeypatch.setattr(Financials, 'extract', lambda candidate: expected)
    assert Company.get_quarterly_financials(company([release])) is expected


@pytest.mark.parametrize('flag', [False, True, None])
def test_earnings_exhibit_still_probes_xbrl_before_html(release, monkeypatch, flag):
    release.is_xbrl = flag
    expected = Financials(object())
    monkeypatch.setattr(Financials, 'extract', lambda candidate: expected)
    assert Company.get_quarterly_financials(company([release])) is expected


@pytest.mark.parametrize('printed', [5000, -5000])
def test_explicit_losses_have_negative_values_in_every_view(release, printed):
    original = pd.DataFrame({'3Q26': [10000, printed, printed]},
                            index=['Revenue', 'Operating loss', 'Net loss'])
    before = original.copy(deep=True)
    statement = QuarterlyIncome(
        source_filing=release, dataframe=original, scale=Scale.MILLIONS, currency='TWD', periods=['3Q26'],
        row_types=[RowType.AMOUNT] * 3)
    assert statement.get_operating_income() == -5_000_000_000
    assert statement.get_net_income() == -5_000_000_000
    assert statement.dataframe['3Q26'].tolist() == [10000, -5000, -5000]
    exported = statement.to_dataframe().set_index('label')
    assert exported.loc['Operating loss', '3Q26'] == -5_000_000_000
    assert exported.loc['Operating loss', 'standard_concept'] == 'OperatingIncomeLoss'
    pd.testing.assert_frame_equal(original, before)


def test_income_loss_label_does_not_imply_negative_sign(release):
    table = QuarterlyIncome(pd.DataFrame({'3Q26': [50]}, index=['Net income (loss)']), periods=['3Q26'])
    assert table.get_net_income() == 50


def test_whitespace_normalization_is_shared_by_getters_and_mapping(release):
    original = release.attachments[0].content
    release.attachments[0].content = original.replace('Net sales', 'Net&#160;  sales').replace(
        'Gross profit', 'Gross&#160;  profit')
    result = _extract_6k_income_statement(release)
    assert result.get_revenue() == 1_494_243_000_000
    assert result.get_gross_profit() == 992_379_000_000
    frame = result.to_dataframe()
    assert frame['standard_concept'].iloc[:2].tolist() == ['Revenue', 'GrossProfit']


@pytest.mark.parametrize('fiscal_end, compact', [('1231', '3Q26'), ('0630', '1Q27')])
def test_dated_and_compact_headers_for_one_quarter_are_deduplicated(fiscal_end, compact):
    table = FinancialTable(pd.DataFrame(
        [[10, 10, 8], [2, 2, 1]], index=['Revenue', 'Net income'],
        columns=['Three Months Ended September 30, 2026', compact, '2Q26']))
    assert _quarter_column_positions(table, 2026, fiscal_end) == [0, 2]
    table.dataframe.iloc[1, 1] = 3
    assert _quarter_column_positions(table, 2026, fiscal_end) == []


def test_mixed_headers_without_fiscal_calendar_are_not_guessed():
    table = FinancialTable(pd.DataFrame([[10, 10]], columns=[
        'Three Months Ended September 30, 2026', '3Q26']))
    assert _quarter_column_positions(table, 2026) == []


@pytest.mark.parametrize('fiscal_end', ['', 1231, '1331', '0230', '123'])
def test_malformed_fiscal_calendar_does_not_abort_search(fiscal_end):
    table = FinancialTable(pd.DataFrame([[10]], columns=['3Q26']))
    assert _quarter_column_positions(table, 2026, fiscal_end) == []


def test_missing_table_index_is_not_a_search_error(release, monkeypatch):
    from edgar.earnings import EarningsRelease

    real = EarningsRelease(release.attachments[0]).income_statement
    real.raw_index = 10000
    monkeypatch.setattr(EarningsRelease, 'income_statement', property(lambda self: real))
    assert _extract_6k_income_statement(release) is None
