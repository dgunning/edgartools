"""
Test script for form-aware item extraction in llm_extraction.py

Run with: python test_form_items.py
"""

from edgar.llm_extraction import (
    get_form_items,
    get_item_info,
    FORM_10K_ITEMS,
    FORM_10Q_ITEMS,
    FORM_20F_ITEMS,
    FORM_ITEM_REGISTRY,
    _normalize_item_name,
    _get_item_boundaries,
    _get_item_title,
    _build_item_pattern,
)

def test_form_item_counts():
    """Test that all forms have the expected number of items."""
    print("=" * 60)
    print("TEST: Form Item Counts")
    print("=" * 60)

    results = {
        "10-K": (len(FORM_10K_ITEMS), 23),  # 16 standard + Item 1C + Item 9C
        "10-Q": (len(FORM_10Q_ITEMS), 11),  # Part I (4) + Part II (7)
        "20-F": (len(FORM_20F_ITEMS), 69),  # Many sub-items
    }

    all_passed = True
    for form, (actual, expected) in results.items():
        status = "PASS" if actual == expected else "FAIL"
        if actual != expected:
            all_passed = False
        print(f"  {form}: {actual} items (expected {expected}) [{status}]")

    return all_passed


def test_form_registry():
    """Test that form registry includes all expected forms."""
    print("\n" + "=" * 60)
    print("TEST: Form Registry")
    print("=" * 60)

    expected_forms = ["10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A"]

    all_passed = True
    for form in expected_forms:
        exists = form in FORM_ITEM_REGISTRY
        status = "PASS" if exists else "FAIL"
        if not exists:
            all_passed = False
        print(f"  {form}: {status}")

    return all_passed


def test_item_normalization():
    """Test item name normalization."""
    print("\n" + "=" * 60)
    print("TEST: Item Normalization")
    print("=" * 60)

    test_cases = [
        # (input, form_type, expected)
        ("item 1", None, "Item 1"),
        ("Item1", None, "Item 1"),
        ("ITEM 1A", None, "Item 1A"),
        ("Item 3.D", None, "Item 3D"),
        ("Item 3.D", "20-F", "Item 3D"),
        ("item16K", None, "Item 16K"),
        ("Item 10.H", None, "Item 10H"),
        ("ITEM 5.B", None, "Item 5B"),
        ("Item 7A", "10-K", "Item 7A"),
        ("item 2", "10-Q", "Item 2"),
    ]

    all_passed = True
    for input_val, form_type, expected in test_cases:
        result = _normalize_item_name(input_val, form_type)
        status = "PASS" if result == expected else "FAIL"
        if result != expected:
            all_passed = False
        print(f"  '{input_val}' ({form_type or 'None'}) -> '{result}' (expected '{expected}') [{status}]")

    return all_passed


def test_item_boundaries():
    """Test that boundaries are correctly retrieved."""
    print("\n" + "=" * 60)
    print("TEST: Item Boundaries")
    print("=" * 60)

    test_cases = [
        # (form_type, item, expected_boundaries_subset)
        ("10-K", "Item 1", ["Item 1A", "Item 1B", "Item 2"]),
        ("10-K", "Item 7", ["Item 7A", "Item 8"]),
        ("10-K", "Item 9B", ["Item 9C", "Part III", "Item 10"]),
        ("10-K", "Item 16", ["Signature"]),
        ("10-Q", "Item 4", ["Part II", "Item 1"]),
        ("20-F", "Item 3D", ["Item 4"]),
        ("20-F", "Item 16K", ["Part III", "Item 17"]),
    ]

    all_passed = True
    for form_type, item, expected_subset in test_cases:
        boundaries = _get_item_boundaries(form_type, item)
        # Check that expected boundaries are present (excluding "Signature" which is always added)
        has_all = all(b in boundaries for b in expected_subset)
        status = "PASS" if has_all else "FAIL"
        if not has_all:
            all_passed = False
        print(f"  {form_type} {item}: {boundaries[:3]}... [{status}]")

    return all_passed


def test_item_titles():
    """Test that official titles are correctly retrieved."""
    print("\n" + "=" * 60)
    print("TEST: Item Titles")
    print("=" * 60)

    test_cases = [
        ("10-K", "Item 1", "Business"),
        ("10-K", "Item 7", "Management's Discussion and Analysis"),
        ("10-K", "Item 1C", "Cybersecurity"),
        ("10-Q", "Item 1", "Financial Statements"),
        ("10-Q", "Item 2", "Management's Discussion and Analysis"),
        ("20-F", "Item 3D", "Risk Factors"),
        ("20-F", "Item 5", "Operating and Financial Review"),
    ]

    all_passed = True
    for form_type, item, expected_substring in test_cases:
        title = _get_item_title(form_type, item)
        has_substring = expected_substring.lower() in title.lower()
        status = "PASS" if has_substring else "FAIL"
        if not has_substring:
            all_passed = False
        print(f"  {form_type} {item}: '{title[:50]}...' [{status}]")

    return all_passed


def test_get_form_items():
    """Test the public get_form_items function."""
    print("\n" + "=" * 60)
    print("TEST: get_form_items()")
    print("=" * 60)

    all_passed = True

    # Test 10-K
    items_10k = get_form_items("10-K")
    has_item_7 = "Item 7" in items_10k
    has_item_1c = "Item 1C" in items_10k
    status = "PASS" if has_item_7 and has_item_1c else "FAIL"
    if not (has_item_7 and has_item_1c):
        all_passed = False
    print(f"  10-K: {len(items_10k)} items, has Item 7: {has_item_7}, has Item 1C: {has_item_1c} [{status}]")

    # Test 10-Q
    items_10q = get_form_items("10-Q")
    has_part2 = any("Part II" in item for item in items_10q)
    status = "PASS" if has_part2 else "FAIL"
    if not has_part2:
        all_passed = False
    print(f"  10-Q: {len(items_10q)} items, has Part II items: {has_part2} [{status}]")

    # Test 20-F
    items_20f = get_form_items("20-F")
    has_subitems = "Item 3D" in items_20f and "Item 16K" in items_20f
    status = "PASS" if has_subitems else "FAIL"
    if not has_subitems:
        all_passed = False
    print(f"  20-F: {len(items_20f)} items, has sub-items: {has_subitems} [{status}]")

    # Test unknown form
    items_unknown = get_form_items("UNKNOWN-FORM")
    status = "PASS" if items_unknown == [] else "FAIL"
    if items_unknown != []:
        all_passed = False
    print(f"  Unknown form: returns empty list: {items_unknown == []} [{status}]")

    return all_passed


def test_get_item_info():
    """Test the public get_item_info function."""
    print("\n" + "=" * 60)
    print("TEST: get_item_info()")
    print("=" * 60)

    all_passed = True

    # Test 10-K Item 7
    info = get_item_info("10-K", "Item 7")
    has_keys = info and "title" in info and "boundaries" in info and "part" in info
    status = "PASS" if has_keys else "FAIL"
    if not has_keys:
        all_passed = False
    print(f"  10-K Item 7: has required keys: {has_keys} [{status}]")
    if info:
        print(f"    title: {info.get('title', 'N/A')[:50]}...")
        print(f"    part: {info.get('part', 'N/A')}")

    # Test 20-F sub-item with parent
    info = get_item_info("20-F", "Item 3D")
    has_parent = info and info.get("parent") == "Item 3"
    status = "PASS" if has_parent else "FAIL"
    if not has_parent:
        all_passed = False
    print(f"  20-F Item 3D: has parent 'Item 3': {has_parent} [{status}]")

    # Test non-existent item
    info = get_item_info("10-K", "Item 99")
    is_none = info is None
    status = "PASS" if is_none else "FAIL"
    if not is_none:
        all_passed = False
    print(f"  10-K Item 99 (non-existent): returns None: {is_none} [{status}]")

    return all_passed


def test_regex_patterns():
    """Test regex pattern building."""
    print("\n" + "=" * 60)
    print("TEST: Regex Pattern Building")
    print("=" * 60)

    import re

    test_cases = [
        # (item_name, form_type, test_strings_should_match, test_strings_should_not_match)
        ("Item 1", None, ["Item 1", "ITEM 1", "Item  1"], ["Item 1A", "Item 10"]),
        ("Item 1A", None, ["Item 1A", "Item 1.A", "ITEM 1A"], ["Item 1", "Item 1B"]),
        ("Item 3D", "20-F", ["Item 3D", "Item 3.D", "ITEM 3D"], ["Item 3", "Item 3E"]),
    ]

    all_passed = True
    for item_name, form_type, should_match, should_not_match in test_cases:
        pattern = _build_item_pattern(item_name, form_type)
        regex = re.compile(pattern, re.IGNORECASE)

        matches_correct = all(regex.search(s) for s in should_match)
        non_matches_correct = all(not regex.fullmatch(s) for s in should_not_match)

        status = "PASS" if matches_correct and non_matches_correct else "FAIL"
        if not (matches_correct and non_matches_correct):
            all_passed = False
        print(f"  {item_name} ({form_type or 'None'}): pattern='{pattern[:30]}...' [{status}]")

    return all_passed


def test_10k_item_structure():
    """Test 10-K item structure is complete and correct."""
    print("\n" + "=" * 60)
    print("TEST: 10-K Item Structure")
    print("=" * 60)

    expected_items = [
        "Item 1", "Item 1A", "Item 1B", "Item 1C", "Item 2", "Item 3", "Item 4",
        "Item 5", "Item 6", "Item 7", "Item 7A", "Item 8", "Item 9", "Item 9A",
        "Item 9B", "Item 9C", "Item 10", "Item 11", "Item 12", "Item 13", "Item 14",
        "Item 15", "Item 16"
    ]

    all_passed = True
    missing = []
    for item in expected_items:
        if item not in FORM_10K_ITEMS:
            missing.append(item)
            all_passed = False

    status = "PASS" if not missing else "FAIL"
    print(f"  All expected items present: {not missing} [{status}]")
    if missing:
        print(f"    Missing: {missing}")

    # Check parts are assigned
    parts = {"Part I", "Part II", "Part III", "Part IV"}
    found_parts = set(info.get("part") for info in FORM_10K_ITEMS.values())
    has_all_parts = parts.issubset(found_parts)
    status = "PASS" if has_all_parts else "FAIL"
    if not has_all_parts:
        all_passed = False
    print(f"  All parts (I-IV) represented: {has_all_parts} [{status}]")

    return all_passed


def test_20f_subitems():
    """Test 20-F sub-item structure."""
    print("\n" + "=" * 60)
    print("TEST: 20-F Sub-item Structure")
    print("=" * 60)

    # Check parent-child relationships
    parent_items = ["Item 3", "Item 4", "Item 5", "Item 6", "Item 7", "Item 8",
                    "Item 9", "Item 10", "Item 12", "Item 16"]

    all_passed = True
    for parent in parent_items:
        info = FORM_20F_ITEMS.get(parent, {})
        sub_items = info.get("sub_items", [])

        # Check that sub-items exist and have correct parent
        if sub_items:
            for sub in sub_items:
                sub_info = FORM_20F_ITEMS.get(sub, {})
                has_correct_parent = sub_info.get("parent") == parent
                if not has_correct_parent:
                    all_passed = False
                    print(f"  {sub} parent mismatch: expected {parent}, got {sub_info.get('parent')} [FAIL]")

    # Count sub-items
    sub_item_count = sum(1 for info in FORM_20F_ITEMS.values() if "parent" in info)
    print(f"  Total sub-items with parent links: {sub_item_count}")
    print(f"  Parent-child relationships: {'PASS' if all_passed else 'FAIL'}")

    return all_passed


def test_real_filing_extraction():
    """Test extraction from a real filing (requires network). Saves output to .md file."""
    print("\n" + "=" * 60)
    print("TEST: Real Filing Extraction (Network Required)")
    print("=" * 60)

    try:
        from edgar import Company

        # Get Apple's latest 10-K
        print("  Fetching Apple's latest 10-K...")
        company = Company("pltr")
        filings = company.get_filings(form="10-K")
        if not filings:
            print("  No 10-K filings found [SKIP]")
            return True

        filing = filings[0]
        print(f"  Found: {filing.form} filed {filing.filing_date}")

        # Test extraction
        from edgar.llm_extraction import extract_filing_sections

        # Test multiple items and save to markdown
        test_items = ["Item 1", "Item 1A", "Item 7", "Item 7A", "Item 8"]

        output_file = f"extraction_test_{filing.form}_{filing.filing_date}.md"

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# Extraction Test Results\n\n")
            f.write(f"**Form:** {filing.form}\n\n")
            f.write(f"**Filing Date:** {filing.filing_date}\n\n")
            f.write(f"**Accession Number:** {filing.accession_no}\n\n")
            f.write(f"**Company:** {filing.company}\n\n")
            f.write("---\n\n")

            for item in test_items:
                print(f"  Extracting {item}...")
                sections = extract_filing_sections(filing, item=item)

                if sections:
                    section = sections[0]
                    length = len(section.markdown)
                    print(f"    {item}: {length:,} chars")

                    f.write(f"## {item}\n\n")
                    f.write(f"**Title:** {section.title}\n\n")
                    f.write(f"**Source:** {section.source}\n\n")
                    f.write(f"**Length:** {length:,} chars\n\n")
                    f.write("### Content\n\n")
                    f.write(section.markdown)
                    f.write("\n\n---\n\n")
                else:
                    print(f"    {item}: NOT FOUND")
                    f.write(f"## {item}\n\n")
                    f.write("**NOT FOUND**\n\n---\n\n")

        print(f"\n  Output saved to: {output_file}")
        return True

    except ImportError as e:
        print(f"  Import error: {e} [SKIP]")
        return True
    except Exception as e:
        print(f"  Error: {e} [SKIP]")
        import traceback
        traceback.print_exc()
        return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("LLM EXTRACTION - FORM ITEM TESTS")
    print("=" * 60)

    results = []

    # Run unit tests
    results.append(("Form Item Counts", test_form_item_counts()))
    results.append(("Form Registry", test_form_registry()))
    results.append(("Item Normalization", test_item_normalization()))
    results.append(("Item Boundaries", test_item_boundaries()))
    results.append(("Item Titles", test_item_titles()))
    results.append(("get_form_items()", test_get_form_items()))
    results.append(("get_item_info()", test_get_item_info()))
    results.append(("Regex Patterns", test_regex_patterns()))
    results.append(("10-K Structure", test_10k_item_structure()))
    results.append(("20-F Sub-items", test_20f_subitems()))

    # Optional network test
    print("\n" + "-" * 60)
    run_network = input("Run network test (requires internet)? [y/N]: ").strip().lower()
    if run_network == 'y':
        results.append(("Real Filing Extraction", test_real_filing_extraction()))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {name}: {status}")

    print(f"\n  Total: {passed}/{total} passed")

    if passed == total:
        print("\n  ALL TESTS PASSED!")
    else:
        print(f"\n  {total - passed} test(s) FAILED")

    return passed == total


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
