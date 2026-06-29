"""
Section extraction from documents.
"""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple

from edgar.documents.document import Document, Section
from edgar.documents.nodes import HeadingNode, Node, SectionNode
from edgar.documents.utils.toc_analyzer import find_toc_boundaries
from edgar.documents.form_schema import get_form_schema

logger = logging.getLogger(__name__)


class SectionExtractor:
    """
    Extracts logical sections from documents.

    Identifies document sections like:
    - Business Overview (Item 1)
    - Risk Factors (Item 1A)
    - MD&A (Item 7)
    - Financial Statements (Item 8)
    """

    # Per-form section/title vocabulary. The data now lives on each FormSchema
    # (the single home of form knowledge — edgartools-llmp.2 / D2); this is a
    # derived back-compat projection keyed exactly as before. 424B* variants are
    # mapped to the '424B' key by extract(). A golden parity test
    # (tests/test_section_patterns_schema_parity.py) guards against any drift.
    SECTION_PATTERNS = {
        form: get_form_schema(form).section_patterns
        for form in ('10-K', '10-Q', '20-F', '8-K', '424B', 'S-1', 'DEF 14A', 'PRE 14A')
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
        # Map 424B variants to the common '424B' pattern key
        pattern_key = form
        if form and form.startswith('424B'):
            pattern_key = '424B'
        if not form or pattern_key not in self.SECTION_PATTERNS:
            return {}  # No filing type or unsupported form = no section detection

        # Get patterns for filing type
        patterns = self.SECTION_PATTERNS.get(pattern_key, {})
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

    def _is_bold(self, node: Node) -> bool:
        """
        Check if node has bold styling.

        Args:
            node: Node to check for bold styling

        Returns:
            True if node has bold font-weight (>= 700), False otherwise
        """
        if not hasattr(node, 'style') or not node.style:
            return False

        fw = node.style.font_weight
        if not fw:
            return False

        # Check for string values
        if fw in ['bold', '700']:
            return True

        # Handle numeric font-weight values
        try:
            if int(fw) >= 700:
                return True
        except (ValueError, TypeError):
            pass

        return False

    @staticmethod
    def _looks_like_section_header(text: str) -> bool:
        """
        Check if bold paragraph text looks like a filing section header.

        Filters out non-header bold text (e.g., "February 2026 Distribution")
        that would otherwise pollute the headers list and cause narrow section
        boundaries.

        Matches: Item X.XX, SIGNATURES, PART I/II, EXHIBITS, FINANCIAL STATEMENTS
        """
        stripped = text.strip()
        if not stripped or len(stripped) > 300:
            return False
        return bool(re.match(
            r'^\s*(?:Item|ITEM)\s+\d'
            r'|^\s*SIGNATURE'
            r'|^\s*PART\s+[IV]'
            r'|^\s*EXHIBIT'
            r'|^\s*FINANCIAL\s+STATEMENTS'
            r'|^\s*FORWARD[\s-]LOOKING'
            r'|^\s*RISK\s+FACTORS'
            r'|^\s*(?:TABLE\s+OF\s+CONTENTS|INDEX)',
            stripped, re.IGNORECASE
        ))

    def _is_main_section_header(self, text: str) -> bool:
        """
        Check if header text looks like a main section header vs a cross-reference.

        Main section headers are typically:
        - All uppercase: "ITEM 4. INFORMATION ON THE COMPANY"
        - Without subsection paths
        - Short and standalone

        Cross-references are typically:
        - Mixed case: "Item 4. Information on the Company"
        - Include subsection paths: "- C. Organizational Structure"
        - Part of a sentence: "See Item 4..." or "...in this annual report"

        Args:
            text: Header text to check

        Returns:
            True if this appears to be a main section header, False if likely a cross-reference
        """
        if not text:
            return False

        text = text.strip()

        # Check if the ITEM part is uppercase (main headers are usually all caps)
        # Match "ITEM X" at the start
        item_match = re.match(r'^(ITEM|Item|item)\s+\d+', text)
        if item_match:
            item_part = item_match.group(1)
            # Main headers have uppercase ITEM
            if item_part == 'ITEM':
                # Check for subsection paths even in uppercase headers
                # e.g., "ITEM 4. INFORMATION ON THE COMPANY - A. HISTORY"
                if re.search(r'[\s\n]+-\s*[A-Z]\.', text):
                    return False
                return True

        # Check for subsection path indicators (cross-references)
        # e.g., "Item 4. Information on the Company - C. Organizational Structure"
        # Also catches paths after newlines like "Item 4...\n- B. Business Overview"
        if re.search(r'[\s\n]+-\s*[A-Z]\.', text):
            return False

        # Check for sentence context indicators (cross-references embedded in text)
        # e.g., 'See "Item 4...' or '...in this annual report'
        lower = text.lower()
        if 'see ' in lower or 'in this' in lower or 'described in' in lower:
            return False

        # Default: assume it could be a main header
        return True

    def _is_likely_toc_entry(self, node: Node, text: str, toc_start: int, toc_end: int, html_content: str) -> bool:
        """
        Check if a header is likely a Table of Contents entry rather than an actual section.

        Uses multiple heuristics:
        1. Check if the text appears within the TOC region of the HTML
        2. Check for page number pattern at end of text/context
        3. Prefer uppercase section headers over mixed case

        Args:
            node: The header node
            text: The header text
            toc_start: Start position of TOC region in HTML
            toc_end: End position of TOC region in HTML
            html_content: Full HTML content

        Returns:
            True if this appears to be a TOC entry, False otherwise
        """
        if not text or toc_start <= 0 or toc_end <= toc_start:
            return False

        # Extract the Item pattern from the text to search for in HTML
        # Use just "Item X." pattern since full text may be split across table cells
        text_stripped = text.strip()
        item_match = re.match(r'^(Item\s+\d+[A-Z]?\.?)', text_stripped, re.IGNORECASE)
        if item_match:
            text_snippet = item_match.group(1)
        else:
            text_snippet = text_stripped[:30]

        if not text_snippet:
            return False

        # Find where this text appears in the HTML
        # For Item patterns, we need to handle HTML entities like &#160; (non-breaking space)
        text_pos = html_content.find(text_snippet)
        if text_pos == -1:
            # Try case-insensitive search
            text_pos = html_content.lower().find(text_snippet.lower())

        # If text is found within TOC region, it's likely a TOC entry
        if text_pos > 0 and toc_start <= text_pos <= toc_end:
            logger.debug(f"Text '{text_snippet}' found at {text_pos}, within TOC region {toc_start}-{toc_end}")

            # Additional check: TOC entries typically have mixed case "Item"
            # while actual sections have uppercase "ITEM"
            # Only skip if it's mixed case (likely TOC) and we might find uppercase later
            if re.match(r'^Item\s+\d', text) and not re.match(r'^ITEM\s+\d', text):
                logger.debug(f"Skipping mixed-case TOC entry: '{text[:50]}'")
                return True

            # Also check if followed by a page number pattern in the same table row
            # TOC entries look like "Item 1. Business 4" where 4 is the page
            # Get some context after the match
            context_end = min(text_pos + 200, len(html_content))
            context = html_content[text_pos:context_end]

            # Look for page number at end of a table cell (common TOC pattern)
            if re.search(r'>\s*\d{1,3}\s*<', context):
                logger.debug(f"Skipping TOC entry with page number pattern: '{text[:50]}'")
                return True
        else:
            logger.debug(f"Text '{text_snippet}' at {text_pos}, outside TOC region {toc_start}-{toc_end}")

        return False

    def _find_actual_section_after_toc(
        self,
        section_name: str,
        section_patterns: List[Tuple[str, str]],
        html_content: str,
        toc_end: int,
        document: Document
    ) -> Optional[Tuple[Node, str, int, int]]:
        """
        Search HTML directly for actual section header after the TOC region.

        When header detection only finds TOC entries, this method searches the HTML
        for the actual section header (typically uppercase like "ITEM 1.") that
        appears after the TOC.

        Args:
            section_name: Name of the section (e.g., 'business')
            section_patterns: List of (pattern, title) tuples for this section
            html_content: Full HTML content
            toc_end: End position of TOC region
            document: Document object

        Returns:
            Tuple of (node, title, start_offset, end_offset) if found, None otherwise
        """
        # Search in HTML after TOC region
        search_region = html_content[toc_end:]

        # Build search pattern based on section type
        # For 10-K Item sections, we look for the uppercase ITEM pattern
        # Note: In HTML, "ITEM 1." and "BUSINESS." may be in separate table cells
        if section_name == 'business':
            # Look for ITEM 1 with HTML entity for non-breaking space
            search_pattern = r'ITEM[\s&#;0-9xnbsp]+1\.'
        elif section_name == 'risk_factors':
            search_pattern = r'ITEM[\s&#;0-9xnbsp]+1A\.'
        elif section_name == 'properties':
            search_pattern = r'ITEM[\s&#;0-9xnbsp]+2\.'
        elif section_name == 'legal_proceedings':
            search_pattern = r'ITEM[\s&#;0-9xnbsp]+3\.'
        elif section_name == 'mda':
            search_pattern = r'ITEM[\s&#;0-9xnbsp]+7\.'
        elif section_name == 'market_risk':
            search_pattern = r'ITEM[\s&#;0-9xnbsp]+7A\.'
        elif section_name == 'financial_statements':
            search_pattern = r'ITEM[\s&#;0-9xnbsp]+8\.'
        elif section_name == 'controls_procedures':
            search_pattern = r'ITEM[\s&#;0-9xnbsp]+9A\.'
        else:
            # Generic fallback - try the first pattern
            if not section_patterns:
                return None
            pattern, _ = section_patterns[0]
            uppercase_pattern = pattern.replace('(Item|ITEM)', 'ITEM').replace('^', '')
            search_pattern = uppercase_pattern.replace(r'\s+', r'[\s&#;0-9]+')

        # First try case-sensitive match (preferred - matches actual headers)
        match = re.search(search_pattern, search_region)
        if not match:
            # Fallback to case-insensitive for edge cases
            match = re.search(search_pattern, search_region, re.IGNORECASE)
        if match:
            # Found the actual section header after TOC
            html_position = toc_end + match.start()
            logger.debug(f"Found actual section '{section_name}' at HTML position {html_position}")

            # Get title from patterns
            title = section_patterns[0][1] if section_patterns else section_name

            # Extract section text from this position
            section_text = self._extract_section_text_from_html(
                html_content, html_position, section_name
            )

            if section_text and len(section_text) > 100:  # Must have substantial content
                # Create a SectionNode with the extracted text stored in metadata
                section_node = SectionNode(section_name=section_name)
                # Store the extracted text so _create_sections can use it directly
                section_node.set_metadata('html_extracted_text', section_text)

                # Return the section info with special marker positions
                # Use negative positions to signal this is an HTML-extracted section
                return (section_node, title, -1, -1)

        return None

    def _extract_section_text_from_html(self, html_content: str, start_pos: int, section_name: str) -> str:
        """
        Extract section text from HTML starting at given position.

        Finds the end of the section by looking for the next major section header
        (ITEM X, PART X, SIGNATURES, etc.)

        Args:
            html_content: Full HTML content
            start_pos: Starting position in HTML
            section_name: Name of current section

        Returns:
            Extracted section text
        """
        from lxml import html as lxml_html

        # Find the end of this section (next ITEM or PART header)
        search_start = start_pos + 100  # Skip past current header
        end_patterns = [
            r'ITEM\s*&#160;\s*\d+[A-Z]?\.?',  # ITEM with HTML entity
            r'ITEM\s+\d+[A-Z]?\.?',  # Regular ITEM
            r'PART\s+[IVX]+',  # PART headers
            r'SIGNATURES?\s*<',  # Signatures section (followed by HTML tag)
        ]

        end_pos = len(html_content)
        for pattern in end_patterns:
            match = re.search(pattern, html_content[search_start:], re.IGNORECASE)
            if match:
                candidate_end = search_start + match.start()
                if candidate_end < end_pos:
                    end_pos = candidate_end

        # Extract HTML between start and end
        section_html = html_content[start_pos:end_pos]

        # Parse and extract text
        try:
            # Wrap in a div to ensure valid HTML
            wrapped = f'<div>{section_html}</div>'
            tree = lxml_html.fromstring(wrapped)
            text = tree.text_content()

            # Clean up the text
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        except Exception as e:
            logger.debug(f"Failed to extract section text: {e}")
            return ""

    def _find_section_headers(self, document: Document) -> List[Tuple[Node, str, int]]:
        """
        Find all potential section headers.

        Searches for section headers using multiple strategies:
        1. HeadingNode objects (semantic HTML headings)
        2. SectionNode objects with embedded headings
        3. Bold ParagraphNode objects (fallback for filings without semantic headings)
        4. TableNode cells (fallback for filings using table-based layouts)
        5. Plain text ParagraphNode objects (final fallback for filings with no styling)

        Returns:
            List of tuples: (node, text, position)
        """
        headers = []

        # Build a node→position map once so per-node lookups are O(1) instead of
        # O(N) full-tree walks — avoids O(M·N) cost when many candidate nodes exist.
        _pos_map: dict = {}
        _pos = 0
        for _n in document.root.walk():
            _pos_map[id(_n)] = _pos
            _pos += 1

        def _node_position(node: Node) -> int:
            return _pos_map.get(id(node), 0)

        # Strategy 1: Find all heading nodes (most reliable)
        heading_nodes = document.root.find(lambda n: isinstance(n, HeadingNode))

        for node in heading_nodes:
            text = node.text()
            if text:
                # Get position in document
                position = _node_position(node)
                headers.append((node, text, position))

        # Strategy 2: Also check for section nodes with embedded headings
        section_nodes = document.root.find(lambda n: isinstance(n, SectionNode))
        for node in section_nodes:
            # Get first heading in section
            first_heading = node.find_first(lambda n: isinstance(n, HeadingNode))
            if first_heading:
                text = first_heading.text()
                if text:
                    position = _node_position(node)
                    headers.append((node, text, position))

        # Strategy 3: Fallback to bold ParagraphNode objects
        # Many 8-K filings (55%) use bold paragraphs instead of semantic headings
        # Only run if no COMPLETE Item headers found yet
        # A complete header has title text after the Item number (e.g., "Item 3. Key Information")
        # An incomplete header is just "Item 3." without title - common in 20-F headings
        def is_complete_item_header(text):
            """Check if header has title text after Item number."""
            match = re.match(r'^(Item|ITEM)\s+\d+[A-Za-z]?\.?\s*[-–—.]?\s*(.+)?$', text.strip(), re.IGNORECASE)
            if match:
                title = match.group(2)
                # Must have substantive title text (not just punctuation or whitespace)
                return title and len(title.strip()) > 3
            return False

        has_complete_item_headers = any(is_complete_item_header(text) for _, text, _ in headers)
        if not has_complete_item_headers:
            from edgar.documents.nodes import ParagraphNode
            paragraph_nodes = document.root.find(lambda n: isinstance(n, ParagraphNode))

            for node in paragraph_nodes:
                if self._is_bold(node):
                    text = node.text()
                    if text and self._looks_like_section_header(text):
                        position = _node_position(node)
                        headers.append((node, text, position))

        # Strategy 3b: ParagraphNodes with bold *children* that read as section headers.
        #
        # Some filings render section headings as a ParagraphNode whose *child*
        # TextNodes carry bold weight (fw=700) but whose own style is unstyled
        # (fw=None).  Strategy 3 misses these because _is_bold() checks the paragraph
        # node itself, not its children.  Strategy 1 only captures them when a
        # HeadingNode child is present.  This sub-strategy fills the gap.
        #
        # For 10-K: catches Part III "incorporated by reference" stubs where Items
        # 11-14 have bold-child paragraph headers (GH #880 / edgartools-01x4).
        #
        # For 8-K: catches the SIGNATURES block, which Workiva renders as a
        # ParagraphNode with an unstyled wrapper and a bold-child TextNode
        # (font-weight:700 on the <span>).  Without this, the last 8-K item
        # over-extends into the signature block (edgartools-papt, GH #879).
        # The `_looks_like_section_header` guard already restricts candidates to
        # structural headers (Item, SIGNATURES, PART, EXHIBIT, ...) so false
        # positives from stray bold text cannot occur.
        #
        # Other forms (10-Q, S-1, 424B) are excluded: their stray bold paragraphs
        # would produce unwanted boundaries.
        # Deduplicates against positions already captured.
        if self.form in ('10-K', '8-K'):
            existing_positions = {pos for _, _, pos in headers}
            from edgar.documents.nodes import ParagraphNode, TextNode as _TextNode

            def _has_bold_descendant(n) -> bool:
                for child in (getattr(n, 'children', None) or []):
                    if isinstance(child, _TextNode) and self._is_bold(child):
                        return True
                    if _has_bold_descendant(child):
                        return True
                return False

            for node in document.root.find(lambda n: isinstance(n, ParagraphNode)):
                text = node.text()
                if not text:
                    continue
                if not self._looks_like_section_header(text):
                    continue
                position = _node_position(node)
                if position in existing_positions:
                    continue  # already captured (e.g. via HeadingNode child in Strategy 1)
                # Recurse into nested descendants — a filer may wrap the bold
                # "ITEM 11." text in a nested inline element, not a direct child.
                if _has_bold_descendant(node):
                    headers.append((node, text.strip(), position))
                    existing_positions.add(position)

        # Strategy 4: Fallback to table cells with Item patterns
        # Many 8-K filings use tables for layout with Items in table cells
        # Check again after Strategy 3
        has_item_headers = any(re.search(r'Item\s+\d', text, re.IGNORECASE) for _, text, _ in headers)
        if not has_item_headers:
            from edgar.documents.table_nodes import TableNode
            table_nodes = document.root.find(lambda n: isinstance(n, TableNode))

            for table in table_nodes:
                # Look through table rows for Items
                for row in table.rows:
                    # Check each cell for Item pattern
                    row_text_parts = []
                    for cell in row.cells:
                        cell_text = cell.text().strip()
                        if cell_text:
                            row_text_parts.append(cell_text)

                    # Combine cell texts (Items often split across cells)
                    row_text = ' '.join(row_text_parts)

                    # Check if this row contains an Item pattern
                    if re.match(r'^\s*Item\s+\d', row_text, re.IGNORECASE):
                        position = _node_position(table)
                        headers.append((table, row_text, position))
                        # Only take the first Item from each table to avoid duplicates
                        break

        # Strategy 5: Final fallback to ANY paragraph with Item pattern (plain text)
        # For filings that use no bold styling, no headings, and no tables
        # This is the last resort - check all paragraphs for Item patterns
        has_item_headers = any(re.search(r'Item\s+\d', text, re.IGNORECASE) for _, text, _ in headers)
        if not has_item_headers:
            from edgar.documents.nodes import ParagraphNode
            paragraph_nodes = document.root.find(lambda n: isinstance(n, ParagraphNode))

            for node in paragraph_nodes:
                text = node.text()
                # Look for Item pattern at start of paragraph (first 100 chars)
                # This catches plain text Items without any styling
                if text and len(text) < 500:  # Reasonable header length
                    text_start = text[:100].strip()
                    # Match Item X.XX at the start
                    if re.match(r'^\s*Item\s+\d', text_start, re.IGNORECASE):
                        position = _node_position(node)
                        # Use the full paragraph text for matching
                        headers.append((node, text.strip(), position))

        # Strategy 5b: SIGNATURES terminal header for 8-K (and 8-K/A).
        #
        # 8-Ks end with a SIGNATURES block that bounds the last item.  The preceding
        # strategies only pick up the block when the heading is bold (Strategy 3 /
        # Strategy 3b). Many filers (e.g. JPMorgan, Workiva-processed filings) render
        # "SIGNATURES" or "SIGNATURE" as plain text with underline styling instead of
        # bold, so those strategies miss it.  This step scans every ParagraphNode for
        # a short text that matches the structural pattern (only "SIGNATURES?" passes
        # `_looks_like_section_header`) and inserts it as a header when not already
        # present.  Runs after all other strategies so it deduplicates automatically.
        # Scoped to 8-K because no other registered form needs this (10-K, 10-Q,
        # 20-F all use the TOC/anchor path; S-1/424B are title-based).
        # (edgartools-papt, GH #879)
        if self.form in ('8-K', '8-K/A'):
            has_sig_header = any(
                re.match(r'^\s*SIGNATURES?\s*$', text, re.IGNORECASE)
                for _, text, _ in headers
            )
            if not has_sig_header:
                from edgar.documents.nodes import ParagraphNode
                existing_positions = {pos for _, _, pos in headers}
                for node in document.root.find(lambda n: isinstance(n, ParagraphNode)):
                    text = node.text()
                    if not text:
                        continue
                    stripped = text.strip()
                    # Only match a bare "SIGNATURES" or "SIGNATURE" line — not
                    # longer paragraphs that merely contain the word.
                    if not re.match(r'^\s*SIGNATURES?\s*$', stripped, re.IGNORECASE):
                        continue
                    position = _node_position(node)
                    if position in existing_positions:
                        continue
                    headers.append((node, stripped, position))
                    existing_positions.add(position)
                    break  # one SIGNATURES header is enough

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
        """
        Match headers to section patterns.

        Collects all candidate headers for each section and prefers main section headers
        (uppercase like "ITEM 4") over cross-references (mixed case like "Item 4...").

        Skips any matches found within the Table of Contents region to avoid
        matching TOC entries instead of actual section headers.
        """
        matched_sections = {}
        used_headers = set()

        # Detect TOC boundaries to skip TOC entries
        # This prevents matching "Item 1. Business 4" (TOC) instead of "ITEM 1. BUSINESS" (actual)
        toc_start, toc_end = 0, 0
        html_content = getattr(document.metadata, 'original_html', None)
        if html_content:
            toc_start, toc_end = find_toc_boundaries(html_content)
            if toc_start > 0 and toc_end > toc_start:
                logger.debug(f"TOC region detected: {toc_start} - {toc_end} ({toc_end - toc_start} chars)")

        # Precompute the header indices that start a *recognized* section for this
        # form. A section ends at the next such boundary header. For Item-based
        # forms these are the "Item N" headers; for title-based forms (e.g. 424B:
        # "Use of Proceeds", "Dilution", "Underwriting") they are the prospectus
        # titles. Passing this set into _find_section_end lets title-based sections
        # close on their own headings, which the generic _looks_like_section_header
        # allowlist alone would miss — so the GH #871 sub-heading fix does not bleed
        # one section into the next on prospectuses.
        boundary_indices = set()
        for _section_patterns in patterns.values():
            for _pattern, _ in _section_patterns:
                for _i, (_node, _text, _position) in enumerate(headers):
                    if re.match(_pattern, _text.strip(), re.IGNORECASE):
                        boundary_indices.add(_i)

        # Try to match each pattern
        for section_name, section_patterns in patterns.items():
            # Collect all candidate headers for this section
            candidates = []

            for pattern, title in section_patterns:
                for i, (node, text, position) in enumerate(headers):
                    if i in used_headers:
                        continue

                    # For 10-Q part-qualified patterns, validate against part context
                    if part_context and section_name.startswith('part_'):
                        _PART_PREFIX_MAP = {
                            'part_i_': 'Part I',
                            'part_ii_': 'Part II',
                            'part_iii_': 'Part III',
                            'part_iv_': 'Part IV',
                        }
                        expected_part = next(
                            (v for k, v in _PART_PREFIX_MAP.items() if section_name.startswith(k)),
                            'Part II',
                        )
                        actual_part = part_context.get(i)
                        # Skip if part context doesn't match expected part
                        if actual_part and actual_part != expected_part:
                            continue

                    # Try to match pattern
                    if re.match(pattern, text.strip(), re.IGNORECASE):
                        # Find end position (next section or end of document)
                        end_position = self._find_section_end(i, headers, document, boundary_indices)

                        # For 10-Q, prefix with Part I or Part II in title
                        final_title = title
                        if part_context and i in part_context:
                            final_title = f"{part_context[i]} - {title}"

                        # Check if this is a main header vs cross-reference
                        is_main = self._is_main_section_header(text)

                        # Check if this is inside the TOC region
                        is_toc_entry = False
                        if toc_start > 0 and toc_end > 0:
                            is_toc_entry = self._is_likely_toc_entry(node, text, toc_start, toc_end, html_content)

                        # Store candidate with metadata
                        candidates.append({
                            'index': i,
                            'node': node,
                            'text': text,
                            'position': position,
                            'end_position': end_position,
                            'title': final_title,
                            'is_main': is_main,
                            'is_toc_entry': is_toc_entry,
                            'content_size': end_position - position
                        })

            # Choose the best candidate if any were found
            if candidates:
                # Priority order for selection:
                # 1. Non-TOC entries (actual section headers)
                # 2. Main headers (uppercase) over cross-references
                # 3. Most content size

                # First, prefer non-TOC entries over TOC entries
                non_toc_candidates = [c for c in candidates if not c.get('is_toc_entry', False)]
                if non_toc_candidates:
                    # Use non-TOC candidates for further selection
                    selection_pool = non_toc_candidates
                    logger.debug(f"Found {len(non_toc_candidates)} non-TOC candidates for {section_name}")
                else:
                    # All candidates are TOC entries - try to find actual section in HTML
                    logger.info(f"All {len(candidates)} candidates for {section_name} are TOC entries")
                    if html_content and toc_end > 0:
                        logger.info(f"Searching HTML after TOC (position {toc_end}) for {section_name}")
                        # Search for uppercase section header after TOC region
                        actual_section = self._find_actual_section_after_toc(
                            section_name, section_patterns, html_content, toc_end, document
                        )
                        if actual_section:
                            logger.info(f"Found actual section for {section_name} after TOC region")
                            matched_sections[section_name] = actual_section
                            continue  # Skip the normal candidate selection
                        else:
                            logger.info(f"Could not find actual section for {section_name} in HTML")
                    else:
                        logger.info(f"No HTML content or TOC end for {section_name}")

                    # Fall back to TOC entries if no actual section found
                    selection_pool = candidates
                    logger.info(f"Using TOC entries as fallback for {section_name}")

                # Among the selection pool, prefer main headers (uppercase)
                main_headers = [c for c in selection_pool if c['is_main']]
                if main_headers:
                    # Among main headers, pick the one with the most content
                    best = max(main_headers, key=lambda c: c['content_size'])
                else:
                    # No main headers found, fall back to the one with most content
                    best = max(selection_pool, key=lambda c: c['content_size'])

                # Store the matched section
                section_key = section_name
                matched_sections[section_key] = (
                    best['node'],
                    best['title'],
                    best['position'],
                    best['end_position']
                )
                used_headers.add(best['index'])

        return matched_sections

    def _find_section_end(self,
                         section_index: int,
                         headers: List[Tuple[Node, str, int]],
                         document: Document,
                         boundary_indices: Optional[Set[int]] = None) -> int:
        """Find where section ends."""
        # Next section starts where next header at same or higher level begins
        if section_index + 1 < len(headers):
            current_node = headers[section_index][0]
            current_level = current_node.level if isinstance(current_node, HeadingNode) else 1

            for i in range(section_index + 1, len(headers)):
                next_node = headers[i][0]
                next_text = headers[i][1]
                next_level = next_node.level if isinstance(next_node, HeadingNode) else 1

                # Only an actual section boundary may close a section. Internal
                # sub-headings are HeadingNodes too — e.g. a bold "Adoption of Fiscal
                # Year 2027 Variable Compensation Plan" inside an 8-K Item 5.02 — and
                # must NOT terminate the item early and orphan the body paragraphs
                # that follow it (GH #871). A header counts as a boundary if it starts
                # one of this form's recognized sections (boundary_indices — covers
                # title-based forms like 424B whose section names aren't in the generic
                # allowlist) or matches the generic structural-header allowlist
                # (Item/PART/SIGNATURE/EXHIBIT/... — covers terminators such as
                # SIGNATURES that aren't themselves extracted sections).
                is_boundary = (
                    (boundary_indices is not None and i in boundary_indices)
                    or self._looks_like_section_header(next_text)
                )
                if not is_boundary:
                    continue

                # If next header is at same or higher level, that's our end
                if next_level <= current_level:
                    return headers[i][2]

        # Otherwise, section goes to end of document
        return sum(1 for _ in document.root.walk())

    def _create_sections(self,
                        matched_sections: Dict[str, Tuple[Node, str, int, int]],
                        document: Document) -> Dict[str, Section]:
        """Create Section objects from matches."""
        from edgar.documents.nodes import TextNode

        sections = {}

        for section_name, (node, title, start_pos, end_pos) in matched_sections.items():
            # Check if this is an HTML-extracted section (marked by start_pos == -1)
            html_extracted_text = node.get_metadata('html_extracted_text') if hasattr(node, 'get_metadata') else None

            if start_pos == -1 and html_extracted_text:
                # Use the pre-extracted text from HTML parsing
                section_node = node  # Already a SectionNode with metadata
                # Add a TextNode with the extracted content
                text_node = TextNode(content=html_extracted_text)
                section_node.add_child(text_node)
                detection_method = 'html_fallback'
                confidence = 0.6  # Lower confidence for HTML fallback
            else:
                # Normal path: Create section node containing all content in range
                section_node = SectionNode(section_name=section_name)

                # Find all nodes in position range - only add top-level nodes
                # (nodes whose parent is outside the range)
                # First collect all nodes in range
                nodes_in_range = []
                position = 0
                for n in document.root.walk():
                    if start_pos <= position < end_pos:
                        nodes_in_range.append(n)
                    position += 1

                # Now add only top-level nodes (nodes whose parent is not in the range)
                # This prevents adding both a parent and its children as direct section children
                for n in nodes_in_range:
                    if n.parent not in nodes_in_range:
                        section_node.add_child(n)

                # Clear text cache to ensure fresh text generation
                # (nodes may have stale cached text from earlier processing)
                if hasattr(section_node, 'clear_text_cache'):
                    section_node.clear_text_cache()

                detection_method = 'pattern'
                confidence = 0.7

            # Parse section name to extract part and item identifiers
            part, item = Section.parse_section_name(section_name)

            # Create Section object
            section = Section(
                name=section_name,
                title=title,
                node=section_node,
                start_offset=start_pos,
                end_offset=end_pos,
                confidence=confidence,
                detection_method=detection_method,
                part=part,
                item=item
            )

            sections[section_name] = section

        return sections
