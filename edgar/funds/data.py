"""
Data structures and functions for working with fund data.

This module provides the FundData class and related functions for 
accessing and manipulating fund data.
"""
import logging
import re
from functools import lru_cache
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

if TYPE_CHECKING:
    from bs4 import Tag

import pandas as pd
import pyarrow as pa
from bs4 import BeautifulSoup

from edgar._filings import Filings
from edgar.datatools import drop_duplicates_pyarrow
from edgar.entity.data import EntityData
from edgar.funds.core import FundClass, FundCompany, FundSeries
from edgar.httprequests import download_text

log = logging.getLogger(__name__)

#
# Direct implementations to replace legacy module dependencies
#

# Direct implementations of fund-related functionality
# These replace the legacy module dependencies

# URL constants for fund searches
fund_series_search_url = "https://www.sec.gov/cgi-bin/series?company="
fund_class_or_series_search_url = "https://www.sec.gov/cgi-bin/browse-edgar?CIK={}"
fund_series_direct_url = "https://www.sec.gov/cgi-bin/browse-edgar?CIK={}&scd=series"

class _FundDTO:
    """
    Data Transfer Object for fund information.

    Internal class used to return fund data from direct implementations.
    This is not part of the public API and should not be used directly.

    Use the Fund class from edgar.funds.core instead.
    """
    def __init__(self, company_cik, company_name, name, series, ticker,
                 class_contract_id, class_contract_name):
        self.company_cik = company_cik
        self.company_name = company_name
        self.name = name
        self.series = series
        self.ticker = ticker
        self.class_contract_id = class_contract_id
        self.class_contract_name = class_contract_name

    def __str__(self):
        return f"{self.name} - {self.ticker} [{self.class_contract_id}]"

# Parse SGML fund data (directly implemented)
def parse_fund_data(series_sgml_data: str) -> pd.DataFrame:
    """
    Parse the SGML text containing fund series and class information.

    Args:
        series_sgml_data: SGML text with SERIES-AND-CLASSES-CONTRACTS-DATA

    Returns:
        DataFrame with parsed fund information

    Example SGML data:
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

    # Create DataFrame and select relevant columns
    df = pd.DataFrame(rows, columns=columns).iloc[:, :6]

    # Rename columns for consistency
    return (df.rename(columns={
            "OWNER-CIK": "CIK", 
            "SERIES-ID": "SeriesID", 
            "SERIES-NAME": "Fund",
            "CLASS-CONTRACT-ID": "ContractID", 
            "CLASS-CONTRACT-NAME": "Class",
            "CLASS-CONTRACT-TICKER-SYMBOL": "Ticker"
        })
        .filter(["Fund", "Ticker", "SeriesID", "ContractID", "Class", "CIK"])
    )

# Direct implementation of FundCompanyInfo
class _FundCompanyInfo:
    """
    Internal helper class representing the fund company.
    This is parsed from the results page when we get the fund class or series.

    Not part of the public API - use the Fund class from edgar.funds.core instead.
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

    @classmethod
    def from_html(cls, company_info_html: Union[str, 'Tag']):

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

        filing_index = cls._extract_filings(soup, company_name, cik)
        filings = Filings(filing_index=filing_index)

        return cls(name=company_name,
                   cik=cik,
                   filings=filings,
                   ident_info=ident_info_dict,
                   addresses=addresses)

    @classmethod
    def _extract_filings(cls, soup, company_name: str, cik: str):
        from datetime import datetime

        import pyarrow as pa

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

        return filing_index


# Direct implementation of FundClassOrSeries and subclasses
class _FundClassOrSeries:
    """
    Internal base class for fund classes and series.

    Not part of the public API - use the FundClass and FundSeries classes 
    from edgar.funds.core instead.
    """
    def __init__(self, company_info: '_FundCompanyInfo', contract_or_series: str):
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
        return None

    @property
    def name(self):
        id_and_name = self._id_and_name()
        if id_and_name:
            return id_and_name[1]
        return None

    @property
    def description(self):
        return f"{self.fund_name} {self.id} {self.name}"

    @property
    def filings(self):
        return self.fund.filings


class _FundClass(_FundClassOrSeries):
    """
    Internal implementation of fund class (contract) information.

    Not part of the public API - use the FundClass class from edgar.funds.core instead.
    """
    def __init__(self, company_info: '_FundCompanyInfo'):
        super().__init__(company_info, "Class/Contract")

    @property
    def ticker(self):
        return self.fund.ident_info.get("Ticker Symbol", None)

    @property
    def description(self):
        return f"{self.fund_name} {self.id} {self.name} {self.ticker or ''}"


class _FundSeries(_FundClassOrSeries):
    """
    Internal implementation of fund series information.

    Not part of the public API - use the FundSeries class from edgar.funds.core instead.
    """
    def __init__(self, company_info: '_FundCompanyInfo'):
        super().__init__(company_info, "Series")


# Direct implementation of get_fund_with_filings
def direct_get_fund_with_filings(contract_or_series_id: str):
    """
    Get fund class or series information including filings from the SEC website.

    Args:
        contract_or_series_id: Series ID (S...) or Class ID (C...)

    Returns:
        FundClass or FundSeries object, or None if not found
    """


    # URL template to search for a fund by class or series ID
    fund_class_or_series_search_url = "https://www.sec.gov/cgi-bin/browse-edgar?CIK={}"

    if not re.match(r"[CS]\d+", contract_or_series_id):
        return None

    base_url = fund_class_or_series_search_url.format(contract_or_series_id)
    # Start at 0 and download 100
    search_url = base_url + "&start=0&count=100"

    try:
        fund_text = download_text(search_url)

        if "No matching" in fund_text:
            return None

        # Company Info
        company_info = _FundCompanyInfo.from_html(fund_text)

        # Get the remaining filings
        start, count = 101, 100

        filing_index = company_info.filings.data
        while True:
            # Get the next page
            next_page = base_url + f"&start={start}&count={count}"
            fund_text = download_text(next_page)
            soup = BeautifulSoup(fund_text, features="html.parser")
            filing_index_on_page = _FundCompanyInfo._extract_filings(soup, company_info.name, company_info.cik)
            if len(filing_index_on_page) == 0:
                break
            filing_index = pa.concat_tables([filing_index, filing_index_on_page])
            start += count

        # Drop duplicate filings by accession number
        filing_index = drop_duplicates_pyarrow(filing_index, column_name='accession_number')
        company_info.filings = Filings(filing_index=filing_index)

        if contract_or_series_id.startswith('C'):
            return _FundClass(company_info)
        else:
            return _FundSeries(company_info)
    except Exception as e:
        log.warning("Error retrieving fund information for %s: %s", contract_or_series_id, e)
        return None

@lru_cache(maxsize=16)
def get_fund_object(identifier: str) -> Optional[Union[FundCompany, FundSeries, FundCompany]]:
    """
    Get a Fund related object by it's identifier.

    Args:
        identifier: A CIK, a series  id (e.g. 'S000001234') or class id or Fund ticker (e.g. 'VFINX')

    Returns:
        A FundCompany or FundSeries or FundClass
    """

    if re.match(r'^[CS]\d+$', identifier):
        identifier_type = 'Series' if identifier.startswith('S') else 'Class'
        fund_search_url = fund_series_search_url + f"&CIK={identifier}"
    elif re.match(r"^[A-Z]{4}X$", identifier):
        identifier_type = 'Class'
        fund_search_url = fund_series_search_url + f"&ticker={identifier}"
    elif re.match(r"^0\d{9}$", identifier):
        identifier_type = 'FundCompany'
        fund_search_url = fund_series_search_url + f"&CIK={identifier}"
    else:
        log.warning("Invalid fund identifier %s", identifier)
        return None

    # Download the fund page
    fund_text = download_text(fund_search_url)

    soup = BeautifulSoup(fund_text, "html.parser")
    if 'To retrieve filings, click on the CIK' not in soup.text:
        return None

    tables = soup.find_all("table")

     # The fund table is the 6th table on the page
    if len(tables) < 6:
        log.warning("Expected fund table not found for %s", identifier)
        return None

    fund_table = tables[5]

    all_series = []
    fund_company:Optional[FundCompany] = None

    current_series:Optional[FundSeries] = None
    current_class:Optional[FundClass] = None
    for tr in fund_table.find_all('tr')[4:]:  # Skip the first 4 rows as they contain headers
        row_data = [td.get_text().strip() for td in tr.find_all('td') if td.get_text().strip()]

        if not row_data:
            continue
        if re.match(r'^0\d{9}$', row_data[0]):
            fund_company = FundCompany(cik_or_identifier=row_data[0], fund_name=row_data[1], all_series=all_series)
        elif re.match(r'^S\d+$', row_data[0]):
            current_series = FundSeries(series_id=row_data[0], name=row_data[1], fund_company=fund_company)
            fund_company.all_series.append(current_series)
        elif re.match(r'^C\d+$', row_data[0]):
            class_id, class_name = row_data[0], row_data[1]
            ticker = row_data[2] if len(row_data) > 2 else None
            current_class = FundClass(class_id=class_id, name=class_name, ticker=ticker)
            current_class.series = current_series
            current_series.fund_classes.append(current_class)

    if identifier_type == "FundCompany":
        return fund_company
    elif identifier_type == "Series":
        return current_series
    elif identifier_type == "Class":
        return current_class


def is_fund_ticker(identifier: str) -> bool:
    """
    Check if an identifier is a fund ticker.

    Args:
        identifier: The identifier to check

    Returns:
        True if it's a fund ticker, False otherwise
    """
    # Use our own implementation
    if identifier and isinstance(identifier, str):
        return bool(re.match(r"^[A-Z]{4}X$", identifier))
    return False


class FundData(EntityData):
    """
    Fund-specific data container.

    Contains specialized properties and methods for fund entities.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.series_id = kwargs.get('series_id')
        self.class_ids = kwargs.get('class_ids', [])
        self._fund_classes = kwargs.get('fund_classes', [])

    @property
    def is_fund(self) -> bool:
        """Check if entity is a fund."""
        return True


def resolve_fund_identifier(identifier):
    """
    Convert fund tickers or series IDs to CIK.

    Args:
        identifier: Fund ticker, Series ID, or CIK

    Returns:
        CIK as integer or original identifier if conversion not possible
    """
    if isinstance(identifier, str):
        # Handle Series ID (S000XXXXX)
        if identifier.startswith('S') and identifier[1:].isdigit():
            try:
                # Try our direct implementation
                fund_info = direct_get_fund_with_filings(identifier)
                if fund_info and hasattr(fund_info, 'fund_cik'):
                    return int(fund_info.fund_cik)
            except Exception as e:
                log.warning("Error resolving series ID %s: %s", identifier, e)

        # Handle Class ID (C000XXXXX)
        if identifier.startswith('C') and identifier[1:].isdigit():
            try:
                # Try our direct implementation
                fund_info = direct_get_fund_with_filings(identifier)
                if fund_info and hasattr(fund_info, 'fund_cik'):
                    return int(fund_info.fund_cik)
            except Exception as e:
                log.warning("Error resolving class ID %s: %s", identifier, e)

        # Handle fund ticker
        if is_fund_ticker(identifier):
            try:
                # Use our direct implementation for tickers
                fund_info = (identifier)
                if fund_info and hasattr(fund_info, 'company_cik'):
                    return int(fund_info.company_cik)
            except Exception as e:
                log.warning("Error resolving fund ticker %s: %s", identifier, e)

    return identifier


def get_fund_information(header):
    """
    Extract fund information from a filing header.

    Args:
        header: Filing header

    Returns:
        Fund series and contract information
    """
    # Import FundSeriesAndContracts here to avoid circular imports
    from edgar.funds import FundSeriesAndContracts

    if not header or not hasattr(header, 'text'):
        return FundSeriesAndContracts()

    try:
        # Try our direct implementation first
        header_text = header.text
        series_and_classes_contracts_text = re.search(
            r'<SERIES-AND-CLASSES-CONTRACTS-DATA>(.*?)</SERIES-AND-CLASSES-CONTRACTS-DATA>', 
            header_text, 
            re.DOTALL
        )

        if series_and_classes_contracts_text:
            # Use our directly implemented parse_fund_data
            df = parse_fund_data(series_and_classes_contracts_text.group(1))
            return FundSeriesAndContracts(df)

    except Exception as e:
        log.debug("Error parsing fund information directly: %s", e)

    # Fallback implementation - extract fund information from header directly using regex
    try:
        # Try to extract fund information from the header text with regex
        if header and hasattr(header, 'text'):
            # Look for SERIES-ID and CONTRACT-ID in the header
            series_matches = re.findall(r'SERIES-ID[^>]*>([^<]+)', str(header.text))
            contract_matches = re.findall(r'CONTRACT-ID[^>]*>([^<]+)', str(header.text))
            name_matches = re.findall(r'FILER[^>]*>.*?COMPANY-DATA[^>]*>.*?CONFORMED-NAME[^>]*>([^<]+)', str(header.text))
            ticker_matches = re.findall(r'TICKER-SYMBOL[^>]*>([^<]+)', str(header.text))

            # If we found any matches, create a DataFrame with the information
            if series_matches or contract_matches:
                data = []
                # Join series and contract IDs as rows
                for i in range(max(len(series_matches), len(contract_matches))):
                    series_id = series_matches[i] if i < len(series_matches) else None
                    contract_id = contract_matches[i] if i < len(contract_matches) else None
                    fund_name = name_matches[0] if name_matches else None
                    ticker = ticker_matches[0] if ticker_matches else None

                    data.append({
                        'SeriesID': series_id,
                        'ContractID': contract_id,
                        'Fund': fund_name,
                        'Ticker': ticker,
                        'Class': f"Class {contract_id[-1].upper()}" if contract_id else None
                    })

                if data:
                    return FundSeriesAndContracts(pd.DataFrame(data))

    except Exception as e:
        log.warning("Error in fallback get_fund_information: %s", e)

    # Return an empty container if everything else fails
    return FundSeriesAndContracts()


def parse_series_and_classes_from_html(html_content: str, cik:str) -> List[Dict]:
    """
    Parse series and class information from the SEC series listing HTML page.

    This parses HTML content from the URL https://www.sec.gov/cgi-bin/browse-edgar?CIK=XXXX&scd=series
    which contains a structured listing of all series and classes for a fund company.

    Args:
        html_content: HTML content from the SEC webpage
        fund: Fund entity to associate with the series/classes

    Returns:
        List of dictionaries containing series and class information
    """
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_content, 'html.parser')
    series_data = []

    # Debug information
    log.debug("Parsing series HTML content for fund %s", cik)

    # The table structure in this specific page has series and classes
    # organized in a specific way with indentation levels
    try:
        # Find the main table - in Kinetics HTML, it's the main table in the content area
        tables = soup.find_all('table')

        # Find the table that's likely to contain the series information
        # In SEC pages, it's typically the one with class/contract and series information
        table = None
        for t in tables:
            # Look for rows with series or class info
            if t.find('tr') and re.search(r'Series|Class/Contract', str(t)):
                table = t
                break

        if not table:
            log.warning("No suitable table found in series HTML content")
            return []

        current_series = None
        series_data = []

        # Loop through all rows and process them
        rows = table.find_all('tr')

        # Debug information
        log.debug("Found %d rows in the table", len(rows))

        # Process all rows since the table structure might vary
        for _row_idx, row in enumerate(rows):
            cells = row.find_all('td')
            if not cells or len(cells) < 3:
                continue

            # Check if this is a series row - marked by an S000 ID in a cell with a link
            series_cell = None
            series_id = None
            series_name = None

            # Series IDs are normally in the form S######
            for cell in cells:
                # Look for <a> tags with S IDs
                links = cell.find_all('a', href=True)
                for link in links:
                    if re.search(r'S\d{6,}', link.text):
                        series_id = re.search(r'S\d{6,}', link.text).group(0)
                        series_cell = cell
                        break
                if series_cell:
                    break

            # If we found a series ID, extract its name and create a series entry
            if series_id:
                # Try to find the series name in the next cell or in the same row
                series_name = None
                for cell in cells:
                    # Look for a cell with a link that's not the series ID
                    if cell != series_cell and cell.find('a'):
                        # Check if the link text doesn't match the series ID - it's likely the name
                        link_text = cell.find('a').text.strip()
                        if link_text and series_id not in link_text:
                            series_name = link_text
                            break

                # If we couldn't find a name, use a default
                if not series_name:
                    series_name = f"Series {series_id}"

                # Create a new series entry
                current_series = {
                    'series_id': series_id,
                    'series_name': series_name,
                    'classes': []
                }
                series_data.append(current_series)
                log.debug("Found series: %s - %s", series_id, series_name)

            # Check if this row contains a class - marked by a C000 ID
            # Classes appear after a series and are indented
            elif current_series:
                class_id = None
                class_name = None
                class_ticker = ""

                # Look for class IDs in the form C######
                for cell in cells:
                    # Search for C IDs in links
                    links = cell.find_all('a', href=True)
                    for link in links:
                        if re.search(r'C\d{6,}', link.text):
                            class_id = re.search(r'C\d{6,}', link.text).group(0)
                            break
                    if class_id:
                        break

                if class_id:
                    # Find the class name - usually in a cell after the ID
                    for cell_idx, cell in enumerate(cells):
                        if class_id in str(cell) and cell_idx + 1 < len(cells):
                            # Class name is often in the next cell
                            class_name = cells[cell_idx + 1].text.strip()
                            break

                    parts = class_name.split("\n")
                    class_name = parts[1]
                    if len(parts) > 2:
                        class_ticker = parts[2].strip()

                    # If we couldn't find a name, use a default
                    if not class_name:
                        class_name = f"Class {class_id}"

                    # Add this class to the current series
                    current_series['classes'].append({
                        'class_id': class_id,
                        'class_name': class_name,
                        'ticker': class_ticker
                    })
                    log.debug("Found class: %s - %s (%s)", class_id, class_name, class_ticker)

        # Debug information
        log.debug("Found %d series with classes", len(series_data))

    except Exception as e:
        log.warning("Error parsing series HTML: %s", e)
        import traceback
        log.debug(traceback.format_exc())

    return series_data


def get_series_and_classes_from_sec(cik: Union[str, int]) -> List[Dict]:
    """
    Directly fetch and parse series and class information from the SEC website.

    This uses the SEC's series listing page which provides a comprehensive view
    of all series and classes for a fund company.

    Args:
        cik: The CIK of the fund company

    Returns:
        List of dictionaries containing parsed series and class information
    """

    # Format CIK properly for URL
    cik_str = str(cik).zfill(10)
    url = fund_series_direct_url.format(cik_str)

    # Download the HTML content
    html_content = download_text(url)

    # Check if we received valid content
    if 'No matching' in html_content or 'series for cik' not in html_content.lower():
        log.debug("No series information found for CIK %s", cik)
        return []

    return parse_series_and_classes_from_html(html_content, cik)
