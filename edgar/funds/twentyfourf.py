"""
24F-2NT Annual Notice of Securities Sold data object.

Form 24F-2NT is filed annually by registered investment companies to report
aggregate sales of securities, redemption credits, net sales, and the
registration fee due to the SEC under Rule 24f-2.

Key data:
  - Fund name, address, investment company type
  - Series/class breakdown
  - Aggregate sales, redemptions, net sales
  - Registration fee calculation
  - Fiscal year end
"""

from __future__ import annotations

import logging
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

__all__ = ['FundFeeNotice']

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_float(val) -> Optional[float]:
    """Parse a numeric string to float, returning None on failure."""
    if val is None:
        return None
    try:
        return float(str(val).replace(',', ''))
    except (ValueError, TypeError):
        return None


def _parse_bool(val) -> bool:
    """Parse an XML boolean string."""
    return str(val).lower() in ('true', 'y', 'yes', '1') if val else False


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
    """

    # ------------------------------------------------------------------
    # Typed properties — Item 1: Issuer
    # ------------------------------------------------------------------

    @property
    def _filing_info(self) -> dict:
        """The annualFilingInfo dict."""
        annual = self._form_data.get('annualFilings', {})
        return annual.get('annualFilingInfo', {}) if isinstance(annual, dict) else {}

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
        """Series reported in this filing."""
        item2 = self._filing_info.get('item2', {})
        if not isinstance(item2, dict):
            return []
        report = item2.get('reportSeriesClass', {})
        if not isinstance(report, dict):
            return []
        info_list = report.get('rptSeriesClassInfo', [])
        if isinstance(info_list, dict):
            info_list = [info_list]
        result = []
        for info in info_list:
            if isinstance(info, dict):
                result.append(SeriesInfo(
                    series_name=info.get('seriesName', ''),
                    series_id=info.get('seriesId', ''),
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

    @property
    def _item5(self) -> dict:
        return self._filing_info.get('item5', {}) if isinstance(self._filing_info, dict) else {}

    @property
    def aggregate_sales(self) -> Optional[float]:
        """Total aggregate sale price of securities sold."""
        return _parse_float(self._item5.get('aggregateSalePriceOfSecuritiesSold'))

    @property
    def redemptions_current_year(self) -> Optional[float]:
        """Aggregate price of securities redeemed/repurchased in fiscal year."""
        return _parse_float(self._item5.get('aggregatePriceOfSecuritiesRedeemedOrRepurchasedInFiscalYear'))

    @property
    def redemptions_prior_years(self) -> Optional[float]:
        """Aggregate price of securities redeemed/repurchased in prior years (unused credits)."""
        return _parse_float(self._item5.get('aggregatePriceOfSecuritiesRedeemedOrRepurchasedAnyPrior'))

    @property
    def total_redemption_credits(self) -> Optional[float]:
        """Total available redemption credits."""
        return _parse_float(self._item5.get('totalAvailableRedemptionCredits'))

    @property
    def net_sales(self) -> Optional[float]:
        """Net sales (aggregate sales minus redemption credits)."""
        return _parse_float(self._item5.get('netSales'))

    @property
    def unused_redemption_credits(self) -> Optional[float]:
        """Redemption credits available for use in future years."""
        return _parse_float(self._item5.get('redemptionCreditsAvailableForUseInFutureYears'))

    @property
    def fee_multiplier(self) -> Optional[float]:
        """Multiplier for determining registration fee."""
        return _parse_float(self._item5.get('multiplierForDeterminingRegistrationFee'))

    @property
    def registration_fee(self) -> Optional[float]:
        """Registration fee due to the SEC."""
        return _parse_float(self._item5.get('registrationFeeDue'))

    # ------------------------------------------------------------------
    # Item 6-7
    # ------------------------------------------------------------------

    @property
    def interest_due(self) -> Optional[float]:
        """Interest due on late payment."""
        item6 = self._filing_info.get('item6', {})
        return _parse_float(item6.get('interestDue')) if isinstance(item6, dict) else None

    @property
    def total_due(self) -> Optional[float]:
        """Total of registration fee plus any interest due."""
        item7 = self._filing_info.get('item7', {})
        return _parse_float(item7.get('totalOfRegistrationFeePlusAnyInterestDue')) if isinstance(item7, dict) else None

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

        if detail == 'minimal':
            return "\n".join(lines)

        if self.total_redemption_credits is not None:
            lines.append(f"Redemption Credits: ${self.total_redemption_credits:,.2f}")

        if detail == 'full':
            lines.append("")
            lines.append("AVAILABLE ACTIONS:")
            lines.append("  .aggregate_sales -> float (total securities sold)")
            lines.append("  .net_sales -> float (sales minus redemptions)")
            lines.append("  .registration_fee -> float (fee due to SEC)")
            lines.append("  .series -> list[SeriesInfo] (fund series)")
            lines.append("  .fiscal_year_end -> str")
            lines.append("  .to_html() -> SEC XSLT-rendered HTML")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Rich display
    # ------------------------------------------------------------------

    def __rich__(self):
        title = f"{self.fund_name or self.company}  {self.filing_date}"
        subtitle = f"24F-2NT  Annual Notice of Securities Sold"

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

        renderables = [t]

        # Financial data table
        has_financials = self.aggregate_sales is not None or self.net_sales is not None
        if has_financials:
            renderables.append(Text(""))
            ft = Table(box=box.SIMPLE, show_header=False, padding=(0, 1),
                       title="Fee Calculation")
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
