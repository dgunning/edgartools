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
from edgar.company_reports._structures import ItemOnlyFilingStructure
from edgar.documents import HTMLParser, ParserConfig
from edgar.files.html import Document
from edgar.files.htmltools import ChunkedDocument, adjust_for_empty_items, chunks2df, detect_decimal_items
from edgar.richtools import repr_rich, rich_to_text

__all__ = ['CurrentReport', 'EightK', 'SixK']


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

        Uses new parser's section detection for improved accuracy.
        Falls back to old chunked_document if new parser returns no sections.

        Returns:
            List of item titles for backward compatibility (e.g., ['Item 5.02', 'Item 9.01'])
        """
        # Try new parser first (95% detection rate)
        if self.sections:
            # Return titles for backward compatibility (e.g., "Item 5.02")
            # Extract just the "Item X.XX" part from titles like "Item 5.02 - Description"
            items = []
            for section in self.sections.values():
                title = section.title
                # Extract "Item X.XX" from title
                import re
                match = re.match(r'(Item\s+\d+\.\s*\d+)', title, re.IGNORECASE)
                if match:
                    items.append(match.group(1))
                else:
                    # Fallback: use first part of title before " - " or use full title
                    if ' - ' in title:
                        items.append(title.split(' - ')[0].strip())
                    else:
                        items.append(title)
            return items

        # Fallback to old parser for backward compatibility
        if self.chunked_document:
            return self.chunked_document.list_items()

        return []

    def __getitem__(self, item_name: str):
        """
        Get section/item text by name or number.

        Supports multiple lookup formats:
        - Section key: 'item_502'
        - Item number: 'Item 5.02', '5.02'
        - Natural language: 'Item 5.02 - Departure of Directors'

        Falls back to old chunked_document for backward compatibility.

        Args:
            item_name: Section identifier in various formats

        Returns:
            Section text content as string, or None if not found
        """
        # Try new parser sections first (95% detection rate)
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

        # Fallback to old chunked_document for backward compatibility
        if self.chunked_document:
            try:
                return self.chunked_document[item_name]
            except (KeyError, TypeError):
                pass

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
