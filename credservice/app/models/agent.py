"""SQLAlchemy model for Agent entities."""

from sqlalchemy import Column, String, LargeBinary, DateTime, func
from sqlalchemy.sql import func
# Remove unused UUID import if not using UUID type directly in this model
# from sqlalchemy.dialects.postgresql import UUID
# import uuid
from datetime import datetime

from app.db.base import Base

class Agent(Base):
    """Represents an agent identity in the database."""
    __tablename__ = "agents"

    agent_id = Column(String, primary_key=True, index=True, comment="Unique identifier for the agent (e.g., agent-<uuid>)")
    # The raw 32 bytes of the Ed25519 public key
    current_public_key = Column(LargeBinary, nullable=False, comment="The current long-term Ed25519 public key for the agent (bytes).")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="Timestamp when the agent record was created.")
    # Add other metadata fields if needed, e.g., owner_id, description
    # metadata = Column(JSONB) 