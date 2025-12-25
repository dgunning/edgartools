"""Analyze span tags to understand subsection patterns"""
from edgar import Company
from lxml import html as lxml_html
import re

def analyze_subsection_spans(ticker, subsection_keywords):
    """Analyze the characteristics of span tags containing subsections."""
    print(f"\n{'='*70}")
    print(f"Analyzing SPAN tags for {ticker}")
    print('='*70)

    try:
        company = Company(ticker)
        filing = company.get_filings(form="10-K").latest()

        # Get Item 1
        tenk = filing.obj()
        doc = tenk.document
        item1 = doc.sections.get_item("1")

        if not item1 or not hasattr(item1, '_html_source') or not item1._html_source:
            print("No HTML source available")
            return

        item1_html = item1._html_source

        # Parse with lxml - encode to bytes to avoid encoding declaration issue
        if isinstance(item1_html, str):
            item1_html_bytes = item1_html.encode('utf-8')
        else:
            item1_html_bytes = item1_html

        tree = lxml_html.fromstring(item1_html_bytes)

        # Find all span tags
        all_spans = tree.xpath('.//span')
        print(f"\nTotal span tags: {len(all_spans)}")

        # Find spans matching our keywords
        subsection_spans = []
        for keyword in subsection_keywords:
            # Find spans containing this keyword (exact match)
            spans = tree.xpath(f'.//span[normalize-space(text())="{keyword}"]')
            if spans:
                subsection_spans.append((keyword, spans[0]))
                print(f"\nFound '{keyword}':")
                span = spans[0]

                # Get attributes
                attrs = span.attrib
                print(f"  Attributes: {attrs}")

                # Get parent
                parent = span.getparent()
                if parent is not None:
                    print(f"  Parent tag: <{parent.tag}>")
                    print(f"  Parent attributes: {parent.attrib}")

                    # Get grandparent
                    grandparent = parent.getparent()
                    if grandparent is not None:
                        print(f"  Grandparent tag: <{grandparent.tag}>")
                        print(f"  Grandparent attributes: {grandparent.attrib}")

                # Get text and siblings
                text = span.text_content().strip()
                print(f"  Text: {text}")

                # Check if it's standalone or part of a paragraph
                next_sibling = span.getnext()
                prev_sibling = span.getprevious()
                print(f"  Has prev sibling: {prev_sibling is not None}")
                print(f"  Has next sibling: {next_sibling is not None}")

        # Also find some non-subsection spans for comparison
        print(f"\n{'='*70}")
        print("Sample of OTHER span tags (first 5):")
        print('='*70)

        subsection_texts = {kw for kw, _ in subsection_spans}
        other_count = 0
        for span in all_spans[:100]:  # Check first 100
            text = span.text_content().strip()
            if text and len(text) < 100 and text not in subsection_texts:
                print(f"\nText: {text[:50]}")
                print(f"  Attributes: {span.attrib}")
                parent = span.getparent()
                if parent is not None:
                    print(f"  Parent: <{parent.tag}> {parent.attrib}")
                other_count += 1
                if other_count >= 5:
                    break

        # Pattern analysis
        print(f"\n{'='*70}")
        print("Pattern Analysis:")
        print('='*70)

        # Check if subsection spans have common attributes
        if subsection_spans:
            common_attrs = {}
            for keyword, span in subsection_spans:
                for attr, value in span.attrib.items():
                    if attr not in common_attrs:
                        common_attrs[attr] = []
                    common_attrs[attr].append(value)

            print("\nCommon attributes across subsection spans:")
            for attr, values in common_attrs.items():
                unique_values = set(values)
                print(f"  {attr}: {unique_values if len(unique_values) <= 3 else f'{len(unique_values)} unique values'}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

# Test with SNAP
snap_keywords = [
    "Overview",
    "Our Partner Ecosystem",
    "Employees and Culture",
    "Competition",
]

analyze_subsection_spans("SNAP", snap_keywords)

# Test with AAPL
aapl_keywords = [
    "Company Background",
    "Products",
    "Advertising",
    "Competition",
]

analyze_subsection_spans("AAPL", aapl_keywords)
