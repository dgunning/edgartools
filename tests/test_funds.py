from edgar.funds import get_fund_by_ticker, Fund, parse_fund_data, get_class_or_series, CompanyInfo
from pathlib import Path
from rich import print
import pandas as pd
pd.options.display.max_columns = None

def test_getfund_by_ticker():
    fund:Fund = get_fund_by_ticker('DXFTX')
    print()
    print(fund)
    assert fund.company_cik == '0001040587'
    assert fund.company_name == 'DIREXION FUNDS'
    assert fund.series == 'S000024976'
    assert fund.name == 'Direxion Currency Trends Strategy Plus Fund'
    assert fund.class_contract == 'Class A'
    assert fund.ticker == 'DXFTX'

    fund = Fund('DXESX') # alias for get_fund
    print(fund)
    assert fund.company_cik == '0001040587'
    assert fund.company_name == 'DIREXION FUNDS'
    assert fund.series == 'S000007038'
    assert fund.name == 'Direxion Monthly Emerging Markets Bear 2X Fund'
    assert fund.class_contract == 'Investor Class'
    assert fund.ticker == 'DXESX'

    company = fund.get_fund_company()
    print(company)

    filings = company.get_filings(form="485BPOS")
    assert filings is not None
    print(filings[0].header.text)



def test_get_fund_by_ticker_not_found():
    fund = get_fund_by_ticker('SASSY')
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

    company_infos = CompanyInfo.from_html(company_info_html)
    company_info = company_infos[0]
    assert company_info.cik == '0001040587'
    assert company_info.name == 'DIREXION FUNDS'
    assert company_info.state == "NY"
    assert company_info.state_of_incorporation == "MA"
    assert company_info.ident_info['Class/Contract'] == 'C000032628 Investor Class'
    print()
    print(str(company_info))
    print(company_info.ident_info)

def test_parse_company_info_for_fund_series():
    company_info_html = Path('data/fundseries.html').read_text()

    company_infos = CompanyInfo.from_html(company_info_html)
    company_info = company_infos[0]
    assert company_info.cik == '0001040587'
    assert company_info.name == 'DIREXION FUNDS'
    assert company_info.state == "NY"
    assert company_info.state_of_incorporation == "MA"

    print()
    print(str(company_info))
    print(company_info.ident_info)
    assert company_info.ident_info['Series'] == 'S000011951 Biotech Bear 2X Fund'


def test_get_fund_class():
    class_contract = get_class_or_series('C000032628')
    assert class_contract.id == 'C000032628'
    assert class_contract.name == 'Investor Class'
    assert class_contract.fund_cik == '0001040587'
    assert class_contract.fund_name == 'DIREXION FUNDS'
    assert not class_contract.ticker
    print()
    print(class_contract)
    assert get_class_or_series("C000032628").name == "Investor Class"
    assert get_class_or_series("C000032627").name == "Service Class"
    assert get_class_or_series("C000032621").id == "C000032621"

    # Find one with a ticker
    class_contract = get_class_or_series("C000053174")
    assert class_contract.ticker == "DXHSX"
    print(class_contract)

def test_get_fund_series():
    series = get_class_or_series('S000011951')
    assert series.id == 'S000011951'
    assert series.name == 'Biotech Bear 2X Fund'
    assert series.fund_cik == '0001040587'
    assert series.fund_name == 'DIREXION FUNDS'
    print()
    print(series)

    assert get_class_or_series("S000053319").name == "Direxion Monthly MSCI EAFE Bear 1.25X Fund"
    assert get_class_or_series("S000011964").name == "Direxion Monthly S&P 500(R) Bear 1.75X Fund"
    assert get_class_or_series("S000011943").id == "S000011943"
    assert get_class_or_series("S000019285").fund_cik == "0001040587"
