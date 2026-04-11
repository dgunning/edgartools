# Evolutionary Normalization Engine (ENE) Developer Guide

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Core Concepts](#3-core-concepts)
4. [Component Deep Dives](#4-component-deep-dives)
5. [Configuration Reference](#5-configuration-reference)
6. [Working Examples](#6-working-examples)
7. [Troubleshooting & FAQ](#7-troubleshooting--faq)
8. [Appendices](#8-appendices)

---

## 1. Executive Summary

### What is ENE?

The **Evolutionary Normalization Engine (ENE)** is EdgarTools' modular framework for extracting standardized financial metrics from SEC XBRL filings. It replaces monolithic extraction code with a strategy-based architecture that adapts to different company types.

### Why ENE Exists

XBRL extraction is deceptively complex. Companies in different industries report the same metrics using vastly different XBRL concepts:

- **Banks** report `ShortTermBorrowings` which may or may not include repos
- **Tech companies** use standard `DebtCurrent` concepts
- **REITs** report property-focused metrics instead of traditional P&L

Before ENE, extraction logic was a single large function with nested if-statements for each special case. This approach:
- Was unmaintainable as edge cases accumulated
- Couldn't track which extraction logic produced which results
- Made it impossible to test changes against similar companies

### Key Problems ENE Solves

| Problem | ENE Solution |
|---------|--------------|
| Monolithic extraction code | Modular strategies with single responsibility |
| No provenance tracking | Strategy fingerprints record exact algorithm used |
| Company-specific hacks | Archetype-based classification routes to appropriate strategy |
| Regression risk | Cohort Reactor tests changes across similar companies |
| Configuration chaos | Centralized `companies.yaml` with clear structure |

### 5-Minute Quick Start

```python
# 1. Classify a company into an archetype
from edgar.xbrl.standardization.archetypes import classify_company

archetype, sub_archetype = classify_company(ticker='JPM', sic='6020')
print(f"JPM: {archetype.value} / {sub_archetype.value}")
# Output: JPM: inverted_financial / hybrid

# 2. Get the appropriate strategy
from edgar.xbrl.standardization.strategies import get_strategy

strategy = get_strategy('hybrid_debt', params={'ticker': 'JPM'})
print(f"Strategy: {strategy.strategy_name}, fingerprint: {strategy.fingerprint}")

# 3. Execute extraction (with XBRL data)
# result = strategy.extract(xbrl, facts_df, mode=ExtractionMode.GAAP)

# 4. Record results to the ledger
from edgar.xbrl.standardization.ledger import ExperimentLedger, ExtractionRun

ledger = ExperimentLedger()
run = ExtractionRun(
    ticker='JPM', metric='ShortTermDebt', fiscal_period='2024-Q4',
    form_type='10-K', archetype='B', sub_archetype='hybrid',
    strategy_name='hybrid_debt', strategy_fingerprint=strategy.fingerprint,
    extracted_value=15_000_000_000, reference_value=15_500_000_000,
)
ledger.record_run(run)
```

---

## 2. Architecture Overview

### System Diagram

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │                      ENE Architecture                        │
                    └─────────────────────────────────────────────────────────────┘

                                        ┌───────────────┐
                                        │  SEC Filing   │
                                        │   (10-K/Q)    │
                                        └───────┬───────┘
                                                │
                                                ▼
                                        ┌───────────────┐
                                        │  XBRL Parser  │
                                        │   (xbrl.py)   │
                                        └───────┬───────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    │                           │                           │
                    ▼                           ▼                           ▼
            ┌───────────────┐           ┌───────────────┐           ┌───────────────┐
            │   Archetype   │           │   Companies   │           │    Facts      │
            │  Classifier   │           │    Config     │           │   DataFrame   │
            │               │           │  (YAML)       │           │               │
            └───────┬───────┘           └───────┬───────┘           └───────┬───────┘
                    │                           │                           │
                    └───────────────┬───────────┘                           │
                                    │                                       │
                                    ▼                                       │
                            ┌───────────────┐                               │
                            │   Strategy    │◄──────────────────────────────┘
                            │   Adapter     │
                            └───────┬───────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│  Commercial   │           │    Hybrid     │           │    Dealer     │
│    Strategy   │           │   Strategy    │           │   Strategy    │
└───────┬───────┘           └───────┬───────┘           └───────┬───────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
                            ┌───────────────┐
                            │   Strategy    │
                            │    Result     │
                            └───────┬───────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
            ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
            │   Experiment  │ │    Cohort     │ │    Golden     │
            │    Ledger     │ │   Reactor     │ │   Masters     │
            └───────────────┘ └───────────────┘ └───────────────┘
```

### Data Flow Summary

```
Filing → XBRL Parser → Facts DataFrame
                           ↓
              ┌────────────┴────────────┐
              │   Archetype Classifier  │ ← SIC/GICS/Config
              └────────────┬────────────┘
                           ↓
              ┌────────────┴────────────┐
              │    Strategy Selection   │ ← Based on archetype
              └────────────┬────────────┘
                           ↓
              ┌────────────┴────────────┐
              │   Strategy Execution    │ ← Extract with params
              └────────────┬────────────┘
                           ↓
              ┌────────────┴────────────┐
              │    StrategyResult       │ → value, concept, method, notes
              └────────────┬────────────┘
                           ↓
              ┌────────────┴────────────┐
              │   Experiment Ledger     │ → SQLite persistence
              └─────────────────────────┘
```

### Directory Structure

```
edgar/xbrl/standardization/
├── __init__.py                    # Package exports
├── README.md                      # Package overview
│
├── archetypes/                    # Archetype classification system
│   ├── __init__.py               # Public exports
│   ├── definitions.py            # AccountingArchetype enum, SIC/GICS mappings
│   └── classifier.py             # classify_company(), detect_bank_sub_archetype()
│
├── strategies/                    # Modular extraction strategies
│   ├── __init__.py               # Strategy registry, get_strategy()
│   ├── base.py                   # BaseStrategy ABC, StrategyResult, FactHelper
│   └── debt/                     # ShortTermDebt strategies
│       ├── __init__.py           # Exports all debt strategies
│       ├── commercial_debt.py    # WFC, USB, PNC
│       ├── dealer_debt.py        # GS, MS
│       ├── custodial_debt.py     # BK, STT
│       ├── hybrid_debt.py        # JPM, BAC, C
│       └── standard_debt.py      # Non-bank companies
│
├── ledger/                        # Experiment tracking
│   ├── __init__.py               # Public exports
│   └── schema.py                 # ExtractionRun, GoldenMaster, ExperimentLedger
│
├── reactor/                       # Cohort testing
│   ├── __init__.py               # Public exports
│   └── cohort_reactor.py         # CohortReactor, CohortDefinition
│
├── config/                        # Configuration files
│   └── companies.yaml            # Company-specific config and cohorts
│
├── industry_logic/                # Legacy interface adapter
│   ├── __init__.py               # ExtractedMetric, ExtractionMethod
│   └── strategy_adapter.py       # Bridges new strategies to old interface
│
└── company_mappings/              # Runtime data
    └── experiment_ledger.db      # SQLite database (auto-created)
```

---

## 3. Core Concepts

### 3.1 Accounting Archetypes (A-E)

ENE classifies companies into five **accounting archetypes** based on their fundamental business models and how they report financials:

| Archetype | Name                    | Coverage | Examples        | Key Characteristic                                |
| --------- | ----------------------- | -------- | --------------- | ------------------------------------------------- |
| **A**     | Standard Industrial     | ~60%     | AAPL, AMZN, WMT | Traditional P&L with COGS, SG&A, Operating Income |
| **B**     | Inverted Financial      | ~8%      | JPM, GS, WFC    | Interest income is primary revenue; no COGS       |
| **C**     | Intangible Digital      | ~15%     | MSFT, META, PFE | High intangibles, R&D capitalization              |
| **D**     | Asset Passthrough       | ~5%      | O, SPG          | REITs; FFO instead of EPS                         |
| **E**     | Probabilistic Liability | ~5%      | BRK, MET        | Insurance; underwriting income, loss reserves     |

**Why Archetypes Matter:**

Different archetypes require different extraction logic. For example, `ShortTermDebt`:

- **Archetype A (Standard)**: Simply read `DebtCurrent` or `ShortTermBorrowings`
- **Archetype B (Banks)**: Must handle repos, trading liabilities, and bank-specific concepts
- **Archetype D (REITs)**: May have unique mortgage-backed debt structures

```python
from edgar.xbrl.standardization.archetypes import AccountingArchetype, ARCHETYPE_DEFINITIONS

# Get archetype definition
defn = ARCHETYPE_DEFINITIONS[AccountingArchetype.B]
print(f"Name: {defn['name']}")           # "Inverted Financial"
print(f"Coverage: {defn['coverage_pct']}%")  # 8%
print(f"Excluded metrics: {defn['excluded_metrics']}")  # ['COGS', 'SGA', 'OperatingIncome', 'Capex']
```

**Classification Priority:**
1. Config override (`archetype_override: true` in companies.yaml)
2. GICS sector/group code
3. SIC code ranges
4. Default to Archetype A

### 3.2 Bank Sub-Archetypes

Banks (Archetype B) are further classified into **sub-archetypes** based on their operational characteristics:

| Sub-Archetype | Banks | Key Traits | Strategy |
|---------------|-------|------------|----------|
| **Commercial** | WFC, USB, PNC | High loan book, repos bundled in STB | `commercial_debt` |
| **Dealer** | GS, MS | High trading assets, uses UnsecuredSTB | `dealer_debt` |
| **Custodial** | BK, STT | Minimal STB, repos as financing | `custodial_debt` |
| **Hybrid** | JPM, BAC, C | Both commercial and dealer traits | `hybrid_debt` |
| **Regional** | Small banks | Simpler structure, like commercial | `commercial_debt` |

**Detection Logic:**

```python
from edgar.xbrl.standardization.archetypes import detect_bank_sub_archetype

# Detection uses balance sheet ratios:
# - trading_ratio > 0.15 → Dealer
# - stb < 1% of assets → Custodial
# - trading_ratio > 0.05 AND loan_ratio > 0.20 → Hybrid
# - loan_ratio > 0.30 → Commercial
# - Default → Regional

sub_archetype = detect_bank_sub_archetype(facts_df, ticker='JPM')
```

### 3.3 Strategies

A **Strategy** is an atomic, reusable extraction algorithm that:
- Extracts a single metric using a specific approach
- Is parameterized for tunable behavior
- Has a fingerprint for tracking

```python
from edgar.xbrl.standardization.strategies import BaseStrategy, StrategyResult

class BaseStrategy(ABC):
    strategy_name: str = "base"     # Unique identifier
    metric_name: str = "unknown"    # What metric it extracts
    version: str = "1.0.0"          # For tracking changes

    def __init__(self, params: Dict[str, Any] = None):
        self.params = params or {}

    @abstractmethod
    def extract(self, xbrl, facts_df, mode: ExtractionMode) -> StrategyResult:
        """Execute the extraction."""
        pass

    @property
    def fingerprint(self) -> str:
        """Unique hash of strategy + params for experiment tracking."""
        # SHA256 of {strategy_name, version, params}
```

**StrategyResult:**

Every extraction returns a `StrategyResult` with full provenance:

```python
@dataclass
class StrategyResult:
    value: Optional[float]               # Extracted value (None if failed)
    concept: Optional[str]               # Primary XBRL concept used
    method: ExtractionMethod             # DIRECT, COMPOSITE, CALCULATED, MAPPED, FALLBACK
    confidence: float                    # 0.0 - 1.0
    notes: str                           # Human-readable explanation
    components: Dict[str, float]         # Breakdown for composite extractions
    metadata: Dict[str, Any]             # Additional context
```

### 3.4 Strategy Fingerprinting

Every strategy execution is fingerprinted, enabling:
- Reproducibility: Know exactly which algorithm produced a result
- A/B testing: Compare different strategy versions
- Regression detection: Track when behavior changes

```python
strategy = get_strategy('commercial_debt', params={
    'ticker': 'WFC',
    'subtract_repos_from_stb': True,
    'safe_fallback': True
})

print(strategy.fingerprint)  # e.g., "a1b2c3d4e5f6g7h8"

# Fingerprint is deterministic based on:
# - strategy_name ("commercial_debt")
# - version ("1.0.0")
# - params (sorted JSON of parameters)
```

### 3.5 Extraction Modes

ENE supports two extraction modes:

| Mode | Purpose | Use Case |
|------|---------|----------|
| **GAAP** | Match yfinance/SEC EDGAR | Validation against reference sources |
| **Street** | Economic analysis view | How analysts actually think about leverage |

Example difference for banks:
- **GAAP ShortTermDebt**: Excludes repos (matches yfinance's "Current Debt")
- **Street ShortTermDebt**: Includes net repos (shows true financing burden)

```python
from edgar.xbrl.standardization.strategies import ExtractionMode

# GAAP extraction (default)
result_gaap = strategy.extract(xbrl, facts_df, mode=ExtractionMode.GAAP)

# Street extraction
result_street = strategy.extract(xbrl, facts_df, mode=ExtractionMode.STREET)
```

### 3.6 Known Divergences

ENE uses **known_divergences** to document cases where XBRL extraction and yfinance reference data are structurally incompatible. This is a **last resort** - the preference is always to fix extraction or reclassify the company.

#### Philosophy: Reclassify or Fix, Don't Patch

Before adding a known_divergence, ask:
1. **Is this an extraction bug?** → Fix the tree parser or strategy code
2. **Is this a misclassification?** → Change the archetype in companies.yaml
3. **Is this industry-specific?** → Add an extractor method for that industry
4. **Is this truly structural?** → Only then add a known_divergence

#### Divergence Categories

| Category | Example | Typical Status |
|----------|---------|----------------|
| **Structural Mismatch** | Stock splits, spin-offs | wont_fix |
| **Concept Selection** | Wrong XBRL concept matched | investigating |
| **Subsidiary Structure** | CAT Financial, DE Financial | deferred |
| **Industry-Specific** | Energy OperatingIncome, bank interest | deferred |

#### Divergence Lifecycle

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Failure    │ ──► │  Triage     │ ──► │  Document   │ ──► │  Review     │
│  Detected   │     │  Root Cause │     │  Divergence │     │  Quarterly  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                          │                    │                    │
                          ▼                    ▼                    ▼
                    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
                    │  Fix Code   │     │  Track in   │     │  Resolve or │
                    │  or Reclass │     │  YAML+Git   │     │  Re-defer   │
                    └─────────────┘     └─────────────┘     └─────────────┘
```

#### Required Tracking Fields

Every known_divergence must include:
- `added_date`: When documented (enables git archaeology)
- `remediation_status`: Current state (none/investigating/deferred/wont_fix/resolved)
- `remediation_notes`: What would fix this
- `review_date`: When to revisit (default: 3 months)

#### Review Process

Run quarterly: `python scripts/review_divergences.py`

This generates a report showing:
- Overdue items past their review_date
- Items missing tracking fields
- Summary by remediation status

---

## 4. Component Deep Dives

### 4.1 Strategies Module (`strategies/`)

#### 4.1.1 BaseStrategy and StrategyResult

**Location:** `edgar/xbrl/standardization/strategies/base.py`

The `BaseStrategy` abstract base class defines the contract for all strategies:

```python
class BaseStrategy(ABC):
    # Class attributes (override in subclasses)
    strategy_name: str = "base"
    metric_name: str = "unknown"
    version: str = "1.0.0"

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        self.params = params or {}

    @abstractmethod
    def extract(self, xbrl, facts_df, mode: ExtractionMode) -> StrategyResult:
        pass

    @property
    def fingerprint(self) -> str:
        # SHA256 hash of strategy_name + version + sorted params
```

**FactHelper** provides reusable extraction utilities:

```python
class FactHelper:
    @staticmethod
    def get_fact_value(facts_df, concept: str, ...) -> Optional[float]:
        """Get consolidated (non-dimensional) value for a concept."""

    @staticmethod
    def get_fact_value_fuzzy(facts_df, concept: str) -> Optional[float]:
        """Get fact value using fuzzy/partial matching."""

    @staticmethod
    def get_fact_value_non_dimensional(facts_df, concept: str) -> Optional[float]:
        """Get fact value explicitly excluding dimensional breakdowns."""
```

#### 4.1.2 Debt Strategies

**Location:** `edgar/xbrl/standardization/strategies/debt/`

| Strategy | File | Target | Approach |
|----------|------|--------|----------|
| `commercial_debt` | `commercial_debt.py` | WFC, USB, PNC | Hybrid bottom-up/top-down with repos subtraction |
| `dealer_debt` | `dealer_debt.py` | GS, MS | UnsecuredShortTermBorrowings direct lookup |
| `custodial_debt` | `custodial_debt.py` | BK, STT | Direct lookup, **never** fuzzy match |
| `hybrid_debt` | `hybrid_debt.py` | JPM, BAC, C | Check nesting before subtracting |
| `standard_debt` | `standard_debt.py` | Non-banks | Simple DebtCurrent/ShortTermDebt lookup |

**Commercial Debt Strategy** (WFC, USB, PNC):

```python
@register_strategy
class CommercialDebtStrategy(BaseStrategy):
    """
    Commercial Banks: Hybrid Bottom-Up/Top-Down.

    Strategy:
    1. TRY DebtCurrent (cleanest yfinance match)
    2. TRY Bottom-Up: CP + FHLB + OtherSTB + CPLTD
    3. IF Bottom-Up yields $0: Top-Down (STB - Repos - Trading + CPLTD)

    Parameters:
        subtract_repos_from_stb: Whether repos are bundled (default True)
        subtract_trading_from_stb: Whether trading liabilities bundled (default True)
        safe_fallback: Allow top-down fallback (default True)
    """

    strategy_name = "commercial_debt"
    metric_name = "ShortTermDebt"
    version = "1.0.0"

    def extract(self, xbrl, facts_df, mode) -> StrategyResult:
        # Implementation details...
```

**Hybrid Debt Strategy** (JPM, BAC, C):

Key feature: **Dual-check before subtracting repos**:

```python
def _is_concept_nested_in_stb(self, xbrl, concept: str) -> bool:
    """
    Check Order:
    1. Calculation Linkbase - definitive parent/child with weight
    2. Presentation Linkbase - visual indentation implies summation
    3. Default: Assume SIBLING (Do Not Subtract)

    Plus BALANCE GUARD: If repos > STB, repos cannot be nested inside STB
    """
```

#### 4.1.3 Strategy Registry

**Location:** `edgar/xbrl/standardization/strategies/__init__.py`

Strategies self-register using the `@register_strategy` decorator:

```python
# Registration
@register_strategy
class MyStrategy(BaseStrategy):
    strategy_name = "my_strategy"
    ...

# Retrieval
from edgar.xbrl.standardization.strategies import get_strategy, list_strategies

strategy = get_strategy('commercial_debt', params={'ticker': 'WFC'})
all_strategies = list_strategies()  # ['commercial_debt', 'dealer_debt', ...]
```

#### 4.1.4 How to Add a New Strategy

1. **Create strategy file:**
```python
# edgar/xbrl/standardization/strategies/debt/new_strategy.py

from ..base import BaseStrategy, StrategyResult, ExtractionMode, ExtractionMethod, FactHelper
from .. import register_strategy

@register_strategy
class NewStrategy(BaseStrategy):
    strategy_name = "new_strategy"
    metric_name = "ShortTermDebt"
    version = "1.0.0"

    def extract(self, xbrl, facts_df, mode: ExtractionMode) -> StrategyResult:
        # Your extraction logic here
        value = FactHelper.get_fact_value(facts_df, 'SomeConcept')

        return StrategyResult(
            value=value,
            concept='us-gaap:SomeConcept',
            method=ExtractionMethod.DIRECT,
            confidence=1.0 if value else 0.0,
            notes=f"New strategy extracted: {value}"
        )
```

2. **Export from `debt/__init__.py`:**
```python
from .new_strategy import NewStrategy
```

3. **Update adapter mapping** (if needed):
```python
# industry_logic/strategy_adapter.py
ARCHETYPE_STRATEGIES = {
    'new_archetype': 'new_strategy',
    ...
}
```

### 4.2 Archetypes Module (`archetypes/`)

#### 4.2.1 AccountingArchetype Enum

**Location:** `edgar/xbrl/standardization/archetypes/definitions.py`

```python
class AccountingArchetype(Enum):
    A = "standard_industrial"       # Manufacturing, retail, tech hardware
    B = "inverted_financial"        # Banks - inverted P&L
    C = "intangible_digital"        # SaaS, Pharma
    D = "asset_passthrough"         # REITs
    E = "probabilistic_liability"   # Insurance
```

#### 4.2.2 ARCHETYPE_DEFINITIONS

Complete configuration for each archetype:

```python
ARCHETYPE_DEFINITIONS = {
    AccountingArchetype.B: {
        "name": "Inverted Financial",
        "description": "Banks with inverted P&L - interest income is primary revenue",
        "coverage_pct": 8,
        "sic_ranges": [
            (6020, 6029),   # Commercial Banks
            (6035, 6036),   # Savings Institutions
            (6200, 6211),   # Security Brokers, Dealers
            ...
        ],
        "gics_sectors": ["40"],  # Financials
        "gics_groups": ["4010", "4020"],  # Banks, Diversified Financials
        "strategies": {
            "ShortTermDebt": ["commercial_debt", "dealer_debt", "custodial_debt", "hybrid_debt"],
            "Capex": None,  # Excluded
        },
        "excluded_metrics": ["COGS", "SGA", "OperatingIncome", "Capex"],
        "validation_tolerance_pct": 20.0,
        "sub_archetypes": ["commercial", "dealer", "custodial", "hybrid", "regional"],
    },
    ...
}
```

#### 4.2.3 BankSubArchetype

```python
class BankSubArchetype(Enum):
    COMMERCIAL = "commercial"  # WFC, USB, PNC
    DEALER = "dealer"          # GS, MS
    CUSTODIAL = "custodial"    # BK, STT
    HYBRID = "hybrid"          # JPM, BAC, C
    REGIONAL = "regional"      # Smaller banks
```

Each sub-archetype has a definition with strategy and parameters:

```python
BANK_SUB_ARCHETYPE_DEFINITIONS = {
    BankSubArchetype.CUSTODIAL: {
        "name": "Custodial Bank",
        "description": "Custody and asset servicing banks",
        "examples": ["BK", "STT"],
        "characteristics": {
            "minimal_stb": True,
            "repos_as_financing": True,
            "never_fuzzy_match": True,  # CRITICAL
        },
        "strategy": "custodial_debt",
        "strategy_params": {
            "repos_as_debt": False,
            "safe_fallback": False,  # CRITICAL: Never fuzzy match
        },
    },
    ...
}
```

#### 4.2.4 Classification Logic

**Location:** `edgar/xbrl/standardization/archetypes/classifier.py`

```python
def classify_company(
    ticker: str = None,
    sic: str = None,
    gics: str = None,
    config: Dict = None,
    facts_df = None,
) -> Tuple[AccountingArchetype, Optional[BankSubArchetype]]:
    """
    Classification Priority:
    1. Config override (companies.yaml archetype field)
    2. GICS sector/group classification
    3. SIC code classification
    4. Default to Standard Industrial (A)
    """
```

Bank sub-archetype detection uses balance sheet ratios:

```python
def detect_bank_sub_archetype(facts_df, ticker: str = None) -> BankSubArchetype:
    # Calculate ratios
    trading_ratio = trading_assets / total_assets
    loan_ratio = loans / total_assets

    # Detection rules
    if trading_ratio > 0.15 and unsecured_stb > 0:
        return BankSubArchetype.DEALER
    if stb < total_assets * 0.01:
        return BankSubArchetype.CUSTODIAL
    if trading_ratio > 0.05 and loan_ratio > 0.20:
        return BankSubArchetype.HYBRID
    if loan_ratio > 0.30:
        return BankSubArchetype.COMMERCIAL
    return BankSubArchetype.REGIONAL
```

### 4.3 Experiment Ledger (`ledger/`)

**Location:** `edgar/xbrl/standardization/ledger/schema.py`

The Experiment Ledger provides SQLite-based tracking for all extraction attempts.

#### 4.3.1 ExtractionRun

Records every extraction attempt:

```python
@dataclass
class ExtractionRun:
    # Identity
    ticker: str
    metric: str
    fiscal_period: str          # "2024-Q4", "2024-FY"
    form_type: str              # "10-K", "10-Q"

    # Classification
    archetype: str              # A, B, C, D, E
    sub_archetype: Optional[str]

    # Strategy
    strategy_name: str
    strategy_fingerprint: str   # Unique hash
    strategy_params: Dict[str, Any]

    # Results
    extracted_value: Optional[float]
    reference_value: Optional[float]
    variance_pct: Optional[float]  # Auto-calculated
    is_valid: bool                 # True if variance <= 20%
    confidence: float

    # Metadata
    run_id: str                    # Auto-generated SHA256
    run_timestamp: str
    extraction_notes: str
    components: Dict[str, float]
    metadata: Dict[str, Any]
```

#### 4.3.2 GoldenMaster

Verified stable configurations (3+ successful periods):

```python
@dataclass
class GoldenMaster:
    golden_id: str
    ticker: str
    metric: str
    archetype: str
    sub_archetype: Optional[str]
    strategy_name: str
    strategy_fingerprint: str
    strategy_params: Dict[str, Any]

    validated_periods: List[str]  # ["2024-Q1", "2024-Q2", "2024-Q3"]
    validation_count: int
    avg_variance_pct: float
    max_variance_pct: float

    is_active: bool
    created_at: str
    last_validated_at: str
```

#### 4.3.3 ExperimentLedger

SQLite-based persistence:

```python
class ExperimentLedger:
    def __init__(self, db_path: str = None):
        # Default: company_mappings/experiment_ledger.db

    # Extraction runs
    def record_run(self, run: ExtractionRun) -> str
    def get_run(self, run_id: str) -> Optional[ExtractionRun]
    def get_runs_for_ticker(self, ticker: str, metric: str = None, limit: int = 100) -> List[ExtractionRun]
    def get_runs_by_strategy(self, strategy_fingerprint: str, limit: int = 100) -> List[ExtractionRun]

    # Golden masters
    def create_golden_master(self, master: GoldenMaster) -> str
    def get_golden_master(self, ticker: str, metric: str) -> Optional[GoldenMaster]
    def get_all_golden_masters(self, active_only: bool = True) -> List[GoldenMaster]

    # Cohort tests
    def record_cohort_test(self, result: CohortTestResult) -> str
    def get_cohort_tests(self, cohort_name: str, limit: int = 10) -> List[CohortTestResult]

    # Analytics
    def get_strategy_performance(self, strategy_name: str) -> Dict[str, Any]
    def get_ticker_summary(self, ticker: str) -> Dict[str, Any]
```

**SQLite Schema:**

```sql
-- extraction_runs
CREATE TABLE extraction_runs (
    run_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    metric TEXT NOT NULL,
    fiscal_period TEXT NOT NULL,
    form_type TEXT NOT NULL,
    archetype TEXT NOT NULL,
    sub_archetype TEXT,
    strategy_name TEXT NOT NULL,
    strategy_fingerprint TEXT NOT NULL,
    strategy_params TEXT,  -- JSON
    extracted_value REAL,
    reference_value REAL,
    variance_pct REAL,
    is_valid INTEGER,
    confidence REAL,
    run_timestamp TEXT NOT NULL,
    extraction_notes TEXT,
    components TEXT,  -- JSON
    metadata TEXT,    -- JSON
    is_golden_candidate INTEGER,
    golden_master_id TEXT
);

-- Indexes for common queries
CREATE INDEX idx_runs_ticker ON extraction_runs(ticker);
CREATE INDEX idx_runs_metric ON extraction_runs(metric);
CREATE INDEX idx_runs_strategy ON extraction_runs(strategy_fingerprint);
```

### 4.4 Cohort Reactor (`reactor/`)

**Location:** `edgar/xbrl/standardization/reactor/cohort_reactor.py`

The Cohort Reactor tests strategy changes against groups of similar companies.

#### 4.4.1 CohortDefinition

```python
@dataclass
class CohortDefinition:
    name: str                   # "Hybrid_Banks"
    members: List[str]          # ["JPM", "BAC", "C"]
    archetype: str              # "B"
    sub_archetype: Optional[str] = None  # "hybrid"
    description: str = ""
    metrics: List[str] = field(default_factory=list)  # ["ShortTermDebt"]
```

#### 4.4.2 Built-in Cohorts

```python
DEFAULT_COHORTS = {
    'GSIB_Banks': CohortDefinition(
        name='GSIB_Banks',
        members=['JPM', 'BAC', 'C', 'WFC', 'GS', 'MS', 'BK', 'STT'],
        archetype='B',
        description='Global Systemically Important Banks',
        metrics=['ShortTermDebt', 'CashAndEquivalents'],
    ),
    'Hybrid_Banks': CohortDefinition(
        name='Hybrid_Banks',
        members=['JPM', 'BAC', 'C'],
        archetype='B',
        sub_archetype='hybrid',
    ),
    'Commercial_Banks': CohortDefinition(
        name='Commercial_Banks',
        members=['WFC', 'USB', 'PNC'],
        archetype='B',
        sub_archetype='commercial',
    ),
    # ... more cohorts
}
```

#### 4.4.3 CohortReactor

```python
class CohortReactor:
    def __init__(self, ledger: ExperimentLedger = None, config_path: str = None):
        self.ledger = ledger or ExperimentLedger()
        self.cohorts = dict(DEFAULT_COHORTS)
        # Load custom cohorts from companies.yaml

    def test_strategy_change(
        self,
        cohort_name: str,
        strategy_name: str,
        strategy_params: Dict[str, Any],
        metric: str = 'ShortTermDebt',
        extractor_fn: Callable = None,  # (ticker, params) -> value
        baseline_fn: Callable = None,   # (ticker) -> (value, variance)
        reference_fn: Callable = None,  # (ticker) -> value
    ) -> CohortTestSummary:
        """Test a strategy change against a cohort."""
```

#### 4.4.4 Impact Classification

```python
def _determine_impact(baseline_variance: float, new_variance: float) -> str:
    delta = new_variance - baseline_variance

    if delta < -2.0:
        return "IMPROVED"   # Variance decreased by >2%
    elif delta > 2.0:
        return "REGRESSED"  # Variance increased by >2%
    else:
        return "NEUTRAL"    # Within +-2%
```

#### 4.4.5 CohortTestSummary

```python
@dataclass
class CohortTestSummary:
    test_id: str
    cohort_name: str
    strategy_name: str
    strategy_fingerprint: str
    test_timestamp: str

    company_results: List[CompanyResult]
    improved_count: int
    neutral_count: int
    regressed_count: int

    total_variance_before: float
    total_variance_after: float
    variance_delta: float

    is_passing: bool  # True if no regressions AND variance_delta <= 0
```

#### 4.4.6 Interpreting Results

```
============================================================
COHORT TEST: Hybrid_Banks
============================================================
Strategy: hybrid_debt
Fingerprint: a1b2c3d4e5f6g7h8
Timestamp: 2024-01-15T10:30:00

Ticker   Baseline %      New %      Delta  Impact
------------------------------------------------------------
JPM          15.2         5.1       -10.1  +++ IMPROVED
BAC          12.5         8.2        -4.3  +++ IMPROVED
C            18.7        17.1        -1.6      NEUTRAL
------------------------------------------------------------
Total Variance: 46.4% -> 30.4% (-16.0%)
Improved: 2, Neutral: 1, Regressed: 0

STATUS: PASS - Safe to merge
============================================================
```

### 4.5 Strategy Adapter (`industry_logic/strategy_adapter.py`)

The Strategy Adapter bridges ENE strategies to the legacy `ExtractedMetric` interface.

```python
class StrategyAdapter:
    ARCHETYPE_STRATEGIES = {
        'commercial': 'commercial_debt',
        'dealer': 'dealer_debt',
        'custodial': 'custodial_debt',
        'hybrid': 'hybrid_debt',
        'regional': 'commercial_debt',
    }

    def extract_short_term_debt(
        self,
        xbrl,
        facts_df,
        ticker: str = None,
        mode: str = 'gaap',
        archetype: str = None,
    ) -> ExtractedMetric:
        """
        Extract ShortTermDebt using the appropriate strategy.

        1. Look up company config
        2. Determine archetype → strategy mapping
        3. Build strategy params from config
        4. Execute strategy
        5. Convert StrategyResult to ExtractedMetric
        """
```

**Usage:**

```python
from edgar.xbrl.standardization.industry_logic.strategy_adapter import (
    extract_short_term_debt_via_strategy
)

# Drop-in replacement for legacy extraction
result = extract_short_term_debt_via_strategy(
    xbrl, facts_df, ticker='JPM', mode='gaap'
)
```

---

## 5. Configuration Reference

### 5.1 companies.yaml Structure

**Location:** `edgar/xbrl/standardization/config/companies.yaml`

```yaml
version: "1.0.0"

companies:
  # MAG7 Tech Companies
  AAPL:
    name: "Apple Inc."
    cik: 320193

  # Bank Configuration (Archetype B)
  JPM:
    name: "JPMorgan Chase & Co."
    cik: 19617
    industry: "banking"
    archetype: "B"                    # Archetype code
    bank_archetype: "hybrid"          # Sub-archetype
    archetype_override: true          # Use config, not dynamic detection

    extraction_rules:
      subtract_repos_from_stb: false  # Repos are separate line items
      check_nesting: true             # Verify linkbase before subtraction
      cash_includes_ib_deposits: true
      street_debt_includes_net_repos: true
      safe_fallback: true

    validation_tolerance_pct: 20.0    # Higher tolerance for banks

    exclude_metrics:
      - COGS
      - SGA

    street_view_notes:
      ShortTermDebt: "Hybrid: Commercial GAAP + Dealer Street View"

    notes: "Hybrid bank - commercial + significant dealer/trading operations"

defaults:
  validation_tolerance_pct: 15.0

  industry_tolerances:
    financial_services: 20.0
    technology: 15.0
    default: 15.0

  fallback_chain:
    - tree_parser
    - ai_semantic
    - temporal
    - manual

  industry_exclusions:
    banking:
      - COGS
      - SGA
      - OperatingIncome
      - Capex

cohorts:
  GSIB_Banks:
    members: [JPM, BAC, C, WFC, GS, MS, BK, STT]
    archetype: "B"
    description: "Global Systemically Important Banks"
    metrics: [ShortTermDebt, CashAndEquivalents]

  Hybrid_Banks:
    members: [JPM, BAC, C]
    archetype: "B"
    sub_archetype: "hybrid"
    description: "Hybrid/Universal Banks"
    metrics: [ShortTermDebt]
```

### 5.2 Company Entry Fields

| Field                      | Required  | Description                                            |
| -------------------------- | --------- | ------------------------------------------------------ |
| `name`                     | No        | Human-readable company name                            |
| `cik`                      | No        | SEC CIK number                                         |
| `industry`                 | No        | Industry classification                                |
| `archetype`                | No        | Archetype code (A-E)                                   |
| `bank_archetype`           | Bank only | Sub-archetype for banks                                |
| `archetype_override`       | No        | If `true`, use config archetype, not dynamic detection |
| `extraction_rules`         | No        | Strategy parameters (see below)                        |
| `validation_tolerance_pct` | No        | Override default tolerance                             |
| `exclude_metrics`          | No        | Metrics that are N/A for this company                  |
| `street_view_notes`        | No        | Documentation for Street View differences              |
| `notes`                    | No        | General notes about the company                        |

### 5.3 Extraction Rules by Archetype

**Commercial Banks (WFC, USB, PNC):**
```yaml
extraction_rules:
  subtract_repos_from_stb: true   # Repos bundled in STB
  subtract_trading_from_stb: true # Trading liabilities bundled
  safe_fallback: true             # Allow top-down fallback
```

**Dealer Banks (GS, MS):**
```yaml
extraction_rules:
  use_unsecured_stb: true  # Dealers have clean UnsecuredSTB tag
  safe_fallback: true
```

**Custodial Banks (BK, STT):**
```yaml
extraction_rules:
  repos_as_debt: false     # Repos NOT included in Current Debt
  safe_fallback: false     # CRITICAL: Return None, never fuzzy match
```

**Hybrid Banks (JPM, BAC, C):**
```yaml
extraction_rules:
  subtract_repos_from_stb: false  # Repos are separate line items
  check_nesting: true             # Verify linkbase before subtraction
  cash_includes_ib_deposits: true
  street_debt_includes_net_repos: true
  safe_fallback: true
```

### 5.4 Cohort Definition Fields

| Field | Required | Description |
|-------|----------|-------------|
| `members` | Yes | List of ticker symbols |
| `archetype` | Yes | Archetype code (A-E) |
| `sub_archetype` | No | Sub-archetype for banks |
| `description` | No | Human-readable description |
| `metrics` | No | Metrics to test (default: `[ShortTermDebt]`) |

### 5.5 Known Divergences Schema

Known divergences are documented in `companies.yaml` under each company's `known_divergences` section. Each metric can have a divergence entry.

#### Full Schema

```yaml
known_divergences:
  MetricName:  # e.g., ShortTermDebt, OperatingIncome
    # Required fields
    form_types: ["10-K", "10-Q"]      # Which form types this applies to
    skip_validation: true              # Whether to skip E2E validation
    reason: >                          # Detailed explanation (multi-line)
      Description of why this divergence exists and why it cannot
      be resolved through code fixes or reclassification.

    # Scope fields (optional)
    fiscal_years: [2023, 2024]         # Limit to specific fiscal years
    variance_pct: 65.0                 # Expected/observed variance percentage

    # Tracking fields (required for new entries)
    added_date: "2026-01-26"           # When this divergence was documented
    remediation_status: "deferred"     # Current status (see below)
    remediation_notes: >               # What would fix this
      Brief description of the work needed to resolve this divergence,
      or why it cannot be fixed.
    review_date: "2026-04-26"          # When to revisit (default: 3 months)

    # Reference fields (optional)
    github_issue: "123"                # Related GitHub issue number
```

#### Remediation Status Values

| Status | Meaning | Review Period |
|--------|---------|---------------|
| `none` | Not yet triaged | 1 month |
| `investigating` | Actively researching fix | 2 weeks |
| `deferred` | Known issue, will address later | 3 months |
| `wont_fix` | Structural incompatibility, cannot fix | 6 months |
| `resolved` | Fixed, divergence should be removed | N/A |

#### Example Entry

```yaml
CAT:
  name: "Caterpillar Inc."
  known_divergences:
    ShortTermDebt:
      form_types: ["10-K", "10-Q"]
      variance_pct: 65.0
      reason: >
        Cat Financial subsidiary debt not included in ShortTermBorrowings.
        yfinance consolidates all debt; XBRL extracts industrial segment only.
      skip_validation: true
      added_date: "2026-01-26"
      remediation_status: "deferred"
      remediation_notes: >
        Would require subsidiary-aware extraction or consolidated statement
        detection. Consider adding segment reconciliation logic.
      review_date: "2026-04-26"
```

---

## 6. Working Examples

### 6.1 Example 1: Extracting ShortTermDebt for JPM (Hybrid Bank)

```python
from edgar import Company
from edgar.xbrl.standardization.archetypes import classify_company
from edgar.xbrl.standardization.strategies import get_strategy, ExtractionMode

# Get the filing and XBRL data
company = Company("JPM")
filings = company.get_filings(form="10-K")
filing = filings.latest()
xbrl = filing.xbrl()
facts_df = xbrl.facts.to_dataframe()

# Step 1: Classify JPM
archetype, sub_archetype = classify_company(
    ticker='JPM',
    sic='6020',
    config={'archetype': 'B', 'bank_archetype': 'hybrid', 'archetype_override': True}
)
print(f"Archetype: {archetype.value}")      # inverted_financial
print(f"Sub-archetype: {sub_archetype.value}")  # hybrid

# Step 2: Get the appropriate strategy
strategy = get_strategy('hybrid_debt', params={
    'ticker': 'JPM',
    'subtract_repos_from_stb': False,
    'check_nesting': True,
    'safe_fallback': True,
})
print(f"Strategy: {strategy.strategy_name}")
print(f"Fingerprint: {strategy.fingerprint}")

# Step 3: Execute extraction
result = strategy.extract(xbrl, facts_df, mode=ExtractionMode.GAAP)

print(f"\nExtraction Result:")
print(f"  Value: ${result.value/1e9:.1f}B")
print(f"  Concept: {result.concept}")
print(f"  Method: {result.method.value}")
print(f"  Confidence: {result.confidence}")
print(f"  Notes: {result.notes}")
print(f"  Components: {result.components}")
```

**Sample Output:**
```
Archetype: inverted_financial
Sub-archetype: hybrid

Strategy: hybrid_debt
Fingerprint: 7a3b5c8d9e2f1a4b

Extraction Result:
  Value: $15.2B
  Concept: None
  Method: composite
  Confidence: 0.9
  Notes: Hybrid [JPM]: STB(15.2B) + CPLTD(0.0B) [repos separate: 234.5B]
  Components: {'ShortTermBorrowings': 15200000000, 'LongTermDebtCurrent': 0}
```

### 6.2 Example 2: Running a Cohort Test

```python
from edgar.xbrl.standardization.reactor import CohortReactor
from edgar.xbrl.standardization.ledger import ExperimentLedger

# Initialize reactor
ledger = ExperimentLedger()
reactor = CohortReactor(ledger=ledger)

# List available cohorts
print("Available cohorts:", reactor.list_cohorts())

# Define extraction functions (these would use actual XBRL data)
def extract_value(ticker: str, params: dict) -> float:
    """Extract value using strategy."""
    strategy = get_strategy('hybrid_debt', params=params)
    # ... actual extraction ...
    return extracted_value

def get_baseline(ticker: str) -> tuple:
    """Get baseline from ledger."""
    runs = ledger.get_runs_for_ticker(ticker, metric='ShortTermDebt', limit=1)
    if runs:
        return runs[0].extracted_value, runs[0].variance_pct
    return None, None

def get_reference(ticker: str) -> float:
    """Get yfinance reference value."""
    import yfinance as yf
    stock = yf.Ticker(ticker)
    return stock.balance_sheet.loc['Current Debt'].iloc[0]

# Run cohort test
summary = reactor.test_strategy_change(
    cohort_name='Hybrid_Banks',
    strategy_name='hybrid_debt',
    strategy_params={
        'subtract_repos_from_stb': False,
        'check_nesting': True,
    },
    metric='ShortTermDebt',
    extractor_fn=extract_value,
    baseline_fn=get_baseline,
    reference_fn=get_reference,
)

# Print results
reactor.print_summary(summary)

# Check if safe to merge
if summary.is_passing:
    print("Safe to merge - no regressions detected!")
else:
    print(f"BLOCKED - {summary.regressed_count} regressions detected")
```

### 6.3 Example 3: Adding a New Company Configuration

```yaml
# Add to config/companies.yaml

companies:
  # Existing entries...

  # New bank entry
  TFC:
    name: "Truist Financial Corporation"
    cik: 92230
    industry: "banking"
    archetype: "B"
    bank_archetype: "commercial"    # Regional commercial bank
    archetype_override: true

    extraction_rules:
      subtract_repos_from_stb: true
      subtract_trading_from_stb: true
      safe_fallback: true

    validation_tolerance_pct: 20.0

    exclude_metrics:
      - COGS
      - SGA

    notes: "Regional commercial bank from BB&T/SunTrust merger"
```

Then verify:

```python
from edgar.xbrl.standardization.industry_logic.strategy_adapter import StrategyAdapter

adapter = StrategyAdapter()
strategy_name = adapter.get_strategy_for_ticker('TFC')
print(f"TFC will use: {strategy_name}")  # commercial_debt
```

### 6.4 Example 4: Creating a New Strategy

**Step 1: Create the strategy file**

```python
# edgar/xbrl/standardization/strategies/debt/fintech_debt.py

"""
Fintech Debt Strategy

Handles ShortTermDebt extraction for fintech companies (SQ, PYPL, SOFI).
These companies often have unique debt structures from their banking licenses.
"""

import logging
from typing import Any, Dict, Optional

from ..base import (
    BaseStrategy,
    StrategyResult,
    ExtractionMode,
    ExtractionMethod,
    FactHelper,
)
from .. import register_strategy

logger = logging.getLogger(__name__)


@register_strategy
class FintechDebtStrategy(BaseStrategy):
    """
    Fintech companies (SQ, PYPL, SOFI): Special handling for banking license debt.

    Strategy:
    1. Try standard DebtCurrent
    2. Check for customer deposits (if bank license)
    3. Handle crypto-related liabilities

    Parameters:
        has_bank_license: Whether company has banking charter (default False)
        include_customer_deposits: Include as STD (default False)
    """

    strategy_name = "fintech_debt"
    metric_name = "ShortTermDebt"
    version = "1.0.0"

    def extract(
        self,
        xbrl: Any,
        facts_df: Any,
        mode: ExtractionMode = ExtractionMode.GAAP
    ) -> StrategyResult:
        """Execute fintech debt extraction."""
        ticker = self.params.get('ticker', 'UNKNOWN')
        has_bank_license = self.params.get('has_bank_license', False)
        include_deposits = self.params.get('include_customer_deposits', False)

        # Standard debt concepts
        debt_current = FactHelper.get_fact_value(facts_df, 'DebtCurrent')
        stb = FactHelper.get_fact_value(facts_df, 'ShortTermBorrowings') or 0
        cpltd = FactHelper.get_fact_value(facts_df, 'LongTermDebtCurrent') or 0

        # If has bank license, may need to handle deposits
        deposits = 0
        if has_bank_license and include_deposits:
            deposits = FactHelper.get_fact_value(facts_df, 'Deposits') or 0

        # Calculate total
        if debt_current is not None and debt_current > 0:
            total = debt_current
            method = ExtractionMethod.DIRECT
            notes = f"Fintech [{ticker}]: DebtCurrent direct"
        else:
            total = stb + cpltd
            if include_deposits:
                total += deposits
            method = ExtractionMethod.COMPOSITE
            notes = f"Fintech [{ticker}]: STB({stb/1e9:.1f}B) + CPLTD({cpltd/1e9:.1f}B)"
            if include_deposits and deposits > 0:
                notes += f" + Deposits({deposits/1e9:.1f}B)"

        return StrategyResult(
            value=total if total > 0 else None,
            concept='us-gaap:DebtCurrent' if debt_current else None,
            method=method,
            confidence=0.9 if total > 0 else 0.0,
            notes=notes,
            components={
                'ShortTermBorrowings': stb,
                'LongTermDebtCurrent': cpltd,
                'Deposits': deposits,
            },
            metadata={
                'archetype': 'fintech',
                'has_bank_license': has_bank_license,
            }
        )
```

**Step 2: Export from debt/__init__.py**

```python
# edgar/xbrl/standardization/strategies/debt/__init__.py

from .fintech_debt import FintechDebtStrategy

__all__ = [
    # ... existing exports ...
    'FintechDebtStrategy',
]
```

**Step 3: Update strategy imports in strategies/__init__.py**

```python
# edgar/xbrl/standardization/strategies/__init__.py

try:
    from .debt import (
        CommercialDebtStrategy,
        DealerDebtStrategy,
        CustodialDebtStrategy,
        HybridDebtStrategy,
        StandardDebtStrategy,
        FintechDebtStrategy,  # Add new strategy
    )
except ImportError:
    pass
```

**Step 4: Add archetype mapping (optional)**

```python
# edgar/xbrl/standardization/industry_logic/strategy_adapter.py

ARCHETYPE_STRATEGIES = {
    'commercial': 'commercial_debt',
    'dealer': 'dealer_debt',
    'custodial': 'custodial_debt',
    'hybrid': 'hybrid_debt',
    'regional': 'commercial_debt',
    'fintech': 'fintech_debt',  # Add new mapping
}
```

**Step 5: Add company configuration**

```yaml
# config/companies.yaml

SQ:
  name: "Block, Inc."
  cik: 1512673
  industry: "fintech"
  archetype: "C"  # Intangible Digital (fintech)
  bank_archetype: "fintech"  # Custom sub-type
  archetype_override: true
  extraction_rules:
    has_bank_license: false
    include_customer_deposits: false
  notes: "Payment processing company, no bank charter"
```

**Step 6: Test the new strategy**

```python
from edgar.xbrl.standardization.strategies import get_strategy, list_strategies

# Verify registration
print('fintech_debt' in list_strategies())  # True

# Test instantiation
strategy = get_strategy('fintech_debt', params={
    'ticker': 'SQ',
    'has_bank_license': False,
})
print(f"Strategy: {strategy.strategy_name}")
print(f"Fingerprint: {strategy.fingerprint}")
```

---

## 7. Troubleshooting & FAQ

### 7.1 Common Issues and Solutions

#### Issue: "Unknown strategy 'xyz'"

**Cause:** Strategy not registered or import failed.

**Solution:**
```python
from edgar.xbrl.standardization.strategies import list_strategies
print(list_strategies())  # Check what's available

# Verify the strategy file has @register_strategy decorator
# Verify the strategy is imported in strategies/__init__.py
```

#### Issue: Variance too high against yfinance

**Cause:** Strategy not subtracting repos when it should (or vice versa).

**Debug:**
```python
# Check what components the strategy found
print(f"Components: {result.components}")
print(f"Metadata: {result.metadata}")

# Key metadata fields:
# - 'repos_is_nested': Did linkbase check say repos is nested in STB?
# - 'raw_stb': What was the raw ShortTermBorrowings value?
# - 'secured_funding_repos': What was the repos value?
```

**Solution:**
- Check if `archetype_override: true` is set in config
- Verify extraction_rules match bank sub-archetype
- Add balance guard logging to see decision points

#### Issue: Strategy returns None

**Cause:** No matching concepts found in XBRL data.

**Debug:**
```python
# Check what concepts are available
concepts = facts_df['concept'].str.lower().unique()
debt_concepts = [c for c in concepts if 'debt' in c or 'borrow' in c]
print(f"Available debt concepts: {debt_concepts}")
```

**Solution:**
- Check if company uses non-standard extension concepts
- Verify form type (10-K vs 10-Q may have different concepts)
- Set `safe_fallback: true` for fuzzy matching (except custodial banks!)

#### Issue: Cohort test shows regressions

**Cause:** Strategy change affected other companies negatively.

**Solution:**
1. Review the regression cases individually
2. Check if the regression is valid (maybe previous result was wrong)
3. Consider adding company-specific config overrides
4. Roll back strategy change if legitimate regression

### 7.2 When to Use Which Archetype

| Question | Archetype |
|----------|-----------|
| Does the company have COGS? | If no → Probably B (bank) or C (SaaS) |
| Is interest income primary revenue? | If yes → B (bank) |
| High intangible assets? R&D capitalization? | If yes → C (intangible digital) |
| Property-based income? FFO metrics? | If yes → D (REIT) |
| Insurance premiums? Loss reserves? | If yes → E (insurance) |
| Traditional manufacturing/retail? | If yes → A (standard industrial) |

### 7.3 Bank Sub-Archetype Decision Tree

```
Is the company a bank (SIC 6020-6029)?
├── Yes → Check trading ratio
│   ├── trading_ratio > 15% AND uses UnsecuredSTB?
│   │   └── DEALER (GS, MS)
│   ├── STB < 1% of assets?
│   │   └── CUSTODIAL (BK, STT)
│   ├── trading_ratio > 5% AND loan_ratio > 20%?
│   │   └── HYBRID (JPM, BAC, C)
│   ├── loan_ratio > 30%?
│   │   └── COMMERCIAL (WFC, USB, PNC)
│   └── Otherwise
│       └── REGIONAL
└── No → Not a bank sub-archetype
```

### 7.4 Debugging Strategy Execution

```python
import logging

# Enable debug logging for strategies
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('edgar.xbrl.standardization.strategies').setLevel(logging.DEBUG)

# Now run extraction - will show decision points
result = strategy.extract(xbrl, facts_df, mode=ExtractionMode.GAAP)
```

### 7.5 FAQ

**Q: Why do custodial banks have `safe_fallback: false`?**

A: Custodial banks (BK, STT) have minimal short-term borrowings. Fuzzy matching on "ShortTermBorrowings" would incorrectly pick up repos or other concepts. It's better to return `None` than a wrong value.

**Q: What's the difference between GAAP and Street mode?**

A: GAAP mode extracts values that match yfinance/SEC EDGAR definitions (for validation). Street mode extracts values as analysts think about them (e.g., including repos in leverage calculations).

**Q: How often should I update strategy fingerprints?**

A: Fingerprints update automatically when you change strategy version or parameters. Increment the `version` attribute when making meaningful logic changes.

**Q: Can I override archetype detection for a single company?**

A: Yes, set `archetype_override: true` in companies.yaml along with the desired archetype and sub-archetype.

**Q: How do I add a company to an existing cohort?**

A: Edit the cohort definition in companies.yaml under the `cohorts` section, adding the ticker to the `members` list.

### 7.6 When to Add a Known Divergence

Use this decision tree when E2E validation fails for a company/metric combination:

```
┌─────────────────────────────────────────────────────────────────┐
│                    E2E VALIDATION FAILURE                       │
│               (variance > tolerance threshold)                  │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. Is it an extraction bug?                                    │
│     - Wrong concept selected by tree parser?                    │
│     - Missing fallback in strategy?                             │
│     - Calculation error in component summation?                 │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
              ┌───────────────────┴───────────────────┐
              │ YES                                   │ NO
              ▼                                       ▼
┌─────────────────────────┐     ┌─────────────────────────────────┐
│  FIX THE CODE           │     │  2. Is it a misclassification?  │
│  - Update tree_parser   │     │     - Wrong archetype?          │
│  - Fix strategy logic   │     │     - Wrong sub-archetype?      │
│  - Add concept mapping  │     │     - archetype_override needed?│
└─────────────────────────┘     └─────────────────────┬───────────┘
                                                      │
                              ┌────────────────────────┴────────────┐
                              │ YES                                 │ NO
                              ▼                                     ▼
                ┌─────────────────────────┐   ┌───────────────────────────────┐
                │  RECLASSIFY COMPANY     │   │  3. Is it industry-specific?  │
                │  - Change archetype     │   │     - Energy cost structure?  │
                │  - Set bank_archetype   │   │     - Bank interest income?   │
                │  - Add override flag    │   │     - Insurance premiums?     │
                └─────────────────────────┘   └─────────────────┬─────────────┘
                                                                │
                                          ┌─────────────────────┴──────────────┐
                                          │ YES                                │ NO
                                          ▼                                    ▼
                            ┌─────────────────────────┐  ┌─────────────────────────────┐
                            │  ADD INDUSTRY EXTRACTOR │  │  4. Is it truly structural? │
                            │  - New strategy method  │  │     - Stock splits?         │
                            │  - Industry logic rule  │  │     - Spin-offs/restates?   │
                            │  - Metric exclusion     │  │     - Subsidiary structure? │
                            └─────────────────────────┘  │     - yfinance data issue?  │
                                                         └─────────────────┬───────────┘
                                                                           │
                                                     ┌─────────────────────┴──────────┐
                                                     │ YES                            │ NO
                                                     ▼                                ▼
                                   ┌───────────────────────────┐    ┌─────────────────────┐
                                   │  ADD KNOWN_DIVERGENCE     │    │  INVESTIGATE MORE   │
                                   │  - Document with reason   │    │  - Check raw XBRL   │
                                   │  - Set skip_validation    │    │  - Compare periods  │
                                   │  - Add tracking fields    │    │  - Ask in Slack     │
                                   │  - Schedule review date   │    └─────────────────────┘
                                   └───────────────────────────┘
```

#### Common Divergence Patterns

| Pattern | Example Companies | Root Cause | Typical Resolution |
|---------|-------------------|------------|-------------------|
| **Subsidiary Financing** | CAT, DE | Financial subsidiary debt separate from industrial | deferred - needs segment-aware extraction |
| **Stock Splits** | NVDA | Pre-split shares vs post-split yfinance | wont_fix - structural mismatch |
| **Spin-offs** | GE | Restated financials vs historical yfinance | wont_fix - apples-to-oranges |
| **Energy Cost Structure** | XOM, CVX, COP | Non-standard P&L with drilling costs | deferred - needs energy archetype |
| **Bank Methodology** | WFC, STT | Different debt aggregation methods | investigating - validate methodology |

#### Checklist for Adding a Divergence

- [ ] Confirmed this is NOT an extraction bug (checked tree parser output)
- [ ] Confirmed this is NOT a misclassification (checked archetype)
- [ ] Confirmed this is NOT fixable with industry logic
- [ ] Documented the root cause in `reason` field
- [ ] Added all tracking fields (added_date, remediation_status, remediation_notes, review_date)
- [ ] Set appropriate remediation_status based on fix feasibility
- [ ] Created GitHub issue if investigation needed

---

## 8. Appendices

### Appendix A: Key API Reference

#### archetypes module

```python
from edgar.xbrl.standardization.archetypes import (
    AccountingArchetype,          # Enum: A, B, C, D, E
    BankSubArchetype,             # Enum: COMMERCIAL, DEALER, CUSTODIAL, HYBRID, REGIONAL
    ARCHETYPE_DEFINITIONS,        # Dict of archetype configs
    BANK_SUB_ARCHETYPE_DEFINITIONS,
    classify_company,             # (ticker, sic, gics, config, facts_df) -> (archetype, sub)
    classify_by_sic,              # (sic) -> archetype
    classify_by_gics,             # (gics) -> archetype
    detect_bank_sub_archetype,    # (facts_df, ticker) -> sub_archetype
    get_archetype_definition,     # (archetype) -> dict
    get_bank_sub_archetype_definition,
)
```

#### strategies module

```python
from edgar.xbrl.standardization.strategies import (
    BaseStrategy,                 # ABC for all strategies
    StrategyResult,               # Extraction result dataclass
    ExtractionMode,               # Enum: GAAP, STREET
    ExtractionMethod,             # Enum: DIRECT, COMPOSITE, CALCULATED, MAPPED, FALLBACK
    FactHelper,                   # Static helper methods for fact extraction
    register_strategy,            # Decorator to register strategy
    get_strategy,                 # (name, params) -> strategy instance
    list_strategies,              # () -> list of strategy names
    get_strategies_for_metric,    # (metric) -> list of strategy names
)
```

#### ledger module

```python
from edgar.xbrl.standardization.ledger import (
    ExtractionRun,                # Dataclass for extraction attempt
    GoldenMaster,                 # Dataclass for verified stable config
    CohortTestResult,             # Dataclass for cohort test result
    ExperimentLedger,             # SQLite-based ledger class
)
```

#### reactor module

```python
from edgar.xbrl.standardization.reactor import (
    CohortReactor,                # Main reactor class
    CohortDefinition,             # Dataclass for cohort
    CompanyResult,                # Dataclass for single company test
    CohortTestSummary,            # Dataclass for test summary
)
```

### Appendix B: SIC Code to Archetype Mapping

| SIC Range | Industry | Archetype |
|-----------|----------|-----------|
| 1000-5999 | Agriculture, Mining, Manufacturing, Retail | A |
| 6020-6029 | Commercial Banks | B |
| 6035-6036 | Savings Institutions | B |
| 6199 | Finance Services (AXP) | B |
| 6200-6211 | Security Brokers, Dealers | B |
| 6282 | Investment Advice | B |
| 6300-6399 | Insurance | E |
| 6500-6553 | Real Estate | D |
| 6798 | REITs | D |
| 2833-2836 | Pharmaceuticals | C |
| 3570-3579 | Computer Equipment | C |
| 3674 | Semiconductors | C |
| 7370-7379 | Computer Services, SaaS | C |
| 7389 | Business Services (V, MA) | C |

### Appendix C: Strategy Fingerprint Explained

The fingerprint is a SHA256 hash of the strategy's identifying characteristics:

```python
fingerprint_data = {
    'strategy': self.strategy_name,  # e.g., "hybrid_debt"
    'version': self.version,          # e.g., "1.0.0"
    'params': self.params,            # e.g., {'ticker': 'JPM', 'check_nesting': True}
}
fingerprint_json = json.dumps(fingerprint_data, sort_keys=True)
fingerprint = hashlib.sha256(fingerprint_json.encode()).hexdigest()[:16]
```

**Properties:**
- **Deterministic:** Same inputs always produce same fingerprint
- **Collision-resistant:** Different inputs produce different fingerprints
- **Truncated:** First 16 characters of SHA256 (64-bit security sufficient for tracking)

**Use cases:**
- Track which exact algorithm produced a result
- Compare results across strategy versions
- Detect when strategy behavior changes
- A/B testing different parameter configurations

### Appendix D: Ledger Database Schema

```sql
-- Core tables
extraction_runs       -- Every extraction attempt
golden_masters        -- Verified stable configurations
cohort_tests          -- Cohort reactor test results

-- Key indexes
idx_runs_ticker       -- Fast lookup by ticker
idx_runs_metric       -- Fast lookup by metric
idx_runs_period       -- Fast lookup by period
idx_runs_strategy     -- Fast lookup by fingerprint
idx_golden_ticker     -- Fast golden master lookup
idx_cohort_name       -- Fast cohort test lookup
```

**Sample queries:**

```sql
-- Get all runs for a ticker
SELECT * FROM extraction_runs
WHERE ticker = 'JPM'
ORDER BY run_timestamp DESC
LIMIT 10;

-- Get strategy performance
SELECT
    strategy_name,
    COUNT(*) as total_runs,
    AVG(variance_pct) as avg_variance,
    SUM(CASE WHEN is_valid = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate
FROM extraction_runs
GROUP BY strategy_name;

-- Get active golden masters
SELECT ticker, metric, strategy_name, validation_count, avg_variance_pct
FROM golden_masters
WHERE is_active = 1
ORDER BY validation_count DESC;
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-24 | ENE Team | Initial comprehensive guide |

---

*This documentation is generated from the ENE codebase. For the most up-to-date information, refer to the source files in `edgar/xbrl/standardization/`.*
