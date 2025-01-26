import asyncio
import os
import re
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Union

import pandas as pd
from bs4 import BeautifulSoup
from httpx import HTTPStatusError, AsyncClient
from tqdm.auto import tqdm

from edgar.core import log, get_edgar_data_directory, filing_date_to_year_quarters, extract_dates, strtobool
from edgar.httprequests import download_bulk_data, download_datafile, download_text, throttle_requests
from edgar.reference.tickers import (ticker_txt_url,
                                     company_tickers_json_url,
                                     mutual_fund_tickers_url,
                                     company_tickers_exchange_url)

__all__ = ['download_edgar_data',
           'get_edgar_data_directory',
           'use_local_storage',
           'is_using_local_storage',
           'download_filings',
           'local_filing_path']

def use_local_storage(use_local: bool = True):
    """
    Will use local data if set to True
    """
    os.environ['EDGAR_USE_LOCAL_DATA'] = "1" if use_local else "0"


def is_using_local_storage() -> bool:
    """
    Returns True if using local storage
    """
    return strtobool(os.getenv('EDGAR_USE_LOCAL_DATA', "False"))


async def download_facts_async(client: Optional[AsyncClient]) -> Path:
    """
    Download company facts
    """
    log.info(f"Downloading Company facts to {get_edgar_data_directory()}/companyfacts")

    return await download_bulk_data(client=client, url="https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip")

def download_facts() -> Path:
    """
    Download company facts
    """
    
    return asyncio.run(download_facts_async(client = None))

async def download_submissions_async(client: Optional[AsyncClient]) -> Path:
    """
    Download company submissions
    """
    log.info(f"Downloading Company submissions to {get_edgar_data_directory()}/submissions")

    return await download_bulk_data(client=client, url="https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip")


def download_submissions() -> Path:
    """
    Download company facts
    """
    return asyncio.run(download_submissions_async(client = None))

def download_ticker_data(reference_data_directory: Path):
    """
    Download reference data from the SEC website.
    """
    log.info(f"Downloading ticker data to {reference_data_directory}")
    download_datafile(ticker_txt_url, reference_data_directory)
    download_datafile(company_tickers_json_url, reference_data_directory)
    download_datafile(mutual_fund_tickers_url, reference_data_directory)
    download_datafile(company_tickers_exchange_url, reference_data_directory)


def download_reference_data():
    """
    Download reference data from the SEC website.
    """
    log.info(f"Downloading reference data to {get_edgar_data_directory()}")
    reference_directory = get_edgar_data_directory() / "reference"
    reference_directory.mkdir(exist_ok=True)
    download_ticker_data(reference_directory)

def download_edgar_data(submissions: bool = True,
                        facts: bool = True,
                        reference: bool = True):
    """
    Download Edgar data to the local storage directory
    :param submissions: Download submissions
    :param facts: Download facts
    :param reference: Download reference data
    """
    if submissions:
        download_submissions()
    if facts:
        download_facts()
    if reference:
        download_reference_data()


def download_filings(filing_date: Optional[str] = None,
                     data_directory: Optional[str] = None,
                     overwrite_existing:bool=False):
    """
    Download feed files for the specified date or date range.

    Examples

    download_filings('2025-01-03:')
    download_filings('2025-01-03', overwrite_existing=False)
    download_filings('2024-01-01:2025-01-05', overwrite_existing=True)

    Args:
        filing_date: String in format 'YYYY-MM-DD', 'YYYY-MM-DD:', ':YYYY-MM-DD',
                    or 'YYYY-MM-DD:YYYY-MM-DD'
        data_directory: Directory to save the downloaded files. Defaults to the Edgar data directory.
        overwrite_existing: If True, overwrite existing files. Default is False.
    """
    if not filing_date:
        filing_date = latest_filing_date()
        log.info('No filing date specified. Using latest filing date: %s', filing_date)

    if not data_directory:
        data_directory = get_edgar_data_directory() / 'filings'
        log.info('Using data directory: %s', data_directory)

    # Get start and end dates for filtering
    start_date_tm, end_date_tm, is_range = extract_dates(filing_date)

    # Get quarters to process
    year_and_quarters = filing_date_to_year_quarters(filing_date)

    for year, quarter in year_and_quarters:
        log.info('Downloading feed files for %d Q%d', year, quarter)
        # Get list of feed files for this quarter
        feed_files = list_filing_feed_files_for_quarter(year, quarter)

        log.info('Found %d total feed files', len(feed_files))

        # Filter files based on date range
        filtered_files = feed_files[
            feed_files['Name'].apply(
                lambda x: is_feed_file_in_date_range(x, start_date_tm, end_date_tm)
            )
        ]
        log.info('Found %d feed files in date range', len(filtered_files))

        if not filtered_files.empty:
            # Process the filtered files...
            for _, row in tqdm(filtered_files.iterrows(), desc='Downloading feed file(s)'):
                bulk_filing_file = row['File']
                bulk_file_directory = data_directory / row['Name'][:8]
                if not overwrite_existing:
                    if bulk_file_directory.exists():
                        log.info('Skipping %s. Already exists', bulk_file_directory)
                        continue
                path = asyncio.run(download_bulk_data(client=None, url=bulk_filing_file, data_directory=data_directory))
                log.info('Downloaded feed file to %s', path)
        else:
            log.info('No feed files found for %d Q%d in date range %s', year, quarter, filing_date)


def is_feed_file_in_date_range(filename: str,
                          start_date: Optional[datetime],
                          end_date: Optional[datetime]) -> bool:
    """
    Check if a feed file falls within the specified date range.
    Feed files are named like '20240102.nc.tar.gz'
    """
    # Extract date from filename
    match = re.search(r'(\d{8})\.nc\.tar\.gz', filename)
    if not match:
        return False

    date_str = match.group(1)
    file_date = datetime.strptime(date_str, '%Y%m%d')

    # For single date (not range)
    if start_date and not end_date:
        return (file_date.year == start_date.year and
                file_date.month == start_date.month and
                file_date.day == start_date.day)

    # For date range
    if start_date:
        if file_date < start_date:
            return False

    if end_date:
        if file_date > end_date:
            return False

    return True

@throttle_requests(requests_per_second=4)
def list_filing_feed_files_for_quarter(year:int, quarter:int) -> pd.DataFrame:
    assert quarter in (1, 2, 3, 4), "Quarter must be between 1 and 4"
    url = f"https://www.sec.gov/Archives/edgar/Feed/{year}/QTR{quarter}/"
    return list_filing_feed_files(url)

def get_sec_file_listing(url:str) -> pd.DataFrame:
    """
    Reads an SEC EDGAR file listing directory and returns file information as a DataFrame.

    Args:
        url (str): URL of the SEC EDGAR feed directory (e.g., 'https://www.sec.gov/Archives/edgar/Feed/2024/QTR1/')

    Returns:
        pd.DataFrame: DataFrame containing file information with columns:
            - Name: str, filename
            - Size: int, file size in bytes
            - Modified: datetime, last modification timestamp

    Raises:
        ValueError: If URL is invalid or doesn't point to SEC EDGAR
        ConnectionError: If unable to download the page
        RuntimeError: If page structure is invalid or no table found
    """
    try:
        html = download_text(url)
    except HTTPStatusError as e:
        if e.response.status_code == 403:
            log.warning(f"There are no feed files for url {url}")
            return pd.DataFrame(columns=['Name', 'File', 'Size', 'Modified'])
        elif e.response.status_code == 404:
            raise FileNotFoundError(f"Page not found: {url}")
        raise ConnectionError(f"Failed to download page: {str(e)}")

    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table')

    if not table:
        raise RuntimeError("No table found in the page")

    records = []

    # Process table rows, skip header row
    for row in table.find_all('tr')[1:]:
        cells = row.find_all('td')

        # Skip if row structure is invalid
        if len(cells) != 3:
            continue

        name = cells[0].text.strip()

        # Skip parent directory entry
        if name in ('.', '..'):
            continue
        feed_file_url = f"{url}{name}"

        # Parse file size (convert "1.2K", "3.4M" etc. to bytes)
        size_text = cells[1].text.strip()
        size = parse_file_size(size_text)

        # Parse modification date
        modified_text = cells[2].text.strip()
        try:
            modified = datetime.strptime(modified_text, '%m/%d/%Y %I:%M:%S %p')
        except ValueError:
            modified = None

        records.append((name, feed_file_url, size, modified))

    df = pd.DataFrame(records, columns=['Name', 'File', 'Size', 'Modified'])
    return df

def list_filing_feed_files(url: str) -> pd.DataFrame:
    """
    Reads the SEC EDGAR filing feed directory and returns file information as a DataFrame.

    Args:
        url (str): URL of the SEC EDGAR feed directory (e.g., 'https://www.sec.gov/Archives/edgar/Feed/2024/QTR1/')

    Returns:
        pd.DataFrame: DataFrame containing file information with columns:
            - Name: str, filename
            - Size: int, file size in bytes
            - Modified: datetime, last modification timestamp

    Raises:
        ValueError: If URL is invalid or doesn't point to SEC EDGAR
        ConnectionError: If unable to download the page
        RuntimeError: If page structure is invalid or no table found
    """
    # Validate URL
    if not url.startswith('https://www.sec.gov/Archives/edgar/Feed/'):
        raise ValueError("URL must be an SEC EDGAR feed directory")
    return get_sec_file_listing(url)


def parse_file_size(size_text: str) -> Optional[int]:
    """Convert size string to bytes (e.g., "1.2K" -> 1228)"""
    if not size_text:
        return None

    units = {'B': 1, 'K': 1024, 'M': 1024 * 1024, 'G': 1024 * 1024 * 1024}
    pattern = r'(\d+\.?\d*)\s*([BKMG])?'
    match = re.match(pattern, size_text.upper())

    if not match:
        return None

    number = float(match.group(1))
    unit = match.group(2) or 'B'

    return int(number * units[unit])


def latest_filing_date():
    """Get the latest filing date"""
    from edgar import get_filings
    return get_filings().end_date

def local_filing_path(filing_date:Union[str, date],
                      accession_number:str,
                      correction:bool=False) -> Path:
    """
    Get the local path for a filing
    If correction is True, will look for the corrected filing with extension 'corr'
    """
    ext = 'corr' if correction else 'nc'
    if isinstance(filing_date, date):
        filing_date = filing_date.strftime('%Y-%m-%d')
    filing_date = filing_date.replace('-', '')
    return get_edgar_data_directory() / 'filings' / filing_date / f"{accession_number}.{ext}"
