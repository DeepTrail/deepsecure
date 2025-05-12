"""SQLAlchemy model for Agent entities."""

from sqlalchemy import Column, String, LargeBinary, DateTime, func, Text # Added Text for description
from sqlalchemy.sql import func
from datetime import datetime # Keep for type hinting if needed, though func.now handles DB time

from app.db.base import Base # Assuming this provides the declarative base

class Agent(Base):
    """Represents an agent identity in the database."""
    __tablename__ = "agents"

    agent_id = Column(String(128), primary_key=True, index=True, comment="Unique identifier for the agent (e.g., agent-<uuid>)")
    name = Column(String(255), nullable=True, index=True, comment="Optional human-readable name for the agent.")
    description = Column(Text, nullable=True, comment="Optional description for the agent.")
    
    # The raw 32 bytes of the Ed25519 public key
    # Stored as bytes in DB, will be base64 encoded/decoded at API boundary.
    current_public_key = Column(LargeBinary(64), unique=True, nullable=False, comment="The current long-term Ed25519 public key for the agent (raw bytes).")
    
    status = Column(String(50), default="active", nullable=False, index=True, comment="Status of the agent (e.g., active, inactive, revoked).")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Timestamp when the agent record was created.")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Timestamp when the agent record was last updated.")
    last_seen_at = Column(DateTime(timezone=True), nullable=True, comment="Timestamp when the agent was last seen (e.g., issued a credential).")

    # Possible future relationships:
    # credentials = relationship("Credential", back_populates="agent")
    # audit_logs = relationship("AuditLog", back_populates="agent")

    def __repr__(self):
        return f"<Agent(agent_id='{self.agent_id}', name='{self.name}', status='{self.status}')>"

    # Add other metadata fields if needed, e.g., owner_id, description
    # metadata = Column(JSONB) 