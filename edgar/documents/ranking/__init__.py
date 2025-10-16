"""
Advanced ranking functionality for edgar.documents.

This package provides BM25-based ranking with semantic structure awareness
and intelligent index caching for performance optimization.
"""

from edgar.documents.ranking.ranking import (
    RankingAlgorithm,
    RankingEngine,
    BM25Engine,
    HybridEngine,
    SemanticEngine,
    RankedResult,
)
from edgar.documents.ranking.cache import (
    SearchIndexCache,
    CacheEntry,
    get_search_cache,
    set_search_cache,
)

__all__ = [
    'RankingAlgorithm',
    'RankingEngine',
    'BM25Engine',
    'HybridEngine',
    'SemanticEngine',
    'RankedResult',
    'SearchIndexCache',
    'CacheEntry',
    'get_search_cache',
    'set_search_cache',
]
