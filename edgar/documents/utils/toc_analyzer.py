"""
Table of Contents analyzer for SEC filings.

This module analyzes the TOC structure to map section names to anchor IDs,
enabling section extraction for API filings with generated anchor IDs.
"""
import re
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from lxml import html as lxml_html


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
    
    def analyze_toc_structure(self, html_content: str) -> Dict[str, str]:
        """
        Analyze HTML content to extract section mappings from TOC.

        Args:
            html_content: Raw HTML content

        Returns:
            Dict mapping normalized section names to anchor IDs
        """
        section_mapping = {}

        try:
            # Handle XML declaration issues
            if html_content.startswith('<?xml'):
                html_content = re.sub(r'<\?xml[^>]*\?>', '', html_content, count=1)

            tree = lxml_html.fromstring(html_content)

            # Find all anchor links that could be TOC links
            anchor_links = tree.xpath('//a[@href]')

            toc_sections = []
            current_part = None  # Track current part context for 10-Q filings
            part_pattern = re.compile(r'^\s*Part\s+([IVX]+)\b', re.IGNORECASE)

            for link in anchor_links:
                href = link.get('href', '').strip()
                text = (link.text_content() or '').strip()

                # Check if this link or its row represents a part header
                # Part headers in 10-Q TOCs typically appear as separate rows: "Part I", "Part II"
                part_match = part_pattern.match(text)
                if part_match:
                    # Update current part context
                    current_part = f"Part {part_match.group(1).upper()}"
                    # Don't create a section for the part header itself
                    continue

                # Look for internal anchor links
                if href.startswith('#') and text:
                    anchor_id = href[1:]  # Remove #

                    # Try to find item number in preceding context (for table-based TOCs)
                    preceding_item = self._extract_preceding_item_label(link)

                    # Check if this looks like a section reference (check text, anchor ID, and context)
                    if self._is_section_link(text, anchor_id, preceding_item):
                        # Verify target exists
                        target_elements = tree.xpath(f'//*[@id="{anchor_id}"]')
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
            section_mapping = self._build_section_mapping(toc_sections)

        except Exception as e:
            # Return empty mapping on error - fallback to other methods
            pass

        return section_mapping

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
        
        # Items
        item_match = re.search(r'item\s*(\d+)([a-z]?)', text_lower)
        if item_match:
            item_num = int(item_match.group(1))
            item_letter = item_match.group(2) or ''
            # Order: Item 1=1000, Item 1A=1001, Item 2=2000, etc.
            order = item_num * 1000 + (ord(item_letter.upper()) - ord('A') + 1 if item_letter else 0)
            return 'item', order
        
        # Parts
        part_match = re.search(r'part\s*([ivx]+)', text_lower)
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
    
    def _build_section_mapping(self, toc_sections: List[TOCSection]) -> Dict[str, str]:
        """Build final section mapping, handling duplicates intelligently.

        For 10-Q filings with part context, generates part-aware section names
        like "part_i_item_1" and "part_ii_item_1" to distinguish sections
        with the same item number across different parts.
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

            # Skip if we already have this section (prefer first occurrence)
            if section_name in seen_names:
                continue

            mapping[section_name] = section.anchor_id
            seen_names.add(section_name)

        return mapping
    
    def get_section_suggestions(self, html_content: str) -> List[str]:
        """Get list of available sections that can be extracted."""
        mapping = self.analyze_toc_structure(html_content)
        return sorted(mapping.keys(), key=lambda x: self._get_section_type_and_order(x)[1])


def analyze_toc_for_sections(html_content: str) -> Dict[str, str]:
    """
    Convenience function to analyze TOC and return section mapping.
    
    Args:
        html_content: Raw HTML content
        
    Returns:
        Dict mapping section names to anchor IDs
    """
    analyzer = TOCAnalyzer()
    return analyzer.analyze_toc_structure(html_content)