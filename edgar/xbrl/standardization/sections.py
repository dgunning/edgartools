"""
Section membership lookups for XBRL standardization.

This module provides APIs for determining which section a standard concept
belongs to within a financial statement. This is foundational for
context-aware disambiguation of ambiguous XBRL tags.

Phase 2 of Context-Aware Standardization (Issue #494).
"""

import json
import logging
import os
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class SectionMembership:
    """
    Lookup service for standard concept section membership.

    Maps standard concepts to their sections within financial statements,
    enabling context-aware disambiguation for ambiguous XBRL tags.

    Example:
        >>> sections = SectionMembership()
        >>> sections.get_section("TradeReceivables", "BalanceSheet")
        'Current Assets'
        >>> sections.get_section("LongTermDebt", "BalanceSheet")
        'Non-Current Liabilities'
        >>> sections.get_statement_sections("BalanceSheet")
        ['Current Assets', 'Non-Current Assets', 'Current Liabilities', ...]
    """

    def __init__(self, membership_path: Optional[str] = None):
        """
        Initialize the section membership lookup.

        Args:
            membership_path: Path to section_membership.json. If None, uses default.
        """
        if membership_path is None:
            module_dir = os.path.dirname(os.path.abspath(__file__))
            membership_path = os.path.join(module_dir, "section_membership.json")

        self._data = self._load_json(membership_path)
        self._reverse_index = self._build_reverse_index()

        # Statistics
        self._stats = self._calculate_stats()

        logger.info(
            "SectionMembership initialized: %d statements, %d sections, %d concepts",
            self._stats["statement_count"],
            self._stats["section_count"],
            self._stats["concept_count"]
        )

    def _load_json(self, path: str) -> dict:
        """Load a JSON file, returning empty dict on failure."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Remove metadata key if present
                data.pop('_metadata', None)
                return data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning("Failed to load %s: %s", path, e)
            return {}

    def _build_reverse_index(self) -> Dict[str, Dict[str, str]]:
        """
        Build reverse index: concept → {statement: section}.

        Returns:
            Dict mapping concept to dict of {statement_type: section_name}
        """
        index: Dict[str, Dict[str, str]] = {}

        for statement_type, sections in self._data.items():
            for section_name, concepts in sections.items():
                for concept in concepts:
                    if concept not in index:
                        index[concept] = {}
                    index[concept][statement_type] = section_name

        return index

    def _calculate_stats(self) -> Dict[str, int]:
        """Calculate statistics about section membership."""
        statement_count = len(self._data)
        section_count = sum(len(sections) for sections in self._data.values())
        concept_count = len(self._reverse_index)

        return {
            "statement_count": statement_count,
            "section_count": section_count,
            "concept_count": concept_count
        }

    def get_section(
        self,
        concept: str,
        statement_type: Optional[str] = None
    ) -> Optional[str]:
        """
        Get the section a concept belongs to.

        Args:
            concept: Standard concept name (e.g., "TradeReceivables")
            statement_type: Optional statement type to filter by
                           (e.g., "BalanceSheet", "IncomeStatement")

        Returns:
            Section name (e.g., "Current Assets") or None if not found
        """
        concept_sections = self._reverse_index.get(concept)
        if concept_sections is None:
            return None

        if statement_type is not None:
            return concept_sections.get(statement_type)

        # Return first section found if no statement type specified
        return next(iter(concept_sections.values()), None)

    def get_statement_for_concept(self, concept: str) -> Optional[str]:
        """
        Get the primary statement type for a concept.

        Args:
            concept: Standard concept name

        Returns:
            Statement type (e.g., "BalanceSheet") or None if not found
        """
        concept_sections = self._reverse_index.get(concept)
        if concept_sections is None:
            return None

        # Return first statement type found
        return next(iter(concept_sections.keys()), None)

    def get_all_sections_for_concept(self, concept: str) -> Dict[str, str]:
        """
        Get all statement/section mappings for a concept.

        Args:
            concept: Standard concept name

        Returns:
            Dict of {statement_type: section_name}
        """
        return self._reverse_index.get(concept, {}).copy()

    def get_statement_sections(self, statement_type: str) -> List[str]:
        """
        Get all sections for a statement type.

        Args:
            statement_type: Statement type (e.g., "BalanceSheet")

        Returns:
            List of section names in order
        """
        statement_data = self._data.get(statement_type, {})
        return list(statement_data.keys())

    def get_concepts_in_section(
        self,
        statement_type: str,
        section: str
    ) -> List[str]:
        """
        Get all concepts in a specific section.

        Args:
            statement_type: Statement type (e.g., "BalanceSheet")
            section: Section name (e.g., "Current Assets")

        Returns:
            List of concept names
        """
        statement_data = self._data.get(statement_type, {})
        return statement_data.get(section, []).copy()

    def get_all_statements(self) -> List[str]:
        """Get list of all statement types."""
        return list(self._data.keys())

    def is_current(self, concept: str) -> Optional[bool]:
        """
        Check if a balance sheet concept is current (vs non-current).

        Args:
            concept: Standard concept name

        Returns:
            True if current, False if non-current, None if not applicable
        """
        section = self.get_section(concept, "BalanceSheet")
        if section is None:
            return None

        section_lower = section.lower()
        if "current" in section_lower and "non-current" not in section_lower:
            return True
        elif "non-current" in section_lower:
            return False

        return None

    def is_asset(self, concept: str) -> Optional[bool]:
        """
        Check if a balance sheet concept is an asset (vs liability/equity).

        Args:
            concept: Standard concept name

        Returns:
            True if asset, False if liability/equity, None if not applicable
        """
        section = self.get_section(concept, "BalanceSheet")
        if section is None:
            return None

        section_lower = section.lower()
        if "asset" in section_lower:
            return True
        elif "liabilit" in section_lower or "equity" in section_lower:
            return False

        # Check section name for totals
        if section == "Totals":
            concept_lower = concept.lower()
            if "asset" in concept_lower:
                return True
            elif "liabilit" in concept_lower or "equity" in concept_lower:
                return False

        return None

    def is_liability(self, concept: str) -> Optional[bool]:
        """
        Check if a balance sheet concept is a liability.

        Args:
            concept: Standard concept name

        Returns:
            True if liability, False otherwise, None if not applicable
        """
        section = self.get_section(concept, "BalanceSheet")
        if section is None:
            return None

        return "liabilit" in section.lower()

    def is_equity(self, concept: str) -> Optional[bool]:
        """
        Check if a balance sheet concept is equity.

        Args:
            concept: Standard concept name

        Returns:
            True if equity, False otherwise, None if not applicable
        """
        section = self.get_section(concept, "BalanceSheet")
        if section is None:
            return None

        return "equity" in section.lower()

    @property
    def stats(self) -> Dict[str, int]:
        """Get statistics about section membership."""
        return self._stats.copy()

    def __len__(self) -> int:
        """Return the number of concepts mapped."""
        return len(self._reverse_index)

    def __contains__(self, concept: str) -> bool:
        """Check if a concept is in the membership index."""
        return concept in self._reverse_index


# Module-level singleton
_default_membership: Optional[SectionMembership] = None


def get_section_membership() -> SectionMembership:
    """
    Get the default section membership singleton.

    Returns:
        The default SectionMembership instance
    """
    global _default_membership
    if _default_membership is None:
        _default_membership = SectionMembership()
    return _default_membership


def get_section_for_concept(
    concept: str,
    statement_type: Optional[str] = None
) -> Optional[str]:
    """
    Convenience function to get section for a concept.

    Args:
        concept: Standard concept name
        statement_type: Optional statement type filter

    Returns:
        Section name or None
    """
    return get_section_membership().get_section(concept, statement_type)


def get_statement_for_concept(concept: str) -> Optional[str]:
    """
    Convenience function to get statement type for a concept.

    Args:
        concept: Standard concept name

    Returns:
        Statement type or None
    """
    return get_section_membership().get_statement_for_concept(concept)


def is_current(concept: str) -> Optional[bool]:
    """
    Convenience function to check if concept is current.

    Args:
        concept: Standard concept name

    Returns:
        True if current, False if non-current, None if not applicable
    """
    return get_section_membership().is_current(concept)


def is_asset(concept: str) -> Optional[bool]:
    """
    Convenience function to check if concept is an asset.

    Args:
        concept: Standard concept name

    Returns:
        True if asset, False otherwise, None if not applicable
    """
    return get_section_membership().is_asset(concept)
