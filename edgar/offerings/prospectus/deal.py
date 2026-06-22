"""Deal — normalized, computed deal summary synthesized from a 424B prospectus."""

from __future__ import annotations

import re
from functools import cached_property
from typing import List, Optional, TYPE_CHECKING

from rich import box
from rich.panel import Panel
from rich.table import Table

from edgar.richtools import repr_rich
from edgar.offerings.prospectus.models import OfferingType
from edgar.offerings.prospectus.parsing import _parse_sec_int, _parse_sec_number

if TYPE_CHECKING:
    from edgar.offerings.prospectus.document import Prospectus424B
    from edgar.offerings.prospectus.models import PricingColumnData


def _extract_amendment_number(form_name: str) -> Optional[int]:
    """Extract amendment number from form name like '424B3/A'."""
    if '/A' not in form_name:
        return None
    m = re.search(r'Amendment\s+No\.?\s*(\d+)', form_name, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


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
