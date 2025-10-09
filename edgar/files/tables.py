from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from edgar.files.html import BaseNode
import re
from functools import lru_cache

from edgar.richtools import rich_to_text


@dataclass
class ProcessedTable:
    """Represents a processed table ready for rendering"""
    headers: Optional[list[str]]
    data_rows: list[list[str]]
    column_alignments: list[str]  # "left" or "right" for each column


# Looks for actual numeric data values, currency, or calculations
data_indicators = [
    r'\$\s*\d',  # Currency with numbers
    r'\d+(?:,\d{3})+',  # Numbers with thousands separators
    r'\d+\s*[+\-*/]\s*\d+',  # Basic calculations
    r'\(\s*\d+(?:,\d{3})*\s*\)',  # Parenthesized numbers
]

data_pattern = '|'.join(data_indicators)


def is_number(s: str) -> bool:
    """
    Check if a string represents a number in common financial formats.

    Handles:
    - Regular numbers (123, -123, 123.45)
    - Currency ($123, $123.45)
    - Parenthetical negatives ((123), (123.45))
    - Thousands separators (1,234, 1,234.56)
    - Mixed formats ($1,234.56)
    - Various whitespace
    - En/Em dashes for negatives
    - Multiple decimal formats (123.45, 123,45)

    Args:
        s: String to check

    Returns:
        bool: True if string represents a valid number
    """
    if not s or s.isspace():
        return False

    # Convert unicode minus/dash characters to regular minus
    s = s.replace('−', '-').replace('–', '-').replace('—', '-')

    # Handle parenthetical negatives
    s = s.strip()
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]

    # Remove currency symbols and whitespace
    s = s.replace('$', '').replace(' ', '')

    # Handle European number format (convert 123,45 to 123.45)
    if ',' in s and '.' not in s and len(s.split(',')[1]) == 2:
        s = s.replace(',', '.')
    else:
        # Remove thousands separators
        s = s.replace(',', '')

    try:
        float(s)
        return True
    except ValueError:
        return False

class TableProcessor:
    @staticmethod
    def process_table(node) -> Optional[ProcessedTable]:
        """Process table node into a format ready for rendering"""
        if not isinstance(node.content, list) or not node.content:
            return None

        def process_cell_content(content: Union[str, 'BaseNode']) -> str:
            """Process cell content to handle HTML breaks and cleanup"""
            if isinstance(content, str):
                content = content.replace('<br/>', '\n').replace('<br>', '\n')
                lines = [line.strip() for line in content.split('\n')]
                return '\n'.join(line for line in lines if line)
            else:
                # Recursively process nested nodes
                processed_table = content.render(500)
                return rich_to_text(processed_table)

        # Process all rows into virtual columns
        virtual_rows = []
        max_cols = max(sum(cell.colspan for cell in row.cells) for row in node.content)

        # Convert all rows to virtual columns first
        for row in node.content:
            virtual_row = [""] * max_cols
            current_col = 0

            for cell in row.cells:
                content = process_cell_content(cell.content)

                if '\n' not in content and cell.is_currency and content.replace(',', '').replace('.', '').isdigit():
                    content = f"${float(content.replace(',', '')):,.2f}"

                if cell.colspan > 1:
                    virtual_row[current_col + 1] = content
                else:
                    virtual_row[current_col] = content

                current_col += cell.colspan

            virtual_rows.append(virtual_row)

        # Analyze and remove empty columns
        empty_cols = []
        for col in range(max_cols):
            if all(row[col].strip() == "" for row in virtual_rows):
                empty_cols.append(col)

        # Process empty columns
        cols_to_remove = TableProcessor._get_columns_to_remove(empty_cols, max_cols)

        # Create optimized rows, filtering out empty ones
        optimized_rows = []
        for virtual_row in virtual_rows:
            has_content = any(col.strip() for col in virtual_row)
            if not has_content:
                continue
            optimized_row = [col for idx, col in enumerate(virtual_row) if idx not in cols_to_remove]
            optimized_rows.append(optimized_row)

        if not optimized_rows:
            return None

        # Detect headers
        header_rows, data_start_idx = TableProcessor._analyze_table_structure(optimized_rows)

        # Detect and fix misalignment in all rows
        fixed_rows = TableProcessor._detect_and_fix_misalignment(optimized_rows, data_start_idx)

        # Use the fixed header portion for processing headers
        headers = None
        if header_rows:
            fixed_headers = fixed_rows[:data_start_idx]  # Take header portion from fixed rows
            headers = TableProcessor._merge_header_rows(fixed_headers)

        # Determine column alignments
        col_count = len(optimized_rows[0])
        alignments = TableProcessor._determine_column_alignments(
            optimized_rows, data_start_idx, col_count)

        # Format data rows
        formatted_rows = TableProcessor._format_data_rows(
            optimized_rows[data_start_idx:])

        return ProcessedTable(
            headers=headers,
            data_rows=formatted_rows,
            column_alignments=alignments
        )

    @staticmethod
    def _is_date_header(text: str) -> bool:
        """Detect if text looks like a date header (year, quarter, month)"""
        text = text.lower().strip()

        # Year patterns
        if text.isdigit() and len(text) == 4:
            return True

        # Quarter patterns
        quarter_patterns = ['q1', 'q2', 'q3', 'q4', 'first quarter', 'second quarter',
                            'third quarter', 'fourth quarter']
        if any(pattern in text for pattern in quarter_patterns):
            return True

        # Month patterns
        months = ['january', 'february', 'march', 'april', 'may', 'june',
                  'july', 'august', 'september', 'october', 'november', 'december',
                  'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        return any(month in text for month in months)


    @staticmethod
    def _analyze_row(row: list) -> dict:
        """Analyze characteristics of a row"""
        return {
            'empty_first': not bool(row[0].strip()),
            'date_headers': sum(1 for cell in row if TableProcessor._is_date_header(cell)),
            'financial_values': sum(1 for i, cell in enumerate(row)
                                    if TableProcessor._is_financial_value(cell, row, i)),
            'financial_metrics': sum(1 for cell in row if TableProcessor._is_financial_metric(cell)),
            'empty_cells': sum(1 for cell in row if not cell.strip()),
            'dollar_signs': sum(1 for cell in row if cell.strip() == '$'),
            'total_cells': len(row)
        }


    @staticmethod
    @lru_cache(maxsize=None)
    def _get_period_header_pattern() -> re.Pattern:
        """Create regex pattern for common financial period headers"""
        # Base components
        periods = r'(?:three|six|nine|twelve|[1-4]|first|second|third|fourth)'
        timeframes = r'(?:month|quarter|year|week)'
        ended_variants = r'(?:ended|ending|end|period)'
        as_of_variants = r'(?:as\s+of|at|as\s+at)'

        # Enhanced date pattern
        months = r'(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)'
        day = r'\d{1,2}'
        year = r'(?:19|20)\d{2}'
        date = fr'{months}\s*\.?\s*{day}\s*,?\s*{year}'

        # Combine into patterns
        patterns = [
            # Standard period headers
            fr'{periods}\s+{timeframes}\s+{ended_variants}(?:\s+{date})?',
            fr'(?:fiscal\s+)?{timeframes}\s+{ended_variants}',
            fr'{timeframes}\s+{ended_variants}(?:\s+{date})?',

            # Balance sheet date headers
            fr'{as_of_variants}\s+{date}',

            # Multiple dates in sequence (common in headers)
            fr'{date}(?:\s*(?:and|,)\s*{date})*',

            # Single date with optional period specification
            fr'(?:{ended_variants}\s+)?{date}'
        ]

        # Combine all patterns
        combined_pattern = '|'.join(f'(?:{p})' for p in patterns)
        return re.compile(combined_pattern, re.IGNORECASE)

    @staticmethod
    def _contains_data(self, text):
        # Check if the string contains data indicators
        return bool(re.search(data_pattern, text))

    @staticmethod
    def _analyze_table_structure(rows: list) -> tuple[list, int]:
        """
        Analyze table structure to determine headers and data rows.
        Returns (header_rows, data_start_index)
        """
        if not rows:
            return [], 0

        row_analyses = [TableProcessor._analyze_row(row) for row in rows[:4]]
        period_pattern = TableProcessor._get_period_header_pattern()

        # Pattern 1: Look for period headers
        for i, row in enumerate(rows[:3]):  # Check first 4 rows
            header_text = ' '.join(cell.strip() for cell in row).lower()
            has_period_header = period_pattern.search(header_text)
            contains_data = bool(re.search(data_pattern, header_text))
            if has_period_header and not contains_data:
                # Found a period header, check if next row has years or is part of header
                if i + 1 < len(rows):
                    next_row = rows[i + 1]
                    next_text = ' '.join(cell.strip() for cell in next_row)
                    # Check if next row has years or quarter references
                    if (any(str(year) in next_text for year in range(2010, 2030)) or
                            any(q in next_text.lower() for q in ['q1', 'q2', 'q3', 'q4'])):
                        return rows[:i + 2], i + 2
                return rows[:i + 1], i + 1

        # Pattern 2: $ symbols in their own columns
        for i, analysis in enumerate(row_analyses):
            if analysis['dollar_signs'] > 0:
                # If we see $ symbols, previous row might be header
                if i > 0:
                    return rows[:i], i
                return [], i

        # Pattern 3: Look for transition from text to numbers with $ alignment
        for i in range(len(rows) - 1):
            curr_analysis = TableProcessor._analyze_row(rows[i])
            next_analysis = TableProcessor._analyze_row(rows[i + 1])

            if (curr_analysis['financial_values'] == 0 and
                    next_analysis['financial_values'] > 0 and
                    next_analysis['dollar_signs'] > 0):
                return rows[:i + 1], i + 1

        # Default to no headers if no clear pattern found
        return [], 0

    # In TableProcessor class
    @staticmethod
    def _detect_and_fix_misalignment(virtual_rows: list[list[str]], data_start_idx: int) -> list[list[str]]:
        """
        Detect and fix misalignment between date headers and numeric data columns.
        Returns corrected virtual rows.
        """
        if not virtual_rows or data_start_idx >= len(virtual_rows):
            return virtual_rows

        # Get header row (assumes dates are in the last header row)
        header_idx = data_start_idx - 1
        if header_idx < 0:
            return virtual_rows

        header_row = virtual_rows[data_start_idx - 1]

        # Find date columns in header
        date_columns = []
        for i, cell in enumerate(header_row):
            if TableProcessor._is_date_header(cell):
                date_columns.append(i)

        if not date_columns:
            return virtual_rows  # No date headers found

        # Find numeric columns in first few data rows
        numeric_columns = set()
        for row in virtual_rows[data_start_idx:data_start_idx + 3]:  # Check first 3 data rows
            for i, cell in enumerate(row):
                if TableProcessor._is_financial_value(cell, row, i):
                    numeric_columns.add(i)

        # Detect misalignment
        if date_columns and numeric_columns:
            # Check if dates are shifted right compared to numeric columns
            dates_shifted = all(
                (i + 1) in numeric_columns
                for i in date_columns
            )
            if dates_shifted:
                # Fix alignment by shifting only the row containing dates
                fixed_rows = virtual_rows.copy()
                # Find and fix only the row containing the dates
                for row_idx, row in enumerate(virtual_rows):
                    if row_idx < data_start_idx:  # Only check header rows
                        # Check if this row contains the dates by counting date headers
                        date_count = sum(1 for cell in row if TableProcessor._is_date_header(cell))
                        if date_count >= 2:  # If multiple dates found, this is our target row
                            new_row = [""] * len(row)  # Start with empty row
                            for i in range(len(row) - 1):
                                new_row[i + 1] = row[i]  # Copy each value one position right
                            fixed_rows[row_idx] = new_row
                            break  # Only fix one row
                return fixed_rows

        return virtual_rows

    @staticmethod
    def _get_columns_to_remove(empty_cols: list[int], max_cols: int) -> set[int]:
        cols_to_remove = set()

        # Handle leading empty columns
        for col in range(max_cols):
            if col in empty_cols:
                cols_to_remove.add(col)
            else:
                break

        # Handle trailing empty columns
        for col in reversed(range(max_cols)):
            if col in empty_cols:
                cols_to_remove.add(col)
            else:
                break

        # Handle consecutive empty columns in the middle
        i = 0
        while i < max_cols - 1:
            if i in empty_cols and (i + 1) in empty_cols:
                consecutive_empty = 0
                j = i
                while j < max_cols and j in empty_cols:
                    consecutive_empty += 1
                    j += 1
                cols_to_remove.update(range(i + 1, i + consecutive_empty))
                i = j
            else:
                i += 1

        return cols_to_remove

    @staticmethod
    def _merge_header_rows(header_rows: list[list[str]]) -> list[str]:
        """Merge multiple header rows into one"""
        if not header_rows:
            return []

        merged = []
        for col_idx in range(len(header_rows[0])):
            parts = []
            for row in header_rows:
                text = row[col_idx].strip()
                if text and text != '$':  # Skip empty cells and lone $ symbols
                    parts.append(text)
            merged.append('\n'.join(parts))
        return merged

    @staticmethod
    def _determine_column_alignments(rows: list[list[str]],
                                     data_start_idx: int,
                                     col_count: int) -> list[str]:
        """Determine alignment for each column"""
        alignments = []
        for col_idx in range(col_count):
            # First column always left-aligned
            if col_idx == 0:
                alignments.append("left")
                continue

            # Check if column contains numbers
            is_numeric = False
            for row in rows[data_start_idx:]:
                cell = row[col_idx].strip()
                if cell and cell != '$':
                    if TableProcessor._is_financial_value(cell, row, col_idx):
                        is_numeric = True
                        break
            alignments.append("right" if is_numeric else "left")

        return alignments

    @staticmethod
    def _is_financial_value(text: str, row: list, col_idx: int) -> bool:
        """
        Check if text represents a financial value, considering layout context
        Takes the full row and column index to check for adjacent $ symbols
        """
        text = text.strip()

        # If it's a $ symbol by itself, not a financial value
        if text == '$':
            return False

        # Check if it's a number
        is_numeric = is_number(text)

        if not is_numeric:
            return False

        # Look for $ in adjacent columns (considering empty columns in between)
        # Look left for $
        left_idx = col_idx - 1
        while left_idx >= 0:
            left_cell = row[left_idx].strip()
            if left_cell == '$':
                return True
            elif left_cell:  # If we hit any non-empty cell that's not $, stop looking
                break
            left_idx -= 1

        return is_numeric  # If we found a number but no $, still treat as financial value

    @staticmethod
    def _is_financial_metric(text: str) -> bool:
        """Check if text represents a common financial metric"""
        text = text.lower().strip()
        metrics = [
            'revenue', 'sales', 'income', 'earnings', 'profit', 'loss',
            'assets', 'liabilities', 'equity', 'cash', 'expenses',
            'cost', 'margin', 'ebitda', 'eps', 'shares', 'tax',
            'operating', 'net', 'gross', 'total', 'capital',
            'depreciation', 'amortization', 'interest', 'debt'
        ]
        return any(metric in text for metric in metrics)

    @staticmethod
    def _format_data_rows(rows: list[list[str]]) -> list[list[str]]:
        """Format data rows for display"""
        formatted_rows = []
        for row in rows:
            formatted_row = []
            for col_idx, cell in enumerate(row):
                content = cell.strip()
                if col_idx > 0:  # Don't format first column
                    # Handle parenthesized numbers
                    if content.startswith('(') and content.endswith(')'):
                        content = f"-{content[1:-1]}"
                formatted_row.append(content)
            formatted_rows.append(formatted_row)
        return formatted_rows


class ColumnOptimizer:
    """Optimizes column widths for table rendering"""

    def __init__(self, total_width: int = 100, min_data_col_width: int = 15,
                 max_left_col_ratio: float = 0.5, target_left_col_ratio: float = 0.4):
        self.total_width = total_width
        self.min_data_col_width = min_data_col_width
        self.max_left_col_ratio = max_left_col_ratio  # Maximum portion of total width for left column
        self.target_left_col_ratio = target_left_col_ratio  # Target portion for left column

    def _measure_content_width(self, content: str) -> int:
        """Measure the display width of content, handling multiline text"""
        if not content:
            return 0
        lines = content.split('\n')
        return max(len(line) for line in lines)

    def _wrap_text(self, text: str, max_width: int) -> str:
        """
        Wrap text to specified width, preserving existing line breaks and word boundaries.
        If text already contains line breaks, preserve the original formatting.
        """
        if not text or len(text) <= max_width:
            return text

        # If text already contains line breaks, preserve them
        if '\n' in text:
            return text

        # Special handling for financial statement line items
        if ',' in text and ':' in text:
            # Split into main description and details
            parts = text.split(':', 1)
            if len(parts) == 2:
                desc, details = parts
                wrapped_desc = self._wrap_text(desc.strip(), max_width)
                wrapped_details = self._wrap_text(details.strip(), max_width)
                return f"{wrapped_desc}:\n{wrapped_details}"

        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            word_length = len(word)

            # Handle very long words
            if word_length > max_width:
                # If we have a current line, add it first
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = []
                    current_length = 0

                # Split long word across lines
                while word_length > max_width:
                    lines.append(word[:max_width - 1] + '-')
                    word = word[max_width - 1:]
                    word_length = len(word)
                if word:
                    current_line = [word]
                    current_length = word_length
                continue

            if current_length + word_length + (1 if current_line else 0) <= max_width:
                current_line.append(word)
                current_length += word_length + (1 if current_length else 0)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = word_length

        if current_line:
            lines.append(' '.join(current_line))

        return '\n'.join(lines)

    def optimize_columns(self, table: ProcessedTable) -> tuple[list[int], ProcessedTable]:
        """
        Optimize column widths and wrap text as needed.
        Returns (column_widths, modified_table)
        """
        col_count = len(table.data_rows[0]) if table.data_rows else 0
        if not col_count:
            return [], table

        # Calculate maximum left column width based on total width
        max_left_col_width = int(self.total_width * self.max_left_col_ratio)
        target_left_col_width = int(self.total_width * self.target_left_col_ratio)

        # Initialize widths array
        widths = [0] * col_count

        # First pass: calculate minimum required widths for data columns
        for col in range(1, col_count):
            col_content_width = self.min_data_col_width
            if table.headers:
                col_content_width = max(col_content_width,
                                        self._measure_content_width(table.headers[col]))

            # Check numeric data width
            for row in table.data_rows:
                if col < len(row):
                    col_content_width = max(col_content_width,
                                            self._measure_content_width(row[col]))

            widths[col] = col_content_width

        # Calculate available space for left column
        data_cols_width = sum(widths[1:])
        available_left_width = self.total_width - data_cols_width

        # Determine left column width
        left_col_max_content = 0
        if table.headers and table.headers[0]:
            left_col_max_content = self._measure_content_width(table.headers[0])
        for row in table.data_rows:
            if row:
                left_col_max_content = max(left_col_max_content,
                                           self._measure_content_width(row[0]))

        # Set left column width based on constraints
        if left_col_max_content <= target_left_col_width:
            widths[0] = left_col_max_content
        else:
            widths[0] = min(max_left_col_width,
                            max(target_left_col_width, available_left_width))

        # If we still exceed total width, redistribute data column space
        total_width = sum(widths)
        if total_width > self.total_width:
            excess = total_width - self.total_width
            data_cols = len(widths) - 1
            reduction_per_col = excess // data_cols

            # Reduce data columns while ensuring minimum width
            for i in range(1, len(widths)):
                if widths[i] - reduction_per_col >= self.min_data_col_width:
                    widths[i] -= reduction_per_col

        # Apply width constraints and wrap text
        modified_table = self._apply_column_constraints(table, widths)

        return widths, modified_table

    def _apply_column_constraints(self, table: ProcessedTable, widths: list[int]) -> ProcessedTable:
        """Apply width constraints to table content, wrapping text as needed"""
        # Wrap headers if present
        wrapped_headers = None
        if table.headers:
            wrapped_headers = [
                self._wrap_text(header, widths[i])
                for i, header in enumerate(table.headers)
            ]

        # Wrap data in first column only
        wrapped_rows = []
        for row in table.data_rows:
            wrapped_row = list(row)  # Make a copy
            wrapped_row[0] = self._wrap_text(row[0], widths[0])
            wrapped_rows.append(wrapped_row)

        return ProcessedTable(
            headers=wrapped_headers,
            data_rows=wrapped_rows,
            column_alignments=table.column_alignments
        )