#!/usr/bin/env python3
"""
Script to download and prepare XBRL2 test fixtures.
Run this script to update or regenerate the test fixtures.

Usage:
    python tests/fixtures/generate_xbrl2_fixtures.py
"""

import os
import shutil
from pathlib import Path
import logging
from typing import List, Tuple, Optional
from edgar import get_filings, Filings

from edgar import Company, Filing
from edgar.xbrl2 import XBRL
from edgar.xbrl import XBRLAttachments

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Base directory for fixtures
FIXTURE_DIR = Path("tests/fixtures/xbrl2")

# Companies to include - (Ticker, CIK, Form types, Years)
COMPANIES = [
    # Large cap technology
    ("AAPL", "320193", ["10-K", "10-Q"], [2023, 2015, 2010]),
    ("MSFT", "789019", ["10-K", "10-Q"], [2024, 2015]),
    ("NVDA", "1045810", ["10-K"], [2024]),
    
    # Financial services
    ("JPM", "19617", ["10-K"], [2024, 2013]),
    ("GS", "886982", ["10-K"], [2024]),
    
    # Consumer products
    ("KO", "21344", ["10-K"], [2024, 2012]),
    ("PG", "80424", ["10-K"], [2023]),
    
    # Healthcare
    ("JNJ", "200406", ["10-K"], [2023]),
    
    # Industrial
    ("BA", "12927", ["10-K"], [2024]),
    
    # Energy
    ("XOM", "34088", ["10-K"], [2023]),
    
    # Mid-cap
    ("HUBS", "1404655", ["10-K"], [2023]),
    
    # Companies with interesting XBRL features
    ("NFLX", "1065280", ["10-K", "10-Q"], [2024, 2010]),  # Historical comparison
]

# Special case companies for specific tests
SPECIAL_CASES = [
    # Companies with complex segment reporting
    ("AMZN", "1018724", ["10-K"], [2023], "segments"),
    
    # Companies with extensive dimensional data
    ("KO", "21344", ["10-K"], [2023], "dimensional"),
    
    # Companies with custom taxonomies
    ("BA", "12927", ["10-K"], [2023], "custom_taxonomy"),
]


def download_filing_xbrl(ticker: str,
                         form: str,
                         year: int,
                         filings:Filings,
                         special_case: Optional[str] = None) -> Optional[Path]:
    """
    Download a specific filing's XBRL data.
    
    Args:
        ticker: Company ticker symbol
        cik: Company CIK number
        form: Filing form type (10-K, 10-Q, etc.)
        year: Filing year
        filings: Filings object
        special_case: Optional category for special test cases
        
    Returns:
        Path to the created fixture directory or None if download fails
    """
    try:
        logger.info(f"Downloading {ticker} {form} {year}...")
        
        # Get filings for the specified year and form
        company_filings = filings.filter(form=form, filing_date=f"{year}-01-01:{year}-12-31", ticker=ticker)
        if not company_filings:
            logger.warning(f"No {form} filings found for {ticker} in {year}")
            return None
        
        # Get the most recent filing for that year
        filing = company_filings[0]
        logger.info(f"Found filing: {filing.accession_no} dated {filing.filing_date}")
        
        # Create XBRL object from filing
        xbrl_attachments = XBRLAttachments(filing.attachments)
        
        # Determine target directory
        if special_case:
            target_dir = FIXTURE_DIR / "special_cases" / special_case / ticker.lower()
        else:
            form_dir = form.lower().replace('-', '')
            target_dir = FIXTURE_DIR / ticker.lower() / f"{form_dir}_{year}"
        
        # Create the directory if it doesn't exist
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Save XBRL files
        save_xbrl_to_directory(xbrl_attachments, filing, ticker, target_dir)
        
        # Write filing metadata for reference
        with open(target_dir / "filing_metadata.txt", "w") as f:
            f.write(f"Company: {filing.company}\n")
            f.write(f"CIK: {filing.cik}\n")
            f.write(f"Form: {filing.form}\n")
            f.write(f"Filing Date: {filing.filing_date}\n")
            f.write(f"Accession No: {filing.accession_no}\n")
            f.write(f"URL: {filing.url}\n")
        
        logger.info(f"Successfully downloaded {ticker} {form} {year} to {target_dir}")
        return target_dir
    
    except Exception as e:
        logger.error(f"Error downloading {ticker} {form} {year}: {str(e)}")
        return None


def save_xbrl_to_directory(xbrl: XBRLAttachments, filing: Filing, ticker:str, target_dir: Path) -> None:
    """
    Save XBRL files to the target directory.
    
    This function extracts and saves all XBRL-related files from the filing attachments
    to the specified target directory for testing purposes.
    
    Args:
        xbrl: XBRLAttachments object containing the filing XBRL documents
        filing: Filing object with metadata
        target_dir: Directory to save files to
    """
    logger.info(f"Saving XBRL files to {target_dir}")
    
    # Ensure target directory exists
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Counter for saved files
    saved_files = 0
    
    # Get all XBRL documents
    if not hasattr(xbrl, '_documents') or not xbrl._documents:
        logger.warning(f"No XBRL documents found for filing {filing.accession_no}")
        return
    
    # Extract company and date information for better filenames
    company_short = ticker.lower()
    filing_date = filing.filing_date.strftime("%Y%m%d")
    
    # Save each XBRL-related document
    for doc_id, attachment in xbrl._documents.items():
        if not attachment.content:
            logger.warning(f"Empty content for document {doc_id}")
            continue
            
        # Determine appropriate filename based on document type
        filename = attachment.document
        
        # If filename doesn't have extension, try to determine from content
        if '.' not in filename:
            if attachment.content.startswith('<?xml'):
                ext = '.xml'
            elif attachment.content.startswith('<xsd:schema') or attachment.content.startswith('<xs:schema'):
                ext = '.xsd'
            else:
                ext = '.txt'
            filename = f"{filename}{ext}"
        
        # Standardize filenames for common XBRL files
        if filename.endswith('.xsd'):
            filename = f"{company_short}-{filing_date}.xsd"
        elif '_pre.' in filename:
            filename = f"{company_short}-{filing_date}_pre.xml"
        elif '_def.' in filename:
            filename = f"{company_short}-{filing_date}_def.xml"
        elif '_cal.' in filename:
            filename = f"{company_short}-{filing_date}_cal.xml"
        elif '_lab.' in filename:
            filename = f"{company_short}-{filing_date}_lab.xml"
        elif '_htm.' in filename:
            filename = f"{company_short}-{filing_date}_htm.xml"
        
        # Save the file
        file_path = target_dir / filename
        try:
            file_path.write_text(attachment.content)
            saved_files += 1
            logger.debug(f"Saved {filename}")
        except Exception as e:
            logger.error(f"Error saving {filename}: {str(e)}")
    
    # Write a summary metadata JSON file
    try:
        import json
        metadata = {
            "company": filing.company,
            "cik": filing.cik,
            "ticker": ticker,
            "form": filing.form,
            "filing_date": filing.filing_date.strftime("%Y-%m-%d"),
            "accession_no": filing.accession_no,
            "files_saved": saved_files
        }
        
        with open(target_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving metadata: {str(e)}")
    
    logger.info(f"Saved {saved_files} XBRL files to {target_dir}")


def copy_existing_fixtures() -> None:
    """
    Copy existing fixtures from data/xbrl/datafiles to the test fixtures directory.
    This reuses existing test data that's already in the repository.
    """
    source_dir = Path("data/xbrl/datafiles")
    if not source_dir.exists():
        logger.warning(f"Source directory {source_dir} does not exist")
        return
    
    # Companies to copy
    companies = ["aapl", "msft", "nflx", "tsla", "unp"]
    
    for company in companies:
        company_dir = source_dir / company
        if not company_dir.exists():
            continue
        
        # Determine target directory
        target_dir = FIXTURE_DIR / company
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy files
        for file in company_dir.glob("**/*"):
            if file.is_file():
                # Determine relative path from company directory
                rel_path = file.relative_to(company_dir)
                # Create target directory if needed
                (target_dir / rel_path.parent).mkdir(parents=True, exist_ok=True)
                # Copy file
                shutil.copy(file, target_dir / rel_path)
        
        logger.info(f"Copied existing fixtures for {company}")


def main() -> None:
    """Download all test fixtures."""
    # Create the main fixture directory if it doesn't exist
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create a directory for special cases
    (FIXTURE_DIR / "special_cases").mkdir(exist_ok=True)
    
    # Copy existing fixtures
    copy_existing_fixtures()

    # Get filings for all the years
    # Get all the years
    all_years = []
    for ticker, cik, forms, years in COMPANIES:
        all_years.extend(years)
    unique_years = list(set(all_years))
    #unique_years = [2023]
    filings = get_filings(unique_years)
    
    # Download standard company fixtures
    for ticker, cik, forms, years in COMPANIES:
        for form in forms:
            for year in years:
                download_filing_xbrl(ticker, form, year, filings)
    
    # Download special case fixtures
    for ticker, cik, forms, years, case_type in SPECIAL_CASES:
        for form in forms:
            for year in years:
                download_filing_xbrl(ticker, form, year, filings, case_type)
    
    logger.info("Fixture generation complete")


if __name__ == "__main__":
    main()