"""Regression test for edgartools-preg / GH #872.

Expose the 13F amendment type (RESTATEMENT vs NEW HOLDINGS) on ``ThirteenF``.

The distinction is load-bearing for correctness: a ``NEW HOLDINGS`` amendment
adds only previously-confidential positions and must be *unioned* with the
original filing, whereas a ``RESTATEMENT`` *replaces* it. A pipeline that blindly
supersedes "the original by its /A" silently drops the real portfolio when the
amendment is ``NEW HOLDINGS``.

https://github.com/dgunning/edgartools/issues/872
"""
import pytest

from edgar import Filing
from edgar.thirteenf import AmendmentInfo, parse_primary_document_xml


def _primary_doc_xml(cover_page_extra: str) -> str:
    """Build a minimal 13F primary document with custom cover-page content."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<edgarSubmission xmlns:com="http://www.sec.gov/edgar/common" xmlns="http://www.sec.gov/edgar/thirteenffiler">
  <headerData>
    <filerInfo>
      <periodOfReport>03-31-2025</periodOfReport>
    </filerInfo>
  </headerData>
  <formData>
    <coverPage>
      <reportCalendarOrQuarter>03-31-2025</reportCalendarOrQuarter>
      {cover_page_extra}
      <filingManager>
        <name>TEST MANAGER LLC</name>
        <address>
          <com:street1>1 Main St</com:street1>
          <com:city>Omaha</com:city>
          <com:stateOrCountry>NE</com:stateOrCountry>
          <com:zipCode>68131</com:zipCode>
        </address>
      </filingManager>
      <reportType>13F HOLDINGS REPORT</reportType>
    </coverPage>
    <signatureBlock>
      <name>Jane Doe</name>
      <title>CIO</title>
      <phone>555-1212</phone>
      <signature>/s/ Jane Doe</signature>
      <city>Omaha</city>
      <stateOrCountry>NE</stateOrCountry>
      <signatureDate>05-15-2025</signatureDate>
    </signatureBlock>
  </formData>
</edgarSubmission>"""


def test_non_amendment_has_no_amendment_metadata():
    """A plain 13F-HR cover page yields is_amendment=False and no amendment type."""
    doc = parse_primary_document_xml(_primary_doc_xml("<isAmendment>false</isAmendment>"))
    cover = doc.cover_page
    assert cover.is_amendment is False
    assert cover.amendment_number is None
    assert cover.amendment_info is None


def test_new_holdings_amendment_parsed():
    """NEW HOLDINGS amendment exposes the type and confidential-treatment fields."""
    extra = """
      <isAmendment>true</isAmendment>
      <amendmentNo>1</amendmentNo>
      <amendmentInfo>
        <amendmentType>NEW HOLDINGS</amendmentType>
        <confDeniedExpired>true</confDeniedExpired>
        <dateDeniedExpired>08-14-2025</dateDeniedExpired>
        <dateReported>05-15-2025</dateReported>
        <reasonForNonConfidentiality>Confidential Treatment Expired</reasonForNonConfidentiality>
      </amendmentInfo>"""
    cover = parse_primary_document_xml(_primary_doc_xml(extra)).cover_page
    assert cover.is_amendment is True
    assert cover.amendment_number == 1
    assert isinstance(cover.amendment_info, AmendmentInfo)
    assert cover.amendment_info.amendment_type == "NEW HOLDINGS"
    assert cover.amendment_info.conf_denied_expired is True
    assert cover.amendment_info.date_denied_expired == "08-14-2025"
    assert cover.amendment_info.reason_for_non_confidentiality == "Confidential Treatment Expired"


def test_restatement_amendment_parsed():
    """RESTATEMENT amendment exposes the type (the 'replaces original' case)."""
    extra = """
      <isAmendment>true</isAmendment>
      <amendmentNo>2</amendmentNo>
      <amendmentInfo>
        <amendmentType>RESTATEMENT</amendmentType>
      </amendmentInfo>"""
    cover = parse_primary_document_xml(_primary_doc_xml(extra)).cover_page
    assert cover.is_amendment is True
    assert cover.amendment_number == 2
    assert cover.amendment_info.amendment_type == "RESTATEMENT"
    assert cover.amendment_info.conf_denied_expired is None


@pytest.mark.network
def test_berkshire_new_holdings_union_ground_truth():
    """Ground truth (GH #872): Berkshire 2025-Q1.

    Original 13F-HR = 110 holdings; the 13F-HR/A is NEW HOLDINGS with 4 holdings.
    Correct "current holdings" is the union (114), NOT the 4-holding amendment.
    """
    original = Filing(
        form="13F-HR", filing_date="2025-05-15", company="Berkshire Hathaway Inc",
        cik=1067983, accession_no="0000950123-25-005701",
    ).obj()
    assert original.is_amendment is False
    assert original.amendment_type is None
    assert original.amendment_number is None
    assert original.total_holdings == 110

    amendment = Filing(
        form="13F-HR/A", filing_date="2025-08-14", company="Berkshire Hathaway Inc",
        cik=1067983, accession_no="0000950123-25-008361",
    ).obj()
    assert amendment.is_amendment is True
    assert amendment.amendment_type == "NEW HOLDINGS"
    assert amendment.amendment_number == 1
    assert amendment.total_holdings == 4
    assert amendment.amendment_info.conf_denied_expired is True

    # The load-bearing correctness fact: union, not supersede.
    assert original.total_holdings + amendment.total_holdings == 114
