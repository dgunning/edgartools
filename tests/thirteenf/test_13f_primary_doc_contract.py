"""What `parse_primary_document_xml` owes its callers, with no network.

`edgar/thirteenf/parsers/primary_xml.py` moved from BeautifulSoup to lxml under
edgartools-07lk.11.3. It is the unit most exposed to the migration's signature
failure, because 13F primary documents are NAMESPACED — they declare
`xmlns="http://www.sec.gov/edgar/thirteenffiler"` plus a second namespace for
`com:` elements — and a plain lxml `.//coverPage` matches nothing at all in such
a document. Not an error: an empty result, several frames from where it would be
noticed.

`tests/test_thirteenf.py` is classified `network` in `tests/conftest.py`, and so
are the #523 other-manager regressions (they resolve a filing over the wire), so
none of this had offline coverage. Every case here reads a checked-in fixture or
an inline string.

Ground truth is MetLife's Q4 2021 13F combination report, checked in at
`data/metlife.13F-HR.primarydoc.xml`.
"""
from datetime import datetime
from pathlib import Path

import pytest

from edgar.thirteenf.parsers.primary_xml import parse_primary_document_xml

METLIFE = Path('data/metlife.13F-HR.primarydoc.xml')

# The namespace declaration is the whole point of this file, so it is written out
# once here rather than being implied by a fixture.
THIRTEENF_NS = ('xmlns:com="http://www.sec.gov/edgar/common" '
                'xmlns="http://www.sec.gov/edgar/thirteenffiler"')


def _document(cover_extra: str = "", summary: str = "") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<edgarSubmission {THIRTEENF_NS}>
  <headerData><filerInfo><periodOfReport>12-31-2024</periodOfReport></filerInfo></headerData>
  <formData>
    <coverPage>
      <reportCalendarOrQuarter>12-31-2024</reportCalendarOrQuarter>
      <reportType>13F HOLDINGS REPORT</reportType>
      <filingManager>
        <name>Example Capital LLC</name>
        <address><com:street1>1 Main St</com:street1><com:city>Boston</com:city>
                 <com:stateOrCountry>MA</com:stateOrCountry><com:zipCode>02110</com:zipCode></address>
      </filingManager>
      {cover_extra}
    </coverPage>
    {summary}
    <signatureBlock><name>Pat Lee</name><title>CFO</title><city>Boston</city>
      <stateOrCountry>MA</stateOrCountry><signatureDate>02-14-2025</signatureDate></signatureBlock>
  </formData>
</edgarSubmission>"""


@pytest.fixture(scope="module")
def metlife():
    return parse_primary_document_xml(METLIFE.read_text())


def test_a_real_namespaced_filing_reads_every_section(metlife):
    """MetLife's Q4 2021 combination report, by value.

    Header, cover page, filing manager, address, summary page and signature block
    each come from a different depth of the document, so a namespace fault would
    have to be very selective to leave any of them intact.
    """
    assert metlife.report_period == datetime(2021, 12, 31)
    assert metlife.cover_page.report_calendar_or_quarter == "12-31-2021"
    assert metlife.cover_page.report_type == "13F COMBINATION REPORT"
    assert metlife.cover_page.is_amendment is False

    manager = metlife.cover_page.filing_manager
    assert manager.name == "METLIFE INC"
    assert manager.address.street1 == "200 PARK AVENUE"
    assert manager.address.city == "NEW YORK"
    assert manager.address.state_or_country == "NY"
    assert manager.address.zipcode == "10166"

    assert metlife.summary_page.total_holdings == 6
    assert metlife.summary_page.total_value == 11019796
    assert metlife.summary_page.other_included_managers_count == 0

    assert metlife.signature.name == "Steven Goulart"
    assert metlife.signature.title == "EVP & Chief Investment Officer"
    assert metlife.signature.phone == "973-355-4814"
    assert metlife.signature.city == "WHIPPANY"
    assert metlife.signature.date == "03-22-2023"

    assert "MetLife, Inc. is the parent holding company" in metlife.additional_information


def test_the_address_is_read_from_a_second_namespace(metlife):
    """The address fields are `com:` elements while their parent is in the filer
    namespace, so the parent's-namespace shortcut is the wrong guess for them and
    only a local-name match finds them. This is the one 13F document shape that
    defeats the fast path in `xmltools`."""
    assert "<com:street1>" in METLIFE.read_text()
    assert metlife.cover_page.filing_manager.address.street1 == "200 PARK AVENUE"


def test_other_managers_are_read_from_the_summary_page():
    """Issue #523's path, which had no offline coverage. Two levels of nesting
    below `<summaryPage>`, all of it namespaced."""
    document = parse_primary_document_xml(_document(summary="""
    <summaryPage>
      <otherIncludedManagersCount>2</otherIncludedManagersCount>
      <tableEntryTotal>40</tableEntryTotal>
      <tableValueTotal>123456</tableValueTotal>
      <otherManagers2Info>
        <otherManager2><sequenceNumber>1</sequenceNumber>
          <otherManager><cik>0000111111</cik><name>First Adviser</name>
            <form13FFileNumber>028-11111</form13FFileNumber></otherManager></otherManager2>
        <otherManager2><sequenceNumber>2</sequenceNumber>
          <otherManager><cik>0000222222</cik><name>Second Adviser</name>
            <form13FFileNumber>028-22222</form13FFileNumber></otherManager></otherManager2>
      </otherManagers2Info>
    </summaryPage>"""))

    assert document.summary_page.total_holdings == 40
    assert document.summary_page.total_value == 123456
    assert [(m.sequence_number, m.cik, m.name, m.file_number)
            for m in document.summary_page.other_managers] == [
        (1, "0000111111", "First Adviser", "028-11111"),
        (2, "0000222222", "Second Adviser", "028-22222")]


def test_amendment_metadata_is_read():
    """Issue #872's path. RESTATEMENT replaces the original filing while NEW
    HOLDINGS is unioned with it, so losing `amendment_type` silently would change
    which holdings a caller ends up with."""
    document = parse_primary_document_xml(_document(cover_extra="""
      <isAmendment>true</isAmendment>
      <amendmentNo>2</amendmentNo>
      <amendmentInfo><amendmentType>NEW HOLDINGS</amendmentType>
        <confDeniedExpired>true</confDeniedExpired>
        <dateDeniedExpired>01-15-2025</dateDeniedExpired>
        <dateReported>11-14-2024</dateReported></amendmentInfo>"""))

    assert document.cover_page.is_amendment is True
    assert document.cover_page.amendment_number == 2
    assert document.cover_page.amendment_info.amendment_type == "NEW HOLDINGS"
    assert document.cover_page.amendment_info.conf_denied_expired is True
    assert document.cover_page.amendment_info.date_denied_expired == "01-15-2025"
    assert document.cover_page.amendment_info.date_reported == "11-14-2024"


def test_a_document_with_no_summary_page_still_parses():
    """A 13F-NT reports no holdings and carries no `<summaryPage>` at all, which
    is the branch a truthiness guard would also take for one that is merely
    empty."""
    document = parse_primary_document_xml(_document())

    assert document.summary_page.total_holdings == 0
    assert document.summary_page.total_value == 0
    assert document.summary_page.other_managers is None
    assert document.cover_page.filing_manager.name == "Example Capital LLC"


def test_parse_rejects_a_document_that_is_not_an_edgar_submission():
    with pytest.raises(ValueError, match="edgarSubmission"):
        parse_primary_document_xml("<?xml version='1.0'?><ownershipDocument><a/></ownershipDocument>")


def test_a_missing_required_section_still_names_itself():
    """The guards raise rather than returning a half-built document. They read
    `is not None` now, because a `<formData/>` with no children is falsy on lxml
    and truthy on bs4 — and the message has to stay the one the caller reads."""
    with pytest.raises(ValueError, match="formData"):
        parse_primary_document_xml(
            f"<?xml version='1.0'?><edgarSubmission {THIRTEENF_NS}>"
            "<headerData><filerInfo><periodOfReport>12-31-2024</periodOfReport>"
            "</filerInfo></headerData></edgarSubmission>")
