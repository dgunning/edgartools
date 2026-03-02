"""
Regression test for Issue #477: SGML parser fails on ITEM and RULE tags

GitHub Issue: https://github.com/dgunning/edgartools/issues/477

Problem:
- The SGML parser didn't include 'ITEM' and 'RULE' in SECTION_TAGS
- This caused parsing failures in _handle_section_end when encountering ITEM/RULE sections
- Common in SD (Specialized Disclosure) filings related to conflict minerals reporting

Root Cause:
- edgar/sgml/sgml_parser.py SubmissionFormatParser.SECTION_TAGS missing 'ITEM' and 'RULE'
- ITEM and RULE are valid section tags in SD filings

Fix:
- Added 'ITEM' and 'RULE' to SECTION_TAGS set
- Added 'ITEM' to REPEATABLE_TAGS (SD filings can have multiple ITEM sections)
- Now handles SD filing headers with RULE and ITEM sections correctly

User Impact:
- Enables parsing of SD filings with conflict minerals reporting
- Supports ESG analysis and supply chain transparency reporting
"""
import pytest
from edgar.httprequests import download_text
from edgar.sgml.sgml_parser import SGMLParser


@pytest.mark.network
@pytest.mark.slow
def test_issue_477_item_rule_tag_parsing():
    """
    Test that SGML parser successfully handles ITEM and RULE tags in SD filings.

    The SD filing from Issue #477 contains RULE and ITEM tags in the header.
    This test verifies the parser doesn't crash when encountering these tags.

    https://www.sec.gov/Archives/edgar/data/91142/000009114225000079/0000091142-25-000079.txt
    """
    # Download the SD filing that contains ITEM and RULE tags
    url = "https://www.sec.gov/Archives/edgar/data/91142/000009114225000079/0000091142-25-000079.txt"
    content = download_text(url)

    # This should not raise ValueError about mismatched tags
    parser = SGMLParser()
    parsed_data = parser.parse(content)

    # Verify parsing succeeded (basic structure)
    assert parsed_data is not None
    assert 'header' in parsed_data
    assert 'documents' in parsed_data

    # Verify ITEM and RULE appear in header text (SEC-DOCUMENT format stores raw header)
    assert 'RULE' in parsed_data['header']
    assert 'ITEM' in parsed_data['header']
    assert '13p-1' in parsed_data['header']  # Rule name
    assert '1.01' in parsed_data['header']  # Item number
    assert '1.02' in parsed_data['header']  # Item number


@pytest.mark.fast
def test_issue_477_item_rule_in_section_tags():
    """
    Verify ITEM and RULE are included in SECTION_TAGS.

    This is a simple unit test to prevent regression.
    """
    from edgar.sgml.sgml_parser import _SECTION_TAGS, _REPEATABLE_TAGS

    # Verify ITEM and RULE are in SECTION_TAGS
    assert 'ITEM' in _SECTION_TAGS
    assert 'RULE' in _SECTION_TAGS

    # Verify ITEM is in REPEATABLE_TAGS (for multiple items)
    assert 'ITEM' in _REPEATABLE_TAGS


@pytest.mark.fast
def test_issue_477_multiple_items_structure():
    """
    Test that parser can handle multiple ITEM sections within RULE.

    This test uses synthetic SGML to verify repeatability handling.
    """
    from edgar.sgml.sgml_parser import SubmissionFormatParser

    # Synthetic SGML with RULE and multiple ITEM sections (based on actual SD filing structure)
    sgml_content = """<SUBMISSION>
<ACCESSION-NUMBER>0000091142-25-000079
<CONFORMED-SUBMISSION-TYPE>SD

<RULE>
<RULE-NAME>13p-1
<ITEM>
<ITEM-NUMBER>1.01
<ITEM-PERIOD>20241231
</ITEM>
<ITEM>
<ITEM-NUMBER>1.02
<ITEM-PERIOD>20241231
</ITEM>
</RULE>

<FILER>
<COMPANY-DATA>
<COMPANY-CONFORMED-NAME>SMITH A O CORP
<CENTRAL-INDEX-KEY>0000091142
</COMPANY-DATA>
</FILER>

<DOCUMENT>
<TYPE>SD
<SEQUENCE>1
<FILENAME>filing.htm
<DESCRIPTION>Specialized Disclosure Report
<TEXT>
Filing content here
</TEXT>
</DOCUMENT>
</SUBMISSION>"""

    parser = SubmissionFormatParser()
    parsed = parser.parse(sgml_content)

    # Verify RULE section was parsed
    assert 'RULE' in parsed
    rule_section = parsed['RULE']
    assert isinstance(rule_section, dict)
    assert rule_section['RULE-NAME'] == '13p-1'

    # Verify both ITEM sections were parsed as a list
    assert 'ITEM' in rule_section
    items = rule_section['ITEM']
    assert isinstance(items, list)
    assert len(items) == 2

    # Verify first item
    assert items[0]['ITEM-NUMBER'] == '1.01'
    assert items[0]['ITEM-PERIOD'] == '20241231'

    # Verify second item
    assert items[1]['ITEM-NUMBER'] == '1.02'
    assert items[1]['ITEM-PERIOD'] == '20241231'


@pytest.mark.fast
def test_issue_477_sd_filing_structure():
    """
    Test comprehensive SD filing structure with all expected tags.

    This ensures the parser handles the complete SD filing format correctly.
    """
    from edgar.sgml.sgml_parser import SubmissionFormatParser

    sgml_content = """<SUBMISSION>
<ACCESSION-NUMBER>0000091142-25-000079
<CONFORMED-SUBMISSION-TYPE>SD
<PUBLIC-DOCUMENT-COUNT>2

<RULE>
<RULE-NAME>13p-1
<ITEM>
<ITEM-NUMBER>1.01
<ITEM-PERIOD>20241231
</ITEM>
<ITEM>
<ITEM-NUMBER>1.02
<ITEM-PERIOD>20241231
</ITEM>
</RULE>

<FILED-AS-OF-DATE>20250520
<DATE-AS-OF-CHANGE>20250520

<FILER>
<COMPANY-DATA>
<COMPANY-CONFORMED-NAME>SMITH A O CORP
<CENTRAL-INDEX-KEY>0000091142
<STANDARD-INDUSTRIAL-CLASSIFICATION>HOUSEHOLD APPLIANCES [3630]
<EIN>390619790
<STATE-OF-INCORPORATION>DE
<FISCAL-YEAR-END>1231
</COMPANY-DATA>
<FILING-VALUES>
<FORM-TYPE>SD
<SEC-ACT>1934 Act
<SEC-FILE-NUMBER>001-00475
<FILM-NUMBER>25967109
</FILING-VALUES>
<BUSINESS-ADDRESS>
<STREET-1>11270 WEST PARK PLACE
<CITY>MILWAUKEE
<STATE>WI
<ZIP>53224
</BUSINESS-ADDRESS>
</FILER>

<DOCUMENT>
<TYPE>SD
<SEQUENCE>1
<FILENAME>sd.htm
<DESCRIPTION>SD
<TEXT>
Content here
</TEXT>
</DOCUMENT>

<DOCUMENT>
<TYPE>EX-1.01
<SEQUENCE>2
<FILENAME>exhibit.htm
<DESCRIPTION>EX-1.01
<TEXT>
Exhibit content
</TEXT>
</DOCUMENT>
</SUBMISSION>"""

    parser = SubmissionFormatParser()
    parsed = parser.parse(sgml_content)

    # Verify top-level fields
    assert parsed['ACCESSION-NUMBER'] == '0000091142-25-000079'
    assert parsed['CONFORMED-SUBMISSION-TYPE'] == 'SD'
    assert parsed['PUBLIC-DOCUMENT-COUNT'] == '2'

    # Verify RULE structure
    assert 'RULE' in parsed
    assert parsed['RULE']['RULE-NAME'] == '13p-1'
    assert len(parsed['RULE']['ITEM']) == 2

    # Verify FILER structure (FILER is repeatable, stored as list)
    assert 'FILER' in parsed
    assert isinstance(parsed['FILER'], list)
    assert len(parsed['FILER']) == 1
    assert parsed['FILER'][0]['COMPANY-DATA']['COMPANY-CONFORMED-NAME'] == 'SMITH A O CORP'
    assert parsed['FILER'][0]['COMPANY-DATA']['CENTRAL-INDEX-KEY'] == '0000091142'

    # Verify documents were parsed
    assert len(parsed['documents']) == 2
    assert parsed['documents'][0]['type'] == 'SD'
    assert parsed['documents'][1]['type'] == 'EX-1.01'
