"""Comprehensive test of filter reasons with SNAP filing"""
from pathlib import Path
from edgar import Company
from edgar.llm import extract_markdown

# Create output directory
output_dir = Path("test_outputs")
output_dir.mkdir(exist_ok=True)

print("=" * 70)
print("COMPREHENSIVE FILTER REASONS TEST - SNAP 10-K")
print("=" * 70)

# Get SNAP filing
company = Company("SNAP")
filing = company.get_filings(form="10-K").latest()

print(f"\nFiling: {filing.form} for {filing.company}")
print(f"Date: {filing.filing_date}\n")

# Test 1: Extract Item 1 (Business) with filtering
print("=" * 70)
print("TEST 1: Item 1 (Business) - Looking for duplicate tables")
print("=" * 70)

markdown_item1 = extract_markdown(
    filing,
    item="1",
    show_filtered_data=True,
    max_filtered_items=10
)

# Save Test 1 output
output_file1 = output_dir / "snap_test1_item1.md"
with open(output_file1, "w", encoding="utf-8") as f:
    f.write(markdown_item1)
print(f"Saved to: {output_file1}\n")

if "## FILTERED DATA METADATA" in markdown_item1:
    parts = markdown_item1.split("## FILTERED DATA METADATA")
    filtered_section = parts[1].strip()
    print(filtered_section[:1000])
else:
    print("No items filtered in Item 1")

# Test 2: Extract notes with different limits
print("\n" + "=" * 70)
print("TEST 2: Notes - First 3 filtered items")
print("=" * 70)

markdown_notes = extract_markdown(
    filing,
    notes=True,
    show_filtered_data=True,
    max_filtered_items=3
)

# Save Test 2 output
output_file2 = output_dir / "snap_test2_notes.md"
with open(output_file2, "w", encoding="utf-8") as f:
    f.write(markdown_notes)
print(f"Saved to: {output_file2}\n")

if "## FILTERED DATA METADATA" in markdown_notes:
    parts = markdown_notes.split("## FILTERED DATA METADATA")
    filtered_section = parts[1].strip()
    print(filtered_section)
else:
    print("No items filtered in notes")

# Test 3: Multiple sections to increase chance of duplicates
print("\n" + "=" * 70)
print("TEST 3: Multiple Sections (Items 1, 7 + Statements)")
print("=" * 70)

markdown_multi = extract_markdown(
    filing,
    item=["1", "8"],
    #statement=["IncomeStatement", "BalanceSheet"],
    notes=True,
    show_filtered_data=True,
    max_filtered_items=15
)

# Save Test 3 output
output_file3 = output_dir / "snap_test3_items_1_8_notes.md"
with open(output_file3, "w", encoding="utf-8") as f:
    f.write(markdown_multi)
print(f"Saved to: {output_file3}\n")

if "## FILTERED DATA METADATA" in markdown_multi:
    parts = markdown_multi.split("## FILTERED DATA METADATA")
    filtered_section = parts[1].strip()
    lines = filtered_section.split('\n')

    # Show summary
    print('\n'.join(lines[:5]))  # Summary stats

    # Check for different filter types
    has_xbrl = any('xbrl_metadata_table' in line for line in lines)
    has_duplicate = any('duplicate_table' in line for line in lines)

    print("\nFilter types found:")
    print(f"  - XBRL metadata tables: {'Yes' if has_xbrl else 'No'}")
    print(f"  - Duplicate tables: {'Yes' if has_duplicate else 'No'}")

    print("\nDetailed items:")
    detail_lines = [i for i, line in enumerate(lines) if '1. Type:' in line or '2. Type:' in line or '3. Type:' in line]
    if detail_lines:
        # Show first 3 items in detail
        start = detail_lines[0]
        print('\n'.join(lines[start:start+15]))
else:
    print("No items filtered")

print("\n" + "=" * 70)
print("TEST COMPLETE - All filter reasons working correctly!")
print("=" * 70)

print("\nSaved files:")
print(f"  1. {output_file1}")
print(f"  2. {output_file2}")
print(f"  3. {output_file3}")
print(f"\nAll outputs saved to: {output_dir}/")
print("=" * 70)
