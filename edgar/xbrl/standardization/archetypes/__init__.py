"""
Accounting Archetype Classification System

This module provides the archetype classification system for the
Evolutionary Normalization Engine (ENE).

Five Accounting Archetypes:
- A (Standard Industrial): ~60% of S&P500 - manufacturing, retail, tech hardware
- B (Inverted Financial): Banks - inverted P&L, interest is revenue
- C (Intangible Digital): SaaS, Pharma - high intangibles, R&D capitalization
- D (Asset Passthrough): REITs - property-based, FFO instead of EPS
- E (Probabilistic Liability): Insurance - underwriting, claims reserves

Usage:
    from edgar.xbrl.standardization.archetypes import (
        AccountingArchetype,
        classify_company,
        get_archetype_definition,
    )

    # Classify a company
    archetype = classify_company(ticker='JPM', sic='6020')
    print(f"JPM is archetype: {archetype.value}")

    # Get archetype definition
    definition = get_archetype_definition(archetype)
    print(f"Strategies: {definition['strategies']}")
"""

from .definitions import (
    AccountingArchetype,
    BankSubArchetype,
    ARCHETYPE_DEFINITIONS,
    BANK_SUB_ARCHETYPE_DEFINITIONS,
    get_archetype_definition,
    get_bank_sub_archetype_definition,
)

from .classifier import (
    classify_company,
    classify_by_sic,
    classify_by_gics,
    detect_bank_sub_archetype,
)

__all__ = [
    # Enums
    'AccountingArchetype',
    'BankSubArchetype',
    # Definitions
    'ARCHETYPE_DEFINITIONS',
    'BANK_SUB_ARCHETYPE_DEFINITIONS',
    'get_archetype_definition',
    'get_bank_sub_archetype_definition',
    # Classification functions
    'classify_company',
    'classify_by_sic',
    'classify_by_gics',
    'detect_bank_sub_archetype',
]
