"""Rich rendering for 13F holdings reports."""

import math

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Column, Table
from rich.text import Text

__all__ = ['render_rich', 'infotable_summary', 'render_holdings_comparison', 'render_holdings_history', 'sparkline']

SPARK_CHARS = "▁▂▃▅▇"


def sparkline(values) -> str:
    """Map a sequence of numeric values to a Unicode sparkline string.

    NaN / None values render as a space.
    If all values are the same (or all missing), returns a flat line.
    """
    nums = []
    for v in values:
        try:
            f = float(v)
            nums.append(f if not math.isnan(f) else None)
        except (TypeError, ValueError):
            nums.append(None)

    valid = [n for n in nums if n is not None]
    if not valid:
        return " " * len(nums)

    lo, hi = min(valid), max(valid)
    span = hi - lo

    chars = []
    for n in nums:
        if n is None:
            chars.append(" ")
        elif span == 0:
            chars.append(SPARK_CHARS[len(SPARK_CHARS) // 2])
        else:
            idx = int((n - lo) / span * (len(SPARK_CHARS) - 1))
            chars.append(SPARK_CHARS[idx])
    return "".join(chars)


def infotable_summary(thirteen_f):
    """
    Create a summary DataFrame of holdings for display (aggregated by security).

    Uses the aggregated holdings view which provides one row per security,
    matching industry-standard presentation.

    Args:
        thirteen_f: ThirteenF instance

    Returns:
        pd.DataFrame or None: Summary of holdings sorted by value (aggregated view)
    """
    if thirteen_f.has_infotable():
        holdings = thirteen_f.holdings
        if holdings is not None and len(holdings) > 0:
            # Select columns that exist (filter automatically handles missing columns)
            display_cols = ['Issuer', 'Class', 'Cusip', 'Ticker', 'Value', 'SharesPrnAmount',
                           'Type', 'PutCall', 'SoleVoting', 'SharedVoting', 'NonVoting']
            available_cols = [col for col in display_cols if col in holdings.columns]

            return (holdings[available_cols]
                    .rename(columns={'SharesPrnAmount': 'Shares'} if 'SharesPrnAmount' in available_cols else {})
                    .assign(Value=lambda df: df.Value if 'Value' in df.columns else 0,
                            Type=lambda df: df.Type.fillna('-') if 'Type' in df.columns else '-',
                            Ticker=lambda df: df.Ticker.fillna('') if 'Ticker' in df.columns else '')
                    .sort_values(['Value'], ascending=False)
                    )
    return None


def render_rich(thirteen_f):
    """
    Create Rich Panel display for a 13F filing.

    Args:
        thirteen_f: ThirteenF instance

    Returns:
        Panel: Rich Panel containing filing summary and holdings table
    """
    title = f"{thirteen_f.form} Holding Report for {thirteen_f.filing.company} for period {thirteen_f.report_period}"
    summary = Table(
        "Report Period",
        Column("Investment Manager", style="bold deep_sky_blue1"),
        "Signed By",
        "Holdings",
        "Value",
        "Accession Number",
        "Filed",
        box=box.SIMPLE)

    summary.add_row(
        thirteen_f.report_period,
        thirteen_f.investment_manager.name if thirteen_f.investment_manager else thirteen_f.manager_name,
        thirteen_f.signer or "-",
        str(thirteen_f.total_holdings or "-"),
        f"${thirteen_f.total_value:,.0f}" if thirteen_f.total_value else "-",
        thirteen_f.filing.accession_no,
        thirteen_f.filing_date
    )

    content = [summary]

    # Other Included Managers (only show if there are any)
    other_managers = thirteen_f.other_managers
    if other_managers:
        managers_table = Table(
            Column("#", style="dim"),
            Column("Other Included Manager", style="bold"),
            "CIK",
            "File Number",
            title=f"Other Included Managers ({len(other_managers)})",
            box=box.SIMPLE,
            title_style="bold italic"
        )
        for mgr in other_managers:
            managers_table.add_row(
                str(mgr.sequence_number) if mgr.sequence_number else "-",
                mgr.name or "-",
                mgr.cik or "-",
                mgr.file_number or "-"
            )
        content.append(managers_table)

    # info table
    infotable_summary_df = infotable_summary(thirteen_f)
    if infotable_summary_df is not None:
        table = Table("", "Issuer", "Class", "Cusip", "Ticker", "Value", "Type", "Shares", "Put/Call",
                      row_styles=["bold", ""],
                      box=box.SIMPLE)
        for index, row in enumerate(infotable_summary_df.itertuples()):
            table.add_row(str(index),
                          row.Issuer,
                          row.Class,
                          row.Cusip,
                          row.Ticker,
                          f"${row.Value:,.0f}",
                          row.Type,
                          f"{int(row.Shares):,.0f}",
                          row.PutCall
                          )
        content.append(table)

    return Panel(
        Group(*content), title=title, subtitle=title
    )


def _status_text(status: str) -> Text:
    """Return a styled Text for a holdings comparison status."""
    if status == "NEW":
        return Text("NEW", style="bold green")
    elif status == "CLOSED":
        return Text("CLOSED", style="bold red")
    elif status == "INCREASED":
        return Text("▲ INCREASED", style="green")
    elif status == "DECREASED":
        return Text("▼ DECREASED", style="red")
    else:
        return Text("• UNCHANGED", style="dim")


def _fmt_change(value, is_pct=False) -> Text:
    """Format a numeric change value with color."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return Text("-", style="dim")
    if is_pct:
        label = f"{value:+,.1f}%"
    else:
        label = f"{value:+,.0f}"
    if value > 0:
        return Text(label, style="green")
    elif value < 0:
        return Text(label, style="red")
    return Text(label, style="dim")


def render_holdings_comparison(comparison) -> Panel:
    """Render a HoldingsComparison as a Rich Panel."""
    title = f"Holdings Comparison: {comparison.manager_name}  {comparison.current_period} vs {comparison.previous_period}"
    df = comparison.data

    # Summary counts
    status_counts = df['Status'].value_counts()
    summary_parts = []
    for status, style in [("NEW", "bold green"), ("CLOSED", "bold red"),
                          ("INCREASED", "green"), ("DECREASED", "red"),
                          ("UNCHANGED", "dim")]:
        count = status_counts.get(status, 0)
        if count:
            summary_parts.append(Text(f"{status}: {count}", style=style))
            summary_parts.append(Text("  "))

    summary_line = Text()
    for part in summary_parts:
        summary_line.append_text(part)

    # Main table
    table = Table(
        Column("Issuer", max_width=30),
        Column("Ticker", style="bold"),
        Column("Shares", justify="right"),
        Column("Prev Shares", justify="right"),
        Column("Chg", justify="right"),
        Column("Chg%", justify="right"),
        Column("Value($K)", justify="right"),
        Column("Prev Val($K)", justify="right"),
        Column("Val Chg", justify="right"),
        Column("Status"),
        box=box.SIMPLE,
        row_styles=["", "dim"],
    )

    for row in df.itertuples():
        shares = f"{int(row.Shares):,}" if not math.isnan(row.Shares) else "-"
        prev_shares = f"{int(row.PrevShares):,}" if not math.isnan(row.PrevShares) else "-"
        value = f"${int(row.Value):,}" if not math.isnan(row.Value) else "-"
        prev_value = f"${int(row.PrevValue):,}" if not math.isnan(row.PrevValue) else "-"

        table.add_row(
            row.Issuer or "",
            row.Ticker or "",
            shares,
            prev_shares,
            _fmt_change(row.ShareChange),
            _fmt_change(row.ShareChangePct, is_pct=True),
            value,
            prev_value,
            _fmt_change(row.ValueChange),
            _status_text(row.Status),
        )

    return Panel(
        Group(summary_line, table),
        title=title,
        subtitle=title,
    )


def render_holdings_history(history) -> Panel:
    """Render a HoldingsHistory as a Rich Panel."""
    n = len(history.periods)
    title = f"Holdings History: {history.manager_name} ({n} quarters)"

    columns = [
        Column("Issuer", max_width=30),
        Column("Ticker", style="bold"),
    ]
    # Period columns oldest→newest (already in that order in history.periods after reversal in method)
    for period in history.periods:
        columns.append(Column(str(period), justify="right"))
    columns.append(Column("Trend", justify="center"))

    table = Table(*columns, box=box.SIMPLE, row_styles=["", "dim"])

    for row in history.data.itertuples():
        cells = [row.Issuer or "", row.Ticker or ""]
        values_for_spark = []
        for period in history.periods:
            val = getattr(row, str(period), None)
            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                cells.append(f"{int(val):,}")
                values_for_spark.append(val)
            else:
                cells.append("-")
                values_for_spark.append(None)
        cells.append(sparkline(values_for_spark))
        table.add_row(*cells)

    return Panel(
        Group(table),
        title=title,
        subtitle=title,
    )
