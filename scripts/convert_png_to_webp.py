#!/usr/bin/env python3
# /// script
# dependencies = [
#   "Pillow",
# ]
# ///
"""Convert PNG files to WebP format using Pillow.

This script provides a convenient interface for converting PNG files to WebP
format. Supports single file conversion, batch conversion via glob patterns,
quality control, lossless mode, and optional resizing.

Examples:
    # Convert single file
    python convert_png_to_webp.py input.png

    # Convert with custom output path
    python convert_png_to_webp.py input.png -o output.webp

    # Convert with custom quality (0-100, default 85)
    python convert_png_to_webp.py input.png --quality 90

    # Lossless conversion
    python convert_png_to_webp.py input.png --lossless

    # Resize to max width (preserves aspect ratio)
    python convert_png_to_webp.py input.png --max-width 800

    # Batch convert all PNGs in a directory
    python convert_png_to_webp.py docs/images/*.png

    # Batch convert preserving directory structure
    python convert_png_to_webp.py docs/images/**/*.png
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required. Install it with: pip install Pillow")
    sys.exit(1)


def convert_png_to_webp(
    png_path: Path,
    webp_path: Optional[Path] = None,
    quality: int = 85,
    lossless: bool = False,
    max_width: Optional[int] = None,
) -> bool:
    """Convert a single PNG file to WebP.

    Args:
        png_path: Path to input PNG file.
        webp_path: Path to output WebP file (defaults to same name with .webp).
        quality: WebP quality 0-100 (default 85). Ignored if lossless=True.
        lossless: If True, use lossless WebP compression.
        max_width: If set, resize to this max width preserving aspect ratio.

    Returns:
        True if conversion succeeded, False otherwise.
    """
    if not png_path.exists():
        print(f"Error: Input file not found: {png_path}")
        return False

    if webp_path is None:
        webp_path = png_path.with_suffix(".webp")

    # Ensure output directory exists
    webp_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        img = Image.open(png_path)

        # Resize if max_width specified and image is wider
        if max_width and img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)

        save_kwargs = {"format": "WEBP", "lossless": lossless}
        if not lossless:
            save_kwargs["quality"] = quality

        img.save(webp_path, **save_kwargs)

        # Report size savings
        original_size = png_path.stat().st_size
        new_size = webp_path.stat().st_size
        reduction = (1 - new_size / original_size) * 100 if original_size > 0 else 0

        print(f"  {png_path.name} -> {webp_path.name}  "
              f"({original_size:,} -> {new_size:,} bytes, {reduction:.0f}% smaller)")
        return True

    except Exception as e:
        print(f"  Failed: {png_path} -- {e}")
        return False


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Convert PNG files to WebP using Pillow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.png
  %(prog)s input.png -o output.webp
  %(prog)s input.png --quality 90
  %(prog)s input.png --lossless
  %(prog)s input.png --max-width 800
  %(prog)s docs/images/*.png
        """,
    )

    parser.add_argument(
        "input",
        nargs="+",
        type=Path,
        help="Input PNG file(s) to convert",
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output WebP file path (only for single file conversion)",
    )

    parser.add_argument(
        "--quality",
        type=int,
        default=85,
        help="WebP quality 0-100 (default: 85). Ignored with --lossless",
    )

    parser.add_argument(
        "--lossless",
        action="store_true",
        help="Use lossless WebP compression",
    )

    parser.add_argument(
        "--max-width",
        type=int,
        help="Resize to max width in pixels (preserves aspect ratio)",
    )

    args = parser.parse_args()

    if args.output and len(args.input) > 1:
        print("Error: --output can only be used with a single input file")
        sys.exit(1)

    print(f"Converting PNG to WebP (quality={args.quality}, lossless={args.lossless})\n")

    success_count = 0
    fail_count = 0

    for png_path in args.input:
        if not png_path.exists():
            print(f"  Skipping non-existent file: {png_path}")
            fail_count += 1
            continue

        if png_path.suffix.lower() != ".png":
            print(f"  Skipping non-PNG file: {png_path}")
            fail_count += 1
            continue

        success = convert_png_to_webp(
            png_path=png_path,
            webp_path=args.output if args.output else None,
            quality=args.quality,
            lossless=args.lossless,
            max_width=args.max_width,
        )

        if success:
            success_count += 1
        else:
            fail_count += 1

    print(f"\nConversion complete:")
    print(f"  Success: {success_count}")
    print(f"  Failed:  {fail_count}")

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
