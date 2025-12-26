"""
Example: Using the LLM extraction API for EdgarTools

This example demonstrates how to extract filing content optimized
for LLM processing.
"""

from edgar import Filing
from edgar.llm import extract_markdown, extract_sections

# Example 1: Extract specific sections
print("="*80)
print("Example 1: Extract Income Statement and Notes")
print("="*80)

filing = Filing(form='10-K', cik='0001318605', accession_no='0001564590-24-004069')  # Tesla 2023 10-K

# Extract with LLM optimization
markdown = extract_markdown(
    filing,
    statement=["IncomeStatement"],
    notes=True,
    optimize_for_llm=True
)

print(f"Generated {len(markdown):,} characters of markdown")
print("\nFirst 1000 characters:")
print(markdown[:1000])
print("...")

# Example 2: Extract as structured sections
print("\n" + "="*80)
print("Example 2: Extract Structured Sections")
print("="*80)

sections = extract_sections(
    filing,
    statement=["IncomeStatement", "BalanceSheet"],
    notes=True
)

print(f"\nExtracted {len(sections)} sections:")
for i, section in enumerate(sections, 1):
    print(f"\n{i}. {section.title}")
    print(f"   Source: {section.source}")
    print(f"   Is XBRL: {section.is_xbrl}")
    print(f"   Length: {len(section.markdown):,} chars")

# Example 3: Table-level LLM optimization
print("\n" + "="*80)
print("Example 3: Individual Table Optimization")
print("="*80)

# Get a single table
doc = filing.obj().document
if doc.tables:
    table = doc.tables[0]

    # Standard markdown
    from edgar.richtools import rich_to_text
    standard = rich_to_text(table.render(500))

    # LLM-optimized markdown
    optimized = table.to_markdown_llm()

    print(f"\nStandard markdown: {len(standard):,} chars")
    print(f"LLM-optimized:     {len(optimized):,} chars")
    print(f"Reduction:         {100 * (1 - len(optimized)/len(standard)):.1f}%")

    print("\nLLM-optimized output:")
    print(optimized[:500])
    print("...")

# Example 4: JSON intermediate format
print("\n" + "="*80)
print("Example 4: JSON Intermediate Format")
print("="*80)

if doc.tables:
    table = doc.tables[0]
    json_data = table.to_json_intermediate()

    print(f"\nRecords: {len(json_data['records'])}")
    print(f"Derived title: {json_data['derived_title']}")
    print(f"Text blocks: {len(json_data['text_blocks'])}")

    if json_data['records']:
        print(f"\nFirst 3 records:")
        for i, record in enumerate(json_data['records'][:3], 1):
            print(f"{i}. {record}")

print("\n" + "="*80)
print("Examples completed!")
print("="*80)
