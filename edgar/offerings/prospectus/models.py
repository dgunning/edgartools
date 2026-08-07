"""Pydantic data models for 424B prospectus extraction.

Covers cover-page fields, pricing/offering terms, selling stockholders,
underwriting, structured notes, dilution/capitalization, filing fees, and the
registration fee table (shelf capacity).
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, field_validator

from edgar.offerings.prospectus.parsing import _parse_sec_int, _parse_sec_number

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
