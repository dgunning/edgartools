#!/usr/bin/env python3
"""Generate images for docs/guides/finding-companies.md using Rich SVG + Inkscape."""

import subprocess
import sys
import tempfile
from pathlib import Path

from rich.console import Console

INKSCAPE = "/Applications/Inkscape.app/Contents/MacOS/inkscape"
OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "images"


def svg_to_webp(svg_content: str, output_path: Path) -> None:
    """Convert SVG string to WebP via Inkscape (SVG→PNG) then Pillow (PNG→WebP)."""
    from PIL import Image
    import io

    with tempfile.NamedTemporaryFile(suffix=".svg", mode="w", delete=False) as svgf:
        svgf.write(svg_content)
        svg_path = svgf.name

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as pngf:
        png_path = pngf.name

    # Inkscape SVG → PNG
    subprocess.run(
        [INKSCAPE, svg_path, "--export-type=png", f"--export-filename={png_path}"],
        capture_output=True,
        check=True,
    )

    # Crop whitespace and convert to WebP
    img = Image.open(png_path)
    # Auto-crop: find the bounding box of non-white content
    bbox = img.getbbox()
    if bbox:
        # Add small padding
        pad = 8
        left = max(0, bbox[0] - pad)
        top = max(0, bbox[1] - pad)
        right = min(img.width, bbox[2] + pad)
        bottom = min(img.height, bbox[3] + pad)
        img = img.crop((left, top, right, bottom))

    img.save(output_path, format="WEBP", quality=90)
    size_kb = output_path.stat().st_size / 1024
    print(f"  {output_path.name}: {img.width}x{img.height}, {size_kb:.1f} KB")

    # Cleanup
    Path(svg_path).unlink(missing_ok=True)
    Path(png_path).unlink(missing_ok=True)


def capture(expression: str, width: int = 100) -> str:
    """Execute expression and capture Rich output as SVG."""
    console = Console(record=True, width=width, force_terminal=True)
    exec_globals = {"console": console, "__builtins__": __builtins__}

    statements = [s.strip() for s in expression.split(";") if s.strip()]
    for stmt in statements[:-1]:
        exec(stmt, exec_globals)

    last = statements[-1]
    try:
        result = eval(last, exec_globals)
        if result is not None:
            console.print(result)
    except SyntaxError:
        exec(last, exec_globals)

    return console.export_svg(title="")


def main():
    from edgar import set_identity
    set_identity("demo@edgartools.io")

    # 1. Company lookup
    print("1/5 Company lookup...")
    svg = capture(
        "from edgar import Company; Company('AAPL')",
        width=100,
    )
    svg_to_webp(svg, OUTPUT_DIR / "company-lookup.webp")

    # 2. Batch lookup — use a Rich Table for nice formatting
    print("2/5 Batch lookup...")
    svg = capture("""
from edgar import Company
from rich.table import Table

tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
table = Table(title="Batch Company Lookup")
table.add_column("Ticker", style="bold cyan")
table.add_column("Name")
table.add_column("CIK", justify="right")
table.add_column("Industry")

for t in tickers:
    c = Company(t)
    table.add_row(t, c.name, str(c.cik), c.industry)

console.print(table)
""", width=110)
    svg_to_webp(svg, OUTPUT_DIR / "company-batch-lookup.webp")

    # 3. Screening with shares_outstanding / public_float
    print("3/5 Company screening...")
    svg = capture("""
from edgar import Company
from rich.table import Table

tickers = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA"]
table = Table(title="Company Screening: Shares Outstanding & Public Float")
table.add_column("Ticker", style="bold cyan")
table.add_column("Name")
table.add_column("Shares Outstanding", justify="right", style="green")
table.add_column("Public Float ($)", justify="right", style="green")

for t in tickers:
    c = Company(t)
    shares = c.shares_outstanding
    pfloat = c.public_float
    shares_str = f"{shares:,.0f}" if shares else "N/A"
    float_str = f"${pfloat:,.0f}" if pfloat else "N/A"
    table.add_row(t, c.name, shares_str, float_str)

console.print(table)
""", width=120)
    svg_to_webp(svg, OUTPUT_DIR / "company-screening.webp")

    # 4. Search by industry
    print("4/5 Search by industry...")
    svg = capture("""
from edgar.reference import get_companies_by_industry
from rich.table import Table

software = get_companies_by_industry(sic=7372)
table = Table(title=f"Software Companies (SIC 7372) — {len(software)} total, showing first 10")
table.add_column("Ticker", style="bold cyan")
table.add_column("Name")
table.add_column("CIK", justify="right")

for _, row in software.head(10).iterrows():
    table.add_row(str(row.get('ticker', '')), str(row.get('name', '')), str(row.get('cik', '')))

console.print(table)
""", width=100)
    svg_to_webp(svg, OUTPUT_DIR / "company-search-by-industry.webp")

    # 5. Search by exchange
    print("5/5 Search by exchange...")
    svg = capture("""
from edgar.reference import get_companies_by_exchanges
from rich.table import Table

nyse = get_companies_by_exchanges("NYSE")
table = Table(title=f"NYSE Companies — {len(nyse)} total, showing first 10")
table.add_column("Ticker", style="bold cyan")
table.add_column("Name")
table.add_column("CIK", justify="right")

for _, row in nyse.head(10).iterrows():
    table.add_row(str(row.get('ticker', '')), str(row.get('name', '')), str(row.get('cik', '')))

console.print(table)
""", width=100)
    svg_to_webp(svg, OUTPUT_DIR / "company-search-by-exchange.webp")

    print("\nDone! All 5 images generated.")


if __name__ == "__main__":
    main()
