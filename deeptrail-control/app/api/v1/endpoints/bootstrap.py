from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.bootstrap import BootstrapRequest, BootstrapResponse
from app.services.attestation_service import attestation_service

router = APIRouter()

@router.post("/attest", response_model=BootstrapResponse)
def attest_and_create_agent(
    *,
    db: Session = Depends(deps.get_db),
    request: BootstrapRequest,
):
    """
    Attest a platform identity token and create a new agent.
    """
    if request.platform == "gcp":
        try:
            # This will be implemented in the next step.
            # It will perform token validation, policy checks, and agent creation.
            agent_id, private_key = attestation_service.attest_gcp_and_create_agent(
                db=db, token=request.token
            )
            return BootstrapResponse(agent_id=agent_id, private_key=private_key)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Attestation failed: {e}")
    else:
        raise HTTPException(status_code=400, detail="Unsupported platform") 