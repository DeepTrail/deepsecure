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

from . import base_client
from .crypto.key_manager import key_manager
from .audit_logger import audit_logger
from .. import exceptions

class VaultClient(base_client.BaseClient):
    """Client for interacting with the Vault API for credential management."""
    
    def __init__(self):
        """Initialize the Vault client."""
        super().__init__("vault")
        self.key_manager = key_manager
        self.audit_logger = audit_logger
        self.identity_store_path = os.path.expanduser("~/.deepsecure/identities")
        os.makedirs(self.identity_store_path, exist_ok=True)
    
    def _get_agent_identity(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get or create an agent identity.
        
        Args:
            agent_id: Optional agent identifier to look up. If None, a new one is generated.
            
        Returns:
            Dictionary with agent identity details
        """
        if agent_id is None:
            # Generate a new random agent ID
            agent_id = f"agent-{uuid.uuid4()}"
        
        # Check if we have this identity stored
        identity_file = os.path.join(self.identity_store_path, f"{agent_id}.json")
        
        if os.path.exists(identity_file):
            # Load existing identity
            with open(identity_file, 'r') as f:
                identity = json.load(f)
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
            with open(identity_file, 'w') as f:
                json.dump(identity, f)
        
        return identity
    
    def _capture_origin_context(self) -> Dict[str, Any]:
        """
        Capture information about the credential issuance origin.
        
        Returns:
            Dictionary with origin context
        """
        context = {
            "hostname": socket.gethostname(),
            "username": os.getlogin(),
            "process_id": os.getpid(),
            "timestamp": int(time.time())
        }
        
        # Add IP address if we can get it
        try:
            context["ip_address"] = socket.gethostbyname(socket.gethostname())
        except:
            context["ip_address"] = "127.0.0.1"
        
        # Add device identifier
        context["device_id"] = self._get_device_identifier()
        
        return context
    
    def _get_device_identifier(self) -> str:
        """
        Get a unique identifier for the current device.
        
        Returns:
            String with device identifier
        """
        # In a real implementation, this would use hardware-specific information
        # For now, we'll use a combination of hostname and a stored UUID
        device_id_file = os.path.expanduser("~/.deepsecure/device_id")
        
        if os.path.exists(device_id_file):
            with open(device_id_file, 'r') as f:
                return f.read().strip()
        else:
            # Create a new device ID
            device_id = str(uuid.uuid4())
            os.makedirs(os.path.dirname(device_id_file), exist_ok=True)
            with open(device_id_file, 'w') as f:
                f.write(device_id)
            return device_id
    
    def _calculate_expiry(self, ttl: str) -> int:
        """
        Calculate expiry timestamp from TTL string.
        
        Args:
            ttl: Time-to-live string (e.g., "5m", "1h", "7d")
            
        Returns:
            Unix timestamp for expiry
            
        Raises:
            ValueError: If TTL format is invalid
        """
        ttl_pattern = re.compile(r'^(\d+)([smhdw])$')
        match = ttl_pattern.match(ttl)
        
        if not match:
            raise ValueError(f"Invalid TTL format: {ttl}. Expected format: <number><unit> (e.g., 5m, 1h, 7d)")
        
        value, unit = match.groups()
        value = int(value)
        
        now = datetime.now()
        
        if unit == 's':
            expiry = now + timedelta(seconds=value)
        elif unit == 'm':
            expiry = now + timedelta(minutes=value)
        elif unit == 'h':
            expiry = now + timedelta(hours=value)
        elif unit == 'd':
            expiry = now + timedelta(days=value)
        elif unit == 'w':
            expiry = now + timedelta(weeks=value)
        else:
            raise ValueError(f"Invalid TTL unit: {unit}")
        
        return int(expiry.timestamp())
    
    def _create_context_bound_message(self, ephemeral_public_key: str, 
                                     origin_context: Dict[str, Any]) -> bytes:
        """
        Create a context-bound message from the ephemeral key and origin context.
        
        Args:
            ephemeral_public_key: Base64-encoded ephemeral public key
            origin_context: Dictionary with origin context
            
        Returns:
            Bytes object with the message to sign
        """
        # Serialize the context with the ephemeral key
        context_data = {
            "ephemeral_public_key": ephemeral_public_key,
            "origin_context": origin_context
        }
        
        # Create a deterministic serialization
        serialized_data = json.dumps(context_data, sort_keys=True).encode('utf-8')
        
        # Hash the data to create a fixed-length message
        return hashlib.sha256(serialized_data).digest()
    
    def _create_credential(self, agent_id: str, ephemeral_public_key: str,
                          signature: str, scope: str, expiry: int,
                          origin_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a credential token.
        
        Args:
            agent_id: Agent identifier
            ephemeral_public_key: Base64-encoded ephemeral public key
            signature: Base64-encoded signature
            scope: Credential scope
            expiry: Expiration timestamp
            origin_context: Dictionary with origin context
            
        Returns:
            Dictionary with credential details
        """
        credential_id = f"cred-{uuid.uuid4()}"
        
        credential = {
            "id": credential_id,
            "agent_id": agent_id,
            "ephemeral_public_key": ephemeral_public_key,
            "signature": signature,
            "scope": scope,
            "issued_at": int(time.time()),
            "expires_at": expiry,
            "origin_context": origin_context
        }
        
        return credential
    
    def issue_credential(self, scope: str, ttl: str, agent_id: Optional[str] = None,
                        origin_context: Optional[Dict[str, Any]] = None,
                        origin_binding: bool = True) -> Dict[str, Any]:
        """
        Issue an ephemeral credential with the specified scope and TTL.
        
        Args:
            scope: Scope of access (e.g., 'db:readonly', 'api:full')
            ttl: Time-to-live for the credential (e.g., '5m', '1h')
            agent_id: Optional agent identifier (generated if not provided)
            origin_context: Optional origin context for origin binding
            origin_binding: Whether to enforce origin binding
            
        Returns:
            Dictionary with credential details
        """
        # 1. Get or create agent identity
        agent_identity = self._get_agent_identity(agent_id)
        
        # 2. Get origin context if needed
        if origin_binding and not origin_context:
            origin_context = self._capture_origin_context()
        elif not origin_binding:
            origin_context = {}
        
        # 3. Generate ephemeral keypair
        ephemeral_keys = self.key_manager.generate_ephemeral_keypair()
        
        # 4. Sign the ephemeral public key (with or without origin binding)
        if origin_binding:
            # Create a context-bound message to sign
            context_message = self._create_context_bound_message(
                ephemeral_keys["public_key"], 
                origin_context
            )
            # Sign the context message
            signature = self.key_manager.sign_ephemeral_key(
                ephemeral_keys["public_key"], 
                agent_identity["private_key"]
            )
        else:
            # Sign just the ephemeral key
            signature = self.key_manager.sign_ephemeral_key(
                ephemeral_keys["public_key"], 
                agent_identity["private_key"]
            )
        
        # 5. Calculate expiry
        expiry = self._calculate_expiry(ttl)
        
        # 6. Create the credential
        credential = self._create_credential(
            agent_identity["id"],
            ephemeral_keys["public_key"],
            signature,
            scope,
            expiry,
            origin_context
        )
        
        # Add private key to the returned credential (wouldn't be stored in real system)
        credential["ephemeral_private_key"] = ephemeral_keys["private_key"]
        
        # 7. Log the issuance
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
        
        Args:
            credential_id: ID of the credential to revoke
            
        Returns:
            True if successful, False otherwise
        """
        # In a real implementation, this would make an API call to revoke the credential
        print(f"[DEBUG] Would revoke credential with id={credential_id}")
        
        # Log the revocation
        self.audit_logger.log_credential_revocation(
            credential_id=credential_id,
            revoked_by="user"  # This would be the current user or system
        )
        
        return True
    
    def rotate_credential(self, credential_type: str, config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Rotate a credential of the specified type.
        
        Args:
            credential_type: Type of credential to rotate
            config_path: Optional path to configuration file
            
        Returns:
            Dictionary with new credential details
        """
        # Placeholder implementation
        print(f"[DEBUG] Would rotate credential of type={credential_type}, config_path={config_path}")
        
        return {
            "id": f"cred-{uuid.uuid4()}",
            "type": credential_type,
            "rotated_at": int(time.time())
        }

# Singleton instance
client = VaultClient() 