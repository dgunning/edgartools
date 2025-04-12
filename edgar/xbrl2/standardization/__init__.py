"""
XBRL concept standardization package.

This package provides functionality to map company-specific XBRL concepts
to standardized concept names, enabling consistent presentation of financial
statements regardless of the filing entity.
"""

from edgar.xbrl2.standardization.core import (
    StandardConcept, 
    MappingStore, 
    ConceptMapper, 
    standardize_statement, 
    initialize_default_mappings
)

__all__ = [
    'StandardConcept',
    'MappingStore', 
    'ConceptMapper', 
    'standardize_statement',
    'initialize_default_mappings'
]