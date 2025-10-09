"""
Fast table renderer for edgar.documents - optimized for performance.

This module provides a high-performance alternative to Rich table rendering
while maintaining professional output quality and readability.

Performance target: ~32x faster than Rich rendering (0.2ms vs 6.5ms per table)
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Union, Tuple
from enum import Enum


class Alignment(Enum):
    """Column alignment options."""
    LEFT = "left"
    RIGHT = "right"
    CENTER = "center"


@dataclass
class ColumnConfig:
    """Configuration for a table column."""
    alignment: Alignment = Alignment.LEFT
    min_width: int = 8
    max_width: Optional[int] = None
    padding: int = 1


@dataclass
class TableStyle:
    """Table styling configuration."""
    border_char: str = "|"
    header_separator: str = "-"
    corner_char: str = "+"
    padding: int = 1
    min_col_width: int = 8
    max_col_width: int = 50
    
    @classmethod
    def pipe_table(cls) -> 'TableStyle':
        """Markdown-compatible pipe table style."""
        return cls(
            border_char="|",
            header_separator="-",
            corner_char="|",
            padding=1,
            min_col_width=8,
            max_col_width=50
        )
    
    @classmethod
    def minimal(cls) -> 'TableStyle':
        """Minimal table style with spacing only."""
        return cls(
            border_char="",
            header_separator="",
            corner_char="",
            padding=2,
            min_col_width=6,
            max_col_width=40
        )

    @classmethod
    def simple(cls) -> 'TableStyle':
        """
        Simple table style matching Rich's box.SIMPLE.

        Features:
        - No outer border
        - No column separators
        - Single horizontal line under header
        - Space-separated columns with generous padding
        - Clean, professional appearance

        This style provides the best balance of visual quality and performance,
        matching Rich's box.SIMPLE aesthetic while maintaining fast rendering speed.
        """
        return cls(
            border_char="",            # No pipes/borders
            header_separator="─",      # Unicode horizontal line
            corner_char="",            # No corners
            padding=2,                 # Generous spacing (was 1 in pipe_table)
            min_col_width=6,          # Slightly relaxed (was 8)
            max_col_width=60          # Raised from 50 for wider columns
        )


class FastTableRenderer:
    """
    High-performance table renderer optimized for speed.
    
    Features:
    - 30x+ faster than Rich table rendering
    - Professional, readable output
    - Configurable alignment and styling
    - Handles complex SEC filing table structures
    - Markdown-compatible output
    - Memory efficient
    """
    
    def __init__(self, style: Optional[TableStyle] = None):
        """Initialize renderer with optional style configuration."""
        self.style = style or TableStyle.pipe_table()
        
        # Pre-compile format strings for performance
        self._format_cache = {}
    
    def render_table_node(self, table_node) -> str:
        """
        Render a TableNode to text format with proper colspan/rowspan handling.

        Args:
            table_node: TableNode instance from edgar.documents

        Returns:
            Formatted table string
        """
        from edgar.documents.utils.table_matrix import TableMatrix

        # Build matrix to handle colspan/rowspan properly
        # This ensures cells are expanded to fill their full colspan/rowspan
        matrix = TableMatrix()
        matrix.build_from_rows(table_node.headers, table_node.rows)

        # Extract headers from expanded matrix
        headers = []
        if table_node.headers:
            for row_idx in range(len(table_node.headers)):
                expanded_row = matrix.get_expanded_row(row_idx)
                # Convert Cell objects to strings, handling None values
                row_texts = [cell.text().strip() if cell else '' for cell in expanded_row]
                headers.append(row_texts)

        # Extract data rows from expanded matrix
        rows = []
        start_row = len(table_node.headers) if table_node.headers else 0
        for row_idx in range(start_row, matrix.row_count):
            expanded_row = matrix.get_expanded_row(row_idx)
            # Convert Cell objects to strings, handling None values
            row_texts = [cell.text().strip() if cell else '' for cell in expanded_row]
            rows.append(row_texts)

        # Render the table
        table_text = self.render_table_data(headers, rows)

        # Add caption if present (matches Rich renderer behavior)
        if hasattr(table_node, 'caption') and table_node.caption:
            return f"{table_node.caption}\n{table_text}"

        return table_text
    
    def render_table_data(self, headers: List[List[str]], rows: List[List[str]]) -> str:
        """
        Render table data with headers and rows.

        Args:
            headers: List of header rows (for multi-row headers)
            rows: List of data rows

        Returns:
            Formatted table string
        """
        if not headers and not rows:
            return ""

        # Determine column count from all rows (headers + data)
        all_rows = headers + rows if headers else rows
        if not all_rows:
            return ""

        max_cols = max(len(row) for row in all_rows) if all_rows else 0
        if max_cols == 0:
            return ""

        # Filter out empty/spacing columns
        meaningful_columns = self._identify_meaningful_columns(all_rows, max_cols)
        if not meaningful_columns:
            return ""

        # Filter all rows (both headers and data) to only meaningful columns
        filtered_headers = [self._filter_row_to_columns(row, meaningful_columns) for row in headers] if headers else []
        filtered_rows = [self._filter_row_to_columns(row, meaningful_columns) for row in rows]

        # Post-process to merge related columns (e.g., currency symbols with amounts)
        # Apply to all rows including headers
        all_filtered = filtered_headers + filtered_rows
        if all_filtered:
            # Merge using first filtered row as reference
            _, all_merged = self._merge_related_columns(all_filtered[0], all_filtered)
            # Split back into headers and data
            if filtered_headers:
                filtered_headers = all_merged[:len(filtered_headers)]
                filtered_rows = all_merged[len(filtered_headers):]
            else:
                filtered_rows = all_merged

        # Recalculate with filtered and merged data
        filtered_all_rows = filtered_headers + filtered_rows if filtered_headers else filtered_rows
        filtered_max_cols = max(len(row) for row in filtered_all_rows) if filtered_all_rows else 0

        # Calculate optimal column widths for filtered columns
        col_widths = self._calculate_column_widths(filtered_all_rows, filtered_max_cols)

        # Detect column alignments based on filtered content
        alignments = self._detect_alignments(filtered_all_rows, filtered_max_cols)

        # Build table with filtered data - pass headers as multiple rows
        return self._build_table(filtered_headers, filtered_rows, col_widths, alignments)
    
    def _combine_headers(self, headers: List[List[str]]) -> List[str]:
        """
        Combine multi-row headers intelligently.
        
        For SEC tables, this prioritizes specific dates/periods over generic labels.
        """
        if not headers:
            return []
        
        if len(headers) == 1:
            return headers[0]
        
        # Determine max columns across all header rows
        max_cols = max(len(row) for row in headers) if headers else 0
        combined = [""] * max_cols
        
        for col in range(max_cols):
            # Collect all values for this column
            values = []
            for header_row in headers:
                if col < len(header_row) and header_row[col].strip():
                    values.append(header_row[col].strip())
            
            if values:
                # Prioritize date-like values over generic terms
                date_values = [v for v in values if self._looks_like_date(v)]
                if date_values:
                    combined[col] = date_values[0]
                elif len(values) == 1:
                    combined[col] = values[0]
                else:
                    # Skip generic terms like "Year Ended" if we have something more specific
                    specific_values = [v for v in values 
                                     if v.lower() not in {'year ended', 'years ended', 'period ended'}]
                    combined[col] = specific_values[0] if specific_values else values[0]
        
        return combined
    
    def _looks_like_date(self, text: str) -> bool:
        """Quick date detection for header processing."""
        if not text or len(text) < 4:
            return False
        
        text_lower = text.lower().replace('\n', ' ').strip()
        
        # Common date indicators
        date_indicators = [
            'january', 'february', 'march', 'april', 'may', 'june',
            'july', 'august', 'september', 'october', 'november', 'december',
            '20', '19',  # Year prefixes
        ]
        
        return any(indicator in text_lower for indicator in date_indicators) and \
               any(c.isdigit() for c in text)
    
    def _identify_meaningful_columns(self, all_rows: List[List[str]], max_cols: int) -> List[int]:
        """
        Identify columns that contain meaningful content (not just spacing).
        
        Returns:
            List of column indices that have meaningful content
        """
        column_scores = []
        
        for col_idx in range(max_cols):
            content_score = 0
            total_rows = 0
            
            # Score each column based on content quality
            for row in all_rows:
                if col_idx < len(row):
                    total_rows += 1
                    cell_content = str(row[col_idx]).strip()
                    
                    if cell_content:
                        # Higher score for longer, more substantial content
                        if len(cell_content) >= 3:  # Substantial content
                            content_score += 3
                        elif len(cell_content) == 2 and cell_content.isalnum():
                            content_score += 2
                        elif len(cell_content) == 1 and (cell_content.isalnum() or cell_content == '$'):
                            content_score += 1
                        # Skip single spaces, dashes, or other likely spacing characters
            
            # Calculate average score per row for this column
            avg_score = content_score / max(total_rows, 1)
            column_scores.append((col_idx, avg_score, content_score))
        
        # Sort by score descending
        column_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Take columns with meaningful content (score >= 0.5 or among top columns)
        meaningful_columns = []
        for col_idx, avg_score, total_score in column_scores:
            # Include if it has good average score or significant total content
            if avg_score >= 0.5 or total_score >= 5:
                meaningful_columns.append(col_idx)
            # Limit to reasonable number of columns for readability
            if len(meaningful_columns) >= 8:
                break
        
        # Sort by original column order
        meaningful_columns.sort()
        
        return meaningful_columns
    
    def _filter_row_to_columns(self, row: List[str], column_indices: List[int]) -> List[str]:
        """
        Filter a row to only include the specified column indices.
        
        Args:
            row: Original row data
            column_indices: List of column indices to keep
            
        Returns:
            Filtered row with only the specified columns
        """
        if not row:
            return []
        
        filtered_row = []
        for col_idx in column_indices:
            if col_idx < len(row):
                filtered_row.append(row[col_idx])
            else:
                filtered_row.append("")  # Missing column
        
        return filtered_row
    
    def _merge_related_columns(self, headers: List[str], rows: List[List[str]]) -> tuple:
        """
        Merge related columns (e.g., currency symbols with their amounts).
        
        Returns:
            Tuple of (merged_headers, merged_rows)
        """
        if not rows or not any(rows):
            return headers, rows
        
        # Find columns that should be merged
        merge_pairs = []
        max_cols = max(len(row) for row in [headers] + rows if row) if rows else len(headers) if headers else 0
        
        for col_idx in range(max_cols - 1):
            # Check if this column and the next should be merged
            should_merge = self._should_merge_columns(headers, rows, col_idx, col_idx + 1)
            if should_merge:
                merge_pairs.append((col_idx, col_idx + 1))
        
        # Apply merges (from right to left to avoid index shifting)
        merged_headers = headers[:] if headers else []
        merged_rows = [row[:] for row in rows]
        
        for left_idx, right_idx in reversed(merge_pairs):
            # Merge headers
            if merged_headers and left_idx < len(merged_headers) and right_idx < len(merged_headers):
                left_header = merged_headers[left_idx].strip()
                right_header = merged_headers[right_idx].strip()
                merged_header = f"{left_header} {right_header}".strip()
                merged_headers[left_idx] = merged_header
                merged_headers.pop(right_idx)
            
            # Merge rows
            for row in merged_rows:
                if left_idx < len(row) and right_idx < len(row):
                    left_cell = str(row[left_idx]).strip()
                    right_cell = str(row[right_idx]).strip()
                    
                    # Smart merging based on content
                    if left_cell == '$' and right_cell:
                        merged_cell = f"${right_cell}"
                    elif left_cell and right_cell:
                        merged_cell = f"{left_cell} {right_cell}"
                    else:
                        merged_cell = left_cell or right_cell
                    
                    row[left_idx] = merged_cell
                    if right_idx < len(row):
                        row.pop(right_idx)
        
        return merged_headers, merged_rows
    
    def _should_merge_columns(self, headers: List[str], rows: List[List[str]], left_idx: int, right_idx: int) -> bool:
        """
        Determine if two adjacent columns should be merged.
        
        Returns:
            True if columns should be merged
        """
        # Check if left column is mostly currency symbols
        currency_count = 0
        total_count = 0
        
        for row in rows:
            if left_idx < len(row) and right_idx < len(row):
                total_count += 1
                left_cell = str(row[left_idx]).strip()
                right_cell = str(row[right_idx]).strip()
                
                # If left is '$' and right is a number, they should be merged
                if left_cell == '$' and right_cell and (right_cell.replace(',', '').replace('.', '').isdigit()):
                    currency_count += 1
        
        # If most rows have currency symbol + number pattern, merge them
        if total_count > 0 and currency_count / total_count >= 0.5:
            return True
        
        # Check for other merge patterns (e.g., empty left column with content right column)
        empty_left_count = 0
        for row in rows:
            if left_idx < len(row) and right_idx < len(row):
                left_cell = str(row[left_idx]).strip()
                right_cell = str(row[right_idx]).strip()
                
                if not left_cell and right_cell:
                    empty_left_count += 1
        
        # If left column is mostly empty, consider merging
        if total_count > 0 and empty_left_count / total_count >= 0.7:
            return True
        
        return False
    
    def _calculate_column_widths(self, all_rows: List[List[str]], max_cols: int) -> List[int]:
        """Calculate optimal column widths based on content."""
        col_widths = [self.style.min_col_width] * max_cols
        
        # Find the maximum content width for each column
        for row in all_rows:
            for col_idx in range(min(len(row), max_cols)):
                content = str(row[col_idx]) if row[col_idx] else ""
                # Handle multi-line content
                max_line_width = max((len(line) for line in content.split('\n')), default=0)
                content_width = max_line_width + (self.style.padding * 2)
                
                # Apply limits
                content_width = min(content_width, self.style.max_col_width)
                col_widths[col_idx] = max(col_widths[col_idx], content_width)
        
        return col_widths
    
    def _detect_alignments(self, all_rows: List[List[str]], max_cols: int) -> List[Alignment]:
        """Detect appropriate alignment for each column based on content."""
        alignments = [Alignment.LEFT] * max_cols
        
        for col_idx in range(max_cols):
            # Analyze column content (skip header row if present)
            data_rows = all_rows[1:] if len(all_rows) > 1 else all_rows
            
            numeric_count = 0
            total_count = 0
            
            for row in data_rows:
                if col_idx < len(row) and row[col_idx].strip():
                    total_count += 1
                    content = row[col_idx].strip()
                    
                    # Check if content looks numeric (currency, percentages, numbers)
                    if self._looks_numeric(content):
                        numeric_count += 1
            
            # If most values in column are numeric, right-align
            if total_count > 0 and numeric_count / total_count >= 0.7:
                alignments[col_idx] = Alignment.RIGHT
        
        return alignments
    
    def _looks_numeric(self, text: str) -> bool:
        """Check if text content looks numeric."""
        if not text:
            return False
        
        # Remove common formatting characters
        clean_text = text.replace(',', '').replace('$', '').replace('%', '').replace('(', '').replace(')', '').strip()
        
        # Handle negative numbers in parentheses
        if text.strip().startswith('(') and text.strip().endswith(')'):
            clean_text = text.strip()[1:-1].replace(',', '').replace('$', '').strip()
        
        # Check if remaining text is numeric
        try:
            float(clean_text)
            return True
        except ValueError:
            return False
    
    def _build_table(self, headers: List[List[str]], rows: List[List[str]],
                    col_widths: List[int], alignments: List[Alignment]) -> str:
        """
        Build the final table string.

        Args:
            headers: List of header rows (can be multiple rows for multi-row headers)
            rows: List of data rows
            col_widths: Column widths
            alignments: Column alignments
        """
        lines = []

        # Header rows (can be multiple)
        if headers:
            for header_row in headers:
                # Only add header rows with meaningful content
                if any(cell.strip() for cell in header_row):
                    # Handle multi-line cells in header rows
                    formatted_lines = self._format_multiline_row(header_row, col_widths, alignments)
                    lines.extend(formatted_lines)

            # Header separator (after all header rows)
            if self.style.header_separator:
                sep_line = self._create_separator_line(col_widths)
                lines.append(sep_line)

        # Data rows
        for row in rows:
            # Only add rows with meaningful content
            if any(cell.strip() for cell in row):
                row_line = self._format_row(row, col_widths, alignments)
                lines.append(row_line)
        
        return '\n'.join(lines)
    
    def _format_row(self, row: List[str], col_widths: List[int], 
                   alignments: List[Alignment]) -> str:
        """Format a single row with proper alignment and padding."""
        cells = []
        border = self.style.border_char
        
        for col_idx, width in enumerate(col_widths):
            # Get cell content
            content = str(row[col_idx]) if col_idx < len(row) else ""
            
            # Handle multi-line content (take first line only for table)
            if '\n' in content:
                content = content.split('\n')[0]
            
            content = content.strip()
            
            # Calculate available width for content
            available_width = width - (self.style.padding * 2)
            
            # Truncate if too long
            if len(content) > available_width:
                content = content[:available_width-3] + "..."
            
            # Apply alignment
            alignment = alignments[col_idx] if col_idx < len(alignments) else Alignment.LEFT
            
            if alignment == Alignment.RIGHT:
                aligned_content = content.rjust(available_width)
            elif alignment == Alignment.CENTER:
                aligned_content = content.center(available_width)
            else:  # LEFT
                aligned_content = content.ljust(available_width)
            
            # Add padding
            padded_cell = ' ' * self.style.padding + aligned_content + ' ' * self.style.padding
            cells.append(padded_cell)
        
        # Join with borders
        if border:
            return border + border.join(cells) + border
        else:
            return '  '.join(cells)
    
    def _format_multiline_row(self, row: List[str], col_widths: List[int],
                              alignments: List[Alignment]) -> List[str]:
        """
        Format a row that may contain multi-line cells (cells with \n characters).

        Returns a list of formatted lines, one for each line of text in the cells.
        """
        # Split each cell by newlines
        cell_lines = []
        max_lines = 1

        for col_idx, content in enumerate(row):
            lines = content.split('\n') if content else ['']
            cell_lines.append(lines)
            max_lines = max(max_lines, len(lines))

        # Build output lines
        output_lines = []
        for line_idx in range(max_lines):
            # Build row for this line
            current_row = []
            for col_idx in range(len(row)):
                # Get the line for this cell, or empty string if this cell has fewer lines
                if line_idx < len(cell_lines[col_idx]):
                    current_row.append(cell_lines[col_idx][line_idx])
                else:
                    current_row.append('')

            # Format this line
            formatted_line = self._format_row(current_row, col_widths, alignments)
            output_lines.append(formatted_line)

        return output_lines

    def _create_separator_line(self, col_widths: List[int]) -> str:
        """
        Create header separator line.

        For bordered styles: |-------|-------|
        For borderless styles:  ─────────────── (full width horizontal line)
        """
        sep_char = self.style.header_separator
        border = self.style.border_char

        if not sep_char:
            # No separator at all (minimal style)
            return ""

        if border:
            # Bordered style: create separator matching column widths
            separators = []
            for width in col_widths:
                separators.append(sep_char * width)
            return border + border.join(separators) + border
        else:
            # Borderless style (simple): single horizontal line across full width
            # Calculate total width: sum of column widths + gaps between columns
            total_width = sum(col_widths) + (len(col_widths) - 1) * 2  # 2-space gaps

            # Add leading space for indentation (matching row indentation)
            return " " + sep_char * total_width


# Factory functions for easy usage
def create_fast_renderer(style: str = "pipe") -> FastTableRenderer:
    """
    Create a FastTableRenderer with predefined style.
    
    Args:
        style: Style name ("pipe", "minimal")
    
    Returns:
        Configured FastTableRenderer instance
    """
    if style == "minimal":
        return FastTableRenderer(TableStyle.minimal())
    else:  # Default to pipe
        return FastTableRenderer(TableStyle.pipe_table())


def render_table_fast(table_node, style: str = "pipe") -> str:
    """
    Convenience function to quickly render a table.
    
    Args:
        table_node: TableNode instance
        style: Style name ("pipe", "minimal")
    
    Returns:
        Formatted table string
    """
    renderer = create_fast_renderer(style)
    return renderer.render_table_node(table_node)