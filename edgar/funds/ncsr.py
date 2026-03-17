"""
N-CSR / N-CSRS Fund Shareholder Report data object.

N-CSR (annual) and N-CSRS (semiannual) are certified shareholder reports
filed by registered investment companies.  They contain Inline XBRL using the
``oef:`` (Open-End Fund) taxonomy — so ``from_filing()`` calls
``filing.xbrl()`` and queries via the ``FactQuery`` API rather than raw XML
parsing.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Dict, List, Optional

import pandas as pd
from pydantic import BaseModel
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table

from edgar.display.formatting import moneyfmt
from edgar.richtools import df_to_rich_table, repr_rich

log = logging.getLogger(__name__)

__all__ = ['FundShareholderReport', 'NCSR_FORMS']

NCSR_FORMS = ["N-CSR", "N-CSR/A", "N-CSRS", "N-CSRS/A"]


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AnnualReturn(BaseModel):
    """A single annual-return data point for a share class."""
    period_label: str = ""
    return_pct: Optional[Decimal] = None
    inception_date: Optional[str] = None


class Holding(BaseModel):
    """A top-holding entry for a share class."""
    name: str = ""
    pct_of_nav: Optional[Decimal] = None
    pct_of_total_inv: Optional[Decimal] = None


class ShareClassInfo(BaseModel):
    """Per-share-class data extracted from the OEF taxonomy."""
    class_name: str = ""
    class_ticker: Optional[str] = None
    expense_ratio_pct: Optional[Decimal] = None
    expenses_paid_amt: Optional[Decimal] = None
    advisory_fees_paid: Optional[Decimal] = None
    annual_returns: List[AnnualReturn] = []
    holdings: List[Holding] = []
    holdings_count: Optional[int] = None

    def __str__(self):
        ticker = f" ({self.class_ticker})" if self.class_ticker else ""
        return f"{self.class_name}{ticker}"


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class FundShareholderReport:
    """
    Certified Shareholder Report for Registered Investment Companies (N-CSR / N-CSRS).

    Wraps the Inline XBRL ``oef:`` taxonomy data into a convenient object
    with DataFrames for performance, expenses and holdings.

    Usage:
        >>> filing = Filing(form='N-CSR', ...)
        >>> report = filing.obj()
        >>> report.fund_name
        'Vanguard 500 Index Fund'
        >>> report.expense_data()
    """

    def __init__(self,
                 fund_name: str,
                 report_type: str,
                 net_assets: Optional[Decimal] = None,
                 portfolio_turnover: Optional[Decimal] = None,
                 share_classes: Optional[List[ShareClassInfo]] = None):
        self._fund_name = fund_name
        self._report_type = report_type  # "Annual" or "Semi-Annual"
        self._net_assets = net_assets
        self._portfolio_turnover = portfolio_turnover
        self.share_classes = share_classes or []
        self._filing = None
        self._cik = None
        self._series_id = None
        self._performance_data = None
        self._expense_data = None
        self._holdings_data = None

    def __str__(self):
        n_classes = len(self.share_classes)
        return f"FundShareholderReport({self._fund_name}, {self._report_type}, {n_classes} classes)"

    # -------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------

    @property
    def filing(self):
        """The source Filing object, if this report was created via from_filing()."""
        return self._filing

    @property
    def cik(self) -> Optional[str]:
        """CIK of the fund company, extracted from the source filing."""
        return self._cik

    @property
    def series_id(self) -> Optional[str]:
        """Series ID, extracted from the source filing header."""
        return self._series_id

    @property
    def fund_name(self) -> str:
        return self._fund_name

    @property
    def report_type(self) -> str:
        return self._report_type

    @property
    def is_annual(self) -> bool:
        return self._report_type == "Annual"

    @property
    def net_assets(self) -> Optional[Decimal]:
        return self._net_assets

    @property
    def portfolio_turnover(self) -> Optional[Decimal]:
        return self._portfolio_turnover

    @property
    def num_share_classes(self) -> int:
        return len(self.share_classes)

    # -------------------------------------------------------------------
    # DataFrame methods
    # -------------------------------------------------------------------

    def performance_data(self) -> pd.DataFrame:
        """Annual returns for all share classes."""
        if self._performance_data is not None:
            return self._performance_data
        rows: list[dict] = []
        for sc in self.share_classes:
            for ar in sc.annual_returns:
                rows.append({
                    "class_name": sc.class_name,
                    "ticker": sc.class_ticker,
                    "period": ar.period_label,
                    "return_pct": float(ar.return_pct) if ar.return_pct is not None else None,
                    "inception_date": ar.inception_date,
                })
        self._performance_data = pd.DataFrame(rows)
        return self._performance_data

    def expense_data(self) -> pd.DataFrame:
        """Expense ratios and fees for all share classes."""
        if self._expense_data is not None:
            return self._expense_data
        rows: list[dict] = []
        for sc in self.share_classes:
            rows.append({
                "class_name": sc.class_name,
                "ticker": sc.class_ticker,
                "expense_ratio_pct": float(sc.expense_ratio_pct) if sc.expense_ratio_pct is not None else None,
                "expenses_paid": float(sc.expenses_paid_amt) if sc.expenses_paid_amt is not None else None,
                "advisory_fees_paid": float(sc.advisory_fees_paid) if sc.advisory_fees_paid is not None else None,
            })
        self._expense_data = pd.DataFrame(rows)
        return self._expense_data

    def holdings_data(self) -> pd.DataFrame:
        """Top holdings for all share classes."""
        if self._holdings_data is not None:
            return self._holdings_data
        rows: list[dict] = []
        for sc in self.share_classes:
            for h in sc.holdings:
                rows.append({
                    "class_name": sc.class_name,
                    "holding": h.name,
                    "pct_of_nav": float(h.pct_of_nav) if h.pct_of_nav is not None else None,
                    "pct_of_total_inv": float(h.pct_of_total_inv) if h.pct_of_total_inv is not None else None,
                })
        self._holdings_data = pd.DataFrame(rows)
        return self._holdings_data

    # -------------------------------------------------------------------
    # Rich display
    # -------------------------------------------------------------------

    @property
    def _summary_table(self) -> Table:
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("Fund", self._fund_name)
        table.add_row("Report Type", self._report_type)
        if self._net_assets is not None:
            table.add_row("Net Assets", moneyfmt(self._net_assets, curr="$", places=0))
        if self._portfolio_turnover is not None:
            table.add_row("Portfolio Turnover", f"{self._portfolio_turnover}%")
        table.add_row("Share Classes", str(self.num_share_classes))
        return table

    @property
    def _expense_table(self) -> Optional[Table]:
        df = self.expense_data()
        if df.empty:
            return None
        display = df.copy()
        display = display.rename(columns={
            "class_name": "Class",
            "ticker": "Ticker",
            "expense_ratio_pct": "Expense Ratio %",
            "expenses_paid": "Expenses Paid",
            "advisory_fees_paid": "Advisory Fees",
        })
        return df_to_rich_table(
            display,
            title="Expenses",
            title_style="bold deep_sky_blue1",
            max_rows=20,
        )

    @property
    def _performance_table(self) -> Optional[Table]:
        df = self.performance_data()
        if df.empty:
            return None
        display = df.copy()
        display = display.rename(columns={
            "class_name": "Class",
            "ticker": "Ticker",
            "period": "Period",
            "return_pct": "Return %",
            "inception_date": "Inception",
        })
        return df_to_rich_table(
            display,
            title="Performance",
            title_style="bold deep_sky_blue1",
            max_rows=30,
        )

    def to_context(self, detail: str = 'standard') -> str:
        """
        AI-optimized context string.

        Args:
            detail: 'minimal' (~100 tokens), 'standard' (~300 tokens), 'full' (~500+ tokens)
        """
        from edgar.display.formatting import format_currency_short
        lines = []

        # === IDENTITY ===
        lines.append(f"FUNDSHAREHOLDERREPORT: {self.fund_name}")
        lines.append("")

        # === CORE METADATA ===
        lines.append(f"Report Type: {self.report_type}")
        if self.net_assets:
            lines.append(f"Net Assets: {format_currency_short(float(self.net_assets))}")
        lines.append(f"Share Classes: {self.num_share_classes}")

        if detail == 'minimal':
            return "\n".join(lines)

        # === STANDARD ===
        lines.append(f"CIK: {self.cik}")
        if self.series_id:
            lines.append(f"Series ID: {self.series_id}")
        if self.portfolio_turnover:
            lines.append(f"Portfolio Turnover: {float(self.portfolio_turnover):.1f}%")

        lines.append("")
        lines.append("AVAILABLE ACTIONS:")
        lines.append("  .performance_data()        Returns by share class and period")
        lines.append("  .expense_data()            Expense ratios by share class")
        lines.append("  .holdings_data()           Portfolio holdings by class")
        lines.append("  .share_classes             Share class details list")

        if detail == 'standard':
            return "\n".join(lines)

        # === FULL ===
        try:
            if self.share_classes:
                lines.append("")
                lines.append("SHARE CLASSES:")
                for sc in self.share_classes[:8]:
                    sc_line = f"  {sc.class_name}"
                    if hasattr(sc, 'ticker') and sc.ticker:
                        sc_line += f" ({sc.ticker})"
                    if hasattr(sc, 'expense_ratio_pct') and sc.expense_ratio_pct:
                        sc_line += f" ER: {float(sc.expense_ratio_pct):.2f}%"
                    lines.append(sc_line)
        except Exception:
            pass

        return "\n".join(lines)

    def __rich__(self):
        renderables = [self._summary_table]
        expense = self._expense_table
        if expense:
            renderables.append(expense)
        perf = self._performance_table
        if perf:
            renderables.append(perf)

        return Panel(
            Group(*renderables),
            title=self._fund_name,
            subtitle=f"Fund Shareholder Report ({self._report_type})",
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    # -------------------------------------------------------------------
    # Parsing
    # -------------------------------------------------------------------

    @classmethod
    def from_filing(cls, filing) -> Optional['FundShareholderReport']:
        """Create a FundShareholderReport from a Filing object."""
        xbrl = filing.xbrl()
        if not xbrl:
            return None
        report_type = "Semi-Annual" if "CSRS" in (filing.form or "") else "Annual"
        report = cls._parse_xbrl(xbrl, report_type)
        if report is not None:
            report._filing = filing
            report._cik = str(filing.cik) if hasattr(filing, 'cik') else None
            # Extract series_id from filing header if available
            header = getattr(filing, 'header', None)
            if header:
                series_id = getattr(header, 'series_id', None)
                if series_id:
                    report._series_id = series_id
        return report

    @classmethod
    def _parse_xbrl(cls, xbrl, report_type: str = "Annual") -> 'FundShareholderReport':
        """Parse OEF Inline XBRL into a FundShareholderReport."""
        facts = xbrl.facts

        # --- Fund-level facts (no dimensions) ---
        fund_name = _get_text_fact(facts, "oef:FundName") or xbrl.entity_name or ""
        net_assets = _get_numeric_fact(facts, "oef:NetAssetsOfSeriesMember")
        if net_assets is None:
            net_assets = _get_numeric_fact(facts, "oef:NetAssets")
        portfolio_turnover = _get_numeric_fact(facts, "oef:PortfolioTurnoverRt")
        if portfolio_turnover is None:
            portfolio_turnover = _get_numeric_fact(facts, "us-gaap:InvestmentCompanyPortfolioTurnover")

        # --- Discover share classes via ClassAxis ---
        class_members = _discover_class_members(facts)

        share_classes: List[ShareClassInfo] = []
        for member_id, member_label in class_members:
            sc = _parse_share_class(facts, member_id, member_label)
            share_classes.append(sc)

        # If no share classes were discovered via dimensions, create a
        # single placeholder class from undimensioned facts
        if not share_classes:
            sc = _parse_undimensioned_share_class(facts, fund_name)
            if sc.expense_ratio_pct is not None or sc.annual_returns or sc.holdings:
                share_classes.append(sc)

        return cls(
            fund_name=fund_name,
            report_type=report_type,
            net_assets=net_assets,
            portfolio_turnover=portfolio_turnover,
            share_classes=share_classes,
        )


# ---------------------------------------------------------------------------
# XBRL extraction helpers
# ---------------------------------------------------------------------------

def _safe_decimal(val) -> Optional[Decimal]:
    """Convert a value to Decimal, returning None for non-numeric or non-finite values."""
    if val is None:
        return None
    try:
        d = Decimal(str(val))
        if not d.is_finite():
            return None
        return d
    except Exception:
        return None


def _get_text_fact(facts, concept: str) -> Optional[str]:
    """Get the first text value for an undimensioned concept."""
    try:
        results = facts.query().by_concept(concept, exact=True).execute()
        # Prefer undimensioned facts
        for r in results:
            if not any(k.startswith("dim_") for k in r):
                val = r.get("value")
                if val is not None:
                    return str(val).strip()
        # Fall back to first result
        if results:
            val = results[0].get("value")
            if val is not None:
                return str(val).strip()
    except Exception:
        pass
    return None


def _get_numeric_fact(facts, concept: str, member_id: Optional[str] = None) -> Optional[Decimal]:
    """Get the first numeric value for a concept, optionally filtered by ClassAxis member."""
    try:
        q = facts.query().by_concept(concept, exact=True)
        if member_id:
            q = q.by_dimension("oef:ClassAxis", member_id)
        results = q.execute()
        if not results:
            return None
        return _safe_decimal(results[0].get("value"))
    except Exception:
        pass
    return None


def _discover_class_members(facts) -> List[tuple]:
    """Return [(member_id, member_label), ...] for all ClassAxis members."""
    seen: Dict[str, str] = {}
    try:
        results = facts.query().by_dimension("oef:ClassAxis").with_dimensions().execute()
        for r in results:
            for key, value in r.items():
                if key.startswith("dim_") and key.endswith("_ClassAxis") and value:
                    member_id = str(value)
                    if member_id not in seen:
                        # Use a human-readable label if available, else derive from member_id
                        label = (r.get("dimension_member_label") or
                                 r.get("dimension_label") or
                                 _member_id_to_label(member_id))
                        seen[member_id] = label
    except Exception:
        pass
    return list(seen.items())


def _member_id_to_label(member_id: str) -> str:
    """Derive a human-readable label from a dimension member ID.

    E.g. ``oef:C000012345Member`` → ``C000012345``
         ``oef:ClassAMember``     → ``Class A``
    """
    label = member_id
    # Strip namespace prefix
    if ":" in label:
        label = label.rsplit(":", 1)[-1]
    # Strip trailing "Member"
    if label.endswith("Member"):
        label = label[:-6]
    return label


def _parse_share_class(facts, member_id: str, member_label: str) -> ShareClassInfo:
    """Build a ShareClassInfo from dimensioned facts for a single ClassAxis member."""
    # Ticker
    class_ticker = None
    try:
        q = facts.query().by_concept("oef:ClassTicker", exact=True).by_dimension("oef:ClassAxis", member_id)
        results = q.execute()
        if results:
            val = results[0].get("value")
            if val:
                class_ticker = str(val).strip()
    except Exception:
        pass

    # Class name — try ClassName, ClassNameDerived, ShareClassNm, or fall back to label
    class_name = member_label
    for concept in ["oef:ClassName", "oef:ClassNameDerived", "oef:ShareClassNm"]:
        try:
            q = facts.query().by_concept(concept, exact=True).by_dimension("oef:ClassAxis", member_id)
            results = q.execute()
            if results:
                val = results[0].get("value")
                if val:
                    class_name = str(val).strip()
                    break
        except Exception:
            pass

    # Expense ratio
    expense_ratio = _get_numeric_fact(facts, "oef:ExpenseRatioPct", member_id)
    if expense_ratio is None:
        expense_ratio = _get_numeric_fact(facts, "oef:ExpensesPctOfAvgNetAssets", member_id)

    # Expenses paid
    expenses_paid = _get_numeric_fact(facts, "oef:ExpensesPaidAmt", member_id)

    # Advisory fees paid
    advisory_fees = _get_numeric_fact(facts, "oef:AdvisoryFeesPaidAmt", member_id)

    # Annual returns
    annual_returns = _parse_annual_returns(facts, member_id)

    # Holdings
    holdings, holdings_count = _parse_holdings(facts, member_id)

    return ShareClassInfo(
        class_name=class_name,
        class_ticker=class_ticker,
        expense_ratio_pct=expense_ratio,
        expenses_paid_amt=expenses_paid,
        advisory_fees_paid=advisory_fees,
        annual_returns=annual_returns,
        holdings=holdings,
        holdings_count=holdings_count,
    )


def _parse_undimensioned_share_class(facts, fund_name: str) -> ShareClassInfo:
    """Build a ShareClassInfo from undimensioned facts (single-class fund)."""
    expense_ratio = _get_numeric_fact(facts, "oef:ExpenseRatioPct")
    if expense_ratio is None:
        expense_ratio = _get_numeric_fact(facts, "oef:ExpensesPctOfAvgNetAssets")

    expenses_paid = _get_numeric_fact(facts, "oef:ExpensesPaidAmt")
    advisory_fees = _get_numeric_fact(facts, "oef:AdvisoryFeesPaidAmt")

    # Also query returns and holdings for single-class funds
    annual_returns = _parse_annual_returns_undimensioned(facts)
    holdings, holdings_count = _parse_holdings_undimensioned(facts)

    return ShareClassInfo(
        class_name=fund_name,
        expense_ratio_pct=expense_ratio,
        expenses_paid_amt=expenses_paid,
        advisory_fees_paid=advisory_fees,
        annual_returns=annual_returns,
        holdings=holdings,
        holdings_count=holdings_count,
    )


def _parse_annual_returns(facts, member_id: str) -> List[AnnualReturn]:
    """Extract average annual return data for a share class."""
    returns: List[AnnualReturn] = []
    try:
        q = facts.query().by_concept("oef:AvgAnnlRtrPct", exact=True).by_dimension("oef:ClassAxis", member_id)
        results = q.execute()
    except Exception:
        return returns
    for r in results:
        try:
            period_end = r.get("period_end", "")
            return_pct = _safe_decimal(r.get("value"))
            # Look for a ColumnAxis dimension to get the period label (1yr, 5yr, etc.)
            col_label = ""
            for k, v in r.items():
                if k.endswith("_ColumnAxis"):
                    col_label = str(v)
                    break
            label = col_label or period_end
            returns.append(AnnualReturn(
                period_label=label,
                return_pct=return_pct,
            ))
        except Exception:
            log.warning("Skipping malformed annual return fact: %r", r.get("value"))
    return returns


def _parse_annual_returns_undimensioned(facts) -> List[AnnualReturn]:
    """Extract average annual return data for undimensioned (single-class) funds."""
    returns: List[AnnualReturn] = []
    try:
        q = facts.query().by_concept("oef:AvgAnnlRtrPct", exact=True)
        results = q.execute()
    except Exception:
        return returns
    for r in results:
        # Skip dimensioned facts
        if any(k.startswith("dim_") for k in r):
            continue
        try:
            period_end = r.get("period_end", "")
            return_pct = _safe_decimal(r.get("value"))
            returns.append(AnnualReturn(
                period_label=period_end,
                return_pct=return_pct,
            ))
        except Exception:
            pass
    return returns


def _parse_holdings(facts, member_id: str) -> tuple:
    """Extract top holdings for a share class. Returns (holdings_list, count)."""
    holdings: List[Holding] = []
    holdings_count = None

    # Number of holdings
    try:
        q = facts.query().by_concept("oef:HoldingsCount", exact=True).by_dimension("oef:ClassAxis", member_id)
        results = q.execute()
        if results:
            d = _safe_decimal(results[0].get("value"))
            if d is not None:
                holdings_count = int(d)
    except Exception:
        pass

    # Top holdings by percentage of NAV
    try:
        q = facts.query().by_concept("oef:HoldingPctOfNav", exact=True).by_dimension("oef:ClassAxis", member_id)
        results = q.execute()
    except Exception:
        return holdings, holdings_count
    for r in results:
        try:
            name = ""
            for k, v in r.items():
                if k.startswith("dim_") and "HoldingAxis" in k:
                    name = _member_id_to_label(str(v))
                    break
            pct = _safe_decimal(r.get("value"))
            if name or pct is not None:
                holdings.append(Holding(name=name, pct_of_nav=pct))
        except Exception:
            log.warning("Skipping malformed holding fact: %r", r.get("value"))

    return holdings, holdings_count


def _parse_holdings_undimensioned(facts) -> tuple:
    """Extract top holdings for undimensioned (single-class) funds."""
    holdings: List[Holding] = []
    holdings_count = None

    try:
        q = facts.query().by_concept("oef:HoldingsCount", exact=True)
        results = q.execute()
        # Take the first undimensioned result
        for r in results:
            if not any(k.startswith("dim_") for k in r):
                d = _safe_decimal(r.get("value"))
                if d is not None:
                    holdings_count = int(d)
                break
    except Exception:
        pass

    return holdings, holdings_count
