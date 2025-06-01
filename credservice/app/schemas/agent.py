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
    
    # This is the field we want in the JSON output, derived from current_public_key (bytes)
    public_key_output: Optional[str] = Field(None, validation_alias="current_public_key", serialization_alias="publicKey")

    # Explicitly exclude the raw bytes version of current_public_key from being part of the direct output fields
    # if it was inherited and not handled by the alias for public_key_output.
    # The validation_alias on public_key_output should handle sourcing from current_public_key.
    # If current_public_key is still considered a separate field for serialization by Pydantic, exclude it.
    current_public_key: Any = Field(None, exclude=True) 

    @field_validator('public_key_output', mode='before')
    @classmethod
    def populate_public_key_output(cls, v: Any, info: FieldValidationInfo) -> Optional[str]:
        # logger.info(f"[AGENT_SCHEMA_DEBUG] populate_public_key_output called. Value v: {v} (type: {type(v)})")
        # logger.info(f"[AGENT_SCHEMA_DEBUG] info.data: {info.data}")

        if isinstance(v, bytes):
            encoded_pk = base64.b64encode(v).decode('utf-8')
            # logger.info(f"[AGENT_SCHEMA_DEBUG] v is bytes, encoded to: {encoded_pk}")
            return encoded_pk
        
        if v is None and info.data and isinstance(info.data.get('current_public_key'), bytes):
            # logger.info("[AGENT_SCHEMA_DEBUG] v is None, trying info.data.get('current_public_key')")
            encoded_pk = base64.b64encode(info.data['current_public_key']).decode('utf-8')
            # logger.info(f"[AGENT_SCHEMA_DEBUG] Fallback successful, encoded to: {encoded_pk}")
            return encoded_pk
        
        if isinstance(v, str):
            # logger.warning(f"[AGENT_SCHEMA_DEBUG] populate_public_key_output received a string, expected bytes. Value: {v}")        
            pass # Let it fall through to return None if not bytes and not handled above

        # logger.error(f"[AGENT_SCHEMA_DEBUG] populate_public_key_output FALLING THROUGH, RETURNING NONE. v was: {v}")
        return None

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