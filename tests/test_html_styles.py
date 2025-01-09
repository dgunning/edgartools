from edgar.files.styles import parse_style, UnitType
from typing import Optional
from bs4 import BeautifulSoup, Tag
from edgar.files.styles import get_heading_level


def create_test_element(html: str, parent_style: Optional[str] = None) -> Tag:
    """Helper to create a test element with optional parent styling"""
    if parent_style:
        html = f'<div style="{parent_style}">{html}</div>'
    return BeautifulSoup(html, 'html.parser').find_all()[-1]


def test_parse_style():

    # Test point units and text alignment
    style = parse_style("margin-top:12pt;text-align:justify")
    assert style.margin_top.value == 12
    assert style.margin_top.unit == UnitType.POINT
    assert style.text_align == "justify"

    # Test different units preserve their original values
    test_cases = {
        "margin-top:1in": (1, UnitType.INCH),
        "margin-top:72pt": (72, UnitType.POINT),
        "margin-top:96px": (96, UnitType.PIXEL),
        "margin-top:2.54cm": (2.54, UnitType.CM),
        "margin-top:25.4mm": (25.4, UnitType.MM),
        "margin-top:100%": (100, UnitType.PERCENT)
    }

    for style_str, (expected_value, expected_unit) in test_cases.items():
        style = parse_style(style_str)
        assert style.margin_top.value == expected_value, \
            f"Wrong value for {style_str}. Expected {expected_value}, got {style.margin_top.value}"
        assert style.margin_top.unit == expected_unit, \
            f"Wrong unit for {style_str}. Expected {expected_unit}, got {style.margin_top.unit}"

    # Test that conversion to chars works correctly
    style = parse_style("width:80%")
    assert style.width.value == 80
    assert style.width.unit == UnitType.PERCENT

    # Test width conversion to chars at different console widths
    test_widths = {
        80: 64,  # 80% of 80 chars = 64
        120: 96,  # 80% of 120 chars = 96
        200: 160  # 80% of 200 chars = 160
    }

    for console_width, expected_chars in test_widths.items():
        actual_chars = style.width.to_chars(console_width)
        assert actual_chars == expected_chars, \
            f"80% width at {console_width} console width should be {expected_chars} chars"

    # Test character conversion for absolute units
    inch_style = parse_style("width:1in")
    pt72_style = parse_style("width:72pt")
    px96_style = parse_style("width:96px")

    # All these should convert to approximately the same number of characters
    # at standard 80-char console width (about 12 chars per inch)
    for style in [inch_style, pt72_style, px96_style]:
        chars = style.width.to_chars(80)
        assert 11 <= chars <= 13, \
            f"1 inch equivalent should convert to approximately 12 chars, got {chars}"


def test_mda_heading_detection():
    html = '''<div style="margin-top:18pt;text-align:center">
              <span style="font-size:14pt;font-weight:700">MANAGEMENT'S DISCUSSION AND ANALYSIS</span>
              </div>'''
    element = create_test_element(html)
    text = element.get_text(strip=True)
    style = parse_style(element.get('style', ''))

    print("\nTesting MD&A heading detection:")
    print("-" * 50)
    level = get_heading_level(element, style, text, debug=True)
    print("\nFinal heading level:", level)

def test_parse_malformed_style_string():
    style_str = 'margin-top:2.1316282072803E-14pt;margin-bottom:21.86pt;margin-left:69.66pt;width:456pt;'
    style = parse_style(style_str)
    print()
    print(style)
    assert style.margin_top is None
    assert style.margin_bottom.value == 21.86