"""
MCP Tool Schema Cache

This module provides a TTL-based cache for backend MCP tool schemas.
Caching reduces latency by avoiding repeated tools/list calls to backends.

Features:
- Per-backend caching with configurable TTL
- Thread-safe operations with RLock
- Lazy refresh on expiry
- Stale-while-revalidate on fetch failure
- Cache statistics (hits, misses, entries)

Usage:
    from app.mcp.tool_cache import ToolCache, get_tool_cache
    
    # Create a cache with custom TTL
    cache = ToolCache(ttl_seconds=300)  # 5 minutes
    
    # Store tools from a backend
    cache.set_tools("notion", [Tool(name="search", description="Search pages")])
    
    # Retrieve tools (from cache or via fetcher)
    tools = cache.get_tools("notion")
    
    # Use global cache instance
    cache = get_tool_cache()
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Callable

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Tool Model (Cache-specific, compatible with namespace.Tool)
# =============================================================================


class CachedTool(BaseModel):
    """
    MCP Tool schema for caching.
    
    This model matches the MCP tool format returned by backends.
    Compatible with namespace.Tool for easy conversion.
    
    Attributes:
        name: Tool name (as returned by backend, not namespaced)
        description: Human-readable description
        inputSchema: JSON Schema for the tool's input parameters
    """
    name: str = Field(..., description="Tool name")
    description: str = Field(default="", description="Tool description")
    inputSchema: dict[str, Any] = Field(
        default_factory=dict,
        alias="inputSchema",
        description="JSON Schema for input parameters"
    )
    
    model_config = {"populate_by_name": True}
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.inputSchema,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CachedTool":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            inputSchema=data.get("inputSchema", {}),
        )


# =============================================================================
# Cache Entry
# =============================================================================


@dataclass
class CacheEntry:
    """
    Cache entry with TTL information.
    
    Attributes:
        tools: List of cached tools
        cached_at: When the entry was cached
        expires_at: When the entry expires
    """
    tools: list[CachedTool]
    cached_at: datetime
    expires_at: datetime
    
    @property
    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        return datetime.now(timezone.utc) >= self.expires_at
    
    @property
    def ttl_remaining(self) -> float:
        """Get seconds until expiry (0 if expired)."""
        remaining = (self.expires_at - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, remaining)


# =============================================================================
# Cache Statistics
# =============================================================================


@dataclass
class CacheStats:
    """
    Cache statistics for monitoring.
    
    Attributes:
        hits: Number of cache hits
        misses: Number of cache misses
        entries: Current number of cached backends
    """
    hits: int = 0
    misses: int = 0
    entries: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate hit rate as a ratio (0.0 to 1.0)."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def total_requests(self) -> int:
        """Total number of get requests."""
        return self.hits + self.misses
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for monitoring endpoints."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "entries": self.entries,
            "hit_rate": round(self.hit_rate, 4),
            "total_requests": self.total_requests,
        }


# =============================================================================
# Tool Cache
# =============================================================================


class ToolCache:
    """
    Cache for backend MCP tool schemas.
    
    Reduces latency by caching tools/list responses from backends
    with configurable TTL-based expiration. Thread-safe for concurrent access.
    
    Attributes:
        DEFAULT_TTL_SECONDS: Default time-to-live (5 minutes)
    
    Usage:
        cache = ToolCache(ttl_seconds=300)
        
        # Store tools
        cache.set_tools("notion", [CachedTool(name="search", description="Search")])
        
        # Get tools (from cache)
        tools = cache.get_tools("notion")
        
        # Get with fetcher (auto-refresh on miss)
        tools = cache.get_tools("slack", fetcher=lambda: fetch_from_backend("slack"))
    """
    
    DEFAULT_TTL_SECONDS = 300  # 5 minutes
    
    def __init__(
        self,
        ttl_seconds: int | None = None,
        fetcher: Callable[[str], list[CachedTool]] | None = None,
    ):
        """
        Initialize tool cache.
        
        Args:
            ttl_seconds: Time-to-live for cache entries in seconds.
                        Defaults to DEFAULT_TTL_SECONDS (300).
            fetcher: Optional global function to fetch tools from a backend.
                    Signature: (backend_id: str) -> List[CachedTool]
                    Can be overridden per-call in get_tools().
        """
        self._ttl = timedelta(seconds=ttl_seconds or self.DEFAULT_TTL_SECONDS)
        self._fetcher = fetcher
        self._cache: dict[str, CacheEntry] = {}
        self._lock = RLock()
        self._stats = CacheStats()
    
    # -------------------------------------------------------------------------
    # Core Cache Operations
    # -------------------------------------------------------------------------
    
    def get_tools(
        self,
        backend_id: str,
        fetcher: Callable[[], list[CachedTool]] | None = None,
    ) -> list[CachedTool]:
        """
        Get tools for a backend, fetching if not cached or expired.
        
        On cache hit: returns cached tools immediately.
        On cache miss/expiry: calls fetcher to refresh cache.
        On fetch failure: returns stale data if available, empty list otherwise.
        
        Args:
            backend_id: Backend identifier (e.g., "notion", "slack")
            fetcher: Optional fetcher function for this specific call.
                    Takes no arguments and returns list of tools.
                    Overrides the global fetcher for this call only.
        
        Returns:
            List of tools for the backend
        
        Examples:
            # Simple get (cache or empty)
            tools = cache.get_tools("notion")
            
            # With fetcher for auto-refresh
            tools = cache.get_tools("slack", fetcher=lambda: fetch_slack_tools())
        """
        with self._lock:
            entry = self._cache.get(backend_id)
            
            # Cache hit
            if entry and not entry.is_expired:
                self._stats.hits += 1
                logger.debug(f"Cache hit for backend: {backend_id}")
                return list(entry.tools)  # Return copy to prevent mutation
            
            # Cache miss
            self._stats.misses += 1
            logger.debug(f"Cache miss for backend: {backend_id}")
            
            # Determine which fetcher to use
            fetch_fn: Callable[[], list[CachedTool]] | None = None
            if fetcher is not None:
                fetch_fn = fetcher
            elif self._fetcher is not None:
                fetch_fn = lambda: self._fetcher(backend_id)  # noqa: E731
            
            # No fetcher available
            if fetch_fn is None:
                logger.debug(f"No fetcher for {backend_id}, returning empty")
                return []
            
            # Try to fetch
            try:
                tools = fetch_fn()
                self._set_tools_internal(backend_id, tools)
                return list(tools)
            except Exception as e:
                logger.error(f"Failed to fetch tools for {backend_id}: {e}")
                # Return stale data if available
                if entry is not None:
                    logger.warning(f"Returning stale cache for {backend_id}")
                    return list(entry.tools)
                return []
    
    def set_tools(self, backend_id: str, tools: list[CachedTool]) -> None:
        """
        Store tools in cache.
        
        Creates a new cache entry with current timestamp and calculated expiry.
        
        Args:
            backend_id: Backend identifier (e.g., "notion")
            tools: List of tools to cache
        
        Examples:
            cache.set_tools("notion", [
                CachedTool(name="search", description="Search pages"),
                CachedTool(name="create", description="Create a page"),
            ])
        """
        with self._lock:
            self._set_tools_internal(backend_id, tools)
    
    def _set_tools_internal(self, backend_id: str, tools: list[CachedTool]) -> None:
        """Internal set without lock (caller must hold lock)."""
        now = datetime.now(timezone.utc)
        self._cache[backend_id] = CacheEntry(
            tools=list(tools),  # Copy to prevent external mutation
            cached_at=now,
            expires_at=now + self._ttl,
        )
        self._stats.entries = len(self._cache)
        logger.debug(f"Cached {len(tools)} tools for {backend_id}")
    
    def invalidate(self, backend_id: str) -> bool:
        """
        Remove a backend from cache.
        
        Args:
            backend_id: Backend identifier to invalidate
        
        Returns:
            True if entry existed and was removed, False otherwise
        
        Examples:
            removed = cache.invalidate("notion")
        """
        with self._lock:
            if backend_id in self._cache:
                del self._cache[backend_id]
                self._stats.entries = len(self._cache)
                logger.debug(f"Invalidated cache for {backend_id}")
                return True
            return False
    
    def invalidate_all(self) -> int:
        """
        Clear entire cache.
        
        Returns:
            Number of entries that were cleared
        
        Examples:
            count = cache.invalidate_all()
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._stats.entries = 0
            logger.debug(f"Invalidated entire cache ({count} entries)")
            return count
    
    # -------------------------------------------------------------------------
    # Cache Status Methods
    # -------------------------------------------------------------------------
    
    def is_cached(self, backend_id: str) -> bool:
        """
        Check if backend has valid (non-expired) cache entry.
        
        Args:
            backend_id: Backend identifier to check
        
        Returns:
            True if backend has valid cached tools
        
        Examples:
            if cache.is_cached("notion"):
                tools = cache.get_tools("notion")  # Guaranteed hit
        """
        with self._lock:
            entry = self._cache.get(backend_id)
            return entry is not None and not entry.is_expired
    
    def is_stale(self, backend_id: str) -> bool:
        """
        Check if backend has expired (stale) cache entry.
        
        Args:
            backend_id: Backend identifier to check
        
        Returns:
            True if backend has cached tools that are expired
        """
        with self._lock:
            entry = self._cache.get(backend_id)
            return entry is not None and entry.is_expired
    
    def get_cache_stats(self) -> CacheStats:
        """
        Get cache statistics.
        
        Returns a copy of current stats to prevent external mutation.
        
        Returns:
            CacheStats with hits, misses, and entries count
        
        Examples:
            stats = cache.get_cache_stats()
            print(f"Hit rate: {stats.hit_rate:.2%}")
        """
        with self._lock:
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                entries=len(self._cache),
            )
    
    def reset_stats(self) -> None:
        """Reset hit/miss counters to zero."""
        with self._lock:
            self._stats.hits = 0
            self._stats.misses = 0
    
    # -------------------------------------------------------------------------
    # Inspection Methods
    # -------------------------------------------------------------------------
    
    def get_all_cached_backends(self) -> list[str]:
        """
        Get list of all cached backend IDs.
        
        Includes both valid and expired entries.
        
        Returns:
            List of backend IDs
        """
        with self._lock:
            return list(self._cache.keys())
    
    def get_valid_backends(self) -> list[str]:
        """
        Get list of backends with non-expired cache entries.
        
        Returns:
            List of backend IDs with valid cache
        """
        with self._lock:
            return [
                backend_id
                for backend_id, entry in self._cache.items()
                if not entry.is_expired
            ]
    
    def get_ttl_remaining(self, backend_id: str) -> float | None:
        """
        Get seconds until cache entry expires.
        
        Args:
            backend_id: Backend identifier
        
        Returns:
            Seconds remaining until expiry, or None if not cached
        
        Examples:
            remaining = cache.get_ttl_remaining("notion")
            if remaining is not None and remaining < 60:
                print("Cache expires in less than a minute")
        """
        with self._lock:
            entry = self._cache.get(backend_id)
            if entry is None:
                return None
            return entry.ttl_remaining
    
    def get_cached_at(self, backend_id: str) -> datetime | None:
        """
        Get when the backend's cache entry was created.
        
        Args:
            backend_id: Backend identifier
        
        Returns:
            Datetime when entry was cached, or None if not cached
        """
        with self._lock:
            entry = self._cache.get(backend_id)
            return entry.cached_at if entry else None
    
    def get_tool_count(self, backend_id: str) -> int:
        """
        Get number of tools cached for a backend.
        
        Args:
            backend_id: Backend identifier
        
        Returns:
            Number of tools, or 0 if not cached
        """
        with self._lock:
            entry = self._cache.get(backend_id)
            return len(entry.tools) if entry else 0
    
    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------
    
    @property
    def ttl_seconds(self) -> float:
        """Get current TTL in seconds."""
        return self._ttl.total_seconds()
    
    def set_ttl(self, ttl_seconds: int) -> None:
        """
        Update TTL for future cache entries.
        
        Does not affect existing entries.
        
        Args:
            ttl_seconds: New TTL in seconds
        """
        self._ttl = timedelta(seconds=ttl_seconds)
        logger.debug(f"Updated cache TTL to {ttl_seconds} seconds")


# =============================================================================
# Global Cache Instance
# =============================================================================


_global_cache: ToolCache | None = None


def get_tool_cache() -> ToolCache:
    """
    Get or create global tool cache instance.
    
    Returns the singleton ToolCache instance, creating it if necessary.
    Useful for sharing cache across the application.
    
    Returns:
        Global ToolCache instance
    
    Examples:
        cache = get_tool_cache()
        cache.set_tools("notion", tools)
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = ToolCache()
    return _global_cache


def reset_global_cache() -> None:
    """
    Reset the global cache instance.
    
    Useful for testing or when reconfiguration is needed.
    """
    global _global_cache
    _global_cache = None
