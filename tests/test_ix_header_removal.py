"""Test removal of ix:header content from rendering."""

import pytest
from edgar.documents import parse_html, ParserConfig


@pytest.mark.fast
def test_ix_header_removed():
    """Test that ix:header content is removed from rendering."""
    html = """
    <html>
    <body>
        <div style="display:none">
            <ix:header>
                <ix:hidden>
                    <ix:nonNumeric contextRef="c-1" name="dei:AmendmentFlag">false</ix:nonNumeric>
                </ix:hidden>
                <ix:resources>
                    <xbrli:context id="c-1">
                        <xbrli:entity>
                            <xbrli:identifier scheme="http://www.sec.gov/CIK">0000320193</xbrli:identifier>
                        </xbrli:entity>
                    </xbrli:context>
                    <xbrli:unit id="usd">
                        <xbrli:measure>iso4217:USD</xbrli:measure>
                    </xbrli:unit>
                    <xbrli:unit id="shares">
                        <xbrli:measure>xbrli:shares</xbrli:measure>
                    </xbrli:unit>
                </ix:resources>
            </ix:header>
        </div>
        <p>This is the actual document content.</p>
    </body>
    </html>
    """
    
    doc = parse_html(html)
    text = doc.text()
    
    # Actual content should be present
    assert "This is the actual document content" in text
    
    # Header content should NOT be present
    assert "iso4217:USD" not in text
    assert "xbrli:shares" not in text
    assert "xbrli:context" not in text
    assert "xbrli:entity" not in text
    assert "0000320193" not in text  # CIK from context
    assert "false" not in text  # Amendment flag value

@pytest.mark.fast
def test_xbrl_extraction_from_header():
    """Test that XBRL data is still extracted from ix:header before removal."""
    html = """
    <html>
    <body>
        <ix:header>
            <ix:hidden>
                <ix:nonNumeric contextRef="c-1" name="dei:EntityCentralIndexKey">0000320193</ix:nonNumeric>
                <ix:nonNumeric contextRef="c-1" name="dei:DocumentType">10-K</ix:nonNumeric>
            </ix:hidden>
            <ix:resources>
                <xbrli:context id="c-1">
                    <xbrli:entity>
                        <xbrli:identifier scheme="http://www.sec.gov/CIK">0000320193</xbrli:identifier>
                    </xbrli:entity>
                    <xbrli:period>
                        <xbrli:instant>2024-09-30</xbrli:instant>
                    </xbrli:period>
                </xbrli:context>
                <xbrli:unit id="usd">
                    <xbrli:measure>iso4217:USD</xbrli:measure>
                </xbrli:unit>
            </ix:resources>
        </ix:header>
        <p>Document body content</p>
    </body>
    </html>
    """
    
    config = ParserConfig(extract_xbrl=True)
    doc = parse_html(html, config)
    
    # Check text doesn't contain header content
    text = doc.text()
    assert "iso4217:USD" not in text
    assert "0000320193" not in text
    
    # Check XBRL data was extracted
    assert doc.metadata.xbrl_data is not None
    facts = doc.metadata.xbrl_data.get('facts', [])
    
    # Should have extracted the nonNumeric facts
    assert len(facts) >= 2
    
    # All facts from header should be marked as hidden
    header_facts = [f for f in facts if f.metadata and f.metadata.get('hidden')]
    assert len(header_facts) >= 2
    
    # Check specific facts
    cik_facts = [f for f in facts if f.concept == 'dei:EntityCentralIndexKey']
    assert len(cik_facts) == 1
    assert cik_facts[0].value == '0000320193'
    
    doc_type_facts = [f for f in facts if f.concept == 'dei:DocumentType']
    assert len(doc_type_facts) == 1
    assert doc_type_facts[0].value == '10-K'

@pytest.mark.fast
def test_real_apple_10k_header():
    """Test with actual Apple 10-K header content."""
    html = """
    <html>
    <body>
        <div style="display:none">
            <ix:header>
                <ix:hidden>
                    <ix:nonNumeric contextRef="c-1" name="dei:AmendmentFlag">false</ix:nonNumeric>
                    <ix:nonNumeric contextRef="c-1" name="dei:DocumentFiscalYearFocus">2024</ix:nonNumeric>
                </ix:hidden>
                <ix:resources>
                    <xbrli:unit id="usd">
                        <xbrli:measure>iso4217:USD</xbrli:measure>
                    </xbrli:unit>
                    <xbrli:unit id="shares">
                        <xbrli:measure>xbrli:shares</xbrli:measure>
                    </xbrli:unit>
                    <xbrli:unit id="usdPerShare">
                        <xbrli:divide>
                            <xbrli:unitNumerator>
                                <xbrli:measure>iso4217:USD</xbrli:measure>
                            </xbrli:unitNumerator>
                            <xbrli:unitDenominator>
                                <xbrli:measure>xbrli:shares</xbrli:measure>
                            </xbrli:unitDenominator>
                        </xbrli:divide>
                    </xbrli:unit>
                    <xbrli:unit id="number">
                        <xbrli:measure>xbrli:pure</xbrli:measure>
                    </xbrli:unit>
                    <xbrli:unit id="vendor">
                        <xbrli:measure>aapl:Vendor</xbrli:measure>
                    </xbrli:unit>
                    <xbrli:unit id="subsidiary">
                        <xbrli:measure>aapl:Subsidiary</xbrli:measure>
                    </xbrli:unit>
                </ix:resources>
            </ix:header>
        </div>
        <p>Apple Inc. Annual Report</p>
    </body>
    </html>
    """
    
    doc = parse_html(html)
    text = doc.text()
    
    # Check that none of the XBRL namespace values appear
    assert "iso4217:USD" not in text
    assert "xbrli:shares" not in text
    assert "xbrli:pure" not in text
    assert "aapl:Vendor" not in text
    assert "aapl:Subsidiary" not in text
    assert "xbrli:unitNumerator" not in text
    assert "xbrli:unitDenominator" not in text
    
    # But actual content is present
    assert "Apple Inc. Annual Report" in text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])