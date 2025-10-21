"""
Abstract concept detection for XBRL elements.

This module provides utilities to determine if an XBRL concept should be marked as abstract,
using multiple fallback strategies when taxonomy schema information is not available.

Background:
-----------
EdgarTools currently only parses company-specific XSD schema files included in SEC filings.
Standard taxonomy schemas (US-GAAP, DEI, etc.) are referenced externally and not parsed.
This means concepts from standard taxonomies are added to the element catalog without their
abstract attribute information, defaulting to abstract=False.

Solution:
---------
This module implements a multi-tier fallback strategy for abstract detection:
1. Trust schema abstract attribute (if available and True)
2. Check known abstract concepts (explicit list)
3. Pattern matching on concept name
4. Structural heuristics (has children but no values)

See: Issue #450 - Statement of Equity rendering problems
"""

import re
from typing import List, Set

# Known abstract concepts from US-GAAP taxonomy
# These are explicitly marked abstract="true" in the US-GAAP taxonomy schemas
KNOWN_ABSTRACT_CONCEPTS: Set[str] = {
    # Statement abstracts
    'us-gaap_StatementOfFinancialPositionAbstract',
    'us-gaap_StatementOfStockholdersEquityAbstract',
    'us-gaap_StatementOfIncomeAndComprehensiveIncomeAbstract',
    'us-gaap_StatementOfCashFlowsAbstract',
    'us-gaap_IncomeStatementAbstract',

    # Roll forward abstracts
    'us-gaap_IncreaseDecreaseInStockholdersEquityRollForward',
    'us-gaap_PropertyPlantAndEquipmentRollForward',
    'us-gaap_IntangibleAssetsRollForward',
    'us-gaap_LongTermDebtRollForward',

    # Reconciliation abstracts
    'us-gaap_AdjustmentsToReconcileNetIncomeLossToCashProvidedByUsedInOperatingActivitiesAbstract',

    # Table and axis abstracts
    'us-gaap_StatementTable',
    'us-gaap_StatementLineItems',
    'us-gaap_StatementEquityComponentsAxis',
    'us-gaap_EquityComponentDomain',

    # Accounting policies
    'us-gaap_AccountingPoliciesAbstract',
    'us-gaap_SignificantAccountingPoliciesTextBlock',

    # Disclosure abstracts
    'us-gaap_DisclosureTextBlockAbstract',

    # Document and entity information (DEI)
    'dei_DocumentInformationAbstract',
    'dei_EntityInformationAbstract',
    'dei_CoverAbstract',
}

# Patterns that indicate a concept is likely abstract
# These are based on XBRL naming conventions
ABSTRACT_CONCEPT_PATTERNS: List[str] = [
    r'.*Abstract$',           # Ends with "Abstract"
    r'.*RollForward$',        # Ends with "RollForward" (roll forward tables)
    r'.*Table$',              # Ends with "Table" (dimensional tables)
    r'.*Axis$',               # Ends with "Axis" (dimensional axes)
    r'.*Domain$',             # Ends with "Domain" (dimension domains)
    r'.*LineItems$',          # Ends with "LineItems" (line item tables)
    r'.*TextBlock$',          # Ends with "TextBlock" (disclosure text blocks)
]


def is_abstract_concept(
    concept_name: str,
    schema_abstract: bool = False,
    has_children: bool = False,
    has_values: bool = False
) -> bool:
    """
    Determine if an XBRL concept should be marked as abstract using multiple fallback strategies.

    Strategy priority:
    1. Trust schema if it explicitly says abstract=True
    2. Check against known abstract concepts list
    3. Apply pattern matching on concept name
    4. Use structural heuristics (has children but no values)
    5. Default to schema value or False

    Args:
        concept_name: The XBRL concept name (e.g., "us-gaap_StatementOfStockholdersEquityAbstract")
        schema_abstract: The abstract attribute from the schema (if available)
        has_children: Whether this concept has children in the presentation tree
        has_values: Whether this concept has fact values in the instance

    Returns:
        True if the concept should be marked as abstract, False otherwise

    Examples:
        >>> is_abstract_concept('us-gaap_StatementOfStockholdersEquityAbstract')
        True

        >>> is_abstract_concept('us-gaap_Revenue')
        False

        >>> is_abstract_concept('us-gaap_SomethingRollForward')
        True

        >>> is_abstract_concept('us-gaap_UnknownConcept', has_children=True, has_values=False)
        True
    """
    # Strategy 1: Trust schema if it says True
    if schema_abstract:
        return True

    # Strategy 2: Check known abstract concepts
    if concept_name in KNOWN_ABSTRACT_CONCEPTS:
        return True

    # Strategy 3: Pattern matching
    for pattern in ABSTRACT_CONCEPT_PATTERNS:
        if re.match(pattern, concept_name):
            return True

    # Strategy 4: Structural heuristics
    # If a concept has children in the presentation tree but no fact values,
    # it's likely an abstract header
    if has_children and not has_values:
        return True

    # Strategy 5: Default to schema value (or False if not provided)
    return schema_abstract


def add_known_abstract_concept(concept_name: str) -> None:
    """
    Add a concept to the known abstracts list.

    This allows runtime extension of the known abstracts list when new abstract
    concepts are discovered that don't match existing patterns.

    Args:
        concept_name: The XBRL concept name to add
    """
    KNOWN_ABSTRACT_CONCEPTS.add(concept_name)


def add_abstract_pattern(pattern: str) -> None:
    """
    Add a pattern to the abstract pattern list.

    Args:
        pattern: Regular expression pattern to match abstract concepts
    """
    ABSTRACT_CONCEPT_PATTERNS.append(pattern)


def get_known_abstract_concepts() -> Set[str]:
    """
    Get the set of known abstract concepts.

    Returns:
        Set of concept names known to be abstract
    """
    return KNOWN_ABSTRACT_CONCEPTS.copy()


def get_abstract_patterns() -> List[str]:
    """
    Get the list of abstract concept patterns.

    Returns:
        List of regex patterns used to identify abstract concepts
    """
    return ABSTRACT_CONCEPT_PATTERNS.copy()
