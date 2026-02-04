"""
MCP Session Manager

This module manages MCP sessions between the gateway (Virtual MCP Server) and
backend MCP servers. When an agent connects to the gateway, we create individual
sessions to each backend server on behalf of that agent.

Session Hierarchy:
- AgentMCPSession: One per agent connection to gateway
  - BackendMCPSession: One per backend (Notion, Slack, etc.)

Usage:
    from app.mcp.session_manager import MCPSessionManager, SessionState
    
    manager = MCPSessionManager()
    
    # Create session when agent connects
    session = manager.create_agent_session(
        agent_session_id="agent-123",
        delegator="sarah@acme.com",
        delegated_permissions=["notion:pages:search"],
        connected_services=[
            {"service_id": "notion", "oauth_token_ref": "vault://ref", "available_tools": ["search_pages"]}
        ]
    )
    
    # Get allowed tools for tools/list
    tools = manager.get_allowed_tools("agent-123")
    
    # Get credential for tools/call
    cred_ref = manager.get_credential_ref_for_tool("agent-123", "notion.search_pages")
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================


class SessionState(Enum):
    """
    MCP session connection states.
    
    Lifecycle: PENDING → INITIALIZED → CONNECTED → DISCONNECTED
    Or: PENDING → INITIALIZED → ERROR
    """
    PENDING = "pending"           # Session created, not yet initialized
    INITIALIZED = "initialized"   # Initialize handshake complete
    CONNECTED = "connected"       # Actively connected and ready
    DISCONNECTED = "disconnected" # Gracefully closed
    ERROR = "error"               # Error state


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class CredentialRef:
    """
    Reference to credentials stored in vault.
    
    We never store actual credentials in session data - only references
    that can be resolved by the credential injection middleware (C7).
    
    Attributes:
        type: Credential type ("oauth", "api_key", "bearer", etc.)
        ref: Vault reference URI (e.g., "vault://sarah-notion-oauth-xyz")
    """
    type: str
    ref: str
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization."""
        return {"type": self.type, "ref": self.ref}


@dataclass
class BackendMCPSession:
    """
    MCP session to a single backend server.
    
    Represents the gateway's connection to one backend (e.g., Notion)
    on behalf of an agent. Each agent may have multiple backend sessions.
    
    Attributes:
        mcp_session_id: Unique session ID (e.g., "mcpsess-notion-abc123")
        parent_agent_session: ID of parent AgentMCPSession
        server_id: Backend identifier (e.g., "notion", "slack")
        connection_state: Current connection state
        allowed_tools: Namespaced tools this session can access
        credential_ref: Reference to credentials for this backend
        created_at: Session creation timestamp
        last_activity: Last activity timestamp
    """
    mcp_session_id: str
    parent_agent_session: str
    server_id: str
    connection_state: SessionState
    allowed_tools: list[str]
    credential_ref: CredentialRef | None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization/logging."""
        return {
            "mcp_session_id": self.mcp_session_id,
            "parent_agent_session": self.parent_agent_session,
            "server_id": self.server_id,
            "connection_state": self.connection_state.value,
            "allowed_tools": self.allowed_tools,
            "injected_credentials": self.credential_ref.to_dict() if self.credential_ref else None,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
        }
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)


@dataclass
class AgentMCPSession:
    """
    Aggregate session for an agent connected to the Virtual MCP Server.
    
    Contains multiple BackendMCPSession instances (one per connected backend).
    This is the top-level session created when an agent calls initialize.
    
    Attributes:
        agent_session_id: Agent's session ID from authentication
        delegator: User who delegated permissions (e.g., "sarah@acme.com")
        delegated_permissions: List of permission strings from delegation
        backend_sessions: Dict mapping backend_id → BackendMCPSession
        created_at: Session creation timestamp
    """
    agent_session_id: str
    delegator: str
    delegated_permissions: list[str]
    backend_sessions: dict[str, BackendMCPSession] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def get_all_allowed_tools(self) -> list[str]:
        """
        Get aggregated list of all allowed tools across all backends.
        
        Returns:
            List of namespaced tool names (e.g., ["notion.search_pages", "slack.send_message"])
        """
        tools = []
        for session in self.backend_sessions.values():
            tools.extend(session.allowed_tools)
        return tools
    
    def get_backend_ids(self) -> list[str]:
        """Get list of connected backend IDs."""
        return list(self.backend_sessions.keys())
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization/logging."""
        return {
            "agent_session_id": self.agent_session_id,
            "delegator": self.delegator,
            "delegated_permissions": self.delegated_permissions,
            "backend_sessions": {
                k: v.to_dict() for k, v in self.backend_sessions.items()
            },
            "created_at": self.created_at.isoformat(),
        }


# =============================================================================
# Session Manager
# =============================================================================


class MCPSessionManager:
    """
    Manages MCP sessions between gateway and backend servers.
    
    For each agent that connects, we maintain:
    - One AgentMCPSession (the agent's view of the gateway)
    - Multiple BackendMCPSessions (gateway's connections to backends)
    
    This is in-memory storage for MVP. Production should use Redis or
    distributed cache for horizontal scaling.
    
    Thread Safety:
        This implementation is NOT thread-safe. For production, add locking
        or use a thread-safe backend like Redis.
    
    Usage:
        manager = MCPSessionManager()
        
        # On agent initialize
        session = manager.create_agent_session(
            agent_session_id="agent-123",
            delegator="sarah@acme.com",
            delegated_permissions=["notion:pages:search"],
            connected_services=[{"service_id": "notion", ...}]
        )
        
        # On tools/list
        tools = manager.get_allowed_tools("agent-123")
        
        # On tools/call
        cred = manager.get_credential_ref_for_tool("agent-123", "notion.search")
    """
    
    def __init__(self) -> None:
        """Initialize empty session store."""
        # agent_session_id -> AgentMCPSession
        self._sessions: dict[str, AgentMCPSession] = {}
    
    def _generate_session_id(self, prefix: str) -> str:
        """
        Generate unique session ID with prefix.
        
        Args:
            prefix: Prefix for the ID (e.g., "mcpsess-notion")
            
        Returns:
            Unique ID like "mcpsess-notion-abc123def456"
        """
        return f"{prefix}-{uuid.uuid4().hex[:12]}"
    
    def _filter_tools_by_permissions(
        self,
        backend_tools: list[str],
        delegated_permissions: list[str],
        backend_id: str
    ) -> list[str]:
        """
        Filter backend tools by delegated permissions.
        
        For MVP, we use simple prefix matching: if any permission starts
        with "{backend_id}:", all tools from that backend are allowed.
        
        Production should implement proper permission → tool mapping (C4).
        
        Args:
            backend_tools: Tools offered by backend (e.g., ["search_pages", "create_page"])
            delegated_permissions: Permissions from delegation (e.g., ["notion:pages:search"])
            backend_id: Backend identifier (e.g., "notion")
        
        Returns:
            List of namespaced tools agent can access (e.g., ["notion.search_pages"])
        """
        # Check if any permission grants access to this backend
        has_backend_permission = any(
            perm.startswith(f"{backend_id}:") for perm in delegated_permissions
        )
        
        if not has_backend_permission:
            return []
        
        # For MVP, grant all tools from permitted backends
        # TODO: Implement fine-grained tool→permission mapping (C4)
        return [f"{backend_id}.{tool}" for tool in backend_tools]
    
    def create_agent_session(
        self,
        agent_session_id: str,
        delegator: str,
        delegated_permissions: list[str],
        connected_services: list[dict[str, Any]]
    ) -> AgentMCPSession:
        """
        Create a new agent session with backend connections.
        
        Called during initialize when an agent connects to the gateway.
        Creates backend sessions for each connected service that the
        agent has permissions to access.
        
        Args:
            agent_session_id: Agent's session ID from authentication
            delegator: User who delegated permissions (e.g., "sarah@acme.com")
            delegated_permissions: List of delegated permission strings
            connected_services: List of service configs with:
                - service_id: Backend identifier (e.g., "notion")
                - oauth_token_ref: Vault reference for credentials (optional)
                - available_tools: Tools offered by backend (optional)
        
        Returns:
            Created AgentMCPSession with backend sessions
        
        Example:
            >>> manager.create_agent_session(
            ...     "agent-123",
            ...     "sarah@acme.com",
            ...     ["notion:pages:search", "slack:messages:read"],
            ...     [
            ...         {"service_id": "notion", "oauth_token_ref": "vault://ref1", 
            ...          "available_tools": ["search_pages", "read_page"]},
            ...         {"service_id": "slack", "oauth_token_ref": "vault://ref2",
            ...          "available_tools": ["search_messages"]}
            ...     ]
            ... )
        """
        # Check if session already exists
        if agent_session_id in self._sessions:
            logger.warning(f"Session already exists for agent {agent_session_id}, closing old session")
            self.close_agent_session(agent_session_id)
        
        # Create agent session
        agent_session = AgentMCPSession(
            agent_session_id=agent_session_id,
            delegator=delegator,
            delegated_permissions=delegated_permissions,
        )
        
        # Create backend session for each connected service
        for service in connected_services:
            service_id = service.get("service_id")
            if not service_id:
                logger.warning("Skipping service with no service_id")
                continue
            
            # Filter tools by permissions
            available_tools = service.get("available_tools", [])
            allowed_tools = self._filter_tools_by_permissions(
                available_tools,
                delegated_permissions,
                service_id
            )
            
            # Skip if no allowed tools for this backend
            if not allowed_tools:
                logger.debug(f"No allowed tools for {service_id}, skipping backend session")
                continue
            
            # Create credential reference if provided
            credential_ref = None
            oauth_ref = service.get("oauth_token_ref")
            if oauth_ref:
                credential_ref = CredentialRef(type="oauth", ref=oauth_ref)
            
            # Create backend session
            backend_session = BackendMCPSession(
                mcp_session_id=self._generate_session_id(f"mcpsess-{service_id}"),
                parent_agent_session=agent_session_id,
                server_id=service_id,
                connection_state=SessionState.INITIALIZED,
                allowed_tools=allowed_tools,
                credential_ref=credential_ref,
            )
            
            agent_session.backend_sessions[service_id] = backend_session
            logger.debug(
                f"Created backend session {backend_session.mcp_session_id} "
                f"for {service_id} with {len(allowed_tools)} tools"
            )
        
        # Store session
        self._sessions[agent_session_id] = agent_session
        logger.info(
            f"Created agent session {agent_session_id} with "
            f"{len(agent_session.backend_sessions)} backend connections"
        )
        
        return agent_session
    
    def get_agent_session(self, agent_session_id: str) -> AgentMCPSession | None:
        """
        Get agent session by ID.
        
        Args:
            agent_session_id: Agent's session ID
            
        Returns:
            AgentMCPSession or None if not found
        """
        return self._sessions.get(agent_session_id)
    
    def get_backend_session(
        self,
        agent_session_id: str,
        backend_id: str
    ) -> BackendMCPSession | None:
        """
        Get specific backend session for an agent.
        
        Args:
            agent_session_id: Agent's session ID
            backend_id: Backend identifier (e.g., "notion")
            
        Returns:
            BackendMCPSession or None if not found
        """
        agent_session = self.get_agent_session(agent_session_id)
        if not agent_session:
            return None
        return agent_session.backend_sessions.get(backend_id)
    
    def get_all_backend_sessions(
        self,
        agent_session_id: str
    ) -> list[BackendMCPSession]:
        """
        Get all backend sessions for an agent.
        
        Args:
            agent_session_id: Agent's session ID
            
        Returns:
            List of BackendMCPSession (empty if agent not found)
        """
        agent_session = self.get_agent_session(agent_session_id)
        if not agent_session:
            return []
        return list(agent_session.backend_sessions.values())
    
    def update_session_state(
        self,
        agent_session_id: str,
        backend_id: str,
        state: SessionState
    ) -> bool:
        """
        Update connection state for a backend session.
        
        Args:
            agent_session_id: Agent's session ID
            backend_id: Backend identifier
            state: New session state
            
        Returns:
            True if updated, False if session not found
        """
        session = self.get_backend_session(agent_session_id, backend_id)
        if not session:
            return False
        
        old_state = session.connection_state
        session.connection_state = state
        session.update_activity()
        
        logger.debug(
            f"Backend session {session.mcp_session_id} state: "
            f"{old_state.value} → {state.value}"
        )
        
        return True
    
    def close_agent_session(self, agent_session_id: str) -> bool:
        """
        Close agent session and all backend sessions.
        
        Marks all backend sessions as DISCONNECTED and removes
        the agent session from storage.
        
        Args:
            agent_session_id: Agent's session ID
            
        Returns:
            True if session existed and was closed
        """
        if agent_session_id not in self._sessions:
            return False
        
        agent_session = self._sessions[agent_session_id]
        
        # Mark all backend sessions as disconnected
        for backend_session in agent_session.backend_sessions.values():
            backend_session.connection_state = SessionState.DISCONNECTED
        
        # Remove from active sessions
        del self._sessions[agent_session_id]
        
        logger.info(
            f"Closed agent session {agent_session_id} with "
            f"{len(agent_session.backend_sessions)} backend sessions"
        )
        
        return True
    
    def get_allowed_tools(self, agent_session_id: str) -> list[str]:
        """
        Get aggregated list of allowed tools for agent.
        
        Returns all tools from all backend sessions.
        
        Args:
            agent_session_id: Agent's session ID
            
        Returns:
            List of namespaced tool names (empty if session not found)
        """
        agent_session = self.get_agent_session(agent_session_id)
        if not agent_session:
            return []
        return agent_session.get_all_allowed_tools()
    
    def get_credential_ref_for_tool(
        self,
        agent_session_id: str,
        namespaced_tool: str
    ) -> CredentialRef | None:
        """
        Get credential reference for executing a tool.
        
        Used by credential injection middleware (C7) to fetch
        actual credentials from vault.
        
        Args:
            agent_session_id: Agent's session ID
            namespaced_tool: Tool name (e.g., "notion.search_pages")
        
        Returns:
            CredentialRef for the backend, or None if not found
        """
        # Extract backend from namespaced tool name
        if "." not in namespaced_tool:
            logger.warning(f"Tool name not namespaced: {namespaced_tool}")
            return None
        
        backend_id = namespaced_tool.split(".", 1)[0]
        backend_session = self.get_backend_session(agent_session_id, backend_id)
        
        if not backend_session:
            logger.warning(
                f"No backend session for {backend_id} in agent {agent_session_id}"
            )
            return None
        
        # Update activity
        backend_session.update_activity()
        
        return backend_session.credential_ref
    
    def is_tool_allowed(
        self,
        agent_session_id: str,
        namespaced_tool: str
    ) -> bool:
        """
        Check if an agent is allowed to use a specific tool.
        
        Args:
            agent_session_id: Agent's session ID
            namespaced_tool: Tool name (e.g., "notion.search_pages")
            
        Returns:
            True if tool is in agent's allowed tools
        """
        allowed_tools = self.get_allowed_tools(agent_session_id)
        return namespaced_tool in allowed_tools
    
    def get_session_count(self) -> int:
        """Get number of active agent sessions."""
        return len(self._sessions)
    
    def get_all_session_ids(self) -> list[str]:
        """Get all active agent session IDs."""
        return list(self._sessions.keys())
