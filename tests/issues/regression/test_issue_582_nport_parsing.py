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
from edgar import Filing
from edgar.documents import HTMLParser, ParserConfig


@pytest.mark.regression
@pytest.mark.network
def test_nport_p_parsing_no_attribute_error():
    """Test that NPORT-P filing can be parsed without AttributeError."""
    # The filing that was failing
    filing = Filing(
        form='NPORT-P',
        filing_date='2025-08-27',
        company='PRUDENTIAL SERIES FUND',
        cik=711175,
        accession_no='0001752724-25-208163'
    )

    # Get HTML
    html = filing.html()
    assert html is not None
    assert len(html) > 1000  # Sanity check

    # This was causing AttributeError before the fix
    config = ParserConfig(form='NPORT-P')
    parser = HTMLParser(config)

    # Should not raise AttributeError
    document = parser.parse(html)

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
