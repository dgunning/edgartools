#!/usr/bin/env python
"""
Simple parser comparison tool for quality improvement loop.

Usage:
    # Use shortcuts (easy!)
    python tests/manual/compare_parsers.py aapl
    python tests/manual/compare_parsers.py nvda --tables
    python tests/manual/compare_parsers.py 'tsla 10-q' --table 5

    # Or use full paths
    python tests/manual/compare_parsers.py data/html/Apple.10-K.html

    # Show only tables
    python tests/manual/compare_parsers.py aapl --tables

    # Show specific table
    python tests/manual/compare_parsers.py aapl --table 5

    # Show text comparison
    python tests/manual/compare_parsers.py msft --text

    # Show sections
    python tests/manual/compare_parsers.py orcl --sections

    # Run all test files
    python tests/manual/compare_parsers.py --all

Available shortcuts:
    Companies: aapl, msft, tsla, nvda, orcl
    Filing types: 10-K (default), 10-Q, 8-K
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Clear cached modules for clean imports
modules_to_remove = [m for m in list(sys.modules.keys()) if 'edgar.documents' in m]
for m in modules_to_remove:
    del sys.modules[m]

import argparse
import time
from typing import Optional, List

from rich.console import Console
from rich.table import Table as RichTable
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text

# Import both parsers
from edgar.files.html import Document as OldDocument
from edgar.documents import HTMLParser, ParserConfig, parse_html
from edgar.richtools import rich_to_text

console = Console(width=200)

# Test corpus from quality improvement strategy
TEST_FILES = [
    "data/html/Apple.10-K.html",
    "data/html/Oracle.10-K.html",
    "data/html/Nvidia.10-K.html",
    "data/html/Microsoft.10-K.html",
    "data/html/Tesla.10-K.html",
]

# Shortcuts for common companies and filings
SHORTCUTS = {
    # Companies
    'aapl': 'Apple',
    'apple': 'Apple',
    'msft': 'Microsoft',
    'microsoft': 'Microsoft',
    'tsla': 'Tesla',
    'tesla': 'Tesla',
    'nvda': 'Nvidia',
    'nvidia': 'Nvidia',
    'orcl': 'Oracle',
    'oracle': 'Oracle',
}

def resolve_file_path(file_arg: str) -> Optional[Path]:
    """
    Resolve a file path from various input formats.

    Examples:
        AAPL 10-K -> data/html/Apple.10-K.html
        aapl -> data/html/Apple.10-K.html
        apple 10q -> data/html/Apple.10-Q.html
        data/html/Apple.10-K.html -> data/html/Apple.10-K.html
    """
    # If it's already a valid path, use it
    path = Path(file_arg)
    if path.exists():
        return path

    # Parse the input
    parts = file_arg.lower().split()

    company = None
    filing_type = None

    # Try to identify company and filing type
    for part in parts:
        part_clean = part.replace('-', '').replace('.', '').strip()

        # Check if it's a company shortcut
        if part_clean in SHORTCUTS:
            company = SHORTCUTS[part_clean]

        # Check if it's a filing type
        if part_clean in ['10k', '10q', '8k', 'def14a', 'proxy']:
            if part_clean == '10k':
                filing_type = '10-K'
            elif part_clean == '10q':
                filing_type = '10-Q'
            elif part_clean == '8k':
                filing_type = '8-K'
            elif part_clean in ['def14a', 'proxy']:
                filing_type = 'DEF-14A'

    # If we found a company, try to find the file
    if company:
        # Default to 10-K if no filing type specified
        if not filing_type:
            filing_type = '10-K'

        # Try to find the file
        possible_paths = [
            Path(f"data/html/{company}.{filing_type}.html"),
            Path(f"data/html/{company}-{filing_type}.html"),
            Path(f"data/html/{company}_{filing_type}.html"),
        ]

        for p in possible_paths:
            if p.exists():
                return p

    # If nothing found, try to find any file with that pattern
    if company:
        data_dir = Path("data/html")
        if data_dir.exists():
            # Find files matching the company name
            matches = list(data_dir.glob(f"{company}*.html"))
            if matches:
                console.print(f"[yellow]Multiple files found for {company}:[/yellow]")
                for i, match in enumerate(matches):
                    console.print(f"  {i}. {match.name}")
                console.print(f"[yellow]Using: {matches[0].name}[/yellow]")
                return matches[0]

    # Try original path
    return Path(file_arg) if file_arg else None


class ParserComparator:
    """Simple comparison between old and new parsers."""

    def __init__(self, html_path: Path):
        self.html_path = html_path
        self.html_content = html_path.read_text(encoding='utf-8')
        self.old_doc = None
        self.new_doc = None
        self.old_time = 0
        self.new_time = 0

    def parse_both(self):
        """Parse with both parsers."""
        console.print(f"\n[bold cyan]Parsing: {self.html_path.name}[/bold cyan]")
        console.print(f"Size: {len(self.html_content):,} bytes ({len(self.html_content)/1024/1024:.1f} MB)")

        # Old parser
        start = time.time()
        self.old_doc = OldDocument.parse(self.html_content)
        self.old_time = (time.time() - start) * 1000

        # New parser
        start = time.time()
        self.new_doc = parse_html(self.html_content)
        self.new_time = (time.time() - start) * 1000

        # Quick stats
        speedup = self.old_time / self.new_time if self.new_time > 0 else 0
        console.print(f"[yellow]Old: {self.old_time:.0f}ms[/yellow]  [green]New: {self.new_time:.0f}ms[/green]  [magenta]{speedup:.1f}x faster[/magenta]")

    def show_overview(self):
        """Show quick overview comparison."""
        table = RichTable(title="Parser Comparison Overview", show_lines=True)
        table.add_column("Metric", style="cyan", width=25)
        table.add_column("Old Parser", style="yellow", width=30)
        table.add_column("New Parser", style="green", width=30)
        table.add_column("Notes", style="dim", width=40)

        # Parse time
        speedup = self.old_time / self.new_time if self.new_time > 0 else 0
        table.add_row(
            "Parse Time",
            f"{self.old_time:.0f}ms",
            f"{self.new_time:.0f}ms",
            f"{speedup:.1f}x faster" if speedup > 1 else f"{1/speedup:.1f}x slower"
        )

        # Tables
        old_tables = list(self.old_doc.tables) if hasattr(self.old_doc, 'tables') else []
        new_tables = list(self.new_doc.tables)
        table.add_row(
            "Tables Found",
            str(len(old_tables)),
            str(len(new_tables)),
            f"{len(new_tables) - len(old_tables):+d} difference"
        )

        # Text length
        old_text = self.old_doc.text if hasattr(self.old_doc, 'text') else ""
        new_text = self.new_doc.text()
        table.add_row(
            "Text Length",
            f"{len(old_text):,}",
            f"{len(new_text):,}",
            f"{len(new_text) - len(old_text):+,} chars"
        )

        # Sections
        old_sections = len(self.old_doc.sections) if hasattr(self.old_doc, 'sections') else 0
        new_sections = len(self.new_doc.sections)
        table.add_row(
            "Sections",
            str(old_sections),
            str(new_sections),
            f"{new_sections - old_sections:+d} more detected"
        )

        # New parser features
        table.add_row(
            "Headings",
            "N/A",
            str(len(self.new_doc.headings)),
            "New feature"
        )

        table.add_row(
            "XBRL Data",
            "N/A",
            "Yes" if self.new_doc.has_xbrl else "No",
            "New feature"
        )

        console.print(table)

    def show_tables(self, table_index: Optional[int] = None, table_range: Optional[tuple] = None):
        """Show table comparison."""
        old_tables = list(self.old_doc.tables) if hasattr(self.old_doc, 'tables') else []
        new_tables = list(self.new_doc.tables)

        if table_range is not None:
            # Show range of tables
            start, end = table_range
            end = min(end, len(new_tables))

            console.print(f"\n[bold]Tables {start} to {end-1} Comparison[/bold]\n")

            for idx in range(start, end):
                if idx >= len(new_tables):
                    break

                console.print(f"\n[cyan]═══ Table {idx} ═══[/cyan]")

                # Old table (if available)
                if idx < len(old_tables):
                    old_rendered = old_tables[idx].render(console_width=195)
                    if old_rendered:
                        old_text = rich_to_text(old_rendered)
                        old_panel = Panel(old_text, title="Old Parser", border_style="yellow", width=198)
                        console.print(old_panel)

                # New table
                console.print("\n[green]New Parser:[/green]")
                new_table = new_tables[idx]
                new_rich_table = new_table.render(width=195)
                new_panel = Panel(new_rich_table, title="New Parser", border_style="green", width=198)
                console.print(new_panel)

                console.print("\n")

            return

        if table_index is not None:
            # Show specific table with full rendering like check_tables.py
            if table_index >= len(new_tables):
                console.print(f"[red]Table {table_index} not found. Only {len(new_tables)} tables available.[/red]")
                return

            console.print(f"\n[cyan]Table {table_index} Rendering Comparison:[/cyan]")

            # Old table (if available)
            if table_index < len(old_tables):
                old_rendered = old_tables[table_index].render(console_width=195)
                if old_rendered:
                    old_text = rich_to_text(old_rendered)
                    old_panel = Panel(old_text, title="Old Parser", border_style="yellow", width=198)
                    console.print(old_panel)

            # New table - render directly, not in panel
            console.print("\n[green]New Parser (with render()):[/green]")
            new_table = new_tables[table_index]
            new_rich_table = new_table.render(width=195)
            new_panel = Panel(new_rich_table, title="New Parser", border_style="green", width=198)
            console.print(new_panel)

            # Table details
            details = RichTable(show_header=False)
            details.add_column("Property", style="cyan")
            details.add_column("Value", style="white")

            details.add_row("Caption", new_table.caption or "None")
            details.add_row("Dimensions", f"{new_table.row_count} rows × {new_table.col_count} cols")
            details.add_row("Type", str(new_table.table_type) if hasattr(new_table, 'table_type') else "Unknown")
            details.add_row("Has Header", "Yes" if new_table.has_header else "No")

            console.print("\n[bold]Table Details:[/bold]")
            console.print(details)
        else:
            # Show all tables summary
            console.print(f"\n[bold]Tables Summary[/bold]")
            console.print(f"Old parser: {len(old_tables)} tables")
            console.print(f"New parser: {len(new_tables)} tables\n")

            # List tables
            for i, table in enumerate(new_tables[:20]):  # Limit to first 20
                caption = table.caption[:50] if table.caption else "[No caption]"
                dims = f"{table.row_count}×{table.col_count}"
                console.print(f"  {i:2d}. {caption:50s} {dims:>8s}")

            if len(new_tables) > 20:
                console.print(f"\n  ... and {len(new_tables) - 20} more tables")

            console.print("\n[dim]Tip: Use --table N to see specific table comparison[/dim]")

    def show_text(self, lines: int = 50):
        """Show text comparison."""
        old_text = self.old_doc.text if hasattr(self.old_doc, 'text') else ""
        new_text = self.new_doc.text()

        # Show preview
        old_lines = old_text.split('\n')[:lines]
        new_lines = new_text.split('\n')[:lines]

        old_preview = '\n'.join(old_lines)
        new_preview = '\n'.join(new_lines)

        console.print("\n[bold]Text Preview (first 50 lines)[/bold]")

        # Side by side panels
        old_panel = Panel(old_preview, title="Old Parser", border_style="yellow", width=95)
        new_panel = Panel(new_preview, title="New Parser", border_style="green", width=95)

        console.print(Columns([old_panel, new_panel]))

        # Stats
        console.print(f"\n[dim]Old: {len(old_lines)} lines shown, {len(old_text):,} total chars[/dim]")
        console.print(f"[dim]New: {len(new_lines)} lines shown, {len(new_text):,} total chars[/dim]")

    def show_sections(self):
        """Show sections comparison."""
        old_sections = self.old_doc.sections if hasattr(self.old_doc, 'sections') else {}
        new_sections = self.new_doc.sections

        console.print(f"\n[bold]Sections Comparison[/bold]")
        console.print(f"Old: {len(old_sections)} sections")
        console.print(f"New: {len(new_sections)} sections\n")

        # List new sections
        table = RichTable(title="Sections Detected (New Parser)")
        table.add_column("#", style="cyan", width=5)
        table.add_column("Section Name", style="green", width=40)
        table.add_column("Text Length", style="yellow", width=15)
        table.add_column("Tables", style="magenta", width=10)

        for i, (name, section) in enumerate(new_sections.items()):
            text_len = len(section.text())
            table_count = len(section.tables())
            table.add_row(str(i), name, f"{text_len:,}", str(table_count))

        console.print(table)


def run_single_file(file_arg: str, args):
    """Run comparison on a single file."""
    file_path = resolve_file_path(file_arg)

    if not file_path or not file_path.exists():
        console.print(f"[red]File not found: {file_arg}[/red]")
        console.print("\n[yellow]Available shortcuts:[/yellow]")
        console.print("  Companies: aapl, msft, tsla, nvda, orcl")
        console.print("  Filing types: 10-K, 10-Q, 8-K")
        console.print("\n[yellow]Examples:[/yellow]")
        console.print("  python tests/manual/compare_parsers.py aapl")
        console.print("  python tests/manual/compare_parsers.py 'aapl 10-q'")
        console.print("  python tests/manual/compare_parsers.py nvda")
        console.print("  python tests/manual/compare_parsers.py data/html/Apple.10-K.html")
        return

    comparator = ParserComparator(file_path)
    comparator.parse_both()

    # Show requested output
    if args.tables:
        comparator.show_tables()
    elif args.range:
        # Parse range string
        try:
            parts = args.range.split(':')
            start = int(parts[0])
            end = int(parts[1]) if len(parts) > 1 else start + 1
            comparator.show_tables(table_range=(start, end))
        except (ValueError, IndexError):
            console.print(f"[red]Invalid range format: {args.range}. Use START:END (e.g., 5:10)[/red]")
    elif args.table is not None:
        comparator.show_tables(table_index=args.table)
    elif args.text:
        comparator.show_text(lines=args.lines)
    elif args.sections:
        comparator.show_sections()
    else:
        # Default: show overview
        comparator.show_overview()


def run_all_files(args):
    """Run comparison on all test files."""
    console.print("[bold magenta]Running comparison on all test files[/bold magenta]\n")

    results = []
    for file_path_str in TEST_FILES:
        file_path = Path(file_path_str)
        if not file_path.exists():
            console.print(f"[yellow]Skipping {file_path.name} (not found)[/yellow]")
            continue

        try:
            comparator = ParserComparator(file_path)
            comparator.parse_both()
            comparator.show_overview()
            console.print("\n" + "="*80 + "\n")

            results.append({
                'file': file_path.name,
                'old_time': comparator.old_time,
                'new_time': comparator.new_time,
                'old_tables': len(list(comparator.old_doc.tables)) if hasattr(comparator.old_doc, 'tables') else 0,
                'new_tables': len(list(comparator.new_doc.tables)),
            })
        except Exception as e:
            console.print(f"[red]Error processing {file_path.name}: {e}[/red]\n")

    # Summary table
    if results:
        console.print("\n[bold]Summary Across All Files[/bold]")
        summary = RichTable()
        summary.add_column("File", style="cyan")
        summary.add_column("Old Time", style="yellow")
        summary.add_column("New Time", style="green")
        summary.add_column("Speedup", style="magenta")
        summary.add_column("Tables", style="blue")

        for r in results:
            speedup = r['old_time'] / r['new_time'] if r['new_time'] > 0 else 0
            summary.add_row(
                r['file'],
                f"{r['old_time']:.0f}ms",
                f"{r['new_time']:.0f}ms",
                f"{speedup:.1f}x",
                f"{r['old_tables']} → {r['new_tables']}"
            )

        console.print(summary)


def main():
    parser = argparse.ArgumentParser(
        description='Compare OLD and NEW HTML parsers',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use shortcuts (ticker symbols)
  python tests/manual/compare_parsers.py aapl
  python tests/manual/compare_parsers.py nvda --tables
  python tests/manual/compare_parsers.py 'tsla 10-q' --table 5

  # Or use full paths
  python tests/manual/compare_parsers.py data/html/Apple.10-K.html

  # Show all tables
  python tests/manual/compare_parsers.py aapl --tables

  # Show specific table
  python tests/manual/compare_parsers.py aapl --table 5

  # Show text comparison
  python tests/manual/compare_parsers.py msft --text

  # Run all test files
  python tests/manual/compare_parsers.py --all

Available shortcuts:
  Companies: aapl, msft, tsla, nvda, orcl (or full names)
  Filing types: 10-K (default), 10-Q, 8-K
        """
    )

    parser.add_argument('file', nargs='?', help='HTML file to compare (or use shortcuts like "aapl")')
    parser.add_argument('--all', action='store_true', help='Run on all test files')
    parser.add_argument('--tables', action='store_true', help='Show tables summary')
    parser.add_argument('--table', type=int, metavar='N', help='Show specific table N')
    parser.add_argument('--range', type=str, metavar='START:END', help='Show range of tables (e.g., 5:10)')
    parser.add_argument('--text', action='store_true', help='Show text comparison')
    parser.add_argument('--sections', action='store_true', help='Show sections comparison')
    parser.add_argument('--lines', type=int, default=50, help='Number of text lines to show (default: 50)')

    args = parser.parse_args()

    # Validate arguments
    if not args.all and not args.file:
        parser.print_help()
        console.print("\n[red]Error: Provide a file or use --all[/red]")
        sys.exit(1)

    try:
        if args.all:
            run_all_files(args)
        else:
            run_single_file(args.file, args)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
