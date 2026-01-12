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
from app.schemas.credential import SecretStoreRequest, SecretStoreResponse
from app.schemas.agent import AgentRotateRequest # Import schema for rotation

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/secrets", status_code=status.HTTP_200_OK)
def list_secrets(
    db: deps.DbDep,
    _: Any = deps.APIKeyDep
):
    """
    Lists all secrets in the vault (metadata only, no values).
    Returns secret names, created timestamps, and metadata labels.
    Share values are never exposed.
    """
    logger.info("Listing all secrets in vault")
    try:
        secrets = crud.secret.list_secrets(db=db)
        return {
            "secrets": [
                {
                    "name": s.name,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "metadata": s.secret_metadata or {}
                }
                for s in secrets
            ],
            "count": len(secrets)
        }
    except Exception as e:
        logger.error(f"Failed to list secrets: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not list secrets")


@router.post("/store", response_model=SecretStoreResponse, status_code=status.HTTP_201_CREATED)
def store_secret(
    secret_in: SecretStoreRequest,
    db: deps.DbDep,
    _: Any = deps.APIKeyDep
):
    """
    Store or update a secret in the vault.
    This is a simple key-value store for demonstration and testing.
    In a real-world scenario, this would involve encryption and more robust access control.
    """
    logger.info(f"Storing secret with name: {secret_in.name}")
    try:
        crud.secret.create_secret(db=db, obj_in=secret_in)
        return {"name": secret_in.name, "message": "Secret stored successfully"}
    except Exception as e:
        logger.error(f"Failed to store secret {secret_in.name}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not store secret")

@router.get("/secrets/{name}", status_code=status.HTTP_200_OK)
def get_secret_direct(
    name: str,
    db: deps.DbDep,
    _: Any = deps.APIKeyDep
):
    """
    Retrieve a secret directly from the vault by name.
    This is for administrative/CLI use and bypasses the ephemeral credential system.
    For programmatic agent access, use the credential issuance flow instead.
    """
    logger.info(f"Retrieving secret with name: {name}")
    try:
        secret_obj = crud.secret.get_secret_by_name(db=db, name=name)
        if not secret_obj:
            logger.warning(f"Secret '{name}' not found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Secret '{name}' not found")
        
        return {
            "name": secret_obj.name,
            "metadata": secret_obj.secret_metadata or {},
            "created_at": secret_obj.created_at.isoformat() if secret_obj.created_at else None
        }
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Failed to retrieve secret {name}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve secret")


@router.get("/secrets/{name}/value", status_code=status.HTTP_200_OK)
def get_secret_with_value(
    name: str,
    db: deps.DbDep,
    _: Any = deps.APIKeyDep
):
    """
    Retrieve a secret with its reassembled value.
    
    This endpoint fetches share_1 from the local database and share_2 from the gateway,
    then reassembles the original secret using Shamir's Secret Sharing algorithm.
    
    This is for administrative/CLI use and requires API key authentication.
    The reassembled secret only exists briefly in memory during this request.
    """
    import json
    import httpx
    from sslib import shamir
    from app.core.config import settings
    
    logger.info(f"Retrieving secret with value for: {name}")
    try:
        # 1. Get share_1 from the local database
        secret_obj = crud.secret.get_secret_by_name(db=db, name=name)
        if not secret_obj:
            logger.warning(f"Secret '{name}' not found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Secret '{name}' not found")
        
        share_1_str = secret_obj.share_1
        
        # 2. Fetch share_2 from the gateway
        try:
            gateway_url = f"{settings.GATEWAY_URL}/internal/shares/{name}"
            headers = {"X-Internal-API-Token": settings.GATEWAY_INTERNAL_API_TOKEN}
            with httpx.Client() as client:
                response = client.get(gateway_url, headers=headers)
                if response.status_code == 404:
                    logger.warning(f"Share_2 for '{name}' not found in gateway (may have expired)")
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, 
                                      detail=f"Secret share not found in gateway (may have expired)")
                response.raise_for_status()
                gateway_data = response.json()
                # Gateway returns {"secret_name": ..., "share_2": {"share_value": [...], "prime_mod": ..., ...}}
                share_2_container = gateway_data.get("share_2", {})
                # Extract the actual share value from the container
                if isinstance(share_2_container, dict):
                    share_2_str = share_2_container.get("share_value")
                    gateway_prime_mod_hex = share_2_container.get("prime_mod")
                else:
                    share_2_str = share_2_container
                    gateway_prime_mod_hex = None
        except httpx.RequestError as e:
            logger.error(f"Could not connect to gateway for share_2: {e}")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                              detail="Could not retrieve secret share from gateway")
        
        # 3. Parse shares from JSON
        try:
            share_1 = json.loads(share_1_str) if isinstance(share_1_str, str) else share_1_str
            share_2 = json.loads(share_2_str) if isinstance(share_2_str, str) else share_2_str
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse shares: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                              detail="Failed to parse secret shares")
        
        # 4. Reassemble the secret using Shamir's algorithm
        try:
            # Convert hex strings back to bytes
            share_1_bytes = (share_1[0], bytes.fromhex(share_1[1]))
            share_2_bytes = (share_2[0], bytes.fromhex(share_2[1]))
            
            # Get prime_mod from secret_metadata (stored during split) or gateway response
            prime_mod_hex = None
            if secret_obj.secret_metadata:
                prime_mod_hex = secret_obj.secret_metadata.get('_prime_mod')
            if not prime_mod_hex and gateway_prime_mod_hex:
                prime_mod_hex = gateway_prime_mod_hex
            
            if prime_mod_hex:
                prime_mod = bytes.fromhex(prime_mod_hex)
            else:
                # Fallback: estimate prime_mod based on share length (may not work)
                share_len = len(share_1_bytes[1])
                prime_mod = b'\x07' + b'\xff' * (share_len - 1)
                logger.warning(f"Using estimated prime_mod for secret '{name}' - consider re-storing")
            
            # Reconstruct the data structure expected by recover_secret
            recovery_data = {
                'required_shares': 2,
                'prime_mod': prime_mod,
                'shares': [share_1_bytes, share_2_bytes]
            }
            
            # Reassemble the secret
            recovered_secret = shamir.recover_secret(recovery_data)
            secret_value = recovered_secret.decode('utf-8')
            
            logger.info(f"Successfully reassembled secret '{name}'")
        except Exception as e:
            logger.error(f"Failed to reassemble secret '{name}': {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                              detail="Failed to reassemble secret")
        
        return {
            "name": secret_obj.name,
            "value": secret_value,
            "metadata": secret_obj.secret_metadata or {},
            "created_at": secret_obj.created_at.isoformat() if secret_obj.created_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve secret with value {name}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                          detail="Could not retrieve secret")


@router.delete("/secrets/{name}", status_code=status.HTTP_200_OK)
def delete_secret(
    name: str,
    db: deps.DbDep,
    _: Any = deps.APIKeyDep
):
    """
    Delete a secret from the vault by name.
    This also deletes the corresponding share from the gateway.
    """
    import httpx
    from app.core.config import settings
    
    logger.info(f"Deleting secret with name: {name}")
    try:
        # First, check if the secret exists
        secret_obj = crud.secret.get_secret_by_name(db=db, name=name)
        if not secret_obj:
            logger.warning(f"Secret '{name}' not found for deletion")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Secret '{name}' not found")
        
        # Delete share from gateway (best effort - gateway might already have expired it)
        try:
            gateway_url = f"{settings.GATEWAY_URL}/internal/shares/{name}"
            headers = {"X-Internal-API-Token": settings.GATEWAY_INTERNAL_API_TOKEN}
            with httpx.Client() as client:
                response = client.delete(gateway_url, headers=headers)
                if response.status_code == 404:
                    logger.info(f"Share for '{name}' not found in gateway (may have expired)")
                else:
                    response.raise_for_status()
                    logger.info(f"Successfully deleted share for '{name}' from gateway")
        except httpx.RequestError as e:
            logger.warning(f"Could not delete share from gateway for '{name}': {e}")
            # Continue with local deletion even if gateway fails
        
        # Delete from local database
        deleted = crud.secret.delete_secret(db=db, name=name)
        if deleted:
            logger.info(f"Successfully deleted secret '{name}' from control plane")
            return {"name": name, "message": "Secret deleted successfully"}
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete secret")
            
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Failed to delete secret {name}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not delete secret")

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

    # 4. Check if this is a secret access request and fetch the secret value
    secret_value = None
    if credential_in.scope and credential_in.scope.startswith("secret:"):
        secret_name = credential_in.scope[7:]  # Remove "secret:" prefix
        logger.info(f"Fetching secret '{secret_name}' for credential issuance")
        secret_obj = crud.secret.get_secret_by_name(db=db, name=secret_name)
        if not secret_obj:
            logger.warning(f"Secret '{secret_name}' not found for agent {credential_in.agent_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Secret '{secret_name}' not found")
        secret_value = secret_obj.value
        logger.info(f"Successfully retrieved secret '{secret_name}' for credential issuance")

    # 5. Create the credential record in the database
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

    # 6. Add secret value to the response if this was a secret request
    if secret_value is not None:
        # We need to add the secret_value to the credential response
        # Since we're returning the credential object directly, we need to modify the response
        credential_dict = credential.__dict__.copy()
        credential_dict['secret_value'] = secret_value
        return credential_dict

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