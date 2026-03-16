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

    def has_index(self) -> bool:
        """
        Detect if filing uses Cross Reference Index format.

        Returns:
            True if Cross Reference Index is present
        """
        # Look for the specific heading (case-insensitive, allow hyphen in "Cross-Reference")
        if not re.search(r'FORM\s+10-K\s+CROSS[- ]?REFERENCE\s+INDEX', self.html, re.IGNORECASE):
            return False

        # Look for table with Item/page mapping pattern
        # Search for a row with "Item 1A" or bare "1A.", "Risk Factors", and page numbers
        pattern = (
            r'<td[^>]*>.*?(?:Item\s+)?1A\..*?</td>'
            r'.*?<td[^>]*>.*?Risk\s+Factors.*?</td>'
            r'.*?<td[^>]*>.*?\d+(?:(?:&#8211;|-)\d+)?.*?</td>'
        )
        return bool(re.search(pattern, self.html, re.DOTALL | re.IGNORECASE))

    def _find_index_table(self) -> Optional[str]:
        """Find the cross-reference index table HTML.

        The heading may appear multiple times (e.g., TOC link + actual table).
        We search from the last occurrence and handle two layouts:
        1. Heading inside a <table> (GE style) — search backwards for <table
        2. Heading before a <table> (Citigroup style) — search forwards for <table
        """
        # Find all occurrences and use the last one (actual table, not TOC link)
        matches = list(re.finditer(
            r'FORM\s+10-K\s+CROSS[- ]?REFERENCE\s+INDEX', self.html, re.IGNORECASE
        ))
        if not matches:
            return None

        heading_pos = matches[-1].start()

        # Check if heading is inside a table (search backwards for <table)
        preceding = self.html[max(0, heading_pos - 5000):heading_pos]
        last_table_open = preceding.rfind('<table')
        last_table_close = preceding.rfind('</table>')

        if last_table_open != -1 and last_table_open > last_table_close:
            # Heading is inside an open table — use that table
            table_start = max(0, heading_pos - 5000) + last_table_open
        else:
            # Heading is before the table — search forward
            table_start = self.html.find('<table', heading_pos)
            if table_start == -1:
                return None

        table_end = self.html.find('</table>', table_start)
        if table_end == -1:
            return None
        return self.html[table_start:table_end + 8]

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

        table_html = self._find_index_table()
        if not table_html:
            return self._entries

        # Extract rows and parse cell text from each row
        current_part = None
        last_entry = None
        item_number_pattern = re.compile(r'^(?:Item\s+)?(\d+[A-Z]?)\.?$', re.IGNORECASE)
        # Pattern for continuation rows: just page numbers like "129, 160-164,"
        page_continuation_pattern = re.compile(r'^[\d,\s&#;.\-\u2013]+$')

        for row_match in re.finditer(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL):
            row_html = row_match.group(1)
            # Extract non-empty text from each <td>
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL)
            cell_texts = []
            for cell in cells:
                text = re.sub(r'<[^>]+>', '', cell).strip()
                if text and text != '&#160;' and text != '\xa0':
                    cell_texts.append(text)

            if not cell_texts:
                continue

            # Check for Part headers
            part_match = re.match(r'^Part\s+(I+|IV)', cell_texts[0], re.IGNORECASE)
            if part_match:
                current_part = f"Part {part_match.group(1).upper()}"
                continue

            # Check for item row: first cell should be an item number
            item_match = item_number_pattern.match(cell_texts[0])
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
