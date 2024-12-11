import re
from dataclasses import dataclass
from typing import List, Dict
from typing import Optional, Union, Any, Literal

from bs4 import Tag, NavigableString
from prompt_toolkit.contrib.telnet.log import logger
from rich import box
from rich.align import Align
from rich.console import Console, Group, RenderResult
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
import textwrap
from edgar.files.html_documents import HtmlDocument, clean_html_root
from edgar.files.html_documents import DocumentData
from edgar.richtools import repr_rich

__all__ = ['SECHTMLParser', 'Document', 'DocumentNode', 'StyleInfo']



# Define unit types for type checking
UnitType = Literal['pt', 'px', 'in', 'cm', 'mm', '%']



@dataclass
class Width:
    """Represents a width value with its unit"""
    value: float
    unit: UnitType

    def to_chars(self, console_width: int) -> int:
        """Convert width to character count based on console width"""
        # Base conversion rates (at standard 80-char width)
        BASE_CONSOLE_WIDTH = 80  # standard width
        CHARS_PER_INCH = 12.3  # at standard width

        # Scale factor based on actual console width
        scale = console_width / BASE_CONSOLE_WIDTH

        # Convert to inches first
        inches = self._to_inches()

        # Convert to characters, scaling based on console width
        chars = round(inches * CHARS_PER_INCH * scale)

        # Handle percentage
        if self.unit == '%':
            return round(console_width * (self.value / 100))

        return min(chars, console_width)

    def _to_inches(self) -> float:
        """Convert any unit to inches"""
        conversions = {
            'in': 1.0,
            'pt': 1 / 72,  # 72 points per inch
            'px': 1 / 96,  # 96 pixels per inch
            'cm': 0.393701,  # 1 cm = 0.393701 inches
            'mm': 0.0393701,  # 1 mm = 0.0393701 inches
            '%': 1.0  # percentage handled separately in to_chars
        }
        return self.value * conversions[self.unit]


@dataclass
class StyleInfo:
    display: Optional[str] = None
    margin_top: Optional[float] = None
    margin_bottom: Optional[float] = None
    font_size: Optional[float] = None
    font_weight: Optional[str] = None
    text_align: Optional[str] = None
    line_height: Optional[float] = None
    width: Optional[Width] = None # Width in characters
    text_decoration: Optional[str] = None

    def merge(self, parent_style: Optional['StyleInfo']) -> 'StyleInfo':
        """Merge this style with parent style, child properties take precedence"""
        if not parent_style:
            return self

        # Create new style with parent values
        merged = StyleInfo(
            display=parent_style.display,
            margin_top=parent_style.margin_top,
            margin_bottom=parent_style.margin_bottom,
            font_size=parent_style.font_size,
            font_weight=parent_style.font_weight,
            text_align=parent_style.text_align,
            line_height=parent_style.line_height,
            width=parent_style.width,
            text_decoration=parent_style.text_decoration
        )

        # Override with child values where they exist
        if self.display is not None:
            merged.display = self.display
        if self.margin_top is not None:
            merged.margin_top = self.margin_top
        if self.margin_bottom is not None:
            merged.margin_bottom = self.margin_bottom
        if self.font_size is not None:
            merged.font_size = self.font_size
        if self.font_weight is not None:
            merged.font_weight = self.font_weight
        if self.text_align is not None:
            merged.text_align = self.text_align
        if self.line_height is not None:
            merged.line_height = self.line_height
        if self.width is not None:
            merged.width = self.width
        if self.text_decoration is not None:
            merged.text_decoration = self.text_decoration

        return merged

    def get_char_width(self, console_width: int = 80) -> Optional[int]:
        """Get width in characters, respecting console width"""
        if self.width is None:
            return None
        return min(self.width, console_width)


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
NodeType = Literal['heading', 'text_block', 'table']
ContentType = Union[str, Dict[str, Any], List[TableRow]]

def is_table_content(content: ContentType) -> bool:
    return isinstance(content, list) and all(isinstance(x, TableRow) for x in content)

def is_text_content(content: ContentType) -> bool:
    return isinstance(content, str)

def is_dict_content(content: ContentType) -> bool:
    return isinstance(content, dict)

@dataclass
class DocumentNode:
    type: Literal['heading', 'text_block', 'table']  # Changed from 'paragraph' to 'text_block'
    content: Union[str, Dict[str, Any], List[TableRow]]
    style: StyleInfo
    level: int = 0

    def _validate_content(self) -> None:
        """Validate content matches the node type"""
        if self.type == 'table' and not is_table_content(self.content):
            raise ValueError(f"Table node must have List[TableRow] content, got {type(self.content)}")
        elif self.type in ('heading', 'text_block') and not is_text_content(self.content):
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

    def __init__(self, nodes: List[DocumentNode]):
        self.nodes = nodes

    def __len__(self):
        return len(self.nodes)

    def __getitem__(self, index):
        return self.nodes[index]

    @staticmethod
    def _get_width() -> int:
        """Get the width of the console that this document is being rendered into"""
        return Console().width

    @property
    def tables(self) -> List[DocumentNode]:
        """Get all table nodes in the document"""
        return [node for node in self.nodes if node.type == 'table']

    @classmethod
    def parse(cls, html:str) -> Optional['Document']:
        root = HtmlDocument.get_root(html)
        if root:
            parser = SECHTMLParser(root)
            return parser.parse()

    def to_markdown(self) -> str:
        from edgar.files.markdown import MarkdownRenderer
        return MarkdownRenderer(self).render()

    def __rich__(self) -> RenderResult:
        """Rich console protocol for rendering document"""
        console = Console()
        console_width = console.width

        renderable_elements = []
        for node in self.nodes:
            if node.type == 'heading':
                element = self._render_heading(node)
            elif node.type == 'text_block':
                element = self._render_text_block(node, console_width)
            elif node.type == 'table':
                element = self._render_table(node)
            else:
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

    def _render_text_block(self, node: DocumentNode, console_width: int) -> Text:
        """Render text block with improved line wrapping to avoid orphaned words"""
        if not node.content:
            return Text("")

        # Calculate width
        width = console_width
        if node.style and node.style.width:
            width = min(node.style.width.to_chars(console_width), console_width)

        def wrap_line(line: str) -> List[str]:
            """Wrap a single line with improved handling of word breaks"""
            if not line.strip():
                return ['']

            if len(line) <= width:
                return [line]

            # Initial wrap
            wrapped = textwrap.wrap(
                line,
                width=width,
                break_long_words=True,
                break_on_hyphens=True,
                expand_tabs=True
            )

            # Post-process to handle orphaned words
            processed = []
            i = 0
            while i < len(wrapped):
                current_line = wrapped[i]

                # Check if next line is very short (e.g., single word)
                if i < len(wrapped) - 1:
                    next_line = wrapped[i + 1]
                    # If next line is short (less than 20% of width or just one word)
                    if len(next_line) < width * 0.2 or ' ' not in next_line.strip():
                        # Try to fit it on current line if possible
                        combined = current_line + ' ' + next_line
                        if len(combined) <= width:
                            processed.append(combined)
                            i += 2
                            continue

                        # If we can't combine, try to rebalance the lines
                        words = (current_line + ' ' + next_line).split()
                        if len(words) >= 3:
                            # Distribute words more evenly
                            midpoint = len(words) // 2
                            line1 = ' '.join(words[:midpoint])
                            line2 = ' '.join(words[midpoint:])
                            if len(line1) <= width and len(line2) <= width:
                                processed.extend([line1, line2])
                                i += 2
                                continue

                processed.append(current_line)
                i += 1

            return processed

        # Split content into lines preserving existing breaks
        lines = node.content.splitlines(keepends=False)

        # Process each line
        rendered_lines = []
        for line in lines:
            stripped = line.rstrip('\n')
            wrapped_lines = wrap_line(stripped)
            rendered_lines.extend(wrapped_lines)

            # Preserve original line endings
            if line.endswith('\n'):
                rendered_lines.append('')

        # Join preserving line breaks
        final_text = '\n'.join(rendered_lines)

        # Create Rich Text object
        result = Text(final_text)

        # Apply styling
        if node.style:
            if node.style.text_align:
                align_map = {
                    'center': 'center',
                    'right': 'right',
                    'justify': 'full',
                    'left': 'left'
                }
                result.justify = align_map.get(node.style.text_align, 'left')

            if node.style.font_weight in ('bold', '700', '800', '900'):
                result.stylize("bold")

        return result

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


@dataclass
class StyledText:
    """Represents a piece of text with its associated style"""
    content: str
    style: StyleInfo
    is_paragraph: bool = False  # Track if this came from a <p> tag


class SECHTMLParser:
    def __init__(self, root: Tag, extract_data: bool = True):
        self.data:DocumentData = HtmlDocument.extract_data(root) if extract_data else None
        self.root:Tag = clean_html_root(root)
        self.base_font_size = 10.0  # Default base font size in pt
        self.style_stack: List[StyleInfo] = []

    def parse(self) -> Optional[Document]:
        body = self.root.find('body')
        if not body:
            logger.warn("No body tag found in HTML")
            return None

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
            if key == 'width':
                width = self._parse_width(value)
                if width:
                    style.width = width
            elif key == 'display':
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
            elif key == 'text-decoration':
                style.text_decoration = value

        return style

    def _parse_width(self, value: str) -> Optional[Width]:
        """Parse CSS width value into Width object"""
        if not value:
            return None

        # Handle percentage values
        if value.endswith('%'):
            try:
                return Width(float(value[:-1]), '%')
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

        # Map CSS units to our unit types
        unit_map = {
            'in': 'in',
            'pt': 'pt',
            'px': 'px',
            'cm': 'cm',
            'mm': 'mm',
            '': 'px'  # default to pixels if no unit specified
        }

        unit = unit_map.get(unit)
        if not unit:
            return None

        return Width(number, unit)


    def _parse_unit(self, value: str) -> Optional[float]:
        """Parse CSS unit values into integer character width"""
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

        # Convert different units to characters
        # Assuming typical terminal character widths:
        # - 80 chars ≈ 6.5 inches
        # - 1 inch ≈ 12.3 chars
        chars_per_unit = {
            'in': 12.3,     # 1 inch ≈ 12.3 chars
            'pt': 12.3/72,  # 1 pt = 1/72 inch
            'px': 12.3/96,  # 1 px = 1/96 inch
            'cm': 4.84,     # 1 cm ≈ 4.84 chars
            'mm': 0.484,    # 1 mm ≈ 0.484 chars
            'em': 1.6,      # 1 em ≈ 1.6 chars (assuming typical font)
            'rem': 1.6,     # Same as em
        }

        multiplier = chars_per_unit.get(unit, 1.0)
        return int(number * multiplier)


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
        """Determine if a div looks like it should be treated as a heading"""
        # Get text content
        text = element.get_text(strip=True)
        if not text:
            return False

        # Check header-like characteristics, converting each to explicit boolean
        hints = [
            bool(style.font_weight and style.font_weight in ['bold', '700', '800', '900']),  # Bold text
            bool(style.margin_top and style.margin_top > 12),  # Significant top margin
            bool(len(text.split()) <= 10),  # Relatively short text
            not bool(element.find('table')),  # No tables inside
            not any(c.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'] for c in element.find_all()),  # No header tags inside
            bool(style.font_size and style.font_size >= self.base_font_size)  # Font size >= base size
        ]

        # Consider it a header if it meets most criteria
        return sum(hints) >= 3

    def _determine_heading_level(self, style: StyleInfo) -> int:
        """Determine heading level based on styling"""
        if not style:
            return 2  # Default level

        # Use font size relative to base size to determine level
        if style.font_size:
            size_ratio = style.font_size / self.base_font_size
            if size_ratio >= 1.8:  # Much larger
                return 1
            elif size_ratio >= 1.4:  # Notably larger
                return 2
            elif size_ratio >= 1.2:  # Somewhat larger
                return 3

        # If bold but not significantly larger, treat as lower-level heading
        if style.font_weight in ['bold', '700', '800', '900']:
            return 3

        return 4  # Default to lowest level if uncertain

    def _process_element(self, element: Tag) -> Optional[Union[DocumentNode, List[DocumentNode]]]:
        """Process an element into one or more document nodes with inherited styles"""
        # Parse current element's style
        current_style = self.parse_style(element.get('style', ''))

        # Merge with parent style if there is one
        if self.style_stack:
            current_style = current_style.merge(self.style_stack[-1])

        # Push current style to stack before processing children
        self.style_stack.append(current_style)

        try:
            # Handle ix: tags by getting their content
            if element.name.startswith('ix:'):
                for child in element.children:
                    if isinstance(child, Tag):
                        return self._process_element(child)
                text = self._get_text_with_spacing(element)
                if text:
                    return DocumentNode(
                        type='text_block',
                        content=text,
                        style=current_style
                    )

            # Process specific element types
            if element.name == 'table':
                return self._process_table(element)
            elif element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                level = int(element.name[1])
                return DocumentNode(
                    type='heading',
                    content=element.get_text(strip=True),
                    style=current_style,
                    level=level
                )
            elif element.name == 'p':
                return self._process_paragraph(element, current_style)
            elif element.name == 'div':
                # Check if this div looks like a heading
                if self._looks_like_header(element, current_style):
                    return DocumentNode(
                        type='heading',
                        content=element.get_text(strip=True),
                        style=current_style,
                        level=self._determine_heading_level(current_style)
                    )

                # First check if this div has direct text content
                has_direct_text = any(isinstance(child, NavigableString) and child.strip()
                                      for child in element.children)

                # If it has direct text, process it as a paragraph
                if has_direct_text:
                    text = self._get_text_with_spacing(element)
                    if text.strip():
                        return DocumentNode(
                            type='text_block',
                            content=text.strip(),
                            style=current_style
                        )

                # Otherwise process children normally
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

            # For other elements, process children
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

        finally:
            # Always pop the style from stack when done with this element
            self.style_stack.pop()


    def _process_paragraph(self, element: Tag, parent_style: StyleInfo) -> Optional[DocumentNode]:
        """Process a paragraph element with inherited styles"""
        text_parts = []

        for child in element.children:
            if isinstance(child, NavigableString):
                text = str(child)
                if text:
                    text_parts.append(text)
            elif isinstance(child, Tag):
                if child.name == 'br':
                    text_parts.append('\n')
                elif child.name in ['span', 'strong', 'em', 'b', 'i', 'a']:
                    inline_text = child.get_text()
                    if inline_text:
                        text_parts.append(inline_text)

        if not text_parts:
            return None

        combined_text = ''.join(text_parts)
        normalized_text = ' '.join(combined_text.split())

        # Merge paragraph's own style with parent style
        style = self.parse_style(element.get('style', '')).merge(parent_style)

        return DocumentNode(
            type='text_block',
            content=normalized_text,
            style=style
        )

    def _process_content(self, element: Tag, style: StyleInfo) -> List[DocumentNode]:
        """Process any content-containing element into document nodes"""
        nodes = []
        current_pieces: List[StyledText] = []

        def flush_text() -> None:
            """Convert accumulated text pieces into text block node"""
            if not current_pieces:
                return

            # Determine if this is from a paragraph tag
            is_paragraph = any(piece.is_paragraph for piece in current_pieces)
            text = self._normalize_text(current_pieces, is_paragraph)

            # Use the most specific (last) style for the block
            final_style = current_pieces[-1].style

            if text.strip():
                nodes.append(DocumentNode(
                    type='text_block',
                    content=text,
                    style=final_style
                ))
            current_pieces.clear()

        # First check if this element should be a heading
        if self._is_heading(element, style) and not element.find('table', recursive=True):
            return [DocumentNode(
                type='heading',
                content=element.get_text(strip=True),
                style=style,
                level=self._determine_heading_level(style)
            )]

        def process_node(node: Union[Tag, NavigableString]) -> None:
            nonlocal current_pieces

            if isinstance(node, NavigableString):
                text = str(node)
                if text:
                    # Not from a <p> tag, preserve line breaks
                    current_pieces.append(StyledText(text, style, is_paragraph=False))
            elif isinstance(node, Tag):
                if node.name == 'table':
                    # Flush any accumulated text before table
                    flush_text()
                    # Process table and add to nodes
                    table_node = self._process_table(node)
                    if table_node:
                        nodes.append(table_node)
                elif node.name == 'br':
                    current_pieces.append(StyledText('\n', style, is_paragraph=False))
                elif node.name == 'p':
                    # Flush any previous content
                    flush_text()
                    # Process paragraph content with stricter normalization
                    node_style = self._get_combined_style(node, style)
                    text = self._get_text_with_spacing(node)
                    if text:
                        current_pieces.append(StyledText(text, node_style, is_paragraph=True))
                    flush_text()
                else:
                    # Handle other elements
                    node_style = self._get_combined_style(node, style)

                    if self._is_block_element(node):
                        # Flush current content before block element
                        flush_text()
                        # Process block element
                        block_nodes = self._process_content(node, node_style)
                        nodes.extend(block_nodes)
                    else:
                        # Handle inline element
                        text = self._get_text_with_spacing(node)
                        if text:
                            current_pieces.append(StyledText(text, node_style, is_paragraph=False))

        # Process all children
        for child in element.children:
            process_node(child)

        # Flush any remaining text
        flush_text()

        return nodes

    def _normalize_text(self, pieces: List[StyledText], is_paragraph: bool) -> str:
        """Normalize text differently for paragraphs vs general text blocks"""
        if is_paragraph:
            # For actual paragraphs, collapse all whitespace
            text = ' '.join(piece.content for piece in pieces)
            return ' '.join(text.split())
        else:
            # For general text blocks, preserve line breaks
            lines = []
            current_line = []

            for piece in pieces:
                if piece.content == '\n':
                    # Flush current line
                    if current_line:
                        lines.append(' '.join(''.join(current_line).split()))
                        current_line = []
                    lines.append('')  # Add empty line for break
                else:
                    current_line.append(piece.content)

            # Flush any remaining content
            if current_line:
                lines.append(' '.join(''.join(current_line).split()))

            # Remove any extra empty lines but preserve single line breaks
            text = '\n'.join(lines)
            return re.sub(r'\n{3,}', '\n\n', text)



    def _is_block_element(self, element: Tag) -> bool:
        """Determine if an element is block-level"""
        # Check explicit display style first
        style = self.parse_style(element.get('style', ''))
        if style.display:
            return style.display != 'inline'

        # Default block elements
        block_elements = {
            'div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'ul', 'ol', 'li', 'blockquote', 'pre', 'hr',
            'table', 'form', 'fieldset', 'address'
        }

        return element.name in block_elements

    def _collect_styled_text(self, element: Tag, style: StyleInfo) -> List[StyledText]:
        """Collect text with style information from inline elements"""
        pieces = []

        for child in element.children:
            if isinstance(child, NavigableString):
                text = str(child)
                if text.strip():
                    pieces.append(StyledText(text, style))
            elif isinstance(child, Tag):
                if child.name == 'br':
                    pieces.append(StyledText('\n', style))
                elif child.name != 'table':  # Skip tables in inline collection
                    child_style = self._get_combined_style(child, style)
                    pieces.extend(self._collect_styled_text(child, child_style))

        return pieces

    def _get_combined_style(self, element: Tag, parent_style: StyleInfo) -> StyleInfo:
        """Combine element's style with parent style, including HTML attributes"""
        style = self.parse_style(element.get('style', ''))

        # Handle specific HTML tags and their attributes
        if element.name == 'font':
            if size := element.get('size'):
                try:
                    size_num = float(size.replace('pt', ''))
                    style.font_size = size_num
                except ValueError:
                    pass

        elif element.name in {'b', 'strong'}:
            style.font_weight = 'bold'
        elif element.name in {'i', 'em'}:
            style.font_style = 'italic'

        return style.merge(parent_style)

    def _convert_pieces_to_nodes(self, pieces: List[StyledText]) -> List[DocumentNode]:
        """Convert collected text pieces into document nodes"""
        nodes = []
        current_paragraph: List[StyledText] = []

        def flush_paragraph():
            if not current_paragraph:
                return

            # Combine text and determine final style
            text = self._normalize_paragraph_text(current_paragraph)
            # Use the most specific (last) style for the paragraph
            final_style = current_paragraph[-1].style

            if text.strip():
                nodes.append(DocumentNode(
                    type='text_block',
                    content=text,
                    style=final_style
                ))
            current_paragraph.clear()

        for piece in pieces:
            if piece.is_block:
                flush_paragraph()
            else:
                current_paragraph.append(piece)

        # Flush any remaining content
        flush_paragraph()

        return nodes

    def _normalize_paragraph_text(self, pieces: List[StyledText]) -> str:
        """Normalize text within a paragraph while preserving intentional breaks"""
        # Join all pieces and split into lines
        text = ''.join(piece.content for piece in pieces)
        lines = text.splitlines()

        # Normalize each line individually
        normalized_lines = []
        for line in lines:
            # Collapse whitespace within each line
            normalized = ' '.join(line.split())
            if normalized:
                normalized_lines.append(normalized)

        # Join lines with single newlines
        return '\n'.join(normalized_lines)

    def _is_inline(self, element: Tag) -> bool:
        """Determine if an element should be treated as inline"""
        style = self.parse_style(element.get('style', ''))
        if style.display == 'inline':
            return True

        # Standard inline elements
        inline_elements = {
            'span', 'font', 'b', 'strong', 'i', 'em', 'a',
            'sub', 'sup', 'u', 'small', 'mark'
        }

        return element.name in inline_elements

    def _is_empty_text(self, text: str) -> bool:
        """Check if text is effectively empty"""
        return not bool(text.strip())


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
            if (current.type == 'text_block' and
                    node.type == 'text_block' and
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




