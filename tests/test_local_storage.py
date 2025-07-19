
from datetime import datetime

import pytest
from edgar.httprequests import download_file, download_text
from edgar import *
from edgar.storage import list_filing_feed_files, list_filing_feed_files_for_quarter, is_feed_file_in_date_range, \
    DirectoryBrowsingNotAllowed


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


def test_list_bulk_filing_not_found():
    files = list_filing_feed_files("https://www.sec.gov/Archives/edgar/Feed/2024/QTR5/")
    assert files.empty

@pytest.mark.skipif(True, reason="The directory browsing issue is fixed")
def test_list_bulk_filing_no_listing_allowed():
    # The SEC does not allow listing of files in this directory since 2025
    with pytest.raises(DirectoryBrowsingNotAllowed):
        files = list_filing_feed_files("https://www.sec.gov/Archives/edgar/Feed/2025/QTR2/")

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


def test_set_local_storage_path(tmp_path, monkeypatch):
    """Test the set_local_storage_path function."""
    from edgar import set_local_storage_path
    from edgar.core import get_edgar_data_directory
    from pathlib import Path
    
    # Test with valid directory
    test_dir = tmp_path / "edgar_test"
    test_dir.mkdir()
    
    set_local_storage_path(test_dir)
    assert get_edgar_data_directory() == test_dir
    
    # Test with string path
    set_local_storage_path(str(test_dir))
    assert get_edgar_data_directory() == test_dir
    
    # Test with Path object
    set_local_storage_path(Path(test_dir))
    assert get_edgar_data_directory() == test_dir
    
    # Test with non-existent directory
    nonexistent = tmp_path / "nonexistent"
    with pytest.raises(FileNotFoundError):
        set_local_storage_path(nonexistent)
    
    # Test with file instead of directory
    test_file = tmp_path / "testfile.txt"
    test_file.write_text("test")
    with pytest.raises(NotADirectoryError):
        set_local_storage_path(test_file)


def test_use_local_storage_backward_compatibility(monkeypatch):
    """Test that use_local_storage maintains backward compatibility."""
    from edgar import use_local_storage, is_using_local_storage
    
    # Test original True/False behavior
    use_local_storage(True)
    assert is_using_local_storage()
    
    use_local_storage(False)
    assert not is_using_local_storage()
    
    # Test default behavior
    use_local_storage()
    assert is_using_local_storage()


def test_use_local_storage_intuitive_syntax(tmp_path, monkeypatch):
    """Test the new intuitive path-first syntax."""
    from edgar import use_local_storage, is_using_local_storage
    from edgar.core import get_edgar_data_directory
    from pathlib import Path
    
    # Create test directory
    test_dir = tmp_path / "edgar_intuitive"
    test_dir.mkdir()
    
    # Test string path
    use_local_storage(str(test_dir))
    assert is_using_local_storage()
    assert get_edgar_data_directory() == test_dir
    
    # Test Path object
    test_dir2 = tmp_path / "edgar_path_obj"
    test_dir2.mkdir()
    use_local_storage(test_dir2)
    assert is_using_local_storage()
    assert get_edgar_data_directory() == test_dir2
    
    # Test that invalid path raises error
    nonexistent = tmp_path / "nonexistent"
    with pytest.raises(FileNotFoundError):
        use_local_storage(str(nonexistent))


def test_use_local_storage_advanced_syntax(tmp_path, monkeypatch):
    """Test the advanced path + explicit enable/disable syntax."""
    from edgar import use_local_storage, is_using_local_storage
    from edgar.core import get_edgar_data_directory
    
    # Create test directory
    test_dir = tmp_path / "edgar_advanced"
    test_dir.mkdir()
    
    # Test path with explicit enable
    use_local_storage(str(test_dir), True)
    assert is_using_local_storage()
    assert get_edgar_data_directory() == test_dir
    
    # Test path with explicit disable
    use_local_storage(str(test_dir), False)
    assert not is_using_local_storage()
    # Path should still be set even when disabled
    assert get_edgar_data_directory() == test_dir


def test_use_local_storage_error_handling(tmp_path):
    """Test error handling in use_local_storage."""
    from edgar import use_local_storage
    
    # Test invalid type
    with pytest.raises(TypeError, match="First parameter must be bool, str, Path, or None"):
        use_local_storage(123)
    
    with pytest.raises(TypeError, match="First parameter must be bool, str, Path, or None"):
        use_local_storage(["/some/path"])
    
    # Test invalid path
    with pytest.raises(FileNotFoundError):
        use_local_storage("/nonexistent/path")


def test_use_local_storage_tilde_expansion(monkeypatch):
    """Test that tilde expansion works in use_local_storage."""
    from edgar import use_local_storage, is_using_local_storage
    from edgar.core import get_edgar_data_directory
    from pathlib import Path
    import os
    
    # Test tilde expansion (home directory should exist)
    home_dir = Path.home()
    use_local_storage("~")
    assert is_using_local_storage()
    assert get_edgar_data_directory() == home_dir


def test_local_storage_integration(tmp_path, monkeypatch):
    """Test integration of set_local_storage_path and use_local_storage."""
    from edgar import set_local_storage_path, use_local_storage, is_using_local_storage
    from edgar.core import get_edgar_data_directory
    
    # Create test directories
    dir1 = tmp_path / "edgar_int1"
    dir2 = tmp_path / "edgar_int2"
    dir1.mkdir()
    dir2.mkdir()
    
    # Test sequence: set path, then enable
    set_local_storage_path(dir1)
    use_local_storage(True)
    assert is_using_local_storage()
    assert get_edgar_data_directory() == dir1
    
    # Test sequence: disable, set new path, enable with new syntax
    use_local_storage(False)
    assert not is_using_local_storage()
    
    use_local_storage(str(dir2))
    assert is_using_local_storage()
    assert get_edgar_data_directory() == dir2


def test_local_storage_environment_persistence(tmp_path, monkeypatch):
    """Test that local storage settings persist in environment variables."""
    from edgar import use_local_storage, set_local_storage_path
    import os
    
    # Create test directory
    test_dir = tmp_path / "edgar_env"
    test_dir.mkdir()
    
    # Test that use_local_storage sets environment variable
    use_local_storage(True)
    assert os.getenv('EDGAR_USE_LOCAL_DATA') == "1"
    
    use_local_storage(False)
    assert os.getenv('EDGAR_USE_LOCAL_DATA') == "0"
    
    # Test that set_local_storage_path sets environment variable
    set_local_storage_path(test_dir)
    assert os.getenv('EDGAR_LOCAL_DATA_DIR') == str(test_dir)
    
    # Test that use_local_storage with path sets both variables
    use_local_storage(str(test_dir))
    assert os.getenv('EDGAR_USE_LOCAL_DATA') == "1"
    assert os.getenv('EDGAR_LOCAL_DATA_DIR') == str(test_dir)
