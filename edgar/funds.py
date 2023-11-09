import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Union, Dict, List, Tuple, Optional

import pandas as pd
from bs4 import BeautifulSoup
from bs4.element import Tag
from rich import box
from rich.table import Table, Column

from edgar._companies import Company
from edgar._filings import SECHeader
from edgar._party import Address
from edgar._rich import repr_rich, df_to_rich_table
from edgar.core import download_text

__all__ = [
    'get_fund_by_ticker',
    'get_fund_information',
    'FundSeriesAndContracts',
    'Fund',
    'get_class_contract',
    'get_series',
]

# The URL to search for a fund by company name
fund_company_search = "https://www.sec.gov/cgi-bin/browse-edgar?company={}&owner=exclude&action=getcompany"

# The URL to search for a fund by ticker
fund_ticker_search_url = "https://www.sec.gov/cgi-bin/series?CIK=&sc=companyseries&ticker={}&Find=Search"

# Search for a fund by class
fund_class_or_series_search_url = "https://www.sec.gov/cgi-bin/browse-edgar?CIK={}&action=getcompany"


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


def get_fund_by_ticker(ticker: str):
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


Fund = get_fund_by_ticker


def get_class_contract(class_contract_id: str):
    return get_class_or_series(class_contract_id)


def get_series(series_id: str):
    return get_class_or_series(series_id)


class CompanyInfo:

    def __init__(self, name: str,
                 cik: str,
                 ident_info: Dict[str, str], addresses: List[Address]):
        self.name: str = name
        self.cik: str = cik
        self.ident_info: Dict[str, str] = ident_info
        self.addresses: List[Address] = addresses

    @property
    def state(self):
        return self.ident_info.get("State location", None)

    @property
    def state_of_incorporation(self):
        return self.ident_info.get("State of Inc.", None)

    def __str__(self):
        return f"{self.name} ({self.cik})"

    @classmethod
    def from_tag(cls, content_div: Tag):

        ident_info_dict = {}
        company_info_div = content_div.find("div", class_="companyInfo")
        company_name_tag = company_info_div.find('span', class_='companyName')
        company_name = company_name_tag.text.split('CIK')[0].strip()

        cik = company_name_tag.a.text.split(' ')[0]

        # Extract the identifying information
        for tag in company_info_div.find_all('br'):
            tag.replace_with('\n')
        ident_info = company_info_div.find('p', class_='identInfo')
        ident_line = ident_info.get_text().replace("|", "\n").strip()
        for line in ident_line.split("\n"):
            if ":" in line:
                key, value = line.split(":")
                ident_info_dict[key.strip()] = value.strip().replace("\xa0", " ")

        # Addresses
        mailer_divs = content_div.find_all("div", class_="mailer")
        addresses = [re.sub(r'\n\s+', '\n', mailer_div.text.strip())
                     for mailer_div in mailer_divs]

        return cls(name=company_name, cik=cik, ident_info=ident_info_dict, addresses=addresses)

    @classmethod
    def from_html(cls, company_info_html: Union[str, Tag]):
        soup = BeautifulSoup(company_info_html, features="html.parser")
        content_div = soup.find_all("div", {"id": "contentDiv"})
        return [CompanyInfo.from_tag(tag) for tag in content_div]


class ClassContractOrSeries:

    def __init__(self, company_info: CompanyInfo, contract_or_series: str):
        self.company_info = company_info
        self._contract_or_series = contract_or_series

    @property
    def fund_cik(self):
        return self.company_info.cik

    @property
    def fund_name(self):
        return self.company_info.name

    @lru_cache(maxsize=1)
    def _id_and_name(self) -> Optional[Tuple[str, str]]:
        class_contract_str = self.company_info.ident_info.get(self._contract_or_series, None)
        if not class_contract_str:
            return None
        match = re.match(r'([CS]\d+)(?:\s(.*))?', class_contract_str)

        # Storing the results in variables if matched, with a default for description if not present
        cik = match.group(1) if match else ""
        cik_description = match.group(2) if match and match.group(2) else ""
        return cik, cik_description

    @property
    def id(self):
        id_and_name = self._id_and_name()
        if id_and_name:
            return id_and_name[0]

    @property
    def name(self):
        id_and_name = self._id_and_name()
        if id_and_name:
            return id_and_name[1]

    def __rich__(self):
        table = Table(Column("Fund", style="bold"),
                      Column("Id", style="bold"),
                      Column("Name", style="bold"),
                      box=box.ROUNDED)
        table.add_row(self.fund_name, self.id, self.name)
        return table

    def __repr__(self):
        return repr_rich(self.__rich__())


class ClassContract(ClassContractOrSeries):

    def __init__(self, company_info: CompanyInfo):
        super().__init__(company_info, "Class/Contract")

    @property
    def ticker(self):
        return self.company_info.ident_info.get("Ticker Symbol", None)

    def __rich__(self):
        table = Table(Column("Fund", style="bold"),
                      Column("Class/Contract", style="bold"),
                      Column("Ticker", style="bold"),
                      box=box.ROUNDED)
        table.add_row(self.fund_name, f"{self.id} {self.name}", self.ticker or "")
        return table


class FundSeries(ClassContractOrSeries):

    def __init__(self, company_info: CompanyInfo):
        super().__init__(company_info, "Series")

    def __rich__(self):
        table = Table(Column("Fund", style="bold"),
                      Column("Series", style="bold"),
                      box=box.ROUNDED)
        table.add_row(self.fund_name, f"{self.id} {self.name}")
        return table


def get_class_or_series(contract_or_series_id: str):
    """Get the fund using the class id"""
    search_url = fund_class_or_series_search_url.format(contract_or_series_id)

    fund_text = download_text(search_url)
    soup = BeautifulSoup(fund_text, features="html.parser")
    content_div = soup.find("div", {"id": "contentDiv"})

    # Company Info
    company_info = CompanyInfo.from_tag(content_div)

    if contract_or_series_id.startswith('C'):
        return ClassContract(company_info)
    else:
        return FundSeries(company_info)


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
