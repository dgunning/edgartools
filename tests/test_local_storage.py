from edgar import *
from pathlib import Path
from datetime import datetime
import shutil
from edgar import *
from edgar.storage import list_filing_feed_files, list_filing_feed_files_for_quarter, is_feed_file_in_date_range
from edgar.storage import local_filing_path


def test_get_html_from_local_storage(monkeypatch):
    filing = Filing(form='10-Q',
                    filing_date='2025-01-08',
                    company='ANGIODYNAMICS INC',
                    cik=1275187,
                    accession_no='0001275187-25-000005')
    monkeypatch.setenv('EDGAR_LOCAL_DATA_DIR', 'data/localstorage')
    monkeypatch.setenv('EDGAR_USE_LOCAL_DATA', "1")
    html = filing.html()
    assert html

    header = filing.header
    assert header.accession_number == '0001275187-25-000005'
    assert header

def test_list_bulk_filing_files():
    data = list_filing_feed_files("https://www.sec.gov/Archives/edgar/Feed/2024/QTR1/")
    assert len(data) == 62
    assert data.iloc[0].File == 'https://www.sec.gov/Archives/edgar/Feed/2024/QTR1/20240102.nc.tar.gz'
    assert data.iloc[0].Name == '20240102.nc.tar.gz'

    assert data.iloc[1].File == 'https://www.sec.gov/Archives/edgar/Feed/2024/QTR1/20240103.nc.tar.gz'
    assert data.iloc[1].Name == '20240103.nc.tar.gz'

    assert data.iloc[2].File == 'https://www.sec.gov/Archives/edgar/Feed/2024/QTR1/20240104.nc.tar.gz'
    assert data.iloc[2].Name == '20240104.nc.tar.gz'

def test_list_feed_files_for_quarter():
    data = list_filing_feed_files_for_quarter(2024, 1)
    assert data.iloc[0].File == 'https://www.sec.gov/Archives/edgar/Feed/2024/QTR1/20240102.nc.tar.gz'
    assert len(data) == 62

def test_list_bulk_filing_not_found():
    files = list_filing_feed_files("https://www.sec.gov/Archives/edgar/Feed/2024/QTR5/")
    assert files.empty

def test_is_feed_file_in_date_range():
    def parse_date(d):
        return datetime.strptime(d, '%Y-%m-%d')
    assert is_feed_file_in_date_range('20240102.nc.tar.gz', parse_date('2024-01-02'), None)
    assert is_feed_file_in_date_range('20240102.nc.tar.gz', None, parse_date('2024-01-02'))
    assert is_feed_file_in_date_range('20240103.nc.tar.gz', parse_date('2024-01-02'), parse_date('2024-01-05'))
    assert not is_feed_file_in_date_range('20240203.nc.tar.gz', parse_date('2024-01-02'), parse_date('2024-01-05'))
    assert not is_feed_file_in_date_range('20240203.nc.tar.gz', None, parse_date('2024-01-05'))
