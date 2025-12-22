"""
Unit handling and normalization for financial facts.

This module provides comprehensive unit normalization and conversion capabilities
to address unit inconsistencies across different companies' SEC filings.

Key features:
- Currency unit normalization (USD, EUR, GBP, etc.)
- Share-based unit standardization
- Scale-aware unit matching
- Unit compatibility checking
- Error reporting with unit mismatch details

Usage:
    from edgar.entity.unit_handling import UnitNormalizer, UnitResult

    # Normalize a unit
    normalized = UnitNormalizer.normalize_unit("US DOLLAR")  # Returns "USD"

    # Check unit compatibility
    compatible = UnitNormalizer.are_compatible("USD", "DOLLARS")  # Returns True

    # Get unit with error details
    result = UnitNormalizer.get_normalized_value(fact, target_unit="USD")
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from edgar.entity.models import FinancialFact

logger = logging.getLogger(__name__)


class UnitType(Enum):
    """Types of financial units."""
    CURRENCY = "currency"
    SHARES = "shares"
    RATIO = "ratio"
    BUSINESS = "business"
    TIME = "time"
    AREA = "area"
    OTHER = "other"


@dataclass
class UnitResult:
    """Result of unit normalization with error details."""
    value: Optional[float]
    normalized_unit: Optional[str]
    original_unit: str
    success: bool
    error_reason: Optional[str] = None
    scale_applied: Optional[int] = None
    unit_type: Optional[UnitType] = None
    suggestions: List[str] = None

    def __post_init__(self):
        if self.suggestions is None:
            self.suggestions = []


class UnitNormalizer:
    """Comprehensive unit normalization for financial facts."""

    # Currency unit mappings
    CURRENCY_MAPPINGS = {
        'USD': ['USD', 'US DOLLAR', 'DOLLARS', 'usd', 'US$', 'DOLLAR'],
        'EUR': ['EUR', 'EURO', 'EUROS', 'eur', '€', 'EUROPEAN UNION EURO'],
        'GBP': ['GBP', 'POUND', 'POUNDS', 'gbp', '£', 'BRITISH POUND', 'POUND STERLING'],
        'JPY': ['JPY', 'YEN', 'yen', 'jpy', '¥', 'JAPANESE YEN'],
        'CAD': ['CAD', 'CANADIAN DOLLAR', 'CANADIAN DOLLARS', 'cad'],
        'CHF': ['CHF', 'SWISS FRANC', 'SWISS FRANCS', 'chf'],
        'AUD': ['AUD', 'AUSTRALIAN DOLLAR', 'AUSTRALIAN DOLLARS', 'aud'],
        'CNY': ['CNY', 'YUAN', 'CHINESE YUAN', 'cny', '¥'],
    }

    # Share unit mappings
    SHARE_MAPPINGS = {
        'shares': ['shares', 'share', 'SHARES', 'SHARE', 'STOCK', 'EQUITY'],
        'shares_unit': ['shares_unit', 'share_unit', 'SHARES_UNIT'],
        'partnership_unit': ['USD/PartnershipUnit', 'PartnershipUnit', 'partnership_unit']
    }

    # Ratio/dimensionless unit mappings
    RATIO_MAPPINGS = {
        'pure': ['pure', 'number', 'ratio', 'percent', '%', 'PURE', 'NUMBER'],
        'basis_points': ['bp', 'bps', 'basis_points', 'BASIS_POINTS']
    }

    # Per-share combinations
    PER_SHARE_MAPPINGS = {
        'USD_per_share': ['USD/shares', 'USD per share', 'USD/share', 'usd/shares'],
        'USD_per_share_unit': ['USD/shares_unit', 'USD per share unit', 'USD/share_unit']
    }

    # Business/operational unit mappings
    BUSINESS_MAPPINGS = {
        'customer': ['Customer', 'customer', 'CUSTOMER'],
        'store': ['Store', 'store', 'STORE'],
        'entity': ['Entity', 'entity', 'ENTITY'],
        'segment': ['Segment', 'segment', 'SEGMENT', 'reportable_segment'],
        'instrument': ['instrument', 'INSTRUMENT', 'financial_instrument'],
        'contract': ['USD/Contract', 'contract', 'CONTRACT'],
        'investment': ['USD/Investment', 'investment', 'INVESTMENT']
    }

    # Time-based unit mappings
    TIME_MAPPINGS = {
        'years': ['Year', 'years', 'YEAR', 'YEARS'],
        'months': ['Month', 'months', 'MONTH', 'MONTHS'],
        'days': ['Day', 'days', 'DAY', 'DAYS']
    }

    # Area unit mappings
    AREA_MAPPINGS = {
        'sqft': ['sqft', 'square_feet', 'SQFT', 'sq_ft'],
        'sqm': ['sqm', 'square_meters', 'SQMETER', 'sq_m']
    }

    # Comprehensive mapping combining all categories
    ALL_MAPPINGS = {
        **CURRENCY_MAPPINGS,
        **SHARE_MAPPINGS,
        **RATIO_MAPPINGS,
        **PER_SHARE_MAPPINGS,
        **BUSINESS_MAPPINGS,
        **TIME_MAPPINGS,
        **AREA_MAPPINGS
    }

    # Reverse mapping for faster lookups
    _REVERSE_MAPPING = None

    @classmethod
    def _build_reverse_mapping(cls) -> Dict[str, str]:
        """Build reverse mapping from variant to normalized unit."""
        if cls._REVERSE_MAPPING is not None:
            return cls._REVERSE_MAPPING

        reverse_map = {}
        for normalized_unit, variants in cls.ALL_MAPPINGS.items():
            for variant in variants:
                reverse_map[variant.upper()] = normalized_unit

        cls._REVERSE_MAPPING = reverse_map
        return reverse_map

    @classmethod
    def normalize_unit(cls, unit: str) -> str:
        """
        Normalize a unit string to its canonical form.

        Args:
            unit: Raw unit string from SEC filing

        Returns:
            Normalized unit string

        Example:
            >>> UnitNormalizer.normalize_unit("US DOLLAR")
            'USD'
            >>> UnitNormalizer.normalize_unit("shares_unit")
            'shares_unit'
        """
        if not unit:
            return ""

        reverse_map = cls._build_reverse_mapping()
        normalized = reverse_map.get(unit.upper())

        return normalized if normalized else unit

    @classmethod
    def get_unit_type(cls, unit: str) -> UnitType:
        """
        Determine the type of a unit.

        Args:
            unit: Unit string (normalized or raw)

        Returns:
            UnitType enum value
        """
        normalized = cls.normalize_unit(unit)

        if normalized in cls.CURRENCY_MAPPINGS:
            return UnitType.CURRENCY
        elif normalized in cls.PER_SHARE_MAPPINGS:
            # Per-share units are a special currency-like type (amount per share)
            return UnitType.CURRENCY  # Treat per-share as currency-derived
        elif normalized in cls.SHARE_MAPPINGS:
            return UnitType.SHARES
        elif normalized in cls.RATIO_MAPPINGS:
            return UnitType.RATIO
        elif normalized in cls.BUSINESS_MAPPINGS:
            return UnitType.BUSINESS
        elif normalized in cls.TIME_MAPPINGS:
            return UnitType.TIME
        elif normalized in cls.AREA_MAPPINGS:
            return UnitType.AREA
        else:
            return UnitType.OTHER

    @classmethod
    def are_compatible(cls, unit1: str, unit2: str) -> bool:
        """
        Check if two units are compatible for calculations.

        Args:
            unit1: First unit
            unit2: Second unit

        Returns:
            True if units are compatible
        """
        norm1 = cls.normalize_unit(unit1)
        norm2 = cls.normalize_unit(unit2)

        # Exact match
        if norm1 == norm2:
            return True

        # Same unit type
        type1 = cls.get_unit_type(norm1)
        type2 = cls.get_unit_type(norm2)

        if type1 == type2:
            # Special cases for compatible unit types
            if type1 == UnitType.CURRENCY:
                # Regular currencies are compatible, but per-share must match exactly
                if norm1 in cls.PER_SHARE_MAPPINGS or norm2 in cls.PER_SHARE_MAPPINGS:
                    # Per-share units must match exactly (USD_per_share != USD_per_share_unit)
                    return norm1 == norm2
                return True  # Regular currencies could be converted
            elif type1 == UnitType.SHARES:
                # shares and shares_unit are compatible for some calculations
                return norm1 in ['shares', 'shares_unit'] and norm2 in ['shares', 'shares_unit']

        return False

    @classmethod
    def get_normalized_value(
        cls,
        fact: FinancialFact,
        target_unit: Optional[str] = None,
        apply_scale: bool = True,
        strict_unit_match: bool = False
    ) -> UnitResult:
        """
        Get a normalized value from a financial fact with detailed error reporting.

        Args:
            fact: FinancialFact to normalize
            target_unit: Desired unit (if None, just normalize existing unit)
            apply_scale: Whether to apply scale factor
            strict_unit_match: If True, require exact unit match. If False, allow compatible units.

        Returns:
            UnitResult with value and metadata
        """
        if fact.numeric_value is None:
            return UnitResult(
                value=None,
                normalized_unit=None,
                original_unit=fact.unit,
                success=False,
                error_reason="No numeric value available"
            )

        original_unit = fact.unit or ""
        normalized_unit = cls.normalize_unit(original_unit)
        unit_type = cls.get_unit_type(normalized_unit)

        # Apply scale factor if requested
        value = fact.numeric_value
        scale_applied = None
        if apply_scale and fact.scale:
            value *= fact.scale
            scale_applied = fact.scale

        # If no target unit specified, return normalized value
        if target_unit is None:
            return UnitResult(
                value=value,
                normalized_unit=normalized_unit,
                original_unit=original_unit,
                success=True,
                scale_applied=scale_applied,
                unit_type=unit_type
            )

        # Check compatibility with target unit
        target_normalized = cls.normalize_unit(target_unit)

        if normalized_unit == target_normalized:
            # Exact match
            return UnitResult(
                value=value,
                normalized_unit=target_normalized,
                original_unit=original_unit,
                success=True,
                scale_applied=scale_applied,
                unit_type=unit_type
            )

        elif not strict_unit_match and cls.are_compatible(normalized_unit, target_normalized):
            # Compatible units - could potentially convert (only if not in strict mode)
            suggestions = []
            if cls.get_unit_type(normalized_unit) == UnitType.CURRENCY:
                suggestions.append(f"Consider currency conversion from {normalized_unit} to {target_normalized}")

            return UnitResult(
                value=value,
                normalized_unit=normalized_unit,  # Keep original, mark as compatible
                original_unit=original_unit,
                success=True,
                scale_applied=scale_applied,
                unit_type=unit_type,
                suggestions=suggestions
            )

        else:
            # Incompatible units
            suggestions = cls._get_unit_suggestions(normalized_unit, target_normalized)

            return UnitResult(
                value=None,
                normalized_unit=normalized_unit,
                original_unit=original_unit,
                success=False,
                error_reason=f"Unit mismatch: {normalized_unit} is not compatible with {target_normalized}",
                unit_type=unit_type,
                suggestions=suggestions
            )

    @classmethod
    def _get_unit_suggestions(cls, actual_unit: str, target_unit: str) -> List[str]:
        """Generate helpful suggestions for unit mismatches."""
        suggestions = []

        actual_type = cls.get_unit_type(actual_unit)
        target_type = cls.get_unit_type(target_unit)

        if actual_type != target_type:
            suggestions.append(f"Unit type mismatch: {actual_unit} is {actual_type.value}, "
                             f"but {target_unit} is {target_type.value}")

        # Specific suggestions based on unit types
        if target_type == UnitType.CURRENCY and actual_type != UnitType.CURRENCY:
            suggestions.append("Consider using a financial amount concept instead of a ratio/count")

        elif target_type == UnitType.SHARES and actual_type != UnitType.SHARES:
            suggestions.append("Consider using a share-based concept instead of a monetary amount")

        # Alternative units in the same category
        if actual_type == target_type:
            if actual_type == UnitType.CURRENCY:
                suggestions.append("Use currency conversion or specify the correct currency unit")
            elif actual_type == UnitType.SHARES:
                suggestions.append("Try using 'shares' instead of 'shares_unit' or vice versa")

        return suggestions


def apply_scale_factor(value: float, scale: Optional[int]) -> float:
    """
    Apply scale factor to a value.

    Args:
        value: Numeric value
        scale: Scale factor (e.g., 1000 for thousands)

    Returns:
        Scaled value
    """
    if scale and scale != 1:
        return value * scale
    return value


def format_unit_error(unit_result: UnitResult) -> str:
    """
    Format a unit error message for user display.

    Args:
        unit_result: UnitResult with error details

    Returns:
        Formatted error message
    """
    if unit_result.success:
        return "No error"

    message = f"Unit handling error: {unit_result.error_reason}"

    if unit_result.suggestions:
        message += "\n  Suggestions:\n"
        for suggestion in unit_result.suggestions:
            message += f"    - {suggestion}\n"

    message += f"  Original unit: '{unit_result.original_unit}'"
    if unit_result.normalized_unit != unit_result.original_unit:
        message += f"  Normalized to: '{unit_result.normalized_unit}'"

    return message


# Legacy support - maintain compatibility with existing code
def normalize_unit_legacy(unit: str) -> str:
    """Legacy unit normalization for backward compatibility."""
    return UnitNormalizer.normalize_unit(unit)


def are_units_compatible_legacy(unit1: str, unit2: str) -> bool:
    """Legacy unit compatibility check for backward compatibility."""
    return UnitNormalizer.are_compatible(unit1, unit2)
