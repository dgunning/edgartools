from edgar.sgml import iter_documents, list_documents, FilingSgml, FilingHeader
from edgar.sgml.parsers import SGMLDocument, SGMLParser, SGMLFormatType
from edgar.sgml.tools import get_content_between_tags
from pathlib import Path
from edgar import Filing, find

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
    fs = FilingSgml.from_source("data/sgml/0001011438-98-000429.txt")
    document = fs.get_document_by_sequence("1")
    assert document
    assert document.type == "8-K"
    print(document)
    html = document.html()
    assert not html
    text = document.text()
    assert text

def test_sgml_from_url():
    fs = FilingSgml.from_source('https://www.sec.gov/Archives/edgar/data/730200/000073020016000084/0000730200-16-000084.txt')
    assert fs
    document = fs.get_document_by_sequence("1")
    assert document
    assert document.type == "485BPOS"
    assert document.description == ""
    assert document.html()


def test_sgm_sequence_numbers_match_attachment_sequence_numbers():
    filing = Filing(form='3', filing_date='2018-12-21', company='Aptose Biosciences Inc.', cik=882361, accession_no='0001567619-18-008556')
    attachments = filing.attachments
    filing_sgml = FilingSgml.from_filing(filing)
    sgml_sequences = set(filing_sgml.documents.keys())
    attachment_sequences = {attachment.sequence_number for attachment in attachments if attachment.sequence_number.isdigit()}
    assert sgml_sequences & attachment_sequences


def test_sgml_from_filing():
    filing = Filing(form='S-3/A', filing_date='1995-05-25', company='PAGE AMERICA GROUP INC', cik=311048,
           accession_no='0000899681-95-000096')
    filing_sgml = FilingSgml.from_filing(filing)
    assert filing_sgml
    assert filing_sgml.header.is_empty()

def test_sgml_parser_detect_content():
    parser = SGMLParser()
    assert parser.detect_format(Path("data/sgml/0001011438-98-000429.txt").read_text()) == SGMLFormatType.SEC_DOCUMENT
    assert parser.detect_format(Path("data/sgml/0000899681-95-000096.txt").read_text()) == SGMLFormatType.SEC_DOCUMENT
    assert parser.detect_format(Path("data/sgml/0001398344-24-000491.nc").read_text()) == SGMLFormatType.SUBMISSION

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
        filing_sgml = FilingSgml.from_filing(filing)
        for attachment in filing.attachments:
            if attachment.sequence_number.isdigit():
                sgml_document = filing_sgml.get_document_by_sequence(attachment.sequence_number)
                assert sgml_document
                assert sgml_document.text()


def test_sgml_parsing_of_headers():
    filing = Filing(form='8-K', filing_date='2003-03-05', company='NEW YORK COMMUNITY BANCORP INC', cik=910073, accession_no='0001169232-03-001935')
    filing_sgml = FilingSgml.from_filing(filing)
    assert filing_sgml
    eightk = filing.obj()
    repr(eightk)


def test_sgml_from_submission_file():
    source = Path("data/sgml/0002002260-24-000001.nc")
    filing_sgml = FilingSgml.from_source(source)
    header = filing_sgml.header
    print()

    # Test the header
    assert filing_sgml
    assert header.accession_number == '0002002260-24-000001'
    assert header.filing_date == '2024-01-11'
    assert header.form == 'D'
    assert not header.acceptance_datetime

    # Documents
    assert filing_sgml.documents
    assert len(filing_sgml.documents) == 1
    document:SGMLDocument = filing_sgml.get_document_by_sequence("1")
    assert document
    assert document.filename == "primary_doc.xml"
    text = document.text()
    assert text


def test_sgml_with_multiple_subject_companies():
    source = Path("data/sgml/0001104659-25-002604.txt")
    filing_sgml = FilingSgml.from_source(source)
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
    filing_sgml = FilingSgml.from_source(source)
    header:FilingHeader = filing_sgml.header
    reporting_owner = header.reporting_owners[0]
    assert reporting_owner.owner.name == 'Jessica A. Garascia'

def test_get_attachments_from_sgml_filings():
    source = Path("data/sgml/0001127602-25-001055.txt")
    filing_sgml = FilingSgml.from_source(source)
    s_attachments = filing_sgml.attachments
    assert s_attachments
    assert len(s_attachments.documents) == 2
    assert len(s_attachments.primary_documents) == 1
    assert s_attachments.primary_documents[0].document == 'form4.xml'

def test_html_from_sgml_filing():
    source = Path("data/localstorage/filings/20250108/0001493152-25-001317.nc")
    filing_sgml = FilingSgml.from_source(source)
    html = filing_sgml.html()
    assert html

def test_xml_from_sgml_filing():
    # A form 4 filing
    source = Path("data/localstorage/filings/20250108/0001562180-25-000280.nc")
    filing_sgml = FilingSgml.from_source(source)
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



