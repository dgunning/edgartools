from pathlib import Path
from edgar.npx.parsing import PrimaryDocExtractor, ProxyVoteTableExtractor

# Define the path to the sample files
SAMPLE_FILES_DIR = (
    Path(__file__).parent.parent / "data" / "NPX" / "EDGAR Form N-PX XML Samples"
)


def test_npx_sample_extraction():
    """Test extraction from a sample N-PX filing."""
    xml_file_path = SAMPLE_FILES_DIR / "N-PX_sample.xml"
    extractor = PrimaryDocExtractor.from_file(xml_file_path)
    primary_doc = extractor.extract()

    assert primary_doc.cik == "0001125480"
    assert primary_doc.submission_type == "N-PX"
    assert primary_doc.fund_name == "Raja Comp1"
    assert primary_doc.street1 == "BUSINESS STREET 1"
    assert primary_doc.city == "GERMANCITY"
    assert primary_doc.state == "CA"
    assert primary_doc.zip_code == "210105"
    assert primary_doc.period_of_report == "06/30/2023"
    assert primary_doc.report_calendar_year == "2023"
    assert primary_doc.signer_name == "test"
    assert primary_doc.signer_title == "test"
    assert primary_doc.signature_date == "05/15/2024"
    assert primary_doc.other_included_managers_count == "0"
    assert not primary_doc.included_managers


def test_proxy_vote_table_extraction():
    """Test extraction from a sample Proxy Vote Table XML."""
    xml_file_path = SAMPLE_FILES_DIR / "ProxyVoteTable.xml"
    extractor = ProxyVoteTableExtractor.from_file(xml_file_path)
    proxy_vote_table = extractor.extract()

    assert len(proxy_vote_table.proxy_tables) == 1
    table = proxy_vote_table.proxy_tables[0]
    assert table.issuer_name == "Issuer Name"
    assert table.cusip == "123456789"
    assert table.meeting_date == "10/11/2022"
    assert table.shares_voted == 1.0
    assert len(table.vote_records) == 3
    assert table.vote_records[0].how_voted == "WITHHOLD"
    assert table.vote_records[0].shares_voted == 1.0
    assert table.vote_records[0].management_recommendation == "AGAINST"


def test_npx_amendment_extraction():
    """Test extraction from a sample N-PX/A amendment filing."""
    xml_file_path = SAMPLE_FILES_DIR / "N-PX_A.xml"
    extractor = PrimaryDocExtractor.from_file(xml_file_path)
    primary_doc = extractor.extract()

    assert primary_doc.submission_type == "N-PX/A"
    assert primary_doc.is_amendment is True
    assert primary_doc.amendment_no == "1"
    assert primary_doc.cik == "0000350001"
    assert primary_doc.fund_name == "BIG FUND TRUST inc"
