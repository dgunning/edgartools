"""
Unit tests for N-MFP Money Market Fund data object.

These are fast, offline tests that exercise parsing logic, helpers,
properties, DataFrame methods, and display without network calls.
"""
from decimal import Decimal

import pandas as pd
import pytest
from rich.panel import Panel

from edgar.funds.nmfp3 import (
    MONEY_MARKET_FORMS,
    NMFP2_FORMS,
    NMFP3_FORMS,
    CollateralIssuer,
    CreditRating,
    GeneralInfo,
    MoneyMarketFund,
    PortfolioSecurity,
    RepurchaseAgreement,
    SeriesLevelInfo,
    ShareClassInfo,
    _flag,
    _opt_int,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_general_info(**overrides):
    defaults = dict(
        report_date="2026-01-31",
        registrant_name="Test Registrant",
        cik="0000000001",
        registrant_lei="LEI123",
        series_name="Test Money Market Fund",
        series_lei="SLEI456",
        series_id="S000099999",
        total_share_classes=2,
        final_filing=False,
    )
    defaults.update(overrides)
    return GeneralInfo(**defaults)


def _make_series_info(**overrides):
    defaults = dict(
        fund_category="Government",
        avg_portfolio_maturity=45,
        avg_life_maturity=90,
        cash=Decimal("100000.00"),
        total_value_portfolio_securities=Decimal("5000000.00"),
        amortized_cost_portfolio_securities=Decimal("4999000.00"),
        total_value_other_assets=Decimal("10000.00"),
        total_value_liabilities=Decimal("5000.00"),
        net_assets=Decimal("5005000.00"),
        shares_outstanding=Decimal("5005000"),
        seek_stable_price=True,
        stable_price_per_share=Decimal("1.0000"),
        seven_day_gross_yields=[
            {"date": "2026-01-02", "gross_yield": Decimal("0.04")},
            {"date": "2026-01-03", "gross_yield": Decimal("0.041")},
        ],
        daily_nav_per_share=[
            {"date": "2026-01-02", "nav_per_share": Decimal("1.0001")},
        ],
        liquidity_details=[
            {"date": "2026-01-02", "daily_liquid_value": Decimal("3000000"),
             "weekly_liquid_value": Decimal("4000000"),
             "pct_daily_liquid": Decimal("0.60"), "pct_weekly_liquid": Decimal("0.80")},
        ],
    )
    defaults.update(overrides)
    return SeriesLevelInfo(**defaults)


def _make_share_class(**overrides):
    defaults = dict(
        class_name="Class A",
        class_id="C000012345",
        min_initial_investment=Decimal("1000"),
        net_assets=Decimal("2500000.00"),
        shares_outstanding=Decimal("2500000"),
        daily_nav=[{"date": "2026-01-02", "nav_per_share": Decimal("1.0001")}],
        daily_flows=[{"date": "2026-01-02", "gross_subscriptions": Decimal("50000"),
                      "gross_redemptions": Decimal("30000")}],
        seven_day_net_yields=[{"date": "2026-01-02", "net_yield": Decimal("0.038")}],
    )
    defaults.update(overrides)
    return ShareClassInfo(**defaults)


def _make_security(**overrides):
    defaults = dict(
        issuer_name="US Treasury",
        title="US Treasury Bill",
        cusip="912796XX1",
        isin="US912796XX10",
        lei="LEI_TREAS",
        cik="0000000002",
        investment_category="U.S. Treasury Debt",
        maturity_date_wam="2026-03-15",
        maturity_date_wal="2026-06-15",
        final_maturity_date="2026-06-15",
        yield_rate=Decimal("0.042"),
        market_value=Decimal("1000000.00"),
        amortized_cost=Decimal("999500.00"),
        pct_of_nav=Decimal("0.20"),
        daily_liquid=True,
        weekly_liquid=True,
        illiquid=False,
        demand_feature=False,
        guarantee=False,
        enhancement=False,
        ratings=[CreditRating(agency="Moody's", rating="Aaa")],
        repo_agreement=None,
    )
    defaults.update(overrides)
    return PortfolioSecurity(**defaults)


def _make_mmf(**overrides):
    """Build a MoneyMarketFund with sensible defaults."""
    gi = overrides.pop("general_info", _make_general_info())
    si = overrides.pop("series_info", _make_series_info())
    scs = overrides.pop("share_classes", [_make_share_class(), _make_share_class(class_name="Class B", class_id="C000012346")])
    secs = overrides.pop("securities", [
        _make_security(market_value=Decimal("1000000.00"), pct_of_nav=Decimal("0.20")),
        _make_security(issuer_name="FHLB", cusip="3133XXXX", market_value=Decimal("500000.00"),
                       pct_of_nav=Decimal("0.10"), investment_category="Government Agency Debt"),
        _make_security(issuer_name="Repo Counterparty", cusip="REPO001",
                       market_value=Decimal("2000000.00"), pct_of_nav=Decimal("0.40"),
                       investment_category="U.S. Treasury Repurchase Agreement",
                       repo_agreement=RepurchaseAgreement(
                           open_flag=True, cleared_flag=False, tri_party_flag=True,
                           collateral=[
                               CollateralIssuer(issuer_name="US T-Bond", cusip="COLL001",
                                                maturity_date="2030-01-01", coupon=Decimal("2.5"),
                                                principal_amount=Decimal("2100000"),
                                                collateral_value=Decimal("2050000"),
                                                collateral_category="U.S. Treasury Debt"),
                           ])),
    ])
    return MoneyMarketFund(general_info=gi, series_info=si,
                           share_classes=scs, securities=secs)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestConstants:

    def test_nmfp3_forms_content(self):
        assert NMFP3_FORMS == ["N-MFP3", "N-MFP3/A"]

    def test_nmfp2_forms_content(self):
        assert NMFP2_FORMS == ["N-MFP2", "N-MFP2/A"]

    def test_money_market_forms_is_union(self):
        assert MONEY_MARKET_FORMS == NMFP2_FORMS + NMFP3_FORMS


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestHelpers:

    def test_opt_int_valid(self):
        from lxml import etree
        root = etree.fromstring("<r><val>42</val></r>")
        assert _opt_int(root, "val") == 42

    def test_opt_int_missing_tag(self):
        from lxml import etree
        root = etree.fromstring("<r></r>")
        assert _opt_int(root, "val") is None

    def test_opt_int_invalid_text(self):
        from lxml import etree
        root = etree.fromstring("<r><val>abc</val></r>")
        assert _opt_int(root, "val") is None

    def test_opt_int_empty_text(self):
        from lxml import etree
        root = etree.fromstring("<r><val></val></r>")
        assert _opt_int(root, "val") is None

    def test_flag_yes(self):
        from lxml import etree
        root = etree.fromstring("<r><f>Y</f></r>")
        assert _flag(root, "f") is True

    def test_flag_no(self):
        from lxml import etree
        root = etree.fromstring("<r><f>N</f></r>")
        assert _flag(root, "f") is False

    def test_flag_missing(self):
        from lxml import etree
        root = etree.fromstring("<r></r>")
        assert _flag(root, "f") is False


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestPydanticModels:

    def test_general_info_defaults(self):
        gi = GeneralInfo(
            report_date="2026-01-31", registrant_name="R", cik="001",
            series_name="S", series_id="S000000001", total_share_classes=1,
        )
        assert gi.final_filing is False
        assert gi.registrant_lei is None
        assert gi.series_lei is None

    def test_series_level_info_defaults(self):
        si = SeriesLevelInfo()
        assert si.fund_category is None
        assert si.seek_stable_price is False
        assert si.seven_day_gross_yields == []

    def test_share_class_info_defaults(self):
        sc = ShareClassInfo(class_name="A", class_id="C001")
        assert sc.min_initial_investment is None
        assert sc.daily_nav == []
        assert sc.daily_flows == []

    def test_credit_rating_fields(self):
        cr = CreditRating(agency="S&P", rating="AAA")
        assert cr.agency == "S&P"
        assert cr.rating == "AAA"

    def test_collateral_issuer_defaults(self):
        ci = CollateralIssuer()
        assert ci.issuer_name is None
        assert ci.coupon is None

    def test_repurchase_agreement_defaults(self):
        ra = RepurchaseAgreement()
        assert ra.open_flag is False
        assert ra.collateral == []

    def test_portfolio_security_defaults(self):
        ps = PortfolioSecurity()
        assert ps.daily_liquid is False
        assert ps.ratings == []
        assert ps.repo_agreement is None


# ---------------------------------------------------------------------------
# MoneyMarketFund properties
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestMoneyMarketFundProperties:

    def test_name(self):
        mmf = _make_mmf()
        assert mmf.name == "Test Money Market Fund"

    def test_report_date(self):
        mmf = _make_mmf()
        assert mmf.report_date == "2026-01-31"

    def test_fund_category(self):
        mmf = _make_mmf()
        assert mmf.fund_category == "Government"

    def test_net_assets(self):
        mmf = _make_mmf()
        assert mmf.net_assets == Decimal("5005000.00")

    def test_num_securities(self):
        mmf = _make_mmf()
        assert mmf.num_securities == 3

    def test_num_share_classes(self):
        mmf = _make_mmf()
        assert mmf.num_share_classes == 2

    def test_average_maturity_wam(self):
        mmf = _make_mmf()
        assert mmf.average_maturity_wam == 45

    def test_average_maturity_wal(self):
        mmf = _make_mmf()
        assert mmf.average_maturity_wal == 90

    def test_none_maturity_when_missing(self):
        si = _make_series_info(avg_portfolio_maturity=None, avg_life_maturity=None)
        mmf = _make_mmf(series_info=si)
        assert mmf.average_maturity_wam is None
        assert mmf.average_maturity_wal is None


# ---------------------------------------------------------------------------
# DataFrame methods
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestMoneyMarketFundDataFrames:

    def test_portfolio_data_columns(self):
        mmf = _make_mmf()
        pdf = mmf.portfolio_data()
        expected_cols = {"issuer", "title", "cusip", "isin", "category",
                         "maturity_wam", "maturity_wal", "yield", "market_value",
                         "amortized_cost", "pct_of_nav", "daily_liquid",
                         "weekly_liquid", "has_repo"}
        assert expected_cols == set(pdf.columns)

    def test_portfolio_data_sorted_descending(self):
        mmf = _make_mmf()
        pdf = mmf.portfolio_data()
        values = pdf["market_value"].dropna().tolist()
        assert values == sorted(values, reverse=True)

    def test_portfolio_data_has_repo_flag(self):
        mmf = _make_mmf()
        pdf = mmf.portfolio_data()
        repo_rows = pdf[pdf["has_repo"] == True]
        assert len(repo_rows) == 1

    def test_share_class_data_columns(self):
        mmf = _make_mmf()
        scd = mmf.share_class_data()
        assert set(scd.columns) == {"class_name", "class_id", "min_investment",
                                     "net_assets", "shares_outstanding"}

    def test_share_class_data_length(self):
        mmf = _make_mmf()
        assert len(mmf.share_class_data()) == 2

    def test_yield_history(self):
        mmf = _make_mmf()
        yh = mmf.yield_history()
        assert len(yh) == 2
        assert "date" in yh.columns
        assert "gross_yield" in yh.columns

    def test_nav_history(self):
        mmf = _make_mmf()
        nh = mmf.nav_history()
        assert len(nh) == 1
        assert nh.iloc[0]["nav_per_share"] == Decimal("1.0001")

    def test_liquidity_history(self):
        mmf = _make_mmf()
        lh = mmf.liquidity_history()
        assert len(lh) == 1
        assert "pct_daily_liquid" in lh.columns

    def test_collateral_data(self):
        mmf = _make_mmf()
        cd = mmf.collateral_data()
        assert len(cd) == 1
        assert cd.iloc[0]["collateral_issuer"] == "US T-Bond"
        assert cd.iloc[0]["collateral_value"] == Decimal("2050000")

    def test_collateral_data_empty_when_no_repos(self):
        secs = [_make_security()]  # no repo
        mmf = _make_mmf(securities=secs)
        cd = mmf.collateral_data()
        assert len(cd) == 0

    def test_holdings_by_category(self):
        mmf = _make_mmf()
        hbc = mmf.holdings_by_category()
        assert "category" in hbc.columns
        assert "count" in hbc.columns
        assert "total_market_value" in hbc.columns
        assert len(hbc) == 3  # three distinct categories

    def test_holdings_by_category_empty_securities(self):
        mmf = _make_mmf(securities=[])
        hbc = mmf.holdings_by_category()
        assert len(hbc) == 0

    def test_portfolio_data_empty_securities(self):
        mmf = _make_mmf(securities=[])
        pdf = mmf.portfolio_data()
        assert len(pdf) == 0


# ---------------------------------------------------------------------------
# Display / Rich
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestMoneyMarketFundDisplay:

    def test_str(self):
        mmf = _make_mmf()
        s = str(mmf)
        assert "MoneyMarketFund" in s
        assert "Test Money Market Fund" in s
        assert "3 securities" in s

    def test_repr_returns_string(self):
        mmf = _make_mmf()
        r = repr(mmf)
        assert isinstance(r, str)
        assert len(r) > 0

    def test_rich_returns_panel(self):
        mmf = _make_mmf()
        panel = mmf.__rich__()
        assert isinstance(panel, Panel)

    def test_summary_table_stable_price_shown(self):
        mmf = _make_mmf()
        table = mmf._summary_table
        # The table should render without error
        assert table is not None

    def test_summary_table_no_stable_price(self):
        si = _make_series_info(seek_stable_price=False, stable_price_per_share=None)
        mmf = _make_mmf(series_info=si)
        table = mmf._summary_table
        assert table is not None

    def test_summary_table_no_net_assets(self):
        si = _make_series_info(net_assets=None)
        mmf = _make_mmf(series_info=si)
        table = mmf._summary_table
        assert table is not None

    def test_summary_table_no_fund_category(self):
        si = _make_series_info(fund_category=None)
        mmf = _make_mmf(series_info=si)
        table = mmf._summary_table
        assert table is not None

    def test_share_classes_table(self):
        mmf = _make_mmf()
        table = mmf._share_classes_table
        assert table is not None

    def test_share_classes_table_empty(self):
        mmf = _make_mmf(share_classes=[])
        table = mmf._share_classes_table
        assert table is not None

    def test_top_holdings_table(self):
        mmf = _make_mmf()
        table = mmf._top_holdings_table
        assert table is not None

    def test_top_holdings_table_empty(self):
        mmf = _make_mmf(securities=[])
        table = mmf._top_holdings_table
        assert table is not None


# ---------------------------------------------------------------------------
# XML Parsing (N-MFP3 format)
# ---------------------------------------------------------------------------

_MINIMAL_V3_XML = """\
<edgarSubmission>
  <formData>
    <generalInfo>
      <reportDate>2026-01-31</reportDate>
      <registrantFullName>Test Registrant Inc</registrantFullName>
      <cik>0000000099</cik>
      <registrantLEIId>LEI12345</registrantLEIId>
      <nameOfSeries>Test Series</nameOfSeries>
      <leiOfSeries>SLEI67890</leiOfSeries>
      <seriesId>S000099999</seriesId>
      <totalShareClassesInSeries>1</totalShareClassesInSeries>
      <finalFilingFlag>N</finalFilingFlag>
    </generalInfo>
    <seriesLevelInfo>
      <moneyMarketFundCategory>Government</moneyMarketFundCategory>
      <averagePortfolioMaturity>30</averagePortfolioMaturity>
      <averageLifeMaturity>60</averageLifeMaturity>
      <cash>50000.00</cash>
      <netAssetOfSeries>1000000.00</netAssetOfSeries>
      <numberOfSharesOutstanding>1000000</numberOfSharesOutstanding>
      <seekStablePricePerShare>Y</seekStablePricePerShare>
      <stablePricePerShare>1.0000</stablePricePerShare>
      <sevenDayGrossYield>
        <sevenDayGrossYieldDate>2026-01-02</sevenDayGrossYieldDate>
        <sevenDayGrossYieldValue>0.0400</sevenDayGrossYieldValue>
      </sevenDayGrossYield>
      <dailyNetAssetValuePerShareSeries>
        <dailyNetAssetValuePerShareDateSeries>2026-01-02</dailyNetAssetValuePerShareDateSeries>
        <dailyNetAssetValuePerShareSeries>1.0001</dailyNetAssetValuePerShareSeries>
      </dailyNetAssetValuePerShareSeries>
      <liquidAssetsDetails>
        <totalLiquidAssetsNearPercentDate>2026-01-02</totalLiquidAssetsNearPercentDate>
        <totalValueDailyLiquidAssets>600000</totalValueDailyLiquidAssets>
        <totalValueWeeklyLiquidAssets>800000</totalValueWeeklyLiquidAssets>
        <percentageDailyLiquidAssets>0.60</percentageDailyLiquidAssets>
        <percentageWeeklyLiquidAssets>0.80</percentageWeeklyLiquidAssets>
      </liquidAssetsDetails>
    </seriesLevelInfo>
    <classLevelInfo>
      <classFullName>Class A</classFullName>
      <classesId>C000012345</classesId>
      <minInitialInvestment>1000</minInitialInvestment>
      <netAssetsOfClass>500000.00</netAssetsOfClass>
      <numberOfSharesOutstanding>500000</numberOfSharesOutstanding>
      <dailyNetAssetValuePerShareClass>
        <dailyNetAssetValuePerShareDateClass>2026-01-02</dailyNetAssetValuePerShareDateClass>
        <dailyNetAssetValuePerShareClass>1.0001</dailyNetAssetValuePerShareClass>
      </dailyNetAssetValuePerShareClass>
      <dialyShareholderFlowReported>
        <dailyShareHolderFlowDate>2026-01-02</dailyShareHolderFlowDate>
        <dailyGrossSubscriptions>10000</dailyGrossSubscriptions>
        <dailyGrossRedemptions>5000</dailyGrossRedemptions>
      </dialyShareholderFlowReported>
      <sevenDayNetYield>
        <sevenDayNetYieldDate>2026-01-02</sevenDayNetYieldDate>
        <sevenDayNetYieldValue>0.038</sevenDayNetYieldValue>
      </sevenDayNetYield>
    </classLevelInfo>
    <scheduleOfPortfolioSecuritiesInfo>
      <nameOfIssuer>US Treasury</nameOfIssuer>
      <titleOfIssuer>T-Bill</titleOfIssuer>
      <CUSIPMember>912796001</CUSIPMember>
      <ISINId>US9127960010</ISINId>
      <investmentCategory>U.S. Treasury Debt</investmentCategory>
      <investmentMaturityDateWAM>2026-03-15</investmentMaturityDateWAM>
      <investmentMaturityDateWAL>2026-06-15</investmentMaturityDateWAL>
      <yieldOfTheSecurityAsOfReportingDate>0.042</yieldOfTheSecurityAsOfReportingDate>
      <includingValueOfAnySponsorSupport>500000.00</includingValueOfAnySponsorSupport>
      <excludingValueOfAnySponsorSupport>499500.00</excludingValueOfAnySponsorSupport>
      <percentageOfMoneyMarketFundNetAssets>0.50</percentageOfMoneyMarketFundNetAssets>
      <dailyLiquidAssetSecurityFlag>Y</dailyLiquidAssetSecurityFlag>
      <weeklyLiquidAssetSecurityFlag>Y</weeklyLiquidAssetSecurityFlag>
      <illiquidSecurityFlag>N</illiquidSecurityFlag>
      <securityDemandFeatureFlag>N</securityDemandFeatureFlag>
      <securityGuaranteeFlag>N</securityGuaranteeFlag>
      <securityEnhancementsFlag>N</securityEnhancementsFlag>
      <assigningNRSRORating>
        <nameOfNRSRO>Moody's</nameOfNRSRO>
        <rating>Aaa</rating>
      </assigningNRSRORating>
    </scheduleOfPortfolioSecuritiesInfo>
    <scheduleOfPortfolioSecuritiesInfo>
      <nameOfIssuer>Repo Bank</nameOfIssuer>
      <titleOfIssuer>Repo Agreement</titleOfIssuer>
      <CUSIPMember>REPO001</CUSIPMember>
      <investmentCategory>U.S. Treasury Repurchase Agreement</investmentCategory>
      <yieldOfTheSecurityAsOfReportingDate>0.035</yieldOfTheSecurityAsOfReportingDate>
      <includingValueOfAnySponsorSupport>300000.00</includingValueOfAnySponsorSupport>
      <percentageOfMoneyMarketFundNetAssets>0.30</percentageOfMoneyMarketFundNetAssets>
      <dailyLiquidAssetSecurityFlag>Y</dailyLiquidAssetSecurityFlag>
      <weeklyLiquidAssetSecurityFlag>Y</weeklyLiquidAssetSecurityFlag>
      <illiquidSecurityFlag>N</illiquidSecurityFlag>
      <securityDemandFeatureFlag>N</securityDemandFeatureFlag>
      <securityGuaranteeFlag>N</securityGuaranteeFlag>
      <securityEnhancementsFlag>N</securityEnhancementsFlag>
      <repurchaseAgreement>
        <repurchaseAgreementOpenFlag>N</repurchaseAgreementOpenFlag>
        <repurchaseAgreementClearedFlag>Y</repurchaseAgreementClearedFlag>
        <repurchaseAgreementTripartyFlag>Y</repurchaseAgreementTripartyFlag>
        <collateralIssuers>
          <nameOfCollateralIssuer>US Treasury Bond</nameOfCollateralIssuer>
          <LEIID>COLLATERAL_LEI</LEIID>
          <CUSIPMember>COLLCUSIP</CUSIPMember>
          <maturityDate><date>2035-06-15</date></maturityDate>
          <coupon>2.500</coupon>
          <principalAmountToTheNearestCent>310000.00</principalAmountToTheNearestCent>
          <valueOfCollateralToTheNearestCent>305000.00</valueOfCollateralToTheNearestCent>
          <ctgryInvestmentsRprsntsCollateral>U.S. Treasury Debt</ctgryInvestmentsRprsntsCollateral>
        </collateralIssuers>
      </repurchaseAgreement>
    </scheduleOfPortfolioSecuritiesInfo>
  </formData>
</edgarSubmission>
"""


@pytest.mark.fast
class TestParseV3XML:

    def test_parse_general_info(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V3_XML)
        assert mmf.general_info.report_date == "2026-01-31"
        assert mmf.general_info.registrant_name == "Test Registrant Inc"
        assert mmf.general_info.cik == "0000000099"
        assert mmf.general_info.registrant_lei == "LEI12345"
        assert mmf.general_info.series_name == "Test Series"
        assert mmf.general_info.series_id == "S000099999"
        assert mmf.general_info.total_share_classes == 1
        assert mmf.general_info.final_filing is False

    def test_parse_series_info(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V3_XML)
        assert mmf.series_info.fund_category == "Government"
        assert mmf.series_info.avg_portfolio_maturity == 30
        assert mmf.series_info.avg_life_maturity == 60
        assert mmf.series_info.cash == Decimal("50000.00")
        assert mmf.series_info.net_assets == Decimal("1000000.00")
        assert mmf.series_info.seek_stable_price is True
        assert mmf.series_info.stable_price_per_share == Decimal("1.0000")

    def test_parse_series_time_series(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V3_XML)
        assert len(mmf.series_info.seven_day_gross_yields) == 1
        assert mmf.series_info.seven_day_gross_yields[0]["gross_yield"] == Decimal("0.0400")
        assert len(mmf.series_info.daily_nav_per_share) == 1
        assert len(mmf.series_info.liquidity_details) == 1

    def test_parse_share_classes(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V3_XML)
        assert len(mmf.share_classes) == 1
        sc = mmf.share_classes[0]
        assert sc.class_name == "Class A"
        assert sc.class_id == "C000012345"
        assert sc.min_initial_investment == Decimal("1000")
        assert sc.net_assets == Decimal("500000.00")

    def test_parse_class_time_series(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V3_XML)
        sc = mmf.share_classes[0]
        assert len(sc.daily_nav) == 1
        assert len(sc.daily_flows) == 1
        assert sc.daily_flows[0]["gross_subscriptions"] == Decimal("10000")
        assert sc.daily_flows[0]["gross_redemptions"] == Decimal("5000")
        assert len(sc.seven_day_net_yields) == 1
        assert sc.seven_day_net_yields[0]["net_yield"] == Decimal("0.038")

    def test_parse_securities(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V3_XML)
        assert len(mmf.securities) == 2

    def test_parse_security_details(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V3_XML)
        sec = mmf.securities[0]
        assert sec.issuer_name == "US Treasury"
        assert sec.cusip == "912796001"
        assert sec.isin == "US9127960010"
        assert sec.yield_rate == Decimal("0.042")
        assert sec.market_value == Decimal("500000.00")
        assert sec.daily_liquid is True
        assert sec.weekly_liquid is True
        assert sec.illiquid is False

    def test_parse_security_ratings(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V3_XML)
        sec = mmf.securities[0]
        assert len(sec.ratings) == 1
        assert sec.ratings[0].agency == "Moody's"
        assert sec.ratings[0].rating == "Aaa"

    def test_parse_repo_agreement(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V3_XML)
        sec = mmf.securities[1]
        assert sec.repo_agreement is not None
        assert sec.repo_agreement.cleared_flag is True
        assert sec.repo_agreement.tri_party_flag is True
        assert sec.repo_agreement.open_flag is False
        assert len(sec.repo_agreement.collateral) == 1

    def test_parse_collateral(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V3_XML)
        coll = mmf.securities[1].repo_agreement.collateral[0]
        assert coll.issuer_name == "US Treasury Bond"
        assert coll.lei == "COLLATERAL_LEI"
        assert coll.cusip == "COLLCUSIP"
        assert coll.maturity_date == "2035-06-15"
        assert coll.coupon == Decimal("2.500")
        assert coll.principal_amount == Decimal("310000.00")
        assert coll.collateral_value == Decimal("305000.00")

    def test_parse_nmfp3_xml_backward_compat(self):
        """parse_nmfp3_xml is the old public method, should still work."""
        mmf = MoneyMarketFund.parse_nmfp3_xml(_MINIMAL_V3_XML)
        assert mmf.name == "Test Series"

    def test_parse_xml_bytes(self):
        """_parse_xml should accept bytes as well as str."""
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V3_XML.encode("utf-8"))
        assert mmf.name == "Test Series"


# ---------------------------------------------------------------------------
# XML Parsing (N-MFP2 format)
# ---------------------------------------------------------------------------

_MINIMAL_V2_XML = """\
<edgarSubmission xmlns="http://www.sec.gov/edgar/nmfp2">
  <formData>
    <generalInfo>
      <reportDate>2023-11-30</reportDate>
      <cik>0000000088</cik>
      <seriesId>S000088888</seriesId>
      <totalShareClassesInSeries>2</totalShareClassesInSeries>
      <finalFilingFlag>N</finalFilingFlag>
    </generalInfo>
    <seriesLevelInfo>
      <moneyMarketFundCategory>Prime</moneyMarketFundCategory>
      <averagePortfolioMaturity>25</averagePortfolioMaturity>
      <averageLifeMaturity>50</averageLifeMaturity>
      <cash>10000.00</cash>
      <netAssetOfSeries>200000.00</netAssetOfSeries>
      <sevenDayGrossYield>0.0500</sevenDayGrossYield>
      <stablePricePerShare>1.0000</stablePricePerShare>
      <netAssetValue>
        <fridayWeek1>1.0000</fridayWeek1>
        <fridayWeek2>1.0001</fridayWeek2>
      </netAssetValue>
      <totalValueDailyLiquidAssets>
        <fridayDay1>120000</fridayDay1>
      </totalValueDailyLiquidAssets>
      <totalValueWeeklyLiquidAssets>
        <fridayWeek1>160000</fridayWeek1>
      </totalValueWeeklyLiquidAssets>
      <percentageDailyLiquidAssets>
        <fridayDay1>0.60</fridayDay1>
      </percentageDailyLiquidAssets>
      <percentageWeeklyLiquidAssets>
        <fridayWeek1>0.80</fridayWeek1>
      </percentageWeeklyLiquidAssets>
    </seriesLevelInfo>
    <classLevelInfo>
      <classFullName>Class I</classFullName>
      <classesId>C000077777</classesId>
      <netAssetsOfClass>100000.00</netAssetsOfClass>
      <numberOfSharesOutstanding>100000</numberOfSharesOutstanding>
      <sevenDayNetYield>0.048</sevenDayNetYield>
      <netAssetPerShare>
        <fridayWeek1>1.0000</fridayWeek1>
      </netAssetPerShare>
      <fridayWeek1>
        <weeklyGrossSubscriptions>20000</weeklyGrossSubscriptions>
        <weeklyGrossRedemptions>15000</weeklyGrossRedemptions>
      </fridayWeek1>
    </classLevelInfo>
    <scheduleOfPortfolioSecuritiesInfo>
      <nameOfIssuer>Bank ABC</nameOfIssuer>
      <titleOfIssuer>CD</titleOfIssuer>
      <otherUniqueId>OTHER123</otherUniqueId>
      <investmentCategory>Certificate of Deposit</investmentCategory>
      <yieldOfTheSecurityAsOfReportingDate>0.05</yieldOfTheSecurityAsOfReportingDate>
      <includingValueOfAnySponsorSupport>50000.00</includingValueOfAnySponsorSupport>
      <percentageOfMoneyMarketFundNetAssets>0.25</percentageOfMoneyMarketFundNetAssets>
      <dailyLiquidAssetSecurityFlag>N</dailyLiquidAssetSecurityFlag>
      <weeklyLiquidAssetSecurityFlag>Y</weeklyLiquidAssetSecurityFlag>
      <illiquidSecurityFlag>N</illiquidSecurityFlag>
      <securityDemandFeatureFlag>N</securityDemandFeatureFlag>
      <securityGuaranteeFlag>N</securityGuaranteeFlag>
      <securityEnhancementsFlag>N</securityEnhancementsFlag>
    </scheduleOfPortfolioSecuritiesInfo>
  </formData>
</edgarSubmission>
"""


@pytest.mark.fast
class TestParseV2XML:

    def test_v2_detected(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V2_XML)
        # V2 lacks registrantFullName, so name should be empty
        assert mmf.general_info.registrant_name == ""
        assert mmf.name == ""

    def test_v2_general_info(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V2_XML)
        assert mmf.general_info.report_date == "2023-11-30"
        assert mmf.general_info.cik == "0000000088"
        assert mmf.general_info.series_id == "S000088888"
        assert mmf.general_info.total_share_classes == 2

    def test_v2_series_info(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V2_XML)
        assert mmf.series_info.fund_category == "Prime"
        assert mmf.series_info.avg_portfolio_maturity == 25
        assert mmf.net_assets == Decimal("200000.00")

    def test_v2_yield_single_scalar(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V2_XML)
        yh = mmf.yield_history()
        assert len(yh) == 1
        assert yh.iloc[0]["gross_yield"] == Decimal("0.0500")

    def test_v2_nav_weekly(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V2_XML)
        nh = mmf.nav_history()
        assert len(nh) == 2
        assert nh.iloc[0]["date"] == "week_1"
        assert nh.iloc[0]["nav_per_share"] == Decimal("1.0000")

    def test_v2_liquidity_friday_snapshots(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V2_XML)
        lh = mmf.liquidity_history()
        assert len(lh) >= 1
        assert lh.iloc[0]["date"] == "friday_1"
        assert lh.iloc[0]["pct_daily_liquid"] == Decimal("0.60")

    def test_v2_share_class(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V2_XML)
        assert len(mmf.share_classes) == 1
        sc = mmf.share_classes[0]
        assert sc.class_name == "Class I"
        assert sc.class_id == "C000077777"
        assert sc.net_assets == Decimal("100000.00")

    def test_v2_class_net_yield_scalar(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V2_XML)
        sc = mmf.share_classes[0]
        assert len(sc.seven_day_net_yields) == 1
        assert sc.seven_day_net_yields[0]["net_yield"] == Decimal("0.048")

    def test_v2_class_weekly_flows(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V2_XML)
        sc = mmf.share_classes[0]
        assert len(sc.daily_flows) == 1
        assert sc.daily_flows[0]["gross_subscriptions"] == Decimal("20000")

    def test_v2_class_nav(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V2_XML)
        sc = mmf.share_classes[0]
        assert len(sc.daily_nav) == 1
        assert sc.daily_nav[0]["nav_per_share"] == Decimal("1.0000")

    def test_v2_cusip_fallback_to_other_unique_id(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V2_XML)
        sec = mmf.securities[0]
        assert sec.cusip == "OTHER123"

    def test_v2_security_fields(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V2_XML)
        sec = mmf.securities[0]
        assert sec.issuer_name == "Bank ABC"
        assert sec.investment_category == "Certificate of Deposit"
        assert sec.yield_rate == Decimal("0.05")
        assert sec.market_value == Decimal("50000.00")
        assert sec.daily_liquid is False
        assert sec.weekly_liquid is True

    def test_v2_stable_price_detection(self):
        mmf = MoneyMarketFund._parse_xml(_MINIMAL_V2_XML)
        # V2: presence of stablePricePerShare means seek_stable = True
        assert mmf.series_info.seek_stable_price is True
        assert mmf.series_info.stable_price_per_share == Decimal("1.0000")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestParseEdgeCases:

    def test_malformed_xml_recovery(self):
        """Malformed XML should be parsed using recovery mode."""
        bad_xml = "<edgarSubmission><formData><generalInfo><reportDate>2026-01-01</reportDate><cik>001</cik><seriesId>S001</seriesId><totalShareClassesInSeries>0</totalShareClassesInSeries></generalInfo><seriesLevelInfo></seriesLevelInfo></formData>"  # no closing tag
        mmf = MoneyMarketFund._parse_xml(bad_xml)
        assert mmf.general_info.report_date == "2026-01-01"

    def test_xml_with_namespaces_stripped(self):
        """Namespaces should be stripped before parsing."""
        ns_xml = '<edgarSubmission xmlns:nmfp="http://www.sec.gov/edgar/nmfp3"><formData><generalInfo><reportDate>2026-02-01</reportDate><registrantFullName>NS Test</registrantFullName><cik>002</cik><seriesId>S002</seriesId><nameOfSeries>NS Fund</nameOfSeries><totalShareClassesInSeries>0</totalShareClassesInSeries></generalInfo><seriesLevelInfo></seriesLevelInfo></formData></edgarSubmission>'
        mmf = MoneyMarketFund._parse_xml(ns_xml)
        assert mmf.name == "NS Fund"

    def test_empty_securities_list(self):
        """No securities yields empty portfolio."""
        xml = '<edgarSubmission><formData><generalInfo><reportDate>2026-01-01</reportDate><registrantFullName>X</registrantFullName><cik>003</cik><seriesId>S003</seriesId><nameOfSeries>Empty</nameOfSeries><totalShareClassesInSeries>0</totalShareClassesInSeries></generalInfo><seriesLevelInfo></seriesLevelInfo></formData></edgarSubmission>'
        mmf = MoneyMarketFund._parse_xml(xml)
        assert mmf.num_securities == 0
        assert len(mmf.portfolio_data()) == 0

    def test_no_share_classes(self):
        xml = '<edgarSubmission><formData><generalInfo><reportDate>2026-01-01</reportDate><registrantFullName>X</registrantFullName><cik>004</cik><seriesId>S004</seriesId><nameOfSeries>NoClass</nameOfSeries><totalShareClassesInSeries>0</totalShareClassesInSeries></generalInfo><seriesLevelInfo></seriesLevelInfo></formData></edgarSubmission>'
        mmf = MoneyMarketFund._parse_xml(xml)
        assert mmf.num_share_classes == 0
        assert len(mmf.share_class_data()) == 0

    def test_wrapped_in_outer_element(self):
        """XML with edgarSubmission nested inside another root element."""
        xml = '<root><edgarSubmission><formData><generalInfo><reportDate>2026-01-01</reportDate><registrantFullName>Wrapped</registrantFullName><cik>005</cik><seriesId>S005</seriesId><nameOfSeries>Wrapped Fund</nameOfSeries><totalShareClassesInSeries>0</totalShareClassesInSeries></generalInfo><seriesLevelInfo></seriesLevelInfo></formData></edgarSubmission></root>'
        mmf = MoneyMarketFund._parse_xml(xml)
        assert mmf.name == "Wrapped Fund"


# ---------------------------------------------------------------------------
# from_filing
# ---------------------------------------------------------------------------

@pytest.mark.fast
class TestFromFiling:

    def test_from_filing_none_xml(self):
        """from_filing returns None when filing.xml() is empty."""
        from unittest.mock import MagicMock
        filing = MagicMock()
        filing.xml.return_value = None
        result = MoneyMarketFund.from_filing(filing)
        assert result is None

    def test_from_filing_empty_xml(self):
        from unittest.mock import MagicMock
        filing = MagicMock()
        filing.xml.return_value = ""
        result = MoneyMarketFund.from_filing(filing)
        assert result is None

    def test_from_filing_valid_xml(self):
        from unittest.mock import MagicMock
        filing = MagicMock()
        filing.xml.return_value = _MINIMAL_V3_XML
        result = MoneyMarketFund.from_filing(filing)
        assert result is not None
        assert result.name == "Test Series"
