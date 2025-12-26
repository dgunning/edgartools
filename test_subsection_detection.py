"""Test subsection detection in LLM markdown extraction"""
from edgar import Company
from edgar.llm import extract_markdown
from pathlib import Path

def test_subsection_detection(ticker, expected_subsections):
    """Test that subsections are properly detected and converted to markdown headings."""
    print(f"\n{'='*70}")
    print(f"Testing {ticker}")
    print('='*70)

    try:
        company = Company(ticker)
        filing = company.get_filings(form="10-K").latest()

        print(f"Filing: {filing.form} - {filing.filing_date}")

        # Extract Item 1 with new subsection detection
        markdown = extract_markdown(filing, item="1")

        # Save output for inspection
        output_dir = Path("test_outputs/subsection_detection")
        output_dir.mkdir(exist_ok=True, parents=True)

        output_file = output_dir / f"{ticker}_item1_with_subsections.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(markdown)

        print(f"Saved to: {output_file}")

        # Check for expected subsections
        print(f"\nChecking for expected subsections:")
        found_count = 0
        for subsection in expected_subsections:
            # Check for ### or ####
            if f"### {subsection}" in markdown or f"#### {subsection}" in markdown:
                # Determine which level
                if f"### {subsection}" in markdown:
                    level = "###"
                else:
                    level = "####"
                print(f"  [OK] Found: {level} {subsection}")
                found_count += 1
            else:
                print(f"  [MISS] Missing: {subsection}")

        print(f"\nFound {found_count}/{len(expected_subsections)} expected subsections")

        # Count all subsection headings
        level3_count = markdown.count('\n### ')
        level4_count = markdown.count('\n#### ')
        print(f"Total subsections: {level3_count} level-3 (###), {level4_count} level-4 (####)")

        return {
            'ticker': ticker,
            'found': found_count,
            'expected': len(expected_subsections),
            'level3': level3_count,
            'level4': level4_count,
            'file': output_file
        }

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

# Test configurations
tests = [
    {
        'ticker': 'SNAP',
        'expected': [
            'Overview',
            'Snapchat',
            'Our Partner Ecosystem',
            'Our Advertising Products',
            'Technology',
            'Employees and Culture',
            'Competition',
            'Intellectual Property',
        ]
    },
    {
        'ticker': 'AAPL',
        'expected': [
            'Company Background',
            'Products',
            'iPhone',
            'Mac',
            'iPad',
            'Services',
            'Advertising',
            'AppleCare',
            'Competition',
        ]
    },
    {
        'ticker': 'BFLY',
        'expected': [
            'Overview',
            'Market Opportunity',
            'Business Strategy',
            'Products',
            'Marketing and Sales',
        ]
    },
]

# Run tests
results = []
for test in tests:
    result = test_subsection_detection(test['ticker'], test['expected'])
    if result:
        results.append(result)

# Summary
print(f"\n{'='*70}")
print("SUMMARY")
print('='*70)
print(f"{'Ticker':<10} {'Found':<10} {'Expected':<10} {'L3 (###)':<10} {'L4 (####)':<10}")
print('-'*70)
for r in results:
    print(f"{r['ticker']:<10} {r['found']:<10} {r['expected']:<10} {r['level3']:<10} {r['level4']:<10}")

print(f"\n{'='*70}")
print("Test complete! Check output files for detailed results.")
print('='*70)
