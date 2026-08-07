"""
Regression test for edgartools-nzfp: stale subheader corrupts flat KEY: value
sections in SGML filing headers.

`FilingHeader.parse_from_sgml_text` never reset `current_subheader` when a new
top-level header section started. Some filings from the 1999-2005 era mix a
properly nested section (e.g. "FILER:" with a "MAIL ADDRESS:" subsection) with
a later top-level section that has no subheader of its own and just flat
"KEY: value" lines (e.g. a bare "COMPANY DATA:" section). Because
`current_subheader` still held "MAIL ADDRESS" from the previous section, the
flat lines were routed through `data[current_header][-1][current_subheader]`,
which raised a KeyError (the new section's dict has no "MAIL ADDRESS" key),
silently dropping the data behind a
"Subheader 'MAIL ADDRESS' not found in header 'COMPANY DATA'" warning.

No network access required - this is a synthetic header reproducing the exact
mechanism.
"""
import logging

from edgar.sgml.sgml_header import FilingHeader

# A FILER section with a legitimate nested MAIL ADDRESS subsection, followed by
# a second, malformed top-level COMPANY DATA section with no subheader of its
# own - just flat KEY: value lines. Pre-fix, current_subheader ("MAIL ADDRESS")
# leaked from the FILER section into the second COMPANY DATA section.
HEADER_TEXT = """ACCESSION NUMBER:\t\t0000000000-99-000000
CONFORMED SUBMISSION TYPE:\tSC 13D
FILER:
\tCOMPANY DATA:
\t\tCOMPANY CONFORMED NAME:\tACME CORP
\tMAIL ADDRESS:
\t\tSTREET 1:\t123 MAIN ST
\t\tCITY:\tNEW YORK
COMPANY DATA:
\tSTREET 1:\t999 SECOND AVE
\tCITY:\tBOSTON
"""


class TestStaleSubheaderNoLongerDropsData:
    def test_no_subheader_warning_is_emitted(self, caplog):
        with caplog.at_level(logging.WARNING, logger="edgar.core"):
            FilingHeader.parse_from_sgml_text(HEADER_TEXT)

        subheader_warnings = [
            record.message for record in caplog.records if "Subheader" in record.message
        ]
        assert subheader_warnings == []

    def test_flat_second_section_values_are_captured(self):
        # _tokenize_header is the same state machine parse_from_sgml_text uses
        # internally (extracted for testability); it exposes the raw parsed
        # dict, including top-level sections like a malformed "COMPANY DATA:"
        # that aren't surfaced through any of FilingHeader's public dataclasses.
        data = FilingHeader._tokenize_header(HEADER_TEXT)

        # Before the fix this section was silently dropped (KeyError swallowed
        # behind a warning); it must now retain its flat key/value pairs.
        assert data["COMPANY DATA"] == [
            {"STREET 1": "999 SECOND AVE", "CITY": "BOSTON"}
        ]

    def test_legitimate_nested_filer_mail_address_still_parses(self):
        header = FilingHeader.parse_from_sgml_text(HEADER_TEXT)

        assert len(header.filers) == 1
        filer = header.filers[0]
        assert filer.company_information.name == "ACME CORP"
        assert filer.mailing_address.street1 == "123 MAIN ST"
        assert filer.mailing_address.city == "NEW YORK"
