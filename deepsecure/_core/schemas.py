from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime # Will be useful if we want to parse datetime strings

# Common Error Model
class ErrorDetail(BaseModel):
    detail: str

# Request Models
class CredentialIssueRequest(BaseModel):
    scope: str
    ttl: int = Field(default=300, ge=60) # Min 1 min TTL
    agent_id: Optional[str] = None # Kept optional, VaultClient.issue() will ensure it's passed if signing
    ephemeral_public_key: str # Base64 encoded raw public key
    signature: str            # Base64 encoded signature - NOW REQUIRED
    origin_context: Optional[Dict[str, Any]] = None # Added origin_context

class AgentKeyRotateRequest(BaseModel):
    new_public_key: str # Base64 encoded

# Response Models
class CredentialBase(BaseModel):
    credential_id: str
    agent_id: str
    scope: str
    # Assuming API returns ISO format strings for datetimes
    # Pydantic can automatically parse these to datetime objects if type is datetime
    expires_at: datetime 
    issued_at: datetime
    status: str # e.g., "issued", "valid", "revoked", "expired"
    origin_context: Optional[Dict[str, Any]] = None # Added origin_context

class CredentialResponse(CredentialBase):
    """The full credential response returned to the client, including the ephemeral private key."""
    ephemeral_public_key_b64: str
    ephemeral_private_key_b64: str
    secret_value: Optional[str] = None # Temporary field for fetching secrets directly

class RevocationResponse(BaseModel):
    status: str # e.g., "revoked"
    credential_id: str
    message: Optional[str] = None

class AgentKeyRotationResponse(BaseModel):
    agent_id: Optional[str] = None # Made optional
    status: Optional[str] = None # Made optional, e.g., "success", "rotation_initiated"
    new_public_key: Optional[str] = None # The key that was set
    message: Optional[str] = None

class VerificationResponse(CredentialBase):
    """Response for a credential verification request."""
    is_valid: bool
    # ephemeral_public_key is part of CredentialBase if API returns it for verification
    # If not, it might need to be added here specifically or handled differently.
    # For now, assuming 'ephemeral_public_key' (as b64 string) is part of what verify endpoint returns under this name.
    ephemeral_public_key: Optional[str] = None # Base64 encoded, usually matches the one from issue. Made Optional.
    verified_at: Optional[str] = None # Or datetime if parsed. Made Optional.

class AgentDetailsResponse(BaseModel):
    agent_id: str
    public_key: str = Field(..., alias="publicKey") # Base64 encoded, added alias
    created_at: str # Or datetime
    updated_at: Optional[str] = None # Added based on server response
    last_seen_at: Optional[str] = None # Or datetime
    status: Optional[str] = None # e.g., "active", "inactive"
    name: Optional[str] = None # Added based on server response
    description: Optional[str] = None # Added based on server response
    # any other fields the API might return

    model_config = {
        "populate_by_name": True, # Allows use of alias field names for population
    }

# --- Policy Schemas ---

class PolicyResponse(BaseModel):
    """
    Response model for a policy object.
    """
    id: str
    name: str
    description: Optional[str] = None
    effect: str
    actions: List[str]
    resources: List[str]
    agent_id: str 