import re
from datetime import datetime
from functools import lru_cache
from typing import Union, Dict, List, Tuple, Optional

import pandas as pd
import pyarrow as pa
from bs4 import BeautifulSoup
from bs4.element import Tag
from pydantic import BaseModel
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table, Column

from edgar.entities import Company
from edgar._filings import FilingHeader, Filings
from edgar.richtools import repr_rich, df_to_rich_table
from edgar.core import log
from edgar.httprequests import download_text

__all__ = [
    'Fund',
    'get_fund',
    'FundSeries',
    'FundSeriesAndContracts',
    'FundClass',
    'get_fund',
    'get_fund_with_filings',
    'get_fund_information',

]

# The URL to search for a fund by company name
fund_company_search = "https://www.sec.gov/cgi-bin/browse-edgar?company={}&owner=exclude&action=getcompany"

# The URL to search for a fund by ticker
fund_series_search_url = "https://www.sec.gov/cgi-bin/series?company="

# Search for a fund by class
fund_class_or_series_search_url = "https://www.sec.gov/cgi-bin/browse-edgar?CIK={}"


class Fund(BaseModel):
    """This actually represents a fund contract"""
    company_cik: str
    company_name: str
    name: str
    series: str
    ticker: str
    class_contract_id: str
    class_contract_name: str

    def get_fund_company(self):
        return Company(self.company_cik)

    @property
    @lru_cache(maxsize=1)
    def filings(self):
        fund_class: FundClass = get_fund_with_filings(self.class_contract_id)
        return fund_class.filings

    def __hash__(self):
        return hash(self.class_contract_id)

    def __rich__(self):
        table = Table(Column("Fund", style="bold"),
                      Column("Class", style="bold"),
                      Column("Series Id", style="bold"),
                      Column("Ticker", style="bold"),
                      box=box.ROUNDED)
        table.add_row(self.name,
                      f"{self.class_contract_name} {self.class_contract_id}",
                      self.series,
                      self.ticker)
        return table

    def __repr__(self):
        return repr_rich(self.__rich__())


@lru_cache(maxsize=16)
def get_fund(identifier: str):
    """Get the fund information from the ticker
    Uses this url "https://www.sec.gov/cgi-bin/series?CIK=&sc=companyseries&ticker={}&Find=Search"
    """
    if re.match(r'^[CS]\d+$', identifier):
        fund_search_url = fund_series_search_url + f"&CIK={identifier}"
    elif re.match(r"^[A-Z]{4}X$", identifier):
        fund_search_url = fund_series_search_url + f"&ticker={identifier}"
    else:
        log.warning(f"Invalid fund identifier {identifier}")
        return None

    # Download the fund page
    fund_text = download_text(fund_search_url)

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
    fund = Fund(
        company_cik=df.iloc[0, 0],
        company_name=df.iloc[0, 1],
        name=df.iloc[1, 2],
        series=df.iloc[1, 1],
        ticker=df.iloc[-1, -1],
        class_contract_id=df.iloc[-1, -3],
        class_contract_name=df.iloc[-1, -2]
    )

    # Display the structured data
    return fund


class FundCompanyInfo:
    """
    Represents the fund company
    This is parsed from the resuls page when we get the fund class or series

    """

    def __init__(self,
                 name: str,
                 cik: str,
                 ident_info: Dict[str, str],
                 addresses: List[str],
                 filings: Filings):
        self.name: str = name
        self.cik: str = cik
        self.ident_info: Dict[str, str] = ident_info
        self.addresses: List[str] = addresses
        self.filings = filings

    @property
    def state(self):
        return self.ident_info.get("State location", None)

    @property
    def state_of_incorporation(self):
        return self.ident_info.get("State of Inc.", None)

    @lru_cache(maxsize=1)
    def id_and_name(self, contract_or_series: str) -> Optional[Tuple[str, str]]:
        class_contract_str = self.ident_info.get(contract_or_series, None)
        if not class_contract_str:
            return None
        match = re.match(r'([CS]\d+)(?:\s(.*))?', class_contract_str)

        # Storing the results in variables if matched, with a default for description if not present
        cik = match.group(1) if match else ""
        cik_description = match.group(2) if match and match.group(2) else ""
        return cik, cik_description

    def __str__(self):
        return f"{self.name} ({self.cik})"

    @classmethod
    def from_html(cls, company_info_html: Union[str, Tag]):
        soup = BeautifulSoup(company_info_html, features="html.parser")

        # Parse the fund company info
        content_div = soup.find("div", {"id": "contentDiv"})

        if content_div is None:
            # Should not reach here, but this is precautionary
            log.warning("Did not find div with id 'contentDiv'")
            return None

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

        filings_table = soup.find("table", class_="tableFile2")
        rows = filings_table.find_all("tr")[1:]

        forms, accession_nos, filing_dates = [], [], []
        for row in rows:
            cells = row.find_all("td")
            form = cells[0].text
            forms.append(form)

            # Get the link href from cell[1]
            link = cells[1].find("a")
            href = link.attrs["href"]
            accession_no = href.split("/")[-1].replace("-index.htm", "")
            accession_nos.append(accession_no)

            # Get the filing_date
            filing_date = datetime.strptime(cells[3].text, '%Y-%m-%d')
            filing_dates.append(filing_date)

        schema = pa.schema([
            ('form', pa.string()),
            ('company', pa.string()),
            ('cik', pa.int32()),
            ('filing_date', pa.date32()),
            ('accession_number', pa.string()),
        ])

        # Create an empty table with the defined schema
        filing_index = pa.Table.from_arrays(arrays=[
            pa.array(forms, type=pa.string()),
            pa.array([company_name] * len(forms), type=pa.string()),
            pa.array([int(cik)] * len(forms), type=pa.int32()),
            pa.array(filing_dates, type=pa.date32()),
            pa.array(accession_nos, type=pa.string()),
        ], schema=schema)
        # Drop duplicate filings by accession number
        # There are duplicates on the results page because each duplicate row actually point to another file number
        filing_index = pa.Table.from_pandas(filing_index.to_pandas().drop_duplicates(subset=["accession_number"]))

        filings = Filings(filing_index=filing_index)

        return cls(name=company_name,
                   cik=cik,
                   filings=filings,
                   ident_info=ident_info_dict,
                   addresses=addresses)

    def __rich__(self):
        table = Table("CIK", Column("Fund Company", style="bold"), box=box.SIMPLE)
        table.add_row(self.cik, self.name)
        return Panel(
            table,
            title=f"{self.name}", box=box.ROUNDED
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


class FundClassOrSeries:

    def __init__(self, company_info: FundCompanyInfo, contract_or_series: str):
        self.fund = company_info
        self._contract_or_series = contract_or_series

    @property
    def fund_cik(self):
        return self.fund.cik

    @property
    def fund_name(self):
        return self.fund.name

    @lru_cache(maxsize=1)
    def _id_and_name(self) -> Optional[Tuple[str, str]]:
        class_contract_str = self.fund.ident_info.get(self._contract_or_series, None)
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

    @property
    def description(self):
        return f"{self.fund_name} {self.id} {self.name}"

    @property
    def filings(self):
        return self.fund.filings

    def __rich__(self):
        table = Table(Column("Fund", style="bold"),
                      Column("Id", style="bold"),
                      Column("Name", style="bold"),
                      box=box.ROUNDED)
        table.add_row(self.fund_name, self.id, self.name)
        return Panel(Group(table, self.filings.__rich__()), title=self.description, subtitle=self.description)

    def __repr__(self):
        return repr_rich(self.__rich__())


class FundClass(FundClassOrSeries):

    def __init__(self, company_info: FundCompanyInfo):
        super().__init__(company_info, "Class/Contract")

    @property
    def ticker(self):
        return self.fund.ident_info.get("Ticker Symbol", None)

    @property
    def description(self):
        return f"{self.fund_name} {self.id} {self.name} {self.ticker or ''}"

    def __rich__(self):
        table = Table(Column("Fund", style="bold"),
                      Column("Class/Contract", style="bold"),
                      Column("Ticker", style="bold"),
                      box=box.ROUNDED)
        table.add_row(self.fund_name, f"{self.id} {self.name}", self.ticker or "")
        return Panel(Group(table, self.filings.__rich__()), title=self.description, subtitle=self.description)


class FundSeries(FundClassOrSeries):

    def __init__(self, company_info: FundCompanyInfo):
        super().__init__(company_info, "Series")

    def __rich__(self):
        table = Table(Column("Fund", style="bold"),
                      Column("Series", style="bold"),
                      box=box.ROUNDED)
        table.add_row(self.fund_name, f"{self.id} {self.name}")
        return Panel(Group(table, self.filings.__rich__()), title=self.description, subtitle=self.description)


def get_fund_with_filings(contract_or_series_id: str):
    """Uses this url https://www.sec.gov/cgi-bin/browse-edgar?CIK={}
       to get the fund class or series including the filings

    """
    if not re.match("[CS]\d+", contract_or_series_id):
        return None
    search_url = fund_class_or_series_search_url.format(contract_or_series_id)

    fund_text = download_text(search_url)

    if "No matching" in fund_text:
        return None

    # Company Info
    company_info = FundCompanyInfo.from_html(fund_text)

    if contract_or_series_id.startswith('C'):
        return FundClass(company_info)
    else:
        return FundSeries(company_info)


class FundSeriesAndContracts:

    def __init__(self, data: pd.DataFrame):
        self.data = data

    def __rich__(self):
        return df_to_rich_table(self.data.set_index("Fund"), index_name="Fund", title="Fund Series and Contracts")

    def __repr__(self):
        return repr_rich(self.__rich__())


def get_fund_information(sec_header: FilingHeader):
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
    series_re = re.compile(r'<SERIES>(.*?)</SERIES>', re.DOTALL)
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
