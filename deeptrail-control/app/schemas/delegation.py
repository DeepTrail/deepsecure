from typing import List, Optional

from pydantic import BaseModel


class DelegationRequest(BaseModel):
    """
    Defines the request body for creating a delegation token.
    """

    target_agent_id: str
    resource: str
    permissions: List[str]
    ttl_seconds: int


class DelegationResponse(BaseModel):
    """
    Defines the response body containing the minted delegation token.
    """

    delegation_token: str 