"""
Table matrix builder for handling complex colspan/rowspan structures.
"""

from dataclasses import dataclass
from typing import List, Optional

from edgar.documents.table_nodes import Cell, Row


@dataclass
class MatrixCell:
    """Cell in the matrix with reference to original cell"""
    original_cell: Optional[Cell] = None
    is_spanned: bool = False  # True if this is part of a colspan/rowspan
    row_origin: int = -1  # Original row index
    col_origin: int = -1  # Original column index
    

class TableMatrix:
    """
    Build a 2D matrix representation of table with proper handling of merged cells.
    
    This class converts a table with colspan/rowspan into a regular 2D grid
    where each merged cell occupies multiple positions in the matrix.
    """
    
    def __init__(self):
        """Initialize empty matrix"""
        self.matrix: List[List[MatrixCell]] = []
        self.row_count = 0
        self.col_count = 0
        self.header_row_count = 0  # Track number of header rows

    def build_from_rows(self, header_rows: List[List[Cell]], data_rows: List[Row]) -> 'TableMatrix':
        """
        Build matrix from header rows and data rows.

        Args:
            header_rows: List of header rows (each row is a list of Cells)
            data_rows: List of Row objects

        Returns:
            Self for chaining
        """
        # Store header row count for later use
        self.header_row_count = len(header_rows)

        # Combine all rows for processing
        all_rows = []

        # Add header rows
        for header_row in header_rows:
            all_rows.append(header_row)
        
        # Add data rows
        for row in data_rows:
            all_rows.append(row.cells)
        
        if not all_rows:
            return self
        
        # Calculate dimensions
        self.row_count = len(all_rows)
        
        # First pass: determine actual column count
        self._calculate_dimensions(all_rows)
        
        # Initialize matrix
        self.matrix = [[MatrixCell() for _ in range(self.col_count)] 
                       for _ in range(self.row_count)]
        
        # Second pass: place cells in matrix
        self._place_cells(all_rows)
        
        return self
    
    def _calculate_dimensions(self, rows: List[List[Cell]]):
        """Calculate the actual dimensions considering colspan"""
        max_cols = 0
        
        for row_idx, row in enumerate(rows):
            col_pos = 0
            for cell in row:
                # Skip positions that might be occupied by rowspan from above
                while col_pos < max_cols and self._is_occupied(row_idx, col_pos):
                    col_pos += 1
                
                # This cell will occupy from col_pos to col_pos + colspan
                col_end = col_pos + cell.colspan
                max_cols = max(max_cols, col_end)
                col_pos = col_end
        
        self.col_count = max_cols
    
    def _is_occupied(self, row: int, col: int) -> bool:
        """Check if a position is occupied by a cell from a previous row (rowspan)"""
        if row == 0:
            return False
        
        # Check if any cell above has rowspan that reaches this position
        for prev_row in range(row):
            if prev_row < len(self.matrix) and col < len(self.matrix[prev_row]):
                cell = self.matrix[prev_row][col]
                if cell.original_cell and cell.row_origin == prev_row:
                    # Check if this cell's rowspan reaches current row
                    if prev_row + cell.original_cell.rowspan > row:
                        return True
        return False
    
    def _place_cells(self, rows: List[List[Cell]]):
        """Place cells in the matrix handling colspan and rowspan"""
        for row_idx, row in enumerate(rows):
            col_pos = 0
            
            for cell_idx, cell in enumerate(row):
                # Find next available column position
                while col_pos < self.col_count and self.matrix[row_idx][col_pos].original_cell is not None:
                    col_pos += 1
                
                if col_pos >= self.col_count:
                    # Need to expand matrix
                    self._expand_columns(col_pos + cell.colspan)
                
                # Special handling for cells with colspan > 1 containing numeric values
                # Only apply this logic for Table 15-style alignment issues
                # Check if this looks like a financial value that should be right-aligned
                cell_text = cell.text().strip()
                
                # Check for numeric values that need special alignment
                # This is specifically for cases like "167,045" that should align with "$167,045"
                has_comma_separator = ',' in cell_text
                digit_ratio = sum(c.isdigit() for c in cell_text) / len(cell_text) if cell_text else 0
                
                # Only apply special placement for colspan=2 numeric values in data rows
                # This handles Table 15's specific case without breaking Table 13
                is_special_numeric = (cell.colspan == 2 and  # Specifically colspan=2
                                    has_comma_separator and
                                    digit_ratio > 0.5 and  # More than 50% digits
                                    not cell_text.startswith('$') and
                                    not any(month in cell_text.lower() for month in 
                                           ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 
                                            'jul', 'aug', 'sep', 'oct', 'nov', 'dec']) and
                                    row_idx > 1)  # Not a header row (allow for multi-row headers)
                
                if is_special_numeric:
                    # Place empty cell at first position, content at second position
                    # This is specifically for Table 15 alignment
                    for r in range(cell.rowspan):
                        # First column of span: empty
                        if row_idx + r < self.row_count and col_pos < self.col_count:
                            self.matrix[row_idx + r][col_pos] = MatrixCell()
                        
                        # Second column of span: the actual content
                        if row_idx + r < self.row_count and col_pos + 1 < self.col_count:
                            matrix_cell = MatrixCell(
                                original_cell=cell,
                                is_spanned=False,
                                row_origin=row_idx,
                                col_origin=col_pos + 1
                            )
                            self.matrix[row_idx + r][col_pos + 1] = matrix_cell
                        
                        # Remaining columns of span: mark as spanned (though colspan=2 has no remaining)
                        for c in range(2, cell.colspan):
                            if row_idx + r < self.row_count and col_pos + c < self.col_count:
                                matrix_cell = MatrixCell(
                                    original_cell=cell,
                                    is_spanned=True,
                                    row_origin=row_idx,
                                    col_origin=col_pos + 1
                                )
                                self.matrix[row_idx + r][col_pos + c] = matrix_cell
                else:
                    # Normal placement for other cells
                    for r in range(cell.rowspan):
                        for c in range(cell.colspan):
                            if row_idx + r < self.row_count and col_pos + c < self.col_count:
                                matrix_cell = MatrixCell(
                                    original_cell=cell,
                                    is_spanned=(r > 0 or c > 0),
                                    row_origin=row_idx,
                                    col_origin=col_pos
                                )
                                self.matrix[row_idx + r][col_pos + c] = matrix_cell
                
                col_pos += cell.colspan
    
    def _expand_columns(self, new_col_count: int):
        """Expand matrix to accommodate more columns"""
        if new_col_count <= self.col_count:
            return
        
        for row in self.matrix:
            row.extend([MatrixCell() for _ in range(new_col_count - self.col_count)])
        
        self.col_count = new_col_count
    
    def get_actual_columns(self) -> int:
        """Get the actual number of data columns (excluding empty/spacing columns)"""
        non_empty_cols = 0
        
        for col_idx in range(self.col_count):
            has_content = False
            for row_idx in range(self.row_count):
                cell = self.matrix[row_idx][col_idx]
                if cell.original_cell and not cell.is_spanned:
                    # Check if cell has actual content
                    text = cell.original_cell.text().strip()
                    if text and text not in ['', ' ', '\xa0']:
                        has_content = True
                        break
            
            if has_content:
                non_empty_cols += 1
        
        return non_empty_cols
    
    def get_column_widths(self) -> List[float]:
        """Estimate column widths based on content"""
        widths = []
        
        for col_idx in range(self.col_count):
            max_width = 0
            content_count = 0
            
            for row_idx in range(self.row_count):
                cell = self.matrix[row_idx][col_idx]
                if cell.original_cell and not cell.is_spanned:
                    text = cell.original_cell.text().strip()
                    if text:
                        max_width = max(max_width, len(text))
                        content_count += 1
            
            # If column has no content, it's likely a spacing column
            if content_count == 0:
                widths.append(0)
            else:
                widths.append(max_width)
        
        return widths
    
    def get_cell(self, row_idx: int, col_idx: int) -> Optional[Cell]:
        """
        Get a cell at specific position in the matrix.
        
        Args:
            row_idx: Row index
            col_idx: Column index
            
        Returns:
            Cell at position or None if out of bounds
        """
        if row_idx >= self.row_count or col_idx >= self.col_count or row_idx < 0 or col_idx < 0:
            return None
        
        matrix_cell = self.matrix[row_idx][col_idx]
        
        # Return the original cell
        if matrix_cell.original_cell:
            return matrix_cell.original_cell
        
        # Return empty cell for empty positions
        return Cell("")
    
    def get_expanded_row(self, row_idx: int) -> List[Optional[Cell]]:
        """
        Get a row with cells expanded to match column count.
        
        For cells with colspan > 1, the cell appears in the first position
        and None in subsequent positions.
        """
        if row_idx >= self.row_count:
            return []
        
        expanded = []
        for col_idx in range(self.col_count):
            matrix_cell = self.matrix[row_idx][col_idx]
            if matrix_cell.original_cell:
                if not matrix_cell.is_spanned:
                    # This is the origin cell
                    expanded.append(matrix_cell.original_cell)
                else:
                    # This is a spanned position
                    expanded.append(None)
            else:
                # Empty cell
                expanded.append(None)
        
        return expanded
    
    def get_data_columns(self) -> List[int]:
        """
        Get indices of columns that contain actual data (not spacing).
        Uses strategy similar to old parser - keeps single empty columns for spacing.
        
        Returns:
            List of column indices that contain data
        """
        # First, identify which columns are empty
        empty_cols = []
        for col_idx in range(self.col_count):
            has_content = False
            for row_idx in range(self.row_count):
                cell = self.matrix[row_idx][col_idx]
                if cell.original_cell and not cell.is_spanned:
                    text = cell.original_cell.text().strip()
                    if text:
                        has_content = True
                        break
            if not has_content:
                empty_cols.append(col_idx)
        
        # Apply old parser's strategy
        cols_to_remove = set()
        
        # Remove leading empty columns
        for col in range(self.col_count):
            if col in empty_cols:
                cols_to_remove.add(col)
            else:
                break
        
        # Remove trailing empty columns
        for col in reversed(range(self.col_count)):
            if col in empty_cols:
                cols_to_remove.add(col)
            else:
                break
        
        # Remove consecutive empty columns in the middle (keep single empty cols for spacing)
        i = 0
        while i < self.col_count - 1:
            if i in empty_cols and (i + 1) in empty_cols:
                # Found consecutive empty columns
                consecutive_count = 0
                j = i
                while j < self.col_count and j in empty_cols:
                    consecutive_count += 1
                    j += 1
                # Keep first empty column as spacer, remove the rest
                cols_to_remove.update(range(i + 1, i + consecutive_count))
                i = j
            else:
                i += 1
        
        # Return columns that are NOT in the removal set
        data_cols = [col for col in range(self.col_count) if col not in cols_to_remove]
        
        return data_cols
    
    def filter_spacing_columns(self) -> 'TableMatrix':
        """
        Create a new matrix with spacing columns removed.
        Also handles colspan-generated duplicate columns and misalignment.
        
        Returns:
            New TableMatrix with only data columns
        """
        # First pass: identify primary header columns (those with colspan > 1 headers)
        # and data columns
        primary_header_cols = set()
        all_header_cols = set()
        data_cols = set()
        
        # Find primary header columns (those that start a colspan)
        for row_idx in range(min(3, self.row_count)):
            for col_idx in range(self.col_count):
                cell = self.matrix[row_idx][col_idx]
                if cell.original_cell and not cell.is_spanned:
                    if cell.original_cell.text().strip():
                        all_header_cols.add(col_idx)
                        # Check if this is a primary header (colspan > 1)
                        if cell.original_cell.colspan > 1:
                            primary_header_cols.add(col_idx)
        
        # If no primary headers found, use all headers as primary
        if not primary_header_cols:
            primary_header_cols = all_header_cols

        # Phase 1.5: Identify columns with header content
        # Any column with non-empty text in ANY header row must be preserved
        # This prevents legitimate header columns from being removed as "spacing"
        # Also preserve columns that are spanned by headers (colspan > 1)
        header_content_columns = set()
        for col_idx in range(self.col_count):
            for row_idx in range(self.header_row_count):
                cell = self.matrix[row_idx][col_idx]
                if cell.original_cell:
                    # Check for original header cell with content
                    if not cell.is_spanned:
                        text = cell.original_cell.text().strip()
                        if text:
                            header_content_columns.add(col_idx)
                            # Also add all columns spanned by this header
                            if cell.original_cell.colspan > 1:
                                for span_offset in range(1, cell.original_cell.colspan):
                                    span_col = col_idx + span_offset
                                    if span_col < self.col_count:
                                        header_content_columns.add(span_col)
                            break  # Found content, no need to check other header rows
                    # Also preserve columns that are spanned (part of a colspan)
                    elif cell.is_spanned:
                        # This column is part of a header's colspan
                        text = cell.original_cell.text().strip()
                        if text:
                            header_content_columns.add(col_idx)

        # Find columns with data (skip header rows)
        # Count actual header rows by checking for non-data content
        actual_header_rows = 0
        for row_idx in range(min(3, self.row_count)):
            has_numeric_data = False
            for col_idx in range(self.col_count):
                cell = self.matrix[row_idx][col_idx]
                if cell.original_cell and not cell.is_spanned:
                    text = cell.original_cell.text().strip()
                    # Check if it looks like numeric data (has commas or starts with $)
                    if text and (',' in text and any(c.isdigit() for c in text)) or text == '$':
                        has_numeric_data = True
                        break
            if has_numeric_data:
                break
            actual_header_rows += 1
        
        data_start_row = max(1, actual_header_rows)
        
        # Track columns with significant data (not just isolated cells)
        col_data_count = {}
        for row_idx in range(data_start_row, self.row_count):
            for col_idx in range(self.col_count):
                cell = self.matrix[row_idx][col_idx]
                if cell.original_cell and not cell.is_spanned:
                    if cell.original_cell.text().strip():
                        data_cols.add(col_idx)
                        col_data_count[col_idx] = col_data_count.get(col_idx, 0) + 1
        
        # Build initial list of columns to keep
        # Always include column 0 if it contains row labels
        cols_to_keep = set(primary_header_cols)

        # Add columns with header content (prevents removing legitimate headers)
        cols_to_keep.update(header_content_columns)
        
        # Identify misaligned data columns that need to be consolidated
        # These are data columns that are not primary header columns
        misaligned_data_cols = data_cols - primary_header_cols
        
        # Map misaligned data columns to their nearest column for consolidation
        # Only consolidate directly adjacent columns with specific patterns
        consolidation_map = {}
        
        # First pass: identify all potential consolidations
        potential_consolidations = {}
        for data_col in sorted(misaligned_data_cols):
            # Check if this column should be consolidated with an adjacent column
            # Check the column immediately before this one
            prev_col = data_col - 1
            
            # Sample some cells to see if consolidation makes sense
            consolidation_type = None
            
            for row_idx in range(data_start_row, min(data_start_row + 10, self.row_count)):
                prev_cell = self.matrix[row_idx][prev_col] if prev_col >= 0 else None
                curr_cell = self.matrix[row_idx][data_col]
                
                if prev_cell and prev_cell.original_cell and curr_cell.original_cell:
                    prev_text = prev_cell.original_cell.text().strip()
                    curr_text = curr_cell.original_cell.text().strip()
                    
                    # Skip empty cells
                    if not prev_text or not curr_text:
                        continue
                    
                    # Check for patterns that indicate consolidation
                    if prev_text == '$' and curr_text and curr_text[0].isdigit():
                        consolidation_type = 'currency'
                        break
                    elif prev_text.startswith('(') and curr_text == ')':
                        consolidation_type = 'parentheses'
                        break
                    elif curr_text == '%' and prev_text and prev_text[-1].isdigit():
                        consolidation_type = 'percentage'
                        break
            
            if consolidation_type:
                potential_consolidations[data_col] = (prev_col, consolidation_type)
        
        # Second pass: resolve conflicts
        # If column Y is a target for consolidation from Y+1 (e.g., parentheses),
        # then don't consolidate Y into another column
        columns_needed_as_targets = set()
        for data_col, (target_col, cons_type) in potential_consolidations.items():
            if cons_type == 'parentheses':
                # This target column is needed for parentheses consolidation
                columns_needed_as_targets.add(target_col)
        
        # Build final consolidation map, skipping consolidations that would remove needed targets
        for data_col, (target_col, cons_type) in potential_consolidations.items():
            # Don't consolidate this column if it's needed as a target for parentheses
            if data_col in columns_needed_as_targets and cons_type != 'parentheses':
                continue

            # CRITICAL: Don't consolidate columns that have header content
            # This prevents legitimate header columns from being merged together
            if data_col in header_content_columns or target_col in header_content_columns:
                continue

            consolidation_map[data_col] = target_col
            # Debug: uncomment to see consolidation mapping
            # import os
            # if os.environ.get('DEBUG_TABLE_CONSOLIDATION'):
            #     print(f"Consolidating column {data_col} into {target_col}")
        
        # Special case: Keep data columns that are associated with header columns
        # This handles cases where headers span multiple columns but data is in specific columns
        for header_col in primary_header_cols:
            # Check if there's a data column immediately after the header column
            # This is common when headers span multiple columns
            for offset in range(1, 3):  # Check next 1-2 columns
                data_col = header_col + offset
                if data_col in data_cols and data_col not in cols_to_keep:
                    # Check if this column has meaningful data
                    has_data = False
                    for row_idx in range(data_start_row, min(data_start_row + 5, self.row_count)):
                        cell = self.matrix[row_idx][data_col]
                        if cell.original_cell and not cell.is_spanned:
                            text = cell.original_cell.text().strip()
                            if text and text not in ['', '-', '—', '–']:
                                has_data = True
                                break
                    if has_data:
                        cols_to_keep.add(data_col)
        
        # Keep data columns that have significant content but aren't near header columns
        # This includes columns with dates, text descriptions, etc.
        for col_idx in data_cols:
            if col_idx not in cols_to_keep:
                # Check if this column has important data
                has_important_data = False
                non_empty_count = 0
                text_samples = []
                
                for row_idx in range(data_start_row, min(data_start_row + 10, self.row_count)):
                    cell = self.matrix[row_idx][col_idx]
                    if cell.original_cell and not cell.is_spanned:
                        text = cell.original_cell.text().strip()
                        if text and text not in ['', '-', '—', '–']:
                            non_empty_count += 1
                            if len(text_samples) < 3:
                                text_samples.append(text)
                            
                            # Check for important patterns
                            # Dates, years, text descriptions, etc.
                            if any([
                                len(text) > 3 and not text.replace(',', '').replace('.', '').isdigit(),  # Non-trivial text
                                any(month in text for month in ['January', 'February', 'March', 'April', 'May', 'June', 
                                                                'July', 'August', 'September', 'October', 'November', 'December']),
                                any(month in text for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                                                                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']),
                                '20' in text and any(c.isdigit() for c in text),  # Likely contains year
                            ]):
                                has_important_data = True
                
                # Keep columns with consistent important data
                if has_important_data and non_empty_count >= 3:
                    cols_to_keep.add(col_idx)
        
        # Special case: If we have very few primary headers but lots of data columns,
        # we might have a table where headers are in data rows (like years)
        # Keep columns that have significant financial data
        if len(primary_header_cols) <= 2 and len(data_cols) > 4:
            # Check for financial data patterns in columns
            for col_idx in data_cols:
                has_financial_data = False
                sample_count = 0
                
                # Sample a few cells from this column
                for row_idx in range(data_start_row, min(data_start_row + 5, self.row_count)):
                    cell = self.matrix[row_idx][col_idx]
                    if cell.original_cell and not cell.is_spanned:
                        text = cell.original_cell.text().strip()
                        if text:
                            sample_count += 1
                            # Check for financial patterns
                            if any([
                                text.startswith('(') and any(c.isdigit() for c in text),  # Negative numbers
                                text == ')' and col_idx > 0,  # Closing parenthesis
                                '$' in text,  # Currency
                                '%' in text,  # Percentages
                                text.replace(',', '').replace('.', '').isdigit(),  # Plain numbers
                                text in ['—', '–', '-', '*']  # Common placeholders
                            ]):
                                has_financial_data = True
                                break
                
                # Keep columns with financial data
                if has_financial_data and sample_count > 0:
                    cols_to_keep.add(col_idx)
        
        # Check if column 0 contains row labels (non-empty cells in data rows)
        col_0_has_labels = False
        data_start_row = max(1, actual_header_rows)
        for row_idx in range(data_start_row, self.row_count):
            cell = self.matrix[row_idx][0]
            if cell.original_cell and not cell.is_spanned:
                text = cell.original_cell.text().strip()
                if text and not text.isdigit() and not text.startswith('$') and len(text) > 1:
                    col_0_has_labels = True
                    break
        
        # Include column 0 if it has labels
        if col_0_has_labels:
            cols_to_keep.add(0)
        
        # Remove columns that will be consolidated into other columns
        # These columns' data will be merged into their target columns
        cols_to_remove = set(consolidation_map.keys())
        cols_to_keep = cols_to_keep - cols_to_remove
        
        cols_to_keep = sorted(cols_to_keep)
        
        # Create new matrix with consolidated columns
        if not cols_to_keep:
            return self
        
        new_matrix = TableMatrix()
        new_matrix.row_count = self.row_count
        new_matrix.col_count = len(cols_to_keep)
        new_matrix.header_row_count = self.header_row_count  # Preserve header row count
        new_matrix.matrix = []
        
        # Create mapping from old to new column indices
        old_to_new = {old_col: new_idx for new_idx, old_col in enumerate(cols_to_keep)}
        
        # Build new matrix with consolidation
        for row_idx in range(self.row_count):
            new_row = [MatrixCell() for _ in range(new_matrix.col_count)]
            
            # Track which cells we've already placed to handle colspan properly
            placed_origins = {}  # Maps (row_origin, col_origin) to new column index
            
            # First, copy cells from kept columns
            for old_col in sorted(cols_to_keep):
                if old_col not in old_to_new:
                    continue
                new_col = old_to_new[old_col]
                cell = self.matrix[row_idx][old_col]
                if cell.original_cell:
                    origin_key = (cell.row_origin, cell.col_origin)
                    
                    # Check if we've already placed this cell (due to colspan)
                    if origin_key in placed_origins:
                        # This is a continuation of a colspan - mark as spanned
                        new_row[new_col] = MatrixCell(
                            original_cell=cell.original_cell,
                            is_spanned=True,  # Mark as spanned since it's part of a colspan
                            row_origin=cell.row_origin,
                            col_origin=placed_origins[origin_key]  # Point to the original placement
                        )
                    else:
                        # First occurrence of this cell - place normally
                        new_row[new_col] = MatrixCell(
                            original_cell=cell.original_cell,
                            is_spanned=False,  # This is the primary cell
                            row_origin=cell.row_origin,
                            col_origin=new_col
                        )
                        placed_origins[origin_key] = new_col
            
            # Then, consolidate misaligned data into header columns
            for data_col, header_col in consolidation_map.items():
                if header_col in old_to_new:
                    new_col = old_to_new[header_col]
                    data_cell = self.matrix[row_idx][data_col] if data_col < len(self.matrix[row_idx]) else None
                    
                    
                    # If data cell has content, merge it with header column
                    if data_cell and data_cell.original_cell and not data_cell.is_spanned:
                        # Skip empty data cells
                        if not data_cell.original_cell.text().strip():
                            continue
                        # Check the original header column cell to see if it has content to merge
                        header_cell = self.matrix[row_idx][header_col]
                        existing_cell = new_row[new_col]
                        
                        # Check if we need to merge (e.g., $ with value)
                        if header_cell.original_cell and header_cell.original_cell.text().strip():
                            existing_text = header_cell.original_cell.text().strip()
                            new_text = data_cell.original_cell.text().strip()
                            
                            
                            # Merge currency symbol with value OR value with percentage OR parentheses
                            if existing_text == '$' and new_text:
                                # Currency merge: $ + number
                                merged_text = f"${new_text}"
                                # Create new cell with merged content
                                merged_cell = Cell(
                                    content=merged_text,
                                    colspan=header_cell.original_cell.colspan,
                                    rowspan=header_cell.original_cell.rowspan,
                                    is_header=header_cell.original_cell.is_header,
                                    align=data_cell.original_cell.align if hasattr(data_cell.original_cell, 'align') else None
                                )
                                new_row[new_col] = MatrixCell(
                                    original_cell=merged_cell,
                                    is_spanned=False,
                                    row_origin=row_idx,
                                    col_origin=new_col
                                )
                            elif new_text == ')' and existing_text.startswith('('):
                                # Parentheses merge: (number + )
                                merged_text = f"{existing_text})"
                                # Create new cell with merged content
                                merged_cell = Cell(
                                    content=merged_text,
                                    colspan=header_cell.original_cell.colspan,
                                    rowspan=header_cell.original_cell.rowspan,
                                    is_header=header_cell.original_cell.is_header,
                                    align=data_cell.original_cell.align if hasattr(data_cell.original_cell, 'align') else None
                                )
                                new_row[new_col] = MatrixCell(
                                    original_cell=merged_cell,
                                    is_spanned=False,
                                    row_origin=row_idx,
                                    col_origin=new_col
                                )
                            elif new_text == '%' and existing_text:
                                # Percentage merge: number + %
                                merged_text = f"{existing_text}%"
                                # Create new cell with merged content
                                merged_cell = Cell(
                                    content=merged_text,
                                    colspan=header_cell.original_cell.colspan,
                                    rowspan=header_cell.original_cell.rowspan,
                                    is_header=header_cell.original_cell.is_header,
                                    align=header_cell.original_cell.align if hasattr(header_cell.original_cell, 'align') else None
                                )
                                new_row[new_col] = MatrixCell(
                                    original_cell=merged_cell,
                                    is_spanned=False,
                                    row_origin=row_idx,
                                    col_origin=new_col
                                )
                            else:
                                # Just keep the data cell if can't merge
                                new_row[new_col] = MatrixCell(
                                    original_cell=data_cell.original_cell,
                                    is_spanned=False,
                                    row_origin=row_idx,
                                    col_origin=new_col
                                )
                        else:
                            # No existing content, just move the data
                            new_row[new_col] = MatrixCell(
                                original_cell=data_cell.original_cell,
                                is_spanned=False,
                                row_origin=row_idx,
                                col_origin=new_col
                            )
            
            new_matrix.matrix.append(new_row)
        
        return new_matrix
    
    def to_cell_grid(self) -> List[List[Optional[Cell]]]:
        """
        Convert matrix to a simple 2D grid of cells.
        
        Returns:
            2D list where each position contains either a Cell or None
        """
        grid = []
        
        for row_idx in range(self.row_count):
            row = []
            for col_idx in range(self.col_count):
                matrix_cell = self.matrix[row_idx][col_idx]
                if matrix_cell.original_cell and not matrix_cell.is_spanned:
                    row.append(matrix_cell.original_cell)
                else:
                    row.append(None)
            grid.append(row)
        
        return grid
    
    def debug_print(self):
        """Print matrix structure for debugging"""
        print(f"Matrix: {self.row_count}×{self.col_count}")
        
        for row_idx in range(self.row_count):
            row_str = []
            for col_idx in range(self.col_count):
                cell = self.matrix[row_idx][col_idx]
                if cell.original_cell:
                    text = cell.original_cell.text()[:10]
                    if cell.is_spanned:
                        row_str.append(f"[{text}...]")
                    else:
                        row_str.append(f"{text}...")
                else:
                    row_str.append("___")
            print(f"Row {row_idx}: {' | '.join(row_str)}")


class ColumnAnalyzer:
    """Analyze column structure to identify data vs spacing columns"""
    
    def __init__(self, matrix: TableMatrix):
        """Initialize with a table matrix"""
        self.matrix = matrix
    
    def identify_spacing_columns(self) -> List[int]:
        """
        Identify columns used only for spacing.
        
        Returns:
            List of column indices that are spacing columns
        """
        spacing_cols = []
        widths = self.matrix.get_column_widths()
        total_width = sum(widths)
        
        for col_idx in range(self.matrix.col_count):
            if self._is_spacing_column(col_idx, widths, total_width):
                spacing_cols.append(col_idx)
        
        return spacing_cols
    
    def _is_spacing_column(self, col_idx: int, widths: List[float], total_width: float) -> bool:
        """
        Check if a column is used for spacing.
        Only mark as spacing if column is completely empty.
        
        Criteria:
        - Column has absolutely no content across all rows
        """
        # Check if column is completely empty
        for row_idx in range(self.matrix.row_count):
            cell = self.matrix.matrix[row_idx][col_idx]
            if cell.original_cell and not cell.is_spanned:
                text = cell.original_cell.text().strip()
                # If there's any text at all, it's not a spacing column
                if text:
                    return False
        
        # Column is completely empty
        return True
    
    def get_clean_column_indices(self) -> List[int]:
        """
        Get indices of non-spacing columns.
        
        Returns:
            List of column indices that contain actual data
        """
        spacing = set(self.identify_spacing_columns())
        return [i for i in range(self.matrix.col_count) if i not in spacing]