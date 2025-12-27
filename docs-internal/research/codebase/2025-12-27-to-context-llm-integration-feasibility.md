# Research: Can llm.py functionality merge into to_context()?

**Date**: 2025-12-27
**Research Phase**: 1 of 3 (FIC Workflow)
**Next Phase**: Planning (`/plan`)

## Research Question

User asked: "can you merge llm.py functionality to to_context()?"

This research investigates whether the `edgar/llm.py` module (which provides deep content extraction for LLM analysis) can or should be integrated into the `to_context()` API pattern (which provides lightweight metadata summaries across 7+ classes).

## Summary

**Recommendation: Keep systems separate with shared metadata helper**

After comprehensive analysis of both systems, they serve fundamentally different purposes:

- **to_context()**: Lightweight navigation metadata (100-500 tokens) for AI agent discovery
- **llm.py**: Deep content extraction (thousands of tokens) for detailed analysis

**Key findings:**
1. ✅ Minimal overlap (~15 lines of duplicate header metadata)
2. ✅ Complementary use cases (navigation vs extraction)
3. ❌ Merging would confuse purposes and violate single-responsibility principle
4. ✅ Can create shared `_extract_filing_metadata()` helper to eliminate duplication

## Detailed Findings

### System 1: to_context() Pattern - AI-Native Navigation

**Implementations**: 7 classes across the codebase

| Class | File | Line | Purpose |
|-------|------|------|---------|
| `Filings` | `edgar/_filings.py` | 930 | Collection navigation |
| `Filing` | `edgar/_filings.py` | 1977 | Single filing metadata |
| `XBRL` | `edgar/xbrl/xbrl.py` | 1721 | Financial data context |
| `Company` | `edgar/entity/core.py` | 638 | Corporate entity context |
| `EntityFilings` | `edgar/entity/filings.py` | 368 | Entity-specific collections |
| `FormC` | `edgar/offerings/formc.py` | 693 | Crowdfunding forms |
| `Offering` | `edgar/offerings/campaign.py` | 510 | Campaign lifecycle |

**What it does:**
- Returns Markdown-KV formatted metadata summaries
- Provides "AVAILABLE ACTIONS" navigation hints
- Progressive disclosure via detail levels: minimal/standard/full
- Token budgets: 100-500 tokens per detail level

**Data sources:**
- Entity metadata (company name, CIK, ticker, industry, SIC, exchange)
- Filing metadata (form type, date, accession number, period)
- XBRL metadata (fact counts, statement availability, period coverage)
- Collection metadata (count, form distribution, date ranges)

**Output example** (Company.to_context('standard')):
```markdown
COMPANY: Apple Inc.
CIK: 0000320193
Ticker: AAPL
Exchange: NASDAQ
Industry: Electronic Computers (SIC 3571)
Category: Large accelerated filer
Fiscal Year End: September 30

AVAILABLE ACTIONS:
  - Use .get_filings() to access SEC filings
  - Use .financials to get financial statements
  - Use .facts to access company facts API
  - Use .docs for detailed API documentation
```

**Token optimization:**
- Research-backed Markdown-KV format (60.7% accuracy, 25% fewer tokens than JSON)
- Detail levels control output size
- Optional max_tokens parameter (Company, XBRL)
- Truncation with "[Truncated for token limit]" message

### System 2: llm.py - Deep Content Extraction

**Implementation**: Single module with 726 lines

**File**: `edgar/llm.py`

**Main functions:**
1. `extract_markdown(filing, item, statement, notes, ...)` → str
   - Extracts and combines all requested sections
   - Returns single markdown string with YAML frontmatter

2. `extract_sections(filing, item, statement, notes, ...)` → List[ExtractedSection]
   - Returns structured sections for granular control
   - Optional filtered data tracking

**What it does:**
- Extracts full financial statement tables (income, balance sheet, cash flow)
- Extracts filing item sections (Item 1, Item 7, Item 7A, etc.)
- Extracts financial notes with XBRL FilingSummary or Document fallback
- Applies LLM optimizations (cell merging, deduplication, noise filtering)

**Data sources:**
- XBRL statements via `filing.financials` → renders full tables
- Filing items via `filing.obj().document.sections` or regex fallback
- Financial notes via `filing.reports.get_by_category("Notes")`

**Output example** (extract_markdown with IncomeStatement):
```markdown
---
filing_type: 10-K
company: Apple Inc.
ticker: AAPL
sections:
  - Income Statement
format: markdown
---

## SECTION: Income Statement
<!-- Source: XBRL -->
| Label | 2023 | 2022 | 2021 |
|---|---:|---:|---:|
| Revenue | $394,328 | $365,817 | $365,817 |
| Cost of Revenue | $214,137 | $223,546 | $212,981 |
| Gross Profit | $180,191 | $142,271 | $152,836 |
...
```

**Token optimization:**
- Currency/percent cell merging (~5-10% reduction)
- Column deduplication (~20-40% reduction)
- Noise filtering (~10-30% reduction)
- Total: 40-60% reduction vs raw HTML
- Typical output: thousands to tens of thousands of tokens

### Overlap Analysis

**Shared functionality:**

Only **~15 lines of duplicate code** for extracting filing metadata headers:

```python
# Both extract these fields from filing object:
form = getattr(filing, 'form', None)
accession_no = getattr(filing, 'accession_no', None)
filing_date = getattr(filing, 'filing_date', None)
company_name = filing.company
ticker = find_ticker(filing.cik)
```

**This overlap appears in:**
- `llm.py:_build_header()` (lines 316-343)
- `Filing.to_context()` (lines 2020-2027)
- `EntityFilings.to_context()` (lines 400-405)

**Unique to to_context():**
- Entity-specific metadata (industry, SIC, exchange, fiscal year end)
- Collection statistics (counts, form breakdowns, date ranges)
- AVAILABLE ACTIONS navigation hints
- Detail level control (minimal/standard/full)
- Token budget enforcement

**Unique to llm.py:**
- Full content extraction (tables, narratives, notes)
- Multi-strategy extraction (XBRL → Document → Regex)
- LLM optimizations (dedup, noise filtering, cell merging)
- Filtered data tracking
- Section-level granularity (ExtractedSection objects)

### Use Case Comparison

| Use Case | to_context() | llm.py |
|----------|--------------|--------|
| "What filings exist?" | ✅ Perfect fit | ❌ Wrong tool |
| "Show me company details" | ✅ Perfect fit | ❌ Wrong tool |
| "What can I do next?" | ✅ AVAILABLE ACTIONS | ❌ Wrong tool |
| "Get income statement" | ❌ Shows availability only | ✅ Perfect fit |
| "Extract Item 7" | ❌ Shows availability only | ✅ Perfect fit |
| "Analyze risk factors" | ❌ Wrong tool | ✅ Perfect fit |
| Multi-turn AI discovery | ✅ Token-efficient | ❌ Too verbose |
| RAG system integration | ❌ Insufficient content | ✅ Full extraction |

### Integration Potential

**Option 1: Merge llm.py into to_context()** ❌ NOT RECOMMENDED

**Problems:**
1. **Purpose confusion**: to_context() is for navigation, llm.py is for extraction
2. **Token explosion**: to_context() carefully limits output to 100-500 tokens; llm.py produces thousands
3. **API complexity**: Would require complex parameters to toggle between modes
4. **Single responsibility violation**: One method doing two very different things
5. **Breaking change**: Existing to_context() users expect lightweight metadata

**Option 2: Make llm.py call to_context() for headers** ⚠️ PARTIAL VALUE

**Pros:**
- Eliminates 15 lines of duplication
- Consistent metadata format

**Cons:**
- llm.py needs YAML frontmatter, to_context() uses plain markdown
- Different formatting requirements (e.g., section lists)
- Creates coupling between independent systems

**Option 3: Create shared metadata helper** ✅ RECOMMENDED

**Implementation:**
```python
# edgar/metadata_helpers.py

def extract_filing_metadata(filing, include_ticker=True, include_period=False):
    """Extract common filing metadata used by both to_context() and llm.py"""
    metadata = {
        'form': getattr(filing, 'form', None),
        'accession_no': getattr(filing, 'accession_no', None),
        'filing_date': getattr(filing, 'filing_date', None),
        'company': filing.company if hasattr(filing, 'company') else None,
    }

    if include_ticker:
        from edgar.reference.tickers import find_ticker
        metadata['ticker'] = find_ticker(filing.cik) if hasattr(filing, 'cik') else None

    if include_period:
        metadata['period'] = getattr(filing, 'period_of_report', None)

    return metadata
```

**Usage in llm.py:**
```python
def _build_header(filing, sections):
    metadata = extract_filing_metadata(filing, include_ticker=True, include_period=False)

    # Build YAML from metadata dict
    yaml_lines = ["---"]
    if metadata['form']:
        yaml_lines.append(f"filing_type: {metadata['form']}")
    # ... etc
```

**Usage in Filing.to_context():**
```python
def to_context(self, detail='standard'):
    metadata = extract_filing_metadata(self, include_ticker=True, include_period=True)

    lines = []
    lines.append(f"FILING: Form {metadata['form']}")
    lines.append(f"Company: {metadata['company']}")
    # ... etc
```

**Option 4: Add cross-references** ✅ RECOMMENDED

Update to_context() implementations to mention llm.py when relevant:

```python
# In Filing.to_context(), standard detail level:
lines.append("AVAILABLE ACTIONS:")
lines.append("  - Use .obj() to parse as structured data")
lines.append("  - Use extract_markdown(filing, statement=['IncomeStatement']) for LLM analysis")  # NEW
lines.append("  - Use .xbrl() for financial statements")
lines.append("  - Use .document() for structured text extraction")
```

## Code References

### to_context() Implementations

- `edgar/_filings.py:930-1033` - Filings collection context
- `edgar/_filings.py:1977-2092` - Single filing context
- `edgar/entity/core.py:638-769` - Company context
- `edgar/xbrl/xbrl.py:1721-1868` - XBRL document context
- `edgar/entity/filings.py:368-437` - Entity-specific filings
- `edgar/offerings/formc.py:693-861` - Form C crowdfunding
- `edgar/offerings/campaign.py:510-630` - Offering lifecycle

### llm.py Core Functions

- `edgar/llm.py:100-215` - extract_markdown() main function
- `edgar/llm.py:218-292` - extract_sections() structured output
- `edgar/llm.py:304-374` - _build_header() YAML frontmatter
- `edgar/llm.py:377-461` - _extract_xbrl_statements() financial tables
- `edgar/llm.py:486-603` - _extract_items() section extraction
- `edgar/llm.py:606-725` - _extract_notes() notes processing

### Overlap Locations

- `edgar/llm.py:316-343` - Filing metadata extraction in _build_header()
- `edgar/_filings.py:2020-2027` - Metadata in Filing.to_context()
- `edgar/entity/filings.py:400-405` - Metadata in EntityFilings.to_context()

## Architecture Documentation

### Current Design Pattern

Both systems follow **AI-Native API Design** principles:

1. **Progressive Disclosure**: Start with minimal info, expand as needed
2. **Token Awareness**: Explicit budgets and optimization
3. **Markdown-KV Format**: Research-backed LLM-optimized format
4. **Method Discovery**: Guide users to next available actions
5. **Context Relevance**: Include only what's needed for the task

### Separation of Concerns

```
┌─────────────────────────────────────────────────┐
│         AI Agent Interaction Flow               │
├─────────────────────────────────────────────────┤
│                                                 │
│  1. Discovery: to_context()                     │
│     "What filings exist for AAPL?"              │
│     → Returns: Collection metadata + actions    │
│                                                 │
│  2. Selection: User/AI picks filing             │
│     "Get latest 10-K"                           │
│                                                 │
│  3. Context: to_context() on specific filing    │
│     filing.to_context()                         │
│     → Returns: Filing metadata + available data │
│                                                 │
│  4. Extraction: llm.py for deep content         │
│     extract_markdown(filing, statement=[...])   │
│     → Returns: Full financial tables            │
│                                                 │
│  5. Analysis: AI processes extracted content    │
│                                                 │
└─────────────────────────────────────────────────┘
```

The systems work in **sequence**, not as alternatives:
- **to_context()**: Helps AI agents navigate to the right data
- **llm.py**: Extracts the data once you know what you want

### Design Principles Violated by Merging

1. **Single Responsibility**: Each method should do one thing well
   - to_context(): Provide lightweight navigation metadata
   - llm.py: Extract deep content for analysis

2. **Interface Segregation**: Clients shouldn't depend on methods they don't use
   - Navigation clients don't need full extraction capabilities
   - Extraction clients don't need navigation hints

3. **Token Budgets**: to_context() promises 100-500 tokens
   - Adding extraction would explode token counts
   - Breaks existing contracts

## Test Coverage

### to_context() Tests

- `tests/test_ai_native_context.py:356 lines` - Full workflow validation
- `tests/test_ai_text_methods.py` - Format validation
- `tests/test_company.py` - Company-specific context tests

**Key test patterns:**
```python
def test_filing_to_context_standard():
    filing = filings[0]
    context = filing.to_context('standard')
    assert 'FILING:' in context
    assert 'AVAILABLE ACTIONS:' in context
    assert len(context) < 2000  # Token budget check
```

### llm.py Tests

- `tests/test_llm_return_types.py:144 lines` - Return type contract validation
- `tests/test_*.py` - Various integration tests

**Key test patterns:**
```python
def test_extract_sections_returns_list():
    sections = extract_sections(filing, item="1")
    assert isinstance(sections, list)

def test_extract_sections_returns_tuple_with_tracking():
    sections, filtered = extract_sections(filing, item="1", track_filtered=True)
    assert isinstance(sections, list)
    assert isinstance(filtered, dict)
```

## Dependencies

### to_context() Dependencies

**Internal:**
- `edgar.reference.tickers` - Ticker lookups
- `edgar.formatting` - Date formatting helpers
- Entity/Filing metadata access

**External:**
- None (pure Python string formatting)

### llm.py Dependencies

**Internal:**
- `edgar.llm_helpers` - LLM optimization functions
- `edgar.llm_extraction` - Regex fallback extraction
- `edgar.reference.tickers` - Ticker lookups
- `edgar.richtools` - Rich to text conversion

**External:**
- `dataclasses` - ExtractedSection model
- `typing` - Type hints

**Filing Dependencies:**
- `filing.financials` / `filing.obj().financials`
- `filing.reports.get_by_category("Notes")`
- `filing.obj().document.sections`
- `filing.html()`

## Key Data Flows

### to_context() Data Flow

```
Entity/Filing Object
    ↓
Metadata Extraction (CIK, ticker, form, date, etc.)
    ↓
Format as Markdown-KV
    ↓
Add Available Actions
    ↓
Apply Detail Level Filtering
    ↓
Return String (100-500 tokens)
```

### llm.py Data Flow

```
Filing Object
    ↓
extract_sections() Router
    ├─→ _extract_xbrl_statements()
    │   ├─→ filing.financials
    │   ├─→ stmt.render() → DataFrame
    │   └─→ to_markdown()
    ├─→ _extract_items()
    │   ├─→ Document.sections (preferred)
    │   └─→ Regex extraction (fallback)
    └─→ _extract_notes()
        ├─→ filing.reports (XBRL notes)
        └─→ Document.sections (fallback)
    ↓
LLM Optimization (llm_helpers)
    ├─→ Cell merging ($, %)
    ├─→ Column deduplication
    ├─→ Noise filtering
    └─→ Table deduplication
    ↓
ExtractedSection Objects
    ↓
extract_markdown() Combiner
    ├─→ YAML Frontmatter (_build_header)
    ├─→ Section Markdown
    └─→ Filtered Metadata (optional)
    ↓
Return String (thousands of tokens)
```

## Related Documentation

**Research citations:**
- Markdown-KV format study: improvingagents.com/blog/best-input-data-format-for-llms
  - 60.7% accuracy
  - 25% fewer tokens than JSON

**Internal docs:**
- `docs-internal/planning/AI_NATIVE_WORKFLOW_IMPLEMENTATION_PLAN.md` - AI-native API design
- `docs-internal/examples/ai_native_api_patterns.md` - Usage examples
- `edgar/ai/skills/core/*.md` - AI skill implementations

**CLAUDE.md guides:**
- `edgar/entity/CLAUDE.md` - Entity package guide
- `edgar/xbrl/CLAUDE.md` - XBRL package guide

## Open Questions for Planning Phase

None - research is conclusive that systems should remain separate.

## Recommendation

### Keep Systems Separate

**Rationale:**
1. **Different purposes**: Navigation (to_context) vs Extraction (llm.py)
2. **Different scales**: 100-500 tokens vs thousands of tokens
3. **Different audiences**: AI navigation agents vs content analysis
4. **Minimal duplication**: Only ~15 lines of shared metadata extraction

### Implementation Steps

If user wants to improve integration:

1. **Create shared metadata helper** (`edgar/metadata_helpers.py`)
   - Extract common filing metadata logic
   - Used by both to_context() and llm.py
   - Eliminates ~15 lines of duplication

2. **Add cross-references in to_context()**
   - Update AVAILABLE ACTIONS to mention extract_markdown()
   - Guide users from navigation to extraction
   - Example: "Use extract_markdown(filing, statement=[...]) for LLM analysis"

3. **Update documentation**
   - Clarify when to use to_context() vs llm.py
   - Add workflow examples showing both in sequence
   - Document the navigation → extraction pattern

### Anti-Pattern: Merging

**Do NOT:**
- ❌ Add llm.py extraction to to_context() methods
- ❌ Make to_context() return thousands of tokens
- ❌ Create complex parameter flags to toggle modes
- ❌ Break existing to_context() token budgets

**Why:**
- Violates single-responsibility principle
- Confuses API purpose
- Breaks existing contracts
- Creates maintenance burden

## Conclusion

The `to_context()` and `llm.py` systems are **complementary, not redundant**. They work together in a navigation → extraction workflow:

1. **to_context()** helps AI agents discover what data exists (100-500 tokens)
2. **llm.py** extracts that data for analysis (thousands of tokens)

The minimal overlap (~15 lines) should be extracted into a shared helper function, but the systems themselves should remain architecturally separate. This maintains clean separation of concerns, preserves token budgets, and keeps the API clear and purposeful.

**Final Answer to User**: No, llm.py functionality should NOT merge into to_context(). They serve different purposes and work best as complementary tools in a discovery → extraction workflow. A small shared metadata helper can eliminate duplication while preserving the architectural benefits of separation.
