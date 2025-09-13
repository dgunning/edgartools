"""
Regression test for Issue #412: SGML parsing failure with XBRL inline content

This test ensures that SGML files containing XBRL inline content with multiple '>' 
characters in a single line can be parsed correctly.

Fixed: SGML header parser was splitting on all '>' characters instead of just the first one,
causing "ValueError: too many values to unpack" when encountering XBRL inline tags like:
<ix:nonNumeric id="F_000001" name="dei:AmendmentFlag" contextRef="C_0001318605_20190101_20191231">false</ix:nonNumeric>
"""

import pytest
from pathlib import Path
from edgar.sgml.sgml_header import FilingHeader


def test_sgml_parsing_with_multiple_angle_brackets():
    """
    Test that SGML files with multiple '>' characters in lines can be parsed.
    
    This specifically tests the fix for TSLA 2020 10-K filing that was failing
    due to XBRL inline content with multiple '>' characters.
    """
    # Read the TSLA SGML file that was previously failing (minimal version for testing)
    sgml_file = Path("data/sgml/0001564590-20-004475-minimal.txt")
    
    # Skip test if file doesn't exist (for CI environments without test data)
    if not sgml_file.exists():
        pytest.skip("SGML test data file not available")
    
    content = sgml_file.read_text()
    
    # This should not raise "ValueError: too many values to unpack"
    filing_header = FilingHeader.parse_from_sgml_text(content)
    
    # Verify basic header parsing worked
    assert filing_header is not None
    assert hasattr(filing_header, 'cik')
    assert str(filing_header.cik) == '1318605'  # Tesla's CIK (without leading zeros)


def test_sgml_line_with_multiple_angle_brackets_unit():
    """
    Unit test for lines containing multiple '>' characters.
    
    Tests the specific parsing logic that was fixed to handle XBRL inline content.
    """
    # Simulate SGML content with problematic line
    sgml_content = """<SEC-DOCUMENT>test.txt : 20200213
<SEC-HEADER>test.hdr.sgml : 20200213
<ACCEPTANCE-DATETIME>20200213071218
ACCESSION NUMBER:\t\ttest-123
CONFORMED SUBMISSION TYPE:\t10-K
</SEC-HEADER>
<DOCUMENT>
<TYPE>10-K
<SEQUENCE>1
<TEXT>
<ix:nonNumeric id="F_000001" name="dei:AmendmentFlag" contextRef="C_0001318605_20190101_20191231">false</ix:nonNumeric>
<ix:nonNumeric id="F_000003" name="dei:DocumentFiscalYearFocus" contextRef="C_0001318605_20190101_20191231">2019</ix:nonNumeric>
</TEXT>
</DOCUMENT>
</SEC-DOCUMENT>"""
    
    # This should parse without errors
    filing_header = FilingHeader.parse_from_sgml_text(sgml_content)
    
    # Verify basic parsing worked
    assert filing_header is not None
    assert hasattr(filing_header, 'accession_number')
    assert filing_header.accession_number == 'test-123'


def test_backwards_compatibility_simple_sgml():
    """
    Ensure the fix doesn't break existing simple SGML parsing.
    """
    simple_sgml = """<SEC-DOCUMENT>simple.txt : 20200213
<SEC-HEADER>simple.hdr.sgml : 20200213
<ACCEPTANCE-DATETIME>20200213071218
ACCESSION NUMBER:\t\tsimple-123
CONFORMED SUBMISSION TYPE:\t10-K
FILED AS OF DATE:\t\t20200213
</SEC-HEADER>
<DOCUMENT>
<TYPE>10-K
<SEQUENCE>1
<DESCRIPTION>Simple Test
<TEXT>Simple content</TEXT>
</DOCUMENT>
</SEC-DOCUMENT>"""
    
    # Should parse without issues
    filing_header = FilingHeader.parse_from_sgml_text(simple_sgml)
    
    assert filing_header is not None
    assert filing_header.accession_number == 'simple-123'
    assert filing_header.form == '10-K'
    # Filing date is parsed and formatted, so check it exists rather than exact format
    assert filing_header.filing_date is not None


if __name__ == "__main__":
    test_sgml_parsing_with_multiple_angle_brackets()
    test_sgml_line_with_multiple_angle_brackets_unit()
    test_backwards_compatibility_simple_sgml()
    print("✅ All Issue #412 regression tests passed!")