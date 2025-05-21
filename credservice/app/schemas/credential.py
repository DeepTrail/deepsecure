"""Pydantic schemas for Credential related API operations."""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import base64
import logging

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# --- Base Schema --- #

class CredentialBase(BaseModel):
    """Shared base properties for credentials."""
    agent_id: str = Field(..., example="agent_f3b4c1a9")
    scope: Optional[str] = Field(None, example="read:secrets:prod/app1")

# --- Issue Credential --- #

class CredentialIssueRequest(CredentialBase):
    """Schema for requesting a new credential to be issued."""
    ephemeral_public_key: str = Field(..., description="Base64 encoded X25519 public key from the agent.", example="base64_encoded_x25519_pub_key")
    signature: str = Field(..., description="Base64 encoded Ed25519 signature of the ephemeral_public_key by the agent's long-term key.", example="base64_encoded_signature")
    ttl: int = Field(..., gt=0, description="Requested Time-To-Live for the credential in seconds.", example=3600)
    origin_context: Optional[Dict[str, Any]] = Field(None, description="Optional context about the request origin.", example={"hostname": "agent-host-1", "ip": "192.168.1.100"})

    # Store decoded bytes after validation
    ephemeral_public_key_bytes: bytes | None = None
    signature_bytes: bytes | None = None

    @field_validator('ephemeral_public_key', 'signature')
    def decode_base64(cls, v: str, info) -> str:
        """Validate and decode base64 fields."""
        try:
            decoded_bytes = base64.b64decode(v)
            # Store bytes in the instance context for CRUD to use
            if info.field_name == 'ephemeral_public_key':
                # Basic validation for X25519 key size
                if len(decoded_bytes) != 32:
                    raise ValueError("Decoded ephemeral public key must be 32 bytes long")
                # Add to validated data - this won't work directly, handle in CRUD
            elif info.field_name == 'signature':
                # Basic validation for Ed25519 signature size
                if len(decoded_bytes) != 64:
                    raise ValueError("Decoded signature must be 64 bytes long")
                # Add to validated data - this won't work directly, handle in CRUD
            return v # Return original string
        except (ValueError, base64.binascii.Error) as e:
            logger.error(f"Base64 decoding failed for field {info.field_name}: {e}")
            raise ValueError(f"Invalid base64 encoding for {info.field_name}: {e}")

class CredentialIssueResponse(CredentialBase):
    """Schema for the response after successfully issuing a credential."""
    credential_id: str = Field(..., example=str(uuid.uuid4()))
    ephemeral_public_key: str = Field(..., description="Base64 encoded X25519 public key.")
    expires_at: datetime
    origin_context: Optional[Dict[str, Any]] = Field(None, description="Context of the request origin, if provided and processed.")

    model_config = {
        "from_attributes": True
    }

    @field_validator('ephemeral_public_key', mode='before')
    def encode_key_bytes(cls, v):
        if isinstance(v, bytes):
            return base64.b64encode(v).decode('utf-8')
        return v

# --- Verify Credential --- #

class CredentialVerifyResponse(BaseModel):
    """Schema for the response when verifying a credential."""
    credential_id: str
    is_valid: bool
    status: str = Field(..., example="valid | expired | revoked | not_found")
    scope: Optional[str] = None
    agent_id: Optional[str] = None
    expires_at: Optional[datetime] = None

# --- Revoke Credential --- #

class CredentialRevokeResponse(BaseModel):
    """Schema for the response after revoking a credential."""
    credential_id: str
    status: str = Field(..., example="revoked | already_revoked | not_found")

# --- General Credential Representation --- #

class Credential(CredentialBase):
    """Schema representing a credential record, often used internally or for full GET responses."""
    credential_id: str
    ephemeral_public_key: str # Base64 encoded
    signature: str # Base64 encoded
    issued_at: datetime
    expires_at: datetime
    revoked_at: Optional[datetime] = None
    origin_context: Optional[Dict[str, Any]] = None

    model_config = {
        "from_attributes": True
    }

    @field_validator('ephemeral_public_key', 'signature', mode='before')
    def encode_bytes_fields(cls, v):
        if isinstance(v, bytes):
            return base64.b64encode(v).decode('utf-8')
        return v 