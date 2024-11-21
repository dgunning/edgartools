import re
from dataclasses import dataclass
from io import StringIO
from typing import List, Optional, Union, Tuple, Dict, Any

from bs4 import Tag, NavigableString
from rich.console import Console
from rich.markdown import Markdown

from edgar.documents import HtmlDocument, clean_html_root

__all__ = ['SECHTMLParser', 'Document', 'DocumentNode', 'StyleInfo', 'MarkdownRenderer', 'to_markdown']


@dataclass
class StyleInfo:
    display: Optional[str] = None
    margin_top: Optional[float] = None
    margin_bottom: Optional[float] = None
    font_size: Optional[float] = None
    font_weight: Optional[str] = None
    text_align: Optional[str] = None
    line_height: Optional[float] = None
    width: Optional[float] = None
    text_decoration: Optional[str] = None


@dataclass
class TableCell:
    content: str
    colspan: int = 1
    rowspan: int = 1
    align: str = 'left'
    is_currency: bool = False


@dataclass
class TableRow:
    cells: List[TableCell]
    is_header: bool = False


@dataclass
class DocumentNode:
    type: str
    content: Union[str, Dict[str, Any], List[TableRow]]  # Modified to handle structured table data
    style: StyleInfo
    level: int = 0


@dataclass
class Document:
    nodes: List[DocumentNode]


class SECHTMLParser:
    def __init__(self, html_content: str, extract_data: bool = True):
        root = HtmlDocument.get_root(html_content)
        self.data = HtmlDocument.extract_data(root) if extract_data else None
        self.root = clean_html_root(root)
        self.base_font_size = 10.0  # Default base font size in pt

    def parse(self) -> Document:
        body = self.root.find('body')
        if not body:
            raise ValueError("No body tag found in HTML")

        nodes = self._parse_element(body)
        return Document(nodes=nodes)

    def _parse_element(self, element: Tag) -> List[DocumentNode]:
        nodes = []

        for child in element.children:
            if not isinstance(child, Tag):
                continue

            node = self._process_element(child)
            if node:
                nodes.extend(node if isinstance(node, list) else [node])

        return self._merge_adjacent_nodes(nodes)

    def parse_style(self, style_str: str) -> StyleInfo:
        """Parse inline CSS style string into StyleInfo object"""
        style = StyleInfo()
        if not style_str:
            return style

        # Split style string into individual properties
        properties = [p.strip() for p in style_str.split(';') if p.strip()]
        for prop in properties:
            if ':' not in prop:
                continue

            key, value = prop.split(':', 1)
            key = key.strip().lower()
            value = value.strip().lower()

            # Parse different style properties
            if key == 'display':
                style.display = value
            elif key == 'margin-top':
                style.margin_top = self._parse_unit(value)
            elif key == 'margin-bottom':
                style.margin_bottom = self._parse_unit(value)
            elif key == 'font-size':
                style.font_size = self._parse_unit(value)
            elif key == 'font-weight':
                style.font_weight = value
            elif key == 'text-align':
                style.text_align = value
            elif key == 'line-height':
                style.line_height = self._parse_unit(value)
            elif key == 'width':
                style.width = self._parse_unit(value)
            elif key == 'text-decoration':
                style.text_decoration = value

        return style

    def _parse_unit(self, value: str) -> Optional[float]:
        """Parse CSS unit values into float numbers"""
        if not value:
            return None

        # Handle percentage values
        if value.endswith('%'):
            try:
                return float(value[:-1]) / 100.0
            except ValueError:
                return None

        # Extract number and unit
        match = re.match(r'(-?\d*\.?\d+)([a-z]*)', value)
        if not match:
            return None

        number, unit = match.groups()
        try:
            number = float(number)
        except ValueError:
            return None

        # Convert different units to a standard unit (pt)
        unit_conversions = {
            'pt': 1.0,
            'px': 0.75,  # Approximate px to pt conversion
            'em': 12.0,  # Assume 1em = 12pt
            'rem': 12.0,
            'in': 72.0,
            'cm': 28.35,
            'mm': 2.835,
        }

        multiplier = unit_conversions.get(unit, 1.0)
        return number * multiplier

    def _process_link(self, element: Tag, style: StyleInfo) -> DocumentNode:
        """Process <a> tags into document nodes"""
        href = element.get('href', '')
        text = element.get_text(strip=True)

        # Handle internal links (like TOC references)
        if href.startswith('#'):
            return DocumentNode(
                type='internal_link',
                content={'text': text, 'target': href[1:]},
                style=style
            )

        # Handle external links
        return DocumentNode(
            type='link',
            content={'text': text, 'url': href},
            style=style
        )


    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content while preserving meaningful whitespace"""
        # Replace HTML entities
        entities = {
            '&nbsp;': ' ',
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&apos;': "'",
            '&#8202;': ' ',  # hair space
            '&#8203;': ''  # zero-width space
        }

        for entity, replacement in entities.items():
            text = text.replace(entity, replacement)

        # Normalize whitespace while preserving single newlines
        lines = text.splitlines()
        lines = [' '.join(line.split()) for line in lines]
        text = '\n'.join(lines)

        return text

    def _looks_like_header(self, element: Tag, style: StyleInfo) -> bool:
        """Determine if an element looks like it might be a header"""
        # Check if parent has header-like styling
        parent = element.parent
        parent_style = self.parse_style(parent.get('style', '')) if parent else None

        # Characteristics that suggest this is a header
        hints = [
            style.font_size and style.font_size > self.base_font_size,
            style.font_weight in ['bold', '700', '800', '900'],
            style.text_align == 'center',
            bool(element.find_parent('h1')),
            bool(element.find_parent('h2')),
            bool(element.find_parent('h3')),
            parent_style and parent_style.margin_top and parent_style.margin_top > 10
        ]

        # If multiple header characteristics are present, treat as header
        return sum(bool(hint) for hint in hints) >= 2

    def _determine_heading_level(self, style: StyleInfo) -> int:
        """Determine appropriate heading level based on styling"""
        if not style or not style.font_size:
            return 2  # default level

        # Base heading level on font size relative to base
        size_ratio = style.font_size / self.base_font_size

        if size_ratio >= 1.8:
            return 1
        elif size_ratio >= 1.5:
            return 2
        elif size_ratio >= 1.2:
            return 3
        else:
            return 4

    def _process_element(self, element: Tag) -> Optional[Union[DocumentNode, List[DocumentNode]]]:
        """Process an element into one or more document nodes"""
        nodes = []
        current_text = []

        # First, determine if this element itself should be a specific node type
        if element.name == 'table':
            table_node = self._process_table(element, self.parse_style(element.get('style', '')))
            return table_node if table_node else None
        elif element.name == 'div':
            return self._process_div(element, self.parse_style(element.get('style', '')))

        # Process children
        for child in element.children:
            if isinstance(child, NavigableString):
                # Handle text nodes
                text = str(child).strip()
                if text:
                    current_text.append(text)
            elif isinstance(child, Tag):
                # If we have accumulated text, create a paragraph node
                if current_text:
                    nodes.append(DocumentNode(
                        type='paragraph',
                        content=' '.join(current_text),
                        style=self.parse_style(element.get('style', ''))
                    ))
                    current_text = []

                # Process the child element
                if child.name == 'table':
                    table_node = self._process_table(child, self.parse_style(child.get('style', '')))
                    if table_node:
                        nodes.append(table_node)
                elif child.name == 'br':
                    current_text.append('\n')
                else:
                    # Recursively process other elements
                    child_result = self._process_element(child)
                    if child_result:
                        if isinstance(child_result, list):
                            nodes.extend(child_result)
                        else:
                            nodes.append(child_result)

        # Handle any remaining text
        if current_text:
            nodes.append(DocumentNode(
                type='paragraph',
                content=' '.join(current_text),
                style=self.parse_style(element.get('style', ''))
            ))

        # If we only have one node, return it directly
        if len(nodes) == 1:
            return nodes[0]
        # If we have multiple nodes, return the list
        elif len(nodes) > 1:
            return nodes
        # If we have no nodes, return None
        return None

    def _get_text_with_spacing(self, element: Tag) -> str:
        """Extract text while preserving meaningful whitespace"""
        # Don't process tables in text extraction
        if element.name == 'table':
            return ''

        style = self.parse_style(element.get('style', ''))
        is_inline = (
                style.display == 'inline' or
                element.name in ['span', 'strong', 'em', 'b', 'i', 'a']
                or element.name.startswith('ix:')
        )

        parts = []
        for child in element.children:
            if isinstance(child, NavigableString):
                parts.append(str(child))
            elif child.name == 'br':
                parts.append('\n')
            elif child.name == 'table':
                continue  # Skip tables in text extraction
            elif child.name in ['p', 'div']:
                child_style = self.parse_style(child.get('style', ''))
                child_is_inline = child_style.display == 'inline'

                text = self._get_text_with_spacing(child)
                if text.strip():
                    if child_is_inline:
                        parts.append(text)
                    else:
                        parts.append(f'\n{text}\n')
            else:
                parts.append(self._get_text_with_spacing(child))

        text = ''.join(parts)
        return text if is_inline else text


    def _merge_adjacent_nodes(self, nodes: List[DocumentNode]) -> List[DocumentNode]:
        """Merge adjacent nodes while preserving proper spacing"""
        if not nodes:
            return []

        merged = []
        current = None

        for node in nodes:
            if not current:
                current = node
                continue

            # Handle different node combinations
            if (current.type == 'paragraph' and
                    node.type == 'paragraph' and
                    self._similar_styles(current.style, node.style)):
                # Merge paragraphs with appropriate spacing
                current.content = f"{current.content}\n\n{node.content}"
            elif current.type == 'linebreak':
                # Handle explicit line breaks
                if merged:
                    merged[-1].content += '\n'
                else:
                    merged.append(current)
                current = node
            else:
                merged.append(current)
                current = node

        if current:
            merged.append(current)

        return merged


    def _process_div(self, element: Tag, style: StyleInfo) -> Optional[Union[DocumentNode, List[DocumentNode]]]:
        """Process div elements"""
        # Check if this div should be a heading
        if self._is_heading(element, style):
            return DocumentNode(
                type='heading',
                content=element.get_text(strip=True),
                style=style,
                level=self._determine_heading_level(style)
            )

        # Process children
        child_nodes = []
        current_text = []

        # First check for any tables in the subtree
        tables = element.find_all('table', recursive=True)
        if tables:
            # Process the div's content as a series of text and table nodes
            for child in element.children:
                if isinstance(child, NavigableString):
                    text = str(child)
                    if text:
                        current_text.append(text)
                elif isinstance(child, Tag):
                    if child.name == 'table':
                        # Flush any accumulated text before the table
                        if current_text:
                            text = ''.join(current_text)
                            if text.strip():
                                child_nodes.append(DocumentNode(
                                    type='paragraph',
                                    content=text,
                                    style=style
                                ))
                            current_text = []

                        # Process the table
                        table_node = self._process_table(child, self.parse_style(child.get('style', '')))
                        if table_node:
                            child_nodes.append(table_node)
                    else:
                        # Recursively process non-table elements
                        child_result = self._process_element(child)
                        if child_result:
                            if isinstance(child_result, list):
                                child_nodes.extend(child_result)
                            else:
                                child_nodes.append(child_result)
        else:
            # No tables - process normally with _get_text_with_spacing
            text = self._get_text_with_spacing(element)
            if text.strip():
                child_nodes.append(DocumentNode(
                    type='paragraph',
                    content=text,
                    style=style
                ))

        return child_nodes if len(child_nodes) > 1 else child_nodes[0] if child_nodes else None

    def _is_heading(self, element: Tag, style: StyleInfo) -> bool:
        # Heuristics for heading detection
        if not style:
            return False

        # Check font size
        is_larger = (style.font_size or 0) > self.base_font_size

        # Check font weight
        is_bold = style.font_weight in ['bold', '700', '800', '900']

        # Check content length
        text = element.get_text(strip=True)
        is_short = len(text) < 200  # Arbitrary threshold

        # Combined heuristics
        return (is_larger or is_bold) and is_short


    def _get_cell_content(self, cell: Tag) -> str:
        """Extract cell content preserving structure"""
        # Replace <br> with newlines
        for br in cell.find_all('br'):
            br.replace_with('\n')

        # Get text content preserving whitespace
        text = cell.get_text(strip=True)

        # Clean up newlines and spaces while preserving structure
        lines = [line.strip() for line in text.split('\n')]
        return '\n'.join(line for line in lines if line)

    def _process_table(self, element: Tag, style: StyleInfo) -> Optional[DocumentNode]:
        """Process table using explicit cell alignments"""

        def get_cell_alignment(cell: Tag) -> str:
            """Extract text alignment directly from cell style"""
            style_str = cell.get('style', '')
            if 'text-align:right' in style_str:
                return 'right'
            elif 'text-align:center' in style_str:
                return 'center'
            elif 'text-align:left' in style_str:
                return 'left'
            return 'left'  # Default to left if not specified

        def process_cell(cell: Tag) -> TableCell:
            """Process cell preserving explicit alignment"""
            divs = cell.find_all('div')
            if divs:
                # Check if divs have inline style
                texts = []
                for div in divs:
                    style = self.parse_style(div.get('style', ''))
                    text = div.get_text(strip=True)
                    if style.display == 'inline':
                        texts.append(text)
                    else:
                        texts.append(f"\n{text}" if texts else text)
                content = ''.join(texts)
            else:
                content = cell.get_text(strip=True)

            colspan = int(cell.get('colspan', 1))
            align = get_cell_alignment(cell)

            return TableCell(
                content=content,
                colspan=colspan,
                align=align,
                is_currency='$' in content
            )

        def merge_cells(cells: List[TableCell]) -> List[TableCell]:
            """Merge cells preserving explicit alignment"""
            if not cells:
                return []

            merged = []
            current = None

            for cell in cells:
                if not cell.content.strip() and cell.colspan == 1:
                    continue

                if not current:
                    current = cell
                    continue

                # When merging $ with numbers or numbers with %, preserve right alignment
                if current.content.strip() == '$' and cell.align == 'right':
                    current.content = f"${cell.content.strip()}"
                    current.align = 'right'
                    current.colspan += cell.colspan
                    continue
                elif (cell.content.strip() == '%' and
                      current.content.strip().replace(',', '').replace('.', '').isdigit()):
                    current.content = f"{current.content.strip()}%"
                    current.align = 'right'
                    current.colspan += cell.colspan
                    continue

                merged.append(current)
                current = cell

            if current:
                merged.append(current)

            return merged

        def process_row(tr: Tag) -> Optional[TableRow]:
            cells = []
            for td in tr.find_all(['td', 'th']):
                cell = process_cell(td)
                if cell:
                    cells.append(cell)

            if not any(cell.content.strip() for cell in cells):
                return None

            cells = merge_cells(cells)
            is_header = bool(tr.find('th')) or tr.find_parent('thead')
            return TableRow(cells=cells, is_header=is_header) if cells else None

        # Process all rows
        rows = []
        for tr in element.find_all('tr'):
            row = process_row(tr)
            if row and row.cells:
                rows.append(row)

        return DocumentNode(type='table', content=rows, style=style)


    def _similar_styles(self, style1: StyleInfo, style2: StyleInfo) -> bool:
        # Compare relevant style attributes to determine if they're similar
        return (
                style1.font_size == style2.font_size and
                style1.font_weight == style2.font_weight and
                style1.text_align == style2.text_align
        )


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
                rendered = self._render_table(node)
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

        # Ensure proper spacing around headers
        text = re.sub(r'\n*(#{1,6}.*?)\n*', r'\n\n\1\n', text)

        # Clean up spacing around paragraphs
        text = re.sub(r'\n{2,}(?=\S)', '\n\n', text)

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
        if node.type == 'heading':
            return self._render_heading(node)
        elif node.type == 'paragraph':
            return self._render_paragraph(node)
        elif node.type == 'table':
            return self._render_table(node)
        elif node.type == 'list':
            return self._render_list(node)
        else:
            return node.content

    def _render_heading(self, node: DocumentNode) -> str:
        prefix = '#' * node.level
        text = node.content.strip()
        anchor = self._create_anchor(text)

        # Add extra spacing for major sections
        if node.level == 1:
            return f"\n\n{prefix} {text} {{#{anchor}}}\n"
        return f"{prefix} {text} {{#{anchor}}}"

    def _render_paragraph(self, node: DocumentNode) -> str:
        """Render paragraph with minimal spacing"""
        text = node.content.strip()

        # Apply styling
        if node.style:
            if node.style.font_weight == 'bold':
                text = f"**{text}**"
            if node.style.text_align == 'center':
                text = f"<div align='center'>{text}</div>"

        return text

    def _render_table(self, node: DocumentNode) -> str:
        if not isinstance(node.content, list) or not node.content:
            return ''

        rows = node.content

        # Normalize table structure
        normalized_rows = self._normalize_table_structure(rows)

        # Calculate column widths
        col_widths = self._calculate_column_widths(normalized_rows)  # No longer needs virtual_columns

        # Render table
        table_lines = []

        # Render each row
        for i, row in enumerate(normalized_rows):
            line = self._render_table_row(row, col_widths)
            table_lines.append(line)

            # Add separator after header
            if i == 0:
                separator = self._render_separator(col_widths, row)
                table_lines.append(separator)

        return '\n'.join(table_lines)

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

    def _format_financial_numbers(self, text: str) -> str:
        """Format financial numbers with proper separators"""

        def replace_number(match):
            num = float(match.group(0).replace(',', ''))
            if num >= 1_000_000:
                return f"{num / 1_000_000:.2f}M"
            if num >= 1_000:
                return f"{num / 1_000:.2f}K"
            return f"{num:,.2f}"

        return re.sub(r'\d+(?:,\d{3})*(?:\.\d+)?', replace_number, text)

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


