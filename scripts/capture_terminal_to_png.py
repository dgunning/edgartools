#!/usr/bin/env python3
"""Capture terminal output to PNG image using PIL/Pillow.

This is a simple alternative to snapshot_rich.py that doesn't require cairo.
It creates a simple PNG image with the terminal output.
"""

import argparse
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from rich.console import Console
from io import StringIO


def capture_terminal_output(script_path: Path) -> str:
    """Execute a script and capture its output."""
    console = Console(width=120, force_terminal=True, file=StringIO())

    # Redirect stdout to capture output
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        # Execute the script
        exec_globals = {"__builtins__": __builtins__}
        code = script_path.read_text()
        exec(compile(code, str(script_path), "exec"), exec_globals)

        # Get the output
        output = sys.stdout.getvalue()
        return output
    finally:
        sys.stdout = old_stdout


def text_to_image(text: str, output_path: Path, font_size: int = 14):
    """Convert text to a PNG image."""
    # Split text into lines
    lines = text.split('\n')

    # Calculate image dimensions
    # Use a monospace font
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Monaco.ttf", font_size)
    except:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Courier.ttf", font_size)
        except:
            font = ImageFont.load_default()

    # Calculate max line width and total height
    max_width = 0
    line_height = font_size + 4

    # Create a temporary image to measure text
    temp_img = Image.new('RGB', (1, 1))
    draw = ImageDraw.Draw(temp_img)

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        max_width = max(max_width, line_width)

    # Add padding
    padding = 20
    img_width = max_width + (padding * 2)
    img_height = (len(lines) * line_height) + (padding * 2)

    # Create the actual image
    img = Image.new('RGB', (img_width, img_height), color='#282a36')
    draw = ImageDraw.Draw(img)

    # Draw text
    y = padding
    for line in lines:
        draw.text((padding, y), line, font=font, fill='#f8f8f2')
        y += line_height

    # Save
    img.save(output_path)
    print(f"Saved: {output_path} ({img_width}x{img_height})")


def main():
    parser = argparse.ArgumentParser(description="Capture terminal output to PNG")
    parser.add_argument("script", type=Path, help="Python script to execute")
    parser.add_argument("-o", "--output", type=Path, default=Path("output.png"),
                       help="Output PNG file")
    parser.add_argument("--font-size", type=int, default=14, help="Font size")

    args = parser.parse_args()

    if not args.script.exists():
        print(f"Error: Script not found: {args.script}")
        sys.exit(1)

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Capture output
    print(f"Capturing output from {args.script}...")
    output = capture_terminal_output(args.script)

    # Convert to image
    text_to_image(output, args.output, args.font_size)


if __name__ == "__main__":
    main()
