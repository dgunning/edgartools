"""
Demonstration of show_dimension parameter
"""
from edgar import Company
from edgar.llm import extract_markdown

print("=" * 80)
print("SHOW_DIMENSION PARAMETER DEMONSTRATION")
print("=" * 80)

# Get a filing
snap = Company("SNAP")
filing = snap.get_filings(form='10-K').latest()

print(f"\nFiling: {filing}")
print(f"Date: {filing.filing_date}")

# Test 1: WITH dimension columns (show_dimension=True, default)
print("\n" + "=" * 80)
print("Test 1: show_dimension=True (DEFAULT)")
print("=" * 80)

markdown_with_dims = extract_markdown(
    filing,
    statement="IncomeStatement",
    show_dimension=True,  # <-- Show level, abstract, dimension columns
    include_header=False
)

print("\nExtracted statement WITH dimension columns:")
print(markdown_with_dims[:800])
print("...")

# Count columns
lines = markdown_with_dims.split('\n')
header_line = [line for line in lines if '|' in line and 'label' in line.lower()]
if header_line:
    num_cols_with = header_line[0].count('|') - 1
    print(f"\nNumber of columns: {num_cols_with}")
    print(f"Columns: {header_line[0]}")

# Test 2: WITHOUT dimension columns (show_dimension=False)
print("\n" + "=" * 80)
print("Test 2: show_dimension=False")
print("=" * 80)

markdown_without_dims = extract_markdown(
    filing,
    statement="IncomeStatement",
    show_dimension=False,  # <-- Hide level, abstract, dimension columns
    include_header=False
)

print("\nExtracted statement WITHOUT dimension columns:")
print(markdown_without_dims[:800])
print("...")

# Count columns
lines = markdown_without_dims.split('\n')
header_line = [line for line in lines if '|' in line and 'label' in line.lower()]
if header_line:
    num_cols_without = header_line[0].count('|') - 1
    print(f"\nNumber of columns: {num_cols_without}")
    print(f"Columns: {header_line[0]}")

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

print(f"\nWith show_dimension=True:  {num_cols_with} columns (includes level, abstract, dimension)")
print(f"With show_dimension=False: {num_cols_without} columns (hides level, abstract, dimension)")
print(f"\nColumns hidden: {num_cols_with - num_cols_without}")

print("\n" + "=" * 80)
print("USAGE RECOMMENDATIONS")
print("=" * 80)

print("""
When to use show_dimension=True (default):
- When you need full detail about statement structure
- For detailed financial analysis
- When you want to see dimensionality (segments, subsidiaries, etc.)

When to use show_dimension=False:
- For cleaner, simpler output
- When you only need the core financial data
- To reduce token count for LLM processing
- For general-purpose financial data extraction

Example:
    # Clean, simple output
    markdown = extract_markdown(
        filing,
        statement="IncomeStatement",
        show_dimension=False  # Just show label + period columns
    )
""")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
