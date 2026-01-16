"""
Example: Using table_max_col_width for AI-friendly text extraction

This demonstrates how to control table column width when extracting text
from SEC filings, useful for AI/LLM processing where you need complete
table labels without truncation.
"""

from edgar import Company, set_identity

# Set your identity for SEC requests
set_identity("Your Name your.email@example.com")

# Get a filing
company = Company("AAPL")
filing = company.get_filings(form="10-K").latest(1)

# Get the TenK object, then access its document property
tenk = filing.obj()
doc = tenk.document  # This is the Document object with text() method

print("=" * 80)
print("Example 1: Default behavior (max_col_width=200)")
print("=" * 80)
text_default = doc.text(max_length=3000)
print(text_default)
print("\n\n" + "=" * 80)
print("Example 2: Wider columns for long labels (max_col_width=500)")
print("=" * 80)
text_wide = doc.text(max_length=3000, table_max_col_width=500)
print(text_wide)

print("\n\n" + "=" * 80)
print("Example 3: Unlimited width (table_max_col_width=None)")
print("=" * 80)
text_unlimited = doc.text(max_length=3000, table_max_col_width=None)
print(text_unlimited)

print("\n\n" + "=" * 80)
print("Example 4: For AI/LLM - get full text with wide tables")
print("=" * 80)
# This is ideal for feeding to AI models where you want complete information
ai_text = doc.text(
    clean=True,              # Clean text for readability
    include_tables=True,     # Include table data
    table_max_col_width=500  # Wide columns to avoid truncation
)
print(f"Total characters: {len(ai_text)}")
print(f"Preview:\n{ai_text[:2000]}...")

# For very long documents, you can also combine with max_length
ai_text_limited = doc.text(
    clean=True,
    include_tables=True,
    table_max_col_width=500,
    max_length=50000  # Limit total length for token budgets
)
print(f"\n\nWith max_length: {len(ai_text_limited)} characters")
