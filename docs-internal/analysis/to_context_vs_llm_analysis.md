# Analysis: to_context() vs llm.py Functionality

## Executive Summary

`to_context()` and `llm.py` serve **complementary** roles in EdgarTools' LLM integration:

- **to_context()**: Lightweight metadata summaries for navigation/discovery (100-500 tokens)
- **llm.py**: Deep content extraction for analysis (thousands of tokens)

They operate on different data sources with minimal overlap and should be integrated rather than merged.

---

## 1. Data Sources Comparison

### to_context() Data Sources

**Location**: Implemented across multiple classes
- `edgar/_filings.py:930` - `Filings.to_context()`
- `edgar/_filings.py:1977` - `Filing.to_context()`
- `edgar/xbrl/xbrl.py:1721` - `XBRL.to_context()`
- `edgar/entity/core.py:638` - `Company.to_context()`
- `edgar/entity/filings.py:368` - `EntityFilings.to_context()`
- `edgar/offerings/formc.py:693` - `FormC.to_context()`

**Data Pulled**:
1. **Entity Metadata** (from objects in memory):
   - Company name, CIK, ticker
   - Exchange, SIC code, industry
   - Fiscal year end, entity type
   - Filer category

2. **Filing Metadata** (from filing records):
   - Form type, filing date
   - Accession number, period of report
   - Multi-entity status
   - Document count

3. **XBRL Metadata** (from parsed XBRL):
   - Entity info (name, ticker, CIK)
   - Fiscal period/year
   - Fact count, context count
   - Available statement types
   - Reporting period labels
   - Common usage patterns

**Implementation Pattern**:
```python
# edgar/_filings.py:1977-2092
def to_context(self, detail: str = 'standard') -> str:
    lines = []
    lines.append(f"FILING: Form {self.form}")
    lines.append(f"Company: {self.company}")
    lines.append(f"CIK: {self.cik}")
    lines.append(f"Filed: {self.filing_date}")

    if detail in ['standard', 'full']:
        lines.append("AVAILABLE ACTIONS:")
        lines.append("  - Use .obj() to parse as structured data")
        lines.append("  - Use .xbrl() for financial statements")

    return "\n".join(lines)
```

### llm.py Data Sources

**Location**: `edgar/llm.py:100-726`

**Data Pulled**:
1. **XBRL Statements** (via `filing.financials`):
   - Income statement, balance sheet, cash flow
   - Statement of equity, comprehensive income
   - Cover page
   - Rendered as DataFrames → Markdown tables
   - Source: `edgar/llm.py:377-461`

2. **Filing Items** (via `filing.obj().document`):
   - Item 1-16 sections from 10-K/10-Q
   - Uses Document.sections API or regex fallback
   - Tables extracted via `.tables()` and `.to_markdown_llm()`
   - Source: `edgar/llm.py:486-603`

3. **Financial Notes** (via `filing.reports`):
   - XBRL FilingSummary notes (preferred)
   - Document sections fallback
   - HTML content processed via `llm_helpers.process_content()`
   - Source: `edgar/llm.py:606-725`

**Implementation Pattern**:
```python
# edgar/llm.py:100-215
def extract_markdown(
    filing,
    *,
    item: Optional[Union[str, Sequence[str]]] = None,
    statement: Optional[Union[str, Sequence[str]]] = None,
    notes: bool = False,
    include_header: bool = True,
    optimize_for_llm: bool = True
) -> str:
    sections, filtered_data = extract_sections(
        filing, item=item, statement=statement, notes=notes,
        optimize_for_llm=optimize_for_llm
    )

    parts = []
    if include_header:
        header = _build_header(filing, sections)
        parts.append(header)

    for section in sections:
        parts.append(f"## SECTION: {section.title}")
        parts.append(section.markdown)

    return "\n".join(parts)
```

### Data Source Overlap

**Minimal Overlap**:
- Both extract basic filing metadata (form, company, date, accession)
- `llm.py:304-374` builds YAML header similar to `to_context()` output

**Unique to to_context()**:
- Industry classification (SIC code)
- Exchange information
- Filer category
- XBRL fact/context counts
- Available methods/actions guide

**Unique to llm.py**:
- Full financial statement data tables
- Section narrative text (Items 1-16)
- Financial statement notes
- Filtered data metadata

---

## 2. Output Format Comparison

### to_context(): Markdown-KV Metadata Summaries

**Format**: Hierarchical key-value pairs in Markdown
**Token Budget**: 100-500 tokens (controlled by `detail` parameter)
**Purpose**: Quick navigation and discovery

**Example Output** (`edgar/_filings.py:1996-2010`):
```
FILING: Form C

Company: ViiT Health Inc
CIK: 1881570
Filed: 2025-06-11
Accession: 0001670254-25-000647

AVAILABLE ACTIONS:
  - Use .obj() to parse as structured data
    Returns: FormC (crowdfunding offering details)
  - Use .docs for detailed API documentation
  - Use .xbrl() for financial statements (if available)
  - Use .document() for structured text extraction
  - Use .attachments for exhibits (5 documents)
```

**XBRL Example** (`edgar/xbrl/xbrl.py:1742-1867`):
```
**Entity:** Apple Inc. (AAPL)
**CIK:** 0000320193
**Form:** 10-K
**Fiscal Period:** FY 2023 (ended 2023-09-30)
**Facts:** 2,487
**Contexts:** 156

**Available Data Coverage:**
  Annual: FY 2023, FY 2022, FY 2021
  Quarterly: Q4 2023, Q3 2023

**Available Statements:**
  Core: IncomeStatement, BalanceSheet, CashFlowStatement
  Other: 3 additional statements

**Common Actions:**
  # List all available statements
  xbrl.statements

  # View core financial statements
  stmt = xbrl.statements.income_statement()

  # Get current period only
  current = xbrl.current_period
```

### llm.py: Full Markdown Content Extraction

**Format**: YAML frontmatter + section-based markdown
**Token Budget**: Thousands (optimized via filtering)
**Purpose**: Deep content analysis

**Example Output** (`edgar/llm.py:304-374` + sections):
```yaml
---
filing_type: 10-K
accession_number: 0000320193-23-000106
filing_date: 2023-11-03
company: Apple Inc.
ticker: AAPL
sections:
  - Income Statement
  - Item 7
  - Note 1 - Summary of Significant Accounting Policies
format: markdown
---

## SECTION: Income Statement
<!-- Source: XBRL -->
| label | 2023 | 2022 | 2021 |
|-------|------|------|------|
| Revenue | $394,328 | $365,817 | $274,515 |
| Cost of Revenue | $214,137 | $201,471 | $169,559 |
| Gross Profit | $180,191 | $164,346 | $104,956 |
...

## SECTION: Item 7
Management's Discussion and Analysis of Financial Condition and Results of Operations

Overview
The Company designs, manufactures, and markets smartphones...
[Full narrative content]

## SECTION: Note 1 - Summary of Significant Accounting Policies
The Company's fiscal year is the 52 or 53-week period...
[Full note content]
```

### Format Differences

| Aspect | to_context() | llm.py |
|--------|--------------|--------|
| **Structure** | Key-value pairs | Sections with full content |
| **Headers** | Implicit (bold/caps) | YAML frontmatter |
| **Size** | 100-500 tokens | Thousands of tokens |
| **Tables** | Not included | Full markdown tables |
| **Narrative** | None | Full text content |
| **Optimization** | Minimal (concise by design) | Heavy (cell merging, dedup, filtering) |

---

## 3. Use Cases Comparison

### to_context() Use Cases

**Primary**: LLM navigation and discovery
- Agent decides which filing to analyze
- Agent determines what methods to call
- Agent understands available data before fetching
- Quick context for multi-turn conversations

**Example Workflow**:
```python
# LLM sees: "Find Apple's latest 10-K"
filings = company.get_filings(form="10-K")
# Agent: print(filings.to_context('minimal'))
# Output: "Total: 10 filings, Latest: 2023-11-03"

latest = filings.latest()
# Agent: print(latest.to_context('standard'))
# Output: Shows available actions (.xbrl(), .obj(), .attachments)

# Agent decides: "Use .xbrl() to get financials"
xbrl = latest.xbrl()
# Agent: print(xbrl.to_context())
# Output: Shows available statements and usage patterns
```

**Key Locations**:
- `edgar/_filings.py:930-1033` - Collection navigation
- `edgar/_filings.py:1977-2092` - Individual filing navigation
- `edgar/xbrl/xbrl.py:1721-1868` - XBRL data discovery

### llm.py Use Cases

**Primary**: Deep content extraction for analysis
- Extract specific sections for question answering
- Analyze financial statement trends
- Compare narrative disclosures across periods
- Extract structured data from notes

**Example Workflow**:
```python
from edgar.llm import extract_markdown

# LLM task: "Analyze Apple's revenue trends and risk factors"
filing = company.get_filings(form="10-K").latest()

# Extract specific content
md = extract_markdown(
    filing,
    statement=["IncomeStatement"],  # Financial data
    item=["1A", "7"],               # Risk factors + MD&A
    notes=False,                     # Skip notes for now
    optimize_for_llm=True           # Apply filtering
)

# LLM receives full content for analysis
# Can now answer: "What were the top 3 revenue drivers?"
```

**Key Locations**:
- `edgar/llm.py:100-215` - Main extraction function
- `edgar/llm.py:377-461` - XBRL statement extraction
- `edgar/llm.py:486-603` - Item section extraction
- `edgar/llm.py:606-725` - Notes extraction

### Complementary Use Cases

| Stage | Use to_context() | Use llm.py |
|-------|------------------|------------|
| **Discovery** | "What filings are available?" | N/A |
| **Navigation** | "What's in this filing?" | N/A |
| **Selection** | "Does this filing have XBRL?" | N/A |
| **Extraction** | N/A | "Get income statement data" |
| **Analysis** | N/A | "Extract Item 7 narrative" |
| **Deep Dive** | N/A | "Analyze financial notes" |

---

## 4. Integration Potential

### Current Integration Points

**llm.py already uses to_context() concepts**:
- `edgar/llm.py:304-374` - `_build_header()` creates YAML frontmatter similar to to_context()
- Both use markdown-based output
- Both optimize for token efficiency

**Actual Code**:
```python
# edgar/llm.py:304-374
def _build_header(filing: 'Filing', sections: List['ExtractedSection']) -> str:
    """Build filing metadata header in YAML frontmatter format."""
    form = getattr(filing, 'form', None)
    accession_no = getattr(filing, 'accession_no', None)
    filing_date = getattr(filing, 'filing_date', None)
    company_name = filing.company if hasattr(filing, 'company') else None

    # Get ticker from CIK lookup
    ticker = find_ticker(filing.cik) if hasattr(filing, 'cik') else None

    # Build YAML frontmatter
    yaml_lines = ["---"]
    if form: yaml_lines.append(f"filing_type: {form}")
    if accession_no: yaml_lines.append(f"accession_number: {accession_no}")
    # ... etc
```

This duplicates logic from `Filing.to_context()` at `edgar/_filings.py:2016-2023`.

### Proposed Integration: Option 1 (Lightweight)

**Make llm.py reuse to_context() for headers**:

```python
# edgar/llm.py:304-374 (modified)
def _build_header(filing: 'Filing', sections: List['ExtractedSection']) -> str:
    """Build filing metadata header using to_context()."""
    # Get basic metadata from to_context
    context = filing.to_context(detail='minimal')

    # Convert to YAML frontmatter
    yaml_lines = ["---"]

    # Parse key-value pairs from context
    for line in context.split('\n'):
        if ':' in line and not line.startswith(' '):
            key, value = line.split(':', 1)
            yaml_key = key.lower().replace(' ', '_')
            yaml_lines.append(f"{yaml_key}: {value.strip()}")

    # Add section list
    section_titles = [s.title for s in sections]
    if section_titles:
        yaml_lines.append("sections:")
        for title in section_titles:
            yaml_lines.append(f"  - {title}")

    yaml_lines.append("format: markdown")
    yaml_lines.append("---")

    return "\n".join(yaml_lines)
```

**Benefits**:
- Eliminates code duplication
- Consistent metadata across both systems
- Single source of truth for filing metadata

**Risks**:
- Parsing text output (fragile)
- Different format requirements (key-value vs YAML)

### Proposed Integration: Option 2 (Better Architecture)

**Create shared metadata extractor**:

```python
# edgar/ai/metadata.py (new file)
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class FilingMetadata:
    """Structured filing metadata for AI consumption."""
    form: str
    company: str
    cik: str
    filing_date: str
    accession_no: str
    ticker: Optional[str] = None
    period_of_report: Optional[str] = None
    industry: Optional[str] = None
    exchange: Optional[str] = None

    @classmethod
    def from_filing(cls, filing: 'Filing') -> 'FilingMetadata':
        """Extract metadata from filing object."""
        ticker = find_ticker(filing.cik) if hasattr(filing, 'cik') else None
        return cls(
            form=filing.form,
            company=filing.company,
            cik=str(filing.cik),
            filing_date=str(filing.filing_date),
            accession_no=filing.accession_no,
            ticker=ticker,
            period_of_report=getattr(filing, 'period_of_report', None)
        )

    def to_markdown_kv(self) -> str:
        """Convert to markdown key-value format (for to_context)."""
        lines = []
        lines.append(f"FILING: Form {self.form}")
        lines.append(f"Company: {self.company}")
        lines.append(f"CIK: {self.cik}")
        lines.append(f"Filed: {self.filing_date}")
        if self.ticker:
            lines.append(f"Ticker: {self.ticker}")
        return "\n".join(lines)

    def to_yaml(self, sections: Optional[List[str]] = None) -> str:
        """Convert to YAML frontmatter (for llm.py headers)."""
        yaml_lines = ["---"]
        yaml_lines.append(f"filing_type: {self.form}")
        yaml_lines.append(f"company: {self.company}")
        yaml_lines.append(f"cik: {self.cik}")
        yaml_lines.append(f"filing_date: {self.filing_date}")
        if self.ticker:
            yaml_lines.append(f"ticker: {self.ticker}")
        if sections:
            yaml_lines.append("sections:")
            for s in sections:
                yaml_lines.append(f"  - {s}")
        yaml_lines.append("format: markdown")
        yaml_lines.append("---")
        return "\n".join(yaml_lines)
```

Then both systems use this:

```python
# edgar/_filings.py:1977 (modified)
def to_context(self, detail: str = 'standard') -> str:
    from edgar.ai.metadata import FilingMetadata

    metadata = FilingMetadata.from_filing(self)
    lines = [metadata.to_markdown_kv()]

    if detail in ['standard', 'full']:
        lines.append("")
        lines.append("AVAILABLE ACTIONS:")
        # ... rest of actions

    return "\n".join(lines)

# edgar/llm.py:304 (modified)
def _build_header(filing: 'Filing', sections: List['ExtractedSection']) -> str:
    from edgar.ai.metadata import FilingMetadata

    metadata = FilingMetadata.from_filing(filing)
    section_titles = [s.title for s in sections]
    return metadata.to_yaml(sections=section_titles)
```

**Benefits**:
- Single source of truth
- Type-safe metadata
- Easy to extend
- Both systems stay in sync
- Testable in isolation

### Proposed Integration: Option 3 (to_context() calls llm.py)

**Make to_context() delegate to llm.py for content-rich detail levels**:

```python
# edgar/_filings.py:1977 (enhanced)
def to_context(self, detail: str = 'standard', include_content: bool = False) -> str:
    """
    Args:
        detail: 'minimal', 'standard', 'full', 'content'
        include_content: If True, includes actual filing content (uses llm.py)
    """
    if detail == 'content' or include_content:
        # Delegate to llm.py for deep extraction
        from edgar.llm import extract_markdown
        return extract_markdown(
            self,
            statement=["IncomeStatement", "BalanceSheet", "CashFlowStatement"],
            item=None,
            notes=False,
            include_header=True,
            optimize_for_llm=True
        )

    # Standard metadata summary
    lines = []
    lines.append(f"FILING: Form {self.form}")
    # ... rest of to_context logic
```

**Benefits**:
- Unified API (`to_context()` for all needs)
- Progressive disclosure (detail level controls depth)
- Backward compatible

**Risks**:
- Large token jump from 'full' to 'content'
- Confusing API (two systems under one method)
- Harder to control what content is extracted

---

## 5. Recommendations

### Keep Systems Separate

**Recommended**: Do NOT merge `to_context()` and `llm.py`

**Rationale**:
1. **Different purposes**: Metadata vs content
2. **Different token budgets**: 100-500 vs thousands
3. **Different data sources**: Object metadata vs filing content
4. **Different use cases**: Navigation vs analysis
5. **Clean separation of concerns**

### Implement Option 2: Shared Metadata Extractor

**Create**: `edgar/ai/metadata.py`

**Benefits**:
1. Eliminates duplication in header building
2. Single source of truth for filing metadata
3. Type-safe, testable
4. Easy to extend with new metadata fields
5. Both systems stay consistent

**Implementation Priority**: Medium (nice-to-have, not critical)

### Document Integration Pattern

**Create**: `docs/ai-native/integration-guide.md`

**Content**:
```markdown
# AI-Native Integration Guide

## Discovery → Extraction Workflow

1. **Discovery Phase** - Use to_context()
   ```python
   filings = company.get_filings(form="10-K")
   print(filings.to_context('minimal'))  # See what's available

   latest = filings.latest()
   print(latest.to_context('standard'))  # See available methods
   ```

2. **Extraction Phase** - Use llm.py
   ```python
   from edgar.llm import extract_markdown

   content = extract_markdown(
       latest,
       statement=["IncomeStatement"],
       item=["7", "1A"],
       notes=True
   )
   # Analyze full content
   ```

## When to Use Each

| Goal | Use | Example |
|------|-----|---------|
| "What filings exist?" | `filings.to_context()` | List available filings |
| "What's in this filing?" | `filing.to_context()` | Show metadata + actions |
| "Does this have XBRL?" | `filing.to_context('full')` | Check XBRL status |
| "Extract income statement" | `extract_markdown(..., statement=['IncomeStatement'])` | Get full table |
| "Analyze risk factors" | `extract_markdown(..., item=['1A'])` | Get full text |
```

### Cross-Reference Implementation

**Add to to_context() output**:

```python
# edgar/_filings.py:2040-2073 (enhanced)
if detail in ['standard', 'full']:
    lines.append("")
    lines.append("AVAILABLE ACTIONS:")
    lines.append("  - Use .obj() to parse as structured data")
    lines.append("  - Use .xbrl() for financial statements")
    lines.append("  - Use .docs for detailed API documentation")

    # NEW: Point to llm.py for content extraction
    lines.append("")
    lines.append("DEEP CONTENT EXTRACTION:")
    lines.append("  from edgar.llm import extract_markdown")
    lines.append("  # Extract statements + sections for LLM analysis")
    lines.append("  content = extract_markdown(filing, statement=['IncomeStatement'], item=['7'])")
```

**Add to llm.py docstrings**:

```python
# edgar/llm.py:100-142 (enhanced docstring)
def extract_markdown(...) -> str:
    """
    Extract filing content as LLM-optimized markdown.

    For quick metadata summaries, use filing.to_context() instead.
    This function is for deep content extraction and analysis.

    Discovery workflow:
        1. Use filing.to_context() to see what's available
        2. Use extract_markdown() to get specific content

    Args:
        filing: Filing object
        ...
    """
```

---

## 6. Summary

### Overlap Analysis

**Minimal Overlap** (only in header metadata):
- Form type, company name, CIK, filing date, accession number
- Represents ~10-15 lines of duplicated code in `llm.py:304-374`

**Unique Functionality**:

| to_context() | llm.py |
|--------------|--------|
| Industry/SIC | Financial statements |
| Exchange | Section narratives |
| Filer category | Financial notes |
| XBRL metadata | Table extraction |
| Usage guidance | Content optimization |
| Method discovery | Deep analysis |

### Integration Approach

**Recommended**:
1. ✅ Keep systems separate (different purposes)
2. ✅ Create shared metadata extractor (`edgar/ai/metadata.py`)
3. ✅ Add cross-references in documentation
4. ✅ Point to_context() users to llm.py for content
5. ✅ Point llm.py users to to_context() for discovery

**Not Recommended**:
1. ❌ Merge into single system (confuses purposes)
2. ❌ Make to_context() call llm.py (wrong abstraction)
3. ❌ Parse to_context() output in llm.py (fragile)

### File References

**to_context() Implementations**:
- `edgar/_filings.py:930-1033` - Filings collection
- `edgar/_filings.py:1977-2092` - Individual filing
- `edgar/xbrl/xbrl.py:1721-1868` - XBRL document
- `edgar/entity/core.py:638-718` - Company entity
- `edgar/entity/filings.py:368-450` - Entity filings
- `edgar/offerings/formc.py:693-850` - Form C offerings

**llm.py Implementation**:
- `edgar/llm.py:100-215` - Main extraction function
- `edgar/llm.py:218-293` - Section extraction
- `edgar/llm.py:304-374` - Header builder (metadata)
- `edgar/llm.py:377-461` - XBRL statement extraction
- `edgar/llm.py:486-603` - Item section extraction
- `edgar/llm.py:606-725` - Notes extraction

**Supporting Files**:
- `edgar/llm_helpers.py` - Content optimization utilities
- `edgar/llm_extraction.py` - Regex-based extraction fallbacks

---

## Conclusion

`to_context()` and `llm.py` are **complementary systems** that should remain separate:

- **to_context()**: Lightweight navigation (100-500 tokens)
- **llm.py**: Deep extraction (thousands of tokens)

The only overlap is header metadata (~15 lines), which should be extracted to a shared `FilingMetadata` class. Otherwise, these systems serve different stages of the LLM workflow and should cross-reference each other in documentation rather than merge.
