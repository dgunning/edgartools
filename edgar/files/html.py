import re
import textwrap
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Dict, List, Literal, Optional, Union

from bs4 import NavigableString, Tag
from rich import box
from rich.align import Align
from rich.console import Console, Group, RenderResult
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.core import log
from edgar.files.html_documents import DocumentData, HtmlDocument
from edgar.files.styles import StyleInfo, Width, get_heading_level, parse_style
from edgar.files.tables import ColumnOptimizer, ProcessedTable, TableProcessor
from edgar.richtools import repr_rich

__all__ = ['SECHTMLParser', 'Document', 'DocumentNode']


class BaseNode(ABC):
    """Abstract base class for all document nodes with metadata support"""

    def __init__(self):
        self.metadata: Dict[str, Any] = {}

    @abstractmethod
    def render(self, console_width: int) -> RenderResult:
        """Render the node for display"""
        pass

    @property
    @abstractmethod
    def type(self) -> str:
        """Return the type of the node"""
        pass

    def add_metadata(self, key: str, value: Any) -> None:
        """Add or update metadata"""
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value with optional default"""
        return self.metadata.get(key, default)

    def remove_metadata(self, key: str) -> None:
        """Remove metadata if it exists"""
        self.metadata.pop(key, None)



@dataclass
class HeadingNode(BaseNode):
    content: str
    style: StyleInfo
    level: int = 1

    def __post_init__(self):
        super().__init__()

    @property
    def type(self) -> str:
        return 'heading'

    def render(self, console_width: int) -> RenderResult:
        """Render heading with enhanced styling based on level"""
        # Enhanced style configurations based on heading level
        styles = {
            1: {
                "text_style": "bold cyan",
                "box": box.DOUBLE,
                "border_style": "cyan",
                "padding": (1, 2),
                "title": "§" if self.content else None  # Section symbol for level 1
            },
            2: {
                "text_style": "bold blue",
                "box": box.ROUNDED,
                "border_style": "blue",
                "padding": (1, 2),
                "title": "•" if self.content else None  # Bullet for level 2
            },
            3: {
                "text_style": "bold blue",
                "box": box.SIMPLE_HEAVY,
                "border_style": "white",
                "padding": (0, 2),
                "title": "" if self.content else None  # Arrow for level 3
            },
            4: {
                "text_style": "bold underline",
                "box": box.MINIMAL,
                "border_style": "grey62",
                "padding": (0, 1),
                "title": "" if self.content else None  # Dash for level 4
            }
        }

        # Get style configuration for current heading level, defaulting to level 4
        style_config = styles.get(self.level, styles[4])

        # Create base text with style
        text = Text(self.content.strip(), style=style_config["text_style"])

        # Apply text alignment based on style
        if self.style and self.style.text_align == 'center':
            text = Align.center(text)

        # Create panel with enhanced styling
        return Panel(
            text,
            box=style_config["box"],
            border_style=style_config["border_style"],
            padding=style_config["padding"],
            expand=True,
            title=style_config["title"],
            title_align="left"
        )


@dataclass
class TextBlockNode(BaseNode):
    content: str
    style: StyleInfo

    def __post_init__(self):
        super().__init__()

    @property
    def type(self) -> str:
        return 'text_block'

    def render(self, console_width: int) -> RenderResult:
        if not self.content:
            return Text("")

        width = console_width
        if self.style and self.style.width:
            width = min(self.style.width.to_chars(console_width), console_width)

        # Wrap text with improved handling
        def wrap_line(line: str) -> List[str]:
            if not line.strip():
                return ['']
            if len(line) <= width:
                return [line]

            wrapped = textwrap.wrap(
                line,
                width=width,
                break_long_words=True,
                break_on_hyphens=True,
                expand_tabs=True
            )

            # Handle orphaned words
            processed = []
            i = 0
            while i < len(wrapped):
                current_line = wrapped[i]
                if i < len(wrapped) - 1:
                    next_line = wrapped[i + 1]
                    if len(next_line) < width * 0.2 or ' ' not in next_line.strip():
                        combined = current_line + ' ' + next_line
                        if len(combined) <= width:
                            processed.append(combined)
                            i += 2
                            continue
                processed.append(current_line)
                i += 1
            return processed

        lines = self.content.splitlines(keepends=False)
        rendered_lines = []
        for line in lines:
            wrapped_lines = wrap_line(line.rstrip('\n'))
            rendered_lines.extend(wrapped_lines)
            if line.endswith('\n'):
                rendered_lines.append('')

        final_text = '\n'.join(rendered_lines)
        result = Text(final_text)

        if self.style:
            if self.style.text_align:
                align_map = {
                    'center': 'center',
                    'right': 'right',
                    'justify': 'full',
                    'left': 'left'
                }
                result.justify = align_map.get(self.style.text_align, 'left')

            if self.style.font_weight in ('bold', '700', '800', '900'):
                result.stylize("bold")

        return result



@dataclass
class TableCell:
    content: Union[str, BaseNode]
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


@dataclass
class TableNode(BaseNode):
    content: List[TableRow]
    style: StyleInfo
    _processed_table: Optional[ProcessedTable] = None

    def __post_init__(self):
        super().__init__()

    @property
    def type(self) -> str:
        return 'table'

    @property
    def row_count(self) -> int:
        """Quick count of rows without processing"""
        return len(self.content)

    @property
    def approximate_column_count(self) -> int:
        """Quick approximate of columns using max cells in any row"""
        if not self.content:
            return 0
        return max(row.virtual_columns for row in self.content)

    @cached_property
    def _processed(self) -> Optional[ProcessedTable]:
        """Cached access to processed table"""
        if self._processed_table is None:
            self._processed_table = TableProcessor.process_table(self)
        return self._processed_table

    @property
    def processed_row_count(self) -> int:
        """Accurate row count after processing"""
        if not self._processed:
            return self.row_count
        return len(self._processed.data_rows) + (len(self._processed.headers or []) > 0)

    @property
    def processed_column_count(self) -> int:
        """Accurate column count after processing"""
        if not self._processed:
            return self.approximate_column_count
        if self._processed.headers:
            return len(self._processed.headers)
        elif self._processed.data_rows:
            return len(self._processed.data_rows[0])
        return 0

    def reset_processing(self) -> None:
        """Clear cached processed table"""
        self._processed_table = None
        # Clear cached properties
        try:
            del self._processed
        except AttributeError:
            pass

    def render(self, console_width: int) -> RenderResult:
        from edgar.files.tables import TableProcessor
        processed_table = TableProcessor.process_table(self)
        if not processed_table:
            return None

        # Optimize the table
        column_optimizer:ColumnOptimizer = ColumnOptimizer()
        widths, processed_table = column_optimizer.optimize_columns(processed_table)

        table = Table(
            box=box.SIMPLE,
            border_style="blue",
            padding=(0, 1),
            show_header=bool(processed_table.headers),
            row_styles=["", "gray54"],
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


@dataclass
class PageBreakNode(BaseNode):
    """Represents a page break in the document"""
    page_number: int

    def __post_init__(self):
        super().__init__()

    @property
    def type(self) -> str:
        return 'page_break'

    def render(self, console_width: int) -> RenderResult:
        """Render page break with page number"""
        return Text(f"--- Page {self.page_number} ---", style="dim")


def create_node(
        type_: str,
        content: Union[str, List[TableRow]],
        style: StyleInfo,
        level: int = 1,
        metadata: Optional[Dict[str, Any]] = None,
        page_number: Optional[int] = None
) -> BaseNode:
    """Create a node with optional metadata"""
    metadata = metadata or {}

    if type_ == 'heading':
        node = HeadingNode(content=content, style=style, level=level)
    elif type_ == 'text_block':
        node = TextBlockNode(content=content, style=style)
    elif type_ == 'table':
        node = TableNode(content=content, style=style)
    elif type_ == 'page_break':
        node = PageBreakNode(page_number=page_number)
    else:
        raise ValueError(f"Unknown node type: {type_}")

    # Apply metadata after creation
    if metadata:
        node.metadata.update(metadata)

    return node


# 1. Add type literals and type guards
NodeType = Literal['heading', 'text_block', 'table', 'page_break']
ContentType = Union[str, Dict[str, Any], List[TableRow]]

def is_table_content(content: ContentType) -> bool:
    return isinstance(content, list) and all(isinstance(x, TableRow) for x in content)

def is_text_content(content: ContentType) -> bool:
    return isinstance(content, str)

def is_dict_content(content: ContentType) -> bool:
    return isinstance(content, dict)


class IXTagTracker:
    """Tracks IX tag context throughout HTML parsing"""

    def __init__(self):
        # Maps continuation IDs to their original ix tag info
        self.continuation_map: Dict[str, Dict[str, str]] = {}
        # Current stack of ix tags
        self.tag_stack: List[Dict[str, str]] = []

    def enter_tag(self, element: Tag) -> None:
        """Process entering an ix: tag, handling both regular tags and continuations"""
        if not element.name.startswith('ix:'):
            return

        if element.name == 'ix:continuation':
            # For continuation tags, look up the original tag's metadata
            continued_at = element.get('continuedAt')
            tag_id = element.get('id')
            if continued_at and tag_id:
                self.continuation_map[tag_id] = self.continuation_map.get(continued_at, {})
        else:
            # For regular ix tags, store their metadata
            tag_info = {
                'name': element.get('name', ''),
                'contextRef': element.get('contextRef', ''),
                'id': element.get('id', '')
            }
            # Store any additional attributes
            for key, value in element.attrs.items():
                if key not in {'name', 'contextRef', 'id'}:
                    tag_info[key] = value

            # Add to continuation map if this tag has an ID
            if tag_info['id']:
                self.continuation_map[tag_info['id']] = tag_info

            self.tag_stack.append(tag_info)

    def exit_tag(self, element: Tag) -> None:
        """Record exiting an ix: tag"""
        if element.name.startswith('ix:') and element.name != 'ix:continuation':
            if self.tag_stack:
                self.tag_stack.pop()

    def get_current_context(self, element: Tag) -> Dict[str, Any]:
        """Get the current ix tag context, handling both regular tags and continuations"""
        # First check if we're in a continuation
        if element.name == 'ix:continuation':
            tag_id = element.get('id')
            if tag_id in self.continuation_map:
                original_tag = self.continuation_map[tag_id]
                return {
                    'ix_tag': original_tag.get('name'),
                    'ix_context': original_tag.get('contextRef'),
                    'ix_original_id': original_tag.get('id'),
                    'ix_continuation_id': tag_id,
                    **{f'ix_{k}': v for k, v in original_tag.items()
                       if k not in {'name', 'contextRef', 'id'}}
                }
            return {}

        # Otherwise use current tag stack
        if not self.tag_stack:
            return {}

        current = self.tag_stack[-1]
        metadata = {
            'ix_tag': current.get('name'),
            'ix_context': current.get('contextRef'),
            'ix_id': current.get('id')
        }

        # Add any additional attributes
        for key, value in current.items():
            if key not in {'name', 'contextRef', 'id'}:
                metadata[f'ix_{key}'] = value

        return metadata



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
    """Document class that works with the new node hierarchy"""
    nodes: List[BaseNode]

    def __len__(self):
        return len(self.nodes)

    def __getitem__(self, index):
        return self.nodes[index]

    def empty(self) -> bool:
        return len(self.nodes) == 0

    @staticmethod
    def _get_width() -> int:
        """Get the width of the console that this document is being rendered into"""
        return Console().width

    @property
    def tables(self) -> List[BaseNode]:
        """Get all table nodes in the document"""
        return [node for node in self.nodes if node.type == 'table']

    @property
    def headings(self) -> List[BaseNode]:
        """Get all heading nodes in the document"""
        return [node for node in self.nodes if node.type == 'heading']

    @classmethod
    def parse(cls, html: str, include_page_breaks: bool = False) -> Optional['Document']:
        root = HtmlDocument.get_root(html)
        if root:
            parser = SECHTMLParser(root, include_page_breaks=include_page_breaks)
            return parser.parse()

    def to_markdown(self, start_page_number: int = 0) -> str:
        from edgar.files.markdown import MarkdownRenderer
        return MarkdownRenderer(self, start_page_number=start_page_number).render()

    def __rich__(self) -> RenderResult:
        """Rich console protocol for rendering document"""
        console = Console()
        console_width = console.width

        renderable_elements = []
        for node in self.nodes:
            element = node.render(console_width)
            if element:
                renderable_elements.append(element)

        return Group(*renderable_elements)

    def __repr__(self):
        return repr_rich(self)


@dataclass
class StyledText:
    """Represents a piece of text with its associated style"""
    content: str
    style: StyleInfo
    is_paragraph: bool = False  # Track if this came from a <p> tag


class SECHTMLParser:
    def __init__(self, root: Tag, extract_data: bool = True, include_page_breaks: bool = False):
        self.data:DocumentData = HtmlDocument.extract_data(root) if extract_data else None
        self.root:Tag = root
        self.base_font_size = 10.0  # Default base font size in pt
        self.style_stack: List[StyleInfo] = []
        self.ix_tracker = IXTagTracker()  # Add IX tag tracker
        self.include_page_breaks = include_page_breaks
        self.current_page = -1  # Start at -1 so first page div becomes page 0

    def parse(self) -> Optional[Document]:
        body = self.root.find('body')
        if not body:
            log.warning("No body tag found in HTML")
            return None

        # If page breaks are enabled, detect them first
        if self.include_page_breaks:
            self._mark_page_breaks(body)

        nodes = self._parse_element(body)

        # If page breaks are enabled, ensure proper page numbering
        if self.include_page_breaks and nodes:
            # Find the first page break node
            first_page_break_idx = None
            for i, node in enumerate(nodes):
                if node.type == 'page_break':
                    first_page_break_idx = i
                    break

            if first_page_break_idx is None:
                # No page breaks found, this shouldn't happen if include_page_breaks is True
                # but add a document start page break just in case
                initial_page_break = create_node(
                    type_='page_break',
                    content=None,
                    style=StyleInfo(),
                    page_number=0,
                    metadata={'source_element': 'document_start'}
                )
                nodes.insert(0, initial_page_break)
            elif first_page_break_idx > 0:
                # There's content before the first page break, add document start page break
                initial_page_break = create_node(
                    type_='page_break',
                    content=None,
                    style=StyleInfo(),
                    page_number=0,
                    metadata={'source_element': 'document_start'}
                )
                nodes.insert(0, initial_page_break)
                # Re-number subsequent page breaks
                for i in range(1, len(nodes)):
                    if nodes[i].type == 'page_break':
                        nodes[i].page_number = i // 2  # Rough estimate, will be fixed in next loop

            # Final pass: renumber all page breaks sequentially
            page_counter = 0
            for node in nodes:
                if node.type == 'page_break':
                    node.page_number = page_counter
                    page_counter += 1

        return Document(nodes=nodes)

    def _mark_page_breaks(self, element: Tag) -> None:
        """Mark page break elements for detection during parsing"""
        from .page_breaks import PageBreakDetector
        PageBreakDetector.mark_page_breaks(element)

    def _mark_page_divs(self, element: Tag) -> None:
        """Mark div elements with page-like dimensions as page breaks"""
        # This is now handled by PageBreakDetector.mark_page_breaks()
        # Keeping this method for backward compatibility
        pass

    def _is_page_like_div(self, style: str) -> bool:
        """Check if a div has page-like dimensions based on its style"""
        from .page_breaks import PageBreakDetector
        return PageBreakDetector._is_page_like_div(style)

    def _process_div_content(self, element: Tag) -> Optional[Union[BaseNode, List[BaseNode]]]:
        """Process the content inside a page div without treating the div itself as a page break"""
        # Parse current element's style
        current_style = parse_style(element.get('style', ''))

        # Merge with parent style if there is one
        if self.style_stack:
            current_style = current_style.merge(self.style_stack[-1])

        # Track entering ix tags and get metadata
        self.ix_tracker.enter_tag(element)
        ix_metadata = self.ix_tracker.get_current_context(element)

        try:
            # Push current style to stack before processing children
            self.style_stack.append(current_style)

            try:
                # Check if this div contains tables
                if element.get('has_table'):
                    # Structure-preserving mode for divs with tables
                    result = self._process_structured_content(element, current_style)
                else:
                    # Content-combining mode for divs without tables
                    result = self._process_inline_content(element, current_style)

                # Apply ix metadata if available
                if result and ix_metadata:
                    if isinstance(result, list):
                        for node in result:
                            if hasattr(node, 'metadata'):
                                node.metadata.update(ix_metadata)
                    else:
                        if hasattr(result, 'metadata'):
                            result.metadata.update(ix_metadata)

                return result

            finally:
                # Always pop the style from stack when done
                self.style_stack.pop()

        finally:
            # Track exiting ix tags
            self.ix_tracker.exit_tag(element)

    def _parse_element(self, element: Tag) -> List[BaseNode]:
        nodes = []

        for child in element.children:
            if not isinstance(child, Tag):
                continue

            node = self._process_element(child)
            if node:
                nodes.extend(node if isinstance(node, list) else [node])

        return self._merge_adjacent_nodes(nodes)


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
            '&#8203;': '',  # zero-width space
            '\xa0': ' ',  # non-breaking space
            '\u200b': '',  # zero-width space
            '\u200c': '',  # zero-width non-joiner
            '\u200d': '',  # zero-width joiner
            '\u2028': ' ',  # line separator
            '\u2029': ' ',  # paragraph separator
            '\ufeff': ''  # byte order mark
        }

        for entity, replacement in entities.items():
            text = text.replace(entity, replacement)

        # Replace multiple consecutive spaces with a single space
        text = ' '.join(text.split())

        # Normalize whitespace while preserving single newlines
        lines = text.splitlines()
        lines = [' '.join(line.split()) for line in lines]
        text = '\n'.join(lines)

        # Clean up any remaining multiple spaces around newlines
        text = re.sub(r'\s*\n\s*', '\n', text)

        # Remove any remaining consecutive spaces
        text = re.sub(r' +', ' ', text)
        return text.strip()

    def _handle_page_break_element(self, element: Tag) -> Optional[Union[BaseNode, List[BaseNode]]]:
        """Handle elements marked as page breaks"""
        # For the first page break, don't increment if we're at -1 (start)
        if self.current_page == -1:
            self.current_page = 0
        else:
            self.current_page += 1

        page_break_node = create_node(
            type_='page_break',
            content=None,
            style=StyleInfo(),
            page_number=self.current_page,
            metadata={'source_element': element.name}
        )

        # Check if this is a container page break or content-bearing page break
        if element.name == 'div' and self._is_page_like_div(element.get('style', '')):
            # This is a page div - return page break AND process content inside
            nodes = [page_break_node]
            content_nodes = self._process_div_content(element)
            if content_nodes:
                if isinstance(content_nodes, list):
                    nodes.extend(content_nodes)
                else:
                    nodes.append(content_nodes)
            return nodes

        elif element.name in ['p', 'div'] and element.get_text(strip=True):
            # This is a content-bearing element with page break style - return page break AND content
            nodes = [page_break_node]

            if element.name == 'p':
                current_style = parse_style(element.get('style', ''))
                if self.style_stack:
                    current_style = current_style.merge(self.style_stack[-1])
                content_node = self._process_paragraph(element, current_style)
                if content_node:
                    nodes.append(content_node)
            elif element.name == 'div':
                content_nodes = self._process_div_content(element)
                if content_nodes:
                    if isinstance(content_nodes, list):
                        nodes.extend(content_nodes)
                    else:
                        nodes.append(content_nodes)
            return nodes

        else:
            # This is a marker-only page break (hr, empty elements) - return just the page break
            return page_break_node

    def _apply_metadata_to_nodes(self, nodes: Union[BaseNode, List[BaseNode]], metadata: Dict[str, Any]) -> None:
        """Apply metadata to a node or list of nodes"""
        if not metadata:
            return

        if isinstance(nodes, list):
            for node in nodes:
                if hasattr(node, 'metadata'):
                    node.metadata.update(metadata)
        else:
            if hasattr(nodes, 'metadata'):
                nodes.metadata.update(metadata)

    def _process_element_with_page_breaks(self, element: Tag) -> Optional[Union[BaseNode, List[BaseNode]]]:
        """Process an element that contains page break descendants"""
        nodes = []

        for child in element.children:
            if isinstance(child, Tag):
                # Check if this child is a page break or contains page breaks
                if child.get('_is_page_break') == 'true':
                    page_break_result = self._handle_page_break_element(child)
                    if page_break_result:
                        if isinstance(page_break_result, list):
                            nodes.extend(page_break_result)
                        else:
                            nodes.append(page_break_result)
                else:
                    # Process child normally
                    child_result = self._process_element(child)
                    if child_result:
                        if isinstance(child_result, list):
                            nodes.extend(child_result)
                        else:
                            nodes.append(child_result)

        return nodes[0] if len(nodes) == 1 else nodes if nodes else None

    def _dispatch_element_processing(self, element: Tag, current_style: StyleInfo, ix_metadata: Dict[str, Any]) -> Optional[Union[BaseNode, List[BaseNode]]]:
        """Dispatch element processing based on element type"""
        # Handle ix: tags by processing their content sequentially
        if element.name.startswith('ix:'):
            return self._process_ix_element(element, current_style, ix_metadata)

        # Process table elements directly
        if element.name == 'table':
            table_node = self._process_table(element)
            self._apply_metadata_to_nodes(table_node, ix_metadata)
            return table_node

        elif element.name == 'p':
            return self._process_paragraph_element(element, current_style, ix_metadata)

        elif element.name == 'div':
            return self._process_div_element(element, current_style, ix_metadata)

        # For other elements, process children
        return self._process_generic_element(element, ix_metadata)

    def _process_ix_element(self, element: Tag, current_style: StyleInfo, ix_metadata: Dict[str, Any]) -> Optional[Union[BaseNode, List[BaseNode]]]:
        """Process ix: tagged elements"""
        nodes = []
        children = list(element.children)  # Convert to list to avoid iterator modification

        for child in children:
            if isinstance(child, Tag):
                if child.name == 'table':
                    table_node = self._process_table(child)
                    if table_node:
                        self._apply_metadata_to_nodes(table_node, ix_metadata)
                        nodes.append(table_node)
                elif child.name == 'p':
                    para_node = self._process_paragraph(child, current_style)
                    if para_node:
                        self._apply_metadata_to_nodes(para_node, ix_metadata)
                        nodes.append(para_node)
                elif child.name == 'div':
                    div_style = parse_style(child.get('style', '')).merge(current_style)
                    div_result = self._process_structured_content(child, div_style)
                    if div_result:
                        self._apply_metadata_to_nodes(div_result, ix_metadata)
                        if isinstance(div_result, list):
                            nodes.extend(div_result)
                        else:
                            nodes.append(div_result)
                else:
                    child_result = self._process_element(child)
                    if child_result:
                        self._apply_metadata_to_nodes(child_result, ix_metadata)
                        if isinstance(child_result, list):
                            nodes.extend(child_result)
                        else:
                            nodes.append(child_result)

        return nodes[0] if len(nodes) == 1 else nodes if nodes else None

    def _process_paragraph_element(self, element: Tag, current_style: StyleInfo, ix_metadata: Dict[str, Any]) -> Optional[BaseNode]:
        """Process paragraph elements, checking for headings first"""
        para_text = element.get_text(strip=True)
        if para_text:
            heading_level = get_heading_level(element, current_style, para_text)
            if heading_level is not None:
                node = create_node(
                    type_='heading',
                    content=para_text,
                    style=current_style,
                    level=heading_level
                )
                self._apply_metadata_to_nodes(node, ix_metadata)
                return node

        para_node = self._process_paragraph(element, current_style)
        self._apply_metadata_to_nodes(para_node, ix_metadata)
        return para_node

    def _process_div_element(self, element: Tag, current_style: StyleInfo, ix_metadata: Dict[str, Any]) -> Optional[Union[BaseNode, List[BaseNode]]]:
        """Process div elements based on whether they contain tables"""
        if element.get('has_table'):
            # Structure-preserving mode for divs with tables
            block_result = self._process_structured_content(element, current_style)
        else:
            # Content-combining mode for divs without tables
            block_result = self._process_inline_content(element, current_style)

        self._apply_metadata_to_nodes(block_result, ix_metadata)
        return block_result

    def _process_generic_element(self, element: Tag, ix_metadata: Dict[str, Any]) -> Optional[Union[BaseNode, List[BaseNode]]]:
        """Process generic elements by processing their children"""
        nodes = []
        for child in element.children:
            if isinstance(child, Tag):
                child_result = self._process_element(child)
                if child_result:
                    self._apply_metadata_to_nodes(child_result, ix_metadata)
                    if isinstance(child_result, list):
                        nodes.extend(child_result)
                    else:
                        nodes.append(child_result)

        return nodes[0] if len(nodes) == 1 else nodes if nodes else None

    def _process_element(self, element: Tag) -> Optional[Union[BaseNode, List[BaseNode]]]:
        """Process an element into one or more nodes with inherited styles and ix metadata"""
        # Handle page break elements first
        if self.include_page_breaks and element.get('_is_page_break') == 'true':
            return self._handle_page_break_element(element)

        # Also check if this element contains page break descendants
        if self.include_page_breaks and element.select('[_is_page_break="true"]'):
            # This element contains page breaks, process them individually
            return self._process_element_with_page_breaks(element)

        # Phase 1: Mark all ancestors of tables
        tables = element.find_all('table', recursive=True)
        for table in tables:
            parent = table.parent
            while parent:
                parent['has_table'] = True
                parent = parent.parent

        # Parse current element's style
        current_style = parse_style(element.get('style', ''))

        # Merge with parent style if there is one
        if self.style_stack:
            current_style = current_style.merge(self.style_stack[-1])

        # Track entering ix tags and get metadata
        self.ix_tracker.enter_tag(element)
        ix_metadata = self.ix_tracker.get_current_context(element)

        try:
            # Push current style to stack before processing children
            self.style_stack.append(current_style)

            try:
                # First check if this element could be a heading
                text = element.get_text(strip=True)
                if text:  # Only check for headings if there's text content
                    heading_level = get_heading_level(element, current_style, text)
                    if heading_level is not None:
                        node = create_node(
                            type_='heading',
                            content=text,
                            style=current_style,
                            level=heading_level
                        )
                        if ix_metadata:
                            node.metadata.update(ix_metadata)
                        return node

                # Dispatch to appropriate element handler
                return self._dispatch_element_processing(element, current_style, ix_metadata)

            finally:
                # Always pop the style from stack when done
                self.style_stack.pop()

        finally:
            # Always track exiting ix tags
            self.ix_tracker.exit_tag(element)


    def _process_structured_content(self, element: Tag, style: StyleInfo) -> Optional[Union[BaseNode, List[BaseNode]]]:
        """Process content in structure-preserving mode (for elements containing tables)"""
        nodes = []
        text_parts = []

        def flush_text():
            if text_parts:
                text = ' '.join(text_parts).strip()
                if text:
                    nodes.append(create_node(
                        type_='text_block',
                        content=text,
                        style=style
                    ))
                text_parts.clear()

        for child in element.children:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    text_parts.append(text)
            elif isinstance(child, Tag):
                if child.name == 'table':
                    flush_text()
                    table_node = self._process_table(child)
                    if table_node:
                        nodes.append(table_node)
                elif child.get('has_table'):
                    # This child contains a table somewhere, process structurally
                    flush_text()
                    child_result = self._process_element(child)
                    if child_result:
                        if isinstance(child_result, list):
                            nodes.extend(child_result)
                        else:
                            nodes.append(child_result)
                else:
                    # Non-table-containing element, can process for text
                    text = self._get_text_with_spacing(child).strip()
                    if text:
                        text_parts.append(text)

        flush_text()
        return nodes[0] if len(nodes) == 1 else nodes if nodes else None

    def _process_inline_content(self, element: Tag, style: StyleInfo) -> Optional[Union[BaseNode, List[BaseNode]]]:
        """Process content in content-combining mode (for elements without tables)"""

        # First check if the entire element is a heading
        text = element.get_text(strip=True)
        if text:
            heading_level = get_heading_level(element, style, text)
            if heading_level is not None:
                return create_node(
                    type_='heading',
                    content=text,
                    style=style,
                    level=heading_level
                )

        nodes = []
        text_parts: List[str] = []  # Explicitly type as strings

        def flush_text():
            if text_parts:
                text = ' '.join(text_parts).strip()
                if text:
                    # Check if combined text forms a heading
                    heading_level = get_heading_level(element, style, text)
                    if heading_level is not None:
                        nodes.append(create_node(
                            type_='heading',
                            content=text,
                            style=style,
                            level=heading_level
                        ))
                    else:
                        nodes.append(create_node(
                            type_='text_block',
                            content=text,
                            style=style
                        ))
                    text_parts.clear()

        # Process children while handling special cases
        for child in element.children:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text and text != '\u200B':  # Skip zero-width spaces
                    text_parts.append(text)
            elif isinstance(child, Tag):
                if child.name == 'br':
                    text_parts.append('\n')
                elif not self._is_block_element(child):
                    # Get the child's style combined with parent style
                    child_style = parse_style(child.get('style', '')).merge(style)
                    text = self._get_text_with_spacing(child).strip()
                    if text:
                        # Check if this individual child is a heading
                        heading_level = get_heading_level(child, child_style, text)
                        if heading_level is not None:
                            # Flush any existing text first
                            flush_text()
                            nodes.append(create_node(
                                type_='heading',
                                content=text,
                                style=child_style,
                                level=heading_level
                            ))
                        else:
                            # Store just the text, but use child_style when creating the node
                            text_parts.append(text)
                            # Update the style for the current text block to use the child's style
                            style = child_style
                else:
                    # For block elements, flush current text and process the element
                    flush_text()
                    child_result = self._process_element(child)
                    if child_result:
                        if isinstance(child_result, list):
                            nodes.extend(child_result)
                        else:
                            nodes.append(child_result)

        # Flush any remaining text
        flush_text()

        return nodes[0] if len(nodes) == 1 else nodes if nodes else None



    def _normalize_text_parts(self, parts: List[str]) -> str:
        """Normalize text parts while preserving intentional line breaks"""
        # Remove empty parts and normalize spaces
        normalized_parts = []
        for i, part in enumerate(parts):
            if part == '\n':
                # Keep newlines but ensure no extra spaces around them
                normalized_parts.append('\n')
            else:
                # For text content, strip and add only if non-empty
                stripped = part.strip()
                if stripped:
                    # Don't add space if previous part was a newline or this is the first part
                    if normalized_parts and normalized_parts[-1] != '\n' and i > 0:
                        normalized_parts.append(' ')
                    normalized_parts.append(stripped)

        # Join all parts and remove any extra whitespace around newlines
        text = ''.join(normalized_parts)

        # Clean up any potential multiple newlines or spaces
        #text = re.sub(r'\s*\n\s*', '\n', text)
        text = re.sub(r' +', ' ', text)

        return text.strip()

    def _process_table(self, element: Tag) -> Optional[BaseNode]:
        """Process table element into a TableNode with precise line break handling"""
        if not element:
            return None

        def replace_html_entities(text: str) -> str:
            """Replace HTML entities with markdown-safe alternatives"""
            # Map of HTML entities to their markdown-safe replacements
            entity_replacements = {
                '&horbar;': '-----',  # Horizontal bar
                '&mdash;': '-----',  # Em dash
                '&ndash;': '---',  # En dash
                '&minus;': '-',  # Minus sign
                '&hyphen;': '-',  # Hyphen
                '&dash;': '-',  # Generic dash
                # Add other common entities that might need replacement
                '&nbsp;': ' ',  # Non-breaking space
                '&amp;': '&',  # Ampersand
                '&lt;': '<',  # Less than
                '&gt;': '>',  # Greater than
                '&quot;': '"',  # Quote
                '&apos;': "'",  # Apostrophe
                '&#8202;': ' ',  # Hair space
                '&#8203;': '',  # Zero-width space
                '&#x2014;': '-----',  # Another way to encode mdash
                '&#x2013;': '---',  # Another way to encode ndash
                '&#x2212;': '-',  # Another way to encode minus
            }

            # Also handle numeric entities that might represent dashes
            # Unicode values for various dashes
            dash_codepoints = {
                '8208': '-',  # hyphen
                '8209': '-',  # non-breaking hyphen
                '8210': '-',  # figure dash
                '8211': '---',  # en dash
                '8212': '-----',  # em dash
                '8213': '-----',  # horizontal bar
                '8722': '-',  # minus sign
            }

            result = text
            # Replace named entities
            for entity, replacement in entity_replacements.items():
                result = result.replace(entity, replacement)

            # Replace numeric entities (both decimal and hex) for dashes
            for code, replacement in dash_codepoints.items():
                # Replace decimal format
                result = result.replace(f'&#{code};', replacement)
                # Replace hexadecimal format
                result = result.replace(f'&#x{hex(int(code))[2:]};', replacement)

            return result

        def extract_cell_text(cell: Tag) -> str:
            """Extract text from cell with careful line break handling"""
            # First check for div children
            divs = cell.find_all('div', recursive=False)
            if divs:
                # Get text from each div and handle entities
                div_texts = [replace_html_entities(div.get_text(strip=True)) for div in divs]
                return '\n'.join(div_texts)

            # Handle <br/> tags by replacing them with newlines
            for br in cell.find_all('br'):
                br.replace_with('\n')

            # Get text and handle entities
            text = cell.get_text(strip=False)
            text = replace_html_entities(text)
            return text.strip()

        def process_cell(cell: Tag) -> List[TableCell]:
            """Process cell preserving exact colspan and positioning values correctly"""
            try:
                colspan = int(cell.get('colspan', '1'))
            except ValueError:
                colspan = 1
            style = parse_style(cell.get('style', ''))

            text = extract_cell_text(cell)

            # If this is a right-aligned cell with colspan > 1 (like percentage values)
            if style.text_align == 'right' and colspan > 1:
                # Create empty cells for all but last column of colspan
                cells = [
                    TableCell(content='', colspan=1, align='right', is_currency=False)
                    for _ in range(colspan - 1)
                ]
                # Add actual value in last column
                cells.append(TableCell(
                    content=text,
                    colspan=1,
                    align='right',
                    is_currency=False
                ))
                return cells

            # For single cells
            return [TableCell(
                content=text,
                colspan=colspan,
                align=style.text_align or 'left',
                is_currency=text.startswith('$')
            )]


        def process_row(row: Tag) -> TableRow:
            """Process row preserving cell structure"""
            cells = []
            # Find direct child cells only to avoid nested table conflicts
            for td in row.find_all(['td', 'th'], recursive=False):
                # Check if cell contains a nested table
                nested_table = td.find('table')
                if nested_table:
                    # Create a TableNode from the nested table using _process_table
                    table_node = self._process_table(nested_table)
                    if table_node:
                        # Store the table node in the cell content
                        cells.extend([TableCell(
                            content=table_node,  # We'll need to handle this special content later
                            colspan=int(td.get('colspan', '1')),
                            align=td.get('align', 'left')
                        )])

                else:
                    cells.extend(process_cell(td))

            return TableRow(cells=cells, is_header=row.find_parent('thead') is not None)

        # Process all rows (including those nested in tbody, thead, tfoot)
        rows = []

        # First, try to find direct child tr elements
        direct_trs = element.find_all('tr', recursive=False)
        if direct_trs:
            # If we found direct tr elements, use them
            for tr in direct_trs:
                row = process_row(tr)
                if row.cells:
                    rows.append(row)
        else:
            # If no direct tr elements, look in tbody, thead, tfoot children
            for section in element.find_all(['tbody', 'thead', 'tfoot'], recursive=False):
                for tr in section.find_all('tr', recursive=False):
                    row = process_row(tr)
                    if row.cells:
                        rows.append(row)

        if rows:
            # Create metadata from table attributes
            metadata = {
                'id': element.get('id', ''),
                'class': element.get('class', []),
                'data_attrs': {
                    k: v for k, v in element.attrs.items()
                    if k.startswith('data-')
                }
            }

            return create_node(
                'table',
                rows,
                parse_style(element.get('style', '')),
                metadata=metadata
            )

        return None

    def _process_paragraph(self, element: Tag, style: StyleInfo) -> Optional[BaseNode]:
        """Process a paragraph element with inherited styles"""
        text_parts = []
        last_was_text = False

        for child in element.children:
            if isinstance(child, NavigableString):
                text = str(child)
                if text.strip():
                    text_parts.append(text)
                    last_was_text = True
                elif text.isspace() and last_was_text:
                    text_parts.append(' ')
            elif isinstance(child, Tag):
                if child.name == 'br':
                    text_parts.append('\n')
                    last_was_text = False
                elif child.name in ['span', 'font', 'strong', 'em', 'b', 'i', 'a']:
                    text = self._get_text_with_spacing(child)
                    if text.strip():
                        text_parts.append(text.strip())
                        last_was_text = True

        if not text_parts:
            return None

        # Join all parts and normalize whitespace while preserving intentional breaks
        text = ''.join(text_parts)
        # Split into lines, normalize each line's whitespace, then rejoin
        lines = [' '.join(line.split()) for line in text.split('\n')]
        text = '\n'.join(line for line in lines if line)

        if text.strip():
            return create_node(
                type_='text_block',
                content=text,
                style=style
            )

        return None

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
        style = parse_style(element.get('style', ''))
        if style.display:
            return style.display != 'inline'

        # Default block elements
        block_elements = {
            'div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'ul', 'ol', 'li', 'blockquote', 'pre', 'hr',
            'table', 'form', 'fieldset', 'address'
        }

        return element.name in block_elements and 'float:left' not in element.get('style', '')


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
        style = parse_style(element.get('style', ''))

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
        style = parse_style(element.get('style', ''))
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
        if element.name == 'table':
            return ''

        texts = []
        last_was_text = False

        for child in element.children:
            if isinstance(child, NavigableString):
                text = self._clean_text(str(child))
                if text.strip():
                    texts.append(text.strip())
                    last_was_text = True
                elif text.isspace() and last_was_text:
                    texts.append(' ')
            elif child.name == 'br':
                texts.append('\n')
                last_was_text = False
            elif child.name == 'table':
                continue
            else:
                child_text = self._get_text_with_spacing(child)
                if child_text.strip():
                    # Only add space if needed
                    if texts and last_was_text and not texts[-1].endswith(' ') and not child_text.startswith(' '):
                        texts.append(' ')
                    texts.append(child_text.strip())
                    last_was_text = True

        return ''.join(texts)

    def _merge_adjacent_nodes(self, nodes: List[BaseNode]) -> List[BaseNode]:
        """Merge adjacent nodes while preserving styling from both nodes"""
        if not nodes:
            return []

        def merge_styles(style1: StyleInfo, style2: StyleInfo) -> StyleInfo:
            """Merge two styles intelligently"""
            # Start with a new style object
            merged = StyleInfo()

            # For each style attribute, take the non-None value
            # If both have values, use the more specific one
            merged.display = style2.display or style1.display
            merged.margin_top = style1.margin_top  # Keep first node's top margin
            merged.margin_bottom = style2.margin_bottom  # Keep second node's bottom margin

            # For font properties, prefer the second node's style if it's different
            # This preserves intentional style changes in the second block
            if style2.font_size and style2.font_size != style1.font_size:
                merged.font_size = style2.font_size
            else:
                merged.font_size = style1.font_size

            if style2.font_weight and style2.font_weight != style1.font_weight:
                merged.font_weight = style2.font_weight
            else:
                merged.font_weight = style1.font_weight

            # For alignment, if they differ, don't merge
            if style1.text_align != style2.text_align:
                return None
            merged.text_align = style1.text_align

            # Improved width handling
            if style1.width and style2.width:
                # If units differ, prefer the larger width's unit
                if style1.width.unit != style2.width.unit:
                    # Convert both to pixels for comparison
                                        # This is a simplified conversion - you might want to use the existing
                    # Width.to_chars method for more accurate conversion
                    w1_px = _to_pixels(style1.width)
                    w2_px = _to_pixels(style2.width)

                    # If one width is significantly smaller (like a bullet point)
                    # use the larger width
                    if w1_px < w2_px * 0.3:  # First node is much smaller
                        merged.width = style2.width
                    elif w2_px < w1_px * 0.3:  # Second node is much smaller
                        merged.width = style1.width
                    else:
                        # Widths are comparable, use the second node's width
                        merged.width = style2.width
                else:
                    # Same units, apply the same logic
                    if style1.width.value < style2.width.value * 0.3:
                        merged.width = style2.width
                    elif style2.width.value < style1.width.value * 0.3:
                        merged.width = style1.width
                    else:
                        merged.width = style2.width
            else:
                # If only one has width, use that
                merged.width = style2.width or style1.width

            merged.text_decoration = style2.text_decoration or style1.text_decoration
            merged.line_height = style2.line_height or style1.line_height

            return merged

        def _to_pixels(width: Width) -> float:
            """Convert width to pixels for comparison"""
            # Conversion factors (approximate)
            conversions = {
                'px': 1,
                'pt': 1.333,  # 1pt ≈ 1.333px
                'in': 96,  # 1in = 96px
                'cm': 37.795,  # 1cm ≈ 37.795px
                'mm': 3.7795,  # 1mm ≈ 3.7795px
                '%': 1  # Handle percentages separately
            }
            return width.value * conversions.get(width.unit, 1)

        def can_merge_nodes(node1: BaseNode, node2: BaseNode) -> bool:
            """Determine if two nodes can be safely merged"""
            if node1.type != 'text_block' or node2.type != 'text_block':
                return False

            # Don't merge if either has special metadata
            if node1.metadata or node2.metadata:
                return False

            # Try to merge styles
            merged_style = merge_styles(node1.style, node2.style)
            if merged_style is None:
                return False

            return True

        merged = []
        current = None

        for node in nodes:
            if not current:
                current = node
                continue

            if can_merge_nodes(current, node):
                merged_style = merge_styles(current.style, node.style)
                # Create new merged text block with the combined style
                merged_content = f"{current.content}\n\n{node.content}"
                current = create_node(
                    'text_block',
                    merged_content,
                    merged_style
                )
            else:
                merged.append(current)
                current = node

        if current:
            merged.append(current)

        return merged


    def _similar_styles(self, style1: StyleInfo, style2: StyleInfo) -> bool:
        # Compare relevant style attributes to determine if they're similar
        return (
                style1.font_size == style2.font_size and
                style1.font_weight == style2.font_weight and
                style1.text_align == style2.text_align
        )




