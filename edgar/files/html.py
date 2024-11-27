import re
from dataclasses import dataclass
from typing import List, Dict
from typing import Optional, Union, Any, Literal

from bs4 import Tag, NavigableString
from rich import box
from rich.align import Align
from rich.console import Group, RenderResult
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.files.html_documents import HtmlDocument, clean_html_root
from edgar.richtools import repr_rich

__all__ = ['SECHTMLParser', 'Document', 'DocumentNode', 'StyleInfo']



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

    @property
    def virtual_columns(self):
        return sum(cell.colspan for cell in self.cells)


# 1. Add type literals and type guards
NodeType = Literal['heading', 'paragraph', 'table']
ContentType = Union[str, Dict[str, Any], List[TableRow]]

def is_table_content(content: ContentType) -> bool:
    return isinstance(content, list) and all(isinstance(x, TableRow) for x in content)

def is_text_content(content: ContentType) -> bool:
    return isinstance(content, str)

def is_dict_content(content: ContentType) -> bool:
    return isinstance(content, dict)

@dataclass
class DocumentNode:
    type: NodeType
    content: Union[str, Dict[str, Any], List[TableRow]]  # Modified to handle structured table data
    style: StyleInfo
    level: int = 0

    def _validate_content(self) -> None:
        """Validate content matches the node type"""
        if self.type == 'table' and not is_table_content(self.content):
            raise ValueError(f"Table node must have List[TableRow] content, got {type(self.content)}")
        elif self.type in ('heading', 'paragraph') and not is_text_content(self.content):
            raise ValueError(f"{self.type} node must have string content, got {type(self.content)}")

    @property
    def text(self) -> str:
        """Helper method for accessing text content"""
        if not is_text_content(self.content):
            raise ValueError(f"Cannot get text from {self.type} node")
        return self.content

    @property
    def rows(self) -> List[TableRow]:
        """Helper method for accessing table rows"""
        if not is_table_content(self.content):
            raise ValueError(f"Cannot get rows from {self.type} node")
        return self.content



@dataclass
class Document:
    nodes: List[DocumentNode]

    def __len__(self):
        return len(self.nodes)

    def __getitem__(self, index):
        return self.nodes[index]

    @property
    def tables(self) -> List[DocumentNode]:
        """Get all table nodes in the document"""
        return [node for node in self.nodes if node.type == 'table']

    @classmethod
    def parse(cls, html:str) -> 'Document':
        parser = SECHTMLParser(html)
        return parser.parse()

    def to_markdown(self) -> str:
        from edgar.files.markdown import MarkdownRenderer
        return MarkdownRenderer(self).render()

    def __rich__(self) -> RenderResult:
        """Rich console protocol for rendering document"""
        renderable_elements = []

        for node in self.nodes:
            if node.type == 'heading':
                element = self._render_heading(node)
            elif node.type == 'paragraph':
                element = self._render_paragraph(node)
            elif node.type == 'table':
                element = self._render_table(node)
            else:
                # Fallback for unknown types
                element = Text(str(node.content))

            if element:
                renderable_elements.append(element)

        return Group(*renderable_elements)


    def _render_heading(self, node: DocumentNode) -> Panel:
        """Render heading with appropriate level styling"""
        # Style based on heading level
        styles = {
            1: ("bold cyan", 'SIMPLE'),
            2: ("bold blue", 'SIMPLE'),
            3: ("bold", 'SIMPLE'),
            4: ("dim bold", 'SIMPLE')
        }

        style, box_style = styles.get(node.level, ("", "single"))

        text = Text(node.content.strip(), style=style)

        # Center if specified in style
        if node.style and node.style.text_align == 'center':
            text = Align.center(text)

        return Panel(
            text,
            box=box.SIMPLE,
            padding=(0, 2),
            expand=True
        )

    def _render_paragraph(self, node: DocumentNode) -> Text:
        """Render paragraph with styling"""
        text = Text(node.content.strip())

        # Apply styling based on StyleInfo
        if node.style:
            if node.style.font_weight == 'bold':
                text.stylize("bold")

            # Handle text alignment
            if node.style.text_align == 'center':
                return Text(node.content.strip(), justify='center')
            elif node.style.text_align == 'right':
                return Text(node.content.strip(), justify='right')

        return text

    def _render_table(self, node: DocumentNode) -> Optional[Table]:
        """Render node as Rich table"""
        from edgar.files.tables import TableProcessor
        processed_table = TableProcessor.process_table(node)
        if not processed_table:
            return None
        table = Table(
            box=box.SIMPLE,
            border_style="blue",
            padding=(0, 1),
            show_header=bool(processed_table.headers),
            row_styles=["", "dim"],
            collapse_padding=True,
            width=None
        )

        # Add columns
        for col_idx, alignment in enumerate(processed_table.column_alignments):
            table.add_column(
                header=processed_table.headers[col_idx] if processed_table.headers else None,
                justify=alignment,
                vertical="middle"
            )

        # Add data rows
        for row in processed_table.data_rows:
            table.add_row(*row)

        return table

    def __repr__(self):
        return repr_rich(self)




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
        # Handle ix: tags by getting their content
        if element.name.startswith('ix:'):
            for child in element.children:
                if isinstance(child, Tag):
                    return self._process_element(child)
            text = self._get_text_with_spacing(element)
            if text:
                return DocumentNode(
                    type='paragraph',
                    content=text,
                    style=self.parse_style(element.get('style', ''))
                )

        # Process specific element types
        if element.name == 'table':
            return self._process_table(element)
        elif element.name == 'div':
            return self._process_div(element, self.parse_style(element.get('style', '')))
        elif element.name == 'p':
            return self._process_paragraph(element)

        # Process other elements
        nodes = []
        for child in element.children:
            if isinstance(child, Tag):
                child_result = self._process_element(child)
                if child_result:
                    if isinstance(child_result, list):
                        nodes.extend(child_result)
                    else:
                        nodes.append(child_result)

        return nodes[0] if len(nodes) == 1 else nodes if nodes else None

    def _process_paragraph(self, element: Tag) -> Optional[DocumentNode]:
        """Process a paragraph element into a single text node"""
        text_parts = []

        for child in element.children:
            if isinstance(child, NavigableString):
                text = str(child)  # Don't strip individual NavigableStrings
                if text:
                    text_parts.append(text)
            elif isinstance(child, Tag):
                if child.name == 'br':
                    text_parts.append('\n')
                elif child.name in ['span', 'strong', 'em', 'b', 'i', 'a']:
                    # Handle inline elements
                    inline_text = child.get_text()  # Don't strip inline text
                    if inline_text:
                        text_parts.append(inline_text)
                # We'll ignore any div elements since they shouldn't be in paragraphs

        if not text_parts:
            return None

        # Join all parts and then normalize whitespace at the end
        combined_text = ''.join(text_parts)
        # Replace multiple spaces with single space and strip at the end
        normalized_text = ' '.join(combined_text.split())

        return DocumentNode(
            type='paragraph',
            content=normalized_text,
            style=self.parse_style(element.get('style', ''))
        )


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
        # First check for ix: tags and handle their content
        ix_elements = element.find_all(lambda tag: tag.name.startswith('ix:'), recursive=False)
        if ix_elements:
            child_nodes = []
            for ix_elem in ix_elements:
                # Look for tables within the ix tag
                tables = ix_elem.find_all('table', recursive=True)
                if tables:
                    for table in tables:
                        table_node = self._process_table(table)
                        if table_node:
                            child_nodes.append(table_node)
                else:
                    # If no tables, process normally
                    result = self._process_element(ix_elem)
                    if result:
                        if isinstance(result, list):
                            child_nodes.extend(result)
                        else:
                            child_nodes.append(result)
            return child_nodes if len(child_nodes) > 1 else child_nodes[0] if child_nodes else None

        # Check if this div should be a heading (modified to avoid catching tables)
        if self._is_heading(element, style) and not element.find('table', recursive=True):
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
                        table_node = self._process_table(child)
                        if table_node:
                            child_nodes.append(table_node)
                    elif child.name.startswith('ix:'):
                        # Process ix: tags
                        ix_result = self._process_element(child)
                        if ix_result:
                            if isinstance(ix_result, list):
                                child_nodes.extend(ix_result)
                            else:
                                child_nodes.append(ix_result)
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

    def _process_table(self, element: Tag) -> Optional[DocumentNode]:
        """Process table using virtual columns from row colspans and correct value positioning"""
        if not element:
            return None

        def process_cell(cell: Tag) -> List[TableCell]:
            """Process cell preserving exact colspan and positioning values correctly"""
            colspan = int(cell.get('colspan', '1'))

            def extract_cell_text(cell: Tag) -> str:
                # If cell has div children
                divs = cell.find_all('div', recursive=False)
                if divs:
                    # Join text from each div with newlines
                    return '\n'.join(div.get_text(strip=True) for div in divs)

                # Handle <br/> tags by replacing them with newlines
                # Convert <br/> to newlines first
                for br in cell.find_all('br'):
                    br.replace_with('\n')

                # If no divs, get regular text
                return cell.get_text(strip=False).strip()

            text = extract_cell_text(cell)

            style = self.parse_style(cell.get('style', ''))

            # If this is a right-aligned cell with colspan > 1 (like percentage values)
            if style.text_align == 'right' and colspan > 1:
                # Create empty cells for all but last column of colspan
                cells = [
                    TableCell(content='', colspan=1, align='right', is_currency=False)
                    for _ in range(colspan - 1)
                ]
                # Add actual value in last column
                cells.append(TableCell(
                    content=text.strip(),  # Remove any trailing spaces
                    colspan=1,
                    align='right',
                    is_currency=False
                ))
                return cells

            # For single cells (including $ symbols and % symbols)
            return [TableCell(
                content=text.strip(),
                colspan=colspan,
                align=style.text_align or 'left',
                is_currency=text.startswith('$')
            )]

        def process_row(row: Tag) -> TableRow:
            """Process row preserving cell structure"""
            cells = []
            for td in row.find_all(['td', 'th']):
                cells.extend(process_cell(td))

            return TableRow(cells=cells, is_header=row.find_parent('thead') is not None)

        # Process all rows
        rows = []
        for tr in element.find_all('tr'):
            row = process_row(tr)
            if row.cells:
                rows.append(row)

        return DocumentNode(
            type='table',
            content=rows,
            style=self.parse_style(element.get('style', ''))
        )


    def _similar_styles(self, style1: StyleInfo, style2: StyleInfo) -> bool:
        # Compare relevant style attributes to determine if they're similar
        return (
                style1.font_size == style2.font_size and
                style1.font_weight == style2.font_weight and
                style1.text_align == style2.text_align
        )




