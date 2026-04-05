"""
Section extraction for SEC filings using Table of Contents analysis.

This system uses TOC structure to extract specific sections like "Item 1", 
"Item 1A", etc. from SEC filings. This approach works consistently across
all SEC filings regardless of whether they use semantic anchors or generated IDs.
"""
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from lxml import etree
from lxml import html as lxml_html

from edgar.documents.document import Document
from edgar.documents.nodes import Node
from edgar.documents.utils.toc_analyzer import TOCAnalyzer


@dataclass
class SectionBoundary:
    """Represents the boundaries of a document section."""
    name: str
    anchor_id: str
    start_element_id: Optional[str] = None
    end_element_id: Optional[str] = None
    start_node: Optional[Node] = None
    end_node: Optional[Node] = None
    text_start: Optional[int] = None  # Character position in full text
    text_end: Optional[int] = None
    confidence: float = 1.0  # Detection confidence (0.0-1.0)
    detection_method: str = 'unknown'  # How section was detected


class SECSectionExtractor:
    """
    Extract specific sections from SEC filings using Table of Contents analysis.
    
    This uses TOC structure to identify section boundaries and extract content
    between them. Works consistently for all SEC filings.
    """

    def __init__(self, document: Document):
        self.document = document
        self.section_map = {}  # Maps section names to canonical names
        self.section_boundaries = {}  # Maps section names to boundaries
        self.toc_analyzer = TOCAnalyzer()
        self._analyze_sections()

    def _analyze_sections(self) -> None:
        """
        Analyze the document using TOC structure to identify section boundaries.
        
        This creates a map of section names to their anchor positions using
        Table of Contents analysis, which works for all SEC filings.
        """
        # Get the original HTML if available
        html_content = getattr(self.document.metadata, 'original_html', None)
        if not html_content:
            return

        # Use TOC analysis to find sections
        toc_mapping = self.toc_analyzer.analyze_toc_structure(html_content)

        if not toc_mapping:
            return  # No sections found

        # Handle XML declaration issues  
        if html_content.startswith('<?xml'):
            html_content = re.sub(r'<\?xml[^>]*\?>', '', html_content, count=1)

        tree = lxml_html.fromstring(html_content)

        sec_sections = {}

        for section_name, anchor_id in toc_mapping.items():
            # Verify the anchor target exists
            target_elements = tree.xpath(f'//*[@id="{anchor_id}"]')
            if target_elements:
                element = target_elements[0]

                # Use TOC-based section info
                section_type, order = self.toc_analyzer._get_section_type_and_order(section_name)

                sec_sections[section_name] = {
                    'anchor_id': anchor_id,
                    'element': element,
                    'canonical_name': section_name,
                    'type': section_type,
                    'order': order,
                    'confidence': 0.95,  # TOC-based detection = high confidence
                    'detection_method': 'toc'  # Method: Table of Contents
                }

        if not sec_sections:
            return  # No valid sections found

        # Sort sections by their logical order
        sorted_sections = sorted(sec_sections.items(), key=lambda x: x[1]['order'])

        # Calculate section boundaries
        for i, (section_name, section_data) in enumerate(sorted_sections):
            start_anchor = section_data['anchor_id']

            # End boundary is the start of the next section (if any)
            end_anchor = None
            if i + 1 < len(sorted_sections):
                next_section = sorted_sections[i + 1][1]
                end_anchor = next_section['anchor_id']

            self.section_boundaries[section_name] = SectionBoundary(
                name=section_name,
                anchor_id=start_anchor,
                end_element_id=end_anchor,
                confidence=section_data.get('confidence', 0.95),
                detection_method=section_data.get('detection_method', 'toc')
            )

        self.section_map = {name: data['canonical_name'] for name, data in sec_sections.items()}



    def get_available_sections(self) -> List[str]:
        """
        Get list of available sections that can be extracted.
        
        Returns:
            List of section names
        """
        return sorted(self.section_boundaries.keys(), 
                     key=lambda x: self.section_boundaries[x].anchor_id)

    def get_section_text(self, section_name: str,
                        include_subsections: bool = True,
                        clean: bool = True) -> Optional[str]:
        """
        Extract text content for a specific section.

        Args:
            section_name: Name of section (e.g., "Item 1", "Item 1A", "Part I")
            include_subsections: Whether to include subsections
            clean: Whether to apply text cleaning

        Returns:
            Section text content or None if section not found
        """
        # Normalize section name
        normalized_name = self._normalize_section_name(section_name)

        if normalized_name not in self.section_boundaries:
            return None

        boundary = self.section_boundaries[normalized_name]

        # Extract content between boundaries using HTML parsing
        html_content = getattr(self.document.metadata, 'original_html', None)
        if not html_content:
            return None

        try:
            section_text = self._extract_section_content(html_content, boundary, include_subsections, clean)

            # Check if extracted content is suspiciously short for an Item section
            # This can happen when TOC anchors point to "PART I" header instead of actual Item content
            if section_text and len(section_text.strip()) < 200:
                # Check if this is an Item section that should have more content
                item_match = re.match(r'(?:part_[iv]+_)?item[_\s]*(\d+[a-z]?)', normalized_name, re.IGNORECASE)
                if item_match:
                    item_num = item_match.group(1).upper()
                    # Try to find actual Item content in HTML
                    actual_content = self._find_actual_item_content(html_content, item_num, boundary, clean)
                    if actual_content and len(actual_content) > len(section_text):
                        section_text = actual_content

            # If no direct content but include_subsections=True, aggregate subsection text
            if not section_text and include_subsections:
                subsections = self._get_subsections(normalized_name)
                if subsections:
                    # Recursively get text from all subsections
                    subsection_texts = []
                    for subsection_name in subsections:
                        subsection_text = self.get_section_text(subsection_name, include_subsections=True, clean=clean)
                        if subsection_text:
                            subsection_texts.append(subsection_text)

                    if subsection_texts:
                        section_text = '\n\n'.join(subsection_texts)

            return section_text
        except Exception:
            # Fallback to simple text extraction
            return self._extract_section_fallback(section_name, clean)

    def _normalize_section_name(self, section_name: str) -> str:
        """Normalize section name for lookup."""
        # Handle common variations
        name = section_name.strip()

        # "Item 1" vs "Item 1." vs "Item 1:"
        name = re.sub(r'[.:]$', '', name)

        # Case normalization
        if re.match(r'item\s+\d+', name, re.IGNORECASE):
            match = re.match(r'item\s+(\d+[a-z]?)', name, re.IGNORECASE)
            if match:
                name = f"Item {match.group(1).upper()}"
        elif re.match(r'part\s+[ivx]+', name, re.IGNORECASE):
            match = re.match(r'part\s+([ivx]+)', name, re.IGNORECASE)
            if match:
                name = f"Part {match.group(1).upper()}"

        return name

    def _extract_section_content(self, html_content: str, boundary: SectionBoundary,
                               include_subsections: bool, clean: bool) -> str:
        """
        Extract section content from HTML between anchors using document-order traversal.

        This method traverses the document in reading order (depth-first) from the start
        anchor to the end anchor, correctly handling multi-container sections where content
        spans across different parent elements.

        Args:
            html_content: Full HTML content
            boundary: Section boundary info
            include_subsections: Whether to include subsections
            clean: Whether to clean the text

        Returns:
            Extracted section text
        """
        # Handle XML declaration issues
        if html_content.startswith('<?xml'):
            html_content = re.sub(r'<\?xml[^>]*\?>', '', html_content, count=1)

        tree = lxml_html.fromstring(html_content)

        # Verify start anchor exists
        start_elements = tree.xpath(f'//*[@id="{boundary.anchor_id}"]')
        if not start_elements:
            return ""

        # Use document-order traversal (iterwalk) to collect all text between anchors
        # This correctly handles multi-container sections where start and end anchors
        # are in different parent containers
        all_text = []
        in_range = False

        # Block-level elements that should have paragraph breaks
        block_elements = {'p', 'div', 'table', 'tr', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                         'blockquote', 'pre', 'section', 'article', 'header', 'footer'}

        for event, el in etree.iterwalk(tree, events=('start', 'end')):
            # Skip non-element nodes (comments, etc.)
            if not hasattr(el, 'get'):
                continue

            el_id = el.get('id', '')
            tag_name = el.tag.lower() if isinstance(el.tag, str) else ''

            if event == 'start':
                # Check if we've reached the start anchor
                if el_id == boundary.anchor_id:
                    in_range = True
                    continue

                # Check if we've reached the end boundary
                if boundary.end_element_id and el_id == boundary.end_element_id:
                    in_range = False
                    break

                # Check for sibling section boundaries (when not including subsections)
                if in_range and not include_subsections and self._is_sibling_section(el_id, boundary.name):
                    in_range = False
                    break

                # Collect text content from element's direct text
                if in_range and el.text:
                    all_text.append(el.text)

            elif event == 'end':
                # Add paragraph break after block-level elements
                if in_range and tag_name in block_elements:
                    all_text.append('\n\n')

                # Collect tail text (text after closing tag)
                if in_range and el.tail:
                    all_text.append(el.tail)

        combined_text = ''.join(all_text)

        # Apply cleaning if requested
        if clean:
            combined_text = self._clean_section_text(combined_text)

        return combined_text

    def _is_sibling_section(self, element_id: str, current_section: str) -> bool:
        """Check if element ID represents a sibling section."""
        if not element_id:
            return False

        # Check if this looks like another item at the same level
        if 'item' in current_section.lower() and 'item' in element_id.lower():
            current_item = re.search(r'item\s*(\d+)', current_section, re.IGNORECASE)
            other_item = re.search(r'item[\s_]*(\d+)', element_id, re.IGNORECASE)

            if current_item and other_item:
                return current_item.group(1) != other_item.group(1)

        return False

    def _extract_element_text(self, element) -> str:
        """Extract clean text from an HTML element."""
        # Skip non-element nodes (comments, processing instructions, etc.)
        try:
            return element.text_content() or ""
        except (ValueError, AttributeError):
            # HtmlComment and other non-element nodes don't have text_content()
            return ""

    def _clean_section_text(self, text: str) -> str:
        """Clean extracted section text."""
        # Apply the same cleaning as the main document
        from edgar.documents.utils.anchor_cache import filter_with_cached_patterns

        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)

        # Filter navigation links
        html_content = getattr(self.document.metadata, 'original_html', None)
        if html_content:
            text = filter_with_cached_patterns(text, html_content)

        return text.strip()

    def _find_actual_item_content(self, html_content: str, item_num: str,
                                    boundary: SectionBoundary, clean: bool) -> Optional[str]:
        """
        Find actual Item content when TOC anchor points to wrong location.

        Some filings have TOC anchors that point to "PART I" header instead of
        the actual "ITEM 1. BUSINESS" content. This method searches for the
        actual Item header in the HTML and extracts content from there.

        Args:
            html_content: Full HTML content
            item_num: Item number (e.g., "1", "1A", "7")
            boundary: Original section boundary
            clean: Whether to clean the text

        Returns:
            Extracted section text, or None if not found
        """
        from lxml import html as lxml_html

        # Handle XML declaration
        if html_content.startswith('<?xml'):
            html_content = re.sub(r'<\?xml[^>]*\?>', '', html_content, count=1)

        # Build pattern to find actual ITEM header
        # Match "ITEM 1." or "ITEM 1A." with various spacing/entities
        # Examples: "ITEM 1. BUSINESS", "ITEM 1.&#160;&#160;BUSINESS", "ITEM&#160;1. BUSINESS"
        item_pattern = rf'ITEM[\s&#;0-9xnbsp]+{re.escape(item_num)}\.?[\s&#;0-9xnbsp]*'

        # Common titles for different items
        item_titles = {
            '1': r'BUSINESS',
            '1A': r'RISK\s*FACTORS?',
            '1B': r'UNRESOLVED\s*STAFF\s*COMMENTS?',
            '1C': r'CYBERSECURITY',
            '2': r'PROPERTIES',
            '3': r'LEGAL\s*PROCEEDINGS?',
            '4': r'MINE\s*SAFETY',
            '5': r'MARKET\s*FOR',
            '6': r'(SELECTED|RESERVED)',
            '7': r'MANAGEMENT',
            '7A': r'QUANTITATIVE',
            '8': r'FINANCIAL\s*STATEMENTS?',
            '9': r'CHANGES?\s*IN',
            '9A': r'CONTROLS?',
            '9B': r'OTHER\s*INFORMATION',
            '9C': r'DISCLOSURE',
        }

        title_pattern = item_titles.get(item_num, r'\w+')
        full_pattern = rf'{item_pattern}{title_pattern}'

        # Search for the pattern in HTML
        match = re.search(full_pattern, html_content, re.IGNORECASE)
        if not match:
            return None

        start_pos = match.start()

        # Find the end of this section (next ITEM header)
        # Start searching after current match
        search_start = start_pos + len(match.group())

        # Find next ITEM or PART header
        next_item_pattern = rf'ITEM[\s&#;0-9xnbsp]*\d+[A-Z]?\.?\s*[A-Z]'
        next_match = re.search(next_item_pattern, html_content[search_start:], re.IGNORECASE)

        if next_match:
            end_pos = search_start + next_match.start()
        else:
            # No next item found - use end boundary anchor if available
            if boundary.end_element_id:
                end_anchor_pos = html_content.find(f'id="{boundary.end_element_id}"')
                if end_anchor_pos > start_pos:
                    end_pos = end_anchor_pos
                else:
                    end_pos = len(html_content)
            else:
                end_pos = len(html_content)

        # Extract HTML content
        section_html = html_content[start_pos:end_pos]

        # Parse and extract text
        try:
            wrapped = f'<div>{section_html}</div>'
            tree = lxml_html.fromstring(wrapped)
            text = tree.text_content()

            if clean:
                text = self._clean_section_text(text)

            return text.strip()
        except Exception:
            return None

    def _extract_section_fallback(self, section_name: str, clean: bool) -> Optional[str]:
        """
        Fallback section extraction using document nodes.

        This is used when HTML-based extraction fails.

        NOTE: This method CANNOT access self.document.sections because it's called
        DURING section detection, which would create infinite recursion.
        The circular dependency was: document.sections -> detect_sections() ->
        get_section_text() -> _extract_section_fallback() -> document.sections

        Returns:
            None - fallback disabled to prevent infinite recursion
        """
        # BUGFIX: Removed circular dependency that caused infinite recursion
        # Previously this accessed self.document.sections.items() which created
        # an infinite loop during section detection.
        #
        # If HTML-based extraction fails, we simply return None rather than
        # trying to use sections that haven't been computed yet.
        return None

    def get_section_info(self, section_name: str) -> Optional[Dict]:
        """
        Get detailed information about a section.
        
        Args:
            section_name: Section name to look up
            
        Returns:
            Dict with section metadata
        """
        normalized_name = self._normalize_section_name(section_name)

        if normalized_name not in self.section_boundaries:
            return None

        boundary = self.section_boundaries[normalized_name]

        return {
            'name': boundary.name,
            'anchor_id': boundary.anchor_id,
            'available': True,
            'estimated_length': None,  # Could calculate if needed
            'subsections': self._get_subsections(normalized_name)
        }

    def _get_subsections(self, parent_section: str) -> List[str]:
        """
        Get subsections of a parent section.

        For example:
        - "Item 1" has subsections "Item 1A", "Item 1B" (valid)
        - "Item 1" does NOT have subsection "Item 10" (invalid - different item)
        """
        subsections = []

        # Look for sections that start with the parent name
        for section_name in self.section_boundaries:
            if section_name == parent_section:
                continue

            if section_name.startswith(parent_section):
                # Check if this is a true subsection (e.g., Item 1A)
                # vs a different section that happens to start with same prefix (e.g., Item 10)
                remainder = section_name[len(parent_section):]

                # Valid subsection patterns:
                # - "Item 1A" (remainder: "A") - letter suffix
                # - "Item 1 - Business" (remainder: " - Business") - has separator
                # Invalid patterns:
                # - "Item 10" (remainder: "0") - digit continues the number

                if remainder and remainder[0].isalpha():
                    # Letter suffix like "A", "B" - valid subsection
                    subsections.append(section_name)
                elif remainder and remainder[0] in [' ', '-', '.', ':']:
                    # Has separator - could be descriptive title
                    subsections.append(section_name)
                # If remainder starts with digit, it's NOT a subsection (e.g., "Item 10")

        return sorted(subsections)
