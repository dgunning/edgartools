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

__all__ = [
    'LRUCache',
    'WeakCache', 
    'TimeBasedCache',
    'CacheManager',
    'get_cache_manager',
    'cached',
    'CacheStats',
    'StreamingParser',
    'ChunkedStreamingParser'
]