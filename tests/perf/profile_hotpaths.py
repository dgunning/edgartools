"""
Profile hot paths in HTML parser to identify performance bottlenecks.

Uses cProfile to identify where time is spent during parsing.
"""

import cProfile
import pstats
import io
from pathlib import Path
from pstats import SortKey

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig


def profile_document(html_path: Path, iterations: int = 10):
    """
    Profile parsing a single document.

    Args:
        html_path: Path to HTML file
        iterations: Number of parsing iterations
    """
    html = html_path.read_text()
    config = ParserConfig(max_document_size=100 * 1024 * 1024)

    print(f"\n{'='*80}")
    print(f"PROFILING: {html_path.name}")
    print(f"Size: {len(html) / (1024 * 1024):.1f}MB")
    print(f"Iterations: {iterations}")
    print(f"{'='*80}\n")

    # Create profiler
    profiler = cProfile.Profile()

    # Profile the parsing
    profiler.enable()
    for _ in range(iterations):
        doc = parse_html(html, config=config)
        # Access properties to trigger lazy loading
        _ = doc.tables
        _ = doc.sections
        del doc
    profiler.disable()

    # Print statistics
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)

    # Sort by cumulative time
    print("\n" + "="*80)
    print("TOP 30 FUNCTIONS BY CUMULATIVE TIME")
    print("="*80)
    ps.sort_stats(SortKey.CUMULATIVE).print_stats(30)
    print(s.getvalue())

    # Sort by total time (self time)
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)
    print("\n" + "="*80)
    print("TOP 30 FUNCTIONS BY SELF TIME")
    print("="*80)
    ps.sort_stats(SortKey.TIME).print_stats(30)
    print(s.getvalue())

    # Filter to show only edgar.documents code
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)
    print("\n" + "="*80)
    print("EDGAR.DOCUMENTS FUNCTIONS ONLY")
    print("="*80)
    ps.sort_stats(SortKey.CUMULATIVE).print_stats('edgar/documents')
    print(s.getvalue())

    # Save detailed stats to file
    output_file = Path('tests/perf') / f'profile_{html_path.stem}.stats'
    ps.dump_stats(str(output_file))
    print(f"\n💾 Detailed profile saved to {output_file}")
    print(f"   View with: python -m pstats {output_file}")
    print(f"   Or visualize with: snakeviz {output_file}")

    return profiler


def profile_specific_operations(html_path: Path):
    """
    Profile specific parser operations separately.

    Args:
        html_path: Path to HTML file
    """
    html = html_path.read_text()
    config = ParserConfig(max_document_size=100 * 1024 * 1024)

    print(f"\n{'='*80}")
    print(f"OPERATION-SPECIFIC PROFILING: {html_path.name}")
    print(f"{'='*80}\n")

    operations = {
        'parse_only': lambda: parse_html(html, config=config),
        'parse_and_tables': lambda: (doc := parse_html(html, config=config), doc.tables),
        'parse_and_sections': lambda: (doc := parse_html(html, config=config), doc.sections),
        'parse_and_text': lambda: (doc := parse_html(html, config=config), doc.text()),
        'parse_and_all': lambda: (
            doc := parse_html(html, config=config),
            doc.tables,
            doc.sections,
            doc.text()
        ),
    }

    results = {}

    for op_name, op_func in operations.items():
        profiler = cProfile.Profile()

        profiler.enable()
        for _ in range(5):
            op_func()
        profiler.disable()

        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s)
        ps.sort_stats(SortKey.CUMULATIVE)

        # Get total time
        total_time = sum(stat[2] for stat in ps.stats.values())
        results[op_name] = total_time

        print(f"{op_name:20} {total_time:>8.3f}s")

    print(f"\n{'='*80}")
    print("OPERATION BREAKDOWN")
    print(f"{'='*80}\n")

    base = results['parse_only']
    print(f"Base parsing:        {base:>8.3f}s (100%)")
    print(f"+ Tables:            {results['parse_and_tables']-base:>8.3f}s (+{(results['parse_and_tables']-base)/base*100:.1f}%)")
    print(f"+ Sections:          {results['parse_and_sections']-base:>8.3f}s (+{(results['parse_and_sections']-base)/base*100:.1f}%)")
    print(f"+ Text:              {results['parse_and_text']-base:>8.3f}s (+{(results['parse_and_text']-base)/base*100:.1f}%)")
    print(f"+ All:               {results['parse_and_all']-base:>8.3f}s (+{(results['parse_and_all']-base)/base*100:.1f}%)")


def analyze_table_processing(html_path: Path):
    """
    Profile table processing specifically.

    Args:
        html_path: Path to HTML file with many tables
    """
    html = html_path.read_text()
    config = ParserConfig(max_document_size=100 * 1024 * 1024)

    print(f"\n{'='*80}")
    print(f"TABLE PROCESSING ANALYSIS: {html_path.name}")
    print(f"{'='*80}\n")

    profiler = cProfile.Profile()

    profiler.enable()
    doc = parse_html(html, config=config)
    tables = doc.tables
    profiler.disable()

    print(f"Total tables: {len(tables)}")

    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)

    # Focus on table-related functions
    print("\n" + "="*80)
    print("TABLE PROCESSING HOTSPOTS")
    print("="*80)
    ps.sort_stats(SortKey.CUMULATIVE).print_stats('table')
    print(s.getvalue())


def main():
    """Run profiling suite."""
    import argparse

    parser = argparse.ArgumentParser(description='Profile HTML parser hot paths')
    parser.add_argument('--file', type=Path, default=None,
                       help='Specific file to profile')
    parser.add_argument('--iterations', type=int, default=10,
                       help='Number of iterations')
    parser.add_argument('--operations', action='store_true',
                       help='Profile specific operations')
    parser.add_argument('--tables', action='store_true',
                       help='Profile table processing')

    args = parser.parse_args()

    # Default files to profile
    if args.file:
        files = [args.file]
    else:
        corpus_dir = Path('data/html')
        files = [
            corpus_dir / 'Apple.10-K.html',       # Medium, typical
            corpus_dir / 'MSFT.10-K.html',        # Large, memory issue
            corpus_dir / 'JPM.10-K.html',         # Very large, streaming
        ]

    for html_file in files:
        if not html_file.exists():
            print(f"⚠️  File not found: {html_file}")
            continue

        # Main profiling
        profile_document(html_file, iterations=args.iterations)

        # Operation-specific profiling
        if args.operations:
            profile_specific_operations(html_file)

        # Table processing profiling
        if args.tables:
            analyze_table_processing(html_file)

    print("\n" + "="*80)
    print("PROFILING COMPLETE")
    print("="*80)
    print("\nNext steps:")
    print("1. Review profile_*.stats files with: python -m pstats <file>")
    print("2. Visualize with snakeviz: snakeviz <file>")
    print("3. Focus on functions with high cumulative time")
    print("4. Look for optimization opportunities in edgar/documents code")


if __name__ == '__main__':
    main()
