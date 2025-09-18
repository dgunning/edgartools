import logging
import urllib.parse
from dataclasses import dataclass
from functools import lru_cache
from io import StringIO
from typing import Dict, List, Optional, Set, Tuple, Union

import pandas as pd
from bs4 import BeautifulSoup

from edgar.httprequests import download_text

# Base URL for resolving relative links
SEC_BASE_URL = "https://www.sec.gov"

log = logging.getLogger(__name__)

# Data classes for our normalized data model
@dataclass
class FundCompanyRecord:
    cik: str
    name: str
    entity_org_type: str
    file_number: str
    address_1: Optional[str] = None
    address_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None


@dataclass
class FundSeriesRecord:
    series_id: str
    name: str
    cik: str  # Parent company CIK


@dataclass
class FundClassRecord:
    class_id: str
    name: str
    ticker: Optional[str]
    series_id: str  # Parent series ID


class FundReferenceData:
    """
    A memory-efficient container for fund reference data that provides fast lookups
    while minimizing data duplication.

    Internally, this class normalizes the data into separate tables for companies,
    series, and classes, with relationships maintained through IDs.

    Lookups are accelerated through indices on common lookup patterns
    like ticker, CIK, series ID, and class ID.
    """

    def __init__(self, data: pd.DataFrame = None):
        """
        Initialize with a DataFrame of fund data.

        The DataFrame should have columns similar to the SEC fund data file:
        - 'Reporting File Number', 'CIK Number', 'Entity Name', 'Entity Org Type',
        - 'Series ID', 'Series Name', 'Class ID', 'Class Name', 'Class Ticker', etc.

        Args:
            data: DataFrame containing fund reference data
        """
        # Initialize empty containers
        self._companies: Dict[str, FundCompanyRecord] = {}
        self._series: Dict[str, FundSeriesRecord] = {}
        self._classes: Dict[str, FundClassRecord] = {}

        # Indexes for fast lookups
        self._ticker_to_class: Dict[str, str] = {}  # ticker -> class_id
        self._series_by_company: Dict[str, Set[str]] = {}  # cik -> set of series_ids
        self._classes_by_series: Dict[str, Set[str]] = {}  # series_id -> set of class_ids

        # Load data if provided
        if data is not None:
            self._load_data(data)

    def _load_data(self, data: pd.DataFrame):
        """
        Load and normalize data from a DataFrame into the internal data structures.

        Args:
            data: DataFrame containing fund reference data
        """
        # Standardize column names if needed
        col_map = {
            'CIK Number': 'cik',
            'Entity Name': 'company_name',
            'Entity Org Type': 'entity_org_type',
            'Reporting File Number': 'file_number',
            'Series ID': 'series_id',
            'Series Name': 'series_name',
            'Class ID': 'class_id',
            'Class Name': 'class_name',
            'Class Ticker': 'ticker',
            'Address_1': 'address_1',
            'Address_2': 'address_2',
            'City': 'city',
            'State': 'state',
            'Zip Code': 'zip_code'
        }

        # Rename columns if they don't match our expected names
        df = data.copy()
        rename_dict = {k: v for k, v in col_map.items() if k in df.columns and v not in df.columns}
        if rename_dict:
            df = df.rename(columns=rename_dict)

        # Process companies (distinct CIKs)
        company_df = df.drop_duplicates(subset=['cik'])[
            ['cik', 'company_name', 'entity_org_type', 'file_number', 
             'address_1', 'address_2', 'city', 'state', 'zip_code']
        ].fillna('')

        for _, row in company_df.iterrows():
            cik = str(row['cik']).zfill(10)  # Ensure CIK is properly formatted
            self._companies[cik] = FundCompanyRecord(
                cik=cik,
                name=row['company_name'],
                entity_org_type=row['entity_org_type'],
                file_number=row['file_number'],
                address_1=row['address_1'] if row['address_1'] else None,
                address_2=row['address_2'] if row['address_2'] else None,
                city=row['city'] if row['city'] else None,
                state=row['state'] if row['state'] else None,
                zip_code=row['zip_code'] if row['zip_code'] else None
            )
            # Initialize empty set for series in this company
            self._series_by_company[cik] = set()

        # Process series (distinct series IDs)
        series_df = df.dropna(subset=['series_id']).drop_duplicates(subset=['series_id'])[
            ['series_id', 'series_name', 'cik']
        ]

        for _, row in series_df.iterrows():
            series_id = row['series_id']
            cik = str(row['cik']).zfill(10)

            # Skip if parent company doesn't exist
            if cik not in self._companies:
                continue

            self._series[series_id] = FundSeriesRecord(
                series_id=series_id,
                name=row['series_name'],
                cik=cik
            )

            # Add to company's series set
            self._series_by_company[cik].add(series_id)

            # Initialize empty set for classes in this series
            self._classes_by_series[series_id] = set()

        # Process classes (distinct class IDs)
        class_df = df.dropna(subset=['class_id']).drop_duplicates(subset=['class_id'])[
            ['class_id', 'class_name', 'ticker', 'series_id']
        ]

        for _, row in class_df.iterrows():
            class_id = row['class_id']
            series_id = row['series_id']

            # Skip if parent series doesn't exist
            if series_id not in self._series:
                continue

            # Handle potentially missing ticker
            ticker = row['ticker'] if pd.notna(row['ticker']) else None

            self._classes[class_id] = FundClassRecord(
                class_id=class_id,
                name=row['class_name'],
                ticker=ticker,
                series_id=series_id
            )

            # Add to series' classes set
            self._classes_by_series[series_id].add(class_id)

            # Add ticker to lookup index if available
            if ticker:
                self._ticker_to_class[ticker] = class_id

    @property
    def companies_count(self) -> int:
        """Get the total number of fund companies."""
        return len(self._companies)

    @property
    def series_count(self) -> int:
        """Get the total number of fund series."""
        return len(self._series)

    @property
    def classes_count(self) -> int:
        """Get the total number of fund classes."""
        return len(self._classes)

    def get_company(self, cik: str) -> Optional[FundCompanyRecord]:
        """
        Get company information by CIK.

        Args:
            cik: Company CIK

        Returns:
            FundCompanyRecord or None if not found
        """
        # Ensure consistent formatting of CIK
        cik = str(cik).zfill(10)
        return self._companies.get(cik)

    def get_series(self, series_id: str) -> Optional[FundSeriesRecord]:
        """
        Get series information by series ID.

        Args:
            series_id: Series ID

        Returns:
            FundSeriesRecord or None if not found
        """
        return self._series.get(series_id)

    def get_class(self, class_id: str) -> Optional[FundClassRecord]:
        """
        Get class information by class ID.

        Args:
            class_id: Class ID

        Returns:
            FundClassRecord or None if not found
        """
        return self._classes.get(class_id)

    def get_class_by_ticker(self, ticker: str) -> Optional[FundClassRecord]:
        """
        Get class information by ticker symbol.

        Args:
            ticker: Ticker symbol

        Returns:
            FundClassRecord or None if not found
        """
        class_id = self._ticker_to_class.get(ticker)
        if class_id:
            return self._classes.get(class_id)
        return None

    def get_series_for_company(self, cik: str) -> List[FundSeriesRecord]:
        """
        Get all series for a company.

        Args:
            cik: Company CIK

        Returns:
            List of FundSeriesRecord objects
        """
        cik = str(cik).zfill(10)
        series_ids = self._series_by_company.get(cik, set())
        return [self._series[s_id] for s_id in series_ids if s_id in self._series]

    def get_classes_for_series(self, series_id: str) -> List[FundClassRecord]:
        """
        Get all classes for a series.

        Args:
            series_id: Series ID

        Returns:
            List of FundClassRecord objects
        """
        class_ids = self._classes_by_series.get(series_id, set())
        return [self._classes[c_id] for c_id in class_ids if c_id in self._classes]

    def find_by_name(self, name_fragment: str, search_type: str = 'company') -> List[Union[FundCompanyRecord, FundSeriesRecord, FundClassRecord]]:
        """
        Find entities containing the name fragment.

        Args:
            name_fragment: Case-insensitive fragment to search for
            search_type: Type of entity to search ('company', 'series', or 'class')

        Returns:
            List of matching records
        """
        name_fragment = name_fragment.lower()

        if search_type == 'company':
            return [company for company in self._companies.values() 
                    if name_fragment in company.name.lower()]
        elif search_type == 'series':
            return [series for series in self._series.values() 
                   if name_fragment in series.name.lower()]
        elif search_type == 'class':
            return [cls for cls in self._classes.values() 
                   if name_fragment in cls.name.lower()]
        else:
            raise ValueError(f"Invalid search_type: {search_type}")

    def get_company_for_series(self, series_id: str) -> Optional[FundCompanyRecord]:
        """
        Get the parent company for a series.

        Args:
            series_id: Series ID

        Returns:
            FundCompanyRecord or None if not found
        """
        series = self._series.get(series_id)
        if series:
            return self._companies.get(series.cik)
        return None

    def get_series_for_class(self, class_id: str) -> Optional[FundSeriesRecord]:
        """
        Get the parent series for a class.

        Args:
            class_id: Class ID

        Returns:
            FundSeriesRecord or None if not found
        """
        class_record = self._classes.get(class_id)
        if class_record:
            return self._series.get(class_record.series_id)
        return None

    def get_company_for_class(self, class_id: str) -> Optional[FundCompanyRecord]:
        """
        Get the parent company for a class (traversing through series).

        Args:
            class_id: Class ID

        Returns:
            FundCompanyRecord or None if not found
        """
        series = self.get_series_for_class(class_id)
        if series:
            return self._companies.get(series.cik)
        return None

    def get_hierarchical_info(self, identifier: str) -> Tuple[Optional[FundCompanyRecord], Optional[FundSeriesRecord], Optional[FundClassRecord]]:
        """
        Get the complete hierarchy for an identifier (CIK, series ID, class ID, or ticker).

        Args:
            identifier: Any identifier (CIK, series ID, class ID, or ticker)

        Returns:
            Tuple of (company, series, class) records, with None for levels not applicable
        """
        company = None
        series = None
        class_record = None

        # Check if it's a CIK (10 digits with leading zeros)
        if isinstance(identifier, str) and (identifier.isdigit() or identifier.startswith('0')):
            cik = str(identifier).zfill(10)
            company = self.get_company(cik)
            if company:
                return company, None, None

        # Check if it's a series ID (starts with S)
        if isinstance(identifier, str) and identifier.upper().startswith('S'):
            series = self.get_series(identifier)
            if series:
                company = self.get_company(series.cik)
                return company, series, None

        # Check if it's a class ID (starts with C)
        if isinstance(identifier, str) and identifier.upper().startswith('C'):
            class_record = self.get_class(identifier)
            if class_record:
                series = self.get_series(class_record.series_id)
                if series:
                    company = self.get_company(series.cik)
                return company, series, class_record

        # Check if it's a ticker
        class_record = self.get_class_by_ticker(identifier)
        if class_record:
            series = self.get_series(class_record.series_id)
            if series:
                company = self.get_company(series.cik)
            return company, series, class_record

        # Nothing found
        return None, None, None

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert the normalized data back to a flat DataFrame.

        Returns:
            DataFrame containing all fund data
        """
        records = []

        for _class_id, class_record in self._classes.items():
            series_id = class_record.series_id
            series_record = self._series.get(series_id)

            if not series_record:
                continue

            cik = series_record.cik
            company_record = self._companies.get(cik)

            if not company_record:
                continue

            records.append({
                'cik': company_record.cik,
                'company_name': company_record.name,
                'entity_org_type': company_record.entity_org_type,
                'file_number': company_record.file_number,
                'series_id': series_record.series_id,
                'series_name': series_record.name,
                'class_id': class_record.class_id,
                'class_name': class_record.name,
                'ticker': class_record.ticker,
                'address_1': company_record.address_1,
                'address_2': company_record.address_2,
                'city': company_record.city,
                'state': company_record.state,
                'zip_code': company_record.zip_code
            })

        return pd.DataFrame(records)


def _find_latest_fund_data_url():
    """Find the URL of the latest fund data CSV file from the SEC website.
    The listing looks like this:

    | File                         | Format | Size |
    |------------------------------|--------|------|
    |[2024](link) Updated 6/5/24   | XML    | 1.2 MB|
    |[2024](link) Updated 6/5/24   | CSV    | 1.2 MB|
    |[2023](link) Updated 6/5/24   | XML    | 1.2 MB|
    |[2023](link) Updated 6/5/24   | CSV    | 1.2 MB|


    """
    list_url = "https://www.sec.gov/about/opendatasetsshtmlinvestment_company"
    html_content = download_text(list_url)
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find all tables on the page
    tables = soup.find_all('table')

    for table in tables:
        # Look for a table with a header row containing 'File', 'Format', 'Size'
        headers = [th.get_text(strip=True) for th in table.find_all('th')]
        if 'File' in headers and 'Format' in headers and 'Size' in headers:
            # Find the index of the Format and File columns
            try:
                format_index = headers.index('Format')
                file_index = headers.index('File')
            except ValueError:
                continue # Headers not found in the expected order

            # Iterate through the rows of this table
            for row in table.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) > max(format_index, file_index):
                    # Check if the format is CSV
                    format_text = cells[format_index].get_text(strip=True)
                    if 'CSV' in format_text:
                        # Find the link in the File column
                        link_tag = cells[file_index].find('a')
                        if link_tag and 'href' in link_tag.attrs:
                            relative_url = link_tag['href']
                            # Construct the absolute URL
                            absolute_url = urllib.parse.urljoin(SEC_BASE_URL, relative_url)
                            return absolute_url
            # If CSV not found in this suitable table, continue to next table just in case
            # but typically the first one found is the correct one.

    # If no suitable table or CSV link is found after checking all tables
    raise ValueError("No fund data CSV file found on the SEC website.")


@lru_cache(maxsize=1)
def get_bulk_fund_data() -> pd.DataFrame:
    """
    Downloads the latest Investment Company tickers and CIKs from the SEC website.
    These are the columns
    ['Reporting File Number', 'CIK Number', 'Entity Name', 'Entity Org Type',
       'Series ID', 'Series Name', 'Class ID', 'Class Name', 'Class Ticker',
       'Address_1', 'Address_2', 'City', 'State', 'Zip Code']

    Returns:
        pd.DataFrame: A DataFrame containing the fund ticker data.
                      Columns typically include 'Ticker', 'CIK', 'Series ID', 'Class ID', etc.
    """
    # Find the latest fund data file URL
    csv_url = _find_latest_fund_data_url()

    raw_data = download_text(csv_url)
    fund_data = pd.read_csv(StringIO(raw_data))

    return fund_data


@lru_cache(maxsize=1)
def get_fund_reference_data() -> FundReferenceData:
    """
    Get a normalized reference data object for all funds, series, and classes.

    Returns:
        FundReferenceData: An object providing efficient lookups for fund entities
    """
    fund_data = get_bulk_fund_data()
    return FundReferenceData(fund_data)


if __name__ == "__main__":
    try:
        # Get the fund reference data
        fund_ref_data = get_fund_reference_data()

        # Print summary statistics

        # Show sample lookups

        # Look up a well-known fund
        vfinx_class = fund_ref_data.get_class_by_ticker('VFIAX')
        if vfinx_class:

            # Get parent series
            vfinx_series = fund_ref_data.get_series_for_class(vfinx_class.class_id)
            if vfinx_series:

                # Get all classes in the series
                series_classes = fund_ref_data.get_classes_for_series(vfinx_series.series_id)
                for _i, _cls in enumerate(series_classes[:5]):
                    pass
                if len(series_classes) > 5:
                    pass

                # Get parent company
                vanguard = fund_ref_data.get_company_for_series(vfinx_series.series_id)
                if vanguard:

                    # Get all series for the company
                    company_series = fund_ref_data.get_series_for_company(vanguard.cik)

    except Exception:
        pass
