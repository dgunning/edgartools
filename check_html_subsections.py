"""Check HTML structure of subsections to determine their tags"""
from edgar import Company
from lxml import html as lxml_html
import re

def check_subsection_html(ticker, subsection_keywords):
    """Check HTML tags for known subsections."""
    print(f"\n{'='*70}")
    print(f"Analyzing HTML structure for {ticker}")
    print('='*70)

    try:
        company = Company(ticker)
        filing = company.get_filings(form="10-K").latest()
        print(f"Filing: {filing.form} - {filing.filing_date}")

        # Get the document
        tenk = filing.obj()
        doc = tenk.document

        # Get Item 1
        item1 = doc.sections.get_item("1")
        if not item1:
            print("Could not find Item 1")
            return

        print(f"\nItem 1 detection method: {item1.detection_method}")

        # Get HTML content from section
        if hasattr(item1, '_html_source') and item1._html_source:
            item1_html = item1._html_source
            print(f"HTML source length: {len(item1_html)} chars")
        else:
            print("No HTML source available for this section")
            print(f"Available attributes: {dir(item1)}")
            return

        # Parse with lxml for better structure
        try:
            tree = lxml_html.fromstring(item1_html)
        except:
            # If parsing fails, work with raw HTML
            tree = None

        print(f"\n{'='*70}")
        print("Checking subsection keywords in HTML")
        print('='*70)

        for keyword in subsection_keywords:
            print(f"\n--- Keyword: '{keyword}' ---")

            # Find in HTML
            idx = item1_html.lower().find(keyword.lower())
            if idx == -1:
                print(f"  NOT FOUND in HTML")
                continue

            # Get context around keyword
            start = max(0, idx - 300)
            end = min(len(item1_html), idx + 300)
            context = item1_html[start:end]

            # Look for tags around the keyword
            # Find opening tag before keyword
            before = context[:idx-start]
            after = context[idx-start+len(keyword):]

            # Find tag pattern
            tag_pattern = r'<(\w+)[^>]*>([^<]*' + re.escape(keyword) + r'[^<]*)</\1>'
            matches = re.finditer(tag_pattern, context, re.IGNORECASE)

            found_tag = False
            for match in matches:
                tag_name = match.group(1)
                full_text = match.group(2).strip()
                print(f"  Found in <{tag_name}> tag")
                print(f"  Full text: {full_text[:100]}")
                found_tag = True
                break

            if not found_tag:
                # Check if it's in bold/strong
                if '<b>' in before[-20:] or '<strong>' in before[-20:]:
                    print(f"  Found in <b> or <strong> tag")
                    # Show snippet
                    snippet_start = max(0, len(before) - 50)
                    snippet_end = min(len(after), 50)
                    print(f"  Context: ...{before[snippet_start:]}{keyword}{after[:snippet_end]}...")
                else:
                    # Show raw context
                    snippet_start = max(0, len(before) - 100)
                    snippet_end = min(len(after), 100)
                    print(f"  Raw context: ...{before[snippet_start:]}{keyword}{after[:snippet_end]}...")

        # Also find ALL bold text in first 10000 chars
        print(f"\n{'='*70}")
        print("All bold/strong tags in first 10000 chars:")
        print('='*70)

        bold_pattern = r'<(?:b|strong)[^>]*>([^<]+)</(?:b|strong)>'
        matches = re.findall(bold_pattern, item1_html[:10000], re.IGNORECASE)
        for i, match in enumerate(matches[:20]):
            if len(match.strip()) > 3 and len(match.strip()) < 100:
                print(f"{i+1}. {match.strip()}")

        if len(matches) > 20:
            print(f"... and {len(matches) - 20} more bold tags")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

# Test with SNAP subsections
snap_keywords = [
    "Overview",
    "Snapchat",
    "Our Partner Ecosystem",
    "Our Advertising Products",
    "Technology",
    "Employees and Culture",
    "Competition",
    "Camera:",  # Title: Description pattern
]

check_subsection_html("SNAP", snap_keywords)

# Test with AAPL subsections
print("\n" + "="*70)
aapl_keywords = [
    "Company Background",
    "Products",
    "iPhone",
    "Services",
    "Advertising",
    "Competition",
]

check_subsection_html("AAPL", aapl_keywords)
