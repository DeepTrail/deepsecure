'''Client for interacting with the Vault API for credential management.'''

import time
import socket
import os
import json
import uuid
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import re
import sys

from . import base_client
from .crypto.key_manager import key_manager
from .audit_logger import audit_logger
from .. import exceptions

class VaultClient(base_client.BaseClient):
    """Client for interacting with the Vault API for credential management.

    Handles agent identity management (local file-based for now), ephemeral
    key generation, credential signing, origin context capture, and interaction
    with the audit logger and cryptographic key manager.
    """
    
    def __init__(self):
        """Initialize the Vault client.

        Sets up the service name for the base client, initializes dependencies
        like the key manager and audit logger, and ensures the local identity
        storage directory exists.
        """
        super().__init__("vault")
        self.key_manager = key_manager
        self.audit_logger = audit_logger
        # TODO: Replace simple file-based identity storage with a more secure mechanism.
        self.identity_store_path = os.path.expanduser("~/.deepsecure/identities")
        os.makedirs(self.identity_store_path, exist_ok=True)
    
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
        identity_file = os.path.join(self.identity_store_path, f"{agent_id}.json")
        
        if os.path.exists(identity_file):
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
                os.chmod(identity_file, 0o600) # Restrict permissions
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
        device_id_file = os.path.expanduser("~/.deepsecure/device_id")
        
        if os.path.exists(device_id_file):
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
            os.makedirs(os.path.dirname(device_id_file), exist_ok=True)
            with open(device_id_file, 'w') as f:
                f.write(device_id)
            os.chmod(device_id_file, 0o600) # Restrict permissions
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
    
    def issue_credential(self, scope: str, ttl: str, agent_id: Optional[str] = None,
                        origin_context: Optional[Dict[str, Any]] = None,
                        origin_binding: bool = True) -> Dict[str, Any]:
        """
        Issue an ephemeral credential, optionally binding it to the origin context.

        This is the main method for credential issuance. It coordinates getting agent
        identity, capturing origin context (if needed), generating keys, signing,
        calculating expiry, creating the final credential structure, and logging.

        Args:
            scope: Scope of access (e.g., 'db:readonly', 'api:full').
            ttl: Time-to-live for the credential (e.g., '5m', '1h').
            agent_id: Optional agent identifier. If None, a new identity is created.
            origin_context: Optional pre-captured origin context. If None and origin_binding
                            is True, context will be captured automatically.
            origin_binding: If True, capture origin context and include it in the process
                            (intended to be part of the signature eventually).

        Returns:
            A dictionary representing the issued credential, including the ephemeral
            private key (which should NOT be stored or transmitted long-term).

        Raises:
            ValueError: If the TTL format is invalid.
            VaultError: If identity loading/saving fails.
        """
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
        # Currently, it signs only the key regardless of origin_binding flag,
        # although the context is captured and included in the token.
        # The _create_context_bound_message helper exists but isn't used for signing.
        # signature_payload = self._create_context_bound_message(...) if origin_binding else base64.b64decode(ephemeral_keys["public_key"])
        # signature = self.key_manager.sign(signature_payload, agent_identity["private_key"]) 
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
            captured_context # Pass the captured context (empty if origin_binding=False)
        )
        
        # Add ephemeral private key to the returned credential for immediate use by the caller.
        # WARNING: This private key should be handled securely by the caller and
        #          discarded after establishing the secure channel. It MUST NOT be stored
        #          persistently with the credential token itself.
        credential["ephemeral_private_key"] = ephemeral_keys["private_key"]
        
        # 7. Log the issuance event
        self.audit_logger.log_credential_issuance(
            credential_id=credential["id"],
            agent_id=agent_identity["id"],
            scope=scope,
            ttl=ttl
        )
        
        return credential
    
    def revoke_credential(self, credential_id: str) -> bool:
        """
        Revoke a credential by its ID.

        Currently, this is a placeholder. In a real implementation, it would
        interact with a backend service (e.g., an API endpoint or a revocation list)
        to mark the credential as invalid.

        Args:
            credential_id: The ID of the credential to revoke.

        Returns:
            True if the (placeholder) revocation was successful, False otherwise.
        """
        # TODO: Implement actual revocation logic (e.g., call backend API).
        # This requires a backend system to track issued credentials.
        print(f"[DEBUG] Would revoke credential with id={credential_id}")
        
        # Log the revocation event
        # TODO: Determine the actual source of revocation (e.g., user ID from context).
        self.audit_logger.log_credential_revocation(
            credential_id=credential_id,
            revoked_by="user" # Placeholder
        )
        
        return True # Placeholder success
    
    def rotate_credential(self, credential_type: str, config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Rotate a long-lived credential (Placeholder).

        This functionality is not fully defined or implemented for ephemeral credentials.
        It might apply to rotating the agent's long-term identity key.

        Args:
            credential_type: The type of credential to rotate.
            config_path: Optional path to a configuration file containing the credential.

        Returns:
            A dictionary with placeholder details about the rotation.
        """
        # TODO: Define and implement credential rotation, likely for the agent's long-term identity key.
        print(f"[DEBUG] Would rotate credential of type={credential_type}, config_path={config_path}")
        
        # Placeholder response
        return {
            "id": f"cred-{uuid.uuid4()}", # Placeholder ID
            "type": credential_type,
            "rotated_at": int(time.time())
        }

# Singleton instance of the client for easy import and use.
client = VaultClient() 