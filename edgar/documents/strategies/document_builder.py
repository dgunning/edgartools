"""
Document builder that converts parsed HTML tree into document nodes.
"""

from typing import Any, Dict, Optional

from lxml.html import HtmlElement

from edgar.documents.config import ParserConfig
from edgar.documents.nodes import (
    ContainerNode,
    DocumentNode,
    HeadingNode,
    ImageNode,
    LinkNode,
    ListItemNode,
    ListNode,
    Node,
    ParagraphNode,
    SectionNode,
    TextNode,
)
from edgar.documents.strategies.style_parser import StyleParser
from edgar.documents.table_nodes import Cell, Row, TableNode
from edgar.documents.types import ParseContext, SemanticType, Style


class DocumentBuilder:
    """
    Builds Document node tree from parsed HTML.

    Handles the conversion of HTML elements into structured nodes
    with proper hierarchy and metadata.
    """

    # Block-level elements
    BLOCK_ELEMENTS = {
        'div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'blockquote', 'pre', 'hr',
        'table', 'form', 'fieldset', 'address', 'section',
        'article', 'aside', 'nav', 'header', 'footer', 'main'
    }

    # Inline elements
    INLINE_ELEMENTS = {
        'span', 'a', 'em', 'strong', 'b', 'i', 'u', 's',
        'small', 'mark', 'del', 'ins', 'sub', 'sup',
        'code', 'kbd', 'var', 'samp', 'abbr', 'cite',
        'q', 'time', 'font'
    }

    # Elements to skip
    SKIP_ELEMENTS = {'script', 'style', 'meta', 'link', 'noscript'}

    def __init__(self, config: ParserConfig, strategies: Dict[str, Any]):
        """
        Initialize document builder.

        Args:
            config: Parser configuration
            strategies: Dictionary of parsing strategies
        """
        self.config = config
        self.strategies = strategies
        self.style_parser = StyleParser()
        self.context = ParseContext()

        # Track XBRL context
        self.xbrl_context_stack = []
        self.xbrl_continuations = {}

    def build(self, tree: HtmlElement) -> DocumentNode:
        """
        Build document from HTML tree.

        Args:
            tree: Parsed HTML tree

        Returns:
            Document root node
        """
        # Create root document node
        root = DocumentNode()

        # Find body element
        body = tree.find('.//body')
        if body is None:
            # If no body, use the entire tree
            body = tree

        # Process body content
        self._process_element(body, root)

        # Apply node merging if configured
        if self.config.merge_adjacent_nodes:
            self._merge_adjacent_nodes(root)

        return root

    def _process_element(self, element: HtmlElement, parent: Node) -> Optional[Node]:
        """
        Process HTML element into node.

        Args:
            element: HTML element to process
            parent: Parent node

        Returns:
            Created node or None if skipped
        """
        # Skip certain elements
        if element.tag in self.SKIP_ELEMENTS:
            return None

        # Track parsing depth
        self.context.depth += 1

        try:
            # Handle XBRL elements
            if element.tag.startswith('{'):  # Namespaced element
                self._enter_xbrl_context(element)

            # Extract style
            style = self._extract_style(element)

            # Create appropriate node based on element type
            node = self._create_node_for_element(element, style)

            if node:
                # Add XBRL metadata if in context
                if self.xbrl_context_stack:
                    node.metadata.update(self._get_current_xbrl_metadata())

                # Add to parent
                parent.add_child(node)

                # Process children for container nodes
                if self._should_process_children(element, node):
                    # Add element's direct text first
                    if element.text:
                        if self.config.preserve_whitespace:
                            if element.text:  # Don't strip whitespace
                                text_node = TextNode(content=element.text)
                                node.add_child(text_node)
                        else:
                            if element.text.strip():
                                text_node = TextNode(content=element.text.strip())
                                node.add_child(text_node)

                    # Process child elements
                    for child in element:
                        self._process_element(child, node)

                    # Process text after children
                    if element.tail:
                        if self.config.preserve_whitespace:
                            text_node = TextNode(content=element.tail)
                            parent.add_child(text_node)
                        else:
                            if element.tail.strip():
                                text_node = TextNode(content=element.tail.strip())
                                parent.add_child(text_node)
                else:
                    # Node created but children not processed - still need to handle tail
                    if element.tail:
                        if self.config.preserve_whitespace:
                            text_node = TextNode(content=element.tail)
                            parent.add_child(text_node)
                        else:
                            if element.tail.strip():
                                text_node = TextNode(content=element.tail.strip())
                                parent.add_child(text_node)
            else:
                # No node created, process children with same parent
                for child in element:
                    self._process_element(child, parent)

                # Process tail text
                if element.tail:
                    if self.config.preserve_whitespace:
                        text_node = TextNode(content=element.tail)
                        parent.add_child(text_node)
                    else:
                        if element.tail.strip():
                            text_node = TextNode(content=element.tail.strip())
                            parent.add_child(text_node)

            # Exit XBRL context
            if element.tag.startswith('{'):
                self._exit_xbrl_context(element)

            return node

        finally:
            self.context.depth -= 1

    def _create_node_for_element(self, element: HtmlElement, style: Style) -> Optional[Node]:
        """Create appropriate node for HTML element."""
        tag = element.tag.lower() if not element.tag.startswith('{') else element.tag

        # Check for heading
        if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = int(tag[1])
            text = self._get_element_text(element)
            if text:
                return HeadingNode(content=text, level=level, style=style)

        # Handle specific elements first before header detection
        if tag == 'p':
            return ParagraphNode(style=style)

        elif tag == 'li':
            return ListItemNode(style=style)

        # Check if element might be a heading based on style/content
        # Skip header detection for certain tags that should never be headers
        skip_header_detection_tags = {'li', 'td', 'th', 'option', 'a', 'button', 'label'}
        if tag not in skip_header_detection_tags and self.strategies.get('header_detection'):
            header_info = self.strategies['header_detection'].detect(element, self.context)
            if header_info and header_info.confidence > self.config.header_detection_threshold:
                text = self._get_element_text(element)
                if text:
                    node = HeadingNode(
                        content=text,
                        level=header_info.level,
                        style=style
                    )
                    # Add header metadata
                    node.set_metadata('detection_method', header_info.detection_method)
                    node.set_metadata('confidence', header_info.confidence)
                    if header_info.is_item:
                        node.semantic_type = SemanticType.ITEM_HEADER
                        node.set_metadata('item_number', header_info.item_number)
                    return node

        # Continue handling other specific elements
        if tag == 'table':
            if self.strategies.get('table_processing'):
                return self.strategies['table_processing'].process(element)
            else:
                return self._process_table_basic(element, style)

        elif tag in ['ul', 'ol']:
            return ListNode(ordered=(tag == 'ol'), style=style)

        elif tag == 'li':
            return ListItemNode(style=style)

        elif tag == 'a':
            href = element.get('href', '')
            title = element.get('title', '')
            text = self._get_element_text(element)
            return LinkNode(content=text, href=href, title=title, style=style)

        elif tag == 'img':
            return ImageNode(
                src=element.get('src'),
                alt=element.get('alt'),
                width=self._parse_dimension(element.get('width')),
                height=self._parse_dimension(element.get('height')),
                style=style
            )

        elif tag == 'br':
            # Line break - add as text node
            return TextNode(content='\n')

        elif tag in ['section', 'article']:
            return SectionNode(style=style)

        elif tag == 'div' or tag in self.BLOCK_ELEMENTS:
            # Check if this is just a text container
            if self._is_text_only_container(element):
                text = self._get_element_text(element)
                if text:
                    return ParagraphNode(style=style)
            else:
                return ContainerNode(tag_name=tag, style=style)

        elif tag in self.INLINE_ELEMENTS:
            # Inline elements - extract text and add to parent
            text = self._get_element_text(element)
            if text:
                text_node = TextNode(content=text, style=style)
                # Preserve inline element metadata
                text_node.set_metadata('original_tag', tag)
                return text_node

        # Default: create container for unknown elements
        return ContainerNode(tag_name=tag, style=style)

    def _extract_style(self, element: HtmlElement) -> Style:
        """Extract style from element."""
        style_str = element.get('style', '')
        style = self.style_parser.parse(style_str)

        # Add tag-specific styles
        tag = element.tag.lower()
        if tag == 'b' or tag == 'strong':
            style.font_weight = 'bold'
        elif tag == 'i' or tag == 'em':
            style.font_style = 'italic'
        elif tag == 'u':
            style.text_decoration = 'underline'

        # Handle alignment
        align = element.get('align')
        if align:
            style.text_align = align

        return style

    def _get_element_text(self, element: HtmlElement) -> str:
        """Get text content from element."""
        text_parts = []

        # Get element's direct text
        if element.text:
            text_parts.append(element.text.strip())

        # For simple elements, get all text content
        if element.tag.lower() in self.INLINE_ELEMENTS or \
           element.tag.lower() in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            # Get all text including from child elements
            for child in element:
                if child.tag.lower() not in self.SKIP_ELEMENTS:
                    child_text = child.text_content()
                    if child_text:
                        text_parts.append(child_text.strip())

        return ' '.join(text_parts)

    def _is_text_only_container(self, element: HtmlElement) -> bool:
        """Check if element contains only text and inline elements."""
        for child in element:
            if child.tag.lower() in self.BLOCK_ELEMENTS:
                return False
            if child.tag.lower() == 'table':
                return False
        return True

    def _should_process_children(self, element: HtmlElement, node: Node) -> bool:
        """Determine if children should be processed."""
        # Don't process children for certain node types
        if isinstance(node, (TextNode, HeadingNode)):
            return False

        # Tables are processed separately
        if isinstance(node, TableNode):
            return False

        return True

    def _process_table_basic(self, element: HtmlElement, style: Style) -> TableNode:
        """Basic table processing without advanced strategy."""
        table = TableNode(style=style)

        # Extract caption
        caption_elem = element.find('.//caption')
        if caption_elem is not None:
            table.caption = caption_elem.text_content().strip()

        # Process rows
        for tr in element.findall('.//tr'):
            cells = []
            for td in tr.findall('.//td') + tr.findall('.//th'):
                cell = Cell(
                    content=td.text_content().strip(),
                    colspan=int(td.get('colspan', '1')),
                    rowspan=int(td.get('rowspan', '1')),
                    is_header=(td.tag == 'th'),
                    align=td.get('align')
                )
                cells.append(cell)

            if cells:
                row = Row(cells=cells, is_header=(tr.find('.//th') is not None))

                # Determine if header or data row
                if tr.getparent().tag == 'thead' or row.is_header:
                    table.headers.append(cells)
                else:
                    table.rows.append(row)

        return table

    def _parse_dimension(self, value: Optional[str]) -> Optional[int]:
        """Parse dimension value (width/height)."""
        if not value:
            return None

        # Remove 'px' suffix if present
        value = value.strip().rstrip('px')

        try:
            return int(value)
        except ValueError:
            return None

    def _enter_xbrl_context(self, element: HtmlElement):
        """Enter XBRL context."""
        if self.config.extract_xbrl and self.strategies.get('xbrl_extraction'):
            xbrl_data = self.strategies['xbrl_extraction'].extract_context(element)
            if xbrl_data:
                self.xbrl_context_stack.append(xbrl_data)

    def _exit_xbrl_context(self, element: HtmlElement):
        """Exit XBRL context."""
        if self.xbrl_context_stack:
            self.xbrl_context_stack.pop()

    def _get_current_xbrl_metadata(self) -> Dict[str, Any]:
        """Get current XBRL metadata."""
        if not self.xbrl_context_stack:
            return {}

        # Merge all contexts in stack
        metadata = {}
        for context in self.xbrl_context_stack:
            metadata.update(context)

        return metadata

    def _merge_adjacent_nodes(self, root: Node):
        """Merge adjacent text nodes with similar styles."""
        # Implementation would recursively merge adjacent text nodes
        # This is a placeholder for the actual implementation
        pass
