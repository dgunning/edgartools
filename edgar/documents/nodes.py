"""
Node hierarchy for the document tree.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable, Iterator

from edgar.documents.types import NodeType, SemanticType, Style
from edgar.documents.cache_mixin import CacheableMixin


@dataclass
class Node(ABC):
    """
    Base node class for document tree.
    
    All nodes in the document inherit from this class and implement
    the abstract methods for text and HTML generation.
    """
    
    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: NodeType = NodeType.DOCUMENT
    
    # Hierarchy
    parent: Optional['Node'] = field(default=None, repr=False)
    children: List['Node'] = field(default_factory=list, repr=False)
    
    # Content
    content: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    style: Style = field(default_factory=Style)
    
    # Semantic info
    semantic_type: Optional[SemanticType] = None
    semantic_role: Optional[str] = None
    
    def add_child(self, child: 'Node') -> None:
        """Add child node, maintaining parent reference."""
        child.parent = self
        self.children.append(child)
    
    def remove_child(self, child: 'Node') -> None:
        """Remove child node."""
        if child in self.children:
            self.children.remove(child)
            child.parent = None
    
    def insert_child(self, index: int, child: 'Node') -> None:
        """Insert child at specific index."""
        child.parent = self
        self.children.insert(index, child)
    
    @abstractmethod
    def text(self) -> str:
        """Extract text content from node and its children."""
        pass
    
    @abstractmethod
    def html(self) -> str:
        """Generate HTML representation of node."""
        pass
    
    def find(self, predicate: Callable[['Node'], bool]) -> List['Node']:
        """Find all nodes matching predicate."""
        results = []
        if predicate(self):
            results.append(self)
        for child in self.children:
            results.extend(child.find(predicate))
        return results
    
    def find_first(self, predicate: Callable[['Node'], bool]) -> Optional['Node']:
        """Find first node matching predicate."""
        if predicate(self):
            return self
        for child in self.children:
            result = child.find_first(predicate)
            if result:
                return result
        return None
    
    def xpath(self, expression: str) -> List['Node']:
        """
        Simple XPath-like node selection.
        
        Supports:
        - //node_type - Find all nodes of type
        - /node_type - Direct children of type
        - [@attr=value] - Attribute matching
        """
        # Simple implementation - can be extended
        if expression.startswith('//'):
            node_type = expression[2:].lower()
            return self.find(lambda n: n.type.name.lower() == node_type)
        elif expression.startswith('/'):
            node_type = expression[1:].lower()
            return [c for c in self.children if c.type.name.lower() == node_type]
        return []
    
    def walk(self) -> Iterator['Node']:
        """Walk the tree depth-first."""
        yield self
        for child in self.children:
            yield from child.walk()
    
    @property
    def depth(self) -> int:
        """Get depth of node in tree."""
        depth = 0
        current = self.parent
        while current:
            depth += 1
            current = current.parent
        return depth
    
    @property
    def path(self) -> str:
        """Get path from root to this node."""
        parts = []
        current = self
        while current:
            parts.append(current.type.name)
            current = current.parent
        return '/'.join(reversed(parts))
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value with default."""
        return self.metadata.get(key, default)
    
    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata value."""
        self.metadata[key] = value
    
    def has_metadata(self, key: str) -> bool:
        """Check if metadata key exists."""
        return key in self.metadata


@dataclass
class DocumentNode(Node, CacheableMixin):
    """Root document node."""
    type: NodeType = field(default=NodeType.DOCUMENT, init=False)

    def text(self) -> str:
        """Extract all text from document with caching."""
        def _generate_text():
            parts = []
            for child in self.children:
                text = child.text()
                if text:
                    parts.append(text)
            return '\n\n'.join(parts)

        return self._get_cached_text(_generate_text)
    
    def html(self) -> str:
        """Generate complete HTML document."""
        body_content = '\n'.join(child.html() for child in self.children)
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Document</title>
</head>
<body>
{body_content}
</body>
</html>"""


@dataclass
class TextNode(Node):
    """Plain text content node."""
    type: NodeType = field(default=NodeType.TEXT, init=False)
    content: str = ""
    
    def text(self) -> str:
        """Return text content."""
        return self.content
    
    def html(self) -> str:
        """Generate HTML for text."""
        # Escape HTML entities
        text = self.content
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        return text


@dataclass
class ParagraphNode(Node, CacheableMixin):
    """Paragraph node."""
    type: NodeType = field(default=NodeType.PARAGRAPH, init=False)

    def text(self) -> str:
        """Extract paragraph text with intelligent spacing and caching."""
        def _generate_text():
            parts = []
            for i, child in enumerate(self.children):
                text = child.text()
                if text:
                    # For the first child, just add the text
                    if i == 0:
                        parts.append(text)
                    else:
                        # For subsequent children, check if previous child had tail whitespace
                        prev_child = self.children[i - 1]
                        should_add_space = False

                        # Add space if previous child had tail whitespace
                        if hasattr(prev_child, 'get_metadata') and prev_child.get_metadata('has_tail_whitespace'):
                            should_add_space = True

                        # Add space if current text starts with space (preserve intended spacing)
                        elif text.startswith(' '):
                            should_add_space = True
                            # Remove the leading space from text since we're adding it as separation
                            text = text.lstrip()

                        # Add space if previous text ends with punctuation (sentence boundaries)
                        elif parts and parts[-1].rstrip()[-1:] in '.!?:;':
                            should_add_space = True

                        # Add space between adjacent inline elements if the current text starts with a letter/digit
                        # This handles cases where whitespace was stripped but spacing is semantically important
                        elif (text and text[0].isalpha() and
                              parts and parts[-1] and not parts[-1].endswith(' ') and
                              hasattr(child, 'get_metadata') and child.get_metadata('original_tag') in ['span', 'a', 'em', 'strong', 'i', 'b']):
                            should_add_space = True

                        if should_add_space:
                            parts.append(' ' + text)
                        else:
                            # Concatenate directly without space
                            if parts:
                                parts[-1] += text
                            else:
                                parts.append(text)

            return ''.join(parts)

        return self._get_cached_text(_generate_text)
    
    def html(self) -> str:
        """Generate paragraph HTML."""
        content = ''.join(child.html() for child in self.children)
        style_attr = self._generate_style_attr()
        return f'<p{style_attr}>{content}</p>'
    
    def _generate_style_attr(self) -> str:
        """Generate style attribute from style object."""
        if not self.style:
            return ''
        
        styles = []
        if self.style.text_align:
            styles.append(f'text-align: {self.style.text_align}')
        if self.style.margin_top:
            styles.append(f'margin-top: {self.style.margin_top}px')
        if self.style.margin_bottom:
            styles.append(f'margin-bottom: {self.style.margin_bottom}px')
        
        if styles:
            return f' style="{"; ".join(styles)}"'
        return ''


@dataclass
class HeadingNode(Node):
    """Heading node with level."""
    type: NodeType = field(default=NodeType.HEADING, init=False)
    level: int = 1
    
    def text(self) -> str:
        """Extract heading text."""
        if isinstance(self.content, str):
            return self.content
        
        parts = []
        for child in self.children:
            text = child.text()
            if text:
                parts.append(text)
        return ' '.join(parts)
    
    def html(self) -> str:
        """Generate heading HTML."""
        level = max(1, min(6, self.level))  # Ensure level is 1-6
        content = self.text()
        style_attr = self._generate_style_attr()
        return f'<h{level}{style_attr}>{content}</h{level}>'
    
    def _generate_style_attr(self) -> str:
        """Generate style attribute."""
        styles = []
        if self.style.text_align:
            styles.append(f'text-align: {self.style.text_align}')
        if self.style.color:
            styles.append(f'color: {self.style.color}')
        if styles:
            return f' style="{"; ".join(styles)}"'
        return ''


@dataclass
class ContainerNode(Node, CacheableMixin):
    """Generic container node (div, section, etc.)."""
    type: NodeType = field(default=NodeType.CONTAINER, init=False)
    tag_name: str = 'div'

    def text(self) -> str:
        """Extract text from container with caching."""
        def _generate_text():
            parts = []
            for child in self.children:
                text = child.text()
                if text:
                    parts.append(text)
            return '\n'.join(parts)

        return self._get_cached_text(_generate_text)
    
    def html(self) -> str:
        """Generate container HTML."""
        content = '\n'.join(child.html() for child in self.children)
        style_attr = self._generate_style_attr()
        class_attr = f' class="{self.semantic_role}"' if self.semantic_role else ''
        return f'<{self.tag_name}{style_attr}{class_attr}>{content}</{self.tag_name}>'
    
    def _generate_style_attr(self) -> str:
        """Generate style attribute."""
        if not self.style:
            return ''
        
        styles = []
        if self.style.margin_top:
            styles.append(f'margin-top: {self.style.margin_top}px')
        if self.style.margin_bottom:
            styles.append(f'margin-bottom: {self.style.margin_bottom}px')
        if self.style.padding_left:
            styles.append(f'padding-left: {self.style.padding_left}px')
        
        if styles:
            return f' style="{"; ".join(styles)}"'
        return ''


@dataclass 
class SectionNode(ContainerNode):
    """Document section node."""
    type: NodeType = field(default=NodeType.SECTION, init=False)
    section_name: Optional[str] = None
    tag_name: str = field(default='section', init=False)
    
    def __post_init__(self):
        if self.section_name:
            self.set_metadata('section_name', self.section_name)


@dataclass
class ListNode(Node):
    """List node (ordered or unordered)."""
    type: NodeType = field(default=NodeType.LIST, init=False)
    ordered: bool = False
    
    def text(self) -> str:
        """Extract list text."""
        parts = []
        for i, child in enumerate(self.children):
            if self.ordered:
                prefix = f"{i+1}. "
            else:
                prefix = "• "
            text = child.text()
            if text:
                parts.append(f"{prefix}{text}")
        return '\n'.join(parts)
    
    def html(self) -> str:
        """Generate list HTML."""
        tag = 'ol' if self.ordered else 'ul'
        items = '\n'.join(child.html() for child in self.children)
        return f'<{tag}>\n{items}\n</{tag}>'


@dataclass
class ListItemNode(Node):
    """List item node."""
    type: NodeType = field(default=NodeType.LIST_ITEM, init=False)
    
    def text(self) -> str:
        """Extract list item text."""
        parts = []
        for child in self.children:
            text = child.text()
            if text:
                parts.append(text)
        return ' '.join(parts)
    
    def html(self) -> str:
        """Generate list item HTML."""
        content = ''.join(child.html() for child in self.children)
        return f'<li>{content}</li>'


@dataclass
class LinkNode(Node):
    """Hyperlink node."""
    type: NodeType = field(default=NodeType.LINK, init=False)
    href: Optional[str] = None
    title: Optional[str] = None
    
    def text(self) -> str:
        """Extract link text."""
        if isinstance(self.content, str):
            return self.content
        
        parts = []
        for child in self.children:
            text = child.text()
            if text:
                parts.append(text)
        return ' '.join(parts)
    
    def html(self) -> str:
        """Generate link HTML."""
        content = self.text()
        href_attr = f' href="{self.href}"' if self.href else ''
        title_attr = f' title="{self.title}"' if self.title else ''
        return f'<a{href_attr}{title_attr}>{content}</a>'


@dataclass
class ImageNode(Node):
    """Image node."""
    type: NodeType = field(default=NodeType.IMAGE, init=False)
    src: Optional[str] = None
    alt: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    
    def text(self) -> str:
        """Extract image alt text."""
        return self.alt or ''
    
    def html(self) -> str:
        """Generate image HTML."""
        src_attr = f' src="{self.src}"' if self.src else ''
        alt_attr = f' alt="{self.alt}"' if self.alt else ''
        width_attr = f' width="{self.width}"' if self.width else ''
        height_attr = f' height="{self.height}"' if self.height else ''
        return f'<img{src_attr}{alt_attr}{width_attr}{height_attr}>'