"""
Backend Connectors Package

Provides connection management and MCP clients for backend servers.

Main Components:
- BackendConnectionManager: Manages connections, pooling, health checks
- BaseMCPClient: Abstract base class for backend MCP clients
- GenericMCPClient: Generic client for testing/MVP
- BackendConfig: Configuration for a backend server
- MCPRequest/MCPResponse: Request/response wrappers

Usage:
    from app.backends import (
        BackendConnectionManager,
        BackendConfig,
        BaseMCPClient,
        GenericMCPClient,
        create_mcp_client,
    )
"""

from .connection_manager import (
    # Enums
    BackendStatus,
    RequestMethod,
    # Data Classes
    BackendConfig,
    BackendState,
    MCPRequest,
    MCPResponse,
    # Exceptions
    BackendError,
    BackendNotFoundError,
    BackendUnavailableError,
    BackendTimeoutError,
    BackendRequestError,
    # Manager
    BackendConnectionManager,
    # Factory
    create_default_manager,
)

from .base_mcp_client import (
    # Enums
    MCPCapability,
    ToolCallStatus,
    # Data Classes
    ServerInfo,
    ToolSchema,
    ToolResult,
    # Exceptions
    MCPClientError,
    MCPInitializeError,
    MCPToolNotFoundError,
    MCPToolCallError,
    # Base Class
    BaseMCPClient,
    # Generic Implementation
    GenericMCPClient,
    # Factory
    create_mcp_client,
)

__all__ = [
    # Connection Manager Enums
    "BackendStatus",
    "RequestMethod",
    # Connection Manager Data Classes
    "BackendConfig",
    "BackendState",
    "MCPRequest",
    "MCPResponse",
    # Connection Manager Exceptions
    "BackendError",
    "BackendNotFoundError",
    "BackendUnavailableError",
    "BackendTimeoutError",
    "BackendRequestError",
    # Connection Manager
    "BackendConnectionManager",
    "create_default_manager",
    # MCP Client Enums
    "MCPCapability",
    "ToolCallStatus",
    # MCP Client Data Classes
    "ServerInfo",
    "ToolSchema",
    "ToolResult",
    # MCP Client Exceptions
    "MCPClientError",
    "MCPInitializeError",
    "MCPToolNotFoundError",
    "MCPToolCallError",
    # MCP Client Classes
    "BaseMCPClient",
    "GenericMCPClient",
    "create_mcp_client",
]
