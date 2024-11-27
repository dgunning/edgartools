import re
from io import StringIO
from typing import List, Tuple, Dict

from rich.console import Console
from rich.markdown import Markdown

from edgar.files.html import Document, DocumentNode, TableRow, TableCell, SECHTMLParser
from edgar.files.tables import ProcessedTable, TableProcessor

__all__ = ['to_markdown', 'MarkdownRenderer']

class MarkdownRenderer:
    def __init__(self, document: Document):
        self.document = document
        self.toc_entries: List[Tuple[int, str, str]] = []  # level, text, anchor
        self.reference_links: Dict[str, str] = {}
        self.current_section = ""

    def render(self) -> str:
        """Render complete document"""
        rendered_parts = []

        for node in self.document.nodes:
            rendered = ""
            if node.type == 'paragraph':
                rendered = self._render_paragraph(node)
            elif node.type == 'table':
                processed_table = TableProcessor.process_table(node)
                rendered = self._render_table(processed_table) if processed_table else ""
            elif node.type == 'heading':
                rendered = self._render_heading(node)

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
            if node.type == 'paragraph':
                if 'registration no.' in node.content.lower():
                    header_parts.append(f"**Registration No.:** {node.content.split('.')[-1].strip()}")
                if 'filed pursuant to' in node.content.lower():
                    header_parts.append(f"**Filing Type:** {node.content.strip()}")

        return "\n".join(header_parts) if header_parts else ""

    def _render_toc(self) -> str:
        """Render table of contents"""
        if not self.toc_entries:
            return ""

        toc_lines = ["# Table of Contents\n"]

        for level, text, anchor in self.toc_entries:
            indent = "    " * (level - 1)
            toc_lines.append(f"{indent}- [{text}](#{anchor})")

        return "\n".join(toc_lines)

    def _render_main_content(self) -> str:
        """Render main document content"""
        return "\n\n".join(self._render_node(node) for node in self.document.nodes)

    def _render_node(self, node: DocumentNode) -> str:
        try:
            if node.type == 'heading':
                return self._render_heading(node)
            elif node.type == 'paragraph':
                return self._render_paragraph(node)
            elif node.type == 'table':
                return self._render_table(node)
            else:
                raise ValueError(f"Unknown node type: {node.type}")
        except ValueError as e:
            print(f"Warning: Failed to render node: {e}")
            return ""

    def _render_heading(self, node: DocumentNode) -> str:
        if node.type != 'heading':
            raise ValueError(f"Expected heading node, got {node.type}")
        prefix = '#' * node.level
        text = node.text

        return f"{prefix} {text}"

    def _render_paragraph(self, node: DocumentNode) -> str:
        if node.type != 'paragraph':
            raise ValueError(f"Expected paragraph node, got {node.type}")
        text = node.text

        # Apply styling
        if node.style:
            if node.style.font_weight == 'bold':
                text = f"**{text}**"
            if node.style.text_align == 'center':
                text = f"<div align='center'>{text}</div>"

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
            for header in processed.headers:
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

    def _normalize_table_structure(self, rows: List[TableRow]) -> List[TableRow]:
        """Normalize table structure by analyzing header pattern"""
        if not rows:
            return []

        # Analyze first few rows to determine column structure
        max_cols = 0
        for row in rows[:3]:  # Check first 3 rows
            num_cols = 0
            for cell in row.cells:
                if cell.content.strip() == '$':
                    # Count $ and following number as separate columns
                    num_cols += 2
                else:
                    num_cols += 1
            max_cols = max(max_cols, num_cols)

        normalized = []
        for row in rows:
            normalized_cells = []
            current_cols = 0

            for cell in row.cells:
                if cell.content.strip() == '$':
                    # Keep $ as separate column
                    normalized_cells.append(cell)
                    current_cols += 1
                else:
                    normalized_cells.append(cell)
                    current_cols += 1

            # Pad if needed
            while current_cols < max_cols:
                normalized_cells.append(TableCell(content="", align='left'))
                current_cols += 1

            normalized.append(TableRow(cells=normalized_cells, is_header=row.is_header))

        return normalized

    def _calculate_column_widths(self, rows: List[TableRow]) -> List[int]:
        """Calculate column widths accounting for colspans"""
        if not rows:
            return []

        # Get true number of columns from normalized structure
        virtual_cols = sum(cell.colspan for cell in rows[0].cells)
        widths = [0] * virtual_cols

        for row in rows:
            current_col = 0
            for cell in row.cells:
                # Calculate width needed for this cell
                content_width = len(cell.content)
                if cell.colspan > 1:
                    # Distribute width across spanned columns
                    width_per_col = (content_width + cell.colspan - 1) // cell.colspan
                    for i in range(current_col, current_col + cell.colspan):
                        if i < virtual_cols:
                            widths[i] = max(widths[i], width_per_col)
                else:
                    if current_col < virtual_cols:
                        widths[current_col] = max(widths[current_col], content_width)

                current_col += cell.colspan

        return widths

    def _render_table_row(self, row: TableRow, col_widths: List[int]) -> str:
        """Render a single table row"""
        cells = []
        for cell, width in zip(row.cells, col_widths):
            lines = cell.content.split('\n')
            # Pad each line to match column width
            padded_lines = []
            for line in lines:
                if cell.align == 'right':
                    formatted = f" {line:>{width}} "
                else:
                    formatted = f" {line:<{width}} "
                padded_lines.append(formatted)
            # Join lines with spaces matching column width
            content = ' '.join(padded_lines)
            cells.append(content)

        return '|' + '|'.join(cells) + '|'

    def _render_separator(self, col_widths: List[int], header_row: TableRow) -> str:
        """Render separator row with proper alignment indicators"""
        separators = []
        for cell, width in zip(header_row.cells, col_widths):
            if cell.align == 'right':
                separator = '-' * (width + 1) + ':'
            else:
                separator = ':' + '-' * (width + 1)
            separators.append(separator)
        return '|' + '|'.join(separators) + '|'

    def _render_list(self, node: DocumentNode) -> str:
        if not node.children:
            return ""

        list_items = []
        for child in node.children:
            prefix = '-' if node.style.list_type == 'unordered' else '1.'
            list_items.append(f"{prefix} {child.content}")

        return '\n'.join(list_items)

    def _render_references(self) -> str:
        """Render collected reference links"""
        if not self.reference_links:
            return ""

        ref_lines = ["\n## References\n"]
        for ref_id, url in self.reference_links.items():
            ref_lines.append(f"[{ref_id}]: {url}")

        return '\n'.join(ref_lines)

    def _collect_document_metadata(self, nodes: List[DocumentNode]) -> None:
        """First pass to collect TOC entries and references"""
        for node in nodes:
            if node.type == 'heading':
                anchor = self._create_anchor(node.content)
                self.toc_entries.append((node.level, node.content, anchor))

            # Collect reference links
            if node.type == 'paragraph':
                self._extract_references(node.content)

    def _create_anchor(self, text: str) -> str:
        """Create GitHub-style anchors from heading text"""
        return re.sub(r'[^\w\s-]', '', text.lower()).replace(' ', '-')

    def _extract_references(self, text: str) -> None:
        """Extract reference links from text"""
        ref_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        for match in re.finditer(ref_pattern, text):
            ref_id, url = match.groups()
            self.reference_links[ref_id] = url

    def _is_note_paragraph(self, text: str) -> bool:
        """Detect if paragraph is a note or important statement"""
        note_indicators = [
            'note:', 'important:', 'attention:',
            'see accompanying notes', 'refer to'
        ]
        return any(indicator in text.lower() for indicator in note_indicators)

    def render_to_text(self):
        # Create string buffer console
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)

        # Render markdown
        markdown = Markdown(self.render())
        console.print(markdown)

        return output.getvalue()


def to_markdown(html_content: str) -> str:
    parser = SECHTMLParser(html_content)
    document = parser.parse()
    renderer = MarkdownRenderer(document)
    return renderer.render()
