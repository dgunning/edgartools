"""
Simple HTML parser implementation for basic testing.
"""

import lxml.html

from edgar.documents.document import Document, DocumentMetadata
from edgar.documents.nodes import ContainerNode, DocumentNode, HeadingNode, ParagraphNode, TextNode
from edgar.documents.table_nodes import Cell, Row, TableNode


class SimpleHTMLParser:
    """Simple HTML parser for testing."""

    def parse(self, html: str) -> Document:
        """Parse HTML into document."""
        # Parse with lxml
        parser = lxml.html.HTMLParser(
            remove_blank_text=True,
            remove_comments=True,
            recover=True
        )

        if not html.strip():
            # Return empty document
            root = DocumentNode()
            metadata = DocumentMetadata()
            return Document(root=root, metadata=metadata)

        # Remove XML declaration if present
        if html.startswith('<?xml'):
            end_of_decl = html.find('?>')
            if end_of_decl != -1:
                html = html[end_of_decl + 2:]

        tree = lxml.html.fromstring(html, parser=parser)

        # Create document
        root = DocumentNode()
        metadata = DocumentMetadata()

        # Build node tree
        self._build_node_tree(tree, root)

        return Document(root=root, metadata=metadata)

    def _build_node_tree(self, elem, parent_node):
        """Build node tree from lxml element."""
        tag = elem.tag.lower() if isinstance(elem.tag, str) else ''

        # Skip script and style
        if tag in ['script', 'style']:
            return

        # Create appropriate node
        if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = int(tag[1])
            text = self._get_text_content(elem)
            node = HeadingNode(level=level, content=text)
            parent_node.add_child(node)

        elif tag == 'p':
            node = ParagraphNode()
            parent_node.add_child(node)

            # Add text content
            if elem.text:
                text_node = TextNode(content=elem.text.strip())
                node.add_child(text_node)

            # Process children
            for child in elem:
                self._build_node_tree(child, node)

                # Add tail text
                if child.tail:
                    text_node = TextNode(content=child.tail.strip())
                    node.add_child(text_node)

        elif tag == 'table':
            node = self._build_table(elem)
            if node:
                parent_node.add_child(node)

        else:
            # Generic container
            node = ContainerNode(tag_name=tag)
            parent_node.add_child(node)

            # Add text
            if elem.text:
                text_node = TextNode(content=elem.text.strip())
                node.add_child(text_node)

            # Process children
            for child in elem:
                self._build_node_tree(child, node)

                # Add tail text
                if child.tail:
                    text_node = TextNode(content=child.tail.strip())
                    node.add_child(text_node)

    def _build_table(self, elem):
        """Build table node from element."""
        table = TableNode()

        # Get caption
        caption_elem = elem.find('.//caption')
        if caption_elem is not None:
            table.caption = self._get_text_content(caption_elem)

        # Process rows
        for tr in elem.findall('.//tr'):
            cells = []
            is_header = False

            # Process cells
            for td in tr:
                if td.tag in ['td', 'th']:
                    text = self._get_text_content(td)
                    cell = Cell(content=text, is_header=(td.tag == 'th'))
                    cells.append(cell)
                    if td.tag == 'th':
                        is_header = True

            if cells:
                row = Row(cells=cells, is_header=is_header)
                if is_header:
                    table.headers.append(cells)
                else:
                    table.rows.append(row)

        return table if (table.headers or table.rows) else None

    def _get_text_content(self, elem):
        """Get text content from element."""
        return ''.join(elem.itertext()).strip()


def parse_html_simple(html: str) -> Document:
    """Simple HTML parsing for testing."""
    parser = SimpleHTMLParser()
    return parser.parse(html)
