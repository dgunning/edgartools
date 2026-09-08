"""Verification tests for CompanyReport.reports property."""
import pytest

from edgar import Filing
from edgar.company_reports import TenK
from edgar.sgml.filing_summary import Reports


@pytest.fixture(scope="module")
def apple_10k():
    """Apple 2024 10-K filing object."""
    filing = Filing(company='Apple Inc.', cik=320193, form='10-K',
                    filing_date='2024-11-01', accession_no='0000320193-24-000123')
    return filing.obj()


@pytest.mark.network
class TestCompanyReportReports:

    def test_tenk_has_reports(self, apple_10k):
        """TenK.reports returns a Reports object with entries."""
        reports = apple_10k.reports
        assert isinstance(reports, Reports)
        assert len(reports) > 0

    def test_tenk_reports_have_statements(self, apple_10k):
        """reports.statements exposes balance sheet, income, and cash flow."""
        statements = apple_10k.reports.statements
        assert statements is not None
        assert statements.balance_sheet is not None
        assert statements.income_statement is not None
        assert statements.cash_flow_statement is not None

    def test_tenk_reports_categories(self, apple_10k):
        """Notes, Tables, and Details categories are present."""
        reports = apple_10k.reports
        notes = reports.get_by_category('Notes')
        assert len(notes) > 0
        details = reports.get_by_category('Details')
        assert len(details) > 0

    def test_tenk_report_delegates_to_filing(self, apple_10k):
        """CompanyReport.reports is the same object as Filing.reports."""
        assert apple_10k.reports is apple_10k._filing.reports

    def test_filing_without_xbrl_has_no_reports(self):
        """A Form 4 filing (no FilingSummary.xml) returns None for reports."""
        filing = Filing(form='4', filing_date='2024-11-01', company='Apple Inc.',
                        cik=320193, accession_no='0000320193-24-000126')
        assert filing.reports is None
