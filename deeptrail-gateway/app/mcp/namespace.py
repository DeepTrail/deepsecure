"""
MCP Namespace Prefixer

This module provides utilities for namespacing tool names from multiple backend
MCP servers. When aggregating tools from multiple backends (e.g., Notion, Slack),
namespace prefixing prevents collisions and enables routing.

Pattern: {backend_id}.{tool_name}

Examples:
    - search_pages → notion.search_pages
    - send_message → slack.send_message
    - get_contact  → hubspot.get_contact

Usage:
    from app.mcp.namespace import prefix_tool_name, unprefix_tool_name
    
    # Prefix a tool name for tools/list response
    namespaced = prefix_tool_name("notion", "search_pages")
    # Returns: "notion.search_pages"
    
    # Unprefix for routing tools/call to backend
    backend_id, tool_name = unprefix_tool_name("slack.send_message")
    # Returns: ("slack", "send_message")
"""

import re
from typing import Any

from pydantic import BaseModel, Field

# =============================================================================
# Constants
# =============================================================================

# Namespace separator used between backend_id and tool_name
NAMESPACE_SEPARATOR = "."

# Valid backend ID pattern: lowercase letter followed by lowercase alphanumeric/underscore
# Examples: "notion", "slack", "hub_spot", "github_api"
BACKEND_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

# Maximum lengths for safety
MAX_BACKEND_ID_LENGTH = 64
MAX_TOOL_NAME_LENGTH = 256


# =============================================================================
# Exceptions
# =============================================================================


class NamespaceError(Exception):
    """
    Error in namespace operations.
    
    Raised when:
    - Backend ID is invalid (empty, wrong format, too long)
    - Tool name is invalid (empty, too long)
    - Namespaced name cannot be parsed
    """
    pass


# =============================================================================
# Validation Functions
# =============================================================================


def validate_backend_id(backend_id: str) -> None:
    """
    Validate backend ID format.
    
    Valid backend IDs must:
    - Not be empty
    - Start with a lowercase letter
    - Contain only lowercase letters, digits, and underscores
    - Be less than MAX_BACKEND_ID_LENGTH characters
    
    Args:
        backend_id: Backend identifier to validate
        
    Raises:
        NamespaceError: If backend_id is invalid
    
    Examples:
        >>> validate_backend_id("notion")  # OK
        >>> validate_backend_id("hub_spot")  # OK
        >>> validate_backend_id("Notion")  # Raises NamespaceError
        >>> validate_backend_id("123abc")  # Raises NamespaceError
    """
    if not backend_id:
        raise NamespaceError("Backend ID cannot be empty")
    
    if len(backend_id) > MAX_BACKEND_ID_LENGTH:
        raise NamespaceError(
            f"Backend ID too long ({len(backend_id)} chars). "
            f"Maximum is {MAX_BACKEND_ID_LENGTH} characters."
        )
    
    if not BACKEND_ID_PATTERN.match(backend_id):
        raise NamespaceError(
            f"Invalid backend ID '{backend_id}'. "
            "Must start with lowercase letter and contain only "
            "lowercase letters, digits, and underscores."
        )


def validate_tool_name(tool_name: str) -> None:
    """
    Validate tool name.
    
    Valid tool names must:
    - Not be empty
    - Not consist of only whitespace
    - Be less than MAX_TOOL_NAME_LENGTH characters
    
    Args:
        tool_name: Tool name to validate
        
    Raises:
        NamespaceError: If tool_name is invalid
    """
    if not tool_name:
        raise NamespaceError("Tool name cannot be empty")
    
    if not tool_name.strip():
        raise NamespaceError("Tool name cannot be whitespace only")
    
    if len(tool_name) > MAX_TOOL_NAME_LENGTH:
        raise NamespaceError(
            f"Tool name too long ({len(tool_name)} chars). "
            f"Maximum is {MAX_TOOL_NAME_LENGTH} characters."
        )


# =============================================================================
# Core Namespace Functions
# =============================================================================


def prefix_tool_name(backend_id: str, tool_name: str) -> str:
    """
    Add namespace prefix to a tool name.
    
    Args:
        backend_id: Backend identifier (e.g., "notion", "slack")
        tool_name: Original tool name (e.g., "search_pages")
    
    Returns:
        Namespaced tool name (e.g., "notion.search_pages")
        
    Raises:
        NamespaceError: If backend_id or tool_name is invalid
    
    Examples:
        >>> prefix_tool_name("notion", "search_pages")
        "notion.search_pages"
        >>> prefix_tool_name("hub_spot", "get_contact")
        "hub_spot.get_contact"
    """
    validate_backend_id(backend_id)
    validate_tool_name(tool_name)
    return f"{backend_id}{NAMESPACE_SEPARATOR}{tool_name}"


def unprefix_tool_name(namespaced_name: str) -> tuple[str, str]:
    """
    Remove namespace prefix from a tool name.
    
    Splits on the FIRST separator only, allowing tool names to contain dots.
    
    Args:
        namespaced_name: Namespaced tool name (e.g., "notion.search_pages")
    
    Returns:
        Tuple of (backend_id, tool_name)
        
    Raises:
        NamespaceError: If name doesn't contain valid namespace
    
    Examples:
        >>> unprefix_tool_name("slack.send_message")
        ("slack", "send_message")
        >>> unprefix_tool_name("github.repos.create")  # Tool has dots
        ("github", "repos.create")
    """
    if not namespaced_name:
        raise NamespaceError("Namespaced name cannot be empty")
    
    if NAMESPACE_SEPARATOR not in namespaced_name:
        raise NamespaceError(
            f"Invalid namespaced tool name '{namespaced_name}'. "
            f"Missing namespace separator '{NAMESPACE_SEPARATOR}'."
        )
    
    # Split on first separator only (tool names might contain dots)
    backend_id, tool_name = namespaced_name.split(NAMESPACE_SEPARATOR, 1)
    
    validate_backend_id(backend_id)
    validate_tool_name(tool_name)
    
    return backend_id, tool_name


def get_backend_from_tool_name(namespaced_name: str) -> str:
    """
    Extract just the backend ID from a namespaced tool name.
    
    This is a convenience wrapper around unprefix_tool_name for when
    you only need the backend_id.
    
    Args:
        namespaced_name: Namespaced tool name (e.g., "notion.search_pages")
    
    Returns:
        Backend ID (e.g., "notion")
        
    Raises:
        NamespaceError: If name doesn't contain valid namespace
    
    Examples:
        >>> get_backend_from_tool_name("notion.search_pages")
        "notion"
    """
    backend_id, _ = unprefix_tool_name(namespaced_name)
    return backend_id


def is_namespaced(tool_name: str) -> bool:
    """
    Check if a tool name is already namespaced.
    
    A name is considered namespaced if it contains the separator AND
    the part before the separator is a valid backend ID.
    
    Args:
        tool_name: Tool name to check
        
    Returns:
        True if the name appears to be namespaced
    
    Examples:
        >>> is_namespaced("notion.search_pages")
        True
        >>> is_namespaced("search_pages")
        False
        >>> is_namespaced("Invalid.search")  # Invalid backend ID
        False
    """
    if not tool_name or NAMESPACE_SEPARATOR not in tool_name:
        return False
    
    # Check if the prefix is a valid backend ID
    potential_backend = tool_name.split(NAMESPACE_SEPARATOR, 1)[0]
    try:
        validate_backend_id(potential_backend)
        return True
    except NamespaceError:
        return False


# =============================================================================
# Description Prefixing
# =============================================================================


def prefix_description(backend_id: str, description: str) -> str:
    """
    Add backend prefix to tool description for clarity.
    
    Converts backend_id to title case for display:
    - "notion" → "[Notion]"
    - "hub_spot" → "[Hub Spot]"
    
    Args:
        backend_id: Backend identifier (e.g., "notion")
        description: Original description
    
    Returns:
        Prefixed description (e.g., "[Notion] Search pages in workspace")
    
    Examples:
        >>> prefix_description("notion", "Search pages")
        "[Notion] Search pages"
        >>> prefix_description("hub_spot", "Get contact")
        "[Hub Spot] Get contact"
    """
    validate_backend_id(backend_id)
    
    # Convert backend_id to display name (title case, underscores to spaces)
    display_name = backend_id.replace("_", " ").title()
    
    if not description:
        return f"[{display_name}]"
    
    return f"[{display_name}] {description}"


# =============================================================================
# Tool Model and Operations
# =============================================================================


class Tool(BaseModel):
    """
    MCP Tool representation.
    
    This model represents a tool as returned by the tools/list method.
    
    Attributes:
        name: Tool name (may be namespaced or not)
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


def prefix_tool(backend_id: str, tool: Tool) -> Tool:
    """
    Create a new tool with namespaced name and description.
    
    The input schema is preserved unchanged.
    
    Args:
        backend_id: Backend identifier
        tool: Original tool from backend
    
    Returns:
        New Tool with prefixed name and description
        
    Raises:
        NamespaceError: If backend_id is invalid
    
    Examples:
        >>> tool = Tool(name="search", description="Search items")
        >>> prefixed = prefix_tool("notion", tool)
        >>> prefixed.name
        "notion.search"
        >>> prefixed.description
        "[Notion] Search items"
    """
    return Tool(
        name=prefix_tool_name(backend_id, tool.name),
        description=prefix_description(backend_id, tool.description),
        inputSchema=tool.inputSchema,
    )


def prefix_tools(backend_id: str, tools: list[Tool]) -> list[Tool]:
    """
    Prefix a list of tools with backend namespace.
    
    Args:
        backend_id: Backend identifier
        tools: List of original tools from backend
    
    Returns:
        List of tools with prefixed names and descriptions
        
    Raises:
        NamespaceError: If backend_id is invalid
    
    Examples:
        >>> tools = [
        ...     Tool(name="search", description="Search"),
        ...     Tool(name="read", description="Read item")
        ... ]
        >>> prefixed = prefix_tools("notion", tools)
        >>> [t.name for t in prefixed]
        ["notion.search", "notion.read"]
    """
    return [prefix_tool(backend_id, tool) for tool in tools]


def unprefix_tool(tool: Tool) -> tuple[str, Tool]:
    """
    Remove namespace prefix from a tool.
    
    Args:
        tool: Namespaced tool
        
    Returns:
        Tuple of (backend_id, unprefixed_tool)
        
    Raises:
        NamespaceError: If tool name is not properly namespaced
    """
    backend_id, original_name = unprefix_tool_name(tool.name)
    
    # Remove the [Backend] prefix from description if present
    description = tool.description
    display_name = backend_id.replace("_", " ").title()
    prefix = f"[{display_name}] "
    if description.startswith(prefix):
        description = description[len(prefix):]
    
    unprefixed = Tool(
        name=original_name,
        description=description,
        inputSchema=tool.inputSchema,
    )
    
    return backend_id, unprefixed
