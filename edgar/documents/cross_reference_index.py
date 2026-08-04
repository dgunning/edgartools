"""
Cross Reference Index Parser

Some companies (e.g., GE, Citigroup) use a Cross Reference Index table
instead of standard Item headings in their 10-K filings.

This module provides functionality to:
1. Detect Cross Reference Index format
2. Parse the index table to extract Item-to-page mappings
3. Navigate to page ranges to extract content
"""

import html as html_lib
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

# The index heading. Cross-reference filers write it in various cases and with or
# without the hyphen ("FORM 10-K CROSS-REFERENCE INDEX", "Form 10-K Cross Reference Index").
_INDEX_HEADING_RE = re.compile(r'FORM\s+10-K\s+CROSS[- ]?REFERENCE\s+INDEX', re.IGNORECASE)

# Item numbers may be bare ("1A.") or prefixed ("Item 1A.") — see Citigroup, issue #251.
_ITEM_1A_RE = re.compile(r'(?:Item\s+)?1A\.?', re.IGNORECASE)

# An index row opens with an item number ("7A." / "Item 7A.") or a Part header.
_ITEM_NUMBER_RE = re.compile(r'^(?:Item\s+)?(\d+[A-Z]?)\.?$', re.IGNORECASE)
# IV is matched before I+ — the other order lets `I+` claim the leading "I" of
# "Part IV" and label Part IV content as Part I.
_PART_RE = re.compile(r'^Part\s+(IV|I+)', re.IGNORECASE)

# How far back from the heading the index table may open. The heading is often
# rendered *inside* the table (GE), so the first row can precede it.
_TABLE_LOOKBACK = 5_000

# An index interrupted by a page break resumes in a *new* <table> (Citigroup
# breaks after Item 9A and opens a second table for 9B onward). A following
# table is treated as a continuation only when nothing but layout markup
# separates it from the previous one — this much visible text between them
# means the index ended and body content has started.
_CONTINUATION_MAX_GAP_TEXT = 200

# Cap on how many tables one index may span. Two is the observed maximum
# (one page break); the cap stops a malformed document from walking the whole
# filing table by table.
_MAX_INDEX_TABLES = 6


def _cell_texts(row_html: str) -> List[str]:
    """Non-empty text of each <td> in a row, tags stripped."""
    texts = []
    for cell in re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL):
        text = re.sub(r'<[^>]+>', '', cell).strip()
        if text and text != '&#160;' and text != '\xa0':
            texts.append(text)
    return texts


@dataclass
class PageRange:
    """Represents a page or range of pages."""
    start: int
    end: int

    @classmethod
    def parse(cls, page_str: str) -> List['PageRange']:
        """
        Parse page number string into PageRange objects.

        Args:
            page_str: Page numbers like "26-33", "4", "4-7, 9-11, 74-75", "77-78, (a)"

        Returns:
            List of PageRange objects

        Examples:
            >>> PageRange.parse("26-33")
            [PageRange(start=26, end=33)]

            >>> PageRange.parse("4-7, 9-11, 74-75")
            [PageRange(start=4, end=7), PageRange(start=9, end=11), PageRange(start=74, end=75)]

            >>> PageRange.parse("25")
            [PageRange(start=25, end=25)]

            >>> PageRange.parse("77-78, (a)")
            [PageRange(start=77, end=78)]
        """
        if not page_str or page_str.lower() == 'not applicable':
            return []

        ranges = []
        # Normalize en-dash HTML entities and Unicode en-dashes to hyphens
        page_str = page_str.replace('&#8211;', '-').replace('\u2013', '-')

        # Split by comma to handle multiple ranges
        parts = [p.strip() for p in page_str.split(',')]

        for part in parts:
            # Skip non-numeric parts like "(a)", "(b)", footnotes, etc.
            if not any(c.isdigit() for c in part):
                continue

            # Remove any parenthetical notes
            part = re.sub(r'\([^)]*\)', '', part).strip()
            # Strip trailing footnote markers. Items that are *also* incorporated
            # by reference carry one ("319-321*" for Citigroup's Item 10); the
            # cited pages are still real, and leaving the marker attached made
            # int("321*") raise and silently discarded the whole range. A
            # marker-only cell ("**") reduces to empty and is skipped below.
            part = part.rstrip('*†‡§').strip()
            if not part:
                continue

            if '-' in part:
                # Range like "26-33"
                try:
                    start, end = part.split('-', 1)
                    ranges.append(cls(start=int(start.strip()), end=int(end.strip())))
                except ValueError:
                    # Skip if can't parse
                    continue
            else:
                # Single page like "25"
                try:
                    page = int(part.strip())
                    ranges.append(cls(start=page, end=page))
                except ValueError:
                    # Skip if can't parse
                    continue

        return ranges

    def __str__(self) -> str:
        if self.start == self.end:
            return str(self.start)
        return f"{self.start}-{self.end}"


@dataclass
class IndexEntry:
    """Represents a single entry in the Cross Reference Index."""
    item_number: str  # e.g., "1", "1A", "1B"
    item_title: str   # e.g., "Business", "Risk Factors"
    pages: List[PageRange]  # Page ranges where content is located
    part: Optional[str] = None  # e.g., "Part I", "Part II"

    @property
    def item_id(self) -> str:
        """Return standardized item ID (e.g., '1A' for 'Item 1A.')."""
        return self.item_number

    @property
    def full_item_name(self) -> str:
        """Return full item name (e.g., 'Item 1A. Risk Factors')."""
        return f"Item {self.item_number}. {self.item_title}"


class CrossReferenceIndex:
    """Parser for Cross Reference Index tables in 10-K filings."""

    def __init__(self, html: str):
        """
        Initialize with HTML content.

        Args:
            html: Full HTML content of the filing
        """
        self.html = html
        self._entries: Optional[Dict[str, IndexEntry]] = None

    def _heading_position(self) -> Optional[int]:
        """Position of the index heading, or None if the filing has no such heading.

        The heading may appear more than once (a TOC link as well as the table
        itself); the last occurrence is the table, so that is the one we anchor to.
        """
        last = None
        for match in _INDEX_HEADING_RE.finditer(self.html):
            last = match
        return last.start() if last else None

    def has_index(self) -> bool:
        """
        Detect if filing uses Cross Reference Index format.

        Returns:
            True if Cross Reference Index is present
        """
        if self._heading_position() is None:
            return False

        # The Item 1A row is always in the first table (the index runs in item
        # order), so detection does not need the continuation walk.
        tables = self._find_index_tables()
        if not tables:
            return False

        return self._has_index_row(tables[0])

    @staticmethod
    def _has_index_row(table_html: str) -> bool:
        """True if the table holds an Item 1A / Risk Factors / page-number row.

        Scans row by row rather than matching one pattern across the table. The
        previous single regex nested six lazy quantifiers under DOTALL and ran
        against the whole filing: where the heading matched but the table shape
        did not, it backtracked catastrophically and never returned on a
        multi-MB document (issue #928). Row-wise matching is linear, and reuses
        the row/cell shapes parse() already relies on.
        """
        for row_match in re.finditer(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL):
            cells = _cell_texts(row_match.group(1))
            if len(cells) < 3:
                continue
            if not _ITEM_1A_RE.fullmatch(cells[0]):
                continue
            if 'risk factor' not in html_lib.unescape(cells[1]).lower():
                continue
            if PageRange.parse(cells[2]):
                return True
        return False

    def _find_index_tables(self) -> List[str]:
        """Find the cross-reference index table(s), in document order.

        Anchored to the last heading occurrence, handling two layouts:
        1. Heading inside a <table> (GE style) — search backwards for <table
        2. Heading before a <table> (Citigroup style) — search forwards for <table

        An index that runs past a page break resumes in a *separate* <table>.
        Citigroup breaks after Item 9A, so reading only the first table stopped
        the parse at 14 of 22 items and silently lost Items 9B-15 (including all
        of Part III). Adjacent tables are therefore appended while they still
        look like the index, which recovers the full item set without guessing:
        a continuation must follow with only layout markup in between and must
        itself carry an item-number or Part row.
        """
        heading_pos = self._heading_position()
        if heading_pos is None:
            return []

        # Check if heading is inside a table (search backwards for <table)
        preceding = self.html[max(0, heading_pos - _TABLE_LOOKBACK):heading_pos]
        last_table_open = preceding.rfind('<table')
        last_table_close = preceding.rfind('</table>')

        if last_table_open != -1 and last_table_open > last_table_close:
            # Heading is inside an open table — use that table
            table_start = max(0, heading_pos - _TABLE_LOOKBACK) + last_table_open
        else:
            # Heading is before the table — search forward
            table_start = self.html.find('<table', heading_pos)
            if table_start == -1:
                return []

        tables: List[str] = []
        cursor = table_start
        while len(tables) < _MAX_INDEX_TABLES:
            open_pos = self.html.find('<table', cursor)
            if open_pos == -1:
                break
            close_pos = self.html.find('</table>', open_pos)
            if close_pos == -1:
                break
            end = close_pos + 8

            if tables:
                # Continuation candidate: reject on intervening body text, or on
                # a table that carries no index row of its own.
                gap = re.sub(r'<[^>]+>', '', self.html[cursor:open_pos])
                gap = gap.replace('&#160;', ' ').replace('&nbsp;', ' ').strip()
                if len(gap) > _CONTINUATION_MAX_GAP_TEXT:
                    break
                if not self._looks_like_index_table(self.html[open_pos:end]):
                    break

            tables.append(self.html[open_pos:end])
            cursor = end

        return tables

    @staticmethod
    def _looks_like_index_table(table_html: str) -> bool:
        """True if the table opens rows with item numbers or Part headers.

        Deliberately weaker than :meth:`_has_index_row`: a continuation table
        holds only the tail of the index (Citigroup's second table starts at
        Item 9B), so it can't be asked for the Item 1A / Risk Factors row that
        anchors detection.
        """
        for row_match in re.finditer(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL):
            cells = _cell_texts(row_match.group(1))
            if not cells:
                continue
            if _ITEM_NUMBER_RE.match(cells[0]) or _PART_RE.match(cells[0]):
                return True
        return False

    def parse(self) -> Dict[str, IndexEntry]:
        """
        Parse Cross Reference Index table.

        Returns:
            Dictionary mapping item IDs to IndexEntry objects
            {
                '1': IndexEntry(item_number='1', item_title='Business', ...),
                '1A': IndexEntry(item_number='1A', item_title='Risk Factors', ...),
                ...
            }
        """
        if self._entries is not None:
            return self._entries

        self._entries = {}

        tables = self._find_index_tables()
        if not tables:
            return self._entries

        # Extract rows and parse cell text from each row. Part context and
        # page-continuation rows carry across a table boundary, because a page
        # break can split the index mid-item (Citigroup) \u2014 so the row loop runs
        # over the concatenated tables rather than restarting per table.
        current_part = None
        last_entry = None
        # Pattern for continuation rows: just page numbers like "129, 160-164,"
        page_continuation_pattern = re.compile(r'^[\d,\s&#;.\-\u2013]+$')

        rows = (
            row_match
            for table_html in tables
            for row_match in re.finditer(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL)
        )
        for row_match in rows:
            cell_texts = _cell_texts(row_match.group(1))

            if not cell_texts:
                continue

            # Check for Part headers
            part_match = _PART_RE.match(cell_texts[0])
            if part_match:
                current_part = f"Part {part_match.group(1).upper()}"
                continue

            # Check for item row: first cell should be an item number
            item_match = _ITEM_NUMBER_RE.match(cell_texts[0])
            if item_match:
                item_num = item_match.group(1).upper()
                item_title = cell_texts[1] if len(cell_texts) > 1 else ''
                page_str = cell_texts[2] if len(cell_texts) > 2 else ''

                # Decode HTML entities in title
                item_title = html_lib.unescape(item_title)

                pages = PageRange.parse(page_str)

                entry = IndexEntry(
                    item_number=item_num,
                    item_title=item_title,
                    pages=pages,
                    part=current_part
                )

                self._entries[item_num] = entry
                last_entry = entry
                continue

            # Continuation row: page numbers that belong to the previous item
            # (e.g., "129, 160-164," or "299-300")
            combined = ' '.join(cell_texts)
            if last_entry and page_continuation_pattern.match(combined):
                extra_pages = PageRange.parse(combined)
                if extra_pages:
                    last_entry.pages.extend(extra_pages)

        return self._entries

    def get_item(self, item_id: str) -> Optional[IndexEntry]:
        """
        Get index entry for a specific item.

        Args:
            item_id: Item identifier like "1", "1A", "7"

        Returns:
            IndexEntry if found, None otherwise
        """
        if self._entries is None:
            self.parse()
        return self._entries.get(item_id)

    def get_page_ranges(self, item_id: str) -> List[PageRange]:
        """
        Get page ranges for a specific item.

        Args:
            item_id: Item identifier like "1A"

        Returns:
            List of PageRange objects, empty list if not found
        """
        entry = self.get_item(item_id)
        return entry.pages if entry else []

    def find_page_breaks(self) -> List[int]:
        """
        Find page break positions in HTML.

        Returns:
            List of character positions where page breaks occur

        Note:
            Page breaks are indicated by:
            - <hr style="page-break-after:always"/>
            - <div style="page-break-after:always"/>
        """
        breaks = [0]  # Start of document is page 1

        # Find all page break elements
        patterns = [
            r'<hr\s+[^>]*style="[^"]*page-break-after\s*:\s*always[^"]*"[^>]*/?>',
            r'<div\s+[^>]*style="[^"]*page-break-after\s*:\s*always[^"]*"[^>]*>',
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, self.html, re.IGNORECASE):
                breaks.append(match.end())

        # Sort and deduplicate
        breaks = sorted(set(breaks))

        return breaks

    def extract_content_by_page_range(
        self,
        page_range: PageRange
    ) -> Optional[str]:
        """
        Extract HTML content from specified page range.

        Args:
            page_range: PageRange specifying which pages to extract

        Returns:
            Extracted HTML content, or None if pages not found

        Note:
            This is a best-effort extraction. HTML doesn't have explicit
            page numbers, so we rely on page-break indicators.
        """
        page_breaks = self.find_page_breaks()

        if len(page_breaks) < page_range.end:
            # Not enough page breaks found
            return None

        # Extract content between page breaks
        # Page numbers are 1-indexed, list is 0-indexed
        start_idx = page_breaks[page_range.start - 1]

        # If this is the last page, go to end of document
        if page_range.end >= len(page_breaks):
            end_idx = len(self.html)
        else:
            end_idx = page_breaks[page_range.end]

        return self.html[start_idx:end_idx]

    def extract_item_content(self, item_id: str) -> Optional[str]:
        """
        Extract content for a specific Item.

        Args:
            item_id: Item identifier like "1A"

        Returns:
            Extracted HTML content, or None if not found
        """
        ranges = self.get_page_ranges(item_id)
        if not ranges:
            return None

        # Extract content from all page ranges and concatenate
        contents = []
        for page_range in ranges:
            content = self.extract_content_by_page_range(page_range)
            if content:
                contents.append(content)

        return '\n'.join(contents) if contents else None


def detect_cross_reference_index(html: str) -> bool:
    """
    Convenience function to detect Cross Reference Index format.

    Args:
        html: HTML content of filing

    Returns:
        True if filing uses Cross Reference Index format
    """
    index = CrossReferenceIndex(html)
    return index.has_index()


def parse_cross_reference_index(html: str) -> Dict[str, IndexEntry]:
    """
    Convenience function to parse Cross Reference Index.

    Args:
        html: HTML content of filing

    Returns:
        Dictionary mapping item IDs to IndexEntry objects
    """
    index = CrossReferenceIndex(html)
    return index.parse()
