"""
Simple Examples: 5 Common Use Cases
"""
import sys
sys.path.insert(0, '../')

from edgar import Company
from edgar.llm import extract_markdown

# Setup
company = Company("AAPL")
filing = company.get_filings(form="10-K").latest(1)

print("Simple Examples: 5 Common Use Cases")
print("="*70)

# ============================================================================
# 1. DEFAULT: Everything visible (backward compatible)
# ============================================================================
print("\n1. DEFAULT: Standard extraction")
print("-"*70)

code = '''
markdown = extract_markdown(filing, item="7")
# Shows everything, filters nothing extra
'''
print(code)

markdown = extract_markdown(filing, item="7")
print(f"[OK] Extracted: {len(markdown)} chars")

# ============================================================================
# 2. LLM OPTIMIZED: Clean output for AI analysis
# ============================================================================
print("\n2. LLM OPTIMIZED: Clean output for AI")
print("-"*70)

code = '''
markdown = extract_markdown(
    filing,
    statement="income",
    show_dimension=False  # Hide XBRL metadata columns
)
# Result: Only label + period columns (30% smaller)
'''
print(code)

markdown = extract_markdown(filing, statement="income", show_dimension=False)
print(f"[OK]Extracted: {len(markdown)} chars (no dimension columns)")

# ============================================================================
# 3. AUDIT MODE: See what was filtered
# ============================================================================
print("\n3. AUDIT MODE: Check filtered data")
print("-"*70)

code = '''
markdown = extract_markdown(
    filing,
    notes=True,
    show_filtered_data=True  # Show metadata about filtered items
)
# Result: Includes section showing what was filtered
'''
print(code)

markdown = extract_markdown(filing, notes=True, show_filtered_data=True)
has_metadata = "FILTERED DATA METADATA" in markdown
print(f"[OK] Extracted: {len(markdown)} chars")
print(f"[OK]Includes filtered data metadata: {has_metadata}")

# ============================================================================
# 4. PRODUCTION: Efficient + Transparent
# ============================================================================
print("\n4. PRODUCTION: Efficient + Transparent")
print("-"*70)

code = '''
markdown = extract_markdown(
    filing,
    item=["1", "7"],
    statement=["income", "balance"],
    show_dimension=False,      # Efficient (less tokens)
    show_filtered_data=True    # Transparent (audit trail)
)
# Result: Clean output + visibility into filtering
'''
print(code)

markdown = extract_markdown(
    filing,
    item=["1", "7"],
    statement=["income", "balance"],
    show_dimension=False,
    show_filtered_data=True
)
print(f"[OK] Extracted: {len(markdown)} chars")
print(f"[OK]Clean financial statements (no dimensions)")
print(f"[OK]Metadata shows what was filtered")

# ============================================================================
# 5. FULL DETAIL: XBRL Structure Analysis
# ============================================================================
print("\n5. FULL DETAIL: XBRL Structure Analysis")
print("-"*70)

code = '''
markdown = extract_markdown(
    filing,
    statement="balance",
    show_dimension=True  # Keep all XBRL metadata
)
# Result: Complete XBRL structure with hierarchy
'''
print(code)

markdown = extract_markdown(filing, statement="balance", show_dimension=True)
print(f"[OK] Extracted: {len(markdown)} chars")
print(f"[OK]Includes level, abstract, dimension columns")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print("""
Use Case                    show_dimension    show_filtered_data
----------------------------------------------------------------
1. Default/Standard         True (default)    False (default)
2. LLM Analysis            False             False
3. Data Audit              True              True
4. Production Pipeline     False             True
5. XBRL Analysis           True              False

Quick Tips:
- show_dimension=False -> Cleaner output for LLMs (20-40% smaller)
- show_filtered_data=True -> See what was omitted (audit trail)
- Both parameters work with item, statement, and notes
- Default behavior is unchanged (backward compatible)
""")
