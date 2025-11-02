"""
Ranking engines for document search.

Provides BM25-based ranking with optional semantic structure boosting.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict, Any, TYPE_CHECKING

from rank_bm25 import BM25Okapi

if TYPE_CHECKING:
    from edgar.documents.nodes import Node


class RankingAlgorithm(Enum):
    """Supported ranking algorithms."""
    BM25 = auto()           # Classic BM25 (Okapi variant)
    HYBRID = auto()         # BM25 + Semantic structure boosting
    SEMANTIC = auto()       # Pure structure-aware scoring


@dataclass
class RankedResult:
    """
    A search result with ranking score.

    Attributes:
        node: Document node containing the match
        score: Relevance score (higher is better)
        rank: Position in results (1-indexed)
        text: Matched text content
        bm25_score: Raw BM25 score (if applicable)
        semantic_score: Semantic boost score (if applicable)
        metadata: Additional result metadata
    """
    node: 'Node'
    score: float
    rank: int
    text: str
    bm25_score: Optional[float] = None
    semantic_score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def snippet(self) -> str:
        """Get text snippet (first 200 chars)."""
        if len(self.text) <= 200:
            return self.text
        return self.text[:197] + "..."


class RankingEngine(ABC):
    """Abstract base class for ranking engines."""

    @abstractmethod
    def rank(self, query: str, nodes: List['Node']) -> List[RankedResult]:
        """
        Rank nodes by relevance to query.

        Args:
            query: Search query
            nodes: Nodes to rank

        Returns:
            List of ranked results sorted by relevance (best first)
        """
        pass

    @abstractmethod
    def get_algorithm_name(self) -> str:
        """Get name of ranking algorithm."""
        pass


class BM25Engine(RankingEngine):
    """
    BM25 ranking engine using Okapi variant.

    BM25 is a probabilistic retrieval function that ranks documents based on
    query term frequency and inverse document frequency. Well-suited for
    financial documents where exact term matching is important.

    Parameters:
        k1: Term frequency saturation parameter (default: 1.5)
            Controls how quickly term frequency impact plateaus.
        b: Length normalization parameter (default: 0.75)
            0 = no normalization, 1 = full normalization.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 engine.

        Args:
            k1: Term frequency saturation (1.2-2.0 typical)
            b: Length normalization (0.75 is standard)
        """
        self.k1 = k1
        self.b = b
        self._bm25: Optional[BM25Okapi] = None
        self._corpus_nodes: Optional[List['Node']] = None
        self._tokenized_corpus: Optional[List[List[str]]] = None

    def rank(self, query: str, nodes: List['Node']) -> List[RankedResult]:
        """
        Rank nodes using BM25 algorithm.

        Args:
            query: Search query
            nodes: Nodes to rank

        Returns:
            Ranked results sorted by BM25 score
        """
        if not nodes:
            return []

        # Import preprocessing here to avoid circular dependency
        from edgar.documents.ranking.preprocessing import preprocess_text, tokenize

        # Build index if needed or if nodes changed
        if self._corpus_nodes != nodes:
            self._build_index(nodes)

        # Tokenize and preprocess query
        query_tokens = tokenize(preprocess_text(query))

        if not query_tokens:
            return []

        # Get BM25 scores
        scores = self._bm25.get_scores(query_tokens)

        # Create ranked results
        results = []
        for idx, (node, score) in enumerate(zip(nodes, scores)):
            if score > 0:  # Only include nodes with positive scores
                text = node.text() if hasattr(node, 'text') else str(node)
                results.append(RankedResult(
                    node=node,
                    score=float(score),
                    rank=0,  # Will be set after sorting
                    text=text,
                    bm25_score=float(score),
                    metadata={'algorithm': 'BM25'}
                ))

        # Sort by score (highest first) and assign ranks
        results.sort(key=lambda r: r.score, reverse=True)
        for rank, result in enumerate(results, start=1):
            result.rank = rank

        return results

    def _build_index(self, nodes: List['Node']):
        """Build BM25 index from nodes."""
        from edgar.documents.ranking.preprocessing import preprocess_text, tokenize

        # Store corpus
        self._corpus_nodes = nodes

        # Tokenize all nodes
        self._tokenized_corpus = []
        for node in nodes:
            text = node.text() if hasattr(node, 'text') else str(node)
            processed = preprocess_text(text)
            tokens = tokenize(processed)
            self._tokenized_corpus.append(tokens)

        # Build BM25 index with custom parameters
        self._bm25 = BM25Okapi(
            self._tokenized_corpus,
            k1=self.k1,
            b=self.b
        )

    def get_index_data(self) -> Dict[str, Any]:
        """
        Serialize index data for caching.

        Returns:
            Dictionary with serializable index data
        """
        return {
            'tokenized_corpus': self._tokenized_corpus,
            'k1': self.k1,
            'b': self.b,
            'algorithm': 'BM25'
        }

    def load_index_data(self, index_data: Dict[str, Any], nodes: List['Node']) -> None:
        """
        Load index from cached data.

        Args:
            index_data: Serialized index data
            nodes: Nodes corresponding to the index
        """
        self._corpus_nodes = nodes
        self._tokenized_corpus = index_data['tokenized_corpus']
        self.k1 = index_data['k1']
        self.b = index_data['b']

        # Rebuild BM25 index from tokenized corpus
        self._bm25 = BM25Okapi(
            self._tokenized_corpus,
            k1=self.k1,
            b=self.b
        )

    def get_algorithm_name(self) -> str:
        """Get algorithm name."""
        return "BM25"


class HybridEngine(RankingEngine):
    """
    Hybrid ranking engine: BM25 + Semantic structure boosting.

    Combines classic BM25 text matching with semantic structure awareness:
    - BM25 provides strong exact-match ranking for financial terms
    - Semantic scoring boosts results based on document structure:
      * Headings and section markers
      * Cross-references ("See Item X")
      * Gateway content (summaries, overviews)
      * Table and XBRL importance

    This approach is agent-friendly: it surfaces starting points for
    investigation rather than fragmented chunks.

    Parameters:
        bm25_weight: Weight for BM25 score (default: 0.8)
        semantic_weight: Weight for semantic score (default: 0.2)
        k1: BM25 term frequency saturation
        b: BM25 length normalization
    """

    def __init__(self,
                 bm25_weight: float = 0.8,
                 semantic_weight: float = 0.2,
                 k1: float = 1.5,
                 b: float = 0.75,
                 boost_sections: Optional[List[str]] = None):
        """
        Initialize hybrid engine.

        Args:
            bm25_weight: Weight for BM25 component (0-1)
            semantic_weight: Weight for semantic component (0-1)
            k1: BM25 k1 parameter
            b: BM25 b parameter
            boost_sections: Section names to boost (e.g., ["Risk Factors"])
        """
        self.bm25_engine = BM25Engine(k1=k1, b=b)
        self.bm25_weight = bm25_weight
        self.semantic_weight = semantic_weight
        self.boost_sections = boost_sections or []

        # Validate weights
        total_weight = bm25_weight + semantic_weight
        if not (0.99 <= total_weight <= 1.01):  # Allow small floating point error
            raise ValueError(f"Weights must sum to 1.0, got {total_weight}")

    def rank(self, query: str, nodes: List['Node']) -> List[RankedResult]:
        """
        Rank nodes using hybrid approach.

        Args:
            query: Search query
            nodes: Nodes to rank

        Returns:
            Ranked results with combined BM25 + semantic scores
        """
        if not nodes:
            return []

        # Get BM25 results
        bm25_results = self.bm25_engine.rank(query, nodes)

        if not bm25_results:
            return []

        # Import semantic scoring
        from edgar.documents.ranking.semantic import compute_semantic_scores

        # Get semantic scores for all nodes
        semantic_scores_dict = compute_semantic_scores(
            nodes=nodes,
            query=query,
            boost_sections=self.boost_sections
        )

        # Normalize BM25 scores to 0-1 range
        max_bm25 = max(r.bm25_score for r in bm25_results)
        if max_bm25 > 0:
            for result in bm25_results:
                result.bm25_score = result.bm25_score / max_bm25

        # Combine scores
        for result in bm25_results:
            semantic_score = semantic_scores_dict.get(id(result.node), 0.0)
            result.semantic_score = semantic_score

            # Weighted combination
            result.score = (
                self.bm25_weight * result.bm25_score +
                self.semantic_weight * semantic_score
            )

            result.metadata['algorithm'] = 'Hybrid'
            result.metadata['bm25_weight'] = self.bm25_weight
            result.metadata['semantic_weight'] = self.semantic_weight

        # Re-sort by combined score
        bm25_results.sort(key=lambda r: r.score, reverse=True)

        # Update ranks
        for rank, result in enumerate(bm25_results, start=1):
            result.rank = rank

        return bm25_results

    def get_algorithm_name(self) -> str:
        """Get algorithm name."""
        return "Hybrid"


class SemanticEngine(RankingEngine):
    """
    Pure semantic/structure-based ranking (no text matching).

    Ranks nodes purely by structural importance:
    - Section headings
    - Cross-references
    - Gateway content
    - Document structure position

    Useful for understanding document organization without specific queries.
    """

    def __init__(self, boost_sections: Optional[List[str]] = None):
        """
        Initialize semantic engine.

        Args:
            boost_sections: Section names to boost
        """
        self.boost_sections = boost_sections or []

    def rank(self, query: str, nodes: List['Node']) -> List[RankedResult]:
        """
        Rank nodes by semantic importance.

        Args:
            query: Search query (used for context)
            nodes: Nodes to rank

        Returns:
            Ranked results by structural importance
        """
        if not nodes:
            return []

        from edgar.documents.ranking.semantic import compute_semantic_scores

        # Get semantic scores
        semantic_scores = compute_semantic_scores(
            nodes=nodes,
            query=query,
            boost_sections=self.boost_sections
        )

        # Create results
        results = []
        for node in nodes:
            score = semantic_scores.get(id(node), 0.0)
            if score > 0:
                text = node.text() if hasattr(node, 'text') else str(node)
                results.append(RankedResult(
                    node=node,
                    score=score,
                    rank=0,
                    text=text,
                    semantic_score=score,
                    metadata={'algorithm': 'Semantic'}
                ))

        # Sort and rank
        results.sort(key=lambda r: r.score, reverse=True)
        for rank, result in enumerate(results, start=1):
            result.rank = rank

        return results

    def get_algorithm_name(self) -> str:
        """Get algorithm name."""
        return "Semantic"
