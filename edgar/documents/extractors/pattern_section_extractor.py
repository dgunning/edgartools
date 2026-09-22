"""
Section extraction from documents.
"""

import copy
import logging
import re
from typing import Dict, List, Optional, Set, Tuple

from edgar.documents.document import Document, Section
from edgar.documents.nodes import HeadingNode, Node, SectionNode
from edgar.documents.utils.toc_analyzer import find_toc_boundaries
from edgar.documents.form_schema import get_form_schema

logger = logging.getLogger(__name__)

# A header that *begins* with an item number, capturing the number. Anchored on
# purpose: the gates below used to ask whether the string "Item 5" appeared
# anywhere in a header, which counted prose cross-references ("Please refer to
# Item 6.E, Directors, Senior Management and Employees") as evidence that the
# filing's item structure had been found.
_ITEM_HEADER_START = re.compile(r'^\s*item\s+(\d+(?:\.\d+)?[A-Za-z]?)\b', re.IGNORECASE)

_WHITESPACE_RUN = re.compile(r'\s+')

# A Part boundary — "PART II", "PART II. OTHER INFORMATION", "Part I - Financial
# Information". Anchored, and the numeral must end at a word boundary so
# "Participation in the plan" is not read as a part header.
_PART_HEADER = re.compile(r'^\s*PART\s+(I|II|III|IV|V)\b', re.IGNORECASE)

# A bare SIGNATURES line, which terminates the last item of a report. Requires
# the whole paragraph to be that one word — "Signatures of the undersigned
# officers appear below" is prose, not a boundary. Same test Strategy 5b uses.
_SIGNATURES_HEADER = re.compile(r'^\s*SIGNATURES?\s*$', re.IGNORECASE)

# An item's own SUB-header: an item number, one or more parenthesized
# sub-designations, and nothing else — "Item 14(a)(1):", "Item 14 (a)(2):".
# Filings that itemize under Regulation S-K's lettered sub-paragraphs write
# these inside the item they belong to, so they mark a subdivision and never the
# start of a new section.
#
# The whole string must be consumed, which is what separates a sub-header from a
# designated item header: "ITEM 9A(T). CONTROLS AND PROCEDURES" carries a title
# and so fails this test and stays a boundary. A bare, undesignated "Item 3." —
# the shape 20-F headings commonly use — has no parenthesized group and likewise
# stays a boundary.
_ITEM_SUBHEADER = re.compile(
    r'^\s*(?:Item|ITEM)\s+\d+[A-Za-z]?\s*(?:\([A-Za-z0-9]{1,3}\)\s*)+[.:;\-–—]?\s*$',
    re.IGNORECASE
)


def _normalize_header_text(text: str) -> str:
    """Collapse a header's internal whitespace runs to single spaces.

    Header text arrives carrying the source HTML's line wrapping — a table cell
    written as::

        <td>ITEM 5. OPERATING
        AND FINANCIAL REVIEW AND PROSPECTS</td>

    yields ``'ITEM\\n5. OPERATING\\nAND FINANCIAL REVIEW AND PROSPECTS'``. In HTML
    that newline is just whitespace, but the section patterns join words with
    ``.*``, which does not cross a newline (they are compiled without DOTALL).
    So a wrapped header matched or missed depending on which metacharacter its
    pattern happened to use: ``Information\\s+on\\s+the\\s+Company`` matched
    because ``\\s`` covers ``\\n``, while ``Operating.*Financial\\s+Review`` did
    not. On the 2010 20-F ``0001144204-10-017467`` that silently cost Items 5,
    6, 11, 12, 15 and 16D-16F, and on ``0001062993-16-008650`` Items 6 and 11 —
    lookups that returned text only via the legacy ChunkedDocument fallback
    (edgartools-dt1f.1).
    """
    return _WHITESPACE_RUN.sub(' ', text).strip()


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
        return self._create_sections(sections, document, form)

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

    # A filing's item structure counts as "already found" — and the fallback
    # strategies below stay off — once the headers seen so far name at least this
    # fraction of the items the form defines.
    #
    # Half is not a round number picked for tidiness; it is the middle of a gap
    # that exists in every form's measured distribution over the parity corpus
    # (tests/fixtures/parser_corpus). Sorting each form's filings by the share of
    # canonical items its heading nodes name, the observed values fall into two
    # clusters with nothing between them:
    #
    #     20-F   10%  |  61% 84% 90% 90%
    #     10-K   17% 22% 39% 48%  |  65% 78% 83% 87% 96% 100%
    #     10-Q   43%  |  71% 86% 100%
    #
    # Filings on the left are ones where heading detection produced a handful of
    # stray item-ish headings and nothing resembling the form's structure; on the
    # right it found the structure. A cut anywhere in 49-60% separates them
    # identically, so the exact value carries no weight — the bimodality does.
    _ITEM_COVERAGE_FLOOR = 0.5

    @staticmethod
    def _has_page_number_suffix(text: str) -> bool:
        """Does this header end in a bare page number, the way a TOC row does?

        "ITEM 1. IDENTITY OF DIRECTORS, SENIOR MANAGEMENT AND ADVISERS 5" is a
        table-of-contents row; the body header is the same words without the 5.
        Used only to DEMOTE a candidate when a cleaner one exists for the same
        section, because the number is suggestive rather than conclusive — some
        filings do carry a stray trailing digit on a real header, and a section
        whose only candidate is page-numbered is still better found than not.

        `_is_likely_toc_entry` answers the same question from HTML offsets and is
        the primary guard, but it needs `find_toc_boundaries` to have located a
        TOC; on 0001144204-10-017467 it locates none, so nothing marked that
        filing's TOC rows at all.

        The leading item number is stripped before testing so that a bare "ITEM
        5" header does not read its own number as a page number.
        """
        remainder = _ITEM_HEADER_START.sub('', text.strip())
        return bool(re.search(r'\S\s+\d{1,3}$', remainder))

    @staticmethod
    def _is_complete_item_header(text: str) -> bool:
        """Does this header carry title text after the item number?

        "Item 3. Key Information" does; a bare "Item 3." does not. 20-F filers
        commonly emit the bare form as a heading and the titled form in the body,
        so a bare header is not evidence that the body header was found.
        """
        match = re.match(r'^(Item|ITEM)\s+\d+[A-Za-z]?\.?\s*[-–—.]?\s*(.+)?$', text.strip(), re.IGNORECASE)
        if match:
            title = match.group(2)
            # Must have substantive title text (not just punctuation or whitespace)
            return bool(title and len(title.strip()) > 3)
        return False

    @staticmethod
    def _item_numbers_in(headers: List[Tuple[Node, str, int]]) -> Set[str]:
        """Distinct item numbers among headers that begin with one."""
        found = set()
        for _node, text, _position in headers:
            match = _ITEM_HEADER_START.match(text)
            if match:
                found.add(match.group(1).upper())
        return found

    def _canonical_item_count(self) -> int:
        """How many distinct items this form defines.

        Returns 0 when the count is not a usable denominator, which is the case
        for 8-K and for title-based forms. An 8-K reports only the items that
        happened to occur, so a two-item 8-K is complete and a coverage ratio
        against the 33 items the form *allows* would be meaningless — the same
        reason the parity benchmark gives 8-K no coverage rate. Those forms keep
        the presence test they have always used.
        """
        if not self.form or self.form.startswith('8-K'):
            return 0
        schema = get_form_schema(self.form)
        if schema.title_based:
            return 0
        items = {schema.item_for_section_key(key) for key in schema.section_patterns}
        items.discard(None)
        return len(items)

    def _item_structure_found(self,
                              headers: List[Tuple[Node, str, int]],
                              complete_only: bool = False) -> bool:
        """Have the strategies so far found this filing's item structure?

        This is the question the fallback strategies in ``_find_section_headers``
        are gated on, and getting it wrong is expensive in both directions: answer
        yes too readily and the fallbacks that would have found the real headers
        never run; answer no too readily and every filing pays for extra tree
        walks that can only add noise.

        It used to be answered by presence — *any* header mentioning an item meant
        yes. On a 2010 20-F (0001144204-10-017467) three stray headings, one of
        them a prose cross-reference, were enough to suppress the strategies that
        find that filing's 15 real item headers, leaving four sections where
        legacy ChunkedDocument found 26. Coverage is the question that filing was
        actually failing: three items out of the thirty-one a 20-F defines is not
        an item structure.
        """
        if complete_only:
            headers = [h for h in headers if self._is_complete_item_header(h[1])]
        found = self._item_numbers_in(headers)
        if not found:
            return False
        expected = self._canonical_item_count()
        if not expected:
            return True  # No usable denominator — presence is the only test available.
        return len(found) >= expected * self._ITEM_COVERAGE_FLOOR

    def _item_structure_complete(self, headers: List[Tuple[Node, str, int]]) -> bool:
        """Has every item this form defines turned up among the candidates?

        The stricter sibling of ``_item_structure_found``, and a different
        question: that one asks whether the document parsed at all, this one asks
        whether there is anything left to look for. A strategy that can only ADD
        candidates should be gated on this, because "we have enough items" is not
        a reason to stop when the items already in hand cannot become the missing
        one — see Strategy 4, where a filer rendering one item in a table and the
        rest as headings lost that item entirely.

        Forms with no usable denominator (8-K, title-based) are never complete by
        this test, so they keep running the strategies they have always run:
        their gate was ``presence``, which is False until something is found, and
        an 8-K that has found nothing still needs the fallbacks.
        """
        expected = self._canonical_item_count()
        if not expected:
            return False
        return len(self._item_numbers_in(headers)) >= expected

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
        # Skipped once the COMPLETE Item headers found so far already amount to
        # the form's item structure — see _item_structure_found for why "found
        # one" is not the same question as "found the structure".
        # A complete header has title text after the Item number (e.g., "Item 3. Key Information")
        # An incomplete header is just "Item 3." without title - common in 20-F headings
        if not self._item_structure_found(headers, complete_only=True):
            from edgar.documents.nodes import ParagraphNode
            paragraph_nodes = document.root.find(lambda n: isinstance(n, ParagraphNode))

            # Positions already taken. The strategies below can now run in the
            # same pass rather than only when every earlier one came up empty, so
            # a bold "ITEM 5. OPERATING AND FINANCIAL REVIEW" paragraph is a
            # candidate for both this strategy and Strategy 5 and would otherwise
            # be appended twice.
            existing_positions = {pos for _, _, pos in headers}
            for node in paragraph_nodes:
                if self._is_bold(node):
                    text = node.text()
                    if text and self._looks_like_section_header(text):
                        position = _node_position(node)
                        if position in existing_positions:
                            continue
                        headers.append((node, text, position))
                        existing_positions.add(position)

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
        # For 10-Q: PART boundaries and the terminal SIGNATURES line, nothing
        # else. Goldman's 10-Q renders "PART II. OTHER INFORMATION" in exactly
        # this shape, and without that marker every header after it is still
        # labelled Part I by _detect_10q_parts, so the `part_ii_*` patterns
        # reject their own headers on part context and the filing resolves
        # part_i_item_1..4 and nothing else. Items 5 and 6 were found and then
        # thrown away (edgartools-dt1f.1 Defect D). SIGNATURES comes too, for the
        # same reason 8-K needs it: it is what stops the last item — Item 6,
        # Exhibits — running to the end of the document.
        #
        # Admitting the rest of the `_looks_like_section_header` vocabulary for
        # 10-Q was tried and reverted. Measured across 31 fixtures it fixed
        # Goldman's Part II but truncated four other filings, one MD&A from
        # 33,102 characters to 93, and left Goldman's own Item 6 at 16 — because
        # a bold "Exhibits" or "Item 6." inside a 10-Q body is ordinarily a
        # cross-reference, while a bold "PART II" or a bare bold "SIGNATURES" is
        # not. That is the difference the two patterns encode; it is not a
        # difference `_looks_like_section_header` can express, since 10-K needs
        # the wider vocabulary for its Part III stubs.
        #
        # S-1 and 424B stay out entirely: they are title-based forms with no
        # part structure to recover.
        # Deduplicates against positions already captured.
        if self.form in ('10-K', '8-K', '10-Q'):
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
                if self.form == '10-Q' and not (
                    _PART_HEADER.match(text) or _SIGNATURES_HEADER.match(text)
                ):
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
        #
        # Gated on COMPLETENESS rather than on _item_structure_found, which asks
        # whether half the form's items have turned up. That is the right
        # question for "did this document parse at all" and the wrong one here,
        # because a filer does not have to render every item the same way.
        # ExxonMobil's 10-Q writes six of its seven items as headings and puts
        # Item 1 in a table — so the gate was satisfied at 6/7 by the very
        # headers that could never contribute the missing one, and the strategy
        # that would have found it never ran. Part I Item 1 is the whole
        # financial-statement section, and get_item_with_part('Part I', 'Item 1')
        # fell through to id_parse_document for it (edgartools-yrrh).
        #
        # A cheaper strategy having succeeded is not evidence that an expensive
        # one has nothing to add. Same shape as the TOC-augmentation gate
        # (edgartools-dt1f), which asked whether Part III was complete before
        # running the pattern pass and so almost never ran it.
        if not self._item_structure_complete(headers):
            from edgar.documents.table_nodes import TableNode
            table_nodes = document.root.find(lambda n: isinstance(n, TableNode))
            existing_positions = {pos for _, _, pos in headers}

            for table in table_nodes:
                # Look through table rows for Items.
                #
                # Header rows are scanned as well as body rows. A filer whose
                # item headings are standalone one-row tables ("ITEM 1A." |
                # "RISK FACTORS" — Wells Fargo) has that row classified as the
                # table's *header*, leaving `rows` empty, so scanning only
                # `rows` found no items at all and the extractor fell through
                # to keyword matching, which labeled Item 15's exhibit list as
                # `financial_statements` (edgartools-4agg).
                header_cell_rows = [list(hr) for hr in (table.headers or [])]
                body_cell_rows = [list(row.cells) for row in table.rows]

                for cells in header_cell_rows + body_cell_rows:
                    # Check each cell for Item pattern
                    row_text_parts = []
                    for cell in cells:
                        cell_text = cell.text().strip()
                        if cell_text:
                            row_text_parts.append(cell_text)

                    # Combine cell texts (Items often split across cells)
                    row_text = ' '.join(row_text_parts)

                    # Check if this row contains an Item pattern
                    if re.match(r'^\s*Item\s+\d', row_text, re.IGNORECASE):
                        position = _node_position(table)
                        if position not in existing_positions:
                            headers.append((table, row_text, position))
                            existing_positions.add(position)
                        # Only take the first Item from each table to avoid duplicates
                        break

        # Strategy 5: Final fallback to ANY paragraph with Item pattern (plain text)
        # For filings that use no bold styling, no headings, and no tables
        # This is the last resort - check all paragraphs for Item patterns
        if not self._item_structure_found(headers):
            from edgar.documents.nodes import ParagraphNode
            paragraph_nodes = document.root.find(lambda n: isinstance(n, ParagraphNode))

            existing_positions = {pos for _, _, pos in headers}
            for node in paragraph_nodes:
                text = node.text()
                # Look for Item pattern at start of paragraph (first 100 chars)
                # This catches plain text Items without any styling
                if text and len(text) < 500:  # Reasonable header length
                    text_start = text[:100].strip()
                    # Match Item X.XX at the start
                    if re.match(r'^\s*Item\s+\d', text_start, re.IGNORECASE):
                        position = _node_position(node)
                        if position in existing_positions:
                            continue
                        # Use the full paragraph text for matching
                        headers.append((node, text.strip(), position))
                        existing_positions.add(position)

        # Strategy 5c: bare TextNode headers, for filings with no block structure
        # at all.
        #
        # Pre-2002 filings are preformatted text wrapped in minimal HTML, and they
        # parse to ContainerNode > TextNode with *zero* HeadingNodes and *zero*
        # ParagraphNodes. Every strategy above draws its candidates from headings,
        # sections, bold paragraphs or table cells, so on those documents the
        # header list is not merely short — there is no candidate source at all,
        # and section detection returns nothing however good the patterns are.
        # That is why these filings fell through to the legacy ChunkedDocument
        # fallback in the report classes (edgartools-3dp).
        #
        # The header is the node's FIRST LINE, not its whole text: in
        # preformatted filings a single TextNode carries the heading and the body
        # that follows it, so the untrimmed text is a thousand characters of prose
        # that `_looks_like_section_header` rejects on length alone. A title
        # wrapped across two lines is truncated by this ("...AND RESULTS" without
        # "OF OPERATIONS"), which costs nothing — the pattern match is anchored at
        # the start, and the section's title comes from the pattern table rather
        # than from the matched text.
        # NOT for 8-K/6-K, and the reason generalises: this strategy can only
        # find the items that happen to START a TextNode, so it may hand back a
        # PARTIAL header set. For the annual forms a partial set is still an
        # improvement on nothing. For current reports it is actively worse —
        # CurrentReport.__getitem__ tries the new parser first and only falls
        # through to its text-based extraction when the parser yields nothing, so
        # one detected header makes it stop at a section that runs past the item
        # it should have ended at. That is a real filing: GMAC 0001047469-05-006981
        # carries Item 4.02 at the head of one node and Item 8.01 elsewhere, and
        # asking for 4.02 returned 8.01's text as well (test_issue_l6cl_8k_items_missing).
        # Current reports already have era-appropriate text extraction; the annual
        # forms are what had nothing.
        if not self._item_structure_found(headers) and not self.form.startswith(("8-K", "6-K")):
            from edgar.documents.nodes import TextNode as _BareTextNode

            existing_positions = {pos for _, _, pos in headers}
            for node in document.root.find(lambda n: isinstance(n, _BareTextNode)):
                text = node.text()
                if not text:
                    continue
                first_line = text.strip().split("\n", 1)[0].strip()
                if not re.match(r'^Item\s+\d', first_line, re.IGNORECASE):
                    continue
                if not self._looks_like_section_header(first_line):
                    continue
                position = _node_position(node)
                if position in existing_positions:
                    continue
                headers.append((node, first_line, position))
                existing_positions.add(position)

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

        # Collapse the source's line wrapping, once, after every strategy has
        # run. See _normalize_header_text for what it costs to skip this.
        #
        # Deliberately last: the `_item_structure_found` gates above decide which
        # strategies get to run at all, and they were calibrated against raw
        # header text. Normalizing before them would change which strategies fire
        # on filings that have nothing to do with this defect; normalizing here
        # changes only what the patterns are matched against.
        headers = [
            (node, _normalize_header_text(text), position)
            for node, text, position in headers
        ]

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

    # A schema pattern that anchors on an explicit item number, e.g.
    # '^(Item|ITEM)\\s+8\\.?\\s*Financial\\s+Statements'. Matched against the
    # pattern source, not the header text, so it reflects what the schema
    # actually asserted rather than what the document happened to contain.
    _ITEM_NUMBERED_PATTERN_RE = re.compile(r'^\^?\(?(?:Item|ITEM)', re.IGNORECASE)

    @classmethod
    def _is_item_numbered_pattern(cls, pattern: str) -> bool:
        """True if this schema pattern requires an 'Item N' prefix to match."""
        return bool(cls._ITEM_NUMBERED_PATTERN_RE.match(pattern))

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
                            'is_item_numbered': self._is_item_numbered_pattern(pattern),
                            'has_page_number': self._has_page_number_suffix(text),
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

                # A header that names its item ("ITEM 8. FINANCIAL STATEMENTS")
                # identifies the section outright; a bare title ("FINANCIAL
                # STATEMENTS") only suggests it, and the same words routinely
                # head an unrelated block. Ranking by content size alone let the
                # weaker evidence win whenever it happened to span more text:
                # Wells Fargo's Item 8 is a 261-char "incorporated by reference"
                # pointer, so the "1. FINANCIAL STATEMENTS" heading inside Item
                # 15's exhibit list claimed the `financial_statements` key with
                # 42K chars of the wrong content (edgartools-4agg). Item-numbered
                # matches are therefore preferred outright, and size only breaks
                # ties within a tier.
                item_numbered = [c for c in selection_pool if c['is_item_numbered']]
                if item_numbered:
                    selection_pool = item_numbered

                # Then drop TOC rows that the HTML-offset guard above did not
                # catch, but only when a candidate without a page number is
                # available. Size alone would pick the TOC row every time: it
                # sits at the front of the filing, so the span it opens runs
                # through the whole front matter, while the body header it
                # duplicates opens the item's real (often one-line) content.
                without_page_number = [c for c in selection_pool if not c['has_page_number']]
                if without_page_number:
                    selection_pool = without_page_number

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
                # ...but an item's own sub-designated headers are not boundaries,
                # however much they look like Item headers. The 1999 10-K
                # 0000950153-99-001234 divides Item 14 with bold "Item 14(a)(1):",
                # "Item 14 (a)(2):", "Item 14 (a)(3):" markers; without this the
                # section stopped at the second of them and returned 1,189 of its
                # 16,063 characters, losing the schedules and the entire exhibit
                # index (edgartools-dt1f.1 Defect A).
                if is_boundary and _ITEM_SUBHEADER.match(next_text.strip()):
                    is_boundary = False
                if not is_boundary:
                    continue

                # A bare SIGNATURES line ends the last item whatever its level.
                # Heading level here is a heuristic score, not markup depth, so a
                # filing whose item headers land at level 1 and whose SIGNATURES
                # line lands at level 3 would otherwise run the item past the
                # signature block to the end of the document — which is what the
                # 1999 10-K does once its Item 14 sub-headers stop closing it.
                if _SIGNATURES_HEADER.match(next_text.strip()):
                    return headers[i][2]

                # If next header is at same or higher level, that's our end
                if next_level <= current_level:
                    return headers[i][2]

        # Otherwise, section goes to end of document
        return sum(1 for _ in document.root.walk())

    def _create_sections(self,
                        matched_sections: Dict[str, Tuple[Node, str, int, int]],
                        document: Document,
                        form: Optional[str] = None) -> Dict[str, Section]:
        """Create Section objects from matches."""
        from edgar.documents.nodes import TextNode
        from edgar.documents.form_schema import get_form_schema

        schema = get_form_schema(form)

        sections = {}

        # Walk the document once, and record each node's position, its original
        # parent, and how far its subtree reaches.
        #
        # The walk was previously redone per section, which is also why the
        # parent test below has to work from a snapshot: add_child() reassigns
        # child.parent, so by the time a later section asked "is my parent in my
        # range?" the answer could already have been rewritten by an earlier one.
        # Sections are created in dict order, not document order, so that made
        # the result depend on iteration order. The snapshot is taken before any
        # node is attached, so every section sees the document as parsed.
        walk = list(document.root.walk())
        positions = {id(n): i for i, n in enumerate(walk)}
        original_parent = {id(n): id(n.parent) if n.parent is not None else None
                           for n in walk}
        # reach[node] is one past the last index its subtree occupies.
        reach = {}
        for n in reversed(walk):
            end = positions[id(n)] + 1
            for child in getattr(n, 'children', None) or []:
                child_end = reach.get(id(child))
                if child_end is not None and child_end > end:
                    end = child_end
            reach[id(n)] = end

        def attach_bounded(target: Node, source: Node, limit: int) -> None:
            """Attach ``source`` to ``target``, dropping any subtree past ``limit``.

            A section's boundary is the position of the *next* item's header, but
            that header is usually nested inside a container which itself starts
            before the boundary. Attaching that container whole handed the
            section everything the container held — Wells Fargo's Item 8 is a
            261-character incorporation-by-reference pointer and came back as
            3,329 characters running through Items 9, 9A, 9B and 9C, because one
            container spanning positions 489-517 was attached to a section whose
            range ended at 492 (edgartools-llmp.6.1).

            A node whose subtree fits inside the range is attached as it is. One
            that straddles the boundary is replaced by a shallow stand-in holding
            only the children that fall inside, so the nesting the text extractor
            sees is unchanged while the out-of-range content is not carried. The
            remainder is not lost: it belongs to the next section, whose own
            range starts at this limit.
            """
            if reach[id(source)] <= limit:
                target.add_child(source)
                return

            stand_in = copy.copy(source)
            stand_in.children = []
            stand_in.parent = None
            stand_in.metadata = dict(source.metadata) if source.metadata else {}
            # copy.copy carries the source's memoised text, which described the
            # untrimmed subtree.
            if hasattr(stand_in, 'clear_text_cache'):
                stand_in._text_cache = None

            for child in getattr(source, 'children', None) or []:
                child_pos = positions.get(id(child))
                if child_pos is None or child_pos >= limit:
                    break
                attach_bounded(stand_in, child, limit)

            if stand_in.children:
                target.add_child(stand_in)

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
                nodes_in_range = walk[start_pos:end_pos]

                # Now add only top-level nodes (nodes whose parent is not in the range)
                # This prevents adding both a parent and its children as direct section children
                #
                # Membership here means identity — "is this same node object also in
                # the range". It must not go through `in` on the list: Node used to
                # be a plain @dataclass, so `==` compared field-by-field and recursed
                # through `children`, which was both quadratic (10.5s of Citigroup's
                # 18s sections stage) and wrong. Two distinct paragraphs with
                # identical text and styling compared equal, so a node whose parent
                # merely resembled an in-range node was treated as nested and
                # silently dropped — boilerplate-heavy filings are exactly where
                # identical nodes are common. Nodes compare by identity now
                # (edgartools-llmp.10), but the id() test stays: it is what this
                # means, and it reads as deliberate rather than incidental.
                ids_in_range = {id(n) for n in nodes_in_range}
                for n in nodes_in_range:
                    if original_parent[id(n)] not in ids_in_range:
                        attach_bounded(section_node, n, end_pos)

                # Clear text cache to ensure fresh text generation
                # (nodes may have stale cached text from earlier processing)
                if hasattr(section_node, 'clear_text_cache'):
                    section_node.clear_text_cache()

                detection_method = 'pattern'
                confidence = 0.7

            # Parse section name to extract part and item identifiers. Semantic
            # 10-K keys ('mda', 'business', ...) carry no item number in the key
            # string, so parse_section_name yields item=None; recover item/part
            # from the form schema's title vocabulary so these sections carry the
            # same .item/.part as part_iii_item_N-style keys (GH #891).
            part, item = Section.parse_section_name(section_name)
            if item is None:
                schema_part, schema_item = schema.resolve_section_key(section_name)
                if schema_item is not None:
                    item = schema_item
                    if part is None:
                        part = schema_part

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
