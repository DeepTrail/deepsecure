"""
Base MCP Client

Abstract base class for backend MCP server clients. Provides standardized
interface for MCP protocol operations (initialize, tools/list, tools/call)
while allowing backend-specific customizations.

Architecture:
- BaseMCPClient defines the interface and common behavior
- Concrete clients (NotionMCPClient, SlackMCPClient) extend for specifics
- Uses BackendConnectionManager for actual HTTP transport

Usage:
    # Create concrete implementation
    class NotionMCPClient(BaseMCPClient):
        @property
        def backend_id(self) -> str:
            return "notion"
        
        def transform_tool_result(self, tool_name, result):
            # Notion-specific result processing
            return result
    
    # Use the client
    client = NotionMCPClient(connection_manager)
    tools = await client.list_tools(auth_token="Bearer xyz")
    result = await client.call_tool("search_pages", {"query": "test"}, auth_token="Bearer xyz")
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypeVar

from .connection_manager import (
    BackendConnectionManager,
    BackendError,
    BackendTimeoutError,
    BackendUnavailableError,
    MCPResponse,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Enums and Constants
# =============================================================================


class MCPCapability(str, Enum):
    """MCP server capabilities."""
    TOOLS = "tools"
    RESOURCES = "resources"
    PROMPTS = "prompts"
    LOGGING = "logging"


class ToolCallStatus(str, Enum):
    """Status of a tool call."""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    UNAUTHORIZED = "unauthorized"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ServerInfo:
    """
    Information about a backend MCP server.
    
    Populated from the initialize response.
    
    Attributes:
        name: Server name (e.g., "Notion MCP Server")
        version: Server version (e.g., "1.0.0")
        protocol_version: MCP protocol version (e.g., "2024-11-05")
        capabilities: List of supported capabilities
        raw: Raw server info dict from response
    """
    name: str
    version: str
    protocol_version: str = "2024-11-05"
    capabilities: list[MCPCapability] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServerInfo":
        """Parse from initialize response serverInfo."""
        capabilities = []
        caps_data = data.get("capabilities", {})
        # Check if key exists (empty dict means capability is present)
        if "tools" in caps_data:
            capabilities.append(MCPCapability.TOOLS)
        if "resources" in caps_data:
            capabilities.append(MCPCapability.RESOURCES)
        if "prompts" in caps_data:
            capabilities.append(MCPCapability.PROMPTS)
        if "logging" in caps_data:
            capabilities.append(MCPCapability.LOGGING)
        
        return cls(
            name=data.get("name", "Unknown"),
            version=data.get("version", "0.0.0"),
            protocol_version=data.get("protocolVersion", "2024-11-05"),
            capabilities=capabilities,
            raw=data,
        )


@dataclass
class ToolSchema:
    """
    Schema for a single MCP tool.
    
    Attributes:
        name: Tool name (without namespace prefix)
        description: Human-readable description
        input_schema: JSON Schema for tool inputs
        raw: Raw tool dict from backend
    """
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolSchema":
        """Parse from tools/list response item."""
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            input_schema=data.get("inputSchema", {}),
            raw=data,
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to MCP tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass
class ToolResult:
    """
    Result from a tools/call invocation.
    
    Attributes:
        status: Call status (success, error, etc.)
        content: Result content (list of content items)
        is_error: Whether the tool returned an error
        error_message: Error message if is_error
        raw: Raw response from backend
        duration_ms: Call duration in milliseconds
    """
    status: ToolCallStatus
    content: list[dict[str, Any]] = field(default_factory=list)
    is_error: bool = False
    error_message: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    duration_ms: float | None = None
    
    @classmethod
    def from_response(
        cls,
        response: MCPResponse,
        duration_ms: float | None = None,
    ) -> "ToolResult":
        """Parse from MCP response."""
        if not response.is_success:
            error = response.error or {}
            return cls(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message=error.get("message", "Unknown error"),
                raw=response.raw,
                duration_ms=duration_ms,
            )
        
        result = response.result or {}
        content = result.get("content", [])
        is_error = result.get("isError", False)
        
        return cls(
            status=ToolCallStatus.ERROR if is_error else ToolCallStatus.SUCCESS,
            content=content,
            is_error=is_error,
            error_message=content[0].get("text") if is_error and content else None,
            raw=response.raw,
            duration_ms=duration_ms,
        )
    
    @classmethod
    def from_error(cls, status: ToolCallStatus, message: str) -> "ToolResult":
        """Create error result."""
        return cls(
            status=status,
            is_error=True,
            error_message=message,
            content=[{"type": "text", "text": message}],
        )
    
    def get_text_content(self) -> str:
        """Extract text content from result."""
        texts = []
        for item in self.content:
            if item.get("type") == "text":
                texts.append(item.get("text", ""))
        return "\n".join(texts)


# =============================================================================
# Exceptions
# =============================================================================


class MCPClientError(Exception):
    """Base exception for MCP client errors."""
    pass


class MCPInitializeError(MCPClientError):
    """Failed to initialize MCP session with backend."""
    pass


class MCPToolNotFoundError(MCPClientError):
    """Requested tool not found on backend."""
    pass


class MCPToolCallError(MCPClientError):
    """Tool call failed."""
    pass


# =============================================================================
# Base MCP Client
# =============================================================================


class BaseMCPClient(ABC):
    """
    Abstract base class for backend MCP clients.
    
    Provides common interface for MCP protocol operations while allowing
    backend-specific customizations through abstract methods and hooks.
    
    Subclasses must implement:
    - backend_id: Property returning the backend identifier
    
    Subclasses may override:
    - transform_tool_result: Process tool results before returning
    - get_default_headers: Add backend-specific headers
    - validate_tool_arguments: Validate arguments before sending
    
    Usage:
        class NotionMCPClient(BaseMCPClient):
            @property
            def backend_id(self) -> str:
                return "notion"
        
        client = NotionMCPClient(connection_manager)
        await client.initialize(auth_token="Bearer xyz")
        tools = await client.list_tools(auth_token="Bearer xyz")
        result = await client.call_tool("search_pages", {...}, auth_token="Bearer xyz")
    """
    
    def __init__(
        self,
        connection_manager: BackendConnectionManager,
        *,
        auto_initialize: bool = False,
    ) -> None:
        """
        Initialize MCP client.
        
        Args:
            connection_manager: Backend connection manager for HTTP transport
            auto_initialize: If True, automatically initialize on first request
        """
        self._connection_manager = connection_manager
        self._auto_initialize = auto_initialize
        self._server_info: ServerInfo | None = None
        self._initialized = False
        self._tools_cache: list[ToolSchema] | None = None
    
    # ─────────────────────────────────────────────────────────────────────────
    # Abstract Properties
    # ─────────────────────────────────────────────────────────────────────────
    
    @property
    @abstractmethod
    def backend_id(self) -> str:
        """
        Return the backend identifier.
        
        This must match the backend_id registered with BackendConnectionManager.
        
        Returns:
            Backend identifier (e.g., "notion", "slack", "hubspot")
        """
        pass
    
    # ─────────────────────────────────────────────────────────────────────────
    # Properties
    # ─────────────────────────────────────────────────────────────────────────
    
    @property
    def is_initialized(self) -> bool:
        """Check if client has completed initialize handshake."""
        return self._initialized
    
    @property
    def server_info(self) -> ServerInfo | None:
        """Get server info from last initialize (or None if not initialized)."""
        return self._server_info
    
    @property
    def connection_manager(self) -> BackendConnectionManager:
        """Get the connection manager."""
        return self._connection_manager
    
    # ─────────────────────────────────────────────────────────────────────────
    # MCP Protocol Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    async def initialize(
        self,
        auth_token: str | None = None,
        client_info: dict[str, Any] | None = None,
    ) -> ServerInfo:
        """
        Initialize MCP session with backend.
        
        Performs the MCP initialize handshake to establish capabilities
        and protocol version with the backend server.
        
        Args:
            auth_token: Authorization token (e.g., "Bearer xyz")
            client_info: Client information to send to backend
            
        Returns:
            ServerInfo from backend
            
        Raises:
            MCPInitializeError: If initialization fails
        """
        if client_info is None:
            client_info = {
                "name": "DeepTrail Gateway",
                "version": "1.0.0",
            }
        
        try:
            response = await self._connection_manager.send_initialize(
                backend_id=self.backend_id,
                client_info=client_info,
                auth_header=auth_token,
            )
            
            if not response.is_success:
                error_msg = (
                    response.error.get("message", "Unknown error")
                    if response.error
                    else "Unknown error"
                )
                raise MCPInitializeError(f"Initialize failed: {error_msg}")
            
            result = response.result or {}
            server_info_data = result.get("serverInfo", result)
            
            self._server_info = ServerInfo.from_dict(server_info_data)
            self._initialized = True
            
            logger.info(
                "Initialized MCP session with %s: %s v%s",
                self.backend_id,
                self._server_info.name,
                self._server_info.version,
            )
            
            return self._server_info
            
        except BackendError as e:
            raise MCPInitializeError(f"Initialize failed: {e}") from e
    
    async def list_tools(
        self,
        auth_token: str | None = None,
        *,
        use_cache: bool = True,
        force_refresh: bool = False,
    ) -> list[ToolSchema]:
        """
        List available tools from backend.
        
        Args:
            auth_token: Authorization token
            use_cache: Use cached tools if available
            force_refresh: Force refresh even if cached
            
        Returns:
            List of ToolSchema objects
            
        Raises:
            MCPClientError: If request fails
        """
        # Check cache
        if use_cache and not force_refresh and self._tools_cache is not None:
            return self._tools_cache
        
        # Auto-initialize if needed
        if self._auto_initialize and not self._initialized:
            await self.initialize(auth_token=auth_token)
        
        try:
            response = await self._connection_manager.send_tools_list(
                backend_id=self.backend_id,
                auth_header=auth_token,
            )
            
            if not response.is_success:
                error_msg = (
                    response.error.get("message", "Unknown error")
                    if response.error
                    else "Unknown error"
                )
                raise MCPClientError(f"tools/list failed: {error_msg}")
            
            result = response.result or {}
            tools_data = result.get("tools", [])
            
            tools = [ToolSchema.from_dict(t) for t in tools_data]
            
            # Cache results
            if use_cache:
                self._tools_cache = tools
            
            logger.debug("Listed %d tools from %s", len(tools), self.backend_id)
            
            return tools
            
        except BackendError as e:
            raise MCPClientError(f"tools/list failed: {e}") from e
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Execute a tool on the backend.
        
        Args:
            tool_name: Tool name (without namespace prefix)
            arguments: Tool arguments
            auth_token: Authorization token
            
        Returns:
            ToolResult with execution result
            
        Raises:
            MCPToolCallError: If tool call fails unexpectedly
        """
        # Validate arguments (hook for subclasses)
        validated_args = self.validate_tool_arguments(tool_name, arguments)
        
        # Auto-initialize if needed
        if self._auto_initialize and not self._initialized:
            await self.initialize(auth_token=auth_token)
        
        start_time = datetime.now(timezone.utc)
        
        try:
            response = await self._connection_manager.send_tools_call(
                backend_id=self.backend_id,
                tool_name=tool_name,
                arguments=validated_args,
                auth_header=auth_token,
            )
            
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            
            # Parse result
            result = ToolResult.from_response(response, duration_ms=duration_ms)
            
            # Transform result (hook for subclasses)
            result = self.transform_tool_result(tool_name, result)
            
            if result.is_error:
                logger.warning(
                    "Tool %s.%s returned error: %s",
                    self.backend_id,
                    tool_name,
                    result.error_message,
                )
            else:
                logger.debug(
                    "Tool %s.%s completed in %.1fms",
                    self.backend_id,
                    tool_name,
                    duration_ms,
                )
            
            return result
            
        except BackendTimeoutError as e:
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            logger.warning(
                "Tool %s.%s timed out after %.1fms",
                self.backend_id,
                tool_name,
                duration_ms,
            )
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, f"Tool call timed out: {e}"
            )
            
        except BackendUnavailableError as e:
            logger.warning(
                "Backend %s unavailable for tool %s", self.backend_id, tool_name
            )
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Backend unavailable: {e}"
            )
            
        except BackendError as e:
            raise MCPToolCallError(f"Tool call failed: {e}") from e
    
    async def call_tool_with_namespace(
        self,
        namespaced_tool: str,
        arguments: dict[str, Any],
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Execute a tool using its namespaced name.
        
        Strips the namespace prefix before forwarding to backend.
        
        Args:
            namespaced_tool: Namespaced tool name (e.g., "notion.search_pages")
            arguments: Tool arguments
            auth_token: Authorization token
            
        Returns:
            ToolResult with execution result
        """
        # Strip namespace prefix
        tool_name = self.strip_namespace(namespaced_tool)
        return await self.call_tool(tool_name, arguments, auth_token=auth_token)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Namespace Handling
    # ─────────────────────────────────────────────────────────────────────────
    
    def strip_namespace(self, namespaced_tool: str) -> str:
        """
        Remove namespace prefix from tool name.
        
        Args:
            namespaced_tool: Namespaced name (e.g., "notion.search_pages")
            
        Returns:
            Tool name without prefix (e.g., "search_pages")
        """
        if "." in namespaced_tool:
            parts = namespaced_tool.split(".", 1)
            if parts[0] == self.backend_id:
                return parts[1]
        return namespaced_tool
    
    def add_namespace(self, tool_name: str) -> str:
        """
        Add namespace prefix to tool name.
        
        Args:
            tool_name: Tool name without prefix
            
        Returns:
            Namespaced name (e.g., "notion.search_pages")
        """
        if "." not in tool_name:
            return f"{self.backend_id}.{tool_name}"
        return tool_name
    
    # ─────────────────────────────────────────────────────────────────────────
    # Hook Methods (Override in Subclasses)
    # ─────────────────────────────────────────────────────────────────────────
    
    def validate_tool_arguments(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate and potentially transform tool arguments.
        
        Override in subclasses to add backend-specific validation.
        
        Args:
            tool_name: Tool being called
            arguments: Raw arguments from caller
            
        Returns:
            Validated/transformed arguments
            
        Raises:
            ValueError: If arguments are invalid
        """
        # Default: pass through unchanged
        return arguments
    
    def transform_tool_result(
        self,
        tool_name: str,
        result: ToolResult,
    ) -> ToolResult:
        """
        Transform tool result before returning to caller.
        
        Override in subclasses to add backend-specific result processing.
        
        Args:
            tool_name: Tool that was called
            result: Raw result from backend
            
        Returns:
            Transformed result
        """
        # Default: pass through unchanged
        return result
    
    def get_default_headers(self) -> dict[str, str]:
        """
        Get default headers to include in all requests.
        
        Override in subclasses to add backend-specific headers.
        
        Returns:
            Dict of header name → value
        """
        return {}
    
    # ─────────────────────────────────────────────────────────────────────────
    # Utility Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def clear_cache(self) -> None:
        """Clear cached tools list."""
        self._tools_cache = None
    
    def reset(self) -> None:
        """Reset client state (requires re-initialization)."""
        self._initialized = False
        self._server_info = None
        self._tools_cache = None
    
    async def check_health(self) -> bool:
        """
        Check if backend is healthy.
        
        Returns:
            True if backend is reachable and healthy
        """
        return await self._connection_manager.check_backend_health(self.backend_id)
    
    def __repr__(self) -> str:
        """String representation."""
        status = "initialized" if self._initialized else "not initialized"
        return f"<{self.__class__.__name__} backend={self.backend_id} {status}>"


# =============================================================================
# Concrete Implementation for Testing/MVP
# =============================================================================


class GenericMCPClient(BaseMCPClient):
    """
    Generic MCP client for backends without specific implementations.
    
    Use this for testing or for backends that don't need custom behavior.
    
    Usage:
        client = GenericMCPClient(connection_manager, backend_id="notion")
    """
    
    def __init__(
        self,
        connection_manager: BackendConnectionManager,
        backend_id: str,
        **kwargs: Any,
    ) -> None:
        """
        Initialize generic client.
        
        Args:
            connection_manager: Backend connection manager
            backend_id: Backend identifier to use
            **kwargs: Additional arguments for BaseMCPClient
        """
        super().__init__(connection_manager, **kwargs)
        self._backend_id = backend_id
    
    @property
    def backend_id(self) -> str:
        """Return the configured backend ID."""
        return self._backend_id


# =============================================================================
# Factory Functions
# =============================================================================


def create_mcp_client(
    connection_manager: BackendConnectionManager,
    backend_id: str,
    **kwargs: Any,
) -> BaseMCPClient:
    """
    Create an MCP client for the specified backend.
    
    For MVP, returns GenericMCPClient. In production, would return
    backend-specific clients (NotionMCPClient, SlackMCPClient, etc.)
    
    Args:
        connection_manager: Backend connection manager
        backend_id: Backend identifier
        **kwargs: Additional client options
        
    Returns:
        Configured MCP client
    """
    # MVP: Use generic client for all backends
    # Production: Return backend-specific clients based on backend_id
    return GenericMCPClient(
        connection_manager=connection_manager,
        backend_id=backend_id,
        **kwargs,
    )
