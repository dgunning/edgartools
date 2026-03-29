"""
Verification tests for FundFeeNotice (24F-2NT) data object.

Ground truth filings:
  - Advisors' Inner Circle Fund (0002048251-26-002390) — 2 series, $418M sales
  - Aegis Funds — 0 series, $546M sales
"""
import pytest
from edgar.funds.twentyfourf import FundFeeNotice, SeriesInfo


# ---------------------------------------------------------------------------
# Unit tests (no network)
# ---------------------------------------------------------------------------

class TestObjInfo:

    def test_24f2nt_registered(self):
        from edgar import get_obj_info
        has_obj, class_name, desc = get_obj_info("24F-2NT")
        assert has_obj is True
        assert class_name == 'FundFeeNotice'

    def test_is_xmlfiling_subclass(self):
        from edgar.xmlfiling import XmlFiling
        assert issubclass(FundFeeNotice, XmlFiling)


class TestSeriesInfo:

    def test_series_model(self):
        s = SeriesInfo(series_name="Growth Fund", series_id="S000012345")
        assert s.series_name == "Growth Fund"
        assert s.series_id == "S000012345"
        assert s.include_all_classes is False


# ---------------------------------------------------------------------------
# Network tests — real 24F-2NT filings
# ---------------------------------------------------------------------------

@pytest.mark.network
class TestFundFeeNotice:

    def test_advisors_inner_circle(self):
        """Advisors' Inner Circle Fund — ground truth with 2 series."""
        from edgar import find
        filing = find('0002048251-26-002390')
        notice = filing.obj()

        assert isinstance(notice, FundFeeNotice)
        assert notice.form in ('24F-2NT', '24F-2NT/A')
        assert notice.fund_name == "ADVISORS' INNER CIRCLE FUND"
        assert notice.fiscal_year_end == '12/31/2025'
        assert notice.investment_company_act_file_number == '811-06400'

        # Financial data — ground truth values
        assert notice.aggregate_sales == 418915624.0
        assert notice.net_sales == 109874728.46
        assert notice.registration_fee == 15173.7
        assert notice.total_due == 15173.7

        # Series
        assert len(notice.series) == 2
        assert notice.series[0].series_name == 'Hamlin High Dividend Equity Fund'
        assert notice.series[0].series_id == 'S000036634'

    def test_zero_net_sales(self):
        """Filing with zero net sales (redemptions >= sales)."""
        from edgar import get_filings
        # Find a filing with net_sales == 0
        filings = get_filings(form='24F-2NT')
        for f in filings:
            notice = f.obj()
            if notice and notice.net_sales == 0.0:
                assert notice.aggregate_sales is not None
                assert notice.aggregate_sales >= 0
                return
        pytest.skip("No zero-net-sales filing found in recent filings")

    def test_no_series(self):
        """Filing with no series breakdown."""
        from edgar import get_filings
        filings = get_filings(form='24F-2NT')
        for f in filings:
            notice = f.obj()
            if notice and len(notice.series) == 0:
                assert notice.fund_name is not None
                assert notice.aggregate_sales is not None
                return
        pytest.skip("No no-series filing found in recent filings")

    def test_rich_display(self):
        from edgar import find
        filing = find('0002048251-26-002390')
        notice = filing.obj()
        assert notice.__rich__() is not None

    def test_to_context(self):
        from edgar import find
        filing = find('0002048251-26-002390')
        notice = filing.obj()

        ctx = notice.to_context()
        assert '24F-2NT' in ctx
        assert 'ADVISORS' in ctx
        assert '$418,915,624.00' in ctx

    def test_to_html(self):
        """XSLT-rendered HTML from SEC."""
        from edgar import find
        filing = find('0002048251-26-002390')
        notice = filing.obj()

        html = notice.to_html()
        assert html is not None
        assert '<html' in html[:500].lower()

    def test_str(self):
        from edgar import find
        filing = find('0002048251-26-002390')
        notice = filing.obj()
        s = str(notice)
        assert 'FundFeeNotice' in s
        assert '418915624' in s
