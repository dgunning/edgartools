"""
Type definitions for the HTML parser.
"""

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol, Union, Optional, Dict, Any, List


class NodeType(Enum):
    """Types of nodes in the document tree."""
    DOCUMENT = auto()
    SECTION = auto()
    HEADING = auto()
    PARAGRAPH = auto()
    TABLE = auto()
    LIST = auto()
    LIST_ITEM = auto()
    LINK = auto()
    IMAGE = auto()
    XBRL_FACT = auto()
    TEXT = auto()
    CONTAINER = auto()


class SemanticType(Enum):
    """Semantic types for document understanding."""
    TITLE = auto()
    HEADER = auto()
    BODY_TEXT = auto()
    FOOTNOTE = auto()
    TABLE_OF_CONTENTS = auto()
    FINANCIAL_STATEMENT = auto()
    DISCLOSURE = auto()
    ITEM_HEADER = auto()
    SECTION_HEADER = auto()
    SIGNATURE = auto()
    EXHIBIT = auto()


class TableType(Enum):
    """Types of tables for semantic understanding."""
    FINANCIAL = auto()
    METRICS = auto()
    REFERENCE = auto()
    GENERAL = auto()
    TABLE_OF_CONTENTS = auto()
    EXHIBIT_INDEX = auto()


@dataclass
class Style:
    """Unified style representation."""
    font_size: Optional[float] = None
    font_weight: Optional[str] = None
    font_style: Optional[str] = None
    text_align: Optional[str] = None
    text_decoration: Optional[str] = None
    color: Optional[str] = None
    background_color: Optional[str] = None
    margin_top: Optional[float] = None
    margin_bottom: Optional[float] = None
    margin_left: Optional[float] = None
    margin_right: Optional[float] = None
    padding_top: Optional[float] = None
    padding_bottom: Optional[float] = None
    padding_left: Optional[float] = None
    padding_right: Optional[float] = None
    display: Optional[str] = None
    width: Optional[Union[float, str]] = None
    height: Optional[Union[float, str]] = None
    line_height: Optional[float] = None
    
    def merge(self, other: 'Style') -> 'Style':
        """Merge this style with another, with other taking precedence."""
        merged = Style()
        for field in self.__dataclass_fields__:
            other_value = getattr(other, field)
            if other_value is not None:
                setattr(merged, field, other_value)
            else:
                setattr(merged, field, getattr(self, field))
        return merged
    
    @property
    def is_bold(self) -> bool:
        """Check if style represents bold text."""
        return self.font_weight in ('bold', '700', '800', '900')
    
    @property
    def is_italic(self) -> bool:
        """Check if style represents italic text."""
        return self.font_style == 'italic'
    
    @property
    def is_centered(self) -> bool:
        """Check if text is centered."""
        return self.text_align == 'center'


class NodeProtocol(Protocol):
    """Protocol for all nodes."""
    id: str
    type: NodeType
    content: Any
    metadata: Dict[str, Any]
    style: Style
    parent: Optional['NodeProtocol']
    children: List['NodeProtocol']
    
    def text(self) -> str: ...
    def html(self) -> str: ...
    def find(self, predicate) -> List['NodeProtocol']: ...


@dataclass
class HeaderInfo:
    """Information about detected headers."""
    level: int  # 1-6
    confidence: float  # 0.0-1.0
    text: str
    detection_method: str
    is_item: bool = False
    item_number: Optional[str] = None
    
    @classmethod
    def from_text(cls, text: str, level: int, confidence: float, method: str) -> 'HeaderInfo':
        """Create HeaderInfo from text, detecting if it's an item header."""
        # Check for item patterns
        item_pattern = re.compile(r'^(Item|ITEM)\s+(\d+[A-Z]?\.?)', re.IGNORECASE)
        match = item_pattern.match(text.strip())
        
        is_item = bool(match)
        item_number = match.group(2).rstrip('.') if match else None
        
        return cls(
            level=level,
            confidence=confidence,
            text=text,
            detection_method=method,
            is_item=is_item,
            item_number=item_number
        )


@dataclass
class XBRLFact:
    """Represents an XBRL fact extracted from inline XBRL."""
    concept: str
    value: str
    context_ref: Optional[str] = None
    unit_ref: Optional[str] = None
    decimals: Optional[str] = None
    scale: Optional[str] = None
    format: Optional[str] = None
    sign: Optional[str] = None
    
    # Resolved references
    context: Optional[Dict[str, Any]] = None
    unit: Optional[str] = None
    
    # Additional metadata
    metadata: Optional[Dict[str, Any]] = None
    
    @property
    def numeric_value(self) -> Optional[float]:
        """Get numeric value if applicable."""
        try:
            # Remove commas and convert
            clean_value = self.value.replace(',', '')
            return float(clean_value)
        except (ValueError, AttributeError):
            return None
    
    @property
    def is_numeric(self) -> bool:
        """Check if this is a numeric fact."""
        return self.numeric_value is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert XBRLFact to dictionary."""
        return {
            'concept': self.concept,
            'value': self.value,
            'context_ref': self.context_ref,
            'unit_ref': self.unit_ref,
            'decimals': self.decimals,
            'scale': self.scale,
            'format': self.format,
            'sign': self.sign,
            'context': self.context,
            'unit': self.unit,
            'is_numeric': self.is_numeric,
            'numeric_value': self.numeric_value
        }


@dataclass
class SearchResult:
    """
    Result from document search.

    Designed for agent-friendly investigation workflows - provides access to
    full section context rather than fragmented chunks.
    """
    node: 'NodeProtocol'
    score: float
    snippet: str
    section: Optional[str] = None
    context: Optional[str] = None
    _section_obj: Optional[Any] = None  # Hidden Section object for agent navigation

    @property
    def section_object(self) -> Optional[Any]:
        """
        Get full Section object for agent navigation.

        Enables multi-step investigation by providing access to complete
        section content, not just the matched fragment.

        Returns:
            Section object with text(), tables(), and search() methods
        """
        return self._section_obj

    @property
    def full_context(self) -> str:
        """
        Get complete section text for agent investigation.

        Returns full section content instead of fragmented chunks.
        This supports the post-RAG "investigation not retrieval" pattern.

        Returns:
            Complete section text if section available, else snippet
        """
        if self._section_obj and hasattr(self._section_obj, 'text'):
            return self._section_obj.text()
        return self.snippet


@dataclass
class ParseContext:
    """Context information during parsing."""
    base_font_size: float = 10.0
    current_section: Optional[str] = None
    in_table: bool = False
    in_list: bool = False
    depth: int = 0
    style_stack: List[Style] = None
    
    def __post_init__(self):
        if self.style_stack is None:
            self.style_stack = []
    
    def push_style(self, style: Style):
        """Push style onto stack."""
        self.style_stack.append(style)
    
    def pop_style(self):
        """Pop style from stack."""
        if self.style_stack:
            self.style_stack.pop()
    
    def get_current_style(self) -> Style:
        """Get combined style from stack."""
        if not self.style_stack:
            return Style()
        
        result = self.style_stack[0]
        for style in self.style_stack[1:]:
            result = result.merge(style)
        return result


# Type aliases for clarity
NodeId = str
SectionName = str
ConceptName = str
ContextRef = str
UnitRef = str