
from datetime import datetime
from edgar import *
from edgar.storage import list_filing_feed_files, list_filing_feed_files_for_quarter, is_feed_file_in_date_range


def test_local_storage_env_variable(monkeypatch):
    monkeypatch.setenv("EDGAR_USE_LOCAL_DATA", "1")
    assert is_using_local_storage()

    monkeypatch.setenv("EDGAR_USE_LOCAL_DATA", "0")
    assert not is_using_local_storage()

    monkeypatch.setenv("EDGAR_USE_LOCAL_DATA", "True")
    assert is_using_local_storage()

    monkeypatch.setenv("EDGAR_USE_LOCAL_DATA", "Yes")
    assert is_using_local_storage()

    monkeypatch.setenv("EDGAR_USE_LOCAL_DATA", "No")
    assert not is_using_local_storage()

    monkeypatch.setenv("EDGAR_USE_LOCAL_DATA", "1")
    assert is_using_local_storage()

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
    print(data.File.tolist())
    assert data.iloc[0].File == 'https://www.sec.gov/Archives/edgar/Feed/2024/QTR1/20240102.nc.tar.gz'
    assert len(data) == 62

    data = list_filing_feed_files_for_quarter(2025, 2)
    print(data.File.tolist())

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


def test_local_storage_and_related_filings(monkeypatch):

    filing = Filing(form='13F-HR', filing_date='2025-01-24', company='ABNER HERRMAN & BROCK LLC', cik=1038661,
           accession_no='0001667731-25-000122')
    monkeypatch.setenv("EDGAR_USE_LOCAL_DATA", "1")
    related_filings = filing.related_filings()
    assert len(related_filings) > 10
