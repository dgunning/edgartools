import re
from typing import Dict, List, Optional, Tuple

from edgar.files.html import BaseNode, Document
from edgar.files.tables import ProcessedTable, TableProcessor

__all__ = ['to_markdown', 'MarkdownRenderer']


class MarkdownRenderer:
    def __init__(self, document: Document, start_page_number: int = 0):
        self.document = document
        self.start_page_number = start_page_number
        self.toc_entries: List[Tuple[int, str, str]] = []  # level, text, anchor
        self.reference_links: Dict[str, str] = {}
        self.current_section = ""

    def render(self) -> str:
        """Render complete document"""
        rendered_parts = []

        for node in self.document.nodes:
            rendered = ""
            if node.type == 'text_block':  # Changed from 'paragraph'
                rendered = self._render_text_block(node)
            elif node.type == 'table':
                processed_table = TableProcessor.process_table(node)
                rendered = self._render_table(processed_table) if processed_table else ""
            elif node.type == 'heading':
                rendered = self._render_heading(node)
            elif node.type == 'page_break':
                rendered = self._render_page_break(node)

            if rendered:
                rendered_parts.append(rendered.rstrip())  # Remove trailing whitespace

        # Join with single newline and clean up multiple newlines
        return self._clean_spacing('\n\n'.join(filter(None, rendered_parts)))

    def _clean_spacing(self, text: str) -> str:
        """Clean up spacing while maintaining valid markdown"""
        # Replace 3 or more newlines with 2 newlines
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Fix header spacing by treating the header line as a complete unit
        text = re.sub(r'\n*(#{1,6} [^\n]*[A-Za-z0-9][^\n]*)\n*', r'\n\n\1\n', text)

        # Clean up spacing around paragraphs
        text = re.sub(r'\n{2,}(?=\S)', '\n\n', text)

        text = re.sub("\xa0", " ", text)

        # Trim leading/trailing whitespace
        return text.strip()

    def _render_header(self) -> str:
        """Render SEC filing header with metadata"""
        header_parts = []

        # Try to find filing type and registration number
        for node in self.document.nodes[:5]:  # Check first few nodes
            if node.type == 'text_block':  # Changed from 'paragraph'
                text = node.content
                if 'registration no.' in text.lower():
                    header_parts.append(f"**Registration No.:** {text.split('.')[-1].strip()}")
                if 'filed pursuant to' in text.lower():
                    header_parts.append(f"**Filing Type:** {text.strip()}")

        return "\n".join(header_parts) if header_parts else ""

    def _render_heading(self, node: BaseNode) -> str:
        """Render heading with metadata support"""
        if node.type != 'heading':
            raise ValueError(f"Expected heading node, got {node.type}")

        prefix = '#' * node.level
        text = node.content

        # Check metadata for any special rendering instructions
        if node.get_metadata('render_style') == 'centered':
            return f"{prefix} <div align='center'>{text}</div>"

        return f"{prefix} {text}"

    def _render_text_block(self, node: BaseNode) -> str:
        """Render text block (formerly paragraph) with metadata support"""
        if node.type != 'text_block':
            raise ValueError(f"Expected text_block node, got {node.type}")

        text = node.content

        # Apply styling
        if node.style:
            if node.style.font_weight == 'bold':
                text = f"**{text}**"
            if node.style.text_align == 'center':
                text = f"<div align='center'>{text}</div>"

        # Check metadata for special handling
        if node.get_metadata('is_note', False):
            text = f"> Note: {text}"
        elif node.get_metadata('is_quote', False):
            text = f"> {text}"

        return text

    def _render_table(self, processed: ProcessedTable) -> str:
        """Render processed table as Markdown"""
        if not processed.data_rows:
            return ""

        # Calculate column widths
        col_widths = []
        for col_idx in range(len(processed.data_rows[0])):
            # Consider headers in width calculation
            col_content = []
            if processed.headers:
                col_content.append(processed.headers[col_idx])
            col_content.extend(row[col_idx] for row in processed.data_rows)

            # Calculate max width, considering multiline content and handling empty columns
            widths = []
            for cell in col_content:
                if cell.strip():  # Only consider non-empty cells
                    widths.extend(len(line) for line in cell.split('\n'))

            # Default to minimum width of 3 if column is empty
            max_width = max(widths) if widths else 3
            col_widths.append(max_width)

        # Build table lines
        lines = []

        # Add headers if present
        if processed.headers:
            header_lines = []
            for col_idx, header in enumerate(processed.headers):
                header_lines.append(self._format_markdown_cell(
                    header, col_widths[col_idx], processed.column_alignments[col_idx]))
            lines.append('|' + '|'.join(header_lines) + '|')

            # Add separator line
            separators = []
            for idx, width in enumerate(col_widths):
                align = processed.column_alignments[idx]
                if align == "left":
                    sep = ':' + '-' * (width + 1)
                else:  # right
                    sep = '-' * (width + 1) + ':'
                separators.append(sep)
            lines.append('|' + '|'.join(separators) + '|')

        # Add data rows
        for row in processed.data_rows:
            row_cells = []
            for col_idx, cell in enumerate(row):
                row_cells.append(self._format_markdown_cell(
                    cell, col_widths[col_idx], processed.column_alignments[col_idx]))
            lines.append('|' + '|'.join(row_cells) + '|')

        return '\n'.join(lines)

    def _format_markdown_cell(self, content: str, width: int, alignment: str) -> str:
        """Format cell content for markdown table"""
        if not content.strip():
            return ' ' * (width + 2)  # Add padding

        lines = content.split('\n')
        formatted_lines = []
        for line in lines:
            if alignment == "left":
                formatted_lines.append(f" {line:<{width}} ")
            else:  # right
                formatted_lines.append(f" {line:>{width}} ")

        return '\n'.join(formatted_lines)

    def _render_page_break(self, node: BaseNode) -> str:
        """Render page break as delimiter"""
        adjusted_page_number = node.page_number + self.start_page_number
        return f"{{{adjusted_page_number}}}------------------------------------------------"


def to_markdown(html_content: str, include_page_breaks: bool = False, start_page_number: int = 0) -> Optional[str]:
    """Convert HTML content to markdown with optional page breaks

    Args:
        html_content: HTML string to convert
        include_page_breaks: Whether to include page break markers
        start_page_number: Starting page number for page break markers (default: 0)

    Returns:
        Markdown string or None if parsing failed
    """
    document = Document.parse(html_content, include_page_breaks=include_page_breaks)
    if document:
        return document.to_markdown(start_page_number=start_page_number)
    return None
