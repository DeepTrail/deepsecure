"""Pydantic schemas for Credential related API operations."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import base64
import logging
import binascii

from pydantic import BaseModel, Field, field_validator, ValidationInfo

logger = logging.getLogger(__name__)

# --- Base Schema --- #

class CredentialBase(BaseModel):
    """Shared base properties for credentials."""
    agent_id: str = Field(..., example="agent_f3b4c1a9")
    scope: Optional[str] = Field(None, example="read:secrets:prod/app1")

# --- Issue Credential --- #

class CredentialIssueRequest(CredentialBase):
    """Schema for requesting a new credential to be issued.
    Both ephemeral_public_key and signature are received as base64 strings
    from the API client, and this Pydantic model's validators convert them to bytes
    for internal use by the application (e.g., CRUD layer, cryptographic operations).
    """
    ephemeral_public_key: bytes
    signature: bytes
    ttl: int = Field(..., gt=0, description="Requested Time-To-Live for the credential in seconds.", example=3600)
    origin_context: Optional[Dict[str, Any]] = Field(None, description="Optional context about the request origin.", example={"hostname": "agent-host-1", "ip": "192.168.1.100"})

    @field_validator('ephemeral_public_key', 'signature', mode='before')
    @classmethod
    def validate_and_decode_field_to_bytes(cls, v: Any, info: ValidationInfo) -> bytes:
        """
        Validates that the input 'v' (for ephemeral_public_key or signature)
        is a base64 string, decodes it, checks its length, and returns raw bytes.
        """
        field_name = info.field_name
        
        if not isinstance(v, str):
            raise ValueError(f"Input for {field_name} must be a base64 encoded string, received type {type(v)}.")
        
        try:
            decoded_bytes = base64.b64decode(v, validate=True)
            expected_length = 0
            if field_name == 'ephemeral_public_key':
                expected_length = 32
            elif field_name == 'signature':
                expected_length = 64
            
            if expected_length > 0 and len(decoded_bytes) != expected_length:
                raise ValueError(f"Decoded {field_name} must be {expected_length} bytes long, but was {len(decoded_bytes)} bytes.")
            
            return decoded_bytes
        except (binascii.Error, ValueError) as e:
            raise ValueError(f"Invalid base64 content or length for {field_name}: {e}")

class CredentialIssueResponse(CredentialBase):
    """Schema for the response after successfully issuing a credential."""
    credential_id: str = Field(..., example=str(uuid.uuid4()))
    ephemeral_public_key: str = Field(..., description="Base64 encoded Ed25519 public key from the agent.")
    issued_at: datetime
    expires_at: datetime
    status: str
    origin_context: Optional[Dict[str, Any]] = Field(None, description="Context of the request origin, if provided and processed.")

    model_config = {
        "from_attributes": True
    }

    @field_validator('ephemeral_public_key', mode='before')
    def encode_ephemeral_key_bytes_to_b64_for_response(cls, v: Any) -> str:
        if isinstance(v, bytes):
            return base64.b64encode(v).decode('utf-8')
        if isinstance(v, str):
            return v
        raise ValueError("ephemeral_public_key must be bytes or a base64 string for response model.")

# --- Verify Credential --- #

class CredentialVerifyResponse(CredentialBase):
    """Schema for the response when verifying a credential."""
    credential_id: str
    is_valid: bool
    status: str = Field(..., example="valid | expired | revoked | not_found")
    scope: Optional[str] = None
    agent_id: Optional[str] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    ephemeral_public_key: Optional[str] = None
    origin_context: Optional[Dict[str, Any]] = None

    @field_validator('ephemeral_public_key', mode='before')
    @classmethod
    def encode_verify_eph_key_bytes_to_b64(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, bytes):
            return base64.b64encode(v).decode('utf-8')
        if isinstance(v, str):
            return v
        raise ValueError("ephemeral_public_key for verify response must be bytes or a base64 string.")

# --- Revoke Credential --- #

class CredentialRevokeResponse(BaseModel):
    """Schema for the response after revoking a credential."""
    credential_id: str
    status: str = Field(..., example="revoked | already_revoked | not_found")

# --- General Credential Representation --- #

class Credential(CredentialBase):
    """Schema representing a credential record, often used internally or for full GET responses."""
    credential_id: str
    ephemeral_public_key: str
    signature: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: Optional[datetime] = None
    origin_context: Optional[Dict[str, Any]] = None
    status: str

    model_config = {
        "from_attributes": True
    }

    @field_validator('ephemeral_public_key', 'signature', mode='before')
    def encode_bytes_fields_to_b64(cls, v: Any) -> str:
        if isinstance(v, bytes):
            return base64.b64encode(v).decode('utf-8')
        if isinstance(v, str):
            return v
        raise ValueError("Field must be bytes or base64 string for Credential model.")

# Schema for storing a simple key-value secret
class SecretStoreRequest(BaseModel):
    name: str
    value: str

class SecretStoreResponse(BaseModel):
    name: str
    message: str = "Secret stored successfully" 