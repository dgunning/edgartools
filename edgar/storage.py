import asyncio
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Union

if TYPE_CHECKING:
    from edgar._filings import Filings

import pandas as pd
from bs4 import BeautifulSoup
from httpx import AsyncClient, HTTPStatusError
from tqdm.auto import tqdm

from edgar.core import filing_date_to_year_quarters, get_edgar_data_directory, log, strtobool
from edgar.dates import extract_dates
from edgar.httprequests import download_bulk_data, download_datafile, download_text
from edgar.urls import (
    build_ticker_url,
    build_company_tickers_url,
    build_mutual_fund_tickers_url,
    build_company_tickers_exchange_url
)

__all__ = ['download_edgar_data',
           'get_edgar_data_directory',
           'use_local_storage',
           'is_using_local_storage',
           'set_local_storage_path',
           'download_filings',
           'local_filing_path',
           'check_filings_exist_locally',
           '_filter_extracted_files',
           'compress_filing',
           'decompress_filing',
           'compress_all_filings',
           'is_compressed_file']

class DirectoryBrowsingNotAllowed(Exception):

    def __init__(self, url: str, message: str = "Directory browsing is not allowed for this URL."):
        super().__init__(f"{message} \nurl: {url}")
        self.url = url

def use_local_storage(path_or_enable: Union[bool, str, Path, None] = True, use_local: Optional[bool] = None):
    """
    Enable or disable local storage, optionally setting the storage path.

    This function supports multiple calling patterns for convenience:

    Args:
        path_or_enable: Can be:
            - bool: Enable (True) or disable (False) local storage
            - str/Path: Path to storage directory (enables local storage)
            - None: Use default behavior
        use_local: Optional boolean to explicitly set enable/disable state.
                  Only used when path_or_enable is a path.

    Raises:
        FileNotFoundError: If path is provided but does not exist.
        NotADirectoryError: If path exists but is not a directory.

    Examples:
        >>> # Simple enable/disable (backward compatible)
        >>> use_local_storage(True)
        >>> use_local_storage(False)
        >>> use_local_storage()  # defaults to True

        >>> # Set path and enable (new intuitive syntax)
        >>> use_local_storage("~/Documents/edgar")
        >>> use_local_storage("/tmp/edgar_data")
        >>> use_local_storage(Path.home() / "edgar")

        >>> # Set path and explicitly control enable/disable
        >>> use_local_storage("/tmp/edgar", True)   # enable
        >>> use_local_storage("/tmp/edgar", False)  # set path but disable
    """
    # Determine the actual values based on parameter types
    if isinstance(path_or_enable, bool):
        # Backward compatible: use_local_storage(True/False)
        enable = path_or_enable
        path = None
    elif isinstance(path_or_enable, (str, Path)):
        # New syntax: use_local_storage("/path/to/storage")
        path = path_or_enable
        enable = use_local if use_local is not None else True
    elif path_or_enable is None:
        # use_local_storage() - default behavior
        enable = True
        path = None
    else:
        raise TypeError(f"First parameter must be bool, str, Path, or None, got {type(path_or_enable)}")

    # If a path is provided and we're enabling local storage, set the path first
    if path is not None and enable:
        set_local_storage_path(path)

    # Set the local storage flag
    os.environ['EDGAR_USE_LOCAL_DATA'] = "1" if enable else "0"


def is_using_local_storage() -> bool:
    """
    Returns True if using local storage
    """
    return strtobool(os.getenv('EDGAR_USE_LOCAL_DATA', "False"))


def set_local_storage_path(path: Union[str, Path]) -> None:
    """
    Set the local storage path for Edgar data.

    This function provides a programmatic way to set the local storage directory,
    equivalent to setting the EDGAR_LOCAL_DATA_DIR environment variable.

    Args:
        path: Path to the directory where Edgar data should be stored.
              Can be a string or Path object. The directory must already exist.

    Raises:
        FileNotFoundError: If the specified directory does not exist.
        NotADirectoryError: If the path exists but is not a directory.

    Example:
        >>> # First create the directory
        >>> os.makedirs("/tmp/edgar_data", exist_ok=True)
        >>> set_local_storage_path("/tmp/edgar_data")
        >>> 
        >>> # Or use an existing directory
        >>> set_local_storage_path(Path.home() / "Documents")
    """
    from pathlib import Path

    # Convert to Path object and resolve to absolute path
    storage_path = Path(path).expanduser().resolve()

    # Validate that the directory exists
    if not storage_path.exists():
        raise FileNotFoundError(f"Directory does not exist: {storage_path}")

    # Validate that it's actually a directory
    if not storage_path.is_dir():
        raise NotADirectoryError(f"Path exists but is not a directory: {storage_path}")

    # Set the environment variable
    os.environ['EDGAR_LOCAL_DATA_DIR'] = str(storage_path)


async def download_facts_async(client: Optional[AsyncClient]) -> Path:
    """
    Download company facts
    """
    from edgar.config import SEC_ARCHIVE_URL
    log.info(f"Downloading Company facts to {get_edgar_data_directory()}/companyfacts")

    return await download_bulk_data(client=client, url=f"{SEC_ARCHIVE_URL}/daily-index/xbrl/companyfacts.zip")

def download_facts() -> Path:
    """
    Download company facts
    """

    return asyncio.run(download_facts_async(client = None))

async def download_submissions_async(client: Optional[AsyncClient]) -> Path:
    """
    Download company submissions
    """
    from edgar.config import SEC_ARCHIVE_URL
    log.info(f"Downloading Company submissions to {get_edgar_data_directory()}/submissions")

    return await download_bulk_data(client=client, url=f"{SEC_ARCHIVE_URL}/daily-index/bulkdata/submissions.zip")


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
    download_datafile(build_ticker_url(), reference_data_directory)
    download_datafile(build_company_tickers_url(), reference_data_directory)
    download_datafile(build_mutual_fund_tickers_url(), reference_data_directory)
    download_datafile(build_company_tickers_exchange_url(), reference_data_directory)


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
                     overwrite_existing:bool=False,
                     filings: Optional['Filings'] = None,
                     compress: bool = True,
                     compression_level: int = 6):
    """
    Download feed files for the specified date or date range, or for specific filings.
    Optionally compresses the extracted files to save disk space.

    Examples

    download_filings('2025-01-03:')
    download_filings('2025-01-03', overwrite_existing=False)
    download_filings('2024-01-01:2025-01-05', overwrite_existing=True)
    download_filings(filings=my_filings_object)
    download_filings('2025-01-03', compress=True, compression_level=9)  # Maximum compression

    Args:
        filing_date: String in format 'YYYY-MM-DD', 'YYYY-MM-DD:', ':YYYY-MM-DD',
                    or 'YYYY-MM-DD:YYYY-MM-DD'. If both filing_date and filings are provided,
                    filing_date takes precedence for determining which feed files to download.
        data_directory: Directory to save the downloaded files. Defaults to the Edgar data directory.
        overwrite_existing: If True, overwrite existing files. Default is False.
        filings: Optional Filings object. If provided, will download only filings with matching accession numbers.
        compress: Whether to compress the extracted files to save disk space. Default is True.
        compression_level: Compression level for gzip (1-9, with 9 being highest compression). Default is 6.
    """
    if not data_directory:
        data_directory = get_edgar_data_directory() / 'filings'
        log.info('Using data directory: %s', data_directory)

    # If filings object is provided, extract accession numbers
    accession_numbers = None
    if filings is not None:
        log.info('Using provided Filings object with %d filings', len(filings))
        accession_numbers = filings.data['accession_number'].to_pylist()

        # If both filing_date and filings are provided, let the user know which takes precedence
        if filing_date:
            log.info('Both filing_date and filings parameters provided. Using filing_date %s for determining feed files to download.', filing_date)
        # Use the date range from the filings object if no filing_date specified
        else:
            start_date, end_date = filings.date_range
            filing_date = f"{start_date}:{end_date}"
            log.info('Using date range from filings: %s', filing_date)

    # Use default date if not specified
    if not filing_date:
        filing_date = latest_filing_date()
        log.info('No filing date specified. Using latest filing date: %s', filing_date)

    # Get start and end dates for filtering
    start_date_tm, end_date_tm, is_range = extract_dates(filing_date)

    # Get quarters to process
    year_and_quarters = filing_date_to_year_quarters(filing_date)

    # Track statistics
    total_feed_files_downloaded = 0
    total_filings_kept = 0

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
                filing_date_str = row['Name'][:8]  # Extract YYYYMMDD from filename

                if not overwrite_existing:
                    if bulk_file_directory.exists():
                        log.warning('Skipping %s. Already exists', bulk_file_directory)
                        continue

                # Optimization: If we have specific accession numbers, check if all the ones 
                # for this specific filing date already exist locally
                if accession_numbers and filings is not None:
                    # Convert YYYYMMDD to YYYY-MM-DD format 
                    formatted_date = f"{filing_date_str[:4]}-{filing_date_str[4:6]}-{filing_date_str[6:8]}"

                    # Filter accession numbers to only those for this specific filing date
                    date_filtered_filings = filings.filter(filing_date=formatted_date)
                    if not date_filtered_filings.empty:
                        date_accession_numbers = date_filtered_filings.data['accession_number'].to_pylist()
                        if check_filings_exist_locally(formatted_date, date_accession_numbers):
                            log.warning('Not downloading for %s. All %d filings for this date already exist in local %s',
                                   formatted_date, len(date_accession_numbers), bulk_file_directory)
                            continue

                # Track existing files before extraction to preserve them during filtering
                existing_files = set()
                if accession_numbers and bulk_file_directory.exists():
                    existing_files = {str(f) for f in bulk_file_directory.glob('*.nc')}

                path = asyncio.run(download_bulk_data(client=None, url=bulk_filing_file, data_directory=data_directory))
                log.info('Downloaded feed file to %s', path)
                total_feed_files_downloaded += 1

                # If we have specific accession numbers, filter the extracted files
                if accession_numbers and path.exists():
                    _filter_extracted_files._existing_files = existing_files

                    log.info('Filtering extracted files to keep only specified accession numbers')
                    filings_kept = _filter_extracted_files(path, accession_numbers, compress=compress, compression_level=compression_level)
                    total_filings_kept += filings_kept

                    # Clean up the tracking
                    if hasattr(_filter_extracted_files, '_existing_files'):
                        delattr(_filter_extracted_files, '_existing_files')
                # If we don't have specific accession numbers but compression is enabled, compress all files
                elif compress and path.exists():
                    log.info('Compressing all extracted files')
                    for file_path in path.glob('*.nc'):
                        if not is_compressed_file(file_path):
                            try:
                                compress_filing(file_path, compression_level=compression_level)
                            except Exception as e:
                                log.warning(f"Failed to compress {file_path}: {e}")
        else:
            log.info('No feed files found for %d Q%d in date range %s', year, quarter, filing_date)

    # Log summary statistics
    log.info('Download complete. Downloaded %d feed files.', total_feed_files_downloaded)
    if accession_numbers:
        log.info('Kept %d filings out of %d requested.', total_filings_kept, len(accession_numbers))


def _filter_extracted_files(directory_path: Path, accession_numbers: List[str], compress: bool = True, compression_level: int = 6) -> int:
    """
    Filter files in the extracted directory to keep only those matching the specified accession numbers.
    Files from the current extraction that don't match are removed to save disk space.
    Files that existed before this extraction (from previous downloads) are preserved.

    Args:
        directory_path: Path to the directory containing extracted files
        accession_numbers: List of accession numbers to keep
        compress: Whether to compress the kept files (default: True)
        compression_level: Compression level for gzip (1-9, with 9 being highest compression)

    Returns:
        int: Number of filings kept
    """
    if not directory_path.is_dir():
        return 0

    # Convert accession numbers to the format used in filenames (removing dashes)
    normalized_accession_numbers = [an.replace('-', '') for an in accession_numbers]

    # Keep track of which filings were found
    filings_kept = 0

    # Get list of files that existed before this extraction
    # We'll preserve these even if they don't match our filter
    existing_files = getattr(_filter_extracted_files, '_existing_files', set())

    # Find all .nc files in the directory
    for file_path in directory_path.glob('*.nc'):
        # Extract accession number from filename
        file_accession = file_path.stem
        undashed_accession = file_accession.replace('-', '')

        # Check if this file matches our filter
        matches_filter = (undashed_accession in normalized_accession_numbers or 
                         file_accession in accession_numbers)

        # Check if this file existed before this extraction
        was_preexisting = str(file_path) in existing_files

        if matches_filter:
            filings_kept += 1
            # Compress the file if requested
            if compress and not is_compressed_file(file_path):
                try:
                    compress_filing(file_path, compression_level=compression_level)
                    log.debug(f"Compressed {file_path}")
                except Exception as e:
                    log.warning(f"Failed to compress {file_path}: {e}")
        elif not was_preexisting:
            # Remove files from current extraction that don't match filter
            # But preserve files that existed before this extraction
            try:
                file_path.unlink()
                log.debug(f"Removed non-matching file from current extraction: {file_path}")
            except Exception as e:
                log.warning(f"Failed to remove {file_path}: {e}")

    return filings_kept


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

def list_filing_feed_files_for_quarter(year:int, quarter:int) -> pd.DataFrame:
    assert quarter in (1, 2, 3, 4), "Quarter must be between 1 and 4"
    from edgar.urls import build_feed_url
    url = build_feed_url(year, quarter)
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
            raise FileNotFoundError(f"Page not found: {url}") from None
        raise ConnectionError(f"Failed to download page: {str(e)}") from e

    if "Directory Browsing Not Allowed" in html:
        log.warning(f"Directory browsing is not allowed for {url}")
        raise DirectoryBrowsingNotAllowed("""
        Directory browsing is not allowed for here.
        This is unexpected and the SEC likely has changed their policy for viewing the bulk filing files.
        """)

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
    from edgar.config import SEC_ARCHIVE_URL
    expected_prefix = f"{SEC_ARCHIVE_URL}/Feed/"
    if not url.startswith(expected_prefix):
        raise ValueError(f"URL must be an SEC EDGAR feed directory starting with {expected_prefix}")
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


def is_compressed_file(file_path: Path) -> bool:
    """
    Check if a file is gzip-compressed by examining its extension.

    Args:
        file_path: Path to the file

    Returns:
        bool: True if the file has a .gz extension, False otherwise
    """
    return str(file_path).endswith('.gz')


def compress_filing(file_path: Path, compression_level: int = 6, delete_original: bool = True) -> Path:
    """
    Compress a filing file using gzip and optionally delete the original.

    Args:
        file_path: Path to the file to compress
        compression_level: Compression level (1-9, with 9 being highest compression)
        delete_original: Whether to delete the original file after compression

    Returns:
        Path to the compressed file

    Raises:
        FileNotFoundError: If the file does not exist
        ValueError: If the file is already compressed
    """
    import gzip
    import shutil

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if is_compressed_file(file_path):
        raise ValueError(f"File is already compressed: {file_path}")

    compressed_path = Path(f"{file_path}.gz")

    # Compress the file
    with file_path.open('rb') as f_in:
        with gzip.open(compressed_path, 'wb', compresslevel=compression_level) as f_out:
            shutil.copyfileobj(f_in, f_out)

    # Delete the original file if requested
    if delete_original:
        file_path.unlink()

    return compressed_path


def decompress_filing(file_path: Path, output_path: Optional[Path] = None, delete_original: bool = False) -> Path:
    """
    Decompress a gzip-compressed filing file.

    Args:
        file_path: Path to the compressed file
        output_path: Path to save the decompressed file (if None, use the original path without .gz)
        delete_original: Whether to delete the original compressed file

    Returns:
        Path to the decompressed file

    Raises:
        FileNotFoundError: If the file does not exist
        ValueError: If the file is not compressed
        gzip.BadGzipFile: If the file is not a valid gzip file
    """
    import gzip
    import shutil

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not is_compressed_file(file_path):
        raise ValueError(f"File is not compressed: {file_path}")

    # Determine output path if not provided
    if output_path is None:
        # Remove .gz extension
        output_path = Path(str(file_path)[:-3])

    # Decompress the file
    with gzip.open(file_path, 'rb') as f_in:
        with output_path.open('wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

    # Delete the original compressed file if requested
    if delete_original:
        file_path.unlink()

    return output_path


def compress_all_filings(data_directory: Optional[Path] = None, compression_level: int = 6) -> int:
    """
    Compress all uncompressed filing files in the data directory.

    Args:
        data_directory: Path to the data directory (defaults to the Edgar data directory)
        compression_level: Compression level (1-9, with 9 being highest compression)

    Returns:
        Number of files compressed
    """
    if data_directory is None:
        data_directory = get_edgar_data_directory() / 'filings'

    # Find all .nc files (not already compressed)
    files_compressed = 0
    for file_path in tqdm(list(data_directory.glob('**/*.nc')), desc="Compressing files"):
        if not is_compressed_file(file_path) and file_path.is_file():
            try:
                compress_filing(file_path, compression_level=compression_level)
                files_compressed += 1
            except Exception as e:
                log.warning(f"Failed to compress {file_path}: {e}")

    return files_compressed

def check_filings_exist_locally(filing_date: Union[str, date], accession_numbers: List[str]) -> bool:
    """
    Check if all specified accession numbers already exist locally for a given filing date.

    Args:
        filing_date: The filing date (YYYY-MM-DD format)
        accession_numbers: List of accession numbers to check

    Returns:
        bool: True if all filings exist locally, False otherwise
    """
    if not accession_numbers:
        return False

    for accession_number in accession_numbers:
        # Check both compressed and uncompressed versions
        filing_path = local_filing_path(filing_date, accession_number)
        if not filing_path.exists():
            return False

    return True


def local_filing_path(filing_date:Union[str, date],
                      accession_number:str,
                      correction:bool=False) -> Path:
    """
    Get the local path for a filing
    If correction is True, will look for the corrected filing with extension 'corr'

    Returns the compressed version (.gz) if it exists, otherwise returns the uncompressed path.
    """
    ext = 'corr' if correction else 'nc'
    if isinstance(filing_date, date):
        filing_date = filing_date.strftime('%Y-%m-%d')
    filing_date = filing_date.replace('-', '')

    # Base path without compression extension
    base_path = get_edgar_data_directory() / 'filings' / filing_date / f"{accession_number}.{ext}"

    # Check for compressed version first
    compressed_path = Path(f"{base_path}.gz")
    if compressed_path.exists():
        return compressed_path

    # Fall back to uncompressed version
    return base_path
