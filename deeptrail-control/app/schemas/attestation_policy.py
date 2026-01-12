from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.attestation_policy import PlatformType


# Shared properties
class AttestationPolicyBase(BaseModel):
    platform: Optional[PlatformType] = None
    selector: Optional[str] = None
    agent_name_to_bootstrap: Optional[str] = None


# Properties to receive on item creation
class AttestationPolicyCreate(AttestationPolicyBase):
    platform: PlatformType
    selector: str
    agent_name_to_bootstrap: str


# Properties to receive on item update
class AttestationPolicyUpdate(AttestationPolicyBase):
    pass


# Properties shared by models stored in DB
class AttestationPolicyInDBBase(AttestationPolicyBase):
    id: UUID
    platform: PlatformType
    selector: str
    agent_name_to_bootstrap: str

    class Config:
        from_attributes = True


# Properties to return to client
class AttestationPolicy(AttestationPolicyInDBBase):
    pass


# Properties properties stored in DB
class AttestationPolicyInDB(AttestationPolicyInDBBase):
    pass 