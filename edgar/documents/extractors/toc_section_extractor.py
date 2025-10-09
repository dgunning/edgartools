"""
Section extraction for SEC filings using Table of Contents analysis.

This system uses TOC structure to extract specific sections like "Item 1", 
"Item 1A", etc. from SEC filings. This approach works consistently across
all SEC filings regardless of whether they use semantic anchors or generated IDs.
"""
import re
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from lxml import html as lxml_html

from edgar.documents.nodes import Node, SectionNode
from edgar.documents.document import Document
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
        except Exception as e:
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
        Extract section content from HTML between anchors.
        
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
        
        # Find start element
        start_elements = tree.xpath(f'//*[@id="{boundary.anchor_id}"]')
        if not start_elements:
            return ""
        
        start_element = start_elements[0]

        # Collect content until we hit the end boundary (if specified)
        content_elements = []

        # If anchor has no siblings (nested in empty container), traverse up to find content container
        # This handles cases like <div id="item7"><div></div></div> where content is after the container
        current = start_element.getnext()
        if current is None:
            # No sibling - traverse up to find a container with siblings
            container = start_element.getparent()
            while container is not None and container.getnext() is None:
                container = container.getparent()

            # Start from the container's next sibling if found
            if container is not None:
                current = container.getnext()

        # Collect content from siblings
        if current is not None:
            # Normal case - anchor has siblings
            while current is not None:
                # Check if we've reached the end boundary
                if boundary.end_element_id:
                    current_id = current.get('id', '')
                    if current_id == boundary.end_element_id:
                        break

                    # Also check if this is a sibling section we should stop at
                    if not include_subsections and self._is_sibling_section(current_id, boundary.name):
                        break

                content_elements.append(current)
                current = current.getnext()
        
        # Extract text from collected elements
        section_texts = []
        for element in content_elements:
            text = self._extract_element_text(element)
            if text.strip():
                section_texts.append(text)
        
        combined_text = '\n\n'.join(section_texts)
        
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
        # This would integrate with your existing text extraction logic
        # For now, simple text extraction
        return element.text_content() or ""
    
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
    
    def _extract_section_fallback(self, section_name: str, clean: bool) -> Optional[str]:
        """
        Fallback section extraction using document nodes.
        
        This is used when HTML-based extraction fails.
        """
        # Search through document sections
        for name, section in self.document.sections.items():
            if section_name.lower() in name.lower():
                return section.text(clean=clean)
        
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