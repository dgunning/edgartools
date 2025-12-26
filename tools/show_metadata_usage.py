"""
Demonstrate what metadata is actually used in table conversion
"""
import sys
sys.path.insert(0, '../')

from edgar.documents.table_nodes import TableNode, Cell, Row

print("="*70)
print("METADATA USAGE IN TABLE CONVERSION")
print("="*70)

# Example 1: Table WITHOUT caption (most common case)
print("\nEXAMPLE 1: Table WITHOUT caption")
print("-"*70)

table1 = TableNode(
    headers=[
        [Cell(""), Cell("2024"), Cell("2023")]
    ],
    rows=[
        Row([Cell("Revenue"), Cell("$100M"), Cell("$90M")])
    ]
)

print("TableNode metadata:")
print(f"  caption: {table1.caption}")
print(f"  table_type: {table1.table_type}")
print(f"  summary: {table1.summary}")

md1 = table1.to_markdown_llm()
print("\nMarkdown output:")
for line in md1.split('\n')[:5]:
    print(f"  {line}")
print("\nNotice: Title is '#### Table 1: Table' (generic)")

# Example 2: Table WITH caption
print("\n" + "="*70)
print("EXAMPLE 2: Table WITH caption")
print("-"*70)

table2 = TableNode(
    caption="Consolidated Income Statement",  # <-- SET THIS
    headers=[
        [Cell(""), Cell("2024"), Cell("2023")]
    ],
    rows=[
        Row([Cell("Revenue"), Cell("$100M"), Cell("$90M")])
    ]
)

print("TableNode metadata:")
print(f"  caption: {table2.caption}")
print(f"  table_type: {table2.table_type}")
print(f"  summary: {table2.summary}")

md2 = table2.to_markdown_llm()
print("\nMarkdown output:")
for line in md2.split('\n')[:5]:
    print(f"  {line}")
print("\nNotice: Title uses caption '#### Table 1: Consolidated Income Statement'")

# Example 3: Show what metadata IS and ISN'T used
print("\n" + "="*70)
print("METADATA USAGE SUMMARY")
print("="*70)

print("""
METADATA USED IN CONVERSION:
---------------------------
[OK] caption          -> Used as section_title in process_content()
[OK] headers          -> Used for multi-row header merging
[OK] rows             -> Used for table data
[OK] footer           -> Used if present
[OK] Cell.colspan     -> Used for table matrix building
[OK] Cell.rowspan     -> Used for table matrix building
[OK] Cell.is_header   -> Used to detect header vs data rows

METADATA NOT USED:
-----------------
[X] table_type        -> Not used in conversion logic
[X] summary           -> Not used at all
[X] is_financial_table -> Not used in markdown generation
[X] row_count         -> Only used for metadata queries
[X] col_count         -> Only used for metadata queries
[X] has_row_headers   -> Not used in markdown generation
[X] numeric_columns   -> Not used in markdown generation
[X] Cell.align        -> Not used (could be used for alignment)
[X] Cell.is_numeric   -> Not used in title/header logic
[X] Row.is_total_row  -> Not used in markdown conversion
""")

# Example 4: Derived title extraction
print("\n" + "="*70)
print("EXAMPLE 4: Derived Title from First Row")
print("-"*70)

print("""
When the first row of a table spans all columns with a single value,
it's extracted as 'derived_title' and removed from the table.

Example HTML:
<table>
  <tr><th colspan="4">Year Ended December 31</th></tr>
  <tr><th></th><th>2024</th><th>2023</th><th>2022</th></tr>
  <tr><td>Revenue</td><td>$100M</td><td>$90M</td><td>$80M</td></tr>
</table>

Extraction Logic (edgar/llm_helpers.py:376-385):
1. Check if first row has single unique value
2. Check if value is 3-150 characters
3. If yes: derived_title = "Year Ended December 31"
4. Remove first row from table
5. Title becomes: "#### Table: Year Ended December 31"

THIS IS WHY YOU SEE "Year Ended December 31" AS TABLE TITLES!
""")

# Example 5: Generic titles
print("\n" + "="*70)
print("EXAMPLE 5: Why You See 'Table 1', 'Table 2', etc.")
print("-"*70)

print("""
Title Generation Logic (edgar/llm_helpers.py:808-811):

if derived_title:
    title = f"#### Table: {derived_title}"
else:
    title = f"#### Table {counter}: {section_title or 'Data'}"

Where section_title comes from:
  section_title = table.caption or "Table"

So:
- No caption, no derived_title  -> "#### Table 1: Table"
- No caption, has derived_title -> "#### Table: Year Ended December 31"
- Has caption, no derived_title -> "#### Table 1: Consolidated Income Statement"
- Has caption, has derived_title -> "#### Table: Year Ended December 31"
                                    (derived_title takes precedence)
""")

# Example 6: How to get better titles
print("\n" + "="*70)
print("EXAMPLE 6: How to Get Better Table Titles")
print("-"*70)

print("""
SOLUTION 1: Set caption when creating TableNode
-----------------------------------------------
table = TableNode(
    caption="Quarterly Revenue by Region",  # <-- This
    headers=[...],
    rows=[...]
)

Result: "#### Table 1: Quarterly Revenue by Region"


SOLUTION 2: Ensure first row has spanning title
-----------------------------------------------
HTML with spanning first row:
<table>
  <tr><th colspan="5">Summary of Stock Compensation</th></tr>
  <tr><th>Type</th><th>Q1</th><th>Q2</th><th>Q3</th><th>Q4</th></tr>
  ...
</table>

Result: "#### Table: Summary of Stock Compensation"
        (First row extracted as derived_title and removed)


SOLUTION 3: Use <caption> tag in HTML
-------------------------------------
Currently NOT implemented, but could be enhanced:
<table>
  <caption>Balance Sheet</caption>
  <tr><th>Assets</th><th>2024</th><th>2023</th></tr>
  ...
</table>

Would need parser enhancement to extract caption from <caption> tag.
""")

print("\n" + "="*70)
print("CONCLUSION")
print("="*70)
print("""
Most tables show generic titles because:
1. TableNode.caption is rarely set (None by default)
2. First row often doesn't span all columns (no derived_title)
3. Defaults to "Table" → "#### Table 1: Table"

Only 2 metadata fields affect titles:
- caption (if set)
- derived_title (if extracted from first row)

Everything else (table_type, summary, is_financial_table, etc.)
is NOT used in the markdown conversion logic!
""")
