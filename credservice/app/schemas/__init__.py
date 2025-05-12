"""Expose Pydantic schemas for easier importing."""

from .agent import (
    AgentBase,
    AgentCreate,
    AgentUpdate,
    Agent,  # This is our main response schema
    AgentList,
    AgentRotateKeyRequest # Kept if still relevant
    # AgentInDBBase might not need to be exported if only used by CRUD
)
from .credential import (
    CredentialBase,
    CredentialIssueRequest,
    CredentialIssueResponse,
    CredentialVerifyResponse,
    CredentialRevokeResponse,
    Credential
)
from .token import Token, AgentLogin

__all__ = [
    "AgentBase",
    "AgentCreate",
    "AgentUpdate",
    "Agent",
    "AgentList",
    "AgentRotateKeyRequest",
    "CredentialBase",
    "CredentialIssueRequest",
    "CredentialIssueResponse",
    "CredentialVerifyResponse",
    "CredentialRevokeResponse",
    "Credential",
    "Token",
    "AgentLogin",
]

# Add any other schemas needed globally here 