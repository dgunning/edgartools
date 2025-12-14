"""
Advanced Ranking Search Examples for EdgarTools
================================================

Demonstrates the BM25-based ranking search with semantic structure awareness
and intelligent caching.

Features:
- Three ranking algorithms: BM25, Hybrid, Semantic
- Intelligent index caching for 10x+ speedup
- Structure-aware boosting for gateway content
- Agent-friendly results with full section context
"""

from edgar import Company, get_filings
from edgar.documents.search import DocumentSearch


def example_basic_ranked_search():
    """
    Example 1: Basic ranked search with BM25 algorithm.

    BM25 provides relevance-ranked results based on term frequency
    and inverse document frequency. Best for exact term matching.
    """
    print("\n" + "=" * 70)
    print("Example 1: Basic BM25 Ranked Search")
    print("=" * 70)

    # Get a 10-K filing
    company = Company("AAPL")
    filing = company.get_filings(form="10-K").latest(1)

    # Parse and create search
    document = filing.document
    searcher = DocumentSearch(document)

    # Search for revenue-related content
    results = searcher.ranked_search(
        query="revenue growth trends",
        algorithm="bm25",
        top_k=5
    )

    print(f"\nFound {len(results)} relevant results:\n")
    for i, result in enumerate(results, 1):
        print(f"{i}. Score: {result.score:.3f}")
        print(f"   Section: {result.section or 'Unknown'}")
        print(f"   Snippet: {result.snippet}\n")


def example_hybrid_search():
    """
    Example 2: Hybrid search (BM25 + semantic structure boosting).

    Hybrid combines BM25 with semantic structure awareness to boost:
    - Headings and section markers
    - Cross-references ("See Item X")
    - Gateway content (summaries, overviews)
    - Tables and XBRL data
    """
    print("\n" + "=" * 70)
    print("Example 2: Hybrid Search with Structure Boosting")
    print("=" * 70)

    filings = get_filings(form="10-K", ticker="MSFT")
    filing = filings[0]
    document = filing.document
    searcher = DocumentSearch(document)

    # Hybrid search boosts structural elements
    results = searcher.ranked_search(
        query="risk factors cybersecurity",
        algorithm="hybrid",
        top_k=5
    )

    print("\nHybrid results (BM25 + semantic boosting):\n")
    for result in results:
        print(f"Score: {result.score:.3f} | Section: {result.section}")
        print(f"  {result.snippet[:100]}...\n")


def example_semantic_search():
    """
    Example 3: Pure semantic/structure-based ranking.

    Semantic ranking prioritizes document structure without text matching:
    - Section headings
    - Document organization
    - Structural importance
    """
    print("\n" + "=" * 70)
    print("Example 3: Semantic Structure Search")
    print("=" * 70)

    company = Company("GOOGL")
    filing = company.get_filings(form="10-K").latest(1)
    document = filing.document
    searcher = DocumentSearch(document)

    # Semantic search finds structurally important content
    results = searcher.ranked_search(
        query="business overview",
        algorithm="semantic",
        top_k=5
    )

    print("\nStructurally important sections:\n")
    for result in results:
        print(f"Score: {result.score:.3f}")
        print(f"Section: {result.section}")
        print(f"Type: {result.node.type}\n")


def example_section_specific_search():
    """
    Example 4: Search within specific sections.

    Limit search to particular document sections.
    """
    print("\n" + "=" * 70)
    print("Example 4: Section-Specific Search")
    print("=" * 70)

    filings = get_filings(form="10-K", ticker="NVDA")
    filing = filings[0]
    document = filing.document
    searcher = DocumentSearch(document)

    # Search only in Risk Factors section
    results = searcher.ranked_search(
        query="supply chain semiconductor",
        algorithm="hybrid",
        in_section="Risk Factors",
        top_k=3
    )

    print("\nResults from 'Risk Factors' section:\n")
    for result in results:
        print(f"Score: {result.score:.3f}")
        print(f"{result.snippet[:150]}...\n")


def example_section_boosting():
    """
    Example 5: Boost specific sections.

    Give higher weight to matches in certain sections.
    """
    print("\n" + "=" * 70)
    print("Example 5: Section Boosting")
    print("=" * 70)

    company = Company("TSLA")
    filing = company.get_filings(form="10-K").latest(1)
    document = filing.document
    searcher = DocumentSearch(document)

    # Boost results from MD&A and Risk Factors
    results = searcher.ranked_search(
        query="production capacity manufacturing",
        algorithm="hybrid",
        boost_sections=["MD&A", "Risk Factors"],
        top_k=5
    )

    print("\nResults with section boosting:\n")
    for result in results:
        print(f"Score: {result.score:.3f} | Section: {result.section}")
        print(f"  {result.snippet[:100]}...\n")


def example_cache_performance():
    """
    Example 6: Cache performance optimization.

    Demonstrates the performance improvement from caching.
    """
    print("\n" + "=" * 70)
    print("Example 6: Cache Performance")
    print("=" * 70)

    import time

    filings = get_filings(form="10-K", ticker="AAPL")
    filing = filings[0]
    document = filing.document

    # First search (cold cache)
    searcher = DocumentSearch(document, use_cache=True)

    start = time.perf_counter()
    results1 = searcher.ranked_search("revenue", algorithm="bm25")
    cold_time = time.perf_counter() - start

    # Second search (warm cache)
    start = time.perf_counter()
    results2 = searcher.ranked_search("revenue", algorithm="bm25")
    warm_time = time.perf_counter() - start

    print("\nCache Performance:")
    print(f"  Cold cache (first search): {cold_time:.3f}s")
    print(f"  Warm cache (repeat search): {warm_time:.3f}s")
    print(f"  Speedup: {cold_time / warm_time:.1f}x faster\n")

    # Get cache statistics
    stats = searcher.get_cache_stats()
    print("Cache Statistics:")
    print(f"  Instance cache entries: {stats['instance_cache_entries']}")

    global_stats = stats.get('global_cache_stats', {})
    if global_stats:
        print(f"  Cache hits: {global_stats.get('cache_hits', 0)}")
        print(f"  Cache misses: {global_stats.get('cache_misses', 0)}")
        print(f"  Hit rate: {global_stats.get('hit_rate', 0):.1%}")


def example_agent_workflow():
    """
    Example 7: Agent-friendly workflow.

    Results include full section context for post-RAG investigation.
    """
    print("\n" + "=" * 70)
    print("Example 7: Agent-Friendly Workflow")
    print("=" * 70)

    company = Company("META")
    filing = company.get_filings(form="10-K").latest(1)
    document = filing.document
    searcher = DocumentSearch(document)

    # Search for AI-related content
    results = searcher.ranked_search(
        query="artificial intelligence machine learning",
        algorithm="hybrid",
        top_k=3
    )

    print("\nAgent workflow: Find → Investigate → Navigate\n")

    for i, result in enumerate(results, 1):
        print(f"{i}. Found: {result.section}")
        print(f"   Score: {result.score:.3f}")
        print(f"   Snippet: {result.snippet[:100]}...")

        # Agent can access full section for investigation
        if hasattr(result, '_section_obj') and result._section_obj:
            section = result._section_obj
            full_text = section.text()
            print(f"   Full section: {len(full_text)} characters available")
            print("   Can navigate: section.children for sub-sections\n")
        else:
            print()


def example_comparing_algorithms():
    """
    Example 8: Compare different ranking algorithms.

    See how BM25, Hybrid, and Semantic produce different results.
    """
    print("\n" + "=" * 70)
    print("Example 8: Comparing Ranking Algorithms")
    print("=" * 70)

    filings = get_filings(form="10-K", ticker="AMZN")
    filing = filings[0]
    document = filing.document
    searcher = DocumentSearch(document)

    query = "cloud computing revenue"

    # BM25: Pure text matching
    bm25_results = searcher.ranked_search(query, algorithm="bm25", top_k=3)

    # Hybrid: Text + structure
    hybrid_results = searcher.ranked_search(query, algorithm="hybrid", top_k=3)

    # Semantic: Pure structure
    semantic_results = searcher.ranked_search(query, algorithm="semantic", top_k=3)

    print(f"\nQuery: '{query}'\n")

    print("BM25 Results (text-focused):")
    for r in bm25_results:
        print(f"  {r.score:.3f} | {r.section}")

    print("\nHybrid Results (text + structure):")
    for r in hybrid_results:
        print(f"  {r.score:.3f} | {r.section}")

    print("\nSemantic Results (structure-focused):")
    for r in semantic_results:
        print(f"  {r.score:.3f} | {r.section}")


def example_disable_cache():
    """
    Example 9: Disable caching when needed.

    For testing or memory-constrained environments.
    """
    print("\n" + "=" * 70)
    print("Example 9: Disable Caching")
    print("=" * 70)

    company = Company("NFLX")
    filing = company.get_filings(form="10-K").latest(1)
    document = filing.document

    # Disable caching
    searcher = DocumentSearch(document, use_cache=False)

    results = searcher.ranked_search("subscriber growth", algorithm="bm25", top_k=3)

    print(f"\nSearch without caching: {len(results)} results")
    print("(Useful for testing or memory-constrained environments)")


def example_clear_cache():
    """
    Example 10: Cache management.

    Clear cache when needed to free memory.
    """
    print("\n" + "=" * 70)
    print("Example 10: Cache Management")
    print("=" * 70)

    company = Company("DIS")
    filing = company.get_filings(form="10-K").latest(1)
    document = filing.document
    searcher = DocumentSearch(document)

    # Perform searches (builds cache)
    searcher.ranked_search("streaming", algorithm="bm25")
    searcher.ranked_search("content", algorithm="bm25")

    stats_before = searcher.get_cache_stats()
    print("\nBefore clear:")
    print(f"  Instance cache entries: {stats_before['instance_cache_entries']}")

    # Clear only instance cache
    searcher.clear_cache(memory_only=True)

    stats_after = searcher.get_cache_stats()
    print("\nAfter clear (memory only):")
    print(f"  Instance cache entries: {stats_after['instance_cache_entries']}")

    # Clear all caches
    searcher.clear_cache(memory_only=False)
    print("\nCleared all caches (memory + disk)")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("EdgarTools Advanced Ranking Search Examples")
    print("=" * 70)
    print("\nThese examples demonstrate:")
    print("  - BM25 ranking for exact term matching")
    print("  - Hybrid search with structure boosting")
    print("  - Semantic structure-aware search")
    print("  - Section filtering and boosting")
    print("  - Intelligent caching for performance")
    print("  - Agent-friendly workflows")
    print("=" * 70)

    # Run examples
    try:
        example_basic_ranked_search()
        example_hybrid_search()
        example_semantic_search()
        example_section_specific_search()
        example_section_boosting()
        example_cache_performance()
        example_agent_workflow()
        example_comparing_algorithms()
        example_disable_cache()
        example_clear_cache()

        print("\n" + "=" * 70)
        print("All examples completed successfully!")
        print("=" * 70)

    except Exception as e:
        print(f"\nError running examples: {e}")
        print("Make sure you have filings downloaded and internet access.")
