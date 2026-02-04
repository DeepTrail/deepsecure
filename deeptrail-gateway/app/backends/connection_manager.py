"""
Backend Connection Manager

Manages connections to backend MCP servers. Provides connection pooling,
health checks, and request forwarding for the Virtual MCP Server gateway.

Architecture:
- Gateway maintains pool of connections to each backend
- Connections are reused across agent sessions
- Health checks run periodically in background
- Unhealthy backends are marked and excluded from routing

Usage:
    from app.backends.connection_manager import BackendConnectionManager
    
    manager = BackendConnectionManager()
    
    # Register backends
    manager.register_backend(BackendConfig(
        backend_id="notion",
        base_url="https://api.notion.com/mcp",
        health_endpoint="/health",
    ))
    
    # Send request
    response = await manager.send_request(
        backend_id="notion",
        request=MCPRequest(method="tools/call", params={"name": "search_pages"}),
        auth_header="Bearer token123"
    )
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================


class BackendStatus(Enum):
    """
    Backend connection status.
    
    Lifecycle: UNKNOWN → HEALTHY or UNHEALTHY
    """
    UNKNOWN = "unknown"       # Not yet checked
    HEALTHY = "healthy"       # Passing health checks
    UNHEALTHY = "unhealthy"   # Failing health checks
    DISABLED = "disabled"     # Manually disabled


class RequestMethod(str, Enum):
    """MCP request methods."""
    INITIALIZE = "initialize"
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"


# =============================================================================
# Configuration Data Classes
# =============================================================================


@dataclass
class BackendConfig:
    """
    Configuration for a backend MCP server.
    
    Attributes:
        backend_id: Unique identifier (e.g., "notion", "slack")
        base_url: Base URL for MCP requests
        health_endpoint: Path for health check (None to disable)
        timeout_seconds: Request timeout
        max_connections: Maximum pool connections
        retry_attempts: Number of retries on failure
        retry_delay_seconds: Base delay between retries (exponential backoff)
    """
    backend_id: str
    base_url: str
    health_endpoint: str | None = "/health"
    timeout_seconds: float = 30.0
    max_connections: int = 10
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    
    def __post_init__(self) -> None:
        """Validate configuration."""
        if not self.backend_id:
            raise ValueError("backend_id is required")
        if not self.base_url:
            raise ValueError("base_url is required")
        # Remove trailing slash from base_url
        self.base_url = self.base_url.rstrip("/")


@dataclass
class BackendState:
    """
    Runtime state for a backend connection.
    
    Attributes:
        config: Backend configuration
        status: Current health status
        client: HTTP client for this backend
        last_health_check: Timestamp of last health check
        last_error: Last error message (if unhealthy)
        consecutive_failures: Number of consecutive failed requests
    """
    config: BackendConfig
    status: BackendStatus = BackendStatus.UNKNOWN
    client: httpx.AsyncClient | None = None
    last_health_check: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    
    def mark_healthy(self) -> None:
        """Mark backend as healthy."""
        self.status = BackendStatus.HEALTHY
        self.last_health_check = datetime.now(timezone.utc)
        self.last_error = None
        self.consecutive_failures = 0
    
    def mark_unhealthy(self, error: str) -> None:
        """Mark backend as unhealthy with error."""
        self.status = BackendStatus.UNHEALTHY
        self.last_health_check = datetime.now(timezone.utc)
        self.last_error = error
        self.consecutive_failures += 1
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for logging/debugging."""
        return {
            "backend_id": self.config.backend_id,
            "base_url": self.config.base_url,
            "status": self.status.value,
            "last_health_check": (
                self.last_health_check.isoformat() if self.last_health_check else None
            ),
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
        }


@dataclass
class MCPRequest:
    """
    MCP JSON-RPC request to send to backend.
    
    Attributes:
        method: MCP method (e.g., "tools/call")
        params: Request parameters
        request_id: JSON-RPC request ID
    """
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    request_id: str | int = field(default_factory=lambda: 1)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-RPC 2.0 format."""
        return {
            "jsonrpc": "2.0",
            "method": self.method,
            "params": self.params,
            "id": self.request_id,
        }


@dataclass
class MCPResponse:
    """
    MCP JSON-RPC response from backend.
    
    Attributes:
        result: Successful result (if no error)
        error: Error object (if failed)
        request_id: JSON-RPC request ID
        raw: Raw response dict
    """
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    request_id: str | int | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_success(self) -> bool:
        """Check if response is successful."""
        return self.error is None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPResponse":
        """Parse from JSON-RPC response dict."""
        return cls(
            result=data.get("result"),
            error=data.get("error"),
            request_id=data.get("id"),
            raw=data,
        )
    
    @classmethod
    def from_error(
        cls,
        code: int,
        message: str,
        request_id: Any = None,
    ) -> "MCPResponse":
        """Create error response."""
        return cls(
            error={"code": code, "message": message},
            request_id=request_id,
        )


# =============================================================================
# Exceptions
# =============================================================================


class BackendError(Exception):
    """Base exception for backend errors."""
    pass


class BackendNotFoundError(BackendError):
    """Raised when backend is not registered."""
    pass


class BackendUnavailableError(BackendError):
    """Raised when backend is unhealthy or unreachable."""
    pass


class BackendTimeoutError(BackendError):
    """Raised when request times out."""
    pass


class BackendRequestError(BackendError):
    """Raised when request fails."""
    pass


# =============================================================================
# Connection Manager
# =============================================================================


class BackendConnectionManager:
    """
    Manages connections to backend MCP servers.
    
    Features:
    - Connection pooling per backend
    - Periodic health checks
    - Automatic retries with exponential backoff
    - Graceful handling of backend failures
    
    Thread Safety:
        This implementation uses asyncio locks for thread-safety.
        Safe for concurrent access from multiple async tasks.
    
    Usage:
        manager = BackendConnectionManager()
        
        # Register backends
        manager.register_backend(BackendConfig(
            backend_id="notion",
            base_url="https://api.notion.com/mcp"
        ))
        
        # Start health checks (optional)
        await manager.start_health_checks(interval_seconds=30)
        
        # Send request
        response = await manager.send_request(
            backend_id="notion",
            request=MCPRequest(method="tools/list"),
            auth_header="Bearer token123"
        )
        
        # Cleanup
        await manager.close_all()
    """
    
    # Default settings
    DEFAULT_HEALTH_CHECK_INTERVAL = 30.0  # seconds
    
    def __init__(self) -> None:
        """Initialize empty connection manager."""
        self._backends: dict[str, BackendState] = {}
        self._lock = asyncio.Lock()
        self._health_check_task: asyncio.Task | None = None
        self._shutdown = False
    
    # ─────────────────────────────────────────────────────────────────────────
    # Backend Registration
    # ─────────────────────────────────────────────────────────────────────────
    
    def register_backend(self, config: BackendConfig) -> None:
        """
        Register a backend MCP server.
        
        Args:
            config: Backend configuration
            
        Note:
            Does not create the HTTP client yet - that happens lazily
            on first request or health check.
        """
        if config.backend_id in self._backends:
            logger.warning(
                "Backend %s already registered, replacing", config.backend_id
            )
        
        self._backends[config.backend_id] = BackendState(config=config)
        logger.info(
            "Registered backend: %s at %s", config.backend_id, config.base_url
        )
    
    def unregister_backend(self, backend_id: str) -> bool:
        """
        Unregister a backend and close its connections.
        
        Args:
            backend_id: Backend to unregister
            
        Returns:
            True if backend was registered and removed
        """
        if backend_id not in self._backends:
            return False
        
        state = self._backends.pop(backend_id)
        if state.client:
            # Schedule client close (don't await in sync method)
            asyncio.create_task(state.client.aclose())
        
        logger.info("Unregistered backend: %s", backend_id)
        return True
    
    def get_backend_ids(self) -> list[str]:
        """Get list of registered backend IDs."""
        return list(self._backends.keys())
    
    def get_backend_status(self, backend_id: str) -> BackendStatus | None:
        """
        Get health status of a backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            BackendStatus or None if not registered
        """
        state = self._backends.get(backend_id)
        return state.status if state else None
    
    def get_healthy_backends(self) -> list[str]:
        """Get list of healthy backend IDs."""
        return [
            bid for bid, state in self._backends.items()
            if state.status == BackendStatus.HEALTHY
        ]
    
    def get_all_backend_states(self) -> dict[str, dict[str, Any]]:
        """Get status info for all backends (for debugging/monitoring)."""
        return {
            bid: state.to_dict()
            for bid, state in self._backends.items()
        }
    
    def is_backend_registered(self, backend_id: str) -> bool:
        """Check if a backend is registered."""
        return backend_id in self._backends
    
    # ─────────────────────────────────────────────────────────────────────────
    # Connection Management
    # ─────────────────────────────────────────────────────────────────────────
    
    async def _get_or_create_client(self, backend_id: str) -> httpx.AsyncClient:
        """
        Get or create HTTP client for backend (lazy initialization).
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            Configured httpx.AsyncClient
            
        Raises:
            BackendNotFoundError: If backend not registered
        """
        async with self._lock:
            state = self._backends.get(backend_id)
            if not state:
                raise BackendNotFoundError(f"Backend '{backend_id}' not registered")
            
            if state.client is None:
                config = state.config
                state.client = httpx.AsyncClient(
                    base_url=config.base_url,
                    timeout=httpx.Timeout(config.timeout_seconds),
                    limits=httpx.Limits(max_connections=config.max_connections),
                )
                logger.debug("Created HTTP client for backend: %s", backend_id)
            
            return state.client
    
    async def close_backend(self, backend_id: str) -> bool:
        """
        Close connections for a specific backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            True if backend existed and was closed
        """
        async with self._lock:
            state = self._backends.get(backend_id)
            if not state:
                return False
            
            if state.client:
                await state.client.aclose()
                state.client = None
                logger.debug("Closed HTTP client for backend: %s", backend_id)
            
            return True
    
    async def close_all(self) -> None:
        """Close all backend connections and stop health checks."""
        self._shutdown = True
        
        # Stop health checks
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
        
        # Close all clients
        async with self._lock:
            for state in self._backends.values():
                if state.client:
                    await state.client.aclose()
                    state.client = None
        
        logger.info("Closed all backend connections")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Health Checks
    # ─────────────────────────────────────────────────────────────────────────
    
    async def check_backend_health(self, backend_id: str) -> bool:
        """
        Check health of a specific backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            True if healthy, False otherwise
        """
        state = self._backends.get(backend_id)
        if not state:
            return False
        
        config = state.config
        
        # Skip if no health endpoint configured
        if not config.health_endpoint:
            state.mark_healthy()
            return True
        
        try:
            client = await self._get_or_create_client(backend_id)
            response = await client.get(config.health_endpoint)
            
            if response.status_code == 200:
                state.mark_healthy()
                logger.debug("Backend %s is healthy", backend_id)
                return True
            else:
                state.mark_unhealthy(f"Health check returned {response.status_code}")
                logger.warning(
                    "Backend %s unhealthy: status %s", backend_id, response.status_code
                )
                return False
                
        except httpx.TimeoutException:
            state.mark_unhealthy("Health check timed out")
            logger.warning("Backend %s health check timed out", backend_id)
            return False
            
        except Exception as e:
            state.mark_unhealthy(str(e))
            logger.warning("Backend %s health check failed: %s", backend_id, e)
            return False
    
    async def check_all_backends_health(self) -> dict[str, bool]:
        """
        Check health of all registered backends.
        
        Returns:
            Dict mapping backend_id to health status
        """
        results = {}
        for backend_id in self._backends:
            results[backend_id] = await self.check_backend_health(backend_id)
        return results
    
    async def start_health_checks(
        self,
        interval_seconds: float = DEFAULT_HEALTH_CHECK_INTERVAL,
    ) -> None:
        """
        Start periodic health checks in background.
        
        Args:
            interval_seconds: Interval between health checks
        """
        if self._health_check_task:
            logger.warning("Health checks already running")
            return
        
        async def health_check_loop() -> None:
            while not self._shutdown:
                try:
                    await self.check_all_backends_health()
                    await asyncio.sleep(interval_seconds)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("Health check error: %s", e)
                    await asyncio.sleep(interval_seconds)
        
        self._health_check_task = asyncio.create_task(health_check_loop())
        logger.info("Started health checks with %ss interval", interval_seconds)
    
    def stop_health_checks(self) -> None:
        """Stop periodic health checks."""
        if self._health_check_task:
            self._health_check_task.cancel()
            self._health_check_task = None
            logger.info("Stopped health checks")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Request Handling
    # ─────────────────────────────────────────────────────────────────────────
    
    async def send_request(
        self,
        backend_id: str,
        request: MCPRequest,
        auth_header: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> MCPResponse:
        """
        Send MCP request to a backend.
        
        Args:
            backend_id: Target backend identifier
            request: MCP request to send
            auth_header: Authorization header value (e.g., "Bearer token")
            extra_headers: Additional headers to include
            
        Returns:
            MCPResponse from backend
            
        Raises:
            BackendNotFoundError: If backend not registered
            BackendUnavailableError: If backend is unhealthy
            BackendTimeoutError: If request times out
            BackendRequestError: If request fails
        """
        state = self._backends.get(backend_id)
        if not state:
            raise BackendNotFoundError(f"Backend '{backend_id}' not registered")
        
        # Check if backend is healthy (unless status is unknown)
        if state.status == BackendStatus.UNHEALTHY:
            raise BackendUnavailableError(
                f"Backend '{backend_id}' is unhealthy: {state.last_error}"
            )
        
        if state.status == BackendStatus.DISABLED:
            raise BackendUnavailableError(
                f"Backend '{backend_id}' is disabled"
            )
        
        config = state.config
        client = await self._get_or_create_client(backend_id)
        
        # Build headers
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if auth_header:
            headers["Authorization"] = auth_header
        if extra_headers:
            headers.update(extra_headers)
        
        # Retry loop
        last_error: Exception | None = None
        for attempt in range(config.retry_attempts):
            try:
                response = await client.post(
                    "/",  # MCP endpoint is typically at root
                    json=request.to_dict(),
                    headers=headers,
                )
                
                # Parse response
                if response.status_code == 200:
                    data = response.json()
                    state.mark_healthy()  # Successful request = healthy
                    return MCPResponse.from_dict(data)
                else:
                    error_text = response.text[:200]  # Truncate for logging
                    logger.warning(
                        "Backend %s returned %s: %s",
                        backend_id,
                        response.status_code,
                        error_text,
                    )
                    return MCPResponse.from_error(
                        code=-32000,
                        message=f"Backend returned {response.status_code}",
                        request_id=request.request_id,
                    )
                    
            except httpx.TimeoutException:
                last_error = BackendTimeoutError(
                    f"Request to {backend_id} timed out"
                )
                logger.warning(
                    "Timeout on attempt %d for %s", attempt + 1, backend_id
                )
                
            except httpx.RequestError as e:
                last_error = BackendRequestError(
                    f"Request to {backend_id} failed: {e}"
                )
                logger.warning(
                    "Request error on attempt %d for %s: %s", attempt + 1, backend_id, e
                )
            
            # Exponential backoff before retry
            if attempt < config.retry_attempts - 1:
                delay = config.retry_delay_seconds * (2 ** attempt)
                await asyncio.sleep(delay)
        
        # All retries failed
        state.mark_unhealthy(str(last_error))
        raise last_error or BackendRequestError(f"Request to {backend_id} failed")
    
    async def send_tools_list(
        self,
        backend_id: str,
        auth_header: str | None = None,
    ) -> MCPResponse:
        """
        Send tools/list request to a backend.
        
        Convenience method for fetching available tools.
        
        Args:
            backend_id: Target backend
            auth_header: Authorization header
            
        Returns:
            MCPResponse containing tools list
        """
        return await self.send_request(
            backend_id=backend_id,
            request=MCPRequest(method=RequestMethod.TOOLS_LIST.value),
            auth_header=auth_header,
        )
    
    async def send_tools_call(
        self,
        backend_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        auth_header: str | None = None,
    ) -> MCPResponse:
        """
        Send tools/call request to a backend.
        
        Convenience method for executing a tool.
        
        Args:
            backend_id: Target backend
            tool_name: Tool name (without namespace prefix)
            arguments: Tool arguments
            auth_header: Authorization header
            
        Returns:
            MCPResponse containing tool result
        """
        return await self.send_request(
            backend_id=backend_id,
            request=MCPRequest(
                method=RequestMethod.TOOLS_CALL.value,
                params={"name": tool_name, "arguments": arguments},
            ),
            auth_header=auth_header,
        )
    
    async def send_initialize(
        self,
        backend_id: str,
        client_info: dict[str, Any] | None = None,
        auth_header: str | None = None,
    ) -> MCPResponse:
        """
        Send initialize request to a backend.
        
        Convenience method for MCP initialization handshake.
        
        Args:
            backend_id: Target backend
            client_info: Client information for handshake
            auth_header: Authorization header
            
        Returns:
            MCPResponse containing server info
        """
        params: dict[str, Any] = {}
        if client_info:
            params["clientInfo"] = client_info
        
        return await self.send_request(
            backend_id=backend_id,
            request=MCPRequest(
                method=RequestMethod.INITIALIZE.value,
                params=params,
            ),
            auth_header=auth_header,
        )


# =============================================================================
# Global Instance Management
# =============================================================================


_connection_manager: BackendConnectionManager | None = None


def get_connection_manager() -> BackendConnectionManager:
    """
    Get the global BackendConnectionManager instance.
    
    Raises:
        RuntimeError: If manager not initialized
    """
    if _connection_manager is None:
        raise RuntimeError(
            "BackendConnectionManager not initialized. "
            "Call configure_connection_manager() first."
        )
    return _connection_manager


def configure_connection_manager(
    backends: list[BackendConfig] | None = None,
) -> BackendConnectionManager:
    """
    Initialize the global BackendConnectionManager.
    
    Args:
        backends: Optional list of backend configurations
        
    Returns:
        Configured BackendConnectionManager instance
    """
    global _connection_manager
    _connection_manager = BackendConnectionManager()
    
    if backends:
        for config in backends:
            _connection_manager.register_backend(config)
    
    logger.info(
        "BackendConnectionManager configured with %d backends",
        len(backends or []),
    )
    return _connection_manager


def reset_connection_manager() -> None:
    """
    Reset the global BackendConnectionManager.
    
    Useful for testing or reconfiguration.
    """
    global _connection_manager
    _connection_manager = None


# =============================================================================
# Factory Functions
# =============================================================================


def create_default_manager() -> BackendConnectionManager:
    """
    Create a connection manager with default MVP backends.
    
    For MVP, we configure mock/test backends. In production,
    these would be loaded from configuration or database.
    
    Returns:
        Configured BackendConnectionManager
    """
    manager = BackendConnectionManager()
    
    # MVP: Register placeholder backends
    # Production: Load from config/database
    default_backends = [
        BackendConfig(
            backend_id="notion",
            base_url="https://mcp.notion.so",
            health_endpoint="/health",
        ),
        BackendConfig(
            backend_id="slack",
            base_url="https://mcp.slack.com",
            health_endpoint="/health",
        ),
        BackendConfig(
            backend_id="hubspot",
            base_url="https://mcp.hubspot.com",
            health_endpoint="/health",
        ),
    ]
    
    for config in default_backends:
        manager.register_backend(config)
    
    return manager
