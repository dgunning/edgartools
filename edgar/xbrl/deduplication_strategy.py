"""
Revenue Deduplication Strategy for Issue #438

This module implements intelligent deduplication for revenue concepts
that may have the same underlying value but different GAAP concept names.

The strategy:
1. Identify groups of items with the same value in the same period
2. Apply hierarchical precedence rules to choose the most appropriate concept
3. Filter out less specific concepts when duplicates exist

Revenue Concept Hierarchy (most to least preferred):
1. us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax (most specific - ASC 606)
2. us-gaap:Revenues (standard general concept)
3. us-gaap:SalesRevenueNet (less common)
4. us-gaap:Revenue (least specific)
"""

import logging
from collections import defaultdict
from typing import Any, Dict, List, Set

log = logging.getLogger(__name__)


class RevenueDeduplicator:
    """
    Handles deduplication of revenue concepts in financial statements.
    """

    # Revenue concept precedence (higher number = higher precedence)
    REVENUE_CONCEPT_PRECEDENCE = {
        'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax': 100,  # Most specific (ASC 606)
        'us-gaap:Revenues': 90,  # Standard concept
        'us-gaap:SalesRevenueNet': 80,  # Alternative concept
        'us-gaap:Revenue': 70,  # Generic concept
        'us-gaap:TotalRevenuesAndGains': 60,  # Broader concept
    }

    # Additional revenue-related concepts that might cause duplicates
    REVENUE_RELATED_CONCEPTS = {
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'Revenues', 
        'Revenue',
        'SalesRevenueNet',
        'TotalRevenuesAndGains',
        'RevenueFromContractWithCustomer',
        'TotalRevenues'
    }

    @classmethod
    def deduplicate_statement_items(cls, statement_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate revenue concepts from statement items.

        Args:
            statement_items: List of statement line items

        Returns:
            Filtered list with duplicates removed
        """
        if not statement_items:
            return statement_items

        # Group items by period and value to find potential duplicates
        period_value_groups = cls._group_by_period_value(statement_items)

        # Identify items to remove
        items_to_remove = set()

        for (_period, _value), items in period_value_groups.items():
            if len(items) > 1 and cls._are_revenue_duplicates(items):
                # This is a group of revenue items with the same value
                # Keep only the highest precedence item
                items_to_remove.update(cls._select_duplicates_to_remove(items))

        # Filter out the items marked for removal
        result = []
        for i, item in enumerate(statement_items):
            if i not in items_to_remove:
                result.append(item)
            else:
                log.debug("Removed duplicate revenue item: %s = %s", item.get('label', 'Unknown'), item.get('values', {}))

        removed_count = len(statement_items) - len(result)
        if removed_count > 0:
            log.info("Revenue deduplication: removed %d duplicate items", removed_count)

        return result

    @classmethod
    def _group_by_period_value(cls, statement_items: List[Dict[str, Any]]) -> Dict[tuple, List[tuple]]:
        """
        Group statement items by (period, value) pairs.

        Returns:
            Dict mapping (period, value) to list of (index, item) tuples
        """
        groups = defaultdict(list)

        for i, item in enumerate(statement_items):
            values = item.get('values', {})
            for period, value in values.items():
                if value is not None and value != 0:
                    groups[(period, value)].append((i, item))

        return groups

    @classmethod
    def _are_revenue_duplicates(cls, indexed_items: List[tuple]) -> bool:
        """
        Check if a group of items are revenue duplicates.

        Args:
            indexed_items: List of (index, item) tuples

        Returns:
            True if these items are revenue duplicates
        """
        revenue_count = 0

        for _, item in indexed_items:
            if cls._is_revenue_concept(item):
                revenue_count += 1

        # If we have multiple revenue concepts, they're potential duplicates
        return revenue_count > 1

    @classmethod
    def _is_revenue_concept(cls, item: Dict[str, Any]) -> bool:
        """
        Check if an item represents a revenue concept.
        """
        concept = item.get('concept', '')
        all_names = item.get('all_names', [])
        label = item.get('label', '').lower()

        # First check for exclusions (costs, expenses, etc.)
        exclusion_terms = ['cost', 'expense', 'loss', 'depreciation', 'amortization']
        for name in [concept] + all_names + [label]:
            if any(excl in name.lower() for excl in exclusion_terms):
                return False

        # Look for revenue-related terms in concept or names
        for name in [concept] + all_names:
            if any(term in name for term in cls.REVENUE_RELATED_CONCEPTS):
                return True

        # Also check label for revenue indicators (but not cost-related)
        if any(term in label for term in ['revenue', 'sales']) and not any(excl in label for excl in exclusion_terms):
            return True

        return False

    @classmethod
    def _select_duplicates_to_remove(cls, indexed_items: List[tuple]) -> Set[int]:
        """
        Select which items to remove from a duplicate group.

        Args:
            indexed_items: List of (index, item) tuples

        Returns:
            Set of indices to remove
        """
        if len(indexed_items) <= 1:
            return set()

        # Score each item by precedence
        scored_items = []
        for index, item in indexed_items:
            score = cls._get_precedence_score(item)
            scored_items.append((score, index, item))

        # Sort by score (highest first)
        scored_items.sort(reverse=True)

        # Keep the highest scored item, remove the rest
        indices_to_remove = set()
        for i in range(1, len(scored_items)):  # Skip first (highest scored)
            _, index, item = scored_items[i]
            indices_to_remove.add(index)

        return indices_to_remove

    @classmethod
    def _get_precedence_score(cls, item: Dict[str, Any]) -> int:
        """
        Get the precedence score for a revenue concept.

        Higher scores are preferred and will be kept.
        """
        concept = item.get('concept', '')
        all_names = item.get('all_names', [])

        # Check for exact matches in precedence table
        for name in [concept] + all_names:
            if name in cls.REVENUE_CONCEPT_PRECEDENCE:
                return cls.REVENUE_CONCEPT_PRECEDENCE[name]

        # Check for partial matches (handle namespace prefixes)
        for name in [concept] + all_names:
            for precedence_concept, score in cls.REVENUE_CONCEPT_PRECEDENCE.items():
                if precedence_concept.split(':')[-1] in name:
                    return score

        # Default score for unrecognized revenue concepts
        return 50

    @classmethod
    def get_deduplication_stats(cls, original_items: List[Dict[str, Any]], 
                              deduplicated_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate statistics about the deduplication process.
        """
        original_count = len(original_items)
        deduplicated_count = len(deduplicated_items)
        removed_count = original_count - deduplicated_count

        # Count revenue items
        original_revenue_count = sum(1 for item in original_items if cls._is_revenue_concept(item))
        deduplicated_revenue_count = sum(1 for item in deduplicated_items if cls._is_revenue_concept(item))

        return {
            'original_total_items': original_count,
            'deduplicated_total_items': deduplicated_count,
            'removed_items': removed_count,
            'original_revenue_items': original_revenue_count,
            'deduplicated_revenue_items': deduplicated_revenue_count,
            'removed_revenue_items': original_revenue_count - deduplicated_revenue_count,
            'deduplication_performed': removed_count > 0
        }
