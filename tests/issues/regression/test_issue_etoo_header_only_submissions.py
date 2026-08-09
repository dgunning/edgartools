"""
Regression test for edgartools-etoo: pre-2004 header-only SGML submissions.

Reported by Michael Gruening (TU Ilmenau) from a ~7M filing crawl of the
1993-2009 and 2018 archives. Accession 0000950123-96-000525 is a 1.2 KB
submission where EDGAR served the ``.hdr.sgml`` artifact as the submission text
file: a bare ``<SEC-HEADER>`` block with no ``<SEC-DOCUMENT>`` wrapper and no
document body at all.

Two distinct defects sat behind it:

1. ``SGMLParser.detect_format`` recognised only ``<SUBMISSION>``,
   ``<SEC-DOCUMENT>``, ``<IMS-DOCUMENT>`` and a leading ``<DOCUMENT>``, so this
   content raised ``ValueError("Unknown SGML format")``.

2. The filer of a Schedule 13D/G arrives under ``FILED-BY``, not ``FILER``, and
   ``parse_submission_format_header`` only ever read ``FILER``. The header
   therefore parsed to zero filers and a ``None`` cik *without raising* - the
   more dangerous failure, because a bulk crawl records it as a success.

The dialect check is load-bearing and gets its own test below: a ``<SEC-HEADER>``
root can introduce either the hyphenated tag dialect or the tab-indented "space"
dialect, and SubmissionFormatParser silently yields an empty header when handed
the latter.

No network access required - the fixture is the verbatim submission.
"""
import pytest

from edgar.sgml import FilingSGML
from edgar.sgml.sgml_parser import SGMLFormatType, SGMLParser

# Verbatim content of https://www.sec.gov/Archives/edgar/data/789920/0000950123-96-000525.txt
HEADER_ONLY_1996 = """<SEC-HEADER>0000950123-96-000525.hdr.sgml : 19960213
<ACCESSION-NUMBER>0000950123-96-000525
<TYPE>SC 13G/A
<PUBLIC-DOCUMENT-COUNT>1
<FILING-DATE>19960212
<SROS>NYSE
<SUBJECT-COMPANY>
<COMPANY-DATA>
<CONFORMED-NAME>MCKESSON CORP
<CIK>0000927653
<ASSIGNED-SIC>5122
<IRS-NUMBER>943207296
<STATE-OF-INCORPORATION>DE
<FISCAL-YEAR-END>0331
</COMPANY-DATA>
<FILING-VALUES>
<FORM-TYPE>SC 13G/A
<ACT>34
<FILE-NUMBER>005-44207
<FILM-NUMBER>96515429
</FILING-VALUES>
<BUSINESS-ADDRESS>
<STREET1>ONE POST ST
<CITY>SAN FRANCISCO
<STATE>CA
<ZIP>94104
<PHONE>4159838300
</BUSINESS-ADDRESS>
<FORMER-COMPANY>
<FORMER-CONFORMED-NAME>SP VENTURES INC
<DATE-CHANGED>19940728
</FORMER-COMPANY>
</SUBJECT-COMPANY>
<FILED-BY>
<COMPANY-DATA>
<CONFORMED-NAME>CHIEFTAIN CAPITAL MANAGEMENT INC
<CIK>0000789920
<ASSIGNED-SIC>0000
<IRS-NUMBER>133194313
<STATE-OF-INCORPORATION>NY
<FISCAL-YEAR-END>1231
</COMPANY-DATA>
<FILING-VALUES>
<FORM-TYPE>SC 13G/A
</FILING-VALUES>
<BUSINESS-ADDRESS>
<STREET1>12 EAST 49TH ST
<CITY>NEW YORK
<STATE>NY
<ZIP>10017
<PHONE>2124219760
</BUSINESS-ADDRESS>
<MAIL-ADDRESS>
<STREET1>C/O NATHAN & BRECHER LLP
<STREET2>100 PARK AVENUE 22ND FLOOR
<CITY>NEW YORK
<STATE>NY
<ZIP>10017
</MAIL-ADDRESS>
</FILED-BY>
</SEC-HEADER>
"""

# The same era in the "space" dialect, rooted at <SEC-HEADER> with no
# <SEC-DOCUMENT> wrapper. Derived from 0000950123-96-000524.
HEADER_ONLY_SPACE_DIALECT = """<SEC-HEADER>0000950123-96-000524.hdr.sgml : 19960213
ACCESSION NUMBER:\t\t0000950123-96-000524
CONFORMED SUBMISSION TYPE:\tSC 13G/A
PUBLIC DOCUMENT COUNT:\t\t1
FILED AS OF DATE:\t\t19960212
SROS:\t\t\tNYSE

SUBJECT COMPANY:

\tCOMPANY DATA:
\t\tCOMPANY CONFORMED NAME:\t\t\tTIDEWATER INC
\t\tCENTRAL INDEX KEY:\t\t\t0000098222
\t\tSTANDARD INDUSTRIAL CLASSIFICATION:\tWATER TRANSPORTATION [4400]
\t\tIRS NUMBER:\t\t\t\t720487776
\t\tSTATE OF INCORPORATION:\t\t\tDE
\t\tFISCAL YEAR END:\t\t\t0331
</SEC-HEADER>
"""


@pytest.fixture(scope="module")
def sgml():
    return FilingSGML.from_text(HEADER_ONLY_1996)


class TestHeaderOnlySubmissionParses:
    """A bare <SEC-HEADER> submission must parse instead of raising."""

    def test_from_text_does_not_raise(self):
        """The original crash: ValueError("Unknown SGML format").

        Deliberately does not use the module fixture. The fixture is built once
        at collection, so a test that takes it and asserts `is not None` cannot
        fail for the reason it is named after -- the raise would surface as an
        error in every other test in the file, and this one would never run.
        Calling from_text here is what makes the claim testable, and the
        accession proves the returned object came from THIS content.
        """
        sgml = FilingSGML.from_text(HEADER_ONLY_1996)
        assert sgml.header.accession_number == "0000950123-96-000525"

    def test_detected_as_submission_format(self):
        assert SGMLParser.detect_format(HEADER_ONLY_1996) == SGMLFormatType.SUBMISSION

    def test_no_documents(self, sgml):
        assert sgml.header.document_count == 1  # what the header claims
        # ...but the submission carries no document body, so there is no text.
        assert sgml.text() is None


class TestHeaderFieldsAreGroundTruth:
    """Values asserted against the verbatim 1996 submission, not just non-None."""

    def test_filing_metadata(self, sgml):
        header = sgml.header
        assert header.accession_number == "0000950123-96-000525"
        assert header.form == "SC 13G/A"
        assert str(header.filing_date) == "1996-02-12"

    def test_header_is_not_silently_empty(self, sgml):
        assert not sgml.header.is_empty()

    def test_filed_by_populates_the_filer(self, sgml):
        """The regression: SC 13G/A files under FILED-BY, not FILER."""
        filers = sgml.header.filers
        assert len(filers) == 1
        company = filers[0].company_information
        assert company.name == "CHIEFTAIN CAPITAL MANAGEMENT INC"
        assert company.cik == "0000789920"
        assert company.irs_number == "133194313"
        assert company.state_of_incorporation == "NY"

    def test_cik_resolves_from_filed_by(self, sgml):
        """cik falls back to the first filer; it was None while FILED-BY was ignored."""
        assert sgml.header.cik == 789920

    def test_filer_addresses(self, sgml):
        filer = sgml.header.filers[0]
        assert filer.business_address.street1 == "12 EAST 49TH ST"
        assert filer.business_address.city == "NEW YORK"
        assert filer.business_address.zipcode == "10017"
        assert filer.mailing_address.street1 == "C/O NATHAN & BRECHER LLP"
        assert filer.mailing_address.street2 == "100 PARK AVENUE 22ND FLOOR"

    def test_subject_company(self, sgml):
        subjects = sgml.header.subject_companies
        assert len(subjects) == 1
        company = subjects[0].company_information
        assert company.name == "MCKESSON CORP"
        assert company.cik == "0000927653"
        assert company.irs_number == "943207296"

    def test_assigned_sic_is_read(self, sgml):
        """Pre-2004 headers name the field ASSIGNED-SIC, not
        STANDARD-INDUSTRIAL-CLASSIFICATION; sic was silently None before."""
        assert sgml.header.subject_companies[0].company_information.sic == "5122"


class TestDialectRoutingIsNotSilent:
    """A <SEC-HEADER> root can carry either dialect. Misrouting the space
    dialect into SubmissionFormatParser yields an empty header with no error,
    which is exactly the failure mode this fix exists to prevent."""

    def test_space_dialect_routes_to_sec_document_parser(self):
        assert SGMLParser.detect_format(
            HEADER_ONLY_SPACE_DIALECT) == SGMLFormatType.SEC_DOCUMENT

    def test_space_dialect_header_is_populated(self):
        header = FilingSGML.from_text(HEADER_ONLY_SPACE_DIALECT).header
        assert not header.is_empty()
        assert header.accession_number == "0000950123-96-000524"
        assert header.form == "SC 13G/A"
        assert header.subject_companies[0].company_information.name == "TIDEWATER INC"
