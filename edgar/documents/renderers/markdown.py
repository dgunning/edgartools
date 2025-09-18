"""
Markdown renderer for parsed documents.
"""

from typing import Dict, List, Optional, Set

from edgar.documents.document import Document
from edgar.documents.nodes import HeadingNode, ListItemNode, ListNode, Node, ParagraphNode, TextNode
from edgar.documents.table_nodes import TableNode


class MarkdownRenderer:
    """
    Renders parsed documents to Markdown format.

    Features:
    - Preserves document structure
    - Handles tables with proper formatting
    - Supports nested lists
    - Includes metadata annotations
    - Configurable output options
    """

    def __init__(self,
                 include_metadata: bool = False,
                 include_toc: bool = False,
                 max_heading_level: int = 6,
                 table_format: str = 'pipe',
                 wrap_width: Optional[int] = None):
        """
        Initialize markdown renderer.

        Args:
            include_metadata: Include metadata annotations
            include_toc: Generate table of contents
            max_heading_level: Maximum heading level to render
            table_format: Table format ('pipe', 'grid', 'simple')
            wrap_width: Wrap text at specified width
        """
        self.include_metadata = include_metadata
        self.include_toc = include_toc
        self.max_heading_level = max_heading_level
        self.table_format = table_format
        self.wrap_width = wrap_width

        # Track state during rendering
        self._toc_entries: List[tuple] = []
        self._rendered_ids: Set[str] = set()
        self._list_depth = 0
        self._in_table = False

    def render(self, document: Document) -> str:
        """
        Render document to Markdown.

        Args:
            document: Document to render

        Returns:
            Markdown formatted text
        """
        self._reset_state()

        parts = []

        # Add metadata header if requested
        if self.include_metadata:
            parts.append(self._render_metadata(document))
            parts.append("")

        # Placeholder for TOC
        if self.include_toc:
            toc_placeholder = "<!-- TOC -->"
            parts.append(toc_placeholder)
            parts.append("")

        # Render document content
        content = self._render_node(document.root)
        parts.append(content)

        # Join parts
        markdown = "\n".join(parts)

        # Replace TOC placeholder
        if self.include_toc and self._toc_entries:
            toc = self._generate_toc()
            markdown = markdown.replace(toc_placeholder, toc)

        return markdown.strip()

    def render_node(self, node: Node) -> str:
        """
        Render a specific node to Markdown.

        Args:
            node: Node to render

        Returns:
            Markdown formatted text
        """
        self._reset_state()
        return self._render_node(node)

    def _reset_state(self):
        """Reset renderer state."""
        self._toc_entries = []
        self._rendered_ids = set()
        self._list_depth = 0
        self._in_table = False

    def _render_node(self, node: Node) -> str:
        """Render a node and its children."""
        # Skip if already rendered (handles shared nodes)
        if node.id in self._rendered_ids:
            return ""
        self._rendered_ids.add(node.id)

        # Dispatch based on node type
        if isinstance(node, HeadingNode):
            return self._render_heading(node)
        elif isinstance(node, ParagraphNode):
            return self._render_paragraph(node)
        elif isinstance(node, TextNode):
            return self._render_text(node)
        elif isinstance(node, TableNode):
            return self._render_table(node)
        elif isinstance(node, ListNode):
            return self._render_list(node)
        elif isinstance(node, ListItemNode):
            return self._render_list_item(node)
        else:
            # Default: render children
            return self._render_children(node)

    def _render_heading(self, node: HeadingNode) -> str:
        """Render heading node."""
        # Limit heading level
        level = min(node.level, self.max_heading_level)

        # Get heading text
        text = node.text().strip()
        if not text:
            return ""

        # Add to TOC
        if self.include_toc:
            self._toc_entries.append((level, text, node.id))

        # Create markdown heading
        markdown = "#" * level + " " + text

        # Add metadata if requested
        if self.include_metadata and node.metadata:
            metadata = self._format_metadata(node.metadata)
            if metadata:
                markdown += f" <!-- {metadata} -->"

        # Add children content
        children_content = self._render_children(node)
        if children_content:
            markdown += "\n\n" + children_content

        return markdown

    def _render_paragraph(self, node: ParagraphNode) -> str:
        """Render paragraph node."""
        # Get paragraph content
        content = self._render_children(node).strip()
        if not content:
            return ""

        # Wrap if requested
        if self.wrap_width:
            content = self._wrap_text(content, self.wrap_width)

        # Add metadata if requested
        if self.include_metadata and node.metadata:
            metadata = self._format_metadata(node.metadata)
            if metadata:
                content = f"<!-- {metadata} -->\n{content}"

        return content

    def _render_text(self, node: TextNode) -> str:
        """Render text node."""
        text = node.text()

        # Escape markdown special characters
        text = self._escape_markdown(text)

        # Apply text formatting based on style
        if node.style:
            if node.style.font_weight in ['bold', '700', '800', '900']:
                text = f"**{text}**"
            elif node.style.font_style == 'italic':
                text = f"*{text}*"
            elif node.style.text_decoration == 'underline':
                text = f"<u>{text}</u>"

        return text

    def _render_table(self, node: TableNode) -> str:
        """Render table node."""
        self._in_table = True

        parts = []

        # Add caption if present
        if node.caption:
            parts.append(f"**Table: {node.caption}**")
            parts.append("")

        # Render based on format
        if self.table_format == 'pipe':
            table_md = self._render_table_pipe(node)
        elif self.table_format == 'grid':
            table_md = self._render_table_grid(node)
        else:  # simple
            table_md = self._render_table_simple(node)

        parts.append(table_md)

        # Add metadata if requested
        if self.include_metadata and node.metadata:
            metadata = self._format_metadata(node.metadata)
            if metadata:
                parts.append(f"<!-- Table metadata: {metadata} -->")

        self._in_table = False

        return "\n".join(parts)

    def _render_table_pipe(self, node: TableNode) -> str:
        """Render table in pipe format."""
        rows = []

        # Render headers
        if node.headers:
            for header_row in node.headers:
                cells = [cell.text() for cell in header_row]
                row_md = "| " + " | ".join(cells) + " |"
                rows.append(row_md)

            # Add separator after headers
            if node.headers[0]:
                separator = "|"
                for _ in node.headers[0]:
                    separator += " --- |"
                rows.append(separator)

        # Render data rows
        for row in node.rows:
            cells = [cell.text() for cell in row.cells]
            row_md = "| " + " | ".join(cells) + " |"
            rows.append(row_md)

        return "\n".join(rows)

    def _render_table_grid(self, node: TableNode) -> str:
        """Render table in grid format."""
        # Simplified grid format
        all_rows = []

        # Add headers
        if node.headers:
            for header_row in node.headers:
                cells = [cell.text() for cell in header_row]
                all_rows.append(" | ".join(cells))

        # Add data rows
        for row in node.rows:
            cells = [cell.text() for cell in row.cells]
            all_rows.append(" | ".join(cells))

        if all_rows:
            # Add borders
            max_width = max(len(row) for row in all_rows)
            border = "+" + "-" * (max_width + 2) + "+"
            result = [border]
            for row in all_rows:
                result.append(f"| {row:<{max_width}} |")
            result.append(border)
            return "\n".join(result)

        return ""

    def _render_table_simple(self, node: TableNode) -> str:
        """Render table in simple format."""
        rows = []

        # Add headers
        if node.headers:
            for header_row in node.headers:
                cells = [cell.text() for cell in header_row]
                rows.append("  ".join(cells))

        # Add separator if we have headers
        if node.headers and node.rows:
            rows.append("")

        # Add data rows
        for row in node.rows:
            cells = [cell.text() for cell in row.cells]
            rows.append("  ".join(cells))

        return "\n".join(rows)

    def _render_list(self, node: ListNode) -> str:
        """Render list node."""
        self._list_depth += 1

        items = []
        for child in node.children:
            if isinstance(child, ListItemNode):
                item_md = self._render_list_item(child)
                if item_md:
                    items.append(item_md)

        self._list_depth -= 1

        return "\n".join(items)

    def _render_list_item(self, node: ListItemNode) -> str:
        """Render list item node."""
        # Determine bullet/number
        if node.parent and hasattr(node.parent, 'ordered') and node.parent.ordered:
            # Ordered list
            index = node.parent.children.index(node) + 1
            marker = f"{index}."
        else:
            # Unordered list
            markers = ['*', '-', '+']
            marker = markers[(self._list_depth - 1) % len(markers)]

        # Indentation
        indent = "  " * (self._list_depth - 1)

        # Get content
        content = self._render_children(node).strip()

        # Format item
        if '\n' in content:
            # Multi-line content
            lines = content.split('\n')
            result = indent + marker + " " + lines[0]
            for line in lines[1:]:
                result += "\n" + indent + "  " + line
            return result
        else:
            # Single line
            return indent + marker + " " + content

    def _render_children(self, node: Node) -> str:
        """Render all children of a node."""
        parts = []

        for child in node.children:
            child_md = self._render_node(child)
            if child_md:
                parts.append(child_md)

        # Join with appropriate separator
        if self._in_table:
            return " ".join(parts)
        elif any(isinstance(child, (HeadingNode, ParagraphNode, TableNode, ListNode)) 
                for child in node.children):
            return "\n\n".join(parts)
        else:
            return " ".join(parts)

    def _render_metadata(self, document: Document) -> str:
        """Render document metadata."""
        lines = ["---"]

        if document.metadata.company:
            lines.append(f"company: {document.metadata.company}")
        if document.metadata.filing_type:
            lines.append(f"filing_type: {document.metadata.filing_type}")
        if document.metadata.filing_date:
            lines.append(f"filing_date: {document.metadata.filing_date}")
        if document.metadata.cik:
            lines.append(f"cik: {document.metadata.cik}")
        if document.metadata.accession_number:
            lines.append(f"accession_number: {document.metadata.accession_number}")

        lines.append("---")

        return "\n".join(lines)

    def _generate_toc(self) -> str:
        """Generate table of contents."""
        lines = ["## Table of Contents", ""]

        for level, text, _node_id in self._toc_entries:
            # Create anchor link
            anchor = self._create_anchor(text)

            # Indentation based on level
            indent = "  " * (level - 1)

            # Add TOC entry
            lines.append(f"{indent}- [{text}](#{anchor})")

        return "\n".join(lines)

    def _create_anchor(self, text: str) -> str:
        """Create anchor from heading text."""
        # Convert to lowercase and replace spaces with hyphens
        anchor = text.lower()
        anchor = anchor.replace(' ', '-')

        # Remove special characters
        import re
        anchor = re.sub(r'[^a-z0-9\-]', '', anchor)

        # Remove multiple hyphens
        anchor = re.sub(r'-+', '-', anchor)

        return anchor.strip('-')

    def _format_metadata(self, metadata: Dict) -> str:
        """Format metadata for display."""
        parts = []

        for key, value in metadata.items():
            if key == 'semantic_type':
                parts.append(f"type:{value}")
            elif key == 'section':
                parts.append(f"section:{value}")
            elif key == 'ix_tag':
                parts.append(f"xbrl:{value}")
            else:
                parts.append(f"{key}:{value}")

        return " ".join(parts)

    def _escape_markdown(self, text: str) -> str:
        """Escape markdown special characters."""
        # Don't escape in tables
        if self._in_table:
            return text

        # Escape special characters
        for char in ['\\', '`', '*', '_', '{', '}', '[', ']', '(', ')', '#', '+', '-', '.', '!']:
            text = text.replace(char, '\\' + char)

        return text

    def _wrap_text(self, text: str, width: int) -> str:
        """Wrap text at specified width."""
        import textwrap
        return textwrap.fill(text, width=width, break_long_words=False)
