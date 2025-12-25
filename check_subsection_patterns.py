"""Check subsection patterns across different companies"""
from edgar import Company
from edgar.llm import extract_markdown
from pathlib import Path
import re

def analyze_subsection_patterns(ticker, output_dir):
    """Extract Item 1 and analyze subsection patterns."""
    print(f"\n{'='*70}")
    print(f"Analyzing {ticker}")
    print('='*70)

    try:
        company = Company(ticker)
        filing = company.get_filings(form="10-K").latest()

        print(f"Filing: {filing.form} - {filing.filing_date}")

        # Extract Item 1
        markdown = extract_markdown(filing, item="1")

        # Save to file
        output_file = output_dir / f"{ticker}_item1.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(markdown)
        print(f"Saved to: {output_file}")

        # Analyze patterns
        lines = markdown.split('\n')

        # Find standalone short lines (potential subsections)
        potential_subsections = []
        for i, line in enumerate(lines):
            stripped = line.strip()

            # Skip if empty, too long, or already a heading
            if not stripped or len(stripped) > 80 or stripped.startswith('#'):
                continue

            # Check if it's a short standalone line
            prev_line = lines[i-1].strip() if i > 0 else ""
            next_line = lines[i+1].strip() if i < len(lines)-1 else ""

            # Potential subsection if:
            # - Short line (< 80 chars)
            # - Surrounded by empty lines or followed by content
            # - Not part of a list
            # - Title case or all caps
            if (len(stripped) < 80 and
                prev_line == "" and
                not stripped.startswith('•') and
                not stripped.startswith('-')):

                # Check if title case or all caps
                words = stripped.split()
                if words:
                    first_word = words[0]
                    if (first_word[0].isupper() or
                        stripped.isupper() or
                        stripped.istitle()):
                        potential_subsections.append((i, stripped))

        # Find "Title: Description" patterns
        title_desc_patterns = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if ':' in stripped and len(stripped) < 200:
                parts = stripped.split(':', 1)
                if len(parts) == 2:
                    title = parts[0].strip()
                    desc = parts[1].strip()
                    # Title should be short and start with capital
                    if (len(title) < 50 and
                        title and title[0].isupper() and
                        len(desc) > 20):
                        title_desc_patterns.append((i, title, desc[:100] + "..."))

        # Print findings
        print(f"\nFound {len(potential_subsections)} potential subsection headers:")
        for i, (line_num, text) in enumerate(potential_subsections[:15], 1):
            print(f"  {i}. Line {line_num}: {text}")

        if len(potential_subsections) > 15:
            print(f"  ... and {len(potential_subsections) - 15} more")

        print(f"\nFound {len(title_desc_patterns)} 'Title: Description' patterns:")
        for i, (line_num, title, desc) in enumerate(title_desc_patterns[:15], 1):
            print(f"  {i}. Line {line_num}: {title}")
            print(f"     → {desc}")

        if len(title_desc_patterns) > 15:
            print(f"  ... and {len(title_desc_patterns) - 15} more")

        return {
            'ticker': ticker,
            'subsections': len(potential_subsections),
            'title_desc': len(title_desc_patterns),
            'file': output_file
        }

    except Exception as e:
        print(f"Error processing {ticker}: {e}")
        import traceback
        traceback.print_exc()
        return None

# Create output directory
output_dir = Path("test_outputs/subsection_analysis")
output_dir.mkdir(exist_ok=True, parents=True)

# Analyze multiple tickers
tickers = ["SNAP", "NVDA", "AAPL", "BFLY"]
results = []

for ticker in tickers:
    result = analyze_subsection_patterns(ticker, output_dir)
    if result:
        results.append(result)

# Summary
print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print(f"{'Ticker':<10} {'Subsections':<15} {'Title:Desc':<15} {'File'}")
print("-"*70)
for r in results:
    print(f"{r['ticker']:<10} {r['subsections']:<15} {r['title_desc']:<15} {r['file'].name}")

print("\n" + "="*70)
print("Analysis complete! Check files for detailed patterns.")
print("="*70)
