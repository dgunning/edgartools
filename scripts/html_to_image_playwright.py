#!/usr/bin/env python3
"""Convert HTML to image using Playwright."""

import sys
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright


async def html_to_image(html_path: Path, output_path: Path):
    """Convert HTML file to PNG/WebP using Playwright."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await p.new_page()

        # Load the HTML file
        html_content = html_path.read_text()
        await page.set_content(html_content)

        # Take screenshot
        await page.screenshot(path=str(output_path))
        await browser.close()

        print(f"Saved screenshot to: {output_path}")


def main():
    if len(sys.argv) < 3:
        print("Usage: python html_to_image_playwright.py <input.html> <output.png>")
        sys.exit(1)

    html_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    if not html_path.exists():
        print(f"Error: {html_path} not found")
        sys.exit(1)

    asyncio.run(html_to_image(html_path, output_path))


if __name__ == "__main__":
    main()
