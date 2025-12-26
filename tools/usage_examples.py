"""
Examples: Using the new LLM extraction features

New Parameters:
1. show_dimension (bool, default=True): Control visibility of XBRL dimension columns
2. show_filtered_data (bool, default=False): Show metadata about filtered/omitted data
"""
import sys
sys.path.insert(0, '../')

from edgar import Company
from edgar.llm import extract_markdown

# Get a filing to work with
print("="*70)
print("SETUP: Getting SNAP 10-K filing")
print("="*70)

snap = Company("SNAP")
filing = snap.get_filings(form="10-K").latest(1)

print(f"Filing: {filing.form} for {filing.company}")
print(f"Date: {filing.filing_date}\n")

# ============================================================================
# EXAMPLE 1: Basic Usage (Default Behavior)
# ============================================================================
print("="*70)
print("EXAMPLE 1: Basic Usage (all defaults)")
print("="*70)
print("""
from edgar.llm import extract_markdown

# Extract Item 7 with default settings
markdown = extract_markdown(filing, item="7")

# Defaults:
# - show_dimension=True  (shows level, abstract, dimension columns in XBRL statements)
# - show_filtered_data=False  (no metadata about filtered data)
""")

markdown_default = extract_markdown(filing, item="7")
print(f"\nResult: {len(markdown_default)} characters")
print("First 500 characters:")
print(markdown_default[:500])
print("...")

# ============================================================================
# EXAMPLE 2: Hide Dimension Columns (Cleaner for LLMs)
# ============================================================================
print("\n" + "="*70)
print("EXAMPLE 2: Hide Dimension Columns")
print("="*70)
print("""
# When extracting financial statements, you can hide XBRL metadata columns
# to make the output cleaner and more LLM-friendly

markdown = extract_markdown(
    filing,
    statement="income",  # Extract income statement
    show_dimension=False  # Hide level, abstract, dimension columns
)

# Result: Only shows label and period columns (cleaner for analysis)
""")

markdown_no_dim = extract_markdown(
    filing,
    statement="income",
    show_dimension=False
)
print(f"\nResult: {len(markdown_no_dim)} characters")
print("Preview:")
lines = markdown_no_dim.split('\n')[:15]
print('\n'.join(lines))

# ============================================================================
# EXAMPLE 3: Show Dimension Columns (Full Detail)
# ============================================================================
print("\n" + "="*70)
print("EXAMPLE 3: Show Dimension Columns (Default)")
print("="*70)
print("""
# Keep dimension columns for detailed XBRL analysis

markdown = extract_markdown(
    filing,
    statement="income",
    show_dimension=True  # Show level, abstract, dimension columns
)

# Result: Includes metadata columns for XBRL structure analysis
""")

markdown_with_dim = extract_markdown(
    filing,
    statement="income",
    show_dimension=True
)
print(f"\nResult: {len(markdown_with_dim)} characters")
print("Preview (showing dimension columns):")
lines = markdown_with_dim.split('\n')[:15]
print('\n'.join(lines))

# Compare sizes
print(f"\nSize comparison:")
print(f"  With dimensions: {len(markdown_with_dim)} chars")
print(f"  Without dimensions: {len(markdown_no_dim)} chars")
print(f"  Reduction: {len(markdown_with_dim) - len(markdown_no_dim)} chars ({100*(1-len(markdown_no_dim)/len(markdown_with_dim)):.1f}%)")

# ============================================================================
# EXAMPLE 4: Show Filtered Data Metadata
# ============================================================================
print("\n" + "="*70)
print("EXAMPLE 4: Show Filtered Data Metadata")
print("="*70)
print("""
# See what data was filtered/omitted during extraction

markdown = extract_markdown(
    filing,
    notes=True,  # Extract all notes
    show_filtered_data=True  # Append metadata about filtered items
)

# Result: Markdown includes a section at the end showing:
# - Number of XBRL metadata tables filtered
# - Number of duplicate tables removed
# - Number of text blocks filtered
# - Details about each filtered item
""")

markdown_with_metadata = extract_markdown(
    filing,
    notes=True,
    show_filtered_data=True
)

# Show the metadata section
lines = markdown_with_metadata.split('\n')
# Find the metadata section
metadata_start = None
for i, line in enumerate(lines):
    if "FILTERED DATA METADATA" in line:
        metadata_start = i - 2
        break

if metadata_start:
    print("\nFiltered data metadata section:")
    print('\n'.join(lines[metadata_start:metadata_start+20]))
else:
    print("\nNo filtered data metadata found (nothing was filtered)")

# ============================================================================
# EXAMPLE 5: Combining Both Parameters
# ============================================================================
print("\n" + "="*70)
print("EXAMPLE 5: Combining Both Parameters")
print("="*70)
print("""
# Use both parameters together for maximum control

markdown = extract_markdown(
    filing,
    item=["1", "7"],  # Extract multiple items
    statement=["income", "balance"],  # Extract multiple statements
    notes=True,  # Extract notes
    show_dimension=False,  # Hide dimension columns for cleaner output
    show_filtered_data=True  # Show what was filtered
)

# Result:
# - Clean financial statements (no dimension clutter)
# - Visibility into what data was omitted
# - Comprehensive extraction with transparency
""")

markdown_combined = extract_markdown(
    filing,
    item="1",
    show_dimension=False,
    show_filtered_data=True
)

print(f"\nResult: {len(markdown_combined)} characters")
print("\nFirst section:")
print('\n'.join(markdown_combined.split('\n')[:20]))

# ============================================================================
# EXAMPLE 6: Use Cases
# ============================================================================
print("\n" + "="*70)
print("EXAMPLE 6: Practical Use Cases")
print("="*70)

print("""
USE CASE 1: LLM Analysis (Token Efficiency)
-------------------------------------------
# When feeding to LLMs, hide dimensions to reduce tokens
markdown = extract_markdown(
    filing,
    statement="income",
    show_dimension=False  # Cleaner, fewer tokens
)

USE CASE 2: Data Quality Audit
------------------------------
# Check what data was filtered during extraction
markdown = extract_markdown(
    filing,
    notes=True,
    show_filtered_data=True  # See what was omitted
)

USE CASE 3: XBRL Structure Analysis
-----------------------------------
# Keep dimensions for analyzing XBRL taxonomy
markdown = extract_markdown(
    filing,
    statement="balance",
    show_dimension=True  # Full XBRL structure
)

USE CASE 4: Production Pipeline
-------------------------------
# Combine for transparency + efficiency
markdown = extract_markdown(
    filing,
    item=["1", "7"],
    statement=["income", "balance", "cash"],
    notes=True,
    show_dimension=False,  # Efficient
    show_filtered_data=True  # Transparent
)
""")

# ============================================================================
# EXAMPLE 7: Programmatic Access to Filtered Data
# ============================================================================
print("\n" + "="*70)
print("EXAMPLE 7: Programmatic Access (Advanced)")
print("="*70)
print("""
# For advanced use, you can access filtered data programmatically
# using extract_sections() instead of extract_markdown()

from edgar.llm import extract_sections

sections, filtered_data = extract_sections(
    filing,
    notes=True,
    track_filtered=True  # Returns (sections, filtered_metadata) tuple
)

# Now you have:
# - sections: List of section dictionaries
# - filtered_data: Dictionary with counts and details

print(f"Filtered items:")
print(f"  XBRL metadata tables: {filtered_data['xbrl_metadata_tables']}")
print(f"  Duplicate tables: {filtered_data['duplicate_tables']}")
print(f"  Text blocks: {filtered_data['filtered_text_blocks']}")

# Access details
for detail in filtered_data['details'][:5]:
    print(f"  - {detail['type']}: {detail.get('preview', detail.get('title', '')[:50])}")
""")

print("\n" + "="*70)
print("EXAMPLES COMPLETE")
print("="*70)
print("""
Summary of New Parameters:

1. show_dimension (bool, default=True)
   - Controls XBRL dimension column visibility
   - False = cleaner output for LLMs
   - True = full XBRL structure

2. show_filtered_data (bool, default=False)
   - Controls filtered data metadata
   - False = no metadata (default)
   - True = append metadata section

Both are available in extract_markdown() for easy use!
""")
