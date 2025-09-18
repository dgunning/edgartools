"""
Utility modules for HTML parsing.
"""

from edgar.documents.utils.cache import CacheManager, CacheStats, LRUCache, TimeBasedCache, WeakCache, cached, get_cache_manager
from edgar.documents.utils.streaming import ChunkedStreamingParser, StreamingParser

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
