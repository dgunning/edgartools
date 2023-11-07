import re
from dataclasses import dataclass

import pandas as pd
from bs4 import BeautifulSoup

from edgar._companies import Company
from edgar._filings import SECHeader
from edgar._rich import repr_rich, df_to_rich_table
from rich.table import Table, Column
from rich import box
from edgar.core import download_text

__all__ = [
    'get_fund',
    'get_fund_information',
    'FundSeriesAndContracts',
    'Fund'
]

# The URL to search for a fund by company name
fund_company_search = "https://www.sec.gov/cgi-bin/browse-edgar?company={}&owner=exclude&action=getcompany"

# The URL to search for a fund by ticker
fund_ticker_search_url = "https://www.sec.gov/cgi-bin/series?CIK=&sc=companyseries&type=N-PX&ticker={}&Find=Search"


@dataclass(frozen=True)
class FundObject:
    company_cik: str
    company_name: str
    name: str
    series: str
    ticker: str
    class_contract: str

    def get_fund_company(self):
        return Company(self.company_cik)

    def __rich__(self):
        table = Table(Column("Fund", style="bold"),
                      Column("Series", style="bold"),
                      Column("Ticker", style="bold"),
                      Column("Class", style="bold"),
                      box=box.ROUNDED)
        table.add_row(self.name, self.series, self.ticker, self.class_contract)
        return table

    def __repr__(self):
        return repr_rich(self.__rich__())


def get_fund(ticker: str):
    """Get the fund information from the ticker"""
    ticker_search_url = fund_ticker_search_url.format(ticker)

    fund_text = download_text(ticker_search_url)

    soup = BeautifulSoup(fund_text, "html.parser")
    if 'To retrieve filings, click on the CIK' not in soup.text:
        return None

    tables = soup.find_all("table")

    # The fund table is the 6th table on the page
    fund_table = tables[5]

    # Initialize empty list to store the rows data
    data = []

    # Loop through each row in the table
    for tr in fund_table.find_all('tr')[4:]:  # Skip the first 4 rows as they contain headers/not needed info
        row_data = []
        for td in tr.find_all('td'):  # Loop through each cell in the row
            if td.a:  # Check if there is an 'a' (anchor) tag in the cell
                if 'CIK' in td.a['href']:
                    row_data.append(td.a.string.strip())  # Append CIK if present
                else:
                    row_data.append(
                        td.a.string.strip() if td.a.string else '')  # Append series or class/contract if present
            else:
                row_data.append(td.get_text(strip=True))  # Otherwise just get the cell text

        # Only append non-empty row data to prevent adding header or line rows
        if any(row_data):
            data.append(row_data)

    # Creating DataFrame from the extracted data
    df = pd.DataFrame(data)

    # Now create the fund
    fund = FundObject(
        company_cik=df.iloc[0, 0],
        company_name=df.iloc[0, 1],
        name=df.iloc[1, 2],
        series=df.iloc[1, 1],
        ticker=df.iloc[-1, -1],
        class_contract=df.iloc[-1, -2]
    )

    # Display the structured data
    return fund


Fund = get_fund


class FundSeriesAndContracts:

    def __init__(self, data: pd.DataFrame):
        self.data = data

    def __rich__(self):
        return df_to_rich_table(self.data.set_index("Fund"), index_name="Fund", title="Fund Series and Contracts")

    def __repr__(self):
        return repr_rich(self.__rich__())


def get_fund_information(sec_header: SECHeader):
    header_text = sec_header.text
    series_and_classes_contracts_text = re.search(
        r'<SERIES-AND-CLASSES-CONTRACTS-DATA>(.*?)</SERIES-AND-CLASSES-CONTRACTS-DATA>', header_text, re.DOTALL)
    if series_and_classes_contracts_text:
        df = parse_fund_data(series_and_classes_contracts_text.group(1))
        return FundSeriesAndContracts(df)


def parse_fund_data(series_sgml_data: str) -> pd.DataFrame:
    """
    Parse the SGML text that looks like this:
    <SERIES-AND-CLASSES-CONTRACTS-DATA>
    <EXISTING-SERIES-AND-CLASSES-CONTRACTS>
    <SERIES>
    <OWNER-CIK>0001090372
    <SERIES-ID>S000071967
    <SERIES-NAME>Jacob Forward ETF
    <CLASS-CONTRACT>
    <CLASS-CONTRACT-ID>C000227599
    <CLASS-CONTRACT-NAME>Jacob Forward ETF
    <CLASS-CONTRACT-TICKER-SYMBOL>JFWD
    </CLASS-CONTRACT>
    </SERIES>
    </EXISTING-SERIES-AND-CLASSES-CONTRACTS>
    </SERIES-AND-CLASSES-CONTRACTS-DATA>
    :param series_sgml_data:
    :return:
    """
    # Regular expressions to match each relevant tag
    series_re = re.compile(r'<SERIES>(.*?)<\/SERIES>', re.DOTALL)
    data_re = re.compile(r'<([^>]+)>([^<]*)')

    # Extract SERIES blocks
    series_blocks = series_re.findall(series_sgml_data)

    # Create an empty DataFrame
    columns = [
        "OWNER-CIK", "SERIES-ID", "SERIES-NAME",
        "CLASS-CONTRACT-ID", "CLASS-CONTRACT-NAME", "CLASS-CONTRACT-TICKER-SYMBOL"
    ]

    # Extract information from SERIES blocks and append to DataFrame
    rows = []
    for block in series_blocks:
        data_matches = data_re.findall(block)
        data_dict = {tag: value.strip() for tag, value in data_matches}

        class_contract_data = {
            "CLASS-CONTRACT-ID": data_dict.get("CLASS-CONTRACT-ID", ""),
            "CLASS-CONTRACT-NAME": data_dict.get("CLASS-CONTRACT-NAME", ""),
            "CLASS-CONTRACT-TICKER-SYMBOL": data_dict.get("CLASS-CONTRACT-TICKER-SYMBOL", "")
        }

        # Merge SERIES and CLASS-CONTRACT data
        row_data = {**data_dict, **class_contract_data}
        rows.append(row_data)
    df = pd.DataFrame(rows, columns=columns).iloc[:, :6]

    return (df.rename(columns={"OWNER-CIK": "CIK", "SERIES-ID": "SeriesID", "SERIES-NAME": "Fund",
                               "CLASS-CONTRACT-ID": "ContractID", "CLASS-CONTRACT-NAME": "Class",
                               "CLASS-CONTRACT-TICKER-SYMBOL": "Ticker"})
            .filter(["Fund", "Ticker", "SeriesID", "ContractID", "Class", "CIK"])
            )
