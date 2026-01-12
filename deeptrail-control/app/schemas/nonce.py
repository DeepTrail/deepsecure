from pydantic import BaseModel
import uuid
from datetime import datetime

# Shared properties
class NonceBase(BaseModel):
    pass

# Properties to receive on creation
class NonceCreate(NonceBase):
    agent_id: uuid.UUID
    nonce: str
    expires_at: datetime

# Properties to receive on update
class NonceUpdate(NonceBase):
    pass

# Properties shared by models stored in DB
class NonceInDBBase(NonceBase):
    id: uuid.UUID
    agent_id: uuid.UUID
    nonce: str
    created_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True

# Properties to return to client
class Nonce(NonceInDBBase):
    pass

# Properties stored in DB
class NonceInDB(NonceInDBBase):
    pass 