# deepsecure/core/identity_manager.py
import os
import json
import time
import uuid
import hashlib
import base64
from pathlib import Path
from typing import Dict, Any, Optional, List
import sys

import keyring # Import the keyring library
# Make sure to handle potential import errors for keyring itself if it's optional
# For now, assume it's a hard dependency for secure storage.
from keyring.errors import NoKeyringError, PasswordDeleteError, PasswordSetError

# Import the key_manager instance directly
from .crypto.key_manager import key_manager 
from .. import utils 
from ..exceptions import DeepSecureClientError, IdentityManagerError
from cryptography.hazmat.primitives.asymmetric import ed25519

# Helper to generate the dynamic service name for an agent's private key in the keyring
def _get_keyring_service_name_for_agent(agent_id: str) -> str:
    if not agent_id.startswith("agent-"):
        # Fallback or raise error for unexpected agent_id format
        # For now, use a generic one if format is off, but ideally, format should always be correct.
        # Or, this could be a point of failure if agent_id is malformed.
        # Let's make it strict for now.
        raise ValueError(f"Agent ID '{agent_id}' does not follow the expected 'agent-<uuid>' format.")
    parts = agent_id.split('-')
    if len(parts) < 2:
        raise ValueError(f"Agent ID '{agent_id}' does not contain a UUID part after 'agent-'.")
    prefix = parts[1] # Get the first part of the UUID
    return f"deepsecure_agent-{prefix}_private_key"

class IdentityManager:
    """
    Simplified Identity Manager for Backend-Only Architecture.
    
    This new architecture eliminates local JSON metadata storage and relies solely on:
    1. Backend for all agent metadata (public keys, names, creation times, etc.)
    2. Keychain for private keys only
    
    Benefits:
    - Single source of truth (backend)
    - No synchronization issues between local and backend state
    - Simplified cleanup (just sync keychain with backend)
    - No orphaned JSON files
    """
    
    def __init__(self, silent_mode: bool = False):
        self.silent_mode = silent_mode
        self.key_manager = key_manager
        
        # Note: We no longer create or use local identity directories
        # All metadata comes from the backend
        
    def _generate_agent_id(self) -> str:
        """Generate a new agent ID."""
        return f"agent-{uuid.uuid4()}"

    def generate_ed25519_keypair_raw_b64(self) -> Dict[str, str]:
        """
        Generates a new Ed25519 key pair.
        Returns: Dict with "private_key" and "public_key" (base64-encoded raw bytes).
        """
        return self.key_manager.generate_identity_keypair()

    def get_public_key_fingerprint(self, public_key_b64: str) -> str:
        """Generate a fingerprint for the given public key."""
        try:
            public_key_bytes = base64.b64decode(public_key_b64)
            fingerprint = hashlib.sha256(public_key_bytes).hexdigest()
            return f"sha256:{fingerprint[:64]}"
        except Exception as e:
            raise IdentityManagerError(f"Failed to generate fingerprint: {e}")

    def decode_private_key(self, private_key_b64: str):
        """Decode a base64-encoded private key for cryptographic operations."""
        try:
            private_key_bytes = base64.b64decode(private_key_b64)
            return ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        except Exception as e:
            raise IdentityManagerError(f"Failed to decode private key: {e}")

    def create_keypair_for_agent(self, agent_id: str) -> Dict[str, str]:
        """
        Creates and stores a new keypair for the given agent ID.
        Only stores the private key in keychain - no local metadata files.
        
        Returns: Dict with public_key, private_key, and public_key_fingerprint
        """
        # Generate new keypair
        keys = self.generate_ed25519_keypair_raw_b64()
        public_key_b64 = keys["public_key"]
        private_key_b64 = keys["private_key"]
        
        # Store private key in keychain
        keyring_service_name = _get_keyring_service_name_for_agent(agent_id)
        
        try:
            keyring.set_password(keyring_service_name, agent_id, private_key_b64)
            if not self.silent_mode:
                utils.console.print(f"[IdentityManager] Private key for agent [cyan]{agent_id}[/cyan] securely stored in system keyring (Service: '{keyring_service_name}').", style="green")
        except NoKeyringError:
            msg = (f"CRITICAL SECURITY RISK: No system keyring backend found. "
                   f"Private key for agent {agent_id} cannot be stored securely. "
                   f"Aborting keypair creation. Please install and configure a keyring backend.")
            if not self.silent_mode:
                utils.console.print(f"[IdentityManager] {msg}", style="bold red")
            raise IdentityManagerError(msg)
        except PasswordSetError as pse:
            msg = f"Failed to store private key in keyring for agent {agent_id} (PasswordSetError): {pse}. Check keyring access and permissions."
            if not self.silent_mode: 
                utils.console.print(f"[IdentityManager] {msg}", style="bold red")
            raise IdentityManagerError(msg) from pse
        except Exception as e:
            msg = f"An unexpected error occurred while storing private key in keyring for agent {agent_id}: {e}"
            if not self.silent_mode: 
                utils.console.print(f"[IdentityManager] {msg}", style="bold red")
            raise IdentityManagerError(msg) from e

        # Generate fingerprint
        try:
            public_key_fingerprint = self.get_public_key_fingerprint(public_key_b64)
        except IdentityManagerError as e:
            if not self.silent_mode:
                utils.console.print(f"[IdentityManager] Warning: Could not generate fingerprint for new keypair {agent_id}: {e}", style="yellow")
            public_key_fingerprint = "Error/Unavailable"
        
        return {
            "public_key": public_key_b64,
            "private_key": private_key_b64,
            "public_key_fingerprint": public_key_fingerprint
        }

    def get_private_key(self, agent_id: str) -> Optional[str]:
        """
        Retrieves the private key for an agent from the keychain.
        Returns None if not found.
        """
        keyring_service_name = _get_keyring_service_name_for_agent(agent_id)
        
        try:
            retrieved_private_key = keyring.get_password(keyring_service_name, agent_id)
            if retrieved_private_key:
                if not self.silent_mode: 
                    utils.console.print(f"[IdentityManager] Successfully retrieved private key for agent {agent_id} from system keyring (Service: '{keyring_service_name}').", style="dim")
                return retrieved_private_key
            else:
                if not self.silent_mode: 
                    utils.console.print(f"[IdentityManager] Private key for agent [yellow]{agent_id}[/yellow] was NOT FOUND in the system keyring (Service: '{keyring_service_name}').", style="bold yellow")
                return None
        except NoKeyringError:
            if not self.silent_mode: 
                utils.console.print(f"[IdentityManager] WARNING: No system keyring backend found when trying to load private key for agent [yellow]{agent_id}[/yellow] (Service: '{keyring_service_name}').", style="bold yellow")
            return None
        except Exception as e:
            if not self.silent_mode: 
                utils.console.print(f"[IdentityManager] WARNING: An unexpected error occurred while trying to retrieve private key from keyring for agent [yellow]{agent_id}[/yellow] (Service: '{keyring_service_name}'): {e}", style="bold yellow")
            return None

    def delete_private_key(self, agent_id: str) -> bool:
        """
        Deletes the private key for an agent from the keychain.
        Returns True if successful or key didn't exist, False on error.
        """
        keyring_service_name = _get_keyring_service_name_for_agent(agent_id)
        
        try:
            keyring.delete_password(keyring_service_name, agent_id)
            if not self.silent_mode: 
                utils.console.print(f"[IdentityManager] Deleted private key for agent {agent_id} from system keyring (Service: '{keyring_service_name}').", style="dim")
            return True
        except PasswordDeleteError: 
            if not self.silent_mode: 
                utils.console.print(f"[IdentityManager] Private key for agent {agent_id} not found in system keyring (Service: '{keyring_service_name}') (considered success for deletion).", style="dim")
            return True
        except NoKeyringError:
            if not self.silent_mode: 
                utils.console.print(f"[IdentityManager] Warning: No system keyring backend. Cannot delete private key for agent {agent_id} from keyring (Service: '{keyring_service_name}').", style="bold yellow")
            return False
        except Exception as e:
            if not self.silent_mode: 
                utils.console.print(f"[IdentityManager] Error deleting private key from keyring for agent {agent_id} (Service: '{keyring_service_name}'): {e}", style="red")
            return False

    def get_all_keychain_agent_ids(self) -> List[str]:
        """
        Discovers all agent IDs that have private keys stored in the keychain.
        
        Since macOS doesn't provide a list API, this uses a discovery approach
        by checking known patterns against the backend agent list.
        """
        # This method will be used by the cleanup functionality
        # For now, return empty list - will be implemented in cleanup logic
        return []

    def cleanup_orphaned_keychain_entries(self, valid_agent_ids: List[str], confirm: bool = True) -> int:
        """
        Removes keychain entries for agents not in the valid_agent_ids list.
        
        Args:
            valid_agent_ids: List of agent IDs that should be preserved
            confirm: Whether to ask for confirmation before deletion
            
        Returns:
            Number of entries deleted
        """
        # This will be implemented as part of the cleanup command enhancement
        # For now, return 0
        return 0

    # Additional utility methods for the new architecture
    
    def store_private_key_directly(self, agent_id: str, private_key_b64: str) -> None:
        """
        Directly store a private key in the keychain for a given agent ID.
        Used when you have a private key from external source (e.g., backend registration).
        """
        keyring_service_name = _get_keyring_service_name_for_agent(agent_id)
        try:
            keyring.set_password(keyring_service_name, agent_id, private_key_b64)
            if not self.silent_mode: 
                utils.console.print(f"[IdentityManager] Private key for agent [cyan]{agent_id}[/cyan] stored in system keyring (Service: '{keyring_service_name}').", style="green")
        except NoKeyringError:
            msg = (f"CRITICAL SECURITY RISK: No system keyring backend found. "
                   f"Private key for agent {agent_id} cannot be stored securely. "
                   f"Aborting key storage. Please install and configure a keyring backend.")
            if not self.silent_mode:
                utils.console.print(f"[IdentityManager] {msg}", style="bold red")
            raise IdentityManagerError(msg)
        except PasswordSetError as pse:
            msg = f"Failed to store private key in keyring for agent {agent_id} (PasswordSetError): {pse}. Check keyring access and permissions."
            if not self.silent_mode: 
                utils.console.print(f"[IdentityManager] {msg}", style="bold red")
            raise IdentityManagerError(msg) from pse
        except Exception as e:
            msg = f"An unexpected error occurred while storing private key in keyring for agent {agent_id}: {e}"
            if not self.silent_mode: 
                utils.console.print(f"[IdentityManager] {msg}", style="bold red")
            raise IdentityManagerError(msg) from e

# Singleton instance - this will be created with default settings
identity_manager = IdentityManager()

if __name__ == '__main__':
    # Basic test of the IdentityManager - New Architecture
    print("--- Testing IdentityManager (New Backend-Only Architecture) ---")
    
    im = IdentityManager()

    # Test keypair generation
    print("\n1. Generating keypair for test agent...")
    try:
        agent_id = "agent-12345678-1234-1234-1234-123456789abc"
        keypair = im.create_keypair_for_agent(agent_id)
        print(f"Generated keypair for {agent_id}")
        print(f"Public key fingerprint: {keypair['public_key_fingerprint']}")

        # Test private key retrieval
        print(f"\n2. Retrieving private key for {agent_id}...")
        retrieved_key = im.get_private_key(agent_id)
        if retrieved_key:
            print(f"Successfully retrieved private key from keychain")
        else:
            print(f"Failed to retrieve private key")

        # Test private key deletion
        print(f"\n3. Deleting private key for {agent_id}...")
        if im.delete_private_key(agent_id):
            print(f"Successfully deleted private key")
        else:
            print(f"Failed to delete private key")
        
        # Verify deletion
        print(f"\n4. Verifying deletion...")
        if not im.get_private_key(agent_id):
            print(f"Private key no longer exists (as expected)")
        else:
            print(f"Error: Private key still exists after deletion")

    except IdentityManagerError as e:
        print(f"An IdentityManagerError occurred during testing: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during testing: {e}")

    print("\n--- IdentityManager Test Complete ---") 