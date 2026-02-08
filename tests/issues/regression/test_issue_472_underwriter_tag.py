"""
Regression test for Issue #472: SGML parser fails on UNDERWRITER tag

GitHub Issue: https://github.com/dgunning/edgartools/issues/472

Problem:
- The SGML parser didn't include 'UNDERWRITER' in SECTION_TAGS
- This caused parsing failures in _handle_section_end when encountering UNDERWRITER sections
- Common in registration statements (S-1, S-3, ABS-15G) with underwriter information

Root Cause:
- edgar/sgml/sgml_parser.py SubmissionFormatParser.SECTION_TAGS missing 'UNDERWRITER'
- UNDERWRITER is a valid section tag like FILER, DEPOSITOR, SECURITIZER

Fix:
- Added 'UNDERWRITER' to SECTION_TAGS set
- Added 'UNDERWRITER' to REPEATABLE_TAGS (underwriting syndicates can have multiple underwriters)
- Now handles single or multiple UNDERWRITER sections correctly

User Impact:
- Enables parsing of registration statements with underwriter information
- Supports IPO/offering analysis and underwriter identification
"""
import pytest
from edgar.httprequests import download_text
from edgar.sgml.sgml_parser import SGMLParser


@pytest.mark.network
@pytest.mark.slow
def test_issue_472_underwriter_tag_parsing():
    """
    Test that SGML parser successfully handles UNDERWRITER tag without crashing.

    The actual filing from Issue #472 uses SEC-DOCUMENT format which doesn't parse
    header structure. This test verifies the parser doesn't crash when encountering
    UNDERWRITER tags in the header text.

    https://www.sec.gov/Archives/edgar/data/315030/000153949725002648/0001539497-25-002648.txt
    """
    # Download the filing that contains UNDERWRITER tag
    url = "https://www.sec.gov/Archives/edgar/data/315030/000153949725002648/0001539497-25-002648.txt"
    content = download_text(url)

    # This should not raise ValueError about mismatched tags
    parser = SGMLParser()
    parsed_data = parser.parse(content)

    # Verify parsing succeeded (basic structure)
    assert parsed_data is not None
    assert 'header' in parsed_data
    assert 'documents' in parsed_data

    # Verify UNDERWRITER appears in header text (SEC-DOCUMENT format stores raw header)
    assert 'UNDERWRITER' in parsed_data['header']
    assert 'Citigroup Global Markets Inc.' in parsed_data['header']


@pytest.mark.fast
def test_issue_472_underwriter_in_section_tags():
    """
    Verify UNDERWRITER is included in SECTION_TAGS.

    This is a simple unit test to prevent regression.
    """
    from edgar.sgml.sgml_parser import _SECTION_TAGS, _REPEATABLE_TAGS

    # Verify UNDERWRITER is in SECTION_TAGS
    assert 'UNDERWRITER' in _SECTION_TAGS

    # Verify UNDERWRITER is in REPEATABLE_TAGS (for multiple underwriters)
    assert 'UNDERWRITER' in _REPEATABLE_TAGS


@pytest.mark.fast
def test_issue_472_multiple_underwriters_structure():
    """
    Test that parser can handle multiple UNDERWRITER sections.

    This test uses synthetic SGML to verify repeatability handling.
    """
    from edgar.sgml.sgml_parser import SubmissionFormatParser

    # Synthetic SGML with multiple UNDERWRITER sections
    sgml_content = """<SUBMISSION>
<ACCESSION-NUMBER>0001234567-25-000001
<CONFORMED-SUBMISSION-TYPE>S-1

<UNDERWRITER>
<COMPANY-DATA>
<COMPANY-CONFORMED-NAME>Lead Underwriter LLC
<CENTRAL-INDEX-KEY>0000111111
</COMPANY-DATA>
</UNDERWRITER>

<UNDERWRITER>
<COMPANY-DATA>
<COMPANY-CONFORMED-NAME>Co-Manager Inc
<CENTRAL-INDEX-KEY>0000222222
</COMPANY-DATA>
</UNDERWRITER>

<DOCUMENT>
<TYPE>S-1
<SEQUENCE>1
<FILENAME>form.txt
<DESCRIPTION>Registration Statement
<TEXT>
Filing content here
</TEXT>
</DOCUMENT>
</SUBMISSION>"""

    parser = SubmissionFormatParser()
    parsed = parser.parse(sgml_content)

    # Verify both underwriters were parsed
    assert 'UNDERWRITER' in parsed
    underwriters = parsed['UNDERWRITER']
    assert isinstance(underwriters, list)
    assert len(underwriters) == 2

    # Verify first underwriter
    assert underwriters[0]['COMPANY-DATA']['COMPANY-CONFORMED-NAME'] == 'Lead Underwriter LLC'
    assert underwriters[0]['COMPANY-DATA']['CENTRAL-INDEX-KEY'] == '0000111111'

    # Verify second underwriter
    assert underwriters[1]['COMPANY-DATA']['COMPANY-CONFORMED-NAME'] == 'Co-Manager Inc'
    assert underwriters[1]['COMPANY-DATA']['CENTRAL-INDEX-KEY'] == '0000222222'
