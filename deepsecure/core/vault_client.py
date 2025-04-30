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

from . import base_client
from .crypto.key_manager import key_manager
from .audit_logger import audit_logger
from .. import exceptions

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
        super().__init__("vault")
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
    
    def _get_agent_identity(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get or create an agent identity, storing it locally.

        If agent_id is provided, it attempts to load the identity from a local
        JSON file. If not found or agent_id is None, it generates a new identity
        (including an Ed25519 key pair) and saves it.

        Args:
            agent_id: Optional specific agent identifier to look up or create.
                      If None, a new UUID-based ID is generated.

        Returns:
            A dictionary containing the agent's identity details:
            {'id': str, 'created_at': int, 'private_key': str, 'public_key': str}
        """
        if agent_id is None:
            # Generate a new random agent ID
            agent_id = f"agent-{uuid.uuid4()}"
        
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
        
        return identity
    
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
            "id": credential_id,
            "agent_id": agent_id,
            "ephemeral_public_key": ephemeral_public_key,
            "signature": signature,
            "scope": scope,
            "issued_at": int(time.time()),
            "expires_at": expiry,
            "origin_context": origin_context # Empty if origin_binding=False
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
        If `local_only` is False (default), attempts to issue via the backend (placeholder).

        Args:
            scope: Scope of access (e.g., 'db:readonly', 'api:full').
            ttl: Time-to-live for the credential (e.g., '5m', '1h').
            agent_id: Optional agent identifier. If None, a new identity is created.
            origin_context: Optional pre-captured origin context.
            origin_binding: If True, capture/use origin context.
            local_only: If True, force local generation even if backend exists.

        Returns:
            A dictionary representing the issued credential, including the ephemeral
            private key.

        Raises:
            ValueError: If the TTL format is invalid.
            VaultError: If identity loading/saving fails.
            ApiError: If backend communication fails (when implemented).
        """
        if not local_only:
            # --- Backend Issuance Attempt (Placeholder) --- #
            # TODO: Implement backend issuance logic.
            print(f"[DEBUG] (Placeholder) Would attempt backend issuance for scope={scope}, ttl={ttl}")
            try:
                # response = self._request("POST", "/issue", data={"scope": scope, ...})
                # return response["data"] # Assuming backend returns the credential dict
                # Simulate a failure for now to fall back to local
                raise exceptions.ApiError("Backend issuance not implemented")
            except exceptions.ApiError as e:
                # TODO: Decide on fallback behavior. For now, fall back to local if backend fails.
                print(f"[Warning] Backend issuance failed: {e}. Falling back to local issuance.", file=sys.stderr)
                pass # Continue with local issuance
            # If backend succeeded in the future, we would return here.
            # return backend_credential 

        # --- Local Issuance Flow --- #
        # print("[Debug] Performing local credential issuance.", file=sys.stderr) # Removed this line causing test failures
        
        # 1. Get or create agent identity
        agent_identity = self._get_agent_identity(agent_id)
        
        # 2. Get origin context if needed
        captured_context = {}
        if origin_binding:
            captured_context = origin_context if origin_context is not None else self._capture_origin_context()
        
        # 3. Generate ephemeral keypair (X25519)
        ephemeral_keys = self.key_manager.generate_ephemeral_keypair()
        
        # 4. Sign the ephemeral public key (with Ed25519 identity key)
        # TODO: Implement actual context-bound signing as planned.
        signature = self.key_manager.sign_ephemeral_key(
            ephemeral_keys["public_key"], 
            agent_identity["private_key"]
        )
        
        # 5. Calculate expiry timestamp
        expiry = self._calculate_expiry(ttl)
        
        # 6. Create the final credential structure
        credential = self._create_credential(
            agent_identity["id"],
            ephemeral_keys["public_key"],
            signature,
            scope,
            expiry,
            captured_context 
        )
        
        # Add ephemeral private key
        credential["ephemeral_private_key"] = ephemeral_keys["private_key"]
        
        # 7. Log the issuance event
        self.audit_logger.log_credential_issuance(
            credential_id=credential["id"],
            agent_id=agent_identity["id"],
            scope=scope,
            ttl=ttl
        )
        
        return credential
    
    def revoke_credential(self, credential_id: str, local_only: bool = False) -> bool:
        """
        Revoke a credential.

        If `local_only` is True, only adds the ID to the local revocation list.
        If `local_only` is False (default), it attempts backend revocation (placeholder)
        AND updates the local list.

        Args:
            credential_id: The ID of the credential to revoke.
            local_only: If True, skip backend interaction attempt.

        Returns:
            True if the credential was successfully added to the local list or
            if the backend call succeeded (in the future), False otherwise.
        """
        if not credential_id:
            print("[Warning] Attempted to revoke an empty credential ID.", file=sys.stderr)
            return False

        # --- Backend Revocation Attempt (Placeholder) --- # 
        backend_success = False
        if not local_only:
            # TODO: Implement actual backend revocation logic (e.g., call backend API).
            # This requires a backend system to track issued credentials.
            print(f"[DEBUG] (Placeholder) Would attempt backend revocation for id={credential_id}")
            # Simulate backend success for now if not local_only
            backend_success = True 
            # In a real implementation, check the actual result from the backend API call.
            # if not backend_api.revoke(credential_id):
            #     print(f"[Error] Backend revocation failed for {credential_id}", file=sys.stderr)
            #     # Decide if failure to revoke on backend should prevent local revocation
            #     # return False # Option 1: Fail entirely
            # else:
            #     backend_success = True

        # --- Local Revocation --- #
        local_update_needed = True
        if credential_id in self._revoked_ids:
            print(f"[Info] Credential {credential_id} is already revoked locally.", file=sys.stderr)
            local_update_needed = False # No need to add again
            # Even if already revoked locally, log the attempt again for audit trail
            self.audit_logger.log_credential_revocation(credential_id=credential_id, revoked_by="local_user") # Placeholder user
            # If backend succeeded OR we only care about local, return True
            return backend_success or local_only

        if local_update_needed:
            self._revoked_ids.add(credential_id)
            self._save_revocation_list()
            # print(f"[Debug] Credential {credential_id} added to local revocation list.", file=sys.stderr)

        # Log the event (only once if added locally)
        if local_update_needed:
             self.audit_logger.log_credential_revocation(
                credential_id=credential_id,
                revoked_by="local_user" # Placeholder for actual user context
            )

        # Return True if the backend call succeeded (if attempted) OR if it was local_only
        # AND the local list was updated (or already contained the ID).
        return backend_success or local_only
    
    def rotate_credential(self, credential_type: str, config_path: Optional[str] = None, local_only: bool = False) -> Dict[str, Any]:
        """
        Rotate a long-lived credential.

        If `local_only` is True, performs rotation locally (placeholder).
        If `local_only` is False (default), attempts backend rotation (placeholder).
        Currently, only local placeholder logic exists.

        Args:
            credential_type: The type of credential to rotate (e.g., "agent-identity").
            config_path: Optional path to a configuration file (usage TBD).
            local_only: If True, force local-only placeholder rotation.

        Returns:
            A dictionary with placeholder details about the rotation.
        """
        if not local_only:
            # --- Backend Rotation Attempt (Placeholder) --- #
            # TODO: Implement backend rotation logic.
            print(f"[DEBUG] (Placeholder) Would attempt backend rotation for type={credential_type}")
            try:
                # response = self._request("POST", "/rotate", data={"type": credential_type, ...})
                # return response["data"] # Assuming backend returns rotation details
                # Simulate a failure for now to fall back to local
                raise exceptions.ApiError("Backend rotation not implemented")
            except exceptions.ApiError as e:
                print(f"[Warning] Backend rotation failed: {e}. Falling back to local rotation (placeholder).", file=sys.stderr)
                pass # Continue with local placeholder
            # If backend succeeded in the future, we would return here.
            # return backend_rotation_details

        # --- Local Rotation Logic (Placeholder) --- #
        print(f"[DEBUG] Performing local rotation (placeholder) for type={credential_type}, config_path={config_path}")
        # TODO: Define and implement actual local rotation logic, 
        #       likely for the agent's long-term identity key stored locally.
        #       This would involve calling key_manager.generate_identity_keypair()
        #       and updating the stored identity file in ~/.deepsecure/identities/
        
        # Placeholder response
        new_id_ref = f"rotated-{credential_type}-{uuid.uuid4()}" # Placeholder ID/Ref
        rotation_time = int(time.time())
        
        # TODO: Log rotation event via audit_logger
        # self.audit_logger.log_credential_rotation(rotated_id=new_id_ref, type=credential_type)
        
        return {
            "id": new_id_ref, 
            "type": credential_type,
            "rotated_at": rotation_time
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
        if not all(k in credential for k in ["id", "agent_id", "ephemeral_public_key", "signature", "expires_at"]):
            raise ValueError("Credential dictionary is missing required fields.")

        cred_id = credential["id"]
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
            agent_identity = self._get_agent_identity(agent_id)
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