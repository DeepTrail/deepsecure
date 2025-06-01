"""API endpoints for Vault operations (credential issuance, revocation, verification, agent rotation)."""

import logging
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, status
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519 as ed25519_crypto
from cryptography.exceptions import InvalidSignature

from app import schemas, crud
from app.api import deps
from app.schemas.agent import AgentRotateRequest # Import schema for rotation

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/credentials", response_model=schemas.credential.CredentialIssueResponse, status_code=status.HTTP_201_CREATED)
def issue_credential(
    credential_in: schemas.credential.CredentialIssueRequest, # Input now has .ephemeral_public_key and .signature as bytes
    db: deps.DbDep,
    _: Any = deps.APIKeyDep # Use APIKeyDep directly as it's already Depends(verify_api_key)
):
    # logger.info(f"[VAULT_EP_DEBUG] Received credential_in.origin_context: {credential_in.origin_context}")
    logger.info(f"Attempting to issue credential for agent: {credential_in.agent_id}, scope: {credential_in.scope}")

    # 1. Fetch the agent's long-term public key
    logger.info(f"Fetching agent record for agent_id: {credential_in.agent_id}")
    agent = crud.agent.get_by_agent_id(db=db, agent_id=credential_in.agent_id)
    if not agent:
        logger.warning(f"Agent not found during credential issuance: {credential_in.agent_id}. This agent MUST be registered first.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{credential_in.agent_id}' not found.")
    
    if agent.status != "active":
        logger.warning(f"Agent {credential_in.agent_id} is not active (status: {agent.status}). Cannot issue credentials.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Agent {credential_in.agent_id} is not active.")

    if not agent.current_public_key or not isinstance(agent.current_public_key, bytes):
        logger.error(f"Agent {credential_in.agent_id} has no valid current_public_key (must be bytes) in DB.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Agent public key not available or invalid in database.")

    # 2. Ephemeral public key and signature are already bytes from Pydantic model validation
    ephemeral_public_key_bytes = credential_in.ephemeral_public_key 
    signature_bytes = credential_in.signature # This is now mandatory bytes
    agent_public_key_bytes = agent.current_public_key

    # 3. Verify the signature - Mandatory
    logger.info(f"Attempting signature verification for agent {credential_in.agent_id}")
    # Optional: Detailed debug logging if needed, commented out by default
    # logger.debug(f"VERIFY_DEBUG: Agent's Stored PubKey (b64): {base64.b64encode(agent_public_key_bytes).decode('utf-8')}")
    # logger.debug(f"VERIFY_DEBUG: Ephemeral PubKey Received (bytes as hex): {ephemeral_public_key_bytes.hex()}")
    # logger.debug(f"VERIFY_DEBUG: Signature Received (bytes as hex): {signature_bytes.hex()}")
    try:
        public_key_obj = ed25519_crypto.Ed25519PublicKey.from_public_bytes(agent_public_key_bytes)
        public_key_obj.verify(signature_bytes, ephemeral_public_key_bytes) 
        logger.info(f"Signature verified successfully for agent {credential_in.agent_id}")
    except InvalidSignature:
        logger.warning(f"Invalid signature provided by agent {credential_in.agent_id}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")
    except ValueError as ve: # Catch errors from from_public_bytes if key is malformed
        logger.error(f"Error loading agent's public key for signature verification (agent {credential_in.agent_id}): {ve}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid agent public key data: {ve}")
    except Exception as e:
        logger.error(f"Unexpected error during signature verification for agent {credential_in.agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Signature verification failed: {e}")

    # 4. Create the credential record in the database
    try:
        # crud.credential.create now expects obj_in where .ephemeral_public_key and .signature are bytes
        credential = crud.credential.create(db=db, obj_in=credential_in)
        logger.info(f"Successfully created credential {credential.credential_id} for agent {credential_in.agent_id}")
        # logger.info(f"[VAULT_EP_DEBUG] DB model credential.origin_context before return: {credential.origin_context}")
    except ValueError as ve: 
        logger.error(f"ValueError during credential creation in CRUD: {ve}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to create credential record for agent {credential_in.agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create credential")

    return credential # Pydantic will use schemas.credential.CredentialIssueResponse for serialization

@router.post("/credentials/{credential_id}/revoke", response_model=schemas.CredentialRevokeResponse)
def revoke_credential(
    credential_id: str,
    db: deps.DbDep,
    _: Any = deps.APIKeyDep # Corrected here as well
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
    rotation_request: schemas.agent.AgentRotateRequest, # Corrected to use schemas.agent
    db: deps.DbDep,
    _: Any = deps.APIKeyDep # Corrected here as well
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
    # This endpoint is typically public, no API key dep by default
):
    logger.debug(f"Verifying credential: {credential_id}")
    db_credential = crud.credential.get_by_credential_id(db=db, credential_id=credential_id)

    now = datetime.now(timezone.utc) # Ensure timezone is imported
    status_message = "valid"
    is_valid = True
    issued_at_aware: Optional[datetime] = None
    expires_at_aware: Optional[datetime] = None
    scope_val: Optional[str] = None
    agent_id_val: Optional[str] = None
    eph_pub_key_b64: Optional[str] = None

    if not db_credential:
        logger.info(f"Credential not found for verification: {credential_id}")
        status_message = "not_found"
        is_valid = False
    else:
        scope_val = db_credential.scope
        agent_id_val = db_credential.agent_id
        if db_credential.ephemeral_public_key:
            if isinstance(db_credential.ephemeral_public_key, bytes):
                eph_pub_key_b64 = base64.b64encode(db_credential.ephemeral_public_key).decode('utf-8')
            else: # Should not happen if DB stores bytes
                eph_pub_key_b64 = str(db_credential.ephemeral_public_key) 

        revoked_at_aware = db_credential.revoked_at
        if revoked_at_aware and revoked_at_aware.tzinfo is None:
            revoked_at_aware = revoked_at_aware.replace(tzinfo=timezone.utc)

        expires_at_aware = db_credential.expires_at
        if expires_at_aware and expires_at_aware.tzinfo is None:
            expires_at_aware = expires_at_aware.replace(tzinfo=timezone.utc)
        
        issued_at_aware = db_credential.issued_at # From DB
        if issued_at_aware and issued_at_aware.tzinfo is None:
            issued_at_aware = issued_at_aware.replace(tzinfo=timezone.utc)

        if revoked_at_aware is not None and revoked_at_aware <= now:
            status_message = "revoked"
            is_valid = False
        elif expires_at_aware <= now:
            status_message = "expired"
            is_valid = False
        # else: status_message is "valid", is_valid is True (defaults)

    return schemas.CredentialVerifyResponse(
        credential_id=credential_id,
        is_valid=is_valid,
        status=status_message,
        scope=scope_val,
        agent_id=agent_id_val,
        issued_at=issued_at_aware,
        expires_at=expires_at_aware,
        ephemeral_public_key=eph_pub_key_b64,
        verified_at=now 
    ) 