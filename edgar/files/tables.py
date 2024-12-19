from dataclasses import dataclass
from typing import Optional
import re


@dataclass
class ProcessedTable:
    """Represents a processed table ready for rendering"""
    headers: Optional[list[str]]
    data_rows: list[list[str]]
    column_alignments: list[str]  # "left" or "right" for each column


class TableProcessor:
    @staticmethod
    def process_table(node) -> Optional[ProcessedTable]:
        """Process table node into a format ready for rendering"""
        if not isinstance(node.content, list) or not node.content:
            return None

        def process_cell_content(content: str) -> str:
            """Process cell content to handle HTML breaks and cleanup"""
            content = content.replace('<br/>', '\n').replace('<br>', '\n')
            lines = [line.strip() for line in content.split('\n')]
            return '\n'.join(line for line in lines if line)

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

        # Process headers
        headers = None
        if header_rows:
            headers = TableProcessor._merge_header_rows(header_rows)

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
    def _get_period_header_pattern() -> re.Pattern:
        """Create regex pattern for common financial period headers"""
        periods = r'(?:three|six|nine|twelve|[1-4]|first|second|third|fourth)'
        timeframes = r'(?:month|quarter|year|week)'
        ended_variants = r'(?:ended|ending|end|period)'
        date_patterns = r'(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}'
        years = r'(?:19|20)\d{2}'

        # Combine into flexible patterns that match common variations
        patterns = [
            # "Three Months Ended December 31,"
            fr'{periods}\s+{timeframes}\s+{ended_variants}(?:\s+{date_patterns})?',
            # "Fiscal Year Ended"
            fr'(?:fiscal\s+)?{timeframes}\s+{ended_variants}',
            # "Quarters Ended June 30, 2023"
            fr'{timeframes}\s+{ended_variants}(?:\s+{date_patterns})?(?:\s*,?\s*{years})?'
        ]

        # Combine all patterns with non-capturing group
        combined_pattern = '|'.join(f'(?:{p})' for p in patterns)
        return re.compile(combined_pattern, re.IGNORECASE)

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
        for i, row in enumerate(rows[:3]):  # Check first 3 rows
            header_text = ' '.join(cell.strip() for cell in row).lower()
            if period_pattern.search(header_text):
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

        # First check if it's a standalone number
        def is_number(s: str) -> bool:
            # Remove commas, spaces, parentheses
            s = s.replace(",", "").replace(" ", "").strip("()")
            try:
                float(s)
                return True
            except ValueError:
                return False

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
