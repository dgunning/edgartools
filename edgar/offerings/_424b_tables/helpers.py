"""Shared cell/text helpers for 424B table classification and extraction.

Low-level utilities that read text out of a ``TableNode`` — flattening cells,
normalizing whitespace, and the row label/value splitter. Imported by the
classifier, extractor, and underwriter submodules.
"""

from __future__ import annotations

import re
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from edgar.documents.table_nodes import TableNode


# Pre-compiled whitespace normalizer (used per-cell in hot paths)
_WS_RE = re.compile(r'\s+')


def _get_table_cells(table: 'TableNode') -> List[str]:
    """Flatten all non-empty cell texts from table rows."""
    cells = []
    for r in table.rows:
        for c in r.cells:
            t = c.text().strip()
            if t:
                cells.append(t)
    return cells


def _get_all_cells_including_headers(table: 'TableNode') -> List[str]:
    """All non-empty cells including header rows."""
    cells = []
    for r in table.rows:
        for c in r.cells:
            t = c.text().strip()
            if t:
                cells.append(t)
    for h in table.headers:
        for c in h:
            t = c.text().strip()
            if t:
                cells.append(t)
    return cells


def _get_full_text(table: 'TableNode') -> str:
    """Lowercase text from all cells including headers, with normalized whitespace."""
    cells = [_WS_RE.sub(' ',t) for t in _get_all_cells_including_headers(table)]
    return ' '.join(cells).lower()


def _get_row_texts(table: 'TableNode') -> List[List[str]]:
    """List of rows, each as list of non-empty cell texts."""
    result = []
    for r in table.rows:
        row = [c.text().strip() for c in r.cells if c.text().strip()]
        result.append(row)
    return result


def _fraction_long_cells(table: 'TableNode', min_len: int = 60) -> float:
    """Fraction of non-empty cells exceeding min_len characters."""
    cells = _get_table_cells(table)
    if not cells:
        return 0.0
    return sum(1 for c in cells if len(c) >= min_len) / len(cells)


def _has_numeric_cells(table: 'TableNode') -> bool:
    """True if any row cell is numeric."""
    return any(c.is_numeric for r in table.rows for c in r.cells)


def _prefix_dollar(val: str) -> str:
    """Prefix a value with $ unless it already has one or contains %."""
    if not val or '$' in val or '%' in val:
        return val
    return '$' + val


def _extract_row_label_and_values(row) -> tuple:
    """
    Extract (label, numeric_values) from a row with sparse cells.

    SEC HTML tables often have empty spacer cells and separate '$' cells.
    Returns the first non-empty non-$ text as label, and all numeric cell
    texts as the values list.
    """
    label = ''
    values = []
    for c in row.cells:
        t = c.text().strip()
        if not t or t == '$':
            continue
        if c.is_numeric:
            values.append(t)
        elif not label:
            label = t
    return label, values
