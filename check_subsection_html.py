"""Check HTML structure of subsections in Item 1"""
from edgar import Company
import re
from lxml import html as lxml_html

filing = Company('SNAP').get_filings(form='10-K').latest()
tenk = filing.obj()
doc = tenk.document

# Get Item 1 section
item1 = doc.sections.get_item("1")
if item1:
    print(f"Item 1 detection method: {item1.detection_method}")
    print(f"Has HTML source: {hasattr(item1, '_html_source') and item1._html_source is not None}")

    # Get the HTML content from the full document
    full_html = str(doc.html)

    # Search for Item 1 content in full HTML
    item1_start = full_html.lower().find('item 1.')
    if item1_start == -1:
        item1_start = full_html.lower().find('item 1 ')

    if item1_start != -1:
        html = full_html[item1_start:item1_start+15000]
    else:
        print("Could not find Item 1 in HTML")
        html = None

    if html:
        # Look for subsection patterns
        print("\n" + "="*70)
        print("Looking for 'Overview' in HTML:")
        print("="*70)

        # Find context around 'Overview'
        idx = html.lower().find('overview')
        if idx != -1:
            snippet = html[max(0, idx-200):min(len(html), idx+200)]
            print(snippet)

        print("\n" + "="*70)
        print("Looking for 'Snapchat' in HTML:")
        print("="*70)

        idx = html.lower().find('snapchat')
        if idx != -1:
            snippet = html[max(0, idx-200):min(len(html), idx+200)]
            print(snippet)

        print("\n" + "="*70)
        print("Looking for bold/strong tags:")
        print("="*70)

        # Find all bold tags
        bold_pattern = r'<(?:b|strong)[^>]*>([^<]+)</(?:b|strong)>'
        matches = re.findall(bold_pattern, html, re.IGNORECASE)
        for i, match in enumerate(matches[:15]):
            if len(match.strip()) > 3 and len(match.strip()) < 100:
                print(f"{i+1}. {match.strip()}")
