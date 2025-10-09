"""
Utility modules for HTML parsing.
"""

from edgar.documents.utils.cache import (
    LRUCache,
    WeakCache,
    TimeBasedCache,
    CacheManager,
    get_cache_manager,
    cached,
    CacheStats
)
from edgar.documents.utils.streaming import (
    StreamingParser,
    ChunkedStreamingParser
)
from edgar.documents.utils.table_matrix import (
    TableMatrix,
    ColumnAnalyzer,
    MatrixCell
)
from edgar.documents.utils.currency_merger import (
    CurrencyColumnMerger
)

__all__ = [
    'LRUCache',
    'WeakCache', 
    'TimeBasedCache',
    'CacheManager',
    'get_cache_manager',
    'cached',
    'CacheStats',
    'StreamingParser',
    'ChunkedStreamingParser',
    'TableMatrix',
    'ColumnAnalyzer',
    'MatrixCell',
    'CurrencyColumnMerger'
]