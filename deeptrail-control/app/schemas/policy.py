from typing import List, Optional
import uuid
from pydantic import BaseModel

# Shared properties
class PolicyBase(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    effect: str = "allow"
    actions: Optional[List[str]] = None
    resources: Optional[List[str]] = None
    agent_id: Optional[uuid.UUID] = None

# Properties to receive on item creation
class PolicyCreate(PolicyBase):
    name: str
    actions: List[str]
    resources: List[str]
    agent_id: uuid.UUID

# Properties to receive on item update
class PolicyUpdate(PolicyBase):
    pass

# Properties shared by models stored in DB
class PolicyInDBBase(PolicyBase):
    id: uuid.UUID
    name: str
    agent_id: uuid.UUID
    actions: List[str]
    resources: List[str]

    class Config:
        orm_mode = True

# Properties to return to client
class Policy(PolicyInDBBase):
    pass

# Properties properties stored in DB
class PolicyInDB(PolicyInDBBase):
    pass 