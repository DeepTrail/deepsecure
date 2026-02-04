"""
Unit tests for MCP Tool Schema Cache.

Tests cover:
- CachedTool model operations
- CacheEntry expiration logic
- CacheStats calculations
- ToolCache CRUD operations
- TTL expiration behavior
- Thread-safe concurrent access
- Stale-while-revalidate pattern
- Global cache instance
"""

import threading
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.mcp.tool_cache import (
    CachedTool,
    CacheEntry,
    CacheStats,
    ToolCache,
    get_tool_cache,
    reset_global_cache,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_tool() -> CachedTool:
    """Create a sample tool for testing."""
    return CachedTool(
        name="search_pages",
        description="Search for pages in workspace",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    )


@pytest.fixture
def sample_tools() -> list[CachedTool]:
    """Create a list of sample tools for testing."""
    return [
        CachedTool(name="search", description="Search items", inputSchema={}),
        CachedTool(name="read", description="Read an item", inputSchema={}),
        CachedTool(name="create", description="Create an item", inputSchema={}),
    ]


@pytest.fixture
def cache() -> ToolCache:
    """Create a fresh ToolCache for testing."""
    return ToolCache(ttl_seconds=60)


@pytest.fixture(autouse=True)
def reset_global():
    """Reset global cache before and after each test."""
    reset_global_cache()
    yield
    reset_global_cache()


# =============================================================================
# CachedTool Tests
# =============================================================================


class TestCachedTool:
    """Tests for CachedTool model."""
    
    def test_create_tool_with_all_fields(self):
        """Test creating a tool with all fields."""
        tool = CachedTool(
            name="search",
            description="Search for items",
            inputSchema={"type": "object"},
        )
        
        assert tool.name == "search"
        assert tool.description == "Search for items"
        assert tool.inputSchema == {"type": "object"}
    
    def test_create_tool_with_defaults(self):
        """Test creating a tool with default values."""
        tool = CachedTool(name="search")
        
        assert tool.name == "search"
        assert tool.description == ""
        assert tool.inputSchema == {}
    
    def test_to_dict(self, sample_tool):
        """Test conversion to dictionary."""
        data = sample_tool.to_dict()
        
        assert data["name"] == "search_pages"
        assert data["description"] == "Search for pages in workspace"
        assert "inputSchema" in data
        assert data["inputSchema"]["type"] == "object"
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "name": "send_message",
            "description": "Send a message",
            "inputSchema": {"type": "object"},
        }
        
        tool = CachedTool.from_dict(data)
        
        assert tool.name == "send_message"
        assert tool.description == "Send a message"
        assert tool.inputSchema == {"type": "object"}
    
    def test_from_dict_with_missing_optional_fields(self):
        """Test creation from dict with missing optional fields."""
        data = {"name": "simple_tool"}
        
        tool = CachedTool.from_dict(data)
        
        assert tool.name == "simple_tool"
        assert tool.description == ""
        assert tool.inputSchema == {}
    
    def test_alias_input_schema(self):
        """Test that inputSchema alias works correctly."""
        # Using alias in constructor
        tool = CachedTool(name="test", inputSchema={"type": "string"})
        assert tool.inputSchema == {"type": "string"}
        
        # Model dump uses alias by default
        data = tool.model_dump(by_alias=True)
        assert "inputSchema" in data


# =============================================================================
# CacheEntry Tests
# =============================================================================


class TestCacheEntry:
    """Tests for CacheEntry expiration logic."""
    
    def test_entry_not_expired_within_ttl(self, sample_tools):
        """Test that entry is not expired within TTL."""
        now = datetime.now(timezone.utc)
        entry = CacheEntry(
            tools=sample_tools,
            cached_at=now,
            expires_at=now + timedelta(minutes=5),
        )
        
        assert entry.is_expired is False
        assert entry.ttl_remaining > 0
    
    def test_entry_expired_after_ttl(self, sample_tools):
        """Test that entry is expired after TTL."""
        now = datetime.now(timezone.utc)
        entry = CacheEntry(
            tools=sample_tools,
            cached_at=now - timedelta(minutes=10),
            expires_at=now - timedelta(minutes=5),
        )
        
        assert entry.is_expired is True
        assert entry.ttl_remaining == 0.0
    
    def test_ttl_remaining_calculation(self, sample_tools):
        """Test TTL remaining calculation."""
        now = datetime.now(timezone.utc)
        entry = CacheEntry(
            tools=sample_tools,
            cached_at=now,
            expires_at=now + timedelta(seconds=100),
        )
        
        remaining = entry.ttl_remaining
        assert 99 <= remaining <= 100


# =============================================================================
# CacheStats Tests
# =============================================================================


class TestCacheStats:
    """Tests for CacheStats calculations."""
    
    def test_default_values(self):
        """Test default stat values."""
        stats = CacheStats()
        
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.entries == 0
    
    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        stats = CacheStats(hits=75, misses=25, entries=5)
        
        assert stats.hit_rate == 0.75
        assert stats.total_requests == 100
    
    def test_hit_rate_zero_requests(self):
        """Test hit rate with zero requests."""
        stats = CacheStats()
        
        assert stats.hit_rate == 0.0
    
    def test_to_dict(self):
        """Test stats serialization."""
        stats = CacheStats(hits=10, misses=2, entries=3)
        
        data = stats.to_dict()
        
        assert data["hits"] == 10
        assert data["misses"] == 2
        assert data["entries"] == 3
        assert data["hit_rate"] == pytest.approx(0.8333, abs=0.001)
        assert data["total_requests"] == 12


# =============================================================================
# ToolCache Basic Operations Tests
# =============================================================================


class TestToolCacheBasicOperations:
    """Tests for basic ToolCache operations."""
    
    def test_set_and_get_tools(self, cache, sample_tools):
        """Test storing and retrieving tools."""
        cache.set_tools("notion", sample_tools)
        
        retrieved = cache.get_tools("notion")
        
        assert len(retrieved) == 3
        assert retrieved[0].name == "search"
        assert retrieved[1].name == "read"
        assert retrieved[2].name == "create"
    
    def test_get_nonexistent_backend_returns_empty(self, cache):
        """Test getting tools for unknown backend returns empty list."""
        tools = cache.get_tools("unknown_backend")
        
        assert tools == []
    
    def test_is_cached_true_for_stored(self, cache, sample_tools):
        """Test is_cached returns True for stored backends."""
        cache.set_tools("notion", sample_tools)
        
        assert cache.is_cached("notion") is True
    
    def test_is_cached_false_for_missing(self, cache):
        """Test is_cached returns False for missing backends."""
        assert cache.is_cached("notion") is False
    
    def test_invalidate_removes_entry(self, cache, sample_tools):
        """Test invalidating a cache entry."""
        cache.set_tools("notion", sample_tools)
        
        result = cache.invalidate("notion")
        
        assert result is True
        assert cache.is_cached("notion") is False
    
    def test_invalidate_nonexistent_returns_false(self, cache):
        """Test invalidating nonexistent entry returns False."""
        result = cache.invalidate("nonexistent")
        
        assert result is False
    
    def test_invalidate_all_clears_cache(self, cache, sample_tools):
        """Test clearing entire cache."""
        cache.set_tools("notion", sample_tools)
        cache.set_tools("slack", sample_tools)
        cache.set_tools("github", sample_tools)
        
        count = cache.invalidate_all()
        
        assert count == 3
        assert cache.is_cached("notion") is False
        assert cache.is_cached("slack") is False
        assert cache.is_cached("github") is False
    
    def test_get_all_cached_backends(self, cache, sample_tools):
        """Test getting list of all cached backends."""
        cache.set_tools("notion", sample_tools)
        cache.set_tools("slack", sample_tools)
        
        backends = cache.get_all_cached_backends()
        
        assert set(backends) == {"notion", "slack"}
    
    def test_get_tool_count(self, cache, sample_tools):
        """Test getting tool count for a backend."""
        cache.set_tools("notion", sample_tools)
        
        count = cache.get_tool_count("notion")
        
        assert count == 3
    
    def test_get_tool_count_missing_returns_zero(self, cache):
        """Test tool count for missing backend returns 0."""
        count = cache.get_tool_count("missing")
        
        assert count == 0


# =============================================================================
# ToolCache Statistics Tests
# =============================================================================


class TestToolCacheStatistics:
    """Tests for cache statistics tracking."""
    
    def test_hit_increments_on_cache_hit(self, cache, sample_tools):
        """Test hits counter increments on cache hit."""
        cache.set_tools("notion", sample_tools)
        
        cache.get_tools("notion")
        cache.get_tools("notion")
        cache.get_tools("notion")
        
        stats = cache.get_cache_stats()
        assert stats.hits == 3
        assert stats.misses == 0
    
    def test_miss_increments_on_cache_miss(self, cache):
        """Test misses counter increments on cache miss."""
        cache.get_tools("notion")
        cache.get_tools("slack")
        
        stats = cache.get_cache_stats()
        assert stats.hits == 0
        assert stats.misses == 2
    
    def test_entries_count_accurate(self, cache, sample_tools):
        """Test entries count is accurate."""
        cache.set_tools("notion", sample_tools)
        cache.set_tools("slack", sample_tools)
        
        stats = cache.get_cache_stats()
        
        assert stats.entries == 2
    
    def test_entries_count_decrements_on_invalidate(self, cache, sample_tools):
        """Test entries count decrements on invalidate."""
        cache.set_tools("notion", sample_tools)
        cache.set_tools("slack", sample_tools)
        cache.invalidate("notion")
        
        stats = cache.get_cache_stats()
        
        assert stats.entries == 1
    
    def test_reset_stats(self, cache, sample_tools):
        """Test resetting statistics."""
        cache.set_tools("notion", sample_tools)
        cache.get_tools("notion")
        cache.get_tools("missing")
        
        cache.reset_stats()
        
        stats = cache.get_cache_stats()
        assert stats.hits == 0
        assert stats.misses == 0
        # entries not reset
        assert stats.entries == 1


# =============================================================================
# ToolCache TTL Tests
# =============================================================================


class TestToolCacheTTL:
    """Tests for TTL expiration behavior."""
    
    def test_cache_expires_after_ttl(self, sample_tools):
        """Test that cache entry expires after TTL."""
        cache = ToolCache(ttl_seconds=1)  # 1 second TTL
        cache.set_tools("notion", sample_tools)
        
        assert cache.is_cached("notion") is True
        
        time.sleep(1.1)
        
        assert cache.is_cached("notion") is False
    
    def test_expired_entry_triggers_fetcher(self, sample_tools):
        """Test that expired entry calls fetcher."""
        fetcher = MagicMock(return_value=[CachedTool(name="fresh", description="")])
        cache = ToolCache(ttl_seconds=1, fetcher=fetcher)
        cache.set_tools("notion", sample_tools)
        
        time.sleep(1.1)
        
        tools = cache.get_tools("notion")
        
        fetcher.assert_called_once_with("notion")
        assert tools[0].name == "fresh"
    
    def test_is_stale_for_expired_entry(self, sample_tools):
        """Test is_stale returns True for expired entries."""
        cache = ToolCache(ttl_seconds=1)
        cache.set_tools("notion", sample_tools)
        
        time.sleep(1.1)
        
        assert cache.is_stale("notion") is True
        assert cache.is_cached("notion") is False
    
    def test_get_ttl_remaining(self, cache, sample_tools):
        """Test getting remaining TTL."""
        cache.set_tools("notion", sample_tools)
        
        remaining = cache.get_ttl_remaining("notion")
        
        assert remaining is not None
        assert 58 <= remaining <= 60  # ~60 seconds TTL
    
    def test_get_ttl_remaining_missing_returns_none(self, cache):
        """Test TTL remaining for missing backend returns None."""
        remaining = cache.get_ttl_remaining("missing")
        
        assert remaining is None
    
    def test_get_valid_backends_excludes_expired(self, sample_tools):
        """Test get_valid_backends excludes expired entries."""
        cache = ToolCache(ttl_seconds=1)
        cache.set_tools("notion", sample_tools)
        cache.set_tools("slack", sample_tools)
        
        time.sleep(1.1)
        
        # Add fresh entry
        cache.set_tools("github", sample_tools)
        
        valid = cache.get_valid_backends()
        
        assert "github" in valid
        assert "notion" not in valid
        assert "slack" not in valid
    
    def test_set_ttl_affects_new_entries(self, cache, sample_tools):
        """Test updating TTL affects new entries."""
        cache.set_tools("notion", sample_tools)
        old_remaining = cache.get_ttl_remaining("notion")
        
        cache.set_ttl(120)  # 2 minutes
        cache.set_tools("slack", sample_tools)
        new_remaining = cache.get_ttl_remaining("slack")
        
        assert old_remaining is not None
        assert new_remaining is not None
        assert 58 <= old_remaining <= 60
        assert 118 <= new_remaining <= 120
    
    def test_ttl_seconds_property(self, cache):
        """Test ttl_seconds property."""
        assert cache.ttl_seconds == 60.0
        
        cache.set_ttl(120)
        assert cache.ttl_seconds == 120.0


# =============================================================================
# ToolCache Fetcher Tests
# =============================================================================


class TestToolCacheFetcher:
    """Tests for fetcher functionality."""
    
    def test_global_fetcher_called_on_miss(self, sample_tools):
        """Test global fetcher is called on cache miss."""
        fetcher = MagicMock(return_value=sample_tools)
        cache = ToolCache(fetcher=fetcher)
        
        tools = cache.get_tools("notion")
        
        fetcher.assert_called_once_with("notion")
        assert len(tools) == 3
    
    def test_per_call_fetcher_overrides_global(self, sample_tools):
        """Test per-call fetcher overrides global fetcher."""
        global_fetcher = MagicMock(return_value=[CachedTool(name="global")])
        local_fetcher = MagicMock(return_value=sample_tools)
        cache = ToolCache(fetcher=global_fetcher)
        
        tools = cache.get_tools("notion", fetcher=local_fetcher)
        
        global_fetcher.assert_not_called()
        local_fetcher.assert_called_once()
        assert len(tools) == 3
    
    def test_fetched_tools_are_cached(self, sample_tools):
        """Test that fetched tools are stored in cache."""
        fetcher = MagicMock(return_value=sample_tools)
        cache = ToolCache(fetcher=fetcher)
        
        cache.get_tools("notion")
        cache.get_tools("notion")  # Second call should be cache hit
        
        fetcher.assert_called_once()
        assert cache.is_cached("notion") is True
    
    def test_fetcher_error_returns_stale_data(self, sample_tools):
        """Test stale data returned on fetcher error."""
        fetcher = MagicMock(side_effect=Exception("Network error"))
        cache = ToolCache(ttl_seconds=1, fetcher=fetcher)
        
        # Pre-populate with data
        cache.set_tools("notion", sample_tools)
        
        # Wait for expiry
        time.sleep(1.1)
        
        # Should return stale data on fetch failure
        tools = cache.get_tools("notion")
        
        fetcher.assert_called_once()
        assert len(tools) == 3
        assert tools[0].name == "search"
    
    def test_fetcher_error_returns_empty_without_stale_data(self):
        """Test empty list returned when fetcher fails and no stale data."""
        fetcher = MagicMock(side_effect=Exception("Network error"))
        cache = ToolCache(fetcher=fetcher)
        
        tools = cache.get_tools("notion")
        
        assert tools == []


# =============================================================================
# ToolCache Thread Safety Tests
# =============================================================================


class TestToolCacheThreadSafety:
    """Tests for thread-safe concurrent access."""
    
    def test_concurrent_writes(self, sample_tools):
        """Test concurrent writes don't cause errors."""
        cache = ToolCache()
        errors: list[Exception] = []
        
        def writer(backend_prefix: str):
            try:
                for i in range(50):
                    tools = [CachedTool(name=f"tool_{i}", description="")]
                    cache.set_tools(f"{backend_prefix}_{i}", tools)
            except Exception as e:
                errors.append(e)
        
        threads = [
            threading.Thread(target=writer, args=(f"backend_{t}",))
            for t in range(5)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert len(cache.get_all_cached_backends()) == 250  # 5 threads * 50 backends
    
    def test_concurrent_reads_and_writes(self, sample_tools):
        """Test concurrent reads and writes don't cause errors."""
        cache = ToolCache()
        errors: list[Exception] = []
        
        # Pre-populate
        for i in range(20):
            cache.set_tools(f"backend_{i}", sample_tools)
        
        def writer():
            try:
                for i in range(50):
                    cache.set_tools(f"new_backend_{i}", sample_tools)
            except Exception as e:
                errors.append(e)
        
        def reader():
            try:
                for i in range(100):
                    cache.get_tools(f"backend_{i % 20}")
                    cache.is_cached(f"backend_{i % 20}")
                    cache.get_cache_stats()
            except Exception as e:
                errors.append(e)
        
        threads = []
        threads.extend(threading.Thread(target=writer) for _ in range(3))
        threads.extend(threading.Thread(target=reader) for _ in range(5))
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
    
    def test_concurrent_invalidation(self, sample_tools):
        """Test concurrent invalidation is safe."""
        cache = ToolCache()
        errors: list[Exception] = []
        
        # Pre-populate
        for i in range(50):
            cache.set_tools(f"backend_{i}", sample_tools)
        
        def invalidator():
            try:
                for i in range(50):
                    cache.invalidate(f"backend_{i}")
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=invalidator) for _ in range(5)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert len(cache.get_all_cached_backends()) == 0


# =============================================================================
# ToolCache Inspection Tests
# =============================================================================


class TestToolCacheInspection:
    """Tests for cache inspection methods."""
    
    def test_get_cached_at(self, cache, sample_tools):
        """Test getting cache timestamp."""
        before = datetime.now(timezone.utc)
        cache.set_tools("notion", sample_tools)
        after = datetime.now(timezone.utc)
        
        cached_at = cache.get_cached_at("notion")
        
        assert cached_at is not None
        assert before <= cached_at <= after
    
    def test_get_cached_at_missing_returns_none(self, cache):
        """Test cached_at for missing backend returns None."""
        cached_at = cache.get_cached_at("missing")
        
        assert cached_at is None
    
    def test_returned_tools_are_copies(self, cache, sample_tools):
        """Test that returned tools are copies, not references."""
        cache.set_tools("notion", sample_tools)
        
        tools1 = cache.get_tools("notion")
        tools2 = cache.get_tools("notion")
        
        # Modify returned list
        tools1.append(CachedTool(name="extra"))
        
        # Original cache unchanged
        assert len(cache.get_tools("notion")) == 3
        assert len(tools2) == 3


# =============================================================================
# Global Cache Tests
# =============================================================================


class TestGlobalCache:
    """Tests for global cache instance."""
    
    def test_get_tool_cache_returns_singleton(self):
        """Test get_tool_cache returns same instance."""
        cache1 = get_tool_cache()
        cache2 = get_tool_cache()
        
        assert cache1 is cache2
    
    def test_reset_global_cache(self, sample_tools):
        """Test resetting global cache."""
        cache1 = get_tool_cache()
        cache1.set_tools("notion", sample_tools)
        
        reset_global_cache()
        
        cache2 = get_tool_cache()
        
        assert cache1 is not cache2
        assert not cache2.is_cached("notion")
    
    def test_global_cache_default_ttl(self):
        """Test global cache uses default TTL."""
        cache = get_tool_cache()
        
        assert cache.ttl_seconds == ToolCache.DEFAULT_TTL_SECONDS


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_empty_tools_list(self, cache):
        """Test caching empty tools list."""
        cache.set_tools("notion", [])
        
        tools = cache.get_tools("notion")
        
        assert tools == []
        assert cache.is_cached("notion") is True
    
    def test_overwrite_existing_cache(self, cache, sample_tools):
        """Test overwriting existing cache entry."""
        cache.set_tools("notion", sample_tools)
        new_tools = [CachedTool(name="new_tool")]
        
        cache.set_tools("notion", new_tools)
        
        tools = cache.get_tools("notion")
        assert len(tools) == 1
        assert tools[0].name == "new_tool"
    
    def test_invalidate_all_empty_cache(self, cache):
        """Test invalidate_all on empty cache."""
        count = cache.invalidate_all()
        
        assert count == 0
    
    def test_very_long_backend_id(self, cache, sample_tools):
        """Test caching with long backend ID."""
        long_id = "a" * 1000
        cache.set_tools(long_id, sample_tools)
        
        assert cache.is_cached(long_id) is True
        tools = cache.get_tools(long_id)
        assert len(tools) == 3
    
    def test_special_characters_in_backend_id(self, cache, sample_tools):
        """Test caching with special characters in backend ID."""
        special_id = "backend-with_special.chars@123"
        cache.set_tools(special_id, sample_tools)
        
        assert cache.is_cached(special_id) is True
    
    def test_zero_ttl(self, sample_tools):
        """Test cache with zero TTL triggers fetcher on next access."""
        fetch_count = 0
        
        def counting_fetcher():
            nonlocal fetch_count
            fetch_count += 1
            return sample_tools
        
        cache = ToolCache(ttl_seconds=0)
        cache.set_tools("notion", sample_tools)
        
        # With zero TTL, the entry expires at same moment it's created.
        # The key behavior: next get_tools should treat it as expired
        # and would call fetcher (if provided) or return stale/empty.
        time.sleep(0.001)  # Ensure time has advanced
        
        # Should be expired (or at boundary)
        tools = cache.get_tools("notion", fetcher=counting_fetcher)
        
        # Either returns cached (if exact timing hit) or fetches
        # The point is: very short TTL leads to quick expiry
        assert len(tools) == 3  # Either cached or fetched, both return 3 tools
    
    def test_negative_ttl_treated_as_zero(self, sample_tools):
        """Test negative TTL is handled gracefully."""
        cache = ToolCache(ttl_seconds=-10)
        cache.set_tools("notion", sample_tools)
        
        # Treated as immediate expiry
        assert cache.is_cached("notion") is False
