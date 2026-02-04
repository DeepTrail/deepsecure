"""
MCP Method Handlers

This module provides handler implementations for MCP methods:
- initialize: MCP session handshake (B2)
- tools/list: List available tools (B6)
- tools/call: Execute a tool (B7)

Handlers are registered with the MCPProtocolHandler from the protocol module.
"""

from .initialize import (
    handle_initialize,
    InitializeParams,
    InitializeResult,
    SUPPORTED_PROTOCOL_VERSIONS,
    SERVER_INFO,
    SERVER_CAPABILITIES,
)

from .tools_list import (
    handle_tools_list,
    handle_tools_list_standalone,
    configure_tools_list_handler,
    ToolsListParams,
    ToolsListResult,
)

from .tools_call import (
    handle_tools_call,
    handle_tools_call_standalone,
    configure_tools_call_handler,
    ToolsCallParams,
    ToolsCallResult,
    ToolsCallErrorCode,
)

__all__ = [
    # Initialize handler (B2)
    "handle_initialize",
    "InitializeParams",
    "InitializeResult",
    "SUPPORTED_PROTOCOL_VERSIONS",
    "SERVER_INFO",
    "SERVER_CAPABILITIES",
    # Tools list handler (B6)
    "handle_tools_list",
    "handle_tools_list_standalone",
    "configure_tools_list_handler",
    "ToolsListParams",
    "ToolsListResult",
    # Tools call handler (B7)
    "handle_tools_call",
    "handle_tools_call_standalone",
    "configure_tools_call_handler",
    "ToolsCallParams",
    "ToolsCallResult",
    "ToolsCallErrorCode",
]
