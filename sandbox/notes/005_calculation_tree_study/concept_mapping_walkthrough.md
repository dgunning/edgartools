# Concept Mapping Workflow - Developer Walkthrough

This document explains the XBRL Concept Mapping system for new developers joining the edgartools project.

## Overview

The concept mapping system **standardizes XBRL concepts across different company filings**. Each company may use different XBRL concept names for the same financial metric (e.g., "Revenue" might be `RevenueFromContractWithCustomerExcludingAssessedTax` for one company and `Revenues` for another). This system resolves those differences.

```mermaid
flowchart LR
    A[Company XBRL Filing] --> B[Multi-Layer Mapper]
    B --> C[Standardized Metrics]
    C --> D[Validated Output]
    
    B --> B1[Layer 1: Tree Parser]
    B --> B2[Layer 2: Facts Search]
    B --> B3[Layer 3: AI Semantic]
```

---

## Commit History & Evolution

The concept mapping system was developed iteratively. Here's the evolution based on recent commits:

| Commit | Description | Key Changes |
|--------|-------------|-------------|
| `45c31700` | Initial AI agent tools | Created reusable tools for concept mapping workflow |
| `7a954a2b` | Concept-mapping-resolver agent | Added the AI agent definition and bulk data support |
| `67b1e510` | Investigation reporting | Enhanced agent with detailed investigation methodology |
| `f2a8f115` | Tolerance tuning | Increased variance tolerance from 10% to 15% |
| `139e298d` | Composite metrics (IntangibleAssets) | Defined IntangibleAssets as a composite metric |
| `69c4ffbc` | Composite metric extraction | Added extraction logic for composite metrics |
| `16aea1a1` | XBRL value extraction fixes | Fixed extraction and composite debt metrics |
| `70a06066` | E2E test documentation | Added investigation scripts and test results |
| `f71a2d7f` | **Workflow restructure** | Reordered layers (Facts before AI), validation-in-loop |
| `dfc231d3` | E2E test SP500 | 86.4% coverage on 10 diverse S&P 500 companies |
| `3c09bd5a` | **JPM investigation** | Deep dive into dimensional XBRL reporting issues |
| `6977c22d` | Agent enhancements | Added gap types, dimensional reporting guide, decision tree |

---

## Architecture - The Multi-Layer System

### Directory Structure

```
edgar/xbrl/standardization/
├── config/
│   ├── metrics.yaml       # Target metric definitions
│   └── companies.yaml     # Company-specific overrides
├── layers/
│   ├── tree_parser.py     # Layer 1: XBRL calc tree parsing
│   ├── ai_semantic.py     # Layer 2: AI-powered semantic mapping
│   └── facts_search.py    # Layer 3: Facts database search
├── tools/
│   ├── discover_concepts.py
│   ├── check_fallback_quality.py
│   ├── verify_mapping.py
│   ├── learn_mappings.py
│   └── resolve_gaps.py    # Main gap resolution entry point
├── models.py              # Data structures (MappingResult, etc.)
├── orchestrator.py        # Main pipeline coordinator
├── reference_validator.py # yfinance validation
└── README.md
```

### Key Components Explained

---

### 1. Configuration: [metrics.yaml](file:///mnt/c/Users/Sangicook/LAB_FHI/Project/Side_project/edgartools/edgar/xbrl/standardization/config/metrics.yaml)

Defines **target metrics** we want to extract. Each metric has:

```yaml
Revenue:
  description: "Total revenue from operations"
  known_concepts:      # XBRL concepts that map to this metric
    - RevenueFromContractWithCustomerExcludingAssessedTax
    - Revenues
    - SalesRevenueNet
  tree_hints:          # Hints for tree-based discovery
    statements: [INCOME, OPERATIONS]
    parent_pattern: OperatingIncome
  universal: true      # Present in all MAG7 companies
```

**Composite metrics** (added in `139e298d`) sum multiple concepts:

```yaml
IntangibleAssets:
  composite: true
  components:
    - Goodwill
    - IntangibleAssetsNetExcludingGoodwill
```

---

### 2. Data Models: [models.py](file:///mnt/c/Users/Sangicook/LAB_FHI/Project/Side_project/edgartools/edgar/xbrl/standardization/models.py)

**Core data structures:**

| Class | Purpose |
|-------|---------|
| `MappingResult` | Output of a mapping operation (concept, confidence, source) |
| `MappingSource` | Enum: `TREE`, `AI`, `MANUAL`, `CONFIG`, etc. |
| `ConfidenceLevel` | Enum: `HIGH`, `MEDIUM`, `LOW`, `NONE`, `INVALID` |
| `MetricConfig` | Loaded metric definition from YAML |
| `MappingState` | Tracks progress through layers |

---

### 3. The Mapping Layers

#### Layer 1: Tree Parser - [tree_parser.py](file:///mnt/c/Users/Sangicook/LAB_FHI/Project/Side_project/edgartools/edgar/xbrl/standardization/layers/tree_parser.py)

**Handles ~85% of mappings** by parsing XBRL calculation trees.

```mermaid
flowchart TD
    A[XBRL Calculation Tree] --> B{Known Concept Match?}
    B -->|Yes| C[High Confidence Mapping]
    B -->|No| D{Tree Hints Match?}
    D -->|Yes| E[Medium Confidence Mapping]
    D -->|No| F[Pass to Layer 2]
```

**Strategy:**
1. Try direct match against `known_concepts` from config
2. Use `tree_hints` (parent patterns, statement type) for discovery
3. Return with appropriate confidence level

#### Layer 2: AI Semantic - [ai_semantic.py](file:///mnt/c/Users/Sangicook/LAB_FHI/Project/Side_project/edgartools/edgar/xbrl/standardization/layers/ai_semantic.py)

> [!IMPORTANT]
> **What is "AI Semantic" exactly?**
> 
> It uses an **LLM API via OpenRouter** (specifically `mistralai/devstral-2512:free` by default). The code imports `OpenAI` client and connects to `https://openrouter.ai/api/v1`. It requires the `OPENROUTER_API_KEY` environment variable.

**What it does:**
1. Extracts all concepts from calc trees
2. Finds **candidate concepts** using keyword matching against metric names
3. Sends each candidate to the LLM with tree context (parent, weight, statement type)
4. LLM evaluates if the concept matches the target metric
5. Returns the best match with confidence and reasoning

**Fallback:** If `OPENROUTER_API_KEY` is not set, it falls back to simple heuristic matching (no LLM call).

```python
# Example LLM prompt sent:
"""Evaluate if this XBRL concept matches the target metric:

Target Metric: Revenue
Description: Total revenue from operations

XBRL Concept: SalesRevenueNet
Tree Context:
  - Parent: CostsAndExpenses
  - Weight: 1.0
  - Trees: IncomeStatement, Operations

Does this concept represent Revenue?"""
```

#### Layer 3: Facts Search - [facts_search.py](file:///mnt/c/Users/Sangicook/LAB_FHI/Project/Side_project/edgartools/edgar/xbrl/standardization/layers/facts_search.py)

Searches the company facts database. Only matches against **known concepts from config**.

---

### Critical Discussion: Layer Order & Validation Integration

> [!CAUTION]
> **Architectural Observation: The Current Design Has a Flaw**
> 
> The current workflow has a limitation that future developers should understand:

#### Current Design (What Actually Happens)

```mermaid
flowchart TD
    A[Layer 1: Tree Parser] --> B{Mapped?}
    B -->|No| C[Layer 2: AI Semantic]
    B -->|Yes| D[Continue]
    C --> E{Mapped?}
    E -->|No| F[Layer 3: Facts Search]
    E -->|Yes| D
    F --> D
    D --> G[All layers complete]
    G --> H[Validation against yfinance]
    H --> I{Valid?}
    I -->|No| J[Mark as INVALID - but no retry!]
    I -->|Yes| K[Done]
```

**Problem:** Validation happens **AFTER** all layers complete. If AI finds a mapping but it fails validation, we **don't retry** with the next layer.

#### Implemented Architecture (After Restructure)

> [!TIP]
> **This architecture has been implemented!**
> 
> The workflow now follows the improved design with validation-in-loop.

A properly resolved concept has **two properties** (see `is_resolved` property in `models.py`):
1. ✅ **Mapped** - We found an XBRL concept
2. ✅ **Validated** - The value matches yfinance reference

```mermaid
flowchart TD
    A[Layer 1: Tree Parser] --> V1[Validate]
    V1 --> B{Gaps?}
    B -->|Yes| C[Layer 2: Facts Search - static]
    B -->|No| DONE[Done]
    C --> V2[Validate]
    V2 --> D{Gaps?}
    D -->|Yes| E[Layer 3: AI Semantic - discovery]
    D -->|No| DONE
    E --> V3[Validate]
    V3 --> F{Gaps?}
    F -->|Yes| G[Gap remains - needs investigation]
    F -->|No| DONE
```

**Key features of implemented design:**
1. **Static methods first** - Tree Parser, then Facts Search, then AI
2. **Validation in the loop** - `_validate_layer()` runs after each layer
3. **"Gap" = Unmapped OR Invalid** - Invalid mappings are reset and retried
4. **yfinance caching** - Single API call per company via `_get_stock()`

#### How Invalid Mappings Are Handled

When a layer produces a mapping that fails validation:
1. The mapping is marked as `validation_status='invalid'`
2. `_validate_layer()` resets `concept`, `confidence`, and `source`
3. The metric becomes a "gap" again
4. The next layer can attempt a fresh mapping

```python
# From _validate_layer() in orchestrator.py
if result.validation_status == 'invalid':
    result.concept = None
    result.confidence = 0.0
    result.source = MappingSource.UNKNOWN
    gaps.append(metric)  # Retry with next layer
```

#### Does AI Semantic Update `metrics.yaml` Config?

> [!NOTE]
> **No! AI Semantic does NOT automatically update `known_concepts` in config.**
> 
> During a normal orchestrator run:
> - AI Semantic finds a concept → Returns a `MappingResult`
> - The concept is used for **this run only**
> - Nothing is written to `metrics.yaml`
> 
> **Config updates happen separately** via the gap resolution workflow (either manually or through the `concept-mapping-resolver` agent). That workflow explicitly calls `update_config()` after discovering new concepts.

---

### 4. The Orchestrator: [orchestrator.py](file:///mnt/c/Users/Sangicook/LAB_FHI/Project/Side_project/edgartools/edgar/xbrl/standardization/orchestrator.py)

**The main entry point** that coordinates all layers with validation-in-loop.

```mermaid
flowchart TD
    A[Start: map_company] --> B[Layer 1: Tree Parser]
    B --> V1[_validate_layer]
    V1 --> C{Gaps?}
    C -->|Yes| D[Layer 2: Facts Search]
    C -->|No| H
    D --> V2[_validate_layer]
    V2 --> E{Gaps?}
    E -->|Yes| F[Layer 3: AI Semantic]
    E -->|No| H
    F --> V3[_validate_layer]
    V3 --> G{Gaps?}
    G -->|Yes| I[Report remaining gaps]
    G -->|No| H
    I --> H[Return Results]
```

**Key methods:**
- `map_company(ticker)` - Map all metrics for one company
- `map_companies(tickers)` - Map multiple companies (defaults to MAG7)
- `_validate_layer()` - **NEW** - Validate after each layer, returning updated gaps

**Usage:**
```python
from edgar.xbrl.standardization.orchestrator import Orchestrator

orchestrator = Orchestrator()
results = orchestrator.map_companies(['AAPL', 'GOOG', 'MSFT'])
orchestrator.print_summary(results)
```

---

### 5. Reference Validator: [reference_validator.py](file:///mnt/c/Users/Sangicook/LAB_FHI/Project/Side_project/edgartools/edgar/xbrl/standardization/reference_validator.py)

**Validates mappings against yfinance** as external truth.

Key features:
- `COMPOSITE_METRICS` dict defines metrics that sum multiple concepts
- `tolerance_pct` - 15% variance threshold
- `validate_and_update_mappings()` - Updates `MappingResult.validation_status`
- `_get_stock()` - **NEW** - Cached yfinance Stock objects to avoid redundant API calls

**Validation statuses:**
- `"valid"` - XBRL value matches yfinance within tolerance
- `"invalid"` - Variance exceeds threshold (mapping will be retried by next layer)
- `"no_ref"` - No yfinance reference available

---

### 6. AI Agent Tools: [tools/](file:///mnt/c/Users/Sangicook/LAB_FHI/Project/Side_project/edgartools/edgar/xbrl/standardization/tools)

Reusable functions for AI agents and direct use:

| Tool | Purpose |
|------|---------|
| `discover_concepts()` | Find candidate XBRL concepts from calc trees and facts |
| `check_fallback_quality()` | Validate semantic quality, reject parent-concept fallbacks |
| `verify_mapping()` | Compare extracted XBRL values against yfinance reference |
| `learn_mappings()` | Discover patterns across multiple companies |
| `resolve_all_gaps()` | Main entry point for gap resolution |

---

## The Gap Resolution Workflow

When the orchestrator leaves gaps (unmapped or invalid mappings), use the gap resolution process.

> [!IMPORTANT]
> **Is this conducted by the `concept-mapping-resolver` agent?**
> 
> **Both options are available:**
> 
> 1. **Direct Python code** - You can run `resolve_gaps.py` functions directly without any AI agent
> 2. **AI Agent** - The `concept-mapping-resolver.md` provides a prompt for Claude/AI assistants to follow this workflow systematically
> 
> The agent is just a **prompt template** that instructs an AI assistant how to use the Python tools. The actual logic lives in `tools/resolve_gaps.py` and can be called programmatically.

### Two Ways to Run Gap Resolution

**Option 1: Direct Python (No AI agent needed)**
```python
from edgar.xbrl.standardization.tools.resolve_gaps import resolve

# Run full resolution workflow programmatically
report = resolve(tickers=['AAPL', 'GOOG', 'AMZN'])
print(report)
```

**Option 2: AI Agent (for interactive/complex scenarios)**
- Open Claude or similar AI assistant
- Invoke the `concept-mapping-resolver` agent
- The agent follows the systematic workflow, investigates failures, and generates reports

```mermaid
flowchart TD
    A[Run Orchestrator] --> B[Calculate BEFORE Coverage]
    B --> C[Identify All Gaps]
    C --> D[For Each Gap]
    D --> E[discover_concepts]
    E --> F[check_fallback_quality]
    F --> G[verify_mapping]
    G --> H{Resolved?}
    H -->|Yes| I[Add to Resolutions]
    H -->|No| J[Log Failure Reason]
    I --> K[Learn Patterns]
    J --> K
    K --> L[Update Config]
    L --> M[Generate Report]
    M --> N[Calculate AFTER Coverage]
```

**Entry point:** [resolve_gaps.py](file:///mnt/c/Users/Sangicook/LAB_FHI/Project/Side_project/edgartools/edgar/xbrl/standardization/tools/resolve_gaps.py)

---

## Key Insights from Commit History

### Composite Metrics Problem (commits `139e298d`, `69c4ffbc`)

**Problem:** yfinance "Goodwill And Other Intangible Assets" sums multiple XBRL concepts, but we were extracting only one.

**Solution:** Define composite metrics that sum components:
```yaml
IntangibleAssets:
  composite: true
  components:
    - Goodwill
    - IntangibleAssetsNetExcludingGoodwill
```

### Variance Tolerance Tuning (commit `f2a8f115`)

**Problem:** 10% variance was too strict for some companies.

**Solution:** Increased to 15% to reduce false negatives while maintaining accuracy.

### XBRL Value Extraction Fixes (commit `16aea1a1`)

**Problem:** Extraction was picking up dimensional (segment-specific) values instead of consolidated totals.

**Solution:** Filter for non-dimensioned values (consolidated entity).

---

## How to Expand the System

### Adding a New Metric

1. Add to [metrics.yaml](file:///mnt/c/Users/Sangicook/LAB_FHI/Project/Side_project/edgartools/edgar/xbrl/standardization/config/metrics.yaml):
```yaml
NewMetric:
  description: "Description here"
  known_concepts:
    - ConceptName1
    - ConceptName2
  tree_hints:
    statements: [BALANCE]  # or INCOME, CASHFLOW
  universal: false
```

2. If composite, add components:
```yaml
NewMetric:
  composite: true
  components:
    - Component1
    - Component2
```

3. Run orchestrator to test:
```python
results = orchestrator.map_companies(['AAPL'])
```

### Adding a New Company

1. Run for the company:
```python
results = orchestrator.map_company('TICKER')
```

2. Review gaps and investigate:
```python
from edgar.xbrl.standardization.tools import discover_concepts
candidates = discover_concepts('MetricName', xbrl, facts_df)
```

3. Add company-specific overrides if needed to `companies.yaml`

---

## Testing & Verification

1. **Run Orchestrator:**
```bash
python -m edgar.xbrl.standardization.orchestrator --companies AAPL,GOOG
```

2. **Check Coverage:**
```python
from edgar.xbrl.standardization.tools.resolve_gaps import calculate_coverage
stats = calculate_coverage(results)
print(stats)
```

3. **Run E2E Test:**
```python
from edgar.xbrl.standardization.tools.resolve_gaps import resolve
report = resolve()  # Defaults to MAG7
```

---

## Quick Reference

| Task | Location |
|------|----------|
| Add new metric | `config/metrics.yaml` |
| Add company override | `config/companies.yaml` |
| Debug mapping | `TreeParser.map_metric()` |
| Add composite metric | `metrics.yaml` + `reference_validator.py` |
| Run full pipeline | `orchestrator.py` |
| Resolve gaps | `tools/resolve_gaps.py` |
| AI agent config | `.claude/agents/concept-mapping-resolver.md` |

---

## The AI Agent: concept-mapping-resolver

The [concept-mapping-resolver.md](file:///mnt/c/Users/Sangicook/LAB_FHI/Project/Side_project/edgartools/.claude/agents/concept-mapping-resolver.md) is an AI agent prompt that:

1. **Analyzes all gaps** from orchestrator results
2. **Resolves each gap** using AI tools in sequence
3. **Learns cross-company patterns** for metrics that fail in multiple companies
4. **Auto-updates config** with newly discovered concepts
5. **Generates reports** with before/after coverage
6. **Investigates unresolved issues** with detailed root cause analysis

This agent can be invoked by Claude or similar AI assistants to systematically improve mapping coverage.

---

## Summary

The concept mapping system uses a **multi-layer fallback architecture** with **validation-in-loop** to map company-specific XBRL concepts to standardized metrics:

1. **Layer 1 (Tree Parser)** - Primary, handles ~85%
2. **Layer 2 (Facts Search)** - Static lookup for known concepts
3. **Layer 3 (AI Semantic)** - Dynamic discovery for new concepts
4. **Validation after each layer** - Invalid mappings retry with next layer

The system is **configurable** via YAML, **extensible** with new metrics/companies, and **self-improving** through the AI agent tools that discover patterns and update configuration.

---

## E2E Test Results (2026-01-08)

### MAG7 Companies (Without AI Layer)

| Company | Resolved | Coverage |
|---------|----------|----------|
| AAPL    | 14/14    | 100%     |
| GOOG    | 14/14    | 100%     |
| MSFT    | 13/14    | 93%      |
| AMZN    | 13/14    | 93%      |
| META    | 13/13    | 100%     |
| NVDA    | 12/14    | 86%      |
| TSLA    | 10/14    | 71%      |
| **TOTAL** | **89/97** | **91.8%** |

### SP500 Random Sample - AI Layer Impact

Comparison test on 10 random SP500 companies:

| Metric | Without AI | With AI |
|--------|------------|---------|
| Coverage | 70.7% | **80.7%** |
| Improvement | - | **+14 metrics** |

**Key finding**: AI layer provides +10% coverage improvement, primarily helping when:
- Concepts are not in our `known_concepts` config
- Companies use non-standard concept names
- Local filing data was unavailable (AI still works via calc tree context)

Most remaining gaps are **validation failures** (value mismatch), not missing mappings.

### E2E with Diverse SP500 Companies (10 companies)

Tested with: JPM, WMT, CVS, XOM, CMCSA, UNH, HD, PFE, KO, DIS

| Metric | Result |
|--------|--------|
| Coverage | **86.4% (121/140)** |
| AI Resolution | 0% (all gaps structural/validation) |
| Sectors | Finance, Retail, Healthcare, Energy, Media |

---

## Understanding Gap Types

Based on real-world testing (commit `6977c22d`), gaps fall into three categories:

| Type | Description | Resolution |
|------|-------------|------------|
| **Structural** | Metric doesn't exist (banks lack COGS) | Exclude in config |
| **Validation** | Mapping exists but value mismatch | Investigate definition |
| **Unmapped** | No concept found | Use AI tools |

---

## Dimensional Reporting Issues

> [!CAUTION]
> **Key Discovery from JPM Investigation (commit `3c09bd5a`)**
>
> Current validator filters ALL dimensional values, but some companies report concepts ONLY with dimensions.

**Example: JPM CommercialPaper**
- `ShortTermBorrowings`: $52.89B (non-dimensioned, extracted ✓)
- `CommercialPaper`: $21.80B (dimensioned as "VIE", filtered out ✗)
- Gap vs yfinance: 18% variance

**Root cause:** JPM reports CommercialPaper ONLY under "Beneficial interests issued by consolidated VIEs" dimension.

**Recommendations:**
1. **Short-term:** Industry-specific tolerance (20% for financials)
2. **Long-term:** Selective dimensional value inclusion framework

See: [jpm_investigation_summary.md](file:///mnt/c/Users/Sangicook/LAB_FHI/Project/Side_project/edgartools/sandbox/notes/005_calculation_tree_study/jpm_investigation_summary.md)
