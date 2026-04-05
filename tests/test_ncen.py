"""
Verification tests for N-CEN Fund Census data object.

Ground truth filings:
  - Mutual fund: AB CAP FUND, INC. (accession 0001410368-26-010921)
  - ETF: AB Active ETFs, Inc. (accession 0001410368-26-010918)
"""
from decimal import Decimal

import pandas as pd
import pytest

from edgar import get_by_accession_number
from edgar.funds.ncen import (
    NCEN_FORMS,
    BrokerDealer,
    ETFInfo,
    FundCensus,
    LineOfCredit,
    RegistrantInfo,
    ServiceProvider,
    SignatureInfo,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mutual_fund_census():
    """AB CAP FUND, INC. — mutual fund, 3 series, no ETFs."""
    filing = get_by_accession_number("0001410368-26-010921")
    return filing.obj()


@pytest.fixture(scope="module")
def etf_census():
    """AB Active ETFs, Inc. — ETF company, 22 series."""
    filing = get_by_accession_number("0001410368-26-010918")
    return filing.obj()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:

    def test_ncen_forms(self):
        assert NCEN_FORMS == ["N-CEN", "N-CEN/A"]


# ---------------------------------------------------------------------------
# Registrant — mutual fund
# ---------------------------------------------------------------------------

class TestMutualFundRegistrant:

    def test_is_fund_census(self, mutual_fund_census):
        assert isinstance(mutual_fund_census, FundCensus)

    def test_registrant_name(self, mutual_fund_census):
        assert mutual_fund_census.registrant.name == "AB CAP FUND, INC."

    def test_registrant_cik(self, mutual_fund_census):
        assert mutual_fund_census.registrant.cik == "0000081443"

    def test_registrant_lei(self, mutual_fund_census):
        assert mutual_fund_census.registrant.lei == "549300I24E20QB4B6Y20"

    def test_report_date(self, mutual_fund_census):
        assert mutual_fund_census.report_date == "2025-11-30"

    def test_classification_type(self, mutual_fund_census):
        assert mutual_fund_census.classification_type == "N-1A"

    def test_total_series(self, mutual_fund_census):
        assert mutual_fund_census.total_series == 11

    def test_name_property(self, mutual_fund_census):
        assert mutual_fund_census.name == "AB CAP FUND, INC."

    def test_cik_property(self, mutual_fund_census):
        assert mutual_fund_census.cik == "0000081443"

    def test_lei_property(self, mutual_fund_census):
        assert mutual_fund_census.lei == "549300I24E20QB4B6Y20"

    def test_is_not_etf_company(self, mutual_fund_census):
        assert mutual_fund_census.is_etf_company is False

    def test_is_not_lt_12_months(self, mutual_fund_census):
        assert mutual_fund_census.is_period_lt_12_months is False

    def test_file_number(self, mutual_fund_census):
        assert mutual_fund_census.registrant.file_number == "811-01716"


# ---------------------------------------------------------------------------
# Directors
# ---------------------------------------------------------------------------

class TestDirectors:

    def test_director_count(self, mutual_fund_census):
        assert len(mutual_fund_census.registrant.directors) == 8

    def test_first_director_name(self, mutual_fund_census):
        assert mutual_fund_census.registrant.directors[0].name == "Alexander Chaloff"

    def test_first_director_crd(self, mutual_fund_census):
        # Alexander Chaloff has a real CRD number
        assert mutual_fund_census.registrant.directors[0].crd_number == "005019996"

    def test_non_interested_director_crd_is_none(self, mutual_fund_census):
        # Carol C. McMullen has "N/A" in XML, which should be cleaned to None
        assert mutual_fund_census.registrant.directors[1].crd_number is None

    def test_first_director_is_interested(self, mutual_fund_census):
        assert mutual_fund_census.registrant.directors[0].is_interested_person is True

    def test_second_director_not_interested(self, mutual_fund_census):
        assert mutual_fund_census.registrant.directors[1].is_interested_person is False

    def test_director_str(self, mutual_fund_census):
        d = mutual_fund_census.registrant.directors[0]
        assert "Alexander Chaloff" in str(d)
        assert "interested" in str(d)


# ---------------------------------------------------------------------------
# CCO & Accountant
# ---------------------------------------------------------------------------

class TestCCOAndAccountant:

    def test_cco_name(self, mutual_fund_census):
        assert mutual_fund_census.registrant.cco_name == "Jennifer Friedland"

    def test_accountant_name(self, mutual_fund_census):
        assert mutual_fund_census.registrant.accountant.name == "Ernst & Young LLP"

    def test_accountant_pcaob(self, mutual_fund_census):
        assert mutual_fund_census.registrant.accountant.pcaob_number == "42"

    def test_accountant_lei(self, mutual_fund_census):
        assert mutual_fund_census.registrant.accountant.lei == "254900Y3CIB1KF938C31"

    def test_underwriter_name(self, mutual_fund_census):
        assert mutual_fund_census.registrant.underwriter_name == "AllianceBernstein Investments, Inc."


# ---------------------------------------------------------------------------
# Series — mutual fund
# ---------------------------------------------------------------------------

class TestMutualFundSeries:

    def test_num_series(self, mutual_fund_census):
        assert mutual_fund_census.num_series == 3

    def test_first_series_name(self, mutual_fund_census):
        assert mutual_fund_census.series[0].name == "AB All China Equity Portfolio"

    def test_first_series_id(self, mutual_fund_census):
        assert mutual_fund_census.series[0].series_id == "S000062452"

    def test_first_series_lei(self, mutual_fund_census):
        assert mutual_fund_census.series[0].lei == "549300M0QRVBUIG3U327"

    def test_first_series_avg_net_assets(self, mutual_fund_census):
        # 52887264.89846153
        avg = mutual_fund_census.series[0].avg_net_assets
        assert avg is not None
        assert abs(avg - Decimal("52887264.89846153")) < Decimal("0.01")

    def test_first_series_aggregate_commission(self, mutual_fund_census):
        comm = mutual_fund_census.series[0].aggregate_commission
        assert comm is not None
        assert abs(comm - Decimal("77222.38")) < Decimal("0.01")

    def test_third_series_name(self, mutual_fund_census):
        assert mutual_fund_census.series[2].name == "AB Small Cap Value Portfolio"

    def test_third_series_avg_net_assets(self, mutual_fund_census):
        avg = mutual_fund_census.series[2].avg_net_assets
        assert avg is not None
        assert abs(avg - Decimal("564700404.99461538")) < Decimal("0.01")


# ---------------------------------------------------------------------------
# Service providers
# ---------------------------------------------------------------------------

class TestServiceProviders:

    def test_first_series_advisers(self, mutual_fund_census):
        advisers = mutual_fund_census.series[0].advisers
        assert len(advisers) == 1
        assert advisers[0].name == "AllianceBernstein L.P."
        assert advisers[0].role == "adviser"

    def test_first_series_custodians(self, mutual_fund_census):
        custodians = mutual_fund_census.series[0].custodians
        assert len(custodians) == 11
        assert custodians[0].name == "Brown Brothers Harriman & Co."

    def test_first_series_transfer_agents(self, mutual_fund_census):
        agents = mutual_fund_census.series[0].transfer_agents
        assert len(agents) == 1
        assert "AllianceBernstein" in agents[0].name

    def test_first_series_pricing_services(self, mutual_fund_census):
        ps = mutual_fund_census.series[0].pricing_services
        assert len(ps) == 7
        assert ps[0].name == "Bloomberg L.P."

    def test_first_series_admins(self, mutual_fund_census):
        admins = mutual_fund_census.series[0].admins
        assert len(admins) == 1
        assert admins[0].name == "AllianceBernstein L.P."
        assert admins[0].is_affiliated is True


# ---------------------------------------------------------------------------
# Brokers and principal transactions
# ---------------------------------------------------------------------------

class TestBrokersAndTransactions:

    def test_first_series_broker_dealers(self, mutual_fund_census):
        bds = mutual_fund_census.series[0].broker_dealers
        assert len(bds) == 2
        assert bds[0].name == "Sanford C. Bernstein & Co., LLC"

    def test_first_series_brokers(self, mutual_fund_census):
        brokers = mutual_fund_census.series[0].brokers
        assert len(brokers) == 10
        assert brokers[0].name == "J.P. Morgan Securities LLC"
        assert brokers[0].commission is not None
        assert brokers[0].commission > 0

    def test_first_series_principal_transactions(self, mutual_fund_census):
        pts = mutual_fund_census.series[0].principal_transactions
        assert len(pts) == 1
        assert pts[0].name == "Brown Brothers Harriman Investments, LLC"
        assert pts[0].total_purchase_sale is not None
        assert abs(pts[0].total_purchase_sale - Decimal("39223357.80")) < Decimal("0.01")


# ---------------------------------------------------------------------------
# Securities lending
# ---------------------------------------------------------------------------

class TestSecuritiesLending:

    def test_securities_lending_flag(self, mutual_fund_census):
        assert mutual_fund_census.series[0].is_securities_lending is True

    def test_securities_lending_agents(self, mutual_fund_census):
        sl = mutual_fund_census.series[0].securities_lending
        assert len(sl) == 1
        assert sl[0].agent_name == "Mitsubishi UFJ Trust and Banking Corporation"

    def test_securities_lending_indemnified(self, mutual_fund_census):
        sl = mutual_fund_census.series[0].securities_lending[0]
        assert sl.is_indemnified is True


# ---------------------------------------------------------------------------
# Line of credit
# ---------------------------------------------------------------------------

class TestLineOfCredit:

    def test_has_line_of_credit(self, mutual_fund_census):
        loc = mutual_fund_census.series[0].line_of_credit
        assert loc is not None
        assert loc.has_line_of_credit is True

    def test_line_of_credit_size(self, mutual_fund_census):
        loc = mutual_fund_census.series[0].line_of_credit
        assert loc.size is not None
        assert loc.size == Decimal("325000000.00000000")

    def test_line_of_credit_committed(self, mutual_fund_census):
        loc = mutual_fund_census.series[0].line_of_credit
        assert loc.is_committed == "Committed"

    def test_line_of_credit_institutions(self, mutual_fund_census):
        loc = mutual_fund_census.series[0].line_of_credit
        assert len(loc.institution_names) == 14
        assert "JPMORGAN CHASE BANK, N.A." in loc.institution_names


# ---------------------------------------------------------------------------
# Liquidity providers
# ---------------------------------------------------------------------------

class TestLiquidityProviders:

    def test_liquidity_providers(self, mutual_fund_census):
        lps = mutual_fund_census.series[0].liquidity_providers
        assert len(lps) == 1
        assert lps[0].name == "MSCI Inc."

    def test_liquidity_asset_classes(self, mutual_fund_census):
        lps = mutual_fund_census.series[0].liquidity_providers
        assert len(lps[0].asset_classes) >= 1
        assert "Equity-common" in lps[0].asset_classes


# ---------------------------------------------------------------------------
# Signature
# ---------------------------------------------------------------------------

class TestSignature:

    def test_signature_info(self, mutual_fund_census):
        sig = mutual_fund_census.signature_info
        assert sig is not None
        assert sig.registrant_name == "AB CAP FUND, INC."
        assert sig.signer == "Stephen Woetzel"
        assert sig.title == "Controller"
        assert sig.signed_date == "2026-02-10"


# ---------------------------------------------------------------------------
# ETF filing
# ---------------------------------------------------------------------------

class TestETFCensus:

    def test_is_etf_company(self, etf_census):
        assert etf_census.is_etf_company is True

    def test_etf_registrant_name(self, etf_census):
        assert etf_census.registrant.name == "AB Active ETFs, Inc."

    def test_etf_registrant_cik(self, etf_census):
        assert etf_census.registrant.cik == "0001496608"

    def test_etf_num_series(self, etf_census):
        assert etf_census.num_series == 22

    def test_etf_total_series(self, etf_census):
        assert etf_census.total_series == 23

    def test_first_etf_info(self, etf_census):
        etf = etf_census.series[0].etf_info
        assert etf is not None
        assert etf.fund_name == "AB California Intermediate Municipal ETF"
        assert etf.series_id == "S000093944"

    def test_first_etf_ticker(self, etf_census):
        etf = etf_census.series[0].etf_info
        assert etf.ticker == "CAM"

    def test_first_etf_exchange(self, etf_census):
        etf = etf_census.series[0].etf_info
        assert etf.exchange == "ARCX"

    def test_first_etf_creation_unit_size(self, etf_census):
        etf = etf_census.series[0].etf_info
        assert etf.creation_unit_size == Decimal("50000.00000000")

    def test_first_etf_authorized_participants(self, etf_census):
        etf = etf_census.series[0].etf_info
        assert len(etf.authorized_participants) == 22

    def test_first_ap_name(self, etf_census):
        ap = etf_census.series[0].etf_info.authorized_participants[0]
        assert ap.name == "Credit Suisse Securities (Europe) Limited"

    def test_first_ap_lei(self, etf_census):
        ap = etf_census.series[0].etf_info.authorized_participants[0]
        assert ap.lei == "DL6FFRRLF74S01HE2M14"

    def test_all_series_have_etf_info(self, etf_census):
        for s in etf_census.series:
            assert s.etf_info is not None, f"Series {s.name} missing ETF info"


# ---------------------------------------------------------------------------
# DataFrame methods
# ---------------------------------------------------------------------------

class TestDataFrames:

    def test_series_data_shape(self, mutual_fund_census):
        df = mutual_fund_census.series_data()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert "name" in df.columns
        assert "avg_net_assets" in df.columns

    def test_series_data_has_etf_column(self, mutual_fund_census):
        df = mutual_fund_census.series_data()
        assert "has_etf" in df.columns
        assert not df["has_etf"].any()

    def test_service_providers_shape(self, mutual_fund_census):
        df = mutual_fund_census.service_providers()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert "role" in df.columns

    def test_service_providers_has_expected_roles(self, mutual_fund_census):
        df = mutual_fund_census.service_providers()
        roles = set(df["role"].unique())
        assert "adviser" in roles
        assert "custodian" in roles
        assert "transfer agent" in roles

    def test_broker_data_columns(self, mutual_fund_census):
        df = mutual_fund_census.broker_data()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert "broker_name" in df.columns
        assert "commission" in df.columns

    def test_director_data(self, mutual_fund_census):
        df = mutual_fund_census.director_data()
        assert len(df) == 8
        assert df.iloc[0]["name"] == "Alexander Chaloff"
        assert df.iloc[0]["interested_person"] == True

    def test_etf_data_mutual_fund(self, mutual_fund_census):
        df = mutual_fund_census.etf_data()
        assert len(df) == 0

    def test_etf_data_etf_filing(self, etf_census):
        df = etf_census.etf_data()
        assert len(df) == 22
        assert "ticker" in df.columns
        assert "creation_unit_size" in df.columns
        assert "num_authorized_participants" in df.columns


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

class TestDisplay:

    def test_repr_mutual_fund(self, mutual_fund_census):
        r = repr(mutual_fund_census)
        assert "AB CAP FUND" in r
        assert "2025-11-30" in r

    def test_repr_etf(self, etf_census):
        r = repr(etf_census)
        assert "AB Active ETFs" in r

    def test_rich_panel(self, mutual_fund_census):
        from rich.panel import Panel
        panel = mutual_fund_census.__rich__()
        assert isinstance(panel, Panel)

    def test_str(self, mutual_fund_census):
        s = str(mutual_fund_census)
        assert "FundCensus" in s
        assert "3 series" in s


# ---------------------------------------------------------------------------
# obj() integration
# ---------------------------------------------------------------------------

class TestObjIntegration:

    def test_obj_returns_fund_census(self):
        filing = get_by_accession_number("0001410368-26-010921")
        result = filing.obj()
        assert isinstance(result, FundCensus)

    def test_get_obj_info(self):
        from edgar import get_obj_info
        has_obj, class_name, desc = get_obj_info("N-CEN")
        assert has_obj is True
        assert class_name == "FundCensus"
        assert "census" in desc


# ---------------------------------------------------------------------------
# Model __str__ methods
# ---------------------------------------------------------------------------

class TestModelStrMethods:

    def test_service_provider_str(self):
        sp = ServiceProvider(name="Test Provider", role="adviser")
        assert "Test Provider" in str(sp)
        assert "adviser" in str(sp)

    def test_broker_dealer_str(self):
        bd = BrokerDealer(name="Test Broker")
        assert str(bd) == "Test Broker"

    def test_line_of_credit_str_no_loc(self):
        loc = LineOfCredit(has_line_of_credit=False)
        assert str(loc) == "No"

    def test_line_of_credit_str_with_loc(self):
        loc = LineOfCredit(has_line_of_credit=True, institution_names=["Bank A", "Bank B"])
        assert "2 institutions" in str(loc)

    def test_registrant_str(self):
        reg = RegistrantInfo(name="Test Fund", cik="0000000001")
        assert "Test Fund" in str(reg)

    def test_etf_info_str(self):
        etf = ETFInfo(series_id="S000001", fund_name="Test ETF", ticker="TEST")
        assert "TEST" in str(etf)

    def test_signature_str(self):
        sig = SignatureInfo(signer="John Doe", title="CEO", signed_date="2025-01-01")
        assert "John Doe" in str(sig)
