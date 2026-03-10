"""
424B* Prospectus Parser.

Handles all 424B form variants (424B1 through 424B8) including amendments (/A).
Phase 1: Cover page extraction + offering type classification + obj() dispatch.
"""

from __future__ import annotations

import logging
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

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from edgar._filings import Filing, Filings

__all__ = ['Prospectus424B', 'ShelfLifecycle', 'Deal', 'OfferingType', 'CoverPageData',
           'SellingStockholdersData', 'SellingStockholderEntry']

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
    """A single row from a selling stockholders table.

    Raw string values are preserved as-is from the filing.
    Use the numeric properties (shares_before, shares_offered, etc.) for parsed int/float values.
    """
    name: str
    shares_before_offering: Optional[str] = None
    pct_before_offering: Optional[str] = None
    shares_offered: Optional[str] = None
    shares_after_offering: Optional[str] = None
    pct_after_offering: Optional[str] = None
    warrants_or_convertible: Optional[str] = None

    # --- Numeric properties (return None on parse failure) ---

    @property
    def shares_before(self) -> Optional[int]:
        return _parse_sec_int(self.shares_before_offering)

    @property
    def shares(self) -> Optional[int]:
        return _parse_sec_int(self.shares_offered)

    @property
    def shares_after(self) -> Optional[int]:
        return _parse_sec_int(self.shares_after_offering)

    @property
    def pct_before(self) -> Optional[float]:
        return _parse_sec_number(self.pct_before_offering)

    @property
    def pct_after(self) -> Optional[float]:
        return _parse_sec_number(self.pct_after_offering)

    @property
    def warrants(self) -> Optional[int]:
        return _parse_sec_int(self.warrants_or_convertible)


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

    def to_dataframe(self):
        """Convert selling stockholders to a pandas DataFrame with numeric columns."""
        import pandas as pd
        rows = []
        for entry in self.stockholders:
            rows.append({
                'name': entry.name,
                'shares_before': entry.shares_before,
                'pct_before': entry.pct_before,
                'shares_offered': entry.shares,
                'shares_after': entry.shares_after,
                'pct_after': entry.pct_after,
                'warrants': entry.warrants,
            })
        return pd.DataFrame(rows)


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
_SHELF_BASE_FORMS = {'S-3', 'S-3ASR', 'F-3', 'F-3ASR', 'S-1'}
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
    def filing(self) -> 'Filing':
        """The current 424B filing this lifecycle was computed from."""
        return self._current

    @property
    def filings(self) -> 'Filings':
        """The full set of related filings under this shelf."""
        return self._related

    @cached_property
    def shelf_registration(self) -> Optional['Filing']:
        """The S-3/F-3/S-1 filing that initiated this shelf."""
        for f in self._related:
            base_form = f.form.replace('/A', '')
            if base_form in _SHELF_BASE_FORMS:
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
            elif remaining is not None and remaining == 0:
                summary.add_row("Shelf Expires", f"{exp} (expires today)")
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

            if base_form in _SHELF_BASE_FORMS:
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

    # ------------------------------------------------------------------
    # AI context
    # ------------------------------------------------------------------

    def to_context(self, detail: str = 'standard') -> str:
        """Returns AI-optimized shelf lifecycle context for language models.

        Args:
            detail: Level of detail - 'minimal', 'standard', or 'full'

        Returns:
            Markdown-KV formatted context string optimized for LLMs
        """
        lines = []
        lines.append(f"SHELF LIFECYCLE: {self._current.company}")
        lines.append("")

        reg = self.shelf_registration
        if reg:
            lines.append(f"Shelf Registration: {reg.form} filed {reg.filing_date}")
        if self.effective_date:
            review = f" ({self.review_period_days} days review)" if self.review_period_days is not None else ""
            lines.append(f"Effective Date: {self.effective_date}{review}")
        if self.shelf_expires:
            remaining = self.days_to_expiry
            if remaining is not None and remaining > 0:
                lines.append(f"Shelf Expires: {self.shelf_expires} ({remaining} days remaining)")
            elif remaining is not None and remaining == 0:
                lines.append(f"Shelf Expires: {self.shelf_expires} (expires today)")
            elif remaining is not None:
                lines.append(f"Shelf Expires: {self.shelf_expires} (EXPIRED)")

        td_num = self.takedown_number
        if td_num is not None:
            latest = " (latest)" if self.is_latest_takedown else ""
            lines.append(f"Takedown Position: #{td_num} of {self.total_takedowns}{latest}")

        avg = self.avg_days_between_takedowns
        if avg is not None:
            lines.append(f"Avg Cadence: {avg:.0f} days between takedowns")

        if detail in ('standard', 'full'):
            lines.append("")
            lines.append("TIMELINE:")
            takedown_idx = 0
            for f in self._related:
                base_form = f.form.replace('/A', '')
                is_current = f.accession_no == self._current.accession_no
                marker = " << current" if is_current else ""

                if base_form in _SHELF_BASE_FORMS:
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

                lines.append(f"  {f.form:10s} {f.filing_date}  {desc}{marker}")

        if detail == 'full':
            lines.append("")
            lines.append("AVAILABLE ACTIONS:")
            lines.append("  - .shelf_registration -> Filing object for the S-3/F-3/S-1")
            lines.append("  - .takedowns -> list of all 424B* takedown Filing objects")
            lines.append("  - .filings -> full Filings set under this shelf")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Number parsing helper
# ---------------------------------------------------------------------------

def _parse_sec_number(val: Optional[str]) -> Optional[float]:
    """Parse SEC-style numeric strings into float.

    Handles: '$1,234,567', '1,234,567', '10.5 million', '(0.45)', '3.5%'
    Returns None on failure or empty input.
    """
    if not val or not isinstance(val, str):
        return None
    s = val.strip()
    if not s:
        return None
    # Skip non-numeric sentinel values
    lower = s.lower()
    if lower in ('-', 'n/a', 'none') or lower.startswith(('at', 'exchange', 'preliminary', 'market')):
        return None
    # Strip currency symbol and commas
    s = s.replace('$', '').replace(',', '').strip()
    # Handle parenthetical negatives: (123) → -123
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1].strip()
    # Strip trailing %
    s = s.rstrip('%').strip()
    if not s:
        return None
    # Handle multiplier words
    lower = s.lower()
    multipliers = {'million': 1_000_000, 'billion': 1_000_000_000}
    for word, mult in multipliers.items():
        if lower.endswith(word):
            num_part = lower[:len(lower) - len(word)].strip()
            try:
                return float(num_part) * mult
            except ValueError:
                return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_sec_int(val: Optional[str]) -> Optional[int]:
    """Parse SEC-style numeric string to int, rounding if needed."""
    f = _parse_sec_number(val)
    if f is None:
        return None
    return round(f)


# ---------------------------------------------------------------------------
# Deal — normalized deal summary
# ---------------------------------------------------------------------------

class Deal:
    """Normalized, computed deal summary synthesized from a 424B prospectus.

    All numeric properties return None when data is unavailable or unparseable.
    Triangulates across cover_page, pricing, offering_terms, underwriting, and
    dilution sub-objects to produce the most reliable values.

    Usage:
        prospectus = filing.obj()  # Prospectus424B
        deal = prospectus.deal
        deal.price           # 2.48
        deal.shares          # 1500000
        deal.gross_proceeds  # 3720000.0
    """

    def __init__(self, prospectus: 'Prospectus424B'):
        self._prospectus = prospectus

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @cached_property
    def _pricing_per_unit(self) -> Optional['PricingColumnData']:
        """First (per-unit) column from pricing table."""
        p = self._prospectus.pricing
        if p and p.columns:
            return p.columns[0]
        return None

    @cached_property
    def _pricing_total(self) -> Optional['PricingColumnData']:
        """Last (total) column from pricing table, only if >1 column."""
        p = self._prospectus.pricing
        if p and len(p.columns) > 1:
            return p.columns[-1]
        return None

    # ------------------------------------------------------------------
    # Core deal terms
    # ------------------------------------------------------------------

    @cached_property
    def price(self) -> Optional[float]:
        """Per-unit offering price."""
        # 1. Cover page (most reliable for clean per-share price)
        val = self._prospectus.cover_page.offering_price_float
        if val is not None and val > 0:
            return val
        # 2. Pricing table per-unit column
        pu = self._pricing_per_unit
        if pu and pu.offering_price:
            val = _parse_sec_number(pu.offering_price)
            if val is not None and val > 0:
                return val
        return None

    @cached_property
    def shares(self) -> Optional[int]:
        """Number of shares offered."""
        # 1. Offering terms
        ot = self._prospectus.offering_terms
        if ot and ot.shares_offered:
            val = _parse_sec_int(ot.shares_offered)
            if val is not None and val > 0:
                return val
        # 2. Compute from gross_proceeds / price (avoid recursion via _raw_gross)
        raw_gross = self._raw_gross_proceeds
        if raw_gross is not None and raw_gross > 0 and self.price and self.price > 0:
            return round(raw_gross / self.price)
        return None

    @cached_property
    def _raw_gross_proceeds(self) -> Optional[float]:
        """Gross proceeds without using shares (avoids circular dependency)."""
        # 1. Cover page total amount
        val = self._prospectus.cover_page.offering_amount_float
        if val is not None and val > 0:
            return val
        # 2. Pricing table total column - offering price field (aggregate amount)
        tot = self._pricing_total
        if tot and tot.offering_price:
            val = _parse_sec_number(tot.offering_price)
            if val is not None and val > 0:
                return val
        return None

    @cached_property
    def gross_proceeds(self) -> Optional[float]:
        """Total offering amount (gross, before fees)."""
        # 1-2: Cover page and pricing table total
        val = self._raw_gross_proceeds
        if val is not None:
            return val
        # 3. Compute: shares × price
        if self.shares and self.price:
            return self.shares * self.price
        return None

    @cached_property
    def net_proceeds(self) -> Optional[float]:
        """Proceeds after underwriting fees/discounts."""
        # 1. Pricing table total column - proceeds field
        tot = self._pricing_total
        if tot and tot.proceeds:
            val = _parse_sec_number(tot.proceeds)
            if val is not None:
                return val
        # 2. Compute: gross - total_fees
        if self.gross_proceeds is not None and self.total_fees is not None:
            return self.gross_proceeds - self.total_fees
        return None

    @cached_property
    def security_type(self) -> Optional[str]:
        """Security description from cover page."""
        return self._prospectus.cover_page.security_description

    @cached_property
    def offering_type(self) -> OfferingType:
        """Offering type classification."""
        return self._prospectus.offering_type

    @cached_property
    def is_atm(self) -> bool:
        """Whether this is an at-the-market offering."""
        return self._prospectus.is_atm

    # ------------------------------------------------------------------
    # Underwriting economics
    # ------------------------------------------------------------------

    @cached_property
    def fee_per_share(self) -> Optional[float]:
        """Per-unit underwriting discount or placement agent fee."""
        pu = self._pricing_per_unit
        if pu and pu.fee_or_discount:
            return _parse_sec_number(pu.fee_or_discount)
        return None

    @cached_property
    def total_fees(self) -> Optional[float]:
        """Total underwriting fees."""
        # 1. Pricing table total column fee field
        tot = self._pricing_total
        if tot and tot.fee_or_discount:
            val = _parse_sec_number(tot.fee_or_discount)
            if val is not None:
                return val
        # 2. Compute: fee_per_share × shares
        if self.fee_per_share is not None and self.shares:
            return self.fee_per_share * self.shares
        return None

    @cached_property
    def discount_rate(self) -> Optional[float]:
        """Fee as fraction of price (e.g. 0.03 for 3%)."""
        if self.fee_per_share is not None and self.price and self.price > 0:
            return self.fee_per_share / self.price
        return None

    @cached_property
    def fee_type(self) -> Optional[str]:
        """'underwriting_discount' or 'placement_agent_fees'."""
        uw = self._prospectus.underwriting
        if uw:
            return uw.fee_type
        p = self._prospectus.pricing
        if p and p.fee_type:
            return p.fee_type
        return None

    @cached_property
    def lead_bookrunner(self) -> Optional[str]:
        """Lead underwriter or placement agent name."""
        uw = self._prospectus.underwriting
        return uw.lead_manager if uw else None

    @cached_property
    def underwriter_count(self) -> int:
        """Number of underwriters/agents in the syndicate."""
        uw = self._prospectus.underwriting
        return len(uw.underwriters) if uw else 0

    # ------------------------------------------------------------------
    # Dilution
    # ------------------------------------------------------------------

    @cached_property
    def dilution_per_share(self) -> Optional[float]:
        """Dilution per share to new investors."""
        d = self._prospectus.dilution
        return _parse_sec_number(d.dilution_per_share) if d else None

    @cached_property
    def dilution_pct(self) -> Optional[float]:
        """Dilution percentage."""
        d = self._prospectus.dilution
        return _parse_sec_number(d.dilution_percentage) if d else None

    @cached_property
    def shares_before(self) -> Optional[int]:
        """Shares outstanding before offering."""
        d = self._prospectus.dilution
        return _parse_sec_int(d.shares_outstanding_before) if d else None

    @cached_property
    def shares_after(self) -> Optional[int]:
        """Shares outstanding after offering."""
        d = self._prospectus.dilution
        return _parse_sec_int(d.shares_outstanding_after) if d else None

    @cached_property
    def ntbv_before(self) -> Optional[float]:
        """Net tangible book value per share before offering."""
        d = self._prospectus.dilution
        return _parse_sec_number(d.ntbv_before_offering) if d else None

    @cached_property
    def ntbv_after(self) -> Optional[float]:
        """Net tangible book value per share after offering."""
        d = self._prospectus.dilution
        return _parse_sec_number(d.ntbv_after_offering) if d else None

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """All non-None computed values as a flat dict."""
        fields = [
            'price', 'shares', 'gross_proceeds', 'net_proceeds',
            'security_type', 'offering_type', 'is_atm',
            'fee_per_share', 'total_fees', 'discount_rate', 'fee_type',
            'lead_bookrunner', 'underwriter_count',
            'dilution_per_share', 'dilution_pct',
            'shares_before', 'shares_after', 'ntbv_before', 'ntbv_after',
        ]
        result = {}
        for name in fields:
            val = getattr(self, name)
            if val is not None:
                # Convert enums to string
                if isinstance(val, OfferingType):
                    val = val.value
                result[name] = val
        return result

    def to_context(self, detail: str = 'standard') -> str:
        """Markdown-KV formatted deal summary for LLM consumption."""
        lines = [f"DEAL SUMMARY: {self._prospectus.company}"]
        lines.append("")

        lines.append(f"Offering Type: {self.offering_type.display_name}")
        if self.security_type:
            lines.append(f"Security: {self.security_type[:100]}")
        if self.is_atm:
            lines.append("ATM: Yes")
        if self.price is not None:
            lines.append(f"Price: ${self.price:,.4f}" if self.price < 1 else f"Price: ${self.price:,.2f}")
        if self.shares is not None:
            lines.append(f"Shares: {self.shares:,}")
        if self.gross_proceeds is not None:
            lines.append(f"Gross Proceeds: ${self.gross_proceeds:,.2f}")
        if self.net_proceeds is not None:
            lines.append(f"Net Proceeds: ${self.net_proceeds:,.2f}")

        # Underwriting
        if self.fee_type or self.lead_bookrunner:
            lines.append("")
            if self.fee_type:
                label = self.fee_type.replace('_', ' ').title()
                if self.discount_rate is not None:
                    label += f" ({self.discount_rate:.1%})"
                lines.append(f"Fee Type: {label}")
            if self.lead_bookrunner:
                lines.append(f"Lead: {self.lead_bookrunner}")
            if self.fee_per_share is not None:
                lines.append(f"Fee Per Share: ${self.fee_per_share:,.4f}")
            if self.total_fees is not None:
                lines.append(f"Total Fees: ${self.total_fees:,.2f}")

        # Dilution
        if detail in ('standard', 'full') and self.dilution_per_share is not None:
            lines.append("")
            lines.append(f"Dilution Per Share: ${self.dilution_per_share:,.2f}")
            if self.dilution_pct is not None:
                lines.append(f"Dilution: {self.dilution_pct:.1f}%")
            if self.shares_before is not None:
                lines.append(f"Shares Before: {self.shares_before:,}")
            if self.shares_after is not None:
                lines.append(f"Shares After: {self.shares_after:,}")
            if self.ntbv_before is not None:
                lines.append(f"NTBV Before: ${self.ntbv_before:,.2f}")
            if self.ntbv_after is not None:
                lines.append(f"NTBV After: ${self.ntbv_after:,.2f}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Rich display
    # ------------------------------------------------------------------

    def __rich__(self):
        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        t.add_column("field", style="bold deep_sky_blue1", min_width=22)
        t.add_column("value")

        t.add_row("Offering Type", self.offering_type.display_name)
        if self.security_type:
            t.add_row("Security", self.security_type[:100])
        if self.shares is not None:
            t.add_row("Shares", f"{self.shares:,}")
        if self.price is not None:
            t.add_row("Price", f"${self.price:,.4f}" if self.price < 1 else f"${self.price:,.2f}")
        if self.gross_proceeds is not None:
            t.add_row("Gross Proceeds", f"${self.gross_proceeds:,.2f}")
        if self.net_proceeds is not None:
            t.add_row("Net Proceeds", f"${self.net_proceeds:,.2f}")

        # Underwriting section
        if self.fee_type or self.lead_bookrunner:
            t.add_row("", "")  # spacer
            fee_label = ""
            if self.fee_type:
                fee_label = self.fee_type.replace('_', ' ').title()
                if self.discount_rate is not None:
                    fee_label += f" ({self.discount_rate:.1%})"
            if fee_label:
                t.add_row("Underwriting", fee_label)
            if self.lead_bookrunner:
                t.add_row("Lead", self.lead_bookrunner)

        # Dilution section
        if self.dilution_per_share is not None:
            t.add_row("", "")  # spacer
            dil_str = f"${self.dilution_per_share:,.2f}/share"
            if self.dilution_pct is not None:
                dil_str += f" ({self.dilution_pct:.1f}%)"
            t.add_row("Dilution", dil_str)
            if self.shares_before is not None:
                t.add_row("Shares Before", f"{self.shares_before:,}")
            if self.shares_after is not None:
                t.add_row("Shares After", f"{self.shares_after:,}")

        return Panel(
            t,
            title=f"[bold]Deal: {self._prospectus.company}[/bold]",
            box=box.ROUNDED,
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        parts = [f"Deal(company={self._prospectus.company!r}"]
        if self.price is not None:
            parts.append(f"price={self.price}")
        if self.shares is not None:
            parts.append(f"shares={self.shares}")
        if self.gross_proceeds is not None:
            parts.append(f"gross={self.gross_proceeds}")
        return ", ".join(parts) + ")"


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
                 offering_type: OfferingType, confidence: str,
                 document=None):
        self._filing = filing
        self._cover_page = cover_page
        self._offering_type = offering_type
        self._confidence = confidence
        self._document = document

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

        # Parse once, reuse everywhere
        try:
            document = filing.parse()
        except Exception:
            document = None

        cover_fields = extract_cover_page_fields(filing, document=document)
        cover_page = CoverPageData(**cover_fields)

        classification = classify_offering_type(filing, document=document)
        offering_type = OfferingType(classification.get('type', 'unknown'))
        confidence = classification.get('confidence', 'low')

        return cls(
            filing=filing,
            cover_page=cover_page,
            offering_type=offering_type,
            confidence=confidence,
            document=document,
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
        doc = self._document
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
        Merges all selling stockholder tables found in the filing.
        Returns None if no selling stockholders table is found."""
        from edgar.offerings._424b_tables import extract_selling_stockholders_data
        tables = self._classified_tables.get('selling_stockholders', [])
        if not tables:
            return None
        # Extract from first table
        result = extract_selling_stockholders_data(tables[0])
        # Merge additional tables (e.g. warrants table separate from common shares)
        for extra_table in tables[1:]:
            extra = extract_selling_stockholders_data(extra_table)
            if extra.is_populated:
                result.stockholders.extend(extra.stockholders)
                if extra.total_shares_offered and not result.total_shares_offered:
                    result.total_shares_offered = extra.total_shares_offered
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

        doc = self._document
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
            text_results = extract_underwriting_from_text(self._filing, document=doc)
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
            # Use file_number from cover page (already extracted from SGML header)
            # to skip the redundant accession_number lookup in related_filings().
            # Use trigger_full_load=False to avoid paginating through the entire
            # filing history — shelf registrations expire after 3 years so the
            # relevant filings are almost always in the most recent ~1000.
            file_number = self._cover_page.registration_number
            if file_number:
                from edgar.entity import Company
                company = Company(self._filing.cik)
                related = company.get_filings(
                    file_number=file_number,
                    sort_by=[("filing_date", "ascending"), ("accession_number", "ascending")],
                    trigger_full_load=False,
                )
                if related is not None and not related.empty:
                    return ShelfLifecycle(self._filing, related)
            # Fallback to generic related_filings if no file number on cover page
            related = self._filing.related_filings()
            if related is None or related.empty:
                return None
            return ShelfLifecycle(self._filing, related)
        except Exception as e:
            log.debug("ShelfLifecycle construction failed for %s: %s", self._filing.accession_no, e)
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
    # Deal summary
    # ------------------------------------------------------------------

    @cached_property
    def deal(self) -> 'Deal':
        """Normalized deal summary with computed metrics.

        Always returns a Deal object (never None). Individual fields
        within it are None when data is unavailable.
        """
        return Deal(self)

    # ------------------------------------------------------------------
    # AI context
    # ------------------------------------------------------------------

    def to_context(self, detail: str = 'standard') -> str:
        """Returns AI-optimized prospectus context for language models.

        Args:
            detail: Level of detail - 'minimal', 'standard', or 'full'

        Returns:
            Markdown-KV formatted context string optimized for LLMs
        """
        cp = self._cover_page
        lines = []

        lines.append(f"PROSPECTUS: {self.company} ({self.form})")
        lines.append("")
        lines.append(f"Filed: {self.filing_date}")
        lines.append(f"Offering Type: {self._offering_type.display_name}")

        if cp.security_description:
            lines.append(f"Security: {cp.security_description[:100]}")
        if cp.offering_amount:
            lines.append(f"Offering Amount: {cp.offering_amount}")
        if cp.offering_price:
            lines.append(f"Offering Price: {cp.offering_price}")
        if cp.exchange_ticker:
            lines.append(f"Ticker: {cp.exchange_ticker}")
        if cp.registration_number:
            lines.append(f"Registration No.: {cp.registration_number}")

        flags = []
        if cp.is_atm:
            flags.append("ATM")
        if cp.is_preliminary:
            flags.append("PRELIMINARY")
        if cp.is_supplement:
            flags.append("Supplement")
        if self.is_amendment:
            flags.append("AMENDMENT")
        if flags:
            lines.append(f"Status: {' | '.join(flags)}")

        if detail == 'minimal':
            return "\n".join(lines)

        # Standard: add pricing and underwriting summaries
        if self.pricing and self.pricing.columns:
            lines.append("")
            lines.append("PRICING:")
            for col in self.pricing.columns:
                label = col.column_label or "Value"
                parts = []
                if col.offering_price:
                    parts.append(f"Price: {col.offering_price}")
                if col.proceeds:
                    parts.append(f"Proceeds: {col.proceeds}")
                if parts:
                    lines.append(f"  {label}: {', '.join(parts)}")

        uw = self.underwriting
        if uw and uw.underwriters:
            lines.append("")
            lines.append(f"UNDERWRITING ({uw.fee_type.replace('_', ' ').title()}):")
            for entry in uw.underwriters[:5]:
                lines.append(f"  - {entry.name}")
            if len(uw.underwriters) > 5:
                lines.append(f"  ... +{len(uw.underwriters) - 5} more")

        lc = self.lifecycle
        if lc:
            lines.append("")
            td_num = lc.takedown_number
            if td_num is not None:
                latest = " (latest)" if lc.is_latest_takedown else ""
                lines.append(f"Shelf Position: Takedown #{td_num} of {lc.total_takedowns}{latest}")
            if lc.shelf_expires:
                remaining = lc.days_to_expiry
                if remaining is not None and remaining > 0:
                    lines.append(f"Shelf Expires: {lc.shelf_expires} ({remaining} days remaining)")
                elif remaining is not None:
                    lines.append(f"Shelf Expires: {lc.shelf_expires} (EXPIRED)")

        if detail == 'full':
            lines.append("")
            lines.append("AVAILABLE ACTIONS:")
            lines.append("  - .cover_page -> CoverPageData with all extracted fields")
            lines.append("  - .pricing -> PricingData (offering price, fee, proceeds)")
            lines.append("  - .underwriting -> UnderwritingInfo (syndicate details)")
            lines.append("  - .offering_terms -> OfferingTerms (shares, warrants, use of proceeds)")
            lines.append("  - .selling_stockholders -> SellingStockholdersData")
            lines.append("  - .structured_note_terms -> StructuredNoteTerms (for 424B2)")
            lines.append("  - .dilution -> DilutionData")
            lines.append("  - .capitalization -> CapitalizationData")
            lines.append("  - .filing_fees -> FilingFeesData (from XBRL exhibit)")
            lines.append("  - .lifecycle -> ShelfLifecycle (takedown position, expiry, timeline)")

        return "\n".join(lines)

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
