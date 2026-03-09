"""
424B* Prospectus Parser.

Handles all 424B form variants (424B1 through 424B8) including amendments (/A).
Phase 1: Cover page extraction + offering type classification + obj() dispatch.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
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
    from edgar._filings import Filing, Filings

__all__ = ['Prospectus424B', 'ShelfLifecycle', 'OfferingType', 'CoverPageData']

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
            multipliers = {'million': 1_000_000, 'billion': 1_000_000_000}
            for word, mult in multipliers.items():
                if clean.lower().endswith(word):
                    return float(clean[:len(clean) - len(word)].strip()) * mult
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
# Shelf Lifecycle
# ---------------------------------------------------------------------------

# Registration forms that start a shelf
_SHELF_FORMS = {'S-3', 'S-3ASR', 'F-3', 'F-3ASR', 'S-1', 'S-1/A', 'S-3/A', 'F-3/A'}
_TAKEDOWN_FORMS = {'424B1', '424B2', '424B3', '424B4', '424B5', '424B7', '424B8'}


def _parse_filing_date(d) -> Optional[date]:
    """Parse a filing date string or date to a date object."""
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        try:
            return date.fromisoformat(d)
        except (ValueError, TypeError):
            return None
    return None


class ShelfLifecycle:
    """Lifecycle position and insights for a 424B filing within its shelf registration.

    Computes actionable insights from the related filings returned by
    Filing.related_filings(): shelf registration date, SEC review period,
    shelf expiration, takedown position, offering cadence, and a timeline.

    Usage:
        prospectus = filing.obj()  # Prospectus424B
        lc = prospectus.lifecycle
        lc.takedown_number       # e.g. 5
        lc.total_takedowns       # e.g. 5
        lc.shelf_expires         # e.g. date(2026, 8, 2)
        lc.avg_days_between_takedowns  # e.g. 228.0
    """

    def __init__(self, current_filing: 'Filing', related: 'Filings'):
        self._current = current_filing
        self._related = related

    # ------------------------------------------------------------------
    # Core properties
    # ------------------------------------------------------------------

    @property
    def filings(self) -> 'Filings':
        """The full set of related filings under this shelf."""
        return self._related

    @cached_property
    def shelf_registration(self) -> Optional['Filing']:
        """The S-3/F-3/S-1 filing that initiated this shelf."""
        for f in self._related:
            base_form = f.form.replace('/A', '')
            if base_form in ('S-3', 'S-3ASR', 'F-3', 'F-3ASR', 'S-1'):
                return f
        return None

    @cached_property
    def _effective_filing(self) -> Optional['Filing']:
        """The EFFECT filing that declared the shelf effective."""
        for f in self._related:
            if f.form == 'EFFECT':
                return f
        return None

    @cached_property
    def shelf_filed_date(self) -> Optional[str]:
        """Date the shelf registration was filed (string)."""
        reg = self.shelf_registration
        return str(reg.filing_date) if reg else None

    @cached_property
    def effective_date(self) -> Optional[str]:
        """Date the shelf was declared effective (string)."""
        eff = self._effective_filing
        return str(eff.filing_date) if eff else None

    @cached_property
    def shelf_expires(self) -> Optional[date]:
        """Expiration date of the shelf (filed date + 3 years)."""
        if not self.shelf_filed_date:
            return None
        filed = _parse_filing_date(self.shelf_filed_date)
        if not filed:
            return None
        try:
            return filed.replace(year=filed.year + 3)
        except ValueError:
            # Feb 29 -> Feb 28
            return filed.replace(year=filed.year + 3, day=filed.day - 1)

    @cached_property
    def days_to_expiry(self) -> Optional[int]:
        """Days remaining until the shelf expires. Negative if expired."""
        exp = self.shelf_expires
        if not exp:
            return None
        return (exp - date.today()).days

    @cached_property
    def review_period_days(self) -> Optional[int]:
        """Days between shelf filing (S-3) and declared effective (EFFECT)."""
        if not self.shelf_filed_date or not self.effective_date:
            return None
        filed = _parse_filing_date(self.shelf_filed_date)
        eff = _parse_filing_date(self.effective_date)
        if filed and eff:
            return (eff - filed).days
        return None

    @cached_property
    def takedowns(self) -> List['Filing']:
        """All 424B* takedown filings, in chronological order."""
        result = []
        for f in self._related:
            base_form = f.form.replace('/A', '')
            if base_form in _TAKEDOWN_FORMS:
                result.append(f)
        return result

    @cached_property
    def total_takedowns(self) -> int:
        """Total number of takedowns under this shelf."""
        return len(self.takedowns)

    @cached_property
    def takedown_number(self) -> Optional[int]:
        """1-based position of the current filing among takedowns."""
        for i, f in enumerate(self.takedowns, 1):
            if f.accession_no == self._current.accession_no:
                return i
        return None

    @cached_property
    def is_latest_takedown(self) -> bool:
        """Whether the current filing is the most recent takedown."""
        return self.takedown_number == self.total_takedowns

    @cached_property
    def avg_days_between_takedowns(self) -> Optional[float]:
        """Average days between consecutive takedowns."""
        if len(self.takedowns) < 2:
            return None
        dates = []
        for f in self.takedowns:
            d = _parse_filing_date(f.filing_date)
            if d:
                dates.append(d)
        if len(dates) < 2:
            return None
        gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        return sum(gaps) / len(gaps)

    @cached_property
    def related_8k(self) -> Optional['Filing']:
        """8-K filed on the same day as the current filing, if any."""
        for f in self._related:
            if f.form == '8-K' and str(f.filing_date) == str(self._current.filing_date):
                return f
        return None

    # ------------------------------------------------------------------
    # Rich display
    # ------------------------------------------------------------------

    def __rich__(self):
        company_name = self._current.company

        # Summary table
        summary = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        summary.add_column("field", style="bold deep_sky_blue1", min_width=24)
        summary.add_column("value")

        reg = self.shelf_registration
        if reg:
            summary.add_row("Shelf Registration", f"{reg.form} filed {reg.filing_date}")

        eff = self._effective_filing
        if eff:
            review = f" ({self.review_period_days} days review)" if self.review_period_days is not None else ""
            summary.add_row("Effective Date", f"{eff.filing_date}{review}")

        exp = self.shelf_expires
        if exp:
            remaining = self.days_to_expiry
            if remaining is not None and remaining > 0:
                summary.add_row("Shelf Expires", f"{exp} ({remaining} days remaining)")
            elif remaining is not None:
                summary.add_row("Shelf Expires", f"{exp} (EXPIRED)")
            else:
                summary.add_row("Shelf Expires", str(exp))

        td_num = self.takedown_number
        if td_num is not None:
            latest = " (latest)" if self.is_latest_takedown else ""
            summary.add_row("Takedown Position", f"#{td_num} of {self.total_takedowns}{latest}")

        avg = self.avg_days_between_takedowns
        if avg is not None:
            summary.add_row("Avg Cadence", f"{avg:.0f} days between takedowns")

        # Timeline table
        timeline = Table(box=box.SIMPLE, padding=(0, 1))
        timeline.add_column("#", style="dim", justify="right")
        timeline.add_column("Form", style="bold")
        timeline.add_column("Date")
        timeline.add_column("Description")

        takedown_idx = 0
        for i, f in enumerate(self._related, 1):
            base_form = f.form.replace('/A', '')
            is_current = f.accession_no == self._current.accession_no

            if base_form in ('S-3', 'S-3ASR', 'F-3', 'F-3ASR', 'S-1'):
                desc = "Shelf registration"
            elif f.form == 'EFFECT':
                desc = "Declared effective"
            elif base_form in _TAKEDOWN_FORMS:
                takedown_idx += 1
                desc = f"Takedown #{takedown_idx}"
            elif f.form == '8-K':
                desc = "Current report"
            else:
                desc = ""

            marker = "  << current" if is_current else ""
            style = "bold green" if is_current else None
            timeline.add_row(str(i), f.form, str(f.filing_date), f"{desc}{marker}", style=style)

        return Panel(
            Group(summary, Text(""), timeline),
            title=f"[bold]Shelf Lifecycle: {company_name}[/bold]",
            box=box.ROUNDED,
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        td = self.takedown_number
        pos = f"#{td}/{self.total_takedowns}" if td else "?"
        return f"ShelfLifecycle(takedown={pos}, takedowns={self.total_takedowns})"


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
        """Filing fees from EX-FILING FEES XBRL exhibit.
        Available for ~43% of 424B2, ~23% of 424B5. Returns empty if no exhibit."""
        from edgar.offerings._424b_xbrl import extract_filing_fees_xbrl

        data = extract_filing_fees_xbrl(self._filing)
        if not data.get('has_exhibit'):
            return FilingFeesData()

        rows = []
        for row in data.get('offering_rows', []):
            rows.append(FilingFeesRow(
                security_type=row.get('security_type'),
                security_title=row.get('security_title'),
                max_aggregate_offering_price=row.get('max_aggregate_offering_price'),
                fee_rate=row.get('fee_rate'),
                fee_amount=row.get('fee_amount'),
                fee_rule=row.get('fee_rule'),
            ))

        return FilingFeesData(
            has_exhibit=True,
            exhibit_url=data.get('exhibit_url'),
            form_type=data.get('form_type'),
            registration_file_number=data.get('registration_file_number'),
            total_offering_amount=data.get('total_offering_amount'),
            total_fee_amount=data.get('total_fee_amount'),
            offering_rows=rows,
            is_final_prospectus=data.get('is_final_prospectus', True),
        )

    # ------------------------------------------------------------------
    # Lifecycle navigation
    # ------------------------------------------------------------------

    @cached_property
    def lifecycle(self) -> Optional[ShelfLifecycle]:
        """Shelf lifecycle position and insights.

        Returns a ShelfLifecycle object with takedown position, shelf expiry,
        review period, cadence analysis, and a Rich timeline display.
        Returns None if related filings cannot be determined.
        """
        try:
            related = self._filing.related_filings()
            if related is None or related.empty:
                return None
            return ShelfLifecycle(self._filing, related)
        except Exception:
            return None

    @cached_property
    def shelf_registration(self) -> Optional['Filing']:
        """The shelf registration filing (S-3, F-3, S-1). Delegates to lifecycle."""
        lc = self.lifecycle
        return lc.shelf_registration if lc else None

    @cached_property
    def related_filings(self):
        """All filings under the same shelf file number. Delegates to lifecycle."""
        lc = self.lifecycle
        return lc.filings if lc else None

    @cached_property
    def related_8k(self) -> Optional['Filing']:
        """8-K filed on the same day. Delegates to lifecycle."""
        lc = self.lifecycle
        return lc.related_8k if lc else None

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
