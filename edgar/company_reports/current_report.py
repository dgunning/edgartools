"""Form 8-K and 6-K current report classes."""
import re
from datetime import datetime
from functools import cached_property, partial
from typing import List, Optional

from rich import box, print
from rich.console import Group, Text
from rich.panel import Panel
from rich.table import Table

from edgar._filings import Attachments
from edgar.company_reports._base import CompanyReport
from edgar.company_reports._structures import ItemOnlyFilingStructure, extract_items_from_sections
from edgar.documents import HTMLParser, ParserConfig
from edgar.files.html import Document
from edgar.files.htmltools import ChunkedDocument, adjust_for_empty_items, chunks2df, detect_decimal_items
from edgar.richtools import repr_rich, rich_to_text

__all__ = ['CurrentReport', 'EightK', 'SixK']


def _normalize_item_number(item_str: str) -> str:
    """
    Normalize item string to standard format (e.g., '2.02').

    Handles:
    - "Item 2.02" -> "2.02"
    - "Item 2. 02" -> "2.02"  (Apple-style spacing)
    - "ITEM 2.02" -> "2.02"   (case variation)
    - "Item 2" -> "2"         (legacy single-digit)

    Args:
        item_str: Raw item string from text extraction

    Returns:
        Normalized item number string
    """
    # Remove "Item" prefix (case insensitive)
    cleaned = re.sub(r'^item\s+', '', item_str.lower().strip())

    # Remove spaces around dots: "2. 02" -> "2.02"
    cleaned = re.sub(r'\s*\.\s*', '.', cleaned)

    # Remove trailing dots: "2.02." -> "2.02"
    cleaned = cleaned.rstrip('.')

    return cleaned


def _extract_items_from_text(text: str) -> List[str]:
    """
    Extract 8-K item numbers from filing text using pattern matching.

    This is a fallback extraction method for legacy SGML filings (1999-2001)
    where SEC metadata is incomplete. Research validated 100% accuracy across
    all filing eras on filing.text().

    Pattern matches:
    - Modern: "Item 2.02", "ITEM 2.02", "Item 2. 02"
    - Legacy: "Item 1", "Item 4"
    - Case insensitive, handles line breaks

    Handles range notation (e.g., "Item 1-Item 4") by only including items
    that have actual standalone headers. Intermediate items that only appear
    in ranges are excluded to maintain consistency between item detection
    and item content access.

    Args:
        text: Full text content from filing.text()

    Returns:
        List of normalized item numbers sorted (e.g., ['1', '4', '5'])

    References:
        - Research: scripts/research_8k_parser_findings.md
        - GitHub Issue: #462
        - Beads Issue: edgartools-k1k
    """
    # Extract items that appear at the start of lines only.
    # This ensures consistency with _extract_item_content_from_text which
    # requires items to be at line starts for content extraction.
    #
    # Pattern matches "Item X" or "Item X.XX" at start of line
    # This will match:
    # - "Item 1" (standalone)
    # - "Item 1-Item 4" (only Item 1, since it's at line start)
    # - "Item 2.02" (modern format)
    #
    # This will NOT match:
    # - "  Item 1" (indented, not at line start)
    # - "Item 1-Item 4" (Item 4, not at line start)
    # - Mid-sentence references to items
    pattern = re.compile(
        r'^Item\s+(\d+\.?\s*\d*)',
        re.IGNORECASE | re.MULTILINE
    )
    matches = pattern.findall(text)

    # Normalize and deduplicate
    items = []
    seen = set()

    for match in matches:
        normalized = _normalize_item_number(match)
        if normalized and normalized not in seen:
            items.append(normalized)
            seen.add(normalized)

    return sorted(items)


def _format_item_for_display(item_num: str) -> str:
    """
    Format normalized item number for display (e.g., '2.02' -> 'Item 2.02').

    Args:
        item_num: Normalized item number

    Returns:
        Display format string
    """
    return f"Item {item_num}"


def _extract_item_content_from_text(filing_text: str, item_name: str) -> Optional[str]:
    """
    Extract content for a specific item from legacy SGML filing text.

    This is a fallback extraction method for legacy SGML filings (1999-2001)
    where HTML is unavailable but text content exists. Used by __getitem__ when
    document parser and chunked_document strategies fail.

    Handles:
    - Input normalization: "Item 9", "9", "item 9" -> "Item 9"
    - Flexible item headers: "Item 9", "Item 9.", "Item 9:", etc.
    - End detection: next item or SIGNATURES section

    Args:
        filing_text: Full text content from filing.text()
        item_name: Item identifier (e.g., "Item 9", "9", "Item 2.02", "2.02")

    Returns:
        Item content as string, or None if not found

    References:
        - GitHub Issue: #462
        - Beads Issue: edgartools-k1k
    """
    # Step 1: Normalize input to extract item number
    # "Item 9" or "9" -> "9"
    # "Item 2.02" or "2.02" -> "2.02"
    item_num = _normalize_item_number(item_name)
    if not item_num:
        return None

    # Step 2: Find item header in text
    # Pattern matches: "Item 9", "Item 9.", "Item 9:", "Item 9.02", etc.
    # Must be at start of line (^) to avoid false positives
    item_pattern = re.compile(
        rf'^(Item\s+{re.escape(item_num)}[\s\.:\-]*)',
        re.IGNORECASE | re.MULTILINE
    )

    match = item_pattern.search(filing_text)
    if not match:
        return None

    start_pos = match.start()

    # Step 3: Find end position
    # Look for next "Item X" pattern
    next_item_pattern = re.compile(
        r'^Item\s+\d+\.?\s*\d*[\s\.:\-]',
        re.IGNORECASE | re.MULTILINE
    )
    next_match = next_item_pattern.search(
        filing_text,
        start_pos + len(match.group(0))
    )

    if next_match:
        end_pos = next_match.start()
    else:
        # Look for SIGNATURES section
        sig_pattern = re.compile(
            r'\n\s*SIGNATURES?\s*\n',
            re.IGNORECASE
        )
        sig_match = sig_pattern.search(filing_text[start_pos:])
        if sig_match:
            end_pos = start_pos + sig_match.start()
        else:
            end_pos = len(filing_text)

    # Step 4: Extract and clean content
    content = filing_text[start_pos:end_pos].strip()
    return content if content else None


class CurrentReport(CompanyReport):
    structure = ItemOnlyFilingStructure({
        "ITEM 1.01": {
            "Title": "Entry into a Material Definitive Agreement",
            "Description": "Reports any material agreement not made in the ordinary course of business."
        },
        "ITEM 1.02": {
            "Title": "Termination of a Material Definitive Agreement",
            "Description": "Reports the termination of any material agreement."
        },
        "ITEM 1.03": {
            "Title": "Bankruptcy or Receivership",
            "Description": "Reports any bankruptcy or receivership."
        },
        "ITEM 2.01": {"Title": "Completion of Acquisition or Disposition of Assets",
                      "Description": "Reports the completion of an acquisition or disposition of a significant " +
                                     "amount of assets."},
        "ITEM 2.02": {"Title": "Results of Operations and Financial Condition",
                      "Description": "Reports on the company's results of operations and financial condition."},
        "ITEM 2.03": {
            "Title": "Creation of a Direct Financial Obligation or an Obligation under an Off-Balance Sheet " +
                     "Arrangement of a Registrant",
            "Description": "Reports the creation of a direct financial obligation."},
        "ITEM 2.04": {
            "Title": "Triggering Events That Accelerate or Increase a Direct Financial Obligation or an Obligation "
                     + "under an Off-Balance Sheet Arrangement",
            "Description": "Reports any triggering events."},
        "ITEM 2.05": {"Title": "Costs Associated with Exit or Disposal Activities",
                      "Description": "Reports costs related to exit or disposal activities."},
        "ITEM 2.06": {"Title": "Material Impairments", "Description": "Reports on any material impairments."},
        "ITEM 3.01": {
            "Title": "Notice of Delisting or Failure to Satisfy a Continued Listing Rule or Standard; " +
                     "Transfer of Listing",
            "Description": "Reports on delisting or failure to satisfy listing rules."},
        "ITEM 3.02": {"Title": "Unregistered Sales of Equity Securities",
                      "Description": "Reports on the sale of unregistered equity securities."},
        "ITEM 3.03": {"Title": "Material Modification to Rights of Security Holders",
                      "Description": "Reports on any modifications to the rights of security holders."},
        "ITEM 4.01": {"Title": "Changes in Registrant's Certifying Accountant",
                      "Description": "Reports any change in the company's accountant."},
        "ITEM 4.02": {
            "Title": "Non-Reliance on Previously Issued Financial Statements or a Related Audit Report or " +
                     "Completed Interim Review",
            "Description": "Reports on non-reliance on previously issued financial statements."},
        "ITEM 5.01": {"Title": "Changes in Control of Registrant",
                      "Description": "Reports changes in control of the company."},
        "ITEM 5.02": {
            "Title": "Departure of Directors or Certain Officers; Election of Directors; Appointment of Certain " +
                     "Officers",
            "Description": "Compensatory Arrangements of Certain Officers: Reports any changes in the company's " +
                           "directors or certain officers."},
        "ITEM 5.03": {"Title": "Amendments to Articles of Incorporation or Bylaws; Change in Fiscal Year",
                      "Description": "Reports on amendments to articles of incorporation or bylaws."},
        "ITEM 5.04": {
            "Title": "Temporary Suspension of Trading Under Registrant's Employee Benefit Plans",
            "Description": "Reports on the temporary suspension of trading under the company's employee benefit plans."
        },
        "ITEM 5.05": {
            "Title": "Amendment to the Registrant's Code of Ethics, or Waiver of a Provision of the Code of Ethics",
            "Description": "Reports on amendments or waivers to the code of ethics."},
        "ITEM 5.06": {"Title": "Change in Shell Company Status",
                      "Description": "Reports a change in the company's shell company status."},
        "ITEM 5.07": {"Title": "Submission of Matters to a Vote of Security Holders",
                      "Description": "Reports on matters submitted to a vote of security holders."},
        "ITEM 5.08": {"Title": "Shareholder Director Nominations",
                      "Description": "Reports on shareholder director nominations."},
        "ITEM 6.01": {"Title": "ABS Informational and Computational Material",
                      "Description": "Reports ABS informational and computational material."},
        "ITEM 6.02": {"Title": "Change of Servicer or Trustee",
                      "Description": "Reports on the change of servicer or trustee."},
        "ITEM 6.03": {"Title": "Change in Credit Enhancement or Other External Support",
                      "Description": "Reports on changes in credit enhancement or external support."},
        "ITEM 6.04": {"Title": "Failure to Make a Required Distribution",
                      "Description": "Reports on the failure to make a required distribution."},
        "ITEM 6.05": {"Title": "Securities Act Updating Disclosure",
                      "Description": "Reports on Securities Act updating disclosure."},
        "ITEM 9.01": {
            "Title": "Financial Statements and Exhibits",
            "Description": "Reports financial statements and other exhibits related to the events reported in the 8-K."
        }
    })

    def __init__(self, filing):
        assert filing.form in ['8-K', '8-K/A', '6-K', '6-K/A'], f"This form should be an 8-K but was {filing.form}"
        super().__init__(filing)
        self._cached_filing_text = None

    def _get_filing_text(self) -> Optional[str]:
        """
        Get filing text with caching to avoid redundant extraction.

        This method caches the result of expensive filing.text() calls to improve
        performance when both items property and __getitem__ method need text.

        Returns:
            Filing text as string, or None if extraction fails
        """
        if self._cached_filing_text is None:
            try:
                self._cached_filing_text = self._filing.text()
            except (AttributeError, KeyError, ValueError, TypeError):
                return None
        return self._cached_filing_text

    @cached_property
    def document(self):
        """
        Parse 8-K using new HTMLParser with improved section detection (95% rate).

        This uses the enhanced pattern-based section extractor that handles:
        - All 33 8-K item patterns
        - Bold paragraph fallback detection
        - Table cell detection
        - Space variations in item numbers (e.g., "Item 2. 02")

        Returns:
            Document object from edgar.documents module with sections property
        """
        html = self._filing.html()
        if not html:
            return None
        config = ParserConfig(form='8-K')
        parser = HTMLParser(config)
        return parser.parse(html)

    @property
    def sections(self):
        """
        Get detected 8-K sections using new parser (95% detection rate).

        Returns a Sections dictionary mapping section names to Section objects.
        Section names are normalized (e.g., 'item_502' for Item 5.02).

        Example:
            >>> eight_k.sections
            {'item_502': Section(...), 'item_901': Section(...)}
            >>> eight_k.sections['item_502'].text()
            'Item 5.02 - Departure of Directors...'
        """
        if self.document:
            return self.document.sections
        return {}

    @property
    def has_press_release(self):
        return self.press_releases is not None

    @property
    def press_releases(self):
        from edgar.company_reports.press_release import PressReleases

        attachments: Attachments = self._filing.attachments
        # This query for press release currently includes EX-99, EX-99.1, EX-99.01 but not EX-99.2
        # Here is what we think so far
        html_document = "document.endswith('.htm')"
        named_release = "re.match('.*RELEASE', description)"
        type_ex_99 = "document_type in ['EX-99.1', 'EX-99', 'EX-99.01']"
        press_release_query = f"{html_document} and ({named_release} or {type_ex_99})"
        press_release_results = attachments.query(press_release_query)
        if press_release_results:
            return PressReleases(press_release_results)

    @cached_property
    def chunked_document(self):
        html = self._filing.html()
        if not html:
            return None
        decimal_chunk_fn = partial(chunks2df,
                                   item_detector=detect_decimal_items,
                                   item_adjuster=adjust_for_empty_items,
                                   item_structure=self.structure)

        return ChunkedDocument(html,
                               chunk_fn=decimal_chunk_fn)

    @property
    def doc(self):
        return self.chunked_document

    @property
    def items(self) -> List[str]:
        """
        List of detected item names (consistent with sections property).

        Uses multi-tier fallback strategy:
        1. New parser's section detection (95% accuracy for modern filings)
        2. Chunked document parser (legacy parser)
        3. Text-based pattern extraction (100% accuracy, all eras including SGML)

        The text-based fallback handles legacy SGML filings (1999-2001) where
        SEC metadata is incomplete (GitHub issue #462).

        Returns:
            List of item titles for backward compatibility (e.g., ['Item 5.02', 'Item 9.01'])
        """
        # Strategy 1: Try new parser first (95% detection rate for modern filings)
        if self.sections:
            # Extract items using shared helper (eliminates code duplication)
            item_pattern = re.compile(r'(Item\s+\d+\.\s*\d+)', re.IGNORECASE)
            items = extract_items_from_sections(self.sections, item_pattern)
            if items:
                return items

        # Strategy 2: Fallback to old chunked_document parser
        if self.chunked_document:
            chunked_items = self.chunked_document.list_items()
            if chunked_items:
                return chunked_items

        # Strategy 3: Text-based fallback for legacy SGML filings
        # This handles filings where SEC metadata is incomplete (particularly 1999-2001)
        # Use cached text extraction to improve performance
        filing_text = self._get_filing_text()
        if filing_text:
            extracted_items = _extract_items_from_text(filing_text)
            if extracted_items:
                # Format for display consistency: ['2.02', '9.01'] -> ['Item 2.02', 'Item 9.01']
                return [_format_item_for_display(item) for item in extracted_items]

        return []

    def __getitem__(self, item_name: str):
        """
        Get section/item text by name or number.

        Uses multi-tier fallback strategy:
        1. New parser's section detection (95% accuracy for modern filings)
        2. Chunked document parser (legacy parser)
        3. Text-based pattern extraction (100% accuracy, all eras including SGML)

        The text-based fallback handles legacy SGML filings (1999-2001) where
        HTML is unavailable (GitHub issue #462).

        Supports multiple lookup formats:
        - Section key: 'item_502'
        - Item number: 'Item 5.02', '5.02'
        - Natural language: 'Item 5.02 - Departure of Directors'

        Args:
            item_name: Section identifier in various formats

        Returns:
            Section text content as string, or None if not found
        """
        # Strategy 1: Try new parser sections first (95% detection rate)
        if self.sections:
            # Direct key lookup
            if item_name in self.sections:
                return self.sections[item_name].text()

            # Try fuzzy matching for different formats
            # Normalize: "Item 5.02" → "item_502", "5.02" → "502"
            normalized_input = item_name.lower().replace(' ', '_').replace('.', '').replace('-', '_')
            normalized_input = normalized_input.replace('item_', '')

            for key, section in self.sections.items():
                # Normalize section key: "item_502" → "502"
                normalized_key = key.replace('item_', '').replace('_', '')
                if normalized_key == normalized_input:
                    return section.text()

        # Strategy 2: Fallback to old chunked_document for backward compatibility
        if self.chunked_document:
            try:
                return self.chunked_document[item_name]
            except (KeyError, TypeError):
                pass

        # Strategy 3: Text-based fallback for legacy SGML filings
        # This handles filings where HTML is unavailable but text exists
        # Use cached text extraction to improve performance
        filing_text = self._get_filing_text()
        if filing_text:
            content = _extract_item_content_from_text(filing_text, item_name)
            if content:
                return content

        return None

    def view(self, item_or_part: str):
        """Get the Item or Part from the filing document. e.g. Item 1 Business from 10-K or Part I from 10-Q"""
        item_text = self[item_or_part]
        if item_text:
            print(item_text)

    @property
    def date_of_report(self):
        """Return the period of report for this filing"""
        period_of_report_str = self._filing.header.period_of_report
        if period_of_report_str:
            period_of_report = datetime.strptime(period_of_report_str, "%Y-%m-%d")
            return period_of_report.strftime("%B %d, %Y")
        return ""

    def _get_exhibit_content(self, exhibit) -> Optional[str]:
        """
        Get the content of the exhibit
        """
        # For old filings the exhibit might not have a document. So we need to get the full text content
        # from the sgml content
        if exhibit.empty:
            # Download the SGML document
            sgml_document = self._filing.sgml().get_document_by_sequence(exhibit.sequence_number)
            if sgml_document:
                exhibit_content = sgml_document.text()
                return exhibit_content
        else:
            html_content = exhibit.download()
            if html_content:
                document = Document.parse(html_content)
                return repr_rich(document, width=200, force_terminal=False)

    def _content_renderables(self):
        """Get the content of the exhibits as renderables"""
        renderables = []
        for exhibit in self._filing.exhibits:
            # Skip binary files
            if exhibit.is_binary():
                continue
            exhibit_content = self._get_exhibit_content(exhibit)

            if exhibit_content:
                # Remove text like [/she] and replace with (she) to prevent it being treated as rich markup
                cleaned_content = re.sub(r'\[(/[^]]*)]', r'(\1)',exhibit_content)
                title = Text.assemble(("Exhibit ", "bold gray54"), (exhibit.document_type, "bold green"))
                renderables.append(Panel(cleaned_content,
                                         title=title,
                                         subtitle=Text(exhibit.description, style="gray54"),
                                         box=box.SIMPLE))
        return Group(*renderables)

    def text(self):
        """Get the text of the EightK filing
           This includes the text content of all the exhibits
        """
        return rich_to_text(self._content_renderables())

    def __rich__(self):

        # Renderables for the panel.
        renderables = []

        # List the exhibits as a table
        exhibit_table = Table("", "Type", "Description",
                      title="Exhibits", show_header=True, header_style="bold", box=box.ROUNDED)
        renderables.append(exhibit_table)
        for exhibit in self._filing.exhibits:
            exhibit_table.add_row(exhibit.sequence_number, exhibit.document_type, exhibit.description)

        panel_title = Text.assemble(
            (f"{self.company}", "bold deep_sky_blue1"),
            (" ", ""),
            (f"{self.form}", "bold green"),
            (" ", ""),
            (f"{self.date_of_report}", "bold yellow")
        )

        # Add the content of the exhibits
        renderables.append(self._content_renderables())

        return Panel(
            Group(*renderables),
            title=panel_title,
            box=box.SIMPLE
        )

    def __str__(self):
        return f"{self.company} {self.form} {self.date_of_report}"

    def __repr__(self):
        return repr_rich(self.__rich__())

# Aliases for the current report
EightK = CurrentReport
SixK = CurrentReport
