# Research: Comparing EdgarTools Standardization with mpreiss9's Approach

**Date**: 2025-11-20 (Updated: 2025-11-22)
**Research Phase**: 1 of 3 (FIC Workflow)
**Next Phase**: Planning (`/plan`) - COMPLETE
**GitHub Issue**: #494 - "Create documentation on how to customize standardization tagging"
**Architecture**: `docs-internal/planning/architecture/xbrl-standardization-pipeline.md` (2025-11-22)
**CSV Analysis**: `docs-internal/research/xbrl-mapping-analysis-mpreiss9.md` (2025-11-21)

## Research Question

Looking at Issue #494, particularly the last comment where user @mpreiss9 outlined their standardization method, could we improve how we do standardization by following their approach?

**UPDATE 2025-11-21**: @mpreiss9 shared production CSV mapping files containing 6,177 mappings from 390 companies. Detailed analysis: `docs-internal/research/xbrl-mapping-analysis-mpreiss9.md`

## Executive Summary

This research compares two fundamentally different approaches to XBRL standardization:

1. **EdgarTools Current Approach**: Forward mapping (`StandardConcept → [CompanyConcepts]`) with priority-based resolution
2. **mpreiss9's Approach**: Reverse mapping (`CompanyConcept → [StandardConcepts]`) with section-based context resolution

### Key Findings

- **EdgarTools has the infrastructure for context-aware disambiguation BUT it's not implemented** - context is passed throughout the code but completely ignored during mapping
- **mpreiss9's method successfully handles 200+ ambiguous tags** using backwards processing and section-based resolution
- **Both approaches have merit** - EdgarTools excels at simplicity and performance, mpreiss9's excels at handling ambiguity and validation
- **The two approaches are complementary, not contradictory** - elements from mpreiss9's method could enhance EdgarTools without replacing the current system
- **Real-world validation data now available** - 6,177 production mappings from 390 companies provide concrete test cases and validation data (2025-11-21)
- **Architecture designed** (2025-11-22) - 7-stage pipeline integrates both approaches with clean boundaries

---

## Detailed Findings

### 1. EdgarTools Current Implementation

#### Mapping Direction: Forward (`StandardConcept → [CompanyConcepts]`)

**File**: `edgar/xbrl/standardization/core.py`

**Data Structure** (Lines 134-137):
```python
class MappingStore:
    """
    Attributes:
        mappings (Dict[str, Set[str]]): Dictionary mapping standard concepts to sets of company concepts
    """
```

**JSON Format** (`concept_mappings.json`):
```json
{
  "Revenue": [
    "us-gaap:Revenue",
    "us-gaap:Revenues",
    "us-gaap:SalesRevenueNet"
  ],
  "Automotive Revenue": [
    "tsla:AutomotiveRevenue",
    "tsla:AutomotiveSales"
  ]
}
```

**Lookup Flow**:
1. Given `company_concept` like `"tsla:AutomotiveRevenue"`
2. Iterate through ALL standard concepts
3. Check if `company_concept` is IN the set of mapped concepts
4. Return the standard concept (or None)

**Time Complexity**: O(n × m) where n = number of standard concepts, m = average set size

#### Priority-Based Resolution

**File**: `edgar/xbrl/standardization/core.py:408-449`

**Priority Levels**:
- **P1 (lowest)**: Core mappings from `concept_mappings.json`
- **P2 (higher)**: Company-specific mappings from `company_mappings/*.json`
- **P4 (highest)**: When concept prefix matches company (e.g., `tsla:Revenue` uses Tesla mappings)

**Resolution Logic** (Lines 430-443):
```python
for std_concept, mapping_list in self.merged_mappings.items():
    for concept, source, priority in mapping_list:
        if concept == company_concept:
            effective_priority = priority
            # Boost priority if it matches detected entity
            if detected_entity and source == detected_entity:
                effective_priority = 4  # Highest priority
            candidates.append((std_concept, effective_priority, source))

# Return highest priority match
if candidates:
    best_match = max(candidates, key=lambda x: x[1])
    return best_match[0]
```

#### Context Handling: NOT IMPLEMENTED

**Critical Finding**: Context parameter exists but is **completely ignored** during mapping.

**Evidence** (`core.py:493-518`):
```python
def map_concept(self, company_concept: str, label: str, context: Dict[str, Any]) -> Optional[str]:
    # Use cache for faster lookups
    cache_key = (company_concept, context.get('statement_type', ''))  # ← Context only for caching
    if cache_key in self._cache:
        return self._cache[cache_key]

    # Check if we already have a mapping in the store
    standard_concept = self.mapping_store.get_standard_concept(company_concept)  # ← NO context passed!
    if standard_concept:
        self._cache[cache_key] = standard_concept
        return standard_concept
```

**Documentation Confirms** (`core.py:414`):
```python
def get_standard_concept(self, company_concept: str, context: Dict = None) -> Optional[str]:
    """
    Args:
        context: Optional context information (not used in current implementation)  # ← Explicit statement
    """
```

#### Ambiguous Tag Problem

**Issue #494 Comment**: User @mpreiss9 identified **200+ ambiguous XBRL tags** including:

**Asset/Liability Ambiguity (12 tags)**:
- `DeferredTaxAssetsLiabilitiesNet` - Could be asset OR liability depending on sign
- `DerivativeAssetsLiabilitiesAtFairValueNet` - Net of assets and liabilities
- `UnamortizedDebtIssuanceExpense` - Could be asset (deferred charge) OR liability offset

**Current/Noncurrent Ambiguity (180+ tags)**:
- `AccountsPayableCurrentAndNoncurrent` - Could be current OR noncurrent
- `DeferredRevenue` - Doesn't specify current vs noncurrent
- `ConvertibleDebt` - Could be short-term OR long-term

**Triple Ambiguity (1 tag)**:
- `DerivativeLiabilityFairValueGrossAsset` - Ambiguous in 3 dimensions:
  1. Asset vs Liability
  2. Current vs Noncurrent
  3. Gross vs Net

**EdgarTools Cannot Handle These**: The current system has no mechanism to map these differently based on:
- Where they appear in statement hierarchy
- Their calculation parent
- Their sign/value
- Statement context

---

### 2. mpreiss9's Standardization Method

#### Mapping Direction: Reverse (`CompanyConcept → [StandardConcepts]`)

**From Issue #494 Comment**:

> "My tag map is reversed from yours - I have xbrl tags as a primary key (since they are unique) and then standard tags attached. So an xbrl tag can be mapped to more than one standard tag."

**Data Structure** (Conceptual):
```python
{
  "us-gaap:DeferredTaxAssetsLiabilitiesNet": [
    "Deferred Tax Assets",  # When in assets context
    "Deferred Tax Liabilities"  # When in liabilities context
  ],
  "us-gaap:AccountsPayableCurrentAndNoncurrent": [
    "Accounts Payable, Current",  # When parent is current liabilities
    "Accounts Payable, Noncurrent",  # When parent is noncurrent liabilities
    "Accounts Payable, Total"  # When it's a total line
  ]
}
```

**Advantages**:
1. **Natural lookup**: O(1) hash lookup instead of iteration
2. **Explicit ambiguity handling**: Multiple standard tags per XBRL tag
3. **Context-aware by design**: Same tag can map to different concepts based on context

#### Section-Based Resolution Strategy

**From Issue #494 Comment**:

> "I have a dictionary with balance sheet sections as keys (using a standard tag) and all the possible standard tags for that section as a set attached to the key."

**Section Dictionary** (Conceptual):
```python
{
  "Current Assets": {
    "Cash and Cash Equivalents",
    "Accounts Receivable",
    "Inventory",
    "Prepaid Expenses",
    ...
  },
  "Current Liabilities": {
    "Accounts Payable, Current",
    "Accrued Liabilities",
    "Short Term Debt",
    ...
  }
}
```

**Resolution Algorithm** (From comment):

1. **Assign standard tags** to all items (including ambiguous ones with multiple tags)
2. **Assign sections** working backwards using hierarchy levels and totals
3. **Disambiguate** by checking which standard tag belongs in the assigned section
4. **Remove incorrect mappings** leaving only the contextually appropriate one

**Quote**:
> "Then again working backwards up the balance sheet for any item that has more than one standard tag I look to see which of the standard tags matches what should be in that section (using the dictionary just described). I then remove the incorrect ones from that item."

#### Backwards Processing

**Why Backwards?**

> "Working backwards is helpful because the subtotals are the trigger for a new section."

**Explanation**: In financial statements, subtotals (like "Total Current Assets") define section boundaries. By processing backwards (bottom to top), you encounter the subtotal first, which tells you what section you're in.

**Example** (Balance Sheet):
```
Total Assets                          ← Process 5th: Top-level section marker
  Total Current Assets                ← Process 4th: Section marker → entering Current Assets
    Cash                              ← Process 3rd: Now we know we're in Current Assets
    Accounts Receivable               ← Process 2nd
    Inventory                         ← Process 1st: Start here
```

#### Special Case: Noncurrent Liabilities

**From Issue #494 Comment**:

> "There is one special case in the balance sheet where different filers will use an xbrl tag either as a line item or as a total (Noncurrent liabilities). That one has to be dealt with first before doing the above process."

**Resolution Strategy**:
```python
# Check label for clues
if "Other" in label:
    → "Other Noncurrent Liabilities" (line item)
elif "Total" in label:
    → "Total Noncurrent Liabilities" (total)
else:
    # Check if it matches the calculation
    if (total_liabilities - current_liabilities) == value:
        → "Total Noncurrent Liabilities"
    else:
        → "Other Noncurrent Liabilities"
```

#### CSV Format for Mapping Management

**From Issue #494 Comment**:

> "I happen to use .csv for my 2 mapping files so it's easy to edit, check for duplicates and so on in Excel."

**CSV Structure**:
```csv
company_concept,standard_concept,company_cik,notes
us-gaap:Revenue,Revenue,,Core GAAP
tsla:AutomotiveRevenue,Automotive Revenue,1318605,Tesla-specific
us-gaap:DeferredTaxAssetsLiabilitiesNet,Deferred Tax Assets,,When positive/in assets
us-gaap:DeferredTaxAssetsLiabilitiesNet,Deferred Tax Liabilities,,When negative/in liabilities
```

**Benefits**:
- Excel editing and duplicate detection
- Easy filtering by company (CIK)
- Explicit handling of multi-mapping
- Notes column for context rules

#### Unmapped Tag Logging

**From Issue #494 Comment**:

> "I also did to make the process easier was to create separate log files for unmapped tags discovered during processing that caused me to have out of balance statements. The logs are in the same format as my mapping files, and include a 'guess' as to the correct mapping."

**Log Format** (Conceptual):
```csv
company_concept,suggested_mapping,confidence,label,cik,context,notes
us-gaap:NewConceptFound,Revenue,0.85,Total Revenue,1318605,parent=Income,Review: high confidence
us-gaap:AmbiguousTag,Deferred Tax Assets,0.50,Deferred Tax,0001652044,parent=Assets,Review: needs context
```

**Process**:
1. Discover unmapped tag during statement processing
2. Log it with suggested mapping and confidence
3. Include context (parent, statement type, etc.)
4. Review and add to mapping file

---

### 3. Validation: Balance Sheet Balancing

#### mpreiss9's Validation Strategy

**From Issue #494 Comment**:

> "For me, the validation is always can I create a statement that balances using just mapped data. That means, for Balance Sheet Total Assets = Current Assets + Noncurrent Assets (if it's provided) = all the asset detail items. Ditto Liabilities/Equity."

**Validation Equations**:
```python
# Level 1: Fundamental equation
Total Assets == Total Liabilities + Total Equity

# Level 2: Section totals
Total Assets == Current Assets + Noncurrent Assets
Total Liabilities == Current Liabilities + Noncurrent Liabilities

# Level 3: Detail rollup
Total Assets == sum(all individual asset line items)
Current Assets == sum(all current asset line items)
```

**Validation Triggers Mapping Fixes**:
- If statement doesn't balance → unmapped tag or incorrect mapping
- Log the unmapped tag with context
- Review and add to mapping file
- Reprocess to verify balance

#### EdgarTools Validation: What EXISTS

**Balance Type Validation** (`edgar/xbrl/parsers/concepts.py`):
- Lines 144-380: `US_GAAP_BALANCE_TYPES` dictionary mapping 155+ concepts to 'debit' or 'credit'
- Assets, Expenses → debit balance
- Liabilities, Equity, Revenue → credit balance

**Required Concepts** (`edgar/xbrl/statements.py:72-87`):
```python
REQUIRED_CONCEPTS = {
    'BalanceSheet': ['Assets', 'Liabilities', 'StockholdersEquity'],
    'IncomeStatement': ['Revenues', 'NetIncomeLoss'],
    'CashFlowStatement': ['CashAndCashEquivalentsPeriodIncreaseDecrease', 'CashAndCashEquivalentsAtCarryingValue']
}
```

**Test-Level Validation** (`tests/test_standardized_concepts.py:123-127`):
```python
# Implements accounting equation validation
balance_diff = abs(assets - (liabilities + equity))
assert balance_diff < (assets * 0.01)  # 1% tolerance
```

**BUT**: No automated balance sheet validation in production code that:
- Checks Assets = Liabilities + Equity
- Verifies section totals equal detail items
- Triggers mapping corrections

#### EdgarTools Period Data Quality

**Period Validation** (`edgar/xbrl/period_data_check.py:111-237`):
```python
def check_period_data_quality(xbrl, period_key, statement_type):
    """Validates period has sufficient data"""
    return {
        'fact_count': total_facts,
        'meaningful_fact_count': non_zero_facts,
        'essential_coverage': percentage,  # % of essential concepts present
        'has_sufficient_data': fact_count > min_threshold,
        'missing_essentials': [...],
        'found_essentials': [...]
    }
```

**What It Does**:
- Counts facts for specific periods
- Checks essential concept coverage
- Filters periods with insufficient data
- **Does NOT validate accounting equations**

---

### 4. Comparison: EdgarTools vs mpreiss9 Approach

#### Mapping Direction

| Aspect | EdgarTools | mpreiss9 |
|--------|------------|----------|
| **Primary Key** | Standard Concept | Company Concept (XBRL tag) |
| **Data Structure** | `{std: [company1, company2]}` | `{company: [std1, std2]}` |
| **Lookup Complexity** | O(n × m) iteration | O(1) hash lookup |
| **Multi-Mapping** | Not supported by design | Explicitly supported |
| **Ambiguity Handling** | Priority-based (company > core) | Context-based resolution |

#### Context Awareness

| Aspect | EdgarTools | mpreiss9 |
|--------|------------|----------|
| **Context Infrastructure** | ✅ Exists (parameter threaded through code) | ✅ Fully implemented |
| **Context Usage** | ❌ Ignored during mapping | ✅ Core to disambiguation |
| **Available Context** | statement_type, level, is_total | Parent concept, section, sign, value |
| **Resolution Strategy** | Priority levels (P1/P2/P4) | Section membership + backwards processing |

#### Ambiguous Tag Handling

**EdgarTools Current**:
- Cannot distinguish `DeferredTaxAssetsLiabilitiesNet` as asset vs liability
- Returns same mapping regardless of context
- Would need significant enhancements

**mpreiss9's Method**:
- Explicitly handles 200+ ambiguous tags
- Uses section dictionaries to determine correct mapping
- Backwards processing identifies section boundaries
- Special case handling (e.g., Noncurrent Liabilities total vs line item)

#### Validation

| Aspect | EdgarTools | mpreiss9 |
|--------|------------|----------|
| **Balance Sheet Equation** | Test-level only | Production validation |
| **Section Totals** | Not checked | Checked during mapping |
| **Detail Rollup** | Not validated | Validates all detail items sum to totals |
| **Validation Triggers** | Manual | Triggers mapping corrections |
| **Out of Balance Handling** | No automated response | Logs unmapped tags for review |

#### Workflow

**EdgarTools**:
1. Load mappings from JSON
2. For each concept → lookup standard concept (priority-based)
3. Cache result
4. Standardize statement

**mpreiss9**:
1. Load mappings from CSV (allows multi-mapping)
2. Assign ALL possible standard tags to each item
3. Assign sections working backwards (using subtotals)
4. Disambiguate by checking section membership
5. Remove incorrect mappings
6. Validate balance sheet equation
7. If out of balance → log unmapped tags
8. Review logs and update mappings

---

### 5. Statement Processing Patterns in EdgarTools

#### Line Item Ordering

**File**: `edgar/xbrl/xbrl.py:662-1003`

**Processing**: Depth-first traversal with order attribute sorting

```python
def _get_line_items_from_tree(node, facts_dict, level=0):
    for child_id in node.children:  # Forward iteration
        child_node = presentation_tree.get(child_id)
        # Recurse depth-first
```

**NOT backwards**: EdgarTools processes top-to-bottom

#### Section Identification

**File**: `edgar/xbrl/rendering.py:273-290`

**Method**: Hierarchy level-based

```python
if row.level == 0:
    # Top-level section (like "Total Assets")
elif row.level == 1:
    # Subsection (like "Current Assets")
```

**Limitation**: Doesn't use backwards processing to identify section boundaries from subtotals

#### Abstract Items (Section Headers)

**File**: `edgar/xbrl/presentation.py:211-219`

**Detection**:
```python
is_abstract = (
    elem.attrib.get('abstract') == 'true' or
    not elem.attrib.get('id')
)
```

**Usage**: Abstract items mark section headers, but not used for section-based mapping

#### Backwards Processing: Limited Use

**File**: `edgar/xbrl/rendering.py:1514-1613`

**Only for Statement of Equity**: Special handling with backwards date lookup

```python
# Backwards date lookup for beginning balance
beginning_period = match_date - timedelta(days=1)
```

**NOT used for**:
- Section boundary detection
- Ambiguous tag resolution
- Statement validation

---

### 6. What Could Be Learned from mpreiss9's Approach

#### 1. Reverse Mapping Structure (Optional Alternative)

**Current**: `StandardConcept → [CompanyConcepts]`
**Alternative**: `CompanyConcept → [StandardConcepts]`

**Advantages**:
- O(1) lookup instead of O(n × m) iteration
- Natural support for multi-mapping
- Explicit ambiguity handling

**Implementation Path**:
- Create `ReverseMap pingStore` class
- Load from reversed JSON or CSV
- Use for ambiguous tag resolution
- Keep current structure for non-ambiguous tags

#### 2. Section-Based Context Resolution

**What to Add**:
```python
# Section membership dictionary
BALANCE_SHEET_SECTIONS = {
    "Current Assets": {
        "Cash and Cash Equivalents",
        "Accounts Receivable",
        "Inventory",
        ...
    },
    "Current Liabilities": {
        "Accounts Payable, Current",
        "Accrued Liabilities",
        ...
    }
}

def resolve_ambiguous_tag(company_concept, context):
    """Resolve ambiguous tag using section membership."""
    # Get all possible standard concepts
    candidates = reverse_mapping.get(company_concept, [])

    if len(candidates) <= 1:
        return candidates[0] if candidates else None

    # Get section from context (parent concept or hierarchy)
    section = determine_section(context)

    # Find which candidate belongs in this section
    for std_concept in candidates:
        if std_concept in BALANCE_SHEET_SECTIONS.get(section, set()):
            return std_concept

    return None  # Ambiguous, needs manual resolution
```

#### 3. Enhanced Context Information

**Current Context** (Lines 714-719):
```python
context = {
    "statement_type": "BalanceSheet",
    "level": 1,
    "is_total": False
}
```

**Enhanced Context** (What mpreiss9 uses):
```python
context = {
    "statement_type": "BalanceSheet",
    "level": 1,
    "is_total": False,
    "calculation_parent": "us-gaap:AssetsCurrent",  # NEW
    "parent_standard_concept": "Total Current Assets",  # NEW
    "section": "Current Assets",  # NEW (derived from parent)
    "fact_value": 150000000,  # NEW (for sign-based disambiguation)
    "label": "Deferred Tax"  # NEW (for "Total" vs "Other" detection)
}
```

**Where to Get This**:
- `calculation_parent`: From XBRL calculation trees (already parsed)
- `parent_standard_concept`: Map parent concept to standard concept
- `section`: Derive from parent using backwards processing
- `fact_value`: From fact data
- `label`: Already available

#### 4. Backwards Section Detection

**Algorithm** (Adapted from mpreiss9):

```python
def assign_sections_backwards(line_items):
    """Assign sections working backwards from subtotals."""
    current_section = None

    # Process backwards (bottom to top)
    for item in reversed(line_items):
        # Check if this is a subtotal (section marker)
        if item.is_total and item.level == 1:
            # This is a section boundary
            current_section = item.standard_label

        # Assign section to this item
        item.section = current_section

    return line_items
```

**Integration Point**: `edgar/xbrl/rendering.py` line item processing

#### 5. Balance Sheet Validation

**Validation Engine** (Adapted from mpreiss9):

```python
def validate_balance_sheet(statement_data):
    """Validate balance sheet using mapped concepts."""

    # Get key totals
    total_assets = get_concept_value(statement_data, "Total Assets")
    current_assets = get_concept_value(statement_data, "Total Current Assets")
    noncurrent_assets = get_concept_value(statement_data, "Total Noncurrent Assets")
    total_liabilities = get_concept_value(statement_data, "Total Liabilities")
    total_equity = get_concept_value(statement_data, "Total Stockholders' Equity")

    # Validation 1: Fundamental equation
    if abs(total_assets - (total_liabilities + total_equity)) > 1.0:
        return ValidationError("Accounting equation violated")

    # Validation 2: Asset sections
    if noncurrent_assets:  # Some companies don't report separately
        if abs(total_assets - (current_assets + noncurrent_assets)) > 1.0:
            return ValidationError("Asset sections don't sum to total")

    # Validation 3: Detail rollup
    asset_details = sum_concept_values(statement_data, section="Assets", level > 0)
    if abs(total_assets - asset_details) > 1.0:
        return ValidationError("Asset details don't sum to total")

    return ValidationSuccess()
```

#### 6. Unmapped Tag Discovery

**Logging System** (Adapted from mpreiss9):

```python
class UnmappedTagLogger:
    """Log unmapped tags discovered during processing."""

    def __init__(self, output_path):
        self.output_path = output_path
        self.unmapped = []

    def log_unmapped(self, company_concept, label, context, suggested_mapping=None):
        """Log an unmapped tag with context."""
        self.unmapped.append({
            'company_concept': company_concept,
            'label': label,
            'statement_type': context.get('statement_type'),
            'parent_concept': context.get('calculation_parent'),
            'section': context.get('section'),
            'suggested_mapping': suggested_mapping or infer_mapping(company_concept, label),
            'confidence': calculate_confidence(suggested_mapping),
            'cik': context.get('cik'),
            'notes': ''  # For manual review
        })

    def save_to_csv(self):
        """Save unmapped tags to CSV for Excel editing."""
        df = pd.DataFrame(self.unmapped)
        df.to_csv(self.output_path, index=False)
```

**Integration**: Call during statement processing when mapping returns None

#### 7. CSV Workflow Support

**Already Partially Implemented**: `edgar/xbrl/standardization/utils.py`

**Enhancements**:
- Support reverse mapping CSV format
- Import multi-mapping from CSV (same company_concept, multiple rows)
- Export unmapped tag logs
- Duplicate detection across all mappings

---

### 7. Complementary Not Contradictory

**Important Realization**: The two approaches are not mutually exclusive.

#### EdgarTools Strengths

✅ Simple, elegant API
✅ Priority-based company-specific overrides
✅ Works well for non-ambiguous tags (majority of cases)
✅ Good performance with caching
✅ Modular company mapping files

#### mpreiss9 Strengths

✅ Handles ambiguous tags systematically
✅ Validation-driven mapping correction
✅ Section-based context resolution
✅ Excel-friendly CSV workflow
✅ Explicit multi-mapping support

#### Hybrid Approach

**Recommendation**: Use EdgarTools as foundation, add mpreiss9's enhancements for edge cases

**Architecture Designed** (2025-11-22): See 7-stage pipeline in `xbrl-standardization-pipeline.md`

The hybrid approach is now documented as:
- **Stage 3**: Base Standardization (current EdgarTools - Reason 1: standardization)
- **Stage 4**: Granularity Transformation (mpreiss9's insight - Reason 2: consolidation)
- **Stage 5**: Context-Aware Resolution (mpreiss9's method - ambiguous tags)

```python
# Pipeline integration (from architecture)
def get_standard_concept(self, company_concept: str, context: Dict = None) -> Optional[str]:
    """Enhanced mapping with optional context-aware disambiguation."""

    # Step 1: Check if this is a known ambiguous tag
    if company_concept in AMBIGUOUS_TAGS:
        # Use context-aware resolution (Stage 5 - mpreiss9's method)
        return self._resolve_ambiguous_tag(company_concept, context)

    # Step 2: Standard priority-based resolution (Stage 3 - EdgarTools current)
    return self._priority_based_resolution(company_concept)
```

**Benefits**:
- Maintain simplicity for 95% of tags
- Handle edge cases systematically
- Validation-driven improvement
- Best of both approaches
- **Clear architectural boundaries** (EdgarTools = infrastructure, users = config)

---

## Architecture Documentation

### EdgarTools Standardization Flow

```
Filing → XBRL Parser → Facts → Statement Builder
                                      ↓
                              ConceptMapper (standardization)
                                      ↓
                              StandardConcept (enum)
                                      ↓
                              Standardized Statement
```

**Current Mapping Flow**:
```
CompanyConcept → MappingStore.get_standard_concept()
                      ↓
              Iterate through all standard concepts
                      ↓
              Check if CompanyConcept in concept set
                      ↓
              Apply priority-based resolution
                      ↓
              Return StandardConcept (or None)
```

### mpreiss9's Processing Flow

```
Filing → XBRL Parser → Facts → Raw Statement
                                      ↓
                          1. Assign ALL possible standard tags
                                      ↓
                          2. Process backwards to assign sections
                                      ↓
                          3. Disambiguate using section membership
                                      ↓
                          4. Validate balance sheet equation
                                      ↓
                          5. Log unmapped tags if validation fails
                                      ↓
                          Standardized Statement
```

**mpreiss9's Mapping Flow**:
```
CompanyConcept → ReverseMapping[CompanyConcept]
                      ↓
              Get [StandardConcept1, StandardConcept2, ...]
                      ↓
              Get section from context (backwards processing)
                      ↓
              Filter by section membership
                      ↓
              Return contextually appropriate StandardConcept
```

---

## Key Data Flows

### EdgarTools: Statement Standardization

**File**: `edgar/xbrl/standardization/core.py:684-757`

```python
# Input: statement_data (list of dicts)
[
    {
        "concept": "tsla:AutomotiveRevenue",
        "label": "Automotive Sales",
        "value": 50000000,
        "statement_type": "IncomeStatement",
        "level": 1
    },
    ...
]

# Build context
context = {
    "statement_type": "IncomeStatement",
    "level": 1,
    "is_total": False
}

# Map concept → standard concept
standard_label = mapper.map_concept("tsla:AutomotiveRevenue", "Automotive Sales", context)
# Returns: "Automotive Revenue" (from tsla_mappings.json, priority 2)

# Output: Standardized statement
[
    {
        "concept": "tsla:AutomotiveRevenue",
        "label": "Automotive Revenue",  # ← Standardized
        "original_label": "Automotive Sales",
        "value": 50000000,
        ...
    }
]
```

### mpreiss9: Section-Based Disambiguation

```python
# Input: Item with ambiguous tag
item = {
    "concept": "us-gaap:DeferredTaxAssetsLiabilitiesNet",
    "label": "Deferred Tax",
    "value": 150000000,
    "parent": "us-gaap:AssetsCurrent"
}

# Step 1: Get all possible mappings
candidates = reverse_mapping["us-gaap:DeferredTaxAssetsLiabilitiesNet"]
# Returns: ["Deferred Tax Assets", "Deferred Tax Liabilities"]

# Step 2: Determine section (backwards processing finds parent = "Total Current Assets")
section = "Current Assets"

# Step 3: Check section membership
section_concepts = BALANCE_SHEET_SECTIONS["Current Assets"]
# Returns: {"Cash", "Accounts Receivable", "Deferred Tax Assets", ...}

# Step 4: Find matching candidate
for candidate in candidates:
    if candidate in section_concepts:
        return candidate
# Returns: "Deferred Tax Assets"

# Output: Disambiguated item
item["label"] = "Deferred Tax Assets"  # ← Contextually correct
```

---

## Dependencies

### EdgarTools Standardization

**External**:
- Python 3.9+
- `json` (stdlib)
- `difflib.SequenceMatcher` (for inference)

**Internal**:
- `edgar.xbrl.xbrl` - XBRL parser provides concepts and labels
- `edgar.xbrl.statements` - Statement builder calls standardization
- `edgar.xbrl.rendering` - Rendering uses standardized labels

### mpreiss9's Approach (Conceptual)

**Required**:
- Reverse mapping data structure
- Section membership dictionaries
- Backwards processing algorithm
- Balance sheet validation engine

**Integration Points**:
- XBRL calculation trees (for parent concepts)
- Fact values (for sign-based disambiguation)
- Presentation trees (for backwards processing)

---

## Test Coverage

### EdgarTools Standardization Tests

**File**: `tests/test_xbrl_standardization.py`

**Coverage**:
- ✅ Basic concept mapping
- ✅ Priority-based resolution
- ✅ Company-specific mappings
- ✅ Context parameter passing (but not usage)
- ❌ Context-aware disambiguation
- ❌ Ambiguous tag handling
- ❌ Balance sheet validation
- ❌ Section-based resolution

### mpreiss9's Approach (No Tests in EdgarTools)

**Would Need**:
- Section assignment tests
- Backwards processing tests
- Ambiguous tag resolution tests (200+ tags)
- Balance sheet validation tests
- Special case handling (Noncurrent Liabilities total vs line item)

---

## Related Documentation

### EdgarTools Documentation

- **Comprehensive Guide**: `docs/advanced/customizing-standardization.md` (2,408 lines)
  - Created Nov 19, 2025 in response to Issue #494
  - Covers current system, limitations, future enhancements
  - Lines 872-891: Documents **planned** context-based resolution (not implemented)

- **CSV Analysis**: `docs-internal/research/xbrl-mapping-analysis-mpreiss9.md` (NEW - 2025-11-21)
  - Detailed analysis of mpreiss9's production CSV files
  - 6,177 mappings: 2,343 GAAP + 3,834 custom (390 companies)
  - 215 ambiguous tags documented with resolution patterns
  - Files in `data/xbrl-mappings/` (not committed)

- **Package README**: `edgar/xbrl/standardization/README.md`
  - Basic usage examples
  - Utility functions for CSV export/import

- **GitHub Issue**: #494 - "Create documentation on how to customize standardization tagging"
  - User feedback and feature requests
  - mpreiss9's detailed methodology (comment 2025-11-19)
  - CSV files shared (comment 2025-11-21)

### Internal Documentation

- **XBRL Package Guide**: `edgar/xbrl/CLAUDE.md`
  - Data availability checking methods
  - Period selection logic
  - Query interface documentation

---

## Open Questions for Planning Phase

### 1. Implementation Strategy

**Question**: Should we enhance the existing forward-mapping system or create a separate reverse-mapping system for ambiguous tags?

**Options**:
- **A**: Enhance existing `MappingStore` to use context (requires threading calculation parent info)
- **B**: Create `ReverseMappingStore` for ambiguous tags only (hybrid approach)
- **C**: Fully replace with reverse mapping (breaking change, not recommended)

### 2. Backwards Processing

**Question**: Where should section assignment via backwards processing happen?

**Options**:
- **A**: In statement builder before standardization
- **B**: During standardization as part of context enrichment
- **C**: As a separate validation/enhancement step

### 3. Balance Sheet Validation

**Question**: Should validation be:

**Options**:
- **A**: Always-on production validation
- **B**: Opt-in validation mode
- **C**: Development/testing tool only

### 4. Unmapped Tag Logging

**Question**: How should unmapped tags be surfaced to users?

**Options**:
- **A**: Silent logging to file
- **B**: Warning messages during processing
- **C**: Validation report API
- **D**: All of the above with configurable levels

### 5. CSV Workflow

**Question**: Should EdgarTools support:

**Options**:
- **A**: Current JSON-only format (status quo)
- **B**: Native CSV support (as documented in future enhancements)
- **C**: Both JSON and CSV with auto-detection
- **D**: CSV as primary, JSON as export format

### 6. Scope of Ambiguous Tag Support

**Question**: Should we handle:

**Options**:
- **A**: Only the 12 asset/liability ambiguous tags (smallest scope)
- **B**: The 200+ ambiguous tags identified by mpreiss9 (comprehensive)
- **C**: Provide framework for users to define their own ambiguous tags

### 7. Backwards Compatibility

**Question**: How to handle breaking changes?

**Options**:
- **A**: Add as optional feature, preserve existing behavior as default
- **B**: Add with deprecation warnings, migrate in v5.0.0
- **C**: Feature flag for experimental context-aware mode

---

## Summary

### What We Learned

1. **EdgarTools has the infrastructure but not the implementation**
   - Context parameter exists throughout the code
   - Completely ignored during actual mapping
   - Priority system works but doesn't solve ambiguity

2. **mpreiss9's approach successfully handles 200+ ambiguous tags**
   - Reverse mapping enables multi-mapping
   - Section-based resolution using backwards processing
   - Validation-driven mapping improvement

3. **The approaches are complementary**
   - EdgarTools: Simple, performant for standard cases
   - mpreiss9: Robust, handles edge cases systematically
   - Hybrid approach leverages strengths of both

4. **Key insights from mpreiss9's method**:
   - Backwards processing identifies section boundaries
   - Section membership resolves ambiguity
   - Validation triggers mapping corrections
   - CSV workflow enables Excel-based management
   - Logging unmapped tags accelerates coverage

5. **Implementation is feasible**:
   - Can enhance existing system without breaking changes
   - Most required data already available in XBRL parser
   - Would benefit 95% of use cases (validation) while solving 5% edge cases (ambiguity)

### Recommendations for Planning Phase

1. **Start with validation**: Add balance sheet equation checking (high value, low risk)
2. **Enhance context**: Thread calculation parent through to standardization
3. **Create section dictionaries**: Document standard concepts by section
4. **Implement backwards processing**: For section assignment
5. **Handle ambiguous tags**: Start with 12 asset/liability ambiguous tags, expand to 200+
6. **Add unmapped tag logging**: CSV-based workflow for continuous improvement
7. **Preserve backwards compatibility**: Make all enhancements opt-in

---

## File References

### EdgarTools Implementation

- **Core Standardization**: `edgar/xbrl/standardization/core.py`
  - Lines 128-462: `MappingStore` class
  - Lines 408-449: `get_standard_concept()` - Context ignored
  - Lines 493-518: `ConceptMapper.map_concept()` - Context only for caching
  - Lines 684-757: `standardize_statement()` - Builds context

- **Mappings**: `edgar/xbrl/standardization/concept_mappings.json`
- **Company Mappings**: `edgar/xbrl/standardization/company_mappings/*.json`
  - `tsla_mappings.json` - Tesla example
  - `msft_mappings.json` - Microsoft example

- **Utilities**: `edgar/xbrl/standardization/utils.py`
  - CSV export/import functions
  - Validation helpers

- **Validation**:
  - `edgar/xbrl/parsers/concepts.py:144-380` - Balance types
  - `edgar/xbrl/statements.py:72-87` - Required concepts
  - `edgar/xbrl/period_data_check.py:111-237` - Period data quality

- **Statement Processing**:
  - `edgar/xbrl/xbrl.py:662-1003` - Line item traversal
  - `edgar/xbrl/rendering.py:273-290` - Section identification
  - `edgar/xbrl/rendering.py:1514-1613` - Backwards processing (equity only)

### Issue #494

- **GitHub Issue**: https://github.com/dgunning/edgartools/issues/494
- **Last Comment**: @mpreiss9's detailed methodology explanation (2025-11-19)
- **200+ Ambiguous Tags**: Listed in comment

### Documentation

- **Comprehensive Guide**: `docs/advanced/customizing-standardization.md`
  - Lines 577-851: Ambiguous tag documentation
  - Lines 872-891: Planned context-based resolution

- **XBRL Guide**: `edgar/xbrl/CLAUDE.md`

### Tests

- **Standardization Tests**: `tests/test_xbrl_standardization.py`
- **Balance Tests**: `tests/test_xbrl_balance_weight.py`
- **Concept Tests**: `tests/test_standardized_concepts.py:115-127` - Accounting equation

---

**Research Complete**: 2025-11-20
**Architecture Complete**: 2025-11-22
**Status**: Ready for Implementation (when stakeholders approve)
**Next Step**: See `xbrl-standardization-pipeline.md` for complete design
