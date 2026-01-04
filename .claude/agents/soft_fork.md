---
name: soft-fork-protocol
description: Canonical reference document defining the Soft Fork Protocol - architectural guidelines for extending edgar/ library functionality through quant/ package without modifying core files. Referenced by all agents to ensure consistent adherence to read-only core, inheritance-based extension, and proper import patterns.
type: reference
---

# Soft Fork Protocol (Required)

## Purpose

The **Soft Fork Protocol** ensures that experimental or domain-specific features can be developed in `quant/` without modifying the stable, production-ready `edgar/` library. This separation allows:

- **Safe experimentation** with new financial metrics and calculations
- **Backward compatibility** - `edgar/` remains stable for existing users
- **Clean separation** between core library and quantitative analysis features
- **Easy testing** - new features can be tested in isolation

## Core Principles

### 1. Read-Only Core Library

**NEVER modify files in `edgar/` directory.**

The `edgar/` library is stable, well-tested, and used in production. All new quantitative features, experimental calculations, or domain-specific enhancements MUST go in `quant/`.

### 2. Extension Through Inheritance

Extend `edgar/` classes using Python inheritance in `quant/`. Always call `super()` to preserve parent behavior.

**Example:**
```python
# quant/core.py
from edgar import Company

class QuantCompany(Company):
    """Extended Company with quantitative features."""

    def __init__(self, ticker: str):
        super().__init__(ticker)  # ✓ Preserve parent initialization

    def get_ttm_metrics(self):
        """New method - adds TTM calculations."""
        # Your new functionality here
        pass
```

### 3. Relative Imports Within quant/

Inside `quant/` modules, use relative imports to reference other `quant/` modules. This keeps the package self-contained.

**Example:**
```python
# quant/core.py
from .utils import TTMCalculator, detect_splits  # ✓ Relative import
from .entity_facts_wrapper import EnhancedEntityFacts  # ✓ Relative import

# Import from edgar/ using absolute imports
from edgar import Company  # ✓ Absolute import for edgar/
from edgar.entity.entity_facts import EntityFacts  # ✓ Absolute import
```

### 4. Module Organization

```
quant/
├── __init__.py           # Public API exports
├── core.py               # Main extensions (QuantCompany, etc.)
├── utils.py              # Utility functions (TTMCalculator, split detection)
├── entity_facts_wrapper.py  # Wrappers for edgar classes
├── markdown/             # Markdown rendering extensions
├── quality/              # Data quality checks
├── test/                 # Test scripts and debugging
├── tests/                # pytest test suite
└── xbrl_standardize/     # XBRL standardization tools
```

## Guidelines

### ✓ DO

- **Extend through inheritance:** `class QuantCompany(Company):`
- **Call super() in overridden methods:** `super().__init__(ticker)`
- **Use relative imports in quant/:** `from .utils import TTMCalculator`
- **Add new methods to extended classes:** `def get_ttm_metrics(self):`
- **Import from edgar/ with absolute imports:** `from edgar import Company`
- **Put all new features in quant/:** New calculations, metrics, formatters

### ✗ DON'T

- **Modify edgar/ files** - This breaks the soft fork principle
- **Copy-paste edgar/ code** - Use inheritance instead
- **Use absolute imports within quant/** - Use relative imports like `from .utils`
- **Mix quant/ logic into edgar/** - Keep separation clean
- **Skip super() calls** - This breaks parent functionality

## Real-World Examples

### Example 1: Extending Company Class

```python
# quant/core.py
from edgar import Company
from .utils import TTMCalculator, detect_splits, apply_split_adjustments

class QuantCompany(Company):
    """
    Company subclass with quantitative features:
    - TTM (Trailing Twelve Months) calculations
    - Automatic stock split adjustments
    - Quarterly data derivation (Q4 from FY)
    """

    def _get_adjusted_facts(self) -> List[FinancialFact]:
        """Get facts with stock split adjustments applied."""
        ef = self.facts  # ✓ Use parent's facts property
        if not ef or not ef._facts:
            return []

        facts = ef._facts
        splits = detect_splits(facts)  # ✓ Use utility from quant/utils

        if splits:
            facts = apply_split_adjustments(facts, splits)

        return facts

    def get_ttm_statement(self, statement_type: str = "income"):
        """New feature: Get TTM financial statement."""
        facts = self._get_adjusted_facts()
        calculator = TTMCalculator()  # ✓ Use quant/ utility
        return calculator.build_ttm(facts, statement_type)
```

### Example 2: Using Utilities

```python
# quant/utils.py
from typing import List, Dict
from edgar.entity.models import FinancialFact

class TTMCalculator:
    """Calculate Trailing Twelve Months metrics."""

    def build_ttm(self, facts: List[FinancialFact], statement_type: str):
        # Implementation here
        pass

def detect_splits(facts: List[FinancialFact]) -> List[Dict]:
    """Detect stock splits from share count changes."""
    # Implementation here
    pass
```

### Example 3: Public API

```python
# quant/__init__.py
"""
Quantitative analysis extensions for edgartools.
Provides TTM calculations, split adjustments, and enhanced metrics.
"""

from .core import QuantCompany
from .utils import TTMCalculator, TTMMetric

__all__ = [
    'QuantCompany',
    'TTMCalculator',
    'TTMMetric',
]
```

## Usage Pattern

```python
# User code
from quant import QuantCompany  # ✓ Use extended class

# Create instance
company = QuantCompany("AAPL")

# Use parent Company features (inherited)
print(company.name)  # ✓ Works via inheritance
filings = company.get_filings(form="10-K")  # ✓ Works via inheritance

# Use new quant features
ttm_income = company.get_ttm_statement("income")  # ✓ New feature
adjusted_facts = company._get_adjusted_facts()  # ✓ New feature
```

## Testing

Keep tests organized:
- `quant/tests/` - pytest test suite (run with `pytest quant/tests/`)
- `quant/test/` - Debug scripts and one-off analysis

## Summary

The Soft Fork Protocol is simple:

1. **Never touch `edgar/`** - It's read-only
2. **Extend via inheritance** - Subclass in `quant/core.py`
3. **Use relative imports** - `from .utils import ...` within `quant/`
4. **Call super()** - Preserve parent behavior
5. **Organize cleanly** - Keep `quant/` modular and well-structured

This ensures `edgar/` remains stable while `quant/` can evolve rapidly with new quantitative features.
