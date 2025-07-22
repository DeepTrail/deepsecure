from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timedelta

from app.db.base import Base

class Nonce(Base):
    __tablename__ = "nonces"

    nonce = Column(String, primary_key=True, nullable=False)
    agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    
    agent = relationship("Agent", back_populates="nonces") 