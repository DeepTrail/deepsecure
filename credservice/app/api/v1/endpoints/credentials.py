import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status, Depends, Response

from app import schemas, crud, models
from app.api.deps import DbDep, CurrentUser # Import DB session and authenticated user dependencies
from app.core import security
from app.core.config import settings
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter()

@router.post("/issue", response_model=schemas.CredentialIssue)
def issue_credential(
    cred_in: schemas.CredentialCreate, # Input schema
    db: DbDep,
    current_agent_id: CurrentUser # Get agent_id from validated token
):
    """Issue a new short-lived credential (JWT) for a registered agent.

    Requires authentication via a valid agent JWT.
    The agent_id in the request body must match the authenticated agent.
    """
    # --- Validation ---
    # 1. Check if the requesting agent matches the agent in the payload
    if cred_in.agent_id != current_agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated agent cannot issue credentials for another agent."
        )

    # 2. Check if the agent exists in the database
    agent = crud.agent.get_by_agent_id(db=db, agent_id=current_agent_id)
    if not agent:
        # This shouldn't happen if the token validation worked based on registered agents,
        # but good practice to check.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Authenticated agent with ID '{current_agent_id}' not found in database."
        )

    # --- Credential Generation ---
    # 1. Generate a unique ID for this credential instance
    credential_id = f"cred_{uuid.uuid4()}"

    # 2. Determine expiration time
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expires_at = datetime.now(timezone.utc) + expires_delta

    # 3. Create the JWT access token
    # The 'sub' (subject) of the JWT will be the credential_id itself.
    # We can add agent_id to the claims as well.
    token_data = {"sub": credential_id, "agent_id": current_agent_id}
    access_token = security.create_access_token(subject=token_data, expires_delta=expires_delta)

    # --- Database Record Creation ---
    # Prepare data for the database model
    # Note: CRUDBase.create expects a schema object matching the model fields
    # or we need to adapt CRUDBase or pass a dict directly.
    # For now, let's create the model instance directly here.
    db_credential_data = {
        "credential_id": credential_id,
        "agent_id": current_agent_id,
        "issued_at": datetime.now(timezone.utc),
        "expires_at": expires_at,
        "is_revoked": False,
        "revoked_at": None,
        # Add other fields like scope, ephemeral_key if they become part of the model
    }
    db_credential = models.Credential(**db_credential_data)

    try:
        db.add(db_credential)
        db.commit()
        db.refresh(db_credential)
    except SQLAlchemyError as e:
        db.rollback()
        # Log error e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not store credential record in database."
        )

    # --- Response ---
    # Return the issued token details
    return schemas.CredentialIssue(
        access_token=access_token,
        token_type="bearer",
        credential_id=credential_id,
        expires_at=expires_at
    )

# Add other credential endpoints here (e.g., revoke, verify)
@router.delete("/revoke/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_credential(
    credential_id: str,
    db: DbDep,
    current_agent_id: CurrentUser # Ensure the caller is authenticated
):
    """Revoke an active credential.

    Requires authentication. Only the agent that owns the credential can revoke it.
    """
    # 1. Fetch the credential by its ID
    credential = crud.credential.get_by_credential_id(db=db, credential_id=credential_id)

    # 2. Check if credential exists
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credential with ID '{credential_id}' not found."
        )

    # 3. Check if the authenticated agent owns this credential
    if credential.agent_id != current_agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated agent cannot revoke a credential belonging to another agent."
        )

    # 4. Check if already revoked
    if credential.is_revoked:
        # Optionally return success (idempotent) or a specific message
        # Return success code 204 even if already revoked
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # 5. Revoke the credential using the CRUD method
    try:
        crud.credential.revoke(db=db, db_obj=credential)
    except SQLAlchemyError as e:
        db.rollback()
        # Log error e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not revoke credential due to a database error."
        )

    # Return 204 No Content on successful revocation
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# Placeholder for verification endpoint
@router.get("/verify/{credential_id}", response_model=schemas.CredentialVerificationResponse)
def verify_credential_status(credential_id: str, db: DbDep):
    """Check the status of a credential (valid, revoked, expired, not_found).

    This endpoint is typically unauthenticated.
    """
    credential = crud.credential.get_by_credential_id(db=db, credential_id=credential_id)

    if not credential:
        status = "not_found"
        return schemas.CredentialVerificationResponse(credential_id=credential_id, status=status)

    if credential.is_revoked:
        status = "revoked"
    elif credential.expires_at < datetime.now(timezone.utc):
        status = "expired"
    else:
        status = "valid"

    # Return the status along with some basic info
    return schemas.CredentialVerificationResponse(
        credential_id=credential.credential_id,
        status=status,
        # Optionally add other relevant fields from the credential model if needed
        # scope=credential.scope, # Example if scope was added to model
        agent_id=credential.agent_id,
        expires_at=credential.expires_at,
    ) 