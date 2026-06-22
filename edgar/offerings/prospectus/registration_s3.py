"""
S-3 Registration Statement data object.

Handles S-3, S-3/A, and S-3ASR shelf registration statements.
S-3 filings are typically short (50-200K chars) because they incorporate
financials by reference from existing 10-K/10-Q filings.

Key data:
  - Fee table (total offering capacity, per-security breakdowns)
  - Cover page (filer category, state of incorporation, EIN)
  - Offering type classification (universal shelf / resale / S-3ASR)
  - Forward navigation to 424B takedowns

Cover-page model, checkbox parsing, field extraction, and offering-type
classification live in ``_s3_cover`` (mirrors the S-1 layout).
"""

from __future__ import annotations

import logging
from functools import cached_property
from typing import List, Optional, TYPE_CHECKING

from rich import box
from rich.console import Group, Text
from rich.panel import Panel
from rich.table import Table

from edgar.richtools import repr_rich
# Re-imported here so `from edgar.offerings.prospectus.registration_s3 import S3CoverPage,
# S3OfferingType, _is_checked, _extract_s3_cover_page` keeps resolving.
from edgar.offerings.prospectus._s3_cover import (
    S3OfferingType,
    S3CoverPage,
    _is_checked,
    _extract_s3_cover_page,
    _classify_s3_offering,
)

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from edgar._filings import Filing, Filings

__all__ = ['RegistrationS3', 'S3OfferingType', 'S3CoverPage']


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class RegistrationS3:
    """
    Data object for S-3 registration statement filings.

    Handles S-3, S-3/A, and S-3ASR forms. S-3 filings are short shelf
    registrations that incorporate financials by reference from 10-K/10-Q.

    Construction via from_filing() or filing.obj():
        filing = find("S-3 accession number")
        s3 = filing.obj()  # Returns RegistrationS3
        s3 = RegistrationS3.from_filing(filing)

    Key properties:
        s3.cover_page          -> S3CoverPage
        s3.offering_type       -> S3OfferingType enum
        s3.fee_table           -> RegistrationFeeTable | None
        s3.total_offering      -> float | None (total registered amount)
        s3.takedowns           -> Filings (424B filings under this shelf)
    """

    def __init__(self, filing: 'Filing', cover_page: S3CoverPage,
                 offering_type: S3OfferingType, fee_table=None):
        self._filing = filing
        self._cover_page = cover_page
        self._offering_type = offering_type
        self._fee_table = fee_table

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_filing(cls, filing: 'Filing') -> 'RegistrationS3':
        """Primary entry point. Extracts cover page, fee table, and offering type."""
        from edgar.offerings.prospectus._fee_table import extract_registration_fee_table

        # Extract fee table first (used by classifier)
        try:
            fee_table = extract_registration_fee_table(filing)
        except Exception:
            fee_table = None

        # Extract cover page
        html = filing.html()
        cover_page = _extract_s3_cover_page(filing, html) if html else S3CoverPage(
            company_name=filing.company
        )

        # Classify offering type (reuse html to avoid second network call)
        offering_type = _classify_s3_offering(filing, fee_table, html=html)

        return cls(
            filing=filing,
            cover_page=cover_page,
            offering_type=offering_type,
            fee_table=fee_table,
        )

    # ------------------------------------------------------------------
    # Core properties
    # ------------------------------------------------------------------

    @property
    def filing(self) -> 'Filing':
        return self._filing

    @property
    def cover_page(self) -> S3CoverPage:
        return self._cover_page

    @property
    def offering_type(self) -> S3OfferingType:
        return self._offering_type

    @property
    def form(self) -> str:
        return self._filing.form

    @property
    def company(self) -> str:
        return self._filing.company

    @property
    def filing_date(self):
        return self._filing.filing_date

    @property
    def accession_number(self) -> str:
        return self._filing.accession_no

    @property
    def is_amendment(self) -> bool:
        return '/A' in self._filing.form

    @property
    def is_auto_shelf(self) -> bool:
        return 'ASR' in self._filing.form or self._offering_type == S3OfferingType.AUTO_SHELF

    @property
    def registration_number(self) -> Optional[str]:
        return self._cover_page.registration_number

    @property
    def state_of_incorporation(self) -> Optional[str]:
        return self._cover_page.state_of_incorporation

    @property
    def ein(self) -> Optional[str]:
        return self._cover_page.ein

    # ------------------------------------------------------------------
    # Fee table
    # ------------------------------------------------------------------

    @property
    def fee_table(self):
        """Registration fee table from Exhibit 107."""
        return self._fee_table

    @property
    def total_offering(self) -> Optional[float]:
        """Total registered offering amount in dollars."""
        if self._fee_table:
            return self._fee_table.total_offering_amount
        return None

    @property
    def net_fee(self) -> Optional[float]:
        """Net registration fee due."""
        if self._fee_table:
            return self._fee_table.net_fee_due
        return None

    @property
    def fee_deferred(self) -> bool:
        """Whether fees are deferred (S-3ASR pattern)."""
        if self._fee_table:
            return self._fee_table.fee_deferred
        return False

    @property
    def securities(self) -> List:
        """Per-security breakdowns from the fee table."""
        if self._fee_table:
            return self._fee_table.securities
        return []

    # ------------------------------------------------------------------
    # Lifecycle navigation
    # ------------------------------------------------------------------

    @cached_property
    def takedowns(self) -> Optional['Filings']:
        """424B filings issued under this shelf registration.

        Navigates forward from S-3 → 424B takedowns using the
        registration file number to link filings.
        """
        file_number = self._cover_page.registration_number
        if not file_number:
            return None

        try:
            from edgar.entity import Company
            company = Company(self._filing.cik)
            related = company.get_filings(
                file_number=file_number,
                sort_by=[("filing_date", "ascending")],
                trigger_full_load=False,
            )
            if related is None or related.empty:
                return None
            # Filter to only 424B forms
            takedown_forms = ['424B1', '424B2', '424B3', '424B4', '424B5', '424B7', '424B8']
            takedowns = related.filter(form=takedown_forms)
            return takedowns if takedowns and not takedowns.empty else None
        except Exception as e:
            log.debug("Failed to get takedowns for %s: %s", self._filing.accession_no, e)
            return None

    @cached_property
    def related_filings(self) -> Optional['Filings']:
        """All filings under the same registration file number."""
        file_number = self._cover_page.registration_number
        if not file_number:
            return None

        try:
            from edgar.entity import Company
            company = Company(self._filing.cik)
            return company.get_filings(
                file_number=file_number,
                sort_by=[("filing_date", "ascending")],
                trigger_full_load=False,
            )
        except Exception as e:
            log.debug("Failed to get related filings for %s: %s", self._filing.accession_no, e)
            return None

    # ------------------------------------------------------------------
    # AI context
    # ------------------------------------------------------------------

    def to_context(self, detail: str = 'standard') -> str:
        """AI-optimized context string for language models."""
        cp = self._cover_page
        lines = [
            f"REGISTRATION STATEMENT: {self.company} ({self.form})",
            "",
            f"Filed: {self.filing_date}",
            f"Offering Type: {self._offering_type.display_name}",
        ]

        if cp.registration_number:
            lines.append(f"Registration No.: {cp.registration_number}")
        if cp.state_of_incorporation:
            lines.append(f"State: {cp.state_of_incorporation}")
        if cp.ein:
            lines.append(f"EIN: {cp.ein}")

        flags = []
        if self.is_auto_shelf:
            flags.append("AUTO-SHELF")
        if self.is_amendment:
            flags.append("AMENDMENT")
        if cp.is_rule_415:
            flags.append("Rule 415")
        if flags:
            lines.append(f"Status: {' | '.join(flags)}")

        # Filer category
        categories = []
        if cp.is_large_accelerated_filer:
            categories.append("Large Accelerated Filer")
        if cp.is_accelerated_filer:
            categories.append("Accelerated Filer")
        if cp.is_non_accelerated_filer:
            categories.append("Non-Accelerated Filer")
        if cp.is_smaller_reporting_company:
            categories.append("Smaller Reporting Company")
        if cp.is_emerging_growth_company:
            categories.append("Emerging Growth Company")
        if categories:
            lines.append(f"Filer Category: {', '.join(categories)}")

        lines.append(f"Extraction Confidence: {cp.confidence}")

        if detail == 'minimal':
            return "\n".join(lines)

        # Fee table
        if self._fee_table:
            lines.append("")
            lines.append("FEE TABLE:")
            if self.total_offering is not None:
                lines.append(f"  Total Offering: ${self.total_offering:,.2f}")
            if self.net_fee is not None:
                lines.append(f"  Net Fee: ${self.net_fee:,.2f}")
            if self.fee_deferred:
                lines.append("  Fee Status: Deferred (S-3ASR)")
            for sec in self.securities[:5]:
                title = sec.security_title or sec.security_type or "Security"
                amt = f"${sec.max_aggregate_amount:,.2f}" if sec.max_aggregate_amount else "TBD"
                lines.append(f"  - {title}: {amt}")

        if detail == 'full':
            lines.append("")
            lines.append("AVAILABLE ACTIONS:")
            lines.append("  - .cover_page -> S3CoverPage (filer info, checkboxes)")
            lines.append("  - .fee_table -> RegistrationFeeTable (offering capacity)")
            lines.append("  - .total_offering -> float (total registered amount)")
            lines.append("  - .takedowns -> Filings (424B filings under this shelf)")
            lines.append("  - .related_filings -> Filings (all filings, same file number)")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Rich display
    # ------------------------------------------------------------------

    def __rich__(self):
        title = f"{self.company}  {self.filing_date}"
        subtitle = f"{self.form}  {self._offering_type.display_name}"

        # Cover page table
        cp = self._cover_page
        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        t.add_column("field", style="bold deep_sky_blue1", min_width=22)
        t.add_column("value")

        t.add_row("Form", self.form)
        t.add_row("Offering Type", self._offering_type.display_name)
        if cp.registration_number:
            t.add_row("Registration No.", cp.registration_number)
        if cp.state_of_incorporation:
            t.add_row("State", cp.state_of_incorporation)
        if cp.ein:
            t.add_row("EIN", cp.ein)

        # Filer category
        categories = []
        if cp.is_large_accelerated_filer:
            categories.append("Large Accelerated Filer")
        if cp.is_accelerated_filer:
            categories.append("Accelerated Filer")
        if cp.is_non_accelerated_filer:
            categories.append("Non-Accelerated Filer")
        if cp.is_smaller_reporting_company:
            categories.append("Smaller Reporting")
        if cp.is_emerging_growth_company:
            categories.append("EGC")
        if categories:
            t.add_row("Filer Category", ", ".join(categories))

        # Status flags
        flags = []
        if self.is_auto_shelf:
            flags.append("[green]AUTO-SHELF[/green]")
        if self.is_amendment:
            flags.append("[yellow]AMENDMENT[/yellow]")
        if cp.is_rule_415:
            flags.append("Rule 415")
        if flags:
            t.add_row("Status", " | ".join(flags))

        t.add_row("Confidence", cp.confidence)

        renderables = [t]

        # Fee table
        if self._fee_table:
            ft = Table(box=box.SIMPLE, padding=(0, 1), title="Fee Table")
            ft.add_column("Field", style="bold")
            ft.add_column("Value", justify="right", style="deep_sky_blue1")

            if self.total_offering is not None:
                ft.add_row("Total Offering", f"${self.total_offering:,.2f}")
            if self.net_fee is not None:
                ft.add_row("Net Fee", f"${self.net_fee:,.2f}")
            if self.fee_deferred:
                ft.add_row("Fee Status", "Deferred")
            ft.add_row("Securities", str(len(self.securities)))

            renderables.append(Text(""))
            renderables.append(ft)

        return Panel(
            Group(*renderables),
            title=f"[bold]{title}[/bold]",
            subtitle=subtitle,
            box=box.ROUNDED,
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        return (
            f"RegistrationS3("
            f"form={self.form!r}, "
            f"company={self.company!r}, "
            f"offering_type={self._offering_type.value!r}, "
            f"date={self.filing_date!r})"
        )
