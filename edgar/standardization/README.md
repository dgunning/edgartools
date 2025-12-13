# Standardization Package

Centralized standardization infrastructure for EdgarTools, enabling consistent cross-company financial analysis.

## Overview

The standardization package provides unified synonym management for XBRL tags. Different companies use different XBRL tags for the same financial concept (e.g., `Revenues`, `SalesRevenueNet`, `RevenueFromContractWithCustomerExcludingAssessedTax` all mean "Revenue"). This package maps these variations to canonical concept names.

## Quick Start

```python
from edgar.standardization import SynonymGroups, get_synonym_groups

# Get the default instance (singleton with builtin groups)
synonyms = get_synonym_groups()

# Look up all tags for a concept
revenue_group = synonyms.get_group('revenue')
print(revenue_group.synonyms)
# ['RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues', ...]

# Identify what concept a tag represents
info = synonyms.identify_concept('us-gaap:Revenues')
print(info.name)  # 'revenue'
print(info.category)  # 'income_statement'

# Check if a tag belongs to a concept
synonyms.get_group('revenue').contains_tag('SalesRevenueNet')  # True
```

## Key Classes

### SynonymGroup

Represents a group of XBRL tags that map to a single financial concept.

```python
from edgar.standardization import SynonymGroup

group = SynonymGroup(
    name='revenue',
    synonyms=['Revenues', 'SalesRevenueNet', 'NetSales'],
    description='Total revenue/sales from operations',
    category='income_statement'
)

# Check membership (O(1) lookup)
group.contains_tag('Revenues')  # True
group.contains_tag('NetIncome')  # False
```

**Attributes:**
- `name`: Canonical concept name (normalized to lowercase with underscores)
- `synonyms`: List of XBRL tag names (order preserved, duplicates removed)
- `description`: Human-readable description
- `namespace`: Default namespace (default: `us-gaap`)
- `priority_order`: How to order synonyms (`listed`, `frequency`, `specificity`)
- `category`: Financial statement category

### SynonymGroups

Registry that manages multiple synonym groups with reverse lookup capabilities.

```python
from edgar.standardization import SynonymGroups

synonyms = SynonymGroups()  # Includes 59 builtin groups

# Access groups
synonyms.get_group('net_income')
synonyms.get_synonyms('revenue')  # Returns list of tag names

# Reverse lookup
info = synonyms.identify_concept('NetIncomeLoss')
print(f"{info.tag} -> {info.name}")  # NetIncomeLoss -> net_income

# List all groups
for name in synonyms.list_groups():
    print(name)
```

### ConceptInfo

Returned by `identify_concept()` with information about a matched concept.

```python
info = synonyms.identify_concept('CashAndCashEquivalentsAtCarryingValue')

info.name        # 'cash_and_cash_equivalents'
info.tag         # 'CashAndCashEquivalentsAtCarryingValue'
info.group       # The full SynonymGroup object
info.category    # 'balance_sheet'
info.synonyms    # All synonyms for this concept
info.match_type  # 'exact'
```

## Multi-Group Membership

Tags can belong to multiple groups to support context-dependent concepts. For example, `DepreciationAndAmortization` appears in both income statements and cash flow statements.

```python
# Get all groups containing a tag
infos = synonyms.identify_concepts('DepreciationAndAmortization')
for info in infos:
    print(f"{info.name} ({info.category})")
# depreciation_and_amortization (income_statement)
# depreciation_adjustment (cash_flow)

# identify_concept() returns the first match
info = synonyms.identify_concept('DepreciationAndAmortization')
# Returns first registered group
```

## Custom Groups

### Register a Custom Group

```python
synonyms = SynonymGroups()

synonyms.register_group(
    name='custom_capex',
    synonyms=[
        'PaymentsToAcquirePropertyPlantAndEquipment',
        'CapitalExpenditures',
        'PurchaseOfPropertyPlantAndEquipment'
    ],
    description='Capital expenditures',
    category='cash_flow'
)
```

### JSON Import/Export

```python
# Export to JSON
synonyms.to_json('my_synonyms.json')

# Import from JSON
synonyms = SynonymGroups.from_json('my_synonyms.json')

# Export to dict (for programmatic use)
data = synonyms.to_dict()
```

### Unregister Groups

```python
synonyms.unregister_group('custom_capex')
```

## Builtin Groups

The package includes 59 pre-built synonym groups organized by category:

### Income Statement
- `revenue`, `cost_of_revenue`, `gross_profit`
- `operating_expenses`, `operating_income`
- `interest_expense`, `interest_income`
- `income_before_tax`, `income_tax_expense`
- `net_income`, `eps_basic`, `eps_diluted`
- `research_and_development`, `selling_general_administrative`
- `depreciation_and_amortization`

### Balance Sheet
- `cash_and_cash_equivalents`, `short_term_investments`
- `accounts_receivable`, `inventory`, `prepaid_expenses`
- `total_current_assets`, `total_assets`
- `property_plant_equipment`, `goodwill`, `intangible_assets`
- `accounts_payable`, `accrued_liabilities`, `short_term_debt`
- `total_current_liabilities`, `long_term_debt`, `total_liabilities`
- `common_stock`, `retained_earnings`, `total_equity`

### Cash Flow
- `operating_cash_flow`, `investing_cash_flow`, `financing_cash_flow`
- `capital_expenditures`, `depreciation_adjustment`
- `dividends_paid`, `share_repurchases`
- `debt_issuance`, `debt_repayment`

### Shares
- `shares_outstanding`, `weighted_average_shares_basic`
- `weighted_average_shares_diluted`

## Performance

The implementation is optimized for performance:

- **Module-level caching**: Builtin groups are cached at module level
- **O(1) tag lookup**: `contains_tag()` uses set-based lookup
- **Singleton pattern**: `get_synonym_groups()` returns cached instance

```python
# Fast: uses cached singleton
synonyms = get_synonym_groups()

# Also fast: builtin groups are cached
synonyms = SynonymGroups()
```

## Design Notes

### Scope

SynonymGroups handles **tag identity** only - mapping XBRL tags to canonical concept names. It does not handle:

- **Calculated concepts** (e.g., Gross Profit = Revenue - COGS) - handled in statement/facts layer
- **Period selection** - handled by calling code
- **Value aggregation** - handled by calling code

### Normalization

- Concept names are normalized to lowercase with underscores
- Namespace prefixes (e.g., `us-gaap:`) are stripped from tags
- Duplicate synonyms are removed while preserving order

## See Also

- `edgar/entity/entity_facts.py` - Uses synonyms for fact retrieval
- `edgar/xbrl/statements.py` - Uses synonyms for statement building
