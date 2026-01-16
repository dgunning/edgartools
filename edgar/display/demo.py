#!/usr/bin/env python3
"""
EdgarTools Display Demo

Run this script to preview the design language and iterate on styles.

Usage:
    python -m edgar.display.demo
    python edgar/display/demo.py
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from edgar.display.styles import (
    PALETTE,
    SYMBOLS,
    get_style,
    styled,
    company_title,
    label_value,
    identifier,
    get_statement_styles,
    source_text,
)
from edgar.display.formatting import accession_number_text, cik_text

console = Console()


# =============================================================================
# CARD COMPONENTS
# =============================================================================

def card_border() -> box.Box:
    """Standard card border - rounded corners."""
    return box.ROUNDED


def thin_separator() -> str:
    """Single line separator for within cards."""
    return "\u2500" * 40  # horizontal line


# =============================================================================
# COMPANY CARD MOCKUP
# =============================================================================

def demo_company_card():
    """Demonstrate the Company card design."""

    # Header zone
    header = Text.assemble(
        ("Apple Inc.", get_style("company_name")),
        " ",
        ("AAPL", get_style("ticker"))
    )

    # Main info - key-value pairs
    info_table = Table(box=None, show_header=False, padding=(0, 2))
    info_table.add_column("Label", style=get_style("label"))
    info_table.add_column("Value")

    info_table.add_row("CIK", Text("0000320193", style=get_style("cik")))
    info_table.add_row("Type", "Large Accelerated Filer")
    info_table.add_row("Industry", "3571: Electronic Computers")
    info_table.add_row("Fiscal Year End", "September")

    # Combine into card
    card = Panel(
        info_table,
        title=header,
        title_align="left",
        border_style=get_style("border"),
        box=card_border(),
        padding=(0, 1),
        expand=False,
    )

    return card


def demo_company_card_v2():
    """Alternate Company card - more compact."""

    # Title line with ticker inline
    title = Text.assemble(
        ("Apple Inc.", get_style("company_name")),
        " ",
        ("AAPL", get_style("ticker")),
        "  ",
        (SYMBOLS["pipe"], get_style("separator")),
        "  ",
        ("CIK ", get_style("label")),
        ("0000320193", get_style("cik")),
    )

    # Details as a single line
    details = Text.assemble(
        ("Large Accelerated Filer", get_style("metadata")),
        ("  ", ""),
        (SYMBOLS["bullet"], get_style("separator")),
        ("  ", ""),
        ("3571: Electronic Computers", get_style("metadata")),
        ("  ", ""),
        (SYMBOLS["bullet"], get_style("separator")),
        ("  ", ""),
        ("FYE: September", get_style("metadata")),
    )

    card = Panel(
        details,
        title=title,
        title_align="left",
        border_style=get_style("border"),
        box=card_border(),
        padding=(0, 1),
        expand=False,
    )

    return card


# =============================================================================
# FILING CARD MOCKUP
# =============================================================================

def demo_filing_card():
    """Demonstrate the Filing card design."""

    # Title: Form + Company + Ticker
    title = Text.assemble(
        ("10-K", get_style("form_type")),
        "  ",
        ("Apple Inc.", get_style("company_name")),
        " ",
        ("AAPL", get_style("ticker")),
    )

    # Subtitle: Form description
    subtitle = Text("Annual Report", style=get_style("metadata"))

    # Info table
    info_table = Table(box=None, show_header=False, padding=(0, 2))
    info_table.add_column("Label", style=get_style("label"))
    info_table.add_column("Value")

    info_table.add_row("Filed", Text("2024-11-01", style=get_style("date")))
    info_table.add_row("Accession", Text("0000320193-24-000081", style=get_style("accession")))
    info_table.add_row("Period", "2024-09-28")
    info_table.add_row("Documents", "85 files")

    card = Panel(
        info_table,
        title=title,
        subtitle=subtitle,
        subtitle_align="left",
        title_align="left",
        border_style=get_style("border"),
        box=card_border(),
        padding=(0, 1),
        expand=False,
    )

    return card


# =============================================================================
# FILINGS TABLE MOCKUP
# =============================================================================

def demo_filings_table():
    """Demonstrate the Filings list design."""

    table = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold",
        padding=(0, 1),
    )

    table.add_column("#", style=get_style("metadata"), justify="right", width=4)
    table.add_column("Form", width=8)
    table.add_column("Company", style=get_style("company_name"), width=30, no_wrap=True)
    table.add_column("Ticker", style=get_style("ticker"), width=6)
    table.add_column("Filed", style=get_style("date"), width=10)
    table.add_column("Accession", style=get_style("accession"), width=20)

    # Sample data
    filings = [
        ("1", "10-K", "Apple Inc.", "AAPL", "2024-11-01", "0000320193-24-000081"),
        ("2", "10-Q", "Apple Inc.", "AAPL", "2024-08-02", "0000320193-24-000070"),
        ("3", "8-K", "Apple Inc.", "AAPL", "2024-10-31", "0000320193-24-000080"),
        ("4", "10-K", "Microsoft Corporation", "MSFT", "2024-07-30", "0000789019-24-000089"),
        ("5", "10-Q", "NVIDIA Corporation", "NVDA", "2024-08-28", "0001045810-24-000121"),
    ]

    for row in filings:
        table.add_row(*row)

    # Wrap in panel with count subtitle
    panel = Panel(
        table,
        title=Text("Filings", style="bold"),
        title_align="left",
        subtitle=Text("Showing 5 of 1,234", style=get_style("metadata")),
        subtitle_align="right",
        border_style=get_style("border"),
        box=card_border(),
        padding=(0, 0),
        expand=False,
    )

    return panel


# =============================================================================
# STATEMENT MOCKUP
# =============================================================================

def demo_statement():
    """Demonstrate financial statement design (legacy style)."""
    styles = get_statement_styles()

    table = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style="bold",
        padding=(0, 1),
    )

    table.add_column("", width=40)  # Concept name
    table.add_column("2024", justify="right", width=15)
    table.add_column("2023", justify="right", width=15)
    table.add_column("2022", justify="right", width=15)

    # Data rows using new statement styles
    rows = [
        (Text("Revenue", style=styles["row"]["abstract"]), "391,035", "383,285", "394,328"),
        (Text("  Products", style=styles["row"]["item"]), "298,085", "298,085", "316,199"),
        (Text("  Services", style=styles["row"]["item"]), "96,169", "85,200", "78,129"),
        (Text("Cost of Sales", style=styles["row"]["item"]), "214,137", "214,137", "223,546"),
        (Text("Gross Profit", style=styles["row"]["total"]), "176,898", "169,148", "170,782"),
        (Text("Operating Expenses", style=styles["row"]["abstract"]), "", "", ""),
        (Text("  R&D", style=styles["row"]["item"]), "29,915", "29,915", "26,251"),
        (Text("  SG&A", style=styles["row"]["item"]), "26,097", "24,932", "25,094"),
        (Text("Operating Income", style=styles["row"]["total"]), "120,886", "114,301", "119,437"),
    ]

    for row in rows:
        table.add_row(*row)

    # Header with company and statement info
    header = Text.assemble(
        ("Apple Inc.", styles["header"]["company_name"]),
        " ",
        ("AAPL", get_style("ticker")),
        "\n",
        ("Consolidated Statements of Operations", styles["header"]["statement_title"]),
    )

    footer = Text("Amounts in millions USD", style=styles["metadata"]["units"])

    panel = Panel(
        table,
        title=header,
        title_align="left",
        subtitle=footer,
        subtitle_align="right",
        border_style=styles["structure"]["border"],
        box=card_border(),
        padding=(0, 1),
        expand=False,
    )

    return panel


def demo_statement_with_source():
    """Demonstrate financial statement with source attribution (target design)."""
    from rich.console import Group

    styles = get_statement_styles()

    table = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style="bold",
        padding=(0, 1),
    )

    table.add_column("", width=40)
    table.add_column("FY 2024", justify="right", width=12)
    table.add_column("FY 2023", justify="right", width=12)
    table.add_column("FY 2022", justify="right", width=12)

    # Data rows with value styling
    data = [
        ("REVENUE", "abstract", None, None, None),
        ("Net Sales", "total", 391035, 383285, 394328),
        ("  Products", "item", 298085, 298085, 316199),
        ("  Services", "item", 96169, 85200, 78129),
        ("COSTS AND EXPENSES", "abstract", None, None, None),
        ("Cost of Sales", "item", 214137, 214137, 223546),
        ("Gross Profit", "total", 176898, 169148, 170782),
        ("Operating Expenses", "abstract", None, None, None),
        ("  Research and Development", "item", 29915, 29915, 26251),
        ("  Selling, General and Administrative", "item", 26097, 24932, 25094),
        ("Total Operating Expenses", "subtotal", 56012, 54847, 51345),
        ("Operating Income", "total", 120886, 114301, 119437),
    ]

    def format_value(val, row_type):
        if val is None:
            return Text("")
        val_str = f"{val:,}"
        if row_type == "total":
            return Text(val_str, style=styles["value"]["total"])
        elif row_type == "subtotal":
            return Text(val_str, style=styles["value"]["total"])
        else:
            return Text(val_str, style=styles["value"]["default"])

    for label, row_type, v1, v2, v3 in data:
        if row_type == "abstract":
            label_text = Text(label, style=styles["row"]["abstract"])
        elif row_type == "total":
            label_text = Text(label, style=styles["row"]["total"])
        elif row_type == "subtotal":
            label_text = Text(label, style=styles["row"]["subtotal"])
        else:
            label_text = Text(label, style=styles["row"]["item"])

        table.add_row(label_text, format_value(v1, row_type), format_value(v2, row_type), format_value(v3, row_type))

    # Build title hierarchy (like XBRL)
    title_lines = [
        Text("Income Statement", style=styles["header"]["statement_title"]),
        Text("Fiscal Year", style=styles["metadata"]["hint"]),
        Text("Amounts in millions USD", style=styles["metadata"]["units"]),
    ]
    title = Text("\n").join(title_lines)

    # Footer with source and company
    footer = Text.assemble(
        ("Apple Inc. ", styles["header"]["company_name"]),
        ("(AAPL)", get_style("ticker")),
        ("  ", ""),
        (SYMBOLS["bullet"], styles["structure"]["separator"]),
        ("  ", ""),
        ("Source: EntityFacts", styles["metadata"]["source"]),
    )

    panel = Panel(
        table,
        title=title,
        title_align="left",
        subtitle=footer,
        subtitle_align="left",
        border_style=styles["structure"]["border"],
        box=box.SIMPLE,
        padding=(0, 1),
        expand=False,
    )

    return panel


def demo_statement_styles():
    """Show the get_statement_styles() structure."""

    styles = get_statement_styles()

    table = Table(
        title="get_statement_styles() Reference",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold",
    )

    table.add_column("Category", width=12)
    table.add_column("Key", width=18)
    table.add_column("Style", width=20)
    table.add_column("Preview", width=25)

    for category, items in styles.items():
        if category == "comparison":
            # Handle comparison separately (has symbol + style)
            for key, val in items.items():
                preview = Text(f"{val['symbol']} {key}", style=val['style'])
                table.add_row(category, key, val['style'], preview)
        else:
            for key, style in items.items():
                preview = Text(f"Sample {key}", style=style) if style else Text("(default)")
                table.add_row(category, key, style or "(none)", preview)

    return table


# =============================================================================
# COLOR PALETTE PREVIEW
# =============================================================================

def demo_palette():
    """Show all palette colors for reference."""

    table = Table(
        title="Semantic Color Palette",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold",
    )

    table.add_column("Name", width=20)
    table.add_column("Style", width=25)
    table.add_column("Preview", width=30)

    for name, style in sorted(PALETTE.items()):
        preview_text = f"Sample {name}" if style else "(default)"
        table.add_row(name, style or "(none)", Text(preview_text, style=style))

    return table


def demo_symbols():
    """Show all unicode symbols for reference."""

    table = Table(
        title="Unicode Symbols",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold",
    )

    table.add_column("Name", width=20)
    table.add_column("Symbol", width=10, justify="center")
    table.add_column("Usage", width=30)

    usages = {
        "arrow_right": "Navigation, progression",
        "arrow_left": "Back navigation",
        "arrow_up": "Increase indicator",
        "arrow_down": "Decrease indicator",
        "bullet": "List items, separators",
        "diamond": "Special markers",
        "triangle_right": "Expandable items",
        "triangle_down": "Expanded items",
        "check": "Success, complete",
        "cross": "Failed, error",
        "warning": "Warning indicator",
        "info": "Information note",
        "pipe": "Inline separator",
        "dash": "Range separator",
        "ellipsis": "Truncation",
        "lbracket": "Emphasis open",
        "rbracket": "Emphasis close",
    }

    for name, symbol in SYMBOLS.items():
        table.add_row(name, symbol, usages.get(name, ""))

    return table


def demo_yellow_options():
    """Compare yellow/gold color options for ticker styling."""

    table = Table(
        title="Yellow/Gold Options for Ticker",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold",
    )

    table.add_column("Color", width=20)
    table.add_column("Company + Ticker Preview", width=40)

    yellows = [
        ("yellow (default)", "yellow"),
        ("yellow1", "yellow1"),
        ("yellow2", "yellow2"),
        ("yellow3", "yellow3"),
        ("yellow4", "yellow4"),
        ("gold1", "gold1"),
        ("gold3", "gold3"),
        ("dark_goldenrod", "dark_goldenrod"),
        ("light_goldenrod2", "light_goldenrod2"),
        ("orange1", "orange1"),
        ("dark_orange", "dark_orange"),
    ]

    for name, color in yellows:
        preview = Text.assemble(
            ("Apple Inc. ", "bold green"),
            ("AAPL", f"bold {color}"),
        )
        table.add_row(name, preview)

    return table


def demo_blue_options():
    """Compare blue color options for identifiers (CIK, accession)."""

    table = Table(
        title="Blue Options for Identifiers",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold",
    )

    table.add_column("Color", width=20)
    table.add_column("CIK Preview", width=20)
    table.add_column("Accession Preview", width=30)

    blues = [
        ("blue", "blue"),
        ("blue1", "blue1"),
        ("blue3", "blue3"),
        ("cyan", "cyan"),
        ("cyan1", "cyan1"),
        ("cyan3", "cyan3"),
        ("deep_sky_blue1", "deep_sky_blue1"),
        ("deep_sky_blue2", "deep_sky_blue2"),
        ("deep_sky_blue3", "deep_sky_blue3"),
        ("deep_sky_blue4", "deep_sky_blue4"),
        ("dodger_blue1", "dodger_blue1"),
        ("dodger_blue2", "dodger_blue2"),
        ("dodger_blue3", "dodger_blue3"),
        ("steel_blue", "steel_blue"),
        ("steel_blue1", "steel_blue1"),
        ("steel_blue3", "steel_blue3"),
        ("cornflower_blue", "cornflower_blue"),
        ("royal_blue1", "royal_blue1"),
        ("sky_blue1", "sky_blue1"),
        ("sky_blue3", "sky_blue3"),
    ]

    for name, color in blues:
        cik_preview = Text(f"0000320193", style=color)
        accession_preview = Text(f"0000320193-24-000081", style=color)
        table.add_row(name, cik_preview, accession_preview)

    return table


def demo_formatted_identifiers():
    """Show the existing formatted identifier styles from edgar.formatting."""

    table = Table(
        title="Formatted Identifiers (from edgar.formatting)",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold",
    )

    table.add_column("Type", width=20)
    table.add_column("Raw Value", width=25)
    table.add_column("Formatted", width=30)

    # CIK examples
    cik_examples = [
        ("320193", "Apple"),
        ("1318605", "Tesla"),
        ("789019", "Microsoft"),
        ("1045810", "NVIDIA"),
    ]

    for cik, company in cik_examples:
        raw = f"CIK {cik.zfill(10)}"
        formatted = cik_text(cik)
        table.add_row(f"CIK ({company})", raw, formatted)

    # Accession examples
    accession_examples = [
        "0000320193-24-000081",
        "0001318605-24-000045",
        "0000789019-24-000089",
        "0001045810-24-000121",
    ]

    for acc in accession_examples:
        table.add_row("Accession", acc, accession_number_text(acc))

    return table


# =============================================================================
# BACKGROUND FILL PROTOTYPES
# =============================================================================

def demo_background_fills():
    """Demonstrate background fill options for added visual pop."""
    from rich.padding import Padding
    from rich.console import Group

    console.print("[bold]Background Fill Options[/bold]\n")

    # Option 1: Section headers with background fills
    console.print("[dim]Section Headers with Background Fills:[/dim]\n")

    headers = [
        ("Current (no fill)", "bold cyan", None),
        ("Subtle grey", "bold white", "grey19"),
        ("Darker grey", "bold white", "grey15"),
        ("Very dark", "bold white", "grey11"),
        ("Dark blue tint", "bold white", "grey7"),
    ]

    for label, fg, bg in headers:
        style = f"{fg} on {bg}" if bg else fg
        # Use Padding with expand=True for full-width background
        header_text = Padding(f"  ASSETS  ", (0, 0), style=style, expand=True)
        console.print(f"  {label}:")
        console.print(header_text)
        console.print()

    return None


def demo_statement_with_fills():
    """Demonstrate financial statement with background fills on key rows."""
    from rich.padding import Padding

    styles = get_statement_styles()

    # Build statement with background fills
    table = Table(
        box=None,
        show_header=True,
        header_style="bold",
        padding=(0, 1),
        expand=True,
    )

    table.add_column("", width=40)
    table.add_column("FY 2024", justify="right", width=12)
    table.add_column("FY 2023", justify="right", width=12)
    table.add_column("FY 2022", justify="right", width=12)

    # Helper to create styled row
    def make_row(label, v1, v2, v3, row_type="item"):
        def fmt_val(v):
            if v is None:
                return ""
            return f"{v:,}"

        if row_type == "abstract":
            return (
                Text(label, style="bold white on grey19"),
                Text(fmt_val(v1), style="on grey19"),
                Text(fmt_val(v2), style="on grey19"),
                Text(fmt_val(v3), style="on grey19"),
            )
        elif row_type == "total":
            return (
                Text(label, style="bold on grey15"),
                Text(fmt_val(v1), style="bold on grey15"),
                Text(fmt_val(v2), style="bold on grey15"),
                Text(fmt_val(v3), style="bold on grey15"),
            )
        elif row_type == "subtotal":
            return (
                Text(label, style="bold dim"),
                Text(fmt_val(v1), style="bold dim"),
                Text(fmt_val(v2), style="bold dim"),
                Text(fmt_val(v3), style="bold dim"),
            )
        else:
            return (
                Text(label),
                Text(fmt_val(v1)),
                Text(fmt_val(v2)),
                Text(fmt_val(v3)),
            )

    # Data rows
    data = [
        ("REVENUE", None, None, None, "abstract"),
        ("Net Sales", 391035, 383285, 394328, "total"),
        ("  Products", 298085, 298085, 316199, "item"),
        ("  Services", 96169, 85200, 78129, "item"),
        ("COSTS AND EXPENSES", None, None, None, "abstract"),
        ("Cost of Sales", 214137, 214137, 223546, "item"),
        ("Gross Profit", 176898, 169148, 170782, "total"),
        ("OPERATING EXPENSES", None, None, None, "abstract"),
        ("  Research and Development", 29915, 29915, 26251, "item"),
        ("  Selling, General and Admin", 26097, 24932, 25094, "item"),
        ("Total Operating Expenses", 56012, 54847, 51345, "subtotal"),
        ("Operating Income", 120886, 114301, 119437, "total"),
    ]

    for label, v1, v2, v3, row_type in data:
        row = make_row(label, v1, v2, v3, row_type)
        table.add_row(*row)

    # Title - Panel titles must be Text objects, not Padding
    # For a full-width title bar, we'd need to construct outside the panel
    title = Text.assemble(
        (" Income Statement ", "bold on grey11"),
        ("  ", ""),
        ("Apple Inc. ", get_style("company_name")),
        ("AAPL", get_style("ticker")),
    )

    footer = Text.assemble(
        ("Amounts in millions USD", styles["metadata"]["units"]),
        ("  ", ""),
        (SYMBOLS["bullet"], "dim"),
        ("  ", ""),
        ("Source: EntityFacts", styles["metadata"]["source"]),
    )

    panel = Panel(
        table,
        title=title,
        title_align="left",
        subtitle=footer,
        subtitle_align="left",
        border_style=styles["structure"]["border"],
        box=box.ROUNDED,
        padding=(0, 0),
    )

    return panel


def demo_status_with_fills():
    """Demonstrate status messages with background fills."""
    from rich.padding import Padding

    console.print("[dim]Status Messages with Background Fills:[/dim]\n")

    statuses = [
        ("Error: Filing not found", "bold white on red"),
        ("Warning: Data may be incomplete", "bold black on yellow"),
        ("Success: 42 filings loaded", "bold white on green"),
        ("Info: Using cached data from 2024-01-15", "bold white on blue"),
    ]

    for message, style in statuses:
        status = Padding(f"  {message}  ", (0, 0), style=style, expand=False)
        console.print(status)
        console.print()

    return None


def demo_highlight_rows():
    """Demonstrate highlighted rows in a table context."""

    table = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style="bold",
        padding=(0, 1),
    )

    table.add_column("Metric", width=30)
    table.add_column("Value", justify="right", width=15)
    table.add_column("Change", justify="right", width=10)

    # Mix of regular and highlighted rows
    rows = [
        ("Revenue", "391,035", "+2.0%", None),
        ("Net Income", "96,995", "+7.5%", "on grey15"),  # Highlighted
        ("EPS (Diluted)", "6.42", "+9.2%", "on grey15"),  # Highlighted
        ("Operating Margin", "31.0%", "+1.2pp", None),
        ("Cash & Equivalents", "29,965", "-12.3%", None),
        ("Total Assets", "352,583", "-1.8%", None),
        ("Free Cash Flow", "108,807", "+5.4%", "on grey15"),  # Highlighted
    ]

    for label, value, change, bg in rows:
        if bg:
            table.add_row(
                Text(label, style=f"bold {bg}"),
                Text(value, style=f"bold {bg}"),
                Text(change, style=f"green {bg}" if not change.startswith("-") else f"red {bg}"),
            )
        else:
            change_style = "green" if not change.startswith("-") else "red"
            table.add_row(label, value, Text(change, style=change_style))

    panel = Panel(
        table,
        title="Key Metrics (highlighted rows have background)",
        title_align="left",
        border_style=get_style("border"),
        box=card_border(),
        padding=(0, 0),
        expand=False,
    )

    return panel


def demo_title_bar_fills():
    """Demonstrate panel titles with background fills."""
    from rich.console import Group

    # Standard panel (no fill)
    standard = Panel(
        "Content goes here...",
        title="Standard Panel Title",
        title_align="left",
        border_style=get_style("border"),
        box=card_border(),
        expand=False,
    )

    # Panel with filled title effect using nested structure
    title_bar = Text.assemble(
        (" 10-K ", get_style("badge_10k")),
        ("  ", ""),
        ("Apple Inc.", get_style("company_name")),
        (" ", ""),
        ("AAPL", get_style("ticker")),
    )

    with_badge = Panel(
        "Content goes here...",
        title=title_bar,
        title_align="left",
        border_style=get_style("border"),
        box=card_border(),
        expand=False,
    )

    # Form type badges with different colors (now using PALETTE)
    badges = [
        ("10-K", get_style("badge_10k")),
        ("10-Q", get_style("badge_10q")),
        ("8-K", get_style("badge_8k")),
        ("DEF 14A", get_style("badge_proxy")),
    ]

    badge_row = Text()
    for form, style in badges:
        badge_row.append(f" {form} ", style=style)
        badge_row.append("  ")

    return Group(
        Text("[dim]Standard panel:[/dim]"),
        standard,
        Text("\n[dim]Panel with form type badge:[/dim]"),
        with_badge,
        Text("\n[dim]Form type badge options:[/dim]"),
        badge_row,
    )


def demo_source_badges():
    """Demonstrate source badges for financial data origin."""
    from rich.console import Group

    # Source badges distinguish where financial data comes from
    console.print("[dim]Source Badges - Distinguish data origin:[/dim]\n")

    # XBRL source badge
    xbrl_footer = Text.assemble(
        ("Amounts in millions USD", get_style("units")),
        ("  ", ""),
        (SYMBOLS["bullet"], "dim"),
        ("  ", ""),
        (" XBRL ", get_style("badge_source_xbrl")),
        (" ", ""),
        ("10-K filed 2024-11-01", get_style("hint")),
    )

    # EntityFacts source badge
    ef_footer = Text.assemble(
        ("Amounts in millions USD", get_style("units")),
        ("  ", ""),
        (SYMBOLS["bullet"], "dim"),
        ("  ", ""),
        (" EntityFacts ", get_style("badge_source_entity_facts")),
        (" ", ""),
        ("Q3 2022 to Q3 2025", get_style("hint")),
    )

    console.print("  XBRL source (single filing):")
    console.print(f"    {xbrl_footer}")
    console.print()
    console.print("  EntityFacts source (aggregated):")
    console.print(f"    {ef_footer}")
    console.print()

    # Side by side comparison
    console.print("[dim]Why this matters:[/dim]")
    console.print("  • [bold white on gold3] XBRL [/bold white on gold3] = Parsed from a specific SEC filing (exact, point-in-time)")
    console.print("  • [bold white on cyan] EntityFacts [/bold white on cyan] = SEC's aggregated company data (convenient, multi-period)")
    console.print()

    # Example in context - mini statement footers
    console.print("[dim]Example statement footers:[/dim]\n")

    # XBRL statement
    xbrl_panel = Panel(
        Text("Revenue: 391,035\nNet Income: 96,995", style=""),
        title=Text.assemble(
            (" 10-K ", get_style("badge_10k")),
            ("  Income Statement", "bold"),
        ),
        title_align="left",
        subtitle=Text.assemble(
            (" XBRL ", get_style("badge_source_xbrl")),
            (" Apple Inc. ", get_style("company_name")),
            ("2024-11-01", get_style("date")),
        ),
        subtitle_align="left",
        border_style=get_style("border"),
        box=card_border(),
        expand=False,
    )

    # EntityFacts statement
    ef_panel = Panel(
        Text("Revenue: 391,035  383,285  394,328\nNet Income: 96,995  93,736  99,803", style=""),
        title=Text.assemble(
            ("Income Statement", "bold"),
            ("  ", ""),
            ("FY 2024 → FY 2022", get_style("period_range")),
        ),
        title_align="left",
        subtitle=Text.assemble(
            (" EntityFacts ", get_style("badge_source_entity_facts")),
            (" Apple Inc. ", get_style("company_name")),
            ("AAPL", get_style("ticker")),
        ),
        subtitle_align="left",
        border_style=get_style("border"),
        box=card_border(),
        expand=False,
    )

    console.print(xbrl_panel)
    console.print()
    console.print(ef_panel)

    return None


def demo_accession_blue_comparison():
    """Compare bright_blue (current) vs dodger_blue1 (new palette) for accession year."""

    table = Table(
        title="Accession Year Color: bright_blue vs dodger_blue1",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold",
    )

    table.add_column("Color", width=15)
    table.add_column("Accession Number", width=35)

    accessions = [
        "0000320193-24-000081",
        "0001318605-24-000045",
        "0000789019-23-000089",
    ]

    for acc in accessions:
        parts = acc.split('-')
        cik_part, year_part, seq_part = parts

        # Count leading zeros
        cik_zeros = len(cik_part) - len(cik_part.lstrip('0'))
        cik_value = cik_part[cik_zeros:]
        seq_zeros = len(seq_part) - len(seq_part.lstrip('0'))
        seq_value = seq_part[seq_zeros:]

        # bright_blue version (current edgar.formatting)
        bright = Text.assemble(
            ('0' * cik_zeros, 'dim'),
            (cik_value, 'bold white'),
            ('-', ''),
            (year_part, 'bright_blue'),
            ('-', ''),
            ('0' * seq_zeros, 'dim'),
            (seq_value, 'bold white'),
        )

        # dodger_blue1 version (new palette)
        dodger = Text.assemble(
            ('0' * cik_zeros, 'dim'),
            (cik_value, 'bold white'),
            ('-', ''),
            (year_part, 'dodger_blue1'),
            ('-', ''),
            ('0' * seq_zeros, 'dim'),
            (seq_value, 'bold white'),
        )

        table.add_row("bright_blue", bright)
        table.add_row("dodger_blue1", dodger)
        table.add_row("", Text(""))  # spacer

    return table


# =============================================================================
# MAIN DEMO
# =============================================================================

def main():
    """Run the full display demo."""

    console.print("\n")
    console.print("[bold]EdgarTools Display Language Demo[/bold]", justify="center")
    console.print("[dim]Iterate on colors, typography, and layout[/dim]", justify="center")
    console.print("\n")

    # Section 1: Company Cards
    console.print("[bold]1. Company Card Designs[/bold]\n")
    console.print("Version 1 - Expanded:")
    console.print(demo_company_card())
    console.print("\nVersion 2 - Compact:")
    console.print(demo_company_card_v2())
    console.print("\n")

    # Section 2: Filing Card
    console.print("[bold]2. Filing Card[/bold]\n")
    console.print(demo_filing_card())
    console.print("\n")

    # Section 3: Filings Table
    console.print("[bold]3. Filings Table[/bold]\n")
    console.print(demo_filings_table())
    console.print("\n")

    # Section 4: Financial Statement (current)
    console.print("[bold]4. Financial Statement (using get_statement_styles)[/bold]\n")
    console.print(demo_statement())
    console.print("\n")

    # Section 4b: Financial Statement with source (target design)
    console.print("[bold]4b. Financial Statement with Source Attribution (Target Design)[/bold]\n")
    console.print(demo_statement_with_source())
    console.print("\n")

    # Section 4c: Statement styles reference
    console.print("[bold]4c. Statement Styles Reference (get_statement_styles)[/bold]\n")
    console.print(demo_statement_styles())
    console.print("\n")

    # Section 5: Reference
    console.print("[bold]5. Reference: Color Palette[/bold]\n")
    console.print(demo_palette())
    console.print("\n")

    console.print("[bold]6. Reference: Unicode Symbols[/bold]\n")
    console.print(demo_symbols())
    console.print("\n")

    console.print("[bold]7. Color Options: Yellow/Gold for Tickers[/bold]\n")
    console.print(demo_yellow_options())
    console.print("\n")

    console.print("[bold]8. Color Options: Blues for Identifiers[/bold]\n")
    console.print(demo_blue_options())
    console.print("\n")

    console.print("[bold]9. Existing Formatted Identifiers (edgar.formatting)[/bold]\n")
    console.print(demo_formatted_identifiers())
    console.print("\n")

    console.print("[bold]10. Accession Year: bright_blue vs dodger_blue1[/bold]\n")
    console.print(demo_accession_blue_comparison())
    console.print("\n")

    # Background fill prototypes
    console.print("[bold]" + "=" * 60 + "[/bold]")
    console.print("[bold]BACKGROUND FILL PROTOTYPES[/bold]", justify="center")
    console.print("[bold]" + "=" * 60 + "[/bold]\n")

    console.print("[bold]11. Section Header Fill Options[/bold]\n")
    demo_background_fills()
    console.print("\n")

    console.print("[bold]12. Financial Statement with Background Fills[/bold]\n")
    console.print(demo_statement_with_fills())
    console.print("\n")

    console.print("[bold]13. Status Messages with Fills[/bold]\n")
    demo_status_with_fills()
    console.print("\n")

    console.print("[bold]14. Highlighted Rows in Tables[/bold]\n")
    console.print(demo_highlight_rows())
    console.print("\n")

    console.print("[bold]15. Form Type Badges with Background Fills[/bold]\n")
    console.print(demo_title_bar_fills())
    console.print("\n")

    console.print("[bold]16. Source Badges (XBRL vs EntityFacts)[/bold]\n")
    demo_source_badges()
    console.print("\n")

    # Usage hints
    console.print("[dim]" + "-" * 60 + "[/dim]")
    console.print("[dim]To iterate: edit edgar/display/styles.py and re-run this demo[/dim]")
    console.print("[dim]python -m edgar.display.demo[/dim]")
    console.print("\n")


if __name__ == "__main__":
    main()