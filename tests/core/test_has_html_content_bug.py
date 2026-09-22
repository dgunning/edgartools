import pytest
from edgar.core import has_html_content


def test_has_html_content_bug_reproduction():
    """
    Test to reproduce the bug where has_html_content() incorrectly returns False
    for valid HTML files that don't match the expected XBRL/XML patterns.
    
    Based on the user's report, ef20048691_ex5-1.htm starts with:
    <html style="font-family: Arial; font-size: 10pt; text-align: left;">
    
    While working files start with:
    <?xml version='1.0' encoding='ASCII'?>
    <html xmlns:xbrli="http://www.xbrl.org/2003/instance"...
    """
    
    # Test case 1: HTML that should be recognized but currently fails
    # This represents the problematic file ef20048691_ex5-1.htm
    problematic_html = """<html style="font-family: Arial; font-size: 10pt; text-align: left;">
<head>
<title>EXHIBIT 5.1</title>
</head>
<body>
<p>This is a valid HTML document that should be recognized.</p>
<div>It has proper HTML structure but doesn't have XBRL namespaces.</div>
</body>
</html>"""
    
    # Test case 2: HTML with XBRL namespaces (currently works)
    working_html = """<?xml version='1.0' encoding='ASCII'?>
<html xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:link="http://www.xbrl.org/2003/linkbase" 
xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi" 
xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:srt="http://fasb.org/srt/2024" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" 
xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2022-02-16" xmlns:ixt-sec="http://www.sec.gov/inlineXBRL/transformation/2015-08-31">
<head>
<title>Working HTML Document</title>
</head>
<body>
<p>This HTML document has XBRL namespaces and should be recognized.</p>
</body>
</html>"""
    
    # Test case 3: Simple HTML with DOCTYPE (should work)
    simple_html = """<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>Simple HTML Document</title>
</head>
<body>
<p>This is a simple HTML document with DOCTYPE.</p>
</body>
</html>"""
    
    # Test case 4: HTML with XHTML namespace (should work)
    xhtml_html = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns:m1="http://www.sec.gov/edgar/rega/oneafiler" xmlns:ns1="http://www.sec.gov/edgar/common" 
xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>XHTML Document</title>
</head>
<body>
<p>This is an XHTML document with proper namespace.</p>
</body>
</html>"""
    
    # Test case 5: Non-HTML content (should fail)
    non_html_content = """<?xml version="1.0"?>
<SEC-DOCUMENT>0001193125-23-048785.txt : 20230224
<SEC-HEADER>0001193125-23-048785.hdr.sgml : 20230224
<ACCEPTANCE-DATETIME>20230224163457
<FILER>
<COMPANY-DATA>
<CONFORMED-NAME>Test Company</CONFORMED-NAME>
</COMPANY-DATA>
</FILER>
</SEC-HEADER>
<DOCUMENT>
<TEXT>
This is not HTML content.
</TEXT>
</DOCUMENT>
</SEC-DOCUMENT>"""
    
    # Current behavior (this is the bug)
    print("=== Current Behavior (Bug) ===")
    print(f"Problematic HTML (should be True): {has_html_content(problematic_html)}")
    print(f"Working HTML (should be True): {has_html_content(working_html)}")
    print(f"Simple HTML (should be True): {has_html_content(simple_html)}")
    print(f"XHTML (should be True): {has_html_content(xhtml_html)}")
    print(f"Non-HTML (should be False): {has_html_content(non_html_content)}")
    
    # Assert the current buggy behavior
    assert has_html_content(working_html) == True, "Working HTML should be recognized"
    assert has_html_content(simple_html) == True, "Simple HTML should be recognized"
    assert has_html_content(xhtml_html) == True, "XHTML should be recognized"
    assert has_html_content(non_html_content) == False, "Non-HTML should be rejected"
    
    # This is the bug - problematic HTML should be recognized but currently isn't
    # We'll fix this in the implementation
    problematic_result = has_html_content(problematic_html)
    print(f"\nBUG: Problematic HTML returns {problematic_result} but should return True")
    
    # Now, after the fix, assert that problematic_result is True
    assert problematic_result == True, "Problematic HTML should now be recognized as HTML"


def test_has_html_content_edge_cases():
    """Test edge cases for has_html_content function"""
    
    # Test with bytes input
    html_bytes = b"<html><body><p>Test</p></body></html>"
    assert has_html_content(html_bytes) == True, "Bytes input should be handled"
    
    # Test with leading whitespace
    html_with_whitespace = """   
    <html>
    <body>
    <p>Test content</p>
    </body>
    </html>"""
    assert has_html_content(html_with_whitespace) == True, "Leading whitespace should be handled"
    
    # Test with very short HTML
    short_html = "<html><body>test</body></html>"
    assert has_html_content(short_html) == True, "Short HTML should be recognized"
    
    # Test with empty content
    assert has_html_content("") == False, "Empty content should be rejected"
    assert has_html_content("   ") == False, "Whitespace-only content should be rejected"
    
    # Test with None (should handle gracefully)
    try:
        result = has_html_content(None)
        print(f"has_html_content(None) returned: {result}")
    except Exception as e:
        print(f"has_html_content(None) raised exception: {e}")


if __name__ == "__main__":
    # Run the tests
    test_has_html_content_bug_reproduction()
    test_has_html_content_edge_cases()
    print("\n✓ All tests passed!") 