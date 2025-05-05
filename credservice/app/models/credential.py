"""SQLAlchemy model for Credential entities."""

from sqlalchemy import Column, String, LargeBinary, DateTime, ForeignKey, JSON, Integer, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
# Remove unused UUID import if not using UUID type directly in this model
# from sqlalchemy.dialects.postgresql import UUID
# import uuid
from datetime import datetime

from app.db.base import Base

class Credential(Base):
    """Represents an issued credential instance in the database."""
    __tablename__ = "credentials"

    id = Column(Integer, primary_key=True, index=True)
    credential_id = Column(String, unique=True, index=True, nullable=False)
    agent_id = Column(String, ForeignKey("agents.agent_id"), index=True, nullable=False)
    issued_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), index=True, nullable=False)
    is_revoked = Column(Boolean(), default=False, nullable=False)
    revoked_at = Column(DateTime(timezone=True), index=True, nullable=True)
    # Add other fields like scope, origin_context_hash etc. if needed
    # scope = Column(String, index=True)
    # ephemeral_public_key = Column(LargeBinary)

    agent = relationship("Agent") # Relationship to parent Agent

    # Additional fields
    ephemeral_public_key = Column(LargeBinary, nullable=False, comment="The ephemeral X25519 public key associated with this credential (bytes).")
    signature = Column(LargeBinary, nullable=False, comment="Signature of the ephemeral_public_key using the agent's long-term key (bytes).")
    scope = Column(String, nullable=False, comment="Scope of access granted by this credential.")
    origin_context = Column(JSON, nullable=True, comment="Optional JSON containing origin context details (hostname, IP, etc.).") 