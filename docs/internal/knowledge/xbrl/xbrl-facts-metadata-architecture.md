# XBRL Facts and Metadata Architecture

**Date**: 2025-01-20
**Context**: Issue #463 - Understanding the XBRL data model and metadata enrichment
**Purpose**: Document how XBRL facts are structured, where metadata comes from, and how it flows through the system

---

## The Problem We Discovered

During Issue #463 implementation, we encountered a bug when trying to add `preferred_sign` to DataFrames:

```python
# WRONG: This doesn't work!
facts_df = xbrl.facts.query().by_concept(concept, exact=True).limit(1).to_dataframe()
fact = facts_df.iloc[0]
preferred_sign = fact.get('preferred_sign')  # ❌ Returns None!
```

**Why?** Because `preferred_sign` is **NOT an attribute of Fact objects**. It comes from the presentation linkbase and is stored in statement line items, not in facts.

This led us to understand the complete XBRL data model and metadata enrichment process.

---

## The XBRL Data Model: Three Separate Structures

XBRL data is organized into **three distinct structures**, each containing different information:

### 1. **Instance Document** (Raw Facts)
**Location**: `{filing}_htm.xml` (instance document)
**Contains**: Numeric values, contexts, units
**Parsed into**: `xbrl._facts` dictionary

```python
{
    'context_id_123': {
        'fact': Fact(
            concept='us-gaap:PaymentsOfDividends',
            value='12769000000',
            context_ref='context_id_123',
            unit_ref='usd',
            decimals='-6'
        ),
        'dimension_info': {...},
        'dimension_key': None
    }
}
```

**What's stored here**:
- ✅ Concept name (e.g., `us-gaap:PaymentsOfDividends`)
- ✅ Numeric value (e.g., `12769000000`)
- ✅ Context reference (period, entity, dimensions)
- ✅ Unit (e.g., `USD`, `shares`)
- ✅ Decimals/precision

**What's NOT stored here**:
- ❌ Balance attribute (debit/credit)
- ❌ Calculation weight
- ❌ Preferred label/sign
- ❌ Human-readable labels

---

### 2. **Schema & Calculation** (Element Definitions)
**Location**: `{filing}-{date}.xsd` (schema), `{filing}-{date}_cal.xml` (calculation linkbase)
**Contains**: Element definitions, balance types, calculation relationships
**Parsed into**: `xbrl.element_catalog`, `xbrl.calculation_trees`

```python
# Element Catalog
{
    'us-gaap_PaymentsOfDividends': Element(
        name='us-gaap:PaymentsOfDividends',
        type='xbrli:monetaryItemType',
        balance='credit',  # ← Balance attribute lives here!
        period_type='duration',
        substitution_group='xbrli:item'
    )
}

# Calculation Trees
{
    'http://www.apple.com/role/CashFlow': CalculationTree(
        nodes={
            'us-gaap_PaymentsOfDividends': CalculationNode(
                weight=-1.0  # ← Calculation weight lives here!
            )
        }
    )
}
```

**What's stored here**:
- ✅ Balance attribute (debit/credit)
- ✅ Calculation weight (+1.0, -1.0)
- ✅ Element type (monetary, shares, pure)
- ✅ Period type (instant, duration)

**What's NOT stored here**:
- ❌ Actual fact values
- ❌ Preferred labels
- ❌ Display order

---

### 3. **Presentation Linkbase** (Display Instructions)
**Location**: `{filing}-{date}_pre.xml` (presentation linkbase)
**Contains**: Display order, hierarchical structure, preferred labels
**Parsed into**: `xbrl.presentation_trees`

```python
{
    'http://www.apple.com/role/CashFlow': PresentationTree(
        nodes={
            'us-gaap_PaymentsOfDividends': PresentationNode(
                element_name='us-gaap:PaymentsOfDividends',
                preferred_label='http://www.xbrl.org/2003/role/negatedLabel',  # ← Lives here!
                order=2.0,
                parent=...,
                children=[]
            )
        }
    )
}
```

**What's stored here**:
- ✅ Preferred label (negatedLabel, terseLabel, etc.)
- ✅ Display order
- ✅ Hierarchical structure (parent/child)
- ✅ Human-readable labels

**What's NOT stored here**:
- ❌ Actual fact values
- ❌ Balance attribute
- ❌ Calculation weights

---

## The Metadata Enrichment Process

### Phase 1: Fact Parsing (instance.py)

When parsing the instance document, facts are created **without** balance or weight:

```python
# In parsers/instance.py
fact = Fact(
    concept='us-gaap:PaymentsOfDividends',
    value='12769000000',
    context_ref='context_id_123',
    # Note: NO balance, NO weight at this stage
)
```

**Why?** Because balance and weight are **not in the instance document**. They're in separate files.

---

### Phase 2: FactsView Enrichment (facts.py)

When you query facts via `FactsView`, enrichment happens:

```python
# In xbrl/facts.py - FactsView.get_facts()
def get_facts(self) -> List[Dict]:
    """Get facts with enriched metadata."""

    for fact in self._xbrl._facts.values():
        concept = fact['fact'].concept

        # Enrich with balance from element_catalog
        element_id = concept.replace(':', '_')
        if element_id in self._xbrl.element_catalog:
            element = self._xbrl.element_catalog[element_id]
            fact_dict['balance'] = element.balance  # ← Added here!

        # Enrich with weight from calculation_trees
        for calc_tree in self._xbrl.calculation_trees.values():
            if element_id in calc_tree.all_nodes:
                calc_node = calc_tree.all_nodes[element_id]
                fact_dict['weight'] = calc_node.weight  # ← Added here!

        yield fact_dict
```

**Result**: Facts DataFrame includes `balance` and `weight` columns.

**Important**: This enrichment happens **on-the-fly** during query processing, not during initial parsing.

---

### Phase 3: Statement Line Item Building (xbrl.py)

When building statement line items from presentation trees, **all three sources** are merged:

```python
# In xbrl/xbrl.py - _generate_line_items()
def _generate_line_items(self, node, period_filter=None, ...):
    """Build line item with metadata from all sources."""

    element_id = node.element_name
    element_id_normalized = element_id.replace(':', '_')

    # 1. Get balance from element catalog (schema)
    balance = None
    if element_id_normalized in self.element_catalog:
        element = self.element_catalog[element_id_normalized]
        balance = element.balance  # ← From schema

    # 2. Get weight from calculation trees (calculation linkbase)
    weight = None
    if hasattr(self, 'calculation_trees') and self.calculation_trees:
        for calc_tree in self.calculation_trees.values():
            if element_id_normalized in calc_tree.all_nodes:
                calc_node = calc_tree.all_nodes[element_id_normalized]
                weight = calc_node.weight  # ← From calculation linkbase
                break

    # 3. Calculate preferred_sign from preferred_label (presentation linkbase)
    preferred_sign_value = None
    if node.preferred_label:  # ← From presentation linkbase
        label_lower = node.preferred_label.lower()
        is_negated = 'negated' in label_lower
        preferred_sign_value = -1 if is_negated else 1

    # 4. Get fact values from instance document
    all_relevant_facts = self._find_facts_for_element(element_id, period_filter)

    # 5. Build line item with ALL metadata
    line_item = {
        'concept': element_id,
        'label': self._get_label_for_element(element_id),
        'balance': balance,  # From schema
        'weight': weight,    # From calculation linkbase
        'preferred_signs': {  # From presentation linkbase
            period_key: preferred_sign_value
            for period_key in period_keys
        },
        'values': {  # From instance document
            period_key: fact_value
            for period_key, fact_value in period_values.items()
        }
    }

    return line_item
```

**Result**: Statement line items contain metadata from **all three sources**.

---

## The Critical Difference: preferred_sign vs balance/weight

### Where Metadata Lives

| Metadata | Source | Stored In | Scope | Available In |
|----------|--------|-----------|-------|--------------|
| **balance** | Schema (.xsd) | `element_catalog` | Concept-level | ✅ Facts, ✅ Statements |
| **weight** | Calculation Linkbase (_cal.xml) | `calculation_trees` | Calculation-level | ✅ Facts, ✅ Statements |
| **preferred_sign** | Presentation Linkbase (_pre.xml) | Presentation nodes | Period-specific | ❌ Facts, ✅ Statements |

### Why preferred_sign is Different

**Balance and Weight**: Concept-level attributes
```python
# PaymentsOfDividends has balance='credit' everywhere it appears
balance = 'credit'  # Same across all contexts

# PaymentsOfDividends has weight=-1.0 in financing activities calculation
weight = -1.0  # Same in all calculations
```

**Preferred Sign**: Period-specific AND context-specific
```python
# PaymentsOfDividends can have different preferred_sign in different periods!
preferred_signs = {
    'duration_2023-10-01_2024-09-28': -1,  # Negated in 2024 period
    'duration_2022-09-25_2023-09-30': -1,  # Negated in 2023 period
    'duration_2021-09-26_2022-09-24': -1,  # Negated in 2022 period
}
```

**Why?** Because the same concept might appear in different presentation contexts (e.g., as a subtotal in one section, as a line item in another).

---

## Common Mistakes and How to Avoid Them

### ❌ Mistake 1: Getting preferred_sign from Facts

```python
# WRONG!
facts_df = xbrl.facts.query().by_concept('PaymentsOfDividends').to_dataframe()
preferred_sign = facts_df.iloc[0]['preferred_sign']  # ❌ Will be None!
```

**Why it fails**: Facts don't have `preferred_sign` because it comes from presentation linkbase, not instance document.

**Correct approach**:
```python
# CORRECT!
stmt = xbrl.statements.cashflow_statement()
stmt_data = stmt.get_raw_data()

for item in stmt_data:
    if 'PaymentsOfDividends' in item['concept']:
        preferred_signs = item.get('preferred_signs', {})  # ✅ From statement data
```

---

### ❌ Mistake 2: Assuming balance/weight are Fact attributes

```python
# WRONG!
fact = Fact(concept='us-gaap:PaymentsOfDividends', value='12769000000')
balance = fact.balance  # ❌ Fact objects don't have balance attribute!
```

**Why it fails**: `Fact` is a simple data class representing instance document content only.

**Correct approach**:
```python
# CORRECT!
# Get balance from element_catalog
element_id = 'us-gaap_PaymentsOfDividends'
if element_id in xbrl.element_catalog:
    element = xbrl.element_catalog[element_id]
    balance = element.balance  # ✅ From schema

# OR: Get enriched fact from FactsView
facts_df = xbrl.facts.query().by_concept('PaymentsOfDividends').to_dataframe()
balance = facts_df.iloc[0]['balance']  # ✅ Enriched during query
```

---

### ❌ Mistake 3: Using concept-level preferred_sign

```python
# WRONG!
preferred_sign = item.get('preferred_sign')  # ❌ No such thing!

# preferred_sign is PERIOD-SPECIFIC:
preferred_signs = item.get('preferred_signs', {})  # ✅ Dictionary keyed by period
```

**Why it fails**: `preferred_sign` is calculated from `preferred_label` which can vary by presentation context.

**Correct approach**:
```python
# CORRECT!
preferred_signs = item.get('preferred_signs', {})  # Dictionary
period_key = 'duration_2023-10-01_2024-09-28'
preferred_sign = preferred_signs.get(period_key)  # ✅ Get for specific period
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        XBRL Filing Package                       │
└─────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
        ┌───────────────┐ ┌─────────────┐ ┌──────────────┐
        │   Instance    │ │   Schema    │ │ Presentation │
        │   Document    │ │ Calculation │ │  Linkbase    │
        │               │ │  Linkbase   │ │              │
        │  _htm.xml     │ │  .xsd       │ │  _pre.xml    │
        │               │ │  _cal.xml   │ │              │
        └───────────────┘ └─────────────┘ └──────────────┘
                │               │               │
                │               │               │
                ▼               ▼               ▼
        ┌───────────────┐ ┌─────────────┐ ┌──────────────┐
        │  xbrl._facts  │ │element_     │ │presentation_ │
        │               │ │catalog      │ │trees         │
        │  {context:    │ │calculation_ │ │              │
        │   Fact(...)}  │ │trees        │ │              │
        └───────────────┘ └─────────────┘ └──────────────┘
                │               │               │
                └───────────────┼───────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  Statement Line Items │
                    │                       │
                    │  concept: str         │
                    │  values: {period: #}  │ ← From Instance
                    │  balance: str         │ ← From Schema
                    │  weight: float        │ ← From Calculation
                    │  preferred_signs: {}  │ ← From Presentation
                    └───────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
                ▼               ▼               ▼
        ┌───────────┐   ┌──────────┐   ┌──────────────┐
        │ DataFrame │   │ Rich     │   │ Facts Query  │
        │           │   │ Display  │   │ (enriched)   │
        └───────────┘   └──────────┘   └──────────────┘
```

---

## Implementation in EdgarTools

### Getting Balance and Weight (Fact-level)

```python
# Method 1: Via FactsView (automatic enrichment)
facts_df = xbrl.facts.query().by_concept('PaymentsOfDividends').to_dataframe()
balance = facts_df.iloc[0]['balance']  # ✅ Enriched from element_catalog
weight = facts_df.iloc[0]['weight']    # ✅ Enriched from calculation_trees

# Method 2: Direct from element_catalog
element_id = 'us-gaap_PaymentsOfDividends'
element = xbrl.element_catalog[element_id]
balance = element.balance  # ✅ Direct access

# Method 3: Direct from calculation_trees
for calc_tree in xbrl.calculation_trees.values():
    if element_id in calc_tree.all_nodes:
        weight = calc_tree.all_nodes[element_id].weight  # ✅ Direct access
```

### Getting Preferred Sign (Statement-level)

```python
# ONLY available in statement line items!
stmt = xbrl.statements.cashflow_statement()
stmt_data = stmt.get_raw_data()

for item in stmt_data:
    if 'PaymentsOfDividends' in item['concept']:
        # Period-specific dictionary
        preferred_signs = item.get('preferred_signs', {})

        # Get for specific period
        period_key = 'duration_2023-10-01_2024-09-28'
        preferred_sign = preferred_signs.get(period_key)  # -1, 1, or None
```

### Adding Metadata to DataFrames (statements.py)

```python
def _add_metadata_columns(self, df: pd.DataFrame) -> pd.DataFrame:
    """Add metadata columns to DataFrame."""

    # Get statement's raw data (has all metadata already)
    raw_data = self.get_raw_data()
    raw_data_by_concept = {item.get('concept'): item for item in raw_data}

    balance_map = {}
    weight_map = {}
    preferred_sign_map = {}

    for concept in df['concept'].unique():
        # Get balance and weight from facts (enriched)
        facts_df = self.xbrl.facts.query().by_concept(concept, exact=True).limit(1).to_dataframe()
        if not facts_df.empty:
            balance_map[concept] = facts_df.iloc[0].get('balance')
            weight_map[concept] = facts_df.iloc[0].get('weight')

        # Get preferred_sign from statement raw data (NOT from facts!)
        if concept in raw_data_by_concept:
            item = raw_data_by_concept[concept]
            preferred_signs = item.get('preferred_signs', {})
            if preferred_signs:
                # Use first period's sign as representative value
                preferred_sign_map[concept] = next(iter(preferred_signs.values()))

    # Add columns
    df['balance'] = df['concept'].map(balance_map)
    df['weight'] = df['concept'].map(weight_map)
    df['preferred_sign'] = df['concept'].map(preferred_sign_map)

    return df
```

---

## Performance Considerations

### Enrichment Cost

**Facts enrichment** (adding balance/weight):
- Happens during `FactsView.get_facts()` query
- O(n) lookups in `element_catalog` and `calculation_trees`
- Cached after first query via `_facts_df_cache`

**Statement building** (merging all metadata):
- Happens during `_generate_line_items()`
- One-time cost per statement
- Results cached in statement objects

### Optimization Tips

1. **Batch fact queries**: Use `FactsView.query()` to get multiple facts at once
2. **Cache DataFrames**: `FactsView` caches enriched DataFrames
3. **Limit queries**: Use `.limit(n)` to avoid processing all facts
4. **Reuse statements**: Statement objects cache their line items

---

## Testing Strategy

### Test Metadata Availability

```python
def test_metadata_columns_included():
    """Verify metadata columns exist in DataFrame."""
    df = statement.to_dataframe()

    assert 'balance' in df.columns
    assert 'weight' in df.columns
    assert 'preferred_sign' in df.columns
```

### Test Metadata Values

```python
def test_balance_attribute_available():
    """Verify balance comes from schema."""
    facts_df = xbrl.facts.query().by_concept('PaymentsOfDividends').to_dataframe()

    assert 'balance' in facts_df.columns
    assert facts_df.iloc[0]['balance'] == 'credit'  # From element_catalog
```

### Test Preferred Sign Source

```python
def test_preferred_sign_from_statement():
    """Verify preferred_sign comes from presentation linkbase."""
    stmt = xbrl.statements.cashflow_statement()
    df = stmt.to_dataframe()

    # preferred_sign should be populated from statement data
    dividend_row = df[df['concept'].str.contains('PaymentsOfDividends')]
    assert pd.notna(dividend_row.iloc[0]['preferred_sign'])
```

---

## Key Takeaways

### 1. **Three Separate Data Structures**
- Instance Document → fact values
- Schema/Calculation → balance, weight
- Presentation → preferred_label, display order

### 2. **Enrichment Happens at Different Stages**
- Facts enrichment: During `FactsView.query()`
- Statement enrichment: During `_generate_line_items()`

### 3. **Preferred Sign is Different**
- Not a Fact attribute
- Period-specific (stored as dictionary)
- Only available in statement line items

### 4. **Always Use the Right Source**
- Balance/Weight → Get from facts or element_catalog
- Preferred Sign → Get from statement raw data
- Never assume metadata exists on raw Fact objects

### 5. **Performance Matters**
- Enrichment has cost (lookups in catalog/trees)
- Use caching (FactsView caches DataFrames)
- Limit queries when possible

---

## Common Patterns

### Pattern 1: Get Fact with Full Metadata

```python
# Use FactsView query (includes balance, weight, but NOT preferred_sign)
facts_df = xbrl.facts.query().by_concept('PaymentsOfDividends').to_dataframe()

# Access enriched metadata
balance = facts_df.iloc[0]['balance']  # ✅
weight = facts_df.iloc[0]['weight']    # ✅
preferred_sign = facts_df.iloc[0].get('preferred_sign')  # ❌ None (not in facts!)
```

### Pattern 2: Get Statement Line Item with All Metadata

```python
# Get from statement (includes balance, weight, AND preferred_signs)
stmt = xbrl.statements.cashflow_statement()
stmt_data = stmt.get_raw_data()

for item in stmt_data:
    balance = item.get('balance')              # ✅ From schema
    weight = item.get('weight')                # ✅ From calculation
    preferred_signs = item.get('preferred_signs')  # ✅ From presentation (dict!)
```

### Pattern 3: Build DataFrame with Metadata

```python
# Use to_dataframe() - handles enrichment automatically
df = statement.to_dataframe()

# All metadata columns included
assert 'balance' in df.columns
assert 'weight' in df.columns
assert 'preferred_sign' in df.columns  # Representative value from first period
```

---

## Debugging Tips

### Check Metadata Sources

```python
# Verify element_catalog has balance
element_id = 'us-gaap_PaymentsOfDividends'
if element_id in xbrl.element_catalog:
    print(f"Balance: {xbrl.element_catalog[element_id].balance}")
else:
    print("Element not in catalog!")

# Verify calculation_trees has weight
for role, calc_tree in xbrl.calculation_trees.items():
    if element_id in calc_tree.all_nodes:
        print(f"Weight in {role}: {calc_tree.all_nodes[element_id].weight}")

# Verify presentation_trees has preferred_label
for role, pres_tree in xbrl.presentation_trees.items():
    if element_id in pres_tree.all_nodes:
        print(f"Preferred Label: {pres_tree.all_nodes[element_id].preferred_label}")
```

### Trace Enrichment

```python
# Check if enrichment happened
facts_df = xbrl.facts.query().by_concept('PaymentsOfDividends').to_dataframe()

print("Columns:", facts_df.columns.tolist())
# Should include: ['concept', 'value', 'balance', 'weight', ...]

if 'balance' not in facts_df.columns:
    print("WARNING: Enrichment didn't happen!")
```

### Compare Sources

```python
# Compare metadata from different sources
concept = 'us-gaap:PaymentsOfDividends'

# From facts
facts_df = xbrl.facts.query().by_concept(concept).to_dataframe()
fact_balance = facts_df.iloc[0]['balance']

# From element catalog
element_id = concept.replace(':', '_')
catalog_balance = xbrl.element_catalog[element_id].balance

# From statement
stmt_data = xbrl.statements.cashflow_statement().get_raw_data()
stmt_balance = [item['balance'] for item in stmt_data if item['concept'] == concept][0]

# Should all match!
assert fact_balance == catalog_balance == stmt_balance
```

---

## References

- **Code**: `edgar/xbrl/facts.py` (FactsView enrichment)
- **Code**: `edgar/xbrl/xbrl.py` (_generate_line_items)
- **Code**: `edgar/xbrl/statements.py` (_add_metadata_columns)
- **Issue**: #463 (XBRL value transformations)
- **Doc**: `xbrl-value-presentation-logic.md` (companion document)

---

**Last Updated**: 2025-01-20
**Maintained By**: EdgarTools Development Team
