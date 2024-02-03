from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pyarrow.compute as pc
from rich import print

from edgar import get_fund_portfolio_filings, Filings, Filing
from edgar.fundreports import FundReport, CurrentMetric
from edgar.funds import get_fund_information, Fund

dupree_fund_xml = Path('data/NPORT.Dupree.xml').read_text()


def test_fund_from_xml():
    print()
    fund_report = FundReport(**FundReport.parse_fund_xml(dupree_fund_xml))

    # General Information
    general_info = fund_report.general_info
    assert general_info.name == "Dupree Mutual Funds"
    assert general_info.cik == '0000311101'
    assert general_info.reg_lei == '549300S8YVGTJ1NMTW57'
    assert general_info.file_number == '811-02918'
    assert general_info.series_lei == '5493006TF05454RBY690'
    assert general_info.series_name == 'Kentucky Tax-Free Short-to-Medium Series'
    assert general_info.series_id == 'S000012000'
    assert general_info.fiscal_year_end == '2023-06-30'
    assert general_info.rep_period_date == '2022-12-31'
    assert general_info.is_final_filing is False
    assert general_info.city == 'Lexington'

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
    assert fund_report.investments[0].balance == Decimal('755000')
    assert fund_report.investments[0].value_usd == Decimal('794207.15')
    assert fund_report.investments[0].currency_code == "USD"
    assert fund_report.investments[0].issuer_category == "MUN"
    assert fund_report.investments[0].pct_value == Decimal('1.9206978745')
    assert fund_report.investments[0].payoff_profile == "Long"

    # Debt security
    assert fund_report.investments[0].debt_security.maturity_date == datetime.strptime("2028-08-01", "%Y-%m-%d")
    assert fund_report.investments[0].debt_security.coupon_kind == "Fixed"
    assert fund_report.investments[0].debt_security.annualized_rate == Decimal("5.00")
    assert fund_report.investments[0].debt_security.is_default is False
    assert fund_report.investments[0].debt_security.are_instrument_payents_in_arrears is False
    assert fund_report.investments[0].debt_security.is_paid_kind is False

    assert fund_report.investments[0].isin == "US49151FGH73"
    assert fund_report.investments[0].ticker == "KYSFAC"

    assert fund_report.investments[1].isin == "US49151FHF09"
    assert fund_report.investments[1].ticker == "KYSFAC"

    print(fund_report)


def test_fund_investment_data_as_pandas():
    print()
    fund_report = FundReport(**FundReport.parse_fund_xml(dupree_fund_xml))
    investment_data = fund_report.investment_data()
    assert all(column in investment_data for column in ["name", "title", "balance", "investment_country"])


def test_parse_sample_1():
    fund_report = FundReport(**FundReport.parse_fund_xml(Path('data/nport/samples/N-PORT Sample 1.xml').read_text()))
    print()
    print(fund_report)


def test_parse_sample_2():
    fund_report = FundReport(**FundReport.parse_fund_xml(Path('data/nport/samples/N-PORT Sample 2.xml').read_text()))
    assert fund_report.name == "ST Testing Co Number 15 - token"

    # Investment of Securities
    assert fund_report.investments[0].asset_category == "EC"

    print()
    print(fund_report)


def test_parse_sample_3():
    fund_report = FundReport(**FundReport.parse_fund_xml(Path('data/nport/samples/N-PORT Sample 3.xml').read_text()))
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
    fund_report = FundReport(**FundReport.parse_fund_xml(Path('data/nport/samples/N-PORT Sample 4.xml').read_text()))
    assert fund_report.name == "Phase V Han Oh Test 6 - Series Name #1"


def test_parse_sample_5():
    fund_report = FundReport(**FundReport.parse_fund_xml(Path('data/nport/samples/N-PORT Sample 5.xml').read_text()))
    assert fund_report.name == "Phase V Han Oh Test 6 - Series Name #1"


def test_get_fund_filings():
    fund_filings: Filings = get_fund_portfolio_filings(year=2021, quarter=1)
    print()
    print(fund_filings)
    assert pc.unique(fund_filings.data['form']).to_pylist() == ['NPORT-P', 'NPORT-P/A']
    filings_jan: Filings = fund_filings.filter(date="2021-01-01:2021-01-31")
    # print(filings_jan)
    min_date, max_date = filings_jan.date_range
    assert min_date >= datetime.strptime('2021-01-01', "%Y-%m-%d").date()
    assert max_date <= datetime.strptime('2021-01-31', "%Y-%m-%d").date()


def test_fund_no_investment_sec_tag():
    fund_report = FundReport(**FundReport.parse_fund_xml(Path('data/NPORT.AdvancedSeries.xml').read_text()))
    assert fund_report.fund_info.return_info.monthly_total_returns
    assert fund_report.general_info.is_final_filing is True


jacob_funds = Filing(form='NPORT-P', filing_date='2023-10-13', company='Jacob Funds Inc.', cik=1090372,
                     accession_no='0001145549-23-062230')


def test_parse_fund_header_sgml():
    fund_data = get_fund_information(jacob_funds.header)
    print()
    print(fund_data)


def test_fund_from_filing():
    fund_report = FundReport.from_filing(jacob_funds)
    assert fund_report
    assert fund_report.series_and_contracts is not None

    # Test .obj()
    fund_report = jacob_funds.obj()
    assert fund_report


def test_fund_report_has_correct_isin():
    filing = Filing(company='SPDR S&P MIDCAP 400 ETF TRUST', cik=936958, form='NPORT-P', filing_date='2023-08-24',
                    accession_no='0001752724-23-188317')
    fund_report = filing.obj()
    investment_data = fund_report.investment_data()
    assert not investment_data['isin'].duplicated().any()


def test_display_of_fund_report():
    filing = Filing(form='NPORT-P',
                    filing_date='2023-10-26',
                    company='PRUDENTIAL SECTOR FUNDS, INC.',
                    cik=352665,
                    accession_no='0001752724-23-238209')
    fund_report = filing.obj()

    # What is the fund?
    fund:Fund = fund_report.fund
    assert fund.name == 'PGIM Jennison Health Sciences Fund'
    assert fund.ticker == "PHSZX"
    assert fund.class_contract_id == "C000012124"
    assert fund.series == 'S000004380'
    #assert fund_report.name == 'PRUDENTIAL SECTOR FUNDS, INC.'

def test_print_fund_report():
    filing = Filing(form='NPORT-P', filing_date='2024-01-29', company='SATURNA INVESTMENT TRUST', cik=811860,
           accession_no='0001145549-24-004741')
    fund_report:FundReport = filing.obj()
    assert 'SATURNA' in repr(fund_report)
    assert 'SATURNA' in str(fund_report)





