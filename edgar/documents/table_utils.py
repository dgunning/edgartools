"""
Table processing utilities for document parsing.

This module consolidates the standard table matrix processing pipeline used
across table rendering implementations (TableNode.render(), TableNode.to_dataframe(),
and FastTableRenderer.render_table_node()).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edgar.documents.utils.table_matrix import TableMatrix, ColumnAnalyzer
    from edgar.documents.utils.currency_merger import CurrencyColumnMerger


def process_table_matrix(matrix: "TableMatrix", headers, rows) -> "TableMatrix":
    """
    Standard table matrix processing pipeline.

    This function applies the standard three-step processing pipeline:
    1. Build matrix from headers and rows (handles colspan/rowspan)
    2. Filter out spacing columns (columns with only whitespace)
    3. Detect and merge currency symbol columns with adjacent value columns

    Args:
        matrix: TableMatrix instance to populate
        headers: List of header rows (each row is a list of Cell objects)
        rows: List of data rows (each row is a list of Cell objects)

    Returns:
        Processed TableMatrix with spacing columns removed and currency columns merged

    Example:
        >>> matrix = TableMatrix()
        >>> clean_matrix = process_table_matrix(matrix, headers, rows)
        >>> # clean_matrix now has colspan/rowspan expanded, spacing removed, and currencies merged

    Note:
        This consolidates the identical processing sequence that appeared in:
        - table_nodes.py:240-251 (TableNode.render())
        - table_nodes.py:XXX (TableNode.to_dataframe())
        - renderers/fast_table.py:XXX (FastTableRenderer.render_table_node())
    """
    # Import at runtime to avoid circular imports
    from edgar.documents.utils.table_matrix import ColumnAnalyzer
    from edgar.documents.utils.currency_merger import CurrencyColumnMerger

    # Step 1: Build matrix from rows (expands colspan/rowspan)
    matrix.build_from_rows(headers, rows)

    # Step 2: Remove spacing columns (columns with only whitespace/empty cells)
    # Note: ColumnAnalyzer is created but unused in original implementation
    analyzer = ColumnAnalyzer(matrix)
    clean_matrix = matrix.filter_spacing_columns()

    # Step 3: Detect and merge currency columns ($ with adjacent numbers)
    currency_merger = CurrencyColumnMerger(clean_matrix)
    currency_merger.detect_currency_pairs()
    if currency_merger.merge_pairs:
        clean_matrix = currency_merger.apply_merges()

    return clean_matrix
