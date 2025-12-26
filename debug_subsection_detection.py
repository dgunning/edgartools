"""Debug subsection detection"""
from edgar import Company
from bs4 import BeautifulSoup

# Get SNAP filing
company = Company("SNAP")
filing = company.get_filings(form="10-K").latest()
tenk = filing.obj()
doc = tenk.document
item1 = doc.sections.get_item("1")

if item1 and hasattr(item1, '_html_source') and item1._html_source:
    html = item1._html_source
    soup = BeautifulSoup(html, 'html.parser')

    # Find "Overview" in the HTML
    print("Looking for 'Overview' element...")

    # Find all elements containing "Overview"
    elements = soup.find_all(string="Overview")
    print(f"Found {len(elements)} elements with 'Overview' text")

    for i, elem in enumerate(elements[:3]):
        print(f"\n--- Element {i+1} ---")
        parent = elem.parent if hasattr(elem, 'parent') else None
        if parent:
            print(f"Parent tag: {parent.name}")
            print(f"Parent text: {parent.get_text().strip()[:100]}")
            print(f"Parent style: {parent.get('style', 'NO STYLE')}")
            print(f"Parent attrs: {parent.attrs}")

            # Check grandparent
            grandparent = parent.parent if hasattr(parent, 'parent') else None
            if grandparent:
                print(f"Grandparent tag: {grandparent.name}")
                print(f"Grandparent style: {grandparent.get('style', 'NO STYLE')}")

                # Check children of grandparent
                children = list(grandparent.children)
                print(f"Grandparent has {len(children)} children")
                for j, child in enumerate(children[:3]):
                    if hasattr(child, 'name'):
                        print(f"  Child {j}: <{child.name}> - {str(child)[:100]}")
                    else:
                        child_str = str(child).strip()
                        if child_str:
                            print(f"  Child {j}: TEXT - {child_str[:50]}")

    # Now test the is_subsection_heading function
    print("\n" + "="*70)
    print("Testing is_subsection_heading function")
    print("="*70)

    # Import the function
    import sys
    sys.path.insert(0, 'edgar')
    from llm_helpers import is_subsection_heading

    # Get top-level children
    body = soup.find('body')
    if body:
        children = [child for child in body.children if hasattr(child, 'name')]
        print(f"\nBody has {len(children)} element children")

        # Check first 50 elements
        subsection_count = 0
        for i, child in enumerate(children[:100]):
            is_sub, level = is_subsection_heading(child)
            if is_sub:
                text = child.get_text().strip()[:80]
                print(f"\n  Element {i}: {child.name}")
                print(f"    Text: {text}")
                print(f"    Level: {level}")
                print(f"    Style: {child.get('style', '')[:100]}")
                subsection_count += 1
                if subsection_count >= 5:
                    break

        if subsection_count == 0:
            print("\n  NO subsections detected in first 100 elements!")
            print("\n  Showing first 10 div elements for debugging:")
            div_count = 0
            for i, child in enumerate(children[:200]):
                if child.name == 'div':
                    text = child.get_text().strip()
                    if len(text) < 100:
                        print(f"\n  Div {div_count}: {text}")
                        print(f"    Style: {child.get('style', '')[:150]}")
                        spans = child.find_all('span', recursive=False)
                        print(f"    Direct span children: {len(spans)}")
                        if spans:
                            for span in spans[:2]:
                                print(f"      Span text: {span.get_text().strip()}")
                                print(f"      Span style: {span.get('style', '')[:100]}")
                        div_count += 1
                        if div_count >= 10:
                            break
