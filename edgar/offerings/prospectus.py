"""
424B* Prospectus Parser.

Handles all 424B form variants (424B1 through 424B8) including amendments (/A).
Phase 1: Cover page extraction + offering type classification + obj() dispatch.
"""

from __future__ import annotations

import re
from enum import Enum
from functools import cached_property
from typing import List, Optional, TYPE_CHECKING

from pydantic import BaseModel, field_validator
from rich import box
from rich.console import Group, Text
from rich.panel import Panel
from rich.table import Table

from edgar.richtools import repr_rich

if TYPE_CHECKING:
    from edgar._filings import Filing

__all__ = ['Prospectus424B', 'OfferingType', 'CoverPageData']

# Forms handled by this parser
PROSPECTUS_FORMS = ['424B1', '424B2', '424B3', '424B4', '424B5', '424B7', '424B8']


# ---------------------------------------------------------------------------
# Offering Type Enum
# ---------------------------------------------------------------------------

class OfferingType(str, Enum):
    """Classification of 424B offering types."""
    FIRM_COMMITMENT = "firm_commitment"
    ATM = "atm"
    BEST_EFFORTS = "best_efforts"
    PIPE_RESALE = "pipe_resale"
    RIGHTS_OFFERING = "rights_offering"
    EXCHANGE_OFFER = "exchange_offer"
    STRUCTURED_NOTE = "structured_note"
    DEBT_OFFERING = "debt_offering"
    BASE_PROSPECTUS_UPDATE = "base_prospectus_update"
    UNKNOWN = "unknown"

    @property
    def display_name(self) -> str:
        return {
            "firm_commitment": "Firm Commitment",
            "atm": "At-the-Market",
            "best_efforts": "Best Efforts / PIPE",
            "pipe_resale": "Resale (PIPE)",
            "rights_offering": "Rights Offering",
            "exchange_offer": "Exchange Offer",
            "structured_note": "Structured Note",
            "debt_offering": "Debt Offering",
            "base_prospectus_update": "Base Prospectus Update",
            "unknown": "Unknown",
        }[self.value]

    @property
    def is_equity(self) -> bool:
        return self in (
            OfferingType.FIRM_COMMITMENT,
            OfferingType.ATM,
            OfferingType.BEST_EFFORTS,
            OfferingType.PIPE_RESALE,
            OfferingType.RIGHTS_OFFERING,
        )

    @property
    def has_fixed_price(self) -> bool:
        return self in (
            OfferingType.FIRM_COMMITMENT,
            OfferingType.BEST_EFFORTS,
            OfferingType.RIGHTS_OFFERING,
        )

    @property
    def has_selling_stockholders(self) -> bool:
        return self in (
            OfferingType.PIPE_RESALE,
            OfferingType.BASE_PROSPECTUS_UPDATE,
        )


# ---------------------------------------------------------------------------
# Pydantic Data Models
# ---------------------------------------------------------------------------

class CoverPageData(BaseModel):
    """
    Extracted cover page fields from a 424B* filing.

    Required fields (always present when parsing succeeds):
      - company_name, registration_number, rule_number
      - is_supplement, is_preliminary, is_atm

    Optional fields (absent for legitimate structural reasons):
      - security_description, offering_amount, offering_price
      - exchange_ticker, base_prospectus_date
    """
    company_name: str
    registration_number: Optional[str] = None

    is_supplement: bool = False
    is_preliminary: bool = False
    is_atm: bool = False

    rule_number: Optional[str] = None
    security_description: Optional[str] = None
    offering_amount: Optional[str] = None
    offering_price: Optional[str] = None
    exchange_ticker: Optional[str] = None
    base_prospectus_date: Optional[str] = None

    @field_validator("offering_amount", "offering_price", mode="before")
    @classmethod
    def coerce_empty_string_to_none(cls, v):
        if v == "":
            return None
        return v

    @property
    def offering_amount_float(self) -> Optional[float]:
        if not self.offering_amount or self.offering_amount in (
            "exchange-offer", "at-the-market", "preliminary-TBD", "market-price"
        ):
            return None
        try:
            clean = self.offering_amount.replace("$", "").replace(",", "").strip()
            return float(clean)
        except (ValueError, AttributeError):
            return None

    @property
    def offering_price_float(self) -> Optional[float]:
        if not self.offering_price or self.offering_price.startswith(
            ("at", "exchange", "preliminary", "market")
        ):
            return None
        try:
            clean = self.offering_price.replace("$", "").replace(",", "").strip()
            return float(clean)
        except (ValueError, AttributeError):
            return None


# --- Stub models for later phases ---

class PricingColumnData(BaseModel):
    column_label: Optional[str] = None
    offering_price: Optional[str] = None
    fee_or_discount: Optional[str] = None
    proceeds: Optional[str] = None


class PricingData(BaseModel):
    columns: List[PricingColumnData] = []
    fee_type: Optional[str] = None
    is_percentage_price: bool = False
    raw_rows: List[List[str]] = []


class OfferingTerms(BaseModel):
    shares_offered: Optional[str] = None
    pre_funded_warrants_offered: Optional[str] = None
    warrants_offered: Optional[str] = None
    use_of_proceeds_summary: Optional[str] = None
    trading_symbol: Optional[str] = None
    listing_exchange: Optional[str] = None
    additional_terms: dict = {}


class SellingStockholderEntry(BaseModel):
    name: str
    shares_before_offering: Optional[str] = None
    pct_before_offering: Optional[str] = None
    shares_offered: Optional[str] = None
    shares_after_offering: Optional[str] = None
    pct_after_offering: Optional[str] = None


class SellingStockholdersData(BaseModel):
    stockholders: List[SellingStockholderEntry] = []
    total_shares_offered: Optional[str] = None
    notes: Optional[str] = None

    @property
    def count(self) -> int:
        return len(self.stockholders)

    @property
    def is_populated(self) -> bool:
        return len(self.stockholders) > 0


class UnderwriterEntry(BaseModel):
    name: str
    shares_allocated: Optional[str] = None
    dollar_amount: Optional[str] = None


class UnderwritingInfo(BaseModel):
    underwriters: List[UnderwriterEntry] = []
    fee_type: str = "underwriting_discount"
    overallotment_shares: Optional[str] = None
    overallotment_amount: Optional[str] = None
    lock_up_days: Optional[int] = None

    @property
    def is_underwritten(self) -> bool:
        return self.fee_type == "underwriting_discount"

    @property
    def lead_manager(self) -> Optional[str]:
        return self.underwriters[0].name if self.underwriters else None


class StructuredNoteTerms(BaseModel):
    issuer: Optional[str] = None
    guarantor: Optional[str] = None
    cusip: Optional[str] = None
    pricing_date: Optional[str] = None
    issue_date: Optional[str] = None
    maturity_date: Optional[str] = None
    underlying: Optional[str] = None
    denominations: Optional[str] = None
    term: Optional[str] = None
    principal_amount: Optional[str] = None
    upside_participation_rate: Optional[str] = None
    max_return: Optional[str] = None
    threshold_value: Optional[str] = None
    buffer_amount: Optional[str] = None
    coupon_rate: Optional[str] = None
    coupon_frequency: Optional[str] = None
    additional_terms: dict = {}


class DilutionData(BaseModel):
    public_offering_price: Optional[str] = None
    ntbv_before_offering: Optional[str] = None
    ntbv_increase: Optional[str] = None
    ntbv_after_offering: Optional[str] = None
    dilution_per_share: Optional[str] = None
    dilution_percentage: Optional[str] = None
    shares_outstanding_before: Optional[str] = None
    shares_outstanding_after: Optional[str] = None


class CapitalizationData(BaseModel):
    rows: List[dict] = []
    cash_actual: Optional[str] = None
    cash_as_adjusted: Optional[str] = None
    total_stockholders_equity_actual: Optional[str] = None
    total_stockholders_equity_as_adjusted: Optional[str] = None
    total_capitalization_actual: Optional[str] = None
    total_capitalization_as_adjusted: Optional[str] = None


class FilingFeesRow(BaseModel):
    security_type: Optional[str] = None
    security_title: Optional[str] = None
    max_aggregate_offering_price: Optional[str] = None
    fee_rate: Optional[str] = None
    fee_amount: Optional[str] = None
    fee_rule: Optional[str] = None


class FilingFeesData(BaseModel):
    has_exhibit: bool = False
    exhibit_url: Optional[str] = None
    form_type: Optional[str] = None
    registration_file_number: Optional[str] = None
    total_offering_amount: Optional[str] = None
    total_fee_amount: Optional[str] = None
    offering_rows: List[FilingFeesRow] = []
    is_final_prospectus: bool = True


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

def _extract_amendment_number(form_name: str) -> Optional[int]:
    """Extract amendment number from form name like '424B3/A'."""
    if '/A' not in form_name:
        return None
    m = re.search(r'Amendment\s+No\.?\s*(\d+)', form_name, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


class Prospectus424B:
    """
    Parser for 424B* prospectus filings.

    Handles all 424B variants:
      - 424B1: Exchange offers, initial public offerings
      - 424B2: Structured notes, debt (large banks)
      - 424B3: Resale prospectuses (PIPE resales, rights offerings)
      - 424B4: Final priced prospectuses (IPOs, shelf takedowns)
      - 424B5: Shelf takedowns (ATM, firm commitment, PIPE, debt)
      - 424B7: WKSI selling stockholder updates
      - 424B8: Prospectus supplements

    Construction via from_filing() or filing.obj():
        filing = find("0001493152-25-029712")
        prospectus = filing.obj()  # Returns Prospectus424B
        prospectus = Prospectus424B.from_filing(filing)

    Key properties:
        prospectus.cover_page       -> CoverPageData (always available)
        prospectus.offering_type    -> OfferingType enum
        prospectus.ticker           -> str | None
        prospectus.offering_price   -> str | None
        prospectus.offering_amount  -> str | None
    """

    def __init__(self, filing: 'Filing', cover_page: CoverPageData,
                 offering_type: OfferingType, confidence: str):
        self._filing = filing
        self._cover_page = cover_page
        self._offering_type = offering_type
        self._confidence = confidence

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_filing(cls, filing: 'Filing') -> 'Prospectus424B':
        """
        Primary entry point. Eagerly extracts cover page and offering type.

        Args:
            filing: An EdgarTools Filing object with a 424B* form type.

        Returns:
            Prospectus424B instance.
        """
        from edgar.offerings._424b_cover import extract_cover_page_fields
        from edgar.offerings._424b_classifier import classify_offering_type

        cover_fields = extract_cover_page_fields(filing)
        cover_page = CoverPageData(**cover_fields)

        classification = classify_offering_type(filing)
        offering_type = OfferingType(classification.get('type', 'unknown'))
        confidence = classification.get('confidence', 'low')

        return cls(
            filing=filing,
            cover_page=cover_page,
            offering_type=offering_type,
            confidence=confidence,
        )

    # ------------------------------------------------------------------
    # Core properties (from filing metadata / eager extraction)
    # ------------------------------------------------------------------

    @property
    def filing(self) -> 'Filing':
        return self._filing

    @property
    def cover_page(self) -> CoverPageData:
        return self._cover_page

    @property
    def offering_type(self) -> OfferingType:
        return self._offering_type

    @property
    def form(self) -> str:
        return self._filing.form

    @property
    def variant(self) -> str:
        return self._filing.form.replace('/A', '')

    @property
    def company(self) -> str:
        return self._filing.company

    @property
    def filing_date(self) -> str:
        return self._filing.filing_date

    @property
    def accession_number(self) -> str:
        return self._filing.accession_no

    @property
    def is_amendment(self) -> bool:
        return '/A' in self._filing.form

    @property
    def amendment_number(self) -> Optional[int]:
        return _extract_amendment_number(self._filing.form)

    @property
    def registration_number(self) -> Optional[str]:
        return self._cover_page.registration_number

    @property
    def is_preliminary(self) -> bool:
        return self._cover_page.is_preliminary

    @property
    def is_atm(self) -> bool:
        return self._cover_page.is_atm

    @property
    def is_supplement(self) -> bool:
        return self._cover_page.is_supplement

    @property
    def ticker(self) -> Optional[str]:
        return self._cover_page.exchange_ticker

    @property
    def offering_amount(self) -> Optional[str]:
        return self._cover_page.offering_amount

    @property
    def offering_price(self) -> Optional[str]:
        return self._cover_page.offering_price

    # ------------------------------------------------------------------
    # Lazy table-extracted data (Phase 2+)
    # ------------------------------------------------------------------

    @cached_property
    def _classified_tables(self) -> dict:
        """Dict mapping table type -> list of matching TableNode objects."""
        from edgar.offerings._424b_tables import classify_tables_in_document
        doc = self._filing.parse()
        if not doc:
            return {}
        return classify_tables_in_document(doc)

    @cached_property
    def pricing(self) -> Optional[PricingData]:
        """Pricing table data (offering price, fee, proceeds).
        Returns None for ATM offerings and resale filings."""
        from edgar.offerings._424b_tables import extract_pricing_data
        tables = self._classified_tables.get('pricing_table', [])
        if not tables:
            return None
        return extract_pricing_data(tables[0])

    @cached_property
    def offering_terms(self) -> Optional[OfferingTerms]:
        """Key-value offering terms from 'The Offering' section."""
        from edgar.offerings._424b_tables import extract_offering_terms
        tables = self._classified_tables.get('offering_summary', [])
        if not tables:
            return None
        return extract_offering_terms(tables[0])

    @cached_property
    def selling_stockholders(self) -> Optional[SellingStockholdersData]:
        """Selling stockholders table data.
        Returns None if no selling stockholders table is found."""
        from edgar.offerings._424b_tables import extract_selling_stockholders_data
        tables = self._classified_tables.get('selling_stockholders', [])
        if not tables:
            return None
        result = extract_selling_stockholders_data(tables[0])
        return result if result.is_populated else None

    @cached_property
    def structured_note_terms(self) -> Optional[StructuredNoteTerms]:
        """Structured note key terms (CUSIP, maturity, underlying, etc.).
        Returns None if no key terms table is found."""
        from edgar.offerings._424b_tables import extract_structured_note_terms
        tables = self._classified_tables.get('key_terms', [])
        if not tables:
            return None
        return extract_structured_note_terms(tables[0])

    @cached_property
    def dilution(self) -> Optional[DilutionData]:
        """Per-share dilution impact table."""
        from edgar.offerings._424b_tables import extract_dilution_data
        tables = self._classified_tables.get('dilution', [])
        if not tables:
            return None
        return extract_dilution_data(tables[0])

    @cached_property
    def capitalization(self) -> Optional[CapitalizationData]:
        """Actual vs. as-adjusted capitalization table."""
        from edgar.offerings._424b_tables import extract_capitalization_data
        tables = self._classified_tables.get('capitalization', [])
        if not tables:
            return None
        return extract_capitalization_data(tables[0])

    @cached_property
    def underwriting(self) -> Optional[UnderwritingInfo]:
        """Underwriting syndicate or placement agent info.
        Uses table extraction first, falls back to cover page text."""
        from edgar.offerings._424b_tables import extract_underwriting_from_tables
        from edgar.offerings._424b_cover import extract_underwriting_from_text

        doc = self._filing.parse()
        if not doc:
            return None

        # Try table-based extraction first (most reliable)
        table_results = extract_underwriting_from_tables(doc)

        entries: list[UnderwriterEntry] = []
        fee_type = 'underwriting_discount'

        # Prefer allocation tables (have full legal names)
        alloc = [r for r in table_results if r['type'] == 'allocation']
        if alloc:
            for name, amt in zip(alloc[0]['names'], alloc[0].get('allocations', [])):
                entries.append(UnderwriterEntry(name=name, shares_allocated=amt))
        else:
            # Use cover grid or role listing names
            for tr in table_results:
                for name in tr['names']:
                    if not any(e.name == name for e in entries):
                        entries.append(UnderwriterEntry(name=name))

        # Fall back to text-based extraction if no tables found
        if not entries:
            text_results = extract_underwriting_from_text(self._filing)
            for tx in text_results:
                for name in tx['names']:
                    if not any(e.name == name for e in entries):
                        entries.append(UnderwriterEntry(name=name))
                if tx['role'] in ('sole_placement_agent', 'placement_agent'):
                    fee_type = 'placement_agent_fees'

        if not entries:
            return None

        # Detect fee type from pricing table if available
        if self.pricing and self.pricing.fee_type:
            fee_type = self.pricing.fee_type

        return UnderwritingInfo(
            underwriters=entries,
            fee_type=fee_type,
        )

    @cached_property
    def filing_fees(self) -> FilingFeesData:
        """Filing fees XBRL data. Returns empty until Phase 4."""
        return FilingFeesData()

    # ------------------------------------------------------------------
    # Rich display
    # ------------------------------------------------------------------

    @cached_property
    def _cover_table(self) -> Table:
        cp = self._cover_page
        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        t.add_column("field", style="bold deep_sky_blue1", min_width=22)
        t.add_column("value")

        t.add_row("Form", self.form)
        t.add_row("Offering Type", self._offering_type.display_name)
        if cp.security_description:
            t.add_row("Security", cp.security_description[:100])
        if cp.offering_amount:
            t.add_row("Offering Amount", cp.offering_amount)
        if cp.offering_price:
            t.add_row("Offering Price", cp.offering_price)
        if cp.exchange_ticker:
            t.add_row("Ticker", cp.exchange_ticker)
        if cp.registration_number:
            t.add_row("Registration No.", cp.registration_number)
        if cp.base_prospectus_date:
            t.add_row("Base Prospectus", f"To Prospectus dated {cp.base_prospectus_date}")

        flags = []
        if cp.is_atm:
            flags.append("[green]ATM[/green]")
        if cp.is_preliminary:
            flags.append("[yellow]PRELIMINARY[/yellow]")
        if cp.is_supplement:
            flags.append("Supplement")
        if self.is_amendment:
            flags.append("[red]AMENDMENT[/red]")
        if flags:
            t.add_row("Status", " | ".join(flags))

        return t

    @cached_property
    def _pricing_table(self) -> Optional[Table]:
        """Rich Table for pricing data, or None if not available."""
        if not self.pricing or not self.pricing.columns:
            return None
        t = Table(box=box.SIMPLE, padding=(0, 1), title="Pricing")
        t.add_column("", style="bold")
        for col in self.pricing.columns:
            t.add_column(col.column_label or "Value", justify="right", style="deep_sky_blue1")
        if any(c.offering_price for c in self.pricing.columns):
            t.add_row("Offering Price", *[c.offering_price or "" for c in self.pricing.columns])
        if any(c.fee_or_discount for c in self.pricing.columns):
            fee_label = self.pricing.fee_type or "Fee"
            fee_label = fee_label.replace('_', ' ').title()
            t.add_row(fee_label, *[c.fee_or_discount or "" for c in self.pricing.columns])
        if any(c.proceeds for c in self.pricing.columns):
            t.add_row("Proceeds", *[c.proceeds or "" for c in self.pricing.columns])
        return t

    @cached_property
    def _underwriting_table(self) -> Optional[Table]:
        """Rich Table for underwriting info."""
        uw = self.underwriting
        if not uw or not uw.underwriters:
            return None
        t = Table(box=box.SIMPLE, padding=(0, 1), title="Underwriting")
        t.add_column("Name", style="bold")
        t.add_column("Allocation", justify="right", style="deep_sky_blue1")
        for entry in uw.underwriters[:10]:
            t.add_row(entry.name, entry.shares_allocated or "")
        if len(uw.underwriters) > 10:
            t.add_row(f"... +{len(uw.underwriters) - 10} more", "")
        return t

    def __rich__(self):
        title = f"{self.company}  {self.filing_date}"
        subtitle = f"{self.form}  {self._offering_type.display_name}"

        renderables = [self._cover_table]

        pt = self._pricing_table
        if pt is not None:
            renderables.append(Text(""))
            renderables.append(pt)

        ut = self._underwriting_table
        if ut is not None:
            renderables.append(Text(""))
            renderables.append(ut)

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
            f"Prospectus424B("
            f"form={self.form!r}, "
            f"company={self.company!r}, "
            f"offering_type={self._offering_type.value!r}, "
            f"date={self.filing_date!r})"
        )
