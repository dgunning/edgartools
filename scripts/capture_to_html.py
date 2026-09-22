#!/usr/bin/env python3
"""Capture Rich console output to HTML for manual screenshotting."""

import sys
from pathlib import Path
from rich.console import Console


def capture_script_to_html(script_path: Path, output_html: Path, width: int = 120):
    """Execute a script and save Rich output as HTML."""
    console = Console(record=True, width=width, force_terminal=True)

    # Execute the script with console available
    exec_globals = {"console": console, "__builtins__": __builtins__}
    code = script_path.read_text()

    # Redirect prints to console
    _orig_print = print

    def custom_print(*args, **kwargs):
        console.print(*args, **kwargs)

    # Replace print temporarily
    import builtins
    builtins.print = custom_print

    try:
        exec(compile(code, str(script_path), "exec"), exec_globals)
    finally:
        builtins.print = _orig_print

    # Export to HTML
    html = console.export_html(inline_styles=True, code_format="{code}")

    # Save
    output_html.write_text(html)
    print(f"Saved HTML to: {output_html}")
    print(f"Open in browser and take a screenshot, or use a headless browser to convert to PNG/WebP")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python capture_to_html.py <script.py> [output.html]")
        sys.exit(1)

    script = Path(sys.argv[1])
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(script.stem + ".html")

    if not script.exists():
        print(f"Error: {script} not found")
        sys.exit(1)

    capture_script_to_html(script, output)
