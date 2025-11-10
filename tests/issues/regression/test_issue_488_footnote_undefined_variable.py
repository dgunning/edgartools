"""
Regression test for GitHub issue #488: UnboundLocalError in footnote extraction

This test ensures that the footnote extraction code handles filings without
footnoteLink elements correctly, without raising UnboundLocalError.

The bug was in edgar/xbrl/parsers/instance.py where undefined_footnotes was
declared inside the footnote_link loop but referenced outside it, causing
UnboundLocalError when no footnoteLink elements existed.
"""

import xml.etree.ElementTree as ET

import pytest

from edgar.xbrl.parsers.instance import InstanceParser


class TestFootnoteExtractionRegression:
    """Test cases for footnote extraction without footnoteLink elements"""

    def test_no_footnotelink_elements(self):
        """Test that footnote extraction works when no footnoteLink elements exist"""
        # Create a minimal XBRL instance document without footnoteLink elements
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <xbrl xmlns="http://www.xbrl.org/2003/instance"
              xmlns:xlink="http://www.w3.org/1999/xlink">
            <context id="ctx1">
                <entity>
                    <identifier scheme="http://www.sec.gov/CIK">0000000001</identifier>
                </entity>
                <period>
                    <instant>2024-12-31</instant>
                </period>
            </context>
        </xbrl>
        """

        # Parse the XML
        root = ET.fromstring(xml_content)

        # Create a parser instance with minimal required arguments
        parser = InstanceParser(
            contexts={},
            facts={},
            units={},
            footnotes={},
            calculation_trees={},
            entity_info={},
            reporting_periods=[],
            context_period_map={}
        )

        # Call the private method directly - should not raise UnboundLocalError
        try:
            parser._extract_footnotes(root)
            # If we get here, the bug is fixed
            assert True
        except UnboundLocalError as e:
            pytest.fail(f"UnboundLocalError raised: {e}. Bug #488 not fixed.")

    def test_empty_root_element(self):
        """Test that footnote extraction handles empty root elements"""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <xbrl xmlns="http://www.xbrl.org/2003/instance"/>
        """

        root = ET.fromstring(xml_content)
        parser = InstanceParser(
            contexts={},
            facts={},
            units={},
            footnotes={},
            calculation_trees={},
            entity_info={},
            reporting_periods=[],
            context_period_map={}
        )

        # Should not raise UnboundLocalError
        try:
            parser._extract_footnotes(root)
            assert True
        except UnboundLocalError as e:
            pytest.fail(f"UnboundLocalError raised with empty root: {e}")

    def test_with_footnotelink_elements(self):
        """Test that footnote extraction still works correctly with footnoteLink elements"""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <xbrl xmlns="http://www.xbrl.org/2003/instance"
              xmlns:link="http://www.xbrl.org/2003/linkbase"
              xmlns:xlink="http://www.w3.org/1999/xlink">
            <link:footnoteLink>
                <link:footnote xlink:label="fn1" xlink:role="http://www.xbrl.org/2003/role/footnote"
                              xml:lang="en-US">
                    This is a test footnote.
                </link:footnote>
                <link:footnoteArc xlink:from="fact1" xlink:to="fn1" xlink:arcrole="http://www.xbrl.org/2003/arcrole/fact-footnote"/>
            </link:footnoteLink>
        </xbrl>
        """

        root = ET.fromstring(xml_content)
        parser = InstanceParser(
            contexts={},
            facts={},
            units={},
            footnotes={},
            calculation_trees={},
            entity_info={},
            reporting_periods=[],
            context_period_map={}
        )

        # Should work correctly
        try:
            parser._extract_footnotes(root)
            # Check that footnote was extracted
            assert len(parser.footnotes) > 0
            assert "fn1" in parser.footnotes
        except Exception as e:
            pytest.fail(f"Exception raised with valid footnoteLink: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
