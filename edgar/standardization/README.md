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
- `basis`: Measurement basis, `'net'` or `'gross'`, for concepts that exist on both bases
  and must not be mixed (default `None`)

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
# Export to JSON (user-defined groups only; include_builtin=True exports all)
synonyms.export_to_json('my_synonyms.json')

# Import from JSON (built-in groups plus the file's groups)
synonyms = SynonymGroups.from_file('my_synonyms.json')

# Export a group to dict (for programmatic use)
data = synonyms.get_group('custom_capex').to_dict()
```

### Unregister Groups

```python
synonyms.unregister_group('custom_capex')
```

## Builtin Groups

The package includes 63 pre-built synonym groups organized by category:

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
- `crypto_assets`, `crypto_assets_current`, `crypto_assets_noncurrent` (one element each;
  three different measures, never synonyms of each other)
- `accounts_payable`, `accrued_liabilities`, `short_term_debt`
- `total_current_liabilities`, `long_term_debt`, `total_liabilities`
- `common_stock`, `retained_earnings`, `total_equity`

### Cash Flow
- `operating_cash_flow`, `investing_cash_flow`, `financing_cash_flow`
- `capital_expenditures`, `depreciation_adjustment`
- `dividends_paid`, `share_repurchases`
- `interest_paid`, `interest_paid_gross`, `income_taxes_paid`, `income_taxes_paid_gross`
- `debt_issuance`, `debt_repayment`

#### Cash interest and income taxes paid

Cash paid for interest and income taxes is reported on two bases, and each basis is
its own group. Neither group falls back to the other, so `interest_paid` returns
`None` for a company that tags only `InterestPaid`; ask for `interest_paid_gross`
when the gross figure is what you want.

| Group | XBRL tag | Basis |
|---|---|---|
| `interest_paid` | `InterestPaidNet` | net of capitalized interest |
| `interest_paid_gross` | `InterestPaid` | including capitalized interest |
| `income_taxes_paid` | `IncomeTaxesPaidNet` | net of refunds |
| `income_taxes_paid_gross` | `IncomeTaxesPaid` | before refunds |

`get_concept(..., return_metadata=True)` adds a `basis` key (`'net'` or `'gross'`)
for these groups. Oracle's fiscal 2026 10-K (accession 0001193125-26-277521):

```python
from edgar import Company

facts = Company("ORCL").get_facts()
cash_interest = facts.get_concept("interest_paid", period="2026-FY", return_metadata=True)
cash_taxes = facts.get_concept("income_taxes_paid", period="2026-FY", return_metadata=True)
cash_interest["value"], cash_interest["tag_used"], cash_interest["basis"]
# (3896000000.0, 'us-gaap:InterestPaidNet', 'net')
cash_taxes["value"]
# 3704000000.0
```

This example is verified by `tests/issues/regression/test_issue_1858.py`.

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
- Standard taxonomy prefixes (`us-gaap`, `ifrs-full`, `dei`, `srt`) are stripped from tags, as `us-gaap:Revenues` or `us-gaap_Revenues`
- Any other prefix, such as a filer's extension (`orcl:Revenues`), names a different concept, so the tag is kept whole and matches no builtin synonym
- Duplicate synonyms are removed while preserving order

## See Also

- `edgar/entity/entity_facts.py` - Uses synonyms for fact retrieval
- `edgar/xbrl/statements.py` - Uses synonyms for statement building
