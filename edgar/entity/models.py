"""
Data models for the enhanced Entity Facts API.

This module provides the unified data models for financial facts,
optimized for both traditional analysis and AI consumption.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union


class DataQuality(Enum):
    """Data quality indicators for facts"""
    HIGH = "high"          # Direct from XBRL, validated
    MEDIUM = "medium"      # Derived or calculated
    LOW = "low"           # Estimated or inferred


@dataclass
class FinancialFact:
    """
    Unified fact representation optimized for both traditional analysis and AI consumption.

    This class represents a single financial fact with rich contextual information,
    quality indicators, and AI-ready metadata.
    """

    # Core identification
    concept: str                    # Standardized concept (e.g., 'us-gaap:Revenue')
    taxonomy: str                   # Taxonomy namespace (us-gaap, ifrs, etc.)
    label: str                      # Human-readable label

    # Values with proper typing
    value: Union[float, int, str]   # The actual value
    numeric_value: Optional[float]  # Numeric representation for calculations
    unit: str                       # Unit of measure (USD, shares, etc.)
    scale: Optional[int] = None     # Scale factor (thousands=1000, millions=1000000)

    # Temporal context
    period_start: Optional[date] = None
    period_end: date = None
    period_type: Literal['instant', 'duration'] = 'instant'
    fiscal_year: int = 0
    fiscal_period: str = ''         # FY, Q1, Q2, Q3, Q4

    # Filing context
    filing_date: date = None
    form_type: str = ''             # 10-K, 10-Q, 8-K, etc.
    accession: str = ''             # SEC accession number

    # Quality and provenance
    data_quality: DataQuality = DataQuality.MEDIUM
    is_audited: bool = False
    is_restated: bool = False
    is_estimated: bool = False
    confidence_score: float = 0.8   # 0.0 to 1.0

    # AI-ready context
    semantic_tags: List[str] = field(default_factory=list)  # ['revenue', 'recurring', 'operating']
    business_context: str = ''      # "Product revenue from iPhone sales"
    calculation_context: Optional[str] = None  # "Derived from segment data"

    # Optional XBRL specifics
    context_ref: Optional[str] = None
    dimensions: Dict[str, str] = field(default_factory=dict)
    statement_type: Optional[str] = None
    line_item_sequence: Optional[int] = None

    # Structural metadata (from learned mappings)
    depth: Optional[int] = None            # Hierarchy depth in statement
    parent_concept: Optional[str] = None   # Parent concept in hierarchy
    section: Optional[str] = None          # Statement section (e.g., "Current Assets")
    is_abstract: bool = False              # Abstract/header item
    is_total: bool = False                 # Total/sum item
    presentation_order: Optional[float] = None  # Order in presentation

    def to_llm_context(self) -> Dict[str, Any]:
        """
        Generate rich context for LLM consumption.

        Returns a dictionary with formatted values and contextual information
        optimized for language model understanding.
        """
        # Format the value appropriately
        if self.numeric_value is not None:
            if self.unit.upper() in ['USD', 'EUR', 'GBP', 'JPY']:
                # Currency formatting
                formatted_value = f"{self.numeric_value:,.0f}"
                if self.scale:
                    if self.scale == 1000:
                        formatted_value += " thousand"
                    elif self.scale == 1000000:
                        formatted_value += " million"
                    elif self.scale == 1000000000:
                        formatted_value += " billion"
            else:
                formatted_value = f"{self.numeric_value:,.2f}"
        else:
            formatted_value = str(self.value)

        # Format the period
        if self.period_type == 'instant':
            period_desc = f"as of {self.period_end}"
        else:
            period_desc = f"for {self.fiscal_period} {self.fiscal_year}"
            if self.period_start and self.period_end:
                period_desc += f" ({self.period_start} to {self.period_end})"

        return {
            "concept": self.label,
            "value": formatted_value,
            "unit": self.unit,
            "period": period_desc,
            "context": self.business_context,
            "quality": self.data_quality.value,
            "confidence": self.confidence_score,
            "tags": self.semantic_tags,
            "source": f"{self.form_type} filed {self.filing_date}" if self.filing_date else "Unknown source",
            "is_audited": self.is_audited,
            "is_estimated": self.is_estimated,
            "dimensions": self.dimensions if self.dimensions else None
        }

    def get_display_period_key(self) -> str:
        """
        Generate a display-friendly period key based on actual period dates.

        This method creates period keys like "Q1 2024" based on the actual period 
        covered by the data, not the filing year. It uses the period_end date to 
        determine the calendar year and quarter.

        Returns:
            A period key in format like "Q1 2024", "FY 2023", etc.
        """
        if not self.period_end:
            # Fallback to fiscal year/period if no period_end
            return f"{self.fiscal_period} {self.fiscal_year}"

        # Extract calendar year from period_end
        calendar_year = self.period_end.year

        # For fiscal years, use "FY" prefix
        if self.fiscal_period == 'FY':
            return f"FY {calendar_year}"

        # For quarters, determine the calendar quarter from the end date
        if self.fiscal_period in ['Q1', 'Q2', 'Q3', 'Q4']:
            end_month = self.period_end.month

            # Map end month to calendar quarter
            if end_month in [1, 2, 3]:
                quarter = 'Q1'
            elif end_month in [4, 5, 6]:
                quarter = 'Q2'
            elif end_month in [7, 8, 9]:
                quarter = 'Q3'
            else:  # 10, 11, 12
                quarter = 'Q4'

            return f"{quarter} {calendar_year}"

        # For other periods, use the fiscal period with calendar year
        return f"{self.fiscal_period} {calendar_year}"

    def get_formatted_value(self) -> str:
        """
        Format the numeric value for display, avoiding scientific notation.

        Returns:
            Formatted string representation of the value
        """
        if self.numeric_value is None:
            return str(self.value)

        # For currency values
        if self.unit.upper() in ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'CHF']:
            # Round to nearest whole number for large values
            if abs(self.numeric_value) >= 1000:
                return f"{self.numeric_value:,.0f}"
            else:
                return f"{self.numeric_value:,.2f}"

        # For share counts
        elif self.unit.lower() in ['shares', 'share']:
            return f"{self.numeric_value:,.0f}"

        # For percentages and ratios
        elif self.unit.lower() in ['pure', 'percent', '%']:
            return f"{self.numeric_value:.2f}"

        # Default formatting
        else:
            if abs(self.numeric_value) >= 1000:
                return f"{self.numeric_value:,.0f}"
            else:
                return f"{self.numeric_value:,.2f}"

    def __repr__(self) -> str:
        """String representation focusing on key information"""
        value_str = f"{self.numeric_value:,.0f}" if self.numeric_value else str(self.value)
        return f"FinancialFact({self.concept}={value_str} {self.unit}, {self.fiscal_period} {self.fiscal_year})"


@dataclass
class ConceptMetadata:
    """
    Metadata about a financial concept.

    This provides additional context about what a concept represents,
    how it's calculated, and how it relates to other concepts.
    """
    concept: str                    # The concept identifier
    label: str                      # Primary display label
    definition: str                 # Detailed definition

    # Concept relationships
    parent_concepts: List[str] = field(default_factory=list)
    child_concepts: List[str] = field(default_factory=list)
    calculation_components: List[str] = field(default_factory=list)

    # Classification
    statement_type: Optional[str] = None  # BalanceSheet, IncomeStatement, etc.
    is_monetary: bool = True
    is_duration: bool = True        # True for flow concepts, False for stock concepts
    normal_balance: Optional[Literal['debit', 'credit']] = None

    # Usage guidance
    common_names: List[str] = field(default_factory=list)  # Alternative labels
    usage_notes: str = ''           # Special considerations
    typical_scale: Optional[int] = None  # Common scale factor


@dataclass
class FactCollection:
    """
    A collection of related facts, typically for a specific time period or statement.

    This is used internally to group facts for efficient processing and analysis.
    """
    facts: List[FinancialFact]
    period_key: str                 # e.g., "2024-Q4", "2024-FY"
    statement_type: Optional[str] = None

    def get_fact(self, concept: str) -> Optional[FinancialFact]:
        """Get a specific fact by concept"""
        for fact in self.facts:
            if fact.concept == concept or fact.label == concept:
                return fact
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary keyed by concept"""
        return {
            fact.concept: {
                'value': fact.numeric_value or fact.value,
                'label': fact.label,
                'unit': fact.unit
            }
            for fact in self.facts
        }
