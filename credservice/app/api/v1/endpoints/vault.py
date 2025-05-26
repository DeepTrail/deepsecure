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

@router.post("/credentials", response_model=schemas.credential.CredentialIssueResponse, status_code=status.HTTP_201_CREATED) # Or schemas.CredentialIssueResponse
def issue_credential(
    credential_in: schemas.credential.CredentialIssueRequest, # Or schemas.CredentialIssueRequest
    db: deps.DbDep,
    _: None = deps.APIKeyDep # Assuming APIKeyDep handles API key auth
):
    logger.info(f"Attempting to issue credential for agent: {credential_in.agent_id} with scope: {credential_in.scope}")

    # 1. Fetch the agent
    # If agent_id is None but your logic requires an agent for unsigned requests (e.g. for accountability)
    # you might need to adjust this. For now, assume agent_id can be None if signature is also None.
    agent = None
    if credential_in.agent_id:
        agent = crud.agent.get_by_agent_id(db=db, agent_id=credential_in.agent_id)
        if not agent:
            logger.warning(f"Agent not found during credential issuance: {credential_in.agent_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    elif credential_in.signature: 
        # If there's a signature, an agent_id must have been provided to find the agent's key.
        # Pydantic model should enforce agent_id if signature is present, or this check is needed.
        # For now, this case implies an issue if signature is present but agent_id was None.
        logger.error(f"Signature provided but agent_id is missing.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="agent_id is required if a signature is provided.")


    # 2. Decode ephemeral_public_key (Base64 validation already done by Pydantic validator)
    try:
        ephemeral_public_key_bytes = base64.b64decode(credential_in.ephemeral_public_key)
    except (TypeError, ValueError, base64.binascii.Error) as e:
        # This should ideally be caught by Pydantic validator, but as a safeguard:
        logger.error(f"Invalid base64 for ephemeral_public_key in endpoint: {credential_in.ephemeral_public_key}, Error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid base64 encoding for ephemeral_public_key")

    # 3. Verify the signature IF IT EXISTS and an agent was found (agent is required for signature verification)
    if credential_in.signature:
        if not agent: # Should have an agent if signature is present
            logger.error(f"Signature provided for agent '{credential_in.agent_id}' but agent could not be loaded (or agent_id was None).")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agent not found or not specified, cannot verify signature.")
        
        logger.info(f"Attempting signature verification for agent {credential_in.agent_id}")
        try:
            # Signature string already validated for base64 format by Pydantic
            signature_bytes = base64.b64decode(credential_in.signature)
            
            # Ensure agent.current_public_key is in raw bytes format
            agent_public_key_bytes = agent.current_public_key 
            if not isinstance(agent_public_key_bytes, bytes):
                # Attempt to decode if it's base64 stored in DB, or handle as per your DB schema
                try:
                    logger.warning("Agent's public key from DB is not in bytes, attempting base64 decode.")
                    agent_public_key_bytes = base64.b64decode(str(agent_public_key_bytes))
                except Exception as decode_err:
                    logger.error(f"Could not decode agent's public key from DB for agent {agent.agent_id}: {decode_err}")
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid agent public key format in database.")

            public_key_obj = ed25519.Ed25519PublicKey.from_public_bytes(agent_public_key_bytes)
            public_key_obj.verify(signature_bytes, ephemeral_public_key_bytes)
            logger.info(f"Signature verified successfully for agent {credential_in.agent_id}")

        except InvalidSignature:
            logger.warning(f"Invalid signature provided by agent {credential_in.agent_id}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")
        except (TypeError, ValueError, base64.binascii.Error) as e:
            logger.error(f"Failed to decode base64 signature in endpoint: {credential_in.signature}, Error: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid base64 encoding for signature")
        except Exception as e:
            logger.error(f"Error during signature verification for agent {credential_in.agent_id}: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Signature verification failed")
    else:
        logger.info(f"Bypassing signature verification (signature not provided in request). Issuing for agent: {credential_in.agent_id if credential_in.agent_id else 'Unspecified Agent'}")
        # If signature is NOT provided, you might have different logic here.
        # For example, you might require specific scopes or other checks.
        # For now, we assume if no signature, and agent_id is provided, it's an "asserted" identity by a trusted caller.
        # If agent_id is also None here, it means an anonymous credential issuance (if your system supports it).

    # 4. Create the credential record in the database
    try:
        # Construct the object for CRUD based on what crud.credential.create expects.
        # It likely takes the Pydantic model `credential_in` or specific fields.
        # Ensure `ttl` field is correctly passed if `crud.credential.create` expects it.
        
        # Map fields from CredentialIssueRequest to what crud.credential.create_with_owner or create expects
        # This example assumes crud.credential.create can handle the CredentialIssueRequest model directly
        # or you have a specific obj_in model for it.
        # For now, directly passing credential_in; adjust if your CRUD expects different structure.
        
        # We need to ensure that the data passed to CRUD for creation
        # has 'ttl' and not 'ttl_seconds' if that's what the DB model expects.
        # The CredentialIssueRequest model already has 'ttl'.
        
        # The CRUD layer will handle the actual database interaction.
        # It might expect `ephemeral_public_key_bytes` and `signature_bytes`
        # which the Pydantic model no longer stores directly.
        # It's better for CRUD or this endpoint to handle final byte conversion.
        
        # Create a dictionary for the CRUD operation, ensuring ephemeral_public_key is bytes
        crud_obj_in_data = {
            "agent_id": credential_in.agent_id,
            "scope": credential_in.scope,
            "ephemeral_public_key": ephemeral_public_key_bytes, # Pass raw bytes
            # Signature might be None or bytes if processed
            "signature": base64.b64decode(credential_in.signature) if credential_in.signature else None,
            "ttl_seconds": credential_in.ttl, # Assuming DB/CRUD might expect ttl_seconds or handles 'ttl'
            "origin_context": credential_in.origin_context,
            # Add other fields your CRUD create method expects
        }
        # You'll need to adjust this mapping based on your actual CRUD `create` method signature
        # and the fields your database model for Credential expects.
        # For instance, if CRUD expects a Pydantic schema, pass that.
        # This is a placeholder for the actual data prep for CRUD.

        # This is a simplified call. Your CRUD might need more specific handling
        # e.g. separate fields for eph_key_bytes and sig_bytes etc.
        # For now, this is illustrative. The main goal was to bypass sig verification.

        # This is a conceptual adaptation for CRUD.
        # You will need to ensure your `crud.credential.create` function
        # is compatible with receiving these fields or a Pydantic model.
        # The example here assumes it can take specific fields, including `ttl_seconds`.
        # If your DB model for Credential uses `ttl` (int seconds), then pass `credential_in.ttl`.
        
        # Based on your vault.py, it seems to use `credential_in` directly:
        # credential = crud.credential.create(db=db, obj_in=credential_in)
        # If so, ensure `credential_in` Pydantic model has all necessary fields in correct types
        # that `crud.credential.create` expects and that the DB model can store.
        # The `ephemeral_public_key` and `signature` in `credential_in` are strings.
        # If CRUD/DB expects bytes, conversion must happen.
        
        # Let's stick to the structure that seems to be in your vault.py:
        # crud.credential.create(db=db, obj_in=credential_in)
        # This means `credential_in` (which is `schemas.credential.CredentialIssueRequest`)
        # must be acceptable to your CRUD layer.
        # The validator in `CredentialIssueRequest` returns the original base64 string,
        # so `credential_in.ephemeral_public_key` and `credential_in.signature` are strings.
        # Your CRUD layer or DB model must handle conversion to bytes if needed.
        
        credential = crud.credential.create(db=db, obj_in=credential_in) # Uses the Pydantic model
        logger.info(f"Successfully created credential {credential.credential_id} for agent {credential_in.agent_id}")
    except ValueError as ve:
        logger.error(f"ValueError during credential creation: {ve}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to create credential record for agent {credential_in.agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create credential")

    # Construct the response using CredentialIssueResponse schema
    # This will handle encoding bytes back to base64 if needed (e.g. for ephemeral_public_key)
    return schemas.credential.CredentialIssueResponse.model_validate(credential)

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
            is_valid=is_valid,
            status=status_message,
            scope=db_credential.scope if db_credential else None,
            agent_id=db_credential.agent_id if db_credential else None,
            issued_at=db_credential.issued_at if db_credential else None,
            expires_at=db_credential.expires_at if db_credential else None,
            # verified_at=db_credential.verified_at if db_credential else None,
            verified_at=datetime.now(timezone.utc),
            ephemeral_public_key=db_credential.ephemeral_public_key if db_credential else None,
            origin_context=db_credential.origin_context if db_credential else None,
        )

    now = datetime.now(timezone.utc)
    status_message = "valid"
    is_valid = True

    # Ensure issued_at from DB is also timezone-aware if needed, similar to expires_at
    issued_at_aware = db_credential.issued_at
    if issued_at_aware and issued_at_aware.tzinfo is None:
        issued_at_aware = issued_at_aware.replace(tzinfo=timezone.utc)

    eph_pub_key_b64: Optional[str] = None
    if db_credential.ephemeral_public_key:
        if isinstance(db_credential.ephemeral_public_key, bytes):
            eph_pub_key_b64 = base64.b64encode(db_credential.ephemeral_public_key).decode('utf-8')
        elif isinstance(db_credential.ephemeral_public_key, str):
            eph_pub_key_b64 = db_credential.ephemeral_public_key

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
        issued_at=issued_at_aware,
        expires_at=expires_at_aware, # Return the timezone-aware version
        verified_at=datetime.now(timezone.utc),
        ephemeral_public_key=eph_pub_key_b64,
        origin_context=db_credential.origin_context if db_credential else None,
    ) 