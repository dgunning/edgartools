"""Rich rendering for 13F holdings reports."""

import math

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Column, Table
from rich.text import Text

__all__ = ['render_rich', 'render_holdings_view', 'infotable_summary', 'render_holdings_comparison', 'render_holdings_history', 'sparkline']

DEFAULT_DISPLAY_LIMIT = 200

SPARK_CHARS = "▁▂▃▅▇"


def _is_number(value) -> bool:
    """Return True if value is a finite number (not None, NaN, or non-numeric)."""
    try:
        return value is not None and not math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def sparkline(values) -> str:
    """Map a sequence of numeric values to a Unicode sparkline string.

    Uses mean-centred ±50% scaling so that small percentage changes
    appear proportionally small rather than filling the entire range.
    A 6% decline occupies ~6% of the visual range, not 100%.

    NaN / None values render as a space.
    If all values are the same (or all missing), returns a flat mid-bar.
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

    mid = len(SPARK_CHARS) // 2
    mean = sum(valid) / len(valid)

    if mean == 0:
        # All zeros — flat line
        return "".join(" " if n is None else SPARK_CHARS[mid] for n in nums)

    # Range covers mean ± 50%, so the full visual width represents
    # a 100-percentage-point swing.  Real changes (typically single-
    # digit %) use a proportionally small slice of the bar range.
    lo = mean * 0.5
    hi = mean * 1.5
    span = hi - lo  # always mean * 1.0

    chars = []
    for n in nums:
        if n is None:
            chars.append(" ")
        else:
            # Clamp to [lo, hi] so outliers don't break the index
            clamped = max(lo, min(hi, n))
            idx = int((clamped - lo) / span * (len(SPARK_CHARS) - 1))
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

            result = (holdings[available_cols]
                      .rename(columns={'SharesPrnAmount': 'Shares'} if 'SharesPrnAmount' in available_cols else {})
                      .assign(Value=lambda df: df.Value if 'Value' in df.columns else 0,
                              Type=lambda df: df.Type.fillna('-') if 'Type' in df.columns else '-',
                              Ticker=lambda df: df.Ticker.fillna('') if 'Ticker' in df.columns else '',
                              PutCall=lambda df: df.PutCall.fillna('') if 'PutCall' in df.columns else '')
                      .sort_values(['Value'], ascending=False)
                      )
            # Guarantee all columns that renderers expect
            for col, default in [('Issuer', ''), ('Class', ''), ('Cusip', ''),
                                 ('Ticker', ''), ('Value', 0), ('Type', '-'),
                                 ('Shares', 0), ('PutCall', '')]:
                if col not in result.columns:
                    result[col] = default
            return result
    return None


def render_rich(thirteen_f, display_limit: int = DEFAULT_DISPLAY_LIMIT):
    """
    Create Rich Panel display for a 13F filing.

    Args:
        thirteen_f: ThirteenF instance
        display_limit: Max holdings rows to display (default 200)

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
        total = len(infotable_summary_df)
        display_df = infotable_summary_df.head(display_limit)
        table = Table("", "Issuer", "Class", "Cusip", "Ticker", "Value", "Type", "Shares", "Put/Call",
                      row_styles=["bold", ""],
                      box=box.SIMPLE)
        for index, row in enumerate(display_df.itertuples()):
            value_str = f"${row.Value:,.0f}" if _is_number(row.Value) else "-"
            shares_str = f"{int(row.Shares):,.0f}" if _is_number(row.Shares) else "-"
            table.add_row(str(index),
                          str(row.Issuer) if row.Issuer else "",
                          str(row.Class) if row.Class else "",
                          str(row.Cusip) if row.Cusip else "",
                          str(row.Ticker) if row.Ticker else "",
                          value_str,
                          str(row.Type) if row.Type else "-",
                          shares_str,
                          str(row.PutCall) if row.PutCall else ""
                          )
        content.append(table)
        if total > display_limit:
            content.append(Text(f"  … and {total - display_limit} more (use .holdings for full DataFrame)", style="dim italic"))

    return Panel(
        Group(*content), title=title, subtitle=title
    )


def render_holdings_view(view, display_limit: int = DEFAULT_DISPLAY_LIMIT) -> Panel:
    """Render a HoldingsView as a Rich Panel (holdings table only)."""
    tf = view._thirteen_f
    title = f"Holdings: {tf.management_company_name} ({tf.report_period})"

    df = view.data
    total = len(df)
    display_df = df.head(display_limit)

    table = Table("", "Issuer", "Class", "Cusip", "Ticker", "Value", "Type", "Shares", "Put/Call",
                  row_styles=["bold", ""], box=box.SIMPLE)
    for index, row in enumerate(display_df.itertuples()):
        value_str = f"${row.Value:,.0f}" if _is_number(row.Value) else "-"
        shares_str = f"{int(row.Shares):,.0f}" if _is_number(row.Shares) else "-"
        table.add_row(str(index),
                      str(row.Issuer) if row.Issuer else "",
                      str(row.Class) if row.Class else "",
                      str(row.Cusip) if row.Cusip else "",
                      str(row.Ticker) if row.Ticker else "",
                      value_str,
                      str(row.Type) if row.Type else "-",
                      shares_str,
                      str(row.PutCall) if row.PutCall else "")

    content = [table]
    if total > display_limit:
        content.append(Text(f"  … and {total - display_limit} more (use .data for full DataFrame)", style="dim italic"))

    return Panel(Group(*content), title=title, subtitle=title)


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


def render_holdings_comparison(comparison, display_limit: int = DEFAULT_DISPLAY_LIMIT) -> Panel:
    """Render a HoldingsComparison as a Rich Panel."""
    title = f"Holdings Comparison: {comparison.manager_name}  {comparison.current_period} vs {comparison.previous_period}"
    df = comparison.data
    total = len(df)

    # Summary counts (always from full data)
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

    display_df = df.head(display_limit)
    for row in display_df.itertuples():
        shares = f"{int(row.Shares):,}" if _is_number(row.Shares) else "-"
        prev_shares = f"{int(row.PrevShares):,}" if _is_number(row.PrevShares) else "-"
        value = f"${int(row.Value):,}" if _is_number(row.Value) else "-"
        prev_value = f"${int(row.PrevValue):,}" if _is_number(row.PrevValue) else "-"

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

    content = [summary_line, table]
    if total > display_limit:
        content.append(Text(f"  … and {total - display_limit} more (use .data for full DataFrame)", style="dim italic"))

    return Panel(
        Group(*content),
        title=title,
        subtitle=title,
    )


def render_holdings_history(history, display_limit: int = DEFAULT_DISPLAY_LIMIT) -> Panel:
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
    columns.append(Column("Chg%", justify="right"))

    table = Table(*columns, box=box.SIMPLE, row_styles=["", "dim"])
    df = history.data
    total = len(df)
    display_df = df.head(display_limit)

    for _, row in display_df.iterrows():
        cells = [row.get('Issuer') or "", row.get('Ticker') or ""]
        values_for_spark = []
        for period in history.periods:
            val = row.get(period)
            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                cells.append(f"{int(val):,}")
                values_for_spark.append(val)
            else:
                cells.append("-")
                values_for_spark.append(None)
        cells.append(sparkline(values_for_spark))

        # First-to-last percentage change
        valid_vals = [v for v in values_for_spark if v is not None]
        if len(valid_vals) >= 2 and valid_vals[0] != 0:
            pct = (valid_vals[-1] - valid_vals[0]) / valid_vals[0] * 100
            cells.append(_fmt_change(pct, is_pct=True))
        else:
            cells.append(Text("-", style="dim"))

        table.add_row(*cells)

    content = [table]
    if total > display_limit:
        content.append(Text(f"  … and {total - display_limit} more (use .data for full DataFrame)", style="dim italic"))

    return Panel(
        Group(*content),
        title=title,
        subtitle=title,
    )
