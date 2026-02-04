"""
MCP (Model Context Protocol) module for DeepTrail Gateway.

This module provides JSON-RPC 2.0 protocol handling for MCP communication,
allowing AI agents to connect to the Virtual MCP Server through a unified interface.

Components:
- MCPProtocolHandler: Main protocol handler for JSON-RPC 2.0 requests
- JsonRpcRequest: Request model for incoming MCP requests
- JsonRpcResponse: Response model for outgoing MCP responses
- JsonRpcErrorCode: Standard JSON-RPC 2.0 and MCP-specific error codes
- Namespace utilities: Tool name prefixing for multi-backend aggregation
- Session Manager: Track MCP sessions per agent and backend
"""

from .protocol import (
    MCPProtocolHandler,
    JsonRpcRequest,
    JsonRpcResponse,
    JsonRpcError,
    JsonRpcErrorCode,
    MCPMethod,
)

from .namespace import (
    # Constants
    NAMESPACE_SEPARATOR,
    # Exceptions
    NamespaceError,
    # Core functions
    prefix_tool_name,
    unprefix_tool_name,
    get_backend_from_tool_name,
    is_namespaced,
    # Description
    prefix_description,
    # Tool operations
    Tool,
    prefix_tool,
    prefix_tools,
    unprefix_tool,
)

from .session_manager import (
    # Enums
    SessionState,
    # Data classes
    CredentialRef,
    BackendMCPSession,
    AgentMCPSession,
    # Manager
    MCPSessionManager,
)

from .tool_cache import (
    # Models
    CachedTool,
    CacheEntry,
    CacheStats,
    # Cache
    ToolCache,
    # Global instance
    get_tool_cache,
    reset_global_cache,
)

from .permission_mapper import (
    PermissionMapper,
)

from .aggregator import (
    AggregatedTool,
    AggregationResult,
    ToolAggregator,
    configure_tool_aggregator,
    get_tool_aggregator,
    reset_tool_aggregator,
)

__all__ = [
    # Protocol
    "MCPProtocolHandler",
    "JsonRpcRequest",
    "JsonRpcResponse",
    "JsonRpcError",
    "JsonRpcErrorCode",
    "MCPMethod",
    # Namespace
    "NAMESPACE_SEPARATOR",
    "NamespaceError",
    "prefix_tool_name",
    "unprefix_tool_name",
    "get_backend_from_tool_name",
    "is_namespaced",
    "prefix_description",
    "Tool",
    "prefix_tool",
    "prefix_tools",
    "unprefix_tool",
    # Session Manager
    "SessionState",
    "CredentialRef",
    "BackendMCPSession",
    "AgentMCPSession",
    "MCPSessionManager",
    # Tool Cache
    "CachedTool",
    "CacheEntry",
    "CacheStats",
    "ToolCache",
    "get_tool_cache",
    "reset_global_cache",
    # Permission Mapper
    "PermissionMapper",
    # Aggregator
    "AggregatedTool",
    "AggregationResult",
    "ToolAggregator",
    "configure_tool_aggregator",
    "get_tool_aggregator",
    "reset_tool_aggregator",
]
