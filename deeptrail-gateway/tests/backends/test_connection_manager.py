"""Tests for Backend Connection Manager."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.backends.connection_manager import (
    BackendConfig,
    BackendConnectionManager,
    BackendNotFoundError,
    BackendRequestError,
    BackendState,
    BackendStatus,
    BackendTimeoutError,
    BackendUnavailableError,
    MCPRequest,
    MCPResponse,
    RequestMethod,
    configure_connection_manager,
    create_default_manager,
    get_connection_manager,
    reset_connection_manager,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def manager():
    """Create a fresh connection manager."""
    return BackendConnectionManager()


@pytest.fixture
def notion_config():
    """Create Notion backend config."""
    return BackendConfig(
        backend_id="notion",
        base_url="https://mcp.notion.so",
        health_endpoint="/health",
        timeout_seconds=10.0,
    )


@pytest.fixture
def slack_config():
    """Create Slack backend config."""
    return BackendConfig(
        backend_id="slack",
        base_url="https://mcp.slack.com",
        health_endpoint="/health",
        timeout_seconds=10.0,
    )


@pytest.fixture
def hubspot_config():
    """Create HubSpot backend config."""
    return BackendConfig(
        backend_id="hubspot",
        base_url="https://mcp.hubspot.com",
        health_endpoint="/health",
        timeout_seconds=10.0,
    )


@pytest.fixture(autouse=True)
def reset_global_manager():
    """Reset global connection manager before and after each test."""
    reset_connection_manager()
    yield
    reset_connection_manager()


# =============================================================================
# BackendConfig Tests
# =============================================================================


class TestBackendConfig:
    """Tests for BackendConfig data class."""

    def test_create_config(self):
        """Test creating a valid config."""
        config = BackendConfig(
            backend_id="notion",
            base_url="https://mcp.notion.so",
        )
        
        assert config.backend_id == "notion"
        assert config.base_url == "https://mcp.notion.so"
        assert config.health_endpoint == "/health"  # default
        assert config.timeout_seconds == 30.0  # default
        assert config.max_connections == 10  # default
        assert config.retry_attempts == 3  # default

    def test_config_strips_trailing_slash(self):
        """Test that trailing slash is removed from base_url."""
        config = BackendConfig(
            backend_id="notion",
            base_url="https://mcp.notion.so/",
        )
        
        assert config.base_url == "https://mcp.notion.so"

    def test_config_requires_backend_id(self):
        """Test that backend_id is required."""
        with pytest.raises(ValueError, match="backend_id is required"):
            BackendConfig(backend_id="", base_url="https://example.com")

    def test_config_requires_base_url(self):
        """Test that base_url is required."""
        with pytest.raises(ValueError, match="base_url is required"):
            BackendConfig(backend_id="test", base_url="")

    def test_config_custom_values(self):
        """Test config with custom values."""
        config = BackendConfig(
            backend_id="custom",
            base_url="https://custom.com",
            health_endpoint="/api/health",
            timeout_seconds=60.0,
            max_connections=20,
            retry_attempts=5,
            retry_delay_seconds=2.0,
        )
        
        assert config.health_endpoint == "/api/health"
        assert config.timeout_seconds == 60.0
        assert config.max_connections == 20
        assert config.retry_attempts == 5
        assert config.retry_delay_seconds == 2.0

    def test_config_no_health_endpoint(self):
        """Test config with disabled health endpoint."""
        config = BackendConfig(
            backend_id="test",
            base_url="https://test.com",
            health_endpoint=None,
        )
        
        assert config.health_endpoint is None


# =============================================================================
# BackendState Tests
# =============================================================================


class TestBackendState:
    """Tests for BackendState data class."""

    def test_initial_state(self, notion_config):
        """Test initial state values."""
        state = BackendState(config=notion_config)
        
        assert state.status == BackendStatus.UNKNOWN
        assert state.client is None
        assert state.last_health_check is None
        assert state.last_error is None
        assert state.consecutive_failures == 0

    def test_mark_healthy(self, notion_config):
        """Test marking backend as healthy."""
        state = BackendState(config=notion_config)
        state.consecutive_failures = 3
        state.last_error = "Previous error"
        
        state.mark_healthy()
        
        assert state.status == BackendStatus.HEALTHY
        assert state.last_health_check is not None
        assert state.last_error is None
        assert state.consecutive_failures == 0

    def test_mark_unhealthy(self, notion_config):
        """Test marking backend as unhealthy."""
        state = BackendState(config=notion_config)
        
        state.mark_unhealthy("Connection refused")
        
        assert state.status == BackendStatus.UNHEALTHY
        assert state.last_health_check is not None
        assert state.last_error == "Connection refused"
        assert state.consecutive_failures == 1
        
        # Mark unhealthy again
        state.mark_unhealthy("Timeout")
        assert state.consecutive_failures == 2
        assert state.last_error == "Timeout"

    def test_to_dict(self, notion_config):
        """Test converting state to dict."""
        state = BackendState(config=notion_config)
        state.mark_healthy()
        
        result = state.to_dict()
        
        assert result["backend_id"] == "notion"
        assert result["base_url"] == "https://mcp.notion.so"
        assert result["status"] == "healthy"
        assert result["last_health_check"] is not None
        assert result["last_error"] is None
        assert result["consecutive_failures"] == 0


# =============================================================================
# MCPRequest Tests
# =============================================================================


class TestMCPRequest:
    """Tests for MCPRequest data class."""

    def test_to_dict_format(self):
        """Test JSON-RPC 2.0 format."""
        request = MCPRequest(
            method="tools/call",
            params={"name": "search", "arguments": {}},
            request_id=42,
        )
        
        result = request.to_dict()
        
        assert result["jsonrpc"] == "2.0"
        assert result["method"] == "tools/call"
        assert result["params"] == {"name": "search", "arguments": {}}
        assert result["id"] == 42

    def test_default_values(self):
        """Test default request values."""
        request = MCPRequest(method="tools/list")
        
        result = request.to_dict()
        
        assert result["params"] == {}
        assert result["id"] == 1

    def test_with_enum_method(self):
        """Test using RequestMethod enum."""
        request = MCPRequest(method=RequestMethod.TOOLS_LIST.value)
        
        assert request.method == "tools/list"


# =============================================================================
# MCPResponse Tests
# =============================================================================


class TestMCPResponse:
    """Tests for MCPResponse data class."""

    def test_from_dict_success(self):
        """Test parsing successful response."""
        data = {
            "jsonrpc": "2.0",
            "result": {"tools": []},
            "id": 1,
        }
        
        response = MCPResponse.from_dict(data)
        
        assert response.is_success
        assert response.result == {"tools": []}
        assert response.error is None
        assert response.request_id == 1
        assert response.raw == data

    def test_from_dict_error(self):
        """Test parsing error response."""
        data = {
            "jsonrpc": "2.0",
            "error": {"code": -32600, "message": "Invalid request"},
            "id": 1,
        }
        
        response = MCPResponse.from_dict(data)
        
        assert not response.is_success
        assert response.error["code"] == -32600
        assert response.error["message"] == "Invalid request"
        assert response.result is None

    def test_from_error_factory(self):
        """Test creating error response."""
        response = MCPResponse.from_error(-32000, "Backend error", request_id=5)
        
        assert not response.is_success
        assert response.error["code"] == -32000
        assert response.error["message"] == "Backend error"
        assert response.request_id == 5

    def test_is_success_with_null_result(self):
        """Test is_success with null result (notification response)."""
        response = MCPResponse(result=None, error=None)
        assert response.is_success  # No error means success


# =============================================================================
# Backend Registration Tests
# =============================================================================


class TestBackendRegistration:
    """Tests for backend registration."""

    def test_register_backend(self, manager, notion_config):
        """Test registering a backend."""
        manager.register_backend(notion_config)
        
        assert "notion" in manager.get_backend_ids()
        assert manager.get_backend_status("notion") == BackendStatus.UNKNOWN

    def test_register_multiple_backends(self, manager, notion_config, slack_config):
        """Test registering multiple backends."""
        manager.register_backend(notion_config)
        manager.register_backend(slack_config)
        
        backend_ids = manager.get_backend_ids()
        assert "notion" in backend_ids
        assert "slack" in backend_ids
        assert len(backend_ids) == 2

    def test_register_duplicate_backend(self, manager, notion_config):
        """Test registering same backend twice replaces it."""
        manager.register_backend(notion_config)
        
        new_config = BackendConfig(
            backend_id="notion",
            base_url="https://new-url.com",
        )
        manager.register_backend(new_config)
        
        assert len(manager.get_backend_ids()) == 1
        # New config should be used
        state = manager._backends["notion"]
        assert state.config.base_url == "https://new-url.com"

    def test_unregister_backend(self, manager, notion_config):
        """Test unregistering a backend."""
        manager.register_backend(notion_config)
        
        result = manager.unregister_backend("notion")
        
        assert result is True
        assert "notion" not in manager.get_backend_ids()

    def test_unregister_nonexistent_backend(self, manager):
        """Test unregistering non-existent backend returns False."""
        result = manager.unregister_backend("nonexistent")
        assert result is False

    def test_get_healthy_backends(self, manager, notion_config, slack_config):
        """Test getting healthy backends."""
        manager.register_backend(notion_config)
        manager.register_backend(slack_config)
        
        manager._backends["notion"].mark_healthy()
        # slack remains UNKNOWN
        
        healthy = manager.get_healthy_backends()
        
        assert "notion" in healthy
        assert "slack" not in healthy

    def test_get_backend_status_unknown(self, manager):
        """Test getting status for unknown backend returns None."""
        assert manager.get_backend_status("unknown") is None

    def test_is_backend_registered(self, manager, notion_config):
        """Test checking if backend is registered."""
        assert not manager.is_backend_registered("notion")
        
        manager.register_backend(notion_config)
        
        assert manager.is_backend_registered("notion")
        assert not manager.is_backend_registered("slack")

    def test_get_all_backend_states(self, manager, notion_config, slack_config):
        """Test getting all backend states."""
        manager.register_backend(notion_config)
        manager.register_backend(slack_config)
        manager._backends["notion"].mark_healthy()
        
        states = manager.get_all_backend_states()
        
        assert len(states) == 2
        assert states["notion"]["status"] == "healthy"
        assert states["slack"]["status"] == "unknown"


# =============================================================================
# Connection Management Tests
# =============================================================================


class TestConnectionManagement:
    """Tests for connection lifecycle."""

    @pytest.mark.asyncio
    async def test_lazy_client_creation(self, manager, notion_config):
        """Test that HTTP client is created lazily."""
        manager.register_backend(notion_config)
        
        # Client should not exist yet
        assert manager._backends["notion"].client is None
        
        # Get or create client
        client = await manager._get_or_create_client("notion")
        
        assert client is not None
        assert manager._backends["notion"].client is not None
        
        # Cleanup
        await manager.close_all()

    @pytest.mark.asyncio
    async def test_client_reused(self, manager, notion_config):
        """Test that same client is returned on subsequent calls."""
        manager.register_backend(notion_config)
        
        client1 = await manager._get_or_create_client("notion")
        client2 = await manager._get_or_create_client("notion")
        
        assert client1 is client2
        
        await manager.close_all()

    @pytest.mark.asyncio
    async def test_get_client_for_unknown_backend(self, manager):
        """Test getting client for unregistered backend raises error."""
        with pytest.raises(BackendNotFoundError, match="not registered"):
            await manager._get_or_create_client("unknown")

    @pytest.mark.asyncio
    async def test_close_backend(self, manager, notion_config):
        """Test closing a specific backend."""
        manager.register_backend(notion_config)
        
        # Create client
        await manager._get_or_create_client("notion")
        assert manager._backends["notion"].client is not None
        
        # Close
        result = await manager.close_backend("notion")
        
        assert result is True
        assert manager._backends["notion"].client is None

    @pytest.mark.asyncio
    async def test_close_nonexistent_backend(self, manager):
        """Test closing non-existent backend returns False."""
        result = await manager.close_backend("unknown")
        assert result is False

    @pytest.mark.asyncio
    async def test_close_all(self, manager, notion_config, slack_config):
        """Test closing all backends."""
        manager.register_backend(notion_config)
        manager.register_backend(slack_config)
        
        await manager._get_or_create_client("notion")
        await manager._get_or_create_client("slack")
        
        await manager.close_all()
        
        assert manager._backends["notion"].client is None
        assert manager._backends["slack"].client is None


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthChecks:
    """Tests for health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, manager, notion_config):
        """Test successful health check."""
        manager.register_backend(notion_config)
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            
            result = await manager.check_backend_health("notion")
        
        assert result is True
        assert manager.get_backend_status("notion") == BackendStatus.HEALTHY
        
        await manager.close_all()

    @pytest.mark.asyncio
    async def test_health_check_failure_status_code(self, manager, notion_config):
        """Test failed health check due to status code."""
        manager.register_backend(notion_config)
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = MagicMock(status_code=503)
            
            result = await manager.check_backend_health("notion")
        
        assert result is False
        assert manager.get_backend_status("notion") == BackendStatus.UNHEALTHY
        
        await manager.close_all()

    @pytest.mark.asyncio
    async def test_health_check_timeout(self, manager, notion_config):
        """Test health check timeout."""
        manager.register_backend(notion_config)
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Timeout")
            
            result = await manager.check_backend_health("notion")
        
        assert result is False
        assert manager.get_backend_status("notion") == BackendStatus.UNHEALTHY
        assert "timed out" in manager._backends["notion"].last_error
        
        await manager.close_all()

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self, manager, notion_config):
        """Test health check connection error."""
        manager.register_backend(notion_config)
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")
            
            result = await manager.check_backend_health("notion")
        
        assert result is False
        assert manager.get_backend_status("notion") == BackendStatus.UNHEALTHY
        
        await manager.close_all()

    @pytest.mark.asyncio
    async def test_no_health_endpoint(self, manager):
        """Test backend without health endpoint is always healthy."""
        config = BackendConfig(
            backend_id="test",
            base_url="https://test.com",
            health_endpoint=None,  # No health endpoint
        )
        manager.register_backend(config)
        
        result = await manager.check_backend_health("test")
        
        assert result is True
        assert manager.get_backend_status("test") == BackendStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_health_check_unknown_backend(self, manager):
        """Test health check for unknown backend returns False."""
        result = await manager.check_backend_health("unknown")
        assert result is False

    @pytest.mark.asyncio
    async def test_check_all_backends_health(
        self, manager, notion_config, slack_config
    ):
        """Test checking health of all backends."""
        manager.register_backend(notion_config)
        manager.register_backend(slack_config)
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            # First call (notion) succeeds, second call (slack) fails
            mock_get.side_effect = [
                MagicMock(status_code=200),
                MagicMock(status_code=503),
            ]
            
            results = await manager.check_all_backends_health()
        
        assert results["notion"] is True
        assert results["slack"] is False
        
        await manager.close_all()


# =============================================================================
# Request Handling Tests
# =============================================================================


class TestRequestHandling:
    """Tests for MCP request handling."""

    @pytest.mark.asyncio
    async def test_send_request_success(self, manager, notion_config):
        """Test successful request."""
        manager.register_backend(notion_config)
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {
                    "jsonrpc": "2.0",
                    "result": {"tools": []},
                    "id": 1,
                },
            )
            
            response = await manager.send_request(
                "notion",
                MCPRequest(method="tools/list"),
                auth_header="Bearer token123",
            )
        
        assert response.is_success
        assert response.result == {"tools": []}
        
        # Verify auth header was included
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["headers"]["Authorization"] == "Bearer token123"
        
        # Backend should be marked healthy
        assert manager.get_backend_status("notion") == BackendStatus.HEALTHY
        
        await manager.close_all()

    @pytest.mark.asyncio
    async def test_send_request_with_extra_headers(self, manager, notion_config):
        """Test request with extra headers."""
        manager.register_backend(notion_config)
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"jsonrpc": "2.0", "result": {}, "id": 1},
            )
            
            await manager.send_request(
                "notion",
                MCPRequest(method="tools/list"),
                extra_headers={"X-Custom-Header": "value"},
            )
        
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["headers"]["X-Custom-Header"] == "value"
        
        await manager.close_all()

    @pytest.mark.asyncio
    async def test_send_request_to_unknown_backend(self, manager):
        """Test request to unregistered backend raises error."""
        with pytest.raises(BackendNotFoundError, match="not registered"):
            await manager.send_request(
                "unknown",
                MCPRequest(method="tools/list"),
            )

    @pytest.mark.asyncio
    async def test_send_request_to_unhealthy_backend(self, manager, notion_config):
        """Test request to unhealthy backend raises error."""
        manager.register_backend(notion_config)
        manager._backends["notion"].mark_unhealthy("Test failure")
        
        with pytest.raises(BackendUnavailableError, match="unhealthy"):
            await manager.send_request(
                "notion",
                MCPRequest(method="tools/list"),
            )

    @pytest.mark.asyncio
    async def test_send_request_to_disabled_backend(self, manager, notion_config):
        """Test request to disabled backend raises error."""
        manager.register_backend(notion_config)
        manager._backends["notion"].status = BackendStatus.DISABLED
        
        with pytest.raises(BackendUnavailableError, match="disabled"):
            await manager.send_request(
                "notion",
                MCPRequest(method="tools/list"),
            )

    @pytest.mark.asyncio
    async def test_send_request_non_200_response(self, manager, notion_config):
        """Test handling non-200 response from backend."""
        manager.register_backend(notion_config)
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MagicMock(
                status_code=500,
                text="Internal Server Error",
            )
            
            response = await manager.send_request(
                "notion",
                MCPRequest(method="tools/list"),
            )
        
        assert not response.is_success
        assert response.error["code"] == -32000
        assert "500" in response.error["message"]
        
        await manager.close_all()

    @pytest.mark.asyncio
    async def test_send_request_timeout_with_retry(self, manager, notion_config):
        """Test request timeout with retries."""
        manager.register_backend(notion_config)
        manager._backends["notion"].config.retry_attempts = 2
        manager._backends["notion"].config.retry_delay_seconds = 0.01
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Timeout")
            
            with pytest.raises(BackendTimeoutError):
                await manager.send_request(
                    "notion",
                    MCPRequest(method="tools/list"),
                )
        
        # Verify retries happened
        assert mock_post.call_count == 2
        
        # Backend should be marked unhealthy after all retries fail
        assert manager.get_backend_status("notion") == BackendStatus.UNHEALTHY
        
        await manager.close_all()

    @pytest.mark.asyncio
    async def test_send_request_connection_error_with_retry(
        self, manager, notion_config
    ):
        """Test connection error with retries."""
        manager.register_backend(notion_config)
        manager._backends["notion"].config.retry_attempts = 3
        manager._backends["notion"].config.retry_delay_seconds = 0.01
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")
            
            with pytest.raises(BackendRequestError):
                await manager.send_request(
                    "notion",
                    MCPRequest(method="tools/list"),
                )
        
        assert mock_post.call_count == 3
        
        await manager.close_all()

    @pytest.mark.asyncio
    async def test_send_request_success_after_retry(self, manager, notion_config):
        """Test successful request after failed retry."""
        manager.register_backend(notion_config)
        manager._backends["notion"].config.retry_delay_seconds = 0.01
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            # First call fails, second succeeds
            mock_post.side_effect = [
                httpx.TimeoutException("Timeout"),
                MagicMock(
                    status_code=200,
                    json=lambda: {"jsonrpc": "2.0", "result": {"ok": True}, "id": 1},
                ),
            ]
            
            response = await manager.send_request(
                "notion",
                MCPRequest(method="tools/list"),
            )
        
        assert response.is_success
        assert response.result == {"ok": True}
        assert mock_post.call_count == 2
        
        await manager.close_all()


# =============================================================================
# Convenience Methods Tests
# =============================================================================


class TestConvenienceMethods:
    """Tests for convenience request methods."""

    @pytest.mark.asyncio
    async def test_send_tools_list(self, manager, notion_config):
        """Test tools/list convenience method."""
        manager.register_backend(notion_config)
        
        with patch.object(
            BackendConnectionManager, "send_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = MCPResponse(result={"tools": []})
            
            await manager.send_tools_list("notion", auth_header="Bearer token")
        
        call_args = mock_send.call_args
        assert call_args.kwargs["request"].method == "tools/list"
        assert call_args.kwargs["auth_header"] == "Bearer token"

    @pytest.mark.asyncio
    async def test_send_tools_call(self, manager, notion_config):
        """Test tools/call convenience method."""
        manager.register_backend(notion_config)
        
        with patch.object(
            BackendConnectionManager, "send_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = MCPResponse(result={"content": []})
            
            await manager.send_tools_call(
                "notion",
                tool_name="search_pages",
                arguments={"query": "test"},
                auth_header="Bearer token",
            )
        
        call_args = mock_send.call_args
        request = call_args.kwargs["request"]
        assert request.method == "tools/call"
        assert request.params["name"] == "search_pages"
        assert request.params["arguments"] == {"query": "test"}

    @pytest.mark.asyncio
    async def test_send_initialize(self, manager, notion_config):
        """Test initialize convenience method."""
        manager.register_backend(notion_config)
        
        with patch.object(
            BackendConnectionManager, "send_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = MCPResponse(
                result={"protocolVersion": "1.0", "serverInfo": {}}
            )
            
            await manager.send_initialize(
                "notion",
                client_info={"name": "gateway", "version": "1.0"},
                auth_header="Bearer token",
            )
        
        call_args = mock_send.call_args
        request = call_args.kwargs["request"]
        assert request.method == "initialize"
        assert request.params["clientInfo"] == {"name": "gateway", "version": "1.0"}

    @pytest.mark.asyncio
    async def test_send_initialize_without_client_info(self, manager, notion_config):
        """Test initialize without client info."""
        manager.register_backend(notion_config)
        
        with patch.object(
            BackendConnectionManager, "send_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = MCPResponse(result={})
            
            await manager.send_initialize("notion")
        
        call_args = mock_send.call_args
        request = call_args.kwargs["request"]
        assert request.params == {}


# =============================================================================
# Global Instance Tests
# =============================================================================


class TestGlobalInstance:
    """Tests for global instance management."""

    def test_get_connection_manager_not_initialized(self):
        """Test getting manager before initialization raises error."""
        with pytest.raises(RuntimeError, match="not initialized"):
            get_connection_manager()

    def test_configure_connection_manager(self, notion_config):
        """Test configuring global manager."""
        manager = configure_connection_manager(backends=[notion_config])
        
        assert manager is not None
        assert "notion" in manager.get_backend_ids()
        
        # Should be able to get the same instance
        same_manager = get_connection_manager()
        assert same_manager is manager

    def test_configure_connection_manager_empty(self):
        """Test configuring manager with no backends."""
        manager = configure_connection_manager()
        
        assert manager is not None
        assert manager.get_backend_ids() == []

    def test_reset_connection_manager(self, notion_config):
        """Test resetting global manager."""
        configure_connection_manager(backends=[notion_config])
        
        reset_connection_manager()
        
        with pytest.raises(RuntimeError):
            get_connection_manager()


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_default_manager(self):
        """Test creating manager with default MVP backends."""
        manager = create_default_manager()
        
        backend_ids = manager.get_backend_ids()
        
        assert "notion" in backend_ids
        assert "slack" in backend_ids
        assert "hubspot" in backend_ids
        assert len(backend_ids) == 3


# =============================================================================
# Edge Cases and Concurrency Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_concurrent_client_creation(self, manager, notion_config):
        """Test concurrent client creation doesn't create duplicates."""
        manager.register_backend(notion_config)
        
        # Create multiple concurrent tasks to get client
        tasks = [
            manager._get_or_create_client("notion")
            for _ in range(10)
        ]
        
        clients = await asyncio.gather(*tasks)
        
        # All should return the same client
        assert all(c is clients[0] for c in clients)
        
        await manager.close_all()

    @pytest.mark.asyncio
    async def test_close_all_stops_health_checks(self, manager, notion_config):
        """Test that close_all stops health check task."""
        manager.register_backend(notion_config)
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            
            await manager.start_health_checks(interval_seconds=0.1)
            
            assert manager._health_check_task is not None
            
            await manager.close_all()
            
            assert manager._health_check_task is None

    @pytest.mark.asyncio
    async def test_start_health_checks_twice(self, manager, notion_config):
        """Test starting health checks when already running logs warning."""
        manager.register_backend(notion_config)
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            
            await manager.start_health_checks(interval_seconds=1.0)
            task1 = manager._health_check_task
            
            # Start again (should log warning, not create new task)
            await manager.start_health_checks(interval_seconds=1.0)
            task2 = manager._health_check_task
            
            assert task1 is task2
            
            await manager.close_all()

    def test_stop_health_checks_when_not_running(self, manager):
        """Test stopping health checks when not running is a no-op."""
        manager.stop_health_checks()  # Should not raise

    @pytest.mark.asyncio
    async def test_unregister_backend_with_active_client(
        self, manager, notion_config
    ):
        """Test unregistering backend closes its client."""
        manager.register_backend(notion_config)
        await manager._get_or_create_client("notion")
        
        assert manager._backends["notion"].client is not None
        
        result = manager.unregister_backend("notion")
        
        assert result is True
        assert "notion" not in manager._backends
        
        # Give the scheduled aclose task time to run
        await asyncio.sleep(0.1)


# =============================================================================
# Enum Tests
# =============================================================================


class TestEnums:
    """Tests for enum values."""

    def test_backend_status_values(self):
        """Test BackendStatus enum values."""
        assert BackendStatus.UNKNOWN.value == "unknown"
        assert BackendStatus.HEALTHY.value == "healthy"
        assert BackendStatus.UNHEALTHY.value == "unhealthy"
        assert BackendStatus.DISABLED.value == "disabled"

    def test_request_method_values(self):
        """Test RequestMethod enum values."""
        assert RequestMethod.INITIALIZE.value == "initialize"
        assert RequestMethod.TOOLS_LIST.value == "tools/list"
        assert RequestMethod.TOOLS_CALL.value == "tools/call"
