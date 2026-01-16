"""
XBRL concept standardization package.

This package provides functionality to map company-specific XBRL concepts
to standardized concept names, enabling consistent presentation of financial
statements regardless of the filing entity.

Pipeline Optimization:
    - Module-level singletons for MappingStore and ConceptMapper
    - Use get_default_mapper() instead of creating new instances
    - Eliminates redundant file I/O and object allocation
"""

from typing import Optional

from edgar.xbrl.standardization.core import ConceptMapper, MappingStore, StandardConcept, initialize_default_mappings, standardize_statement
from edgar.xbrl.standardization.cache import StandardizationCache

# Module-level singletons for performance optimization
_default_store: Optional[MappingStore] = None
_default_mapper: Optional[ConceptMapper] = None


def get_default_store() -> MappingStore:
    """
    Get the module-level singleton MappingStore.

    This eliminates redundant file I/O by loading mappings once per session
    instead of on every statement call.

    Returns:
        The default MappingStore instance
    """
    global _default_store
    if _default_store is None:
        _default_store = initialize_default_mappings(read_only=True)
    return _default_store


def get_default_mapper() -> ConceptMapper:
    """
    Get the module-level singleton ConceptMapper.

    This eliminates redundant object allocation by reusing the same mapper
    across all statement standardization calls.

    Returns:
        The default ConceptMapper instance
    """
    global _default_mapper
    if _default_mapper is None:
        _default_mapper = ConceptMapper(get_default_store())
    return _default_mapper


__all__ = [
    'StandardConcept',
    'MappingStore',
    'ConceptMapper',
    'StandardizationCache',
    'standardize_statement',
    'initialize_default_mappings',
    'get_default_store',
    'get_default_mapper',
]
