import uuid
from sqlalchemy import Column, String, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

class Policy(Base):
    __tablename__ = "policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)
    
    agent_id = Column(String(128), ForeignKey("agents.agent_id"), nullable=False)
    agent = relationship("Agent")

    effect = Column(String, nullable=False, default="allow")
    actions = Column(JSON, nullable=False)
    resources = Column(JSON, nullable=False) 