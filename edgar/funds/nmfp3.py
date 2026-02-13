"""
N-MFP Money Market Fund Portfolio Holdings data object.

Supports both N-MFP3 (June 2024+) and N-MFP2 (2010–mid 2024) form variants.
Money market funds file monthly to report portfolio holdings, yields,
NAV data, liquidity metrics, and share class information.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from functools import lru_cache
from typing import Any, List, Optional, Union

import pandas as pd
from lxml import etree
from pydantic import BaseModel
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table

from edgar.display.formatting import moneyfmt
from edgar.funds.reports import _opt_decimal, _strip_namespaces, _text
from edgar.richtools import df_to_rich_table, repr_rich

log = logging.getLogger(__name__)

__all__ = ['MoneyMarketFund', 'NMFP3_FORMS', 'NMFP2_FORMS', 'MONEY_MARKET_FORMS']

NMFP2_FORMS = ["N-MFP2", "N-MFP2/A"]
NMFP3_FORMS = ["N-MFP3", "N-MFP3/A"]
MONEY_MARKET_FORMS = NMFP2_FORMS + NMFP3_FORMS


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _opt_int(parent, tag) -> Optional[int]:
    """Get optional int from child element text."""
    text = _text(parent, tag)
    if text:
        try:
            return int(text)
        except (ValueError, TypeError):
            return None
    return None


def _flag(parent, tag) -> bool:
    """Parse Y/N flag to boolean."""
    return _text(parent, tag) == "Y"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class GeneralInfo(BaseModel):
    report_date: str
    registrant_name: str
    cik: str
    registrant_lei: Optional[str] = None
    series_name: str
    series_lei: Optional[str] = None
    series_id: str
    total_share_classes: int
    final_filing: bool = False


class SeriesLevelInfo(BaseModel):
    fund_category: Optional[str] = None
    avg_portfolio_maturity: Optional[int] = None
    avg_life_maturity: Optional[int] = None
    cash: Optional[Decimal] = None
    total_value_portfolio_securities: Optional[Decimal] = None
    amortized_cost_portfolio_securities: Optional[Decimal] = None
    total_value_other_assets: Optional[Decimal] = None
    total_value_liabilities: Optional[Decimal] = None
    net_assets: Optional[Decimal] = None
    shares_outstanding: Optional[Decimal] = None
    seek_stable_price: bool = False
    stable_price_per_share: Optional[Decimal] = None
    seven_day_gross_yields: List[dict] = []
    daily_nav_per_share: List[dict] = []
    liquidity_details: List[dict] = []


class ShareClassInfo(BaseModel):
    class_name: str
    class_id: str
    min_initial_investment: Optional[Decimal] = None
    net_assets: Optional[Decimal] = None
    shares_outstanding: Optional[Decimal] = None
    daily_nav: List[dict] = []
    daily_flows: List[dict] = []
    seven_day_net_yields: List[dict] = []


class CreditRating(BaseModel):
    agency: str
    rating: str


class CollateralIssuer(BaseModel):
    issuer_name: Optional[str] = None
    lei: Optional[str] = None
    cusip: Optional[str] = None
    maturity_date: Optional[str] = None
    coupon: Optional[Decimal] = None
    principal_amount: Optional[Decimal] = None
    collateral_value: Optional[Decimal] = None
    collateral_category: Optional[str] = None


class RepurchaseAgreement(BaseModel):
    open_flag: bool = False
    cleared_flag: bool = False
    tri_party_flag: bool = False
    collateral: List[CollateralIssuer] = []


class PortfolioSecurity(BaseModel):
    issuer_name: Optional[str] = None
    title: Optional[str] = None
    cusip: Optional[str] = None
    isin: Optional[str] = None
    lei: Optional[str] = None
    cik: Optional[str] = None
    investment_category: Optional[str] = None
    maturity_date_wam: Optional[str] = None
    maturity_date_wal: Optional[str] = None
    final_maturity_date: Optional[str] = None
    yield_rate: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    amortized_cost: Optional[Decimal] = None
    pct_of_nav: Optional[Decimal] = None
    daily_liquid: bool = False
    weekly_liquid: bool = False
    illiquid: bool = False
    demand_feature: bool = False
    guarantee: bool = False
    enhancement: bool = False
    ratings: List[CreditRating] = []
    repo_agreement: Optional[RepurchaseAgreement] = None


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class MoneyMarketFund:
    """
    Money Market Fund Portfolio Holdings (N-MFP2 and N-MFP3).

    Money market funds file monthly to report their portfolio holdings,
    yields, NAV, liquidity metrics, and share class data.

    Supports both N-MFP3 (June 2024+, daily time series) and
    N-MFP2 (2010–mid 2024, weekly Friday snapshots).

    Usage:
        >>> filing = Filing(form='N-MFP3', ...)
        >>> mmf = filing.obj()
        >>> mmf.net_assets
        Decimal('26435168844.97')
        >>> mmf.portfolio_data().head()
    """

    def __init__(self,
                 general_info: GeneralInfo,
                 series_info: SeriesLevelInfo,
                 share_classes: List[ShareClassInfo],
                 securities: List[PortfolioSecurity]):
        self.general_info = general_info
        self.series_info = series_info
        self.share_classes = share_classes
        self.securities = securities

    def __str__(self):
        return f"MoneyMarketFund({self.name}, {self.report_date}, {self.num_securities} securities)"

    @property
    def name(self) -> str:
        return self.general_info.series_name

    @property
    def report_date(self) -> str:
        return self.general_info.report_date

    @property
    def fund_category(self) -> Optional[str]:
        return self.series_info.fund_category

    @property
    def net_assets(self) -> Optional[Decimal]:
        return self.series_info.net_assets

    @property
    def num_securities(self) -> int:
        return len(self.securities)

    @property
    def num_share_classes(self) -> int:
        return len(self.share_classes)

    @property
    def average_maturity_wam(self) -> Optional[int]:
        """Weighted average maturity in days."""
        return self.series_info.avg_portfolio_maturity

    @property
    def average_maturity_wal(self) -> Optional[int]:
        """Weighted average life in days."""
        return self.series_info.avg_life_maturity

    # -------------------------------------------------------------------
    # DataFrame methods
    # -------------------------------------------------------------------

    @lru_cache(maxsize=1)
    def portfolio_data(self) -> pd.DataFrame:
        """Portfolio securities sorted by market value descending."""
        data = []
        for sec in self.securities:
            data.append({
                "issuer": sec.issuer_name,
                "title": sec.title,
                "cusip": sec.cusip,
                "isin": sec.isin,
                "category": sec.investment_category,
                "maturity_wam": sec.maturity_date_wam,
                "maturity_wal": sec.maturity_date_wal,
                "yield": sec.yield_rate,
                "market_value": sec.market_value,
                "amortized_cost": sec.amortized_cost,
                "pct_of_nav": sec.pct_of_nav,
                "daily_liquid": sec.daily_liquid,
                "weekly_liquid": sec.weekly_liquid,
                "has_repo": sec.repo_agreement is not None,
            })
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values("market_value", ascending=False, na_position="last").reset_index(drop=True)
        return df

    @lru_cache(maxsize=1)
    def share_class_data(self) -> pd.DataFrame:
        """Share class summary."""
        data = []
        for sc in self.share_classes:
            data.append({
                "class_name": sc.class_name,
                "class_id": sc.class_id,
                "min_investment": sc.min_initial_investment,
                "net_assets": sc.net_assets,
                "shares_outstanding": sc.shares_outstanding,
            })
        return pd.DataFrame(data)

    @lru_cache(maxsize=1)
    def yield_history(self) -> pd.DataFrame:
        """Series-level 7-day gross yield time series."""
        return pd.DataFrame(self.series_info.seven_day_gross_yields)

    @lru_cache(maxsize=1)
    def nav_history(self) -> pd.DataFrame:
        """Series-level daily NAV per share time series."""
        return pd.DataFrame(self.series_info.daily_nav_per_share)

    @lru_cache(maxsize=1)
    def liquidity_history(self) -> pd.DataFrame:
        """Daily and weekly liquid asset percentages time series."""
        return pd.DataFrame(self.series_info.liquidity_details)

    @lru_cache(maxsize=1)
    def collateral_data(self) -> pd.DataFrame:
        """All repo collateral flattened into one DataFrame."""
        data = []
        for sec in self.securities:
            if sec.repo_agreement:
                for coll in sec.repo_agreement.collateral:
                    data.append({
                        "security_issuer": sec.issuer_name,
                        "security_cusip": sec.cusip,
                        "collateral_issuer": coll.issuer_name,
                        "collateral_cusip": coll.cusip,
                        "collateral_lei": coll.lei,
                        "maturity_date": coll.maturity_date,
                        "coupon": coll.coupon,
                        "principal_amount": coll.principal_amount,
                        "collateral_value": coll.collateral_value,
                        "collateral_category": coll.collateral_category,
                    })
        return pd.DataFrame(data)

    @lru_cache(maxsize=1)
    def holdings_by_category(self) -> pd.DataFrame:
        """Holdings grouped by investment category."""
        pdf = self.portfolio_data()
        if pdf.empty:
            return pd.DataFrame()
        grouped = pdf.groupby("category", dropna=False).agg(
            count=("cusip", "count"),
            total_market_value=("market_value", "sum"),
            total_pct=("pct_of_nav", "sum"),
        ).sort_values("total_market_value", ascending=False).reset_index()
        return grouped

    # -------------------------------------------------------------------
    # Rich display
    # -------------------------------------------------------------------

    @property
    def _summary_table(self) -> Table:
        """Build a summary info table."""
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("Registrant", self.general_info.registrant_name)
        table.add_row("Series", self.general_info.series_name)
        table.add_row("Report Date", self.general_info.report_date)
        table.add_row("Fund Category", self.series_info.fund_category or "N/A")
        table.add_row("Net Assets", moneyfmt(self.net_assets) if self.net_assets else "N/A")
        table.add_row("WAM (days)", str(self.average_maturity_wam) if self.average_maturity_wam else "N/A")
        table.add_row("WAL (days)", str(self.average_maturity_wal) if self.average_maturity_wal else "N/A")
        table.add_row("Securities", str(self.num_securities))
        table.add_row("Share Classes", str(self.num_share_classes))

        if self.series_info.seek_stable_price and self.series_info.stable_price_per_share:
            table.add_row("Stable Price", str(self.series_info.stable_price_per_share))

        return table

    @property
    def _share_classes_table(self) -> Table:
        """Build share classes table."""
        sc_df = self.share_class_data()
        if sc_df.empty:
            return Table(title="Share Classes")
        return df_to_rich_table(
            sc_df.assign(
                net_assets=sc_df["net_assets"].apply(lambda v: moneyfmt(v) if pd.notna(v) else ""),
                min_investment=sc_df["min_investment"].apply(lambda v: moneyfmt(v) if pd.notna(v) else ""),
            ).rename(columns={
                "class_name": "Class",
                "class_id": "ID",
                "min_investment": "Min Investment",
                "net_assets": "Net Assets",
                "shares_outstanding": "Shares Outstanding",
            }),
            title="Share Classes",
            title_style="bold deep_sky_blue1",
            max_rows=20,
        )

    @property
    def _top_holdings_table(self) -> Table:
        """Build top holdings table."""
        pdf = self.portfolio_data()
        if pdf.empty:
            return Table(title="Top Holdings")
        top = pdf.head(15).copy()
        top["market_value"] = top["market_value"].apply(lambda v: moneyfmt(v) if pd.notna(v) else "")
        top["pct_of_nav"] = top["pct_of_nav"].apply(lambda v: f"{v:.2%}" if pd.notna(v) else "")
        display_df = top[["issuer", "cusip", "category", "market_value", "pct_of_nav"]].rename(columns={
            "issuer": "Issuer",
            "cusip": "CUSIP",
            "category": "Category",
            "market_value": "Market Value",
            "pct_of_nav": "% NAV",
        })
        return df_to_rich_table(
            display_df,
            title=f"Top Holdings (of {self.num_securities})",
            title_style="bold deep_sky_blue1",
            max_rows=15,
        )

    def __rich__(self):
        title = f"{self.general_info.series_name}  {self.general_info.report_date}"
        return Panel(
            Group(
                self._summary_table,
                self._share_classes_table,
                self._top_holdings_table,
            ),
            title=title,
            subtitle=f"Money Market Fund  {self.general_info.report_date}",
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    # -------------------------------------------------------------------
    # Parsing
    # -------------------------------------------------------------------

    @classmethod
    def from_filing(cls, filing) -> Optional['MoneyMarketFund']:
        """Create a MoneyMarketFund from a Filing object."""
        xml = filing.xml()
        if not xml:
            return None
        return cls._parse_xml(xml)

    @classmethod
    def parse_nmfp3_xml(cls, xml: Union[str, Any]) -> 'MoneyMarketFund':
        """Parse N-MFP3 XML. Kept for backward compatibility."""
        return cls._parse_xml(xml)

    @classmethod
    def _parse_xml(cls, xml: Union[str, Any]) -> 'MoneyMarketFund':
        """Parse N-MFP2 or N-MFP3 XML into a MoneyMarketFund object."""
        if isinstance(xml, str):
            xml_bytes = xml.encode('utf-8')
        else:
            xml_bytes = xml

        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError:
            parser = etree.XMLParser(recover=True)
            root = etree.fromstring(xml_bytes, parser=parser)

        # Detect schema version before stripping namespaces
        is_v2 = b'edgar/nmfp2' in xml_bytes

        _strip_namespaces(root)

        # Navigate to edgarSubmission if needed
        if root.tag != "edgarSubmission":
            found = root.find(".//edgarSubmission")
            if found is not None:
                root = found

        form_data = root.find("formData")

        # ----- General Info -----
        gen = form_data.find("generalInfo")
        if is_v2:
            # N-MFP2 lacks registrantFullName, registrantLEIId, nameOfSeries
            general_info = GeneralInfo(
                report_date=_text(gen, "reportDate") or "",
                registrant_name="",
                cik=_text(gen, "cik") or "",
                registrant_lei=None,
                series_name="",
                series_lei=None,
                series_id=_text(gen, "seriesId") or "",
                total_share_classes=_opt_int(gen, "totalShareClassesInSeries") or 0,
                final_filing=_flag(gen, "finalFilingFlag"),
            )
        else:
            general_info = GeneralInfo(
                report_date=_text(gen, "reportDate") or "",
                registrant_name=_text(gen, "registrantFullName") or "",
                cik=_text(gen, "cik") or "",
                registrant_lei=_text(gen, "registrantLEIId"),
                series_name=_text(gen, "nameOfSeries") or "",
                series_lei=_text(gen, "leiOfSeries"),
                series_id=_text(gen, "seriesId") or "",
                total_share_classes=_opt_int(gen, "totalShareClassesInSeries") or 0,
                final_filing=_flag(gen, "finalFilingFlag"),
            )

        # ----- Series Level Info -----
        series_el = form_data.find("seriesLevelInfo")

        if is_v2:
            seven_day_gross_yields, daily_nav, liquidity_details = _parse_v2_series_time_series(series_el)
            # N-MFP2 uses seekStablePricePerShare absent; stablePricePerShare present as direct value
            seek_stable = series_el.find("stablePricePerShare") is not None
        else:
            seven_day_gross_yields, daily_nav, liquidity_details = _parse_v3_series_time_series(series_el)
            seek_stable = _flag(series_el, "seekStablePricePerShare")

        series_info = SeriesLevelInfo(
            fund_category=_text(series_el, "moneyMarketFundCategory"),
            avg_portfolio_maturity=_opt_int(series_el, "averagePortfolioMaturity"),
            avg_life_maturity=_opt_int(series_el, "averageLifeMaturity"),
            cash=_opt_decimal(series_el, "cash"),
            total_value_portfolio_securities=_opt_decimal(series_el, "totalValuePortfolioSecurities"),
            amortized_cost_portfolio_securities=_opt_decimal(series_el, "amortizedCostPortfolioSecurities"),
            total_value_other_assets=_opt_decimal(series_el, "totalValueOtherAssets"),
            total_value_liabilities=_opt_decimal(series_el, "totalValueLiabilities"),
            net_assets=_opt_decimal(series_el, "netAssetOfSeries"),
            shares_outstanding=_opt_decimal(series_el, "numberOfSharesOutstanding"),
            seek_stable_price=seek_stable,
            stable_price_per_share=_opt_decimal(series_el, "stablePricePerShare"),
            seven_day_gross_yields=seven_day_gross_yields,
            daily_nav_per_share=daily_nav,
            liquidity_details=liquidity_details,
        )

        # ----- Share Classes -----
        share_classes = []
        for sc_el in form_data.findall("classLevelInfo"):
            if is_v2:
                class_daily_nav, daily_flows, class_yields = _parse_v2_class_time_series(sc_el)
            else:
                class_daily_nav, daily_flows, class_yields = _parse_v3_class_time_series(sc_el)

            share_classes.append(ShareClassInfo(
                class_name=_text(sc_el, "classFullName") or "",
                class_id=_text(sc_el, "classesId") or "",
                min_initial_investment=_opt_decimal(sc_el, "minInitialInvestment"),
                net_assets=_opt_decimal(sc_el, "netAssetsOfClass"),
                shares_outstanding=_opt_decimal(sc_el, "numberOfSharesOutstanding"),
                daily_nav=class_daily_nav,
                daily_flows=daily_flows,
                seven_day_net_yields=class_yields,
            ))

        # ----- Portfolio Securities (shared between v2 and v3) -----
        securities = _parse_securities(form_data, is_v2)

        return cls(
            general_info=general_info,
            series_info=series_info,
            share_classes=share_classes,
            securities=securities,
        )


# ---------------------------------------------------------------------------
# V3 time series parsing (daily entries with dates)
# ---------------------------------------------------------------------------

def _parse_v3_series_time_series(series_el):
    """Parse N-MFP3 series-level time series (20 daily entries with dates)."""
    seven_day_gross_yields = []
    for y_el in series_el.findall("sevenDayGrossYield"):
        seven_day_gross_yields.append({
            "date": _text(y_el, "sevenDayGrossYieldDate"),
            "gross_yield": _opt_decimal(y_el, "sevenDayGrossYieldValue"),
        })

    daily_nav = []
    for n_el in series_el.findall("dailyNetAssetValuePerShareSeries"):
        daily_nav.append({
            "date": _text(n_el, "dailyNetAssetValuePerShareDateSeries"),
            "nav_per_share": _opt_decimal(n_el, "dailyNetAssetValuePerShareSeries"),
        })

    liquidity_details = []
    for liq_el in series_el.findall("liquidAssetsDetails"):
        liquidity_details.append({
            "date": _text(liq_el, "totalLiquidAssetsNearPercentDate"),
            "daily_liquid_value": _opt_decimal(liq_el, "totalValueDailyLiquidAssets"),
            "weekly_liquid_value": _opt_decimal(liq_el, "totalValueWeeklyLiquidAssets"),
            "pct_daily_liquid": _opt_decimal(liq_el, "percentageDailyLiquidAssets"),
            "pct_weekly_liquid": _opt_decimal(liq_el, "percentageWeeklyLiquidAssets"),
        })

    return seven_day_gross_yields, daily_nav, liquidity_details


def _parse_v3_class_time_series(sc_el):
    """Parse N-MFP3 class-level time series."""
    class_daily_nav = []
    for n_el in sc_el.findall("dailyNetAssetValuePerShareClass"):
        class_daily_nav.append({
            "date": _text(n_el, "dailyNetAssetValuePerShareDateClass"),
            "nav_per_share": _opt_decimal(n_el, "dailyNetAssetValuePerShareClass"),
        })

    # SEC typo: "dialy" not "daily"
    daily_flows = []
    for f_el in sc_el.findall("dialyShareholderFlowReported"):
        daily_flows.append({
            "date": _text(f_el, "dailyShareHolderFlowDate"),
            "gross_subscriptions": _opt_decimal(f_el, "dailyGrossSubscriptions"),
            "gross_redemptions": _opt_decimal(f_el, "dailyGrossRedemptions"),
        })

    class_yields = []
    for y_el in sc_el.findall("sevenDayNetYield"):
        class_yields.append({
            "date": _text(y_el, "sevenDayNetYieldDate"),
            "net_yield": _opt_decimal(y_el, "sevenDayNetYieldValue"),
        })

    return class_daily_nav, daily_flows, class_yields


# ---------------------------------------------------------------------------
# V2 time series parsing (Friday-based weekly snapshots)
# ---------------------------------------------------------------------------

_FRIDAY_DAYS = ["fridayDay1", "fridayDay2", "fridayDay3", "fridayDay4"]
_FRIDAY_WEEKS = ["fridayWeek1", "fridayWeek2", "fridayWeek3", "fridayWeek4", "fridayWeek5"]


def _parse_v2_series_time_series(series_el):
    """Parse N-MFP2 series-level time series (Friday snapshots without dates)."""
    # Single scalar yield in v2
    gross_yield_val = _opt_decimal(series_el, "sevenDayGrossYield")
    seven_day_gross_yields = [{"date": None, "gross_yield": gross_yield_val}] if gross_yield_val is not None else []

    # NAV: fridayWeek1–5 inside <netAssetValue>
    daily_nav = []
    nav_el = series_el.find("netAssetValue")
    if nav_el is not None:
        for i, tag in enumerate(_FRIDAY_WEEKS, 1):
            val = _opt_decimal(nav_el, tag)
            if val is not None and val != Decimal("0"):
                daily_nav.append({"date": f"week_{i}", "nav_per_share": val})

    # Liquidity: daily uses fridayDay1-4, weekly uses fridayWeek1-5
    liquidity_details = []
    daily_liq_el = series_el.find("totalValueDailyLiquidAssets")
    weekly_liq_el = series_el.find("totalValueWeeklyLiquidAssets")
    pct_daily_el = series_el.find("percentageDailyLiquidAssets")
    pct_weekly_el = series_el.find("percentageWeeklyLiquidAssets")
    num_points = max(len(_FRIDAY_DAYS), len(_FRIDAY_WEEKS))
    for i in range(num_points):
        day_tag = _FRIDAY_DAYS[i] if i < len(_FRIDAY_DAYS) else None
        week_tag = _FRIDAY_WEEKS[i] if i < len(_FRIDAY_WEEKS) else None
        daily_val = _opt_decimal(daily_liq_el, day_tag) if daily_liq_el is not None and day_tag else None
        weekly_val = _opt_decimal(weekly_liq_el, week_tag) if weekly_liq_el is not None and week_tag else None
        pct_d = _opt_decimal(pct_daily_el, day_tag) if pct_daily_el is not None and day_tag else None
        pct_w = _opt_decimal(pct_weekly_el, week_tag) if pct_weekly_el is not None and week_tag else None
        if any(v is not None and v != Decimal("0") for v in (daily_val, weekly_val, pct_d, pct_w)):
            liquidity_details.append({
                "date": f"friday_{i + 1}",
                "daily_liquid_value": daily_val,
                "weekly_liquid_value": weekly_val,
                "pct_daily_liquid": pct_d,
                "pct_weekly_liquid": pct_w,
            })

    return seven_day_gross_yields, daily_nav, liquidity_details


def _parse_v2_class_time_series(sc_el):
    """Parse N-MFP2 class-level time series (Friday snapshots)."""
    # NAV: netAssetPerShare contains fridayWeek1–5
    class_daily_nav = []
    nap_el = sc_el.find("netAssetPerShare")
    if nap_el is not None:
        for i, tag in enumerate(_FRIDAY_WEEKS, 1):
            val = _opt_decimal(nap_el, tag)
            if val is not None and val != Decimal("0"):
                class_daily_nav.append({"date": f"week_{i}", "nav_per_share": val})

    # Flows: fridayWeek1–5 are direct children with weeklyGrossSubscriptions/Redemptions
    daily_flows = []
    for i, tag in enumerate(_FRIDAY_WEEKS, 1):
        fw_el = sc_el.find(tag)
        if fw_el is not None:
            subs = _opt_decimal(fw_el, "weeklyGrossSubscriptions")
            reds = _opt_decimal(fw_el, "weeklyGrossRedemptions")
            if subs is not None or reds is not None:
                daily_flows.append({
                    "date": f"week_{i}",
                    "gross_subscriptions": subs,
                    "gross_redemptions": reds,
                })

    # Yield: single scalar sevenDayNetYield
    class_yields = []
    net_yield_val = _opt_decimal(sc_el, "sevenDayNetYield")
    if net_yield_val is not None:
        class_yields.append({"date": None, "net_yield": net_yield_val})

    return class_daily_nav, daily_flows, class_yields


# ---------------------------------------------------------------------------
# Securities parsing (shared between v2 and v3)
# ---------------------------------------------------------------------------

def _parse_securities(form_data, is_v2: bool) -> List[PortfolioSecurity]:
    """Parse portfolio securities from either N-MFP2 or N-MFP3."""
    securities = []
    for sec_el in form_data.findall("scheduleOfPortfolioSecuritiesInfo"):
        # Ratings
        ratings = []
        for r_el in sec_el.findall("assigningNRSRORating"):
            agency = _text(r_el, "nameOfNRSRO")
            rating = _text(r_el, "rating")
            if agency and rating:
                ratings.append(CreditRating(agency=agency, rating=rating))

        # Repurchase agreement
        repo_agreement = None
        repo_el = sec_el.find("repurchaseAgreement")
        if repo_el is not None:
            collateral = []
            for coll_el in repo_el.findall("collateralIssuers"):
                mat_el = coll_el.find("maturityDate")
                mat_date = _text(mat_el, "date") if mat_el is not None else None
                # N-MFP2 uses "couponOrYield", N-MFP3 uses "coupon"
                coupon = _opt_decimal(coll_el, "couponOrYield") if is_v2 else _opt_decimal(coll_el, "coupon")
                collateral.append(CollateralIssuer(
                    issuer_name=_text(coll_el, "nameOfCollateralIssuer"),
                    lei=_text(coll_el, "LEIID"),
                    cusip=_text(coll_el, "CUSIPMember"),
                    maturity_date=mat_date,
                    coupon=coupon,
                    principal_amount=_opt_decimal(coll_el, "principalAmountToTheNearestCent"),
                    collateral_value=_opt_decimal(coll_el, "valueOfCollateralToTheNearestCent"),
                    collateral_category=_text(coll_el, "ctgryInvestmentsRprsntsCollateral"),
                ))
            repo_agreement = RepurchaseAgreement(
                open_flag=_flag(repo_el, "repurchaseAgreementOpenFlag"),
                cleared_flag=_flag(repo_el, "repurchaseAgreementClearedFlag"),
                tri_party_flag=_flag(repo_el, "repurchaseAgreementTripartyFlag"),
                collateral=collateral,
            )

        # CUSIP: N-MFP2 may use otherUniqueId when CUSIPMember is absent
        cusip = _text(sec_el, "CUSIPMember")
        if not cusip and is_v2:
            cusip = _text(sec_el, "otherUniqueId")

        securities.append(PortfolioSecurity(
            issuer_name=_text(sec_el, "nameOfIssuer"),
            title=_text(sec_el, "titleOfIssuer"),
            cusip=cusip,
            isin=_text(sec_el, "ISINId"),
            lei=_text(sec_el, "LEIID"),
            cik=_text(sec_el, "cik"),
            investment_category=_text(sec_el, "investmentCategory"),
            maturity_date_wam=_text(sec_el, "investmentMaturityDateWAM"),
            maturity_date_wal=_text(sec_el, "investmentMaturityDateWAL"),
            final_maturity_date=_text(sec_el, "finalLegalInvestmentMaturityDate"),
            yield_rate=_opt_decimal(sec_el, "yieldOfTheSecurityAsOfReportingDate"),
            market_value=_opt_decimal(sec_el, "includingValueOfAnySponsorSupport"),
            amortized_cost=_opt_decimal(sec_el, "excludingValueOfAnySponsorSupport"),
            pct_of_nav=_opt_decimal(sec_el, "percentageOfMoneyMarketFundNetAssets"),
            daily_liquid=_flag(sec_el, "dailyLiquidAssetSecurityFlag"),
            weekly_liquid=_flag(sec_el, "weeklyLiquidAssetSecurityFlag"),
            illiquid=_flag(sec_el, "illiquidSecurityFlag"),
            demand_feature=_flag(sec_el, "securityDemandFeatureFlag"),
            guarantee=_flag(sec_el, "securityGuaranteeFlag"),
            enhancement=_flag(sec_el, "securityEnhancementsFlag"),
            ratings=ratings,
            repo_agreement=repo_agreement,
        ))

    return securities
