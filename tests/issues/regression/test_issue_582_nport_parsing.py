"""
Regression test for edgartools-582: NPORT-P parsing AttributeError.

Issue: HTMLParser failed on NPORT-P filings with AttributeError:
'HeaderDetectionStrategy' object has no attribute 'is_section_header'

Root Cause: HeaderDetectionStrategy was missing is_section_header method
that was being called by streaming parser.

Fix: Added is_section_header method to HeaderDetectionStrategy with
pattern-based section header detection compatible with lxml.etree._Element.
"""

import pytest
from edgar.documents import HTMLParser, ParserConfig


# Minimal HTML fixture that triggers the streaming parser's is_section_header call.
# The bug occurred when processing ANY heading, so we don't need a full NPORT filing.
MINIMAL_NPORT_HTML = """
<!DOCTYPE html>
<html>
<head><title>NPORT-P Test</title></head>
<body>
<h1>Part A - General Information</h1>
<p>Fund name and other information</p>

<h2>Item A.1 - Fund Information</h2>
<p>Details about the fund</p>

<h3>Holdings Summary</h3>
<table>
<tr><th>Security</th><th>Value</th></tr>
<tr><td>Treasury Bond</td><td>1,000,000</td></tr>
</table>

<h4>Risk Factors</h4>
<p>Market risk and other disclosures</p>

<h2>Item B - Portfolio Securities</h2>
<p>List of securities held</p>
</body>
</html>
"""


@pytest.mark.regression
def test_nport_p_parsing_no_attribute_error():
    """Test that NPORT-P filing can be parsed without AttributeError.

    The bug was that HeaderDetectionStrategy.is_section_header() was missing.
    This method is called by the streaming parser when processing any heading.
    We use a minimal HTML fixture rather than fetching a real 32MB NPORT filing,
    since the bug would trigger on ANY HTML with headings.
    """
    # This was causing AttributeError before the fix
    config = ParserConfig(form='NPORT-P')
    parser = HTMLParser(config)

    # Should not raise AttributeError
    document = parser.parse(MINIMAL_NPORT_HTML)

    # Verify document was created
    assert document is not None
    assert hasattr(document, 'root')


@pytest.mark.regression
def test_header_detection_strategy_has_is_section_header():
    """Test that HeaderDetectionStrategy has is_section_header method."""
    from edgar.documents.strategies.header_detection import HeaderDetectionStrategy
    from edgar.documents.config import ParserConfig

    config = ParserConfig()
    strategy = HeaderDetectionStrategy(config)

    # Should have the method
    assert hasattr(strategy, 'is_section_header')
    assert callable(strategy.is_section_header)


@pytest.mark.regression
def test_is_section_header_recognizes_common_patterns():
    """Test that is_section_header recognizes common section header patterns."""
    from edgar.documents.strategies.header_detection import HeaderDetectionStrategy
    from edgar.documents.config import ParserConfig

    config = ParserConfig()
    strategy = HeaderDetectionStrategy(config)

    # Test Item patterns
    assert strategy.is_section_header('Item 1', None) == True
    assert strategy.is_section_header('Item 1A', None) == True
    assert strategy.is_section_header('ITEM 2', None) == True

    # Test Part patterns
    assert strategy.is_section_header('Part I', None) == True
    assert strategy.is_section_header('PART II', None) == True

    # Test major section headers
    assert strategy.is_section_header('BUSINESS', None) == True
    assert strategy.is_section_header('RISK FACTORS', None) == True
    assert strategy.is_section_header('FINANCIAL STATEMENTS', None) == True

    # Test Management's Discussion
    assert strategy.is_section_header("MANAGEMENT'S DISCUSSION AND ANALYSIS", None) == True

    # Test negative cases
    assert strategy.is_section_header('', None) == False
    assert strategy.is_section_header('This is a very long paragraph that should not be considered a section header because it exceeds the length limit and contains multiple sentences with detailed explanations that go on and on.', None) == False
    assert strategy.is_section_header('Regular text', None) == False
