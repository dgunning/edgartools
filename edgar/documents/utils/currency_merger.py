"""
Currency column merger for handling separated currency symbols in SEC filings.
"""

import re
from typing import List, Tuple

from edgar.documents.table_nodes import Cell
from edgar.documents.utils.table_matrix import TableMatrix, MatrixCell


class CurrencyColumnMerger:
    """
    Detects and merges currency symbol columns with their value columns.
    
    SEC filings often split currency values into two cells:
    - Cell 1: "$" (left-aligned)
    - Cell 2: "224.11" (right-aligned)
    
    This class detects this pattern and merges them into "$224.11"
    """
    
    # Common currency symbols
    CURRENCY_SYMBOLS = {'$', '€', '£', '¥', '₹', 'Rs', 'USD', 'EUR', 'GBP'}
    
    # Pattern for numeric values (with commas, decimals)
    NUMERIC_PATTERN = re.compile(r'^[\d,]+\.?\d*$')
    
    def __init__(self, matrix: TableMatrix):
        """Initialize with a table matrix."""
        self.matrix = matrix
        self.merge_pairs: List[Tuple[int, int]] = []
        
    def detect_currency_pairs(self) -> List[Tuple[int, int]]:
        """
        Detect column pairs that should be merged (currency symbol + value).
        
        Returns:
            List of (symbol_col, value_col) pairs to merge
        """
        pairs = []
        
        for col_idx in range(self.matrix.col_count - 1):
            if self._is_currency_column(col_idx):
                next_col = col_idx + 1
                if self._is_numeric_column(next_col):
                    # Check if they're consistently paired
                    if self._verify_pairing(col_idx, next_col):
                        pairs.append((col_idx, next_col))
        
        self.merge_pairs = pairs
        return pairs
    
    def _is_currency_column(self, col_idx: int) -> bool:
        """
        Check if a column contains only currency symbols.
        
        A currency column typically:
        - Contains only currency symbols or empty cells
        - Has very narrow width (1-3 characters)
        - Is left-aligned (though we check content, not style)
        """
        currency_count = 0
        empty_count = 0
        other_count = 0
        header_rows = 0
        
        for row_idx in range(self.matrix.row_count):
            cell = self.matrix.matrix[row_idx][col_idx]
            if cell.original_cell and not cell.is_spanned:
                text = cell.original_cell.text().strip()
                
                # Skip header rows (first 2 rows typically)
                if row_idx < 2 and text and not text in self.CURRENCY_SYMBOLS:
                    header_rows += 1
                    continue
                
                if not text:
                    empty_count += 1
                elif text in self.CURRENCY_SYMBOLS or text == '$':
                    currency_count += 1
                elif len(text) <= 3 and text in ['$', '€', '£', '¥']:
                    currency_count += 1
                else:
                    other_count += 1
        
        # Column should be mostly currency symbols with some empty cells
        # Exclude header rows from the calculation
        total_non_empty = currency_count + other_count
        if total_non_empty == 0:
            return False
        
        # At least 60% of non-empty, non-header cells should be currency symbols
        # Lower threshold since we're excluding headers
        # Also accept if there's at least 1 currency symbol and no other non-currency content
        return (currency_count >= 1 and other_count == 0) or \
               (currency_count >= 2 and currency_count / total_non_empty >= 0.6)
    
    def _is_numeric_column(self, col_idx: int) -> bool:
        """
        Check if a column contains numeric values.
        """
        numeric_count = 0
        non_empty_count = 0
        
        for row_idx in range(self.matrix.row_count):
            cell = self.matrix.matrix[row_idx][col_idx]
            if cell.original_cell and not cell.is_spanned:
                text = cell.original_cell.text().strip()
                
                # Skip header rows
                if row_idx < 2:
                    continue
                    
                if text:
                    non_empty_count += 1
                    # Remove formatting and check if numeric
                    clean_text = text.replace(',', '').replace('%', '').replace('(', '').replace(')', '')
                    if self.NUMERIC_PATTERN.match(clean_text):
                        numeric_count += 1
        
        if non_empty_count == 0:
            return False
        
        # At least 60% should be numeric (lowered threshold)
        return numeric_count / non_empty_count >= 0.6
    
    def _verify_pairing(self, symbol_col: int, value_col: int) -> bool:
        """
        Verify that symbol and value columns are consistently paired.
        
        They should have content in the same rows (when symbol present, value present).
        """
        paired_rows = 0
        mismatched_rows = 0
        
        for row_idx in range(self.matrix.row_count):
            symbol_cell = self.matrix.matrix[row_idx][symbol_col]
            value_cell = self.matrix.matrix[row_idx][value_col]
            
            if symbol_cell.original_cell and value_cell.original_cell:
                symbol_text = symbol_cell.original_cell.text().strip()
                value_text = value_cell.original_cell.text().strip()
                
                # Check if they're paired (both have content or both empty)
                if symbol_text in self.CURRENCY_SYMBOLS and value_text:
                    paired_rows += 1
                elif not symbol_text and not value_text:
                    # Both empty is fine
                    pass
                elif symbol_text in self.CURRENCY_SYMBOLS and not value_text:
                    # Symbol without value - might be header
                    if row_idx < 2:  # Allow in headers
                        pass
                    else:
                        mismatched_rows += 1
                elif not symbol_text and value_text:
                    # Value without symbol - could be valid (continuation)
                    pass
        
        # Should have more paired than mismatched
        return paired_rows > mismatched_rows
    
    def apply_merges(self) -> 'TableMatrix':
        """
        Create a new matrix with currency columns merged.
        
        Returns:
            New TableMatrix with merged columns
        """
        if not self.merge_pairs:
            self.detect_currency_pairs()
        
        if not self.merge_pairs:
            # No merges needed
            return self.matrix
        
        # Calculate new column count (each merge removes one column)
        new_col_count = self.matrix.col_count - len(self.merge_pairs)
        
        # Create mapping from old to new columns
        old_to_new = {}
        merged_cols = set(pair[0] for pair in self.merge_pairs)  # Symbol columns to remove
        
        new_col = 0
        for old_col in range(self.matrix.col_count):
            if old_col in merged_cols:
                # This column will be merged with next, skip it
                continue
            old_to_new[old_col] = new_col
            new_col += 1
        
        # Create new matrix
        new_matrix = TableMatrix()
        new_matrix.row_count = self.matrix.row_count
        new_matrix.col_count = new_col_count
        new_matrix.matrix = []
        
        # Build new matrix with merged cells
        for row_idx in range(self.matrix.row_count):
            new_row = [MatrixCell() for _ in range(new_col_count)]
            
            for old_col in range(self.matrix.col_count):
                # Check if this is a symbol column to merge
                merge_pair = next((pair for pair in self.merge_pairs if pair[0] == old_col), None)
                
                if merge_pair:
                    # Merge symbol with value
                    symbol_col, value_col = merge_pair
                    symbol_cell = self.matrix.matrix[row_idx][symbol_col]
                    value_cell = self.matrix.matrix[row_idx][value_col]
                    
                    if value_cell.original_cell:
                        # Create merged cell
                        new_cell_content = self._merge_cell_content(symbol_cell, value_cell)
                        if new_cell_content:
                            # Create new merged cell
                            merged_cell = Cell(
                                content=new_cell_content,
                                colspan=value_cell.original_cell.colspan,
                                rowspan=value_cell.original_cell.rowspan,
                                is_header=value_cell.original_cell.is_header,
                                align=value_cell.original_cell.align
                            )
                            
                            new_col_idx = old_to_new.get(value_col)
                            if new_col_idx is not None:
                                new_row[new_col_idx] = MatrixCell(
                                    original_cell=merged_cell,
                                    is_spanned=False,
                                    row_origin=row_idx,
                                    col_origin=new_col_idx
                                )
                
                elif old_col not in set(pair[1] for pair in self.merge_pairs):
                    # Regular column, not involved in merging
                    new_col_idx = old_to_new.get(old_col)
                    if new_col_idx is not None:
                        new_row[new_col_idx] = self.matrix.matrix[row_idx][old_col]
            
            new_matrix.matrix.append(new_row)
        
        return new_matrix
    
    def _merge_cell_content(self, symbol_cell: MatrixCell, value_cell: MatrixCell) -> str:
        """
        Merge symbol and value cell contents.
        
        Returns:
            Merged content like "$224.11" or original value if no symbol
        """
        value_text = value_cell.original_cell.text().strip() if value_cell.original_cell else ""
        symbol_text = symbol_cell.original_cell.text().strip() if symbol_cell.original_cell else ""
        
        if not value_text:
            return symbol_text  # Just return symbol if no value
        
        if symbol_text in self.CURRENCY_SYMBOLS:
            # Merge symbol with value (no space for $, others may vary)
            if symbol_text == '$':
                return f"${value_text}"
            else:
                return f"{symbol_text}{value_text}"
        else:
            # No symbol, just return value
            return value_text
    
    def get_merge_summary(self) -> str:
        """Get a summary of merges to be applied."""
        if not self.merge_pairs:
            return "No currency column merges detected"
        
        summary = f"Currency merges detected: {len(self.merge_pairs)} pairs\n"
        for symbol_col, value_col in self.merge_pairs:
            summary += f"  • Column {symbol_col} ($) + Column {value_col} (value)\n"
        
        return summary