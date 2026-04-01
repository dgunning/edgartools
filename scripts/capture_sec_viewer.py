#!/usr/bin/env python3
"""Capture SEC Viewer screenshots for sec-viewer-guide.md documentation.

Generates three images:
1. viewer-overview.webp    -- FilingViewer __rich__ display (categories + stats)
2. viewer-concept.webp     -- Concept lookup panel (Assets with calculation tree)
3. viewer-income.webp      -- Income statement ViewerReport panel

Run from the repo root:
    python scripts/capture_sec_viewer.py
"""

import sys
import tempfile
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.snapshot_rich import capture_expression, svg_to_image

INKSCAPE = '/Applications/Inkscape.app/Contents/MacOS/inkscape'
OUT_DIR = Path('docs/images')
OUT_DIR.mkdir(parents=True, exist_ok=True)


def save_svg_as_webp(svg: str, output_path: Path, width: int = 1200) -> None:
    """Convert SVG to WebP via Inkscape (cairosvg fallback path)."""
    from PIL import Image

    with tempfile.NamedTemporaryFile(suffix='.svg', mode='w', delete=False) as f:
        f.write(svg)
        svg_path = Path(f.name)

    png_path = svg_path.with_suffix('.png')
    result = subprocess.run(
        [INKSCAPE, str(svg_path), '--export-filename', str(png_path),
         '--export-width', str(width)],
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"  Inkscape error: {result.stderr.decode()[:200]}")
        svg_path.unlink(missing_ok=True)
        return

    img = Image.open(png_path)
    img.save(str(output_path), 'WEBP', quality=85)
    size_kb = output_path.stat().st_size / 1024
    print(f"  Saved: {output_path} ({size_kb:.1f} KB)")

    svg_path.unlink(missing_ok=True)
    png_path.unlink(missing_ok=True)


def capture(code: str, out: Path, title: str, width: int = 82) -> None:
    print(f"Capturing: {title}")
    svg = capture_expression(code, width=width, title=title)

    # Try cairosvg first, fall back to Inkscape
    ok = svg_to_image(svg, out, fmt='webp', quality=85)
    if not ok or out.suffix == '.svg':
        save_svg_as_webp(svg, out, width=1200)


def main():
    # ---- 1. Viewer overview ----
    capture(
        code=(
            "from edgar import set_identity, Company; "
            "set_identity('docs@edgartools.io'); "
            "filing = Company('MSFT').get_filings(form='10-K').latest(); "
            "viewer = filing.viewer; "
            "viewer"
        ),
        out=OUT_DIR / 'viewer-overview.webp',
        title='SEC Viewer — MSFT 10-K',
        width=84,
    )

    # ---- 2. Concept lookup: Assets (shows calculation tree) ----
    capture(
        code=(
            "from edgar import set_identity, Company; "
            "set_identity('docs@edgartools.io'); "
            "filing = Company('MSFT').get_filings(form='10-K').latest(); "
            "viewer = filing.viewer; "
            "viewer['us-gaap_Assets']"
        ),
        out=OUT_DIR / 'viewer-concept-assets.webp',
        title='viewer["Assets"] — Concept Lookup',
        width=84,
    )

    # ---- 3. Revenue concept (shows income statement reference) ----
    capture(
        code=(
            "from edgar import set_identity, Company; "
            "set_identity('docs@edgartools.io'); "
            "filing = Company('MSFT').get_filings(form='10-K').latest(); "
            "viewer = filing.viewer; "
            "viewer['us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax']"
        ),
        out=OUT_DIR / 'viewer-concept-revenue.webp',
        title='viewer["Revenue"] — Concept Lookup',
        width=84,
    )


if __name__ == '__main__':
    main()
