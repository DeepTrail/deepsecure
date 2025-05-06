"""API endpoints for Vault operations (credential issuance, revocation, verification, agent rotation)."""

import logging
import base64
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

from app import schemas, crud
from app.api import deps
from app.schemas.agent import AgentRotateRequest # Import schema for rotation

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/credentials", response_model=schemas.CredentialIssueResponse, status_code=status.HTTP_201_CREATED)
def issue_credential(
    credential_in: schemas.CredentialIssueRequest,
    db: deps.DbDep,
    _: None = deps.APIKeyDep
):
    """Issue a new short-lived credential for an agent.

    - Verifies the provided signature against the agent's registered key.
    - Creates a credential record in the database with a calculated expiry.
    - Requires valid API Key authentication.

    Args:
        credential_in: Input data containing agent ID, ephemeral key, signature, scope, and TTL.
        db: Database session dependency.

    Raises:
        HTTPException 404: If the specified agent_id is not found.
        HTTPException 400: If the base64 encoding is invalid or the signature verification fails.
        HTTPException 500: If there's an internal error during signature verification or DB operation.
    """
    logger.info(f"Attempting to issue credential for agent: {credential_in.agent_id}")

    # 1. Fetch the agent's long-term public key
    agent = crud.agent.get_by_agent_id(db=db, agent_id=credential_in.agent_id)
    if not agent:
        logger.warning(f"Agent not found during credential issuance: {credential_in.agent_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # 2. Decode inputs (schema validator already checked format/length)
    try:
        ephemeral_public_key_bytes = base64.b64decode(credential_in.ephemeral_public_key)
        signature_bytes = base64.b64decode(credential_in.signature)
        agent_public_key_bytes = agent.current_public_key
    except Exception as e:
        logger.error(f"Failed to decode base64 for verification: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid base64 encoding for key or signature")

    # 3. Verify the signature
    try:
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(agent_public_key_bytes)
        public_key.verify(signature_bytes, ephemeral_public_key_bytes)
        logger.info(f"Signature verified successfully for agent {credential_in.agent_id}")
    except InvalidSignature:
        logger.warning(f"Invalid signature provided by agent {credential_in.agent_id}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Error during signature verification for agent {credential_in.agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Signature verification failed")

    # 4. Create the credential record in the database
    try:
        credential = crud.credential.create(db=db, obj_in=credential_in)
        logger.info(f"Successfully created credential {credential.credential_id} for agent {credential_in.agent_id}")
    except ValueError as ve:
        # Catch potential decoding errors within CRUD create (shouldn't happen)
        logger.error(f"ValueError during credential creation: {ve}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to create credential record for agent {credential_in.agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create credential")

    return credential

@router.post("/credentials/{credential_id}/revoke", response_model=schemas.CredentialRevokeResponse)
def revoke_credential(
    credential_id: str,
    db: deps.DbDep,
    _: None = deps.APIKeyDep
):
    """Revoke an existing credential by setting its `revoked_at` timestamp.

    - Requires valid API Key authentication.
    - Idempotent: Returns success even if already revoked.

    Args:
        credential_id: The ID of the credential to revoke.
        db: Database session dependency.

    Raises:
        HTTPException 404: If the credential_id is not found.
        HTTPException 500: If a database error occurs during update.
    """
    logger.info(f"Attempting to revoke credential: {credential_id}")
    db_credential = crud.credential.revoke(db=db, credential_id=credential_id)

    if db_credential is None:
        logger.warning(f"Credential not found for revocation: {credential_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")

    status_message = "revoked"
    revoked_at_aware = db_credential.revoked_at
    if revoked_at_aware and revoked_at_aware.tzinfo is None:
        revoked_at_aware = revoked_at_aware.replace(tzinfo=timezone.utc)

    if revoked_at_aware is None: # Should not happen if revoke worked, but check
        status_message = "revocation_failed"
        logger.error(f"Revocation failed unexpectedly for credential {credential_id}")
    # Check if it was already revoked before this call (within a small tolerance)
    elif datetime.now(timezone.utc) > revoked_at_aware + timedelta(seconds=1):
         status_message = "already_revoked"

    return schemas.CredentialRevokeResponse(credential_id=credential_id, status=status_message)

@router.post("/agents/{agent_id}/rotate-identity", status_code=status.HTTP_204_NO_CONTENT)
def rotate_agent_identity_key(
    agent_id: str,
    rotation_request: AgentRotateRequest,
    db: deps.DbDep,
    _: None = deps.APIKeyDep
):
    """Update the long-term identity public key for an agent.

    - Requires valid API Key authentication.

    Args:
        agent_id: The ID of the agent whose key is being rotated.
        rotation_request: Request body containing the new public key (base64 encoded).
        db: Database session dependency.

    Raises:
        HTTPException 404: If the agent_id is not found.
        HTTPException 400: If the new_public_key format is invalid.
        HTTPException 500: If a database error occurs during update.
    """
    logger.info(f"Attempting to rotate identity key for agent: {agent_id}")
    agent = crud.agent.get_by_agent_id(db=db, agent_id=agent_id)
    if not agent:
        logger.warning(f"Agent not found for key rotation: {agent_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # Decode the new public key
    try:
        # Basic validation - assumes Ed25519 key in Base64
        new_public_key_bytes = base64.b64decode(rotation_request.new_public_key)
        if len(new_public_key_bytes) != 32:
             raise ValueError("New public key must be 32 bytes long after base64 decoding")
        # TODO: Consider adding SSH format parsing/validation here like in agent create?
    except (ValueError, base64.binascii.Error) as e:
        logger.error(f"Invalid new public key format for agent {agent_id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid new public key format: {e}")

    # Update the agent record using the base update method
    try:
        update_data = {"current_public_key": new_public_key_bytes}
        crud.agent.update(db=db, db_obj=agent, obj_in=update_data)
        logger.info(f"Successfully rotated identity key for agent: {agent_id}")
    except Exception as e:
        logger.error(f"Failed to update agent key for {agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not rotate agent key")

    # No content response on success
    return

@router.get("/credentials/{credential_id}/verify", response_model=schemas.CredentialVerifyResponse)
def verify_credential(
    credential_id: str,
    db: deps.DbDep,
):
    """Verify the status of a credential (valid, expired, revoked, not_found).

    This endpoint is publicly accessible.

    Args:
        credential_id: The ID of the credential to verify.
        db: Database session dependency.

    Returns:
        CredentialVerifyResponse: Object detailing the credential's status.
    """
    logger.debug(f"Verifying credential: {credential_id}")
    db_credential = crud.credential.get_by_credential_id(db=db, credential_id=credential_id)

    if not db_credential:
        logger.info(f"Credential not found for verification: {credential_id}")
        return schemas.CredentialVerifyResponse(
            credential_id=credential_id,
            is_valid=False,
            status="not_found"
        )

    now = datetime.now(timezone.utc)
    status_message = "valid"
    is_valid = True

    # Ensure retrieved datetimes are timezone-aware (assume UTC if naive)
    revoked_at_aware = db_credential.revoked_at
    if revoked_at_aware and revoked_at_aware.tzinfo is None:
        revoked_at_aware = revoked_at_aware.replace(tzinfo=timezone.utc)

    expires_at_aware = db_credential.expires_at
    if expires_at_aware and expires_at_aware.tzinfo is None:
        expires_at_aware = expires_at_aware.replace(tzinfo=timezone.utc)

    if revoked_at_aware is not None:
        logger.info(f"Credential {credential_id} is revoked.")
        status_message = "revoked"
        is_valid = False
    elif expires_at_aware <= now:
        logger.info(f"Credential {credential_id} has expired.")
        status_message = "expired"
        is_valid = False
    else:
        logger.info(f"Credential {credential_id} is valid.")

    return schemas.CredentialVerifyResponse(
        credential_id=credential_id,
        is_valid=is_valid,
        status=status_message,
        scope=db_credential.scope,
        agent_id=db_credential.agent_id,
        expires_at=expires_at_aware # Return the timezone-aware version
    ) 