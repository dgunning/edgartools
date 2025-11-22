# XBRL Standardization Pipeline Architecture

**Date**: 2025-11-22
**Status**: Proposed Architecture Design
**Related**: GitHub Issue #494, mpreiss9's methodology
**Context**: Flexible granularity enhancement for XBRL standardization

## Purpose

This document defines the architecture for EdgarTools' XBRL processing pipeline with flexible standardization and granularity control. It establishes clear boundaries between EdgarTools' responsibilities and user customization points.

---

## Design Principles

1. **Clean boundaries**: EdgarTools owns parsing/building, users own business logic
2. **Pipeline composition**: Transformations are composable and chainable
3. **Minimal coupling**: EdgarTools doesn't know about user workflows
4. **Opt-in complexity**: Simple by default, powerful when needed
5. **Data > Code**: Configuration-driven, not code-driven
6. **Immutability**: Transformations return new objects, never mutate
7. **Transparency**: Original data always preserved and accessible

---

## The Pipeline (7 Stages)

```
┌─────────────────────────────────────────────────────────────────┐
│ Stage 1: XBRL PARSING (EdgarTools Core)                        │
│ Input:  XBRL XML files (instance, linkbases)                   │
│ Output: Parsed facts, trees, contexts                          │
│ Owner:  EdgarTools                                              │
│ Files:  edgar/xbrl/parsers/*.py, edgar/xbrl/xbrl.py           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Stage 2: STATEMENT BUILDING (EdgarTools Core)                  │
│ Input:  Parsed XBRL + statement role/type                      │
│ Output: Raw line items [concept, label, values, metadata]      │
│ Owner:  EdgarTools                                              │
│ Files:  edgar/xbrl/xbrl.py (get_statement method)             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Stage 3: BASE STANDARDIZATION (EdgarTools + User Config)       │
│ Input:  Raw line items                                          │
│ Process: Apply concept → standard label mappings               │
│ Output: Base standardized items (preserves originals)          │
│ Owner:  EdgarTools (engine) + User (mappings)                  │
│ Files:  edgar/xbrl/standardization/core.py                    │
│ Plugin: company_mappings/*.json (EXISTING mechanism)           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Stage 4: GRANULARITY TRANSFORMATION (NEW - User Controlled)    │
│ Input:  Base standardized items                                │
│ Process: Apply granularity profile (detailed/standard/summary) │
│ Output: Transformed items at chosen granularity                │
│ Owner:  User (EdgarTools provides profiles + engine)           │
│ Plugin: profiles/*.json (NEW)                                  │
│ Status: PROPOSED - To be implemented                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Stage 5: CONTEXT-AWARE RESOLUTION (NEW - Optional)             │
│ Input:  Granular items (may have ambiguous tags)               │
│ Process: Resolve using section/parent context                  │
│ Output: Disambiguated items                                    │
│ Owner:  EdgarTools (algorithm) + User (ambiguity rules)        │
│ Plugin: ambiguous_tags.json (NEW)                              │
│ Status: PROPOSED - To be implemented                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Stage 6: PERIOD SELECTION (EdgarTools Core)                    │
│ Input:  Transformed statement                                  │
│ Output: Filtered to display periods                            │
│ Owner:  EdgarTools                                              │
│ Files:  edgar/xbrl/periods.py                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Stage 7: RENDERING (EdgarTools Core)                           │
│ Input:  Final statement + periods                              │
│ Output: RenderedStatement (Rich Table)                         │
│ Owner:  EdgarTools                                              │
│ Files:  edgar/xbrl/rendering.py                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Stage Details

### Stage 1: XBRL Parsing

**Purpose**: Convert XBRL XML into structured Python objects

**Input**: 6 XBRL documents
- Instance document (facts and contexts)
- Schema (element definitions)
- Presentation linkbase (hierarchy)
- Calculation linkbase (arithmetic relationships)
- Definition linkbase (dimensional data)
- Label linkbase (human-readable labels)

**Output**:
```python
{
    'facts': Dict[fact_key, Fact],
    'contexts': Dict[context_id, Context],
    'element_catalog': Dict[id, Element],
    'presentation_trees': Dict[role, PresentationTree],
    'calculation_trees': Dict[role, CalculationTree],
    'reporting_periods': List[Period]
}
```

**Complexity**: High (XBRL is complex)
**User Customization**: None (parsing is deterministic)

---

### Stage 2: Statement Building

**Purpose**: Extract statement from XBRL using presentation tree

**Input**: Parsed XBRL + statement identifier

**Process**:
1. Resolve statement role URI
2. Traverse presentation tree depth-first
3. Match facts to concepts using contexts
4. Build line item list with hierarchy

**Output**:
```python
[
    {
        'concept': 'us-gaap:Revenue',
        'label': 'Total Revenue',
        'values': {'FY2023': 25500000000, 'FY2022': 23400000000},
        'metadata': {
            'level': 1,
            'is_abstract': False,
            'parent': 'us-gaap:Revenues',
            'section': None,  # Determined later
            'balance_type': None,
            'calculation_weight': 1.0
        }
    },
    ...
]
```

**Complexity**: Medium (tree traversal + context matching)
**User Customization**: Minimal (can filter periods)

---

### Stage 3: Base Standardization

**Purpose**: Normalize concept labels for consistency

**Input**: Raw line items from Stage 2

**Process**:
1. ConceptMapper checks cache
2. Looks up company-specific mappings (if available)
3. Falls back to core mappings
4. Priority-based resolution (company > core)
5. Preserves original labels

**Output**: Line items with `standard_label` added
```python
{
    'concept': 'us-gaap:Revenue',
    'label': 'Revenue',  # ← Standardized
    'original_label': 'Total Revenue',  # ← Original preserved
    ...
}
```

**Complexity**: Low (dictionary lookup)
**User Customization**: High (via company_mappings/*.json)

**Critical Insight**: This is "Reason 1" from mpreiss9 - same facts, different names

---

### Stage 4: Granularity Transformation (NEW)

**Purpose**: Apply user's analytical granularity preference

**Input**: Base standardized items

**Process**:
1. Load granularity profile (detailed/standard/summarized)
2. Apply transformation rules:
   - **Rollup**: Combine multiple items into summary
   - **Split**: Break single item into components
   - **Rename**: Change granularity level
3. Return transformed items

**Output**: Items at chosen granularity
```python
# BEFORE (base standardization)
[
    {'label': 'Tax Liabilities', 'value': 50M},
    {'label': 'Retirement Liabilities', 'value': 30M},
    {'label': 'Other Non-Operating Liabilities', 'value': 20M}
]

# AFTER (summarized profile)
[
    {'label': 'Non-Operating Liabilities', 'value': 100M,
     'original_items': ['Tax Liabilities', 'Retirement Liabilities', 'Other...']}
]
```

**Complexity**: Medium (rule application + validation)
**User Customization**: Very High (define custom profiles)

**Critical Insight**: This is "Reason 2" from mpreiss9 - different granularity for different needs

---

### Stage 5: Context-Aware Resolution (NEW)

**Purpose**: Resolve ambiguous tags using statement context

**Input**: Items with potential ambiguities

**Process**:
1. Identify ambiguous tags (from registry)
2. Determine context (section, parent concept, sign)
3. Apply resolution rules
4. Select appropriate mapping
5. Log unresolved ambiguities

**Example**:
```python
# Ambiguous: DeferredTaxAssetsLiabilitiesNet
# Context: parent='AssetsCurrent', section='Current Assets'
# Resolution: → 'Deferred Tax Assets' (not 'Deferred Tax Liabilities')
```

**Complexity**: High (context detection + rule application)
**User Customization**: Medium (define ambiguity rules)

**Critical Insight**: Handles mpreiss9's 215 ambiguous tags

---

### Stage 6: Period Selection

**Purpose**: Filter statement to relevant time periods

**Input**: Transformed statement

**Process**:
1. Detect fiscal year/quarter from entity info
2. Select appropriate periods (e.g., 3 annual for FY)
3. Sort by date (newest first)
4. Apply user overrides if specified

**Output**: Same statement with narrowed period list

**Complexity**: Low (date filtering)
**User Customization**: Low (can specify period_view)

---

### Stage 7: Rendering

**Purpose**: Format statement for display

**Input**: Final statement + period list

**Process**:
1. Determine scale (millions, thousands)
2. Apply presentation transforms (sign adjustments)
3. Format values with proper decimals
4. Create Rich Table with styling
5. Add comparison indicators

**Output**: RenderedStatement (Rich Table wrapper)

**Complexity**: Medium (formatting + styling)
**User Customization**: Low (color schemes, formats)

---

## Data Contract

Every stage exchanges data in a standard format to ensure clean boundaries:

```python
# Line Item Structure (grows through pipeline)
{
    # From Stage 2: Statement Building
    'concept': 'us-gaap:Revenue',           # XBRL concept name
    'label': 'Total Revenue',                # Original label
    'values': {                              # Period → value mapping
        'FY2023': 25500000000,
        'FY2022': 23400000000
    },
    'metadata': {
        'level': 1,                          # Hierarchy depth
        'is_abstract': False,
        'parent': 'us-gaap:Revenues',       # Parent concept
        'balance_type': None,               # Debit/credit
        'calculation_weight': 1.0
    },

    # From Stage 3: Base Standardization
    'standard_label': 'Revenue',             # Standardized label
    'original_label': 'Total Revenue',       # Original preserved

    # From Stage 4: Granularity Transformation (if applied)
    'granular_label': 'Product Revenue',     # After granularity profile
    'granularity_level': 'detailed',         # Which profile was applied
    'rollup_source': None,                   # If this is a rollup, what items?

    # From Stage 5: Context-Aware Resolution (if applied)
    'section': 'Revenue',                    # Detected section
    'resolution_applied': False,             # Was ambiguity resolved?
    'ambiguity_candidates': None             # If ambiguous, what were options?
}
```

**Guarantee**: Every stage preserves this contract. Transformations add fields but never remove them.

---

## Boundary: EdgarTools vs. User

### EdgarTools Responsibilities

**What we maintain**:
- ✅ Parse XBRL correctly (Stage 1)
- ✅ Build accurate statements from XBRL (Stage 2)
- ✅ Apply mappings from configuration files (Stage 3, 4, 5)
- ✅ Render output beautifully (Stage 7)
- ✅ Provide transformation engines (ConceptMapper, ProfileTransformer)
- ✅ Provide default profiles (detailed, standard, summarized)
- ✅ Validate profile structure and references
- ✅ Handle errors gracefully with clear messages

**What we DON'T do**:
- ❌ Execute user Python code in the pipeline
- ❌ Try to infer user intent
- ❌ Build a general-purpose transformation language
- ❌ Validate user business logic
- ❌ Store state about user workflows

### User Responsibilities

**What users control**:
- Define custom granularity profiles (JSON/CSV)
- Choose which profile to use
- Define company-specific mappings
- Define ambiguous tag resolution rules
- Handle their own business logic **OUTSIDE** the pipeline

**Critical**: EdgarTools reads user config files (JSON/CSV) but doesn't execute user code. Only data, not code.

---

## User Customization: 3 Levels

### Level 1: Choose a Profile (90% of users)

**Simplest approach** - just pick a granularity level:

```python
# Default (balanced)
statement = xbrl.statements.balance_sheet()

# Maximum detail
statement = xbrl.statements.balance_sheet(granularity='detailed')

# High-level summary
statement = xbrl.statements.balance_sheet(granularity='summarized')
```

**No config needed** - EdgarTools ships with default profiles:
- `detailed`: Maximum granularity (like mpreiss9's mappings)
- `standard`: Balanced level (current EdgarTools behavior)
- `summarized`: High-level rollups for quick analysis

---

### Level 2: Custom Profile File (Advanced users like mpreiss9)

**More control** - provide your own mapping file:

```python
from edgar.xbrl.standardization import Profile

# Load custom profile
profile = Profile.from_csv('my_mappings.csv')
statement = xbrl.statements.balance_sheet().with_profile(profile)

# Or chain transformations
statement = (xbrl.statements.balance_sheet()
    .with_granularity('detailed')      # First: max detail
    .with_profile('my_rollups.json'))  # Then: custom rollups
```

**User provides**: CSV/JSON file with transformation rules
**EdgarTools applies**: The rules to transform the statement

---

### Level 3: Programmatic Transformation (Power users)

**Full control** - user transforms data outside EdgarTools:

```python
# Get statement data
statement = xbrl.statements.balance_sheet()
df = statement.to_dataframe()

# User's own business logic HERE
df_transformed = my_custom_analytics(df)
df_summarized = my_custom_rollups(df_transformed)
df_final = my_special_calculations(df_summarized)

# Convert back if needed (optional)
custom_statement = Statement.from_dataframe(df_final)
```

**Critical**: Level 3 keeps EdgarTools out of user workflows. We give them data, they give us back data (if they want).

---

## Granularity Profiles (Stage 4)

### Profile Format

Profiles are **pure data** (JSON/CSV), not code:

```json
{
  "profile_metadata": {
    "name": "detailed",
    "description": "Maximum granularity for detailed analysis",
    "version": "1.0",
    "based_on": "standard"
  },

  "transformations": {
    "rollup_rules": {
      "NonOperatingLiabilities": {
        "combine": [
          "TaxLiabilities",
          "RetirementLiabilities",
          "OtherNonOperatingLiabilities"
        ],
        "operation": "sum"
      }
    },

    "split_rules": {
      "Revenue": {
        "split_into": {
          "ProductRevenue": {"pattern": "*Product*"},
          "ServiceRevenue": {"pattern": "*Service*"}
        }
      }
    },

    "rename_rules": {
      "PP&E": "PropertyPlantAndEquipment"
    }
  }
}
```

**EdgarTools interprets the rules**, users just provide the data.

---

### Default Profiles

**detailed.json** (like mpreiss9's mappings):
```json
{
  "name": "detailed",
  "transformations": {
    "split_rules": {
      "NonOperatingLiabilities": {
        "TaxLiabilities": ["*Tax*Liab*"],
        "RetirementLiabilities": ["*Pension*", "*Retirement*"],
        "OtherNonOperatingLiabilities": ["*"]
      }
    }
  }
}
```

**summarized.json** (rollups):
```json
{
  "name": "summarized",
  "transformations": {
    "rollup_rules": {
      "NonOperatingLiabilities": {
        "combine": [
          "TaxLiabilities",
          "RetirementLiabilities",
          "OtherNonOperatingLiabilities"
        ]
      }
    }
  }
}
```

**standard.json** (current behavior - no transformation):
```json
{
  "name": "standard",
  "transformations": {}
}
```

---

## Composable Transformations

Think of transformations as a pipeline you can compose:

```python
# Each transformation returns a NEW statement (immutable)
statement = xbrl.statements.balance_sheet()

# Apply granularity
detailed = statement.with_granularity('detailed')
summarized = statement.with_granularity('summarized')

# Chain transformations
custom = (statement
    .with_granularity('detailed')        # First: max detail
    .with_profile('my_rollups.json')     # Then: custom rollups
    .filter_sections(['Assets']))        # Then: filter to assets only

# Original statement unchanged
print(statement)    # Still original
print(custom)       # Transformed version
```

**Key**: Each transformation returns a new object. Originals never mutate. This keeps the pipeline clean and debuggable.

---

## Implementation Phases

### Phase 1: Profile Infrastructure (v4.31.0)

**Goal**: Add profile loading and transformation engine

**Work**:
1. Create `edgar/xbrl/standardization/profiles/` directory
2. Ship default profiles: `detailed.json`, `standard.json`, `summarized.json`
3. Implement `Profile` class (loads JSON/CSV, validates)
4. Implement `ProfileTransformer` (applies rollup/split rules)
5. Add `.with_granularity()` method to Statement class

**User-facing**:
```python
# Just works with defaults
statement = xbrl.statements.balance_sheet(granularity='detailed')
```

**Effort**: 2-3 weeks
**Risk**: Low (self-contained)

---

### Phase 2: Custom Profiles (v5.0.0)

**Goal**: Let users load custom profiles

**Work**:
1. Add `Profile.from_csv()` and `Profile.from_json()` methods
2. Add profile validation (check for cycles, missing refs)
3. Document profile format in user guide
4. Provide mpreiss9's mappings as example
5. Add `.with_profile()` method

**User-facing**:
```python
# Load custom profile
profile = Profile.from_csv('my_rollups.csv')
statement = xbrl.statements.balance_sheet().with_profile(profile)
```

**Effort**: 1-2 weeks
**Risk**: Low (extension of Phase 1)

---

### Phase 3: Hierarchical Profiles (v5.1.0)

**Goal**: Support drill-down/roll-up navigation

**Work**:
1. Add parent-child relationships to profile format
2. Implement `.drill_down(label)` and `.roll_up(label)` methods
3. Add profile composition (combine multiple profiles)
4. Document hierarchical navigation

**User-facing**:
```python
# Navigate hierarchy
summary = statement.with_granularity('summarized')
print(summary)  # Shows "NonOperatingLiabilities: $100M"

# Drill down to see components
detailed = summary.drill_down('NonOperatingLiabilities')
print(detailed)  # Shows Tax ($50M), Retirement ($30M), Other ($20M)

# Roll back up
summary_again = detailed.roll_up('NonOperatingLiabilities')
```

**Effort**: 2-3 weeks
**Risk**: Medium (more complex API)

---

## Success Criteria

### Maintainability

- [ ] Profile engine is <500 lines of code
- [ ] Default profiles ship with EdgarTools
- [ ] Users never need to modify EdgarTools code
- [ ] Profile format is well-documented
- [ ] Validation catches errors early with clear messages

### Flexibility

- [ ] Users can define any granularity via JSON/CSV
- [ ] Profiles compose cleanly (can chain transformations)
- [ ] Can always fall back to raw XBRL (no data loss)
- [ ] Support both rollup and split operations
- [ ] Custom profiles work exactly like default profiles

### Robustness

- [ ] Profile validation catches structural errors
- [ ] Circular references detected and rejected
- [ ] Bad profiles fail gracefully with clear errors
- [ ] Original data always preserved through pipeline
- [ ] All transformations are reversible

### Accuracy

- [ ] Transformations are deterministic (same input → same output)
- [ ] No data loss through pipeline
- [ ] All intermediate results accessible for debugging
- [ ] Rollup calculations mathematically correct
- [ ] Split operations preserve totals

---

## Related Documents

### Research & Analysis
- **CSV Analysis**: `docs-internal/research/xbrl-mapping-analysis-mpreiss9.md`
  - mpreiss9's 6,177 production mappings analyzed
  - "Detailed" profile example
  - Two reasons for mapping (standardization + consolidation)

- **Comparison Research**: `docs-internal/research/issues/issue-494-standardization-comparison.md`
  - EdgarTools vs mpreiss9 approach comparison
  - Hybrid architecture recommendation
  - Context-aware resolution analysis

### Planning & Roadmap
- **Enhancement Roadmap**: `docs-internal/planning/future-enhancements/context-aware-standardization.md`
  - Full implementation roadmap (Phases 1-6)
  - Timeline and effort estimates
  - Stage 4 (Granularity) and Stage 5 (Context-Aware) details

### Implementation
- **Issue Tracking**: GitHub Issue #494
- **Test Data**: `data/xbrl-mappings/*.csv` (mpreiss9's production data)

---

## Conclusion

This architecture provides:

1. **Clear separation** between EdgarTools (infrastructure) and users (business logic)
2. **Flexible granularity** through declarative profiles
3. **Composable transformations** that chain cleanly
4. **Robust boundaries** that prevent coupling to user workflows
5. **Simple defaults** with power features for advanced users

**Key Insight**: EdgarTools provides the **transformation engine**, users provide the **transformation rules** (as data, not code).

This keeps EdgarTools focused on what it does best (XBRL parsing and statement building) while giving users full control over analytical perspective through simple, declarative configuration.

---

**Document Status**: Proposed Architecture
**Last Updated**: 2025-11-22
**Author**: EdgarTools Development Team
**Based on**: mpreiss9's methodology and community feedback
