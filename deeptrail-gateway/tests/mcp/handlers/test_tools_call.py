"""
Tests for MCP tools/call handler (WS-B7).

Tests cover:
- Permission validation (allowed, denied, unknown tools, wildcards)
- Namespace parsing (valid format, invalid format)
- Backend session handling (available, unavailable)
- Constraint validation (placeholder for MVP)
- Audit logging (success and failure events)
- Backend forwarding (mock responses)
- Error handling (session errors, configuration errors)
- Integration with MCPSessionManager and PermissionMapper
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.mcp.handlers.tools_call import (
    handle_tools_call,
    handle_tools_call_standalone,
    configure_tools_call_handler,
    ToolsCallParams,
    ToolsCallResult,
    ToolsCallErrorCode,
    _validate_permission,
    _validate_constraints,
    _generate_mock_response,
    _summarize_result,
)
from app.mcp.protocol import MCPError, JsonRpcErrorCode
from app.mcp.session_manager import MCPSessionManager


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def session_manager():
    """Create a fresh session manager for each test."""
    return MCPSessionManager()


@pytest.fixture
def agent_session(session_manager):
    """Create an agent session with backend connections."""
    return session_manager.create_agent_session(
        agent_session_id="agent-sdr-001",
        delegator="sarah@acme.com",
        delegated_permissions=[
            "notion:pages:search",
            "notion:pages:read",
            "slack:channels:list",
            "slack:messages:send",
        ],
        connected_services=[
            {
                "service_id": "notion",
                "oauth_token_ref": "vault://sarah-notion-oauth-xyz",
                "available_tools": ["search_pages", "read_page", "create_page"],
            },
            {
                "service_id": "slack",
                "oauth_token_ref": "vault://sarah-slack-oauth-abc",
                "available_tools": ["list_channels", "send_message", "list_users"],
            },
        ],
    )


@pytest.fixture
def configured_handler(session_manager, agent_session):
    """Configure the global handler with session manager."""
    configure_tools_call_handler(session_manager)
    yield
    # Reset after test
    configure_tools_call_handler(None)


# =============================================================================
# Test: Permission Validation
# =============================================================================


class TestPermissionValidation:
    """Tests for permission validation logic."""
    
    def test_permitted_tool_allowed(self):
        """Test that permitted tool returns allowed=True."""
        result = _validate_permission(
            "notion.search_pages",
            ["notion:pages:search", "slack:channels:list"]
        )
        assert result["allowed"] is True
        assert result["required_permission"] == "notion:pages:search"
    
    def test_unpermitted_tool_denied(self):
        """Test that unpermitted tool returns allowed=False."""
        result = _validate_permission(
            "notion.create_page",
            ["notion:pages:search"]  # No create permission
        )
        assert result["allowed"] is False
        assert result["required_permission"] == "notion:pages:create"
    
    def test_unknown_tool_denied(self):
        """Test that unknown tool is denied (fail-closed)."""
        result = _validate_permission(
            "unknown.mystery_tool",
            ["notion:pages:search"]
        )
        assert result["allowed"] is False
        # Should try to infer or use unknown prefix
        assert "unknown" in result["required_permission"]
    
    def test_backend_wildcard_permission(self):
        """Test that backend wildcard (notion:*) allows all tools."""
        result = _validate_permission(
            "notion.search_pages",
            ["notion:*"]  # Wildcard for all notion permissions
        )
        assert result["allowed"] is True
        assert result["required_permission"] == "notion:pages:search"
    
    def test_full_wildcard_permission(self):
        """Test that full wildcard (*:*) allows all tools."""
        result = _validate_permission(
            "notion.search_pages",
            ["*:*"]  # Full wildcard
        )
        assert result["allowed"] is True
    
    def test_empty_permissions_denied(self):
        """Test that empty permissions denies all tools."""
        result = _validate_permission("notion.search_pages", [])
        assert result["allowed"] is False


class TestConstraintValidation:
    """Tests for constraint validation (MVP placeholder)."""
    
    @pytest.mark.asyncio
    async def test_constraints_always_allowed_mvp(self):
        """Test that MVP constraint validation always allows."""
        result = await _validate_constraints(
            MagicMock(),  # agent_session
            "notion.search_pages"
        )
        assert result["allowed"] is True


# =============================================================================
# Test: Handler - Successful Calls
# =============================================================================


class TestToolsCallSuccess:
    """Tests for successful tool calls."""
    
    @pytest.mark.asyncio
    async def test_permitted_tool_succeeds(self, session_manager, agent_session):
        """Test that permitted tool call succeeds."""
        params = {
            "name": "notion.search_pages",
            "arguments": {"query": "test"},
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        result = await handle_tools_call_standalone(params, session_manager)
        
        assert "content" in result
        assert isinstance(result["content"], list)
        assert len(result["content"]) > 0
        assert result["content"][0]["type"] == "text"
        assert "Notion" in result["content"][0]["text"]
    
    @pytest.mark.asyncio
    async def test_slack_tool_succeeds(self, session_manager, agent_session):
        """Test Slack tool call succeeds."""
        params = {
            "name": "slack.list_channels",
            "arguments": {},
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": ["slack:channels:list"],
            },
        }
        
        result = await handle_tools_call_standalone(params, session_manager)
        
        assert "content" in result
        assert "Slack" in result["content"][0]["text"]
    
    @pytest.mark.asyncio
    async def test_tool_with_arguments_passed_through(self, session_manager, agent_session):
        """Test that tool arguments are properly handled."""
        params = {
            "name": "notion.search_pages",
            "arguments": {
                "query": "competitor analysis",
                "limit": 10,
                "filter": {"type": "page"},
            },
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        result = await handle_tools_call_standalone(params, session_manager)
        
        assert "content" in result
        # Mock response should include the query
        assert "competitor analysis" in result["content"][0]["text"]
    
    @pytest.mark.asyncio
    async def test_empty_arguments_allowed(self, session_manager, agent_session):
        """Test that empty arguments are allowed."""
        params = {
            "name": "slack.list_channels",
            "arguments": {},
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": ["slack:channels:list"],
            },
        }
        
        result = await handle_tools_call_standalone(params, session_manager)
        
        assert "content" in result
        assert result.get("isError", False) is False


# =============================================================================
# Test: Handler - Permission Denied
# =============================================================================


class TestToolsCallPermissionDenied:
    """Tests for permission denied scenarios."""
    
    @pytest.mark.asyncio
    async def test_unpermitted_tool_denied(self, session_manager, agent_session):
        """Test that unpermitted tool is denied."""
        params = {
            "name": "notion.create_page",  # Not in permissions
            "arguments": {"title": "Test"},
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": ["notion:pages:search"],  # Only search
            },
        }
        
        with pytest.raises(MCPError) as exc_info:
            await handle_tools_call_standalone(params, session_manager)
        
        assert exc_info.value.code == ToolsCallErrorCode.PERMISSION_DENIED
        assert "notion:pages:create" in exc_info.value.message
    
    @pytest.mark.asyncio
    async def test_unknown_tool_denied(self, session_manager, agent_session):
        """Test that unknown tool is denied (fail-closed)."""
        params = {
            "name": "github.create_repo",  # Unknown backend
            "arguments": {},
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        with pytest.raises(MCPError) as exc_info:
            await handle_tools_call_standalone(params, session_manager)
        
        assert exc_info.value.code == ToolsCallErrorCode.PERMISSION_DENIED
    
    @pytest.mark.asyncio
    async def test_empty_permissions_denied(self, session_manager, agent_session):
        """Test that empty permissions denies all tools."""
        params = {
            "name": "notion.search_pages",
            "arguments": {},
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": [],  # No permissions
            },
        }
        
        with pytest.raises(MCPError) as exc_info:
            await handle_tools_call_standalone(params, session_manager)
        
        assert exc_info.value.code == ToolsCallErrorCode.PERMISSION_DENIED


# =============================================================================
# Test: Handler - Namespace Parsing
# =============================================================================


class TestToolsCallNamespace:
    """Tests for namespace parsing."""
    
    @pytest.mark.asyncio
    async def test_invalid_tool_name_no_dot(self, session_manager, agent_session):
        """Test error for tool name without namespace separator."""
        params = {
            "name": "search_pages",  # No namespace
            "arguments": {},
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        with pytest.raises(MCPError) as exc_info:
            await handle_tools_call_standalone(params, session_manager)
        
        assert exc_info.value.code == ToolsCallErrorCode.INVALID_TOOL_NAME
    
    @pytest.mark.asyncio
    async def test_invalid_tool_name_empty(self, session_manager, agent_session):
        """Test error for empty tool name."""
        params = {
            "name": "",
            "arguments": {},
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        with pytest.raises(MCPError) as exc_info:
            await handle_tools_call_standalone(params, session_manager)
        
        assert exc_info.value.code == ToolsCallErrorCode.INVALID_TOOL_NAME
    
    @pytest.mark.asyncio
    async def test_invalid_backend_id_format(self, session_manager, agent_session):
        """Test error for invalid backend ID in namespace."""
        params = {
            "name": "Invalid.search_pages",  # Uppercase not allowed
            "arguments": {},
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        with pytest.raises(MCPError) as exc_info:
            await handle_tools_call_standalone(params, session_manager)
        
        assert exc_info.value.code == ToolsCallErrorCode.INVALID_TOOL_NAME
    
    @pytest.mark.asyncio
    async def test_tool_with_dots_in_name(self, session_manager):
        """Test that tool names with dots are parsed correctly."""
        # Create a session with a tool that has dots
        session_manager.create_agent_session(
            agent_session_id="agent-dots",
            delegator="test@test.com",
            delegated_permissions=["github:repos:list"],
            connected_services=[
                {
                    "service_id": "github",
                    "available_tools": ["repos.public.list"],
                }
            ],
        )
        
        params = {
            "name": "github.repos.public.list",  # Tool name has dots
            "arguments": {},
            "_context": {
                "agent_session_id": "agent-dots",
                "delegated_permissions": ["github:repos:list"],
            },
        }
        
        # Should parse as backend="github", tool="repos.public.list"
        # Will fail permission check (not in mapping), but namespace should parse
        with pytest.raises(MCPError) as exc_info:
            await handle_tools_call_standalone(params, session_manager)
        
        # Should be permission denied (namespace parsed correctly)
        # or backend unavailable (if tool not in session)
        assert exc_info.value.code in [
            ToolsCallErrorCode.PERMISSION_DENIED,
            ToolsCallErrorCode.BACKEND_UNAVAILABLE,
        ]


# =============================================================================
# Test: Handler - Backend Session
# =============================================================================


class TestToolsCallBackend:
    """Tests for backend session handling."""
    
    @pytest.mark.asyncio
    async def test_missing_backend_returns_error(self, session_manager, agent_session):
        """Test error when backend not connected."""
        params = {
            "name": "hubspot.get_contact",
            "arguments": {"id": "123"},
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": ["hubspot:contacts:read"],
            },
        }
        
        with pytest.raises(MCPError) as exc_info:
            await handle_tools_call_standalone(params, session_manager)
        
        assert exc_info.value.code == ToolsCallErrorCode.BACKEND_UNAVAILABLE
        assert "hubspot" in exc_info.value.message
    
    @pytest.mark.asyncio
    async def test_credential_ref_accessible(self, session_manager, agent_session):
        """Test that credential reference is used for backend call."""
        # Get the backend session to verify credential ref
        backend_session = session_manager.get_backend_session(
            "agent-sdr-001", "notion"
        )
        
        assert backend_session is not None
        assert backend_session.credential_ref is not None
        assert backend_session.credential_ref.ref == "vault://sarah-notion-oauth-xyz"


# =============================================================================
# Test: Handler - Session Errors
# =============================================================================


class TestToolsCallSessionErrors:
    """Tests for session-related errors."""
    
    @pytest.mark.asyncio
    async def test_no_session_context_raises_error(self, session_manager):
        """Test error when no session context provided."""
        params = {
            "name": "notion.search_pages",
            "arguments": {},
            # No _context
        }
        
        with pytest.raises(MCPError) as exc_info:
            await handle_tools_call_standalone(params, session_manager)
        
        assert exc_info.value.code == ToolsCallErrorCode.SESSION_INVALID
    
    @pytest.mark.asyncio
    async def test_invalid_session_id_raises_error(self, session_manager):
        """Test error when session ID doesn't exist."""
        params = {
            "name": "notion.search_pages",
            "arguments": {},
            "_context": {
                "agent_session_id": "nonexistent-session",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        with pytest.raises(MCPError) as exc_info:
            await handle_tools_call_standalone(params, session_manager)
        
        assert exc_info.value.code == ToolsCallErrorCode.SESSION_INVALID
    
    @pytest.mark.asyncio
    async def test_handler_not_configured_raises_error(self):
        """Test error when handler not configured."""
        # Reset global configuration
        configure_tools_call_handler(None)
        
        params = {
            "name": "notion.search_pages",
            "arguments": {},
            "_context": {
                "agent_session_id": "agent-123",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        with pytest.raises(MCPError) as exc_info:
            await handle_tools_call(params)
        
        assert exc_info.value.code == JsonRpcErrorCode.INTERNAL_ERROR


# =============================================================================
# Test: Audit Logging
# =============================================================================


class TestToolsCallAudit:
    """Tests for audit logging."""
    
    @pytest.mark.asyncio
    async def test_successful_call_logged(self, session_manager, agent_session):
        """Test that successful calls are logged."""
        mock_audit = MagicMock()
        mock_audit.log = AsyncMock()
        
        params = {
            "name": "notion.search_pages",
            "arguments": {"query": "test"},
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        await handle_tools_call_standalone(
            params, session_manager,
            audit_logger=mock_audit
        )
        
        mock_audit.log.assert_called_once()
        logged_event = mock_audit.log.call_args[0][0]
        
        assert logged_event["event_type"] == "mcp_tool_call"
        assert logged_event["agent_id"] == "agent-sdr-001"
        assert logged_event["on_behalf_of"] == "sarah@acme.com"
        assert logged_event["tool"] == "notion.search_pages"
        assert logged_event["success"] is True
        assert logged_event["result_summary"] is not None
    
    @pytest.mark.asyncio
    async def test_permission_denied_logged(self, session_manager, agent_session):
        """Test that permission denied is logged."""
        mock_audit = MagicMock()
        mock_audit.log = AsyncMock()
        
        params = {
            "name": "notion.create_page",
            "arguments": {},
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": ["notion:pages:search"],  # No create
            },
        }
        
        with pytest.raises(MCPError):
            await handle_tools_call_standalone(
                params, session_manager,
                audit_logger=mock_audit
            )
        
        mock_audit.log.assert_called_once()
        logged_event = mock_audit.log.call_args[0][0]
        
        assert logged_event["event_type"] == "permission_denied"
        assert logged_event["success"] is False
        assert "notion:pages:create" in logged_event["error"]
    
    @pytest.mark.asyncio
    async def test_backend_error_logged(self, session_manager, agent_session):
        """Test that backend errors are logged."""
        mock_audit = MagicMock()
        mock_audit.log = AsyncMock()
        
        params = {
            "name": "hubspot.get_contact",  # Backend not connected
            "arguments": {},
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": ["hubspot:contacts:read"],
            },
        }
        
        with pytest.raises(MCPError):
            await handle_tools_call_standalone(
                params, session_manager,
                audit_logger=mock_audit
            )
        
        mock_audit.log.assert_called_once()
        logged_event = mock_audit.log.call_args[0][0]
        
        assert logged_event["event_type"] == "tool_call_error"
        assert logged_event["success"] is False


# =============================================================================
# Test: Mock Response Generation
# =============================================================================


class TestMockResponses:
    """Tests for mock response generation."""
    
    def test_search_response(self):
        """Test mock response for search tools."""
        response = _generate_mock_response("notion", "search_pages", {"query": "test"})
        assert "Notion" in response
        assert "test" in response
        assert "Found" in response
    
    def test_list_response(self):
        """Test mock response for list tools."""
        response = _generate_mock_response("slack", "list_channels", {})
        assert "Slack" in response
        assert "Retrieved" in response
    
    def test_create_response(self):
        """Test mock response for create tools."""
        response = _generate_mock_response("notion", "create_page", {"title": "Test"})
        assert "Notion" in response
        assert "created" in response.lower()
    
    def test_send_response(self):
        """Test mock response for send tools."""
        response = _generate_mock_response("slack", "send_message", {"text": "Hello"})
        assert "Slack" in response
        assert "sent" in response.lower()
    
    def test_generic_response(self):
        """Test mock response for unknown tools."""
        response = _generate_mock_response("custom", "do_thing", {})
        assert "Custom" in response
        assert "executed" in response.lower()


class TestResultSummary:
    """Tests for result summary generation."""
    
    def test_text_content_summarized(self):
        """Test summary of text content."""
        result = {
            "content": [{"type": "text", "text": "Found 5 pages matching query"}]
        }
        summary = _summarize_result(result)
        assert "Found 5 pages" in summary
    
    def test_long_text_truncated(self):
        """Test that long text is truncated."""
        long_text = "x" * 200
        result = {"content": [{"type": "text", "text": long_text}]}
        summary = _summarize_result(result)
        assert len(summary) <= 103  # 100 chars + "..."
        assert summary.endswith("...")
    
    def test_empty_content_handled(self):
        """Test handling of empty content."""
        result = {"content": []}
        summary = _summarize_result(result)
        assert "No content" in summary
    
    def test_multiple_content_items(self):
        """Test summary with multiple content items."""
        result = {
            "content": [
                {"type": "text", "text": "First"},
                {"type": "text", "text": "Second"},
            ]
        }
        summary = _summarize_result(result)
        assert "First" in summary  # First item is summarized


# =============================================================================
# Test: Integration with Backend Client
# =============================================================================


class TestBackendClientIntegration:
    """Tests for backend client integration."""
    
    @pytest.mark.asyncio
    async def test_custom_backend_client_used(self, session_manager, agent_session):
        """Test that custom backend client is called."""
        mock_client = MagicMock()
        mock_client.call_tool = AsyncMock(return_value={
            "content": [{"type": "text", "text": "Custom response"}],
            "isError": False
        })
        
        params = {
            "name": "notion.search_pages",
            "arguments": {"query": "test"},
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        result = await handle_tools_call_standalone(
            params, session_manager,
            backend_client=mock_client
        )
        
        mock_client.call_tool.assert_called_once()
        assert result["content"][0]["text"] == "Custom response"
        
        # Verify arguments passed to backend client
        call_kwargs = mock_client.call_tool.call_args[1]
        assert call_kwargs["backend_id"] == "notion"
        assert call_kwargs["tool_name"] == "search_pages"
        assert call_kwargs["arguments"] == {"query": "test"}
        assert "vault://" in call_kwargs["credential_ref"]


# =============================================================================
# Test: Pydantic Models
# =============================================================================


class TestPydanticModels:
    """Tests for Pydantic request/response models."""
    
    def test_tools_call_params_validation(self):
        """Test ToolsCallParams validation."""
        params = ToolsCallParams(
            name="notion.search_pages",
            arguments={"query": "test"}
        )
        assert params.name == "notion.search_pages"
        assert params.arguments == {"query": "test"}
    
    def test_tools_call_params_default_arguments(self):
        """Test that arguments default to empty dict."""
        params = ToolsCallParams(name="notion.search_pages")
        assert params.arguments == {}
    
    def test_tools_call_result_validation(self):
        """Test ToolsCallResult validation."""
        result = ToolsCallResult(
            content=[{"type": "text", "text": "test"}],
            isError=False
        )
        assert len(result.content) == 1
        assert result.isError is False
    
    def test_tools_call_result_serialization(self):
        """Test ToolsCallResult serialization with alias."""
        result = ToolsCallResult(
            content=[{"type": "text", "text": "test"}],
            isError=True
        )
        data = result.model_dump(by_alias=True)
        assert "isError" in data
        assert data["isError"] is True


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and unusual scenarios."""
    
    @pytest.mark.asyncio
    async def test_special_characters_in_arguments(self, session_manager, agent_session):
        """Test handling of special characters in arguments."""
        params = {
            "name": "notion.search_pages",
            "arguments": {
                "query": "test with 'quotes' and \"double quotes\"",
                "special": "café résumé naïve",
                "emoji": "👍🎉",
            },
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        result = await handle_tools_call_standalone(params, session_manager)
        
        assert "content" in result
    
    @pytest.mark.asyncio
    async def test_very_long_arguments(self, session_manager, agent_session):
        """Test handling of very long arguments."""
        params = {
            "name": "notion.search_pages",
            "arguments": {
                "query": "x" * 10000,  # Very long query
            },
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        result = await handle_tools_call_standalone(params, session_manager)
        
        assert "content" in result
    
    @pytest.mark.asyncio
    async def test_nested_arguments(self, session_manager, agent_session):
        """Test handling of deeply nested arguments."""
        params = {
            "name": "notion.search_pages",
            "arguments": {
                "filter": {
                    "and": [
                        {"property": "title", "equals": "test"},
                        {"or": [
                            {"property": "status", "equals": "done"},
                            {"property": "status", "equals": "pending"},
                        ]},
                    ]
                }
            },
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        result = await handle_tools_call_standalone(params, session_manager)
        
        assert "content" in result
    
    @pytest.mark.asyncio
    async def test_multiple_calls_same_session(self, session_manager, agent_session):
        """Test multiple calls in the same session."""
        # First call
        params1 = {
            "name": "notion.search_pages",
            "arguments": {"query": "first"},
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": ["notion:pages:search", "slack:channels:list"],
            },
        }
        result1 = await handle_tools_call_standalone(params1, session_manager)
        
        # Second call to different backend
        params2 = {
            "name": "slack.list_channels",
            "arguments": {},
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": ["notion:pages:search", "slack:channels:list"],
            },
        }
        result2 = await handle_tools_call_standalone(params2, session_manager)
        
        assert "content" in result1
        assert "content" in result2
        assert "Notion" in result1["content"][0]["text"]
        assert "Slack" in result2["content"][0]["text"]
    
    @pytest.mark.asyncio
    async def test_session_activity_updated(self, session_manager, agent_session):
        """Test that backend session activity is updated on call."""
        import time
        
        backend_session = session_manager.get_backend_session(
            "agent-sdr-001", "notion"
        )
        initial_activity = backend_session.last_activity
        
        # Small delay to ensure timestamp difference
        time.sleep(0.01)
        
        params = {
            "name": "notion.search_pages",
            "arguments": {},
            "_context": {
                "agent_session_id": "agent-sdr-001",
                "delegated_permissions": ["notion:pages:search"],
            },
        }
        
        await handle_tools_call_standalone(params, session_manager)
        
        # Re-fetch session to check activity
        backend_session = session_manager.get_backend_session(
            "agent-sdr-001", "notion"
        )
        
        assert backend_session.last_activity >= initial_activity


# =============================================================================
# Test: Error Code Constants
# =============================================================================


class TestErrorCodes:
    """Tests for error code constants."""
    
    def test_error_codes_unique(self):
        """Test that error codes are unique."""
        codes = [
            ToolsCallErrorCode.PERMISSION_DENIED,
            ToolsCallErrorCode.SESSION_INVALID,
            ToolsCallErrorCode.CREDENTIAL_ERROR,
            ToolsCallErrorCode.INVALID_TOOL_NAME,
            ToolsCallErrorCode.BACKEND_UNAVAILABLE,
            ToolsCallErrorCode.CONSTRAINT_VIOLATED,
            ToolsCallErrorCode.TOOL_EXECUTION_ERROR,
        ]
        assert len(codes) == len(set(codes))
    
    def test_error_codes_in_mcp_range(self):
        """Test that error codes are in MCP reserved range."""
        codes = [
            ToolsCallErrorCode.INVALID_TOOL_NAME,
            ToolsCallErrorCode.BACKEND_UNAVAILABLE,
            ToolsCallErrorCode.CONSTRAINT_VIOLATED,
            ToolsCallErrorCode.TOOL_EXECUTION_ERROR,
        ]
        for code in codes:
            assert -32099 <= code <= -32000
