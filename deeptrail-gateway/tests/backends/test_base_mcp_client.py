"""Tests for Base MCP Client."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.backends.base_mcp_client import (
    BaseMCPClient,
    GenericMCPClient,
    MCPCapability,
    MCPClientError,
    MCPInitializeError,
    MCPToolCallError,
    ServerInfo,
    ToolCallStatus,
    ToolResult,
    ToolSchema,
    create_mcp_client,
)
from app.backends.connection_manager import (
    BackendConnectionManager,
    BackendError,
    BackendTimeoutError,
    BackendUnavailableError,
    MCPResponse,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_connection_manager():
    """Create mock connection manager."""
    manager = MagicMock(spec=BackendConnectionManager)
    return manager


@pytest.fixture
def generic_client(mock_connection_manager):
    """Create generic MCP client for testing."""
    return GenericMCPClient(
        connection_manager=mock_connection_manager,
        backend_id="notion",
    )


# =============================================================================
# ServerInfo Tests
# =============================================================================


class TestServerInfo:
    """Tests for ServerInfo data class."""

    def test_from_dict_basic(self):
        """Test parsing basic server info."""
        data = {
            "name": "Test Server",
            "version": "1.0.0",
            "protocolVersion": "2024-11-05",
        }

        info = ServerInfo.from_dict(data)

        assert info.name == "Test Server"
        assert info.version == "1.0.0"
        assert info.protocol_version == "2024-11-05"
        assert info.capabilities == []

    def test_from_dict_with_capabilities(self):
        """Test parsing server info with capabilities."""
        data = {
            "name": "Full Server",
            "version": "2.0.0",
            "capabilities": {
                "tools": {},
                "resources": {},
            },
        }

        info = ServerInfo.from_dict(data)

        assert MCPCapability.TOOLS in info.capabilities
        assert MCPCapability.RESOURCES in info.capabilities
        assert MCPCapability.PROMPTS not in info.capabilities
        assert MCPCapability.LOGGING not in info.capabilities

    def test_from_dict_with_all_capabilities(self):
        """Test parsing server info with all capabilities."""
        data = {
            "name": "Complete Server",
            "version": "3.0.0",
            "capabilities": {
                "tools": {},
                "resources": {},
                "prompts": {},
                "logging": {},
            },
        }

        info = ServerInfo.from_dict(data)

        assert MCPCapability.TOOLS in info.capabilities
        assert MCPCapability.RESOURCES in info.capabilities
        assert MCPCapability.PROMPTS in info.capabilities
        assert MCPCapability.LOGGING in info.capabilities

    def test_from_dict_missing_fields(self):
        """Test parsing server info with missing fields uses defaults."""
        data = {}

        info = ServerInfo.from_dict(data)

        assert info.name == "Unknown"
        assert info.version == "0.0.0"
        assert info.protocol_version == "2024-11-05"

    def test_raw_preserved(self):
        """Test that raw dict is preserved."""
        data = {"name": "Test", "version": "1.0", "extra_field": "value"}

        info = ServerInfo.from_dict(data)

        assert info.raw == data
        assert info.raw["extra_field"] == "value"


# =============================================================================
# ToolSchema Tests
# =============================================================================


class TestToolSchema:
    """Tests for ToolSchema data class."""

    def test_from_dict(self):
        """Test parsing tool schema."""
        data = {
            "name": "search_pages",
            "description": "Search for pages",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
            },
        }

        tool = ToolSchema.from_dict(data)

        assert tool.name == "search_pages"
        assert tool.description == "Search for pages"
        assert tool.input_schema["type"] == "object"
        assert "query" in tool.input_schema["properties"]

    def test_from_dict_minimal(self):
        """Test parsing minimal tool schema."""
        data = {"name": "simple_tool"}

        tool = ToolSchema.from_dict(data)

        assert tool.name == "simple_tool"
        assert tool.description == ""
        assert tool.input_schema == {}

    def test_to_dict(self):
        """Test converting tool to dict."""
        tool = ToolSchema(
            name="read_page",
            description="Read a page",
            input_schema={"type": "object"},
        )

        result = tool.to_dict()

        assert result["name"] == "read_page"
        assert result["description"] == "Read a page"
        assert result["inputSchema"]["type"] == "object"

    def test_raw_preserved(self):
        """Test that raw dict is preserved."""
        data = {"name": "tool", "description": "desc", "custom": "value"}

        tool = ToolSchema.from_dict(data)

        assert tool.raw == data
        assert tool.raw["custom"] == "value"


# =============================================================================
# ToolResult Tests
# =============================================================================


class TestToolResult:
    """Tests for ToolResult data class."""

    def test_from_response_success(self):
        """Test parsing successful response."""
        response = MCPResponse(
            result={
                "content": [{"type": "text", "text": "Found 3 pages"}],
            },
        )

        result = ToolResult.from_response(response, duration_ms=100)

        assert result.status == ToolCallStatus.SUCCESS
        assert not result.is_error
        assert result.duration_ms == 100
        assert len(result.content) == 1
        assert "Found 3 pages" in result.get_text_content()

    def test_from_response_error(self):
        """Test parsing error response."""
        response = MCPResponse(
            error={"code": -32000, "message": "Something went wrong"},
        )

        result = ToolResult.from_response(response)

        assert result.status == ToolCallStatus.ERROR
        assert result.is_error
        assert result.error_message == "Something went wrong"

    def test_from_response_tool_error(self):
        """Test parsing tool that returned isError=true."""
        response = MCPResponse(
            result={
                "content": [{"type": "text", "text": "Page not found"}],
                "isError": True,
            },
        )

        result = ToolResult.from_response(response)

        assert result.status == ToolCallStatus.ERROR
        assert result.is_error
        assert result.error_message == "Page not found"

    def test_from_response_empty_content(self):
        """Test parsing response with empty content."""
        response = MCPResponse(result={"content": []})

        result = ToolResult.from_response(response)

        assert result.status == ToolCallStatus.SUCCESS
        assert not result.is_error
        assert result.content == []

    def test_from_error_factory(self):
        """Test creating error result with factory."""
        result = ToolResult.from_error(ToolCallStatus.TIMEOUT, "Request timed out")

        assert result.status == ToolCallStatus.TIMEOUT
        assert result.is_error
        assert result.error_message == "Request timed out"
        assert len(result.content) == 1
        assert result.content[0]["type"] == "text"

    def test_get_text_content_multiple(self):
        """Test extracting text content from multiple items."""
        result = ToolResult(
            status=ToolCallStatus.SUCCESS,
            content=[
                {"type": "text", "text": "Line 1"},
                {"type": "image", "data": "..."},
                {"type": "text", "text": "Line 2"},
            ],
        )

        text = result.get_text_content()

        assert "Line 1" in text
        assert "Line 2" in text
        assert "..." not in text  # image data not included

    def test_get_text_content_empty(self):
        """Test extracting text content when empty."""
        result = ToolResult(status=ToolCallStatus.SUCCESS, content=[])

        assert result.get_text_content() == ""


# =============================================================================
# BaseMCPClient Abstract Tests
# =============================================================================


class TestBaseMCPClientAbstract:
    """Tests for abstract base class."""

    def test_cannot_instantiate_directly(self, mock_connection_manager):
        """Test that BaseMCPClient cannot be instantiated."""
        with pytest.raises(TypeError, match="abstract"):
            BaseMCPClient(mock_connection_manager)


# =============================================================================
# GenericMCPClient Tests
# =============================================================================


class TestGenericMCPClient:
    """Tests for GenericMCPClient."""

    def test_backend_id(self, generic_client):
        """Test backend_id property."""
        assert generic_client.backend_id == "notion"

    def test_initial_state(self, generic_client):
        """Test initial client state."""
        assert not generic_client.is_initialized
        assert generic_client.server_info is None

    def test_connection_manager_property(self, generic_client, mock_connection_manager):
        """Test connection_manager property."""
        assert generic_client.connection_manager is mock_connection_manager

    def test_repr(self, generic_client):
        """Test string representation."""
        repr_str = repr(generic_client)
        assert "GenericMCPClient" in repr_str
        assert "notion" in repr_str
        assert "not initialized" in repr_str

    def test_repr_after_init(self, generic_client):
        """Test repr changes after initialization."""
        generic_client._initialized = True
        repr_str = repr(generic_client)
        assert "initialized" in repr_str
        assert "not initialized" not in repr_str

    @pytest.mark.asyncio
    async def test_initialize_success(self, generic_client, mock_connection_manager):
        """Test successful initialization."""
        mock_connection_manager.send_initialize = AsyncMock(
            return_value=MCPResponse(
                result={
                    "serverInfo": {
                        "name": "Notion MCP Server",
                        "version": "1.0.0",
                    },
                },
            )
        )

        info = await generic_client.initialize(auth_token="Bearer xyz")

        assert generic_client.is_initialized
        assert info.name == "Notion MCP Server"
        assert info.version == "1.0.0"
        assert generic_client.server_info == info

        mock_connection_manager.send_initialize.assert_called_once_with(
            backend_id="notion",
            client_info={"name": "DeepTrail Gateway", "version": "1.0.0"},
            auth_header="Bearer xyz",
        )

    @pytest.mark.asyncio
    async def test_initialize_with_custom_client_info(
        self, generic_client, mock_connection_manager
    ):
        """Test initialization with custom client info."""
        mock_connection_manager.send_initialize = AsyncMock(
            return_value=MCPResponse(
                result={"serverInfo": {"name": "Test", "version": "1.0"}},
            )
        )

        custom_info = {"name": "CustomClient", "version": "2.0.0"}
        await generic_client.initialize(client_info=custom_info)

        call_args = mock_connection_manager.send_initialize.call_args
        assert call_args.kwargs["client_info"] == custom_info

    @pytest.mark.asyncio
    async def test_initialize_failure(self, generic_client, mock_connection_manager):
        """Test initialization failure."""
        mock_connection_manager.send_initialize = AsyncMock(
            return_value=MCPResponse(
                error={"code": -32000, "message": "Auth failed"},
            )
        )

        with pytest.raises(MCPInitializeError, match="Auth failed"):
            await generic_client.initialize()

        assert not generic_client.is_initialized

    @pytest.mark.asyncio
    async def test_initialize_backend_error(
        self, generic_client, mock_connection_manager
    ):
        """Test initialization with backend error."""
        mock_connection_manager.send_initialize = AsyncMock(
            side_effect=BackendError("Connection refused")
        )

        with pytest.raises(MCPInitializeError, match="Connection refused"):
            await generic_client.initialize()

    @pytest.mark.asyncio
    async def test_list_tools(self, generic_client, mock_connection_manager):
        """Test listing tools."""
        mock_connection_manager.send_tools_list = AsyncMock(
            return_value=MCPResponse(
                result={
                    "tools": [
                        {"name": "search_pages", "description": "Search"},
                        {"name": "read_page", "description": "Read"},
                    ],
                },
            )
        )

        tools = await generic_client.list_tools(auth_token="Bearer xyz")

        assert len(tools) == 2
        assert tools[0].name == "search_pages"
        assert tools[1].name == "read_page"

        mock_connection_manager.send_tools_list.assert_called_once_with(
            backend_id="notion",
            auth_header="Bearer xyz",
        )

    @pytest.mark.asyncio
    async def test_list_tools_caching(self, generic_client, mock_connection_manager):
        """Test that tools are cached."""
        mock_connection_manager.send_tools_list = AsyncMock(
            return_value=MCPResponse(
                result={"tools": [{"name": "tool1", "description": ""}]},
            )
        )

        # First call
        tools1 = await generic_client.list_tools()
        # Second call should use cache
        tools2 = await generic_client.list_tools()

        # Only one request made
        assert mock_connection_manager.send_tools_list.call_count == 1
        assert tools1 == tools2

    @pytest.mark.asyncio
    async def test_list_tools_force_refresh(
        self, generic_client, mock_connection_manager
    ):
        """Test force refresh bypasses cache."""
        mock_connection_manager.send_tools_list = AsyncMock(
            return_value=MCPResponse(
                result={"tools": []},
            )
        )

        await generic_client.list_tools()
        await generic_client.list_tools(force_refresh=True)

        assert mock_connection_manager.send_tools_list.call_count == 2

    @pytest.mark.asyncio
    async def test_list_tools_no_cache(self, generic_client, mock_connection_manager):
        """Test disabling cache."""
        mock_connection_manager.send_tools_list = AsyncMock(
            return_value=MCPResponse(result={"tools": []})
        )

        await generic_client.list_tools(use_cache=False)
        await generic_client.list_tools(use_cache=False)

        assert mock_connection_manager.send_tools_list.call_count == 2

    @pytest.mark.asyncio
    async def test_list_tools_failure(self, generic_client, mock_connection_manager):
        """Test list tools failure."""
        mock_connection_manager.send_tools_list = AsyncMock(
            return_value=MCPResponse(
                error={"code": -32000, "message": "Not authorized"}
            )
        )

        with pytest.raises(MCPClientError, match="Not authorized"):
            await generic_client.list_tools()

    @pytest.mark.asyncio
    async def test_call_tool_success(self, generic_client, mock_connection_manager):
        """Test successful tool call."""
        mock_connection_manager.send_tools_call = AsyncMock(
            return_value=MCPResponse(
                result={
                    "content": [{"type": "text", "text": "Result"}],
                },
            )
        )

        result = await generic_client.call_tool(
            "search_pages",
            {"query": "test"},
            auth_token="Bearer xyz",
        )

        assert result.status == ToolCallStatus.SUCCESS
        assert not result.is_error
        assert result.duration_ms is not None
        assert result.duration_ms > 0

        # Verify call was made with correct params
        mock_connection_manager.send_tools_call.assert_called_once_with(
            backend_id="notion",
            tool_name="search_pages",
            arguments={"query": "test"},
            auth_header="Bearer xyz",
        )

    @pytest.mark.asyncio
    async def test_call_tool_with_error_response(
        self, generic_client, mock_connection_manager
    ):
        """Test tool call with error in response."""
        mock_connection_manager.send_tools_call = AsyncMock(
            return_value=MCPResponse(
                error={"code": -32000, "message": "Tool execution failed"}
            )
        )

        result = await generic_client.call_tool("search_pages", {})

        assert result.status == ToolCallStatus.ERROR
        assert result.is_error
        assert "Tool execution failed" in result.error_message

    @pytest.mark.asyncio
    async def test_call_tool_timeout(self, generic_client, mock_connection_manager):
        """Test tool call timeout."""
        mock_connection_manager.send_tools_call = AsyncMock(
            side_effect=BackendTimeoutError("Timeout")
        )

        result = await generic_client.call_tool("search_pages", {})

        assert result.status == ToolCallStatus.TIMEOUT
        assert result.is_error
        assert "timed out" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_call_tool_backend_unavailable(
        self, generic_client, mock_connection_manager
    ):
        """Test tool call when backend unavailable."""
        mock_connection_manager.send_tools_call = AsyncMock(
            side_effect=BackendUnavailableError("Backend is down")
        )

        result = await generic_client.call_tool("search_pages", {})

        assert result.status == ToolCallStatus.ERROR
        assert result.is_error
        assert "unavailable" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_call_tool_backend_error(
        self, generic_client, mock_connection_manager
    ):
        """Test tool call with unexpected backend error."""
        mock_connection_manager.send_tools_call = AsyncMock(
            side_effect=BackendError("Unexpected error")
        )

        with pytest.raises(MCPToolCallError, match="Unexpected error"):
            await generic_client.call_tool("search_pages", {})


# =============================================================================
# Namespace Handling Tests
# =============================================================================


class TestNamespaceHandling:
    """Tests for namespace handling."""

    def test_strip_namespace(self, generic_client):
        """Test stripping namespace prefix."""
        assert generic_client.strip_namespace("notion.search_pages") == "search_pages"
        assert generic_client.strip_namespace("notion.read_page") == "read_page"

    def test_strip_namespace_different_backend(self, generic_client):
        """Test stripping namespace for different backend keeps it."""
        # Different backend prefix should not be stripped
        assert (
            generic_client.strip_namespace("slack.send_message") == "slack.send_message"
        )

    def test_strip_namespace_no_prefix(self, generic_client):
        """Test stripping when no prefix present."""
        assert generic_client.strip_namespace("search_pages") == "search_pages"

    def test_strip_namespace_multiple_dots(self, generic_client):
        """Test stripping with multiple dots in name."""
        assert (
            generic_client.strip_namespace("notion.search.deep.pages")
            == "search.deep.pages"
        )

    def test_add_namespace(self, generic_client):
        """Test adding namespace prefix."""
        assert generic_client.add_namespace("search_pages") == "notion.search_pages"

    def test_add_namespace_already_prefixed(self, generic_client):
        """Test adding namespace when already prefixed."""
        assert (
            generic_client.add_namespace("notion.search_pages")
            == "notion.search_pages"
        )

    def test_add_namespace_different_prefix(self, generic_client):
        """Test adding namespace when has different prefix."""
        # Already has a dot, so won't add another prefix
        assert (
            generic_client.add_namespace("slack.send_message") == "slack.send_message"
        )

    @pytest.mark.asyncio
    async def test_call_tool_with_namespace(
        self, generic_client, mock_connection_manager
    ):
        """Test calling tool with namespaced name."""
        mock_connection_manager.send_tools_call = AsyncMock(
            return_value=MCPResponse(result={"content": []})
        )

        await generic_client.call_tool_with_namespace(
            "notion.search_pages",
            {"query": "test"},
        )

        # Should strip prefix before sending
        mock_connection_manager.send_tools_call.assert_called_once()
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "search_pages"

    @pytest.mark.asyncio
    async def test_call_tool_with_namespace_different_backend(
        self, generic_client, mock_connection_manager
    ):
        """Test calling tool with different backend namespace."""
        mock_connection_manager.send_tools_call = AsyncMock(
            return_value=MCPResponse(result={"content": []})
        )

        await generic_client.call_tool_with_namespace(
            "slack.send_message",  # Different backend
            {},
        )

        # Should NOT strip prefix (different backend)
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "slack.send_message"


# =============================================================================
# Subclass Hooks Tests
# =============================================================================


class TestSubclassHooks:
    """Tests for subclass hook methods."""

    @pytest.mark.asyncio
    async def test_validate_tool_arguments_hook(self, mock_connection_manager):
        """Test argument validation hook."""

        class ValidatingClient(GenericMCPClient):
            def validate_tool_arguments(self, tool_name, arguments):
                if "required_field" not in arguments:
                    raise ValueError("required_field is required")
                return arguments

        client = ValidatingClient(mock_connection_manager, "test")

        with pytest.raises(ValueError, match="required_field"):
            await client.call_tool("some_tool", {})

    @pytest.mark.asyncio
    async def test_validate_tool_arguments_transforms(self, mock_connection_manager):
        """Test that validation can transform arguments."""

        class TransformingClient(GenericMCPClient):
            def validate_tool_arguments(self, tool_name, arguments):
                # Add default value
                return {"limit": 10, **arguments}

        mock_connection_manager.send_tools_call = AsyncMock(
            return_value=MCPResponse(result={"content": []})
        )

        client = TransformingClient(mock_connection_manager, "test")
        await client.call_tool("search", {"query": "test"})

        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["arguments"]["limit"] == 10
        assert call_args.kwargs["arguments"]["query"] == "test"

    @pytest.mark.asyncio
    async def test_transform_tool_result_hook(self, mock_connection_manager):
        """Test result transformation hook."""

        class TransformingClient(GenericMCPClient):
            def transform_tool_result(self, tool_name, result):
                # Add metadata to result
                result.raw["transformed"] = True
                return result

        mock_connection_manager.send_tools_call = AsyncMock(
            return_value=MCPResponse(result={"content": []})
        )

        client = TransformingClient(mock_connection_manager, "test")
        result = await client.call_tool("some_tool", {})

        assert result.raw.get("transformed") is True

    def test_get_default_headers_hook(self, mock_connection_manager):
        """Test default headers hook."""

        class CustomHeadersClient(GenericMCPClient):
            def get_default_headers(self):
                return {"X-Custom-Header": "custom-value"}

        client = CustomHeadersClient(mock_connection_manager, "test")
        headers = client.get_default_headers()

        assert headers["X-Custom-Header"] == "custom-value"


# =============================================================================
# Auto-Initialize Tests
# =============================================================================


class TestAutoInitialize:
    """Tests for auto-initialize behavior."""

    @pytest.mark.asyncio
    async def test_auto_initialize_on_list_tools(self, mock_connection_manager):
        """Test auto-initialize when listing tools."""
        client = GenericMCPClient(
            mock_connection_manager,
            "notion",
            auto_initialize=True,
        )

        mock_connection_manager.send_initialize = AsyncMock(
            return_value=MCPResponse(
                result={"serverInfo": {"name": "Test", "version": "1"}}
            )
        )
        mock_connection_manager.send_tools_list = AsyncMock(
            return_value=MCPResponse(result={"tools": []})
        )

        await client.list_tools()

        # Should have initialized first
        mock_connection_manager.send_initialize.assert_called_once()
        mock_connection_manager.send_tools_list.assert_called_once()
        assert client.is_initialized

    @pytest.mark.asyncio
    async def test_auto_initialize_on_call_tool(self, mock_connection_manager):
        """Test auto-initialize when calling tool."""
        client = GenericMCPClient(
            mock_connection_manager,
            "notion",
            auto_initialize=True,
        )

        mock_connection_manager.send_initialize = AsyncMock(
            return_value=MCPResponse(
                result={"serverInfo": {"name": "Test", "version": "1"}}
            )
        )
        mock_connection_manager.send_tools_call = AsyncMock(
            return_value=MCPResponse(result={"content": []})
        )

        await client.call_tool("search", {})

        mock_connection_manager.send_initialize.assert_called_once()
        assert client.is_initialized

    @pytest.mark.asyncio
    async def test_no_auto_initialize_by_default(self, mock_connection_manager):
        """Test no auto-initialize by default."""
        client = GenericMCPClient(mock_connection_manager, "notion")

        mock_connection_manager.send_tools_list = AsyncMock(
            return_value=MCPResponse(result={"tools": []})
        )

        await client.list_tools()

        # Should NOT have initialized
        mock_connection_manager.send_initialize.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_initialize_only_once(self, mock_connection_manager):
        """Test auto-initialize only happens once."""
        client = GenericMCPClient(
            mock_connection_manager,
            "notion",
            auto_initialize=True,
        )

        mock_connection_manager.send_initialize = AsyncMock(
            return_value=MCPResponse(
                result={"serverInfo": {"name": "Test", "version": "1"}}
            )
        )
        mock_connection_manager.send_tools_list = AsyncMock(
            return_value=MCPResponse(result={"tools": []})
        )

        await client.list_tools()
        await client.list_tools(force_refresh=True)

        # Should only initialize once
        mock_connection_manager.send_initialize.call_count == 1


# =============================================================================
# Utility Methods Tests
# =============================================================================


class TestUtilityMethods:
    """Tests for utility methods."""

    def test_clear_cache(self, generic_client):
        """Test clearing cache."""
        generic_client._tools_cache = [ToolSchema(name="test", description="")]

        generic_client.clear_cache()

        assert generic_client._tools_cache is None

    def test_reset(self, generic_client):
        """Test resetting client state."""
        generic_client._initialized = True
        generic_client._server_info = ServerInfo(name="Test", version="1")
        generic_client._tools_cache = []

        generic_client.reset()

        assert not generic_client.is_initialized
        assert generic_client.server_info is None
        assert generic_client._tools_cache is None

    @pytest.mark.asyncio
    async def test_check_health(self, generic_client, mock_connection_manager):
        """Test health check delegation."""
        mock_connection_manager.check_backend_health = AsyncMock(return_value=True)

        result = await generic_client.check_health()

        assert result is True
        mock_connection_manager.check_backend_health.assert_called_once_with("notion")

    @pytest.mark.asyncio
    async def test_check_health_unhealthy(
        self, generic_client, mock_connection_manager
    ):
        """Test health check when unhealthy."""
        mock_connection_manager.check_backend_health = AsyncMock(return_value=False)

        result = await generic_client.check_health()

        assert result is False


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for create_mcp_client factory."""

    def test_create_mcp_client(self, mock_connection_manager):
        """Test factory creates client."""
        client = create_mcp_client(mock_connection_manager, "notion")

        assert isinstance(client, BaseMCPClient)
        assert isinstance(client, GenericMCPClient)
        assert client.backend_id == "notion"

    def test_create_mcp_client_with_options(self, mock_connection_manager):
        """Test factory passes options."""
        client = create_mcp_client(
            mock_connection_manager,
            "slack",
            auto_initialize=True,
        )

        assert client.backend_id == "slack"
        assert client._auto_initialize is True

    def test_create_mcp_client_different_backends(self, mock_connection_manager):
        """Test factory creates different backends."""
        notion_client = create_mcp_client(mock_connection_manager, "notion")
        slack_client = create_mcp_client(mock_connection_manager, "slack")
        hubspot_client = create_mcp_client(mock_connection_manager, "hubspot")

        assert notion_client.backend_id == "notion"
        assert slack_client.backend_id == "slack"
        assert hubspot_client.backend_id == "hubspot"


# =============================================================================
# Enum Tests
# =============================================================================


class TestEnums:
    """Tests for enum values."""

    def test_mcp_capability_values(self):
        """Test MCPCapability enum values."""
        assert MCPCapability.TOOLS.value == "tools"
        assert MCPCapability.RESOURCES.value == "resources"
        assert MCPCapability.PROMPTS.value == "prompts"
        assert MCPCapability.LOGGING.value == "logging"

    def test_tool_call_status_values(self):
        """Test ToolCallStatus enum values."""
        assert ToolCallStatus.SUCCESS.value == "success"
        assert ToolCallStatus.ERROR.value == "error"
        assert ToolCallStatus.TIMEOUT.value == "timeout"
        assert ToolCallStatus.UNAUTHORIZED.value == "unauthorized"
