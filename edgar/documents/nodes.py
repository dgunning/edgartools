"""
Node hierarchy for the document tree.
"""

import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional

from edgar.documents.cache_mixin import CacheableMixin
from edgar.documents.types import NodeType, SemanticType, Style


def _has_left_gap(node) -> bool:
    """Whether the filer drew a word gap with CSS instead of with whitespace."""
    style = getattr(node, 'style', None)
    if style is None:
        return False
    return bool((style.padding_left or 0) > 0 or (style.margin_left or 0) > 0)


def _is_marker_box(node) -> bool:
    """Whether this node is a fixed-width box holding a list marker.

    A filer who writes `<span style="display:inline-block;width:0.25in">-</span>` has
    reserved a quarter inch for the dash, so the text after it starts at the far edge of
    that box. Same gap as a padding-left on the text, drawn from the other side — it is
    how SigmaTron's FY2025 10-K lays out its risk-factor bullets.
    """
    style = getattr(node, 'style', None)
    if style is None:
        return False
    return bool(style.display and 'inline-block' in style.display and style.width)


_SYMBOL_MARKERS = frozenset('•◦▪▸‣·*†‡§☐☑☒')
# Rendered in Wingdings these are checkboxes; in the character stream they are letters.
_LETTER_MARKERS = frozenset('oýþ¨')
_MARKER_GLYPHS = _SYMBOL_MARKERS | _LETTER_MARKERS


def _is_bare_marker(part: str, next_text: str = '') -> bool:
    """Whether the text so far ends in a standalone list or checkbox marker.

    A checkbox and its label, or a footnote asterisk and its note, are two runs the filer
    does not separate with whitespace — `☐ Yes`, `* Certain projects have multiple wells`.
    Unlike `_has_left_gap` this reads the text rather than the style, which is what makes
    it reach the cover-page checkboxes: SigmaTron writes
    `style="…font-family: "Wingdings""`, nested double quotes inside a double-quoted
    attribute, so `font-family` parses as empty for us and for a browser alike and no
    style-based rule can fire there.

    The letter markers need the second guard. This branch is reached before any test for
    a mid-word split, and filers do split words across elements — A-Power's FY2009 20-F
    writes `our` as `o`+`ur`, which without the guard extracts as `o ur wind turbine
    business`. A checkbox label is `Yes` or `No`, never a lowercase continuation.
    """
    stripped = part.rstrip()
    if not stripped:
        return False
    glyph = stripped[-1]
    if glyph not in _MARKER_GLYPHS:
        return False
    # A standalone glyph, not the last letter of a word ('o' ends 'Chevro', 'Tokyo').
    if not (len(stripped) == 1 or not stripped[-2].isalnum()):
        return False
    if glyph in _LETTER_MARKERS and next_text[:1].islower():
        return False
    return True


def _ends_with_tail_whitespace(node) -> bool:
    """Whether this node's content ends with whitespace that was in the source.

    DocumentBuilder records a whitespace-only tail as metadata on the element that owns
    it, which is the innermost one — but the spacing decision here is made between that
    element's ancestors, so reading the flag off the sibling alone misses it whenever the
    whitespace sits inside a wrapper. Chevron's FY2024 10-K puts a run-in heading in an
    <ix:nonNumeric> and the gap after it in a spacer span inside that element, two levels
    below the sibling being compared, and shipped 'GeneralThe Company follows'.

    Walking the rightmost spine is enough: whitespace anywhere else in the subtree is not
    at the boundary being decided.
    """
    while node is not None:
        if hasattr(node, 'get_metadata') and node.get_metadata('has_tail_whitespace'):
            return True
        children = getattr(node, 'children', None)
        node = children[-1] if children else None
    return False


# eq=False on Node and every subclass: nodes compare by identity, as plain
# objects do.
#
# The generated __eq__ compared field by field and recursed through `parent` and
# `children`, so every `==`, `in`, `.index()` and `.remove()` on a node bought a
# deep structural walk of the tree where the caller meant identity. It cost real
# time — `n.parent not in nodes_in_range` was 10.5s of Citigroup's 18s sections
# stage (edgartools-llmp.6.10) — and on one input it did not return at all:
#
#     a = ParagraphNode(); a.add_child(TextNode(content='x'))
#     a == copy.deepcopy(a)     # RecursionError: parent -> children -> parent
#
# deepcopy preserves `id`, so the uuid that normally decides the comparison on
# its first field stops short-circuiting and the walk turns back on itself.
#
# Nothing observable changes. `id` is a uuid compared first, so two distinct
# nodes were already unequal and a node was already equal to itself; identity
# was the only answer equality could give that was not a crash. Nodes also
# become hashable again — eq=True sets __hash__ to None, so sets and dicts of
# nodes had to be keyed on id() (edgartools-llmp.10).
@dataclass(eq=False)
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


@dataclass(eq=False)
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


@dataclass(eq=False)
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


@dataclass(eq=False)
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
                        if _ends_with_tail_whitespace(prev_child):
                            should_add_space = True

                        # Add space if current text starts with space (preserve intended spacing)
                        elif text.startswith(' '):
                            should_add_space = True
                            # Remove the leading space from text since we're adding it as separation
                            text = text.lstrip()

                        # Add space if previous text ends with sentence-ending punctuation,
                        # but NOT if it looks like an abbreviation (single letter + period,
                        # or common abbreviation like Inc., Corp., etc.)
                        elif parts and parts[-1].rstrip()[-1:] in '.!?:;':
                            if not self._is_abbreviation_ending(parts[-1]):
                                should_add_space = True

                        # The filer drew a word gap without using whitespace: a bullet
                        # glyph and its item text, a footnote marker and its note, a
                        # cover-page checkbox and its label. Three signals, each reading
                        # the boundary rather than guessing at it — a CSS gap on the text
                        # that follows, a fixed-width box around the marker before it, or
                        # a standalone marker glyph in the text itself.
                        #
                        # These replace a `original_tag in ['span','a','em',...]`
                        # allowlist that stood in for them until 2026-08-02, and that
                        # spaced any two adjacent inline elements whatever sat between
                        # them — inventing far more boundaries than it restored, notably
                        # inside Item headings ('Item 1A. RI SK FACTORS'). See the
                        # CHANGELOG and edgartools-jysx for the measurement.
                        elif (parts and parts[-1] and not parts[-1].endswith(' ')
                              and (_has_left_gap(child) or _is_marker_box(prev_child)
                                   or _is_bare_marker(parts[-1], text))):
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

    @staticmethod
    def _is_abbreviation_ending(text: str) -> bool:
        """Check if text ends with an abbreviation rather than a sentence boundary."""
        stripped = text.rstrip()
        if not stripped:
            return False
        # Single letter + period BUT NOT after SEC terms like "Class A.", "Series B.", "Exhibit A."
        # where the letter is an identifier, not an abbreviation component
        if re.search(r'\b[A-Za-z]\.$', stripped):
            # Exclude SEC classification patterns where a single letter is a label, not abbreviation
            if re.search(r'(?:Class|Series|Exhibit|Schedule|Part|Annex|Appendix|Grade|Tier|Type|Group|Tranche)\s+[A-Z]\.$', stripped):
                return False
            return True
        # Common abbreviations that end with a period
        if re.search(r'(?:Inc|Corp|Ltd|Jr|Sr|Dr|Mr|Mrs|Ms|vs|etc|approx|est|Vol|No|Dept)\.$', stripped):
            return True
        return False

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


@dataclass(eq=False)
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


@dataclass(eq=False)
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


@dataclass(eq=False)
class SectionNode(ContainerNode):
    """Document section node."""
    type: NodeType = field(default=NodeType.SECTION, init=False)
    section_name: Optional[str] = None
    tag_name: str = field(default='section', init=False)

    def __post_init__(self):
        if self.section_name:
            self.set_metadata('section_name', self.section_name)


@dataclass(eq=False)
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


@dataclass(eq=False)
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


@dataclass(eq=False)
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


@dataclass(eq=False)
class ImageNode(Node):
    """Image node."""
    type: NodeType = field(default=NodeType.IMAGE, init=False)
    src: Optional[str] = None
    alt: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

    def text(self) -> str:
        """Images contribute no document text.

        ``alt`` is a description *of* an image, not text the filer wrote into
        the document, and it is frequently just the source file name
        ("nvidialogoa10.jpg"). Returning it here leaked bare filenames into
        ``Filing.text()`` through ``ParagraphNode.text()``, which aggregates
        child ``text()``, with nothing marking them as image captions.

        Callers that want images represented ask for it explicitly and read
        ``alt``/``src`` themselves: ``TextExtractor(include_images=True)``
        emits ``[Image: ...]`` and ``MarkdownRenderer`` emits ``![alt](src)``.
        """
        return ''

    def html(self) -> str:
        """Generate image HTML."""
        src_attr = f' src="{self.src}"' if self.src else ''
        alt_attr = f' alt="{self.alt}"' if self.alt else ''
        width_attr = f' width="{self.width}"' if self.width else ''
        height_attr = f' height="{self.height}"' if self.height else ''
        return f'<img{src_attr}{alt_attr}{width_attr}{height_attr}>'
