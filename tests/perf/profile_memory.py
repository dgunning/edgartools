"""
Memory profiling for HTML parser.

Profiles memory usage during parsing to identify:
- Memory leaks
- Unnecessary object retention
- Peak memory usage
- Memory growth patterns
"""

import gc
import tracemalloc
from pathlib import Path
from typing import Dict, List, Tuple
import psutil

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig


class MemoryProfiler:
    """Profile memory usage during HTML parsing."""

    def __init__(self):
        self.process = psutil.Process()
        self.snapshots = []

    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage in MB."""
        mem_info = self.process.memory_info()
        return {
            'rss_mb': mem_info.rss / (1024 * 1024),
            'vms_mb': mem_info.vms / (1024 * 1024),
        }

    def profile_document(self, html_path: Path, detailed: bool = True) -> Dict:
        """
        Profile memory usage for parsing a document.

        Args:
            html_path: Path to HTML file
            detailed: Use tracemalloc for detailed profiling

        Returns:
            Memory profiling results
        """
        print(f"\n{'='*80}")
        print(f"MEMORY PROFILING: {html_path.name}")
        print(f"Size: {html_path.stat().st_size / (1024 * 1024):.1f}MB")
        print(f"{'='*80}\n")

        html = html_path.read_text()
        config = ParserConfig(max_document_size=100 * 1024 * 1024)

        # Force garbage collection before starting
        gc.collect()

        if detailed:
            tracemalloc.start()

        # Measure baseline memory
        mem_before = self.get_memory_usage()
        print(f"Baseline memory: {mem_before['rss_mb']:.1f}MB RSS, {mem_before['vms_mb']:.1f}MB VMS")

        # Parse document
        doc = parse_html(html, config=config)

        mem_after_parse = self.get_memory_usage()
        print(f"After parse:     {mem_after_parse['rss_mb']:.1f}MB RSS "
              f"(+{mem_after_parse['rss_mb'] - mem_before['rss_mb']:.1f}MB)")

        # Access properties to trigger lazy loading
        _ = doc.tables
        mem_after_tables = self.get_memory_usage()
        print(f"After tables:    {mem_after_tables['rss_mb']:.1f}MB RSS "
              f"(+{mem_after_tables['rss_mb'] - mem_after_parse['rss_mb']:.1f}MB)")

        _ = doc.sections
        mem_after_sections = self.get_memory_usage()
        print(f"After sections:  {mem_after_sections['rss_mb']:.1f}MB RSS "
              f"(+{mem_after_sections['rss_mb'] - mem_after_tables['rss_mb']:.1f}MB)")

        _ = doc.text()
        mem_after_text = self.get_memory_usage()
        print(f"After text:      {mem_after_text['rss_mb']:.1f}MB RSS "
              f"(+{mem_after_text['rss_mb'] - mem_after_sections['rss_mb']:.1f}MB)")

        mem_peak = self.get_memory_usage()

        # Get detailed allocation info
        if detailed:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            print(f"\n{'='*80}")
            print("TOP 20 MEMORY ALLOCATIONS")
            print(f"{'='*80}\n")

            for stat in top_stats[:20]:
                size_mb = stat.size / (1024 * 1024)
                print(f"{size_mb:>8.2f}MB  {stat.count:>8} blocks  {stat}")

            tracemalloc.stop()

        # Clean up and measure memory after cleanup
        del doc
        gc.collect()

        mem_after_cleanup = self.get_memory_usage()
        print(f"\nAfter cleanup:   {mem_after_cleanup['rss_mb']:.1f}MB RSS "
              f"(released {mem_peak['rss_mb'] - mem_after_cleanup['rss_mb']:.1f}MB)")

        # Calculate statistics
        doc_size_mb = len(html) / (1024 * 1024)
        peak_increase = mem_peak['rss_mb'] - mem_before['rss_mb']
        memory_ratio = peak_increase / doc_size_mb if doc_size_mb > 0 else 0

        result = {
            'file': html_path.name,
            'doc_size_mb': round(doc_size_mb, 2),
            'baseline_mb': round(mem_before['rss_mb'], 1),
            'peak_mb': round(mem_peak['rss_mb'], 1),
            'peak_increase_mb': round(peak_increase, 1),
            'memory_ratio': round(memory_ratio, 1),
            'after_cleanup_mb': round(mem_after_cleanup['rss_mb'], 1),
            'leaked_mb': round(mem_after_cleanup['rss_mb'] - mem_before['rss_mb'], 1),
            'parse_overhead_mb': round(mem_after_parse['rss_mb'] - mem_before['rss_mb'], 1),
            'tables_overhead_mb': round(mem_after_tables['rss_mb'] - mem_after_parse['rss_mb'], 1),
            'sections_overhead_mb': round(mem_after_sections['rss_mb'] - mem_after_tables['rss_mb'], 1),
            'text_overhead_mb': round(mem_after_text['rss_mb'] - mem_after_sections['rss_mb'], 1),
        }

        print(f"\n{'='*80}")
        print("MEMORY SUMMARY")
        print(f"{'='*80}\n")
        print(f"Document size:        {result['doc_size_mb']:.1f}MB")
        print(f"Peak memory usage:    {result['peak_increase_mb']:.1f}MB")
        print(f"Memory ratio:         {result['memory_ratio']:.1f}x document size")
        print(f"Leaked memory:        {result['leaked_mb']:.1f}MB")
        print(f"\nBreakdown:")
        print(f"  Parse:              {result['parse_overhead_mb']:.1f}MB")
        print(f"  Tables extraction:  {result['tables_overhead_mb']:.1f}MB")
        print(f"  Section extraction: {result['sections_overhead_mb']:.1f}MB")
        print(f"  Text extraction:    {result['text_overhead_mb']:.1f}MB")

        return result

    def profile_lifecycle(self, html_path: Path):
        """
        Profile memory through complete document lifecycle.

        Args:
            html_path: Path to HTML file
        """
        print(f"\n{'='*80}")
        print(f"LIFECYCLE MEMORY PROFILING: {html_path.name}")
        print(f"{'='*80}\n")

        html = html_path.read_text()
        config = ParserConfig(max_document_size=100 * 1024 * 1024)

        gc.collect()
        tracemalloc.start()

        checkpoints = []

        # Checkpoint 1: Before parsing
        mem1 = self.get_memory_usage()
        snap1 = tracemalloc.take_snapshot()
        checkpoints.append(('Before parse', mem1, snap1))
        print(f"1. Before parse:      {mem1['rss_mb']:.1f}MB")

        # Checkpoint 2: After lxml parse (internal)
        doc = parse_html(html, config=config)
        mem2 = self.get_memory_usage()
        snap2 = tracemalloc.take_snapshot()
        checkpoints.append(('After parse', mem2, snap2))
        print(f"2. After parse:       {mem2['rss_mb']:.1f}MB (+{mem2['rss_mb']-mem1['rss_mb']:.1f}MB)")

        # Checkpoint 3: After accessing document properties
        tables = doc.tables
        sections = doc.sections
        text = doc.text()

        mem3 = self.get_memory_usage()
        snap3 = tracemalloc.take_snapshot()
        checkpoints.append(('After full access', mem3, snap3))
        print(f"3. After full access: {mem3['rss_mb']:.1f}MB (+{mem3['rss_mb']-mem2['rss_mb']:.1f}MB)")

        # Checkpoint 4: After dereferencing
        del text
        del sections
        del tables

        mem4 = self.get_memory_usage()
        snap4 = tracemalloc.take_snapshot()
        checkpoints.append(('After deref', mem4, snap4))
        print(f"4. After deref:       {mem4['rss_mb']:.1f}MB ({mem4['rss_mb']-mem3['rss_mb']:+.1f}MB)")

        # Checkpoint 5: After deleting document
        del doc

        mem5 = self.get_memory_usage()
        snap5 = tracemalloc.take_snapshot()
        checkpoints.append(('After del doc', mem5, snap5))
        print(f"5. After del doc:     {mem5['rss_mb']:.1f}MB ({mem5['rss_mb']-mem4['rss_mb']:+.1f}MB)")

        # Checkpoint 6: After garbage collection
        gc.collect()

        mem6 = self.get_memory_usage()
        snap6 = tracemalloc.take_snapshot()
        checkpoints.append(('After GC', mem6, snap6))
        print(f"6. After GC:          {mem6['rss_mb']:.1f}MB ({mem6['rss_mb']-mem5['rss_mb']:+.1f}MB)")

        # Analyze memory growth between checkpoints
        print(f"\n{'='*80}")
        print("MEMORY GROWTH ANALYSIS")
        print(f"{'='*80}\n")

        for i in range(1, len(checkpoints)):
            prev_name, prev_mem, prev_snap = checkpoints[i-1]
            curr_name, curr_mem, curr_snap = checkpoints[i]

            diff = curr_snap.compare_to(prev_snap, 'lineno')
            growth = curr_mem['rss_mb'] - prev_mem['rss_mb']

            print(f"\n{prev_name} → {curr_name}: {growth:+.1f}MB")
            print(f"Top 5 allocations:")

            for stat in diff[:5]:
                size_mb = stat.size_diff / (1024 * 1024)
                if abs(size_mb) > 0.1:  # Only show significant changes
                    print(f"  {size_mb:+8.2f}MB  {stat.count_diff:+8} blocks  {stat}")

        tracemalloc.stop()

        # Check for leaks
        net_increase = mem6['rss_mb'] - mem1['rss_mb']
        print(f"\n{'='*80}")
        print("LEAK DETECTION")
        print(f"{'='*80}\n")
        print(f"Net memory increase: {net_increase:.1f}MB")

        if net_increase > 5:
            print(f"⚠️  WARNING: Potential memory leak detected!")
            print(f"   Memory increased by {net_increase:.1f}MB after cleanup")
        elif net_increase > 1:
            print(f"ℹ️  Minor memory retention: {net_increase:.1f}MB")
        else:
            print(f"✅ No significant memory leak detected")

    def compare_documents(self, html_paths: List[Path]):
        """
        Compare memory usage across multiple documents.

        Args:
            html_paths: List of HTML files to compare
        """
        print(f"\n{'='*80}")
        print("MEMORY COMPARISON ACROSS DOCUMENTS")
        print(f"{'='*80}\n")

        results = []

        for html_path in html_paths:
            if not html_path.exists():
                print(f"⚠️  Skipping {html_path.name} (not found)")
                continue

            result = self.profile_document(html_path, detailed=False)
            results.append(result)

        # Print comparison table
        print(f"\n{'='*80}")
        print("MEMORY USAGE COMPARISON")
        print(f"{'='*80}\n")

        print(f"{'Document':<30} {'Size':>8} {'Peak':>8} {'Ratio':>8} {'Leaked':>8}")
        print(f"{'-'*30} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

        for r in sorted(results, key=lambda x: x['memory_ratio'], reverse=True):
            status = "⚠️ " if r['memory_ratio'] > 5 else "  "
            print(f"{status}{r['file']:<28} "
                  f"{r['doc_size_mb']:>6.1f}MB "
                  f"{r['peak_increase_mb']:>6.1f}MB "
                  f"{r['memory_ratio']:>7.1f}x "
                  f"{r['leaked_mb']:>6.1f}MB")

        # Identify problematic documents
        high_ratio = [r for r in results if r['memory_ratio'] > 5]
        high_leak = [r for r in results if r['leaked_mb'] > 2]

        if high_ratio:
            print(f"\n⚠️  High memory ratio (>5x):")
            for r in high_ratio:
                print(f"   {r['file']}: {r['memory_ratio']:.1f}x ({r['peak_increase_mb']:.1f}MB for {r['doc_size_mb']:.1f}MB doc)")

        if high_leak:
            print(f"\n⚠️  Potential memory leaks (>2MB):")
            for r in high_leak:
                print(f"   {r['file']}: {r['leaked_mb']:.1f}MB leaked")

        return results


def main():
    """Run memory profiling."""
    import argparse

    parser = argparse.ArgumentParser(description='Profile HTML parser memory usage')
    parser.add_argument('--file', type=Path, default=None,
                       help='Specific file to profile')
    parser.add_argument('--lifecycle', action='store_true',
                       help='Profile complete lifecycle')
    parser.add_argument('--compare', action='store_true',
                       help='Compare multiple documents')
    parser.add_argument('--detailed', action='store_true', default=True,
                       help='Use detailed tracemalloc profiling')

    args = parser.parse_args()

    profiler = MemoryProfiler()

    if args.file:
        # Profile single file
        if args.lifecycle:
            profiler.profile_lifecycle(args.file)
        else:
            profiler.profile_document(args.file, detailed=args.detailed)

    elif args.compare:
        # Compare multiple documents
        corpus_dir = Path('data/html')
        files = [
            corpus_dir / 'Apple.10-K.html',      # 1.8MB - baseline
            corpus_dir / 'MSFT.10-K.html',       # 7.8MB - memory spike
            corpus_dir / 'JPM.10-K.html',        # 50MB - streaming
            corpus_dir / 'Apple.10-Q.html',      # 1.1MB - small
        ]
        profiler.compare_documents(files)

    else:
        # Default: Profile key documents
        corpus_dir = Path('data/html')

        # Profile MSFT (known memory issue)
        msft_file = corpus_dir / 'MSFT.10-K.html'
        if msft_file.exists():
            print("\n" + "="*80)
            print("INVESTIGATING MSFT MEMORY SPIKE")
            print("="*80)
            profiler.profile_document(msft_file, detailed=True)
            profiler.profile_lifecycle(msft_file)

        # Profile Apple (normal case)
        apple_file = corpus_dir / 'Apple.10-K.html'
        if apple_file.exists():
            print("\n" + "="*80)
            print("BASELINE: APPLE 10-K")
            print("="*80)
            profiler.profile_document(apple_file, detailed=False)

    print("\n" + "="*80)
    print("MEMORY PROFILING COMPLETE")
    print("="*80)
    print("\nKey metrics to watch:")
    print("- Memory ratio > 5x: Investigate data structure efficiency")
    print("- Leaked memory > 2MB: Potential memory leak")
    print("- Large section/table overhead: Optimize extraction algorithms")


if __name__ == '__main__':
    main()
