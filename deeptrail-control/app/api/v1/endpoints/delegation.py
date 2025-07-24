from fastapi import APIRouter, Depends

from app import models, schemas
from app.api import deps
from app.services.macaroon_service import macaroon_service

router = APIRouter()


@router.post("/delegate", response_model=schemas.DelegationResponse)
def delegate_access(
    *,
    delegation_in: schemas.DelegationRequest,
    current_agent: models.Agent = Depends(deps.get_current_active_agent),
):
    """
    Delegate access to another agent by minting a macaroon.

    This endpoint allows an authenticated agent to generate a temporary,
    scoped credential (a macaroon) and delegate it to another agent.
    """
    #
    # TODO: Implement policy check to ensure the calling agent has the 'delegate'
    # permission for the requested resource (delegation_in.resource).
    # This check will be added once the Policy Engine (Phase 3) is implemented.
    #
    # pseudo-code:
    # if not policy_engine.check(
    #   agent=current_agent,
    #   action="delegate",
    #   resource=delegation_in.resource
    # ):
    #   raise HTTPException(status_code=403, detail="Not authorized to delegate")
    #

    delegation_token = macaroon_service.mint_delegation_macaroon(
        target_agent_id=delegation_in.target_agent_id,
        resource=delegation_in.resource,
        permissions=delegation_in.permissions,
        ttl_seconds=delegation_in.ttl_seconds,
    )
    return {"delegation_token": delegation_token} 