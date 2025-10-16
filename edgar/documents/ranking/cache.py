"""
Search index caching for performance optimization.

Provides memory and disk caching with LRU eviction and TTL expiration.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
import hashlib
import pickle
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """
    Cached search index entry.

    Stores pre-built search indices for a document along with metadata
    for cache management (access tracking, TTL).
    """
    document_hash: str
    index_data: Dict[str, Any]  # Serialized BM25 index data
    created_at: datetime
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SearchIndexCache:
    """
    Manages search index caching with memory + disk storage.

    Features:
    - In-memory LRU cache for fast access
    - Optional disk persistence for reuse across sessions
    - TTL-based expiration
    - Access statistics tracking

    Parameters:
        memory_cache_size: Maximum entries in memory (default: 10)
        disk_cache_enabled: Enable disk persistence (default: True)
        cache_dir: Directory for disk cache (default: ~/.edgar_cache/search)
        ttl_hours: Time-to-live for cached entries (default: 24)
    """

    def __init__(self,
                 memory_cache_size: int = 10,
                 disk_cache_enabled: bool = True,
                 cache_dir: Optional[Path] = None,
                 ttl_hours: int = 24):
        """Initialize cache."""
        self.memory_cache_size = memory_cache_size
        self.disk_cache_enabled = disk_cache_enabled
        self.cache_dir = cache_dir or Path.home() / ".edgar_cache" / "search"
        self.ttl = timedelta(hours=ttl_hours)

        # In-memory cache (LRU)
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._access_order: List[str] = []

        # Statistics
        self._hits = 0
        self._misses = 0

        # Create cache directory
        if disk_cache_enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def compute_document_hash(self, document_id: str, content_sample: str) -> str:
        """
        Compute cache key from document identifiers.

        Uses document ID (e.g., accession number) and a content sample
        to create a unique, stable hash.

        Args:
            document_id: Unique document identifier
            content_sample: Sample of document content for verification

        Returns:
            16-character hex hash
        """
        content = f"{document_id}:{content_sample}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get(self, document_hash: str) -> Optional[CacheEntry]:
        """
        Get cached entry.

        Tries memory cache first, then disk cache. Updates LRU order
        and access statistics.

        Args:
            document_hash: Cache key

        Returns:
            CacheEntry if found and valid, None otherwise
        """
        # Try memory cache first
        if document_hash in self._memory_cache:
            entry = self._memory_cache[document_hash]

            # Check TTL
            if datetime.now() - entry.created_at > self.ttl:
                # Expired - remove from cache
                self._evict_memory(document_hash)
                self._misses += 1
                return None

            # Update access tracking
            entry.access_count += 1
            entry.last_accessed = datetime.now()

            # Update LRU order
            if document_hash in self._access_order:
                self._access_order.remove(document_hash)
            self._access_order.append(document_hash)

            self._hits += 1
            logger.debug(f"Cache hit (memory): {document_hash}")
            return entry

        # Try disk cache
        if self.disk_cache_enabled:
            entry = self._load_from_disk(document_hash)
            if entry:
                # Check TTL
                if datetime.now() - entry.created_at > self.ttl:
                    # Expired - delete file
                    self._delete_from_disk(document_hash)
                    self._misses += 1
                    return None

                # Load into memory cache
                self._put_memory(document_hash, entry)
                self._hits += 1
                logger.debug(f"Cache hit (disk): {document_hash}")
                return entry

        self._misses += 1
        logger.debug(f"Cache miss: {document_hash}")
        return None

    def put(self, document_hash: str, entry: CacheEntry) -> None:
        """
        Cache entry in memory and optionally on disk.

        Args:
            document_hash: Cache key
            entry: Entry to cache
        """
        # Put in memory cache
        self._put_memory(document_hash, entry)

        # Put in disk cache
        if self.disk_cache_enabled:
            self._save_to_disk(document_hash, entry)

        logger.debug(f"Cached entry: {document_hash}")

    def _put_memory(self, document_hash: str, entry: CacheEntry) -> None:
        """Put entry in memory cache with LRU eviction."""
        # Evict if cache full
        while len(self._memory_cache) >= self.memory_cache_size:
            if self._access_order:
                oldest = self._access_order.pop(0)
                self._evict_memory(oldest)
            else:
                break

        self._memory_cache[document_hash] = entry
        self._access_order.append(document_hash)

    def _evict_memory(self, document_hash: str) -> None:
        """Evict entry from memory cache."""
        if document_hash in self._memory_cache:
            del self._memory_cache[document_hash]
            logger.debug(f"Evicted from memory: {document_hash}")

    def _load_from_disk(self, document_hash: str) -> Optional[CacheEntry]:
        """Load entry from disk cache."""
        cache_file = self.cache_dir / f"{document_hash}.pkl"
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'rb') as f:
                entry = pickle.load(f)
            return entry
        except Exception as e:
            logger.warning(f"Failed to load cache from disk: {e}")
            # Delete corrupted file
            try:
                cache_file.unlink()
            except:
                pass
            return None

    def _save_to_disk(self, document_hash: str, entry: CacheEntry) -> None:
        """Save entry to disk cache."""
        cache_file = self.cache_dir / f"{document_hash}.pkl"
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(entry, f)
        except Exception as e:
            logger.warning(f"Failed to save cache to disk: {e}")

    def _delete_from_disk(self, document_hash: str) -> None:
        """Delete entry from disk cache."""
        cache_file = self.cache_dir / f"{document_hash}.pkl"
        try:
            if cache_file.exists():
                cache_file.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete cache file: {e}")

    def clear(self, memory_only: bool = False) -> None:
        """
        Clear cache.

        Args:
            memory_only: If True, only clear memory cache (keep disk)
        """
        self._memory_cache.clear()
        self._access_order.clear()
        logger.info("Cleared memory cache")

        if not memory_only and self.disk_cache_enabled:
            try:
                for cache_file in self.cache_dir.glob("*.pkl"):
                    cache_file.unlink()
                logger.info("Cleared disk cache")
            except Exception as e:
                logger.warning(f"Failed to clear disk cache: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        disk_entries = 0
        if self.disk_cache_enabled:
            try:
                disk_entries = len(list(self.cache_dir.glob("*.pkl")))
            except:
                pass

        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        return {
            "memory_entries": len(self._memory_cache),
            "disk_entries": disk_entries,
            "total_accesses": sum(e.access_count for e in self._memory_cache.values()),
            "cache_hits": self._hits,
            "cache_misses": self._misses,
            "hit_rate": hit_rate,
            "memory_size_mb": self._estimate_cache_size()
        }

    def _estimate_cache_size(self) -> float:
        """Estimate memory cache size in MB."""
        try:
            import sys
            total_bytes = sum(
                sys.getsizeof(entry.index_data)
                for entry in self._memory_cache.values()
            )
            return total_bytes / (1024 * 1024)
        except:
            # Rough estimate if sys.getsizeof fails
            return len(self._memory_cache) * 5.0  # Assume ~5MB per entry


# Global cache instance
_global_cache: Optional[SearchIndexCache] = None


def get_search_cache() -> SearchIndexCache:
    """
    Get global search cache instance.

    Creates a singleton cache instance on first call.

    Returns:
        Global SearchIndexCache instance
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = SearchIndexCache()
    return _global_cache


def set_search_cache(cache: Optional[SearchIndexCache]) -> None:
    """
    Set global search cache instance.

    Useful for testing or custom cache configuration.

    Args:
        cache: Cache instance to use globally (None to disable)
    """
    global _global_cache
    _global_cache = cache
