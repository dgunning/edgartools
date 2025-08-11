"""Test XBRL extraction from ix:hidden elements."""

import pytest
from edgar.documents import parse_html, ParserConfig


def test_xbrl_extraction_from_hidden():
    """Test that XBRL facts are extracted from ix:hidden elements."""
    html = """
    <html>
    <body>
        <div>
            <span>Revenue: </span>
            <ix:nonNumeric name="us-gaap:Revenue" contextRef="FY2023">$1,234,567</ix:nonNumeric>
            <ix:hidden>
                <ix:nonFraction name="us-gaap:Revenue" 
                              contextRef="FY2023" 
                              unitRef="usd" 
                              decimals="-3">1234567000</ix:nonFraction>
            </ix:hidden>
        </div>
    </body>
    </html>
    """
    
    config = ParserConfig(extract_xbrl=True)
    doc = parse_html(html, config)
    
    # Check that hidden content is not in rendered text
    text = doc.text()
    assert "1234567000" not in text
    assert "$1,234,567" in text or "1, 234, 567" in text  # May have spaces
    
    # Check that XBRL data was extracted
    assert doc.metadata.xbrl_data is not None
    assert 'facts' in doc.metadata.xbrl_data
    
    facts = doc.metadata.xbrl_data['facts']
    assert len(facts) >= 2  # Should have both visible and hidden facts
    
    # Find the hidden fact
    hidden_facts = [f for f in facts if f.metadata and f.metadata.get('hidden')]
    assert len(hidden_facts) >= 1
    
    # Check the hidden fact details
    hidden_fact = hidden_facts[0]
    assert hidden_fact.concept == 'us-gaap:Revenue'
    assert hidden_fact.value == '1234567000'
    assert hidden_fact.unit_ref == 'usd'
    assert hidden_fact.decimals == '-3'


def test_multiple_hidden_xbrl_facts():
    """Test extraction of multiple XBRL facts from hidden sections."""
    html = """
    <html>
    <body>
        <table>
            <tr>
                <td>Assets</td>
                <td>
                    <ix:nonNumeric name="us-gaap:Assets" contextRef="2023">$5,000</ix:nonNumeric>
                    <ix:hidden>
                        <ix:nonFraction name="us-gaap:Assets" 
                                      contextRef="2023" 
                                      unitRef="usd" 
                                      decimals="-3">5000000</ix:nonFraction>
                    </ix:hidden>
                </td>
            </tr>
            <tr>
                <td>Liabilities</td>
                <td>
                    <ix:nonNumeric name="us-gaap:Liabilities" contextRef="2023">$3,000</ix:nonNumeric>
                    <ix:hidden>
                        <ix:nonFraction name="us-gaap:Liabilities" 
                                      contextRef="2023" 
                                      unitRef="usd" 
                                      decimals="-3">3000000</ix:nonFraction>
                    </ix:hidden>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    config = ParserConfig(extract_xbrl=True)
    doc = parse_html(html, config)
    
    # Verify XBRL extraction
    assert doc.metadata.xbrl_data is not None
    facts = doc.metadata.xbrl_data['facts']
    
    # Should have 4 facts total (2 visible, 2 hidden)
    assert len(facts) >= 4
    
    # Check hidden facts
    hidden_facts = [f for f in facts if f.metadata and f.metadata.get('hidden')]
    assert len(hidden_facts) >= 2
    
    # Verify concepts
    hidden_concepts = {f.concept for f in hidden_facts}
    assert 'us-gaap:Assets' in hidden_concepts
    assert 'us-gaap:Liabilities' in hidden_concepts


def test_xbrl_disabled():
    """Test that XBRL extraction can be disabled."""
    html = """
    <html>
    <body>
        <ix:nonNumeric name="us-gaap:Revenue" contextRef="FY2023">$1,234,567</ix:nonNumeric>
        <ix:hidden>
            <ix:nonFraction name="us-gaap:Revenue" contextRef="FY2023">1234567000</ix:nonFraction>
        </ix:hidden>
    </body>
    </html>
    """
    
    config = ParserConfig(extract_xbrl=False)
    doc = parse_html(html, config)
    
    # XBRL data should not be extracted
    assert doc.metadata.xbrl_data is None or doc.metadata.xbrl_data == {}


def test_nested_hidden_xbrl():
    """Test XBRL extraction from nested hidden elements."""
    html = """
    <html>
    <body>
        <div>
            <ix:hidden>
                <div>
                    <ix:nonFraction name="us-gaap:NetIncome" 
                                  contextRef="Q1" 
                                  unitRef="usd">1000000</ix:nonFraction>
                    <ix:hidden>
                        <ix:nonFraction name="us-gaap:NetIncomeAdjusted" 
                                      contextRef="Q1" 
                                      unitRef="usd">950000</ix:nonFraction>
                    </ix:hidden>
                </div>
            </ix:hidden>
        </div>
    </body>
    </html>
    """
    
    config = ParserConfig(extract_xbrl=True)
    doc = parse_html(html, config)
    
    # All XBRL facts should be extracted even from nested hidden
    facts = doc.metadata.xbrl_data['facts']
    hidden_facts = [f for f in facts if f.metadata and f.metadata.get('hidden')]
    
    # Both facts should be marked as hidden
    assert len(hidden_facts) >= 2
    
    concepts = {f.concept for f in hidden_facts}
    assert 'us-gaap:NetIncome' in concepts
    assert 'us-gaap:NetIncomeAdjusted' in concepts


if __name__ == "__main__":
    pytest.main([__file__, "-v"])