#!/usr/bin/env python3
"""Capture Rich console output directly to PNG/WebP using Playwright.

This bypasses the cairo dependency by using:
1. Rich's HTML export
2. Playwright for HTML-to-image conversion
"""

import sys
import asyncio
import tempfile
from pathlib import Path
from rich.console import Console
from playwright.async_api import async_playwright
from PIL import Image


def capture_script_to_html(script_path: Path, width: int = 120) -> str:
    """Execute a Python script and capture Rich output as HTML."""
    console = Console(record=True, width=width, force_terminal=True)

    # Execute the script
    exec_globals = {"console": console, "__builtins__": __builtins__}
    code = script_path.read_text()

    # Capture output
    import builtins
    _orig_print = builtins.print

    def custom_print(*args, **kwargs):
        console.print(*args, **kwargs)

    builtins.print = custom_print

    try:
        exec(compile(code, str(script_path), "exec"), exec_globals)
    finally:
        builtins.print = _orig_print

    # Export to HTML with inline styles
    return console.export_html(inline_styles=True, code_format="{code}")


async def html_to_png(html_content: str, output_path: Path):
    """Convert HTML content to PNG using Playwright."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Set viewport to capture full content
        await page.set_viewport_size({"width": 1400, "height": 1000})

        # Load HTML
        await page.set_content(html_content)

        # Wait for any rendering
        await page.wait_for_timeout(100)

        # Get the dimensions of the rendered content
        dimensions = await page.evaluate('''() => {
            const body = document.body;
            const html = document.documentElement;
            return {
                width: Math.max(body.scrollWidth, html.scrollWidth),
                height: Math.max(body.scrollHeight, html.scrollHeight)
            };
        }''')

        # Set viewport to content size
        await page.set_viewport_size({
            "width": dimensions["width"] + 40,
            "height": dimensions["height"] + 40
        })

        # Take screenshot
        await page.screenshot(path=str(output_path))
        await browser.close()


def png_to_webp(png_path: Path, webp_path: Path, quality: int = 85):
    """Convert PNG to WebP using Pillow."""
    img = Image.open(png_path)
    img.save(webp_path, format="WEBP", quality=quality)
    png_path.unlink()  # Remove temporary PNG


async def capture_to_image(script_path: Path, output_path: Path, width: int = 120, quality: int = 85):
    """Capture script output to PNG or WebP."""
    print(f"Capturing output from {script_path}...")

    # Step 1: Execute script and get HTML
    html_content = capture_script_to_html(script_path, width)

    # Step 2: Convert HTML to PNG using Playwright
    if output_path.suffix.lower() == '.webp':
        # Create temporary PNG first
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp_path = Path(tmp.name)

        await html_to_png(html_content, tmp_path)

        # Convert to WebP
        print(f"Converting to WebP...")
        png_to_webp(tmp_path, output_path, quality)
    else:
        # Direct PNG output
        await html_to_png(html_content, output_path)

    size_kb = output_path.stat().st_size / 1024
    print(f"Saved: {output_path} ({size_kb:.1f} KB)")


def main():
    if len(sys.argv) < 3:
        print("Usage: python capture_rich_to_png.py <script.py> <output.png|output.webp> [--width 120] [--quality 85]")
        sys.exit(1)

    script_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    # Parse optional arguments
    width = 120
    quality = 85

    for i, arg in enumerate(sys.argv):
        if arg == '--width' and i + 1 < len(sys.argv):
            width = int(sys.argv[i + 1])
        elif arg == '--quality' and i + 1 < len(sys.argv):
            quality = int(sys.argv[i + 1])

    if not script_path.exists():
        print(f"Error: {script_path} not found")
        sys.exit(1)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Run async capture
    asyncio.run(capture_to_image(script_path, output_path, width, quality))


if __name__ == "__main__":
    main()
