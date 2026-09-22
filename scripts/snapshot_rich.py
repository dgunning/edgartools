#!/usr/bin/env python3
"""Capture Rich console output as images for documentation.

Renders a Python expression or script through Rich's recording console,
exports to SVG, then converts to WebP (or PNG) for use in docs.

Requires: Pillow, cairosvg (for SVG-to-PNG rasterization)

Examples:
    # Capture a simple expression
    python snapshot_rich.py "from edgar import Company; Company('AAPL')" -o docs/images/company-aapl.webp

    # Capture with custom width
    python snapshot_rich.py "from edgar import Company; Company('AAPL')" --width 120 -o docs/images/company-aapl.webp

    # Output as PNG instead of WebP
    python snapshot_rich.py "from edgar import Company; Company('AAPL')" --format png -o docs/images/company-aapl.png

    # Run a script file and capture its output
    python snapshot_rich.py --script examples/demo_holdings.py -o docs/images/holdings-demo.webp

    # Capture with a specific theme
    python snapshot_rich.py "print('hello')" --title "Example Output" -o example.webp
"""

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Optional

from rich.console import Console


def capture_expression(
    expression: str,
    width: int = 120,
    title: Optional[str] = None,
) -> str:
    """Execute a Python expression and capture Rich console output as SVG.

    Args:
        expression: Python code to execute. Statements separated by `;`.
        width: Console width in characters (default 120).
        title: Optional title for the SVG export.

    Returns:
        SVG string of the captured console output.
    """
    console = Console(record=True, width=width, force_terminal=True)

    # Build execution environment with console available
    exec_globals = {"console": console, "__builtins__": __builtins__}

    # Split on semicolons for multi-statement expressions,
    # but handle the last statement specially to auto-print its result
    statements = [s.strip() for s in expression.split(";") if s.strip()]

    if not statements:
        return console.export_svg(title=title or "")

    # Execute all but the last statement
    for stmt in statements[:-1]:
        exec(stmt, exec_globals)

    # For the last statement, try eval first (prints result), fall back to exec
    last = statements[-1]
    try:
        result = eval(last, exec_globals)
        if result is not None:
            console.print(result)
    except SyntaxError:
        exec(last, exec_globals)

    return console.export_svg(title=title or "")


def capture_script(
    script_path: Path,
    width: int = 120,
    title: Optional[str] = None,
) -> str:
    """Execute a Python script file and capture Rich console output as SVG.

    Args:
        script_path: Path to a .py file to execute.
        width: Console width in characters (default 120).
        title: Optional title for the SVG export.

    Returns:
        SVG string of the captured console output.
    """
    console = Console(record=True, width=width, force_terminal=True)
    exec_globals = {"console": console, "__builtins__": __builtins__}

    code = script_path.read_text()
    exec(compile(code, str(script_path), "exec"), exec_globals)

    return console.export_svg(title=title or "")


def svg_to_image(svg_content: str, output_path: Path, fmt: str = "webp", quality: int = 85) -> bool:
    """Convert SVG content to a raster image (WebP or PNG).

    Uses cairosvg for SVG rasterization if available, otherwise falls back
    to saving the SVG and noting the limitation.

    Args:
        svg_content: SVG markup string.
        output_path: Destination file path.
        fmt: Output format -- "webp" or "png".
        quality: WebP quality 0-100 (ignored for PNG).

    Returns:
        True if conversion succeeded.
    """
    try:
        import cairosvg
        from PIL import Image
        import io

        # Render SVG to PNG bytes via cairosvg
        png_bytes = cairosvg.svg2png(bytestring=svg_content.encode("utf-8"))

        if fmt == "png":
            output_path.write_bytes(png_bytes)
        else:
            # Convert PNG bytes to WebP via Pillow
            img = Image.open(io.BytesIO(png_bytes))
            img.save(output_path, format="WEBP", quality=quality)

        size_kb = output_path.stat().st_size / 1024
        print(f"  Saved: {output_path} ({size_kb:.1f} KB)")
        return True

    except ImportError:
        # cairosvg not available -- save as SVG with a note
        svg_path = output_path.with_suffix(".svg")
        svg_path.write_text(svg_content)
        print(f"  Saved SVG (cairosvg not installed for raster conversion): {svg_path}")
        print(f"  Install cairosvg for WebP/PNG output: pip install cairosvg")
        return True

    except Exception as e:
        print(f"  Failed to convert: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Capture Rich console output as images for documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "from edgar import Company; Company('AAPL')" -o docs/images/company-aapl.webp
  %(prog)s --script examples/demo.py -o docs/images/demo.webp
  %(prog)s "print('hello')" --width 80 --format png -o output.png
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "expression",
        nargs="?",
        help="Python expression to execute and capture (use ; to separate statements)",
    )
    group.add_argument(
        "--script",
        type=Path,
        help="Path to a Python script to execute and capture",
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("snapshot.webp"),
        help="Output file path (default: snapshot.webp)",
    )

    parser.add_argument(
        "--width",
        type=int,
        default=120,
        help="Console width in characters (default: 120)",
    )

    parser.add_argument(
        "--format",
        choices=["webp", "png"],
        default=None,
        help="Output format (default: inferred from output file extension)",
    )

    parser.add_argument(
        "--quality",
        type=int,
        default=85,
        help="WebP quality 0-100 (default: 85)",
    )

    parser.add_argument(
        "--title",
        type=str,
        help="Title for the captured output",
    )

    args = parser.parse_args()

    # Determine output format
    fmt = args.format
    if fmt is None:
        ext = args.output.suffix.lower()
        fmt = "png" if ext == ".png" else "webp"

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Capturing Rich output (width={args.width}, format={fmt})")

    # Capture
    if args.script:
        if not args.script.exists():
            print(f"Error: Script not found: {args.script}")
            sys.exit(1)
        svg = capture_script(args.script, width=args.width, title=args.title)
    else:
        svg = capture_expression(args.expression, width=args.width, title=args.title)

    # Convert and save
    success = svg_to_image(svg, args.output, fmt=fmt, quality=args.quality)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
