"""Form 6-K Report of Foreign Private Issuer."""
import re
from datetime import datetime
from functools import cached_property
from typing import List, Optional

from rich import box
from rich.console import Group, Text
from rich.panel import Panel
from rich.table import Table

from edgar.richtools import repr_rich, rich_to_text

__all__ = ['SixK']


def _parse_cover_page(text: str) -> dict:
    """
    Extract metadata from the 6-K cover page text.

    Returns dict with keys: commission_file_number, report_month,
    annual_report_form, content_description.
    """
    result = {
        'commission_file_number': None,
        'report_month': None,
        'annual_report_form': None,
        'content_description': None,
    }

    if not text:
        return result

    # Commission File Number: "Commission File Number 001-14948"
    m = re.search(r'Commission\s+File\s+Number[:\s]+([\d\-]+)', text, re.IGNORECASE)
    if m:
        result['commission_file_number'] = m.group(1).strip()

    # Report month: "For the month of March 2026"
    m = re.search(r'For\s+the\s+month\s+of\s+([A-Za-z]+(?:\s+\d{4})?)', text, re.IGNORECASE)
    if m:
        result['report_month'] = m.group(1).strip()

    # Annual report form: check mark for 20-F or 40-F
    # Patterns: "Form 20-F  X", "Form 20-F [ X ]", "Form20-F    X"
    if re.search(r'Form\s*20-?F\s+\[?\s*X\s*\]?', text, re.IGNORECASE):
        result['annual_report_form'] = '20-F'
    elif re.search(r'Form\s*40-?F\s+\[?\s*X\s*\]?', text, re.IGNORECASE):
        result['annual_report_form'] = '40-F'

    # Content description: text between "Material Contained" / exhibit list and "SIGNATURES"
    # Try "Material Contained in this Report:" first
    m = re.search(
        r'(?:Material\s+Contained\s+in\s+this\s+Report|Exhibit\s+Description)[:\s]*(.*?)(?=SIGNATURES|SIGNATURE\b)',
        text, re.IGNORECASE | re.DOTALL
    )
    if m:
        desc = m.group(1).strip()
        # Clean up excessive whitespace
        desc = re.sub(r'\s+', ' ', desc).strip()
        # Trim trailing dashes/lines
        desc = re.sub(r'[\s─\-]+$', '', desc)
        if desc and len(desc) > 5:
            result['content_description'] = desc

    return result


class SixK:
    """
    Form 6-K — Report of Foreign Private Issuer.

    6-K filings are submitted by foreign private issuers to report material
    information published in their home country, filed with stock exchanges,
    or distributed to shareholders. Unlike 8-K filings, 6-K has no numbered
    item structure — content is either inline in the cover page or in exhibits
    (typically EX-99.x).

    Properties:
        exhibits: Non-graphic attachments (press releases, financial statements)
        press_releases: EX-99.x press release exhibits
        content_description: What the filing contains (from cover page)
        commission_file_number: SEC file number
        report_month: Reporting month (e.g., "March 2026")
        annual_report_form: Whether the issuer files 20-F or 40-F

    Example:
        >>> filing = Company("TM").get_filings(form="6-K").latest()
        >>> six_k = filing.obj()
        >>> six_k.exhibits             # List of exhibits
        >>> six_k.content_description  # What's in this filing
        >>> six_k.press_releases       # EX-99.x press releases
    """

    def __init__(self, filing):
        assert filing.form in ['6-K', '6-K/A'], f"Expected 6-K but got {filing.form}"
        self._filing = filing
        self._cover_metadata = None

    def _get_cover_metadata(self) -> dict:
        """Parse and cache cover page metadata from the primary document only."""
        if self._cover_metadata is None:
            try:
                html = self._filing.html()
                if html:
                    # Parse from raw HTML (preserves checkmarks lost in rich rendering)
                    from lxml import html as lxml_html
                    tree = lxml_html.fromstring(html)
                    text = tree.text_content()
                    self._cover_metadata = _parse_cover_page(text)
                else:
                    self._cover_metadata = {}
            except Exception:
                self._cover_metadata = {}
        return self._cover_metadata

    @property
    def filing_date(self):
        return self._filing.filing_date

    @property
    def form(self):
        return self._filing.form

    @property
    def company(self):
        return self._filing.company

    @property
    def date_of_report(self):
        """Return the period of report for this filing."""
        period_of_report_str = self._filing.header.period_of_report
        if period_of_report_str:
            period_of_report = datetime.strptime(period_of_report_str, "%Y-%m-%d")
            return period_of_report.strftime("%B %d, %Y")
        return ""

    @property
    def commission_file_number(self) -> Optional[str]:
        """SEC Commission File Number (e.g., '001-14948')."""
        return self._get_cover_metadata().get('commission_file_number')

    @property
    def report_month(self) -> Optional[str]:
        """The reporting month from the cover page (e.g., 'March 2026')."""
        return self._get_cover_metadata().get('report_month')

    @property
    def annual_report_form(self) -> Optional[str]:
        """Whether the issuer files annual reports on Form 20-F or 40-F."""
        return self._get_cover_metadata().get('annual_report_form')

    @property
    def content_description(self) -> Optional[str]:
        """Description of material contained in this report, from the cover page."""
        return self._get_cover_metadata().get('content_description')

    @cached_property
    def exhibits(self) -> List:
        """
        Non-graphic exhibit attachments.

        Returns list of Attachment objects, excluding graphics (JPG/GIF/PNG).
        """
        return [
            att for att in self._filing.attachments
            if att.document_type
            and att.document_type != 'GRAPHIC'
            and att.document_type != self._filing.form  # Exclude the cover page itself
        ]

    @property
    def has_exhibits(self) -> bool:
        """Whether this filing has content exhibits."""
        return len(self.exhibits) > 0

    @property
    def press_releases(self):
        """EX-99.x press release exhibits, if any."""
        from edgar.company_reports.press_release import PressReleases

        attachments: Attachments = self._filing.attachments
        html_document = "document.endswith('.htm')"
        named_release = "re.match('.*RELEASE', description)"
        type_ex_99 = "document_type in ['EX-99.1', 'EX-99', 'EX-99.01']"
        press_release_query = f"{html_document} and ({named_release} or {type_ex_99})"
        press_release_results = attachments.query(press_release_query)
        if press_release_results:
            return PressReleases(press_release_results)

    @property
    def has_press_release(self) -> bool:
        return self.press_releases is not None

    @cached_property
    def financials(self):
        """XBRL financials, if present (rare for 6-K; uses IFRS taxonomy)."""
        from edgar.financials import Financials
        return Financials.extract(self._filing)

    def text(self) -> str:
        """Get the full text content of the 6-K including exhibits."""
        return rich_to_text(self._content_renderables())

    def _get_exhibit_content(self, exhibit) -> Optional[str]:
        """Get the rendered text content of an exhibit."""
        from edgar.files.html import Document

        if exhibit.empty:
            sgml_document = self._filing.sgml().get_document_by_sequence(exhibit.sequence_number)
            if sgml_document:
                return sgml_document.text()
        else:
            html_content = exhibit.download()
            if html_content:
                document = Document.parse(html_content)
                return repr_rich(document, width=200, force_terminal=False)

    def _content_renderables(self):
        """Get exhibit content as rich renderables."""
        renderables = []
        for exhibit in self.exhibits:
            if exhibit.is_binary():
                continue
            exhibit_content = self._get_exhibit_content(exhibit)
            if exhibit_content:
                cleaned_content = re.sub(r'\[(/[^]]*)]', r'(\1)', exhibit_content)
                title = Text.assemble(("Exhibit ", "bold gray54"), (exhibit.document_type, "bold green"))
                renderables.append(Panel(cleaned_content,
                                         title=title,
                                         subtitle=Text(exhibit.description, style="gray54"),
                                         box=box.SIMPLE))
        return Group(*renderables)

    def __rich__(self):
        renderables = []

        # Cover page metadata
        meta_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        meta_table.add_column("Field", style="bold")
        meta_table.add_column("Value")

        if self.report_month:
            meta_table.add_row("Report Month", self.report_month)
        if self.commission_file_number:
            meta_table.add_row("File Number", self.commission_file_number)
        if self.annual_report_form:
            meta_table.add_row("Annual Report Form", self.annual_report_form)
        if self.content_description:
            # Truncate long descriptions for display
            desc = self.content_description
            if len(desc) > 200:
                desc = desc[:200] + "..."
            meta_table.add_row("Content", desc)

        renderables.append(meta_table)

        # Exhibits table
        if self.has_exhibits:
            exhibit_table = Table("", "Type", "Description",
                                  title="Exhibits", show_header=True, header_style="bold", box=box.ROUNDED)
            for exhibit in self.exhibits:
                exhibit_table.add_row(
                    exhibit.sequence_number or "",
                    exhibit.document_type or "",
                    exhibit.description or ""
                )
            renderables.append(exhibit_table)

        # Exhibit content
        renderables.append(self._content_renderables())

        panel_title = Text.assemble(
            (f"{self.company}", "bold deep_sky_blue1"),
            (" ", ""),
            (f"{self.form}", "bold green"),
            (" ", ""),
            (f"{self.date_of_report}", "bold yellow")
        )

        return Panel(
            Group(*renderables),
            title=panel_title,
            box=box.SIMPLE
        )

    def __str__(self):
        return f"{self.company} {self.form} {self.date_of_report}"

    def __repr__(self):
        return repr_rich(self.__rich__())

    def to_context(self, detail: str = 'standard') -> str:
        """
        AI-optimized context string.

        Args:
            detail: 'minimal' (~100 tokens), 'standard' (~300 tokens), 'full' (~500+ tokens)
        """
        lines = []

        # Identity
        lines.append(f"6K: {self.company} Report of Foreign Private Issuer")
        lines.append("")

        # Core metadata
        lines.append(f"Filed: {self.filing_date}")
        dor = self.date_of_report
        if dor:
            lines.append(f"Event Date: {dor}")
        if self.report_month:
            lines.append(f"Report Month: {self.report_month}")
        if self.annual_report_form:
            lines.append(f"Annual Report Form: {self.annual_report_form}")

        if self.content_description:
            lines.append(f"Content: {self.content_description}")

        if detail == 'minimal':
            return "\n".join(lines)

        # Standard
        lines.append(f"Form: {self.form}")
        lines.append(f"CIK: {str(self._filing.cik).zfill(10)}")
        if self.commission_file_number:
            lines.append(f"File Number: {self.commission_file_number}")

        flags = []
        if self.has_press_release:
            flags.append("has_press_release")
        if self.has_exhibits:
            flags.append("has_exhibits")
        if flags:
            lines.append(f"Flags: {', '.join(flags)}")

        # Exhibits summary
        if self.exhibits:
            lines.append("")
            lines.append("EXHIBITS:")
            for att in self.exhibits[:10]:
                doc_type = att.document_type or ''
                desc = att.description or ''
                lines.append(f"  {doc_type}: {desc}" if desc else f"  {doc_type}")
            if len(self.exhibits) > 10:
                lines.append(f"  ... ({len(self.exhibits) - 10} more)")

        lines.append("")
        lines.append("AVAILABLE ACTIONS:")
        lines.append("  .exhibits                Content exhibit attachments")
        lines.append("  .press_releases          Press release attachments")
        lines.append("  .content_description     What this filing contains")
        lines.append("  .text()                  Full filing text content")
        lines.append("  .financials              XBRL financials (if present)")

        if detail == 'standard':
            return "\n".join(lines)

        # Full — include exhibit details
        if self.exhibits:
            lines.append("")
            lines.append("EXHIBIT DETAILS:")
            for att in self.exhibits:
                doc_type = att.document_type or ''
                desc = att.description or ''
                doc_name = att.document or ''
                lines.append(f"  {doc_type}: {desc} [{doc_name}]")

        return "\n".join(lines)
