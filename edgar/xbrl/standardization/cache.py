"""
Standardization cache for XBRL instances.

This module provides caching of standardization results at the XBRL instance level,
eliminating redundant computation when accessing multiple statements from the same filing.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from edgar.xbrl.xbrl import XBRL
    from edgar.xbrl.standardization.core import ConceptMapper


class StandardizationCache:
    """
    Cache standardization results at the XBRL instance level.

    This cache provides:
    - Per-concept label caching (avoids repeated mapper lookups)
    - Per-statement data caching (avoids re-standardizing same statement)
    - Single mapper instance per XBRL (uses module-level singleton)

    The cache is tied to a specific XBRL instance and is invalidated when
    the instance is garbage collected.

    Example:
        >>> xbrl = filing.xbrl()
        >>> # First call standardizes and caches
        >>> income_data = xbrl.standardization.standardize_statement_data(
        ...     raw_data, 'IncomeStatement'
        ... )
        >>> # Second call returns cached result
        >>> income_data = xbrl.standardization.standardize_statement_data(
        ...     raw_data, 'IncomeStatement'
        ... )
    """

    def __init__(self, xbrl: 'XBRL'):
        """
        Initialize cache for an XBRL instance.

        Args:
            xbrl: The XBRL instance this cache belongs to
        """
        self._xbrl = xbrl
        # Cache: (concept, label, statement_type) -> standard_label
        self._label_cache: Dict[Tuple[str, str, str], Optional[str]] = {}
        # Cache: statement_type -> standardized data list
        self._statement_cache: Dict[str, List[Dict[str, Any]]] = {}

    @property
    def mapper(self) -> 'ConceptMapper':
        """
        Get the ConceptMapper instance.

        Uses the module-level singleton for efficiency.
        """
        # Late import to avoid circular dependency
        from edgar.xbrl.standardization import get_default_mapper
        return get_default_mapper()

    def get_standard_label(
        self,
        concept: str,
        label: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Get standardized label for a concept with caching.

        Args:
            concept: The XBRL concept name (e.g., 'us-gaap_Revenue')
            label: The original label from the filing
            context: Optional context dict with keys like 'statement_type', 'section'

        Returns:
            The standardized label, or None if no mapping exists
        """
        context = context or {}
        statement_type = context.get('statement_type', '')

        cache_key = (concept, label, statement_type)

        if cache_key not in self._label_cache:
            self._label_cache[cache_key] = self.mapper.map_concept(
                concept, label, context
            )

        return self._label_cache[cache_key]

    def standardize_statement_data(
        self,
        raw_data: List[Dict[str, Any]],
        statement_type: str,
        use_cache: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Standardize statement data with optional caching.

        This method applies label standardization to raw statement data.

        Note: Statement caching is disabled by default because raw_data typically
        varies based on view/period parameters. Only enable caching when you know
        the input data is consistent for the given statement_type.

        Args:
            raw_data: List of line item dicts from statement
            statement_type: The statement type (e.g., 'IncomeStatement', 'BalanceSheet')
            use_cache: If True, cache and return cached results. Default False since
                      input data typically varies by view/period parameters.

        Returns:
            List of line item dicts with standardized labels
        """
        # Check cache first
        if use_cache and statement_type in self._statement_cache:
            return self._statement_cache[statement_type]

        # Add statement type context to each item
        for item in raw_data:
            item['statement_type'] = statement_type

        # Late import to avoid circular dependency
        from edgar.xbrl.standardization import standardize_statement
        # Standardize using the module function (which uses our singleton mapper)
        standardized = standardize_statement(raw_data, self.mapper)

        # Cache the result
        if use_cache:
            self._statement_cache[statement_type] = standardized

        return standardized

    def clear_cache(self, statement_type: Optional[str] = None):
        """
        Clear cached standardization results.

        Args:
            statement_type: If provided, only clear cache for this statement type.
                          If None, clear all caches.
        """
        if statement_type:
            self._statement_cache.pop(statement_type, None)
            # Clear label cache entries for this statement type
            keys_to_remove = [
                k for k in self._label_cache
                if k[2] == statement_type
            ]
            for key in keys_to_remove:
                del self._label_cache[key]
        else:
            self._label_cache.clear()
            self._statement_cache.clear()

    @property
    def cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics for debugging/monitoring.

        Returns:
            Dict with 'label_cache_size' and 'statement_cache_size'
        """
        return {
            'label_cache_size': len(self._label_cache),
            'statement_cache_size': len(self._statement_cache),
            'cached_statements': list(self._statement_cache.keys())
        }
