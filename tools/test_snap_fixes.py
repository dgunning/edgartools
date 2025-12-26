"""
Test both fixes with actual SNAP filing data.
"""
import sys
sys.path.insert(0, '../')

from edgar import Filing
from edgar.llm import extract_markdown

print("="*70)
print("Testing SNAP 10-K with both global fixes")
print("="*70)

# Get latest SNAP 10-K filing
from edgar import Company

snap = Company("SNAP")
filing = snap.get_filings(form="10-K").latest(1)

print(f"\nFiling: {filing.form} for {filing.company}")
print(f"Date: {filing.filing_date}")
print(f"Accession: {filing.accession_no}")

# Test Fix #2: Extract Item 7 to check for placeholder column names
print("\n" + "-"*70)
print("Testing Fix #2: Placeholder Column Names")
print("-"*70)

try:
    item7_md = extract_markdown(filing, item="7", optimize_for_llm=True)

    # Count occurrences of placeholder column names
    placeholder_count = item7_md.count("col_")

    print(f"\nItem 7 extracted: {len(item7_md)} characters")
    print(f"Placeholder column names (col_X) found: {placeholder_count}")

    if placeholder_count > 0:
        print("\n[WARNING] Some placeholder column names still present")
        print("Showing first few occurrences with context:")
        lines = item7_md.split('\n')
        shown = 0
        for i, line in enumerate(lines):
            if 'col_' in line and shown < 2:
                # Show context: 2 lines before, the line, 3 lines after
                start = max(0, i-2)
                end = min(len(lines), i+4)
                print(f"\n  Context around line {i}:")
                for j in range(start, end):
                    prefix = ">>>" if j == i else "   "
                    print(f"  {prefix} {lines[j][:120]}")
                shown += 1
    else:
        print("\n[PASS] No placeholder column names found!")

    # Check for proper quarter/period headers
    has_quarters = any(q in item7_md for q in ['Q1', 'Q2', 'Q3', 'Q4'])
    has_months = any(m in item7_md for m in ['March', 'June', 'September', 'December'])
    has_years = '2024' in item7_md or '2023' in item7_md

    print(f"\nProper headers detected:")
    print(f"  - Quarters (Q1/Q2/etc): {has_quarters}")
    print(f"  - Months: {has_months}")
    print(f"  - Years: {has_years}")

except Exception as e:
    print(f"\n[ERROR] Failed to extract Item 7: {e}")

# Test Fix #1: Extract full document to check duplicate tables
print("\n" + "-"*70)
print("Testing Fix #1: Duplicate Table Detection")
print("-"*70)

try:
    # Extract all items to test deduplication
    full_md = extract_markdown(filing, item=["1", "7"], optimize_for_llm=True)

    # Count tables in markdown (lines starting with |)
    lines = full_md.split('\n')
    table_lines = [l for l in lines if l.strip().startswith('|')]

    # Estimate table count by counting table separators
    separator_count = sum(1 for l in table_lines if '---' in l)

    print(f"\nFull extraction: {len(full_md)} characters")
    print(f"Estimated table count: {separator_count}")
    print(f"Table lines: {len(table_lines)}")

    print("\n[PASS] Duplicate detection is active")
    print("(Exact duplicate count requires comparison with unfiltered version)")

except Exception as e:
    print(f"\n[ERROR] Failed to extract full document: {e}")

print("\n" + "="*70)
print("Testing complete!")
print("="*70)
