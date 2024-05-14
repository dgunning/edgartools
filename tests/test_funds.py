from edgar.funds import (get_fund, Fund, Fund, FundSeries, FundClass, parse_fund_data,
                         get_fund_with_filings,
                         FundCompanyInfo)
from pathlib import Path
from rich import print
import pandas as pd
import pytest
from edgar import find, CompanySearchResults

pd.options.display.max_columns = None


@pytest.mark.parametrize(
    "ticker,expected_name,expected_class_name,expected_class_id",
    [
        ("KINCX", "Kinetics Internet Fund", "Advisor Class C", "C000013712"),
        ("KINAX", "Kinetics Internet Fund", "Advisor Class A", "C000013715"),
        ("DXFTX", "Direxion Currency Trends Strategy Plus Fund", "Class A", "C000074299"),
        ("DXESX", "Direxion Monthly Emerging Markets Bear 2X Fund", "Investor Class", "C000019215"),
        # Add more tuples for each ticker and fund name pair
    ])
def test_get_fund_by_ticker(ticker, expected_name, expected_class_name, expected_class_id):
    fund = get_fund(ticker)
    assert fund.name == expected_name
    assert fund.class_contract_name == expected_class_name
    assert fund.ticker == ticker
    assert fund.class_contract_id == expected_class_id


def test_get_fund_by_class_contract_id():
    fund = get_fund("C000032628")
    assert fund.name == 'Biotech Bear 2X Fund'
    assert fund.class_contract_name == 'Investor Class'
    assert fund.ticker == ''
    assert fund.class_contract_id == 'C000032628'


def test_get_fund_by_series_id():
    fund = get_fund('S000007025')
    assert fund.company_cik == '0001040587'
    assert fund
    assert fund.class_contract_id == 'C000032659'


def test_matching_of_mutual_fund_ticker():
    assert isinstance(find("DXFTX"), Fund)
    assert isinstance(find("DXFTV"), CompanySearchResults)


def test_filings_from_fund_class_are_not_duplicated():
    # When we get a fund we can get the filings
    fund_class: FundClass = get_fund_with_filings("C000245415")
    fund = fund_class.fund
    filings = fund.filings
    assert not filings.to_pandas().duplicated().any()


def test_get_fund_by_ticker_not_found():
    fund = get_fund('SASSY')
    assert fund is None


def test_parse_series_and_classes_contracts_data():
    sgml_data = """
<SERIES-AND-CLASSES-CONTRACTS-DATA>
<EXISTING-SERIES-AND-CLASSES-CONTRACTS>
<SERIES>
<OWNER-CIK>0001040587
<SERIES-ID>S000007025
<SERIES-NAME>Direxion Monthly 7-10 Year Treasury Bull 1.75X Fund
<CLASS-CONTRACT>
<CLASS-CONTRACT-ID>C000019202
<CLASS-CONTRACT-NAME>Investor Class
<CLASS-CONTRACT-TICKER-SYMBOL>DXKLX
</CLASS-CONTRACT>
</SERIES>
<SERIES>
<OWNER-CIK>0001040587
<SERIES-ID>S000007044
<SERIES-NAME>Direxion Monthly Small Cap Bull 1.75X Fund
<CLASS-CONTRACT>
<CLASS-CONTRACT-ID>C000019221
<CLASS-CONTRACT-NAME>Investor Class
<CLASS-CONTRACT-TICKER-SYMBOL>DXRLX
</CLASS-CONTRACT>
</SERIES>
<SERIES>
<OWNER-CIK>0001040587
<SERIES-ID>S000007045
<SERIES-NAME>Direxion Monthly Small Cap Bear 1.75X Fund
<CLASS-CONTRACT>
<CLASS-CONTRACT-ID>C000019222
<CLASS-CONTRACT-NAME>Investor Class
<CLASS-CONTRACT-TICKER-SYMBOL>DXRSX
</CLASS-CONTRACT>
</SERIES>
<SERIES>
<OWNER-CIK>0001040587
<SERIES-ID>S000007050
<SERIES-NAME>Direxion Monthly 7-10 Year Treasury Bear 1.75X Fund
<CLASS-CONTRACT>
<CLASS-CONTRACT-ID>C000019229
<CLASS-CONTRACT-NAME>Investor Class
<CLASS-CONTRACT-TICKER-SYMBOL>DXKSX
</CLASS-CONTRACT>
</SERIES>
<SERIES>
<OWNER-CIK>0001040587
<SERIES-ID>S000011950
<SERIES-NAME>Direxion Monthly S&P 500(R) Bull 1.75X Fund
<CLASS-CONTRACT>
<CLASS-CONTRACT-ID>C000032626
<CLASS-CONTRACT-NAME>Investor Class
<CLASS-CONTRACT-TICKER-SYMBOL>DXSLX
</CLASS-CONTRACT>
</SERIES>
<SERIES>
<OWNER-CIK>0001040587
<SERIES-ID>S000011960
<SERIES-NAME>Direxion Monthly NASDAQ-100(R) Bull 1.75X Fund
<CLASS-CONTRACT>
<CLASS-CONTRACT-ID>C000032646
<CLASS-CONTRACT-NAME>Investor Class
<CLASS-CONTRACT-TICKER-SYMBOL>DXQLX
</CLASS-CONTRACT>
</SERIES>
<SERIES>
<OWNER-CIK>0001040587
<SERIES-ID>S000011964
<SERIES-NAME>Direxion Monthly S&P 500(R) Bear 1.75X Fund
<CLASS-CONTRACT>
<CLASS-CONTRACT-ID>C000032654
<CLASS-CONTRACT-NAME>Investor Class
<CLASS-CONTRACT-TICKER-SYMBOL>DXSSX
</CLASS-CONTRACT>
</SERIES>
<SERIES>
<OWNER-CIK>0001040587
<SERIES-ID>S000046967
<SERIES-NAME>HILTON TACTICAL INCOME FUND
<CLASS-CONTRACT>
<CLASS-CONTRACT-ID>C000146784
<CLASS-CONTRACT-NAME>Investor Class
<CLASS-CONTRACT-TICKER-SYMBOL>HCYAX
</CLASS-CONTRACT>
<CLASS-CONTRACT>
<CLASS-CONTRACT-ID>C000146785
<CLASS-CONTRACT-NAME>Institutional Class
<CLASS-CONTRACT-TICKER-SYMBOL>HCYIX
</CLASS-CONTRACT>
</SERIES>
<SERIES>
<OWNER-CIK>0001040587
<SERIES-ID>S000052787
<SERIES-NAME>DIREXION MONTHLY HIGH YIELD BULL 1.2X FUND
<CLASS-CONTRACT>
<CLASS-CONTRACT-ID>C000165828
<CLASS-CONTRACT-NAME>Investor Class
<CLASS-CONTRACT-TICKER-SYMBOL>DXHYX
</CLASS-CONTRACT>
</SERIES>
<SERIES>
<OWNER-CIK>0001040587
<SERIES-ID>S000053315
<SERIES-NAME>Direxion Monthly NASDAQ-100(R) Bull 1.25X Fund
<CLASS-CONTRACT>
<CLASS-CONTRACT-ID>C000167765
<CLASS-CONTRACT-NAME>Investor Class
<CLASS-CONTRACT-TICKER-SYMBOL>DXNLX
</CLASS-CONTRACT>
</SERIES>
</EXISTING-SERIES-AND-CLASSES-CONTRACTS>
</SERIES-AND-CLASSES-CONTRACTS-DATA>
 """
    series_contracts = parse_fund_data(sgml_data)
    print()
    print(series_contracts)


def test_parse_company_info_for_fund_class():
    company_info_html = Path('data/fundclass.html').read_text()

    company_info = FundCompanyInfo.from_html(company_info_html)

    assert company_info.cik == '0001040587'
    assert company_info.name == 'DIREXION FUNDS'
    assert company_info.state == "NY"
    assert company_info.state_of_incorporation == "MA"
    assert company_info.ident_info['Class/Contract'] == 'C000032628 Investor Class'
    print()
    print(str(company_info))
    print(company_info.ident_info)

    # Test the company filings
    company_filings = company_info.filings
    print(company_filings.to_pandas())


def test_parse_company_info_for_fund_series():
    company_info_html = Path('data/fundseries.html').read_text()
    company_info = FundCompanyInfo.from_html(company_info_html)
    assert company_info.cik == '0001040587'
    assert company_info.name == 'DIREXION FUNDS'
    assert company_info.state == "NY"
    assert company_info.state_of_incorporation == "MA"

    print()
    print(str(company_info))
    print(company_info.ident_info)
    assert company_info.ident_info['Series'] == 'S000011951 Biotech Bear 2X Fund'


def test_get_fund_class():
    class_contract = get_fund_with_filings('C000032628')
    assert class_contract.id == 'C000032628'
    assert class_contract.name == 'Investor Class'
    assert class_contract.fund_cik == '0001040587'
    assert class_contract.fund_name == 'DIREXION FUNDS'
    assert not class_contract.ticker
    print()
    print(class_contract)
    assert get_fund_with_filings("C000032628").name == "Investor Class"
    assert get_fund_with_filings("C000032627").name == "Service Class"
    assert get_fund_with_filings("C000032621").id == "C000032621"

    # Find one with a ticker
    class_contract = get_fund_with_filings("C000053174")
    assert class_contract.ticker == "DXHSX"
    print(class_contract)


def test_get_fund_series():
    series = get_fund_with_filings('S000011951')
    assert series.id == 'S000011951'
    assert series.name == 'Biotech Bear 2X Fund'
    assert series.fund_cik == '0001040587'
    assert series.fund_name == 'DIREXION FUNDS'
    print()
    print(series)

    assert get_fund_with_filings("S000053319").name == "Direxion Monthly MSCI EAFE Bear 1.25X Fund"
    assert get_fund_with_filings("S000011964").name == "Direxion Monthly S&P 500(R) Bear 1.75X Fund"
    assert get_fund_with_filings("S000011943").id == "S000011943"
    assert get_fund_with_filings("S000019285").fund_cik == "0001040587"


def test_get_class_or_series_not_found():
    assert get_fund_with_filings('C100011111') is None
    assert get_fund_with_filings('NONO') is None


def test_fund_function_gets_by_ticker_class_or_series():
    assert isinstance(get_fund("DXHSX"), Fund)
    assert isinstance(get_fund("C000011111"), Fund)
    assert isinstance(get_fund("S000019285"), Fund)


def test_get_fund_by_mutual_fund_ticker():
    ticker = "FCNTX"
    fund = get_fund(ticker)
    print()
    print(fund)
    assert fund.ticker == "FCNTX"
    assert fund.series == "S000006037"
    assert fund.name == "Fidelity Contrafund"

    # Get the fund filings
    latest_nport = fund.filings.filter(form="NPORT-P").latest(1)

    # Get the fund company. This nport should be the same as the fund company's nport
    fund_company = fund.get_fund_company()
    company_nport = fund_company.get_filings(accession_number=latest_nport.accession_no).latest()
    assert company_nport.accession_no == latest_nport.accession_no
