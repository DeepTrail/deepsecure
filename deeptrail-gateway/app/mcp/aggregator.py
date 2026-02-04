"""
MCP Tool Aggregator for Virtual MCP Server.

Combines tools from multiple backend MCP servers into a unified, namespaced
view. This is the core component enabling the "Unified Connection" value
proposition: agent connects to ONE gateway and sees tools from 2-3 backends.

How it works:
1. Collect tools from ToolCache for specified backends
2. Apply namespace prefix to each tool (notion.search_pages)
3. Enhance descriptions with backend prefix ([Notion] Search pages)
4. Optionally filter by permissions or custom predicates
5. Return aggregated, namespaced tools

Features:
- Aggregate tools from multiple backends into unified view
- Apply namespace prefixes to prevent collisions
- Filter by permissions using PermissionMapper
- Track succeeded and failed backends
- Thread-safe for concurrent access

Usage:
    from app.mcp.aggregator import ToolAggregator
    from app.mcp.tool_cache import ToolCache
    
    cache = ToolCache()
    aggregator = ToolAggregator(cache)
    
    # Aggregate from all registered backends
    tools = aggregator.aggregate_all()
    
    # Aggregate from specific backends
    tools = aggregator.aggregate(backends=["notion", "slack"])
    
    # Aggregate with permission filtering
    tools = aggregator.aggregate_with_permissions(
        backends=["notion", "slack"],
        permissions=["notion:pages:search", "slack:messages:search"]
    )
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from .namespace import Tool, prefix_tool
from .permission_mapper import PermissionMapper
from .tool_cache import CachedTool, ToolCache

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class AggregatedTool:
    """
    A tool that has been aggregated from a backend with namespace applied.
    
    Attributes:
        name: Namespaced tool name (e.g., "notion.search_pages")
        description: Enhanced description with backend prefix
        inputSchema: JSON Schema for parameters
        backend: Original backend ID (e.g., "notion")
        original_name: Original tool name without namespace (e.g., "search_pages")
    """
    name: str
    description: str
    inputSchema: dict[str, Any]
    backend: str
    original_name: str
    
    def to_dict(self) -> dict[str, Any]:
        """
        Convert to MCP tool format for JSON-RPC response.
        
        Returns only the standard MCP tool fields (name, description, inputSchema).
        Backend and original_name are internal metadata not sent to clients.
        """
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.inputSchema,
        }
    
    def to_tool(self) -> Tool:
        """Convert to namespace.Tool for compatibility."""
        return Tool(
            name=self.name,
            description=self.description,
            inputSchema=self.inputSchema,
        )


@dataclass
class AggregationResult:
    """
    Result of a tool aggregation operation.
    
    Tracks not just the aggregated tools, but also which backends
    succeeded and which failed, enabling proper error handling and logging.
    
    Attributes:
        tools: List of aggregated tools
        backends_succeeded: Backends that provided tools
        backends_failed: Backends that failed to provide tools
    """
    tools: list[AggregatedTool] = field(default_factory=list)
    backends_succeeded: list[str] = field(default_factory=list)
    backends_failed: list[str] = field(default_factory=list)
    
    @property
    def total_tools(self) -> int:
        """Total number of aggregated tools."""
        return len(self.tools)
    
    @property
    def all_succeeded(self) -> bool:
        """Whether all requested backends succeeded."""
        return len(self.backends_failed) == 0
    
    def to_tool_list(self) -> list[dict[str, Any]]:
        """
        Convert to list of MCP tool dictionaries.
        
        Returns the format expected by tools/list response.
        """
        return [tool.to_dict() for tool in self.tools]
    
    def get_tools_for_backend(self, backend_id: str) -> list[AggregatedTool]:
        """Get only tools from a specific backend."""
        return [t for t in self.tools if t.backend == backend_id]


# =============================================================================
# Tool Aggregator
# =============================================================================


class ToolAggregator:
    """
    Aggregates tools from multiple backend MCP servers.
    
    The aggregator collects tools from the ToolCache, applies namespace
    prefixes, and optionally filters by permissions. It provides a unified
    view of all available tools across backends.
    
    Thread-safety: This class is thread-safe. Multiple threads can call
    aggregation methods concurrently. The only mutable state is the
    registered_backends list, which is modified only by register/unregister.
    
    Example:
        aggregator = ToolAggregator(tool_cache)
        
        # Get all tools from all backends
        result = aggregator.aggregate_all()
        print(f"Found {result.total_tools} tools from {len(result.backends_succeeded)} backends")
        
        # Get tools filtered by permissions
        result = aggregator.aggregate_with_permissions(
            backends=["notion", "slack"],
            permissions=["notion:pages:search", "slack:messages:search"]
        )
    """
    
    def __init__(
        self,
        tool_cache: ToolCache,
        registered_backends: list[str] | None = None,
    ):
        """
        Initialize the aggregator.
        
        Args:
            tool_cache: ToolCache instance for fetching backend tools
            registered_backends: List of known backend IDs (optional, for aggregate_all)
        """
        self._tool_cache = tool_cache
        self._registered_backends = list(registered_backends or [])
    
    # ─────────────────────────────────────────────────────────────────────────
    # Backend Registration
    # ─────────────────────────────────────────────────────────────────────────
    
    def register_backend(self, backend_id: str) -> None:
        """
        Register a backend for aggregate_all() calls.
        
        Args:
            backend_id: Backend identifier (e.g., "notion")
        """
        if backend_id not in self._registered_backends:
            self._registered_backends.append(backend_id)
            logger.debug("Registered backend for aggregation: %s", backend_id)
    
    def unregister_backend(self, backend_id: str) -> bool:
        """
        Unregister a backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            True if backend was removed, False if not found
        """
        if backend_id in self._registered_backends:
            self._registered_backends.remove(backend_id)
            logger.debug("Unregistered backend: %s", backend_id)
            return True
        return False
    
    def get_registered_backends(self) -> list[str]:
        """Get list of registered backend IDs."""
        return list(self._registered_backends)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Core Aggregation Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def aggregate(
        self,
        backends: Iterable[str],
        filter_func: Callable[[AggregatedTool], bool] | None = None,
    ) -> AggregationResult:
        """
        Aggregate tools from specified backends.
        
        Collects tools from each backend's cache, applies namespace prefixes,
        and optionally filters. Failed backends don't stop aggregation.
        
        Args:
            backends: Backend IDs to aggregate from
            filter_func: Optional function to filter tools (returns True to include)
            
        Returns:
            AggregationResult with aggregated tools and status
        
        Example:
            # Get all tools from notion and slack
            result = aggregator.aggregate(["notion", "slack"])
            
            # Get only search tools
            result = aggregator.aggregate(
                ["notion", "slack"],
                filter_func=lambda t: "search" in t.name
            )
        """
        result = AggregationResult()
        
        for backend_id in backends:
            try:
                # Get tools from cache
                cached_tools = self._tool_cache.get_tools(backend_id)
                
                if not cached_tools:
                    logger.warning(
                        "No cached tools for backend: %s (cache miss or empty)",
                        backend_id
                    )
                    result.backends_failed.append(backend_id)
                    continue
                
                # Convert and namespace each tool
                tools_added = 0
                for cached_tool in cached_tools:
                    aggregated = self._create_aggregated_tool(cached_tool, backend_id)
                    
                    # Apply filter if provided
                    if filter_func is not None and not filter_func(aggregated):
                        continue
                    
                    result.tools.append(aggregated)
                    tools_added += 1
                
                result.backends_succeeded.append(backend_id)
                logger.debug(
                    "Aggregated %d tools from backend: %s",
                    tools_added,
                    backend_id
                )
                
            except Exception as e:
                logger.error(
                    "Failed to aggregate tools from backend %s: %s",
                    backend_id,
                    str(e),
                    exc_info=True
                )
                result.backends_failed.append(backend_id)
        
        logger.info(
            "Aggregation complete: %d tools from %d backends (%d failed)",
            result.total_tools,
            len(result.backends_succeeded),
            len(result.backends_failed)
        )
        
        return result
    
    def aggregate_all(
        self,
        filter_func: Callable[[AggregatedTool], bool] | None = None,
    ) -> AggregationResult:
        """
        Aggregate tools from all registered backends.
        
        Args:
            filter_func: Optional function to filter tools
            
        Returns:
            AggregationResult with aggregated tools from all backends
        """
        if not self._registered_backends:
            logger.warning("No backends registered for aggregate_all()")
            return AggregationResult()
        
        return self.aggregate(self._registered_backends, filter_func)
    
    def aggregate_with_permissions(
        self,
        backends: Iterable[str],
        permissions: list[str],
    ) -> AggregationResult:
        """
        Aggregate tools filtered by delegated permissions.
        
        Uses PermissionMapper to check if each tool's required permission
        is in the provided permission list. Only permitted tools are included.
        
        Args:
            backends: Backend IDs to aggregate from
            permissions: List of delegated permission strings
            
        Returns:
            AggregationResult with only permitted tools
        
        Example:
            result = aggregator.aggregate_with_permissions(
                ["notion", "slack"],
                ["notion:pages:search", "slack:messages:search"]
            )
        """
        def permission_filter(tool: AggregatedTool) -> bool:
            return PermissionMapper.is_tool_permitted(tool.name, permissions)
        
        return self.aggregate(backends, permission_filter)
    
    def aggregate_for_backend(
        self,
        backend_id: str,
        filter_func: Callable[[AggregatedTool], bool] | None = None,
    ) -> AggregationResult:
        """
        Aggregate tools from a single backend.
        
        Convenience method for single-backend aggregation.
        
        Args:
            backend_id: Backend to aggregate from
            filter_func: Optional filter function
            
        Returns:
            AggregationResult from the specified backend
        """
        return self.aggregate([backend_id], filter_func)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Helper Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def _create_aggregated_tool(
        self,
        cached_tool: CachedTool,
        backend_id: str,
    ) -> AggregatedTool:
        """
        Create an AggregatedTool from a cached tool.
        
        Applies namespace prefix and enhances description using
        the namespace.prefix_tool function.
        
        Args:
            cached_tool: Tool from cache
            backend_id: Backend identifier for prefixing
            
        Returns:
            AggregatedTool with namespace applied
        """
        # Convert CachedTool to namespace.Tool for prefixing
        tool = Tool(
            name=cached_tool.name,
            description=cached_tool.description,
            inputSchema=cached_tool.inputSchema,
        )
        
        # Apply namespace prefix
        prefixed = prefix_tool(backend_id, tool)
        
        return AggregatedTool(
            name=prefixed.name,
            description=prefixed.description,
            inputSchema=prefixed.inputSchema,
            backend=backend_id,
            original_name=cached_tool.name,
        )
    
    def get_backend_for_tool(self, namespaced_tool: str) -> str | None:
        """
        Extract backend ID from a namespaced tool name.
        
        Args:
            namespaced_tool: Tool name like "notion.search_pages"
            
        Returns:
            Backend ID or None if invalid format
        """
        if "." not in namespaced_tool:
            return None
        return namespaced_tool.split(".", 1)[0]
    
    def get_original_name(self, namespaced_tool: str) -> str | None:
        """
        Extract original tool name from namespaced tool.
        
        Args:
            namespaced_tool: Tool name like "notion.search_pages"
            
        Returns:
            Original name (e.g., "search_pages") or None if invalid
        """
        if "." not in namespaced_tool:
            return None
        return namespaced_tool.split(".", 1)[1]
    
    def find_tool(
        self,
        namespaced_tool: str,
        backends: Iterable[str] | None = None,
    ) -> AggregatedTool | None:
        """
        Find a specific tool by namespaced name.
        
        Useful for validating that a tool exists before calling it.
        
        Args:
            namespaced_tool: Tool name like "notion.search_pages"
            backends: Backends to search (defaults to registered)
            
        Returns:
            AggregatedTool or None if not found
        """
        backend_id = self.get_backend_for_tool(namespaced_tool)
        if not backend_id:
            return None
        
        original_name = self.get_original_name(namespaced_tool)
        if not original_name:
            return None
        
        # Check if backend is in search scope
        search_backends = list(backends) if backends else self._registered_backends
        if backend_id not in search_backends:
            return None
        
        # Get tools from cache
        cached_tools = self._tool_cache.get_tools(backend_id)
        if not cached_tools:
            return None
        
        # Find matching tool
        for cached_tool in cached_tools:
            if cached_tool.name == original_name:
                return self._create_aggregated_tool(cached_tool, backend_id)
        
        return None
    
    def tool_exists(
        self,
        namespaced_tool: str,
        backends: Iterable[str] | None = None,
    ) -> bool:
        """
        Check if a tool exists in the cache.
        
        Args:
            namespaced_tool: Tool name like "notion.search_pages"
            backends: Backends to search
            
        Returns:
            True if tool exists
        """
        return self.find_tool(namespaced_tool, backends) is not None


# =============================================================================
# Global Instance
# =============================================================================


_aggregator: ToolAggregator | None = None


def get_tool_aggregator() -> ToolAggregator:
    """
    Get the global ToolAggregator instance.
    
    Raises:
        RuntimeError: If aggregator not initialized
    """
    if _aggregator is None:
        raise RuntimeError(
            "ToolAggregator not initialized. Call configure_tool_aggregator() first."
        )
    return _aggregator


def configure_tool_aggregator(
    tool_cache: ToolCache,
    registered_backends: list[str] | None = None,
) -> ToolAggregator:
    """
    Initialize the global ToolAggregator.
    
    Args:
        tool_cache: ToolCache instance
        registered_backends: Initial list of backends
        
    Returns:
        Configured ToolAggregator instance
    """
    global _aggregator
    _aggregator = ToolAggregator(tool_cache, registered_backends)
    logger.info(
        "ToolAggregator configured with %d backends",
        len(registered_backends or [])
    )
    return _aggregator


def reset_tool_aggregator() -> None:
    """
    Reset the global ToolAggregator.
    
    Useful for testing or reconfiguration.
    """
    global _aggregator
    _aggregator = None
