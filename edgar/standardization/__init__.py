"""
Shared Standardization Infrastructure for EdgarTools.

This module provides centralized standardization components used by both
XBRL and EntityFacts APIs, enabling consistent cross-company financial analysis.

Components:
    - SynonymGroups: Unified synonym management for XBRL tags
    - (Future) StandardizationProfile: Granularity profile management

Example:
    >>> from edgar.standardization import SynonymGroups, get_synonym_groups
    >>>
    >>> # Get default singleton instance
    >>> synonyms = get_synonym_groups()
    >>>
    >>> # Look up synonyms for a concept
    >>> tags = synonyms.get_synonyms('revenue')
    >>> print(tags[:2])
    ['RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues']

See Also:
    - docs-internal/planning/features/comprehensive-synonym-analysis-solutions.md
    - docs-internal/research/codebase/2025-12-06-entityfacts-xbrl-standardization-sequencing.md
"""

from edgar.standardization.synonym_groups import (
    ConceptInfo,
    SynonymGroup,
    SynonymGroups,
    get_synonym_groups,
)

__all__ = [
    'SynonymGroup',
    'SynonymGroups',
    'ConceptInfo',
    'get_synonym_groups',
]
