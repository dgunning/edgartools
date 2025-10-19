#!/usr/bin/env python3
"""
Analyze pytest test timing reports to identify optimization opportunities.

Usage:
    python analyze_test_timings.py test_timings.txt

This script parses pytest --durations output and provides:
- Top slowest tests
- Category breakdown (XBRL, entity, documents, etc.)
- Pattern analysis (network calls, fixtures, etc.)
- Optimization recommendations
"""

import re
import sys
from collections import defaultdict, Counter
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class TestTiming:
    """Represents timing data for a single test."""
    duration: float
    phase: str  # setup, call, teardown
    file_path: str
    test_name: str
    full_name: str

    @property
    def module(self) -> str:
        """Extract module name from file path."""
        return Path(self.file_path).stem

    @property
    def category(self) -> str:
        """Categorize test by domain."""
        path = self.file_path.lower()

        # Category mapping
        if '/xbrl' in path or 'xbrl' in path or 'statement' in path:
            return 'XBRL/Statements'
        elif '/entity' in path or 'entity' in path or 'company' in path:
            return 'Entity/Company'
        elif '/document' in path or 'document' in path or 'html' in path:
            return 'Documents/HTML'
        elif '/fund' in path:
            return 'Funds'
        elif '/ownership' in path or 'form4' in path:
            return 'Ownership'
        elif 'filing' in path:
            return 'Filings'
        elif '/issues/regression' in path:
            return 'Regression'
        elif '/issues/reproductions' in path:
            return 'Reproductions'
        elif '/batch' in path:
            return 'Batch'
        elif '/perf' in path:
            return 'Performance'
        else:
            return 'Other'

    @property
    def likely_slow_reason(self) -> str:
        """Guess why this test might be slow."""
        name = self.test_name.lower()
        path = self.file_path.lower()

        reasons = []
        if 'company' in name or 'Company(' in self.full_name:
            reasons.append('Company instantiation')
        if 'get_filings' in name or 'filings' in name:
            reasons.append('Filing retrieval')
        if 'xbrl' in name or 'statement' in name:
            reasons.append('XBRL parsing')
        if 'document' in name or 'parse' in name:
            reasons.append('Document parsing')
        if 'rendering' in name or 'render' in name:
            reasons.append('Rendering')
        if 'batch' in path:
            reasons.append('Batch processing')
        if self.duration > 5.0:
            reasons.append('VERY SLOW (>5s)')

        return ', '.join(reasons) if reasons else 'Unknown'


def parse_pytest_durations(file_path: str) -> List[TestTiming]:
    """
    Parse pytest --durations output.

    Expected format:
        0.50s call     tests/test_something.py::TestClass::test_method
        0.30s setup    tests/test_something.py::test_function
    """
    timings = []

    # Pattern: duration phase file::test
    pattern = re.compile(r'(\d+\.\d+)s\s+(setup|call|teardown)\s+(.+?)::(.+?)(?:\s|$)')

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            match = pattern.search(line)
            if match:
                duration = float(match.group(1))
                phase = match.group(2)
                file_path_str = match.group(3)
                test_name = match.group(4)
                full_name = f"{file_path_str}::{test_name}"

                timings.append(TestTiming(
                    duration=duration,
                    phase=phase,
                    file_path=file_path_str,
                    test_name=test_name,
                    full_name=full_name
                ))

    return timings


def aggregate_by_test(timings: List[TestTiming]) -> Dict[str, float]:
    """Aggregate timings by test (sum setup + call + teardown)."""
    test_totals = defaultdict(float)

    for timing in timings:
        test_totals[timing.full_name] += timing.duration

    return dict(test_totals)


def analyze_timings(timings: List[TestTiming]) -> Dict:
    """Perform comprehensive analysis of test timings."""

    if not timings:
        return {'error': 'No timing data found'}

    # Aggregate by test
    test_totals = aggregate_by_test(timings)

    # Sort by duration
    sorted_tests = sorted(test_totals.items(), key=lambda x: x[1], reverse=True)

    # Create timing objects for sorted tests
    test_timing_map = {}
    for timing in timings:
        if timing.full_name not in test_timing_map:
            test_timing_map[timing.full_name] = timing

    # Category breakdown
    category_totals = defaultdict(float)
    category_counts = defaultdict(int)

    for test_name, duration in test_totals.items():
        if test_name in test_timing_map:
            timing = test_timing_map[test_name]
            category = timing.category
            category_totals[category] += duration
            category_counts[category] += 1

    # Phase breakdown
    phase_totals = defaultdict(float)
    for timing in timings:
        phase_totals[timing.phase] += timing.duration

    # Slow reason analysis
    slow_reasons = Counter()
    for test_name, duration in sorted_tests[:50]:  # Top 50
        if test_name in test_timing_map:
            timing = test_timing_map[test_name]
            reason = timing.likely_slow_reason
            if reason != 'Unknown':
                slow_reasons[reason] += 1

    return {
        'total_tests': len(test_totals),
        'total_duration': sum(test_totals.values()),
        'sorted_tests': sorted_tests,
        'test_timing_map': test_timing_map,
        'category_totals': dict(category_totals),
        'category_counts': dict(category_counts),
        'phase_totals': dict(phase_totals),
        'slow_reasons': slow_reasons
    }


def print_report(analysis: Dict):
    """Print comprehensive analysis report."""

    if 'error' in analysis:
        print(f"❌ {analysis['error']}")
        return

    print("=" * 80)
    print("🔍 PYTEST TEST TIMING ANALYSIS")
    print("=" * 80)
    print()

    # Overall stats
    print("📊 OVERALL STATISTICS")
    print("-" * 80)
    print(f"Total tests analyzed:     {analysis['total_tests']:,}")
    print(f"Total test duration:      {analysis['total_duration']:.2f}s ({analysis['total_duration']/60:.1f} minutes)")
    print(f"Average test duration:    {analysis['total_duration']/analysis['total_tests']:.3f}s")
    print()

    # Phase breakdown
    print("⏱️  PHASE BREAKDOWN")
    print("-" * 80)
    phase_totals = analysis['phase_totals']
    total_phase = sum(phase_totals.values())
    for phase in ['setup', 'call', 'teardown']:
        duration = phase_totals.get(phase, 0)
        pct = (duration / total_phase * 100) if total_phase > 0 else 0
        print(f"{phase.capitalize():12} {duration:8.2f}s  ({pct:5.1f}%)")
    print()

    # Category breakdown
    print("📦 CATEGORY BREAKDOWN")
    print("-" * 80)
    print(f"{'Category':<25} {'Tests':>8} {'Duration':>12} {'Avg':>10} {'%':>6}")
    print("-" * 80)

    sorted_categories = sorted(
        analysis['category_totals'].items(),
        key=lambda x: x[1],
        reverse=True
    )

    for category, duration in sorted_categories:
        count = analysis['category_counts'][category]
        avg = duration / count if count > 0 else 0
        pct = (duration / analysis['total_duration'] * 100) if analysis['total_duration'] > 0 else 0
        print(f"{category:<25} {count:>8} {duration:>10.2f}s {avg:>9.3f}s {pct:>5.1f}%")
    print()

    # Top 30 slowest tests
    print("🐌 TOP 30 SLOWEST TESTS")
    print("-" * 80)
    print(f"{'Duration':>8} {'Category':<20} {'Test':<50}")
    print("-" * 80)

    for test_name, duration in analysis['sorted_tests'][:30]:
        timing = analysis['test_timing_map'].get(test_name)
        if timing:
            category = timing.category
            # Truncate test name if too long
            short_name = test_name
            if len(short_name) > 50:
                short_name = short_name[:47] + "..."
            print(f"{duration:>7.2f}s {category:<20} {short_name}")
    print()

    # Slow reason analysis
    if analysis['slow_reasons']:
        print("🔎 SLOW TEST PATTERNS (Top 50 tests)")
        print("-" * 80)
        for reason, count in analysis['slow_reasons'].most_common(10):
            print(f"{count:>3}x  {reason}")
        print()

    # Optimization recommendations
    print("💡 OPTIMIZATION RECOMMENDATIONS")
    print("-" * 80)

    recommendations = []

    # Check for tests over 5 seconds
    very_slow = [t for t, d in analysis['sorted_tests'] if d > 5.0]
    if very_slow:
        recommendations.append(
            f"🎯 {len(very_slow)} tests take >5s - consider mocking or fixtures:\n"
            f"   Run: pytest --durations=0 | grep -E '^[0-9]+\.[0-9]+s.*' | awk '{{ if ($1+0 > 5) print }}'"
        )

    # Check for tests over 2 seconds
    slow = [t for t, d in analysis['sorted_tests'] if 2.0 < d <= 5.0]
    if slow:
        recommendations.append(
            f"⚠️  {len(slow)} tests take 2-5s - review for optimization opportunities"
        )

    # Check setup time
    if analysis['phase_totals'].get('setup', 0) > analysis['total_duration'] * 0.3:
        recommendations.append(
            "🔧 Setup time is >30% of total - consider session/module-scoped fixtures"
        )

    # Category-specific recommendations
    xbrl_time = analysis['category_totals'].get('XBRL/Statements', 0)
    if xbrl_time > analysis['total_duration'] * 0.3:
        recommendations.append(
            f"📊 XBRL tests take {xbrl_time:.1f}s ({xbrl_time/analysis['total_duration']*100:.1f}%) - "
            "consider caching parsed XBRL fixtures"
        )

    entity_time = analysis['category_totals'].get('Entity/Company', 0)
    if entity_time > analysis['total_duration'] * 0.2:
        recommendations.append(
            f"🏢 Entity/Company tests take {entity_time:.1f}s - "
            "maximize use of session fixtures like aapl_company, tsla_company"
        )

    doc_time = analysis['category_totals'].get('Documents/HTML', 0)
    if doc_time > analysis['total_duration'] * 0.2:
        recommendations.append(
            f"📄 Document tests take {doc_time:.1f}s - "
            "consider pre-parsed document fixtures"
        )

    # Print recommendations
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            print(f"\n{i}. {rec}")
    else:
        print("✅ No major optimization opportunities detected!")

    print()
    print("=" * 80)
    print("📈 NEXT STEPS")
    print("=" * 80)
    print("""
1. Review top 30 slowest tests - can any be mocked or use fixtures?
2. Check if slow tests are properly marked with @pytest.mark.slow
3. Consider adding @pytest.mark.network for tests with API calls
4. Review fixture scopes - use session/module where possible
5. Run parallel tests: hatch run pytest -n auto --dist=loadgroup
6. Profile specific slow tests: pytest --profile test_name.py

Commands to try:
  # Show tests >5s
  grep -E '^[0-9]+\.[0-9]+s' test_timings.txt | awk '{ if ($1+0 > 5) print }'

  # Run only fast tests
  hatch run test-fast

  # Run with parallelization (if pytest-xdist installed)
  hatch run pytest -n auto
    """)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python analyze_test_timings.py test_timings.txt")
        sys.exit(1)

    timing_file = sys.argv[1]

    if not Path(timing_file).exists():
        print(f"❌ File not found: {timing_file}")
        sys.exit(1)

    print(f"📖 Reading timing data from: {timing_file}")
    print()

    timings = parse_pytest_durations(timing_file)

    if not timings:
        print("❌ No timing data found in file. Make sure you ran:")
        print("   hatch run pytest --durations=0 --tb=no > test_timings.txt")
        sys.exit(1)

    print(f"✅ Parsed {len(timings)} timing entries")
    print()

    analysis = analyze_timings(timings)
    print_report(analysis)


if __name__ == '__main__':
    main()