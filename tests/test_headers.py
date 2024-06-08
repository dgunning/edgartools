from pathlib import Path

from rich import print

from edgar.headers import *
from edgar import *


def test_load_filing_header_from_text_for_8K():
    header_text = Path('data/headers/23AndMe.index-headers.html').read_text()
    filing_header: IndexHeader = IndexHeader.load(header_text)

    assert filing_header.form == '8-K'
    assert filing_header.filer.company_data.conformed_name == '23andMe Holding Co.'
    assert filing_header.filer.company_data.cik == '0001804591'
    assert filing_header.filer.company_data.assigned_sic == '2834'
    assert filing_header.filer.company_data.irs_number == '871240344'

    assert filing_header.filing_date == '2024-06-03'

    print()
    print(filing_header)


def test_load_filing_header_from_text():
    header_text = Path('data/headers/0001971857-23-000246-index-headers.html').read_text()
    filing_header: IndexHeader = IndexHeader.load(header_text)

    print()
    print(filing_header)


def test_load_filing_directory():
    basedir = 'https://www.sec.gov/Archives/edgar/data/1648960/000121390024004875/'
    filing_dir: FilingDirectory = FilingDirectory.load(basedir)
    assert filing_dir.name == '/Archives/edgar/data/1648960/000121390024004875'
    assert filing_dir.parent_dir == '/Archives/edgar/data/1648960'
    print()
    print(filing_dir)


def test_filing_directory_index_headers():
    basedir = 'https://www.sec.gov/Archives/edgar/data/1648960/000121390024004875/'
    filing_dir: FilingDirectory = FilingDirectory.load(basedir)
    index_headers = filing_dir.index_headers
    print(index_headers)


def test_get_inndex_header_from_filing():
    #filing = Filing(form='13F-HR', filing_date='2024-06-05', company='Objective Capital Management, LLC', cik=1924152, accession_no='0001924152-24-000002')
    filing = Filing(form='1-U', filing_date='2024-06-06', company='Masterworks Vault 5, LLC', cik=1999710, accession_no='0001493152-24-022961')
    index_headers = filing.index_headers
    print()
    print(index_headers)
