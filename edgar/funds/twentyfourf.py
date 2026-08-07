"""
24F-2NT Annual Notice of Securities Sold data object.

Form 24F-2NT is filed annually by registered investment companies to report
aggregate sales of securities, redemption credits, net sales, and the
registration fee due to the SEC under Rule 24f-2.

Two filing patterns occur in the wild:

  - Fund-level (~98%): one ``annualFilingInfo`` block whose ``item5`` carries
    aggregate values for the whole fund.
  - Per-class (~2%): N ``annualFilingInfo`` blocks, one per share class. The
    fund-level metadata (item1/3/4) is identical across blocks; item5 carries a
    ``seriesOrClassId`` and class-level sales/redemptions/fees that must be
    summed to recover fund totals.

Existing typed properties keep their return shape across both patterns: in
per-class mode they aggregate across blocks. The per-class breakdown is
exposed via :attr:`FundFeeNotice.class_fees`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import cached_property
from typing import List, Optional, TYPE_CHECKING

from pydantic import BaseModel
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.richtools import repr_rich
from edgar.xmlfiling import XmlFiling, _XSLT_PREFIXES, _FORM_DESCRIPTIONS

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from edgar._filings import Filing

__all__ = ['FundFeeNotice', 'FundClassFee', 'SeriesInfo']

# Register XSLT prefix and description for 24F-2NT
_XSLT_PREFIXES['24F-2NT'] = 'xsl24F-2NT'
_FORM_DESCRIPTIONS['24F-2NT'] = 'Annual Notice of Securities Sold'


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class SeriesInfo(BaseModel):
    """A fund series reported in the 24F-2NT."""
    series_name: str
    series_id: str
    include_all_classes: bool = False


@dataclass(frozen=True)
class FundClassFee:
    """Per-class fee data from a multi-block 24F-2NT filing.

    Each share class of a fund appears as its own ``annualFilingInfo`` block in
    per-class filings. ``series_id`` is the parent series identifier (typically
    the same value across all classes of a fund).
    """
    series_or_class_id: str
    series_id: Optional[str] = None
    class_name: Optional[str] = None
    aggregate_sales: Optional[float] = None
    aggregate_redemptions_in_fy: Optional[float] = None
    aggregate_redemptions_any_prior: Optional[float] = None
    total_available_redemption_credits: Optional[float] = None
    net_sales: Optional[float] = None
    redemption_credits_for_future: Optional[float] = None
    multiplier_for_fee: Optional[float] = None
    registration_fee_due: Optional[float] = None
    interest_due: Optional[float] = None
    total_due: Optional[float] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_float(val) -> Optional[float]:
    """Parse a numeric string to float, returning None on failure.

    Handles thousands separators and accounting-parens notation
    (``(123.45)`` → ``-123.45``).
    """
    if val is None:
        return None
    try:
        s = str(val).replace(',', '').strip()
        if s.startswith('(') and s.endswith(')'):
            return -float(s[1:-1])
        return float(s)
    except (ValueError, TypeError):
        return None


def _parse_bool(val) -> bool:
    """Parse an XML boolean string."""
    return str(val).lower() in ('true', 'y', 'yes', '1') if val else False


def _sum_or_none(values: List[Optional[float]]) -> Optional[float]:
    """Sum a list of optional floats. Returns None if every value is None."""
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(present)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class FundFeeNotice(XmlFiling):
    """
    Data object for Form 24F-2NT (Annual Notice of Securities Sold).

    Filed annually by registered investment companies to report fund
    sales volumes, redemptions, net sales, and SEC registration fees.

    Construction via from_filing() or filing.obj():
        filing = find("24F-2NT accession number")
        notice = filing.obj()  # Returns FundFeeNotice
        notice = FundFeeNotice.from_filing(filing)

    Key properties:
        notice.fund_name             -> str
        notice.aggregate_sales       -> float (total securities sold)
        notice.net_sales             -> float (sales minus redemptions)
        notice.registration_fee      -> float (fee due to SEC)
        notice.fiscal_year_end       -> str (e.g., '12/31/2025')
        notice.series                -> list[SeriesInfo]
        notice.is_per_class          -> bool (True for multi-block filings)
        notice.class_fees            -> list[FundClassFee] (per-class breakdown)
    """

    # ------------------------------------------------------------------
    # Block accessors
    # ------------------------------------------------------------------

    @cached_property
    def _filing_info_blocks(self) -> List[dict]:
        """All ``annualFilingInfo`` blocks. Length 1 for fund-level filings,
        N for per-class filings."""
        annual = self._form_data.get('annualFilings', {})
        if not isinstance(annual, dict):
            return []
        info = annual.get('annualFilingInfo')
        if info is None:
            return []
        if isinstance(info, list):
            return [b for b in info if isinstance(b, dict)]
        if isinstance(info, dict):
            return [info]
        return []

    @property
    def _filing_info(self) -> dict:
        """Primary block. Fund-level metadata (item1/3/4) is identical across
        blocks; financial fields are aggregated by the typed properties."""
        blocks = self._filing_info_blocks
        return blocks[0] if blocks else {}

    @property
    def is_per_class(self) -> bool:
        """True when this filing reports per share class (multi-block)."""
        return len(self._filing_info_blocks) > 1

    # ------------------------------------------------------------------
    # Typed properties — Item 1: Issuer
    # ------------------------------------------------------------------

    @property
    def fund_name(self) -> Optional[str]:
        """Name of the investment company."""
        item1 = self._filing_info.get('item1', {})
        return item1.get('nameOfIssuer') if isinstance(item1, dict) else None

    @property
    def fund_address(self) -> Optional[dict]:
        """Address of the issuer as a dict."""
        item1 = self._filing_info.get('item1', {})
        return item1.get('addressOfIssuer') if isinstance(item1, dict) else None

    # ------------------------------------------------------------------
    # Item 2: Series/Class
    # ------------------------------------------------------------------

    @cached_property
    def series(self) -> List[SeriesInfo]:
        """Series reported in this filing. In per-class mode, duplicates by
        ``series_id`` are collapsed since every block typically points at the
        same parent series."""
        result: List[SeriesInfo] = []
        seen: set = set()
        for block in self._filing_info_blocks:
            item2 = block.get('item2', {})
            if not isinstance(item2, dict):
                continue
            report = item2.get('reportSeriesClass', {})
            if not isinstance(report, dict):
                continue
            info_list = report.get('rptSeriesClassInfo', [])
            if isinstance(info_list, dict):
                info_list = [info_list]
            for info in info_list:
                if not isinstance(info, dict):
                    continue
                series_id = info.get('seriesId', '')
                if series_id in seen:
                    continue
                seen.add(series_id)
                result.append(SeriesInfo(
                    series_name=info.get('seriesName', '').strip(),
                    series_id=series_id,
                    include_all_classes=_parse_bool(info.get('includeAllClassesFlag')),
                ))
        return result

    # ------------------------------------------------------------------
    # Item 3: File numbers
    # ------------------------------------------------------------------

    @property
    def investment_company_act_file_number(self) -> Optional[str]:
        """Investment Company Act file number (811-XXXXX)."""
        item3 = self._filing_info.get('item3', {})
        return item3.get('investmentCompActFileNo') if isinstance(item3, dict) else None

    # ------------------------------------------------------------------
    # Item 4: Fiscal year
    # ------------------------------------------------------------------

    @property
    def fiscal_year_end(self) -> Optional[str]:
        """Last day of fiscal year (e.g., '12/31/2025')."""
        item4 = self._filing_info.get('item4', {})
        return item4.get('lastDayOfFiscalYear') if isinstance(item4, dict) else None

    @property
    def is_filed_late(self) -> bool:
        """Whether this form was filed late."""
        item4 = self._filing_info.get('item4', {})
        return _parse_bool(item4.get('isThisFormBeingFiledLate')) if isinstance(item4, dict) else False

    @property
    def is_final_filing(self) -> bool:
        """Whether this is the last time the issuer will file this form."""
        item4 = self._filing_info.get('item4', {})
        return _parse_bool(item4.get('isThisTheLastTimeIssuerFilingThisForm')) if isinstance(item4, dict) else False

    # ------------------------------------------------------------------
    # Item 5: Sales and fees (the financial data)
    # ------------------------------------------------------------------

    @staticmethod
    def _block_item5(block: dict) -> dict:
        item5 = block.get('item5', {}) if isinstance(block, dict) else {}
        return item5 if isinstance(item5, dict) else {}

    @staticmethod
    def _block_item(block: dict, key: str) -> dict:
        val = block.get(key, {}) if isinstance(block, dict) else {}
        return val if isinstance(val, dict) else {}

    def _sum_item5(self, field: str) -> Optional[float]:
        """Sum a numeric ``item5`` field across all blocks."""
        return _sum_or_none([
            _parse_float(self._block_item5(b).get(field))
            for b in self._filing_info_blocks
        ])

    @property
    def aggregate_sales(self) -> Optional[float]:
        """Total aggregate sale price of securities sold. Summed across share
        classes in per-class filings."""
        return self._sum_item5('aggregateSalePriceOfSecuritiesSold')

    @property
    def redemptions_current_year(self) -> Optional[float]:
        """Aggregate price of securities redeemed/repurchased in fiscal year."""
        return self._sum_item5('aggregatePriceOfSecuritiesRedeemedOrRepurchasedInFiscalYear')

    @property
    def redemptions_prior_years(self) -> Optional[float]:
        """Aggregate price of securities redeemed/repurchased in prior years (unused credits)."""
        return self._sum_item5('aggregatePriceOfSecuritiesRedeemedOrRepurchasedAnyPrior')

    @property
    def total_redemption_credits(self) -> Optional[float]:
        """Total available redemption credits."""
        return self._sum_item5('totalAvailableRedemptionCredits')

    @property
    def net_sales(self) -> Optional[float]:
        """Net sales (aggregate sales minus redemption credits)."""
        return self._sum_item5('netSales')

    @property
    def unused_redemption_credits(self) -> Optional[float]:
        """Redemption credits available for use in future years."""
        return self._sum_item5('redemptionCreditsAvailableForUseInFutureYears')

    @property
    def fee_multiplier(self) -> Optional[float]:
        """Multiplier for determining registration fee. Identical across
        classes; returned from the first block."""
        for b in self._filing_info_blocks:
            v = _parse_float(self._block_item5(b).get('multiplierForDeterminingRegistrationFee'))
            if v is not None:
                return v
        return None

    @property
    def registration_fee(self) -> Optional[float]:
        """Registration fee due to the SEC."""
        return self._sum_item5('registrationFeeDue')

    # ------------------------------------------------------------------
    # Item 6-7
    # ------------------------------------------------------------------

    @property
    def interest_due(self) -> Optional[float]:
        """Interest due on late payment."""
        return _sum_or_none([
            _parse_float(self._block_item(b, 'item6').get('interestDue'))
            for b in self._filing_info_blocks
        ])

    @property
    def total_due(self) -> Optional[float]:
        """Total of registration fee plus any interest due."""
        return _sum_or_none([
            _parse_float(self._block_item(b, 'item7').get('totalOfRegistrationFeePlusAnyInterestDue'))
            for b in self._filing_info_blocks
        ])

    # ------------------------------------------------------------------
    # Per-class breakdown
    # ------------------------------------------------------------------

    @cached_property
    def class_fees(self) -> List[FundClassFee]:
        """Per-class fee breakdown. Returns an empty list for fund-level
        (single-block) filings."""
        if not self.is_per_class:
            return []

        fees: List[FundClassFee] = []
        for block in self._filing_info_blocks:
            item5 = self._block_item5(block)
            item6 = self._block_item(block, 'item6')
            item7 = self._block_item(block, 'item7')

            series_id = None
            class_name = None
            item2 = block.get('item2', {})
            if isinstance(item2, dict):
                report = item2.get('reportSeriesClass', {})
                if isinstance(report, dict):
                    info = report.get('rptSeriesClassInfo', {})
                    if isinstance(info, list) and info:
                        info = info[0]
                    if isinstance(info, dict):
                        series_id = info.get('seriesId') or None
                        class_info = info.get('classInfo', {})
                        if isinstance(class_info, dict):
                            class_name = class_info.get('className') or None

            fees.append(FundClassFee(
                series_or_class_id=item5.get('seriesOrClassId', '') or '',
                series_id=series_id,
                class_name=class_name,
                aggregate_sales=_parse_float(item5.get('aggregateSalePriceOfSecuritiesSold')),
                aggregate_redemptions_in_fy=_parse_float(item5.get('aggregatePriceOfSecuritiesRedeemedOrRepurchasedInFiscalYear')),
                aggregate_redemptions_any_prior=_parse_float(item5.get('aggregatePriceOfSecuritiesRedeemedOrRepurchasedAnyPrior')),
                total_available_redemption_credits=_parse_float(item5.get('totalAvailableRedemptionCredits')),
                net_sales=_parse_float(item5.get('netSales')),
                redemption_credits_for_future=_parse_float(item5.get('redemptionCreditsAvailableForUseInFutureYears')),
                multiplier_for_fee=_parse_float(item5.get('multiplierForDeterminingRegistrationFee')),
                registration_fee_due=_parse_float(item5.get('registrationFeeDue')),
                interest_due=_parse_float(item6.get('interestDue')),
                total_due=_parse_float(item7.get('totalOfRegistrationFeePlusAnyInterestDue')),
            ))
        return fees

    # ------------------------------------------------------------------
    # AI context
    # ------------------------------------------------------------------

    def to_context(self, detail: str = 'standard') -> str:
        """AI-optimized context string for language models."""
        lines = [
            f"24F-2NT ANNUAL NOTICE OF SECURITIES SOLD: {self.fund_name or self.company}",
            "",
            f"Filed: {self.filing_date}",
            f"Fiscal Year End: {self.fiscal_year_end or 'N/A'}",
        ]

        if self.aggregate_sales is not None:
            lines.append(f"Aggregate Sales: ${self.aggregate_sales:,.2f}")
        if self.net_sales is not None:
            lines.append(f"Net Sales: ${self.net_sales:,.2f}")
        if self.registration_fee is not None:
            lines.append(f"Registration Fee: ${self.registration_fee:,.2f}")

        if self.series:
            lines.append(f"Series Reported: {len(self.series)}")

        if self.is_per_class:
            lines.append(f"Per-Class Breakdown: {len(self.class_fees)} share classes")

        if detail == 'minimal':
            return "\n".join(lines)

        if self.total_redemption_credits is not None:
            lines.append(f"Redemption Credits: ${self.total_redemption_credits:,.2f}")

        if self.is_per_class and detail != 'minimal':
            lines.append("")
            lines.append("CLASS-LEVEL SALES:")
            for cf in self.class_fees:
                label = cf.class_name or cf.series_or_class_id
                if cf.aggregate_sales is not None:
                    lines.append(f"  {cf.series_or_class_id} ({label}): ${cf.aggregate_sales:,.2f}")
                else:
                    lines.append(f"  {cf.series_or_class_id} ({label})")

        if detail == 'full':
            lines.append("")
            lines.append("AVAILABLE ACTIONS:")
            lines.append("  .aggregate_sales -> float (total securities sold)")
            lines.append("  .net_sales -> float (sales minus redemptions)")
            lines.append("  .registration_fee -> float (fee due to SEC)")
            lines.append("  .series -> list[SeriesInfo] (fund series)")
            lines.append("  .class_fees -> list[FundClassFee] (per-class data)")
            lines.append("  .is_per_class -> bool (multi-block filing flag)")
            lines.append("  .fiscal_year_end -> str")
            lines.append("  .to_html() -> SEC XSLT-rendered HTML")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Rich display
    # ------------------------------------------------------------------

    def __rich__(self):
        title = f"{self.fund_name or self.company}  {self.filing_date}"
        subtitle = "24F-2NT  Annual Notice of Securities Sold"

        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        t.add_column("field", style="bold deep_sky_blue1", min_width=22)
        t.add_column("value")

        t.add_row("Fund", self.fund_name or self.company)
        if self.fiscal_year_end:
            t.add_row("Fiscal Year End", self.fiscal_year_end)
        if self.investment_company_act_file_number:
            t.add_row("ICA File No.", self.investment_company_act_file_number)
        if self.series:
            t.add_row("Series", str(len(self.series)))
        if self.is_per_class:
            t.add_row("Share Classes", str(len(self.class_fees)))

        renderables = [t]

        # Financial data table
        has_financials = self.aggregate_sales is not None or self.net_sales is not None
        if has_financials:
            renderables.append(Text(""))
            fee_title = "Fee Calculation (Fund Total)" if self.is_per_class else "Fee Calculation"
            ft = Table(box=box.SIMPLE, show_header=False, padding=(0, 1),
                       title=fee_title)
            ft.add_column("field", style="bold", min_width=22)
            ft.add_column("value", justify="right", style="deep_sky_blue1")

            if self.aggregate_sales is not None:
                ft.add_row("Aggregate Sales", f"${self.aggregate_sales:>,.2f}")
            if self.total_redemption_credits is not None:
                ft.add_row("Redemption Credits", f"${self.total_redemption_credits:>,.2f}")
            if self.net_sales is not None:
                ft.add_row("Net Sales", f"${self.net_sales:>,.2f}")
            if self.registration_fee is not None:
                ft.add_row("Registration Fee", f"${self.registration_fee:>,.2f}")
            if self.interest_due and self.interest_due > 0:
                ft.add_row("Interest Due", f"${self.interest_due:>,.2f}")
            if self.total_due is not None:
                ft.add_row("Total Due", f"${self.total_due:>,.2f}")

            renderables.append(ft)

        # Per-class breakdown
        if self.is_per_class and self.class_fees:
            renderables.append(Text(""))
            ct = Table(box=box.SIMPLE, padding=(0, 1),
                       title="Per-Class Breakdown")
            ct.add_column("Class ID", style="bold")
            ct.add_column("Class", style="dim")
            ct.add_column("Aggregate Sales", justify="right", style="deep_sky_blue1")
            ct.add_column("Net Sales", justify="right", style="deep_sky_blue1")
            ct.add_column("Reg. Fee", justify="right", style="deep_sky_blue1")
            for cf in self.class_fees:
                ct.add_row(
                    cf.series_or_class_id,
                    cf.class_name or "",
                    f"${cf.aggregate_sales:,.2f}" if cf.aggregate_sales is not None else "",
                    f"${cf.net_sales:,.2f}" if cf.net_sales is not None else "",
                    f"${cf.registration_fee_due:,.2f}" if cf.registration_fee_due is not None else "",
                )
            renderables.append(ct)

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
            f"FundFeeNotice("
            f"fund={(self.fund_name or self.company)!r}, "
            f"sales={self.aggregate_sales}, "
            f"net={self.net_sales}, "
            f"fee={self.registration_fee}, "
            f"date={self.filing_date!r})"
        )
