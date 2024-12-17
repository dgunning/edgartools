from multiprocessing.util import debug
from typing import Optional

from bs4 import BeautifulSoup, Tag

from edgar.files.styles import parse_style, is_heading, get_heading_level, HEADING_PATTERNS


def create_test_element(html: str, parent_style: Optional[str] = None) -> Tag:
    """Helper to create a test element with optional parent styling"""
    if parent_style:
        html = f'<div style="{parent_style}">{html}</div>'
    return BeautifulSoup(html, 'html.parser').find_all()[-1]


def test_heading_style_inheritance():
    """Test heading detection with inherited styles"""

    html = '''
    <div style="font-weight:700">
        <span style="font-size:12pt">PART I</span>
        <span>OVERVIEW</span>
    </div>
    '''
    element = BeautifulSoup(html, 'html.parser').find('div')
    style = parse_style(element.get('style', ''))

    # Both spans should be detected as part of the heading
    # due to inherited bold style from parent
    for span in element.find_all('span'):
        span_style = parse_style(span.get('style', '')).merge(style)
        result = is_heading(span, span_style)
        assert result, f"Failed to detect heading in: {span}"


def test_heading_context():
    """Test heading detection based on surrounding context"""

    # Test margin inheritance and sibling analysis
    html = '''
    <div style="margin-top:18pt">
        <span style="font-weight:700">ITEM 1.</span>
        <span>BUSINESS OVERVIEW</span>
        <p>This should not affect heading detection.</p>
    </div>
    '''
    element = BeautifulSoup(html, 'html.parser').find('div')
    for span in element.find_all('span'):
        style = parse_style(span.get('style', ''))
        parent_style = parse_style(element.get('style', ''))
        combined_style = style.merge(parent_style)
        result = is_heading(span, combined_style)
        assert result, f"Failed to detect heading in context: {span}"


def test_negative_patterns():
    """Test patterns that should not be detected as headings"""

    non_headings = [
        '<span style="font-weight:700">Note: The following table...</span>',
        '<div style="font-size:12pt">See "Risk Factors" below.</div>',
        '<span style="font-weight:700;font-size:10pt">*Footnote text</span>',
        '<div style="text-align:center">$ in millions</div>',
    ]

    for html in non_headings:
        element = create_test_element(html)
        style = parse_style(element.get('style', ''))
        result = is_heading(element, style)
        assert not result, f"Incorrectly detected heading in: {html}"


def test_get_heading_level():
    """Test heading level detection for various SEC document patterns"""

    # Test cases as tuples of (html, expected_level, description)
    test_cases = [
        # Level 1 (PART) headings
        (
            '<span style="font-weight:700;font-size:12pt">PART I</span>',
            1,
            "Basic PART I heading"
        ),
        (
            '<div style="margin-top:18pt;text-align:justify"><span style="color:#000000;font-family:\'Helvetica\',sans-serif;font-size:9pt;font-weight:700;line-height:120%">PART I</span></div>',
            1,
            "PART I with full style"
        ),
        (
            '<div style="margin-top:24pt"><span style="font-weight:700">PART II - OTHER INFORMATION</span></div>',
            1,
            "PART with description"
        ),
        (
            '<div style="font-weight:700;text-align:center">Part IV</div>',
            1,
            "Centered PART heading"
        ),

        # Level 2 (ITEM) headings
        (
            '<div style="margin-top:18pt"><span style="font-weight:700">ITEM 1. BUSINESS</span></div>',
            2,
            "Standard Item heading"
        ),
        (
            '<span style="font-weight:700">Item 1A. Risk Factors</span>',
            2,
            "Risk factors item"
        ),
        (
            '<div style="margin-top:12pt"><span style="font-weight:700">ARTICLE III. DIRECTORS</span></div>',
            2,
            "Article heading"
        ),
        (
            '<span style="font-weight:700">Section 3.1 Compensation</span>',
            2,
            "Section heading with subsection"
        ),

        # Level 3 (Major subsection) headings
        (
                '<div style="margin-top:18pt;text-align:center">' +
                '<span style="font-size:14pt;font-weight:700">MANAGEMENT\'S DISCUSSION AND ANALYSIS </span > </div > ',
        3,
        "MD&A heading"
        ),
        (
            '<div style="margin-top:18pt"><span style="font-weight:700">CONSOLIDATED RESULTS OF OPERATIONS</span></div>',
            3,
            "Financial statement section"
        ),
        (
            '<div style="text-align:center;font-size:13pt;font-weight:700">SELECTED FINANCIAL DATA</div>',
            3,
            "Selected financial data section"
        ),
        (
            '<div style="margin-top:18pt"><span style="font-weight:700">SIGNATURES</span></div>',
            3,
            "Signatures section"
        ),

        # Level 4 (Minor subsection) headings
        (
            '<div style="font-weight:700">Competition</div>',
            4,
            "Simple bold subsection"
        ),
        (
            '<span style="font-weight:700">Executive Officers of the Registrant</span>',
            4,
            "Officers section"
        ),
        (
            '<div style="margin-top:12pt"><span style="font-weight:700">Critical Accounting Estimates</span></div>',
            4,
            "Accounting subsection"
        ),

        # Edge cases and non-headings
        (
            '<span style="font-weight:700">Note: The following table presents...</span>',
            None,
            "Note prefix - not a heading"
        ),
        (
            '<div style="font-weight:700">$ in millions</div>',
            None,
            "Table unit indicator - not a heading"
        ),
        (
            '<span style="font-weight:700">(1) Revenue Recognition</span>',
            None,
            "Numbered note - not a heading"
        ),
        (
            '<div style="font-weight:700">This is a very long piece of text that should not be detected as a heading because it is much too long to be a reasonable heading in an SEC document.</div>',
            None,
            "Too long for heading"
        ),

        # Complex nested structures
        (
            '''
            <div style="margin-top:18pt;text-align:center">
                <span style="font-size:14pt">
                    <strong>ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS</strong>
                </span>
            </div>
            ''',
            2,  # Should detect as level 2 because it's an ITEM
            "Complex nested Item heading"
        ),
        (
            '''
            <div style="margin-top:12pt">
                <span style="font-weight:700">2.</span>
                <span style="font-weight:700">Summary of Significant Accounting Policies</span>
            </div>
            ''',
            4,  # Should detect as level 4 minor heading
            "Split heading with multiple spans"
        ),

        # Real-world examples from actual filings
        (
            '<ix:nonnumeric style="font-weight:700">Item 2. Properties</ix:nonnumeric>',
            2,
            "XBRL tagged Item heading"
        ),
        (
            '<div style="text-align:center"><span style="font-size:12pt;font-weight:700">REPORT OF INDEPENDENT REGISTERED PUBLIC ACCOUNTING FIRM</span></div>',
            3,
            "Auditor's report heading"
        ),
        (
            '<p style="font-weight:700;margin-top:12pt">Commitments and Contingencies</p>',
            4,
            "Note subsection heading"
        )
    ]

    for html, expected_level, description in test_cases:
        print("\n" + "-" * 50)
        print(f"Testing: {description}")
        element = create_test_element(html)
        text = element.get_text(strip=True)
        style = parse_style(element.get('style', ''))

        # Get the heading level
        level = get_heading_level(element, style, text, debug=True)

        assert level == expected_level, \
            f"Failed: {description}\nExpected level {expected_level}, got {level}\nHTML: {html}"


def test_part_pattern():
    """Test the PART pattern matching directly"""
    pattern = HEADING_PATTERNS['l1']
    test_cases = [
        ("PART I", True, "Basic PART I"),
        ("Part I", True, "Mixed case Part I"),
        ("PART II", True, "PART II"),
        ("PART II - OTHER INFORMATION", True, "PART with description"),
        ("PARTIAL", False, "Should not match partial"),
        ("NOT A PART", False, "Should not match if PART not at start"),
    ]

    for text, should_match, desc in test_cases:
        result = bool(pattern.match(text))
        print(f"\nTesting: '{text}'")
        print(f"Expected: {should_match}")
        print(f"Got: {result}")
        print(f"Description: {desc}")
        assert result == should_match, f"Pattern match failed for: {desc}"


def test_edge_cases():
    """Test specific edge cases and potential problem areas"""

    edge_cases = [
        # Empty and whitespace
        ('<span style="font-weight:700">  </span>', None, "Empty content"),
        ('<div style="font-weight:700">\n\t  \n</div>', None, "Only whitespace"),

        # Common false positives
        ('<span style="font-weight:700">See Note 1:</span>', None, "Note reference"),
        ('<div style="font-weight:700">(continued)</div>', None, "Continuation marker"),
        ('<span style="font-weight:700">* Compensated Director</span>', None, "Footnote"),

        # Mixed styling
        (
            '''
            <div style="margin-top:12pt">
                <span>Item </span>
                <span style="font-weight:700">1B. </span>
                <span style="font-weight:700">Unresolved Staff Comments</span>
            </div>
            ''',
            2,
            "Split Item heading"
        ),

        # XBRL variations
        (
            '<ix:nonNumeric name="dei:DocumentType" contextRef="c0">10-K</ix:nonNumeric>',
            None,
            "XBRL metadata"
        ),
    ]

    for html, expected_level, description in edge_cases:
        print("\n" + "-" * 30, description, "-" * 30)

        element = create_test_element(html)
        text = element.get_text(strip=True)
        style = parse_style(element.get('style', ''))

        level = get_heading_level(element, style, text, debug=True)

        assert level == expected_level, \
            f"Edge case failed: {description}\nExpected level {expected_level}, got {level}\nHTML: {html}"


def test_style_inheritance():
    """Test heading level detection with inherited styles"""

    test_cases = [
        (
            '''
            <div style="font-weight:700">
                <span style="font-size:12pt">ITEM 1.</span>
                <span>BUSINESS</span>
            </div>
            ''',
            2,
            "Item heading with inherited bold"
        ),
        (
            '''
            <div style="margin-top:18pt;text-align:center">
                <span style="font-size:14pt">
                    <strong>Consolidated Financial Statements</strong>
                </span>
            </div>
            ''',
            3,
            "Financial statement heading with multiple levels"
        )
    ]

    for html, expected_level, description in test_cases:
        print("\n" + "-" * 30, description, "-" * 30)
        element = create_test_element(html)
        text = element.get_text(strip=True)
        style = parse_style(element.get('style', ''))

        level = get_heading_level(element, style, text, debug=True)

        assert level == expected_level, \
            f"Style inheritance failed: {description}\nExpected level {expected_level}, got {level}\nHTML: {html}"