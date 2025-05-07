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

from . import base_client
from .crypto.key_manager import key_manager
from .audit_logger import audit_logger
from .. import exceptions

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
    
    def __init__(self):
        """Initialize the Vault client.

        Sets up the service name for the base client, initializes dependencies
        like the key manager and audit logger, ensures local storage directories
        exist, and loads the local revocation list.
        """
        super().__init__()
        self.key_manager = key_manager
        self.audit_logger = audit_logger
        self.identity_store_path = IDENTITY_STORE_PATH
        self.revocation_list_file = REVOCATION_LIST_FILE
        
        # Ensure directories exist
        DEEPSECURE_DIR.mkdir(exist_ok=True)
        self.identity_store_path.mkdir(exist_ok=True)
        
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
    
    def _get_agent_identity(self, agent_id: Optional[str] = None) -> (Dict[str, Any], bool):
        """
        Get or create an agent identity, storing it locally.

        If agent_id is provided, it attempts to load the identity from a local
        JSON file. If not found or agent_id is None, it generates a new identity
        (including an Ed25519 key pair) and saves it.

        Args:
            agent_id: Optional specific agent identifier to look up or create.
                      If None, a new UUID-based ID is generated.

        Returns:
            A tuple containing:
                - A dictionary with the agent's identity details:
                  {'id': str, 'created_at': int, 'private_key': str, 'public_key': str}
                - A boolean, True if the identity was newly created, False otherwise.
        """
        was_newly_created = False # Flag to track if new identity is made
        if agent_id is None:
            # Generate a new random agent ID
            agent_id = f"agent-{uuid.uuid4()}"
            # If agent_id was None, it implies we intend to create a new one,
            # but we still check existence below in case of a collision or manual file placement.
        
        # Check if we have this identity stored
        identity_file = self.identity_store_path / f"{agent_id}.json"
        
        if identity_file.exists():
            # Load existing identity
            try:
                with open(identity_file, 'r') as f:
                    identity = json.load(f)
                    # TODO: Add validation for the loaded identity structure.
            except (json.JSONDecodeError, IOError) as e:
                raise exceptions.VaultError(f"Failed to load identity for {agent_id}: {e}") from e
        else:
            # Create a new identity
            was_newly_created = True # Set flag
            keys = self.key_manager.generate_identity_keypair()
            
            identity = {
                "id": agent_id,
                "created_at": int(time.time()),
                "private_key": keys["private_key"],
                "public_key": keys["public_key"]
            }
            
            # Store the identity
            try:
                with open(identity_file, 'w') as f:
                    json.dump(identity, f)
                identity_file.chmod(0o600) # Restrict permissions
            except IOError as e:
                raise exceptions.VaultError(f"Failed to save identity for {agent_id}: {e}") from e
        
        return identity, was_newly_created # Return flag along with identity
    
    def _register_agent_with_backend(self, agent_id: str, public_key_b64: str) -> bool:
        """Register a new agent with the backend service."""
        if not (self.backend_url and self.backend_api_token):
            logger.warning("Backend not configured. Cannot register agent with backend.")
            return False

        logger.info(f"Attempting to register new agent {agent_id} with backend.")
        payload = {
            "agent_id": agent_id,
            "current_public_key": public_key_b64 
        }
        try:
            response_data = self._request(
                "POST",
                "/api/v1/agents",
                data=payload,
                is_backend_request=True
            )
            logger.info(f"Successfully registered agent {agent_id} with backend. Response: {response_data}")
            return True
        except exceptions.ApiError as e:
            logger.error(f"Failed to register agent {agent_id} with backend: {e}", exc_info=True)
            if e.status_code == 409: # HTTP 409 Conflict
                logger.warning(f"Agent {agent_id} already exists on backend or conflict occurred. Proceeding as if registered.")
                return True 
            return False
        except Exception as e:
            logger.error(f"Unexpected error registering agent {agent_id} with backend: {e}", exc_info=True)
            return False

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
    
    def issue_credential(self, scope: str, ttl: str, agent_id: Optional[str] = None,
                        origin_context: Optional[Dict[str, Any]] = None,
                        origin_binding: bool = True,
                        local_only: bool = False) -> Dict[str, Any]:
        """
        Issue an ephemeral credential.

        If `local_only` is True, performs all generation and signing locally.
        If `local_only` is False (default), attempts to issue via the backend.

        Args:
            scope: Scope of access (e.g., 'db:readonly', 'api:full').
            ttl: Time-to-live string (e.g., '5m', '1h'). **Backend expects seconds (int)**.
            agent_id: Optional agent identifier. If None, a new identity is created.
            origin_context: Optional pre-captured origin context.
            origin_binding: If True, capture/use origin context.
            local_only: If True, force local generation.

        Returns:
            A dictionary representing the issued credential, including the ephemeral
            private key (whether issued locally or via backend).

        Raises:
            ValueError: If the TTL format is invalid or backend URL/token missing.
            VaultError: If identity loading/saving fails.
            ApiError: If backend communication fails.
        """
        # 1. Get or create agent identity (needed for both local and backend)
        agent_identity, was_newly_created = self._get_agent_identity(agent_id)
        current_agent_id = agent_identity['id']
        current_public_key_b64 = agent_identity['public_key'] # Get public key for registration

        # --- Attempt Agent Registration if New and Backend Mode ---
        if was_newly_created and not local_only and self.backend_url and self.backend_api_token:
            logger.info(f"New agent {current_agent_id} created locally, attempting backend registration.")
            # Pass the Ed25519 public key for registration
            registration_successful = self._register_agent_with_backend(current_agent_id, current_public_key_b64)
            if not registration_successful:
                # If registration fails, log a warning and fall back to local issuance behavior.
                # This maintains the ability to issue credentials even if backend registration has an issue,
                # though such credentials won't be verifiable by a backend that doesn't know the agent.
                logger.warning(
                    f"Backend registration for new agent {current_agent_id} failed. Proceeding with local issuance, but this agent may not be known to the backend."
                )
                # To strictly enforce backend registration, you might choose to raise an error here instead.
                # For now, we allow fallback to local to ensure CLI can still issue something.
                local_only = True # Force local issuance if registration failed

        # 2. Generate ephemeral keypair (X25519) (needed for both)
        ephemeral_keys = self.key_manager.generate_ephemeral_keypair()
        ephemeral_public_key_b64 = ephemeral_keys["public_key"]
        ephemeral_private_key_b64 = ephemeral_keys["private_key"] # Keep this safe!

        # 3. Sign the ephemeral public key (with Ed25519 identity key) (needed for both)
        signature_b64 = self.key_manager.sign_ephemeral_key(
            ephemeral_public_key_b64,
            agent_identity["private_key"]
        )

        # 4. Get origin context if needed (needed for both, potentially)
        captured_context = {}
        if origin_binding:
            captured_context = origin_context if origin_context is not None else self._capture_origin_context()

        # 5. Parse TTL (needed for backend) - Backend expects integer seconds
        try:
            # Use _calculate_expiry logic to get timedelta, then total seconds
            ttl_pattern = re.compile(r'^(\d+)([smhdw])$')
            match = ttl_pattern.match(ttl)
            if not match:
                raise ValueError(f"Invalid TTL format: {ttl}.")
            value, unit = match.groups()
            value = int(value)
            delta = None
            if unit == 's': delta = timedelta(seconds=value)
            elif unit == 'm': delta = timedelta(minutes=value)
            elif unit == 'h': delta = timedelta(hours=value)
            elif unit == 'd': delta = timedelta(days=value)
            elif unit == 'w': delta = timedelta(weeks=value)
            if delta is None: raise ValueError(f"Invalid TTL unit: {unit}")
            ttl_seconds = int(delta.total_seconds())
            if ttl_seconds <= 0: raise ValueError("TTL must be positive.")
        except ValueError as e:
             audit_logger.log_credential_issuance_failed(agent_id=current_agent_id, scope=scope, reason=f"Invalid TTL: {e}")
             raise

        # --- Attempt Backend Issuance ---
        if not local_only and self.backend_url and self.backend_api_token:
            logger.info(f"Attempting backend credential issuance for agent {current_agent_id}")
            try:
                payload = {
                    "agent_id": current_agent_id,
                    "ephemeral_public_key": ephemeral_public_key_b64,
                    "signature": signature_b64,
                    "ttl": ttl_seconds,
                    "scope": scope,
                    "origin_context": captured_context if origin_binding else None,
                }
                # Remove None values from payload
                payload = {k: v for k, v in payload.items() if v is not None}

                response_data = self._request(
                    "POST",
                    "/api/v1/vault/credentials", # Match backend route
                    data=payload,
                    is_backend_request=True
                )

                # Backend returns: agent_id, scope, credential_id, ephemeral_public_key, expires_at
                # We need to add the ephemeral_private_key back for the caller
                issued_credential = response_data # Assume response is the credential dict directly
                issued_credential["ephemeral_private_key"] = ephemeral_private_key_b64

                # Log success
                audit_logger.log_credential_issuance(
                    credential_id=issued_credential["credential_id"],
                    agent_id=current_agent_id,
                    scope=scope,
                    ttl=ttl, # Log original TTL string
                    backend_issued=True
                )
                logger.info(f"Successfully issued credential {issued_credential['credential_id']} via backend.")
                return issued_credential

            except (exceptions.ApiError, ValueError, requests.exceptions.RequestException) as e:
                logger.warning(f"Backend issuance failed: {e}. Falling back to local issuance.", exc_info=True)
                audit_logger.log_credential_issuance_failed(agent_id=current_agent_id, scope=scope, reason=f"Backend error: {e}")
                # Fall through to local issuance
        elif not local_only:
             logger.warning("Backend not configured (URL or Token missing). Performing local issuance.")


        # --- Local Issuance Flow --- #
        logger.info(f"Performing local credential issuance for agent {current_agent_id}")

        # Calculate expiry timestamp (already have delta from TTL parsing)
        now_ts = int(time.time())
        expiry_ts = now_ts + ttl_seconds

        # Create the final credential structure locally
        credential = self._create_credential(
            current_agent_id,
            ephemeral_public_key_b64,
            signature_b64,
            scope,
            expiry_ts,
            captured_context
        )

        # Add ephemeral private key
        credential["ephemeral_private_key"] = ephemeral_private_key_b64

        # Log the local issuance event
        audit_logger.log_credential_issuance(
            credential_id=credential["credential_id"],
            agent_id=current_agent_id,
            scope=scope,
            ttl=ttl, # Log original TTL string
            backend_issued=False
        )

        return credential
    
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
        if not local_only and self.backend_url and self.backend_api_token:
            logger.info(f"Attempting backend revocation for id={credential_id}")
            try:
                # Backend endpoint is POST /api/v1/vault/credentials/{credential_id}/revoke
                response_data = self._request(
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
        identity_file = self.identity_store_path / f"{agent_id}.json"
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
        if not local_only and self.backend_url and self.backend_api_token:
            logger.info(f"Attempting backend notification for key rotation: agent={agent_id}")
            try:
                payload = {
                    # Backend expects key bytes encoded in base64 in the request
                    "new_public_key": new_public_key_b64
                }
                response_data = self._request(
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
            agent_identity, _ = self._get_agent_identity(agent_id)
            identity_public_key = agent_identity["public_key"]
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


# Singleton instance of the client for easy import and use.
client = VaultClient() 