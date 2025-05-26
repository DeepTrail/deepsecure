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
    ephemeral_public_key: str = Field(..., description="Base64 encoded Ed25519 public key from the agent.", example="base64_encoded_x25519_pub_key")
    signature: Optional[str] = Field(None, description="Base64 encoded Ed25519 signature of the ephemeral_public_key by the agent's long-term key.", example="base64_encoded_signature") # MADE OPTIONAL
    ttl: int = Field(..., gt=0, description="Requested Time-To-Live for the credential in seconds.", example=3600)
    origin_context: Optional[Dict[str, Any]] = Field(None, description="Optional context about the request origin.", example={"hostname": "agent-host-1", "ip": "192.168.1.100"})

    # These fields are for internal use after validation if needed by CRUD, not part of request/response schema directly
    # They are also not automatically populated by Pydantic this way.
    # It's usually better to handle byte conversion within the endpoint or CRUD layer if needed.
    # For simplicity, let's remove them from here to avoid confusion as Pydantic won't set them.
    # ephemeral_public_key_bytes: Optional[bytes] = None 
    # signature_bytes: Optional[bytes] = None

    @field_validator('ephemeral_public_key', 'signature')
    def validate_base64_fields(cls, v: Optional[str], info) -> Optional[str]:
        """Validate base64 encoded fields. Allows None for optional fields like signature."""
        field_name = info.field_name

        if v is None:
            if field_name == 'signature': # Signature is Optional, so None is valid.
                return None
            else:
                # This case should ideally not be hit for ephemeral_public_key if it's required
                # and Pydantic's own missing field validation runs first.
                # However, if an explicit None was passed for a required field, this would catch it.
                # For now, we rely on Pydantic to ensure ephemeral_public_key is not None.
                # If it were optional too, we'd return None here.
                # Since ephemeral_public_key IS required, `v` should not be None for it.
                # If `v` is None for `ephemeral_public_key`, Pydantic's earlier validation would fail.
                # This validator will only be called for `ephemeral_public_key` if a string value is provided.
                pass # Let Pydantic handle if a required field is None

        if not isinstance(v, str):
             # This should also be caught by Pydantic's type validation before this runs
             raise ValueError(f"Field '{field_name}' must be a string for base64 decoding.")

        try:
            decoded_bytes = base64.b64decode(v)
            if field_name == 'ephemeral_public_key':
                if len(decoded_bytes) != 32: # Ed25519 keys are 32 bytes
                    raise ValueError("Decoded ephemeral public key must be 32 bytes long")
            elif field_name == 'signature': # Will only run if signature 'v' is not None
                if len(decoded_bytes) != 64: # Ed25519 signatures are 64 bytes
                    raise ValueError("Decoded signature must be 64 bytes long")
            return v # Return original base64 string if all checks pass
        except (TypeError, ValueError, base64.binascii.Error) as e:
            logger.error(f"Base64 validation/decoding failed for field '{field_name}': {v}, Error: {e}")
            raise ValueError(f"Invalid base64 format or content for field '{field_name}'") from e

class CredentialIssueResponse(CredentialBase):
    """Schema for the response after successfully issuing a credential."""
    credential_id: str = Field(..., example=str(uuid.uuid4()))
    status: str          # Should always be present upon issue (e.g., "issued")
    issued_at: datetime  # Should always be present upon issue 
    expires_at: datetime # Should always be present upon issue 
    ephemeral_public_key: str = Field(..., description="Base64 encoded X25519 public key.")
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
    issued_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    ephemeral_public_key: Optional[str] = None
    origin_context: Optional[Dict[str, Any]] = None

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