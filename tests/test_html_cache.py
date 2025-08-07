"""
Tests for cache utilities.
"""

import pytest
import time
import threading
from edgar.documents.utils import (
    LRUCache, WeakCache, TimeBasedCache, 
    CacheManager, get_cache_manager, cached
)


class TestLRUCache:
    """Test LRU cache implementation."""
    
    def test_basic_operations(self):
        """Test basic cache operations."""
        cache = LRUCache[str](max_size=3)
        
        # Test put and get
        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"
        assert cache.get("nonexistent") is None
        
        # Test cache stats
        assert cache.stats.hits == 1
        assert cache.stats.misses == 1
    
    def test_lru_eviction(self):
        """Test LRU eviction policy."""
        cache = LRUCache[int](max_size=3)
        
        # Fill cache
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        
        # Access 'a' to make it recently used
        cache.get("a")
        
        # Add new item, should evict 'b'
        cache.put("d", 4)
        
        assert cache.get("a") == 1
        assert cache.get("b") is None  # Evicted
        assert cache.get("c") == 3
        assert cache.get("d") == 4
    
    def test_thread_safety(self):
        """Test thread safety of cache."""
        cache = LRUCache[int](max_size=100)
        errors = []
        
        def worker(start):
            try:
                for i in range(start, start + 20):
                    cache.put(f"key{i}", i)
                    assert cache.get(f"key{i}") == i
            except Exception as e:
                errors.append(e)
        
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i * 20,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert cache.size() <= 100


class TestWeakCache:
    """Test weak reference cache."""
    
    def test_weak_references(self):
        """Test weak reference behavior."""
        cache = WeakCache()
        
        # Create object and cache it
        class TestObj:
            def __init__(self, value):
                self.value = value
        
        obj = TestObj(42)
        cache.put("key1", obj)
        
        # Object should be retrievable
        cached_obj = cache.get("key1")
        assert cached_obj is not None
        assert cached_obj.value == 42
        
        # Delete reference
        del obj
        
        # Force garbage collection
        import gc
        gc.collect()
        
        # Object should be gone
        assert cache.get("key1") is None
    
    def test_cleanup(self):
        """Test cleanup of dead references."""
        cache = WeakCache()
        
        # Add multiple objects
        objs = []
        for i in range(5):
            obj = object()
            objs.append(obj)
            cache.put(f"key{i}", obj)
        
        # Delete some references
        del objs[1]
        del objs[3]
        
        import gc
        gc.collect()
        
        # Cleanup should remove dead references
        removed = cache.cleanup()
        assert removed == 2


class TestTimeBasedCache:
    """Test time-based cache."""
    
    def test_expiration(self):
        """Test item expiration."""
        cache = TimeBasedCache[str](ttl_seconds=1)
        
        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"
        
        # Wait for expiration
        time.sleep(1.1)
        
        assert cache.get("key1") is None
        assert cache.stats.evictions == 1
    
    def test_cleanup(self):
        """Test cleanup of expired items."""
        cache = TimeBasedCache[int](ttl_seconds=1)
        
        # Add items at different times
        cache.put("a", 1)
        time.sleep(0.5)
        cache.put("b", 2)
        time.sleep(0.6)  # 'a' should be expired
        
        removed = cache.cleanup()
        assert removed == 1
        assert cache.get("a") is None
        assert cache.get("b") == 2


class TestCacheDecorator:
    """Test cache decorator."""
    
    def test_function_caching(self):
        """Test caching function results."""
        cache = LRUCache[int](max_size=10)
        call_count = 0
        
        @cached(cache)
        def expensive_function(x, y):
            nonlocal call_count
            call_count += 1
            return x + y
        
        # First call
        result = expensive_function(1, 2)
        assert result == 3
        assert call_count == 1
        
        # Second call should use cache
        result = expensive_function(1, 2)
        assert result == 3
        assert call_count == 1  # Not incremented
        
        # Different args should call function
        result = expensive_function(2, 3)
        assert result == 5
        assert call_count == 2
    
    def test_custom_key_function(self):
        """Test custom key generation."""
        cache = LRUCache[str](max_size=10)
        
        def key_func(text, ignore_case=False):
            if ignore_case:
                return text.lower()
            return text
        
        @cached(cache, key_func=key_func)
        def process_text(text, ignore_case=False):
            return f"Processed: {text}"
        
        # Test with custom key
        result1 = process_text("Hello", ignore_case=True)
        result2 = process_text("HELLO", ignore_case=True)
        
        # Should be the same (both use key "hello")
        assert result1 == result2


class TestCacheManager:
    """Test cache manager."""
    
    def test_global_instance(self):
        """Test global cache manager."""
        manager1 = get_cache_manager()
        manager2 = get_cache_manager()
        
        # Should be same instance
        assert manager1 is manager2
    
    def test_cache_access(self):
        """Test accessing different caches."""
        manager = get_cache_manager()
        
        # Test different caches exist
        assert manager.style_cache is not None
        assert manager.header_cache is not None
        assert manager.pattern_cache is not None
        assert manager.node_cache is not None
        assert manager.regex_cache is not None
        
        # Test they're different instances
        assert manager.style_cache is not manager.header_cache
    
    def test_stats_collection(self):
        """Test statistics collection."""
        manager = get_cache_manager()
        manager.reset_stats()
        
        # Use caches
        manager.style_cache.put("test", {"font-size": "14px"})
        manager.style_cache.get("test")
        manager.style_cache.get("missing")
        
        # Get stats
        stats = manager.get_stats()
        assert "style" in stats
        assert stats["style"].hits == 1
        assert stats["style"].misses == 1
    
    def test_clear_all(self):
        """Test clearing all caches."""
        manager = get_cache_manager()
        
        # Add data to caches
        manager.style_cache.put("style1", {})
        manager.header_cache.put("header1", True)
        
        # Clear all
        manager.clear_all()
        
        # Verify cleared
        assert manager.style_cache.get("style1") is None
        assert manager.header_cache.get("header1") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])