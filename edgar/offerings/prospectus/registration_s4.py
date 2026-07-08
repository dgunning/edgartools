"""
S-4 / F-4 Registration Statement data object.

Handles S-4, S-4/A (domestic) and F-4, F-4/A (foreign private issuer)
business-combination registration statements. These register securities issued
as consideration in mergers, acquisitions, de-SPAC transactions, and security
exchange offers.

Phase 1 scope — registration-object *parity* with S-1/S-3/F-1/F-3: cover page
(registrant metadata + filer category), the Exhibit 107 fee table (total
offering amount, per-security breakdowns), offering-type classification, and
same-file-number navigation. The business-combination narrative (acquirer /
target, consideration, exchange ratio, fairness opinions) is deliberately out
of scope here and tracked separately (beads edgartools-ssl6).

Cover-page model, field extraction, and offering-type classification live in
``_s4_cover`` (mirrors the S-1/S-3 layout).
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
# Re-imported here so `from edgar.offerings.prospectus.registration_s4 import
# S4CoverPage, S4OfferingType, ...` keeps resolving.
from edgar.offerings.prospectus._s4_cover import (
    S4OfferingType,
    S4CoverPage,
    _extract_s4_cover_page,
    _classify_s4_offering,
)

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from edgar._filings import Filing, Filings

__all__ = ['RegistrationS4', 'S4OfferingType', 'S4CoverPage']


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class RegistrationS4:
    """
    Data object for S-4 / F-4 business-combination registration statements.

    Handles S-4, S-4/A, F-4, and F-4/A forms. Provides the same field surface
    as the other registration objects (RegistrationS1 / RegistrationS3).

    Construction via from_filing() or filing.obj():
        filing = find("S-4 accession number")
        s4 = filing.obj()  # Returns RegistrationS4
        s4 = RegistrationS4.from_filing(filing)

    Key properties:
        s4.cover_page          -> S4CoverPage
        s4.offering_type       -> S4OfferingType enum
        s4.fee_table           -> RegistrationFeeTable | None
        s4.total_offering      -> float | None (total registered amount)
        s4.related_filings     -> Filings (all filings, same file number)
    """

    def __init__(self, filing: 'Filing', cover_page: S4CoverPage,
                 offering_type: S4OfferingType, fee_table=None):
        self._filing = filing
        self._cover_page = cover_page
        self._offering_type = offering_type
        self._fee_table = fee_table

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_filing(cls, filing: 'Filing') -> 'RegistrationS4':
        """Primary entry point. Extracts cover page, fee table, and offering type."""
        from edgar.offerings.prospectus._fee_table import extract_registration_fee_table

        # Extract fee table first
        try:
            fee_table = extract_registration_fee_table(filing)
        except Exception:
            fee_table = None

        # Fetch the primary document once for both cover and classifier. These
        # filings are large (10-24 MB) and the fetch/parse can fail transiently;
        # degrade to a fee-table-only object rather than crashing obj().
        try:
            html = filing.html()
        except Exception:
            html = None

        cover_page = _extract_s4_cover_page(filing, html) if html else S4CoverPage(
            company_name=filing.company
        )

        # Classify offering type (reuse html to avoid a second network call)
        offering_type = _classify_s4_offering(filing, html=html)

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
    def cover_page(self) -> S4CoverPage:
        return self._cover_page

    @property
    def offering_type(self) -> S4OfferingType:
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
    def is_foreign(self) -> bool:
        """True for F-4 / F-4/A (foreign private issuer registration)."""
        return self._filing.form.upper().startswith('F-4')

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
    def securities(self) -> List:
        """Per-security breakdowns from the fee table."""
        if self._fee_table:
            return self._fee_table.securities
        return []

    # ------------------------------------------------------------------
    # Lifecycle navigation
    # ------------------------------------------------------------------

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
        if cp.sic_code:
            lines.append(f"SIC Code: {cp.sic_code}")
        if cp.ein:
            lines.append(f"EIN: {cp.ein}")

        flags = []
        if self.is_foreign:
            flags.append("FOREIGN (F-4)")
        if self.is_amendment:
            flags.append("AMENDMENT")
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
            for sec in self.securities[:5]:
                title = sec.security_title or sec.security_type or "Security"
                amt = f"${sec.max_aggregate_amount:,.2f}" if sec.max_aggregate_amount else "TBD"
                lines.append(f"  - {title}: {amt}")

        if detail == 'full':
            lines.append("")
            lines.append("AVAILABLE ACTIONS:")
            lines.append("  - .cover_page -> S4CoverPage (registrant info, checkboxes)")
            lines.append("  - .fee_table -> RegistrationFeeTable (offering capacity)")
            lines.append("  - .total_offering -> float (total registered amount)")
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
        if cp.sic_code:
            t.add_row("SIC Code", str(cp.sic_code))
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
        if self.is_foreign:
            flags.append("[cyan]FOREIGN (F-4)[/cyan]")
        if self.is_amendment:
            flags.append("[yellow]AMENDMENT[/yellow]")
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
            f"RegistrationS4("
            f"form={self.form!r}, "
            f"company={self.company!r}, "
            f"offering_type={self._offering_type.value!r}, "
            f"date={self.filing_date!r})"
        )
