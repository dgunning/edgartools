"""EX-21 Subsidiaries parser for 10-K filings."""
import re
from dataclasses import dataclass
from typing import List, Optional

from rich import box
from rich.table import Table

from edgar.richtools import repr_rich

__all__ = ['Subsidiary', 'SubsidiaryList', 'parse_subsidiaries']

# Strong header patterns — safe to match against any single cell
_STRONG_HEADER_PATTERNS = re.compile(
    r'(name\s+of\s+(subsidiary|subsidiaries|company|entity|companies)|'
    r'^subsidiary$|^subsidiaries$|company\s+name|entity\s+name|'
    r'percent(age)?\s+(of\s+)?own|'
    r'organized\s+under\s+the\s+laws|'
    r'state\s+or\s+(other\s+)?jurisdiction)',
    re.IGNORECASE
)

# Weaker header keywords — require corroboration from multiple cells
_HEADER_KEYWORDS = {'jurisdiction', 'ownership', 'subsidiary', 'subsidiaries',
                    'incorporation', 'organization', 'organized'}
_JURISDICTION_HEADER_PHRASES = {'jurisdiction', 'state or', 'organized under',
                                'place of', 'country of'}

_SECTION_LABEL_PATTERNS = re.compile(
    r'^(u\.?\s*s\.?\s*(subsidiaries|companies)|'
    r'international\s+(subsidiaries|companies)|'
    r'domestic\s+(subsidiaries|companies)|'
    r'foreign\s+(subsidiaries|companies)|'
    r'subsidiaries\s+of|'
    r'the\s+following|'
    r'significant\s+subsidiaries|'
    r'list\s+of\s+subsidiaries|'
    r'exhibit\s+21|'
    r'part\s+[ivx]+)',
    re.IGNORECASE
)

# Pattern to strip trailing footnote markers like (1), (2)(3), *, **, etc.
# Anchored to end-of-string to avoid stripping mid-name references like "Series [1] Holdings"
# Limited to 1-2 digit numbers to avoid stripping years like [2024]
_FOOTNOTE_PATTERN = re.compile(r'(\s*[\(\[]\d{1,2}[\)\]])+\s*$|\s*\*+\s*$')


@dataclass
class Subsidiary:
    """A single subsidiary record from Exhibit 21."""
    name: str
    jurisdiction: str
    ownership_pct: Optional[float] = None

    def __repr__(self):
        parts = [f"name='{self.name}'", f"jurisdiction='{self.jurisdiction}'"]
        if self.ownership_pct is not None:
            parts.append(f"ownership_pct={self.ownership_pct}")
        return f"Subsidiary({', '.join(parts)})"


class SubsidiaryList:
    """Collection of subsidiaries parsed from Exhibit 21."""

    def __init__(self, subsidiaries: List[Subsidiary]):
        self._subsidiaries = subsidiaries

    def __len__(self):
        return len(self._subsidiaries)

    def __iter__(self):
        return iter(self._subsidiaries)

    def __getitem__(self, item):
        return self._subsidiaries[item]

    def __repr__(self):
        return repr_rich(self.__rich__())

    def to_dataframe(self):
        import pandas as pd
        data = []
        for sub in self._subsidiaries:
            row = {'name': sub.name, 'jurisdiction': sub.jurisdiction}
            if sub.ownership_pct is not None:
                row['ownership'] = sub.ownership_pct
            data.append(row)
        df = pd.DataFrame(data)
        # Only include ownership column if any subsidiary has it
        if 'ownership' in df.columns and df['ownership'].isna().all():
            df = df.drop(columns=['ownership'])
        return df

    def __rich__(self):
        table = Table(
            title=f"Subsidiaries ({len(self._subsidiaries)})",
            box=box.SIMPLE,
            show_edge=False,
            pad_edge=False,
        )
        table.add_column("", style="dim", width=4, justify="right")
        table.add_column("Name", style="bold")
        table.add_column("Jurisdiction")
        has_ownership = any(s.ownership_pct is not None for s in self._subsidiaries)
        if has_ownership:
            table.add_column("Ownership %", justify="right")

        for i, sub in enumerate(self._subsidiaries, 1):
            row = [str(i), sub.name, sub.jurisdiction]
            if has_ownership:
                row.append(f"{sub.ownership_pct:.1f}%" if sub.ownership_pct is not None else "")
            table.add_row(*row)
        return table


def _clean_text(text: str) -> str:
    """Clean cell text: strip whitespace, collapse internal spaces."""
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    # Strip non-breaking spaces
    text = text.replace('\xa0', ' ').strip()
    return text


def _clean_name(name: str) -> str:
    """Clean subsidiary name: remove footnote markers, trailing punctuation."""
    # Remove inline footnote markers like (1), (2), [3], etc.
    name = _FOOTNOTE_PATTERN.sub('', name)
    # Remove trailing asterisks
    name = name.rstrip('* ')
    return name.strip()


def _parse_ownership(text: str) -> Optional[float]:
    """Try to parse an ownership percentage from text like '100%', '80', '99.9%'."""
    text = text.strip().rstrip('%').strip()
    try:
        val = float(text)
        if 0 <= val <= 100:
            return val
    except (ValueError, TypeError):
        pass
    return None


def _is_header_row(cells: List[str]) -> bool:
    """Check if a row looks like a table header."""
    if not cells:
        return False
    # Strong patterns are safe to match on any single cell
    for cell in cells:
        text = cell.strip()
        if text and _STRONG_HEADER_PATTERNS.search(text):
            return True
    # Weaker signals require corroboration across DIFFERENT cells.
    # Tag each cell with what it matches.
    has_keyword = [any(w in c.lower() for w in _HEADER_KEYWORDS) for c in cells]
    has_jurisdiction = [any(w in c.lower() for w in _JURISDICTION_HEADER_PHRASES) for c in cells]

    keyword_cells = [i for i, v in enumerate(has_keyword) if v]
    jurisdiction_cells = [i for i, v in enumerate(has_jurisdiction) if v]

    # Need evidence from at least 2 different cells
    if keyword_cells and jurisdiction_cells:
        all_evidence_cells = set(keyword_cells) | set(jurisdiction_cells)
        if len(all_evidence_cells) >= 2:
            return True
    return len(keyword_cells) >= 2


def _is_section_label(cells: List[str]) -> bool:
    """Check if a row is a section label like 'U.S. Subsidiaries:'."""
    non_empty = [c for c in cells if c.strip()]
    if len(non_empty) != 1:
        return False
    text = non_empty[0].strip().rstrip(':')
    if _SECTION_LABEL_PATTERNS.match(text):
        return True
    # Short all-caps text in a single cell is likely a section header
    if len(text) < 60 and text == text.upper() and not any(c.isdigit() for c in text):
        return True
    return False


def _looks_like_ownership_column(values: List[str]) -> bool:
    """Check if a column's values look like ownership percentages."""
    numeric_count = 0
    for v in values:
        v = v.strip().rstrip('%').strip()
        try:
            val = float(v)
            if 0 <= val <= 100:
                numeric_count += 1
        except (ValueError, TypeError):
            pass
    # If more than 40% of non-empty values parse as numbers 0-100, it's ownership
    non_empty = sum(1 for v in values if v.strip())
    return non_empty > 0 and numeric_count / non_empty > 0.4


def _strip_empty_columns(rows: List[List[str]]) -> List[List[str]]:
    """Remove columns that are empty across all rows (spacer columns)."""
    if not rows:
        return rows
    max_cols = max(len(r) for r in rows)
    # Pad all rows to same width so index access is safe
    padded = [r + [''] * (max_cols - len(r)) for r in rows]
    # Find columns that have at least one non-empty value
    keep = []
    for col_idx in range(max_cols):
        if any(padded[row_idx][col_idx].strip() for row_idx in range(len(padded))):
            keep.append(col_idx)
    # Apply keep indices to padded rows (not original ragged rows)
    return [[padded_row[i] for i in keep] for padded_row in padded]


def parse_subsidiaries(html_content: str) -> List[Subsidiary]:
    """
    Parse HTML content from an EX-21 exhibit into a list of Subsidiary records.

    Handles:
    - 2-column tables (name + jurisdiction)
    - 3-column tables (name + ownership% + jurisdiction, or name + jurisdiction + ownership%)
    - Multiple tables (paginated or sectioned)
    - Header rows, section labels, footnotes
    - Empty spacer columns (common in SEC HTML formatting)
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_content, 'html.parser')
    # Only use top-level tables to avoid double-counting from nested layout tables
    tables = [t for t in soup.find_all('table') if t.find_parent('table') is None]

    if not tables:
        return []

    subsidiaries = []

    for table in tables:
        rows = table.find_all('tr')
        if not rows:
            continue

        # Extract all rows as lists of cell text
        all_cells = []
        for row in rows:
            cells = row.find_all(['td', 'th'])
            cell_texts = [_clean_text(cell.get_text()) for cell in cells]
            all_cells.append(cell_texts)

        if not all_cells:
            continue

        # Strip empty spacer columns (common in SEC HTML tables)
        all_cells = _strip_empty_columns(all_cells)

        # Filter to rows with at least 2 non-empty cells, skip headers/labels
        data_rows = []
        for cells in all_cells:
            non_empty = [c for c in cells if c.strip()]
            if len(non_empty) < 2:
                # Could be a section label (single cell with text)
                continue
            if _is_header_row(cells):
                continue
            if _is_section_label(cells):
                continue
            data_rows.append(cells)

        if not data_rows:
            continue

        # Determine effective column count from data rows
        col_counts = {}
        for cells in data_rows:
            n = len([c for c in cells if c.strip()])
            col_counts[n] = col_counts.get(n, 0) + 1

        if not col_counts:
            continue

        effective_cols = max(col_counts, key=col_counts.get)

        if effective_cols == 2:
            # 2-column: name, jurisdiction
            for cells in data_rows:
                non_empty = [c for c in cells if c.strip()]
                if len(non_empty) < 2:
                    continue
                name = _clean_name(non_empty[0])
                jurisdiction = non_empty[1].strip()
                if name and jurisdiction:
                    subsidiaries.append(Subsidiary(name=name, jurisdiction=jurisdiction))

        elif effective_cols >= 3:
            # 3+ columns: need to identify ownership column
            # Use max row width for positional column scanning
            num_cols = max(len(r) for r in data_rows)

            # Check each column (except first, which is name) for ownership pattern
            ownership_col = None
            for col_idx in range(1, min(num_cols, 4)):
                col_vals = [row[col_idx] if col_idx < len(row) else '' for row in data_rows]
                if _looks_like_ownership_column(col_vals):
                    ownership_col = col_idx
                    break

            if ownership_col is not None:
                # Jurisdiction is the other non-name, non-ownership column
                other_cols = [i for i in range(1, num_cols) if i != ownership_col]
                jurisdiction_col = other_cols[0] if other_cols else (ownership_col + 1)

                for cells in data_rows:
                    name = _clean_name(cells[0] if len(cells) > 0 else '')
                    ownership = _parse_ownership(cells[ownership_col] if ownership_col < len(cells) else '')
                    jurisdiction = (cells[jurisdiction_col] if jurisdiction_col < len(cells) else '').strip()
                    if name and jurisdiction:
                        subsidiaries.append(Subsidiary(name=name, jurisdiction=jurisdiction,
                                                       ownership_pct=ownership))
            else:
                # No ownership column detected — treat as name + jurisdiction
                for cells in data_rows:
                    non_empty = [c for c in cells if c.strip()]
                    if len(non_empty) < 2:
                        continue
                    name = _clean_name(non_empty[0])
                    jurisdiction = non_empty[-1].strip()
                    if name and jurisdiction:
                        subsidiaries.append(Subsidiary(name=name, jurisdiction=jurisdiction))

    return subsidiaries
