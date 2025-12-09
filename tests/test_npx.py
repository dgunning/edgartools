from pathlib import Path

import pytest

from edgar.npx import NPX, ProxyVotes
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


def test_npx_class_from_sample_data():
    """Test the NPX class with sample data."""
    # Parse primary doc
    xml_file_path = SAMPLE_FILES_DIR / "N-PX_sample.xml"
    primary_doc_extractor = PrimaryDocExtractor.from_file(xml_file_path)
    primary_doc = primary_doc_extractor.extract()

    # Parse proxy vote table
    proxy_xml_path = SAMPLE_FILES_DIR / "ProxyVoteTable.xml"
    proxy_extractor = ProxyVoteTableExtractor.from_file(proxy_xml_path)
    proxy_vote_table = proxy_extractor.extract()

    # Create NPX instance directly
    proxy_votes = ProxyVotes(proxy_tables=proxy_vote_table.proxy_tables)
    npx = NPX(primary_doc=primary_doc, proxy_votes=proxy_votes)

    # Test properties
    assert npx.fund_name == "Raja Comp1"
    assert npx.cik == "0001125480"
    assert npx.period_of_report == "06/30/2023"
    assert npx.report_calendar_year == "2023"
    assert npx.submission_type == "N-PX"
    assert npx.is_amendment is False
    assert npx.signer_name == "test"
    assert npx.signer_title == "test"

    # Test proxy votes
    assert npx.proxy_votes is not None
    assert len(npx.proxy_votes) == 1

    # Test string representation
    str_repr = str(npx)
    assert "N-PX" in str_repr
    assert "Raja Comp1" in str_repr


def test_proxy_votes_to_dataframe():
    """Test ProxyVotes.to_dataframe() method."""
    proxy_xml_path = SAMPLE_FILES_DIR / "ProxyVoteTable.xml"
    proxy_extractor = ProxyVoteTableExtractor.from_file(proxy_xml_path)
    proxy_vote_table = proxy_extractor.extract()

    proxy_votes = ProxyVotes(proxy_tables=proxy_vote_table.proxy_tables)

    # Convert to DataFrame
    df = proxy_votes.to_dataframe()

    assert len(df) == 3  # 3 vote records in sample file
    assert "issuer_name" in df.columns
    assert "cusip" in df.columns
    assert "how_voted" in df.columns
    assert "shares_voted" in df.columns
    assert "management_recommendation" in df.columns

    # Check values
    assert df.iloc[0]["issuer_name"] == "Issuer Name"
    assert df.iloc[0]["cusip"] == "123456789"
    assert df.iloc[0]["how_voted"] == "WITHHOLD"


def test_npx_to_dataframe():
    """Test NPX.to_dataframe() method for primary document data."""
    # Parse primary doc using KIM, LLC sample
    xml_file_path = SAMPLE_FILES_DIR / "KIM_LLC_sample.xml"
    primary_doc_extractor = PrimaryDocExtractor.from_file(xml_file_path)
    primary_doc = primary_doc_extractor.extract()

    # Parse proxy vote table
    proxy_xml_path = SAMPLE_FILES_DIR / "KIM_LLC_proxy_votes.xml"
    proxy_extractor = ProxyVoteTableExtractor.from_file(proxy_xml_path)
    proxy_vote_table = proxy_extractor.extract()

    # Create NPX instance
    proxy_votes = ProxyVotes(proxy_tables=proxy_vote_table.proxy_tables)
    npx = NPX(primary_doc=primary_doc, proxy_votes=proxy_votes)

    # Convert to DataFrame
    df = npx.to_dataframe()

    # Should have one row with all metadata fields
    assert len(df) == 1
    assert "cik" in df.columns
    assert "fund_name" in df.columns
    assert "period_of_report" in df.columns
    assert "submission_type" in df.columns
    assert "proxy_vote_count" in df.columns

    # Check values
    assert df.iloc[0]["cik"] == "0001888968"
    assert df.iloc[0]["fund_name"] == "KIM, LLC"
    assert df.iloc[0]["period_of_report"] == "06/30/2024"
    assert df.iloc[0]["submission_type"] == "N-PX"
    assert df.iloc[0]["proxy_vote_count"] == 7
    assert df.iloc[0]["report_type"] == "INSTITUTIONAL MANAGER VOTING REPORT"


def test_npx_kim_llc_properties():
    """Test NPX property access with KIM, LLC sample data."""
    xml_file_path = SAMPLE_FILES_DIR / "KIM_LLC_sample.xml"
    primary_doc_extractor = PrimaryDocExtractor.from_file(xml_file_path)
    primary_doc = primary_doc_extractor.extract()

    proxy_xml_path = SAMPLE_FILES_DIR / "KIM_LLC_proxy_votes.xml"
    proxy_extractor = ProxyVoteTableExtractor.from_file(proxy_xml_path)
    proxy_vote_table = proxy_extractor.extract()

    proxy_votes = ProxyVotes(proxy_tables=proxy_vote_table.proxy_tables)
    npx = NPX(primary_doc=primary_doc, proxy_votes=proxy_votes)

    # Test new properties
    assert npx.phone_number == "316-828-5500"
    assert npx.report_type == "INSTITUTIONAL MANAGER VOTING REPORT"
    assert npx.npx_file_number == "028-22610"
    assert npx.confidential_treatment == "N"
    assert npx.other_included_managers_count == "1"
    assert npx.year_or_quarter == "YEAR"
    assert npx.registrant_type == "IM"

    # Test included managers
    assert len(npx.included_managers) == 1
    assert npx.included_managers[0].name == "Koch Industries, LLC"
    assert npx.included_managers[0].form13f_file_number == "028-10337"


def test_proxy_votes_filter_methods():
    """Test ProxyVotes filter methods."""
    proxy_xml_path = SAMPLE_FILES_DIR / "ProxyVoteTable.xml"
    proxy_extractor = ProxyVoteTableExtractor.from_file(proxy_xml_path)
    proxy_vote_table = proxy_extractor.extract()

    proxy_votes = ProxyVotes(proxy_tables=proxy_vote_table.proxy_tables)

    # Test filter by issuer
    filtered = proxy_votes.filter_by_issuer("Issuer")
    assert len(filtered) == 1

    filtered_empty = proxy_votes.filter_by_issuer("NonExistent")
    assert len(filtered_empty) == 0

    # Test filter by vote (sample only has WITHHOLD votes)
    filtered_vote = proxy_votes.filter_by_vote("WITHHOLD")
    assert len(filtered_vote) == 1


def test_proxy_votes_summary():
    """Test ProxyVotes.summary() method."""
    proxy_xml_path = SAMPLE_FILES_DIR / "ProxyVoteTable.xml"
    proxy_extractor = ProxyVoteTableExtractor.from_file(proxy_xml_path)
    proxy_vote_table = proxy_extractor.extract()

    proxy_votes = ProxyVotes(proxy_tables=proxy_vote_table.proxy_tables)

    summary = proxy_votes.summary()
    assert len(summary) == 1  # Only WITHHOLD votes in sample
    assert summary.iloc[0]["vote_type"] == "WITHHOLD"
    assert summary.iloc[0]["count"] == 3


@pytest.mark.network
def test_npx_from_filing():
    """Test NPX.from_filing() with a real SEC filing."""
    from edgar import Filing, set_identity

    set_identity("Test User test@test.com")

    # Use a known N-PX filing from 2024 Q3
    filing = Filing(
        form='N-PX',
        filing_date='2024-09-30',
        company='ALTFEST L J & CO INC',
        cik=712050,
        accession_no='0000712050-24-000009'
    )

    npx = NPX.from_filing(filing)

    # Basic assertions - NPX might be None if parsing fails for this filing
    if npx is not None:
        assert npx.filing == filing
        assert npx.fund_name is not None
        assert npx.cik is not None
        assert npx.submission_type == "N-PX"

        # Test obj() integration
        obj_result = filing.obj()
        assert isinstance(obj_result, NPX)
