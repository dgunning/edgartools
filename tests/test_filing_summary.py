from rich import print
import pytest
from pathlib import Path
from edgar.sgml.summary import FilingSummary, Reports, Report
from edgar.sgml import FilingSGML


@pytest.fixture
def aapl_summary():
    content = Path('data/sgml/AAPL-FilingSummary.xml').read_text()
    return FilingSummary.parse(content)

def test_parse_filing_summary():
    content = Path('data/sgml/AAPL-FilingSummary.xml').read_text()
    result = FilingSummary.parse(content)
    print(result)

def test_filing_summary_reports():
    content = Path('data/sgml/AAPL-FilingSummary.xml').read_text()
    summary = FilingSummary.parse(content)
    reports = summary.reports
    print(reports)
    report = reports[1]
    assert report
    assert reports[10]
    result = reports.next()
    assert result
    print()
    print(result)

def test_reports_filtering():
    content = Path('data/sgml/AAPL-FilingSummary.xml').read_text()
    summary = FilingSummary.parse(content)
    reports = summary.reports
    result = reports.get_by_category('Statements')
    assert len(result) == 6

def test_get_report_by_filename(aapl_summary):
    reports = aapl_summary.reports
    report = reports.get_by_filename('R72.htm')
    assert report.html_file_name == 'R72.htm'

def test_report_filtering(aapl_summary):

    report = aapl_summary.reports.filter("ShortName", "Cover Page")
    assert isinstance(report, Report)

    reports = aapl_summary.reports.filter("MenuCategory", "Cover")
    assert isinstance(reports, Reports)
    assert len(reports) == 2


def test_get_report_by_position(aapl_summary):
    report = aapl_summary.reports[1]
    assert report.position == "1"

def test_summary_names(aapl_summary):
    assert 'CONSOLIDATED BALANCE SHEETS' in aapl_summary.reports.short_names
    assert '9952153 - Statement - CONSOLIDATED BALANCE SHEETS' in aapl_summary.reports.long_names

def test_summary_statements(aapl_summary):
    statements = aapl_summary.statements
    assert(statements)
    print(statements)

    balance_sheet = statements.balance_sheet
    print(balance_sheet)

def test_report_content():
    sgml: FilingSGML = FilingSGML.from_source("data/sgml/0000320193-24-000123.txt")
    filing_summary:FilingSummary = sgml.filing_summary
    statements = filing_summary.statements
    balance_sheet = statements.balance_sheet
    content = balance_sheet.content
    assert(content)
    balance_sheet.view()

def test_summary_tables(aapl_summary):
    tables = aapl_summary.tables
    assert(tables)
    print(tables)

def test_filing_summary_repr(aapl_summary):
    result = repr(aapl_summary)
    print()
    print(result)
