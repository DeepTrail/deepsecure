"""SQLAlchemy model for Agent entities."""

from sqlalchemy import Column, String, DateTime, func, LargeBinary, Text
from sqlalchemy.orm import relationship

from app.db.base import Base

class Agent(Base):
    __tablename__ = "agents"

    agent_id = Column(String, primary_key=True, index=True, nullable=False)
    name = Column(String(255), index=True)
    description = Column(Text)
    status = Column(String(50), default="active", index=True, nullable=False)
    public_key = Column(LargeBinary, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    last_seen_at = Column(DateTime(timezone=True))
    
    # Relationship to Nonces
    nonces = relationship("Nonce", back_populates="agent", cascade="all, delete-orphan") 