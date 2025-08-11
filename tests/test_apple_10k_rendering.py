"""Test Apple 10-K rendering without XBRL namespaces."""

from pathlib import Path
from edgar.documents import parse_html

# Load Apple 10-K
apple_10k_path = Path("data/html/Apple.10-K.html")
if apple_10k_path.exists():
    html_content = apple_10k_path.read_text()
    
    # Parse the document
    doc = parse_html(html_content)
    
    # Get text
    text = doc.text()
    
    # Check that XBRL namespace values are not in the text
    xbrl_namespaces = [
        "iso4217:USD",
        "xbrli:shares",
        "xbrli:pure",
        "aapl:Vendor",
        "aapl:Subsidiary",
        "iso4217",
        "xbrli:unitNumerator",
        "xbrli:unitDenominator",
        "xbrli:measure"
    ]
    
    print("Checking for XBRL namespace values in rendered text:")
    found_any = False
    for ns in xbrl_namespaces:
        if ns in text:
            print(f"  ❌ Found: {ns}")
            found_any = True
            # Show context
            index = text.find(ns)
            start = max(0, index - 50)
            end = min(len(text), index + len(ns) + 50)
            context = text[start:end]
            print(f"     Context: ...{context}...")
        else:
            print(f"  ✓ Not found: {ns}")
    
    if not found_any:
        print("\n✅ Success: No XBRL namespace values found in rendered text!")
    else:
        print("\n❌ Failed: Some XBRL namespace values are still being rendered")
        
    # Check that actual content is present
    print("\nChecking for actual content:")
    content_checks = [
        "Apple Inc.",
        "Form 10-K",
        "Business",
        "Risk Factors"
    ]
    
    for content in content_checks:
        if content in text:
            print(f"  ✓ Found: {content}")
        else:
            print(f"  ❌ Missing: {content}")
            
    print(f"\nTotal text length: {len(text)} characters")
    
    # Sample first part of text to see what's there
    print("\nFirst 500 characters of text:")
    print(text[:500])
else:
    print(f"Apple 10-K file not found at {apple_10k_path}")