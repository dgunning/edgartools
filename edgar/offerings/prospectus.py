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
    IPO = "ipo"
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
            "ipo": "IPO",
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
            OfferingType.IPO,
            OfferingType.ATM,
            OfferingType.BEST_EFFORTS,
            OfferingType.PIPE_RESALE,
            OfferingType.RIGHTS_OFFERING,
        )

    @property
    def has_fixed_price(self) -> bool:
        return self in (
            OfferingType.FIRM_COMMITMENT,
            OfferingType.IPO,
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


def _build_filing_fees_data(data: Optional[dict]) -> FilingFeesData:
    """Convert a raw extract_filing_fees_xbrl dict into a FilingFeesData."""
    if not data or not data.get('has_exhibit'):
        return FilingFeesData()
    rows = [
        FilingFeesRow(
            security_type=row.get('security_type'),
            security_title=row.get('security_title'),
            max_aggregate_offering_price=row.get('max_aggregate_offering_price'),
            fee_rate=row.get('fee_rate'),
            fee_amount=row.get('fee_amount'),
            fee_rule=row.get('fee_rule'),
        )
        for row in data.get('offering_rows', [])
    ]
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


# ---------------------------------------------------------------------------
# Registration Fee Table (S-3 / F-3 / S-1 shelf capacity)
# ---------------------------------------------------------------------------

class FeeTableSecurity(BaseModel):
    """A single security line from a registration fee table (Exhibit 107)."""
    security_type: Optional[str] = None
    security_title: Optional[str] = None
    fee_rule: Optional[str] = None
    amount_registered: Optional[str] = None
    price_per_unit: Optional[float] = None
    max_aggregate_amount: Optional[float] = None
    fee_rate: Optional[float] = None
    fee_amount: Optional[float] = None


class RegistrationFeeTable(BaseModel):
    """Parsed registration fee table from an EX-FILING FEES exhibit (Exhibit 107).

    Provides the total registered offering capacity for a shelf registration
    (S-3, F-3, S-1) and per-security breakdowns.
    """
    total_offering_amount: Optional[float] = None
    net_fee_due: Optional[float] = None
    total_fees_previously_paid: Optional[float] = None
    securities: List[FeeTableSecurity] = []
    carry_forwards: List[FeeTableSecurity] = []
    has_carry_forward: bool = False
    fee_deferred: bool = False
    exhibit_url: Optional[str] = None


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


def _plus_three_years(d: date) -> date:
    """The Rule 415(a)(5) expiry date: three years after ``d``."""
    try:
        return d.replace(year=d.year + 3)
    except ValueError:
        # Feb 29 -> Feb 28
        return d.replace(year=d.year + 3, day=d.day - 1)


_ASR_BASE_FORMS = {'S-3ASR', 'F-3ASR'}
# 'RW' withdraws the registration; 'RW WD' rescinds an earlier 'RW' (the
# registration is then NOT withdrawn). 'AW' withdraws only an amendment, not the
# registration, so it is deliberately excluded.


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
        """The S-3/F-3/S-1 filing that *initiated* this shelf.

        The earliest shelf-base-form filing in the family (selected explicitly by
        filing date, not by ``_related`` ordering). Establishes the shelf's vintage;
        for the date the expiry clock currently runs from, see
        :attr:`current_effective_date`.
        """
        candidates = [f for f in self._related
                      if f.form.replace('/A', '') in _SHELF_BASE_FORMS]
        return min(candidates, key=lambda f: f.filing_date) if candidates else None

    @cached_property
    def _initial_effective_filing(self) -> Optional['Filing']:
        """The EFFECT filing that *first* declared the shelf effective (earliest)."""
        effects = [f for f in self._related if f.form == 'EFFECT']
        return min(effects, key=lambda f: f.filing_date) if effects else None

    @cached_property
    def _current_effective_filing(self) -> Optional['Filing']:
        """The filing establishing *current* effectiveness (latest).

        The most recent effectiveness event — an EFFECT notice or an automatic
        (S-3ASR/F-3ASR) shelf filing, whichever is later. Automatic shelves are
        effective on filing and never receive an EFFECT notice, so both kinds are
        considered together; a genuine Rule 415(a)(6) re-registration of either
        kind advances this past cosmetic amendments. Stays consistent with
        :attr:`_generations`.
        """
        candidates = [f for f in self._related
                      if f.form == 'EFFECT'
                      or f.form.replace('/A', '') in _ASR_BASE_FORMS]
        return max(candidates, key=lambda f: f.filing_date) if candidates else None

    @cached_property
    def shelf_filed_date(self) -> Optional[str]:
        """Date the shelf registration was *originally* filed (string)."""
        reg = self.shelf_registration
        return str(reg.filing_date) if reg else None

    @cached_property
    def effective_date(self) -> Optional[str]:
        """Date the shelf *first* became effective (string).

        The original effectiveness; immutable for a given registration statement
        and used to measure the initial SEC review period. For the operative
        effectiveness today (which advances on re-registration), see
        :attr:`current_effective_date`.
        """
        eff = self._initial_effective_filing
        return str(eff.filing_date) if eff else None

    @cached_property
    def current_effective_date(self) -> Optional[str]:
        """Date of the shelf's *current* effectiveness (string).

        The latest EFFECT (or, for automatic shelves, the latest ASR filing).
        This is the date the Rule 415(a)(5) three-year clock currently runs from,
        so a re-registration moves it forward while cosmetic amendments do not.
        Equals :attr:`effective_date` for a shelf that has never been re-registered.
        """
        eff = self._current_effective_filing
        return str(eff.filing_date) if eff else None

    @cached_property
    def shelf_expires(self) -> Optional[date]:
        """Expiration date of the shelf (current effective date + 3 years).

        Anchored on *current* effectiveness per Rule 415(a)(5): a genuine
        415(a)(6) re-registration resets the clock, while a cosmetic POS AM or
        S-3/A does not. Returns None for a shelf that is not yet effective.
        """
        eff = _parse_filing_date(self.current_effective_date)
        return _plus_three_years(eff) if eff else None

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
    # Derived lifecycle signals
    # ------------------------------------------------------------------

    @cached_property
    def _generations(self) -> List[date]:
        """Effective dates of each shelf generation, ascending.

        One entry per effectiveness event: each EFFECT notice, plus each
        automatic (ASR) shelf filing — automatic shelves are effective on
        filing and never receive an EFFECT notice. A re-registration adds a
        generation; this underpins re-registration and continuity detection.
        """
        dates = {_parse_filing_date(f.filing_date)
                 for f in self._related if f.form == 'EFFECT'}
        dates |= {_parse_filing_date(f.filing_date) for f in self._related
                  if f.form.replace('/A', '') in _ASR_BASE_FORMS}
        return sorted(d for d in dates if d is not None)

    @cached_property
    def is_automatic_shelf(self) -> bool:
        """Whether this is an automatic (WKSI) shelf — S-3ASR/F-3ASR.

        Automatic shelves are effective on filing with no SEC review. An
        issuer-class signal: only well-known seasoned issuers may use them.
        """
        return any(f.form.replace('/A', '') in _ASR_BASE_FORMS for f in self._related)

    @cached_property
    def is_effective(self) -> bool:
        """Whether the shelf has been declared effective.

        True if an effectiveness event exists (EFFECT or automatic shelf) OR any
        takedown exists — a takedown proves effectiveness even when the EFFECT
        notice has scrolled out of the recent filing window.
        """
        return bool(self._generations) or self.total_takedowns > 0

    @cached_property
    def is_withdrawn(self) -> bool:
        """Whether the shelf registration has been withdrawn and not rescinded.

        A shelf is withdrawn if it has an 'RW' (Registration Withdrawal) request
        that has not been undone by a later 'RW WD' (withdrawal of that request).
        'AW' (withdrawal of an amendment) does not withdraw the registration.
        """
        rw_dates = [_parse_filing_date(f.filing_date)
                    for f in self._related if f.form == 'RW']
        rw_dates = [d for d in rw_dates if d is not None]
        if not rw_dates:
            return False
        rescind_dates = [_parse_filing_date(f.filing_date)
                         for f in self._related if f.form == 'RW WD']
        rescind_dates = [d for d in rescind_dates if d is not None]
        if not rescind_dates:
            return True
        # Withdrawn only if the latest request is more recent than the latest rescission.
        return max(rw_dates) > max(rescind_dates)

    @cached_property
    def is_re_registered(self) -> bool:
        """Whether the shelf has been re-registered (more than one generation).

        When true, the visible vintage (:attr:`shelf_filed_date`) is not the
        operative document; the operative effectiveness is
        :attr:`current_effective_date`.
        """
        return len(self._generations) > 1

    @cached_property
    def continuity(self) -> Optional[str]:
        """Whether shelf coverage has been continuous across re-registrations.

        ``'continuous'`` when each generation became effective on or before the
        prior generation's expiry (Rule 415(a)(6) renewal — securities and fees
        carry forward, no gap). ``'lapsed'`` when any generation became effective
        only after the prior one expired (a revival after a gap with no shelf
        access). None when there is no effectiveness event. A single generation
        is trivially continuous.
        """
        gens = self._generations
        if not gens:
            return None
        for prev, nxt in zip(gens, gens[1:]):
            if nxt > _plus_three_years(prev):
                return 'lapsed'
        return 'continuous'

    @cached_property
    def has_registration_gap(self) -> bool:
        """Data-quality flag: a generation became effective after the prior expired.

        Within a single file number this should not happen under Rule 415 — it
        usually means a revival (a fresh registration reusing the file number)
        and is worth investigating the filing linkage rather than treating the
        shelf as continuously registered.
        """
        return self.continuity == 'lapsed'

    @cached_property
    def status(self) -> str:
        """Lifecycle status: withdrawn | expired | effective | registered.

        Precedence: a withdrawal is terminal; then an effective shelf past its
        expiry is expired; then effective; otherwise registered (filed but not
        yet effective).
        """
        if self.is_withdrawn:
            return 'withdrawn'
        if self.is_effective:
            exp = self.shelf_expires
            if exp and date.today() > exp:
                return 'expired'
            if exp is None and self.takedowns:
                # Effectiveness proven by a takedown but the EFFECT/ASR date is
                # outside the loaded window, so shelf_expires is unknown. A shelf
                # cannot take down after it expires, so the latest takedown + 3y
                # is a guaranteed upper bound on expiry: past it means expired.
                last_td = _parse_filing_date(self.takedowns[-1].filing_date)
                if last_td and date.today() > _plus_three_years(last_td):
                    return 'expired'
            return 'effective'
        return 'registered'

    @cached_property
    def program_mode(self) -> str:
        """Takedown cadence: 'high_frequency' (> 50 takedowns) else 'standard'."""
        return 'high_frequency' if self.total_takedowns > 50 else 'standard'

    @cached_property
    def days_since_last_takedown(self) -> Optional[int]:
        """Days from the most recent takedown to today. None if no takedowns."""
        if not self.takedowns:
            return None
        last = _parse_filing_date(self.takedowns[-1].filing_date)
        return (date.today() - last).days if last else None

    @cached_property
    def program_age_days(self) -> Optional[int]:
        """Age of the shelf program in days.

        Measured from the *original* effectiveness only when coverage has been
        continuous; for a lapsed/revived shelf it measures from the *current*
        effectiveness, since the original program no longer applies. None when
        not yet effective.
        """
        gens = self._generations
        if not gens:
            return None
        anchor = gens[0] if self.continuity == 'continuous' else gens[-1]
        return (date.today() - anchor).days

    # ------------------------------------------------------------------
    # Shelf capacity
    # ------------------------------------------------------------------

    @cached_property
    def shelf_capacity(self) -> Optional['RegistrationFeeTable']:
        """Fee table from the shelf registration (S-3/F-3/S-1).

        Parses the EX-FILING FEES exhibit on the shelf registration to extract
        the total registered offering amount and per-security breakdowns.
        Returns None if no shelf registration found or no fee exhibit.
        """
        reg = self.shelf_registration
        if not reg:
            return None
        try:
            from edgar.offerings._fee_table import extract_registration_fee_table
            return extract_registration_fee_table(reg)
        except Exception as e:
            log.debug("Failed to extract shelf capacity for %s: %s",
                      self._current.accession_no, e)
            return None

    @cached_property
    def total_offering_capacity(self) -> Optional[float]:
        """Total registered offering amount from the shelf's fee table (dollars)."""
        ft = self.shelf_capacity
        return ft.total_offering_amount if ft else None

    # ------------------------------------------------------------------
    # Rich display
    # ------------------------------------------------------------------

    def __rich__(self):
        company_name = self._current.company

        # Summary table
        summary = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        summary.add_column("field", style="bold deep_sky_blue1", min_width=24)
        summary.add_column("value")

        status_label = self.status.capitalize()
        if self.continuity == 'lapsed':
            status_label += " (re-registered after a gap)"
        elif self.is_re_registered:
            status_label += " (re-registered)"
        summary.add_row("Status", status_label)

        reg = self.shelf_registration
        if reg:
            summary.add_row("Shelf Registration", f"{reg.form} filed {reg.filing_date}")

        eff = self._initial_effective_filing
        if eff:
            review = f" ({self.review_period_days} days review)" if self.review_period_days is not None else ""
            summary.add_row("Effective Date", f"{eff.filing_date}{review}")

        cur = self._current_effective_filing
        if cur and (eff is None or cur.filing_date != eff.filing_date):
            summary.add_row("Current Effective", f"{cur.filing_date} (re-registered)")

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

# Floor below which a derived "deal size" is almost certainly an artifact, not a
# real aggregate: the per-note DENOMINATION (commonly $1,000) bleeding through
# the cover-page regex. Used to suppress those artifacts and to prefer the
# authoritative EX-FILING FEES XBRL total when present.
#
# Calibrated on a random sample (scripts/offerings_bench/calibrate_floor.py):
# the sub-$100k tail of cover-derived sizes is bimodal — ~5% of 424B2 sit at
# exactly $1,000 (artifacts), legitimate deals are all >= $100k, and the
# (1k, 100k] band is empty. $100k sits at the top of that empty gap, so it nulls
# every observed artifact with zero observed collateral damage. (The XBRL total
# recovers the artifact subset that carries a fee exhibit; the rest are nulled.)
_MIN_PLAUSIBLE_DEAL_SIZE = 100_000.0

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

    @staticmethod
    def _plausible(val: Optional[float]) -> bool:
        """True if ``val`` is a plausible aggregate deal size (not an artifact)."""
        return val is not None and val >= _MIN_PLAUSIBLE_DEAL_SIZE

    @cached_property
    def _filing_fees_total(self) -> Optional[float]:
        """Authoritative total offering amount from the EX-FILING FEES XBRL.

        ffd:TtlOfferingAmt is machine-readable and regex-free. It covers exactly
        the 424B2/424B5 debt/note shapes the cover-page and pricing-table text
        paths miss (ATM has no fixed amount; pre-2022 and 424B1/424B4 carry no
        iXBRL exhibit, so this stays None there)."""
        ff = self._prospectus.filing_fees
        if ff and ff.total_offering_amount:
            return _parse_sec_number(ff.total_offering_amount)
        return None

    @cached_property
    def _raw_gross_proceeds(self) -> Optional[float]:
        """Gross proceeds without using shares (avoids circular dependency)."""
        # 1. Cover page total amount (when plausible — suppresses the per-note
        #    denomination artifact, e.g. a $1,000 face value read as deal size).
        val = self._prospectus.cover_page.offering_amount_float
        if self._plausible(val):
            return val
        # 2. Authoritative EX-FILING FEES XBRL total offering amount. Consulted
        #    when the cover regex is missing/implausible; supersedes artifacts.
        val = self._filing_fees_total
        if self._plausible(val):
            return val
        # 3. Pricing table total column - offering price field (aggregate amount)
        tot = self._pricing_total
        if tot and tot.offering_price:
            val = _parse_sec_number(tot.offering_price)
            if self._plausible(val):
                return val
        return None

    @cached_property
    def gross_proceeds(self) -> Optional[float]:
        """Total offering amount (gross, before fees)."""
        # 1-3: Cover page, authoritative XBRL, and pricing table total
        val = self._raw_gross_proceeds
        if val is not None:
            return val
        # 4. Compute: shares × price
        if self.shares and self.price:
            computed = self.shares * self.price
            if self._plausible(computed):
                return computed
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
    def offering_type_confidence(self) -> str:
        """Classifier confidence: 'high' | 'medium' | 'low'."""
        return self._prospectus.offering_type_confidence

    @cached_property
    def offering_type_signals(self) -> List[str]:
        """Classifier provenance signals (incl. 'xbrl_security_type:*' markers).

        Persist alongside offering_type to tier values — e.g. exclude
        low-confidence firm_commitment rows sourced from 'xbrl_security_type:equity'
        before summing gross_proceeds (they can be unlabelled resales)."""
        return self._prospectus.offering_type_signals

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
            'security_type', 'offering_type',
            'offering_type_confidence', 'offering_type_signals', 'is_atm',
            'fee_per_share', 'total_fees', 'discount_rate', 'fee_type',
            'lead_bookrunner', 'underwriter_count',
            'dilution_per_share', 'dilution_pct',
            'shares_before', 'shares_after', 'ntbv_before', 'ntbv_after',
        ]
        result = {}
        for name in fields:
            val = getattr(self, name)
            # Keep empty provenance lists out of the dict, like other None fields.
            if val is None or val == []:
                continue
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
                 document=None, filing_fees: Optional['FilingFeesData'] = None,
                 signals: Optional[List[str]] = None, sub_type: Optional[str] = None):
        self._filing = filing
        self._cover_page = cover_page
        self._offering_type = offering_type
        self._confidence = confidence
        # Classifier provenance — lets consumers tier values by how the type was
        # determined (e.g. exclude low-confidence firm_commitment rows carrying
        # the 'xbrl_security_type:equity' signal, which can be unlabelled resales).
        self._signals = signals or []
        self._sub_type = sub_type
        self._document = document
        # Optionally seeded by from_filing when the fee exhibit was already
        # fetched during classification — avoids a second download.
        self._eager_filing_fees = filing_fees

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

        # First pass: text only (filing_fees=None suppresses the fee-exhibit
        # fetch). Only if the text is inconclusive do we fetch the exhibit once
        # and reuse it for both the classifier's structural fallback and the
        # filing_fees cache below — avoiding a redundant download.
        classification = classify_offering_type(filing, document=document, filing_fees=None)
        eager_filing_fees = None
        if classification.get('type') == 'unknown':
            from edgar.offerings._424b_xbrl import extract_filing_fees_xbrl
            try:
                fees_dict = extract_filing_fees_xbrl(filing)
            except Exception:
                fees_dict = {'has_exhibit': False}
            classification = classify_offering_type(
                filing, document=document, filing_fees=fees_dict)
            eager_filing_fees = _build_filing_fees_data(fees_dict)

        offering_type = OfferingType(classification.get('type', 'unknown'))
        confidence = classification.get('confidence', 'low')

        return cls(
            filing=filing,
            cover_page=cover_page,
            offering_type=offering_type,
            confidence=confidence,
            document=document,
            filing_fees=eager_filing_fees,
            signals=classification.get('signals') or [],
            sub_type=classification.get('sub_type'),
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
    def offering_type_confidence(self) -> str:
        """Classifier confidence in offering_type: 'high' | 'medium' | 'low'."""
        return self._confidence

    @property
    def offering_type_signals(self) -> List[str]:
        """Signals behind the offering_type classification.

        Includes structural-fallback markers such as 'xbrl_security_type:equity'
        / ':debt' / ':rights'. Use with offering_type_confidence to tier values
        (e.g. exclude low-confidence firm_commitment rows sourced from the equity
        prior before summing gross_proceeds — they can be unlabelled resales)."""
        return list(self._signals)

    @property
    def offering_type_sub_type(self) -> Optional[str]:
        """Classifier sub-type (e.g. 'equity_resale' for a PIPE resale), if any."""
        return self._sub_type

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
    # Section-level text access
    # ------------------------------------------------------------------

    @cached_property
    def sections(self):
        """Document sections for targeted text extraction.

        Returns a Sections dict mapping section names to Section objects.
        Each section provides .text() and .tables() for downstream extraction.

        Example:
            prospectus = filing.obj()
            for name, section in prospectus.sections.items():
                print(f"{name}: {len(section.text())} chars")

            uop = prospectus.sections.get('use_of_proceeds')
            if uop:
                print(uop.text())
        """
        from edgar.documents.document import Sections
        if self._document:
            return self._document.sections
        return Sections({})

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
        # Merge terms from all key_terms tables (some filings split across multiple)
        merged = extract_structured_note_terms(tables[0])
        for extra_table in tables[1:]:
            extra = extract_structured_note_terms(extra_table)
            for field in merged.model_fields:
                if field == 'additional_terms':
                    continue
                if getattr(merged, field) is None and getattr(extra, field) is not None:
                    setattr(merged, field, getattr(extra, field))
            for k, v in extra.additional_terms.items():
                if k not in merged.additional_terms:
                    merged.additional_terms[k] = v
        return merged

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
        from edgar.offerings._424b_tables import (
            extract_underwriting_from_tables,
            is_plausible_underwriter_name,
        )
        from edgar.offerings._424b_cover import extract_underwriting_from_text

        doc = self._document
        if not doc:
            return None

        # Try table-based extraction first (most reliable)
        table_results = extract_underwriting_from_tables(doc)

        entries: list[UnderwriterEntry] = []
        fee_type = 'underwriting_discount'

        # Prefer allocation tables (have full legal names). Guard every name:
        # 424B2 structured-note/debt covers leak legalese paragraphs and lone
        # bullets into the name slot (edgartools-2h4c).
        alloc = [r for r in table_results if r['type'] == 'allocation' and r['names']]
        if alloc:
            for name, amt in zip(alloc[0]['names'], alloc[0].get('allocations', [])):
                if is_plausible_underwriter_name(name):
                    entries.append(UnderwriterEntry(name=name, shares_allocated=amt))
        else:
            # Use cover grid or role listing names
            for tr in table_results:
                for name in tr['names']:
                    if is_plausible_underwriter_name(name) \
                            and not any(e.name == name for e in entries):
                        entries.append(UnderwriterEntry(name=name))

        # Fall back to text-based extraction if no tables found
        if not entries:
            text_results = extract_underwriting_from_text(self._filing, document=doc)
            for tx in text_results:
                for name in tx['names']:
                    if is_plausible_underwriter_name(name) \
                            and not any(e.name == name for e in entries):
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
        # Reuse the exhibit already fetched during classification, if any.
        if self._eager_filing_fees is not None:
            return self._eager_filing_fees
        from edgar.offerings._424b_xbrl import extract_filing_fees_xbrl
        return _build_filing_fees_data(extract_filing_fees_xbrl(self._filing))

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
