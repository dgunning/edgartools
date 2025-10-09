"""
Comprehensive benchmark suite for HTML parser performance.

Benchmarks:
- Parse time across document sizes
- Memory usage
- Throughput (MB/s)
- Comparison with old parser
- Batch processing performance
"""

import time
import statistics
from pathlib import Path
from typing import Dict, List, Optional
import psutil
import json

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig


class ParserBenchmark:
    """Comprehensive HTML parser performance benchmarks."""

    def __init__(self, corpus_dir: Path = None):
        """
        Initialize benchmark suite.

        Args:
            corpus_dir: Directory containing HTML test files
        """
        self.corpus_dir = corpus_dir or Path('data/html')
        self.results = []
        self.process = psutil.Process()

    def benchmark_document(
        self,
        html_path: Path,
        runs: int = 5,
        config: Optional[ParserConfig] = None
    ) -> Dict:
        """
        Benchmark parsing a single document.

        Args:
            html_path: Path to HTML file
            runs: Number of runs to average
            config: Parser configuration

        Returns:
            Dict with benchmark results
        """
        html = html_path.read_text()
        file_size_mb = len(html) / (1024 * 1024)

        if config is None:
            config = ParserConfig(max_document_size=100 * 1024 * 1024)

        times = []
        memory_usage = []
        table_counts = []
        section_counts = []

        for i in range(runs):
            # Force garbage collection before measurement
            import gc
            gc.collect()

            mem_before = self.process.memory_info().rss / (1024 * 1024)

            start = time.perf_counter()
            doc = parse_html(html, config=config)
            elapsed = time.perf_counter() - start

            mem_after = self.process.memory_info().rss / (1024 * 1024)

            times.append(elapsed)
            memory_usage.append(mem_after - mem_before)
            table_counts.append(len(doc.tables))
            section_counts.append(len(doc.sections))

            # Clean up
            del doc
            gc.collect()

        return {
            'file': html_path.name,
            'size_mb': round(file_size_mb, 2),
            'avg_time_s': round(statistics.mean(times), 3),
            'median_time_s': round(statistics.median(times), 3),
            'min_time_s': round(min(times), 3),
            'max_time_s': round(max(times), 3),
            'std_dev_s': round(statistics.stdev(times) if len(times) > 1 else 0, 3),
            'avg_memory_mb': round(statistics.mean(memory_usage), 1),
            'max_memory_mb': round(max(memory_usage), 1),
            'throughput_mbs': round(file_size_mb / statistics.mean(times), 2),
            'tables': table_counts[0],
            'sections': section_counts[0],
            'runs': runs
        }

    def benchmark_corpus(self, pattern: str = '*.html', max_files: Optional[int] = None) -> List[Dict]:
        """
        Benchmark all files in corpus.

        Args:
            pattern: Glob pattern for HTML files
            max_files: Maximum number of files to benchmark (None = all)

        Returns:
            List of benchmark results
        """
        print(f"\n{'='*80}")
        print(f"HTML PARSER PERFORMANCE BENCHMARK")
        print(f"{'='*80}\n")

        files = sorted(self.corpus_dir.glob(pattern))
        if max_files:
            files = files[:max_files]

        print(f"Benchmarking {len(files)} files from {self.corpus_dir}\n")
        print(f"{'File':<35} {'Size':>8} {'Time':>8} {'Memory':>9} {'Speed':>10} {'Tables':>7}")
        print(f"{'-'*35} {'-'*8} {'-'*8} {'-'*9} {'-'*10} {'-'*7}")

        self.results = []

        for html_file in files:
            try:
                result = self.benchmark_document(html_file)
                self.results.append(result)

                print(f"{result['file']:<35} "
                      f"{result['size_mb']:>6.1f}MB "
                      f"{result['avg_time_s']:>7.3f}s "
                      f"{result['avg_memory_mb']:>8.1f}MB "
                      f"{result['throughput_mbs']:>9.1f}MB/s "
                      f"{result['tables']:>7}")

            except Exception as e:
                print(f"{html_file.name:<35} ERROR: {e}")

        self._print_summary()
        return self.results

    def _print_summary(self):
        """Print benchmark summary statistics."""
        if not self.results:
            return

        print(f"\n{'-'*80}")
        print("SUMMARY STATISTICS")
        print(f"{'-'*80}\n")

        # Overall stats
        total_size = sum(r['size_mb'] for r in self.results)
        total_time = sum(r['avg_time_s'] for r in self.results)
        avg_throughput = statistics.mean(r['throughput_mbs'] for r in self.results)
        avg_memory = statistics.mean(r['avg_memory_mb'] for r in self.results)

        print(f"Total documents: {len(self.results)}")
        print(f"Total size: {total_size:.1f}MB")
        print(f"Total time: {total_time:.2f}s")
        print(f"Average throughput: {avg_throughput:.1f}MB/s")
        print(f"Average memory usage: {avg_memory:.1f}MB")

        # By size category
        print(f"\nPerformance by document size:")
        categories = [
            ('Small (<5MB)', lambda r: r['size_mb'] < 5),
            ('Medium (5-20MB)', lambda r: 5 <= r['size_mb'] < 20),
            ('Large (20-50MB)', lambda r: 20 <= r['size_mb'] < 50),
            ('XLarge (>50MB)', lambda r: r['size_mb'] >= 50)
        ]

        for name, predicate in categories:
            subset = [r for r in self.results if predicate(r)]
            if subset:
                avg_time = statistics.mean(r['avg_time_s'] for r in subset)
                avg_speed = statistics.mean(r['throughput_mbs'] for r in subset)
                print(f"  {name:<20} {len(subset):>3} docs, "
                      f"avg {avg_time:>6.3f}s, {avg_speed:>6.1f}MB/s")

        # Slowest files
        print(f"\nSlowest 5 documents:")
        slowest = sorted(self.results, key=lambda r: r['avg_time_s'], reverse=True)[:5]
        for r in slowest:
            print(f"  {r['file']:<35} {r['avg_time_s']:>7.3f}s ({r['size_mb']:>6.1f}MB)")

        # Fastest throughput
        print(f"\nFastest 5 documents (MB/s):")
        fastest = sorted(self.results, key=lambda r: r['throughput_mbs'], reverse=True)[:5]
        for r in fastest:
            print(f"  {r['file']:<35} {r['throughput_mbs']:>9.1f}MB/s ({r['size_mb']:>6.1f}MB)")

    def save_results(self, output_path: Path):
        """Save benchmark results to JSON file."""
        with open(output_path, 'w') as f:
            json.dump({
                'benchmark_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'corpus_dir': str(self.corpus_dir),
                'total_documents': len(self.results),
                'results': self.results
            }, f, indent=2)

        print(f"\n📊 Results saved to {output_path}")

    def compare_with_baseline(self, baseline_path: Path):
        """
        Compare current results with baseline results.

        Args:
            baseline_path: Path to baseline JSON results
        """
        if not baseline_path.exists():
            print(f"⚠️  No baseline file found at {baseline_path}")
            return

        with open(baseline_path) as f:
            baseline_data = json.load(f)

        baseline_results = {r['file']: r for r in baseline_data['results']}

        print(f"\n{'='*80}")
        print(f"COMPARISON WITH BASELINE")
        print(f"Baseline: {baseline_data['benchmark_date']}")
        print(f"{'='*80}\n")

        print(f"{'File':<35} {'Baseline':>10} {'Current':>10} {'Change':>10}")
        print(f"{'-'*35} {'-'*10} {'-'*10} {'-'*10}")

        improvements = []
        regressions = []

        for result in self.results:
            filename = result['file']
            if filename in baseline_results:
                baseline_time = baseline_results[filename]['avg_time_s']
                current_time = result['avg_time_s']
                change_pct = ((current_time - baseline_time) / baseline_time) * 100

                status = "🔴" if change_pct > 5 else "🟢" if change_pct < -5 else "⚪"

                print(f"{filename:<35} "
                      f"{baseline_time:>9.3f}s "
                      f"{current_time:>9.3f}s "
                      f"{status} {change_pct:>+7.1f}%")

                if change_pct > 5:
                    regressions.append((filename, change_pct))
                elif change_pct < -5:
                    improvements.append((filename, change_pct))

        if improvements:
            print(f"\n✅ {len(improvements)} improvements (>5% faster)")
        if regressions:
            print(f"\n❌ {len(regressions)} regressions (>5% slower)")


def main():
    """Run benchmark suite."""
    import argparse

    parser = argparse.ArgumentParser(description='Benchmark HTML parser performance')
    parser.add_argument('--corpus', type=Path, default=Path('data/html'),
                       help='Path to corpus directory')
    parser.add_argument('--pattern', default='*.html',
                       help='Glob pattern for HTML files')
    parser.add_argument('--max-files', type=int, default=None,
                       help='Maximum number of files to benchmark')
    parser.add_argument('--runs', type=int, default=5,
                       help='Number of runs per file')
    parser.add_argument('--output', type=Path, default=Path('benchmark_results.json'),
                       help='Output file for results')
    parser.add_argument('--baseline', type=Path, default=None,
                       help='Baseline results file for comparison')

    args = parser.parse_args()

    benchmark = ParserBenchmark(corpus_dir=args.corpus)
    benchmark.benchmark_corpus(pattern=args.pattern, max_files=args.max_files)
    benchmark.save_results(args.output)

    if args.baseline:
        benchmark.compare_with_baseline(args.baseline)


if __name__ == '__main__':
    main()
