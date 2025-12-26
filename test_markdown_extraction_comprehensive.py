"""Comprehensive test of markdown extraction with subsection detection for items and notes"""
from edgar import Company
from edgar.llm import extract_markdown
from pathlib import Path

def test_comprehensive_extraction(ticker):
    """Extract all items and notes to test subsection detection."""
    print(f"\n{'='*70}")
    print(f"Testing {ticker} - Comprehensive Extraction")
    print('='*70)

    try:
        company = Company(ticker)
        filing = company.get_filings(form="10-K").latest()

        print(f"Filing: {filing.form} - {filing.filing_date}")

        # Create output directory
        output_dir = Path("test_outputs/subsection_detection")
        output_dir.mkdir(exist_ok=True, parents=True)

        # Test 1: Extract Item 1
        print("\n1. Extracting Item 1...")
        markdown_item1 = extract_markdown(filing, item="Item 1")
        file_item1 = output_dir / f"{ticker}_item1.md"
        with open(file_item1, "w", encoding="utf-8", newline='\n') as f:
            f.write(markdown_item1)
        subsection_count1 = markdown_item1.count('\n###')
        print(f"   Saved to: {file_item1.name}")
        print(f"   Subsections found: {subsection_count1}")

        # Test 2: Extract Item 1A (Risk Factors)
        print("\n2. Extracting Item 1A (Risk Factors)...")
        markdown_item1a = extract_markdown(filing, item="Item 1A")
        file_item1a = output_dir / f"{ticker}_item1A.md"
        with open(file_item1a, "w", encoding="utf-8", newline='\n') as f:
            f.write(markdown_item1a)
        subsection_count1a = markdown_item1a.count('\n###')
        print(f"   Saved to: {file_item1a.name}")
        print(f"   Subsections found: {subsection_count1a}")

        # Test 3: Extract Item 7 (MD&A)
        print("\n3. Extracting Item 7 (MD&A)...")
        markdown_item7 = extract_markdown(filing, item="Item 7")
        file_item7 = output_dir / f"{ticker}_item7.md"
        with open(file_item7, "w", encoding="utf-8", newline='\n') as f:
            f.write(markdown_item7)
        subsection_count7 = markdown_item7.count('\n###')
        print(f"   Saved to: {file_item7.name}")
        print(f"   Subsections found: {subsection_count7}")

        # Test 4: Extract Notes
        print("\n4. Extracting Financial Notes...")
        markdown_notes = extract_markdown(filing, notes=True)
        file_notes = output_dir / f"{ticker}_notes.md"
        with open(file_notes, "w", encoding="utf-8", newline='\n') as f:
            f.write(markdown_notes)
        subsection_count_notes = markdown_notes.count('\n###')
        print(f"   Saved to: {file_notes.name}")
        print(f"   Subsections found: {subsection_count_notes}")

        # Test 5: Extract multiple items together
        print("\n5. Extracting Items 1, 1A, 7 together...")
        markdown_multi = extract_markdown(filing, item=["9"])
        file_multi = output_dir / f"{ticker}_items_9.md"
        with open(file_multi, "w", encoding="utf-8", newline='\n') as f:
            f.write(markdown_multi)
        subsection_count_multi = markdown_multi.count('\n###')
        print(f"   Saved to: {file_multi.name}")
        print(f"   Subsections found: {subsection_count_multi}")

        return {
            'ticker': ticker,
            'item1_subsections': subsection_count1,
            'item1a_subsections': subsection_count1a,
            'item7_subsections': subsection_count7,
            'notes_subsections': subsection_count_notes,
            'multi_subsections': subsection_count_multi,
        }

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

# Test companies
tickers = ["SNAP", "AAPL", "BFLY"]
results = []

for ticker in tickers:
    result = test_comprehensive_extraction(ticker)
    if result:
        results.append(result)

# Summary
print(f"\n{'='*70}")
print("SUMMARY - Subsection Detection Across Items and Notes")
print('='*70)
print(f"{'Ticker':<10} {'Item 1':<10} {'Item 1A':<10} {'Item 7':<10} {'Notes':<10} {'Multi':<10}")
print('-'*70)
for r in results:
    print(f"{r['ticker']:<10} {r['item1_subsections']:<10} {r['item1a_subsections']:<10} {r['item7_subsections']:<10} {r['notes_subsections']:<10} {r['multi_subsections']:<10}")

print(f"\n{'='*70}")
print("Extraction complete! Check test_outputs/subsection_detection/ for all files.")
print('='*70)
