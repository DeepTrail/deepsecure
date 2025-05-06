from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated

from app import schemas, crud
from app.api.deps import DbDep
from app.core import security

router = APIRouter()

@router.post("/access-token", response_model=schemas.Token)
def login_for_access_token(form_data: schemas.AgentLogin, db: DbDep):
    """Authenticate agent via signature and return an access token."""
    # 1. Find the agent by agent_id
    agent = crud.agent.get_by_agent_id(db, agent_id=form_data.agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    # 2. Verify the signature
    # The message signed MUST be the agent_id itself for this implementation
    is_valid_signature = security.verify_signature(
        public_key_str=agent.public_key,
        message=form_data.agent_id, # Agent must sign its own ID
        signature_b64=form_data.signature
    )

    if not is_valid_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
            headers={"WWW-Authenticate": "Bearer"}, # Although this isn't bearer auth itself
        )

    # 3. Signature is valid, create access token for the agent_id
    access_token = security.create_access_token(
        subject=agent.agent_id # Subject of the token is the agent_id
        # expires_delta can be set here for a different duration than default if needed
    )
    return schemas.Token(access_token=access_token, token_type="bearer") 