"""Pydantic schemas for Agent related API operations."""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Any
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
    # For input, we expect a base64 string of the raw 32-byte public key
    public_key: str = Field(..., description="Base64 encoded raw Ed25519 public key (32 bytes).", example="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=") 

class AgentCreate(AgentBase):
    # public_key is inherited and required.
    # This validator will run when an AgentCreate model is instantiated with data.
    # It converts the base64 string public_key into bytes for the ORM model.
    @field_validator('public_key', mode='before')
    @classmethod
    def validate_and_decode_public_key(cls, v: Any) -> bytes:
        if not isinstance(v, str):
            raise ValueError("Public key must be a base64 encoded string.")
        try:
            key_bytes = base64.b64decode(v, validate=True)
            if len(key_bytes) != 32:
                raise ValueError("Decoded public key must be 32 bytes long for Ed25519.")
            return key_bytes # Return raw bytes for CRUD/model layer
        except (binascii.Error, ValueError) as e:
            # Catch b64decode errors (binascii.Error) or our own ValueError
            raise ValueError(f"Invalid base64 encoded public key: {e}")

class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, example="MyRenamedAgent", max_length=255)
    description: Optional[str] = Field(None, example="Updated agent description.")
    status: Optional[str] = Field(None, example="inactive", max_length=50)
    # Public key rotation would likely be a separate endpoint/process

# --- Schemas for Database Interaction (usually includes all model fields) --- #
class AgentInDBBase(AgentBase):
    agent_id: str = Field(example="agent_f3b4c1a9-0123-4567-89ab-cdef01234567")
    # In the DB, public_key is stored as bytes
    current_public_key: bytes # Field name matches SQLAlchemy model
    status: str = Field(example="active")
    created_at: datetime
    updated_at: datetime
    last_seen_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True # Allow creating from ORM model attributes
    }

    # Override public_key from AgentBase to ensure it's not used when creating from DB model
    # where current_public_key (bytes) is the source of truth.
    # Instead, we'll have a property in the response schema 'Agent' to show b64 public_key.
    public_key: Optional[str] = Field(None, exclude=True) # Exclude from direct model init

# --- Schemas for API Responses --- #
class Agent(AgentInDBBase):
    # This schema is used for API responses (e.g., GET /agents/{id}, POST /agents)
    # It should transform DB data (like public_key bytes) into API-friendly formats.
    
    # We want to output public_key as base64 string, derived from current_public_key (bytes)
    public_key_b64: Optional[str] = Field(None, alias="publicKeyBase64") # Use alias for JSON output field name

    @model_validator(mode='before') # was root_validator
    @classmethod
    def set_public_key_b64_from_bytes(cls, data: Any) -> Any:
        if isinstance(data, dict):
            key_bytes = data.get('current_public_key')
            if isinstance(key_bytes, bytes):
                data['public_key_b64'] = base64.b64encode(key_bytes).decode('utf-8')
        elif hasattr(data, 'current_public_key') and isinstance(data.current_public_key, bytes):
            # Handling ORM object directly if from_attributes=True
            # For Pydantic v2, it's better to rely on computed fields or serialization logic if possible
            # This validator can still work but needs careful handling of when it runs.
            # Let's assume `data` could be the ORM model instance itself due to from_attributes
            data.public_key_b64 = base64.b64encode(data.current_public_key).decode('utf-8')
        return data
    
    # Ensure the original 'current_public_key' (bytes) is not part of the response schema by default
    # current_public_key: Optional[bytes] = Field(None, exclude=True) # This will be hidden due to AgentInDBBase

    model_config = {
        "from_attributes": True,
        "populate_by_name": True, # Allows using alias in response
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
        # Reuse the same validation as AgentCreate
        return AgentCreate.validate_and_decode_public_key(v)

# Schema for agent rotation request
class AgentRotateRequest(BaseModel):
    """Schema for the request body when rotating an agent's identity key."""
    new_public_key: str = Field(..., description="Base64 encoded raw Ed25519 public key bytes (32 bytes).", example="Base64EncodedEd25519PublicKeyBytes") 