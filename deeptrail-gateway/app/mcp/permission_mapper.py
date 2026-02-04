"""
Tool to Permission Mapping for Virtual MCP Server.

Maps MCP tool names to permission strings for filtering. This is used by
the tools/list handler (B6) to filter tools by delegated permissions, and
by tools/call handler (B7) to validate permission before execution.

Convention:
- Tool name: {backend}.{operation}
- Permission: {backend}:{resource}:{action}

Examples:
- notion.search_pages → notion:pages:search
- slack.send_message → slack:messages:send

Usage:
    from app.mcp.permission_mapper import PermissionMapper
    
    # Get permission for a tool
    perm = PermissionMapper.get_permission("notion.search_pages")
    # Returns: "notion:pages:search"
    
    # Check if tool is permitted
    if PermissionMapper.is_tool_permitted("notion.search_pages", permissions):
        # Tool is allowed
    
    # Filter tools by permissions
    filtered = PermissionMapper.filter_tools(tools, permissions)
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class PermissionMapper:
    """
    Maps tool names to permission strings.
    
    Used by:
    - tools/list handler (B6): Filter tools by delegated permissions
    - tools/call handler (B7): Validate permission before execution
    
    Security:
    - Unknown tools are denied by default (fail-closed)
    - All permission checks are logged for audit
    """
    
    # Static mapping for MVP backends
    # Production: Load from configuration or database
    TOOL_TO_PERMISSION: dict[str, str] = {
        # Notion tools
        "notion.search_pages": "notion:pages:search",
        "notion.read_page": "notion:pages:read",
        "notion.create_page": "notion:pages:create",
        "notion.update_page": "notion:pages:update",
        "notion.delete_page": "notion:pages:delete",
        "notion.list_databases": "notion:databases:list",
        "notion.query_database": "notion:databases:query",
        
        # Slack tools
        "slack.search_messages": "slack:messages:search",
        "slack.send_message": "slack:messages:send",
        "slack.list_channels": "slack:channels:list",
        "slack.join_channel": "slack:channels:join",
        "slack.post_reaction": "slack:reactions:write",
        "slack.list_users": "slack:users:list",
        
        # HubSpot tools (Phase 2)
        "hubspot.get_contact": "hubspot:contacts:read",
        "hubspot.create_contact": "hubspot:contacts:create",
        "hubspot.update_contact": "hubspot:contacts:update",
        "hubspot.list_contacts": "hubspot:contacts:list",
        "hubspot.list_deals": "hubspot:deals:list",
        "hubspot.create_deal": "hubspot:deals:create",
        "hubspot.update_deal": "hubspot:deals:update",
    }
    
    # Reverse mapping for validation
    PERMISSION_TO_TOOLS: dict[str, list[str]] = {}
    
    @classmethod
    def _build_reverse_mapping(cls) -> None:
        """Build reverse mapping from permission to tools."""
        if not cls.PERMISSION_TO_TOOLS:
            for tool, perm in cls.TOOL_TO_PERMISSION.items():
                if perm not in cls.PERMISSION_TO_TOOLS:
                    cls.PERMISSION_TO_TOOLS[perm] = []
                cls.PERMISSION_TO_TOOLS[perm].append(tool)
    
    @classmethod
    def get_permission(cls, tool_name: str) -> str | None:
        """
        Get the permission string required for a tool.
        
        Args:
            tool_name: Namespaced tool name (e.g., "notion.search_pages")
            
        Returns:
            Permission string (e.g., "notion:pages:search") or None if unknown
        
        Examples:
            >>> PermissionMapper.get_permission("notion.search_pages")
            "notion:pages:search"
            >>> PermissionMapper.get_permission("unknown.tool")
            None
        """
        return cls.TOOL_TO_PERMISSION.get(tool_name)
    
    @classmethod
    def infer_permission(cls, tool_name: str) -> str | None:
        """
        Infer permission from tool name if not in static mapping.
        
        Uses convention: {backend}.{action}_{resource} → {backend}:{resource}:{action}
        
        Args:
            tool_name: Namespaced tool name (e.g., "github.list_repos")
            
        Returns:
            Inferred permission string or None if cannot infer
        
        Examples:
            >>> PermissionMapper.infer_permission("github.list_repos")
            "github:repos:list"
            >>> PermissionMapper.infer_permission("notion.search_pages")
            "notion:pages:search"  # From static mapping
        """
        # First check static mapping
        static = cls.get_permission(tool_name)
        if static:
            return static
        
        # Try to infer: backend.action_resource → backend:resource:action
        match = re.match(r"^([^.]+)\.([^_]+)_(.+)$", tool_name)
        if match:
            backend, action, resource = match.groups()
            inferred = f"{backend}:{resource}:{action}"
            logger.debug(f"Inferred permission for {tool_name}: {inferred}")
            return inferred
        
        logger.debug(f"Could not infer permission for {tool_name}")
        return None
    
    @classmethod
    def is_tool_permitted(
        cls,
        tool_name: str,
        delegated_permissions: list[str],
    ) -> bool:
        """
        Check if a tool is allowed by delegated permissions.
        
        Security: Unknown tools are denied by default (fail-closed).
        
        Args:
            tool_name: Namespaced tool name (e.g., "notion.search_pages")
            delegated_permissions: List of permission strings the agent has
            
        Returns:
            True if tool is permitted, False otherwise
        
        Examples:
            >>> perms = ["notion:pages:search", "slack:channels:list"]
            >>> PermissionMapper.is_tool_permitted("notion.search_pages", perms)
            True
            >>> PermissionMapper.is_tool_permitted("notion.create_page", perms)
            False
        """
        required_permission = cls.get_permission(tool_name)
        
        if required_permission is None:
            # Unknown tool - deny by default (fail-closed)
            logger.warning(f"Permission denied for unknown tool: {tool_name}")
            return False
        
        is_permitted = required_permission in delegated_permissions
        
        if not is_permitted:
            logger.debug(
                f"Tool {tool_name} requires {required_permission}, "
                f"not in delegated permissions"
            )
        
        return is_permitted
    
    @classmethod
    def filter_tools(
        cls,
        tools: list[dict[str, Any]],
        delegated_permissions: list[str],
    ) -> list[dict[str, Any]]:
        """
        Filter a list of tools to only those permitted.
        
        Args:
            tools: List of tool schemas (with 'name' field)
            delegated_permissions: List of permission strings
            
        Returns:
            Filtered list of permitted tools
        
        Examples:
            >>> tools = [
            ...     {"name": "notion.search_pages"},
            ...     {"name": "notion.create_page"},
            ... ]
            >>> perms = ["notion:pages:search"]
            >>> filtered = PermissionMapper.filter_tools(tools, perms)
            >>> [t["name"] for t in filtered]
            ["notion.search_pages"]
        """
        filtered = []
        for tool in tools:
            tool_name = tool.get("name", "")
            if cls.is_tool_permitted(tool_name, delegated_permissions):
                filtered.append(tool)
        
        logger.debug(
            f"Filtered {len(filtered)}/{len(tools)} tools by permissions"
        )
        return filtered
    
    @classmethod
    def get_all_tools_for_permission(cls, permission: str) -> list[str]:
        """
        Get all tools that require a specific permission.
        
        Args:
            permission: Permission string (e.g., "notion:pages:search")
            
        Returns:
            List of tool names that require this permission
        """
        cls._build_reverse_mapping()
        return cls.PERMISSION_TO_TOOLS.get(permission, [])
    
    @classmethod
    def get_all_permissions(cls) -> list[str]:
        """Get list of all known permissions."""
        return list(set(cls.TOOL_TO_PERMISSION.values()))
    
    @classmethod
    def get_all_tools(cls) -> list[str]:
        """Get list of all known tools."""
        return list(cls.TOOL_TO_PERMISSION.keys())
    
    @classmethod
    def get_backend_permissions(cls, backend_id: str) -> list[str]:
        """
        Get all permissions for a specific backend.
        
        Args:
            backend_id: Backend identifier (e.g., "notion")
            
        Returns:
            List of permissions for that backend
        """
        prefix = f"{backend_id}:"
        return [p for p in cls.get_all_permissions() if p.startswith(prefix)]
    
    @classmethod
    def get_backend_tools(cls, backend_id: str) -> list[str]:
        """
        Get all tools for a specific backend.
        
        Args:
            backend_id: Backend identifier (e.g., "notion")
            
        Returns:
            List of tool names for that backend
        """
        prefix = f"{backend_id}."
        return [t for t in cls.get_all_tools() if t.startswith(prefix)]
    
    @classmethod
    def add_mapping(cls, tool_name: str, permission: str) -> None:
        """
        Add a tool→permission mapping dynamically.
        
        Useful for testing or runtime configuration.
        
        Args:
            tool_name: Namespaced tool name
            permission: Permission string
        """
        cls.TOOL_TO_PERMISSION[tool_name] = permission
        # Invalidate reverse mapping
        cls.PERMISSION_TO_TOOLS = {}
        logger.debug(f"Added mapping: {tool_name} → {permission}")
    
    @classmethod
    def remove_mapping(cls, tool_name: str) -> bool:
        """
        Remove a tool→permission mapping.
        
        Args:
            tool_name: Namespaced tool name to remove
            
        Returns:
            True if mapping existed and was removed
        """
        if tool_name in cls.TOOL_TO_PERMISSION:
            del cls.TOOL_TO_PERMISSION[tool_name]
            # Invalidate reverse mapping
            cls.PERMISSION_TO_TOOLS = {}
            logger.debug(f"Removed mapping for: {tool_name}")
            return True
        return False
