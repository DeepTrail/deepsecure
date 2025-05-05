"""Pydantic schemas for Credential related API operations."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

# Base schema with common fields
class CredentialBase(BaseModel):
    """Base schema for Credential data, containing common fields."""
    scope: str
    agent_id: str
    ephemeral_public_key: str # Base64 encoded representation
    credential_id: str = Field(..., example="cred_a1b2c3d4")

# Schema for request body when issuing a credential
class CredentialIssueRequest(CredentialBase):
    """Schema for the request body when issuing a new credential."""
    signature: str # Base64 encoded signature of ephemeral_public_key
    ttl: str = Field(..., description="Time-to-live string (e.g., '5m', '1h')")
    origin_context: Optional[Dict[str, Any]] = Field(None, description="Optional dictionary containing origin context.")

# Schema for the response when a credential is issued
class CredentialIssueResponse(CredentialBase):
    """Schema for the API response after successfully issuing a credential."""
    issued_at: datetime
    expires_at: datetime
    origin_context: Optional[Dict[str, Any]] = None

    class Config:
        """Pydantic configuration."""
        orm_mode = True # Pydantic V1 style, or from_attributes = True in V2

# Schema for verifying a credential (potential response model)
class CredentialVerificationResponse(BaseModel):
    """Schema for the API response when verifying a credential's status."""
    credential_id: str
    status: str = Field(..., description="Verification status (e.g., 'valid', 'expired', 'revoked', 'not_found')")
    scope: Optional[str] = None
    agent_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    # Add more fields as needed for verification context 

# Properties to receive via API on creation/issuance request
class CredentialCreate(BaseModel):
    agent_id: str = Field(..., example="agent_f3b4c1a9")
    # Potentially add audience, scope, requested_ttl_minutes here
    # audience: Optional[str] = Field(None, example="service.example.com")
    # requested_ttl_minutes: Optional[int] = Field(None, example=60)

# Properties included in the actual issued credential/token response
class CredentialIssue(BaseModel):
    access_token: str = Field(..., example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    token_type: str = Field(default="bearer", example="bearer")
    credential_id: str = Field(..., example="cred_a1b2c3d4")
    expires_at: datetime

# Properties stored in and returned from the database record
class Credential(CredentialBase):
    id: int # Database ID
    expires_at: datetime
    issued_at: datetime
    revoked_at: Optional[datetime] = None
    is_revoked: bool = False

    class Config:
        from_attributes = True # Pydantic V2 setting 