"""
Unit tests for MCP tools/list handler.

Tests cover:
- Basic tools/list functionality
- Permission filtering
- Namespace prefixing
- Session management integration
- Tool cache integration
- Error handling
- Edge cases
"""

import pytest

from app.mcp.handlers.tools_list import (
    handle_tools_list,
    handle_tools_list_standalone,
    configure_tools_list_handler,
    ToolsListParams,
    ToolsListResult,
    _build_tool_schemas,
    _build_minimal_tool_schema,
)
from app.mcp.permission_mapper import PermissionMapper
from app.mcp.session_manager import MCPSessionManager
from app.mcp.tool_cache import ToolCache, CachedTool


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def session_manager():
    """Create a fresh session manager."""
    return MCPSessionManager()


@pytest.fixture
def tool_cache():
    """Create a fresh tool cache."""
    return ToolCache(ttl_seconds=300)


@pytest.fixture
def populated_tool_cache(tool_cache):
    """Create a tool cache with sample tools."""
    # Notion tools
    tool_cache.set_tools("notion", [
        CachedTool(name="search_pages", description="Search pages in workspace"),
        CachedTool(name="read_page", description="Read a page"),
        CachedTool(name="create_page", description="Create a new page"),
    ])
    
    # Slack tools
    tool_cache.set_tools("slack", [
        CachedTool(name="list_channels", description="List available channels"),
        CachedTool(name="send_message", description="Send a message"),
        CachedTool(name="search_messages", description="Search messages"),
    ])
    
    return tool_cache


@pytest.fixture
def configured_handler(session_manager, populated_tool_cache):
    """Configure the handler with dependencies."""
    configure_tools_list_handler(session_manager, populated_tool_cache)
    return session_manager, populated_tool_cache


@pytest.fixture
def agent_session_with_permissions(session_manager):
    """Create an agent session with specific permissions."""
    session = session_manager.create_agent_session(
        agent_session_id="agent-test-001",
        delegator="sarah@acme.com",
        delegated_permissions=[
            "notion:pages:search",
            "notion:pages:read",
            "slack:channels:list",
        ],
        connected_services=[
            {
                "service_id": "notion",
                "oauth_token_ref": "vault://notion-token",
                "available_tools": ["search_pages", "read_page", "create_page"],
            },
            {
                "service_id": "slack",
                "oauth_token_ref": "vault://slack-token",
                "available_tools": ["list_channels", "send_message", "search_messages"],
            },
        ],
    )
    return session


# =============================================================================
# Test ToolsListParams Model
# =============================================================================


class TestToolsListParams:
    """Tests for ToolsListParams model."""
    
    def test_default_cursor_is_none(self):
        """Test that cursor defaults to None."""
        params = ToolsListParams()
        assert params.cursor is None
    
    def test_accepts_cursor(self):
        """Test that cursor can be provided."""
        params = ToolsListParams(cursor="next-page-token")
        assert params.cursor == "next-page-token"
    
    def test_allows_extra_fields(self):
        """Test that extra fields are allowed."""
        params = ToolsListParams(extra_field="value")
        # Should not raise


# =============================================================================
# Test ToolsListResult Model
# =============================================================================


class TestToolsListResult:
    """Tests for ToolsListResult model."""
    
    def test_default_empty_tools(self):
        """Test that tools defaults to empty list."""
        result = ToolsListResult()
        assert result.tools == []
        assert result.nextCursor is None
    
    def test_serialization(self):
        """Test serialization to dict."""
        result = ToolsListResult(
            tools=[{"name": "test.tool"}],
            nextCursor="cursor-123",
        )
        
        data = result.model_dump(by_alias=True)
        
        assert data["tools"] == [{"name": "test.tool"}]
        assert data["nextCursor"] == "cursor-123"


# =============================================================================
# Test handle_tools_list
# =============================================================================


class TestHandleToolsList:
    """Tests for handle_tools_list handler."""
    
    @pytest.mark.asyncio
    async def test_returns_filtered_tools(
        self, configured_handler, agent_session_with_permissions
    ):
        """Test that only permitted tools are returned."""
        session_manager, _ = configured_handler
        
        params = {
            "_context": {
                "agent_session_id": "agent-test-001",
                "delegated_permissions": [
                    "notion:pages:search",
                    "notion:pages:read",
                    "slack:channels:list",
                ],
            },
        }
        
        result = await handle_tools_list(params)
        
        assert "tools" in result
        tools = result["tools"]
        tool_names = [t["name"] for t in tools]
        
        # Should include permitted tools
        assert "notion.search_pages" in tool_names
        assert "notion.read_page" in tool_names
        assert "slack.list_channels" in tool_names
        
        # Should NOT include unpermitted tools
        assert "notion.create_page" not in tool_names
        assert "slack.send_message" not in tool_names
    
    @pytest.mark.asyncio
    async def test_tools_are_namespaced(
        self, configured_handler, agent_session_with_permissions
    ):
        """Test that tools have namespace prefix."""
        params = {
            "_context": {
                "agent_session_id": "agent-test-001",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        result = await handle_tools_list(params)
        tools = result["tools"]
        
        # All tool names should have namespace prefix
        for tool in tools:
            assert "." in tool["name"]
            backend = tool["name"].split(".")[0]
            assert backend in ["notion", "slack"]
    
    @pytest.mark.asyncio
    async def test_descriptions_have_backend_prefix(
        self, configured_handler, agent_session_with_permissions
    ):
        """Test that descriptions are enhanced with backend prefix."""
        params = {
            "_context": {
                "agent_session_id": "agent-test-001",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        result = await handle_tools_list(params)
        tools = result["tools"]
        
        # Find the notion.search_pages tool
        notion_tool = next(t for t in tools if t["name"] == "notion.search_pages")
        assert "[Notion]" in notion_tool["description"]
    
    @pytest.mark.asyncio
    async def test_empty_permissions_returns_empty_list(
        self, configured_handler, agent_session_with_permissions
    ):
        """Test that no permissions = no tools."""
        params = {
            "_context": {
                "agent_session_id": "agent-test-001",
                "delegated_permissions": [],  # No permissions
            },
        }
        
        result = await handle_tools_list(params)
        
        assert result["tools"] == []
    
    @pytest.mark.asyncio
    async def test_no_session_returns_empty_list(self, configured_handler):
        """Test that missing session returns empty tools."""
        params = {
            "_context": {
                # No agent_session_id
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        result = await handle_tools_list(params)
        
        assert result["tools"] == []
    
    @pytest.mark.asyncio
    async def test_invalid_session_raises_error(self, configured_handler):
        """Test that invalid session ID raises error."""
        params = {
            "_context": {
                "agent_session_id": "nonexistent-session",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        from app.mcp.protocol import MCPError
        
        with pytest.raises(MCPError) as exc_info:
            await handle_tools_list(params)
        
        assert "Session not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_next_cursor_is_null(
        self, configured_handler, agent_session_with_permissions
    ):
        """Test that nextCursor is null (pagination not implemented)."""
        params = {
            "_context": {
                "agent_session_id": "agent-test-001",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        result = await handle_tools_list(params)
        
        assert result.get("nextCursor") is None


# =============================================================================
# Test handle_tools_list_standalone
# =============================================================================


class TestHandleToolsListStandalone:
    """Tests for standalone handler with explicit dependencies."""
    
    @pytest.mark.asyncio
    async def test_standalone_with_explicit_deps(
        self, session_manager, populated_tool_cache
    ):
        """Test standalone handler with explicit dependencies."""
        # Create session
        session_manager.create_agent_session(
            agent_session_id="standalone-agent",
            delegator="user@test.com",
            delegated_permissions=["notion:pages:search"],
            connected_services=[
                {
                    "service_id": "notion",
                    "available_tools": ["search_pages"],
                },
            ],
        )
        
        params = {
            "_context": {
                "agent_session_id": "standalone-agent",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        result = await handle_tools_list_standalone(
            params, session_manager, populated_tool_cache
        )
        
        assert len(result["tools"]) == 1
        assert result["tools"][0]["name"] == "notion.search_pages"


# =============================================================================
# Test _build_tool_schemas
# =============================================================================


class TestBuildToolSchemas:
    """Tests for _build_tool_schemas helper."""
    
    @pytest.mark.asyncio
    async def test_builds_schemas_from_cache(self, configured_handler):
        """Test building schemas when tools are in cache."""
        allowed_tools = ["notion.search_pages"]
        permissions = ["notion:pages:search"]
        
        schemas = await _build_tool_schemas(allowed_tools, permissions)
        
        assert len(schemas) == 1
        assert schemas[0]["name"] == "notion.search_pages"
        assert "description" in schemas[0]
    
    @pytest.mark.asyncio
    async def test_builds_minimal_schema_when_not_cached(self, configured_handler):
        """Test building minimal schema when tool not in cache."""
        # Use a tool that's permitted but not in cache
        PermissionMapper.add_mapping("custom.tool", "custom:action")
        
        allowed_tools = ["custom.tool"]
        permissions = ["custom:action"]
        
        schemas = await _build_tool_schemas(allowed_tools, permissions)
        
        assert len(schemas) == 1
        assert schemas[0]["name"] == "custom.tool"
        assert "inputSchema" in schemas[0]
    
    @pytest.mark.asyncio
    async def test_filters_unpermitted_defense_in_depth(self, configured_handler):
        """Test that unpermitted tools are filtered even if in allowed_tools."""
        # Simulate a bug where unpermitted tool got into allowed_tools
        allowed_tools = ["notion.search_pages", "notion.create_page"]
        permissions = ["notion:pages:search"]  # Only search permitted
        
        schemas = await _build_tool_schemas(allowed_tools, permissions)
        
        names = [s["name"] for s in schemas]
        assert "notion.search_pages" in names
        assert "notion.create_page" not in names


# =============================================================================
# Test _build_minimal_tool_schema
# =============================================================================


class TestBuildMinimalToolSchema:
    """Tests for _build_minimal_tool_schema helper."""
    
    def test_builds_correct_structure(self):
        """Test minimal schema has correct structure."""
        schema = _build_minimal_tool_schema("notion", "search_pages")
        
        assert schema["name"] == "notion.search_pages"
        assert "[Notion]" in schema["description"]
        assert schema["inputSchema"]["type"] == "object"
    
    def test_handles_underscore_in_backend(self):
        """Test handling of underscores in backend ID."""
        schema = _build_minimal_tool_schema("hub_spot", "get_contact")
        
        assert schema["name"] == "hub_spot.get_contact"
        assert "[Hub Spot]" in schema["description"]


# =============================================================================
# Test Integration
# =============================================================================


class TestToolsListIntegration:
    """Integration tests for tools/list."""
    
    @pytest.mark.asyncio
    async def test_full_flow_sarah_scenario(
        self, session_manager, populated_tool_cache
    ):
        """Test Sarah's journey: agent sees 4 tools, not 20+."""
        configure_tools_list_handler(session_manager, populated_tool_cache)
        
        # Sarah delegates limited permissions to her agent
        session_manager.create_agent_session(
            agent_session_id="sdr-agent-001",
            delegator="sarah@acme.com",
            delegated_permissions=[
                "notion:pages:search",
                "notion:pages:read",
                "slack:channels:list",
                "slack:messages:search",
            ],
            connected_services=[
                {
                    "service_id": "notion",
                    "available_tools": ["search_pages", "read_page", "create_page"],
                },
                {
                    "service_id": "slack",
                    "available_tools": ["list_channels", "send_message", "search_messages"],
                },
            ],
        )
        
        # Agent calls tools/list
        params = {
            "_context": {
                "agent_session_id": "sdr-agent-001",
                "delegated_permissions": [
                    "notion:pages:search",
                    "notion:pages:read",
                    "slack:channels:list",
                    "slack:messages:search",
                ],
            },
        }
        
        result = await handle_tools_list(params)
        
        # Agent should see exactly 4 tools
        tools = result["tools"]
        assert len(tools) == 4
        
        tool_names = [t["name"] for t in tools]
        assert "notion.search_pages" in tool_names
        assert "notion.read_page" in tool_names
        assert "slack.list_channels" in tool_names
        assert "slack.search_messages" in tool_names
        
        # Should NOT see unpermitted tools
        assert "notion.create_page" not in tool_names
        assert "slack.send_message" not in tool_names
    
    @pytest.mark.asyncio
    async def test_response_format_matches_mcp_spec(
        self, configured_handler, agent_session_with_permissions
    ):
        """Test that response matches MCP specification."""
        params = {
            "_context": {
                "agent_session_id": "agent-test-001",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        result = await handle_tools_list(params)
        
        # Check response structure
        assert "tools" in result
        assert isinstance(result["tools"], list)
        
        # Check tool structure
        if result["tools"]:
            tool = result["tools"][0]
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""
    
    @pytest.mark.asyncio
    async def test_empty_context(self, configured_handler):
        """Test handling of empty context."""
        params = {}  # No _context at all
        
        result = await handle_tools_list(params)
        
        # Should return empty tools, not error
        assert result["tools"] == []
    
    @pytest.mark.asyncio
    async def test_multiple_calls_same_session(
        self, session_manager, populated_tool_cache
    ):
        """Test multiple tools/list calls for same session."""
        # Create dedicated session for this test
        session_manager.create_agent_session(
            agent_session_id="multi-call-agent",
            delegator="user@test.com",
            delegated_permissions=["notion:pages:search"],
            connected_services=[
                {
                    "service_id": "notion",
                    "available_tools": ["search_pages"],
                },
            ],
        )
        
        params = {
            "_context": {
                "agent_session_id": "multi-call-agent",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        # Call multiple times with standalone handler
        result1 = await handle_tools_list_standalone(params.copy(), session_manager, populated_tool_cache)
        result2 = await handle_tools_list_standalone(params.copy(), session_manager, populated_tool_cache)
        result3 = await handle_tools_list_standalone(params.copy(), session_manager, populated_tool_cache)
        
        # Should return same results
        assert len(result1["tools"]) == len(result2["tools"]) == len(result3["tools"]) == 1
        assert result1["tools"][0]["name"] == result2["tools"][0]["name"] == result3["tools"][0]["name"]
    
    @pytest.mark.asyncio
    async def test_tool_without_namespace_skipped(
        self, session_manager, populated_tool_cache
    ):
        """Test that tools without namespace separator are skipped."""
        configure_tools_list_handler(session_manager, populated_tool_cache)
        
        # Create session with malformed tool name
        session = session_manager.create_agent_session(
            agent_session_id="test-agent",
            delegator="user@test.com",
            delegated_permissions=["notion:pages:search"],
            connected_services=[],
        )
        
        # Manually inject a bad tool name into session
        session._bad_tools = ["notool"]  # No namespace
        
        # The handler should gracefully handle this
        params = {
            "_context": {
                "agent_session_id": "test-agent",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        result = await handle_tools_list(params)
        
        # Should return empty (no valid tools)
        assert result["tools"] == []
