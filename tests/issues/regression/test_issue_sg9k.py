"""
Regression test for edgartools-sg9k: SGML header parser dropped fields after an
empty-value top-level key.

A top-level SEC-HEADER line that is a key with an empty value (e.g. "CONFIRMING COPY:"
with nothing after the colon) ends with ':' and was misread as a section header (like
"FILER:"). The parser then attached every following top-level field to that pseudo-section
and dropped them — so FILED AS OF DATE / CONFORMED PERIOD OF REPORT were lost and
FilingSGML.filing_date returned None.

Reference: 0000004405-95-000012 (AMCAP FUND INC, N-30D, 1995), reported by M. Gruening.
Parsed here from a synthetic header so the test needs no network.
"""

from edgar.sgml.sgml_header import FilingHeader


# Mirrors the real 0000004405-95-000012 header: an empty-value CONFIRMING COPY line
# sits between CONFORMED SUBMISSION TYPE and the fields that were being dropped.
HEADER_TEXT = """\
ACCESSION NUMBER:\t\t0000004405-95-000012
CONFORMED SUBMISSION TYPE:\tN-30D
CONFIRMING COPY:\t
PUBLIC DOCUMENT COUNT:\t\t1
CONFORMED PERIOD OF REPORT:\t19950831
FILED AS OF DATE:\t\t19951106
SROS:\t\t\tNONE

FILER:

\tCOMPANY DATA:\t
\t\tCOMPANY CONFORMED NAME:\t\t\tAMCAP FUND INC
\t\tCENTRAL INDEX KEY:\t\t\t0000004405
\t\tSTATE OF INCORPORATION:\t\t\tMD
"""


def _header():
    return FilingHeader.parse_from_sgml_text(HEADER_TEXT)


def test_fields_after_empty_value_key_are_not_dropped():
    header = _header()
    # These all appear after the empty-value "CONFIRMING COPY:" line.
    # (Dates are normalized to YYYY-MM-DD by the metadata layer.)
    assert header.filing_date == "1995-11-06"
    assert header.filing_metadata.get("CONFORMED PERIOD OF REPORT") == "1995-08-31"
    assert header.filing_metadata.get("PUBLIC DOCUMENT COUNT") == "1"
    assert header.filing_metadata.get("SROS") == "NONE"


def test_fields_before_empty_value_key_still_parse():
    header = _header()
    assert header.filing_metadata.get("ACCESSION NUMBER") == "0000004405-95-000012"
    assert header.filing_metadata.get("CONFORMED SUBMISSION TYPE") == "N-30D"


def test_real_section_still_parses_as_a_section():
    """The empty-value key must not break genuine sections that follow it."""
    header = _header()
    assert header.filers, "FILER section should still parse"
    assert header.filers[0].company_information.name == "AMCAP FUND INC"
