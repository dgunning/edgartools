"""
Plain-text / AI-context rendering for SEC ownership forms (3, 4, 5).

``ownership_to_context`` produces the token-budgeted text summary returned by
``Ownership.to_context()``. Kept separate from the domain model (mirroring the
``html_render`` split) so the rendering logic can evolve independently.
"""
from typing import TYPE_CHECKING

from edgar.ownership.core import format_numeric

if TYPE_CHECKING:  # pragma: no cover
    from edgar.ownership.forms import Ownership


def ownership_to_context(ownership: "Ownership", detail: str = 'standard') -> str:
    """
    AI-optimized context string for an ownership form.

    Args:
        ownership: The Ownership (Form 3/4/5) instance to render.
        detail: 'minimal' (~100 tokens), 'standard' (~300 tokens), 'full' (~500+ tokens)
    """
    from edgar.display.formatting import format_currency_short

    form_label = f"FORM{ownership.form}"
    is_initial = ownership.form == "3"

    lines = []

    # === IDENTITY ===
    if is_initial:
        lines.append(f"{form_label}: Initial Ownership")
    else:
        lines.append(f"{form_label}: Insider Transaction")
    lines.append("")

    # === CORE METADATA ===
    issuer_str = ownership.issuer.name
    if ownership.issuer.ticker:
        issuer_str += f" ({ownership.issuer.ticker})"
    lines.append(f"Issuer: {issuer_str}")

    # Get summary for transaction/holding details
    try:
        summary = ownership.get_ownership_summary()
    except Exception:
        summary = None

    if is_initial:
        lines.append(f"Owner: {ownership.insider_name} ({ownership.position})")
        if ownership.no_securities:
            lines.append("Holdings: No securities reported")
        elif summary and hasattr(summary, 'total_shares'):
            lines.append(f"Holdings: {format_numeric(summary.total_shares)} shares")
    else:
        lines.append(f"Owner: {ownership.insider_name} ({ownership.position})")
        if summary and hasattr(summary, 'primary_activity'):
            lines.append(f"Activity: {summary.primary_activity}")
        lines.append(f"Date: {ownership.reporting_period}")

    if detail == 'minimal':
        return "\n".join(lines)

    # === STANDARD ===
    # Replace the inline owner with expanded fields
    lines_std = [lines[0], lines[1]]  # header + blank
    lines_std.append(f"Issuer: {issuer_str}")
    lines_std.append(f"CIK: {ownership.issuer.cik}")
    lines_std.append(f"Owner: {ownership.insider_name}")
    lines_std.append(f"Relationship: {ownership.position}")
    lines_std.append(f"Date: {ownership.reporting_period}")

    if is_initial:
        # Form 3: show holdings
        if ownership.no_securities:
            lines_std.append("")
            lines_std.append("No securities reported")
        elif summary and hasattr(summary, 'holdings'):
            holdings = summary.holdings
            if holdings:
                lines_std.append("")
                lines_std.append("HOLDINGS:")
                for h in holdings[:8]:
                    h_line = f"  {h.security_title}: {format_numeric(h.shares)} shares"
                    if h.is_derivative:
                        h_line += " (derivative)"
                    lines_std.append(h_line)
                if len(holdings) > 8:
                    lines_std.append(f"  ... ({len(holdings) - 8} more)")
    else:
        # Form 4/5: show transactions
        if summary and hasattr(summary, 'transactions'):
            txns = summary.transactions
            if txns:
                lines_std.append("")
                lines_std.append("TRANSACTIONS:")
                for t in txns[:5]:
                    shares_str = f"{t.shares_numeric:,.0f}" if t.shares_numeric else str(t.shares)
                    price_str = f"${t.price_numeric:,.2f}" if t.price_numeric else ""
                    value_str = format_currency_short(t.value_numeric) if t.value_numeric else ""
                    t_line = f"  {t.display_name}: {shares_str} shares"
                    if price_str:
                        t_line += f" at {price_str}"
                    if value_str:
                        t_line += f" ({value_str})"
                    lines_std.append(t_line)
                if len(txns) > 5:
                    lines_std.append(f"  ... ({len(txns) - 5} more)")

            # Holdings after
            if summary.remaining_shares is not None:
                lines_std.append("")
                lines_std.append("HOLDINGS AFTER:")
                lines_std.append(f"  {format_numeric(summary.remaining_shares)} shares")

    # Available actions
    lines_std.append("")
    lines_std.append("AVAILABLE ACTIONS:")
    if is_initial:
        lines_std.append("  .extract_form3_holdings()    All holdings as SecurityHolding list")
        lines_std.append("  .non_derivative_table        Common stock holdings")
        lines_std.append("  .derivative_table            Derivative holdings")
    else:
        lines_std.append("  .get_transaction_activities()  Normalized transaction list")
        lines_std.append("  .non_derivative_table          Non-derivative transactions/holdings")
        lines_std.append("  .derivative_table              Derivative transactions/holdings")
        lines_std.append("  .market_trades                 Open market buys and sells")
    lines_std.append("  .reporting_owners              Owner details")
    lines_std.append("  .to_dataframe()                Summary as DataFrame")
    lines_std.append("  .get_ownership_summary()       Structured summary object")

    if detail == 'standard':
        return "\n".join(lines_std)

    # === FULL ===
    # Add derivative details if present
    if not is_initial and not ownership.derivative_table.empty:
        dt = ownership.derivative_table
        if dt.has_transactions and not dt.transactions.empty:
            lines_std.append("")
            lines_std.append("DERIVATIVE TRANSACTIONS:")
            df = dt.transactions.data
            for i, row in df.head(5).iterrows():
                d_line = f"  {row.get('Security', '')}: {row.get('Underlying', '')}"
                lines_std.append(d_line)
            if len(df) > 5:
                lines_std.append(f"  ... ({len(df) - 5} more)")

    # 10b5-1 plan flag
    if not is_initial and summary and hasattr(summary, 'has_10b5_1_plan'):
        plan = summary.has_10b5_1_plan
        if plan is True:
            lines_std.append("")
            lines_std.append("10b5-1 Plan: Yes")
        elif plan is False:
            lines_std.append("")
            lines_std.append("10b5-1 Plan: No")

    # Remarks
    if ownership.remarks:
        lines_std.append("")
        lines_std.append(f"Remarks: {ownership.remarks[:200]}")

    return "\n".join(lines_std)
