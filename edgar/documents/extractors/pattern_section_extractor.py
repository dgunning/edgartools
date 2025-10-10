"""
Section extraction from documents.
"""

import re
from typing import Dict, List, Optional, Tuple

from edgar.documents.document import Document, Section
from edgar.documents.nodes import Node, HeadingNode, SectionNode


class SectionExtractor:
    """
    Extracts logical sections from documents.
    
    Identifies document sections like:
    - Business Overview (Item 1)
    - Risk Factors (Item 1A)
    - MD&A (Item 7)
    - Financial Statements (Item 8)
    """
    
    # Common section patterns for different filing types
    SECTION_PATTERNS = {
        '10-K': {
            'business': [
                (r'^(Item|ITEM)\s+1\.?\s*Business', 'Item 1 - Business'),
                (r'^Business\s*$', 'Business'),
                (r'^Business Overview', 'Business Overview'),
                (r'^Our Business', 'Our Business'),
                (r'^Company Overview', 'Company Overview')
            ],
            'risk_factors': [
                (r'^(Item|ITEM)\s+1A\.?\s*Risk\s+Factors', 'Item 1A - Risk Factors'),
                (r'^Risk\s+Factors', 'Risk Factors'),
                (r'^Factors\s+That\s+May\s+Affect', 'Risk Factors')
            ],
            'properties': [
                (r'^(Item|ITEM)\s+2\.?\s*Properties', 'Item 2 - Properties'),
                (r'^Properties', 'Properties'),
                (r'^Real\s+Estate', 'Real Estate')
            ],
            'legal_proceedings': [
                (r'^(Item|ITEM)\s+3\.?\s*Legal\s+Proceedings', 'Item 3 - Legal Proceedings'),
                (r'^Legal\s+Proceedings', 'Legal Proceedings'),
                (r'^Litigation', 'Litigation')
            ],
            'market_risk': [
                (r'^(Item|ITEM)\s+7A\.?\s*Quantitative.*Disclosures', 'Item 7A - Market Risk'),
                (r'^Market\s+Risk', 'Market Risk'),
                (r'^Quantitative.*Qualitative.*Market\s+Risk', 'Market Risk')
            ],
            'mda': [
                (r'^(Item|ITEM)\s+7\.?\s*Management.*Discussion', 'Item 7 - MD&A'),
                (r'^Management.*Discussion.*Analysis', 'MD&A'),
                (r'^MD&A', 'MD&A')
            ],
            'financial_statements': [
                (r'^(Item|ITEM)\s+8\.?\s*Financial\s+Statements', 'Item 8 - Financial Statements'),
                (r'^Financial\s+Statements', 'Financial Statements'),
                (r'^Consolidated\s+Financial\s+Statements', 'Consolidated Financial Statements')
            ],
            'controls_procedures': [
                (r'^(Item|ITEM)\s+9A\.?\s*Controls.*Procedures', 'Item 9A - Controls and Procedures'),
                (r'^Controls.*Procedures', 'Controls and Procedures'),
                (r'^Internal\s+Control', 'Internal Controls')
            ]
        },
        '10-Q': {
            'financial_statements': [
                (r'^(Item|ITEM)\s+1\.?\s*Financial\s+Statements', 'Item 1 - Financial Statements'),
                (r'^Financial\s+Statements', 'Financial Statements'),
                (r'^Condensed.*Financial\s+Statements', 'Condensed Financial Statements')
            ],
            'mda': [
                (r'^(Item|ITEM)\s+2\.?\s*Management.*Discussion', 'Item 2 - MD&A'),
                (r'^Management.*Discussion.*Analysis', 'MD&A')
            ],
            'market_risk': [
                (r'^(Item|ITEM)\s+3\.?\s*Quantitative.*Disclosures', 'Item 3 - Market Risk'),
                (r'^Market\s+Risk', 'Market Risk')
            ],
            'controls_procedures': [
                (r'^(Item|ITEM)\s+4\.?\s*Controls.*Procedures', 'Item 4 - Controls and Procedures'),
                (r'^Controls.*Procedures', 'Controls and Procedures')
            ],
            'legal_proceedings': [
                (r'^(Item|ITEM)\s+1\.?\s*Legal\s+Proceedings', 'Item 1 - Legal Proceedings'),
                (r'^Legal\s+Proceedings', 'Legal Proceedings')
            ],
            'risk_factors': [
                (r'^(Item|ITEM)\s+1A\.?\s*Risk\s+Factors', 'Item 1A - Risk Factors'),
                (r'^Risk\s+Factors', 'Risk Factors')
            ]
        },
        '8-K': {
            'item_101': [
                (r'^(Item|ITEM)\s+1\.01', 'Item 1.01 - Entry into Material Agreement'),
                (r'^Entry.*Material.*Agreement', 'Material Agreement')
            ],
            'item_201': [
                (r'^(Item|ITEM)\s+2\.01', 'Item 2.01 - Completion of Acquisition'),
                (r'^Completion.*Acquisition', 'Acquisition')
            ],
            'item_202': [
                (r'^(Item|ITEM)\s+2\.02', 'Item 2.02 - Results of Operations'),
                (r'^Results.*Operations', 'Results of Operations')
            ],
            'item_503': [
                (r'^(Item|ITEM)\s+5\.03', 'Item 5.03 - Director/Officer Changes'),
                (r'^Amendments.*Articles', 'Charter Amendments')
            ],
            'item_801': [
                (r'^(Item|ITEM)\s+8\.01', 'Item 8.01 - Other Events'),
                (r'^Other\s+Events', 'Other Events')
            ],
            'item_901': [
                (r'^(Item|ITEM)\s+9\.01', 'Item 9.01 - Financial Statements and Exhibits'),
                (r'^Financial.*Exhibits', 'Financial Statements and Exhibits')
            ]
        }
    }
    
    def __init__(self, form: Optional[str] = None):
        """
        Initialize section extractor.
        
        Args:
            form: Type of filing (10-K, 10-Q, 8-K, etc.)
        """
        self.form = form
    
    def extract(self, document: Document) -> Dict[str, Section]:
        """
        Extract sections from document.

        Args:
            document: Document to extract sections from

        Returns:
            Dictionary mapping section names to Section objects
        """
        # Get filing type from instance, metadata, or document config
        # NOTE: We no longer auto-detect filing type (expensive and unnecessary)
        form = None

        if self.form:
            form = self.form
        elif document.metadata and document.metadata.form:
            form = document.metadata.form
        elif hasattr(document, '_config') and document._config and document._config.form:
            form = document._config.form

        # Only extract sections for forms that have standard sections
        if not form or form not in ['10-K', '10-Q', '8-K']:
            return {}  # No filing type or unsupported form = no section detection

        # Get patterns for filing type
        patterns = self.SECTION_PATTERNS.get(form, {})
        if not patterns:
            return {}  # No patterns defined for this form type

        # Find section headers
        headers = self._find_section_headers(document)

        # For 10-Q, detect Part I/Part II boundaries
        part_context = None
        if form == '10-Q':
            part_context = self._detect_10q_parts(headers)

        # Match headers to sections
        sections = self._match_sections(headers, patterns, document, part_context)

        # Create section objects
        return self._create_sections(sections, document)
    
    # NOTE: _detect_form() removed - form type should be known from context
    # Filing metadata should be set by the caller (Filing class, TenK/TenQ, etc.)

    # NOTE: _infer_form_from_headers() kept for backward compatibility but not used
    # in normal flow anymore. Form type should always be provided explicitly.
    def _infer_form_from_headers(self, document: Document) -> str:
        """
        Infer filing type from section headers.

        NOTE: This method is kept for backward compatibility but should not be used
        in the normal flow. Form type should be explicitly provided via config or metadata.
        """
        headers = document.headings
        header_texts = [h.text().upper() for h in headers if h.text()]

        # Check for 10-K specific sections
        has_10k_sections = any(
            'ITEM 1.' in text or 'ITEM 1A.' in text or 'ITEM 7.' in text or 'ITEM 8.' in text
            for text in header_texts
        )

        # Check for 10-Q specific sections
        has_10q_sections = any(
            ('ITEM 1.' in text and 'FINANCIAL STATEMENTS' in text) or
            ('ITEM 2.' in text and 'MANAGEMENT' in text) or
            'ITEM 3.' in text or 'ITEM 4.' in text
            for text in header_texts
        )

        # Check for 8-K specific sections
        has_8k_sections = any(
            re.search(r'ITEM \d\.\d{2}', text) for text in header_texts
        )

        if has_10k_sections and not has_10q_sections:
            return '10-K'
        elif has_10q_sections:
            return '10-Q'
        elif has_8k_sections:
            return '8-K'
        else:
            return 'UNKNOWN'
    
    def _get_general_patterns(self) -> Dict[str, List[Tuple[str, str]]]:
        """Get general section patterns."""
        return {
            'business': [
                (r'^Business', 'Business'),
                (r'^Overview', 'Overview'),
                (r'^Company', 'Company')
            ],
            'financial': [
                (r'^Financial\s+Statements', 'Financial Statements'),
                (r'^Consolidated.*Statements', 'Consolidated Statements')
            ],
            'notes': [
                (r'^Notes\s+to.*Financial\s+Statements', 'Notes to Financial Statements'),
                (r'^Notes\s+to.*Statements', 'Notes')
            ]
        }
    
    def _find_section_headers(self, document: Document) -> List[Tuple[Node, str, int]]:
        """Find all potential section headers."""
        headers = []
        
        # Find all heading nodes
        heading_nodes = document.root.find(lambda n: isinstance(n, HeadingNode))
        
        for node in heading_nodes:
            text = node.text()
            if text:
                # Get position in document
                position = self._get_node_position(node, document)
                headers.append((node, text, position))
        
        # Also check for section nodes
        section_nodes = document.root.find(lambda n: isinstance(n, SectionNode))
        for node in section_nodes:
            # Get first heading in section
            first_heading = node.find_first(lambda n: isinstance(n, HeadingNode))
            if first_heading:
                text = first_heading.text()
                if text:
                    position = self._get_node_position(node, document)
                    headers.append((node, text, position))
        
        # Sort by position
        headers.sort(key=lambda x: x[2])
        
        return headers
    
    def _get_node_position(self, node: Node, document: Document) -> int:
        """Get position of node in document."""
        position = 0
        for n in document.root.walk():
            if n == node:
                return position
            position += 1
        return position
    
    def _detect_10q_parts(self, headers: List[Tuple[Node, str, int]]) -> Dict[int, str]:
        """
        Detect Part I and Part II boundaries in 10-Q filings.

        Args:
            headers: List of (node, text, position) tuples

        Returns:
            Dict mapping header index to part name ("Part I" or "Part II")
        """
        part_context = {}
        current_part = None

        part_i_pattern = re.compile(r'^\s*PART\s+I\b', re.IGNORECASE)
        part_ii_pattern = re.compile(r'^\s*PART\s+II\b', re.IGNORECASE)

        for i, (node, text, position) in enumerate(headers):
            text_stripped = text.strip()

            # Check if this is a Part I or Part II header
            if part_i_pattern.match(text_stripped):
                current_part = "Part I"
                part_context[i] = current_part
            elif part_ii_pattern.match(text_stripped):
                current_part = "Part II"
                part_context[i] = current_part
            elif current_part:
                # Headers after a Part declaration belong to that part
                part_context[i] = current_part

        return part_context

    def _match_sections(self,
                       headers: List[Tuple[Node, str, int]],
                       patterns: Dict[str, List[Tuple[str, str]]],
                       document: Document,
                       part_context: Optional[Dict[int, str]] = None) -> Dict[str, Tuple[Node, str, int, int]]:
        """Match headers to section patterns."""
        matched_sections = {}
        used_headers = set()

        # Try to match each pattern
        for section_name, section_patterns in patterns.items():
            for pattern, title in section_patterns:
                for i, (node, text, position) in enumerate(headers):
                    if i in used_headers:
                        continue

                    # Try to match pattern
                    if re.match(pattern, text.strip(), re.IGNORECASE):
                        # Find end position (next section or end of document)
                        end_position = self._find_section_end(i, headers, document)

                        # For 10-Q, prefix with Part I or Part II
                        final_title = title
                        if part_context and i in part_context:
                            final_title = f"{part_context[i]} - {title}"

                        # Use final_title as key to avoid conflicts
                        section_key = final_title if part_context and i in part_context else section_name
                        matched_sections[section_key] = (node, final_title, position, end_position)
                        used_headers.add(i)
                        break

                # If we found a match, move to next section
                if section_name in matched_sections:
                    break

        return matched_sections
    
    def _find_section_end(self, 
                         section_index: int, 
                         headers: List[Tuple[Node, str, int]],
                         document: Document) -> int:
        """Find where section ends."""
        # Next section starts where next header at same or higher level begins
        if section_index + 1 < len(headers):
            current_node = headers[section_index][0]
            current_level = current_node.level if isinstance(current_node, HeadingNode) else 1
            
            for i in range(section_index + 1, len(headers)):
                next_node = headers[i][0]
                next_level = next_node.level if isinstance(next_node, HeadingNode) else 1
                
                # If next header is at same or higher level, that's our end
                if next_level <= current_level:
                    return headers[i][2]
        
        # Otherwise, section goes to end of document
        return sum(1 for _ in document.root.walk())
    
    def _create_sections(self, 
                        matched_sections: Dict[str, Tuple[Node, str, int, int]], 
                        document: Document) -> Dict[str, Section]:
        """Create Section objects from matches."""
        sections = {}
        
        for section_name, (node, title, start_pos, end_pos) in matched_sections.items():
            # Create section node containing all content in range
            section_node = SectionNode(section_name=section_name)
            
            # Find all nodes in position range
            position = 0
            for n in document.root.walk():
                if start_pos <= position < end_pos:
                    # Clone node and add to section
                    # (In real implementation, would properly handle node hierarchy)
                    section_node.add_child(n)
                position += 1
            
            # Parse section name to extract part and item identifiers
            part, item = Section.parse_section_name(section_name)

            # Create Section object
            section = Section(
                name=section_name,
                title=title,
                node=section_node,
                start_offset=start_pos,
                end_offset=end_pos,
                confidence=0.7,  # Pattern-based detection = moderate confidence
                detection_method='pattern',  # Method: regex pattern matching
                part=part,
                item=item
            )
            
            sections[section_name] = section
        
        return sections