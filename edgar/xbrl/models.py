"""
Data models for XBRL parsing.

This module defines the core data structures used throughout the XBRL parser.
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

# Constants for label roles
STANDARD_LABEL = "http://www.xbrl.org/2003/role/label"
TERSE_LABEL = "http://www.xbrl.org/2003/role/terseLabel"
PERIOD_START_LABEL = "http://www.xbrl.org/2003/role/periodStartLabel"
PERIOD_END_LABEL = "http://www.xbrl.org/2003/role/periodEndLabel"
TOTAL_LABEL = "http://www.xbrl.org/2003/role/totalLabel"


def select_display_label(
        labels: Dict[str, str],
        preferred_label: Optional[str] = None,
        standard_label: Optional[str] = None,
        element_id: Optional[str] = None,
        element_name: Optional[str] = None
) -> str:
    """
    Select the most appropriate label for display, following a consistent priority order.
    Includes standardization mapping to provide consistent labels across companies.

    Args:
        labels: Dictionary of available labels
        preferred_label: Role of the preferred label (if specified in presentation linkbase)
        standard_label: The standard label content (if available)
        element_id: Element ID (fallback)
        element_name: Element name (alternative fallback)

    Returns:
        The selected label according to priority rules, with standardization applied if available
    """
    # First, select the best available label using existing priority logic
    selected_label = None

    # 1. Use preferred label if specified and available
    if preferred_label and labels and preferred_label in labels:
        selected_label = labels[preferred_label]

    # 2. Use terse label if available (more user-friendly)
    elif labels and TERSE_LABEL in labels:
        selected_label = labels[TERSE_LABEL]

    # 3. Fall back to standard label
    elif standard_label:
        selected_label = standard_label

    # 4. Try STANDARD_LABEL directly from labels dict
    elif labels and STANDARD_LABEL in labels:
        selected_label = labels[STANDARD_LABEL]

    # 5. Take any available label
    elif labels:
        selected_label = next(iter(labels.values()), "")

    # 6. Use element name if available
    elif element_name:
        selected_label = element_name

    # 7. Last resort: element ID
    else:
        selected_label = element_id or ""

    # Apply standardization if we have an element_id (concept)
    if element_id and selected_label:
        try:
            from edgar.xbrl.standardization.core import initialize_default_mappings

            # Initialize mapping store (cached after first call)
            if not hasattr(select_display_label, '_mapping_store'):
                select_display_label._mapping_store = initialize_default_mappings(read_only=True)

            # Try to get standardized concept
            standardized_label = select_display_label._mapping_store.get_standard_concept(element_id)

            if standardized_label:
                return standardized_label

        except ImportError:
            # Standardization not available, continue with selected label
            pass
        except Exception:
            # Any other error in standardization, continue with selected label
            pass

    return selected_label


class ElementCatalog:
    """
    A catalog of XBRL elements with their properties.

    This is the base data structure for element metadata as described in the design document.

    Attributes:
        name: The name of the element (e.g., "us-gaap_NetIncome")
        data_type: The data type of the element (e.g., "monetary", "string", etc.)
        period_type: The period type of the element (e.g., "instant", "duration")
        balance: The balance type of the element (e.g., "debit", "credit", or None)
        abstract: Whether the element is abstract (True/False)
        labels: A dictionary of labels for the element, keyed by role URI
    """

    def __init__(self,
                 name: str,
                 data_type: str,
                 period_type: str,
                 balance: Optional[str] = None,
                 abstract: bool = False,
                 labels: Optional[Dict[str, str]] = None
                 ):
        self.name = name
        self.data_type = data_type
        self.period_type = period_type
        self.balance = balance
        self.abstract = abstract
        self.labels = labels if labels is not None else {}

    def __str__(self) -> str:
        return self.name


class Context(BaseModel):
    """
    An XBRL context defining entity, period, and dimensional information.

    This corresponds to the Context Registry in the design document.
    """
    context_id: str
    entity: Dict[str, Any] = Field(default_factory=dict)
    period: Dict[str, Any] = Field(default_factory=dict)
    dimensions: Dict[str, str] = Field(default_factory=dict)

    @property
    def period_string(self) -> str:
        """Return a human-readable string representation of the period."""
        if self.period.get('type') == 'instant':
            return f"As of {self.period.get('instant')}"
        elif self.period.get('type') == 'duration':
            return f"From {self.period.get('startDate')} to {self.period.get('endDate')}"
        else:
            return "Forever"


class Fact(BaseModel):
    """
    An XBRL fact with value and references to context, unit, and element.

    This corresponds to the Fact Database in the design document.

    The instance_id field is used to differentiate between duplicate facts
    that share the same element_id and context_ref. When a fact has no
    duplicates, instance_id will be None.

    The fact_id field preserves the original id attribute from the XML element,
    enabling linkage with footnotes.
    """
    element_id: str
    context_ref: str
    value: str
    unit_ref: Optional[str] = None
    decimals: Optional[Union[int, str]] = None  # int or "INF"
    numeric_value: Optional[float] = None
    footnotes: List[str] = Field(default_factory=list)
    instance_id: Optional[int] = None
    fact_id: Optional[str] = None  # Original id attribute from the XML


class Footnote(BaseModel):
    """
    Represents an XBRL footnote with its text content and related facts.

    Footnotes are linked to facts via footnoteArc elements that connect
    fact IDs to footnote IDs using xlink:from and xlink:to attributes.
    """
    footnote_id: str
    text: str
    lang: Optional[str] = "en-US"
    role: Optional[str] = None
    related_fact_ids: List[str] = Field(default_factory=list)


class PresentationNode(BaseModel):
    """
    A node in the presentation hierarchy.

    This corresponds to the Presentation Node in the design document.
    """
    element_id: str
    parent: Optional[str] = None
    children: List[str] = Field(default_factory=list)
    order: float = 0.0
    preferred_label: Optional[str] = None
    depth: int = 0

    # Additional information linked from element catalog
    element_name: Optional[str] = None
    standard_label: Optional[str] = None
    is_abstract: bool = False
    labels: Dict[str, str] = Field(default_factory=dict)

    @property
    def display_label(self) -> str:
        """
        Return the appropriate label for display, prioritizing user-friendly options.

        Label selection priority:
        1. Preferred label (if specified in presentation linkbase)
        2. Terse label (for more concise display)
        3. Label (standard label)
        4. Element ID (fallback)
        """
        return select_display_label(
            labels=self.labels,
            standard_label=self.standard_label,
            preferred_label=self.preferred_label,
            element_id=self.element_id
        )


class PresentationTree(BaseModel):
    """
    A presentation tree for a specific role.

    This corresponds to the Presentation Hierarchy in the design document.
    """
    role_uri: str
    definition: str
    root_element_id: str
    all_nodes: Dict[str, PresentationNode] = Field(default_factory=dict)
    order: int = 0


class CalculationNode(BaseModel):
    """
    A node in the calculation hierarchy.

    This corresponds to the Calculation Node in the design document.
    """
    element_id: str
    children: List[str] = Field(default_factory=list)
    parent: Optional[str] = None
    weight: float = 1.0
    order: float = 0.0

    # Information linked from schema
    balance_type: Optional[str] = None  # "debit", "credit", or None
    period_type: Optional[str] = None  # "instant" or "duration"


class CalculationTree(BaseModel):
    """
    A calculation tree for a specific role.

    This corresponds to the Calculation Network in the design document.
    """
    role_uri: str
    definition: str
    root_element_id: str
    all_nodes: Dict[str, CalculationNode] = Field(default_factory=dict)


class Axis(BaseModel):
    """
    A dimensional axis (dimension) in XBRL.

    This corresponds to the Axis (Dimension) in the design document.
    """
    element_id: str
    label: str
    domain_id: Optional[str] = None
    default_member_id: Optional[str] = None
    is_typed_dimension: bool = False
    typed_domain_ref: str = ""


class Domain(BaseModel):
    """
    A domain in an XBRL dimensional structure.

    This corresponds to the Domain in the design document.
    """
    element_id: str
    label: str
    members: List[str] = Field(default_factory=list)  # List of domain member element IDs
    parent: Optional[str] = None  # Parent domain element ID


class Table(BaseModel):
    """
    A dimensional table (hypercube) in XBRL.

    This corresponds to the Table (Hypercube) in the design document.
    """
    element_id: str
    label: str
    role_uri: str
    axes: List[str] = Field(default_factory=list)  # List of axis element IDs
    line_items: List[str] = Field(default_factory=list)  # List of line item element IDs
    closed: bool = False
    context_element: str = "segment"


class XBRLProcessingError(Exception):
    """Exception raised for errors during XBRL processing."""
    pass
