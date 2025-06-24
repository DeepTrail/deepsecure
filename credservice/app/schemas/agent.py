"""Pydantic schemas for Agent related API operations."""

import logging
from pydantic import BaseModel, Field, field_validator, model_validator, FieldValidationInfo
from typing import Optional, Any, List
from datetime import datetime
import base64
import binascii # For b64decode error catching

# Setup logger
logger = logging.getLogger(__name__)

# Test keys for reference
VALID_SSH_PUB_KEY_B64_1 = "AAAAC3NzaC1lZDI1NTE5AAAAIDAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
VALID_SSH_PUB_KEY_B64_2 = "AAAAC3NzaC1lZDI1NTE5AAAAIGBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB="
VALID_SSH_PUB_KEY_B64_3 = "AAAAC3NzaC1lZDI1NTE5AAAAIGCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC="

# Map of test keys - for each agent_id, return the appropriate test key
TEST_KEY_MAP = {
    "test-agent-001": VALID_SSH_PUB_KEY_B64_1,
    "test-agent-002": VALID_SSH_PUB_KEY_B64_2,
    "test-agent-003": VALID_SSH_PUB_KEY_B64_3,
}

# --- Base Schemas --- #
class AgentBase(BaseModel):
    name: Optional[str] = Field(None, example="MyAwesomeAgent", max_length=255)
    description: Optional[str] = Field(None, example="Agent for processing order data.")

class AgentCreate(AgentBase):
    agent_id: Optional[str] = Field(None, description="Optional agent ID. If not provided, one will be generated.")
    public_key: bytes
    
    @field_validator('public_key', mode='before')
    @classmethod
    def validate_public_key_from_str_input(cls, v: Any) -> bytes:
        if not isinstance(v, str):
            raise ValueError("Input public_key must be a base64 encoded string.")
        try:
            key_bytes = base64.b64decode(v, validate=True)
            if len(key_bytes) != 32:
                raise ValueError("Decoded public key must be 32 bytes long for Ed25519.")
            return key_bytes
        except (binascii.Error, ValueError) as e:
            raise ValueError(f"Invalid base64 encoded public key: {e}")

class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, example="MyRenamedAgent", max_length=255)
    description: Optional[str] = Field(None, example="Updated agent description.")
    status: Optional[str] = Field(None, example="inactive", max_length=50)

# --- Schemas for Database Interaction (usually includes all model fields) --- #
class AgentInDBBase(AgentBase):
    agent_id: str = Field(example="agent_f3b4c1a9-0123-4567-89ab-cdef01234567")
    current_public_key: bytes # Field name matches SQLAlchemy model, stores raw bytes from DB
    status: str = Field(example="active")
    created_at: datetime
    updated_at: datetime
    last_seen_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

# --- Schemas for API Responses --- #
class Agent(AgentInDBBase): # Inherits fields from AgentInDBBase, including current_public_key: bytes
    
    # Override the current_public_key field to return a base64 string instead of bytes
    current_public_key: str = Field(serialization_alias="publicKey")

    @field_validator('current_public_key', mode='before')
    @classmethod
    def encode_public_key_bytes(cls, v: Any) -> str:
        """Convert public key bytes from database to base64 string for JSON response."""
        if isinstance(v, bytes):
            return base64.b64encode(v).decode('utf-8')
        elif isinstance(v, str):
            return v  # Already encoded
        else:
            logger.error(f"[AGENT_SCHEMA] Unexpected public key type: {type(v)}, value: {v}")
            return ""  # Return empty string instead of None to avoid null issues

    model_config = {
        "from_attributes": True,
        "populate_by_name": True, # Allows using serialization_alias "publicKey"
    }

# For listing multiple agents
class AgentList(BaseModel):
    agents: List[Agent]
    total: int

# Schema for agent public key rotation request (if needed as separate endpoint)
class AgentRotateKeyRequest(BaseModel):
    new_public_key: str = Field(..., description="New base64 encoded raw Ed25519 public key (32 bytes).")
    @field_validator('new_public_key', mode='before')
    @classmethod
    def validate_new_public_key(cls, v: Any) -> bytes:
        return AgentCreate.validate_public_key_from_str_input(v)

# Schema for agent rotation request
class AgentRotateRequest(BaseModel):
    """Schema for the request body when rotating an agent's identity key."""
    new_public_key: str = Field(..., description="Base64 encoded raw Ed25519 public key bytes (32 bytes).", example="Base64EncodedEd25519PublicKeyBytes") 