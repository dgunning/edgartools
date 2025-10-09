"""
Cache utilities for performance optimization.
"""

import weakref
from collections import OrderedDict
from typing import Any, Dict, Optional, Callable, TypeVar, Generic
from functools import wraps
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta

T = TypeVar('T')


@dataclass
class CacheStats:
    """Statistics for cache performance monitoring."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_time: float = 0.0
    last_reset: datetime = field(default_factory=datetime.now)
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def avg_access_time(self) -> float:
        """Calculate average access time."""
        total = self.hits + self.misses
        return self.total_time / total if total > 0 else 0.0
    
    def reset(self):
        """Reset statistics."""
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.total_time = 0.0
        self.last_reset = datetime.now()


class LRUCache(Generic[T]):
    """
    Thread-safe LRU cache implementation.
    
    Used for caching expensive operations like style parsing
    and header detection results.
    """
    
    def __init__(self, max_size: int = 1000):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of items to cache
        """
        self.max_size = max_size
        self._cache: OrderedDict[str, T] = OrderedDict()
        self._lock = threading.RLock()
        self.stats = CacheStats()
    
    def get(self, key: str) -> Optional[T]:
        """
        Get item from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        start_time = time.time()
        
        with self._lock:
            if key in self._cache:
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                self.stats.hits += 1
                self.stats.total_time += time.time() - start_time
                return self._cache[key]
            
            self.stats.misses += 1
            self.stats.total_time += time.time() - start_time
            return None
    
    def put(self, key: str, value: T) -> None:
        """
        Put item in cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            if key in self._cache:
                # Update existing
                self._cache.move_to_end(key)
                self._cache[key] = value
            else:
                # Add new
                self._cache[key] = value
                
                # Evict oldest if over capacity
                if len(self._cache) > self.max_size:
                    self._cache.popitem(last=False)
                    self.stats.evictions += 1
    
    def clear(self) -> None:
        """Clear all cached items."""
        with self._lock:
            self._cache.clear()
    
    def size(self) -> int:
        """Get current cache size."""
        with self._lock:
            return len(self._cache)


class WeakCache:
    """
    Weak reference cache for parsed nodes.
    
    Allows garbage collection of unused nodes while
    maintaining references to actively used ones.
    """
    
    def __init__(self):
        """Initialize weak cache."""
        self._cache: Dict[str, weakref.ref] = {}
        self._lock = threading.RLock()
        self.stats = CacheStats()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get item from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached object or None if not found or collected
        """
        start_time = time.time()
        
        with self._lock:
            ref = self._cache.get(key)
            if ref is not None:
                obj = ref()
                if obj is not None:
                    self.stats.hits += 1
                    self.stats.total_time += time.time() - start_time
                    return obj
                else:
                    # Object was garbage collected
                    del self._cache[key]
            
            self.stats.misses += 1
            self.stats.total_time += time.time() - start_time
            return None
    
    def put(self, key: str, value: Any) -> None:
        """
        Put item in cache with weak reference.
        
        Args:
            key: Cache key
            value: Object to cache
        """
        with self._lock:
            self._cache[key] = weakref.ref(value)
    
    def clear(self) -> None:
        """Clear all cached references."""
        with self._lock:
            self._cache.clear()
    
    def cleanup(self) -> int:
        """
        Remove dead references.
        
        Returns:
            Number of references removed
        """
        with self._lock:
            dead_keys = [
                key for key, ref in self._cache.items()
                if ref() is None
            ]
            
            for key in dead_keys:
                del self._cache[key]
            
            return len(dead_keys)


class TimeBasedCache(Generic[T]):
    """
    Time-based expiring cache.
    
    Items expire after a specified duration.
    """
    
    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize time-based cache.
        
        Args:
            ttl_seconds: Time to live in seconds
        """
        self.ttl = timedelta(seconds=ttl_seconds)
        self._cache: Dict[str, tuple[T, datetime]] = {}
        self._lock = threading.RLock()
        self.stats = CacheStats()
    
    def get(self, key: str) -> Optional[T]:
        """
        Get item from cache if not expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or expired
        """
        start_time = time.time()
        
        with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if datetime.now() - timestamp < self.ttl:
                    self.stats.hits += 1
                    self.stats.total_time += time.time() - start_time
                    return value
                else:
                    # Expired
                    del self._cache[key]
                    self.stats.evictions += 1
            
            self.stats.misses += 1
            self.stats.total_time += time.time() - start_time
            return None
    
    def put(self, key: str, value: T) -> None:
        """
        Put item in cache with timestamp.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            self._cache[key] = (value, datetime.now())
    
    def clear(self) -> None:
        """Clear all cached items."""
        with self._lock:
            self._cache.clear()
    
    def cleanup(self) -> int:
        """
        Remove expired items.
        
        Returns:
            Number of items removed
        """
        with self._lock:
            now = datetime.now()
            expired_keys = [
                key for key, (_, timestamp) in self._cache.items()
                if now - timestamp >= self.ttl
            ]
            
            for key in expired_keys:
                del self._cache[key]
                self.stats.evictions += 1
            
            return len(expired_keys)


def cached(cache: LRUCache, key_func: Optional[Callable] = None):
    """
    Decorator for caching function results.
    
    Args:
        cache: Cache instance to use
        key_func: Function to generate cache key from arguments
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                # Default key generation
                key = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            
            # Check cache
            result = cache.get(key)
            if result is not None:
                return result
            
            # Compute and cache result
            result = func(*args, **kwargs)
            cache.put(key, result)
            
            return result
        
        return wrapper
    
    return decorator


class CacheManager:
    """
    Manages multiple caches for the parser.
    
    Provides centralized cache management and monitoring.
    """
    
    def __init__(self):
        """Initialize cache manager."""
        # Style parsing cache
        self.style_cache = LRUCache[dict](max_size=5000)
        
        # Header detection cache
        self.header_cache = LRUCache[bool](max_size=2000)
        
        # Pattern matching cache
        self.pattern_cache = LRUCache[bool](max_size=10000)
        
        # Node reference cache
        self.node_cache = WeakCache()
        
        # Compiled regex cache
        self.regex_cache = LRUCache[Any](max_size=500)
        
        # All caches for management
        self._caches = {
            'style': self.style_cache,
            'header': self.header_cache,
            'pattern': self.pattern_cache,
            'node': self.node_cache,
            'regex': self.regex_cache
        }
    
    def get_stats(self) -> Dict[str, CacheStats]:
        """Get statistics for all caches."""
        return {
            name: cache.stats 
            for name, cache in self._caches.items()
            if hasattr(cache, 'stats')
        }
    
    def reset_stats(self) -> None:
        """Reset statistics for all caches."""
        for cache in self._caches.values():
            if hasattr(cache, 'stats'):
                cache.stats.reset()
    
    def clear_all(self) -> None:
        """Clear all caches."""
        for cache in self._caches.values():
            cache.clear()
    
    def cleanup(self) -> Dict[str, int]:
        """
        Cleanup expired/dead entries in all caches.
        
        Returns:
            Number of entries cleaned up per cache
        """
        cleanup_counts = {}
        
        # Cleanup weak cache
        if hasattr(self.node_cache, 'cleanup'):
            cleanup_counts['node'] = self.node_cache.cleanup()
        
        return cleanup_counts
    
    def get_memory_usage(self) -> Dict[str, int]:
        """
        Estimate memory usage of caches.
        
        Returns:
            Approximate memory usage in bytes per cache
        """
        import sys
        
        usage = {}
        
        for name, cache in self._caches.items():
            if hasattr(cache, '_cache'):
                # Rough estimation
                size = 0
                if isinstance(cache._cache, dict):
                    for key, value in cache._cache.items():
                        size += sys.getsizeof(key)
                        if hasattr(value, '__sizeof__'):
                            size += sys.getsizeof(value)
                        else:
                            size += 1000  # Default estimate
                
                usage[name] = size
        
        return usage


# Global cache manager instance
_cache_manager = None


def get_cache_manager() -> CacheManager:
    """Get global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager