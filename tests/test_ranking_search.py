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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
