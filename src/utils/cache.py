"""
Caching utilities for the Movie Enrichment Bot.

Provides an async-safe TTL cache implementation for storing poster URLs
and other frequently accessed data.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

K = TypeVar('K')
V = TypeVar('V')


@dataclass
class CacheEntry(Generic[V]):
    """
    A single cache entry with value and expiration time.
    
    Attributes:
        value: The cached value.
        expires_at: Unix timestamp when this entry expires.
    """
    value: V
    expires_at: float
    
    def is_expired(self) -> bool:
        """Check if this cache entry has expired."""
        return time.time() > self.expires_at


@dataclass
class TTLCache(Generic[K, V]):
    """
    Thread-safe TTL (Time-To-Live) cache implementation.
    
    This cache automatically evicts expired entries and enforces a maximum
    size limit using LRU (Least Recently Used) eviction.
    
    Attributes:
        ttl: Time-to-live for cache entries in seconds.
        max_size: Maximum number of entries to store.
    """
    ttl: int = 3600
    max_size: int = 100
    _cache: dict[K, CacheEntry[V]] = field(default_factory=dict)
    _access_order: list[K] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    
    async def get(self, key: K) -> Optional[V]:
        """
        Get a value from the cache.
        
        Args:
            key: The cache key.
            
        Returns:
            The cached value or None if not found/expired.
        """
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                logger.debug(f"Cache miss for key: {key}")
                return None
            
            if entry.is_expired():
                logger.debug(f"Cache entry expired for key: {key}")
                self._remove_entry(key)
                return None
            
            # Update access order for LRU
            self._update_access_order(key)
            logger.debug(f"Cache hit for key: {key}")
            return entry.value
    
    async def set(self, key: K, value: V, ttl: Optional[int] = None) -> None:
        """
        Set a value in the cache.
        
        Args:
            key: The cache key.
            value: The value to cache.
            ttl: Optional custom TTL for this entry (uses default if not specified).
        """
        async with self._lock:
            # Evict if at capacity
            while len(self._cache) >= self.max_size:
                self._evict_oldest()
            
            # Clean expired entries periodically
            if len(self._cache) % 10 == 0:
                self._clean_expired()
            
            entry_ttl = ttl if ttl is not None else self.ttl
            expires_at = time.time() + entry_ttl
            
            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)
            self._update_access_order(key)
            
            logger.debug(f"Cached key: {key} (expires in {entry_ttl}s)")
    
    async def delete(self, key: K) -> bool:
        """
        Delete a value from the cache.
        
        Args:
            key: The cache key.
            
        Returns:
            True if the key was found and deleted, False otherwise.
        """
        async with self._lock:
            if key in self._cache:
                self._remove_entry(key)
                logger.debug(f"Deleted cache key: {key}")
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all entries from the cache."""
        async with self._lock:
            self._cache.clear()
            self._access_order.clear()
            logger.info("Cache cleared")
    
    async def size(self) -> int:
        """
        Get the current number of entries in the cache.
        
        Returns:
            The number of cached entries.
        """
        async with self._lock:
            return len(self._cache)
    
    def _remove_entry(self, key: K) -> None:
        """Remove an entry from the cache (internal, assumes lock is held)."""
        self._cache.pop(key, None)
        try:
            self._access_order.remove(key)
        except ValueError:
            pass
    
    def _update_access_order(self, key: K) -> None:
        """Update the access order for LRU tracking (internal, assumes lock is held)."""
        try:
            self._access_order.remove(key)
        except ValueError:
            pass
        self._access_order.append(key)
    
    def _evict_oldest(self) -> None:
        """Evict the least recently used entry (internal, assumes lock is held)."""
        if self._access_order:
            oldest_key = self._access_order[0]
            self._remove_entry(oldest_key)
            logger.debug(f"Evicted oldest entry: {oldest_key}")
    
    def _clean_expired(self) -> None:
        """Remove all expired entries (internal, assumes lock is held)."""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        for key in expired_keys:
            self._remove_entry(key)
        
        if expired_keys:
            logger.debug(f"Cleaned {len(expired_keys)} expired entries")


class PosterCache(TTLCache[str, str]):
    """
    Specialized cache for movie poster URLs.
    
    Maps TMDB movie IDs to poster URLs for quick retrieval.
    """
    
    async def get_poster_url(self, movie_id: int) -> Optional[str]:
        """
        Get a cached poster URL for a movie.
        
        Args:
            movie_id: The TMDB movie ID.
            
        Returns:
            The poster URL or None if not cached.
        """
        return await self.get(str(movie_id))
    
    async def cache_poster_url(
        self,
        movie_id: int,
        poster_url: str,
        ttl: Optional[int] = None
    ) -> None:
        """
        Cache a poster URL for a movie.
        
        Args:
            movie_id: The TMDB movie ID.
            poster_url: The poster URL to cache.
            ttl: Optional custom TTL.
        """
        await self.set(str(movie_id), poster_url, ttl)