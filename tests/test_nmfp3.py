"""
Tests for N-MFP Money Market Fund data object (N-MFP2 and N-MFP3).

Ground truth filings:
  N-MFP3: AB Fixed Income Shares, accession 0001410368-26-010417, report date 2026-01-31
  N-MFP2: AB Fixed Income Shares, accession 0001145549-23-075236, report date 2023-11-30
"""
from decimal import Decimal

import pytest

from edgar import get_by_accession_number
from edgar.funds.nmfp3 import MoneyMarketFund, NMFP2_FORMS, NMFP3_FORMS, MONEY_MARKET_FORMS

# Cache the filing and parsed object for all tests in this module
_filing = None
_mmf = None


def get_filing():
    global _filing
    if _filing is None:
        _filing = get_by_accession_number("0001410368-26-010417")
    return _filing


def get_mmf():
    global _mmf
    if _mmf is None:
        filing = get_filing()
        _mmf = filing.obj()
    return _mmf


class TestNMFP3Constants:

    def test_nmfp3_forms(self):
        assert "N-MFP3" in NMFP3_FORMS
        assert "N-MFP3/A" in NMFP3_FORMS


class TestNMFP3GeneralInfo:

    def test_series_name(self):
        mmf = get_mmf()
        assert "AB Government Money Market Portfolio" in mmf.name

    def test_series_id(self):
        mmf = get_mmf()
        assert mmf.general_info.series_id == "S000011990"

    def test_total_share_classes(self):
        mmf = get_mmf()
        assert mmf.general_info.total_share_classes == 7

    def test_report_date(self):
        mmf = get_mmf()
        assert mmf.report_date == "2026-01-31"

    def test_registrant_name(self):
        mmf = get_mmf()
        assert "AllianceBernstein" in mmf.general_info.registrant_name

    def test_cik(self):
        mmf = get_mmf()
        assert mmf.general_info.cik == "0000862021"

    def test_registrant_lei(self):
        mmf = get_mmf()
        assert mmf.general_info.registrant_lei == "254900AM6NTI6YO2LI69"


class TestNMFP3SeriesInfo:

    def test_net_assets(self):
        mmf = get_mmf()
        assert mmf.net_assets == Decimal("26435168844.97")

    def test_fund_category(self):
        mmf = get_mmf()
        assert mmf.fund_category == "Government"

    def test_avg_portfolio_maturity(self):
        mmf = get_mmf()
        assert mmf.average_maturity_wam == 52

    def test_avg_life_maturity(self):
        mmf = get_mmf()
        assert mmf.average_maturity_wal == 88

    def test_stable_price(self):
        mmf = get_mmf()
        assert mmf.series_info.seek_stable_price is True
        assert mmf.series_info.stable_price_per_share == Decimal("1.0000")

    def test_cash(self):
        mmf = get_mmf()
        assert mmf.series_info.cash == Decimal("752624.71")


class TestNMFP3Securities:

    def test_num_securities(self):
        mmf = get_mmf()
        assert mmf.num_securities == 77

    def test_first_security_cusip(self):
        mmf = get_mmf()
        # Securities sorted by market value desc in portfolio_data,
        # but raw list is XML order
        first = mmf.securities[0]
        assert first.cusip == "05252T001"

    def test_first_security_market_value(self):
        mmf = get_mmf()
        first = mmf.securities[0]
        assert first.market_value == Decimal("2300000000.00")

    def test_first_security_issuer(self):
        mmf = get_mmf()
        first = mmf.securities[0]
        assert "Australia" in first.issuer_name
        assert "New Zealand" in first.issuer_name

    def test_first_security_yield(self):
        mmf = get_mmf()
        first = mmf.securities[0]
        assert first.yield_rate == Decimal("0.0369")

    def test_first_security_category(self):
        mmf = get_mmf()
        first = mmf.securities[0]
        assert "U.S. Treasury Repurchase Agreement" in first.investment_category

    def test_first_security_liquidity_flags(self):
        mmf = get_mmf()
        first = mmf.securities[0]
        assert first.daily_liquid is True
        assert first.weekly_liquid is True
        assert first.illiquid is False

    def test_security_with_isin(self):
        """Security index 2 has ISIN."""
        mmf = get_mmf()
        sec = mmf.securities[2]
        assert sec.isin == "US3130B3QB27"

    def test_security_with_ratings(self):
        """Security index 17 has NRSRO ratings."""
        mmf = get_mmf()
        sec = mmf.securities[17]
        assert len(sec.ratings) >= 4
        agencies = {r.agency for r in sec.ratings}
        assert "Moody's Investors Service, Inc." in agencies
        # Check one specific rating
        moodys = [r for r in sec.ratings if "Moody" in r.agency][0]
        assert moodys.rating == "P-1"


class TestNMFP3RepurchaseAgreement:

    def test_first_security_has_repo(self):
        mmf = get_mmf()
        first = mmf.securities[0]
        assert first.repo_agreement is not None

    def test_first_security_collateral_count(self):
        mmf = get_mmf()
        first = mmf.securities[0]
        assert len(first.repo_agreement.collateral) == 21

    def test_collateral_issuer_details(self):
        mmf = get_mmf()
        first_coll = mmf.securities[0].repo_agreement.collateral[0]
        assert "U.S. Treasury Bond" in first_coll.issuer_name
        assert first_coll.maturity_date == "2045-02-28"
        assert first_coll.principal_amount == Decimal("50662313.00")

    def test_repo_flags(self):
        mmf = get_mmf()
        repo = mmf.securities[0].repo_agreement
        assert repo.open_flag is False
        assert repo.cleared_flag is False
        assert repo.tri_party_flag is False


class TestNMFP3ShareClasses:

    def test_num_share_classes(self):
        mmf = get_mmf()
        assert mmf.num_share_classes == 7

    def test_first_class_id(self):
        mmf = get_mmf()
        first = mmf.share_classes[0]
        assert first.class_id == "C000032709"

    def test_first_class_name(self):
        mmf = get_mmf()
        first = mmf.share_classes[0]
        assert first.class_name == "Class AB"

    def test_first_class_net_assets(self):
        mmf = get_mmf()
        first = mmf.share_classes[0]
        assert first.net_assets == Decimal("8365088532.18")

    def test_first_class_daily_flows(self):
        mmf = get_mmf()
        first = mmf.share_classes[0]
        assert len(first.daily_flows) == 20
        flow = first.daily_flows[0]
        assert flow["date"] == "2026-01-02"
        assert flow["gross_subscriptions"] == Decimal("324604511.74")

    def test_first_class_seven_day_yield(self):
        mmf = get_mmf()
        first = mmf.share_classes[0]
        assert len(first.seven_day_net_yields) == 20
        y = first.seven_day_net_yields[0]
        assert y["date"] == "2026-01-02"
        assert y["net_yield"] == Decimal("0.0365")


class TestNMFP3YieldHistory:

    def test_yield_history_shape(self):
        mmf = get_mmf()
        yh = mmf.yield_history()
        assert len(yh) == 20
        assert "date" in yh.columns
        assert "gross_yield" in yh.columns

    def test_first_gross_yield(self):
        mmf = get_mmf()
        yh = mmf.yield_history()
        assert yh.iloc[0]["gross_yield"] == Decimal("0.0386")
        assert yh.iloc[0]["date"] == "2026-01-02"


class TestNMFP3DataFrames:

    def test_portfolio_data_shape(self):
        mmf = get_mmf()
        pdf = mmf.portfolio_data()
        assert len(pdf) == 77
        assert "issuer" in pdf.columns
        assert "market_value" in pdf.columns
        assert "cusip" in pdf.columns

    def test_portfolio_data_sorted_by_market_value(self):
        mmf = get_mmf()
        pdf = mmf.portfolio_data()
        values = pdf["market_value"].dropna().tolist()
        assert values == sorted(values, reverse=True)

    def test_share_class_data_shape(self):
        mmf = get_mmf()
        scd = mmf.share_class_data()
        assert len(scd) == 7
        assert "class_name" in scd.columns
        assert "class_id" in scd.columns
        assert "net_assets" in scd.columns

    def test_nav_history_shape(self):
        mmf = get_mmf()
        nh = mmf.nav_history()
        assert len(nh) == 20
        assert "date" in nh.columns
        assert "nav_per_share" in nh.columns

    def test_liquidity_history_shape(self):
        mmf = get_mmf()
        lh = mmf.liquidity_history()
        assert len(lh) == 20
        assert "pct_daily_liquid" in lh.columns
        assert "pct_weekly_liquid" in lh.columns

    def test_collateral_data(self):
        mmf = get_mmf()
        cd = mmf.collateral_data()
        assert len(cd) > 0
        assert "collateral_issuer" in cd.columns
        assert "collateral_value" in cd.columns
        assert "principal_amount" in cd.columns

    def test_holdings_by_category(self):
        mmf = get_mmf()
        hbc = mmf.holdings_by_category()
        assert len(hbc) > 0
        assert "category" in hbc.columns
        assert "count" in hbc.columns
        assert "total_market_value" in hbc.columns


class TestNMFP3Display:

    def test_repr_does_not_error(self):
        mmf = get_mmf()
        r = repr(mmf)
        assert isinstance(r, str)
        assert len(r) > 0

    def test_rich_returns_panel(self):
        mmf = get_mmf()
        panel = mmf.__rich__()
        from rich.panel import Panel
        assert isinstance(panel, Panel)

    def test_str(self):
        mmf = get_mmf()
        s = str(mmf)
        assert "MoneyMarketFund" in s
        assert "77 securities" in s


class TestNMFP3FromFiling:

    def test_from_filing(self):
        filing = get_filing()
        mmf = MoneyMarketFund.from_filing(filing)
        assert mmf is not None
        assert mmf.num_securities == 77

    def test_filing_obj_returns_money_market_fund(self):
        filing = get_filing()
        result = filing.obj()
        assert isinstance(result, MoneyMarketFund)


# ===================================================================
# N-MFP2 Tests
# Ground truth: AB Fixed Income Shares, accession 0001145549-23-075236
# ===================================================================

_v2_filing = None
_v2_mmf = None


def get_v2_filing():
    global _v2_filing
    if _v2_filing is None:
        _v2_filing = get_by_accession_number("0001145549-23-075236")
    return _v2_filing


def get_v2_mmf():
    global _v2_mmf
    if _v2_mmf is None:
        filing = get_v2_filing()
        _v2_mmf = filing.obj()
    return _v2_mmf


class TestNMFP2Constants:

    def test_nmfp2_forms(self):
        assert "N-MFP2" in NMFP2_FORMS
        assert "N-MFP2/A" in NMFP2_FORMS

    def test_money_market_forms_includes_both(self):
        assert "N-MFP2" in MONEY_MARKET_FORMS
        assert "N-MFP3" in MONEY_MARKET_FORMS


class TestNMFP2GeneralInfo:

    def test_report_date(self):
        mmf = get_v2_mmf()
        assert mmf.report_date == "2023-11-30"

    def test_cik(self):
        mmf = get_v2_mmf()
        assert mmf.general_info.cik == "0000862021"

    def test_series_id(self):
        mmf = get_v2_mmf()
        assert mmf.general_info.series_id == "S000011990"

    def test_total_share_classes(self):
        mmf = get_v2_mmf()
        assert mmf.general_info.total_share_classes == 8

    def test_v2_lacks_registrant_name(self):
        """N-MFP2 does not include registrantFullName."""
        mmf = get_v2_mmf()
        assert mmf.general_info.registrant_name == ""

    def test_v2_lacks_series_name(self):
        """N-MFP2 does not include nameOfSeries."""
        mmf = get_v2_mmf()
        assert mmf.name == ""


class TestNMFP2SeriesInfo:

    def test_net_assets(self):
        mmf = get_v2_mmf()
        assert mmf.net_assets == Decimal("21631114804.65")

    def test_fund_category(self):
        mmf = get_v2_mmf()
        assert mmf.fund_category == "Exempt Government"

    def test_avg_portfolio_maturity(self):
        mmf = get_v2_mmf()
        assert mmf.average_maturity_wam == 37

    def test_avg_life_maturity(self):
        mmf = get_v2_mmf()
        assert mmf.average_maturity_wal == 103

    def test_stable_price(self):
        mmf = get_v2_mmf()
        assert mmf.series_info.stable_price_per_share == Decimal("1.0000")

    def test_cash(self):
        mmf = get_v2_mmf()
        assert mmf.series_info.cash == Decimal("685104.81")


class TestNMFP2TimeSeries:

    def test_yield_history_single_scalar(self):
        """N-MFP2 has a single gross yield value, not daily entries."""
        mmf = get_v2_mmf()
        yh = mmf.yield_history()
        assert len(yh) == 1
        assert yh.iloc[0]["gross_yield"] == Decimal("0.0541")

    def test_nav_history_weekly(self):
        """N-MFP2 NAV uses fridayWeek1-5 (zero weeks excluded)."""
        mmf = get_v2_mmf()
        nh = mmf.nav_history()
        assert len(nh) >= 1
        assert nh.iloc[0]["date"] == "week_1"
        assert nh.iloc[0]["nav_per_share"] == Decimal("1.0000")

    def test_liquidity_history_friday_snapshots(self):
        """N-MFP2 liquidity uses Friday snapshots."""
        mmf = get_v2_mmf()
        lh = mmf.liquidity_history()
        assert len(lh) >= 4
        assert lh.iloc[0]["date"] == "friday_1"
        assert lh.iloc[0]["pct_daily_liquid"] == Decimal("0.7000")
        assert lh.iloc[0]["pct_weekly_liquid"] == Decimal("0.7119")


class TestNMFP2Securities:

    def test_num_securities(self):
        mmf = get_v2_mmf()
        assert mmf.num_securities == 110

    def test_first_security(self):
        mmf = get_v2_mmf()
        sec = mmf.securities[0]
        assert "Bank of America" in sec.issuer_name
        assert sec.market_value == Decimal("90000000.00")
        assert sec.yield_rate == Decimal("0.0532")

    def test_first_security_repo_collateral(self):
        mmf = get_v2_mmf()
        sec = mmf.securities[0]
        assert sec.repo_agreement is not None
        assert len(sec.repo_agreement.collateral) == 1
        coll = sec.repo_agreement.collateral[0]
        assert "U.S. Treasury Note" in coll.issuer_name
        assert coll.coupon == Decimal("4.125000")
        assert coll.maturity_date == "2026-06-15"

    def test_cusip_fallback_to_other_unique_id(self):
        """N-MFP2 securities without CUSIPMember use otherUniqueId."""
        mmf = get_v2_mmf()
        # First security uses otherUniqueId
        sec = mmf.securities[0]
        assert sec.cusip == "03199T002_5.3200"


class TestNMFP2ShareClasses:

    def test_num_share_classes(self):
        mmf = get_v2_mmf()
        assert mmf.num_share_classes == 8

    def test_first_class_id(self):
        mmf = get_v2_mmf()
        assert mmf.share_classes[0].class_id == "C000032709"

    def test_first_class_net_assets(self):
        mmf = get_v2_mmf()
        assert mmf.share_classes[0].net_assets == Decimal("7977041226.87")

    def test_class_weekly_flows(self):
        """N-MFP2 share class flows are weekly (fridayWeek1-5)."""
        mmf = get_v2_mmf()
        sc = mmf.share_classes[0]
        assert len(sc.daily_flows) >= 4
        flow = sc.daily_flows[0]
        assert flow["date"] == "week_1"
        assert flow["gross_subscriptions"] == Decimal("1832786435.08")
        assert flow["gross_redemptions"] == Decimal("1308150107.14")

    def test_class_net_yield_scalar(self):
        """N-MFP2 has a single sevenDayNetYield per class."""
        mmf = get_v2_mmf()
        sc = mmf.share_classes[0]
        assert len(sc.seven_day_net_yields) == 1
        assert sc.seven_day_net_yields[0]["net_yield"] == Decimal("0.0525")


class TestNMFP2DataFrames:

    def test_portfolio_data(self):
        mmf = get_v2_mmf()
        pdf = mmf.portfolio_data()
        assert len(pdf) == 110
        assert "issuer" in pdf.columns

    def test_share_class_data(self):
        mmf = get_v2_mmf()
        scd = mmf.share_class_data()
        assert len(scd) == 8

    def test_collateral_data(self):
        mmf = get_v2_mmf()
        cd = mmf.collateral_data()
        assert len(cd) > 0

    def test_holdings_by_category(self):
        mmf = get_v2_mmf()
        hbc = mmf.holdings_by_category()
        assert len(hbc) > 0


class TestNMFP2Display:

    def test_repr_does_not_error(self):
        mmf = get_v2_mmf()
        r = repr(mmf)
        assert isinstance(r, str)
        assert len(r) > 0

    def test_filing_obj_returns_money_market_fund(self):
        filing = get_v2_filing()
        result = filing.obj()
        assert isinstance(result, MoneyMarketFund)
