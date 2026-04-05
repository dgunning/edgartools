"""
Verification tests for N-CSR/N-CSRS Fund Shareholder Report data object.

Ground truth filings:
  - Annual (N-CSR): ALGER PORTFOLIOS (accession 0001133228-26-002293)
  - Semi-Annual (N-CSRS): AMERICAN CENTURY QUANTITATIVE EQUITY FUNDS (accession 0000827060-26-000002)
"""
from decimal import Decimal

import pandas as pd
import pytest

from edgar import get_by_accession_number
from edgar.funds.ncsr import (
    NCSR_FORMS,
    AnnualReturn,
    FundShareholderReport,
    Holding,
    ShareClassInfo,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def annual_report():
    """ALGER PORTFOLIOS — N-CSR, 7 share classes."""
    filing = get_by_accession_number("0001133228-26-002293")
    return filing.obj()


@pytest.fixture(scope="module")
def semiannual_report():
    """AMERICAN CENTURY QUANTITATIVE EQUITY FUNDS — N-CSRS."""
    filing = get_by_accession_number("0000827060-26-000002")
    return filing.obj()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:

    def test_ncsr_forms(self):
        assert NCSR_FORMS == ["N-CSR", "N-CSR/A", "N-CSRS", "N-CSRS/A"]


# ---------------------------------------------------------------------------
# obj() dispatch
# ---------------------------------------------------------------------------

class TestObjDispatch:

    def test_ncsr_returns_fund_shareholder_report(self, annual_report):
        assert isinstance(annual_report, FundShareholderReport)

    def test_ncsrs_returns_fund_shareholder_report(self, semiannual_report):
        assert isinstance(semiannual_report, FundShareholderReport)


# ---------------------------------------------------------------------------
# Annual report (N-CSR) — ALGER PORTFOLIOS
# ---------------------------------------------------------------------------

class TestAnnualReport:

    def test_fund_name(self, annual_report):
        assert "Alger" in annual_report.fund_name

    def test_report_type_annual(self, annual_report):
        assert annual_report.report_type == "Annual"

    def test_is_annual(self, annual_report):
        assert annual_report.is_annual is True

    def test_portfolio_turnover(self, annual_report):
        """Ground-truth: Alger Capital Appreciation Portfolio turnover = 75.67%."""
        assert annual_report.portfolio_turnover == Decimal("0.7567")

    def test_num_share_classes(self, annual_report):
        assert annual_report.num_share_classes == 7

    def test_share_class_has_expense_ratio(self, annual_report):
        """Ground-truth: at least one class has expense ratio 0.0094 (0.94%)."""
        ratios = [sc.expense_ratio_pct for sc in annual_report.share_classes
                  if sc.expense_ratio_pct is not None]
        assert Decimal("0.0094") in ratios

    def test_share_class_has_expenses_paid(self, annual_report):
        """At least one class has a non-None expenses_paid_amt."""
        paid = [sc.expenses_paid_amt for sc in annual_report.share_classes
                if sc.expenses_paid_amt is not None]
        assert len(paid) > 0

    def test_share_class_has_advisory_fees(self, annual_report):
        fees = [sc.advisory_fees_paid for sc in annual_report.share_classes
                if sc.advisory_fees_paid is not None]
        assert len(fees) > 0

    def test_annual_returns_present(self, annual_report):
        """Each share class should have annual return entries."""
        for sc in annual_report.share_classes:
            assert len(sc.annual_returns) > 0

    def test_holdings_count(self, annual_report):
        """At least one class reports a holdings count."""
        counts = [sc.holdings_count for sc in annual_report.share_classes
                  if sc.holdings_count is not None]
        assert len(counts) > 0


# ---------------------------------------------------------------------------
# Semi-annual report (N-CSRS)
# ---------------------------------------------------------------------------

class TestSemiAnnualReport:

    def test_report_type_semiannual(self, semiannual_report):
        assert semiannual_report.report_type == "Semi-Annual"

    def test_is_annual_false(self, semiannual_report):
        assert semiannual_report.is_annual is False

    def test_has_share_classes(self, semiannual_report):
        assert semiannual_report.num_share_classes > 0

    def test_fund_name(self, semiannual_report):
        assert len(semiannual_report.fund_name) > 0


# ---------------------------------------------------------------------------
# DataFrame methods
# ---------------------------------------------------------------------------

class TestDataFrames:

    def test_expense_data_returns_dataframe(self, annual_report):
        df = annual_report.expense_data()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    def test_expense_data_columns(self, annual_report):
        df = annual_report.expense_data()
        expected = {"class_name", "ticker", "expense_ratio_pct", "expenses_paid", "advisory_fees_paid"}
        assert expected == set(df.columns)

    def test_performance_data_returns_dataframe(self, annual_report):
        df = annual_report.performance_data()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    def test_performance_data_columns(self, annual_report):
        df = annual_report.performance_data()
        expected = {"class_name", "ticker", "period", "return_pct", "inception_date"}
        assert expected == set(df.columns)

    def test_holdings_data_returns_dataframe(self, annual_report):
        df = annual_report.holdings_data()
        assert isinstance(df, pd.DataFrame)
        # holdings_data may be empty if no individual holdings are reported

    def test_holdings_data_columns(self, annual_report):
        df = annual_report.holdings_data()
        if not df.empty:
            expected = {"class_name", "holding", "pct_of_nav", "pct_of_total_inv"}
            assert expected == set(df.columns)


# ---------------------------------------------------------------------------
# Rich display
# ---------------------------------------------------------------------------

class TestRichDisplay:

    def test_repr_not_empty(self, annual_report):
        text = repr(annual_report)
        assert len(text) > 0

    def test_str_contains_class_name(self, annual_report):
        text = str(annual_report)
        assert "FundShareholderReport" in text

    def test_repr_contains_fund_name(self, annual_report):
        text = repr(annual_report)
        assert "Alger" in text


# ---------------------------------------------------------------------------
# Silence check — missing XBRL
# ---------------------------------------------------------------------------

class TestSilenceCheck:

    def test_from_filing_returns_none_for_no_xbrl(self):
        """from_filing should return None when XBRL is missing, not crash."""

        class FakeFiling:
            form = "N-CSR"
            def xbrl(self):
                return None

        result = FundShareholderReport.from_filing(FakeFiling())
        assert result is None
