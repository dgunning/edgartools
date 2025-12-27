# AI/LLM Usage Patterns in EdgarTools

This document catalogs actual usage patterns for `to_context()` and `llm.py` functions found in the EdgarTools codebase.

## Pattern: to_context() for AI-Native API Discovery

### Pattern Overview
The `to_context()` method provides token-efficient, AI-optimized text representations of EdgarTools objects. It enables AI agents to discover and navigate the API by providing contextual hints about available actions and data.

### Key Characteristics
- **Progressive Disclosure**: Uses `detail` parameter ('minimal', 'standard', 'full') to control token usage
- **Navigation Hints**: Includes "AVAILABLE ACTIONS" sections that guide AI agents to next steps
- **Token Budgets**: Respects strict token limits (150-800 tokens per detail level)
- **Markdown-KV Format**: Research-backed format for optimal LLM comprehension

### Examples Found

#### Example 1: Filing.to_context() - AI Discovery for Single Filing
```python
def to_context(self, detail: str = 'standard') -> str:
    """
    Returns AI-optimized filing summary for language models.

    Args:
        detail: Level of detail to include:
            - 'minimal': Basic filing info (~100 tokens)
            - 'standard': Adds document list (~250 tokens)
            - 'full': Adds all metadata (~400 tokens)

    Returns:
        Markdown-KV formatted context string optimized for LLMs
    """
    # Implementation provides filing metadata + hints about .obj(), .docs, etc.
```

**Token Budgets**:
- Minimal: ~100 tokens
- Standard: ~250 tokens
- Full: ~400 tokens

**Navigation Hints Provided**:
- `.obj()` - Parse into structured object (TenK, FormC, etc.)
- `.docs` - Access documentation
- `.xbrl()` - Get XBRL financials
- `.html()` - Get raw HTML

#### Example 2: Filings.to_context() - Collection Navigation

```python
def to_context(self, detail: str = 'standard') -> str:
    """
    Returns AI-optimized collection summary for language models.

    Example Output (standard detail):
        FILINGS COLLECTION

        Total: 150 filings
        Forms: C, C-U, C-AR
        Date Range: 2024-01-01 to 2024-03-31

        AVAILABLE ACTIONS:
          - Use .latest() to get most recent filing
          - Use [index] to access specific filing (e.g., filings[0])
          - Use .filter(form='C') to narrow by form type
          - Use .docs for detailed API documentation

        SAMPLE FILINGS:
          0. Form C - 2024-03-29 - ViiT Health Inc
          1. Form C - 2024-03-28 - Artisan Creative Inc
          ... (147 more)
    """
```

**Token Budgets**:
- Minimal: ~100-150 tokens
- Standard: ~250 tokens
- Full: ~400 tokens

**Navigation Hints Provided**:
- `.latest()` - Get most recent filing
- `[index]` - Array access pattern
- `.filter(form='C')` - Filtering operations

#### Example 3: Company.to_context() - Corporate Entity Context

```python
def to_context(self, detail: str = 'standard', max_tokens: Optional[int] = None) -> str:
    """
    Get AI-optimized plain text representation.

    Uses Markdown-KV format (60.7% accuracy, 25% fewer tokens than JSON) optimized
    for LLM consumption.

    Research basis: improvingagents.com/blog/best-input-data-format-for-llms

    Example Output (standard):
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
    """
```

**Token Budgets**:
- Minimal: ~100-150 tokens
- Standard: ~250-350 tokens
- Full: ~500+ tokens

**Navigation Hints Provided**:
- `.get_filings()` - Filing access
- `.financials` - Financial statements
- `.facts` - Company facts API
- `.docs` - Documentation

#### Example 4: FormC.to_context() - Crowdfunding Form Context

```python
def to_context(self, detail: str = 'standard', filing_date: Optional[date] = None) -> str:
    """
    Returns a token-efficient, AI-optimized text representation of the Form C filing.

    This method provides a compact alternative to __rich__() that is optimized for
    LLM context windows. It includes computed fields (status, days remaining, ratios).

    Example Output (standard):
        FORM C - CROWDFUNDING OFFERING (Filed: 2024-03-15)

        ISSUER: ViiT Health Inc
          CIK: 0001881570
          Legal: Delaware Corporation
          Website: https://viit.health

        FUNDING PORTAL: StartEngine Capital LLC
          File Number: 007-00059

        OFFERING:
          Security: Common Stock
          Target: $50,000 | Maximum: $5,000,000
          Target is 1% of maximum
          Price: $10.00/unit | Units: 500,000
          Deadline: 2024-06-15
          Status: 92 days remaining
    """
```

**Token Budgets**:
- Minimal: ~100-200 tokens
- Standard: ~300-500 tokens
- Full: ~600-1000 tokens

**Computed Fields**:
- Days to deadline
- Target as percentage of maximum
- Offering status

#### Example 5: XBRL.to_context() - Financial Data Context

```python
def to_context(self, max_tokens: int = 2000) -> str:
    """
    Get AI-optimized Markdown-KV representation.

    Returns:
        Markdown-formatted representation with:
        - Entity metadata
        - Available statements
        - Common query patterns
        - Fact counts

    Example Output:
        **Entity:** Apple Inc.
        **CIK:** 0000320193
        **Form:** 10-K
        **Facts:** 1234
        **Contexts:** 567

        **Available Statements:**
        - Income Statement
        - Balance Sheet
        - Cash Flow Statement

        **Common Actions:**
        - xbrl.statements.income_statement()
        - xbrl.facts.query().by_concept("Revenue")
        - xbrl.get_statement("IncomeStatement")
    """
```

**Token Budget**:
- Single parameter: `max_tokens` (default: 2000)
- No progressive disclosure levels

### Pattern Variations

**Variation A: Detail Levels (Filing, Filings, Company, FormC)**
- Uses `detail` parameter: 'minimal', 'standard', 'full'
- Progressively adds more information
- Consistent token budgets across objects

**Variation B: Max Tokens Only (XBRL)**
- Uses `max_tokens` parameter instead of detail levels
- Simple truncation at character limit
- No progressive disclosure

**Variation C: EntityFilings (Company-Specific Collections)**
- Extends Filings.to_context() with company header
- Adds company name and CIK to context
- Maintains same navigation hints

### Usage Locations

**Core Objects**:
- `edgar/_filings.py:930` - Filing.to_context()
- `edgar/_filings.py:1977` - Filings.to_context()
- `edgar/entity/core.py:638` - Company.to_context()
- `edgar/entity/filings.py:368` - EntityFilings.to_context()
- `edgar/xbrl/xbrl.py:1721` - XBRL.to_context()

**Form-Specific Objects**:
- `edgar/offerings/formc.py:693` - FormC.to_context()
- `edgar/offerings/campaign.py:510` - Offering.to_context()

**Test Coverage**:
- `tests/test_ai_native_context.py` - Complete test suite
- `tests/test_ai_text_methods.py` - Format validation tests
- `tests/test_company.py` - Company context tests

### Pattern Context

**Typically used when**:
- AI agent needs to understand available operations
- Building context for LLM prompt
- Discovering API capabilities
- Navigating between related objects

**Often combined with**:
- `.docs` property for detailed documentation
- Helper functions for specific workflows
- Progressive discovery (minimal → standard → full)

**Common parameters**:
- `detail='standard'` - Default balanced view
- `detail='minimal'` - Quick overview when tokens are scarce
- `detail='full'` - Comprehensive view when context window allows
- `max_tokens=None` - No truncation (Company, FormC)

---

## Pattern: extract_markdown() and extract_sections() for Filing Content Extraction

### Pattern Overview
The `edgar.llm` module provides high-level functions for extracting filing content as clean, token-efficient markdown suitable for LLM processing. It handles XBRL statements, items, and notes with smart preprocessing and optimization.

### Key Characteristics
- **Multi-Strategy Extraction**: XBRL → Document sections → Regex fallback
- **LLM Optimizations**: Cell merging, deduplication, noise filtering
- **Flexible Output**: Combined markdown or structured sections
- **YAML Headers**: Filing metadata in frontmatter format

### Examples Found

#### Example 1: Basic extract_markdown() Usage

```python
from edgar import Filing
from edgar.llm import extract_markdown

filing = Filing(form='10-K', cik='0001318605', accession_no='0001564590-24-004069')

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
```

**Output Format**:
```markdown
---
filing_type: 10-K
accession_number: 0001564590-24-004069
filing_date: 2024-01-29
company: Tesla Inc
ticker: TSLA
sections:
  - Income Statement
format: markdown
---

## SECTION: Income Statement
<!-- Source: XBRL -->
| Label | 2023 | 2022 | 2021 |
|-------|------|------|------|
| Revenue | $96,773 | $81,462 | $53,823 |
| Cost of Revenue | $79,113 | $60,609 | $40,217 |
...
```

#### Example 2: Extracting Multiple Items

```python
# Extract multiple items at once
markdown = extract_markdown(filing, item=["1", "1A", "7", "8"])
```

**Use Cases**:
- Item 1: Business description
- Item 1A: Risk factors
- Item 7: MD&A (Management Discussion & Analysis)
- Item 8: Financial statements

#### Example 3: Structured Sections Output

```python
from edgar.llm import extract_sections

# Extract as structured objects
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
```

**ExtractedSection Structure**:
```python
@dataclass
class ExtractedSection:
    title: str           # "Income Statement"
    markdown: str        # Markdown content
    source: str          # "xbrl:IncomeStatement" or "item:1"
    is_xbrl: bool       # True if from XBRL, False if from HTML
```

#### Example 4: Dimension Control in XBRL Statements

```python
# Show dimension, abstract, and level columns (default: True)
markdown_with_dims = extract_markdown(
    filing,
    statement=["IncomeStatement"],
    show_dimension=True
)

# Hide dimension columns for cleaner output
markdown_without_dims = extract_markdown(
    filing,
    statement=["IncomeStatement"],
    show_dimension=False
)
```

**Purpose**:
- `show_dimension=True` - Includes XBRL metadata for analysis
- `show_dimension=False` - Cleaner output for general LLM consumption

#### Example 5: Filtered Data Tracking

```python
# Track what was filtered out during optimization
markdown = extract_markdown(
    filing,
    notes=True,
    optimize_for_llm=True,
    show_filtered_data=True,
    max_filtered_items=10
)
```

**Output Includes**:
```markdown
---
## FILTERED DATA METADATA

Total items filtered: 45
- XBRL metadata tables: 12
- Duplicate tables: 8
- Filtered text blocks: 25

### Details:
1. Type: xbrl_metadata
   Reason: Low information density
   Title: Document and Entity Information
2. Type: duplicate
   Reason: Exact duplicate of earlier table
   Preview: Schedule of Revenue by Segment...
...
```

#### Example 6: Item Extraction with Boundaries

```python
# Item boundary patterns for section extraction
_ITEM_BOUNDARIES = {
    "Item 1": ["Item 1A", "Item 1B", "Item 1C", "Item 2"],
    "Item 1A": ["Item 1B", "Item 1C", "Item 2"],
    "Item 7": ["Item 7A", "Item 8"],
    "Item 8": ["Item 9", "Item 9A", "Item 9B"],
    # ... etc
}
```

**Multi-Strategy Extraction**:
1. **Strategy 1**: Document sections (preferred)
2. **Strategy 2**: Regex with boundaries (fallback)
3. **Strategy 3**: HTML subsection detection

### Pattern Variations

**Variation A: Statement Extraction (XBRL)**

```python
def _extract_xbrl_statements(
    filing: 'Filing',
    statements: Union[str, Sequence[str]],
    optimize_for_llm: bool,
    show_dimension: bool = True
) -> List[ExtractedSection]:
    """
    Strategy:
    1. Get financials from filing
    2. Render using EdgarTools
    3. Convert to DataFrame
    4. Filter dimensions if needed
    5. Convert to markdown
    """
```

**Statement Mappings**:
- "IncomeStatement" → Income Statement
- "BalanceSheet" → Balance Sheet
- "CashFlowStatement" → Cash Flow Statement
- "StatementOfEquity" → Statement of Equity
- "ComprehensiveIncome" → Comprehensive Income

**Variation B: Item Extraction (HTML)**

```python
def _extract_items(
    filing: 'Filing',
    items: Union[str, Sequence[str]],
    optimize_for_llm: bool
) -> List[ExtractedSection]:
    """
    Strategy:
    1. Try Document sections first (structured)
    2. Extract tables from section
    3. Deduplicate tables
    4. Apply LLM optimizations
    5. Fallback to regex boundary extraction
    """
```

**Variation C: Notes Extraction (Hybrid)**

```python
def _extract_notes(
    filing: 'Filing',
    optimize_for_llm: bool,
    track_filtered: bool = False
) -> Union[List[ExtractedSection], Tuple[List[ExtractedSection], Dict]]:
    """
    Strategy 1: Use filing.reports.get_by_category("Notes") for XBRL filings
    Strategy 2: Use Document sections as fallback
    """
```

### Usage Locations

**Primary Module**:
- `edgar/llm.py` - Main extraction functions (726 lines)

**Import Patterns**:
- `from edgar.llm import extract_markdown`
- `from edgar.llm import extract_sections`
- `from edgar.llm import ExtractedSection`

**Example Scripts**:
- `tools/example_llm_usage.py` - Comprehensive examples
- `tools/usage_examples.py` - Usage demonstrations
- `demo_show_dimension.py` - Dimension control demo

**Documentation**:
- `EXTRACTION_GUIDE.md` - Complete extraction guide
- `IMPLEMENTATION_SUMMARY.md` - Implementation overview
- `NEW_FEATURES.md` - Feature documentation

**Test Coverage**:
- `tests/test_llm_return_types.py` - Type checking
- `test_markdown_extraction_comprehensive.py` - Extraction tests
- `test_subsection_detection.py` - Subsection tests

### Pattern Context

**Typically used when**:
- Extracting filing content for LLM analysis
- Building RAG (Retrieval Augmented Generation) systems
- Creating filing summaries
- Analyzing specific sections (Item 7, financials, notes)

**Often combined with**:
- `filing.obj()` - Get typed report object first
- `filing.xbrl()` - Direct XBRL access for complex queries
- LangChain, LlamaIndex - RAG frameworks

**Common parameters**:
- `statement=["IncomeStatement"]` - Extract financial statements
- `item=["1", "7"]` - Extract specific items
- `notes=True` - Include financial statement notes
- `optimize_for_llm=True` - Apply preprocessing (default)
- `show_dimension=True` - Include XBRL metadata columns (default)
- `include_header=True` - Add YAML frontmatter (default)
- `show_filtered_data=False` - Track filtered content (off by default)

---

## Pattern: AI Integration in Real-World Workflows

### Pattern Overview
EdgarTools provides multiple layers of AI integration used in actual workflows: interactive documentation, context generation, and specialized extraction. These are used together for different use cases.

### Examples Found

#### Example 1: Offering Lifecycle Discovery Workflow

```python
# Streamlined API Features Used:
# - Company.get_filings() - Discovery
# - filing.obj() → FormC - Parsing
# - formc.issuer_name, .portal_name - Property access
# - formc.get_offering() → Offering - Aggregation
# - offering.to_context() - AI-optimized context

# STEP 1: Discover filings
forms = ['C', 'C/A', 'C-U', 'C-AR', 'C-TR']
viit = Company(1881570)
filings = viit.get_filings(form=forms)
print(filings.to_context())  # AI discovers available filings

# STEP 2: Parse specific filing
filing = filings.latest()
formc: FormC = filing.obj()
console.print(f"Analyzing filing: {filing.form} on {filing.filing_date}")

# STEP 3: Get complete offering lifecycle
offering: Offering = formc.get_offering()
console.print(f"Status: {offering.status}")

# STEP 4: Navigate lifecycle stages
for stage_name, form_type in [("Initial", "C"), ("Amendments", "C/A"), ...]:
    stage_filings = offering.all_filings.filter(form=form_type)
    # Process each stage...
```

**Use Case**: AI agent tracking crowdfunding campaign lifecycle

#### Example 2: Building LLM Context (Multi-Layer)

```python
def example_4_building_llm_context():
    """Build comprehensive context for an LLM."""
    company = Company("TSLA")

    # Build multi-part context
    context_parts = []
    token_budget = 1500
    tokens_used = 0

    # 1. Company overview (minimal)
    company_text = company.text(detail='minimal', max_tokens=200)
    context_parts.append("# Company Overview")
    context_parts.append(company_text)
    tokens_used += len(company_text.split()) * 1.3

    # 2. Latest filing (standard)
    filing = company.get_filings(form="10-K").latest()
    filing_text = filing.text(detail='standard', max_tokens=300)
    context_parts.append("\n# Latest 10-K Filing")
    context_parts.append(filing_text)
    tokens_used += len(filing_text.split()) * 1.3

    # 3. Financial statement
    xbrl = filing.xbrl()
    income = xbrl.statements.income_statement()
    statement_text = income.text(max_tokens=500)
    context_parts.append("\n# Income Statement")
    context_parts.append(statement_text)
    tokens_used += len(statement_text.split()) * 1.3

    # Combine for LLM
    full_context = "\n".join(context_parts)
    print(f"Total context: ~{tokens_used:.0f} tokens (budget: {token_budget})")
```

**Use Case**: Building optimized context within token budget

#### Example 3: Documentation Search Pattern

```python
from edgar import Company

company = Company("AAPL")

# Search for relevant documentation
query = "how do I get historical financials"
results = company.docs.search(query)

# Display top results
print(f"Search results for: {query}\n")
for i, result in enumerate(results[:3], 1):
    print(f"{i}. {result}")
```

**Use Case**: Interactive API discovery through semantic search

### Usage Patterns Summary

**Pattern 1: Progressive Context Building**
```python
# Start minimal, expand as needed
minimal = company.to_context(detail='minimal')    # ~100 tokens
standard = company.to_context(detail='standard')  # ~250 tokens
full = company.to_context(detail='full')          # ~500 tokens
```

**Pattern 2: Multi-Object Workflow**
```python
# Navigate object graph with context hints
company_ctx = company.to_context()           # Hints at .get_filings()
filings_ctx = filings.to_context()          # Hints at .latest()
filing_ctx = filing.to_context()            # Hints at .obj()
formc_ctx = formc.to_context()              # Hints at .get_offering()
```

**Pattern 3: Hybrid Approach (Context + Extraction)**
```python
# Use context for navigation, extraction for content
context = filing.to_context(detail='standard')  # Discover structure
markdown = extract_markdown(filing, item="7", statement=["IncomeStatement"])  # Extract content
```

**Pattern 4: Token Budget Management**
```python
# Allocate tokens across objects
budget = 2000
company_text = company.to_context(detail='minimal', max_tokens=300)  # 300
filing_text = filing.to_context(detail='standard', max_tokens=400)   # 400
xbrl_text = xbrl.to_context(max_tokens=1300)                         # 1300
# Total: 2000 tokens
```

---

## Use Case Drivers

### 1. AI Agent Navigation (to_context())
**Driver**: AI agents need to discover API capabilities without reading full documentation

**Evidence**:
- Tests in `test_ai_native_context.py` validate workflow discovery
- Planning doc `AI_NATIVE_WORKFLOW_IMPLEMENTATION_PLAN.md` explicitly describes agent navigation
- Example `offering_lifecycle.py` shows step-by-step agent workflow

**Quote from docs**:
> "This method provides structured information about the filings collection in a markdown-KV format that is optimized for AI agent navigation and discovery."

### 2. LLM Context Windows (to_context() with token budgets)
**Driver**: LLM context windows have strict token limits (Claude: 200K, GPT-4: 128K)

**Evidence**:
- Every `to_context()` method has token budgets
- Tests validate token limits: `test_filing_token_budgets()`, `test_filings_token_budgets()`
- `detail` parameter provides progressive disclosure

**Quote from docs**:
> "Uses Markdown-KV format (60.7% accuracy, 25% fewer tokens than JSON) optimized for LLM consumption."

### 3. RAG System Integration (extract_markdown())
**Driver**: Building RAG (Retrieval Augmented Generation) systems requires clean, structured content

**Evidence**:
- `extract_markdown()` returns clean markdown suitable for embedding
- YAML headers provide metadata for retrieval
- `ExtractedSection` supports structured indexing

**Quote from module docstring**:
> "High-level API for LLM-optimized content extraction from SEC filings. Features: XBRL statements, Notes, Items, Smart table preprocessing, Column deduplication, Noise filtering"

### 4. Research Workflows (example scripts)
**Driver**: Researchers need to analyze specific filing sections

**Evidence**:
- `offering_lifecycle.py` - Campaign research
- `viit_research.py` - Company-specific analysis
- `ai_context.py` - Multi-layer context building

**Quote from offering_lifecycle.py**:
> "Research Goal: Track a crowdfunding campaign from inception through completion or termination"

---

## Research-Backed Design Decisions

### Markdown-KV Format Choice
**Research Source**: improvingagents.com/blog/best-input-data-format-for-llms

**Evidence in Code**:
```python
# edgar/entity/core.py:645-646
"""
Uses Markdown-KV format (60.7% accuracy, 25% fewer tokens than JSON) optimized
for LLM consumption.

Research basis: improvingagents.com/blog/best-input-data-format-for-llms
"""
```

**Findings**:
- 60.7% accuracy vs other formats
- 25% fewer tokens than JSON
- Best balance of human readability and machine parseability

### Progressive Disclosure Pattern
**Evidence**: Consistent across all `to_context()` implementations

**Detail Levels**:
- **Minimal**: Essential fields only (~100-150 tokens)
- **Standard**: Adds context and actions (~250-350 tokens)
- **Full**: Comprehensive view (~500-800 tokens)

**Research Basis**: Allows AI agents to request only needed detail level, conserving tokens

---

## Documentation and Testing Patterns

### Test Coverage for to_context()

**Test Classes**:
1. `TestGetObjInfo` - Helper function validation
2. `TestFilingToContext` - Filing context generation
3. `TestFilingsToContext` - Collection context
4. `TestEntityFilingsToContext` - Entity-specific collections
5. `TestFormCToContext` - Form-specific context
6. `TestFullWorkflowDiscovery` - End-to-end agent workflows
7. `TestTokenBudgets` - Token limit validation
8. `TestEdgeCases` - Error handling

**Example Test**:
```python
def test_full_workflow_discoverable(self):
    """Agent should be able to discover full workflow through context."""
    company = Company(1881570)

    # Step 2: Filings hints at .latest()
    filings = company.get_filings(form='C')
    filings_context = filings.to_context()
    assert '.latest()' in filings_context

    # Step 3: Filing hints at .obj()
    filing = filings.latest()
    filing_context = filing.to_context()
    assert '.obj()' in filing_context

    # Step 4: FormC hints at .get_offering()
    formc = filing.obj()
    formc_context = formc.to_context()
    assert '.get_offering()' in formc_context
```

### Documentation Coverage
**AI Integration Guide**: `docs/ai-integration.md` (822 lines)

**Sections**:
1. Overview - Three levels of integration
2. Interactive Documentation (.docs property)
3. AI-Optimized Text Output (.text() methods)
4. AI Skills System
5. Model Context Protocol (MCP) Server
6. Helper Functions
7. Best Practices
8. Token Optimization

**Key Quote**:
> "EdgarTools is designed from the ground up to work seamlessly with AI agents and Large Language Models (LLMs)."

---

## Migration Patterns (Deprecation Handling)

### .text() → .to_context() Migration

```python
def text(self, max_tokens: int = 2000) -> str:
    """
    Deprecated: Use to_context() instead.

    Get AI-optimized plain text representation.
    This method is deprecated and will be removed in a future version.
    Use to_context() for consistent naming with other AI-native methods.
    """
    import warnings
    warnings.warn(
        "Company.text() is deprecated and will be removed in version 6.0. "
        "Use Company.to_context() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    # Delegate to to_context() with 'standard' detail
    return self.to_context(detail='standard', max_tokens=max_tokens)
```

**Test Coverage**:
```python
# tests/test_ai_text_methods.py:116-133
def test_company_text_deprecated(aapl_company):
    """Test that Company.text() still works but issues deprecation warning."""
    import warnings

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        text = aapl_company.text(max_tokens=2000)

        # Should have issued a deprecation warning
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "deprecated" in str(w[0].message).lower()
        assert "to_context" in str(w[0].message)

        # But should still return valid output
        assert "COMPANY:" in text
```

**Migration Timeline** (from CHANGELOG.md):
- Version 5.2.0: Introduced `.to_context()` naming convention
- Version 5.2.0: Deprecated `.text()` with warnings
- Version 6.0.0: Planned removal of `.text()` methods

---

## Summary: Actual Usage Evidence

### What We Know For Sure

1. **to_context() is Production Code**
   - 7+ implementations across core classes
   - 356 lines of tests in test_ai_native_context.py
   - Used in example scripts (offering_lifecycle.py, ai_context.py)

2. **extract_markdown() is Production Code**
   - 726-line module (edgar/llm.py)
   - Multiple example scripts demonstrating usage
   - Complete extraction guide documentation

3. **Real Use Cases Documented**
   - AI agent navigation workflows
   - LLM context building with token budgets
   - RAG system integration
   - Research workflows

4. **Research-Backed Design**
   - Markdown-KV format (60.7% accuracy, 25% fewer tokens)
   - Progressive disclosure pattern
   - Token optimization strategies

5. **Active Development**
   - Recent migration from .text() to .to_context()
   - Comprehensive test coverage
   - Detailed documentation (822-line AI integration guide)

### File Paths Referenced in This Document

**Implementation Files**:
- `C:\Users\SaifA\OneDrive\ai project\Citra\web features\sec-filings\edgartools_git\edgar\_filings.py`
- `C:\Users\SaifA\OneDrive\ai project\Citra\web features\sec-filings\edgartools_git\edgar\entity\core.py`
- `C:\Users\SaifA\OneDrive\ai project\Citra\web features\sec-filings\edgartools_git\edgar\entity\filings.py`
- `C:\Users\SaifA\OneDrive\ai project\Citra\web features\sec-filings\edgartools_git\edgar\offerings\formc.py`
- `C:\Users\SaifA\OneDrive\ai project\Citra\web features\sec-filings\edgartools_git\edgar\offerings\campaign.py`
- `C:\Users\SaifA\OneDrive\ai project\Citra\web features\sec-filings\edgartools_git\edgar\xbrl\xbrl.py`
- `C:\Users\SaifA\OneDrive\ai project\Citra\web features\sec-filings\edgartools_git\edgar\llm.py`

**Test Files**:
- `C:\Users\SaifA\OneDrive\ai project\Citra\web features\sec-filings\edgartools_git\tests\test_ai_native_context.py`
- `C:\Users\SaifA\OneDrive\ai project\Citra\web features\sec-filings\edgartools_git\tests\test_ai_text_methods.py`
- `C:\Users\SaifA\OneDrive\ai project\Citra\web features\sec-filings\edgartools_git\tests\test_company.py`

**Example Files**:
- `C:\Users\SaifA\OneDrive\ai project\Citra\web features\sec-filings\edgartools_git\docs\examples\offering_lifecycle.py`
- `C:\Users\SaifA\OneDrive\ai project\Citra\web features\sec-filings\edgartools_git\examples\scripts\ai\ai_context.py`
- `C:\Users\SaifA\OneDrive\ai project\Citra\web features\sec-filings\edgartools_git\tools\example_llm_usage.py`

**Documentation Files**:
- `C:\Users\SaifA\OneDrive\ai project\Citra\web features\sec-filings\edgartools_git\docs\ai-integration.md`
- `C:\Users\SaifA\OneDrive\ai project\Citra\web features\sec-filings\edgartools_git\EXTRACTION_GUIDE.md`
- `C:\Users\SaifA\OneDrive\ai project\Citra\web features\sec-filings\edgartools_git\docs-internal\planning\AI_NATIVE_WORKFLOW_IMPLEMENTATION_PLAN.md`
