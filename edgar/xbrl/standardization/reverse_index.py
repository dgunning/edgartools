"""
Reverse index for O(1) XBRL tag to standard concept lookups.

This module provides fast lookups from company-specific XBRL tags to
mpreiss9's standard concepts, with support for:
- O(1) hash-based lookups (vs O(n×m) iteration)
- Ambiguous tag detection (tags mapping to multiple concepts)
- Display name resolution (concept → user-friendly label)
- Exclusion filtering (DropThisItem tags)

Architecture:
    XBRL Tag (us-gaap:AccountsPayableCurrent)
        ↓ reverse_index lookup (O(1))
    Standard Concept (TradePayables)
        ↓ display_names lookup
    Display Label ("Accounts Payable")

Generated from: data/xbrl-mappings/gaap_taxonomy_mapping.csv
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from .exclusions import should_exclude, EXCLUDED_TAGS

logger = logging.getLogger(__name__)


@dataclass
class MappingResult:
    """Result of a reverse index lookup."""

    standard_concepts: List[str]
    """List of standard concept names (mpreiss9's taxonomy)."""

    display_names: List[str]
    """List of user-friendly display names."""

    is_ambiguous: bool
    """True if the tag maps to multiple concepts (needs context resolution)."""

    is_deprecated: bool
    """True if the XBRL tag is deprecated."""

    deprecated_year: Optional[str]
    """Year the tag was deprecated, if applicable."""

    comment: Optional[str]
    """Any comment about the mapping (e.g., 'Curr/NonCurr ambiguity')."""

    @property
    def primary_concept(self) -> Optional[str]:
        """Get the primary (first) standard concept."""
        return self.standard_concepts[0] if self.standard_concepts else None

    @property
    def primary_display_name(self) -> Optional[str]:
        """Get the primary (first) display name."""
        return self.display_names[0] if self.display_names else None


class ReverseIndex:
    """
    Reverse index for fast XBRL tag to standard concept lookups.

    This class provides O(1) lookups from XBRL tags to standard concepts,
    replacing the O(n×m) iteration in the current MappingStore.

    Example:
        >>> index = ReverseIndex()
        >>> result = index.lookup("AccountsPayableCurrent")
        >>> result.primary_concept
        'TradePayables'
        >>> result.primary_display_name
        'Accounts Payable'
        >>> result.is_ambiguous
        False

        >>> result = index.lookup("AccountsPayableCurrentAndNoncurrent")
        >>> result.standard_concepts
        ['TradePayables', 'OtherOperatingNonCurrentLiabilities']
        >>> result.is_ambiguous
        True
    """

    def __init__(self,
                 gaap_mappings_path: Optional[str] = None,
                 display_names_path: Optional[str] = None):
        """
        Initialize the reverse index.

        Args:
            gaap_mappings_path: Path to gaap_mappings.json. If None, uses default.
            display_names_path: Path to display_names.json. If None, uses default.
        """
        module_dir = os.path.dirname(os.path.abspath(__file__))

        if gaap_mappings_path is None:
            gaap_mappings_path = os.path.join(module_dir, "gaap_mappings.json")
        if display_names_path is None:
            display_names_path = os.path.join(module_dir, "display_names.json")

        # Load the mappings
        self._gaap_mappings: Dict[str, dict] = self._load_json(gaap_mappings_path)
        self._display_names: Dict[str, str] = self._load_json(display_names_path)

        # Build the reverse index
        self._index: Dict[str, dict] = self._gaap_mappings

        # Cache for normalized lookups (strips namespace prefixes)
        self._normalized_cache: Dict[str, str] = {}
        self._build_normalized_cache()

        # Statistics
        self._stats = {
            "total_mappings": len(self._index),
            "ambiguous_count": sum(1 for v in self._index.values() if v.get("ambiguous", False)),
            "deprecated_count": sum(1 for v in self._index.values() if v.get("deprecated")),
            "excluded_count": len(EXCLUDED_TAGS),
        }

        logger.info(
            "ReverseIndex initialized: %d mappings, %d ambiguous, %d deprecated, %d excluded",
            self._stats["total_mappings"],
            self._stats["ambiguous_count"],
            self._stats["deprecated_count"],
            self._stats["excluded_count"]
        )

    def _load_json(self, path: str) -> dict:
        """Load a JSON file, returning empty dict on failure."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning("Failed to load %s: %s", path, e)
            return {}

    def _build_normalized_cache(self) -> None:
        """Build cache mapping normalized tag names to original keys."""
        for tag in self._index:
            # Store lowercase version for case-insensitive lookup
            self._normalized_cache[tag.lower()] = tag

            # Also store with common prefixes stripped
            for prefix in ("us-gaap:", "us-gaap_", "ifrs-full:", "dei:"):
                if tag.lower().startswith(prefix.lower()):
                    stripped = tag[len(prefix):]
                    self._normalized_cache[stripped.lower()] = tag

    def _normalize_tag(self, tag: str) -> Optional[str]:
        """
        Normalize an XBRL tag to match index keys.

        Handles:
        - Namespace prefixes (us-gaap:, us-gaap_, ifrs-full:, dei:)
        - Case variations

        Args:
            tag: The XBRL tag to normalize

        Returns:
            The normalized tag key, or None if not found
        """
        # Direct match (fastest path)
        if tag in self._index:
            return tag

        # Strip namespace prefix if present
        normalized = tag
        for prefix in ("us-gaap:", "us-gaap_", "ifrs-full:", "dei:"):
            if tag.startswith(prefix):
                normalized = tag[len(prefix):]
                break

        # Check direct match after stripping
        if normalized in self._index:
            return normalized

        # Case-insensitive lookup via cache
        cache_key = normalized.lower()
        if cache_key in self._normalized_cache:
            return self._normalized_cache[cache_key]

        return None

    def lookup(self, xbrl_tag: str) -> Optional[MappingResult]:
        """
        Look up an XBRL tag in the reverse index.

        Args:
            xbrl_tag: The XBRL tag to look up (with or without namespace prefix)

        Returns:
            MappingResult with standard concepts and display names, or None if not found
        """
        # Check if excluded first
        if should_exclude(xbrl_tag):
            return None

        # Normalize the tag
        normalized = self._normalize_tag(xbrl_tag)
        if normalized is None:
            return None

        # Get the mapping entry
        entry = self._index.get(normalized)
        if entry is None:
            return None

        # Extract data from entry
        standard_tags = entry.get("standard_tags", [])
        is_ambiguous = entry.get("ambiguous", False)
        deprecated = entry.get("deprecated")
        comment = entry.get("comment")

        # Resolve display names
        display_names = [
            self._display_names.get(tag, tag)  # Fall back to concept name if no display name
            for tag in standard_tags
        ]

        return MappingResult(
            standard_concepts=standard_tags,
            display_names=display_names,
            is_ambiguous=is_ambiguous,
            is_deprecated=bool(deprecated),
            deprecated_year=deprecated if deprecated else None,
            comment=comment,
        )

    def get_standard_concept(
        self,
        xbrl_tag: str,
        context: Optional[Dict] = None,
        log_ambiguous: bool = False
    ) -> Optional[str]:
        """
        Get the standard concept for an XBRL tag.

        This is the primary lookup method for standardization.
        For ambiguous tags, uses context (section, balance type) to disambiguate.

        Args:
            xbrl_tag: The XBRL tag to look up
            context: Optional context for disambiguation:
                     - section: Balance sheet section (e.g., "Current Assets")
                     - balance: Debit/credit balance type
                     - statement_type: Type of statement
            log_ambiguous: If True, log ambiguous resolutions to UnmappedTagLogger

        Returns:
            The standard concept name, or None if not found/excluded
        """
        result = self.lookup(xbrl_tag)
        if result is None:
            return None

        # Non-ambiguous tags: return primary concept
        if not result.is_ambiguous:
            return result.primary_concept

        # Ambiguous tags: try to disambiguate using context
        resolution_method = "fallback"
        resolved = None

        if context and len(result.standard_concepts) > 1:
            resolved = self._disambiguate_by_context(
                xbrl_tag, result.standard_concepts, context
            )
            if resolved:
                # Determine resolution method for logging
                if context.get('is_total'):
                    resolution_method = "is_total"
                elif context.get('section'):
                    resolution_method = "section"
                logger.debug(
                    "Disambiguated %s to %s using context (section=%s)",
                    xbrl_tag, resolved, context.get('section')
                )

        # Use fallback if disambiguation failed
        if not resolved:
            resolved = result.primary_concept
            resolution_method = "fallback"
            logger.debug(
                "Ambiguous tag %s maps to %s - using first candidate",
                xbrl_tag, result.standard_concepts
            )

        # Log ambiguous resolution if requested (Phase 5)
        if log_ambiguous:
            try:
                from .unmapped_logger import log_ambiguous as log_amb
                log_amb(
                    concept=xbrl_tag,
                    label=context.get('label', '') if context else '',
                    candidates=result.standard_concepts,
                    resolved_to=resolved,
                    resolution_method=resolution_method,
                    statement_type=context.get('statement_type') if context else None,
                    section=context.get('section') if context else None,
                    confidence=1.0 if resolution_method != "fallback" else 0.5,
                )
            except Exception as e:
                logger.debug("Failed to log ambiguous resolution: %s", e)

        return resolved

    def _disambiguate_by_context(
        self,
        xbrl_tag: str,
        candidates: List[str],
        context: Dict
    ) -> Optional[str]:
        """
        Disambiguate between candidate concepts using context.

        Phase 3/4: Uses section membership and label clues to resolve ambiguous tags.

        Args:
            xbrl_tag: The original XBRL tag
            candidates: List of possible standard concepts
            context: Context dict with section, balance, statement_type, is_total

        Returns:
            The resolved concept, or None if disambiguation failed
        """
        section = context.get('section')
        statement_type = context.get('statement_type', 'BalanceSheet')
        is_total = context.get('is_total', False)

        try:
            from .sections import get_section_for_concept

            # Phase 4: Special case - if is_total is True, prefer "Total" concepts
            if is_total:
                for candidate in candidates:
                    if 'total' in candidate.lower():
                        logger.debug(
                            "Disambiguated %s to %s (is_total=True)",
                            xbrl_tag, candidate
                        )
                        return candidate

            if not section:
                return None

            # Find which candidate belongs in this section
            for candidate in candidates:
                candidate_section = get_section_for_concept(candidate, statement_type)
                if candidate_section and self._sections_match(section, candidate_section):
                    return candidate

            # Secondary: check if section name is in concept name
            section_lower = section.lower()
            for candidate in candidates:
                candidate_lower = candidate.lower()
                if 'current' in section_lower and 'noncurrent' not in section_lower:
                    if 'current' in candidate_lower and 'noncurrent' not in candidate_lower:
                        return candidate
                elif 'noncurrent' in section_lower or 'non-current' in section_lower:
                    if 'noncurrent' in candidate_lower or 'nonoperating' in candidate_lower:
                        return candidate

        except Exception as e:
            logger.debug("Disambiguation failed for %s: %s", xbrl_tag, e)

        return None

    def _sections_match(self, context_section: str, concept_section: str) -> bool:
        """Check if two section names match (handles variations)."""
        if not context_section or not concept_section:
            return False

        # Normalize for comparison
        ctx = context_section.lower().replace('-', ' ').replace('_', ' ')
        cpt = concept_section.lower().replace('-', ' ').replace('_', ' ')

        # Direct match
        if ctx == cpt:
            return True

        # Determine if sections are current vs non-current
        ctx_is_current = 'current' in ctx and 'non' not in ctx.split('current')[0]
        ctx_is_noncurrent = 'non current' in ctx or 'noncurrent' in ctx or ('non' in ctx and 'current' in ctx)

        cpt_is_current = 'current' in cpt and 'non' not in cpt.split('current')[0]
        cpt_is_noncurrent = 'non current' in cpt or 'noncurrent' in cpt or ('non' in cpt and 'current' in cpt)

        # Current vs Non-Current must match
        if ctx_is_current != cpt_is_current:
            return False
        if ctx_is_noncurrent != cpt_is_noncurrent:
            return False

        # Check asset/liability type
        ctx_is_asset = 'asset' in ctx
        ctx_is_liability = 'liabilit' in ctx
        cpt_is_asset = 'asset' in cpt
        cpt_is_liability = 'liabilit' in cpt

        # If both specify asset/liability, they must match
        if ctx_is_asset and cpt_is_liability:
            return False
        if ctx_is_liability and cpt_is_asset:
            return False

        # Current Assets match
        if ctx_is_current and cpt_is_current and ctx_is_asset and cpt_is_asset:
            return True

        # Current Liabilities match
        if ctx_is_current and cpt_is_current and ctx_is_liability and cpt_is_liability:
            return True

        # Non-Current Assets match
        if ctx_is_noncurrent and cpt_is_noncurrent and ctx_is_asset and cpt_is_asset:
            return True

        # Non-Current Liabilities match
        if ctx_is_noncurrent and cpt_is_noncurrent and ctx_is_liability and cpt_is_liability:
            return True

        return False

    def get_display_name(self, xbrl_tag: str, context: Optional[Dict] = None) -> Optional[str]:
        """
        Get the user-friendly display name for an XBRL tag.

        Args:
            xbrl_tag: The XBRL tag to look up
            context: Optional context for disambiguation:
                     - section: Balance sheet section (e.g., "Current Assets")
                     - balance: Debit/credit balance type
                     - statement_type: Type of statement

        Returns:
            The display name, or None if not found/excluded
        """
        result = self.lookup(xbrl_tag)
        if result is None:
            return None

        # Non-ambiguous tags: return primary display name
        if not result.is_ambiguous:
            return result.primary_display_name

        # Ambiguous tags: try to disambiguate using context
        if context and len(result.standard_concepts) > 1:
            resolved = self._disambiguate_by_context(
                xbrl_tag, result.standard_concepts, context
            )
            if resolved:
                # Return the display name for the resolved concept
                return self._display_names.get(resolved, resolved)

        return result.primary_display_name

    def is_excluded(self, xbrl_tag: str) -> bool:
        """Check if an XBRL tag should be excluded from standardization."""
        return should_exclude(xbrl_tag)

    def is_ambiguous(self, xbrl_tag: str) -> bool:
        """Check if an XBRL tag is ambiguous (maps to multiple concepts)."""
        result = self.lookup(xbrl_tag)
        return result.is_ambiguous if result else False

    def get_ambiguous_candidates(self, xbrl_tag: str) -> List[Tuple[str, str]]:
        """
        Get all candidate mappings for an ambiguous tag.

        Args:
            xbrl_tag: The XBRL tag to look up

        Returns:
            List of (standard_concept, display_name) tuples
        """
        result = self.lookup(xbrl_tag)
        if result is None:
            return []

        return list(zip(result.standard_concepts, result.display_names))

    def concept_to_display_name(self, standard_concept: str) -> str:
        """
        Convert a standard concept to its display name.

        Args:
            standard_concept: The mpreiss9 standard concept name

        Returns:
            The user-friendly display name, or the concept itself if no mapping
        """
        return self._display_names.get(standard_concept, standard_concept)

    @property
    def stats(self) -> Dict[str, int]:
        """Get statistics about the reverse index."""
        return self._stats.copy()

    def __len__(self) -> int:
        """Return the number of mappings in the index."""
        return len(self._index)

    def __contains__(self, xbrl_tag: str) -> bool:
        """Check if an XBRL tag is in the index."""
        if should_exclude(xbrl_tag):
            return False
        return self._normalize_tag(xbrl_tag) is not None


# Module-level singleton for convenience
_default_index: Optional[ReverseIndex] = None


def get_reverse_index() -> ReverseIndex:
    """
    Get the default reverse index singleton.

    Returns:
        The default ReverseIndex instance
    """
    global _default_index
    if _default_index is None:
        _default_index = ReverseIndex()
    return _default_index


def lookup(xbrl_tag: str) -> Optional[MappingResult]:
    """
    Convenience function to look up an XBRL tag.

    Args:
        xbrl_tag: The XBRL tag to look up

    Returns:
        MappingResult or None
    """
    return get_reverse_index().lookup(xbrl_tag)


def get_standard_concept(
    xbrl_tag: str,
    context: Optional[Dict] = None,
    log_ambiguous: bool = False
) -> Optional[str]:
    """
    Convenience function to get standard concept for an XBRL tag.

    Args:
        xbrl_tag: The XBRL tag to look up
        context: Optional context for disambiguation
        log_ambiguous: If True, log ambiguous resolutions to UnmappedTagLogger

    Returns:
        Standard concept name or None
    """
    return get_reverse_index().get_standard_concept(xbrl_tag, context, log_ambiguous)


def get_display_name(xbrl_tag: str, context: Optional[Dict] = None) -> Optional[str]:
    """
    Convenience function to get display name for an XBRL tag.

    Args:
        xbrl_tag: The XBRL tag to look up
        context: Optional context for disambiguation

    Returns:
        Display name or None
    """
    return get_reverse_index().get_display_name(xbrl_tag, context)
