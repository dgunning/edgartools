import tempfile
from pathlib import Path

import io
import os
import pytest
from rich import print

from edgar import Filing, find
from edgar.attachments import Attachment, Attachments
from edgar.sgml import FilingSGML
from edgar.httprequests import download_file
import tempfile

@pytest.fixture
def press_release_attachments() -> Attachments:
    filing = Filing.from_sgml("data/sgml/0001213900-25-032135.txt")
    return filing.attachments

@pytest.fixture
def sample_attachments():
    return [
        Attachment(
            sequence_number="1",
            description="Sample document 1",
            document="doc1.txt",
            ixbrl=False,
            path="doc1.txt",
            document_type="EX-99",
            size=1024
        ),
        Attachment(
            sequence_number="2",
            description="Sample document 2",
            document="doc2.txt",
            ixbrl=False,
            path="doc2.txt",
            document_type="EX-99.1",
            size=2048
        )
    ]


@pytest.fixture
def attachments(sample_attachments):
    return Attachments(document_files=sample_attachments, data_files=None, primary_documents=[])

# --- Additional Coverage Tests ---
def test_query_with_regex_and_combined_conditions(press_release_attachments):
    attachments = press_release_attachments.query("re.match('ea.*.htm', document) and document_type in ['EX-99', 'EX-99.1']")
    assert len(attachments) == 1
    document = attachments['ea023837201ex99-1_abvcbio.htm']
    assert document.document == 'ea023837201ex99-1_abvcbio.htm'


def test_query_with_no_matches(press_release_attachments):
    result = press_release_attachments.query("document_type=='NONEXISTENT'")
    assert isinstance(result, Attachments)
    assert len(result) == 0

def test_download_returns_content(press_release_attachments):
    att = press_release_attachments[1]
    content = att.download()
    assert isinstance(content, (str, bytes))
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        file_path = temp_path / att.document
        att.download(file_path)
        assert file_path.exists()
        att.download(str(file_path))


def test_download_to_invalid_path(press_release_attachments):
    att = press_release_attachments[1]
    with pytest.raises(Exception):
        att.download("/nonexistent/path/file.txt")

def test_is_html_xml_text_properties(attachments):
    att = attachments[1]
    assert isinstance(att.is_html(), bool)
    assert isinstance(att.is_xml(), bool)
    assert isinstance(att.is_text(), bool)

def test_attachment_repr_and_str(attachments):
    att = attachments[1]
    assert isinstance(str(att), str)
    assert isinstance(repr(att), str)

def test_attachments_getitem_and_len(attachments):
    att_by_index = attachments[1]
    att_by_name = attachments["doc1.txt"]
    assert att_by_index is att_by_name
    assert len(attachments) == 2

def test_attachments_iter(attachments):
    for att in attachments:
        assert isinstance(att, Attachment)

def test_query_chaining(attachments):
    result = attachments.query("document_type in ['EX-99', 'EX-99.1']")
    xml_result = result.query("document.endswith('.xml')")
    assert isinstance(xml_result, Attachments)

def test_attachment_download_bytes_and_str(tmp_path, press_release_attachments):
    att_txt = press_release_attachments[13]
    assert isinstance(att_txt.download(), (str, bytes))
    att_jpg = press_release_attachments[3]
    assert isinstance(att_jpg.download(), (str, bytes))


def test_get_attachment_by_type():
    filing = Filing(form='8-K', filing_date='2024-03-08', company='3M CO', cik=66740,
                    accession_no='0000066740-24-000023')
    attachments = filing.attachments

    # Get a single attachment
    attachment = attachments.query("document_type=='EX-99.1'")
    assert isinstance(attachment, Attachments)

    # Get multiple attachments
    result = attachments.query("re.match('mmm-*', document)")
    assert len(result) == 6

    # No results
    result = attachments.query("re.match('DORM-*', document)")
    assert len(result) == 0


def test_loop_through_attachments():
    filing = Filing(form='8-K', filing_date='2024-03-08', company='3M CO', cik=66740,
                    accession_no='0000066740-24-000023')
    for attachment in filing.attachments:
        assert attachment
        assert isinstance(attachment, Attachment)


def test_attachment_is_empty():
    filing = Filing(form='10-Q', filing_date='2000-05-11', company='APPLE COMPUTER INC', cik=320193,
                    accession_no='0000912057-00-023442')
    attachments = filing.attachments
    print(attachments)
    attachment: Attachment = attachments[1]
    assert attachment.document == ''
    assert attachment.empty





def test_download_to_directory():
    filing = Filing(form='4', filing_date='2024-05-24', company='t Hart Cees', cik=1983327,
                    accession_no='0000950170-24-064537')
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        attachments = filing.attachments
        attachments.download(temp_path)

        for attachment in attachments.documents:
            file_path = temp_path / attachment.document
            assert file_path.exists()


def test_download_to_archive():
    filing = Filing(form='4', filing_date='2024-05-24', company='t Hart Cees', cik=1983327,
                    accession_no='0000950170-24-064537')
    attachments = filing.attachments
    with tempfile.TemporaryDirectory() as temp_dir:
        archive_path = Path(temp_dir) / "attachments.zip"
        attachments.download(archive_path, archive=True)

        import zipfile
        with zipfile.ZipFile(archive_path, 'r') as zipf:
            archive_names = zipf.namelist()
            for attachment in attachments.documents:
                assert attachment.document in archive_names


def test_attachment_list_url():
    filing = Filing(form='8-K', filing_date='2024-03-08', company='3M CO', cik=66740,
                    accession_no='0000066740-24-000023')
    # assert filing.attachment_list_url == 'https://www.sec.gov/Archives/edgar/data/1983327/000095017024064537/index.json'
    files = download_file(f"{filing.base_dir}/index.json")
    print(files)
    print(filing.attachments)
    header_url = f"{filing.base_dir}/0000066740-24-000023-index-headers.html"
    print(header_url)
    index_headers = download_file(header_url)
    print(index_headers)


def test_list_exhibits():
    filing: Filing = Filing(form='8-K', filing_date='2024-03-08', company='3M CO', cik=66740,
                            accession_no='0000066740-24-000023')
    attachments = filing.attachments
    exhibits = attachments.exhibits
    print(exhibits)
    assert len(exhibits) == 2
    assert exhibits[1].document_type == '8-K'
    assert exhibits[2].document_type == 'EX-99.1'


def test_list_graphics():
    filing = Filing(company='Gitlab Inc.', cik=1653482, form='10-K', filing_date='2024-03-26',
                    accession_no='0001628280-24-012963')
    graphics = filing.attachments.graphics
    assert len(graphics) == 2
    assert next(graphics).document_type == 'GRAPHIC'
    assert next(graphics).document_type == 'GRAPHIC'


def test_attachments():
    filing = Filing(company="BLACKROCK INC", cik=1364742, form="8-K",
                    filing_date="2023-02-24", accession_no="0001193125-23-048785")
    attachments = filing.attachments
    assert len(attachments) == 13

    attachment = attachments[3]
    assert attachment
    assert attachment.document == 'blk25-20230224_def.xml'

    text = attachment.download()
    assert text
    assert "<?xml version=" in text

    # Test the filing homepage attachments
    assert filing.homepage.attachments
    assert len(filing.homepage.attachments) == 7

    # Test the filing attachments
    assert filing.attachments
    assert len(filing.attachments) == 13
    assert filing.attachments[5].description == 'XBRL TAXONOMY EXTENSION PRESENTATION LINKBASE'

    # Get the filing using the document name
    assert filing.attachments["blk25-20230224.xsd"].description == "XBRL TAXONOMY EXTENSION SCHEMA"


def test_download_filing_attachment():
    filing = Filing(form='10-K', filing_date='2023-06-02', company='Cyber App Solutions Corp.', cik=1851048,
                    accession_no='0001477932-23-004175')
    attachments = filing.attachments
    print(attachments)

    # Get a text/htm attachment
    attachment = attachments.get_by_sequence(1)
    assert attachment.document == "cyber_10k.htm"
    text = attachment.download()
    assert isinstance(text, str)

    # Get a jpg attachment
    attachment = attachments.get_by_sequence(9)
    assert attachment.document == "cyber_10kimg1.jpg"
    b = attachment.download()
    assert isinstance(b, bytes)


def test_filings_with_no_content_in_attachments():
    filing = Filing(form='8-K', filing_date='1998-12-31', company='AAMES CAPITAL CORP', cik=913951, accession_no='0001011438-98-000429')
    attachments = filing.attachments
    print()
    print(attachments)
    attachment = attachments[1]
    assert attachment.empty
    print(attachment.url)


def test_get_report_attachments():
    filing_sgml = FilingSGML.from_source("data/sgml/0000320193-24-000123.txt")
    attachments = filing_sgml.attachments
    report = attachments.get_report('R5.htm')
    assert report
    assert report.html_file_name == 'R5.htm'
    print()
    text = report.text()
    print(text)
    assert 'CONSOLIDATED BALANCE SHEETS' in text


def test_attachment_markdown_conversion():
    """Test that HTML attachments can be converted to markdown"""
    filing = Filing(form='10-K', filing_date='2023-06-02', company='Cyber App Solutions Corp.', cik=1851048,
                    accession_no='0001477932-23-004175')
    attachments = filing.attachments
    
    # Get the HTML attachment (sequence 1)
    html_attachment = attachments.get_by_sequence(1)
    assert html_attachment.document == "cyber_10k.htm"
    assert html_attachment.is_html()
    
    # Test markdown conversion
    markdown_content = html_attachment.markdown()
    assert markdown_content is not None
    assert isinstance(markdown_content, str)
    assert len(markdown_content) > 0
    
    # Test that non-HTML attachments return None
    if len(attachments) > 1:
        for attachment in attachments:
            if not attachment.is_html():
                assert attachment.markdown() is None


def test_attachments_markdown_batch_conversion():
    """Test batch markdown conversion for all HTML attachments"""
    filing = Filing(form='10-K', filing_date='2023-06-02', company='Cyber App Solutions Corp.', cik=1851048,
                    accession_no='0001477932-23-004175')
    attachments = filing.attachments
    
    # Get markdown for all HTML attachments
    markdown_dict = attachments.markdown()
    assert isinstance(markdown_dict, dict)
    
    # Should have at least the main HTML document
    assert len(markdown_dict) > 0
    
    # Check that the main HTML document is included
    assert "cyber_10k.htm" in markdown_dict
    
    # Verify all entries are strings
    for doc_name, markdown_content in markdown_dict.items():
        assert isinstance(doc_name, str)
        assert isinstance(markdown_content, str)
        assert len(markdown_content) > 0


def test_attachment_markdown_with_non_html_filing():
    """Test markdown conversion with a filing that has non-HTML primary document"""
    filing = Filing(form='4', filing_date='2024-05-24', company='t Hart Cees', cik=1983327,
                    accession_no='0000950170-24-064537')
    attachments = filing.attachments
    
    # Test markdown conversion - should handle gracefully
    markdown_dict = attachments.markdown()
    assert isinstance(markdown_dict, dict)
    
    # May be empty if no HTML attachments
    for doc_name, markdown_content in markdown_dict.items():
        assert isinstance(doc_name, str)
        assert isinstance(markdown_content, str)


def test_attachment_markdown_with_page_breaks():
    """Test that HTML attachments can be converted to markdown with page breaks"""
    filing = Filing(form='10-K', filing_date='2023-06-02', company='Cyber App Solutions Corp.', cik=1851048,
                    accession_no='0001477932-23-004175')
    attachments = filing.attachments
    
    # Get the HTML attachment (sequence 1)
    html_attachment = attachments.get_by_sequence(1)
    assert html_attachment.document == "cyber_10k.htm"
    assert html_attachment.is_html()
    
    # Test with page breaks enabled
    markdown_with_breaks = html_attachment.markdown(include_page_breaks=True)
    assert markdown_with_breaks is not None
    assert isinstance(markdown_with_breaks, str)
    
    # Test without page breaks
    markdown_without_breaks = html_attachment.markdown(include_page_breaks=False)
    assert markdown_without_breaks is not None
    assert isinstance(markdown_without_breaks, str)
    
    # Check that page break markers are present when enabled
    if '{' in markdown_with_breaks and '}' in markdown_with_breaks:
        assert '------------------------------------------------' in markdown_with_breaks
        print("✓ Page break delimiters found in markdown output")
    else:
        print("ℹ No page break markers found in this document")
    
    # The version with page breaks should be different from the one without
    # (unless there are no page breaks in the document)
    if '{' in markdown_with_breaks:
        assert markdown_with_breaks != markdown_without_breaks
        print("✓ Page break versions are different")
    else:
        print("ℹ No page breaks detected in this document")


def test_attachments_batch_markdown_with_page_breaks():
    """Test batch conversion of attachments with page breaks"""
    filing = Filing(form='10-K', filing_date='2023-06-02', company='Cyber App Solutions Corp.', cik=1851048,
                    accession_no='0001477932-23-004175')
    attachments = filing.attachments
    
    # Test batch conversion with page breaks
    markdown_dict_with_breaks = attachments.markdown(include_page_breaks=True)
    assert isinstance(markdown_dict_with_breaks, dict)
    
    # Test batch conversion without page breaks
    markdown_dict_without_breaks = attachments.markdown(include_page_breaks=False)
    assert isinstance(markdown_dict_without_breaks, dict)
    
    # Both should have the same keys (document names)
    assert set(markdown_dict_with_breaks.keys()) == set(markdown_dict_without_breaks.keys())
    
    # Check that at least one attachment was converted
    assert len(markdown_dict_with_breaks) > 0
    print(f"✓ Converted {len(markdown_dict_with_breaks)} attachments to markdown")


def test_filing_markdown_with_page_breaks():
    """Test that main filing can be converted to markdown with page breaks"""
    filing = Filing(form='10-K', filing_date='2023-06-02', company='Cyber App Solutions Corp.', cik=1851048,
                    accession_no='0001477932-23-004175')
    
    # Test main filing with page breaks
    markdown_with_breaks = filing.markdown(include_page_breaks=True)
    assert markdown_with_breaks is not None
    assert isinstance(markdown_with_breaks, str)
    
    # Test main filing without page breaks
    markdown_without_breaks = filing.markdown(include_page_breaks=False)
    assert markdown_without_breaks is not None
    assert isinstance(markdown_without_breaks, str)
    
    print("✓ Main filing markdown conversion with page breaks working")


def test_page_break_detection_patterns():
    """Test that various page break patterns are detected correctly"""
    test_html = """
    <html>
    <body>
        <div>Content before first page break</div>
        <p style="page-break-before:always"></p>
        <div>Content after first page break</div>
        <hr style="page-break-after:always"/>
        <div>Content after second page break</div>
        <div style="page-break-before:always"></div>
        <div>Content after third page break</div>
    </body>
    </html>
    """
    
    from edgar.files.html import Document
    
    # Test with page breaks enabled
    document = Document.parse(test_html, include_page_breaks=True)
    assert document is not None
    
    # Count page break nodes
    page_break_nodes = [node for node in document.nodes if node.type == 'page_break']
    assert len(page_break_nodes) >= 1  # At least one page break should be detected
    
    # Check that page numbers are sequential starting from 0
    page_numbers = [node.page_number for node in page_break_nodes]
    expected_numbers = list(range(0, len(page_break_nodes)))
    assert page_numbers == expected_numbers
    
    # Ensure the first page break is page 0 (document start)
    assert page_numbers[0] == 0
    
    print(f"✓ Detected {len(page_break_nodes)} page breaks with correct numbering: {page_numbers}")






