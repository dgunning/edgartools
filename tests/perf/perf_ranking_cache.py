"""
Performance benchmark for ranking search cache.

Demonstrates the performance improvement from index caching.
"""

import time
from edgar import Company, get_filings
from edgar.documents.search import DocumentSearch
from edgar.documents.ranking.cache import get_search_cache


def benchmark_search_cache():
    """Benchmark search performance with and without caching."""

    print("=" * 70)
    print("Ranking Search Cache Performance Benchmark")
    print("=" * 70)
    print()

    # Get a 10-K filing for testing
    print("Loading 10-K filing...")
    filings = get_filings(form="10-K", ticker="AAPL")
    filing = filings[0]

    print(f"Filing: {filing.company} {filing.form} ({filing.filing_date})")
    print()

    # Parse the document
    print("Parsing document...")
    start = time.perf_counter()
    document = filing.document
    parse_time = time.perf_counter() - start
    print(f"Parse time: {parse_time:.3f}s")
    print()

    # Clear cache to start fresh
    get_search_cache().clear()

    # Create searcher with caching enabled
    searcher = DocumentSearch(document, use_cache=True)

    # Test queries
    queries = [
        "revenue growth",
        "risk factors",
        "financial condition",
        "operating expenses",
        "cash flow"
    ]

    # Cold cache - first search
    print("=" * 70)
    print("Cold Cache (First Search)")
    print("=" * 70)

    cold_times = []
    for query in queries:
        start = time.perf_counter()
        results = searcher.ranked_search(query, algorithm="bm25", top_k=5)
        elapsed = time.perf_counter() - start
        cold_times.append(elapsed)
        print(f"  Query: '{query:25s}' - {elapsed:6.3f}s - {len(results)} results")

    avg_cold = sum(cold_times) / len(cold_times)
    print(f"\nAverage cold cache time: {avg_cold:.3f}s")
    print()

    # Warm cache - repeat same searches
    print("=" * 70)
    print("Warm Cache (Repeat Searches)")
    print("=" * 70)

    warm_times = []
    for query in queries:
        start = time.perf_counter()
        results = searcher.ranked_search(query, algorithm="bm25", top_k=5)
        elapsed = time.perf_counter() - start
        warm_times.append(elapsed)
        print(f"  Query: '{query:25s}' - {elapsed:6.3f}s - {len(results)} results")

    avg_warm = sum(warm_times) / len(warm_times)
    print(f"\nAverage warm cache time: {avg_warm:.3f}s")
    print()

    # Calculate speedup
    speedup = avg_cold / avg_warm if avg_warm > 0 else 0
    print("=" * 70)
    print("Performance Summary")
    print("=" * 70)
    print(f"Cold cache avg:  {avg_cold:.3f}s")
    print(f"Warm cache avg:  {avg_warm:.3f}s")
    print(f"Speedup:         {speedup:.1f}x faster")
    print(f"Time saved:      {(avg_cold - avg_warm) * 1000:.1f}ms per search")
    print()

    # Cache statistics
    stats = searcher.get_cache_stats()
    print("=" * 70)
    print("Cache Statistics")
    print("=" * 70)
    print(f"Instance cache entries: {stats['instance_cache_entries']}")

    global_stats = stats.get('global_cache_stats', {})
    if global_stats:
        print(f"Memory cache entries:   {global_stats.get('memory_entries', 0)}")
        print(f"Disk cache entries:     {global_stats.get('disk_entries', 0)}")
        print(f"Cache hits:             {global_stats.get('cache_hits', 0)}")
        print(f"Cache misses:           {global_stats.get('cache_misses', 0)}")
        print(f"Hit rate:               {global_stats.get('hit_rate', 0):.1%}")
        print(f"Memory size:            {global_stats.get('memory_size_mb', 0):.2f} MB")

    print()
    print("=" * 70)

    return {
        'cold_avg': avg_cold,
        'warm_avg': avg_warm,
        'speedup': speedup,
        'stats': stats
    }


def benchmark_cache_persistence():
    """Benchmark cache persistence across sessions."""

    print("\n")
    print("=" * 70)
    print("Cache Persistence Benchmark")
    print("=" * 70)
    print()

    # Get a filing
    filings = get_filings(form="10-K", ticker="MSFT")
    filing = filings[0]
    document = filing.document

    # First session - build cache
    print("Session 1: Building cache...")
    searcher1 = DocumentSearch(document, use_cache=True)

    start = time.perf_counter()
    results1 = searcher1.ranked_search("revenue", algorithm="bm25", top_k=5)
    time1 = time.perf_counter() - start
    print(f"  First search: {time1:.3f}s - {len(results1)} results")

    # Second session - load from disk cache
    print("\nSession 2: Loading from disk cache...")
    searcher2 = DocumentSearch(document, use_cache=True)

    start = time.perf_counter()
    results2 = searcher2.ranked_search("revenue", algorithm="bm25", top_k=5)
    time2 = time.perf_counter() - start
    print(f"  Cached search: {time2:.3f}s - {len(results2)} results")

    speedup = time1 / time2 if time2 > 0 else 0
    print(f"\nDisk cache speedup: {speedup:.1f}x faster")
    print()


if __name__ == "__main__":
    # Run main benchmark
    results = benchmark_search_cache()

    # Run persistence benchmark
    benchmark_cache_persistence()

    print("\nBenchmark complete!")
