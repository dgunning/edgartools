#!/usr/bin/env python3
"""Convert SVG files to PNG format using Inkscape.

This script provides a convenient interface for converting SVG files to PNG
using Inkscape's command-line interface. Supports single file conversion,
batch conversion, and custom output dimensions.

Examples:
    # Convert single file
    python convert_svg_to_png.py input.svg

    # Convert with custom output path
    python convert_svg_to_png.py input.svg -o output.png

    # Convert with custom dimensions
    python convert_svg_to_png.py input.svg --width 1024 --height 768

    # Batch convert all SVGs in a directory
    python convert_svg_to_png.py path/to/svgs/*.svg

    # Convert with DPI setting
    python convert_svg_to_png.py input.svg --dpi 300
"""

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional, List


def find_inkscape() -> Optional[str]:
    """Find the Inkscape executable path based on the platform.

    Returns:
        Path to Inkscape executable or None if not found.
    """
    system = platform.system()

    # Common Inkscape paths by platform
    if system == "Darwin":  # macOS
        paths = [
            "/Applications/Inkscape.app/Contents/MacOS/inkscape",
            "/usr/local/bin/inkscape",
            os.path.expanduser("~/Applications/Inkscape.app/Contents/MacOS/inkscape"),
        ]
    elif system == "Linux":
        paths = [
            "/usr/bin/inkscape",
            "/usr/local/bin/inkscape",
            "/snap/bin/inkscape",
        ]
    elif system == "Windows":
        paths = [
            r"C:\Program Files\Inkscape\bin\inkscape.exe",
            r"C:\Program Files (x86)\Inkscape\bin\inkscape.exe",
        ]
    else:
        paths = []

    # Check common paths
    for path in paths:
        if os.path.exists(path):
            return path

    # Try to find in PATH
    try:
        result = subprocess.run(
            ["which", "inkscape"] if system != "Windows" else ["where", "inkscape"],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
    except Exception:
        pass

    return None


def convert_svg_to_png(
    svg_path: Path,
    png_path: Optional[Path] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    dpi: Optional[int] = None,
    inkscape_path: Optional[str] = None
) -> bool:
    """Convert a single SVG file to PNG.

    Args:
        svg_path: Path to input SVG file
        png_path: Path to output PNG file (optional, defaults to same name with .png)
        width: Output width in pixels (optional)
        height: Output height in pixels (optional)
        dpi: Output DPI (optional, default is 96)
        inkscape_path: Path to Inkscape executable (optional, will auto-detect)

    Returns:
        True if conversion successful, False otherwise.
    """
    # Find Inkscape if not provided
    if inkscape_path is None:
        inkscape_path = find_inkscape()
        if inkscape_path is None:
            print("Error: Inkscape not found. Please install Inkscape or specify path with --inkscape-path")
            return False

    # Validate input file exists
    if not svg_path.exists():
        print(f"Error: Input file not found: {svg_path}")
        return False

    # Determine output path
    if png_path is None:
        png_path = svg_path.with_suffix('.png')

    # Build Inkscape command
    cmd = [
        inkscape_path,
        str(svg_path),
        f"--export-filename={png_path}"
    ]

    # Add optional parameters
    if width is not None:
        cmd.append(f"--export-width={width}")

    if height is not None:
        cmd.append(f"--export-height={height}")

    if dpi is not None:
        cmd.append(f"--export-dpi={dpi}")

    # Execute conversion
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode == 0:
            print(f"✓ Converted: {svg_path} → {png_path}")
            return True
        else:
            print(f"✗ Failed to convert {svg_path}")
            if result.stderr:
                print(f"  Error: {result.stderr}")
            return False

    except Exception as e:
        print(f"✗ Error converting {svg_path}: {e}")
        return False


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Convert SVG files to PNG using Inkscape",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.svg
  %(prog)s input.svg -o output.png
  %(prog)s input.svg --width 1024 --height 768
  %(prog)s path/to/svgs/*.svg
  %(prog)s input.svg --dpi 300
        """
    )

    parser.add_argument(
        'input',
        nargs='+',
        type=Path,
        help='Input SVG file(s) to convert'
    )

    parser.add_argument(
        '-o', '--output',
        type=Path,
        help='Output PNG file path (only for single file conversion)'
    )

    parser.add_argument(
        '--width',
        type=int,
        help='Output width in pixels'
    )

    parser.add_argument(
        '--height',
        type=int,
        help='Output height in pixels'
    )

    parser.add_argument(
        '--dpi',
        type=int,
        help='Output DPI (default: 96)'
    )

    parser.add_argument(
        '--inkscape-path',
        type=str,
        help='Path to Inkscape executable (auto-detected if not specified)'
    )

    args = parser.parse_args()

    # Validate arguments
    if args.output and len(args.input) > 1:
        print("Error: --output can only be used with a single input file")
        sys.exit(1)

    # Find Inkscape once for all conversions
    inkscape_path = args.inkscape_path or find_inkscape()
    if inkscape_path is None:
        print("Error: Inkscape not found!")
        print("\nPlease install Inkscape:")
        print("  macOS:   brew install inkscape")
        print("  Linux:   sudo apt install inkscape")
        print("  Windows: Download from https://inkscape.org/release/")
        print("\nOr specify the path with --inkscape-path")
        sys.exit(1)

    print(f"Using Inkscape: {inkscape_path}\n")

    # Convert files
    success_count = 0
    fail_count = 0

    for svg_path in args.input:
        # Handle glob patterns that might not expand
        if not svg_path.exists():
            print(f"Warning: Skipping non-existent file: {svg_path}")
            fail_count += 1
            continue

        # Skip non-SVG files
        if svg_path.suffix.lower() != '.svg':
            print(f"Warning: Skipping non-SVG file: {svg_path}")
            fail_count += 1
            continue

        success = convert_svg_to_png(
            svg_path=svg_path,
            png_path=args.output if args.output else None,
            width=args.width,
            height=args.height,
            dpi=args.dpi,
            inkscape_path=inkscape_path
        )

        if success:
            success_count += 1
        else:
            fail_count += 1

    # Print summary
    print(f"\nConversion complete:")
    print(f"  Success: {success_count}")
    print(f"  Failed:  {fail_count}")

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
