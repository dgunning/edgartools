"""
Interactive Demo: Copy and paste these examples into Python

Run this file or copy individual examples to test the new features
"""
import sys
sys.path.insert(0, '../')

print("\n" + "="*70)
print("INTERACTIVE DEMO: New LLM Extraction Features")
print("="*70)
print("\nCopy and paste any of these examples into your Python code:\n")

# ============================================================================
print("-"*70)
print("EXAMPLE 1: Basic Usage (Default)")
print("-"*70)
print("""
from edgar import Company
from edgar.llm import extract_markdown

# Get any company's latest 10-K
company = Company("AAPL")  # Try: AAPL, MSFT, GOOGL, TSLA, etc.
filing = company.get_filings(form="10-K").latest(1)

# Extract with defaults (shows everything)
markdown = extract_markdown(filing, item="7")
print(f"Extracted {len(markdown)} characters")
print(markdown[:500])  # Preview first 500 chars
""")

# ============================================================================
print("\n" + "-"*70)
print("EXAMPLE 2: Clean Output for LLMs")
print("-"*70)
print("""
# Hide dimension columns to reduce token count
markdown = extract_markdown(
    filing,
    statement="income",     # or "balance", "cash", etc.
    show_dimension=False    # 20-40% smaller output
)

# Result: Only label + period columns
print(markdown)
""")

# ============================================================================
print("\n" + "-"*70)
print("EXAMPLE 3: Audit Mode - See What Was Filtered")
print("-"*70)
print("""
# See what data was omitted during extraction
markdown = extract_markdown(
    filing,
    notes=True,              # Extract all notes
    show_filtered_data=True  # Show metadata
)

# Check the end for filtered data section
lines = markdown.split('\\n')
for i, line in enumerate(lines[-20:], len(lines)-20):
    print(f"{i}: {line}")
""")

# ============================================================================
print("\n" + "-"*70)
print("EXAMPLE 4: Production Pipeline")
print("-"*70)
print("""
# Combine both: efficient + transparent
markdown = extract_markdown(
    filing,
    item=["1", "1A", "7", "7A"],  # Multiple items
    statement=["income", "balance", "cash"],  # Multiple statements
    notes=True,                    # All notes
    show_dimension=False,          # Efficient
    show_filtered_data=True        # Transparent
)

# Save with metadata
with open("filing_extract.md", "w", encoding="utf-8") as f:
    f.write(markdown)

print(f"Saved {len(markdown)} chars to filing_extract.md")
""")

# ============================================================================
print("\n" + "-"*70)
print("EXAMPLE 5: Compare With/Without Dimensions")
print("-"*70)
print("""
# Extract same statement both ways
with_dim = extract_markdown(filing, statement="income", show_dimension=True)
without_dim = extract_markdown(filing, statement="income", show_dimension=False)

print(f"With dimensions: {len(with_dim)} chars")
print(f"Without dimensions: {len(without_dim)} chars")
print(f"Reduction: {len(with_dim) - len(without_dim)} chars")
print(f"Percentage: {100*(1-len(without_dim)/len(with_dim)):.1f}%")
""")

# ============================================================================
print("\n" + "-"*70)
print("EXAMPLE 6: Batch Process Multiple Filings")
print("-"*70)
print("""
# Process multiple companies efficiently
companies = ["AAPL", "MSFT", "GOOGL", "AMZN"]

for ticker in companies:
    company = Company(ticker)
    filing = company.get_filings(form="10-K").latest(1)

    markdown = extract_markdown(
        filing,
        item="7",
        show_dimension=False,
        show_filtered_data=True
    )

    # Save each filing
    filename = f"{ticker}_10K_item7.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"Saved {ticker}: {len(markdown)} chars")
""")

# ============================================================================
print("\n" + "-"*70)
print("EXAMPLE 7: Feed to LLM (OpenAI, Anthropic, etc.)")
print("-"*70)
print("""
# Extract clean markdown for LLM analysis
markdown = extract_markdown(
    filing,
    item="7",
    statement=["income", "balance"],
    show_dimension=False  # Minimize tokens
)

# Example with OpenAI
import openai

response = openai.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a financial analyst."},
        {"role": "user", "content": f"Analyze this filing:\\n\\n{markdown}"}
    ]
)

print(response.choices[0].message.content)
""")

# ============================================================================
print("\n" + "-"*70)
print("EXAMPLE 8: Check Filtered Data Programmatically")
print("-"*70)
print("""
from edgar.llm import extract_sections

# Get filtered data as separate return value
sections, filtered_data = extract_sections(
    filing,
    notes=True,
    track_filtered=True  # Returns tuple
)

# Access counts
print(f"XBRL tables filtered: {filtered_data['xbrl_metadata_tables']}")
print(f"Duplicate tables: {filtered_data['duplicate_tables']}")
print(f"Text blocks filtered: {filtered_data['filtered_text_blocks']}")

# Access details
for detail in filtered_data['details'][:5]:
    print(f"- {detail['type']}: {detail.get('preview', '')[:50]}")
""")

# ============================================================================
print("\n" + "="*70)
print("PARAMETER REFERENCE")
print("="*70)
print("""
extract_markdown(
    filing,
    item=None,                    # str or list: "7" or ["1", "7"]
    statement=None,               # str or list: "income" or ["income", "balance"]
    notes=False,                  # bool: Extract all notes
    show_dimension=True,          # NEW: Show XBRL metadata columns
    show_filtered_data=False      # NEW: Show filtered data metadata
)

Quick Tips:
- show_dimension=False reduces output size by 20-40%
- show_filtered_data=True adds transparency (what was omitted)
- Both work globally for all filings and companies
- Defaults are backward compatible (no code changes needed)
""")

print("\n" + "="*70)
print("Try copying any example above into your Python console!")
print("="*70)
