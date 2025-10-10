"""
Table-related nodes for the document tree.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union
import pandas as pd
from rich import box
from rich.table import Table as RichTable
from edgar.richtools import rich_to_text
from edgar.documents.nodes import Node
from edgar.documents.types import NodeType, TableType
from edgar.documents.cache_mixin import CacheableMixin
from edgar.documents.table_utils import process_table_matrix


@dataclass
class Cell:
    """Table cell representation."""
    content: Union[str, Node]
    colspan: int = 1
    rowspan: int = 1
    is_header: bool = False
    align: Optional[str] = None
    
    def text(self) -> str:
        """Extract text from cell."""
        if isinstance(self.content, str):
            return self.content
        elif isinstance(self.content, Node):
            return self.content.text()
        return ''
    
    def html(self) -> str:
        """Generate cell HTML."""
        tag = 'th' if self.is_header else 'td'
        text = self.text()
        
        attrs = []
        if self.colspan > 1:
            attrs.append(f'colspan="{self.colspan}"')
        if self.rowspan > 1:
            attrs.append(f'rowspan="{self.rowspan}"')
        if self.align:
            attrs.append(f'align="{self.align}"')
        
        attr_str = ' ' + ' '.join(attrs) if attrs else ''
        return f'<{tag}{attr_str}>{text}</{tag}>'
    
    @property
    def is_numeric(self) -> bool:
        """Check if cell contains numeric data."""
        text = self.text().strip()
        if not text:
            return False
        
        # Em dash and similar symbols are numeric placeholders (like null/zero)
        if text in ['—', '–', '-', '--', 'N/A', 'n/a', 'NM', 'nm']:
            return True
        
        # Remove common formatting
        clean_text = text.replace(',', '').replace('$', '').replace('%', '')
        clean_text = clean_text.replace('(', '-').replace(')', '')
        
        try:
            float(clean_text)
            return True
        except ValueError:
            return False
    
    @property
    def numeric_value(self) -> Optional[float]:
        """Get numeric value if cell is numeric."""
        if not self.is_numeric:
            return None
        
        text = self.text().strip()
        
        # Em dash and similar symbols represent zero/null
        if text in ['—', '–', '-', '--', 'N/A', 'n/a', 'NM', 'nm']:
            return 0.0
        
        clean_text = text.replace(',', '').replace('$', '').replace('%', '')
        clean_text = clean_text.replace('(', '-').replace(')', '')
        
        try:
            return float(clean_text)
        except ValueError:
            return None


@dataclass
class Row:
    """Table row representation."""
    cells: List[Cell]
    is_header: bool = False
    
    def text(self) -> str:
        """Extract row text."""
        return ' | '.join(cell.text() for cell in self.cells)
    
    def html(self) -> str:
        """Generate row HTML."""
        cells_html = ''.join(cell.html() for cell in self.cells)
        return f'<tr>{cells_html}</tr>'
    
    @property
    def is_numeric_row(self) -> bool:
        """Check if row contains mostly numeric data."""
        numeric_count = sum(1 for cell in self.cells if cell.is_numeric)
        return numeric_count > len(self.cells) / 2
    
    @property
    def is_total_row(self) -> bool:
        """Check if this might be a total row."""
        # Check if the first cell contains total-related keywords
        # This is more accurate than checking the entire row text
        if not self.cells:
            return False
        
        first_cell_text = self.cells[0].text().lower().strip()
        
        # Check if the first cell starts with or is exactly a total keyword
        total_keywords = ['total', 'sum', 'subtotal', 'grand total', 'net total']
        
        # Check for exact match or starts with total keyword
        for keyword in total_keywords:
            if first_cell_text == keyword or first_cell_text.startswith(keyword + ' '):
                return True
        
        # Also check for patterns like "Total revenue", "Total expenses", etc.
        if first_cell_text.startswith('total '):
            return True
            
        return False


@dataclass
class TableNode(Node, CacheableMixin):
    """
    Table node with structured data.

    Supports complex table structures with multi-level headers,
    merged cells, and semantic understanding.
    """
    type: NodeType = field(default=NodeType.TABLE, init=False)
    headers: List[List[Cell]] = field(default_factory=list)
    rows: List[Row] = field(default_factory=list)
    footer: List[Row] = field(default_factory=list)
    table_type: TableType = TableType.GENERAL

    # Table metadata
    caption: Optional[str] = None
    summary: Optional[str] = None

    @property
    def semantic_type(self) -> TableType:
        """Get semantic type of table (alias for table_type)."""
        return self.table_type

    @semantic_type.setter
    def semantic_type(self, value: TableType):
        """Set semantic type of table."""
        self.table_type = value

    def text(self) -> str:
        """Convert table to text representation with caching for performance."""
        def _generate_text():
            # Check if we should use fast rendering
            config = getattr(self, '_config', None)
            if config and getattr(config, 'fast_table_rendering', False):
                return self._fast_text_rendering()
            else:
                # Use Rich renderer (current behavior)
                rich_table = self.render(width=195)
                return rich_to_text(rich_table)

        return self._get_cached_text(_generate_text)
    
    def _fast_text_rendering(self) -> str:
        """
        Fast text rendering using FastTableRenderer with simple() style (clean, borderless).

        The simple style matches Rich's box.SIMPLE appearance:
        - No outer borders
        - No column separators
        - Single horizontal line under header
        - Space-separated columns
        - Clean, professional output

        For performance-critical operations (30x+ faster than Rich rendering).
        """
        from edgar.documents.renderers.fast_table import FastTableRenderer, TableStyle

        # Create fast renderer with simple() style as default
        renderer = FastTableRenderer(TableStyle.simple())

        # Render the table
        return renderer.render_table_node(self)

    
    def _fix_header_misclassification(self):
        """
        Note: We do NOT reorder rows as this would change the structure of the filing.
        This method is kept for compatibility but does minimal processing.
        """
        # We don't want to reorder rows as it changes the filing structure
        # The rendering should handle misclassified headers appropriately
        pass
    
    def render(self, width: Optional[int] = None) -> RichTable:
        """
        Render table using rich.table.Table for beautiful console output.
        
        Args:
            width: Optional max width for the table
            
        Returns:
            Rich Table object for console rendering
        """
        from edgar.documents.utils.table_matrix import TableMatrix, ColumnAnalyzer
        from edgar.documents.utils.currency_merger import CurrencyColumnMerger
        
        # Fix header misclassification issues before rendering
        self._fix_header_misclassification()

        # Normalize header row lengths to prevent alignment issues
        # When header rows have different cell counts (e.g., 14 vs 17 cells),
        # the rendering can misalign columns. Pad shorter rows with empty cells.
        if self.headers and len(self.headers) > 1:
            max_header_cols = max(len(h) for h in self.headers)
            for header_row in self.headers:
                if len(header_row) < max_header_cols:
                    # Pad with empty cells to match the longest header row
                    padding_needed = max_header_cols - len(header_row)
                    header_row.extend([Cell(content='') for _ in range(padding_needed)])

        # Build matrix to handle colspan/rowspan WITHOUT merging currencies
        # Old parser keeps $ as separate cells to maintain alignment
        matrix = TableMatrix()
        clean_matrix = process_table_matrix(matrix, self.headers, self.rows)
        
        # Create rich table with styling (following old parser approach)
        # Use minimal padding when we have symbol columns
        has_symbols = self._has_symbol_columns(clean_matrix) if hasattr(self, '_has_symbol_columns') else False
        padding_config = (0, 0) if has_symbols else (0, 1)
        
        # Don't force table to full width - let it be compact based on content
        # Only use width as a maximum constraint if the table would be too wide
        table = RichTable(
            title=self.caption if self.caption else None,
            box=box.SIMPLE,
            border_style="blue",
            header_style="bold cyan",
            padding=padding_config,  # Minimal padding for tables with symbols
            collapse_padding=True,
            width=None,  # Let Rich auto-size based on column widths
            show_header=bool(self.headers),
            show_footer=bool(self.footer)
        )
        
        # Detect column alignments
        column_alignments = self._detect_column_alignments(clean_matrix)
        
        # Calculate optimal column widths based on content and available width
        # Use smart widths if a width is specified, otherwise use content-based widths
        if width and width > 50:  # Only use smart widths for reasonable target widths
            calculated_widths = self._calculate_smart_widths(clean_matrix, table_width=width)
        else:
            # This creates a compact table that fits its content naturally
            calculated_widths = self._calculate_optimal_content_widths(clean_matrix)
        
        # Add columns with headers
        if self.headers:
            # Merge all header rows into single headers with newlines (like old parser)
            merged_headers = []
            
            # For each column, merge all header rows
            for col_idx in range(clean_matrix.col_count):
                header_parts = []
                for row_idx in range(len(self.headers)):
                    expanded_row = clean_matrix.get_expanded_row(row_idx)
                    if col_idx < len(expanded_row):
                        cell = expanded_row[col_idx]
                        if cell:
                            text = cell.text().strip()
                            # Skip empty cells and lone $ symbols (like old parser)
                            if text and text != '$':
                                header_parts.append(text)
                
                # Join with newlines to create multi-line header
                merged_header = '\n'.join(header_parts)
                merged_headers.append(merged_header)
            
            # Add columns with merged headers
            for col_idx, header_text in enumerate(merged_headers):
                alignment = column_alignments[col_idx] if col_idx < len(column_alignments) else "left"
                
                # Use calculated widths for optimal compact display
                if col_idx < len(calculated_widths):
                    col_width = calculated_widths[col_idx]
                    table.add_column(
                        header=header_text,
                        justify=alignment,
                        vertical="middle",
                        width=col_width,
                        overflow="fold"  # Wrap text instead of truncating
                    )
        else:
            # No headers, create generic columns
            for col_idx in range(clean_matrix.col_count):
                alignment = column_alignments[col_idx] if col_idx < len(column_alignments) else "left"
                
                if col_idx < len(calculated_widths):
                    col_width = calculated_widths[col_idx]
                    table.add_column(
                        header=f"Col{col_idx+1}",
                        justify=alignment,
                        vertical="middle",
                        width=col_width,
                        overflow="ellipsis"
                    )
        
        # Add data rows
        start_row = len(self.headers) if self.headers else 0
        for row_idx in range(start_row, clean_matrix.row_count):
            expanded_row = clean_matrix.get_expanded_row(row_idx)
            row_data = []
            
            for cell in expanded_row:
                if cell is not None:
                    text = cell.text()
                    # Format numbers nicely
                    if cell.is_numeric and not text.startswith('$'):
                        # Preserve em dashes and similar placeholders
                        if text.strip() in ['—', '–', '-', '--', 'N/A', 'n/a', 'NM', 'nm']:
                            # Keep original text for these placeholders
                            pass
                        else:
                            # Check if it's a percentage
                            is_percentage = text.endswith('%')
                            # Check if it's likely a year (4-digit number between 1900-2100)
                            is_likely_year = False
                            try:
                                num_val = cell.numeric_value
                                if num_val is not None:
                                    # Check if it's a 4-digit year-like number
                                    if 1900 <= num_val <= 2100 and num_val == int(num_val):
                                        # Also check if the original text is exactly 4 digits
                                        clean_text = text.strip().replace('%', '')
                                        if len(clean_text) == 4 and clean_text.isdigit():
                                            is_likely_year = True
                                    
                                    # Don't format years with thousands separator
                                    if is_likely_year:
                                        text = str(int(num_val))
                                    elif num_val < 0:
                                        text = f"({abs(num_val):,.0f})"
                                    else:
                                        text = f"{num_val:,.0f}"
                                    # Re-add percentage symbol if it was there
                                    if is_percentage:
                                        text = f"{text}%"
                            except:
                                pass
                    row_data.append(text)
                else:
                    row_data.append("")
            
            # Add row without special styling
            table.add_row(*row_data)
        
        # Add footer rows if present
        if self.footer:
            for row in self.footer:
                footer_data = [cell.text() for cell in row.cells]
                table.add_row(*footer_data, style="dim italic")
        
        return table
    
    def _has_symbol_columns(self, matrix) -> bool:
        """Check if table has columns that contain only symbols like $ or %."""
        header_row_count = len(self.headers) if self.headers else 0
        
        for col_idx in range(matrix.col_count):
            is_symbol_col = True
            has_content = False
            
            for row_idx in range(header_row_count, matrix.row_count):
                cell = matrix.get_cell(row_idx, col_idx)
                if cell and cell.text().strip():
                    has_content = True
                    text = cell.text().strip()
                    # Check if it's not just a symbol
                    if text not in ['$', '%', '€', '£', '¥', '—', '-', '–', '(', ')'] and len(text) > 2:
                        is_symbol_col = False
                        break
            
            if has_content and is_symbol_col:
                return True
        
        return False

    def _calculate_newline_safe_width(self, text: str, base_width: int) -> int:
        """
        Calculate width that guarantees Rich won't re-wrap multi-line text.

        If text contains newlines, ensures column width is sufficient for
        the longest line plus buffer for Rich's padding and borders.
        This preserves semantic line breaks in merged headers (similar to
        old parser's newline preservation approach).

        Args:
            text: Text content (may contain \n)
            base_width: Base width from content measurement

        Returns:
            Safe width that prevents re-wrapping
        """
        if not text or '\n' not in text:
            return base_width

        # Multi-line content detected - ensure Rich won't re-wrap
        lines = text.split('\n')
        max_line_len = max(len(line) for line in lines)

        # Add buffer for Rich's internal processing:
        # +2 for column padding (1 char each side)
        # +2 for safety margin (Rich's internal calculations)
        buffer = 4

        return max(max_line_len + buffer, base_width)

    def _calculate_optimal_content_widths(self, matrix) -> List[int]:
        """
        Calculate optimal column widths based on actual content.
        Creates compact tables that fit their content naturally.
        
        Args:
            matrix: TableMatrix with the table data
            
        Returns:
            List of optimal column widths
        """
        widths = []
        header_row_count = len(self.headers) if self.headers else 0
        
        for col_idx in range(matrix.col_count):
            max_width = 1  # Minimum width
            header_max_width = 1  # Track header width separately
            data_max_width = 1  # Track data width separately
            has_multiline = False  # Track if column has multi-line content
            multiline_text = ""  # Store representative multi-line text

            # Check all cells in column
            for row_idx in range(matrix.row_count):
                # Get the matrix cell to check if it's spanned
                matrix_cell = matrix.matrix[row_idx][col_idx] if row_idx < len(matrix.matrix) and col_idx < len(matrix.matrix[row_idx]) else None
                
                cell = matrix.get_cell(row_idx, col_idx)
                if cell is not None:
                    text = cell.text().strip()
                    if text:
                        # Check if this is a spanned cell (part of colspan)
                        # If it's spanned and not the origin column, don't count its full width
                        is_spanned = matrix_cell and matrix_cell.is_spanned
                        
                        if is_spanned:
                            # For spanned cells, don't use the text width
                            # These are covered by the origin cell
                            continue

                        # Track if this cell has multi-line content
                        if '\n' in text:
                            has_multiline = True
                            # Store the multi-line text for width calculation
                            if not multiline_text or len(text) > len(multiline_text):
                                multiline_text = text

                        # For multi-line text (headers), get the max line width
                        lines = text.split('\n')
                        for line in lines:
                            line_len = len(line)
                            max_width = max(max_width, line_len)
                            # Consider all rows up to row 3 as potential headers for width calculation
                            # This handles tables with multi-row headers like Table 52
                            if row_idx < max(header_row_count, 3):
                                header_max_width = max(header_max_width, line_len)
                            else:
                                data_max_width = max(data_max_width, line_len)
            
            # Add appropriate padding based on content type
            col_width = max_width  # Start with measured max width

            if max_width <= 1:
                # Empty or single char (like symbols)
                col_width = max_width
            elif max_width <= 10:
                # Short to medium content (numbers, percentages, short headers)
                # Give headers adequate room for readability
                if header_max_width >= 7:
                    # Headers like "Accrued", "Expected" need breathing room
                    col_width = max_width + 3
                elif header_max_width > 5:
                    col_width = max_width + 2
                else:
                    col_width = max_width + 1
            elif max_width <= 15:
                # Medium content
                col_width = max_width + 2
            else:
                # Long content (text descriptions or long headers)
                # Check if this is primarily a text column (not numeric)
                is_text_column = False
                cells_checked = 0
                # Check more rows and skip empty ones
                for row_idx in range(header_row_count, matrix.row_count):
                    if cells_checked >= 5:  # Check up to 5 non-empty cells
                        break
                    test_cell = matrix.get_cell(row_idx, col_idx)
                    if test_cell and test_cell.text().strip():
                        cells_checked += 1
                        # If it's not numeric, it's a text column
                        if not test_cell.is_numeric:
                            is_text_column = True
                            break

                if is_text_column:
                    # Allow more width for text columns
                    # For very long text, allow wrapping at a reasonable width
                    if max_width > 80:
                        # Very long text - wrap at 70 chars
                        col_width = 70
                    elif max_width > 50:
                        # Long text - give it generous space
                        col_width = min(max_width + 3, 65)
                    else:
                        # Medium text
                        col_width = max_width + 3
                else:
                    # Numeric columns - need to balance header and data widths
                    # If header is much longer than data, give it reasonable space
                    # but not excessive
                    if header_max_width > data_max_width * 2:
                        # Header is much longer than data
                        # Give enough space for header but allow some wrapping
                        col_width = min(header_max_width + 1, 25)
                    else:
                        # Header and data are similar or data is longer
                        col_width = min(max_width + 2, 35)

            # Apply newline-safe width if column contains multi-line content
            # This prevents Rich from re-wrapping merged headers
            if has_multiline and multiline_text:
                col_width = self._calculate_newline_safe_width(multiline_text, col_width)

            widths.append(col_width)
        
        return widths
    
    def _calculate_smart_widths(self, matrix, table_width: Optional[int] = None) -> List[int]:
        """
        Calculate smart column widths for complex tables.
        
        Args:
            matrix: TableMatrix with the table data
            table_width: Optional target table width (used as maximum, not target)
            
        Returns:
            List of column widths
        """
        if table_width is None:
            table_width = 120  # Default reasonable width
            
        # Start with content-based widths
        content_widths = []
        header_row_count = len(self.headers) if self.headers else 0
        
        for col_idx in range(matrix.col_count):
            max_width = 1  # Minimum width
            
            # Check all cells in column including multi-line headers
            for row_idx in range(matrix.row_count):
                # Get the matrix cell to check if it's spanned
                matrix_cell = matrix.matrix[row_idx][col_idx] if row_idx < len(matrix.matrix) and col_idx < len(matrix.matrix[row_idx]) else None
                
                # Skip spanned cells (they're covered by the origin cell)
                is_spanned = matrix_cell and matrix_cell.is_spanned
                if is_spanned:
                    continue
                    
                cell = matrix.get_cell(row_idx, col_idx)
                if cell is not None:
                    text = cell.text().strip()
                    if text:
                        # For multi-line text, get the max line width
                        lines = text.split('\n')
                        for line in lines:
                            max_width = max(max_width, len(line))
            
            content_widths.append(max_width)
        
        # For compact tables, just use natural widths with some padding
        # Don't try to expand to fill the entire width
        compact_widths = []
        for width in content_widths:
            # Add a bit of padding for readability but keep it compact
            if width <= 2:  # Symbol columns
                compact_widths.append(width)
            elif width <= 10:  # Short numeric columns
                compact_widths.append(width + 1)
            else:  # Text columns
                compact_widths.append(min(width + 2, 40))  # Cap at 40 for very long text
        
        # Check if compact table fits within maximum width
        padding_per_col = 2  # Rich adds padding
        total_padding = padding_per_col * len(compact_widths)
        separators = len(compact_widths) - 1  # Column separators
        total_width = sum(compact_widths) + total_padding + separators + 4  # 4 for table borders
        
        if total_width <= table_width:
            # Compact table fits, use it
            return compact_widths
        
        # If it doesn't fit, we need to compress intelligently
        available_width = table_width - total_padding - separators - 4
        
        # Need to compress - use smarter strategy
        final_widths = []
        
        # First pass: identify column types and minimum widths
        col_types = []
        is_first_text_col = True  # Track first text column (usually description/label)
        
        for col_idx, natural_width in enumerate(content_widths):
            # Check if column is empty or just whitespace
            is_empty = natural_width == 1 or all(
                not matrix.get_cell(row_idx, col_idx) or not matrix.get_cell(row_idx, col_idx).text().strip()
                for row_idx in range(matrix.row_count)
            )
            
            if is_empty:
                col_types.append('empty')
                final_widths.append(1)  # Minimal width for empty columns but not zero
                continue
            
            # Get the header content width for this column by looking at the merged header
            # This is how headers will actually be displayed (same logic as in render method)
            header_parts = []
            for row_idx in range(header_row_count):
                expanded_row = matrix.get_expanded_row(row_idx)
                if col_idx < len(expanded_row):
                    cell = expanded_row[col_idx]
                    if cell:
                        text = cell.text().strip()
                        # Skip empty cells and lone $ symbols (like render method does)
                        if text and text != '$':
                            header_parts.append(text)
            
            # Calculate width needed for merged header
            header_width = 1
            merged_header = ""
            if header_parts:
                merged_header = '\n'.join(header_parts)
                lines = merged_header.split('\n')
                for line in lines:
                    header_width = max(header_width, len(line))

                # Apply newline-safe buffer if header is multi-line
                # This prevents Rich from re-wrapping merged headers
                if '\n' in merged_header:
                    header_width = self._calculate_newline_safe_width(merged_header, header_width)
            
            # Check if this is a symbol column (%, $, etc)
            is_symbol = True
            is_numeric = True
            sample_values = []
            
            for row_idx in range(header_row_count, min(matrix.row_count, header_row_count + 5)):
                cell = matrix.get_cell(row_idx, col_idx)
                if cell and cell.text().strip():
                    text = cell.text().strip()
                    sample_values.append(text)
                    if text not in ['%', '$', '—', '-', '(', ')']:
                        is_symbol = False
                    if not (text.replace(',', '').replace('.', '').replace('(', '').replace(')', '').replace('$', '').replace('%', '').replace('-', '').replace(' ', '').isdigit()):
                        is_numeric = False
            
            if is_symbol:
                col_types.append('symbol')
                # Symbol columns still need space for their headers
                # Use header width if there's a meaningful header, otherwise minimal
                if header_width > 2:  # Has a real header, not just a symbol
                    final_widths.append(max(header_width, 7))  # At least 7 chars for headers
                else:
                    final_widths.append(1)  # True symbol column with no header
            elif is_numeric or any('$' in v for v in sample_values):
                col_types.append('numeric')
                # Financial numbers need reasonable space to avoid wrapping
                # Must be at least as wide as the header, but use at least 10 chars
                min_numeric_width = max(10, header_width)
                final_widths.append(min(natural_width, max(min_numeric_width, natural_width // 2)))
            else:
                col_types.append('text')
                # First text column (usually row labels) gets more space
                if is_first_text_col and col_idx == 0:
                    # Give generous space to the description column
                    # But cap at 35 to leave room for data columns
                    min_text_width = max(25, header_width)
                    final_widths.append(min(natural_width, max(min_text_width, min(35, natural_width))))
                    is_first_text_col = False
                else:
                    # Other text columns get moderate space, but at least as wide as header
                    min_other_width = max(12, header_width)
                    final_widths.append(min(natural_width, max(min_other_width, natural_width // 2)))
        
        # Second pass: redistribute remaining space if we're still over
        current_total = sum(final_widths)
        if current_total > available_width:
            # Need to compress more
            reduction_needed = current_total - available_width
            
            # Sort columns by width (largest first) for reduction
            # But prioritize reducing text columns before numeric columns
            width_indices = sorted(range(len(final_widths)), 
                                   key=lambda i: (col_types[i] != 'text', final_widths[i]), 
                                   reverse=True)
            
            for idx in width_indices:
                if col_types[idx] not in ['symbol', 'empty'] and final_widths[idx] > 8:
                    # Reduce this column but maintain minimum readable width
                    # First text column (descriptions): minimum 20 chars
                    # Other text columns: minimum 10 chars
                    # Numeric columns: minimum 8 chars
                    if col_types[idx] == 'text' and idx == 0:
                        min_width = 20
                    elif col_types[idx] == 'text':
                        min_width = 10
                    else:
                        min_width = 8
                    
                    reduction = min(final_widths[idx] - min_width, reduction_needed)
                    if reduction > 0:
                        final_widths[idx] -= reduction
                        reduction_needed -= reduction
                        if reduction_needed <= 0:
                            break
        elif current_total < available_width - 10:
            # We have extra space - distribute it to columns that need it most
            extra_space = available_width - current_total
            
            # Priority: Give extra space to columns that are below their natural width
            # Focus on numeric columns that might have wrapped values
            for col_idx, (final_w, natural_w) in enumerate(zip(final_widths, content_widths)):
                if col_types[col_idx] == 'numeric' and final_w < natural_w:
                    # Give back some space to numeric columns
                    space_to_add = min(natural_w - final_w, extra_space // 2)
                    final_widths[col_idx] += space_to_add
                    extra_space -= space_to_add
                    if extra_space <= 0:
                        break
        
        return final_widths
    
    def _calculate_optimal_widths(self, matrix) -> List[int]:
        """
        Calculate optimal column widths based on content.
        
        Returns:
            List of optimal widths for each column
        """
        widths = []
        
        for col_idx in range(matrix.col_count):
            max_width = 0
            is_symbol_column = True  # Assume it's a symbol column until proven otherwise
            all_values = []
            
            # Check all cells in column to find max width needed
            # Skip header rows when determining if it's a symbol column
            header_row_count = len(self.headers) if self.headers else 0
            
            for row_idx in range(matrix.row_count):
                cell = matrix.get_cell(row_idx, col_idx)
                if cell is not None:
                    text = cell.text().strip()
                    if text:
                        all_values.append(text)
                        max_width = max(max_width, len(text))
                        
                        # Only check data rows (not headers) for symbol detection
                        if row_idx >= header_row_count:
                            # Check if this is NOT a symbol
                            if text not in ['$', '%', '€', '£', '¥', '—', '-', '–', '']:
                                # If it's not a symbol and has alphanumeric content, it's not a symbol column
                                if any(c.isalnum() for c in text) and len(text) > 2:
                                    is_symbol_column = False
            
            # Determine width based on column type
            if max_width == 0:
                # Empty column
                widths.append(1)
            elif is_symbol_column:
                # Column contains only symbols (%, $, etc.)
                # Use minimal width regardless of header
                widths.append(1)  # Even tighter for symbols
            elif max_width <= 3:
                # Very short content (like "2", "(3)", "—")
                # Check if it's mostly numbers or symbols in data rows
                data_values = [v for v in all_values[header_row_count:] if v]
                if all(len(v) <= 3 for v in data_values):
                    # All data values are 3 chars or less
                    widths.append(max_width + 1)  # Just enough space
                else:
                    widths.append(max_width + 2)
            else:
                # Regular content - use actual width needed
                # But cap very long columns to prevent table explosion
                widths.append(min(max_width, 30))
        
        return widths
    
    def _detect_column_alignments(self, matrix) -> List[str]:
        """Detect whether columns should be left or right aligned."""
        alignments = []
        
        for col_idx in range(matrix.col_count):
            numeric_count = 0
            total_count = 0
            
            # Check data rows (skip headers)
            start_row = len(self.headers) if self.headers else 0
            for row_idx in range(start_row, matrix.row_count):
                cell = matrix.get_cell(row_idx, col_idx)
                if cell is not None and cell.text().strip():
                    total_count += 1
                    if cell.is_numeric:
                        numeric_count += 1
            
            # If more than 60% numeric, right-align
            if total_count > 0 and numeric_count / total_count > 0.6:
                alignments.append("right")
            else:
                alignments.append("left")
        
        return alignments
    
    def html(self) -> str:
        """Generate table HTML."""
        parts = ['<table>']
        
        # Add caption
        if self.caption:
            parts.append(f'<caption>{self.caption}</caption>')
        
        # Add header
        if self.headers:
            parts.append('<thead>')
            for header_row in self.headers:
                cells = ''.join(cell.html() for cell in header_row)
                parts.append(f'<tr>{cells}</tr>')
            parts.append('</thead>')
        
        # Add body
        parts.append('<tbody>')
        for row in self.rows:
            parts.append(row.html())
        parts.append('</tbody>')
        
        # Add footer
        if self.footer:
            parts.append('<tfoot>')
            for row in self.footer:
                parts.append(row.html())
            parts.append('</tfoot>')
        
        parts.append('</table>')
        return '\n'.join(parts)
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert table to pandas DataFrame with proper colspan/rowspan handling."""
        from edgar.documents.utils.table_matrix import TableMatrix

        # Build matrix to handle colspan/rowspan WITHOUT merging currencies
        # Old parser keeps $ as separate cells to maintain alignment
        matrix = TableMatrix()
        clean_matrix = process_table_matrix(matrix, self.headers, self.rows)
        
        # Extract headers with proper alignment
        if self.headers:
            # Get expanded headers from matrix
            header_arrays = []
            num_header_rows = len(self.headers)
            
            for row_idx in range(num_header_rows):
                expanded_row = clean_matrix.get_expanded_row(row_idx)
                header_texts = []
                
                prev_text = ''
                for i, cell in enumerate(expanded_row):
                    if cell is not None:
                        text = cell.text().strip()
                        header_texts.append(text)
                        prev_text = text
                    else:
                        # For spanned cells in first row, repeat the spanning header
                        # For subsequent rows, use empty string
                        if row_idx == 0 and prev_text:
                            header_texts.append(prev_text)
                        else:
                            header_texts.append('')
                
                # Fill in spanned cells with parent header text for MultiIndex
                if row_idx > 0 and header_arrays:
                    # For lower level headers, inherit from parent if empty
                    prev_header = header_arrays[-1]
                    for i, text in enumerate(header_texts):
                        if text == '' and i < len(prev_header):
                            # Check if this is under a spanned parent header
                            for j in range(i, -1, -1):
                                if prev_header[j] != '':
                                    # Keep empty to show it's under parent
                                    break
                
                header_arrays.append(header_texts)
            
            # Create column index
            if len(header_arrays) > 1:
                # Multi-level headers - create MultiIndex
                # Clean up arrays to same length
                max_len = max(len(arr) for arr in header_arrays)
                for arr in header_arrays:
                    while len(arr) < max_len:
                        arr.append('')
                
                df_columns = pd.MultiIndex.from_arrays(header_arrays)
            else:
                # Single level headers
                df_columns = header_arrays[0] if header_arrays else []
        else:
            # No headers, use numeric columns
            df_columns = list(range(clean_matrix.col_count))
        
        # Extract data rows with proper alignment
        data = []
        start_row = len(self.headers) if self.headers else 0
        
        for row_idx in range(start_row, clean_matrix.row_count):
            expanded_row = clean_matrix.get_expanded_row(row_idx)
            row_data = []
            
            for cell in expanded_row:
                if cell is not None:
                    text = cell.text()
                    # Check if this is a merged currency value (starts with $, €, £, etc.)
                    if text and text[0] in {'$', '€', '£', '¥'}:
                        # Keep the full text with currency symbol
                        row_data.append(text)
                    elif cell.is_numeric:
                        row_data.append(cell.numeric_value)
                    else:
                        row_data.append(text)
                else:
                    row_data.append(None)  # Empty cell
            
            # Only add non-empty rows
            if any(v is not None and str(v).strip() for v in row_data):
                data.append(row_data)
        
        # Create DataFrame
        if data and df_columns is not None:
            # Ensure data width matches column width
            col_count = len(df_columns) if hasattr(df_columns, '__len__') else df_columns.nlevels
            for row in data:
                while len(row) < col_count:
                    row.append(None)
                while len(row) > col_count:
                    row.pop()
            
            df = pd.DataFrame(data, columns=df_columns)
            
            # Set row index if first column is labels
            if self.has_row_headers and len(df.columns) > 0:
                df = df.set_index(df.columns[0])
            
            return df
        else:
            # Return empty DataFrame with columns
            return pd.DataFrame(columns=df_columns if df_columns is not None else [])
    
    def to_csv(self) -> str:
        """Export table as CSV."""
        df = self.to_dataframe()
        return df.to_csv(index=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert table to dictionary."""
        return {
            'type': self.table_type.name,
            'caption': self.caption,
            'headers': [[cell.text() for cell in row] for row in self.headers],
            'data': [[cell.text() for cell in row.cells] for row in self.rows],
            'footer': [[cell.text() for cell in row.cells] for row in self.footer]
        }
    
    def find_column(self, header_text: str) -> Optional[int]:
        """Find column index by header text."""
        if not self.headers:
            return None
        
        # Search in first header row
        for i, cell in enumerate(self.headers[0]):
            if header_text.lower() in cell.text().lower():
                return i
        
        return None
    
    def extract_column(self, column_index: int) -> List[str]:
        """Extract all values from a column."""
        values = []
        for row in self.rows:
            if column_index < len(row.cells):
                values.append(row.cells[column_index].text())
        return values
    
    def find_row_by_first_cell(self, text: str) -> Optional[Row]:
        """Find row by first cell content."""
        for row in self.rows:
            if row.cells and text.lower() in row.cells[0].text().lower():
                return row
        return None
    
    def get_numeric_columns(self) -> Dict[str, List[float]]:
        """Extract all numeric columns with their headers."""
        result = {}
        
        if not self.headers:
            return result
        
        # Check each column
        for col_idx, header_cell in enumerate(self.headers[0]):
            header = header_cell.text()
            values = []
            is_numeric_col = True
            
            # Extract values from column
            for row in self.rows:
                if col_idx < len(row.cells):
                    cell = row.cells[col_idx]
                    if cell.is_numeric:
                        values.append(cell.numeric_value)
                    else:
                        # Check if it's a total row or empty
                        if not row.is_total_row and cell.text().strip():
                            is_numeric_col = False
                            break
                        values.append(None)
            
            # Only include if mostly numeric
            if is_numeric_col and values:
                non_none_values = [v for v in values if v is not None]
                if len(non_none_values) > len(values) * 0.5:  # At least 50% numeric
                    result[header] = values
        
        return result
    
    def find_totals(self) -> Dict[str, float]:
        """Find total rows in table."""
        totals = {}
        
        for row in self.rows:
            if row.is_total_row:
                # Extract label from first cell
                label = row.cells[0].text() if row.cells else "Total"
                
                # Find numeric values in row
                for cell in row.cells[1:]:  # Skip label cell
                    if cell.is_numeric:
                        totals[label] = cell.numeric_value
                        break
        
        return totals
    
    @property
    def is_financial_table(self) -> bool:
        """Check if this appears to be a financial table."""
        if self.table_type == TableType.FINANCIAL:
            return True
        
        # Check headers for financial keywords
        financial_keywords = [
            'revenue', 'income', 'expense', 'asset', 'liability',
            'cash', 'equity', 'profit', 'loss', 'margin'
        ]
        
        header_text = ' '.join(
            cell.text().lower() 
            for row in self.headers 
            for cell in row
        )
        
        return any(keyword in header_text for keyword in financial_keywords)
    
    @property
    def row_count(self) -> int:
        """Get total number of rows in table (including headers)."""
        return len(self.headers) + len(self.rows)
    
    @property
    def col_count(self) -> int:
        """Get number of columns in table."""
        if self.headers and self.headers[0]:
            return len(self.headers[0])
        elif self.rows and self.rows[0].cells:
            return len(self.rows[0].cells)
        return 0
    
    @property
    def has_header(self) -> bool:
        """Check if table has header rows."""
        return bool(self.headers)
    
    @property
    def has_row_headers(self) -> bool:
        """Check if table has row headers (first column as labels)."""
        if not self.rows:
            return False
        
        # Check if first column is non-numeric
        first_col_numeric = 0
        for row in self.rows:
            if row.cells and row.cells[0].is_numeric:
                first_col_numeric += 1
        
        # If less than 20% of first column is numeric, likely row headers
        return first_col_numeric < len(self.rows) * 0.2
    
    @property
    def numeric_columns(self) -> List[int]:
        """Get indices of numeric columns."""
        numeric_cols = []
        
        for col_idx in range(self.col_count):
            numeric_count = 0
            total_count = 0
            
            for row in self.rows:
                if col_idx < len(row.cells):
                    total_count += 1
                    if row.cells[col_idx].is_numeric:
                        numeric_count += 1
            
            # If more than 50% numeric, consider it a numeric column
            if total_count > 0 and numeric_count / total_count > 0.5:
                numeric_cols.append(col_idx)
        
        return numeric_cols
    
    
    def summarize_for_llm(self, max_tokens: int = 500) -> str:
        """Create concise table summary for LLM processing."""
        parts = []
        
        # Add type and structure info
        parts.append(f"Table Type: {self.table_type.name}")
        parts.append(f"Size: {len(self.rows)} rows × {len(self.headers[0]) if self.headers else 'unknown'} columns")
        
        if self.caption:
            parts.append(f"Caption: {self.caption}")
        
        # Add column headers
        if self.headers:
            headers = [cell.text() for cell in self.headers[0]]
            parts.append(f"Columns: {', '.join(headers[:5])}")
            if len(headers) > 5:
                parts.append(f"  ... and {len(headers) - 5} more columns")
        
        # Add sample data or totals
        totals = self.find_totals()
        if totals:
            parts.append("Key totals:")
            for label, value in list(totals.items())[:3]:
                parts.append(f"  {label}: {value:,.0f}")
        
        # Add numeric column summary
        numeric_cols = self.get_numeric_columns()
        if numeric_cols:
            parts.append("Numeric columns found:")
            for col_name in list(numeric_cols.keys())[:3]:
                parts.append(f"  - {col_name}")
        
        return '\n'.join(parts)