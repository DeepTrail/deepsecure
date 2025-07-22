'''Client for interacting with the Vault API for credential management.'''

import time
import socket
import os
import json
import uuid
import hashlib
from typing import Dict, Any, Optional, Set
from datetime import datetime, timedelta
import re
import sys
from pathlib import Path
import requests
import logging # Import logging
import base64
from cryptography.hazmat.primitives.asymmetric import ed25519 as ed25519_crypto
from pydantic import ValidationError as PydanticValidationError # Explicit import for clarity

from . import base_client
from .crypto.key_manager import key_manager
from .audit_logger import audit_logger
from .. import exceptions
from . import schemas as client_schemas # Import client-side Pydantic schemas for request payload

# print("\n<<<< DEBUG: vault_client.py IS BEING LOADED AND EXECUTED (top level) >>>>\n", file=sys.stderr)
# # To be absolutely sure, you could uncomment the next line to see if it exits here:
# # sys.exit("<<<< DEBUG: EXITING FROM VAULT_CLIENT.PY TOP LEVEL >>>>")

logger = logging.getLogger(__name__) # Define logger

# --- Constants for Local State --- #
DEEPSECURE_DIR = Path(os.path.expanduser("~/.deepsecure"))
IDENTITY_STORE_PATH = DEEPSECURE_DIR / "identities"
DEVICE_ID_FILE = DEEPSECURE_DIR / "device_id"
REVOCATION_LIST_FILE = DEEPSECURE_DIR / "revoked_creds.json"

class VaultClient(base_client.BaseClient):
    """Client for interacting with the Vault API for credential management.

    Handles agent identity management (local file-based for now), ephemeral
    key generation, credential signing, origin context capture, interaction
    with the audit logger and cryptographic key manager, and local credential
    revocation and verification.
    """
    
    def __init__(self, client: base_client.BaseClient):
        """Initialize the Vault client.

        Sets up the service name for the base client, initializes dependencies
        like the key manager and audit logger, ensures local storage directories
        exist, and loads the local revocation list.
        """
        self._client = client
        self.key_manager = key_manager
        self.audit_logger = audit_logger
        self.revocation_list_file = REVOCATION_LIST_FILE
        
        # Ensure directories exist
        DEEPSECURE_DIR.mkdir(exist_ok=True)
        
        # Load local revocation list
        self._revoked_ids: Set[str] = self._load_revocation_list()
    
    # --- Revocation List Management --- #
    
    def _load_revocation_list(self) -> Set[str]:
        """Loads the set of revoked credential IDs from the local file."""
        if not self.revocation_list_file.exists():
            return set()
        try:
            with open(self.revocation_list_file, 'r') as f:
                # Load as list, convert to set for efficient lookup
                revoked_list = json.load(f)
                if isinstance(revoked_list, list):
                    return set(revoked_list)
                else:
                    print(f"[Warning] Revocation file {self.revocation_list_file} has invalid format. Ignoring.", file=sys.stderr)
                    return set() # Corrupted file
        except (json.JSONDecodeError, IOError) as e:
            print(f"[Warning] Failed to load revocation list {self.revocation_list_file}: {e}", file=sys.stderr)
            return set()

    def _save_revocation_list(self) -> None:
        """Saves the current set of revoked credential IDs to the local file."""
        try:
            with open(self.revocation_list_file, 'w') as f:
                # Save as a list for standard JSON format
                json.dump(list(self._revoked_ids), f, indent=2)
            self.revocation_list_file.chmod(0o600) # Set permissions
        except IOError as e:
            # Non-fatal error, but log it
            print(f"[Warning] Failed to save revocation list {self.revocation_list_file}: {e}", file=sys.stderr)
            # TODO: Improve error handling/logging here.

    def is_revoked(self, credential_id: str) -> bool:
        """Checks if a credential ID is in the local revocation list.
        
        Args:
            credential_id: The ID to check.
            
        Returns:
            True if the credential ID has been revoked locally, False otherwise.
        """
        # Refresh the list in case another process updated it?
        # For simplicity now, we rely on the list loaded at init.
        # self._revoked_ids = self._load_revocation_list()
        return credential_id in self._revoked_ids
        
    # --- Identity and Context Management (mostly unchanged) --- #
    
    def _capture_origin_context(self) -> Dict[str, Any]:
        """
        Capture information about the credential issuance origin environment.

        Collects details like hostname, username, process ID, timestamp, IP address,
        and a persistent device identifier.

        Returns:
            A dictionary containing key-value pairs representing the origin context.
        """
        context = {
            "hostname": socket.gethostname(),
            "username": os.getlogin(), # Note: getlogin() can fail in some environments (e.g., daemons)
            "process_id": os.getpid(),
            "timestamp": int(time.time())
        }
        
        # Add IP address if we can get it
        try:
            # Try getting the IP associated with the hostname
            context["ip_address"] = socket.gethostbyname(socket.gethostname())
        except socket.gaierror:
            # Fallback if hostname resolution fails
            context["ip_address"] = "127.0.0.1"
            # TODO: Implement a more robust method to get the primary IP address.
        
        # Add device identifier
        context["device_id"] = self._get_device_identifier()
        
        # TODO: Optionally include hardware attestation if available (e.g., from TPM/TEE).
        
        return context
    
    def _get_device_identifier(self) -> str:
        """
        Get a unique and persistent identifier for the current device.

        Currently uses a simple file-based UUID stored in the user's home directory.
        A new ID is generated and stored if the file doesn't exist.

        Returns:
            A string representing the device identifier (UUID).
        """
        # TODO: Replace simple file-based device ID with a more robust hardware-based identifier.
        device_id_file = DEVICE_ID_FILE
        
        if device_id_file.exists():
            try:
                with open(device_id_file, 'r') as f:
                    device_id = f.read().strip()
                    # Basic validation for UUID format
                    uuid.UUID(device_id)
                    return device_id
            except (IOError, ValueError):
                # File corrupted or invalid, proceed to create a new one
                pass 
                
        # Create a new device ID if file doesn't exist or is invalid
        device_id = str(uuid.uuid4())
        try:
            device_id_file.parent.mkdir(parents=True, exist_ok=True)
            with open(device_id_file, 'w') as f:
                f.write(device_id)
            device_id_file.chmod(0o600) # Restrict permissions
        except IOError as e:
            # If we can't store it persistently, use a temporary one for this session
            print(f"[Warning] Failed to store persistent device ID: {e}", file=sys.stderr)
            # TODO: Log this warning properly.
            return device_id 
            
        return device_id
    
    def _calculate_expiry(self, ttl: str) -> int:
        """
        Calculate an expiry timestamp from a Time-To-Live (TTL) string.

        Parses TTL strings like "5m", "1h", "7d", "2w".

        Args:
            ttl: The Time-to-live string.

        Returns:
            The calculated expiration timestamp as a Unix epoch integer.

        Raises:
            ValueError: If the TTL format or unit is invalid.
        """
        ttl_pattern = re.compile(r'^(\d+)([smhdw])$')
        match = ttl_pattern.match(ttl)
        
        if not match:
            raise ValueError(f"Invalid TTL format: {ttl}. Expected format: <number><unit> (e.g., 5m, 1h, 7d)")
        
        value, unit = match.groups()
        value = int(value)
        
        now = datetime.now()
        delta = None
        
        if unit == 's':
            delta = timedelta(seconds=value)
        elif unit == 'm':
            delta = timedelta(minutes=value)
        elif unit == 'h':
            delta = timedelta(hours=value)
        elif unit == 'd':
            delta = timedelta(days=value)
        elif unit == 'w':
            delta = timedelta(weeks=value)
        # else: # This case is implicitly handled by the regex, but added for clarity
        #     raise ValueError(f"Invalid TTL unit: {unit}")
        
        if delta is None:
             raise ValueError(f"Invalid TTL unit: {unit}") # Should not happen with regex
             
        expiry = now + delta
        return int(expiry.timestamp())
    
    def _create_context_bound_message(self, ephemeral_public_key: str, 
                                     origin_context: Dict[str, Any]) -> bytes:
        """
        Create a deterministic, hashed message combining the ephemeral public key
        and the origin context. This message is intended to be signed for
        origin-bound credentials.

        Args:
            ephemeral_public_key: Base64-encoded ephemeral public key.
            origin_context: Dictionary containing the origin context.

        Returns:
            A bytes object representing the SHA256 hash of the serialized data.
        """
        # TODO: Verify if signing the hash is the desired approach vs signing raw serialized data.
        # Serialize the context with the ephemeral key
        context_data = {
            "ephemeral_public_key": ephemeral_public_key,
            "origin_context": origin_context
        }
        
        # Create a deterministic serialization (sort keys)
        serialized_data = json.dumps(context_data, sort_keys=True).encode('utf-8')
        
        # Hash the data to create a fixed-length message
        return hashlib.sha256(serialized_data).digest()
    
    def _create_credential(self, agent_id: str, ephemeral_public_key: str,
                          signature: str, scope: str, expiry: int,
                          origin_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assemble the final credential token dictionary.

        Args:
            agent_id: The identifier of the agent receiving the credential.
            ephemeral_public_key: The base64-encoded ephemeral public key.
            signature: The base64-encoded signature.
            scope: The scope of access granted by the credential.
            expiry: The Unix timestamp when the credential expires.
            origin_context: The origin context associated with the credential issuance.

        Returns:
            A dictionary representing the structured credential token.
        """
        # TODO: Consider using a standardized token format like JWT or PASETO.
        credential_id = f"cred-{uuid.uuid4()}"
        
        credential = {
            "credential_id": credential_id,
            "agent_id": agent_id,
            "ephemeral_public_key": ephemeral_public_key,
            "signature": signature,
            "scope": scope,
            "issued_at": int(time.time()),
            "expires_at": expiry,
            "origin_context": origin_context
        }
        
        return credential
    
    # --- Core Credential Operations --- #
    
    def issue_credential(self, scope: str, ttl: str, agent_id: str, # agent_id is now mandatory
                        origin_context: Optional[Dict[str, Any]] = None,
                        origin_binding: bool = True,
                        local_only: bool = False # local_only flag might be deprecated if all issuance goes to backend
                        ) -> Dict[str, Any]: # Should return client_schemas.CredentialResponse eventually
        
        print("\nDEBUG [VaultClient]: TOP OF issue_credential METHOD REACHED\n", file=sys.stderr)
        
        logger.info(f"[VaultClient Core] Issuing credential for agent: {agent_id}, scope: {scope}, ttl: {ttl}")
        try:
            ttl_seconds = self._parse_ttl_to_seconds(ttl)
        except ValueError as e:
            self.audit_logger.log_credential_issuance_failed(agent_id=agent_id, scope=scope, reason=f"Invalid TTL: {e}")
            raise

        agent_identity = self._client._identity_manager.get_identity(agent_id)
        if not agent_identity:
            err_msg = f"Local identity for agent_id '{agent_id}' not found by IdentityManager."
            logger.error(f"[VaultClient Core] {err_msg}")
            self.audit_logger.log_credential_issuance_failed(agent_id=agent_id, scope=scope, reason=err_msg)
            raise exceptions.VaultError(err_msg)

        loaded_public_key_b64 = agent_identity.public_key_b64
        logger.info(f"[VaultClient Core] Public key from loaded local identity for {agent_id}: {loaded_public_key_b64}")

        agent_private_key_b64 = agent_identity.private_key_b64
        logger.info(f"[VaultClient Core] Private key loaded from IdentityManager for {agent_id} (first 10 chars): {str(agent_private_key_b64)[:10]}...")
        if not agent_private_key_b64:
            err_msg = f"Private key for agent_id '{agent_id}' not found via IdentityManager (keyring). Cannot sign request."
            logger.error(f"[VaultClient Core] {err_msg}")
            self.audit_logger.log_credential_issuance_failed(agent_id=agent_id, scope=scope, reason=err_msg)
            raise exceptions.VaultError(err_msg)

        ephemeral_keys = self.key_manager.generate_ephemeral_keypair()
        ephemeral_public_key_b64 = ephemeral_keys["public_key"]
        ephemeral_private_key_b64_to_return = ephemeral_keys["private_key"]

        signature_b64_str: str
        try:
            logger.info(f"[VAULT_CLIENT_DEBUG] Signing for {agent_id} using private key.")
            raw_agent_private_key_bytes = base64.b64decode(agent_private_key_b64)
            if len(raw_agent_private_key_bytes) != 32:
                raise ValueError("Agent private key (decoded) is not 32 bytes.")
            agent_private_key_obj = ed25519_crypto.Ed25519PrivateKey.from_private_bytes(raw_agent_private_key_bytes)
            
            raw_ephemeral_public_key_bytes = base64.b64decode(ephemeral_public_key_b64)
            if len(raw_ephemeral_public_key_bytes) != 32:
                 raise ValueError("Ephemeral public key (decoded) is not 32 bytes for signing.")

            signature_bytes = agent_private_key_obj.sign(raw_ephemeral_public_key_bytes)
            signature_b64_str = base64.b64encode(signature_bytes).decode('utf-8')
            logger.info(f"[VAULT_CLIENT_DEBUG] Successfully signed ephemeral key for {agent_id}. Signature (first 10): {signature_b64_str[:10]}...")
        except Exception as e:
            err_msg = f"Failed to sign ephemeral key for agent {agent_id}: {e}"
            logger.error(f"[VaultClient Core] {err_msg}", exc_info=True)
            self.audit_logger.log_credential_issuance_failed(agent_id=agent_id, scope=scope, reason=err_msg)
            raise exceptions.VaultError(err_msg) from e 

        # This is just to ensure the variable is present for the Pydantic model if the previous block was faulty in an edit.
        if 'signature_b64_str' not in locals(): signature_b64_str = "dummy_signature_for_debug_if_missing"
        if 'ephemeral_public_key_b64' not in locals(): ephemeral_public_key_b64 = "dummy_ephemeral_pk_for_debug"
        if 'ttl_seconds' not in locals(): ttl_seconds = 300 # Dummy TTL

        final_origin_context: Optional[Dict[str, Any]] = None
        if origin_binding:
            final_origin_context = origin_context if origin_context is not None else self._capture_origin_context()
        
        print(f"DEBUG [VaultClient]: 1. final_origin_context to be used: {final_origin_context}", file=sys.stderr)

        try:
            request_payload_model = client_schemas.CredentialIssueRequest(
                agent_id=agent_id,
                ephemeral_public_key=ephemeral_public_key_b64,
                signature=signature_b64_str, 
                ttl=ttl_seconds, 
                scope=scope,
                origin_context=final_origin_context
            )
            print(f"DEBUG [VaultClient]: 2. request_payload_model dir: {dir(request_payload_model)}", file=sys.stderr)
            print(f"DEBUG [VaultClient]: 2.1. request_payload_model.origin_context: {getattr(request_payload_model, 'origin_context', 'MISSING_ATTRIBUTE')}", file=sys.stderr)
            
            # Try dumping with by_alias=False and exclude_unset=False to be very inclusive
            payload_dict = request_payload_model.model_dump(exclude_unset=False, by_alias=False)
            print(f"DEBUG [VaultClient]: 3. payload_dict AFTER model_dump(exclude_unset=False): {payload_dict}", file=sys.stderr)
            print(f"DEBUG [VaultClient]: 3.1. origin_context in payload_dict: {payload_dict.get('origin_context', 'NOT_IN_PAYLOAD_DICT')}", file=sys.stderr)

        except PydanticValidationError as e: 
            err_msg = f"Client-side payload validation error (Pydantic): {e}"
            logger.error(f"[VaultClient Core] {err_msg}", exc_info=True)
            self.audit_logger.log_credential_issuance_failed(agent_id=agent_id, scope=scope, reason=err_msg)
            raise exceptions.InvalidRequestError(err_msg, error_details=e.errors()) from e

        logger.info(f"[VaultClient Core] Attempting backend credential issuance for agent {agent_id}")
        try:
            # Phase 1: Use standardized authenticated request method
            # This ensures proper authentication and consistent routing through BaseClient
            server_response = self._client._authenticated_request(
                "POST",
                "/api/v1/vault/credentials",
                agent_id=agent_id,
                json=payload_dict
            )
            server_response_data = server_response.json()
            # Server returns data matching server-side CredentialIssueResponse (which should be compatible with client_schemas.CredentialBase)
            # Validate against client_schemas.CredentialBase
            server_response_base = client_schemas.CredentialBase.model_validate(server_response_data)

            # Construct final client response, adding back the ephemeral private key
            issued_credential = client_schemas.CredentialResponse(
                **server_response_base.model_dump(),
                ephemeral_public_key_b64=ephemeral_public_key_b64, # Use the one we generated and sent
                ephemeral_private_key_b64=ephemeral_private_key_b64_to_return
            )

            self.audit_logger.log_credential_issuance(
                credential_id=issued_credential.credential_id,
                agent_id=agent_id,
                scope=scope, ttl=ttl, backend_issued=True
            )
            logger.info(f"[VaultClient Core] Successfully issued credential {issued_credential.credential_id} via backend.")
            return issued_credential.model_dump() # Return as dict for CLI compatibility, or return Pydantic model

        except (exceptions.ApiError, ValueError, requests.exceptions.RequestException) as e:
            logger.error(f"[VaultClient Core] Backend issuance failed: {e}", exc_info=True)
            self.audit_logger.log_credential_issuance_failed(agent_id=agent_id, scope=scope, reason=f"Backend error: {e}")
            raise # Re-raise to be caught by CLI command

    # Helper for TTL parsing (internal to VaultClient)
    def _parse_ttl_to_seconds(self, ttl_str: str) -> int:
        ttl_pattern = re.compile(r'^(\d+)([smhdw])$')
        match = ttl_pattern.match(ttl_str)
        if not match:
            raise ValueError(f"Invalid TTL format: '{ttl_str}'. Expected <number><unit> (e.g., 5m, 1h, 7d)")
        value, unit_char = match.groups()
        value_int = int(value)
        delta = None
        if unit_char == 's': delta = timedelta(seconds=value_int)
        elif unit_char == 'm': delta = timedelta(minutes=value_int)
        elif unit_char == 'h': delta = timedelta(hours=value_int)
        elif unit_char == 'd': delta = timedelta(days=value_int)
        elif unit_char == 'w': delta = timedelta(weeks=value_int)
        if delta is None or value_int <=0: raise ValueError("Invalid or non-positive TTL value.")
        return int(delta.total_seconds())

    def revoke_credential(self, credential_id: str, local_only: bool = False) -> bool:
        """
        Revoke a credential.

        If `local_only` is True, only adds the ID to the local revocation list.
        If `local_only` is False (default), attempts backend revocation.
        The local list is ONLY updated if the backend call succeeds (or if local_only).

        Args:
            credential_id: The ID of the credential to revoke.
            local_only: If True, skip backend interaction attempt.

        Returns:
            True if the credential was successfully marked as revoked (either locally
            for local_only=True, or via backend for local_only=False), False otherwise.
        """
        if not credential_id:
            logger.warning("Attempted to revoke an empty credential ID.")
            return False

        # --- Backend Revocation Attempt --- #
        backend_success = False
        if not local_only and self._client.backend_url and self._client.backend_api_token:
            logger.info(f"Attempting backend revocation for id={credential_id}")
            try:
                # Backend endpoint is POST /api/v1/vault/credentials/{credential_id}/revoke
                response_data = self._client._request(
                    "POST",
                    f"/api/v1/vault/credentials/{credential_id}/revoke",
                    is_backend_request=True
                )
                # Check response status field from CredentialRevokeResponse
                if response_data.get("status") in ["revoked", "already_revoked"]:
                    logger.info(f"Backend successfully processed revocation for {credential_id} (status: {response_data.get('status')}).")
                    backend_success = True
                else:
                    logger.error(f"Backend returned unexpected status for revocation of {credential_id}: {response_data.get('status')}")
                    # Consider raising error or just returning False
                    return False # Failed on backend

            except exceptions.ApiError as e:
                # Handle specific errors, e.g., 404 means it didn't exist on backend
                if e.status_code == 404:
                    logger.warning(f"Credential {credential_id} not found on backend for revocation.")
                    # If not found on backend, should we still revoke locally? Maybe not.
                    # Let's return False, as the authoritative source says it doesn't exist.
                    return False
                else:
                    # Log other API errors and potentially fail
                    logger.error(f"Backend revocation failed for {credential_id}: {e}")
                    audit_logger.log_credential_revocation_failed(credential_id=credential_id, reason=f"Backend error: {e}")
                    return False # Backend failed
            except Exception as e:
                 logger.error(f"Unexpected error during backend revocation for {credential_id}: {e}", exc_info=True)
                 audit_logger.log_credential_revocation_failed(credential_id=credential_id, reason=f"Unexpected error: {e}")
                 return False # Unexpected failure
        elif not local_only:
             logger.warning("Backend not configured (URL or Token missing). Cannot perform backend revocation.")
             # If backend isn't configured, should we allow local-only? For now, let's require explicit local_only=True
             print("[Error] Backend not configured. Use --local-only to revoke locally.", file=sys.stderr)
             return False

        # --- Local Revocation (only if backend succeeded or local_only=True) --- #
        if local_only or backend_success:
            if credential_id in self._revoked_ids:
                logger.info(f"Credential {credential_id} is already revoked locally.")
                # Already revoked locally, log the attempt again for audit trail
                audit_logger.log_credential_revocation(credential_id=credential_id, revoked_by="local_user", backend_revoked=backend_success)
                return True # Considered success
            else:
                self._revoked_ids.add(credential_id)
                self._save_revocation_list()
                logger.info(f"Credential {credential_id} added to local revocation list.")
                audit_logger.log_credential_revocation(credential_id=credential_id, revoked_by="local_user", backend_revoked=backend_success)
                return True
        else:
            # This case means backend was attempted but failed (and not local_only)
            return False
    
    def rotate_credential(self, agent_id: str, credential_type: str, local_only: bool = False) -> Dict[str, Any]:
        """Rotate the agent's long-term identity key (Ed25519).

        Updates the local identity file first, then attempts to notify the backend
        if `local_only` is False and the backend is configured.

        Args:
            agent_id: The identifier of the agent whose identity should be rotated.
            credential_type: Must be "agent-identity".
            local_only: If True, skip backend notification attempt.

        Returns:
            A dictionary with status and the agent_id.

        Raises:
            NotImplementedError: If the type is not 'agent-identity'.
            VaultError: If the local identity file cannot be read/written.
            ApiError: If the backend notification fails.
            ValueError: If backend URL/token missing when needed.
        """
        if credential_type != "agent-identity":
            raise NotImplementedError(f"Rotation for type '{credential_type}' is not supported.")

        logger.info(f"Initiating local rotation for agent identity: {agent_id}")

        # --- Local Rotation --- #
        identity_file = IDENTITY_STORE_PATH / f"{agent_id}.json"
        if not identity_file.exists():
             audit_logger.log_credential_rotation_failed(agent_id=agent_id, credential_type=credential_type, reason="Local identity file not found")
             raise exceptions.VaultError(f"Local identity file not found for agent {agent_id}")

        # 1. Generate new keys
        new_keys = self.key_manager.generate_identity_keypair()
        new_public_key_b64 = new_keys["public_key"]
        new_private_key_b64 = new_keys["private_key"]
        logger.debug(f"Generated new identity keys for agent {agent_id}")

        # 2. Read existing identity and update
        try:
            with open(identity_file, 'r') as f:
                identity = json.load(f)
            
            # Optional: Backup old key?
            # old_private_key = identity.get("private_key")
            # old_public_key = identity.get("public_key")

            identity["private_key"] = new_private_key_b64
            identity["public_key"] = new_public_key_b64
            rotated_at_ts = int(time.time()) # Define timestamp before updating dict
            identity["rotated_at"] = rotated_at_ts # Update identity dict

        except (json.JSONDecodeError, IOError, KeyError) as e:
            audit_logger.log_credential_rotation_failed(agent_id=agent_id, credential_type=credential_type, reason=f"Error reading local identity: {e}")
            raise exceptions.VaultError(f"Failed to read or parse identity for {agent_id}: {e}") from e

        # 3. Write updated identity back to file
        try:
            # Write to temp file first for atomicity?
            with open(identity_file, 'w') as f:
                json.dump(identity, f, indent=2)
            identity_file.chmod(0o600) # Ensure permissions
            logger.info(f"Successfully updated local identity file for agent {agent_id}")
        except IOError as e:
            audit_logger.log_credential_rotation_failed(agent_id=agent_id, credential_type=credential_type, reason=f"Error writing local identity: {e}")
            raise exceptions.VaultError(f"Failed to save rotated identity for {agent_id}: {e}") from e

        # --- Backend Notification Attempt --- #
        backend_notified = False
        if not local_only and self._client.backend_url and self._client.backend_api_token:
            logger.info(f"Attempting backend notification for key rotation: agent={agent_id}")
            try:
                payload = {
                    # Backend expects key bytes encoded in base64 in the request
                    "new_public_key": new_public_key_b64
                }
                response_data = self._client._request(
                    "POST",
                    f"/api/v1/vault/agents/{agent_id}/rotate-identity",
                    data=payload,
                    is_backend_request=True
                )
                # Expect 204 No Content on success
                # _handle_response converts 204 to {"status": "success"...}
                if response_data.get("status") == "success":
                     logger.info(f"Backend successfully notified of key rotation for agent {agent_id}")
                     backend_notified = True
                else:
                    # This case should ideally not happen due to _handle_response raising HTTPError
                    logger.error(f"Backend returned unexpected response for rotation: {response_data}")
                    # Decide how critical backend notification is. Re-raise the original error.
                    raise # Re-raise the original caught exception (e)

            except (exceptions.ApiError, ValueError, requests.exceptions.RequestException) as e:
                 logger.error(f"Backend notification failed for agent {agent_id}: {e}")
                 audit_logger.log_credential_rotation_failed(agent_id=agent_id, credential_type=credential_type, reason=f"Backend notification error: {e}")
                 # Decide how critical backend notification is. Re-raise the original error.
                 raise # Re-raise the original caught exception (e)

        elif not local_only:
             logger.warning("Backend not configured (URL or Token missing). Cannot notify backend of rotation.")
             # Should we raise an error here if backend sync is expected?
             # For now, proceed with local rotation complete status, but log warning.

        # --- Log Final Rotation Event --- #
        audit_logger.log_credential_rotation(
            agent_id=agent_id,
            credential_type=credential_type,
            new_credential_ref=f"key_rotated_{rotated_at_ts}", # Use timestamp var
            rotated_by="local_user",
            backend_notified=backend_notified
        )

        return {
            "agent_id": agent_id,
            "status": "Local rotation complete",
            "backend_notified": backend_notified
        }

    # --- Local Verification --- #

    def verify_local_credential(self, credential: Dict[str, Any]) -> bool:
        """Verifies a credential locally against stored identity and revocation list.
        
        Performs checks for:
        - Signature validity against the agent's known public key.
        - Expiration time.
        - Presence in the local revocation list.
        - Origin context match (if origin binding was used).
        
        Args:
            credential: The full credential dictionary (as returned by issue_credential,
                        minus the ephemeral_private_key).
        
        Returns:
            True if the credential is valid locally, False otherwise.
            
        Raises:
            VaultError: If the agent identity cannot be found or loaded.
            ValueError: If the credential format is invalid.
        """
        if not all(k in credential for k in ["credential_id", "agent_id", "ephemeral_public_key", "signature", "expires_at"]):
            raise ValueError("Credential dictionary is missing required fields.")

        cred_id = credential["credential_id"]
        agent_id = credential["agent_id"]
        ephemeral_pub_key = credential["ephemeral_public_key"]
        signature = credential["signature"]
        expires_at = credential["expires_at"]
        origin_context_issued = credential.get("origin_context", {})

        # 1. Check Revocation List
        if self.is_revoked(cred_id):
            print(f"[Verification Failed] Credential {cred_id} is revoked.", file=sys.stderr)
            return False

        # 2. Check Expiry
        if time.time() > expires_at:
            print(f"[Verification Failed] Credential {cred_id} has expired.", file=sys.stderr)
            return False

        # 3. Get Agent Identity Public Key
        try:
            agent_identity = self._client._identity_manager.get_identity(agent_id)
            identity_public_key = agent_identity.public_key_b64 if agent_identity else None
            if not identity_public_key:
                raise exceptions.VaultError(f"No public key found for agent {agent_id}")
        except exceptions.VaultError as e:
            print(f"[Verification Failed] Could not load identity for agent {agent_id}: {e}", file=sys.stderr)
            return False # Cannot verify signature without public key

        # 4. Verify Signature
        # TODO: Adapt if/when context-bound signing is fully implemented
        #       Need to reconstruct the exact message that was signed.
        is_signature_valid = self.key_manager.verify_signature(
            ephemeral_public_key=ephemeral_pub_key,
            signature=signature,
            identity_public_key=identity_public_key
        )
        if not is_signature_valid:
            print(f"[Verification Failed] Invalid signature for credential {cred_id}.", file=sys.stderr)
            return False

        # 5. Check Origin Binding (if context exists in credential)
        if origin_context_issued: # Only check if binding was seemingly used
            current_context = self._capture_origin_context()
            # Basic check: Compare device IDs if both exist
            # TODO: Implement more sophisticated origin policy matching later.
            issued_device_id = origin_context_issued.get("device_id")
            current_device_id = current_context.get("device_id")
            if issued_device_id and current_device_id and issued_device_id != current_device_id:
                print(f"[Verification Failed] Origin context mismatch for {cred_id}. "
                      f"Issued: {issued_device_id}, Current: {current_device_id}", file=sys.stderr)
                return False
            # Add more context checks as needed (IP, hostname, etc.)

        # All checks passed
        return True

# The VaultClient is no longer a self-contained singleton.
# It will be instantiated and managed by the high-level DeepSecure client,
# which will provide it with a fully configured BaseClient.
# client = VaultClient(base_client.BaseClient()) 