"""
Unit Tests for MCP Session Manager

This test suite validates the session manager implementation:
- Session creation and lifecycle
- Backend session management
- Tool filtering by permissions
- Credential reference handling
- Session isolation between agents

Test Organization:
1. SessionState Tests
2. CredentialRef Tests
3. BackendMCPSession Tests
4. AgentMCPSession Tests
5. MCPSessionManager Tests
6. Session Isolation Tests
7. Edge Cases
"""

import pytest
from datetime import datetime, timezone

from app.mcp.session_manager import (
    SessionState,
    CredentialRef,
    BackendMCPSession,
    AgentMCPSession,
    MCPSessionManager,
)


# =============================================================================
# SessionState Tests
# =============================================================================


class TestSessionState:
    """Tests for SessionState enum."""
    
    def test_session_states_exist(self):
        """Test all expected session states exist."""
        assert SessionState.PENDING.value == "pending"
        assert SessionState.INITIALIZED.value == "initialized"
        assert SessionState.CONNECTED.value == "connected"
        assert SessionState.DISCONNECTED.value == "disconnected"
        assert SessionState.ERROR.value == "error"
    
    def test_session_state_count(self):
        """Test correct number of states."""
        assert len(SessionState) == 5


# =============================================================================
# CredentialRef Tests
# =============================================================================


class TestCredentialRef:
    """Tests for CredentialRef dataclass."""
    
    def test_create_oauth_credential_ref(self):
        """Test creating OAuth credential reference."""
        cred = CredentialRef(type="oauth", ref="vault://sarah-notion-oauth-xyz")
        assert cred.type == "oauth"
        assert cred.ref == "vault://sarah-notion-oauth-xyz"
    
    def test_create_api_key_credential_ref(self):
        """Test creating API key credential reference."""
        cred = CredentialRef(type="api_key", ref="vault://api-key-123")
        assert cred.type == "api_key"
        assert cred.ref == "vault://api-key-123"
    
    def test_credential_ref_to_dict(self):
        """Test credential ref serialization."""
        cred = CredentialRef(type="oauth", ref="vault://ref")
        data = cred.to_dict()
        assert data == {"type": "oauth", "ref": "vault://ref"}


# =============================================================================
# BackendMCPSession Tests
# =============================================================================


class TestBackendMCPSession:
    """Tests for BackendMCPSession dataclass."""
    
    def test_create_backend_session(self):
        """Test creating backend session."""
        session = BackendMCPSession(
            mcp_session_id="mcpsess-notion-abc123",
            parent_agent_session="agent-123",
            server_id="notion",
            connection_state=SessionState.INITIALIZED,
            allowed_tools=["notion.search_pages", "notion.read_page"],
            credential_ref=CredentialRef(type="oauth", ref="vault://ref"),
        )
        
        assert session.mcp_session_id == "mcpsess-notion-abc123"
        assert session.parent_agent_session == "agent-123"
        assert session.server_id == "notion"
        assert session.connection_state == SessionState.INITIALIZED
        assert len(session.allowed_tools) == 2
        assert session.credential_ref is not None
    
    def test_backend_session_without_credentials(self):
        """Test backend session without credentials."""
        session = BackendMCPSession(
            mcp_session_id="mcpsess-test",
            parent_agent_session="agent-123",
            server_id="test",
            connection_state=SessionState.PENDING,
            allowed_tools=[],
            credential_ref=None,
        )
        
        assert session.credential_ref is None
    
    def test_backend_session_to_dict(self):
        """Test backend session serialization."""
        session = BackendMCPSession(
            mcp_session_id="mcpsess-notion-abc",
            parent_agent_session="agent-1",
            server_id="notion",
            connection_state=SessionState.CONNECTED,
            allowed_tools=["notion.search"],
            credential_ref=CredentialRef(type="oauth", ref="vault://x"),
        )
        
        data = session.to_dict()
        
        assert data["mcp_session_id"] == "mcpsess-notion-abc"
        assert data["server_id"] == "notion"
        assert data["connection_state"] == "connected"
        assert data["injected_credentials"]["type"] == "oauth"
    
    def test_backend_session_update_activity(self):
        """Test updating activity timestamp."""
        session = BackendMCPSession(
            mcp_session_id="test",
            parent_agent_session="agent",
            server_id="notion",
            connection_state=SessionState.CONNECTED,
            allowed_tools=[],
            credential_ref=None,
        )
        
        old_activity = session.last_activity
        session.update_activity()
        
        assert session.last_activity >= old_activity


# =============================================================================
# AgentMCPSession Tests
# =============================================================================


class TestAgentMCPSession:
    """Tests for AgentMCPSession dataclass."""
    
    def test_create_agent_session(self):
        """Test creating agent session."""
        session = AgentMCPSession(
            agent_session_id="agent-123",
            delegator="sarah@acme.com",
            delegated_permissions=["notion:pages:search"],
        )
        
        assert session.agent_session_id == "agent-123"
        assert session.delegator == "sarah@acme.com"
        assert len(session.delegated_permissions) == 1
        assert len(session.backend_sessions) == 0
    
    def test_agent_session_with_backends(self):
        """Test agent session with backend sessions."""
        session = AgentMCPSession(
            agent_session_id="agent-123",
            delegator="user@example.com",
            delegated_permissions=["notion:pages:read"],
        )
        
        # Add backend session
        backend = BackendMCPSession(
            mcp_session_id="mcpsess-notion",
            parent_agent_session="agent-123",
            server_id="notion",
            connection_state=SessionState.CONNECTED,
            allowed_tools=["notion.read_page"],
            credential_ref=None,
        )
        session.backend_sessions["notion"] = backend
        
        assert len(session.backend_sessions) == 1
        assert "notion" in session.backend_sessions
    
    def test_get_all_allowed_tools(self):
        """Test aggregating tools from all backends."""
        session = AgentMCPSession(
            agent_session_id="agent-123",
            delegator="user@example.com",
            delegated_permissions=[],
        )
        
        # Add Notion backend
        session.backend_sessions["notion"] = BackendMCPSession(
            mcp_session_id="mcpsess-notion",
            parent_agent_session="agent-123",
            server_id="notion",
            connection_state=SessionState.CONNECTED,
            allowed_tools=["notion.search_pages", "notion.read_page"],
            credential_ref=None,
        )
        
        # Add Slack backend
        session.backend_sessions["slack"] = BackendMCPSession(
            mcp_session_id="mcpsess-slack",
            parent_agent_session="agent-123",
            server_id="slack",
            connection_state=SessionState.CONNECTED,
            allowed_tools=["slack.send_message"],
            credential_ref=None,
        )
        
        tools = session.get_all_allowed_tools()
        
        assert len(tools) == 3
        assert "notion.search_pages" in tools
        assert "notion.read_page" in tools
        assert "slack.send_message" in tools
    
    def test_get_backend_ids(self):
        """Test getting list of backend IDs."""
        session = AgentMCPSession(
            agent_session_id="agent-123",
            delegator="user",
            delegated_permissions=[],
        )
        
        session.backend_sessions["notion"] = BackendMCPSession(
            mcp_session_id="m1", parent_agent_session="agent-123",
            server_id="notion", connection_state=SessionState.CONNECTED,
            allowed_tools=[], credential_ref=None,
        )
        session.backend_sessions["slack"] = BackendMCPSession(
            mcp_session_id="m2", parent_agent_session="agent-123",
            server_id="slack", connection_state=SessionState.CONNECTED,
            allowed_tools=[], credential_ref=None,
        )
        
        backend_ids = session.get_backend_ids()
        
        assert "notion" in backend_ids
        assert "slack" in backend_ids


# =============================================================================
# MCPSessionManager Tests
# =============================================================================


class TestMCPSessionManager:
    """Tests for MCPSessionManager."""
    
    @pytest.fixture
    def manager(self) -> MCPSessionManager:
        """Create fresh session manager."""
        return MCPSessionManager()
    
    def test_create_agent_session_basic(self, manager):
        """Test basic agent session creation."""
        session = manager.create_agent_session(
            agent_session_id="agent-123",
            delegator="sarah@acme.com",
            delegated_permissions=["notion:pages:search"],
            connected_services=[
                {
                    "service_id": "notion",
                    "oauth_token_ref": "vault://ref1",
                    "available_tools": ["search_pages", "read_page"]
                }
            ]
        )
        
        assert session.agent_session_id == "agent-123"
        assert session.delegator == "sarah@acme.com"
        assert len(session.backend_sessions) == 1
        assert "notion" in session.backend_sessions
    
    def test_create_agent_session_multiple_backends(self, manager):
        """Test session with multiple backends."""
        session = manager.create_agent_session(
            agent_session_id="agent-multi",
            delegator="user@example.com",
            delegated_permissions=["notion:pages:search", "slack:messages:read"],
            connected_services=[
                {"service_id": "notion", "oauth_token_ref": "vault://n", "available_tools": ["search_pages"]},
                {"service_id": "slack", "oauth_token_ref": "vault://s", "available_tools": ["search_messages"]},
            ]
        )
        
        assert len(session.backend_sessions) == 2
        assert "notion" in session.backend_sessions
        assert "slack" in session.backend_sessions
    
    def test_create_agent_session_no_permission_skips_backend(self, manager):
        """Test that backends without permissions are skipped."""
        session = manager.create_agent_session(
            agent_session_id="agent-limited",
            delegator="user@example.com",
            delegated_permissions=["notion:pages:search"],  # Only Notion permission
            connected_services=[
                {"service_id": "notion", "available_tools": ["search_pages"]},
                {"service_id": "slack", "available_tools": ["send_message"]},  # No permission
            ]
        )
        
        assert len(session.backend_sessions) == 1
        assert "notion" in session.backend_sessions
        assert "slack" not in session.backend_sessions
    
    def test_get_agent_session(self, manager):
        """Test getting agent session by ID."""
        manager.create_agent_session(
            "agent-123", "user", ["notion:pages:read"], []
        )
        
        session = manager.get_agent_session("agent-123")
        assert session is not None
        assert session.agent_session_id == "agent-123"
        
        # Non-existent session
        assert manager.get_agent_session("nonexistent") is None
    
    def test_get_backend_session(self, manager):
        """Test getting specific backend session."""
        manager.create_agent_session(
            "agent-123", "user", ["notion:pages:read"],
            [{"service_id": "notion", "oauth_token_ref": "ref", "available_tools": ["read_page"]}]
        )
        
        notion = manager.get_backend_session("agent-123", "notion")
        assert notion is not None
        assert notion.server_id == "notion"
        
        # Non-existent backend
        slack = manager.get_backend_session("agent-123", "slack")
        assert slack is None
    
    def test_get_all_backend_sessions(self, manager):
        """Test getting all backend sessions."""
        manager.create_agent_session(
            "agent-123", "user", ["notion:pages:read", "slack:messages:read"],
            [
                {"service_id": "notion", "available_tools": ["read_page"]},
                {"service_id": "slack", "available_tools": ["search_messages"]},
            ]
        )
        
        backends = manager.get_all_backend_sessions("agent-123")
        assert len(backends) == 2
        
        # Non-existent agent
        assert manager.get_all_backend_sessions("nonexistent") == []
    
    def test_update_session_state(self, manager):
        """Test updating backend session state."""
        manager.create_agent_session(
            "agent-123", "user", ["notion:pages:read"],
            [{"service_id": "notion", "available_tools": ["read_page"]}]
        )
        
        # Update state
        result = manager.update_session_state("agent-123", "notion", SessionState.CONNECTED)
        assert result is True
        
        # Verify state changed
        session = manager.get_backend_session("agent-123", "notion")
        assert session.connection_state == SessionState.CONNECTED
        
        # Non-existent session
        result = manager.update_session_state("agent-123", "slack", SessionState.CONNECTED)
        assert result is False
    
    def test_close_agent_session(self, manager):
        """Test closing agent session."""
        manager.create_agent_session(
            "agent-123", "user", ["notion:pages:read"],
            [{"service_id": "notion", "available_tools": ["read_page"]}]
        )
        
        assert manager.get_agent_session("agent-123") is not None
        
        # Close session
        result = manager.close_agent_session("agent-123")
        assert result is True
        
        # Session should be gone
        assert manager.get_agent_session("agent-123") is None
        
        # Closing non-existent session
        result = manager.close_agent_session("agent-123")
        assert result is False
    
    def test_get_allowed_tools(self, manager):
        """Test getting aggregated allowed tools."""
        manager.create_agent_session(
            "agent-123", "user",
            ["notion:pages:search", "slack:messages:search"],
            [
                {"service_id": "notion", "available_tools": ["search_pages"]},
                {"service_id": "slack", "available_tools": ["search_messages"]},
            ]
        )
        
        tools = manager.get_allowed_tools("agent-123")
        
        assert "notion.search_pages" in tools
        assert "slack.search_messages" in tools
        
        # Non-existent session
        assert manager.get_allowed_tools("nonexistent") == []
    
    def test_get_credential_ref_for_tool(self, manager):
        """Test getting credential reference for a tool."""
        manager.create_agent_session(
            "agent-123", "user", ["notion:pages:read"],
            [{"service_id": "notion", "oauth_token_ref": "vault://notion-token", "available_tools": ["read_page"]}]
        )
        
        cred = manager.get_credential_ref_for_tool("agent-123", "notion.read_page")
        
        assert cred is not None
        assert cred.type == "oauth"
        assert cred.ref == "vault://notion-token"
    
    def test_get_credential_ref_for_tool_not_found(self, manager):
        """Test credential ref for non-existent tool."""
        manager.create_agent_session(
            "agent-123", "user", ["notion:pages:read"],
            [{"service_id": "notion", "available_tools": ["read_page"]}]
        )
        
        # Non-namespaced tool
        assert manager.get_credential_ref_for_tool("agent-123", "read_page") is None
        
        # Wrong backend
        assert manager.get_credential_ref_for_tool("agent-123", "slack.send_message") is None
        
        # Wrong agent
        assert manager.get_credential_ref_for_tool("other-agent", "notion.read_page") is None
    
    def test_is_tool_allowed(self, manager):
        """Test checking if tool is allowed."""
        manager.create_agent_session(
            "agent-123", "user", ["notion:pages:read"],
            [{"service_id": "notion", "available_tools": ["read_page", "search_pages"]}]
        )
        
        assert manager.is_tool_allowed("agent-123", "notion.read_page") is True
        assert manager.is_tool_allowed("agent-123", "notion.search_pages") is True
        assert manager.is_tool_allowed("agent-123", "notion.create_page") is False
        assert manager.is_tool_allowed("agent-123", "slack.send_message") is False
    
    def test_get_session_count(self, manager):
        """Test getting session count."""
        assert manager.get_session_count() == 0
        
        manager.create_agent_session("agent-1", "user", [], [])
        assert manager.get_session_count() == 1
        
        manager.create_agent_session("agent-2", "user", [], [])
        assert manager.get_session_count() == 2
        
        manager.close_agent_session("agent-1")
        assert manager.get_session_count() == 1
    
    def test_get_all_session_ids(self, manager):
        """Test getting all session IDs."""
        manager.create_agent_session("agent-1", "user", [], [])
        manager.create_agent_session("agent-2", "user", [], [])
        
        ids = manager.get_all_session_ids()
        
        assert "agent-1" in ids
        assert "agent-2" in ids
    
    def test_recreate_session_closes_old(self, manager):
        """Test that creating session with same ID closes old session."""
        manager.create_agent_session(
            "agent-123", "old-user", ["old:perm"], []
        )
        
        # Create new session with same ID
        new_session = manager.create_agent_session(
            "agent-123", "new-user", ["new:perm"], []
        )
        
        # Should have new delegator
        assert new_session.delegator == "new-user"
        assert new_session.delegated_permissions == ["new:perm"]
        
        # Only one session should exist
        assert manager.get_session_count() == 1


# =============================================================================
# Session Isolation Tests
# =============================================================================


class TestSessionIsolation:
    """Tests for session isolation between agents."""
    
    @pytest.fixture
    def manager(self) -> MCPSessionManager:
        """Create manager with multiple agent sessions."""
        manager = MCPSessionManager()
        
        # Agent 1: Has Notion access
        manager.create_agent_session(
            "agent-1", "user-1", ["notion:pages:read"],
            [{"service_id": "notion", "oauth_token_ref": "vault://user1-notion", "available_tools": ["read_page"]}]
        )
        
        # Agent 2: Has Slack access
        manager.create_agent_session(
            "agent-2", "user-2", ["slack:messages:read"],
            [{"service_id": "slack", "oauth_token_ref": "vault://user2-slack", "available_tools": ["search_messages"]}]
        )
        
        return manager
    
    def test_agents_cannot_see_each_others_backends(self, manager):
        """Test that agents cannot access each other's backends."""
        # Agent 1 has Notion, not Slack
        assert manager.get_backend_session("agent-1", "notion") is not None
        assert manager.get_backend_session("agent-1", "slack") is None
        
        # Agent 2 has Slack, not Notion
        assert manager.get_backend_session("agent-2", "slack") is not None
        assert manager.get_backend_session("agent-2", "notion") is None
    
    def test_agents_have_isolated_tools(self, manager):
        """Test that agents have isolated tool lists."""
        agent1_tools = manager.get_allowed_tools("agent-1")
        agent2_tools = manager.get_allowed_tools("agent-2")
        
        assert "notion.read_page" in agent1_tools
        assert "slack.search_messages" not in agent1_tools
        
        assert "slack.search_messages" in agent2_tools
        assert "notion.read_page" not in agent2_tools
    
    def test_agents_have_isolated_credentials(self, manager):
        """Test that agents have isolated credentials."""
        cred1 = manager.get_credential_ref_for_tool("agent-1", "notion.read_page")
        assert cred1.ref == "vault://user1-notion"
        
        cred2 = manager.get_credential_ref_for_tool("agent-2", "slack.search_messages")
        assert cred2.ref == "vault://user2-slack"
        
        # Cross-access should fail
        assert manager.get_credential_ref_for_tool("agent-1", "slack.search_messages") is None
        assert manager.get_credential_ref_for_tool("agent-2", "notion.read_page") is None
    
    def test_closing_one_session_doesnt_affect_other(self, manager):
        """Test that closing one session doesn't affect others."""
        manager.close_agent_session("agent-1")
        
        # Agent 1 should be gone
        assert manager.get_agent_session("agent-1") is None
        
        # Agent 2 should still work
        assert manager.get_agent_session("agent-2") is not None
        assert manager.get_backend_session("agent-2", "slack") is not None


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""
    
    @pytest.fixture
    def manager(self) -> MCPSessionManager:
        """Create fresh session manager."""
        return MCPSessionManager()
    
    def test_empty_connected_services(self, manager):
        """Test session with no connected services."""
        session = manager.create_agent_session(
            "agent-123", "user", ["notion:pages:read"], []
        )
        
        assert len(session.backend_sessions) == 0
        assert manager.get_allowed_tools("agent-123") == []
    
    def test_service_without_service_id(self, manager):
        """Test that service without service_id is skipped."""
        session = manager.create_agent_session(
            "agent-123", "user", ["notion:pages:read"],
            [{"oauth_token_ref": "ref", "available_tools": ["read_page"]}]  # No service_id
        )
        
        assert len(session.backend_sessions) == 0
    
    def test_service_without_oauth_ref(self, manager):
        """Test service without OAuth reference."""
        session = manager.create_agent_session(
            "agent-123", "user", ["notion:pages:read"],
            [{"service_id": "notion", "available_tools": ["read_page"]}]  # No oauth_token_ref
        )
        
        backend = manager.get_backend_session("agent-123", "notion")
        assert backend is not None
        assert backend.credential_ref is None
    
    def test_service_without_available_tools(self, manager):
        """Test service without available tools list."""
        session = manager.create_agent_session(
            "agent-123", "user", ["notion:pages:read"],
            [{"service_id": "notion", "oauth_token_ref": "ref"}]  # No available_tools
        )
        
        # Should be skipped (no tools to allow)
        assert len(session.backend_sessions) == 0
    
    def test_unique_session_ids(self, manager):
        """Test that generated session IDs are unique."""
        manager.create_agent_session(
            "agent-1", "user", ["notion:pages:read", "slack:messages:read"],
            [
                {"service_id": "notion", "available_tools": ["read"]},
                {"service_id": "slack", "available_tools": ["search"]},
            ]
        )
        
        notion = manager.get_backend_session("agent-1", "notion")
        slack = manager.get_backend_session("agent-1", "slack")
        
        assert notion.mcp_session_id != slack.mcp_session_id
        assert "notion" in notion.mcp_session_id
        assert "slack" in slack.mcp_session_id
    
    def test_session_timestamps(self, manager):
        """Test that sessions have timestamps."""
        session = manager.create_agent_session(
            "agent-123", "user", ["notion:pages:read"],
            [{"service_id": "notion", "available_tools": ["read_page"]}]
        )
        
        assert session.created_at is not None
        assert session.created_at.tzinfo == timezone.utc
        
        backend = manager.get_backend_session("agent-123", "notion")
        assert backend.created_at is not None
        assert backend.last_activity is not None
