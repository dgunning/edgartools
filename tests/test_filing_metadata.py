import pytest
from edgar import Filing, find

def test_get_filing_period_from_homepage():
    f = Filing(company='VISA INC.', cik=1403161, form='4', filing_date='2025-01-03', accession_no='0001127602-25-000445')
    home = f.homepage
    filing_date, acceptance, period = home.get_filing_dates()
    assert (filing_date, acceptance, period) == ('2025-01-03', '2025-01-03 16:28:38', '2025-01-02')
    assert home.period_of_report == '2025-01-02'
    assert f.period_of_report == '2025-01-02'


@pytest.mark.slow
def test_get_metadata_from_filing():
    filing = Filing(form='144', filing_date='2024-12-27', company='Bissell John', cik=1863704, accession_no='0001971857-24-000904')
    filing = find("0001959173-24-008236")
    #print(str(filing))
    homepage = filing.homepage
    filing_date, acceptance_datetime, period_of_report = homepage.get_filing_dates()
    assert filing.accession_number
    assert not period_of_report
    assert acceptance_datetime
    assert homepage.url
    assert filing.text_url
    assert filing.document.url


# Tests for shared metadata helper (edgar.filing_metadata module)

from edgar.filing_metadata import extract_filing_metadata
from unittest.mock import Mock


@pytest.mark.fast
def test_extract_filing_metadata_basic():
    """Test basic metadata extraction without optional fields."""
    # Create mock filing
    filing = Mock()
    filing.form = '10-K'
    filing.accession_no = '0001234567-24-000001'
    filing.filing_date = '2024-03-15'
    filing.company = 'Test Corp'
    filing.cik = 1234567

    metadata = extract_filing_metadata(filing, include_ticker=False)

    assert metadata['form'] == '10-K'
    assert metadata['accession_no'] == '0001234567-24-000001'
    assert metadata['filing_date'] == '2024-03-15'
    assert metadata['company'] == 'Test Corp'
    assert metadata['cik'] == '1234567'
    assert 'ticker' not in metadata
    assert 'period' not in metadata
    assert 'cik_padded' not in metadata


@pytest.mark.fast
def test_extract_filing_metadata_with_ticker():
    """Test metadata extraction with ticker lookup."""
    filing = Mock()
    filing.form = '10-K'
    filing.company = 'Apple Inc.'
    filing.cik = 320193
    filing.accession_no = '0001234567-24-000001'
    filing.filing_date = '2024-03-15'

    metadata = extract_filing_metadata(filing, include_ticker=True)

    assert metadata['ticker'] == 'AAPL'
    assert metadata['form'] == '10-K'
    assert metadata['company'] == 'Apple Inc.'
    assert metadata['cik'] == '320193'


@pytest.mark.fast
def test_extract_filing_metadata_with_period():
    """Test metadata extraction with period of report."""
    filing = Mock()
    filing.form = '10-Q'
    filing.company = 'Test Corp'
    filing.cik = 1234567
    filing.accession_no = '0001234567-24-000001'
    filing.filing_date = '2024-03-15'
    filing.period_of_report = '2024-01-31'

    metadata = extract_filing_metadata(filing, include_period=True, include_ticker=False)

    assert metadata['period'] == '2024-01-31'
    assert metadata['form'] == '10-Q'
    assert 'ticker' not in metadata


@pytest.mark.fast
def test_extract_filing_metadata_missing_fields():
    """Test graceful handling of missing fields."""
    filing = Mock(spec=[])  # Mock with no attributes

    metadata = extract_filing_metadata(filing, include_ticker=False)

    assert metadata['form'] is None
    assert metadata['company'] is None
    assert metadata['cik'] is None
    assert metadata['accession_no'] is None
    assert metadata['filing_date'] is None


@pytest.mark.fast
def test_extract_filing_metadata_cik_padded():
    """Test zero-padded CIK extraction."""
    filing = Mock()
    filing.cik = 320193
    filing.form = '10-K'
    filing.company = 'Apple Inc.'
    filing.accession_no = '0001234567-24-000001'
    filing.filing_date = '2024-03-15'

    metadata = extract_filing_metadata(filing, include_cik_padded=True, include_ticker=False)

    assert metadata['cik'] == '320193'
    assert metadata['cik_padded'] == '0000320193'


@pytest.mark.fast
def test_extract_filing_metadata_all_options():
    """Test metadata extraction with all optional fields enabled."""
    filing = Mock()
    filing.form = '10-Q'
    filing.company = 'Apple Inc.'
    filing.cik = 320193
    filing.accession_no = '0001234567-24-000001'
    filing.filing_date = '2024-03-15'
    filing.period_of_report = '2024-01-31'

    metadata = extract_filing_metadata(
        filing,
        include_ticker=True,
        include_period=True,
        include_cik_padded=True
    )

    assert metadata['form'] == '10-Q'
    assert metadata['accession_no'] == '0001234567-24-000001'
    assert metadata['filing_date'] == '2024-03-15'
    assert metadata['company'] == 'Apple Inc.'
    assert metadata['cik'] == '320193'
    assert metadata['ticker'] == 'AAPL'
    assert metadata['period'] == '2024-01-31'
    assert metadata['cik_padded'] == '0000320193'


@pytest.mark.fast
def test_extract_filing_metadata_ticker_fallback():
    """Test ticker fallback when find_ticker fails but filing has ticker attribute."""
    filing = Mock()
    filing.form = '10-K'
    filing.company = 'Test Corp'
    filing.cik = 9999999999  # Non-existent CIK
    filing.accession_no = '0001234567-24-000001'
    filing.filing_date = '2024-03-15'
    filing.ticker = 'TEST'  # Direct ticker attribute

    metadata = extract_filing_metadata(filing, include_ticker=True)

    # Should fall back to filing.ticker when find_ticker fails
    assert metadata['ticker'] == 'TEST'
    assert metadata['cik'] == '9999999999'
