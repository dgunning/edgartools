"""
Semantic scoring for document structure awareness.

Provides structure-based boosting without ML/embeddings:
- Node type importance (headings, tables, XBRL)
- Cross-reference detection (gateway content)
- Section importance
- Text quality signals

This is NOT embedding-based semantic search. It's structure-aware ranking
that helps agents find investigation starting points.
"""

import re
from typing import List, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from edgar.documents.nodes import Node

from edgar.documents.types import NodeType, SemanticType


# Gateway terms that indicate summary/overview content
GATEWAY_TERMS = [
    'summary', 'overview', 'introduction', 'highlights',
    'key points', 'executive summary', 'in summary',
    'table of contents', 'index'
]

# Cross-reference patterns
CROSS_REFERENCE_PATTERNS = [
    r'\bsee\s+item\s+\d+[a-z]?\b',              # "See Item 1A"
    r'\bsee\s+(?:part|section)\s+\d+\b',        # "See Part II"
    r'\brefer\s+to\s+item\s+\d+[a-z]?\b',       # "Refer to Item 7"
    r'\bas\s+discussed\s+in\s+item\s+\d+\b',    # "As discussed in Item 1"
    r'\bfor\s+(?:more|additional)\s+information\b',  # "For more information"
]

# Section importance weights
SECTION_IMPORTANCE = {
    'risk factors': 1.5,
    'management discussion': 1.4,
    'md&a': 1.4,
    'business': 1.3,
    'financial statements': 1.2,
    'controls and procedures': 1.2,
}


def compute_semantic_scores(nodes: List['Node'],
                           query: str,
                           boost_sections: Optional[List[str]] = None) -> Dict[int, float]:
    """
    Compute semantic/structure scores for nodes.

    This provides structure-aware boosting based on:
    1. Node type (headings > tables > paragraphs)
    2. Cross-references (gateway content)
    3. Section importance
    4. Gateway terms (summaries, overviews)
    5. XBRL presence
    6. Text quality

    Args:
        nodes: Nodes to score
        query: Search query (for context-aware boosting)
        boost_sections: Additional sections to boost

    Returns:
        Dictionary mapping node id to semantic score (0-1 range)
    """
    scores = {}
    boost_sections = boost_sections or []

    # Get query context
    query_lower = query.lower()
    is_item_query = bool(re.search(r'item\s+\d+[a-z]?', query_lower))

    for node in nodes:
        score = 0.0

        # 1. Node Type Boosting
        score += _get_node_type_boost(node)

        # 2. Semantic Type Boosting
        score += _get_semantic_type_boost(node)

        # 3. Cross-Reference Detection (gateway content)
        score += _detect_cross_references(node)

        # 4. Gateway Content Detection
        score += _detect_gateway_content(node, query_lower)

        # 5. Section Importance Boosting
        score += _get_section_boost(node, boost_sections)

        # 6. XBRL Fact Boosting (for financial queries)
        score += _get_xbrl_boost(node)

        # 7. Text Quality Signals
        score += _get_quality_boost(node)

        # 8. Query-Specific Boosting
        if is_item_query:
            score += _get_item_header_boost(node)

        # Normalize to 0-1 range (max possible score is ~7.0)
        normalized_score = min(score / 7.0, 1.0)

        scores[id(node)] = normalized_score

    return scores


def _get_node_type_boost(node: 'Node') -> float:
    """
    Boost based on node type.

    Headings and structural elements are more important for navigation.
    """
    type_boosts = {
        NodeType.HEADING: 2.0,      # Headings are key navigation points
        NodeType.SECTION: 1.5,       # Section markers
        NodeType.TABLE: 1.0,         # Tables contain structured data
        NodeType.XBRL_FACT: 0.8,     # Financial facts
        NodeType.LIST: 0.5,          # Lists
        NodeType.PARAGRAPH: 0.3,     # Regular text
        NodeType.TEXT: 0.1,          # Plain text nodes
    }

    return type_boosts.get(node.type, 0.0)


def _get_semantic_type_boost(node: 'Node') -> float:
    """
    Boost based on semantic type.

    Section headers and items are important for SEC filings.
    """
    if not hasattr(node, 'semantic_type') or node.semantic_type is None:
        return 0.0

    semantic_boosts = {
        SemanticType.ITEM_HEADER: 2.0,          # Item headers are critical
        SemanticType.SECTION_HEADER: 1.5,       # Section headers
        SemanticType.FINANCIAL_STATEMENT: 1.2,  # Financial statements
        SemanticType.TABLE_OF_CONTENTS: 1.0,    # TOC is a gateway
        SemanticType.TITLE: 0.8,
        SemanticType.HEADER: 0.6,
    }

    return semantic_boosts.get(node.semantic_type, 0.0)


def _detect_cross_references(node: 'Node') -> float:
    """
    Detect cross-references that indicate gateway content.

    Content that points to other sections is useful for navigation.
    """
    text = node.text() if hasattr(node, 'text') else ''
    if not text:
        return 0.0

    text_lower = text.lower()

    # Check each pattern
    matches = 0
    for pattern in CROSS_REFERENCE_PATTERNS:
        if re.search(pattern, text_lower):
            matches += 1

    # Boost increases with number of cross-references
    return min(matches * 0.5, 1.5)  # Cap at 1.5


def _detect_gateway_content(node: 'Node', query_lower: str) -> float:
    """
    Detect gateway content (summaries, overviews, introductions).

    These are excellent starting points for investigation.
    """
    text = node.text() if hasattr(node, 'text') else ''
    if not text:
        return 0.0

    text_lower = text.lower()

    # Check for gateway terms in text
    for term in GATEWAY_TERMS:
        if term in text_lower:
            return 1.0

    # Check if this is an introductory paragraph (first ~200 chars)
    if len(text) < 200 and len(text) > 20:
        # Short intro paragraphs are often summaries
        if any(word in text_lower for word in ['provides', 'describes', 'includes', 'contains']):
            return 0.5

    return 0.0


def _get_section_boost(node: 'Node', boost_sections: List[str]) -> float:
    """
    Boost nodes in important sections.

    Some SEC sections are more relevant for certain queries.
    """
    # Try to determine section from node or ancestors
    section_name = _get_node_section(node)
    if not section_name:
        return 0.0

    section_lower = section_name.lower()

    # Check built-in importance
    for key, boost in SECTION_IMPORTANCE.items():
        if key in section_lower:
            return boost

    # Check user-specified sections
    for boost_section in boost_sections:
        if boost_section.lower() in section_lower:
            return 1.5

    return 0.0


def _get_xbrl_boost(node: 'Node') -> float:
    """
    Boost XBRL facts and tables with XBRL data.

    Financial data is important for financial queries.
    """
    if node.type == NodeType.XBRL_FACT:
        return 0.8

    # Check if table contains XBRL facts
    if node.type == NodeType.TABLE:
        # Check metadata for XBRL indicator
        if hasattr(node, 'metadata') and node.metadata.get('has_xbrl'):
            return 0.6

    return 0.0


def _get_quality_boost(node: 'Node') -> float:
    """
    Boost based on text quality signals.

    Higher quality content tends to be more useful:
    - Appropriate length (not too short, not too long)
    - Good structure (sentences, punctuation)
    - Substantive content (not just formatting)
    """
    text = node.text() if hasattr(node, 'text') else ''
    if not text:
        return 0.0

    score = 0.0

    # Length signal
    text_len = len(text)
    if 50 <= text_len <= 1000:
        score += 0.3  # Good length
    elif text_len > 1000:
        score += 0.1  # Long but might be comprehensive
    else:
        score += 0.0  # Too short, likely not substantive

    # Sentence structure
    sentence_count = text.count('.') + text.count('?') + text.count('!')
    if sentence_count >= 2:
        score += 0.2  # Multiple sentences indicate substantive content

    # Avoid pure formatting/navigation
    if text.strip() in ['...', '—', '-', 'Table of Contents', 'Page', '']:
        return 0.0  # Skip pure formatting

    return score


def _get_item_header_boost(node: 'Node') -> float:
    """
    Boost Item headers when query is about items.

    "Item 1A" queries should prioritize Item 1A headers.
    """
    if node.type != NodeType.HEADING:
        return 0.0

    text = node.text() if hasattr(node, 'text') else ''
    if not text:
        return 0.0

    # Check if this is an Item header
    if re.match(r'^\s*item\s+\d+[a-z]?[:\.\s]', text, re.IGNORECASE):
        return 1.5

    return 0.0


def _get_node_section(node: 'Node') -> Optional[str]:
    """
    Get section name for a node by walking up the tree.

    Returns:
        Section name if found, None otherwise
    """
    # Check if node has section in metadata
    if hasattr(node, 'metadata') and 'section' in node.metadata:
        return node.metadata['section']

    # Walk up tree looking for section marker
    current = node
    while current:
        if hasattr(current, 'semantic_type'):
            if current.semantic_type in (SemanticType.SECTION_HEADER, SemanticType.ITEM_HEADER):
                return current.text() if hasattr(current, 'text') else None

        current = current.parent if hasattr(current, 'parent') else None

    return None


def get_section_importance_names() -> List[str]:
    """
    Get list of important section names for reference.

    Returns:
        List of section names with built-in importance boosts
    """
    return list(SECTION_IMPORTANCE.keys())
