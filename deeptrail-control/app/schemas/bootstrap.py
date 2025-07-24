from pydantic import BaseModel
from typing import Literal

class BootstrapRequest(BaseModel):
    """
    Request model for the bootstrap/attest endpoint.
    """
    platform: Literal["gcp"]
    token: str

class BootstrapResponse(BaseModel):
    """
    Response model for a successful bootstrap/attest call.
    """
    agent_id: str
    private_key: str # This is returned only once, on creation. 