"""
Table of Contents analyzer for SEC filings.

This module analyzes the TOC structure to map section names to anchor IDs,
enabling section extraction for API filings with generated anchor IDs.
"""
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from lxml import html as lxml_html

from edgar.documents.utils.anchor_targets import find_anchor_targets

logger = logging.getLogger(__name__)


@dataclass
class TOCSection:
    """Represents a section found in the Table of Contents."""
    name: str
    anchor_id: str
    normalized_name: str
    section_type: str  # 'item', 'part', 'other'
    order: int
    part: Optional[str] = None  # NEW: "Part I", "Part II", or None for 10-K


class TOCAnalyzer:
    """
    Analyzes Table of Contents structure to map section names to anchor IDs.

    This enables section extraction for filings where anchor IDs are generated
    rather than semantic (like API filings vs local HTML files).
    """

    def __init__(self):
        # SEC section patterns for normalization
        self.section_patterns = [
            (r'(?:item|part)\s+\d+[a-z]?', 'item'),
            (r'business', 'item'),
            (r'risk\s+factors?', 'item'),
            (r'properties', 'item'),
            (r'legal\s+proceedings', 'item'),
            (r'management.*discussion', 'item'),
            (r'md&a', 'item'),
            (r'financial\s+statements?', 'item'),
            (r'exhibits?', 'item'),
            (r'signatures?', 'item'),
            (r'part\s+[ivx]+', 'part'),
        ]

    def analyze_toc_structure(self, html_content: str, agent: Optional[str] = None,
                              tree=None) -> Dict[str, str]:
        """
        Analyze HTML content to extract section mappings from TOC.

        When a filing agent is known, dispatches to an agent-specific parser
        that understands the agent's particular TOC HTML structure. Falls back
        to generic parsing for unknown agents.

        Args:
            html_content: Raw HTML content
            agent: Filing agent name (e.g., 'Workiva', 'Donnelley') or None
            tree: Pre-parsed lxml tree to avoid redundant parsing (optional)

        Returns:
            Dict mapping normalized section names to anchor IDs
        """
        if agent == 'Workiva':
            result = self._analyze_workiva_toc(html_content, tree=tree)
            if result:
                return result
        elif agent == 'Donnelley':
            result = self._analyze_dfin_toc(html_content, tree=tree)
            if result:
                return result
        elif agent == 'Novaworks':
            result = self._analyze_novaworks_toc(html_content, tree=tree)
            if result:
                return result
        elif agent == 'Toppan Merrill':
            result = self._analyze_toppan_toc(html_content, tree=tree)
            if result:
                return result

        # Generic fallback for unknown agents or when agent-specific parser returns empty
        return self._analyze_generic_toc(html_content, tree=tree)

    def _analyze_generic_toc(self, html_content: str, tree=None) -> Dict[str, str]:
        """
        Generic TOC analysis — the original strategy that scans all anchor links.

        Works across all filing agents but may miss sections or pick up
        non-TOC links for agents with unusual TOC structures.

        Args:
            html_content: Raw HTML content
            tree: Pre-parsed lxml tree (optional, avoids re-parsing)

        Returns:
            Dict mapping normalized section names to anchor IDs
        """
        section_mapping = {}

        try:
            if tree is None:
                # Handle XML declaration issues
                if html_content.startswith('<?xml'):
                    html_content = re.sub(r'<\?xml[^>]*\?>', '', html_content, count=1)
                tree = lxml_html.fromstring(html_content)

            # Find all anchor links that could be TOC links
            anchor_links = tree.xpath('//a[@href]')

            toc_sections = []
            current_part = None  # Track current part context for 10-Q filings

            for link in anchor_links:
                href = link.get('href', '').strip()
                text = (link.text_content() or '').strip()

                # Only internal anchors can define TOC section boundaries.
                if not href.startswith('#'):
                    continue

                if not text:
                    continue

                # Check if this link or its row represents a part header
                # Part headers in 10-Q TOCs typically appear as separate rows: "Part I", "Part II"
                explicit_part = self._extract_part_context(text)
                if explicit_part and not re.search(r'item\s+\d+[a-z]?', text, re.IGNORECASE):
                    # Update current part context
                    current_part = explicit_part
                    # Don't create a section for the part header itself
                    continue

                anchor_id = href[1:]  # Remove #

                # Try to find item number in preceding context (for table-based TOCs)
                preceding_item = self._extract_preceding_item_label(link)

                # Infer current part from surrounding TOC row context when part headers
                # are standalone rows without links (common in some 10-K filings).
                inferred_part = self._infer_part_from_row_context(link)
                if inferred_part:
                    current_part = inferred_part

                # Check if this looks like a section reference (check text, anchor ID, and context)
                if self._is_section_link(text, anchor_id, preceding_item):
                    # Verify target exists
                    target_elements = find_anchor_targets(tree, anchor_id)
                    if target_elements:
                        # Try to extract item number from: anchor ID > preceding context > text
                        normalized_name = self._normalize_section_name(text, anchor_id, preceding_item)
                        section_type, order = self._get_section_type_and_order(normalized_name)

                        toc_section = TOCSection(
                            name=text,
                            anchor_id=anchor_id,
                            normalized_name=normalized_name,
                            section_type=section_type,
                            order=order,
                            part=current_part  # Assign current part context
                        )
                        toc_sections.append(toc_section)

            # Build mapping prioritizing the most standard section names
            section_mapping = self._build_section_mapping(toc_sections, tree=tree)

        except Exception:
            # Return empty mapping on error - fallback to other methods
            pass

        return section_mapping

    # ---- Agent-specific TOC parsers ----

    def _find_toc_table(self, tree, headings: List[str] = None) -> Optional[object]:
        """
        Locate the TOC <table> element by searching for a known heading.

        Args:
            tree: Parsed lxml HTML tree
            headings: List of heading texts to search for (case-insensitive).
                      Defaults to ["TABLE OF CONTENTS", "INDEX"].

        Returns:
            The first <table> element following the heading, or None.
        """
        if headings is None:
            headings = ['TABLE OF CONTENTS', 'INDEX']

        headings_upper = [h.upper() for h in headings]

        def _find_table_in_siblings(element):
            """Search following siblings (and their descendants) for a <table>."""
            for following in element.itersiblings():
                if not isinstance(following.tag, str):
                    continue
                if following.tag == 'table':
                    return following
                tables = following.xpath('.//table')
                if tables:
                    return tables[0]
            return None

        # Search block-level and inline-heading elements likely to contain a TOC heading.
        # Restricting to these tags avoids calling text_content() on every node in a
        # large document (which recursively traverses subtrees).
        _heading_tags = ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                         'b', 'strong', 'span', 'td', 'th', 'center')
        for el in tree.iter(*_heading_tags):
            try:
                text = (el.text_content() or '').strip().upper()
            except (ValueError, AttributeError):
                continue
            if not text:
                continue
            # Check for exact or near-exact match
            for heading in headings_upper:
                if text == heading or text == heading + '.':
                    # Walk up to 3 levels looking for a sibling table
                    current = el
                    for _ in range(3):
                        table = _find_table_in_siblings(current)
                        if table is not None:
                            return table
                        parent = current.getparent()
                        if parent is None:
                            break
                        current = parent

        return None

    def _parse_item_from_text(self, text: str) -> Optional[str]:
        """
        Extract a normalized item/part name from TOC entry text.

        Handles formats like:
        - "Item 1." / "ITEM 1A." / "Item 1A. Risk Factors"
        - "Part I" / "PART II."

        Returns:
            Normalized name like "Item 1A" or "Part II", or None.
        """
        text = text.strip()
        # Strip zero-width spaces
        text = text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')

        item_match = re.match(r'(?:item|ITEM)\s+(\d+[A-Za-z]?)', text, re.IGNORECASE)
        if item_match:
            return f"Item {item_match.group(1).upper()}"

        part_match = re.match(r'(?:part|PART)\s+([IVXivx]+)', text, re.IGNORECASE)
        if part_match:
            return f"Part {part_match.group(1).upper()}"

        return None

    def _item_from_anchor(self, anchor_id: str) -> Optional[str]:
        """
        Extract a normalized item/part name from an anchor ID.

        Handles patterns like:
        - "item_1_business", "item_1a_risk_factors" (DFIN)
        - "ITEM1BUSINESS_392371", "ITEM1ARISKFACTORS_986989" (Toppan Merrill)
        - "item1a", "Item1C" (Novaworks)

        Returns:
            Normalized name like "Item 1A" or None.
        """
        anchor_lower = anchor_id.lower()

        # Match item number + optional single letter suffix.
        # The letter must NOT be followed by another letter (to avoid matching
        # "item1business" as "Item 1B" — the "b" is part of "business", not a suffix).
        item_match = re.search(r'item[_\s]*(\d+)([a-z]?)(?![a-z])', anchor_lower)
        if item_match:
            num = item_match.group(1)
            letter = item_match.group(2).upper()
            return f"Item {num}{letter}"

        part_match = re.search(r'part[_\s]*([ivx]+)', anchor_lower)
        if part_match:
            return f"Part {part_match.group(1).upper()}"

        return None

    @staticmethod
    def _count_item_links(table) -> int:
        """Count how many internal links in a table look like item references."""
        count = 0
        for link in table.xpath('.//a[@href]'):
            href = (link.get('href', '') or '').strip()
            if not href.startswith('#'):
                continue
            text = (link.text_content() or '').strip()
            if re.search(r'item\s+\d', text, re.IGNORECASE):
                count += 1
            elif re.search(r'item[_]?\d', href, re.IGNORECASE):
                count += 1
        return count

    def _find_toc_table_by_links(self, tree) -> Optional[object]:
        """
        Fallback: locate the TOC table by finding the table with the most item links.

        Used when _find_toc_table fails because there's no explicit heading
        (some Toppan and Novaworks filings omit the heading).

        Returns:
            The table element with >= 5 item links, or None.
        """
        best_table = None
        best_count = 0

        for table in tree.xpath('//table'):
            count = self._count_item_links(table)
            if count > best_count:
                best_count = count
                best_table = table

        # Require at least 5 item links to qualify as a TOC
        return best_table if best_count >= 5 else None

    def _find_best_toc_table(self, tree, headings: List[str]) -> Optional[object]:
        """
        Find the best TOC table using heading-based search with link-based fallback.

        First tries heading-based search. If the found table has fewer than 5
        item links, falls back to the link-based search which finds the table
        with the highest concentration of item links.

        Args:
            tree: Parsed HTML tree
            headings: Heading text patterns to search for

        Returns:
            Table element, or None.
        """
        toc_table = self._find_toc_table(tree, headings)
        if toc_table is not None and self._count_item_links(toc_table) >= 5:
            return toc_table
        # Heading table was absent or too small — try link-based detection
        return self._find_toc_table_by_links(tree)

    @staticmethod
    def _make_section_key(item_name: str, current_part: Optional[str]) -> str:
        """
        Build a section mapping key, adding part context when available.

        For 10-K filings (no duplicate items across parts), part prefix is
        cosmetic but harmless. For 10-Q filings, it's essential to distinguish
        Item 1 in Part I from Item 1 in Part II.

        Args:
            item_name: Normalized item name like "Item 1A"
            current_part: Current part context like "Part I", or None

        Returns:
            Key like "part_i_item_1a" or "Item 1A"
        """
        if current_part:
            part_key = current_part.lower().replace(' ', '_')
            item_key = item_name.lower().replace(' ', '_')
            return f"{part_key}_{item_key}"
        return item_name

    @staticmethod
    def _ensure_tree(html_content: str, tree=None):
        """Return the pre-parsed tree or parse from html_content."""
        if tree is not None:
            return tree
        if html_content.startswith('<?xml'):
            html_content = re.sub(r'<\?xml[^>]*\?>', '', html_content, count=1)
        return lxml_html.fromstring(html_content)

    def _analyze_workiva_toc(self, html_content: str, tree=None) -> Dict[str, str]:
        """
        Workiva-specific TOC parser.

        Workiva TOCs use a 3-column table with split <a> tags sharing the same
        UUID href: [Item label] [Title] [Page number]. Anchors are UUID-style
        (e.g., #i719388195b384d85a4e238ad88eba90a_13).

        Strategy:
        1. Find TOC table after "TABLE OF CONTENTS" heading
        2. Process each <tr> — group <a> tags by shared href
        3. Combine text from grouped links to reassemble item + title
        4. Extract item number from combined text (anchor IDs are opaque UUIDs)
        """
        try:
            tree = self._ensure_tree(html_content, tree)

            toc_table = self._find_best_toc_table(tree, ['TABLE OF CONTENTS'])
            if toc_table is None:
                return {}

            mapping = {}
            current_part = None
            rows = toc_table.xpath('.//tr')

            for row in rows:
                links = row.xpath('.//a[@href]')
                if not links:
                    continue

                # Group links by href
                href_groups: Dict[str, List[str]] = {}
                href_order = []
                for link in links:
                    href = link.get('href', '').strip()
                    if not href.startswith('#'):
                        continue
                    text = (link.text_content() or '').strip()
                    if not text:
                        continue
                    if href not in href_groups:
                        href_groups[href] = []
                        href_order.append(href)
                    href_groups[href].append(text)

                for href in href_order:
                    texts = href_groups[href]
                    anchor_id = href[1:]

                    # Skip page-number-only entries (single short numeric text)
                    if len(texts) == 1 and re.match(r'^\d{1,3}$', texts[0]):
                        continue

                    # Filter out page numbers from multi-text groups
                    non_page_texts = [t for t in texts if not re.match(r'^\d{1,3}$', t)]
                    combined = ' '.join(non_page_texts)

                    # Try to parse an item/part name from the combined text
                    parsed = self._parse_item_from_text(combined)
                    if not parsed:
                        continue

                    # Track part context
                    if parsed.startswith('Part'):
                        current_part = parsed
                        continue

                    # Verify target exists
                    if find_anchor_targets(tree, anchor_id):
                        key = self._make_section_key(parsed, current_part)
                        if key not in mapping:
                            mapping[key] = anchor_id

            return mapping

        except Exception:
            logger.debug("Workiva TOC parser failed", exc_info=True)
            return {}

    def _analyze_dfin_toc(self, html_content: str, tree=None) -> Dict[str, str]:
        """
        Donnelley/DFIN-specific TOC parser.

        DFIN TOCs use semantic anchor IDs (e.g., #item_1_business) and may use
        "INDEX" as the heading instead of "TABLE OF CONTENTS". Links are typically
        one per cell with the title text (not split like Workiva/Toppan).

        Strategy:
        1. Find TOC region (try "INDEX" first, then "TABLE OF CONTENTS")
        2. Extract all internal <a> links from the TOC table
        3. Derive item number from the semantic anchor ID (most reliable for DFIN)
        4. Fall back to text-based extraction when anchor doesn't contain item pattern
        """
        try:
            tree = self._ensure_tree(html_content, tree)

            # DFIN typically uses "INDEX" but some use "TABLE OF CONTENTS"
            toc_table = self._find_toc_table(tree, ['INDEX', 'TABLE OF CONTENTS'])
            if toc_table is None:
                # DFIN may also have links without a formal TOC table — fall back
                # to scanning all links but preferring semantic anchors
                return self._analyze_dfin_links(tree)

            mapping = {}
            current_part = None
            links = toc_table.xpath('.//a[@href]')

            for link in links:
                href = link.get('href', '').strip()
                if not href.startswith('#'):
                    continue
                text = (link.text_content() or '').strip()
                if not text:
                    continue

                anchor_id = href[1:]

                # Skip page numbers
                if re.match(r'^\d{1,3}$', text):
                    continue

                # DFIN anchors are semantic — extract item from anchor ID
                parsed = self._item_from_anchor(anchor_id)

                # Fall back to text if anchor doesn't have item pattern
                if not parsed:
                    parsed = self._parse_item_from_text(text)

                if not parsed:
                    continue

                # Track part context
                if parsed.startswith('Part'):
                    current_part = parsed
                    continue

                if find_anchor_targets(tree, anchor_id):
                    key = self._make_section_key(parsed, current_part)
                    if key not in mapping:
                        mapping[key] = anchor_id

            return mapping

        except Exception:
            logger.debug("DFIN TOC parser failed", exc_info=True)
            return {}

    def _analyze_dfin_links(self, tree) -> Dict[str, str]:
        """
        Fallback for DFIN filings without a formal TOC table.

        Scans all internal links for semantic anchor IDs like #item_1_business.
        DFIN anchors are distinctive (underscore-separated, descriptive) so we can
        identify TOC-like links by their anchor pattern alone.
        """
        mapping = {}
        current_part = None

        for link in tree.xpath('//a[@href]'):
            href = link.get('href', '').strip()
            if not href.startswith('#'):
                continue
            anchor_id = href[1:]

            # Only accept semantic DFIN-style anchors (contain item_ or part_)
            parsed = self._item_from_anchor(anchor_id)
            if not parsed:
                continue

            if parsed.startswith('Part'):
                current_part = parsed
                continue

            if find_anchor_targets(tree, anchor_id):
                key = self._make_section_key(parsed, current_part)
                if key not in mapping:
                    mapping[key] = anchor_id

        return mapping

    def _analyze_novaworks_toc(self, html_content: str, tree=None) -> Dict[str, str]:
        """
        Novaworks-specific TOC parser.

        Novaworks TOCs use combined text in single <a> tags (e.g.,
        "ITEM 1A. Risk Factors") with short anchors (#item1a, #Item1C).
        Known quirks:
        - Item 1 often shares anchor with Part I (#part1)
        - Anchor casing is inconsistent (#item1a vs #Item1C)
        - Page numbers are separate <a> tags with class="tocPGNUM"

        Strategy:
        1. Find TOC table after heading
        2. Parse combined "ITEM X. Title" text from each <a>
        3. Handle shared Part/Item anchors by accepting #partN for Item 1
        """
        try:
            tree = self._ensure_tree(html_content, tree)

            toc_table = self._find_best_toc_table(tree, ['INDEX', 'TABLE OF CONTENTS'])
            if toc_table is None:
                return {}

            mapping = {}
            current_part = None
            links = toc_table.xpath('.//a[@href]')

            for link in links:
                href = link.get('href', '').strip()
                if not href.startswith('#'):
                    continue
                text = (link.text_content() or '').strip()
                if not text:
                    continue

                anchor_id = href[1:]

                # Skip page number links
                if re.match(r'^\d{1,3}$', text):
                    continue

                # Parse item from the combined text (e.g., "ITEM 1A. Risk Factors")
                parsed = self._parse_item_from_text(text)
                if not parsed:
                    continue

                # Track part context
                if parsed.startswith('Part'):
                    current_part = parsed
                    continue

                # Verify target exists
                if find_anchor_targets(tree, anchor_id):
                    key = self._make_section_key(parsed, current_part)
                    if key not in mapping:
                        mapping[key] = anchor_id

            return mapping

        except Exception:
            logger.debug("Novaworks TOC parser failed", exc_info=True)
            return {}

    def _analyze_toppan_toc(self, html_content: str, tree=None) -> Dict[str, str]:
        """
        Toppan Merrill-specific TOC parser.

        Toppan TOCs split links across cells like Workiva: "ITEM 1." in one <td>,
        "BUSINESS" in the next, both sharing the same href. Anchors are descriptive
        with numeric suffixes (e.g., #ITEM1BUSINESS_392371). Text may contain
        zero-width spaces (&#8203; / U+200B).

        Strategy:
        1. Find TOC table (may use "INDEX" or "TABLE OF CONTENTS" heading)
        2. Group <a> tags per row by shared href
        3. Strip zero-width spaces from text
        4. Combine texts and extract item number
        """
        try:
            tree = self._ensure_tree(html_content, tree)

            toc_table = self._find_best_toc_table(tree, ['TABLE OF CONTENTS', 'INDEX'])
            if toc_table is None:
                return {}

            mapping = {}
            current_part = None
            rows = toc_table.xpath('.//tr')

            for row in rows:
                links = row.xpath('.//a[@href]')
                if not links:
                    continue

                # Group links by href
                href_groups: Dict[str, List[str]] = {}
                href_order = []
                for link in links:
                    href = link.get('href', '').strip()
                    if not href.startswith('#'):
                        continue
                    text = (link.text_content() or '').strip()
                    # Strip zero-width spaces
                    text = text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')
                    text = text.replace('\xa0', ' ')  # non-breaking space
                    text = text.strip()
                    if not text:
                        continue
                    if href not in href_groups:
                        href_groups[href] = []
                        href_order.append(href)
                    href_groups[href].append(text)

                for href in href_order:
                    texts = href_groups[href]
                    anchor_id = href[1:]

                    # Filter out page numbers
                    non_page_texts = [t for t in texts if not re.match(r'^\d{1,3}$', t)]
                    if not non_page_texts:
                        continue

                    combined = ' '.join(non_page_texts)

                    # Try text first (e.g., "ITEM 1. BUSINESS")
                    parsed = self._parse_item_from_text(combined)

                    # Fall back to anchor ID (e.g., ITEM1BUSINESS_392371)
                    if not parsed:
                        parsed = self._item_from_anchor(anchor_id)

                    if not parsed:
                        continue

                    # Track part context
                    if parsed.startswith('Part'):
                        current_part = parsed
                        continue

                    if find_anchor_targets(tree, anchor_id):
                        key = self._make_section_key(parsed, current_part)
                        if key not in mapping:
                            mapping[key] = anchor_id

            return mapping

        except Exception:
            logger.debug("Toppan Merrill TOC parser failed", exc_info=True)
            return {}

    def _extract_preceding_item_label(self, link_element) -> str:
        """
        Extract item/part label from preceding context.

        Handles table-based TOCs where item number is in a separate cell:
        <td>Item 1.</td><td><a href="...">Business</a></td>

        Also handles nested structures like:
        <td>Item 1.</td><td><div><span><a href="...">Business</a></span></div></td>

        Args:
            link_element: The <a> element

        Returns:
            Item label like "Item 1", "Item 1A", "Part I" or empty string
        """
        try:
            # Traverse up to find the containing <td> or <th> (up to 5 levels)
            current = link_element
            td_element = None

            for _ in range(5):
                parent = current.getparent()
                if parent is None:
                    break

                if parent.tag in ['td', 'th']:
                    td_element = parent
                    break

                current = parent

            # If we found a <td>, check ALL preceding siblings in the row
            # This handles TOCs where item number is not in the immediately adjacent cell
            # Example: ['Business', 'I', '1', '5'] where '1' is the item number
            if td_element is not None:
                # Check all preceding siblings (rightmost to leftmost)
                prev_sibling = td_element.getprevious()
                while prev_sibling is not None:
                    if prev_sibling.tag in ['td', 'th']:
                        prev_text = (prev_sibling.text_content() or '').strip()

                        # Look for "Item X" or just "X" (bare number) pattern
                        # Match full format: "Item 1A"
                        item_match = re.match(r'(Item\s+\d+[A-Z]?)\.?\s*$', prev_text, re.IGNORECASE)
                        if item_match:
                            return item_match.group(1)

                        # Match bare item number: "1A" or "1" (only valid 10-K item numbers: 1-15)
                        # This prevents page numbers (50, 108, etc.) from being treated as items
                        bare_item_match = re.match(r'^([1-9]|1[0-5])([A-Z]?)\.?\s*$', prev_text, re.IGNORECASE)
                        if bare_item_match:
                            item_num = bare_item_match.group(1)
                            item_letter = bare_item_match.group(2)
                            return f"Item {item_num}{item_letter}"

                        # Match part: "Part I" or just "I"
                        part_match = re.match(r'(Part\s+[IVX]+)\.?\s*$', prev_text, re.IGNORECASE)
                        if part_match:
                            return part_match.group(1)

                        # Match bare part: "I", "II", etc.
                        bare_part_match = re.match(r'^([IVX]+)\.?\s*$', prev_text)
                        if bare_part_match:
                            return f"Part {bare_part_match.group(1)}"

                    prev_sibling = prev_sibling.getprevious()

            # Also check immediate parent's text for inline patterns (div/span structures)
            parent = link_element.getparent()
            if parent is not None and parent.tag in ['div', 'span', 'p']:
                if parent.text:
                    text_before = parent.text.strip()
                    item_match = re.search(r'(Item\s+\d+[A-Z]?)\.?\s*$', text_before, re.IGNORECASE)
                    if item_match:
                        return item_match.group(1)

                    part_match = re.search(r'(Part\s+[IVX]+)\.?\s*$', text_before, re.IGNORECASE)
                    if part_match:
                        return part_match.group(1)

        except Exception:
            pass

        return ''

    def _extract_part_context(self, text: str) -> Optional[str]:
        """Extract normalized part label from text, e.g., "Part II"."""
        part_match = re.match(r'^\s*part\s+([ivx]+)\b', text, re.IGNORECASE)
        if not part_match:
            return None

        return f"Part {part_match.group(1).upper()}"

    def _infer_part_from_row_context(self, link_element) -> Optional[str]:
        """
        Infer part context from nearby table rows.

        Many TOCs place part headers ("PART I", "PART II", ...) in standalone
        rows that do not contain links. This method finds the nearest preceding
        sibling row with a part marker and returns it as context for the current
        linked item row.
        """
        max_rows_to_scan = 200

        try:
            # Find containing row for this link.
            current = link_element
            row = None
            for _ in range(10):
                parent = current.getparent()
                if parent is None:
                    break
                if parent.tag == 'tr':
                    row = parent
                    break
                current = parent

            if row is None:
                return None

            # Search backwards through previous rows for a standalone part header.
            prev = row.getprevious()
            rows_scanned = 0
            while prev is not None and rows_scanned < max_rows_to_scan:
                rows_scanned += 1

                if prev.tag == 'tr':
                    # Check each cell separately to avoid row text concatenation
                    # artifacts like "PART I3" when a page number is in another cell.
                    cells = prev.xpath('./td|./th')
                    if cells:
                        for cell in cells:
                            cell_text = (cell.text_content() or '').strip()
                            part = self._extract_part_context(cell_text)
                            if part:
                                return part
                    else:
                        prev_text = (prev.text_content() or '').strip()
                        part = self._extract_part_context(prev_text)
                        if part:
                            return part

                prev = prev.getprevious()

        except Exception:
            return None

        return None

    def _is_section_link(self, text: str, anchor_id: str = '', preceding_item: str = '') -> bool:
        """
        Check if link represents a section reference.

        Checks link text, anchor ID, and preceding context to handle cases where:
        - Text is descriptive (e.g., "Executive Compensation")
        - Anchor ID contains item number (e.g., "item_11_executive_compensation")
        - Item number is in preceding table cell (e.g., <td>Item 1.</td><td><a>Business</a></td>)

        Args:
            text: Link text
            anchor_id: Anchor ID from href (without #)
            preceding_item: Item/part label from preceding context (e.g., "Item 1A")

        Returns:
            True if this appears to be a section link
        """
        if not text:
            return False

        # First check if there's a preceding item label (table-based TOC)
        if preceding_item:
            return True

        # Then check anchor ID for item/part patterns (most reliable)
        if anchor_id:
            anchor_lower = anchor_id.lower()
            # Match patterns like: item_1, item_1a, item1, item1a, part_i, part_ii, etc.
            if re.search(r'item_?\d+[a-z]?', anchor_lower):
                return True
            if re.search(r'part_?[ivx]+', anchor_lower):
                return True

        # Then check text (with relaxed length limit for descriptive section names)
        if len(text) > 150:  # Increased from 100 to accommodate longer section titles
            return False

        # Check against known patterns
        for pattern, _ in self.section_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        # Also consider links with section keywords
        if len(text) < 100 and any(keyword in text.lower() for keyword in
                                   ['item', 'part', 'business', 'risk', 'properties', 'legal',
                                    'compensation', 'ownership', 'governance', 'directors']):
            return True

        return False

    def _normalize_section_name(self, text: str, anchor_id: str = '', preceding_item: str = '') -> str:
        """
        Normalize section name for consistent lookup.

        Prioritizes:
        1. Preceding item label (table-based TOC)
        2. Anchor ID pattern
        3. Text-based normalization

        Args:
            text: Link text
            anchor_id: Anchor ID from href (without #)
            preceding_item: Item/part label from preceding context

        Returns:
            Normalized section name (e.g., "Item 1A", "Part II")
        """
        text = text.strip()

        # HIGHEST PRIORITY: Use preceding item label if available (table-based TOC)
        if preceding_item:
            # Clean up and normalize the preceding item
            item_match = re.match(r'item\s+(\d+[a-z]?)', preceding_item, re.IGNORECASE)
            if item_match:
                return f"Item {item_match.group(1).upper()}"

            part_match = re.match(r'part\s+([ivx]+)', preceding_item, re.IGNORECASE)
            if part_match:
                return f"Part {part_match.group(1).upper()}"

        # SECOND PRIORITY: Try to extract from anchor ID
        if anchor_id:
            anchor_lower = anchor_id.lower()

            # Match item patterns: item_1a, item1a, item_1_business, etc.
            item_match = re.search(r'item_?(\d+[a-z]?)', anchor_lower)
            if item_match:
                item_num = item_match.group(1).upper()
                return f"Item {item_num}"

            # Match part patterns: part_i, part_ii, parti, partii, etc.
            part_match = re.search(r'part_?([ivx]+)', anchor_lower)
            if part_match:
                part_num = part_match.group(1).upper()
                return f"Part {part_num}"

        # THIRD PRIORITY: Text-based normalization
        # Handle common Item patterns in text
        item_match = re.match(r'item\s+(\d+[a-z]?)', text, re.IGNORECASE)
        if item_match:
            return f"Item {item_match.group(1).upper()}"

        # Handle Part patterns
        part_match = re.match(r'part\s+([ivx]+)', text, re.IGNORECASE)
        if part_match:
            return f"Part {part_match.group(1).upper()}"

        # Handle specific known sections by text
        text_lower = text.lower()
        if 'business' in text_lower and 'item' not in text_lower:
            return "Item 1"
        elif 'risk factors' in text_lower and 'item' not in text_lower:
            return "Item 1A"
        elif 'properties' in text_lower and 'item' not in text_lower:
            return "Item 2"
        elif 'legal proceedings' in text_lower and 'item' not in text_lower:
            return "Item 3"
        elif 'management' in text_lower and 'discussion' in text_lower:
            return "Item 7"
        elif 'financial statements' in text_lower:
            return "Item 8"
        elif 'exhibits' in text_lower:
            return "Item 15"

        return text  # Return as-is if no normalization applies

    def _get_section_type_and_order(self, text: str) -> Tuple[str, int]:
        """Get section type and order for sorting."""
        text_lower = text.lower()

        # Part-aware section names (e.g., part_i_item_1, part_ii_item_1a)
        # These names are generated for 10-Q filings to distinguish Part I and Part II items
        part_aware_match = re.search(r'part_([ivx]+)_item[_\s]*(\d+)([a-z]?)', text_lower)
        if part_aware_match:
            part_roman = part_aware_match.group(1)
            item_num = int(part_aware_match.group(2))
            item_letter = part_aware_match.group(3) or ''
            part_num = self._roman_to_int(part_roman)
            # Order: Part I Item 1=100_1000, Part II Item 1=200_1000
            # Part multiplier ensures Part I items come before Part II items
            item_order = item_num * 1000 + (ord(item_letter.upper()) - ord('A') + 1 if item_letter else 0)
            order = part_num * 100000 + item_order
            return 'item', order

        # Standard Items (Item 1, Item 1A, etc.)
        item_match = re.search(r'item[\s_]*(\d+)([a-z]?)', text_lower)
        if item_match:
            item_num = int(item_match.group(1))
            item_letter = item_match.group(2) or ''
            # Order: Item 1=1000, Item 1A=1001, Item 2=2000, etc.
            order = item_num * 1000 + (ord(item_letter.upper()) - ord('A') + 1 if item_letter else 0)
            return 'item', order

        # Parts (Part I, Part II, etc.)
        part_match = re.search(r'part[\s_]*([ivx]+)', text_lower)
        if part_match:
            part_roman = part_match.group(1)
            part_num = self._roman_to_int(part_roman)
            return 'part', part_num * 100  # Part I=100, Part II=200, etc.

        # Known sections without explicit item numbers
        if 'business' in text_lower:
            return 'item', 1000  # Item 1
        elif 'risk factors' in text_lower:
            return 'item', 1001  # Item 1A
        elif 'properties' in text_lower:
            return 'item', 2000  # Item 2
        elif 'legal proceedings' in text_lower:
            return 'item', 3000  # Item 3
        elif 'management' in text_lower and 'discussion' in text_lower:
            return 'item', 7000  # Item 7
        elif 'financial statements' in text_lower:
            return 'item', 8000  # Item 8
        elif 'exhibits' in text_lower:
            return 'item', 15000  # Item 15

        return 'other', 99999

    def _roman_to_int(self, roman: str) -> int:
        """Convert roman numerals to integers."""
        roman_map = {'i': 1, 'v': 5, 'x': 10, 'l': 50, 'c': 100, 'd': 500, 'm': 1000}
        roman = roman.lower()
        result = 0
        prev = 0

        for char in reversed(roman):
            value = roman_map.get(char, 0)
            if value < prev:
                result -= value
            else:
                result += value
            prev = value

        return result

    def _build_section_mapping(self, toc_sections: List[TOCSection],
                               tree=None) -> Dict[str, str]:
        """Build final section mapping, handling duplicates intelligently.

        For 10-Q filings with part context, generates part-aware section names
        like "part_i_item_1" and "part_ii_item_1" to distinguish sections
        with the same item number across different parts.

        When duplicate entries exist for the same section (e.g., "Item 1." and
        "Business" both normalizing to "Item 1"), validates anchors by checking
        if the target content matches the expected item heading.
        """
        # Sort sections by order
        toc_sections.sort(key=lambda x: x.order)

        mapping = {}
        seen_names = set()

        for section in toc_sections:
            # Generate part-aware section name for 10-Q filings
            if section.part:
                # Convert "Part I" -> "part_i", "Part II" -> "part_ii"
                part_key = section.part.lower().replace(' ', '_')
                # Convert "Item 1" -> "item_1", "Item 1A" -> "item_1a"
                item_key = section.normalized_name.lower().replace(' ', '_')
                section_name = f"{part_key}_{item_key}"
            else:
                # 10-K filings: use normalized name as-is
                section_name = section.normalized_name

            if section_name in seen_names:
                # Duplicate: validate which anchor is better.
                # Some TOCs have split links: "Item 1." → wrong anchor,
                # "Business" → correct anchor. Check if the new anchor's
                # target content matches the expected section heading.
                if tree is not None and section_name in mapping:
                    existing_anchor = mapping[section_name]
                    new_anchor = section.anchor_id
                    if existing_anchor != new_anchor:
                        if self._anchor_matches_heading(tree, new_anchor, section.normalized_name):
                            if not self._anchor_matches_heading(tree, existing_anchor, section.normalized_name):
                                # New anchor is better — replace
                                mapping[section_name] = new_anchor
                continue

            mapping[section_name] = section.anchor_id
            seen_names.add(section_name)

        return mapping

    def _anchor_matches_heading(self, tree, anchor_id: str, expected_name: str) -> bool:
        """Check if the content near an anchor target matches the expected section heading."""
        targets = find_anchor_targets(tree, anchor_id)
        if not targets:
            return False

        target = targets[0]
        # Look at the next few elements for a heading that matches
        try:
            following = target.xpath('following::*[string-length(normalize-space(text())) > 3][position() <= 3]')
            for el in following:
                el_text = (el.text_content() or '').strip().upper()[:80]
                # Extract item pattern from expected name (e.g., "Item 1" → "ITEM 1")
                item_match = re.search(r'item\s+(\d+[a-z]?)', expected_name, re.IGNORECASE)
                if item_match:
                    item_pattern = f'ITEM {item_match.group(1).upper()}'
                    if item_pattern in el_text:
                        return True
        except Exception:
            pass

        return False

    def get_section_suggestions(self, html_content: str) -> List[str]:
        """Get list of available sections that can be extracted."""
        mapping = self.analyze_toc_structure(html_content)
        return sorted(mapping.keys(), key=lambda x: self._get_section_type_and_order(x)[1])


def analyze_toc_for_sections(html_content: str, agent: Optional[str] = None,
                             tree=None) -> Dict[str, str]:
    """
    Convenience function to analyze TOC and return section mapping.

    Args:
        html_content: Raw HTML content
        agent: Filing agent name or None
        tree: Pre-parsed lxml tree (optional)

    Returns:
        Dict mapping section names to anchor IDs
    """
    analyzer = TOCAnalyzer()
    return analyzer.analyze_toc_structure(html_content, agent=agent, tree=tree)


def find_toc_boundaries(html_content: str) -> Tuple[int, int]:
    """
    Find the start and end positions of the Table of Contents region in HTML.

    This is used by pattern-based section extraction to skip TOC entries
    and only match actual section headers in the document body.

    The function uses two strategies:
    1. Look for explicit "TABLE OF CONTENTS" heading
    2. Fallback: Find tables with Item + page number pattern

    Args:
        html_content: Raw HTML content

    Returns:
        Tuple of (start_position, end_position) for TOC region.
        Returns (0, 0) if no TOC is found.

    Example:
        >>> start, end = find_toc_boundaries(html)
        >>> if start < match_position < end:
        ...     # Skip this match - it's inside the TOC
        ...     continue
    """
    if not html_content:
        return (0, 0)

    # Handle XML declaration
    if html_content.startswith('<?xml'):
        html_content = re.sub(r'<\?xml[^>]*\?>', '', html_content, count=1)

    # Strategy 1: Look for explicit "TABLE OF CONTENTS" heading
    toc_start = html_content.find('TABLE OF CONTENTS')
    if toc_start == -1:
        # Try case-insensitive
        toc_start_lower = html_content.lower().find('table of contents')
        if toc_start_lower > 0:
            toc_start = toc_start_lower

    # Strategy 2: If no heading found, look for table with TOC-like structure
    if toc_start == -1:
        toc_start = _find_toc_table_start(html_content)

    if toc_start == -1:
        return (0, 0)  # No TOC found

    # Find TOC end by locating "SIGNATURES" (last item in most TOCs)
    # then finding the closing </table> tag
    signatures_pos = html_content.find('SIGNATURES', toc_start)
    if signatures_pos == -1:
        # Fallback: look for case-insensitive
        signatures_lower = html_content.lower().find('signatures', toc_start)
        if signatures_lower > 0:
            signatures_pos = signatures_lower

    if signatures_pos > 0:
        # Find the closing </table> after SIGNATURES
        toc_end = html_content.find('</table>', signatures_pos)
        if toc_end > 0:
            # Add length of </table> tag to include it
            toc_end += len('</table>')
            return (toc_start, toc_end)

    # Fallback: estimate TOC end as ~50KB after start (typical TOC size)
    # This is a safety fallback if SIGNATURES isn't found
    return (toc_start, min(toc_start + 50000, len(html_content)))


def _find_toc_table_start(html_content: str) -> int:
    """
    Find the start position of a TOC table by detecting Item + page number pattern.

    This handles filings that don't have an explicit "TABLE OF CONTENTS" heading
    but do have a structured TOC table.

    Args:
        html_content: Raw HTML content

    Returns:
        Start position of TOC table, or -1 if not found
    """
    try:
        tree = lxml_html.fromstring(html_content)
        tables = tree.xpath('//table')

        for table in tables:
            rows = table.xpath('.//tr')
            if len(rows) < 3:
                continue

            # Count rows with TOC-like pattern: "Item X" + page number at end
            toc_like_rows = 0
            for row in rows[:20]:  # Check first 20 rows
                row_text = row.text_content().strip()
                # Pattern: "Item X" followed by page number (1-3 digits) at end
                has_item = re.search(r'Item\s+\d', row_text, re.IGNORECASE)
                has_page_num = re.search(r'\d{1,3}\s*$', row_text)
                if has_item and has_page_num:
                    toc_like_rows += 1

            # If 3+ rows match the pattern, this is likely a TOC table
            if toc_like_rows >= 3:
                # Find the table's position by searching for its first row content
                first_row_text = rows[0].text_content().strip()
                if first_row_text:
                    # Use first 30 chars to find position
                    search_text = first_row_text[:30]
                    pos = html_content.find(search_text)
                    if pos > 0:
                        return pos

    except Exception:
        pass

    return -1
