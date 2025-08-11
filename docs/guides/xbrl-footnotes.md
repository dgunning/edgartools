# XBRL Footnotes

EdgarTools now supports parsing and accessing footnotes from XBRL documents. Footnotes provide additional context and explanations for specific facts in financial statements.

## Overview

In XBRL documents, footnotes are linked to facts through a structured relationship:
- **Facts** have unique `id` attributes (e.g., `id="ID_123"`)
- **Footnotes** contain explanatory text and have their own identifiers
- **FootnoteArcs** connect facts to footnotes using XLink references

EdgarTools automatically extracts these relationships, making footnotes easily accessible alongside the financial data.

## Basic Usage

### Accessing Footnotes

```python
from edgar.xbrl.parser import XBRLParser

# Parse an XBRL instance document
parser = XBRLParser()
with open("instance.xml") as f:
    content = f.read()
parser.parse_instance_content(content)

# Access footnotes
print(f"Found {len(parser.footnotes)} footnotes")

# Iterate through footnotes
for footnote_id, footnote in parser.footnotes.items():
    print(f"Footnote {footnote_id}: {footnote.text}")
    print(f"Related to facts: {footnote.related_fact_ids}")
```

### Finding Facts with Footnotes

```python
# Find facts that have footnotes
facts_with_footnotes = [
    fact for fact in parser.facts.values() 
    if fact.footnotes
]

print(f"Found {len(facts_with_footnotes)} facts with footnotes")

# Show fact details
for fact in facts_with_footnotes[:5]:
    print(f"Fact: {fact.element_id} (ID: {fact.fact_id})")
    print(f"Value: {fact.value}")
    print(f"Footnotes: {', '.join(fact.footnotes)}")
    print()
```

## Using the XBRL Class

The XBRL class provides convenient methods for working with footnotes:

```python
from edgar.xbrl import XBRL

# Initialize and parse
xbrl = XBRL()
xbrl.parser.parse_instance_content(content)

# Access footnotes property
footnotes = xbrl.footnotes
print(f"Document has {len(footnotes)} footnotes")

# Get footnotes for a specific fact ID
fact_footnotes = xbrl.get_footnotes_for_fact("ID_123")
for footnote in fact_footnotes:
    print(f"Footnote: {footnote.text}")

# Get all facts that have footnotes
facts_with_footnotes = xbrl.get_facts_with_footnotes()
```

## Data Models

### Fact Model

The `Fact` model has been enhanced with footnote support:

```python
class Fact(BaseModel):
    element_id: str
    context_ref: str
    value: str
    unit_ref: Optional[str] = None
    decimals: Optional[Union[int, str]] = None
    numeric_value: Optional[float] = None
    footnotes: List[str] = Field(default_factory=list)  # Footnote IDs
    instance_id: Optional[int] = None
    fact_id: Optional[str] = None  # Original XML id attribute
```

### Footnote Model

```python
class Footnote(BaseModel):
    footnote_id: str
    text: str
    lang: Optional[str] = "en-US"
    role: Optional[str] = None
    related_fact_ids: List[str] = Field(default_factory=list)
```

## Real-World Example

Here's a complete example using a filing with footnotes:

```python
from edgar import Filing
from pathlib import Path

# Get a filing and parse its XBRL
filing = Filing(form='10-K', cik=1234567, accession_no='0001234567-23-000001')
xbrl = filing.xbrl()

# Check if the document has footnotes
if xbrl.footnotes:
    print(f"Document contains {len(xbrl.footnotes)} footnotes")
    
    # Show footnote details
    for footnote_id, footnote in list(xbrl.footnotes.items())[:3]:
        print(f"\nFootnote ID: {footnote_id}")
        print(f"Text: {footnote.text[:100]}...")
        print(f"Language: {footnote.lang}")
        print(f"Linked to {len(footnote.related_fact_ids)} facts")
    
    # Find facts with footnotes in the balance sheet
    balance_sheet = xbrl.get_statement("BalanceSheet")
    if balance_sheet:
        for item in balance_sheet.get_all_line_items():
            facts = item.get("facts", [])
            for fact in facts:
                if fact.footnotes:
                    print(f"\n{item['label']} has footnotes:")
                    for fn_id in fact.footnotes:
                        if fn_id in xbrl.footnotes:
                            print(f"  • {xbrl.footnotes[fn_id].text[:80]}...")
else:
    print("No footnotes found in this document")
```

## Advanced Usage

### Filtering Footnotes by Content

```python
# Find footnotes containing specific keywords
debt_footnotes = [
    (fn_id, footnote) for fn_id, footnote in parser.footnotes.items()
    if any(keyword in footnote.text.lower() for keyword in ['debt', 'loan', 'credit'])
]

print(f"Found {len(debt_footnotes)} footnotes related to debt")
```

### Creating a Footnote Report

```python
from rich.console import Console
from rich.table import Table

console = Console()

# Create a footnote summary table
table = Table(title="Footnote Summary", show_header=True)
table.add_column("ID", style="cyan")
table.add_column("Preview", style="white", width=60)
table.add_column("Facts", style="yellow", justify="right")

for fn_id, footnote in parser.footnotes.items():
    preview = footnote.text[:60] + "..." if len(footnote.text) > 60 else footnote.text
    fact_count = str(len(footnote.related_fact_ids))
    
    table.add_row(fn_id, preview, fact_count)

console.print(table)
```

### Cross-Referencing with Financial Statements

```python
# Find footnotes that reference specific financial statement items
def find_footnotes_for_concept(xbrl, concept_name):
    """Find footnotes related to a specific accounting concept."""
    related_footnotes = []
    
    # Find facts matching the concept
    for fact_key, fact in xbrl.parser.facts.items():
        if concept_name.lower() in fact.element_id.lower():
            if fact.footnotes:
                for fn_id in fact.footnotes:
                    if fn_id in xbrl.footnotes:
                        related_footnotes.append((fact, xbrl.footnotes[fn_id]))
    
    return related_footnotes

# Example: Find footnotes about revenue
revenue_footnotes = find_footnotes_for_concept(xbrl, "Revenue")
for fact, footnote in revenue_footnotes:
    print(f"Revenue fact {fact.fact_id}: {footnote.text}")
```

## XBRL Technical Details

### Footnote Structure in XBRL

XBRL footnotes follow the XBRL 2.1 specification:

```xml
<!-- Footnote definition -->
<link:footnote id="fn-1" xlink:label="fn-1" 
               xlink:role="http://www.xbrl.org/2003/role/footnote" 
               xml:lang="en-US">
    <xhtml:div>
        <xhtml:span>Explanatory text about the fact.</xhtml:span>
    </xhtml:div>
</link:footnote>

<!-- Footnote arc linking fact to footnote -->
<link:footnoteArc xlink:arcrole="http://www.xbrl.org/2003/arcrole/fact-footnote" 
                  xlink:from="fact-id-123" 
                  xlink:to="fn-1" 
                  xlink:type="arc"/>
```

### Supported Footnote Formats

EdgarTools handles:
- **Standard footnotes** with `id` attributes
- **XLink footnotes** with `xlink:label` attributes  
- **XHTML content** within footnotes (automatically extracts text)
- **Multiple languages** via `xml:lang` attributes
- **Custom roles** via `xlink:role` attributes

### Namespace Handling

The parser correctly handles all standard XBRL namespaces:
- `http://www.xbrl.org/2003/linkbase` (link)
- `http://www.w3.org/1999/xlink` (xlink)
- `http://www.w3.org/1999/xhtml` (xhtml)
- `http://www.w3.org/XML/1998/namespace` (xml)

## Performance Considerations

- Footnote extraction adds minimal overhead to XBRL parsing
- Footnotes are parsed lazily during instance document processing
- Both fact-to-footnote and footnote-to-fact lookups are O(1) operations
- Large documents with many footnotes are handled efficiently

## Error Handling

The parser gracefully handles common footnote issues:

```python
# Parser warnings for missing footnote references
# Warning: "Footnote arc references undefined footnote: footnote_123"

# Missing footnote definitions are logged but don't cause parsing to fail
# Malformed XHTML content is handled with fallback text extraction
```

## Migration from Manual Parsing

If you were previously parsing footnotes manually:

```python
# Before (manual parsing)
import xml.etree.ElementTree as ET

def extract_footnotes_manually(xml_content):
    root = ET.fromstring(xml_content)
    footnotes = {}
    # ... complex manual parsing logic ...
    return footnotes

# After (using EdgarTools)
from edgar.xbrl.parser import XBRLParser

parser = XBRLParser()
parser.parse_instance_content(xml_content)
footnotes = parser.footnotes  # Ready to use!
```

## API Reference

### XBRLParser.footnotes
- **Type**: `Dict[str, Footnote]`
- **Description**: Dictionary mapping footnote IDs to Footnote objects

### XBRL.footnotes
- **Type**: `Dict[str, Footnote]`
- **Description**: Property providing access to parser footnotes

### XBRL.get_footnotes_for_fact(fact_id: str)
- **Parameters**: `fact_id` - The ID of the fact to get footnotes for
- **Returns**: `List[Footnote]` - List of associated footnotes
- **Description**: Retrieves all footnotes linked to a specific fact

### XBRL.get_facts_with_footnotes()
- **Returns**: `Dict[str, Fact]` - Dictionary of facts that have footnotes
- **Description**: Returns all facts that reference footnotes

### Fact.footnotes
- **Type**: `List[str]`
- **Description**: List of footnote IDs that reference this fact

### Fact.fact_id
- **Type**: `Optional[str]`
- **Description**: Original `id` attribute from the XML element

---

*This feature was implemented to support the XBRL 2.1 specification for footnotes and is compatible with all standard SEC XBRL filings.*