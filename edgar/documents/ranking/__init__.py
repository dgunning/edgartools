"""
Advanced ranking functionality for edgar.documents.

This package provides BM25-based ranking with semantic structure awareness.
"""

from edgar.documents.ranking.ranking import (
    RankingAlgorithm,
    RankingEngine,
    BM25Engine,
    HybridEngine,
    SemanticEngine,
    RankedResult,
)

__all__ = [
    'RankingAlgorithm',
    'RankingEngine',
    'BM25Engine',
    'HybridEngine',
    'SemanticEngine',
    'RankedResult',
]
