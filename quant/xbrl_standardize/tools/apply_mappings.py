#!/usr/bin/env python3
"""
Apply Mappings - Phase 3 Task 4

Production module for applying learned mappings to XBRL data extraction.

Usage:
    from quant.xbrl_standardize.apply_mappings import extract_income_statement

    # Extract with core mappings
    data = extract_income_statement(facts)

    # Extract with sector overlay
    data = extract_income_statement(facts, sector='banking')
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class MappingConfig:
    """Configuration for mapping extraction."""
    core_map_path: Path = Path(__file__).parent / 'map' / 'map_core.json'
    overlays_dir: Path = Path(__file__).parent / 'map' / 'map_overlays'
    use_fallbacks: bool = True
    strict_mode: bool = False  # If True, raise error on missing required fields


class MappingLoader:
    """Loads and caches mapping files."""

    def __init__(self, config: Optional[MappingConfig] = None):
        self.config = config or MappingConfig()
        self._core_cache = None
        self._overlay_cache = {}

    def load_core(self) -> Dict[str, Any]:
        """Load core mapping (cached)."""
        if self._core_cache is None:
            with open(self.config.core_map_path, 'r') as f:
                self._core_cache = json.load(f)
        return self._core_cache

    def load_overlay(self, sector: str) -> Optional[Dict[str, Any]]:
        """Load sector overlay (cached)."""
        if sector not in self._overlay_cache:
            overlay_path = self.config.overlays_dir / f'{sector}.json'
            if not overlay_path.exists():
                return None
            with open(overlay_path, 'r') as f:
                self._overlay_cache[sector] = json.load(f)
        return self._overlay_cache[sector]

    def get_mapping(self, sector: Optional[str] = None) -> Dict[str, Any]:
        """
        Get combined mapping (core + optional sector overlay).

        Args:
            sector: Optional sector name for overlay

        Returns:
            Combined mapping dict
        """
        core = self.load_core()

        if not sector:
            return core

        overlay = self.load_overlay(sector)
        if not overlay:
            return core

        # Merge core + overlay (overlay takes precedence)
        merged = {'_meta': core.get('_meta', {}), 'fields': {}}
        merged['_meta']['sector'] = sector

        # Start with core fields
        merged['fields'] = core.get('fields', {}).copy()

        # Override with sector-specific fields
        for field_name, field_data in overlay.get('fields', {}).items():
            merged['fields'][field_name] = field_data

        return merged


# Global loader instance
_loader = MappingLoader()


def normalize_concept_name(concept: str) -> str:
    """
    Normalize XBRL concept name for lookup.

    Handles both "us-gaap:Revenue" and "us-gaap_Revenue" formats.

    Args:
        concept: XBRL concept with namespace

    Returns:
        Normalized concept name
    """
    # Replace colon with underscore if present
    if ':' in concept:
        concept = concept.replace(':', '_')

    return concept


def extract_field_value(
    facts: Dict[str, Any],
    field_mapping: Dict[str, Any],
    use_fallbacks: bool = True
) -> Tuple[Optional[Any], Optional[str]]:
    """
    Extract field value from facts using mapping.

    Args:
        facts: Dictionary of XBRL facts {concept_name: value}
        field_mapping: Field mapping spec from map file
        use_fallbacks: Whether to use fallback concepts

    Returns:
        Tuple of (value, concept_used)
    """
    # Try primary concept
    primary = field_mapping.get('primary')
    if primary:
        normalized = normalize_concept_name(primary)
        if normalized in facts:
            return facts[normalized], primary

    # Try fallbacks if enabled
    if use_fallbacks:
        fallbacks = field_mapping.get('fallbacks', [])
        for fallback in fallbacks:
            normalized = normalize_concept_name(fallback)
            if normalized in facts:
                return facts[normalized], fallback

    return None, None


def extract_income_statement(
    facts: Dict[str, Any],
    sector: Optional[str] = None,
    config: Optional[MappingConfig] = None
) -> Dict[str, Any]:
    """
    Extract standardized income statement fields from XBRL facts.

    Args:
        facts: Dictionary of XBRL facts {concept_name: value}
        sector: Optional sector for sector-specific mappings
        config: Optional mapping configuration

    Returns:
        Dictionary of standardized fields with metadata

    Example:
        >>> facts = {
        ...     'us-gaap_Revenues': 100000000,
        ...     'us-gaap_NetIncomeLoss': 15000000
        ... }
        >>> result = extract_income_statement(facts)
        >>> result['data']['revenue']
        100000000
    """
    if config:
        global _loader
        _loader = MappingLoader(config)

    # Load mapping
    mapping = _loader.get_mapping(sector)

    # Extract fields
    extracted = {}
    metadata = {}

    for field_name, field_mapping in mapping.get('fields', {}).items():
        value, concept_used = extract_field_value(
            facts,
            field_mapping,
            use_fallbacks=True
        )

        if value is not None:
            extracted[field_name] = value
            metadata[field_name] = {
                'concept': concept_used,
                'confidence': field_mapping.get('confidence'),
                'label': field_mapping.get('label')
            }

    return {
        'data': extracted,
        'metadata': metadata,
        'sector': sector,
        'fields_extracted': len(extracted),
        'fields_total': len(mapping.get('fields', {}))
    }


def detect_sector(facts: Dict[str, Any], sic: Optional[int] = None) -> Optional[str]:
    """
    Auto-detect company sector from SIC code or facts patterns.

    Args:
        facts: XBRL facts dictionary
        sic: Optional SIC code

    Returns:
        Detected sector name or None
    """
    # Try SIC-based detection
    if sic:
        from quant.xbrl_standardize import get_sector_by_sic
        sector_key = get_sector_by_sic(sic)
        if sector_key:
            # Map sector_key to overlay name
            sector_mapping = {
                'financials_banking': 'banking',
                'financials_insurance': 'insurance',
                'energy_utilities': 'utilities'
            }
            return sector_mapping.get(sector_key)

    # Try pattern-based detection from facts
    fact_patterns = {
        'banking': [
            'us-gaap_InterestIncomeExpenseNet',
            'us-gaap_NoninterestIncome',
            'us-gaap_NoninterestExpense'
        ],
        'insurance': [
            'us-gaap_PremiumsEarnedNet',
            'us-gaap_PolicyholderBenefitsAndClaimsIncurredNet'
        ],
        'utilities': [
            'us-gaap_RegulatedOperatingRevenue',
            'us-gaap_UtilityPlantInService'
        ]
    }

    # Normalize fact keys for comparison
    normalized_facts = set(normalize_concept_name(k) for k in facts.keys())

    # Count matches for each sector
    sector_scores = {}
    for sector, patterns in fact_patterns.items():
        normalized_patterns = set(normalize_concept_name(p) for p in patterns)
        matches = len(normalized_patterns & normalized_facts)
        if matches > 0:
            sector_scores[sector] = matches

    # Return sector with most matches
    if sector_scores:
        return max(sector_scores, key=sector_scores.get)

    return None


def validate_extraction(
    result: Dict[str, Any],
    required_fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Validate extraction results.

    Args:
        result: Extraction result from extract_income_statement()
        required_fields: Optional list of required field names

    Returns:
        Validation result dictionary
    """
    if required_fields is None:
        required_fields = ['revenue', 'netIncome']  # Minimum viable

    extracted_fields = set(result['data'].keys())
    required = set(required_fields)

    missing = required - extracted_fields
    has_required = len(missing) == 0

    # Check confidence distribution
    low_confidence = []
    for field, meta in result.get('metadata', {}).items():
        if meta.get('confidence') == 'low':
            low_confidence.append(field)

    return {
        'valid': has_required,
        'missing_required': sorted(missing),
        'has_all_required': has_required,
        'low_confidence_fields': low_confidence,
        'extraction_rate': result['fields_extracted'] / result['fields_total'] if result['fields_total'] > 0 else 0
    }


# Convenience functions
def extract_with_auto_sector(
    facts: Dict[str, Any],
    sic: Optional[int] = None
) -> Dict[str, Any]:
    """
    Extract income statement with automatic sector detection.

    Args:
        facts: XBRL facts dictionary
        sic: Optional SIC code for sector detection

    Returns:
        Extraction result with auto-detected sector
    """
    sector = detect_sector(facts, sic)
    result = extract_income_statement(facts, sector=sector)
    result['sector_auto_detected'] = sector is not None
    return result


# Export public API
__all__ = [
    'MappingConfig',
    'MappingLoader',
    'extract_income_statement',
    'detect_sector',
    'validate_extraction',
    'extract_with_auto_sector',
    'normalize_concept_name'
]
