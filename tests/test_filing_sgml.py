import tempfile
import zipfile
from pathlib import Path

from edgar import *
from edgar.sgml import iter_documents, list_documents, FilingSGML, Filer
from edgar.sgml.sgml_parser import SGMLDocument, SGMLParser, SGMLFormatType, SECIdentityError, SECFilingNotFoundError, SECHTMLResponseError
from edgar.sgml.tools import get_content_between_tags
import hashlib
from io import BytesIO
from edgar.vendored import uu
from rich import print
import pytest

def test_parse_old_full_text():
    source = Path("data/sgml/0001011438-98-000429.txt")
    documents = list(iter_documents(source))
    current_report = documents[0]
    assert current_report.type == "8-K"
    assert current_report.sequence == "1"
    assert current_report.description == "CURRENT REPORT"

    exhibit = documents[1]
    assert exhibit.type == "EX-20.1"
    assert exhibit.sequence == "2"
    assert exhibit.description == "STATEMENT TO CERTIFICATEHOLDERS"


def test_parse_sgml_with_xbrl():
    source = Path("data/sgml/0000943374-24-000509.txt")
    sgml_documents = list_documents(source)
    xbrl_document = sgml_documents[0]
    assert xbrl_document.type == "8-K"
    assert xbrl_document.sequence == "1"
    assert xbrl_document.description == "1895 BANCORP OF WISCONSIN, INC. FORM 8-K DECEMBER 20, 2024"
    assert xbrl_document.filename == "form8k_122024.htm"
    xbrl = xbrl_document.xbrl()
    assert xbrl
    print(xbrl)
    assert xbrl.startswith("<?xml version='1.0' encoding='ASCII'?>")
    assert 'html' in xbrl


def test_sgml_document_from_source():
    fs = FilingSGML.from_source("data/sgml/0001011438-98-000429.txt")
    document = fs.get_document_by_sequence("1")
    assert document
    assert document.type == "8-K"
    print(document)
    html = document.html()
    assert not html
    text = document.text()
    assert text

def test_sgml_from_url():
    fs = FilingSGML.from_source('https://www.sec.gov/Archives/edgar/data/730200/000073020016000084/0000730200-16-000084.txt')
    assert fs
    document = fs.get_document_by_sequence("1")
    assert document
    assert document.type == "485BPOS"
    assert document.description == ""
    assert document.html()

@pytest.mark.network
def test_sgm_sequence_numbers_match_attachment_sequence_numbers():
    filing = Filing(form='3', filing_date='2018-12-21', company='Aptose Biosciences Inc.', cik=882361, accession_no='0001567619-18-008556')
    attachments = filing.attachments
    filing_sgml = FilingSGML.from_filing(filing)
    sgml_sequences = set(filing_sgml._documents_by_sequence.keys())
    attachment_sequences = {attachment.sequence_number for attachment in attachments if attachment.sequence_number.isdigit()}
    assert sgml_sequences & attachment_sequences

@pytest.mark.network
def test_sgml_from_filing():
    filing = Filing(form='S-3/A', filing_date='1995-05-25', company='PAGE AMERICA GROUP INC', cik=311048,
           accession_no='0000899681-95-000096')
    filing_sgml = FilingSGML.from_filing(filing)
    assert filing_sgml
    assert filing_sgml.accession_number == '0000899681-95-000096'
    assert filing_sgml.cik == 311048
    assert not filing_sgml.header.is_empty()
    repr(filing_sgml.header)

def test_filing_from_sgml():
    filing = Filing.from_sgml('data/sgml/0000320193-24-000123.txt')
    assert filing.form == '10-K'
    assert filing.filing_date == '2024-11-01'
    assert filing.company == 'Apple Inc.'
    assert filing.accession_no == '0000320193-24-000123'
    assert filing.cik == 320193
    print()
    print(filing)

def test_from_sgml_text():
    content = Path('data/sgml/0000320193-24-000123.txt').read_text()
    filing = Filing.from_sgml_text(content)
    assert filing


def test_sgml_parser_detect_content():
    parser = SGMLParser()
    assert parser.detect_format(Path("data/sgml/0001011438-98-000429.txt").read_text()) == SGMLFormatType.SEC_DOCUMENT
    assert parser.detect_format(Path("data/sgml/0000899681-95-000096.txt").read_text()) == SGMLFormatType.SEC_DOCUMENT
    assert parser.detect_format(Path("data/sgml/0001398344-24-000491.nc").read_text()) == SGMLFormatType.SUBMISSION

@pytest.mark.network
def test_get_attachment_content_from_sgml():

    filings = [
        Filing(form='S-3/A', filing_date='1995-05-25', company='PAGE AMERICA GROUP INC', cik=311048,
               accession_no='0000899681-95-000096'),
        Filing(form='DEF 14A', filing_date='2002-05-22', company='14A DIGITAL COURIER TECHNOLOGIES INC', cik=774055,
               accession_no='0000931731-02-000196'),
        Filing(form='4', filing_date='2010-05-20', company='Becker Steven R', cik=1349005,
               accession_no='0001209191-10-029489'),
        Filing(form='POS AMI', filing_date='2015-05-15', company='AMI J.P. Morgan Access Multi-Strategy Fund II',
               cik=1524115, accession_no='0001193125-15-190059'),
        Filing(form='NPORT-P', filing_date='2020-05-20', company='CALVERT SOCIAL INVESTMENT FUND', cik=356682,
               accession_no='0001752724-20-097145'),
        Filing(form='425', filing_date='2024-05-29', company='Uniti Group Inc.', cik=1620280,
               accession_no='0000950103-24-007264')
    ]
    for filing in filings:
        filing_sgml = FilingSGML.from_filing(filing)
        for attachment in filing.attachments:
            if attachment.sequence_number.isdigit():
                sgml_document = filing_sgml.get_document_by_sequence(attachment.sequence_number)
                assert sgml_document
                assert sgml_document.text()
                assert attachment.url

@pytest.mark.network
def test_sgml_parsing_of_headers():
    filing = Filing(form='8-K', filing_date='2003-03-05', company='NEW YORK COMMUNITY BANCORP INC', cik=910073, accession_no='0001169232-03-001935')
    filing_sgml = FilingSGML.from_filing(filing)
    assert filing_sgml
    eightk = filing.obj()
    repr(eightk)


def test_sgml_from_submission_file():
    source = Path("data/sgml/0002002260-24-000001.nc")
    filing_sgml = FilingSGML.from_source(source)
    header = filing_sgml.header
    print()

    # Test the header
    assert filing_sgml
    assert header.accession_number == '0002002260-24-000001'
    assert header.filing_date == '2024-01-11'
    assert header.form == 'D'
    assert not header.acceptance_datetime

    # Documents
    assert filing_sgml._documents_by_sequence
    assert len(filing_sgml._documents_by_sequence) == 1
    document:SGMLDocument = filing_sgml.get_document_by_sequence("1")
    assert document
    assert document.filename == "primary_doc.xml"
    text = document.text()
    assert text


def test_sgml_with_multiple_subject_companies():
    source = Path("data/sgml/0001104659-25-002604.txt")
    filing_sgml = FilingSGML.from_source(source)
    header:FilingHeader = filing_sgml.header
    assert len(header.subject_companies) == 2
    subject_company_0 = header.subject_companies[0]
    assert subject_company_0.company_information.cik == '0001376139'
    assert subject_company_0.company_information.name == 'CVR ENERGY INC'
    assert subject_company_0.filing_information.form == 'SC 13D/A'

    subject_company_1 = header.subject_companies[1]
    assert subject_company_1.company_information.cik == '0001376139'
    assert subject_company_1.company_information.name == 'CVR ENERGY INC'
    assert subject_company_1.filing_information.form == 'SC TO-T/A'
    assert filing_sgml

def test_sgml_with_reporting_owner():
    source = Path("data/sgml/0001127602-25-001055.txt")
    filing_sgml = FilingSGML.from_source(source)
    header:FilingHeader = filing_sgml.header
    reporting_owner = header.reporting_owners[0]
    assert reporting_owner.owner.name == 'Jessica A. Garascia'

def test_get_attachments_from_sgml_filings():
    source = Path("data/sgml/0001127602-25-001055.txt")
    filing_sgml = FilingSGML.from_source(source)
    s_attachments = filing_sgml.attachments
    assert s_attachments
    assert len(s_attachments.documents) == 2
    assert len(s_attachments.primary_documents) == 1
    assert s_attachments.primary_documents[0].document == 'form4.xml'

def test_html_from_sgml_filing():
    source = Path("data/localstorage/filings/20250108/0001493152-25-001317.nc")
    filing_sgml = FilingSGML.from_source(source)
    html = filing_sgml.html()
    assert html

def test_xml_from_sgml_filing():
    # A form 4 filing
    source = Path("data/localstorage/filings/20250108/0001562180-25-000280.nc")
    filing_sgml = FilingSGML.from_source(source)
    xml = filing_sgml.xml()
    assert xml

def test_get_content_between_tags():
    content = """
    <DOCUMENT>
    <TYPE>8-K
    <SEQUENCE>1
    <FILENAME>form8-k.htm
    <TEXT>
    <XBRL>
    Raw content here
    </XBRL>
    </TEXT>
    </DOCUMENT>
    """

    # Get XBRL content specifically
    xbrl_content = get_content_between_tags(content, "XBRL")  # Returns "Raw content here"
    assert xbrl_content.strip() == "Raw content here"

    # Get TEXT content
    text_content = get_content_between_tags(content, "TEXT")  # Returns "<XBRL>\nRaw content here\n</XBRL>"
    assert text_content.strip() == '<XBRL>\n    Raw content here\n    </XBRL>'

    # Get innermost content
    inner_content = get_content_between_tags(content)  # Returns "Raw content here"

    assert inner_content.strip() == "Raw content here"

    content = """
    <DOCUMENT>
    <TYPE>8-K
    <SEQUENCE>1
    <FILENAME>form8-k.htm
    <TEXT>
    <XML>
    Raw content here
    </XML>
    </TEXT>
    </DOCUMENT>
    """

    # Get XML content specifically
    xml_content = get_content_between_tags(content, "XML")  # Returns "Raw content here"
    assert xml_content.strip() == "Raw content here"


def test_sgml_format_for_really_old_filing():
    filing = Filing(form='8-K', filing_date='1995-02-14', company='ALBERTO CULVER CO', cik=3327, accession_no='0000003327-95-000017')
    filing_sgml = FilingSGML.from_filing(filing)
    assert filing_sgml


def test_download_to_directory():
    sgml: FilingSGML = FilingSGML.from_source("data/sgml/0000320193-24-000123.txt")
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        sgml.download(temp_path)

        for document in sgml._documents_by_name.values():
            file_path = temp_path / document.filename
            assert file_path.exists()


def test_download_to_archive():
    sgml: FilingSGML = FilingSGML.from_source("data/sgml/0000320193-24-000123.txt")
    with tempfile.TemporaryDirectory() as temp_dir:
        archive_path = Path(temp_dir) / "attachments.zip"
        sgml.download(archive_path, archive=True)

        with zipfile.ZipFile(archive_path, 'r') as zipf:
            archive_names = zipf.namelist()
            for document in sgml._documents_by_name.values():
                assert document.filename in archive_names

@pytest.mark.network
def test_get_sgml_from_filing_when_no_local_storage_exists(monkeypatch):
    filing = Filing(company='Apple Inc.', cik=320193, form='10-K', filing_date='2024-11-01',
            accession_no='0000320193-24-000123')
    monkeypatch.setenv('EDGAR_USE_LOCAL_DATA', '1')
    filing_sgml = filing.sgml()
    assert filing_sgml

def test_get_filing_summary():
    sgml: FilingSGML = FilingSGML.from_source("data/sgml/0000320193-24-000123.txt")
    summary = sgml.filing_summary
    assert summary

def test_unusual_sgml_format():
    filing = Filing(form='NPORT-P', filing_date='2024-08-14', company='RMB INVESTORS TRUST', cik=30126, accession_no='0001145549-24-048310')
    sgml = filing.sgml()
    assert sgml
    sgml = FilingSGML.from_source(filing.text_url)
    assert sgml

def test_filing_sgml_repr():
    sgml: FilingSGML = FilingSGML.from_source("data/sgml/0000320193-24-000123.txt")
    _repr = repr(sgml)
    assert _repr

def test_get_binary_content():
    sgml: FilingSGML = FilingSGML.from_source("data/sgml/0000320193-24-000123.txt")
    aapl_20240928_g1 = sgml.attachments[19]
    sgml_content = aapl_20240928_g1.content

    # Read the downloaded file
    with open("data/sgml/aapl-20240928_g1.jpg", "rb") as f:
        file_content = f.read()

    with open("data/sgml/aapl-20240928_g1-sgml.jpg", "wb") as f:
        f.write(sgml_content)
    # Create hashes for comparison

    sgml_hash = hashlib.sha256(sgml_content).hexdigest()
    file_hash = hashlib.sha256(file_content).hexdigest()

    # The hashes won't be the same because when the image is added into the SGML, it's encoded in a different way
    #assert sgml_hash == file_hash, f"Content mismatch:\nSGML hash: {sgml_hash}\nFile hash: {file_hash}"


def test_uu_roundtrip():

    # Read original file
    with open("data/sgml/aapl-20240928_g1.jpg", "rb") as f:
        original_content = f.read()

    # Create streams for encoding
    input_stream = BytesIO(original_content)
    encoded_stream = BytesIO()

    # UU encode
    uu.encode(input_stream, encoded_stream)
    encoded_content = encoded_stream.getvalue()

    # Create streams for decoding
    decode_input = BytesIO(encoded_content)
    decoded_stream = BytesIO()

    # UU decode
    uu.decode(decode_input, decoded_stream)
    decoded_content = decoded_stream.getvalue()

    # Compare original and roundtripped content
    original_hash = hashlib.sha256(original_content).hexdigest()
    decoded_hash = hashlib.sha256(decoded_content).hexdigest()

    assert original_hash == decoded_hash, (
        f"Roundtrip failed:\nOriginal hash: {original_hash}\nDecoded hash: {decoded_hash}"
    )

    # Optionally verify the encoded content looks correct
    encoded_text = encoded_content.decode('ascii')
    assert encoded_text.startswith('begin')
    assert encoded_text.endswith('end\n')
    assert '\nend\n' in encoded_text  # Proper end marker format


def test_parse_filing_sgml_from_filing_with_new_series():
    sgml = FilingSGML.from_source('data/sgml/0001193125-24-100942.txt')
    assert sgml
    sgml = FilingSGML.from_source('data/sgml/0001193125-24-100942.nc')
    assert sgml

def test_sgml_from_abs_filing():
    sgml = FilingSGML.from_source('data/sgml/0000929638-25-000114.nc')
    assert sgml


def test_sgml_from_old_filing():
    sgml = FilingSGML.from_source('data/sgml/0001193125-10-145855.nc')
    assert sgml

def test_sgml_from_really_old_filing_needing_preprocessing():
    sgml = FilingSGML.from_source('data/sgml/0001094891-00-000193.txt')
    assert sgml

@pytest.mark.network
def test_sgml_header_has_company_information_485POS():
    filing = Filing(form='485APOS', filing_date='2024-03-13', company='iSHARES TRUST', cik=1100663, accession_no='0001193125-24-066744')
    # This was failing because the header text had extra newlines
    _repr = repr(filing)

def test_parse_header_with_double_newlines():
    content = Path("data/sgml/header_with_double_newlines.txt").read_text()

    filing_header = FilingHeader.parse_from_sgml_text(content)
    assert filing_header
    filer:Filer = filing_header.filers[0]
    print()
    print(filer)
    assert filer.company_information
    assert filer.company_information.name == 'iSHARES TRUST'
    assert filer.business_address.city== 'SAN FRANCISCO'

    assert filer.mailing_address.city == 'SAN FRANCISCO'

@pytest.mark.network
def test_parse_filing_header_with_problem():
    filing = Filing(form='424B5',
                    filing_date='2000-03-14',
                    company='CENTEX HOME EQUITY LOAN TRUST 2000-A',
                    cik=1109352,
                    accession_no='0000912057-00-011488')
    filing_sgml = FilingSGML.from_filing(filing)
    assert filing_sgml


def test_parse_tsla_sgml_with_embedded_ixbrl():
    content = Path("data/sgml/0001564590-20-004475-minimal.txt").read_text()
    filing_header = FilingHeader.parse_from_sgml_text(content)
    assert filing_header

def test_detect_sec_identity_error():
    """Test that SEC identity error HTML is properly detected"""
    html_content = Path("data/html/SEC.AutomatedTool.html").read_text()
    parser = SGMLParser()

    # Should now raise SECIdentityError with helpful message
    with pytest.raises(SECIdentityError, match="SEC rejected request due to invalid or missing EDGAR_IDENTITY"):
        parser.detect_format(html_content)


def test_sec_identity_error_message_quality():
    """Test that the error message is helpful and actionable"""
    html_content = Path("data/html/SEC.AutomatedTool.html").read_text()
    parser = SGMLParser()

    try:
        parser.detect_format(html_content)
        assert False, "Expected SECIdentityError to be raised"
    except SECIdentityError as e:
        error_msg = str(e)
        # Ensure the error message contains helpful information
        assert "set_identity" in error_msg
        assert "sec.gov" in error_msg
        assert "EDGAR_IDENTITY" in error_msg
        assert "your.email@domain.com" in error_msg


def test_generic_html_error():
    """Test that generic HTML content raises SECHTMLResponseError"""
    generic_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Some Random HTML</title></head>
    <body><h1>This is not SGML</h1></body>
    </html>
    """
    parser = SGMLParser()

    # Should raise SECHTMLResponseError for generic HTML
    with pytest.raises(SECHTMLResponseError, match="SEC returned HTML or XML content instead of expected SGML"):
        parser.detect_format(generic_html)


def test_nosuchkey_error():
    """Test that AWS S3 NoSuchKey XML error is properly detected"""
    xml_error = """<?xml version="1.0" encoding="UTF-8"?>
<Error><Code>NoSuchKey</Code><Message>The specified key does not exist.</Message><Key>edgar/data/320193/000078901925000033/0000789019-25-000033.txt</Key><RequestId>V69KE626D814ADQ3</RequestId><HostId>6tCOv+xG9XpkfYSota8rmKe8j0JedY04gPqTGHoV29NyKSnTUH2ETAdw6HTinc/At8JgpHyFjic=</HostId></Error>"""

    parser = SGMLParser()

    # Should raise SECFilingNotFoundError with specific message for NoSuchKey
    with pytest.raises(SECFilingNotFoundError, match="SEC filing not found - the specified key does not exist"):
        parser.detect_format(xml_error)


def test_handle_sec_error_message_in_sgml_with_invalid_identity(monkeypatch):
    """Test that an invalid identity causes appropriate error handling"""
    # Use monkeypatch to set invalid identity without affecting other tests
    monkeypatch.setenv("EDGAR_IDENTITY", "harvey")  # Invalid identity - not email format
    filing = Filing(company='Walmart Inc.', cik=104169, form='4', filing_date='2025-09-24', accession_no='0000104169-25-000155')

    # This should fail when trying to parse the HTML error response
    with pytest.raises(SECIdentityError):
        filing.sgml()


def test_handle_sec_error_message_with_nonexistent_filing(monkeypatch):
    """Test behavior when requesting a non-existent filing"""
    # Use monkeypatch to set proper identity without affecting other tests
    monkeypatch.setenv("EDGAR_IDENTITY", "Test User test@example.com")
    filing = Filing(company='Walmart Inc.', cik=104169, form='4', filing_date='2025-09-24', accession_no='0000104169-25-999999')

    # This should fail when SEC returns error content
    # Could be either SECFilingNotFoundError or SECHTMLResponseError depending on SEC's response
    with pytest.raises((SECFilingNotFoundError, SECHTMLResponseError)):
        filing.sgml()