"""
MCP tools/list Request Handler for Virtual MCP Server.

Handles the MCP `tools/list` method by:
1. Getting tools from the agent's session (pre-computed during session creation)
2. Optionally filtering by delegated permissions (defense in depth)
3. Returning the filtered, namespaced tool list

This is the core handler demonstrating the "filtered visibility" value proposition:
Agent sees 4 tools, not 20+.

MCP Specification Reference:
https://spec.modelcontextprotocol.io/specification/server/tools/

Usage:
    from app.mcp.handlers import handle_tools_list
    from app.mcp.protocol import MCPProtocolHandler, MCPMethod
    
    handler = MCPProtocolHandler()
    handler.register_handler(MCPMethod.TOOLS_LIST, handle_tools_list)

Response Format:
    {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "tools": [
                {
                    "name": "notion.search_pages",
                    "description": "[Notion] Search pages in workspace",
                    "inputSchema": { ... }
                }
            ]
        }
    }
"""

import logging
from typing import Any

from pydantic import BaseModel, Field

from ..namespace import Tool, prefix_tool
from ..permission_mapper import PermissionMapper
from ..protocol import JsonRpcErrorCode, MCPError
from ..session_manager import MCPSessionManager
from ..tool_cache import CachedTool, ToolCache

logger = logging.getLogger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================


class ToolsListParams(BaseModel):
    """
    Parameters for the MCP tools/list request.
    
    The tools/list method takes no required parameters, but may include
    optional cursor for pagination (not implemented in MVP).
    """
    cursor: str | None = Field(default=None, description="Optional pagination cursor")
    
    model_config = {"extra": "allow"}  # Allow additional fields


class ToolsListResult(BaseModel):
    """
    Result for the MCP tools/list response.
    
    Attributes:
        tools: List of available tools
        nextCursor: Optional cursor for pagination (not implemented in MVP)
    """
    tools: list[dict[str, Any]] = Field(default_factory=list, description="Available tools")
    nextCursor: str | None = Field(default=None, alias="nextCursor", description="Pagination cursor")
    
    model_config = {"populate_by_name": True}


# =============================================================================
# Handler Dependencies
# =============================================================================


# Global instances - will be set during app initialization
_session_manager: MCPSessionManager | None = None
_tool_cache: ToolCache | None = None


def configure_tools_list_handler(
    session_manager: MCPSessionManager,
    tool_cache: ToolCache,
) -> None:
    """
    Configure the tools/list handler with required dependencies.
    
    Must be called during app initialization before handling requests.
    
    Args:
        session_manager: MCP session manager instance
        tool_cache: Tool schema cache instance
    """
    global _session_manager, _tool_cache
    _session_manager = session_manager
    _tool_cache = tool_cache
    logger.info("tools/list handler configured")


def get_session_manager() -> MCPSessionManager:
    """Get the configured session manager."""
    if _session_manager is None:
        raise RuntimeError("tools/list handler not configured. Call configure_tools_list_handler() first.")
    return _session_manager


def get_tool_cache() -> ToolCache:
    """Get the configured tool cache."""
    if _tool_cache is None:
        raise RuntimeError("tools/list handler not configured. Call configure_tools_list_handler() first.")
    return _tool_cache


# =============================================================================
# Handler Implementation
# =============================================================================


async def handle_tools_list(params: dict[str, Any]) -> dict[str, Any]:
    """
    Handle MCP tools/list request.
    
    Returns the list of tools available to the agent, filtered by their
    delegated permissions. Tools are pre-namespaced (e.g., "notion.search_pages").
    
    The handler gets tools from the agent's session, which were pre-computed
    during session creation (B3). This provides:
    - Fast response (no backend calls)
    - Consistent tool list for session lifetime
    - Permission enforcement at session creation
    
    Args:
        params: Request parameters (may include _context from middleware):
            - cursor: Optional pagination cursor (not implemented)
            - _context: Request context from middleware containing:
                - agent_session_id: Agent's session ID
                - delegator: User who delegated permissions
                - delegated_permissions: List of permission strings
    
    Returns:
        tools/list result containing:
            - tools: List of tool schemas (name, description, inputSchema)
            - nextCursor: Pagination cursor (null in MVP)
    
    Raises:
        MCPError: If session not found or handler not configured
    
    Example:
        >>> await handle_tools_list({
        ...     "_context": {
        ...         "agent_session_id": "agent-123",
        ...         "delegated_permissions": ["notion:pages:search"]
        ...     }
        ... })
        {
            "tools": [
                {"name": "notion.search_pages", "description": "[Notion] Search pages", ...}
            ],
            "nextCursor": null
        }
    """
    # Extract context (passed by middleware/protocol handler)
    context = params.pop("_context", {})
    agent_session_id = context.get("agent_session_id")
    delegated_permissions = context.get("delegated_permissions", [])
    
    logger.debug(f"tools/list request for session: {agent_session_id}")
    
    # Get session manager
    try:
        session_manager = get_session_manager()
    except RuntimeError as e:
        logger.error(f"Handler not configured: {e}")
        raise MCPError(
            JsonRpcErrorCode.INTERNAL_ERROR,
            "Server configuration error"
        )
    
    # Get agent session
    if not agent_session_id:
        # No session context - return empty tools (unauthenticated)
        logger.warning("tools/list called without agent session")
        return ToolsListResult(tools=[]).model_dump(by_alias=True)
    
    agent_session = session_manager.get_agent_session(agent_session_id)
    if not agent_session:
        logger.warning(f"Agent session not found: {agent_session_id}")
        raise MCPError(
            JsonRpcErrorCode.INVALID_REQUEST,
            "Session not found. Call initialize first."
        )
    
    # Get tools from session (pre-computed during session creation)
    allowed_tools = session_manager.get_allowed_tools(agent_session_id)
    
    logger.debug(f"Session has {len(allowed_tools)} allowed tools")
    
    # Build tool schemas for response
    tools = await _build_tool_schemas(allowed_tools, delegated_permissions)
    
    logger.info(
        f"tools/list returning {len(tools)} tools for agent session {agent_session_id}"
    )
    
    # Build response
    result = ToolsListResult(tools=tools)
    return result.model_dump(by_alias=True)


async def _build_tool_schemas(
    allowed_tools: list[str],
    delegated_permissions: list[str],
) -> list[dict[str, Any]]:
    """
    Build tool schemas for the response.
    
    For each allowed tool:
    1. Get schema from cache (if available)
    2. Apply additional permission check (defense in depth)
    3. Build response schema
    
    Args:
        allowed_tools: List of namespaced tool names from session
        delegated_permissions: Agent's delegated permissions
    
    Returns:
        List of tool schema dicts
    """
    tool_cache = get_tool_cache()
    schemas: list[dict[str, Any]] = []
    
    for namespaced_name in allowed_tools:
        # Defense in depth: double-check permission
        if not PermissionMapper.is_tool_permitted(namespaced_name, delegated_permissions):
            logger.warning(
                f"Tool {namespaced_name} in session but not permitted - skipping"
            )
            continue
        
        # Extract backend and original tool name
        if "." not in namespaced_name:
            logger.warning(f"Invalid tool name (no namespace): {namespaced_name}")
            continue
        
        backend_id, original_name = namespaced_name.split(".", 1)
        
        # Try to get schema from cache
        cached_tools = tool_cache.get_tools(backend_id)
        tool_schema = _find_tool_schema(cached_tools, original_name)
        
        # Build schema for response
        if tool_schema:
            schema = _build_single_tool_schema(backend_id, tool_schema)
        else:
            # Minimal schema if not in cache
            schema = _build_minimal_tool_schema(backend_id, original_name)
        
        schemas.append(schema)
    
    return schemas


def _find_tool_schema(
    cached_tools: list[CachedTool],
    tool_name: str,
) -> CachedTool | None:
    """Find a tool schema by name in cached tools."""
    for tool in cached_tools:
        if tool.name == tool_name:
            return tool
    return None


def _build_single_tool_schema(
    backend_id: str,
    cached_tool: CachedTool,
) -> dict[str, Any]:
    """
    Build a tool schema dict from cached tool.
    
    Applies namespace prefix and enhances description.
    
    Args:
        backend_id: Backend identifier
        cached_tool: Cached tool schema
    
    Returns:
        Tool schema dict for response
    """
    # Create a Tool from CachedTool and prefix it
    tool = Tool(
        name=cached_tool.name,
        description=cached_tool.description,
        inputSchema=cached_tool.inputSchema,
    )
    
    # Apply namespace prefix
    prefixed = prefix_tool(backend_id, tool)
    
    return prefixed.model_dump(by_alias=True)


def _build_minimal_tool_schema(
    backend_id: str,
    tool_name: str,
) -> dict[str, Any]:
    """
    Build minimal tool schema when not in cache.
    
    Used as fallback when tool cache doesn't have the schema.
    
    Args:
        backend_id: Backend identifier
        tool_name: Original tool name
    
    Returns:
        Minimal tool schema dict
    """
    backend_label = backend_id.replace("_", " ").title()
    namespaced_name = f"{backend_id}.{tool_name}"
    
    return {
        "name": namespaced_name,
        "description": f"[{backend_label}] {tool_name}",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    }


# =============================================================================
# Standalone Handler (without dependency injection)
# =============================================================================


async def handle_tools_list_standalone(
    params: dict[str, Any],
    session_manager: MCPSessionManager,
    tool_cache: ToolCache,
) -> dict[str, Any]:
    """
    Handle tools/list with explicit dependencies (for testing).
    
    This is an alternative to the global-configured handler,
    allowing explicit dependency injection for tests.
    
    Args:
        params: Request parameters
        session_manager: Session manager instance
        tool_cache: Tool cache instance
    
    Returns:
        tools/list result
    """
    global _session_manager, _tool_cache
    
    # Temporarily configure globals
    old_sm, old_tc = _session_manager, _tool_cache
    configure_tools_list_handler(session_manager, tool_cache)
    
    try:
        return await handle_tools_list(params)
    finally:
        # Restore globals
        _session_manager, _tool_cache = old_sm, old_tc
