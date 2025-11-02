"""
Tests for BM25-based ranking search with semantic structure awareness.

Tests the new ranking engines: BM25Engine, HybridEngine, SemanticEngine.
"""

import pytest
from edgar.documents.ranking.ranking import (
    BM25Engine,
    HybridEngine,
    SemanticEngine,
    RankingAlgorithm,
    RankedResult,
)
from edgar.documents.ranking.preprocessing import (
    preprocess_text,
    tokenize,
    extract_query_terms,
    normalize_financial_term,
    get_ngrams,
)
from edgar.documents.ranking.semantic import (
    compute_semantic_scores,
    get_section_importance_names,
)
from edgar.documents.nodes import Node, HeadingNode, TextNode
from edgar.documents.types import NodeType, SemanticType


# Fixtures


@pytest.fixture
def sample_nodes():
    """Create sample nodes for testing."""
    nodes = []

    # Heading node (high importance)
    heading = HeadingNode(
        id="h1",
        level=1,
        content="Item 1A - Risk Factors",
        metadata={},
        semantic_type=SemanticType.ITEM_HEADER
    )
    nodes.append(heading)

    # Text nodes with financial content
    text1 = TextNode(
        id="t1",
        content="Revenue increased by 25% to $5 billion in fiscal 2023.",
        metadata={}
    )
    nodes.append(text1)

    text2 = TextNode(
        id="t2",
        content="The company faces significant risks related to market volatility and competition.",
        metadata={}
    )
    nodes.append(text2)

    text3 = TextNode(
        id="t3",
        content="See Item 7 for detailed discussion of financial performance and results.",
        metadata={}
    )
    nodes.append(text3)

    text4 = TextNode(
        id="t4",
        content="Revenue growth exceeded expectations with strong demand in all markets.",
        metadata={}
    )
    nodes.append(text4)

    return nodes


# Preprocessing Tests


def test_preprocess_text_lowercase():
    """Test text preprocessing with lowercase conversion."""
    text = "Revenue Growth In 2023"
    result = preprocess_text(text, lowercase=True)
    assert result == "revenue growth in 2023"


def test_preprocess_text_whitespace_normalization():
    """Test whitespace normalization."""
    text = "Multiple   spaces\t\ttabs\n\nnewlines"
    result = preprocess_text(text)
    assert result == "multiple spaces tabs newlines"


def test_tokenize_basic():
    """Test basic tokenization."""
    text = "Revenue increased significantly over the year"
    tokens = tokenize(text)
    assert "revenue" in tokens
    assert "increased" in tokens
    assert "significantly" in tokens
    assert "over" in tokens
    assert "the" in tokens
    assert "year" in tokens


def test_tokenize_with_stopwords():
    """Test tokenization with stopword removal."""
    text = "The company is growing revenue in the market"
    tokens = tokenize(text, remove_stopwords=True)
    assert "company" in tokens
    assert "growing" in tokens
    assert "revenue" in tokens
    assert "the" not in tokens  # Stopword removed
    assert "is" not in tokens   # Stopword removed


def test_extract_query_terms():
    """Test extraction of important query terms."""
    query = "revenue $5B Item 1A 15% growth"
    terms = extract_query_terms(query)
    assert "$5B" in terms or "$5b" in terms.lower()
    assert "15%" in terms
    assert any("item" in t.lower() for t in terms)


def test_normalize_financial_term():
    """Test financial term normalization."""
    assert normalize_financial_term("$5 billion") == "$5b"
    assert normalize_financial_term("5,000,000") == "5000000"
    assert normalize_financial_term("Item 1A") == "item1a"


def test_get_ngrams():
    """Test n-gram generation."""
    tokens = ["revenue", "growth", "exceeded", "expectations"]
    bigrams = get_ngrams(tokens, n=2)
    assert "revenue growth" in bigrams
    assert "growth exceeded" in bigrams
    assert "exceeded expectations" in bigrams


# BM25Engine Tests


def test_bm25_engine_initialization():
    """Test BM25Engine initialization."""
    engine = BM25Engine(k1=1.5, b=0.75)
    assert engine.k1 == 1.5
    assert engine.b == 0.75
    assert engine.get_algorithm_name() == "BM25"


def test_bm25_engine_rank_basic(sample_nodes):
    """Test basic BM25 ranking."""
    engine = BM25Engine()
    results = engine.rank("revenue growth", sample_nodes)

    assert len(results) > 0
    # Results should be sorted by score
    for i in range(len(results) - 1):
        assert results[i].score >= results[i+1].score

    # Check result structure
    assert all(isinstance(r, RankedResult) for r in results)
    assert all(r.rank > 0 for r in results)
    assert all(r.bm25_score is not None for r in results)


def test_bm25_engine_empty_query(sample_nodes):
    """Test BM25 with empty query."""
    engine = BM25Engine()
    results = engine.rank("", sample_nodes)
    assert len(results) == 0


def test_bm25_engine_empty_nodes():
    """Test BM25 with no nodes."""
    engine = BM25Engine()
    results = engine.rank("test query", [])
    assert len(results) == 0


def test_bm25_engine_relevance_ranking(sample_nodes):
    """Test BM25 ranks by relevance correctly."""
    engine = BM25Engine()
    results = engine.rank("revenue", sample_nodes)

    # Find nodes with "revenue" in text
    revenue_texts = [r.text for r in results if "revenue" in r.text.lower()]
    assert len(revenue_texts) > 0

    # Most relevant should be ranked higher
    top_result = results[0]
    assert "revenue" in top_result.text.lower()


# HybridEngine Tests


def test_hybrid_engine_initialization():
    """Test HybridEngine initialization."""
    engine = HybridEngine(bm25_weight=0.8, semantic_weight=0.2)
    assert engine.bm25_weight == 0.8
    assert engine.semantic_weight == 0.2
    assert engine.get_algorithm_name() == "Hybrid"


def test_hybrid_engine_weights_validation():
    """Test weight validation."""
    with pytest.raises(ValueError):
        HybridEngine(bm25_weight=0.5, semantic_weight=0.3)  # Sum != 1.0


def test_hybrid_engine_rank_basic(sample_nodes):
    """Test hybrid ranking."""
    engine = HybridEngine()
    results = engine.rank("revenue growth", sample_nodes)

    assert len(results) > 0
    assert all(isinstance(r, RankedResult) for r in results)

    # Both BM25 and semantic scores should be present
    assert all(r.bm25_score is not None for r in results)
    assert all(r.semantic_score is not None for r in results)


def test_hybrid_engine_boosts_headings(sample_nodes):
    """Test that hybrid engine boosts heading nodes."""
    engine = HybridEngine()
    results = engine.rank("risk", sample_nodes)

    # Find heading result
    heading_results = [r for r in results if r.node.type == NodeType.HEADING]

    if heading_results:
        # Heading should have semantic boost
        heading = heading_results[0]
        assert heading.semantic_score > 0


def test_hybrid_engine_section_boosting(sample_nodes):
    """Test section-specific boosting."""
    engine = HybridEngine(boost_sections=["Risk Factors"])
    results = engine.rank("risk", sample_nodes)

    assert len(results) > 0
    # Results with section boost should score higher


# SemanticEngine Tests


def test_semantic_engine_initialization():
    """Test SemanticEngine initialization."""
    engine = SemanticEngine()
    assert engine.get_algorithm_name() == "Semantic"


def test_semantic_engine_rank(sample_nodes):
    """Test semantic ranking."""
    engine = SemanticEngine()
    results = engine.rank("test query", sample_nodes)

    assert len(results) > 0
    assert all(r.semantic_score is not None for r in results)


def test_semantic_engine_prioritizes_structure(sample_nodes):
    """Test that semantic engine prioritizes structural elements."""
    engine = SemanticEngine()
    results = engine.rank("risk", sample_nodes)

    # Heading should be ranked high
    top_results = results[:3]
    heading_in_top = any(r.node.type == NodeType.HEADING for r in top_results)
    assert heading_in_top


# Semantic Scoring Tests


def test_compute_semantic_scores_basic(sample_nodes):
    """Test basic semantic score computation."""
    scores = compute_semantic_scores(sample_nodes, query="revenue")

    assert len(scores) == len(sample_nodes)
    assert all(0 <= score <= 1.0 for score in scores.values())


def test_compute_semantic_scores_heading_boost(sample_nodes):
    """Test that headings get semantic boost."""
    scores = compute_semantic_scores(sample_nodes, query="risk")

    # Find heading node score
    heading_node = sample_nodes[0]  # First node is heading
    heading_score = scores[id(heading_node)]

    # Find text node scores
    text_scores = [scores[id(n)] for n in sample_nodes[1:]]

    # Heading should score higher than average text
    avg_text_score = sum(text_scores) / len(text_scores) if text_scores else 0
    assert heading_score > avg_text_score


def test_compute_semantic_scores_cross_reference_detection(sample_nodes):
    """Test cross-reference detection boosts scores."""
    scores = compute_semantic_scores(sample_nodes, query="financial")

    # Find node with "See Item 7"
    cross_ref_node = sample_nodes[3]  # "See Item 7..." node
    cross_ref_score = scores[id(cross_ref_node)]

    # Should have some boost for cross-reference
    assert cross_ref_score > 0


def test_get_section_importance_names():
    """Test getting important section names."""
    names = get_section_importance_names()
    assert isinstance(names, list)
    assert "risk factors" in names
    assert "md&a" in names or "management discussion" in names


# Integration Tests


def test_end_to_end_search_workflow(sample_nodes):
    """Test complete search workflow."""
    # Create engine
    engine = HybridEngine()

    # Search
    query = "revenue growth"
    results = engine.rank(query, sample_nodes)

    # Verify results
    assert len(results) > 0

    # Top result should be relevant
    top = results[0]
    assert "revenue" in top.text.lower() or "growth" in top.text.lower()

    # Scores should be normalized
    assert 0 <= top.score <= 10  # Allow some range for combined scores

    # Rankings should be sequential
    ranks = [r.rank for r in results]
    assert ranks == list(range(1, len(results) + 1))


def test_different_algorithms_produce_different_rankings(sample_nodes):
    """Test that different algorithms produce different rankings."""
    query = "revenue"

    bm25_engine = BM25Engine()
    hybrid_engine = HybridEngine()
    semantic_engine = SemanticEngine()

    bm25_results = bm25_engine.rank(query, sample_nodes)
    hybrid_results = hybrid_engine.rank(query, sample_nodes)
    semantic_results = semantic_engine.rank(query, sample_nodes)

    # At least some differences in top results
    # (may not always be different with simple test data)
    if len(bm25_results) > 0 and len(hybrid_results) > 0:
        # Scores should differ
        assert (bm25_results[0].score != hybrid_results[0].score or
                bm25_results[0].node != hybrid_results[0].node)


def test_ranked_result_snippet_generation(sample_nodes):
    """Test snippet generation in RankedResult."""
    engine = BM25Engine()
    results = engine.rank("revenue", sample_nodes)

    if results:
        result = results[0]
        snippet = result.snippet

        # Snippet should be truncated for long text
        assert len(snippet) <= 203  # 200 + "..."

        # Should contain text
        assert len(snippet) > 0


# Performance/Edge Cases


def test_bm25_with_special_characters(sample_nodes):
    """Test BM25 handles special characters in query."""
    engine = BM25Engine()

    # Query with special characters
    results = engine.rank("$5 billion (revenue)", sample_nodes)

    # Should not crash and return results
    assert isinstance(results, list)


def test_bm25_case_insensitivity(sample_nodes):
    """Test BM25 is case insensitive."""
    engine = BM25Engine()

    results_lower = engine.rank("revenue", sample_nodes)
    results_upper = engine.rank("REVENUE", sample_nodes)

    # Should find same number of results
    assert len(results_lower) == len(results_upper)

    # Top results should be same node
    if results_lower and results_upper:
        assert results_lower[0].node == results_upper[0].node


def test_multiple_searches_same_engine(sample_nodes):
    """Test that engine can be reused for multiple searches."""
    engine = BM25Engine()

    results1 = engine.rank("revenue", sample_nodes)
    results2 = engine.rank("risk", sample_nodes)
    results3 = engine.rank("revenue", sample_nodes)  # Repeat

    # All should return results
    assert len(results1) > 0
    assert len(results2) > 0
    assert len(results3) > 0

    # First and third should match
    assert len(results1) == len(results3)


# Cache Tests


def test_cache_initialization():
    """Test SearchIndexCache initialization."""
    from edgar.documents.ranking.cache import SearchIndexCache

    cache = SearchIndexCache(memory_cache_size=5, ttl_hours=12)
    assert cache.memory_cache_size == 5
    assert cache.ttl.total_seconds() == 12 * 3600


def test_cache_compute_document_hash():
    """Test document hash computation."""
    from edgar.documents.ranking.cache import SearchIndexCache

    cache = SearchIndexCache()
    hash1 = cache.compute_document_hash("doc1", "sample content")
    hash2 = cache.compute_document_hash("doc1", "sample content")
    hash3 = cache.compute_document_hash("doc2", "sample content")

    # Same inputs should produce same hash
    assert hash1 == hash2
    # Different inputs should produce different hash
    assert hash1 != hash3
    # Hash should be 16 characters
    assert len(hash1) == 16


def test_cache_put_and_get():
    """Test basic cache put and get operations."""
    from edgar.documents.ranking.cache import SearchIndexCache, CacheEntry
    from datetime import datetime

    cache = SearchIndexCache(disk_cache_enabled=False)
    cache.clear()

    # Create entry
    entry = CacheEntry(
        document_hash="test123",
        index_data={'tokenized_corpus': [['test', 'data']], 'k1': 1.5, 'b': 0.75},
        created_at=datetime.now()
    )

    # Put and get
    cache.put("test123", entry)
    retrieved = cache.get("test123")

    assert retrieved is not None
    assert retrieved.document_hash == "test123"
    assert retrieved.access_count == 1


def test_cache_miss():
    """Test cache miss scenario."""
    from edgar.documents.ranking.cache import SearchIndexCache

    cache = SearchIndexCache(disk_cache_enabled=False)
    cache.clear()

    result = cache.get("nonexistent")
    assert result is None


def test_cache_lru_eviction():
    """Test LRU eviction when cache is full."""
    from edgar.documents.ranking.cache import SearchIndexCache, CacheEntry
    from datetime import datetime

    cache = SearchIndexCache(memory_cache_size=2, disk_cache_enabled=False)
    cache.clear()

    # Fill cache
    entry1 = CacheEntry("hash1", {'data': 1}, datetime.now())
    entry2 = CacheEntry("hash2", {'data': 2}, datetime.now())
    entry3 = CacheEntry("hash3", {'data': 3}, datetime.now())

    cache.put("hash1", entry1)
    cache.put("hash2", entry2)

    # Cache should have 2 entries
    stats = cache.get_stats()
    assert stats['memory_entries'] == 2

    # Add third entry - should evict oldest
    cache.put("hash3", entry3)

    # Should still have 2 entries
    stats = cache.get_stats()
    assert stats['memory_entries'] == 2

    # First entry should be evicted
    assert cache.get("hash1") is None
    # Second and third should still be there
    assert cache.get("hash2") is not None
    assert cache.get("hash3") is not None


def test_cache_statistics():
    """Test cache statistics tracking."""
    from edgar.documents.ranking.cache import SearchIndexCache, CacheEntry
    from datetime import datetime

    cache = SearchIndexCache(disk_cache_enabled=False)
    cache.clear()

    entry = CacheEntry("test", {'data': 1}, datetime.now())
    cache.put("test", entry)

    # Hit
    cache.get("test")

    # Miss
    cache.get("nonexistent")

    stats = cache.get_stats()
    assert stats['cache_hits'] == 1
    assert stats['cache_misses'] == 1
    assert stats['hit_rate'] == 0.5


def test_bm25_index_serialization(sample_nodes):
    """Test BM25 index can be serialized and deserialized."""
    engine = BM25Engine()

    # Build index
    results = engine.rank("revenue", sample_nodes)
    assert len(results) > 0

    # Get index data
    index_data = engine.get_index_data()
    assert 'tokenized_corpus' in index_data
    assert 'k1' in index_data
    assert 'b' in index_data

    # Create new engine and load index
    new_engine = BM25Engine()
    new_engine.load_index_data(index_data, sample_nodes)

    # Should produce same results
    new_results = new_engine.rank("revenue", sample_nodes)
    assert len(new_results) == len(results)
    assert new_results[0].node == results[0].node


def test_cache_clear():
    """Test cache clearing."""
    from edgar.documents.ranking.cache import SearchIndexCache, CacheEntry
    from datetime import datetime

    cache = SearchIndexCache(disk_cache_enabled=False)

    # Add entries
    entry = CacheEntry("test", {'data': 1}, datetime.now())
    cache.put("test", entry)

    assert len(cache._memory_cache) > 0

    # Clear
    cache.clear()

    assert len(cache._memory_cache) == 0


def test_global_cache_singleton():
    """Test global cache is singleton."""
    from edgar.documents.ranking.cache import get_search_cache

    cache1 = get_search_cache()
    cache2 = get_search_cache()

    assert cache1 is cache2


def test_set_global_cache():
    """Test setting custom global cache."""
    from edgar.documents.ranking.cache import (
        SearchIndexCache,
        get_search_cache,
        set_search_cache
    )

    # Create custom cache
    custom_cache = SearchIndexCache(memory_cache_size=20)
    set_search_cache(custom_cache)

    # Get global cache
    cache = get_search_cache()
    assert cache is custom_cache
    assert cache.memory_cache_size == 20

    # Reset to default
    set_search_cache(None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
