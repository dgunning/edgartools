"""
Base Strategy Pattern for XBRL Metric Extraction

This module provides the foundation for the Evolutionary Normalization Engine (ENE).
All extraction strategies inherit from BaseStrategy and implement the extract() method.

Key Concepts:
- Strategies are atomic, reusable extraction algorithms
- Each strategy has a fingerprint for experiment tracking
- Strategies support both GAAP and Street extraction modes
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib
import json


class ExtractionMode(Enum):
    """Extraction mode determines which accounting perspective to use."""
    GAAP = "gaap"       # GAAP-aligned extraction for yfinance validation
    STREET = "street"   # Street View extraction for economic analysis


class ExtractionMethod(Enum):
    """How the value was extracted."""
    DIRECT = "direct"          # Single concept lookup
    COMPOSITE = "composite"    # Sum of multiple concepts
    CALCULATED = "calculated"  # Derived from other metrics
    MAPPED = "mapped"          # Industry counterpart mapping
    FALLBACK = "fallback"      # Used fallback logic


@dataclass
class StrategyResult:
    """
    Result of a strategy execution with full provenance.

    Attributes:
        value: The extracted numeric value (None if extraction failed)
        concept: The primary XBRL concept used
        method: How the value was extracted
        confidence: Confidence score (0.0-1.0)
        notes: Human-readable extraction notes
        components: Breakdown of component values (for composite extractions)
        metadata: Additional context for experiment tracking
    """
    value: Optional[float]
    concept: Optional[str] = None
    method: ExtractionMethod = ExtractionMethod.DIRECT
    confidence: float = 1.0
    notes: str = ""
    components: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""  # ADR-005: Strategy fingerprint for provenance tracking

    @property
    def is_valid(self) -> bool:
        """Check if extraction produced a valid value."""
        return self.value is not None and self.value >= 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'value': self.value,
            'concept': self.concept,
            'method': self.method.value,
            'confidence': self.confidence,
            'notes': self.notes,
            'components': self.components,
            'metadata': self.metadata,
            'fingerprint': self.fingerprint,  # ADR-005
        }


class BaseStrategy(ABC):
    """
    Abstract base class for all extraction strategies.

    A strategy encapsulates the logic for extracting a specific metric
    using a particular approach. Strategies are:
    - Atomic: One strategy, one extraction algorithm
    - Parameterized: Behavior tuned via params dict
    - Trackable: Fingerprinted for experiment tracking

    Subclasses must implement:
    - strategy_name (class attribute)
    - metric_name (class attribute)
    - extract() method
    """

    # Class attributes - override in subclasses
    strategy_name: str = "base"
    metric_name: str = "unknown"
    version: str = "1.0.0"

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """
        Initialize strategy with optional parameters.

        Args:
            params: Strategy-specific parameters that tune behavior
        """
        self.params = params or {}

    @abstractmethod
    def extract(
        self,
        xbrl: Any,
        facts_df: Any,
        mode: ExtractionMode = ExtractionMode.GAAP
    ) -> StrategyResult:
        """
        Execute the extraction strategy.

        Args:
            xbrl: XBRL object for linkbase access
            facts_df: DataFrame of XBRL facts
            mode: Extraction mode (GAAP or Street)

        Returns:
            StrategyResult with extracted value and provenance
        """
        pass

    def execute(
        self,
        xbrl: Any,
        facts_df: Any,
        mode: ExtractionMode = ExtractionMode.GAAP
    ) -> StrategyResult:
        """
        Execute strategy and auto-inject fingerprint.

        This is the recommended entry point for strategy execution.
        It calls extract() and ensures the fingerprint is set for provenance tracking.

        Args:
            xbrl: XBRL object for linkbase access
            facts_df: DataFrame of XBRL facts
            mode: Extraction mode (GAAP or Street)

        Returns:
            StrategyResult with fingerprint populated
        """
        result = self.extract(xbrl, facts_df, mode)
        result.fingerprint = self.fingerprint
        return result

    @property
    def fingerprint(self) -> str:
        """
        Generate unique hash for experiment tracking.

        The fingerprint captures:
        - Strategy name and version
        - All parameter values

        This allows tracking which exact configuration produced a result.
        """
        fingerprint_data = {
            'strategy': self.strategy_name,
            'version': self.version,
            'params': self.params,
        }
        fingerprint_json = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.sha256(fingerprint_json.encode()).hexdigest()[:16]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(params={self.params}, fingerprint={self.fingerprint})"


class FactHelper:
    """
    Helper class for common fact extraction operations.

    Provides reusable methods that strategies can use for:
    - Getting fact values (exact and fuzzy)
    - Handling dimensional data
    - Balance sheet vs income statement logic
    """

    # Balance sheet concepts (point-in-time values)
    BALANCE_SHEET_CONCEPTS = [
        'shorttermborrowings', 'debtcurrent', 'longtermdebtcurrent',
        'commercialpaper', 'federalfundspurchased', 'othershortermborrowings',
        'assets', 'liabilities', 'equity', 'cash', 'cashandcashequivalents',
    ]

    @staticmethod
    def get_fact_value(
        facts_df: Any,
        concept: str,
        target_period_days: Optional[int] = None,
        prefer_instant: bool = True
    ) -> Optional[float]:
        """
        Get consolidated (non-dimensional) value for a concept.

        Args:
            facts_df: DataFrame of XBRL facts
            concept: XBRL concept name (without namespace)
            target_period_days: Target period duration (90 for Q, 365 for annual)
            prefer_instant: Prefer instant values for balance sheet items

        Returns:
            Numeric value if found, None otherwise
        """
        if facts_df is None or len(facts_df) == 0:
            return None

        concept_lower = concept.lower()

        # Determine if this is a balance sheet concept
        is_balance_sheet = concept_lower in FactHelper.BALANCE_SHEET_CONCEPTS

        # Filter to matching concept
        mask = facts_df['concept'].str.lower().str.endswith(concept_lower)
        concept_facts = facts_df[mask].copy()

        if len(concept_facts) == 0:
            return None

        # Filter out dimensional values (keep consolidated totals)
        if 'full_dimension_label' in concept_facts.columns:
            concept_facts = concept_facts[concept_facts['full_dimension_label'].isna()]

        if len(concept_facts) == 0:
            return None

        # Balance sheet: prefer latest instant
        if is_balance_sheet and prefer_instant and 'period_key' in concept_facts.columns:
            instant_facts = concept_facts[concept_facts['period_key'].str.startswith('instant_')]
            if len(instant_facts) > 0:
                concept_facts = instant_facts

        # Filter by period duration if specified
        if target_period_days and 'period_days' in concept_facts.columns:
            tolerance = 30  # days
            period_mask = abs(concept_facts['period_days'] - target_period_days) <= tolerance
            filtered = concept_facts[period_mask]
            if len(filtered) > 0:
                concept_facts = filtered

        # Get most recent value
        if 'period_key' in concept_facts.columns:
            concept_facts = concept_facts.sort_values('period_key', ascending=False)

        if 'numeric_value' in concept_facts.columns:
            values = concept_facts['numeric_value'].dropna()
            if len(values) > 0:
                return float(values.iloc[0])

        return None

    @staticmethod
    def get_fact_value_fuzzy(
        facts_df: Any,
        concept: str
    ) -> Optional[float]:
        """
        Get fact value using fuzzy/partial matching.

        Useful when companies use extensions or variations of standard concepts.

        Args:
            facts_df: DataFrame of XBRL facts
            concept: Partial concept name to match

        Returns:
            Numeric value if found, None otherwise
        """
        if facts_df is None or len(facts_df) == 0:
            return None

        concept_lower = concept.lower()

        # Try contains match
        mask = facts_df['concept'].str.lower().str.contains(concept_lower, na=False)
        matches = facts_df[mask].copy()

        if len(matches) == 0:
            return None

        # Filter out dimensional values
        if 'full_dimension_label' in matches.columns:
            matches = matches[matches['full_dimension_label'].isna()]

        if len(matches) == 0:
            return None

        # Get most recent value
        if 'period_key' in matches.columns:
            matches = matches.sort_values('period_key', ascending=False)

        if 'numeric_value' in matches.columns:
            values = matches['numeric_value'].dropna()
            if len(values) > 0:
                return float(values.iloc[0])

        return None

    @staticmethod
    def get_fact_value_non_dimensional(
        facts_df: Any,
        concept: str
    ) -> Optional[float]:
        """
        Get fact value explicitly excluding dimensional breakdowns.

        Some companies report dimensional breakdowns that should not be
        used as the consolidated total.

        Args:
            facts_df: DataFrame of XBRL facts
            concept: XBRL concept name

        Returns:
            Non-dimensional value if found, None otherwise
        """
        if facts_df is None or len(facts_df) == 0:
            return None

        concept_lower = concept.lower()

        # Match concept
        mask = facts_df['concept'].str.lower().str.endswith(concept_lower)
        matches = facts_df[mask].copy()

        if len(matches) == 0:
            return None

        # Explicitly filter to non-dimensional
        if 'full_dimension_label' in matches.columns:
            matches = matches[matches['full_dimension_label'].isna()]

        if len(matches) == 0:
            return None

        # Prefer instant values for balance sheet items
        if 'period_key' in matches.columns:
            instant_matches = matches[matches['period_key'].str.startswith('instant_')]
            if len(instant_matches) > 0:
                matches = instant_matches
            matches = matches.sort_values('period_key', ascending=False)

        if 'numeric_value' in matches.columns:
            values = matches['numeric_value'].dropna()
            if len(values) > 0:
                return float(values.iloc[0])

        return None
