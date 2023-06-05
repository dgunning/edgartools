from datetime import datetime
from decimal import Decimal
from pathlib import Path
import pytest

from rich import print

import pyarrow.compute as pc
from edgar import get_fund_filings, Filings, Filing
from edgar.fundreports import FundReport, CurrentMetric, ThirteenF

fund_xml = Path('data/NPORT.Dupree.xml').read_text()


def test_fund_from_xml():
    print()
    fund_report = FundReport.from_xml(fund_xml)

    # Current Metrics
    current_metric: CurrentMetric = fund_report.fund_info.current_metrics['USD']
    assert current_metric.intrstRtRiskdv01.period1Yr == Decimal('2715.650459453238')
    assert current_metric.intrstRtRiskdv100.period3Mon == Decimal('37075.658747329608')

    # Credit spread
    assert fund_report.fund_info.credit_spread_risk_investment_grade.period30Yr == Decimal("0.000000000000")
    assert fund_report.fund_info.credit_spread_risk_investment_grade.period3Mon == Decimal("361.393588571009")

    assert fund_report.fund_info.credit_spread_risk_non_investment_grade.period1Yr == Decimal("35.916503383984")
    assert fund_report.fund_info.credit_spread_risk_non_investment_grade.period3Mon == Decimal("4.434136220240")

    # Return info
    assert fund_report.fund_info.return_info.monthly_total_returns[0].class_id == "C000032728"
    assert fund_report.fund_info.return_info.monthly_total_returns[0].return1 == Decimal("-.05")
    assert fund_report.fund_info.return_info.monthly_total_returns[0].return2 == Decimal("2.15")
    assert fund_report.fund_info.return_info.monthly_total_returns[0].return3 == Decimal(".15")
    assert fund_report.fund_info.return_info.other_mon1.net_realized_gain == Decimal("0.00")
    assert fund_report.fund_info.return_info.other_mon1.net_unrealized_appreciation == Decimal("-101266.88")

    assert fund_report.fund_info.return_info.other_mon3.net_realized_gain == Decimal("-3613.53")
    assert fund_report.fund_info.return_info.other_mon3.net_unrealized_appreciation == Decimal("36684.13")

    # Monthly flow
    assert fund_report.fund_info.monthly_flow1.sales == Decimal("141189.21")
    assert fund_report.fund_info.monthly_flow2.redemption == Decimal("1069086.08")
    assert fund_report.fund_info.monthly_flow3.reinvestment == Decimal("31270.28")

    # Investments
    assert fund_report.investments[0].asset_category == "DBT"
    assert fund_report.investments[0].issuer_category == "MUN"

    print(fund_report)


def test_fund_investment_data_as_pandas():
    print()
    fund_report = FundReport.from_xml(fund_xml)
    investment_data = fund_report.investment_data()
    assert all(column in investment_data for column in ["name", "title", "balance", "investment_country"])


def test_parse_sample_1():
    fund_report = FundReport.from_xml(Path('data/nport/samples/N-PORT Sample 1.xml').read_text())
    print()
    print(fund_report)


def test_parse_sample_2():
    fund_report = FundReport.from_xml(Path('data/nport/samples/N-PORT Sample 2.xml').read_text())
    print()
    print(fund_report)


def test_parse_sample_3():
    fund_report = FundReport.from_xml(Path('data/nport/samples/N-PORT Sample 3.xml').read_text())
    print()
    print(fund_report)

    assert fund_report.investments[0].investment_country == "AF"
    assert fund_report.investments[0].name == "token"
    assert fund_report.investments[0].cusip == "AHJNP*#A1"
    assert fund_report.investments[0].isin == "USAHJNP*@#11"
    assert fund_report.investments[0].balance == Decimal("0")
    assert fund_report.investments[0].units == "NS"
    assert fund_report.investments[0].desc_other_units == "token"
    assert fund_report.investments[0].currency_code == "USD"
    assert fund_report.investments[0].value_usd == Decimal("0.0")
    assert fund_report.investments[0].pct_value == Decimal("0.0")
    assert fund_report.investments[0].payoff_profile == "Long"
    assert fund_report.investments[0].asset_category == "OTHER"
    assert fund_report.investments[0].issuer_category == "OTHER"
    assert fund_report.investments[0].fair_value_level == "1"

    assert fund_report.investments[0].debt_security.maturity_date == datetime.strptime("2700-01-01", "%Y-%m-%d")
    assert fund_report.investments[0].debt_security.coupon_kind == "Fixed"
    assert fund_report.investments[0].debt_security.annualized_rate == Decimal("-5.55")
    assert fund_report.investments[0].debt_security.is_default is True
    assert fund_report.investments[0].debt_security.are_instrument_payents_in_arrears is True
    assert fund_report.investments[0].debt_security.is_paid_kind is True
    assert fund_report.investments[0].debt_security.is_mandatory_convertible is True
    assert fund_report.investments[0].debt_security.is_continuing_convertible is True


def test_parse_sample_4():
    fund_report = FundReport.from_xml(Path('data/nport/samples/N-PORT Sample 4.xml').read_text())
    print()
    print(fund_report)


def test_parse_sample_5():
    fund_report = FundReport.from_xml(Path('data/nport/samples/N-PORT Sample 5.xml').read_text())
    print()
    print(fund_report)


def test_get_fund_filings():
    fund_filings: Filings = get_fund_filings(year=2021, quarter=1)
    print()
    print(fund_filings)
    assert pc.unique(fund_filings.data['form']).to_pylist() == ['NPORT-P', 'NPORT-P/A']
    filings_jan: Filings = fund_filings.filter(date="2021-01-01:2021-01-31")
    # print(filings_jan)
    min_date, max_date = filings_jan.date_range
    assert min_date >= datetime.strptime('2021-01-01', "%Y-%m-%d").date()
    assert max_date <= datetime.strptime('2021-01-31', "%Y-%m-%d").date()


def test_fund_no_investment_sec_tag():
    fund_report = FundReport.from_xml(Path('data/NPORT.AdvancedSeries.xml').read_text())
    assert fund_report.fund_info.return_info.monthly_total_returns


def test_parse_infotable():
    infotable = ThirteenF.parse_infotable_xml(Path("data/13F-HR.infotable.xml").read_text())
    assert len(infotable) == 255


def test_thirteenf_from_filing():
    filing = Filing(form='13F-HR', filing_date='2023-03-23', company='METLIFE INC', cik=1099219, accession_no='0001140361-23-013281')
    thirteenf = ThirteenF(filing)
    assert thirteenf
    assert thirteenf.filing
    assert thirteenf.has_infotable()
    assert len(thirteenf.infotable) == 6

    #assert thirteenf.infotable.iloc[0].name_of_issuer == "METLIFE INC"

    print()
    print(thirteenf)
    assert thirteenf.total_holdings == 6
    assert thirteenf.total_value == Decimal('11019796')

    assert thirteenf.primary_form_information.signature.name == 'Steven Goulart'

    # Call data object
    assert isinstance(filing.obj(), ThirteenF)

    # 13F-NT
    filing = Filing(form='13F-NT', filing_date='2023-03-17', company='Jasopt Investments Bahamas Ltd', cik=1968770,
    accession_no='0000950123-23-002952')
    thirteenf = ThirteenF(filing)
    assert not thirteenf.has_infotable()
    assert not thirteenf.infotable_xml
    assert not thirteenf.infotable_html
    assert not thirteenf.infotable

    print(thirteenf)


    # Should throw an AssertionError if you try to parse a 10-K as a 13F
    filing = Filing(form='10-K', filing_date='2023-03-23', company='ADMA BIOLOGICS, INC.', cik=1368514,
                    accession_no='0001140361-23-013467')
    with pytest.raises(AssertionError):
        ThirteenF(filing)

def test_parse_thirteenf_primary_xml():
    res = ThirteenF.parse_primary_document_xml(Path("data/metlife.13F-HR.primarydoc.xml").read_text())
    print(res)

