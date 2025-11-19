# Customizing XBRL Standardization

**Target Audience**: Advanced users, financial analysts, quantitative researchers
**Prerequisites**: Understanding of XBRL concepts, Python basics, JSON format
**Use Case**: Custom taxonomies, 200+ companies, industry-specific valuations

---

## Table of Contents

1. [Overview and Introduction](#1-overview-and-introduction)
2. [Architecture and Design](#2-architecture-and-design)
3. [Core Mappings Structure](#3-core-mappings-structure)
4. [Company-Specific Mappings](#4-company-specific-mappings)
5. [Priority System and Ambiguous Tag Resolution](#5-priority-system-and-ambiguous-tag-resolution)
6. [Current Limitations](#6-current-limitations)
7. [Validation Techniques](#7-validation-techniques)
8. [CSV Workflow](#8-csv-workflow)
9. [Real-World Examples](#9-real-world-examples)
10. [Future Enhancements](#10-future-enhancements)

---

## 1. Overview and Introduction

### What is XBRL Standardization?

XBRL standardization is the process of mapping company-specific XBRL tags to a consistent set of standardized concept names. This enables:

- **Consistent presentation** of financial statements across different companies
- **Comparable analysis** regardless of each company's unique taxonomy
- **Automated processing** of financial data from diverse sources
- **Reduced complexity** when working with 200+ companies

### Why Companies Need Custom Taxonomies

Every company's XBRL filing uses a mix of:
- **US-GAAP standard tags**: `us-gaap:Revenue`, `us-gaap:Assets`
- **Company-specific extensions**: `tsla:AutomotiveRevenue`, `msft:AzureRevenue`
- **Industry-specific concepts**: Energy, automotive, technology sectors

**The Problem**: Without standardization, analyzing 200 companies means dealing with thousands of unique XBRL tag variations for the same underlying financial concept.

**The Solution**: EdgarTools' standardization system maps all these variations to a unified set of standard concepts.

### When to Customize Standardization

You should customize the standardization system when:

- **Managing 200+ companies** with diverse taxonomies
- **Working with industry-specific filings** (automotive, technology, industrial firms)
- **Building valuation models** requiring granular financial statements
- **Conducting multi-company analysis** that requires consistent data structure
- **Ensuring statement balancing** (Assets = Liabilities + Equity) across diverse filings

### What This Guide Covers

This comprehensive guide explains:
- How the standardization architecture works
- How to create custom concept mappings
- How to handle ambiguous XBRL tags (200+ identified cases)
- How to validate mapping quality
- Production-ready workflows for managing custom taxonomies

---

## 2. Architecture and Design

### The StandardConcept Enum vs JSON Mappings

This is a critical distinction that causes confusion:

#### StandardConcept Enum: IDE Convenience (Optional)

```python
from edgar.xbrl.standardization import StandardConcept

# Enum provides autocomplete and type safety
revenue_label = StandardConcept.REVENUE.value  # "Revenue"
assets_label = StandardConcept.TOTAL_ASSETS.value  # "Total Assets"
```

**Purpose**:
- IDE autocomplete for known concepts
- Type safety for Python code
- Semantic meaning for core financial concepts

**Location**: `edgar/xbrl/standardization/core.py` (lines 18-126)

#### JSON Mappings: Source of Truth (Required)

```json
{
  "Revenue": [
    "us-gaap:Revenue",
    "us-gaap:Revenues",
    "us-gaap:SalesRevenueNet"
  ]
}
```

**Purpose**:
- The actual mapping data used by the system
- Unlimited extensibility without code changes
- User-customizable without touching Python code

**Location**: `edgar/xbrl/standardization/concept_mappings.json`

#### Critical Clarification

**The Relationship**:
- Enum values SHOULD match JSON keys (e.g., `StandardConcept.REVENUE.value == "Revenue"`)
- This relationship is NOT enforced by code
- JSON is what the system actually uses for mapping
- Enum is purely for developer convenience

**For Custom Mappings**:
- **You customize via JSON files** - NOT by modifying the enum
- The enum can remain unchanged; JSON drives all behavior
- You can add mappings in JSON that don't exist in the enum
- System will validate JSON keys against enum if you enable validation (optional)

### How Standardization Works

The standardization system follows this flow:

```
Company XBRL Tag → MappingStore → Priority Resolution → Standard Concept
```

**Example**:
```
"tsla:AutomotiveRevenue" → [Priority 4: Tesla mapping] → "Automotive Revenue"
"us-gaap:Revenue" → [Priority 1: Core mapping] → "Revenue"
```

### Key Components

#### 1. MappingStore (The Brain)

**File**: `edgar/xbrl/standardization/core.py` (lines 128-462)

**Responsibilities**:
- Loads core mappings from `concept_mappings.json`
- Loads company-specific mappings from `company_mappings/` directory
- Merges mappings with priority scoring
- Resolves ambiguous tags using context

**Initialization**:
```python
from edgar.xbrl.standardization import MappingStore

# Default initialization (loads packaged mappings)
store = MappingStore()

# Custom source (future enhancement)
store = MappingStore(source="/path/to/custom_mappings.json")

# Read-only mode (for testing)
store = MappingStore(read_only=True)
```

#### 2. ConceptMapper (The Worker)

**File**: `edgar/xbrl/standardization/core.py` (lines 464-682)

**Responsibilities**:
- Maps individual concepts using MappingStore
- Caches results for performance
- Handles context-aware inference
- Tracks unmapped concepts

**Usage**:
```python
mapper = ConceptMapper(mapping_store)

# Map a concept with context
context = {
    'statement_type': 'BalanceSheet',
    'level': 0,
    'is_total': True
}
standard_concept = mapper.map_concept(
    company_concept='us-gaap:Assets',
    label='Total Assets',
    context=context
)
# Returns: "Total Assets"
```

#### 3. Priority System

The system uses priority levels to resolve conflicts:

| Priority | Source | Description | Example |
|----------|--------|-------------|---------|
| **P1** | Core mappings | Base US-GAAP concepts | `us-gaap:Revenue → "Revenue"` |
| **P2** | Company mappings | Company-specific overrides | `tsla:Revenue → "Automotive Revenue"` |
| **P4** | Detected entity | Auto-detected from prefix | `tsla:CustomTag → uses Tesla P2 mappings` |

**Priority Resolution Algorithm** (lines 408-449):
1. Detect entity from concept prefix (e.g., `tsla:` → `"tsla"`)
2. Search through merged mappings
3. For each match, calculate effective priority
4. If detected entity matches mapping source, boost to P4
5. Return highest priority match

---

## 3. Core Mappings Structure

### File Location

**Current Location** (hardcoded):
```
edgar/xbrl/standardization/concept_mappings.json
```

**Future Enhancement** (v4.30.0): Configurable paths via environment variables.

### JSON Structure

The core mappings file uses a flat dictionary structure:

```json
{
  "Standard Concept Label": [
    "company_specific_tag_1",
    "company_specific_tag_2",
    "us-gaap:StandardTag"
  ],
  "_comment_section": "Documentation comments for maintainers"
}
```

### Real Example from concept_mappings.json

```json
{
  "_comment_revenue_hierarchy": "REVENUE HIERARCHY FIX: Separated total revenue from component revenue types to prevent duplicate labels.",

  "Revenue": [
    "us-gaap:Revenue",
    "us-gaap:Revenues",
    "us-gaap:SalesRevenueNet",
    "us-gaap:OperatingRevenue"
  ],

  "Contract Revenue": [
    "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
    "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax"
  ],

  "Product Revenue": [
    "us-gaap:SalesRevenueGoodsNet",
    "us-gaap:ProductSales"
  ]
}
```

### Understanding Comments

The JSON file includes `_comment_*` keys for documentation:
- These are ignored by the mapping system
- They explain design decisions
- They help maintainers understand complex hierarchies

### Hierarchy Separation

Notice the careful separation of concepts:
- **"Revenue"**: Total revenue (parent concept)
- **"Contract Revenue"**: Component of revenue (child concept)
- **"Product Revenue"**: Another component (sibling to Contract Revenue)

This prevents mapping conflicts where multiple XBRL tags map to the same label.

### Cost Hierarchy Example

```json
{
  "_comment_cost_of_revenue_hierarchy": "Different business models use different cost concepts that should have distinct labels.",

  "Total Cost of Revenue": [
    "us-gaap:CostOfRevenue"
  ],

  "Cost of Goods Sold": [
    "us-gaap:CostOfGoodsSold"
  ],

  "Cost of Goods and Services Sold": [
    "us-gaap:CostOfGoodsAndServicesSold"
  ],

  "Direct Operating Costs": [
    "us-gaap:DirectOperatingCosts"
  ]
}
```

**Why separate these?**
- Manufacturing companies use "Cost of Goods Sold"
- Service companies use "Direct Operating Costs"
- Mixed businesses use "Cost of Goods and Services Sold"
- Each should have a distinct label for clarity

### Adding Custom Core Mappings

To extend core mappings (not recommended for most users):

1. **Locate the file**: `edgar/xbrl/standardization/concept_mappings.json`
2. **Add your mapping**:
```json
{
  "Custom Concept Label": [
    "us-gaap:YourCustomTag",
    "company:AnotherTag"
  ]
}
```
3. **Maintain hierarchy**: Ensure parent/child relationships are clear
4. **Add comments**: Document your reasoning with `_comment_*` keys

**Warning**: Modifying packaged files is not recommended. Use company-specific mappings instead (Section 4).

---

## 4. Company-Specific Mappings

### Why Company-Specific Mappings?

Company-specific mapping files allow you to:
- Override core mappings for specific companies
- Add industry-specific concepts (automotive, technology, energy)
- Handle company extension taxonomies
- Maintain separation of concerns (one file per company)

### File Structure: {ticker}_mappings.json

**Current Location** (hardcoded):
```
edgar/xbrl/standardization/company_mappings/{ticker}_mappings.json
```

**Important Note**: Currently uses ticker as identifier, but **CIK-based identification is coming in v4.30.0/v4.31.0** to handle multi-ticker companies (GOOG/GOOGL, HEI.A/HEI.B).

### Complete Company Mapping Schema

```json
{
  "metadata": {
    "entity_identifier": "ticker_symbol",
    "company_name": "Full Company Name",
    "cik": "1234567",
    "priority": "high|medium|low",
    "created_date": "YYYY-MM-DD",
    "last_updated": "YYYY-MM-DD",
    "description": "Brief description of custom taxonomy needs"
  },

  "concept_mappings": {
    "Standard Concept Label": [
      "company:CustomTag",
      "company:AnotherCustomTag"
    ]
  },

  "hierarchy_rules": {
    "Parent Concept": {
      "children": [
        "Child Concept 1",
        "Child Concept 2"
      ],
      "description": "Optional explanation"
    }
  },

  "business_context": {
    "primary_revenue_streams": ["stream1", "stream2"],
    "revenue_model": "product_and_service|subscription|manufacturing",
    "key_metrics": ["metric1", "metric2"],
    "industry": "industry_classification"
  }
}
```

### Real Example: Tesla (tsla_mappings.json)

```json
{
  "metadata": {
    "entity_identifier": "tsla",
    "company_name": "Tesla, Inc.",
    "cik": "1318605",
    "priority": "high",
    "created_date": "2024-06-25",
    "last_updated": "2024-06-25",
    "description": "Tesla-specific concept mappings to handle automotive, energy, and service revenue streams"
  },

  "concept_mappings": {
    "Automotive Revenue": [
      "tsla:AutomotiveRevenue",
      "tsla:AutomotiveSales",
      "tsla:VehicleRevenue"
    ],

    "Automotive Leasing Revenue": [
      "tsla:AutomotiveLeasing",
      "tsla:AutomotiveLeasingRevenue",
      "tsla:VehicleLeasingRevenue"
    ],

    "Energy Revenue": [
      "tsla:EnergyGenerationAndStorageRevenue",
      "tsla:EnergyRevenue",
      "tsla:SolarRevenue",
      "tsla:EnergyStorageRevenue"
    ],

    "Service Revenue": [
      "tsla:ServicesAndOtherRevenue",
      "tsla:ServiceRevenue",
      "tsla:SuperchargerRevenue"
    ]
  },

  "hierarchy_rules": {
    "Revenue": {
      "children": [
        "Automotive Revenue",
        "Energy Revenue",
        "Service Revenue"
      ]
    },
    "Automotive Revenue": {
      "children": [
        "Automotive Leasing Revenue"
      ]
    }
  },

  "business_context": {
    "primary_revenue_streams": ["automotive", "energy", "services"],
    "revenue_model": "product_and_service",
    "key_metrics": ["vehicle_deliveries", "energy_deployments"],
    "industry": "automotive_technology"
  }
}
```

### Real Example: Microsoft (msft_mappings.json)

```json
{
  "entity_info": {
    "name": "Microsoft Corporation",
    "cik": "0000789019",
    "ticker": "MSFT",
    "description": "Microsoft-specific concept mappings for unique business terminology"
  },

  "concept_mappings": {
    "_comment_msft_revenue": "Microsoft uses specific revenue categorization that differs from standard tech companies",

    "Product Revenue": [
      "msft:ProductRevenue",
      "msft:WindowsCommercialRevenue",
      "msft:WindowsConsumerRevenue",
      "msft:OfficeCommercialRevenue"
    ],

    "Service Revenue": [
      "msft:ServiceRevenue",
      "msft:CloudServicesRevenue",
      "msft:ConsultingServicesRevenue"
    ],

    "Subscription Revenue": [
      "msft:Office365CommercialRevenue",
      "msft:Office365ConsumerRevenue",
      "msft:DynamicsRevenue"
    ],

    "Platform Revenue": [
      "msft:AzureRevenue",
      "msft:XboxContentAndServicesRevenue"
    ],

    "_comment_msft_expenses": "Microsoft has unique expense categorizations",

    "Sales and Marketing Expense": [
      "msft:SalesAndMarketingExpense",
      "msft:AdvertisingAndPromotionExpense"
    ],

    "Technical Support Expense": [
      "msft:TechnicalSupportExpense",
      "msft:CustomerSupportExpense"
    ]
  },

  "hierarchy_rules": {
    "_comment": "Rules for handling Microsoft-specific hierarchical relationships",

    "revenue_hierarchy": {
      "parent": "Revenue",
      "children": ["Product Revenue", "Service Revenue", "Subscription Revenue", "Platform Revenue"],
      "calculation_rule": "sum"
    },

    "expense_hierarchy": {
      "parent": "Operating Expenses",
      "children": ["Sales and Marketing Expense", "Technical Support Expense"],
      "calculation_rule": "sum"
    }
  }
}
```

### Creating Your Own Company Mapping

**Step 1: Identify Company Extension Tags**

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="10-K").latest()
xbrl = filing.xbrl()

# Find company-specific tags
facts = xbrl.facts.query().to_dataframe()
company_tags = facts[facts['concept'].str.startswith('aapl:')]['concept'].unique()
print(f"Found {len(company_tags)} Apple-specific tags")
```

**Step 2: Create Mapping File**

```json
{
  "metadata": {
    "entity_identifier": "aapl",
    "company_name": "Apple Inc.",
    "cik": "0000320193",
    "priority": "high",
    "created_date": "2025-11-19",
    "last_updated": "2025-11-19",
    "description": "Apple-specific mappings for product categories"
  },

  "concept_mappings": {
    "iPhone Revenue": [
      "aapl:IPhoneRevenue",
      "aapl:IPhoneSales"
    ],

    "Services Revenue": [
      "aapl:ServicesRevenue",
      "aapl:AppleCareRevenue",
      "aapl:ICloudRevenue"
    ]
  }
}
```

**Step 3: Place File in Correct Location**

```
edgar/xbrl/standardization/company_mappings/aapl_mappings.json
```

**Current Limitation**: Must be inside the package directory (see Section 6).

---

## 5. Priority System and Ambiguous Tag Resolution

### The Ambiguous Tag Problem

Over **200 XBRL tags** are inherently ambiguous and can map to multiple standard concepts depending on context. These fall into several categories:

#### Category 1: Asset/Liability Ambiguity (12 tags)

Tags that could be either assets or liabilities:

```
DeferredTaxAssetsLiabilitiesNet
DeferredTaxAssetsLiabilitiesNetCurrent
DeferredTaxAssetsLiabilitiesNetNoncurrent
DerivativeAssetsLiabilitiesAtFairValueNet
DeferredFinanceCostsCurrentNet
DeferredFinanceCostsNoncurrentNet
CustomerAdvancesAndProgressPaymentsForLongTermContractsOrPrograms
DeferredTaxLiabilitiesGoodwillAndIntangibleAssets
DeferredTaxLiabilitiesInvestments
UnamortizedDebtIssuanceExpense
DerivativeLiabilityFairValueGrossAsset
```

**Example: DeferredTaxAssetsLiabilitiesNet**

This tag represents the NET of deferred tax assets and liabilities:
- If positive → Deferred Tax Asset
- If negative → Deferred Tax Liability

**Resolution Strategy**: Use statement context and sign convention.

#### Category 2: Current/Noncurrent Ambiguity (180+ tags)

Tags that don't specify classification:

```
AccountsPayableCurrentAndNoncurrent
AccountsPayableAndAccruedLiabilitiesCurrentAndNoncurrent
AccountsReceivableGross
AccountsReceivableNet
DeferredRevenue
ContractWithCustomerLiability
ConvertibleDebt
DebtInstrumentCarryingAmount
```

**Example: AccountsPayableCurrentAndNoncurrent**

Without context, you can't determine if this should map to:
- "Accounts Payable, Current" (on current liabilities)
- "Accounts Payable, Noncurrent" (on long-term liabilities)
- "Accounts Payable, Total" (parent concept)

**Resolution Strategy**: Use calculation tree parent relationships and statement location.

#### Category 3: Triple Ambiguity (1 tag)

```
DerivativeLiabilityFairValueGrossAsset
```

This tag is ambiguous in THREE dimensions:
1. Asset vs. Liability
2. Current vs. Noncurrent
3. Gross vs. Net

**Resolution**: Requires comprehensive context analysis.

#### Category 4: Total vs. Line Item Ambiguity

```
LiabilitiesNoncurrent
```

Some companies use this as:
- **Total line**: Sum of all noncurrent liabilities
- **Other line item**: "Other Noncurrent Liabilities"

**Resolution**: Check if it has children in calculation tree or appears multiple times.

### Priority Levels Explained

#### Priority 1: Core Mappings

**Source**: `concept_mappings.json`
**Use**: Base US-GAAP concepts that apply to all companies

```python
# P1 mapping example
"Revenue": [
  "us-gaap:Revenue",
  "us-gaap:Revenues",
  "us-gaap:SalesRevenueNet"
]
```

**When Applied**: When no company-specific mapping exists.

#### Priority 2: Company Mappings

**Source**: `company_mappings/{ticker}_mappings.json`
**Use**: Company-specific overrides and extensions

```python
# P2 mapping example (Tesla)
"Automotive Revenue": [
  "tsla:AutomotiveRevenue",
  "tsla:AutomotiveSales"
]
```

**When Applied**: When company mapping file exists for the ticker.

#### Priority 4: Detected Entity Match

**Source**: Automatic detection from concept prefix
**Use**: Boost priority when concept prefix matches company

```python
# P4 boost example
concept = "tsla:AutomotiveRevenue"
# System detects "tsla:" prefix
# Checks if "tsla" company mappings exist
# Boosts priority from P2 → P4 for Tesla mappings
```

**When Applied**: When concept prefix matches a known company identifier.

### Context-Based Resolution

The system uses multiple context signals to resolve ambiguous tags:

#### 1. Statement Type Context

```python
context = {
    'statement_type': 'BalanceSheet'  # or 'IncomeStatement', 'CashFlowStatement'
}
```

**Example Resolution**:
```
Tag: "DeferredTaxAssetsLiabilitiesNet"
Statement: BalanceSheet
Parent: "Assets"
→ Maps to: "Deferred Tax Assets"

Tag: "DeferredTaxAssetsLiabilitiesNet"
Statement: BalanceSheet
Parent: "Liabilities"
→ Maps to: "Deferred Tax Liabilities"
```

#### 2. Calculation Tree Relationships

```python
context = {
    'calculation_parent': 'us-gaap:AssetsCurrent',
    'level': 1
}
```

**Example Resolution**:
```
Tag: "AccountsPayableCurrentAndNoncurrent"
Parent: "AssetsCurrent" (impossible - payables are liabilities)
→ Check if sign is negative
→ Maps to: "Accounts Payable, Current" (negative in assets = liability)

Tag: "AccountsPayableCurrentAndNoncurrent"
Parent: "LiabilitiesCurrent"
→ Maps to: "Accounts Payable, Current"

Tag: "AccountsPayableCurrentAndNoncurrent"
Parent: "LiabilitiesNoncurrent"
→ Maps to: "Accounts Payable, Noncurrent"
```

#### 3. Sign Conventions

```python
# Positive value in assets section → Asset
# Negative value in assets section → Liability (unusual presentation)
# Check fact value and location
```

#### 4. Position and Level

```python
context = {
    'position': 0,  # First item in section
    'level': 0,     # Top level (total)
    'is_total': True
}
```

**Example Resolution**:
```
Tag: "LiabilitiesNoncurrent"
Level: 0
Has children: Yes
→ Maps to: "Total Noncurrent Liabilities"

Tag: "LiabilitiesNoncurrent"
Level: 1
Has children: No
→ Maps to: "Other Noncurrent Liabilities"
```

### Complete Ambiguous Tag List

For reference, here are all identified ambiguous tags (from user @mpreiss9's analysis):

**Asset/Liability Ambiguity (12 tags)**:
```
CustomerAdvancesAndProgressPaymentsForLongTermContractsOrPrograms
DeferredFinanceCostsCurrentNet
DeferredFinanceCostsNoncurrentNet
DeferredTaxAssetsLiabilitiesNet
DeferredTaxAssetsLiabilitiesNetCurrent
DeferredTaxAssetsLiabilitiesNetNoncurrent
DeferredTaxLiabilitiesGoodwillAndIntangibleAssets
DeferredTaxLiabilitiesGoodwillAndIntangibleAssetsIntangibleAssets
DeferredTaxLiabilitiesInvestments
DerivativeAssetsLiabilitiesAtFairValueNet
UnamortizedDebtIssuanceExpense
DerivativeLiabilityFairValueGrossAsset
```

**Current/Noncurrent Ambiguity (180+ tags)** - Excerpt:
```
AccountsPayableAndAccruedLiabilitiesCurrentAndNoncurrent
AccountsPayableAndOtherAccruedLiabilities
AccountsPayableCurrentAndNoncurrent
AccountsPayableOtherCurrentAndNoncurrent
AccountsPayableTradeCurrentAndNoncurrent
AccountsReceivableGross
AccountsReceivableNet
AccountsReceivableRelatedParties
AccrualForTaxesOtherThanIncomeTaxesCurrentAndNoncurrent
AccruedAdvertisingCurrentAndNoncurrent
AccruedBonusesCurrentAndNoncurrent
AccruedEmployeeBenefitsCurrentAndNoncurrent
AccruedIncomeTaxes
AccruedLiabilitiesCurrentAndNoncurrent
AvailableForSaleSecuritiesDebtSecurities
BusinessCombinationContingentConsiderationAsset
BusinessCombinationContingentConsiderationLiability
CapitalizedContractCostNet
CapitalLeaseObligations
ContractWithCustomerAssetNet
ContractWithCustomerLiability
ConvertibleDebt
DebtInstrumentCarryingAmount
DeferredRevenue
DeferredTaxAssetsGross
DeferredTaxAssetsNet
DeferredTaxLiabilities
DeferredTaxLiabilitiesNet
DerivativeAssets
DerivativeLiabilities
EquitySecuritiesFvNi
HeldToMaturitySecurities
Investments
LineOfCredit
MarketableSecurities
NotesAndLoansPayable
OperatingLeaseLiability
OtherAssets
OtherLiabilities
RestrictedCash
```

**See issue #494 comment for complete list of 200+ tags**.

### Implementing Custom Ambiguity Resolution

If you need to handle ambiguous tags for your specific use case:

**Option 1: Company-Specific Mapping**

```json
{
  "concept_mappings": {
    "Deferred Tax Assets": [
      "us-gaap:DeferredTaxAssetsLiabilitiesNet"
    ]
  },
  "notes": {
    "DeferredTaxAssetsLiabilitiesNet": "Company X always reports net deferred tax assets; never reports net liability"
  }
}
```

**Option 2: Context Validation (Future Enhancement)**

This is planned for v4.30.0:

```python
from edgar.xbrl.standardization import MappingStore

store = MappingStore()

# Custom resolution function
def custom_resolver(concept, context, value):
    if concept == "us-gaap:DeferredTaxAssetsLiabilitiesNet":
        if value > 0:
            return "Deferred Tax Assets"
        else:
            return "Deferred Tax Liabilities"
    return None

store.add_custom_resolver(custom_resolver)
```

---

## 6. Current Limitations

This section documents **known limitations** of the current implementation and provides workarounds. These are on the roadmap for future releases.

### Limitation 1: Hardcoded Paths

**Problem**: Mapping files MUST be inside the package directory.

**Current Paths**:
```
edgar/xbrl/standardization/concept_mappings.json
edgar/xbrl/standardization/company_mappings/{ticker}_mappings.json
```

**Why This is a Problem**:
- Users can't maintain mappings outside the package
- Difficult to version control custom mappings separately
- Package updates overwrite custom mappings
- Not suitable for production deployment workflows

**Current Workaround**:

Copy your custom mapping files into the package directory after installation:

```bash
# Find package location
python -c "import edgar; print(edgar.__file__)"
# Output: /path/to/site-packages/edgar/__init__.py

# Copy your custom mappings
cp my_custom_mappings.json /path/to/site-packages/edgar/xbrl/standardization/
cp company_mappings/* /path/to/site-packages/edgar/xbrl/standardization/company_mappings/
```

**Better Workaround** (Python script):

```python
import shutil
from pathlib import Path
import edgar

# Find package standardization directory
edgar_path = Path(edgar.__file__).parent
std_path = edgar_path / "xbrl" / "standardization"

# Copy custom core mappings
shutil.copy(
    "my_custom_mappings.json",
    std_path / "concept_mappings.json"
)

# Copy company mappings
company_dir = std_path / "company_mappings"
for mapping_file in Path("my_company_mappings").glob("*_mappings.json"):
    shutil.copy(mapping_file, company_dir / mapping_file.name)

print("Custom mappings installed successfully")
```

**Risks**:
- Mappings are lost on package upgrade
- Must re-run after each `pip install --upgrade edgartools`

**Future Enhancement** (v4.30.0):

```python
# Coming in v4.30.0
import os
os.environ['EDGAR_MAPPINGS_PATH'] = '/path/to/my/mappings'

# Or via constructor
from edgar.xbrl.standardization import MappingStore
store = MappingStore(
    core_path='/path/to/concept_mappings.json',
    company_dir='/path/to/company_mappings/'
)
```

### Limitation 2: Ticker-Based Identification

**Problem**: Company mappings use ticker as identifier, not CIK.

**Current Behavior**:
```python
# File: company_mappings/msft_mappings.json
{
  "metadata": {
    "entity_identifier": "msft",  # Uses ticker
    "cik": "0000789019"            # CIK is just metadata
  }
}
```

**Why This is a Problem**:

1. **Multiple tickers per CIK**:
   - Alphabet: GOOG and GOOGL → Same CIK (1652044)
   - HEICO: HEI.A and HEI.B → Same CIK (46619)

2. **Ticker changes over time**:
   - Facebook → Meta (FB → META)
   - Google → Alphabet (GOOG → GOOGL split)

3. **CIK is the stable identifier** in SEC filings:
   - Every filing contains CIK
   - Ticker can be ambiguous or absent

**Current Workaround**:

Use the **primary ticker** and document alternatives in metadata:

```json
{
  "metadata": {
    "entity_identifier": "goog",
    "company_name": "Alphabet Inc.",
    "cik": "0001652044",
    "alternative_tickers": ["GOOGL", "GOOG"],
    "notes": "Use GOOG as primary; applies to both Class A (GOOGL) and Class C (GOOG)"
  }
}
```

Then create a symlink or duplicate file:
```bash
cd company_mappings/
cp goog_mappings.json googl_mappings.json
```

**Future Enhancement** (v4.30.0 - v4.31.0):

```json
{
  "metadata": {
    "entity_identifier": "0001652044",  # CIK is primary identifier
    "tickers": ["GOOG", "GOOGL"],       # Multiple tickers supported
    "primary_ticker": "GOOG"
  }
}
```

**Timeline**:
- **v4.30.0**: Add CIK-based lookup support (dual lookup during transition)
- **v4.31.0**: Default to CIK-based identification
- **v5.0.0**: Deprecate ticker-based identification

### Limitation 3: JSON-Only Format

**Problem**: No native CSV support for mapping files.

**Why This is a Problem**:
- CSV is easier to edit in Excel or Google Sheets
- Easier to detect duplicates with spreadsheet tools
- Simpler to sort, filter, and validate mappings
- More accessible for non-technical users

**Current Workaround**: See Section 8 (CSV Workflow) for utilities.

**Quick CSV-to-JSON Converter**:

```python
import csv
import json
from collections import defaultdict

def csv_to_mappings(csv_path, json_path):
    """Convert CSV mapping file to JSON format."""
    mappings = defaultdict(list)

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            standard_concept = row['standard_concept']
            company_concept = row['company_concept']
            mappings[standard_concept].append(company_concept)

    with open(json_path, 'w') as f:
        json.dump(dict(mappings), f, indent=2)

    print(f"Converted {len(mappings)} concepts")

# Usage
csv_to_mappings('my_mappings.csv', 'concept_mappings.json')
```

**Expected CSV Format**:
```csv
standard_concept,company_concept,notes
Revenue,us-gaap:Revenue,Standard revenue tag
Revenue,us-gaap:Revenues,Alternative spelling
Automotive Revenue,tsla:AutomotiveRevenue,Tesla-specific
```

**Future Enhancement** (v4.30.0):

```python
# Native CSV support - auto-detect from extension
from edgar.xbrl.standardization import MappingStore

# Automatically loads CSV or JSON based on extension
store = MappingStore(source="my_mappings.csv")
```

---

## 7. Validation Techniques

Validation is critical when working with custom mappings across 200+ companies. Here are proven techniques for ensuring mapping quality.

### The Balance Sheet Validation Principle

The fundamental validation for balance sheets:

```python
# Core accounting equation
Assets = Liabilities + Equity

# Detailed validation
Total Assets = Current Assets + Noncurrent Assets
Total Assets = Sum(all individual asset line items)

Total Liabilities = Current Liabilities + Noncurrent Liabilities
Total Equity = Common Stock + Retained Earnings + Other Equity

Assets = Liabilities + Equity
```

### Balance Sheet Validation Code

```python
def validate_balance_sheet(xbrl, period_key):
    """Validate that balance sheet balances using mapped concepts."""

    facts = xbrl.facts.query().by_period_key(period_key).to_dataframe()

    # Get key totals
    total_assets = facts[facts['label'] == 'Total Assets']['value'].sum()
    current_assets = facts[facts['label'] == 'Total Current Assets']['value'].sum()
    noncurrent_assets = facts[facts['label'] == 'Total Non Current Assets']['value'].sum()

    total_liabilities = facts[facts['label'] == 'Total Liabilities']['value'].sum()
    total_equity = facts[facts['label'] == "Total Stockholders' Equity"]['value'].sum()

    # Validation 1: Assets = Current + Noncurrent
    if noncurrent_assets:  # Some companies don't report noncurrent separately
        assets_check = abs(total_assets - (current_assets + noncurrent_assets)) < 1.0
        if not assets_check:
            print(f"WARNING: Assets don't balance: {total_assets} != {current_assets} + {noncurrent_assets}")

    # Validation 2: Assets = Liabilities + Equity
    accounting_equation = abs(total_assets - (total_liabilities + total_equity)) < 1.0
    if not accounting_equation:
        print(f"ERROR: Accounting equation violated: {total_assets} != {total_liabilities} + {total_equity}")
        return False

    # Validation 3: Sum of line items = Total Assets
    asset_line_items = facts[
        (facts['concept'].str.contains('Asset')) &
        (facts['label'] != 'Total Assets')
    ]['value'].sum()

    detail_check = abs(total_assets - asset_line_items) < 1.0
    if not detail_check:
        print(f"WARNING: Asset line items don't sum to total: {total_assets} != {asset_line_items}")

    return accounting_equation

# Usage
filing = Company("AAPL").get_filings(form="10-K").latest()
xbrl = filing.xbrl()
period_key = xbrl.reporting_periods[0]['key']

is_valid = validate_balance_sheet(xbrl, period_key)
print(f"Balance sheet valid: {is_valid}")
```

### Income Statement Validation

Income statement validation is **more complex** due to:
- Variable presentation formats
- Sign convention inconsistencies (some expenses are positive, some negative)
- Different levels of detail across companies

```python
def validate_income_statement(xbrl, period_key):
    """Validate income statement using anchored approach."""

    facts = xbrl.facts.query().by_period_key(period_key).to_dataframe()

    # Anchor points (always present and unambiguous)
    revenue = facts[facts['label'] == 'Revenue']['value'].sum()
    net_income = facts[facts['label'] == 'Net Income']['value'].sum()

    if revenue == 0 or net_income == 0:
        print("ERROR: Missing anchor points (Revenue or Net Income)")
        return False

    # Get all expense items (with sign normalization)
    expense_concepts = [
        'Cost of Revenue',
        'Research and Development Expense',
        'Selling, General and Administrative Expense',
        'Interest Expense',
        'Income Tax Expense'
    ]

    total_expenses = 0
    for concept in expense_concepts:
        expense_facts = facts[facts['label'] == concept]['value']
        if len(expense_facts) > 0:
            expense_value = expense_facts.sum()
            # Normalize to positive (expenses reduce income)
            if expense_value < 0:
                expense_value = abs(expense_value)
            total_expenses += expense_value

    # Check if Revenue - Expenses ≈ Net Income
    # Allow for other income/expense not captured
    calculated_ni = revenue - total_expenses
    difference = abs(calculated_ni - net_income)

    # Difference should be small (other income/expense)
    acceptable_diff = abs(revenue) * 0.1  # 10% tolerance for other items

    if difference > acceptable_diff:
        print(f"WARNING: Income statement doesn't reconcile:")
        print(f"  Revenue: {revenue:,.0f}")
        print(f"  Total Expenses: {total_expenses:,.0f}")
        print(f"  Calculated NI: {calculated_ni:,.0f}")
        print(f"  Reported NI: {net_income:,.0f}")
        print(f"  Difference: {difference:,.0f} (acceptable: {acceptable_diff:,.0f})")
        return False

    return True
```

### Unmapped Tag Detection

Detect XBRL tags that aren't mapped to standard concepts:

```python
def find_unmapped_tags(xbrl, mapper):
    """Find all XBRL tags that don't map to standard concepts."""

    unmapped = []

    # Get all unique concepts
    facts = xbrl.facts.query().to_dataframe()
    concepts = facts['concept'].unique()

    for concept in concepts:
        # Try to map each concept
        label = facts[facts['concept'] == concept]['label'].iloc[0]
        context = {'statement_type': 'Unknown'}

        standard_concept = mapper.map_concept(concept, label, context)

        if standard_concept is None:
            unmapped.append({
                'concept': concept,
                'label': label,
                'occurrences': len(facts[facts['concept'] == concept])
            })

    # Sort by occurrences (most common first)
    unmapped.sort(key=lambda x: x['occurrences'], reverse=True)

    return unmapped

# Usage
from edgar.xbrl.standardization import MappingStore, ConceptMapper

store = MappingStore()
mapper = ConceptMapper(store)

unmapped = find_unmapped_tags(xbrl, mapper)

print(f"Found {len(unmapped)} unmapped tags")
for tag in unmapped[:10]:  # Top 10
    print(f"  {tag['concept']}: '{tag['label']}' ({tag['occurrences']} occurrences)")
```

### Logging Unmapped Tags for Review

Create a log file of unmapped tags with suggested mappings:

```python
import csv
from difflib import get_close_matches

def log_unmapped_tags(xbrl, mapper, output_path='unmapped_tags.csv'):
    """Create CSV log of unmapped tags with suggested standard concepts."""

    unmapped = find_unmapped_tags(xbrl, mapper)

    # Get all standard concepts for matching
    standard_concepts = list(store.mappings.keys())

    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'company_concept',
            'label',
            'occurrences',
            'suggested_mapping',
            'confidence',
            'cik',
            'notes'
        ])

        for tag in unmapped:
            # Find closest matching standard concept
            matches = get_close_matches(
                tag['label'],
                standard_concepts,
                n=1,
                cutoff=0.6
            )

            suggested = matches[0] if matches else "MANUAL_REVIEW_NEEDED"
            confidence = "high" if matches and len(matches[0]) else "low"

            writer.writerow([
                tag['concept'],
                tag['label'],
                tag['occurrences'],
                suggested,
                confidence,
                xbrl.entity_identifier,
                ""  # Manual notes column
            ])

    print(f"Wrote {len(unmapped)} unmapped tags to {output_path}")
    print("Review file and add to concept_mappings.json")

# Usage - process all companies
companies = ["AAPL", "MSFT", "GOOGL", "TSLA"]

for ticker in companies:
    company = Company(ticker)
    filing = company.get_filings(form="10-K").latest()
    xbrl = filing.xbrl()

    log_unmapped_tags(xbrl, mapper, f"unmapped_{ticker}.csv")
```

### Validation Utility Script

Comprehensive validation script for batch processing:

```python
def validate_company_mappings(ticker, form="10-K", years=3):
    """Validate mappings for a company across multiple years."""

    company = Company(ticker)
    filings = company.get_filings(form=form).head(years)

    results = []

    for filing in filings:
        print(f"\nValidating {ticker} {filing.filing_date}...")

        try:
            xbrl = filing.xbrl()
            period_key = xbrl.reporting_periods[0]['key']

            # Run validations
            bs_valid = validate_balance_sheet(xbrl, period_key)
            is_valid = validate_income_statement(xbrl, period_key)
            unmapped = find_unmapped_tags(xbrl, mapper)

            result = {
                'ticker': ticker,
                'filing_date': filing.filing_date,
                'balance_sheet_valid': bs_valid,
                'income_statement_valid': is_valid,
                'unmapped_count': len(unmapped),
                'total_concepts': len(xbrl.facts.query().to_dataframe()['concept'].unique())
            }

            results.append(result)

            print(f"  Balance Sheet: {'✓' if bs_valid else '✗'}")
            print(f"  Income Statement: {'✓' if is_valid else '✗'}")
            print(f"  Unmapped: {len(unmapped)}")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                'ticker': ticker,
                'filing_date': filing.filing_date,
                'error': str(e)
            })

    return results

# Batch validation
companies = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"]
all_results = []

for ticker in companies:
    results = validate_company_mappings(ticker)
    all_results.extend(results)

# Summary
valid_count = sum(1 for r in all_results if r.get('balance_sheet_valid', False))
print(f"\nOverall: {valid_count}/{len(all_results)} filings validated successfully")
```

---

## 8. CSV Workflow

While EdgarTools currently uses JSON for mappings, many users prefer CSV for editing. This section provides utilities for CSV-based workflows.

**Note**: Native CSV support is planned for v4.29.0/v4.30.0.

### Why CSV for Mapping Management?

**Advantages**:
- **Excel editing**: Use familiar spreadsheet tools
- **Duplicate detection**: Sort columns to find duplicates easily
- **Filtering**: Quick filtering by standard concept or company
- **Validation**: Formulas can check for consistency
- **Collaboration**: Easier for non-technical team members

### CSV Format Specification

**Standard Format**:
```csv
standard_concept,company_concept,company_cik,priority,notes
Revenue,us-gaap:Revenue,,1,Core GAAP concept
Revenue,us-gaap:Revenues,,1,Alternative spelling
Automotive Revenue,tsla:AutomotiveRevenue,1318605,2,Tesla-specific
Automotive Revenue,tsla:VehicleRevenue,1318605,2,Alternative Tesla tag
```

**Columns**:
- `standard_concept`: The standardized label (e.g., "Revenue")
- `company_concept`: The XBRL tag (e.g., "us-gaap:Revenue")
- `company_cik`: Optional CIK for company-specific mappings (empty for core)
- `priority`: 1=core, 2=company-specific (optional, for reference)
- `notes`: Explanation, context, or validation notes

### Export Mappings to CSV

```python
import csv
from edgar.xbrl.standardization import MappingStore

def export_mappings_to_csv(store: MappingStore, output_path: str):
    """Export MappingStore to CSV format for editing."""

    rows = []

    # Export core mappings (priority 1)
    for standard_concept, company_concepts in store.mappings.items():
        for company_concept in company_concepts:
            rows.append({
                'standard_concept': standard_concept,
                'company_concept': company_concept,
                'company_cik': '',
                'priority': 1,
                'notes': 'Core mapping'
            })

    # Export company-specific mappings (priority 2)
    for entity_id, company_data in store.company_mappings.items():
        cik = company_data.get('metadata', {}).get('cik', '')
        concept_mappings = company_data.get('concept_mappings', {})

        for standard_concept, company_concepts in concept_mappings.items():
            for company_concept in company_concepts:
                rows.append({
                    'standard_concept': standard_concept,
                    'company_concept': company_concept,
                    'company_cik': cik,
                    'priority': 2,
                    'notes': f'Company-specific: {entity_id}'
                })

    # Write to CSV
    with open(output_path, 'w', newline='') as f:
        fieldnames = ['standard_concept', 'company_concept', 'company_cik', 'priority', 'notes']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} mappings to {output_path}")

# Usage
store = MappingStore()
export_mappings_to_csv(store, 'all_mappings.csv')
```

### Import Mappings from CSV

```python
import csv
from collections import defaultdict
import json

def import_mappings_from_csv(csv_path: str):
    """Import mappings from CSV and generate JSON files."""

    core_mappings = defaultdict(list)
    company_mappings = defaultdict(lambda: defaultdict(list))

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)

        for row in reader:
            standard_concept = row['standard_concept']
            company_concept = row['company_concept']
            cik = row.get('company_cik', '').strip()

            if cik:
                # Company-specific mapping
                company_mappings[cik][standard_concept].append(company_concept)
            else:
                # Core mapping
                core_mappings[standard_concept].append(company_concept)

    # Save core mappings
    with open('concept_mappings.json', 'w') as f:
        json.dump(dict(core_mappings), f, indent=2)
    print(f"Saved core mappings: {len(core_mappings)} concepts")

    # Save company-specific mappings
    for cik, mappings in company_mappings.items():
        # Find ticker from CIK (simplified - you'd need a CIK-to-ticker lookup)
        ticker = f"cik{cik}"  # Placeholder

        company_data = {
            "metadata": {
                "entity_identifier": ticker,
                "cik": cik,
                "priority": "high",
                "created_date": "2025-11-19"
            },
            "concept_mappings": dict(mappings)
        }

        filename = f"{ticker}_mappings.json"
        with open(filename, 'w') as f:
            json.dump(company_data, f, indent=2)
        print(f"Saved company mappings: {filename}")

# Usage
import_mappings_from_csv('all_mappings.csv')
```

### Excel Editing Workflow

**Step 1: Export to CSV**
```python
from edgar.xbrl.standardization import MappingStore

store = MappingStore()
export_mappings_to_csv(store, 'edgartools_mappings.csv')
```

**Step 2: Open in Excel**
- Open `edgartools_mappings.csv` in Excel or Google Sheets
- Use Excel features:
  - **Sort** by `standard_concept` to group related mappings
  - **Filter** by `company_cik` to see company-specific mappings
  - **Conditional Formatting** to highlight duplicates
  - **Find & Replace** for bulk updates

**Step 3: Duplicate Detection in Excel**

Formula in column F (next to your data):
```excel
=COUNTIFS($B:$B,B2,$A:$A,A2)>1
```

This highlights if the same `company_concept` maps to the same `standard_concept` multiple times.

**Step 4: Validation in Excel**

Add a validation column with this formula:
```excel
=IF(ISBLANK(B2), "Missing concept",
    IF(ISBLANK(A2), "Missing label",
       IF(AND(C2<>"", NOT(ISNUMBER(C2))), "Invalid CIK",
          "OK")))
```

**Step 5: Import Back to JSON**
```python
import_mappings_from_csv('edgartools_mappings.csv')
```

### Single File vs Multiple Files

Two approaches for managing 200+ companies:

#### Approach 1: Single CSV File (Recommended for Excel Users)

**Structure**:
```csv
standard_concept,company_concept,company_cik,ticker,notes
Revenue,us-gaap:Revenue,,,Core GAAP
Automotive Revenue,tsla:AutomotiveRevenue,1318605,TSLA,Tesla-specific
Energy Revenue,tsla:EnergyRevenue,1318605,TSLA,Tesla energy
Product Revenue,msft:ProductRevenue,789019,MSFT,Microsoft
```

**Advantages**:
- Easy to search across all companies
- Single source of truth
- Easy duplicate detection
- Better for bulk operations

**Disadvantages**:
- Large file size (200 companies = 10,000+ rows)
- Merge conflicts in version control
- Slower to load

#### Approach 2: Multiple JSON Files (Current EdgarTools Approach)

**Structure**:
```
company_mappings/
  aapl_mappings.json
  msft_mappings.json
  tsla_mappings.json
  googl_mappings.json
  ...
```

**Advantages**:
- Modular (edit one company at a time)
- Better for version control (fewer merge conflicts)
- Faster loading (only load relevant companies)
- Clear ownership (one file per company)

**Disadvantages**:
- Harder to find duplicates across companies
- More files to manage
- Need tooling to search across all files

#### Hybrid Approach (Best of Both Worlds)

Use CSV as master source, generate JSON files:

```python
def csv_to_company_json_files(csv_path: str, output_dir: str):
    """Convert single CSV to multiple company JSON files."""

    import csv
    import json
    from pathlib import Path
    from collections import defaultdict

    Path(output_dir).mkdir(exist_ok=True)

    # Group by CIK
    company_data = defaultdict(lambda: {
        'metadata': {},
        'concept_mappings': defaultdict(list)
    })

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)

        for row in reader:
            cik = row.get('company_cik', '').strip()
            if not cik:
                continue  # Skip core mappings

            ticker = row.get('ticker', f'cik{cik}').lower()

            # Set metadata
            if not company_data[ticker]['metadata']:
                company_data[ticker]['metadata'] = {
                    'entity_identifier': ticker,
                    'cik': cik,
                    'priority': 'high'
                }

            # Add mapping
            standard = row['standard_concept']
            concept = row['company_concept']
            company_data[ticker]['concept_mappings'][standard].append(concept)

    # Write files
    for ticker, data in company_data.items():
        # Convert defaultdict to regular dict
        data['concept_mappings'] = dict(data['concept_mappings'])

        filename = Path(output_dir) / f"{ticker}_mappings.json"
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        concept_count = len(data['concept_mappings'])
        print(f"Created {filename} with {concept_count} concepts")

# Usage
csv_to_company_json_files(
    'master_mappings.csv',
    'company_mappings/'
)
```

**Recommended Workflow for 200+ Companies**:
1. Maintain master CSV file: `edgartools_master_mappings.csv`
2. Edit in Excel (easy duplicate detection, filtering)
3. Run conversion script to generate JSON files
4. Deploy JSON files to package directory
5. Version control both CSV (master) and JSON (generated)

---

## 9. Real-World Examples

This section explains existing company mapping files with detailed annotations.

### Example 1: Tesla (Automotive + Energy)

Tesla has a complex revenue structure combining automotive sales, leasing, and energy generation/storage.

**File**: `company_mappings/tsla_mappings.json`

```json
{
  "metadata": {
    "entity_identifier": "tsla",
    "company_name": "Tesla, Inc.",
    "cik": "1318605",
    "priority": "high",
    "created_date": "2024-06-25",
    "last_updated": "2024-06-25",
    "description": "Tesla-specific concept mappings to handle automotive, energy, and service revenue streams"
  },

  "concept_mappings": {
    "Automotive Revenue": [
      "tsla:AutomotiveRevenue",
      "tsla:AutomotiveSales",
      "tsla:VehicleRevenue"
    ],

    "Automotive Leasing Revenue": [
      "tsla:AutomotiveLeasing",
      "tsla:AutomotiveLeasingRevenue",
      "tsla:VehicleLeasingRevenue"
    ],

    "Energy Revenue": [
      "tsla:EnergyGenerationAndStorageRevenue",
      "tsla:EnergyRevenue",
      "tsla:SolarRevenue",
      "tsla:EnergyStorageRevenue"
    ],

    "Service Revenue": [
      "tsla:ServicesAndOtherRevenue",
      "tsla:ServiceRevenue",
      "tsla:SuperchargerRevenue"
    ]
  },

  "hierarchy_rules": {
    "Revenue": {
      "children": [
        "Automotive Revenue",
        "Energy Revenue",
        "Service Revenue"
      ]
    },
    "Automotive Revenue": {
      "children": [
        "Automotive Leasing Revenue"
      ]
    }
  },

  "business_context": {
    "primary_revenue_streams": ["automotive", "energy", "services"],
    "revenue_model": "product_and_service",
    "key_metrics": ["vehicle_deliveries", "energy_deployments"],
    "industry": "automotive_technology"
  }
}
```

**Key Design Decisions**:

1. **Granular Revenue Breakdown**:
   - Separate automotive sales from leasing (different economics)
   - Distinguish energy from automotive (different growth drivers)
   - Services as distinct category (recurring revenue)

2. **Hierarchy Rules**:
   - `Revenue` is parent of three main streams
   - `Automotive Revenue` contains `Automotive Leasing Revenue` as child
   - This ensures proper nesting in financial statements

3. **Multiple Tag Variations**:
   - Tesla has changed tag names over time (`AutomotiveRevenue` vs `AutomotiveSales`)
   - All variations map to same standard concept for consistency

**Usage Example**:
```python
from edgar import Company

tesla = Company("TSLA")
filing = tesla.get_filings(form="10-K").latest()
xbrl = filing.xbrl()

# Get standardized income statement
income = xbrl.statements.income_statement()

# Tesla-specific revenue line items will appear as:
# - Automotive Revenue (instead of generic "Revenue")
# - Automotive Leasing Revenue
# - Energy Revenue
# - Service Revenue
```

### Example 2: Microsoft (Technology Platform)

Microsoft has platform-based revenue (Azure, Office 365, Dynamics) requiring specialized mapping.

**File**: `company_mappings/msft_mappings.json`

```json
{
  "entity_info": {
    "name": "Microsoft Corporation",
    "cik": "0000789019",
    "ticker": "MSFT",
    "description": "Microsoft-specific concept mappings for unique business terminology"
  },

  "concept_mappings": {
    "_comment_msft_revenue": "Microsoft uses specific revenue categorization that differs from standard tech companies",

    "Product Revenue": [
      "msft:ProductRevenue",
      "msft:WindowsCommercialRevenue",
      "msft:WindowsConsumerRevenue",
      "msft:OfficeCommercialRevenue"
    ],

    "Service Revenue": [
      "msft:ServiceRevenue",
      "msft:CloudServicesRevenue",
      "msft:ConsultingServicesRevenue"
    ],

    "Subscription Revenue": [
      "msft:Office365CommercialRevenue",
      "msft:Office365ConsumerRevenue",
      "msft:DynamicsRevenue"
    ],

    "Platform Revenue": [
      "msft:AzureRevenue",
      "msft:XboxContentAndServicesRevenue"
    ],

    "_comment_msft_expenses": "Microsoft has unique expense categorizations for sales and marketing vs G&A",

    "Sales and Marketing Expense": [
      "msft:SalesAndMarketingExpense",
      "msft:AdvertisingAndPromotionExpense"
    ],

    "Technical Support Expense": [
      "msft:TechnicalSupportExpense",
      "msft:CustomerSupportExpense"
    ]
  },

  "hierarchy_rules": {
    "_comment": "Rules for handling Microsoft-specific hierarchical relationships",

    "revenue_hierarchy": {
      "parent": "Revenue",
      "children": ["Product Revenue", "Service Revenue", "Subscription Revenue", "Platform Revenue"],
      "calculation_rule": "sum"
    },

    "expense_hierarchy": {
      "parent": "Operating Expenses",
      "children": ["Sales and Marketing Expense", "Technical Support Expense"],
      "calculation_rule": "sum"
    }
  }
}
```

**Key Design Decisions**:

1. **Four Revenue Categories**:
   - **Product**: Traditional software sales (Windows, Office perpetual licenses)
   - **Service**: Consulting, support services
   - **Subscription**: Recurring revenue (Office 365, Dynamics)
   - **Platform**: Cloud platforms (Azure, Xbox services)

2. **Expense Granularity**:
   - Separates sales/marketing from technical support
   - Reflects Microsoft's investment in customer success teams

3. **Hierarchy Rules with Calculation**:
   - Explicit `calculation_rule: sum` indicates children should sum to parent
   - Validation can check this relationship

**Usage Example**:
```python
msft = Company("MSFT")
filing = msft.get_filings(form="10-K").latest()
xbrl = filing.xbrl()

# Analyze revenue mix
facts = xbrl.facts.query().by_statement_type("IncomeStatement").to_dataframe()

revenue_breakdown = facts[facts['label'].str.contains('Revenue')][['label', 'value']]
print(revenue_breakdown)

# Output:
# label                    value
# Product Revenue          75,000,000,000
# Service Revenue          25,000,000,000
# Subscription Revenue     60,000,000,000
# Platform Revenue         40,000,000,000
# Revenue                  200,000,000,000
```

### Example 3: Berkshire Hathaway (Conglomerate)

Berkshire Hathaway is a diversified holding company with insurance, utilities, railroads, and manufacturing.

**File**: `company_mappings/brka_mappings.json`

```json
{
  "concept_mappings": {
    "Sales and Service Revenue": [
      "brka:SalesAndServiceRevenue"
    ]
  },

  "hierarchy_rules": {
    "Revenue": {
      "components": [
        "Sales and Service Revenue",
        "Operating Lease Revenue"
      ],
      "description": "Total revenue comprises sales/service revenue and operating lease income for holding company"
    }
  },

  "business_context": {
    "entity_type": "holding_company",
    "industry": "diversified_conglomerate",
    "description": "Berkshire Hathaway operates diverse businesses including insurance, utilities, railroads, and manufacturing"
  }
}
```

**Key Design Decisions**:

1. **Minimal Customization**:
   - Berkshire uses mostly standard US-GAAP tags
   - Only needs mapping for unique revenue categorization

2. **Lease Revenue Separation**:
   - Operating lease revenue (equipment leasing subsidiaries)
   - Separated from core sales/service revenue

3. **Business Context**:
   - Documents the holding company structure
   - Helps interpreters understand diverse revenue sources

**Why So Simple?**:
- Berkshire's filings primarily use standard US-GAAP taxonomy
- Conglomerates often don't need extensive custom tags
- Industry-specific tags are used by individual subsidiaries (not parent)

### Example 4: Industrial Company Template

For users managing 200+ industrial companies, here's a template:

```json
{
  "metadata": {
    "entity_identifier": "ticker",
    "company_name": "Company Name",
    "cik": "0000000000",
    "priority": "medium",
    "created_date": "2025-11-19",
    "last_updated": "2025-11-19",
    "description": "Industrial company with manufacturing operations",
    "industry": "industrial_manufacturing"
  },

  "concept_mappings": {
    "_comment": "Common industrial company customizations",

    "Product Sales": [
      "company:ProductSales",
      "company:ManufacturedGoodsSales"
    ],

    "Raw Materials Inventory": [
      "company:RawMaterialsInventory"
    ],

    "Work in Process Inventory": [
      "company:WorkInProcessInventory"
    ],

    "Finished Goods Inventory": [
      "company:FinishedGoodsInventory"
    ],

    "Manufacturing Overhead": [
      "company:ManufacturingOverhead",
      "company:FactoryOverhead"
    ]
  },

  "hierarchy_rules": {
    "Inventory": {
      "children": [
        "Raw Materials Inventory",
        "Work in Process Inventory",
        "Finished Goods Inventory"
      ],
      "calculation_rule": "sum",
      "description": "Manufacturing inventory breakdown"
    }
  },

  "business_context": {
    "primary_revenue_streams": ["product_sales"],
    "revenue_model": "manufacturing",
    "key_metrics": ["inventory_turnover", "production_efficiency"],
    "industry": "industrial_manufacturing",
    "notes": "Focus on inventory management and cost of goods sold structure"
  }
}
```

**Adaptation for Your Companies**:
1. Copy this template
2. Replace `company:` prefix with actual company prefix
3. Add industry-specific concepts (automotive parts, chemicals, etc.)
4. Customize inventory structure based on business model

---

## 10. Future Enhancements

This section outlines the roadmap for standardization improvements based on user feedback.

### Version 4.30.0 (Next 1-2 Months)

**Focus**: Configuration and CSV Support

#### 1. Configurable Mapping Paths

**Problem Solved**: Users can maintain mappings outside package directory.

**Implementation**:

```python
# Environment variable configuration
import os
os.environ['EDGAR_CORE_MAPPINGS'] = '/path/to/my/concept_mappings.json'
os.environ['EDGAR_COMPANY_MAPPINGS_DIR'] = '/path/to/my/company_mappings/'

# Library loads from custom paths
from edgar.xbrl.standardization import MappingStore
store = MappingStore()  # Automatically uses env var paths
```

**Alternative: Constructor parameters**:

```python
store = MappingStore(
    core_mappings_path='/path/to/concept_mappings.json',
    company_mappings_dir='/path/to/company_mappings/'
)
```

**Benefits**:
- Separate version control for mappings
- Mappings survive package upgrades
- Multiple mapping sets for different use cases

#### 2. Native CSV Format Support

**Problem Solved**: Excel-based workflows without conversion scripts.

**Implementation**:

```python
# Auto-detect format from extension
store = MappingStore(core_mappings_path='my_mappings.csv')

# Explicit format specification
store = MappingStore(
    core_mappings_path='my_mappings.txt',
    format='csv'
)
```

**CSV Format**:
```csv
standard_concept,company_concept,notes
Revenue,us-gaap:Revenue,Core GAAP tag
Revenue,us-gaap:Revenues,Alternative spelling
```

**Benefits**:
- No conversion scripts needed
- Direct Excel editing
- Easier duplicate detection

#### 3. Enhanced Validation Tools

**Problem Solved**: Automated mapping quality checks.

**Implementation**:

```python
from edgar.xbrl.standardization import MappingValidator

validator = MappingValidator(store)

# Validate balance sheet balancing
report = validator.validate_company(
    ticker="AAPL",
    form="10-K",
    years=3
)

print(report.summary())
# Output:
# ✓ Balance Sheet: 3/3 periods balanced
# ✓ Income Statement: 3/3 periods validated
# ⚠ Unmapped tags: 12 concepts need mapping
```

**Features**:
- Batch validation across multiple companies
- Balance sheet equation checking
- Income statement reconciliation
- Coverage reports (% of concepts mapped)

### Version 4.31.0 (2-3 Months)

**Focus**: CIK-Based Identification

#### 1. CIK as Primary Identifier

**Problem Solved**: Handle multi-ticker companies (GOOG/GOOGL, HEI.A/HEI.B).

**Implementation**:

```json
{
  "metadata": {
    "entity_identifier": "0001652044",
    "cik": "0001652044",
    "tickers": ["GOOG", "GOOGL"],
    "primary_ticker": "GOOG",
    "company_name": "Alphabet Inc."
  }
}
```

**File Naming**:
```
company_mappings/
  cik0001652044_mappings.json  # CIK-based naming
  # OR legacy support:
  goog_mappings.json  # Ticker-based naming (still supported)
```

#### 2. Dual Lookup Support

**During Transition**: Support both ticker and CIK lookups.

```python
# Both work
store.get_company_mappings(ticker="GOOG")
store.get_company_mappings(cik="0001652044")
```

#### 3. Migration Tool

**Help users migrate** from ticker-based to CIK-based files.

```python
from edgar.xbrl.standardization import migrate_to_cik

# Migrate all ticker-based files to CIK-based
migrate_to_cik(
    input_dir='company_mappings/',
    output_dir='company_mappings_cik/',
    cik_lookup_file='ticker_to_cik.csv'
)
```

### Version 5.0.0 (Major Release)

**Focus**: Advanced Features and ML Integration

#### 1. JSON-Loaded StandardConcept

**Problem Solved**: StandardConcept enum becomes fully data-driven.

**Current**:
```python
# Enum is hardcoded in Python
class StandardConcept(str, Enum):
    REVENUE = "Revenue"
    TOTAL_ASSETS = "Total Assets"
```

**Future**:
```python
# Enum loaded from JSON at runtime
StandardConcept = load_concepts_from_json('standard_concepts.json')

# Users can extend without touching Python code
```

#### 2. Concept Marketplace/Repository

**Problem Solved**: Share mappings across community.

**Vision**:
```python
from edgar.xbrl.standardization import ConceptMarketplace

marketplace = ConceptMarketplace()

# Download community mappings
marketplace.install('industrial-companies-pack')
marketplace.install('tech-companies-pack')

# Share your mappings
marketplace.publish(
    'my-custom-mappings',
    description='Custom mappings for 200+ industrial firms',
    companies=['AAPL', 'MSFT', ...],
    license='MIT'
)
```

**Features**:
- Community-contributed mappings
- Rating and review system
- Automatic updates
- Industry-specific packs

#### 3. ML-Based Concept Inference

**Problem Solved**: Automatically suggest mappings for unmapped tags.

**Implementation**:

```python
from edgar.xbrl.standardization import MLConceptMapper

ml_mapper = MLConceptMapper()

# Train on existing mappings
ml_mapper.train(store.mappings)

# Suggest mappings for unmapped concepts
suggestion = ml_mapper.suggest(
    concept='company:CustomRevenueConcept',
    label='Sales of Manufactured Goods',
    context={'statement_type': 'IncomeStatement'}
)

print(suggestion)
# Output:
# Suggested: "Product Revenue"
# Confidence: 0.89
# Similar concepts: ["Revenue", "Product Sales", "Sales"]
```

**Features**:
- Learn from existing mappings
- Context-aware suggestions
- Confidence scoring
- Interactive review workflow

#### 4. Advanced Validation Framework

**Problem Solved**: Comprehensive statement validation.

```python
from edgar.xbrl.standardization import ValidationFramework

framework = ValidationFramework(store)

# Define custom validation rules
@framework.rule(statement='BalanceSheet', severity='error')
def validate_accounting_equation(facts):
    assets = facts.get('Total Assets')
    liabilities = facts.get('Total Liabilities')
    equity = facts.get("Total Stockholders' Equity")

    if abs(assets - (liabilities + equity)) > 1.0:
        return ValidationError("Accounting equation violated")
    return None

# Run validation
results = framework.validate_company('AAPL', years=10)
results.generate_report('validation_report.html')
```

### Timeline Summary

| Feature | Version | Timeline | Status |
|---------|---------|----------|--------|
| Configurable paths | v4.30.0 | 1-2 months | Planned |
| Native CSV support | v4.30.0 | 1-2 months | Planned |
| Enhanced validation | v4.30.0 | 1-2 months | Planned |
| CIK-based identification | v4.31.0 | 2-3 months | Planned |
| Dual lookup support | v4.31.0 | 2-3 months | Planned |
| Migration tool | v4.31.0 | 2-3 months | Planned |
| JSON StandardConcept | v5.0.0 | 6-12 months | Under consideration |
| Concept marketplace | v5.0.0 | 6-12 months | Under consideration |
| ML concept inference | v5.0.0 | 6-12 months | Research phase |

### Providing Feedback

Your feedback shapes these enhancements. To contribute:

1. **GitHub Issues**: Comment on issue #494 or create new issues
2. **Feature Requests**: Use the feature request template
3. **User Stories**: Share your specific use cases
4. **Beta Testing**: Volunteer to test pre-release versions

**Contact**:
- GitHub: https://github.com/dgunning/edgartools/issues/494
- Discussions: https://github.com/dgunning/edgartools/discussions

---

## Summary and Quick Reference

### When to Customize Standardization

✅ **Yes, customize when**:
- Managing 200+ companies with diverse taxonomies
- Industry-specific valuations (industrial, automotive, tech)
- Building models requiring consistent data structure
- Statement balancing is critical to your workflow

❌ **No, use defaults when**:
- Analyzing 1-10 companies
- Standard US-GAAP concepts are sufficient
- Quick analysis or exploration
- Don't need custom taxonomy support

### Quick Decision Tree

```
Do you analyze 200+ companies?
├─ Yes → Use custom company-specific mappings (Section 4)
│        └─ CSV workflow for easier management (Section 8)
└─ No → Do you need industry-specific concepts?
         ├─ Yes → Use custom core mappings (Section 3)
         └─ No → Use default StandardConcept mappings
```

### Essential Resources

| Task | Section | Key File |
|------|---------|----------|
| Understand architecture | Section 2 | `core.py` |
| Add core mappings | Section 3 | `concept_mappings.json` |
| Create company mappings | Section 4 | `{ticker}_mappings.json` |
| Resolve ambiguous tags | Section 5 | Your context analysis |
| Work around limitations | Section 6 | Installation scripts |
| Validate mappings | Section 7 | Validation utilities |
| Use CSV workflow | Section 8 | CSV utilities |
| Learn from examples | Section 9 | Tesla, Microsoft files |

### Key Concepts Clarified

| Concept | What It Is | What It's NOT |
|---------|------------|---------------|
| **StandardConcept Enum** | IDE convenience, type safety | NOT the mapping data |
| **JSON Mappings** | Source of truth for mappings | NOT just for reference |
| **Priority System** | Conflict resolution | NOT just ordering |
| **CIK** | Stable company identifier | NOT ticker (which changes) |
| **Context** | Ambiguity resolution | NOT just metadata |

### Contact and Support

- **GitHub Issue**: #494
- **Documentation**: This guide
- **Examples**: Section 9
- **Roadmap**: Section 10

---

**Document Version**: 1.0
**Last Updated**: 2025-11-19
**EdgarTools Version**: 4.29.0+
**Contributors**: @dgunning, @mpreiss9, EdgarTools community
