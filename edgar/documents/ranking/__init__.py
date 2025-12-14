"""
Advanced ranking functionality for edgar.documents.

This package provides BM25-based ranking with semantic structure awareness
and intelligent index caching for performance optimization.
"""

from edgar.documents.ranking.cache import (
    CacheEntry,
    SearchIndexCache,
    get_search_cache,
    set_search_cache,
)
from edgar.documents.ranking.ranking import (
    BM25Engine,
    HybridEngine,
    RankedResult,
    RankingAlgorithm,
    RankingEngine,
    SemanticEngine,
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
