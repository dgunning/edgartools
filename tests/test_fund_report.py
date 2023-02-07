from datetime import datetime
from decimal import Decimal
from pathlib import Path

from rich import print

import pyarrow.compute as pc
from edgar.filing import get_fund_filings, Filings
from edgar.fund_report import FundReport, CurrentMetric

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
    #print(filings_jan)
    min_date, max_date = filings_jan.date_range
    assert min_date >= datetime.strptime('2021-01-01', "%Y-%m-%d").date()
    assert max_date <= datetime.strptime('2021-01-31', "%Y-%m-%d").date()