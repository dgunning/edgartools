"""
Data structures and functions for working with fund data.

This module provides the FundData class and related functions for 
accessing and manipulating fund data.
"""
import logging
import re
from functools import lru_cache
from typing import List, Dict, Optional, Union, Tuple, TYPE_CHECKING

import pandas as pd
import pyarrow as pa

from edgar.entity.data import EntityData
from edgar._filings import Filings
from edgar.httprequests import download_text
from edgar.datatools import drop_duplicates_pyarrow
from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from edgar.funds.core import Fund, FundClass, FundSeries

log = logging.getLogger(__name__)

#
# Direct implementations to replace legacy module dependencies
#

# Direct implementations of fund-related functionality
# These replace the legacy module dependencies

# URL constants for fund searches
fund_series_search_url = "https://www.sec.gov/cgi-bin/series?company="
fund_class_or_series_search_url = "https://www.sec.gov/cgi-bin/browse-edgar?CIK={}"

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
        import pyarrow as pa
        from datetime import datetime
        
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
        log.warning(f"Error retrieving fund information for {contract_or_series_id}: {e}")
        return None

@lru_cache(maxsize=16)
def direct_get_fund(identifier: str):
    """
    Get fund information from the ticker or identifier.
    
    Args:
        identifier: Fund ticker (e.g. 'VFINX') or series/class ID (e.g. 'S000001234')
        
    Returns:
        Fund object with fund details or None if not found
    """
    from edgar.httprequests import download_text
    from bs4 import BeautifulSoup
    
    if re.match(r'^[CS]\d+$', identifier):
        fund_search_url = fund_series_search_url + f"&CIK={identifier}"
    elif re.match(r"^[A-Z]{4}X$", identifier):
        fund_search_url = fund_series_search_url + f"&ticker={identifier}"
    else:
        log.warning(f"Invalid fund identifier {identifier}")
        return None

    try:
        # Download the fund page
        fund_text = download_text(fund_search_url)

        soup = BeautifulSoup(fund_text, "html.parser")
        if 'To retrieve filings, click on the CIK' not in soup.text:
            return None

        tables = soup.find_all("table")
        
        # The fund table is the 6th table on the page
        if len(tables) < 6:
            log.warning(f"Expected fund table not found for {identifier}")
            return None
            
        fund_table = tables[5]

        # Initialize empty list to store the rows data
        data = []

        # Loop through each row in the table
        for tr in fund_table.find_all('tr')[4:]:  # Skip the first 4 rows as they contain headers
            row_data = []
            for td in tr.find_all('td'):  # Loop through each cell in the row
                if td.a:  # Check if there is an 'a' (anchor) tag in the cell
                    if 'CIK' in td.a.get('href', ''):
                        row_data.append(td.a.string.strip())  # Append CIK if present
                    else:
                        row_data.append(
                            td.a.string.strip() if td.a.string else '')  # Append series or class/contract info
                else:
                    row_data.append(td.get_text(strip=True))  # Otherwise just get the cell text

            # Only append non-empty row data to prevent adding header or line rows
            if any(row_data):
                data.append(row_data)

        # Creating DataFrame from the extracted data
        df = pd.DataFrame(data)
        
        if df.empty or df.shape[1] < 5:
            log.warning(f"Invalid fund data format for {identifier}")
            return None

        # Create the fund object from DataFrame
        try:
            return _FundDTO(
                company_cik=df.iloc[0, 0],
                company_name=df.iloc[0, 1],
                name=df.iloc[1, 2],
                series=df.iloc[1, 1],
                ticker=df.iloc[-1, -1],
                class_contract_id=df.iloc[-1, -3],
                class_contract_name=df.iloc[-1, -2]
            )
        except (IndexError, KeyError) as e:
            log.warning(f"Error creating fund from data for {identifier}: {e}")
            return None
            
    except Exception as e:
        log.warning(f"Error retrieving fund information for {identifier}: {e}")
        return None


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
                log.warning(f"Error resolving series ID {identifier}: {e}")
                
        # Handle Class ID (C000XXXXX)
        if identifier.startswith('C') and identifier[1:].isdigit():
            try:
                # Try our direct implementation
                fund_info = direct_get_fund_with_filings(identifier)
                if fund_info and hasattr(fund_info, 'fund_cik'):
                    return int(fund_info.fund_cik)
            except Exception as e:
                log.warning(f"Error resolving class ID {identifier}: {e}")
                
        # Handle fund ticker
        if is_fund_ticker(identifier):
            try:
                # Use our direct implementation for tickers
                fund_info = direct_get_fund(identifier)
                if fund_info and hasattr(fund_info, 'company_cik'):
                    return int(fund_info.company_cik)
            except Exception as e:
                log.warning(f"Error resolving fund ticker {identifier}: {e}")
    
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
        log.debug(f"Error parsing fund information directly: {e}")
    
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
        log.warning(f"Error in fallback get_fund_information: {e}")
    
    # Return an empty container if everything else fails
    return FundSeriesAndContracts()


def get_fund_classes(fund: 'Fund') -> List['FundClass']:
    """
    Get all share classes associated with a fund company.
    
    The Fund entity represents a fund company that may have multiple fund series
    and classes. This function examines the company's filings to identify all
    associated fund classes.
    
    Args:
        fund: The Fund entity (fund company)
        
    Returns:
        List of FundClass instances for all classes offered by this fund company
    """
    # Import the proper FundClass from core
    from edgar.funds.core import FundClass
    
    classes = []
    
    # First try to get fund series from filings
    filings = fund.get_filings(form=['N-CEN', 'N-CSR', '485BPOS', 'N-1A', 'N-CSR/A', '485APOS'])
    
    for filing in filings:
        try:
            series_contracts = get_fund_information(filing.header)
            if series_contracts and hasattr(series_contracts, 'data'):
                # Extract class data and create FundClass objects
                for _, row in series_contracts.data.iterrows():
                    class_id = row.get('ContractID')
                    if class_id:
                        classes.append(FundClass(
                            class_id=class_id,
                            fund=fund,
                            name=row.get('Class'),
                            ticker=row.get('Ticker')
                        ))
                if classes:
                    break
        except Exception as e:
            log.debug(f"Error getting fund classes from filing {filing.accession_no}: {e}")
    
    return classes


def get_fund_series(fund: 'Fund') -> Optional['FundSeries']:
    """
    Get the primary fund series associated with a fund company.
    
    The Fund entity represents a fund company that may offer multiple fund series.
    This function searches the company's filings to identify the primary series,
    or if multiple series exist, returns one of them.
    
    Args:
        fund: The Fund entity (fund company)
        
    Returns:
        FundSeries instance representing a fund series, or None if not found
    """
    # Import the proper FundSeries from core
    from edgar.funds.core import FundSeries
    
    # Try to get series info from filings first
    filings = fund.get_filings(form=['N-CEN', 'N-PORT', 'N-1A', '485BPOS', '485APOS'])
    for filing in filings:
        try:
            # First try to get series info from the fund_information function
            fund_info = get_fund_information(filing.header())
            if fund_info and hasattr(fund_info, 'data') and not fund_info.data.empty:
                # Extract series info from the first row
                row = fund_info.data.iloc[0]
                series_id = row.get('SeriesID')
                if series_id:
                    return FundSeries(
                        series_id=series_id,
                        name=row.get('Fund', fund.data.name),
                        fund=fund
                    )
            
            # If that doesn't work, try regex on the header
            header = filing.header()
            if header:
                # Look for series ID in the header text
                series_match = re.search(r'SERIES-ID[^>]*>([^<]+)', str(header.text))
                if series_match:
                    series_id = series_match.group(1).strip()
                    return FundSeries(
                        series_id=series_id,
                        name=fund.data.name,
                        fund=fund
                    )
        except Exception as e:
            log.debug(f"Error getting series info from filing {filing.accession_no}: {e}")
    
    # If we couldn't find series info from filings, try the SEC website
    try:
        fund_info = direct_get_fund_with_filings(f"CIK={fund.cik}")
        if fund_info:
            # Check if this is a series
            if hasattr(fund_info, 'id') and fund_info.id and fund_info.id.startswith('S'):
                return FundSeries(
                    series_id=fund_info.id, 
                    name=fund_info.name,
                    fund=fund
                )
            
            # Or check if we can find a series in the fund info
            if hasattr(fund_info, 'fund') and hasattr(fund_info.fund, 'ident_info'):
                series_info = fund_info.fund.ident_info.get('Series')
                if series_info and series_info.startswith('S'):
                    # Extract series ID and name if available
                    series_match = re.match(r'([S]\d+)(?:\s(.*))?', series_info)
                    if series_match:
                        series_id = series_match.group(1)
                        series_name = series_match.group(2) if len(series_match.groups()) > 1 else fund.data.name
                        return FundSeries(
                            series_id=series_id, 
                            name=series_name,
                            fund=fund
                        )
    except Exception as e:
        log.debug(f"Error retrieving fund series from SEC website: {e}")
    
    # If we still can't find a series, try checking if there is an embedded series ID in the name
    if hasattr(fund.data, 'name'):
        series_match = re.search(r'[S]\d{6,}', fund.data.name)
        if series_match:
            series_id = series_match.group(0)
            return FundSeries(
                series_id=series_id,
                name=fund.data.name,
                fund=fund
            )
    
    # As a last resort, create a synthetic series ID based on CIK
    # This is useful for funds that don't have explicit series
    return FundSeries(
        series_id=f"S{fund.cik}",
        name=fund.data.name if hasattr(fund.data, 'name') else f"Fund {fund.cik}",
        fund=fund
    )


def get_fund_portfolio(fund: 'Fund') -> pd.DataFrame:
    """
    Get the portfolio holdings for the fund company.
    
    The Fund entity represents a fund company that may have multiple fund series
    and classes, each with their own portfolios. This function finds the latest
    portfolio filing (typically N-PORT or 13F) and extracts the holdings.
    
    Args:
        fund: The Fund entity (fund company)
        
    Returns:
        DataFrame containing portfolio holdings from the most recent filing
    """
    # Look for N-PORT filings first
    nport_filings = fund.get_filings(form=['N-PORT', 'N-PORT/A'])
    if nport_filings:
        latest_nport = nport_filings.latest()
        if latest_nport:
            try:
                # Import here to avoid circular imports
                from edgar.funds.reports import get_fund_portfolio_from_filing
                return get_fund_portfolio_from_filing(latest_nport)
            except Exception as e:
                log.warning(f"Error parsing N-PORT filing: {e}")
    
    # Or look for 13F filings (some funds file these)
    thirteenf_filings = fund.get_filings(form=['13F-HR', '13F-HR/A'])
    if thirteenf_filings:
        latest_13f = thirteenf_filings.latest()
        if latest_13f:
            try:
                # Import here to avoid circular imports
                from edgar.funds.thirteenf import get_thirteenf_portfolio
                return get_thirteenf_portfolio(latest_13f)
            except Exception as e:
                log.warning(f"Error parsing 13F filing: {e}")
    
    # Return empty DataFrame if no portfolio data found
    return pd.DataFrame()