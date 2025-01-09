import asyncio
import os
from functools import lru_cache
from pathlib import Path

from edgar.core import log, get_edgar_data_directory
from edgar.httprequests import download_bulk_data, download_datafile
from edgar.reference.tickers import (ticker_txt_url,
                                     company_tickers_json_url,
                                     mutual_fund_tickers_url,
                                     company_tickers_exchange_url)

__all__ = ['download_edgar_data', 'get_edgar_data_directory', 'use_local_storage', 'is_using_local_storage']

async def download_facts_async() -> Path:
    """
    Download company facts
    """
    log.info(f"Downloading Company facts to {get_edgar_data_directory()}/companyfacts")
    return await download_bulk_data("https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip")


def download_facts() -> Path:
    """
    Download company facts
    """
    return asyncio.run(download_facts_async())


async def download_submissions_async() -> Path:
    """
    Download company submissions
    """
    log.info(f"Downloading Company submissions to {get_edgar_data_directory()}/submissions")
    return await download_bulk_data("https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip")


def download_submissions() -> Path:
    """
    Download company facts
    """
    return asyncio.run(download_submissions_async())

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


def use_local_storage(use_local: bool = True):
    """
    Will use local data if set to True
    """
    os.environ['EDGAR_USE_LOCAL_DATA'] = "1" if use_local else "0"


def is_using_local_storage() -> bool:
    """
    Returns True if using local storage
    """
    return os.getenv('EDGAR_USE_LOCAL_DATA', "0") == "1"



