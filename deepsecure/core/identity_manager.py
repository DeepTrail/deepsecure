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

# Explicitly import the module and then the instance from it
from .crypto import key_manager as key_manager_module 
from .. import utils 
from ..exceptions import DeepSecureClientError, IdentityManagerError

# Define constants
_MODULE_DEEPSECURE_DIR = Path(os.path.expanduser("~/.deepsecure"))
_MODULE_IDENTITY_STORE_PATH = _MODULE_DEEPSECURE_DIR / "identities"
IDENTITY_FILE_MODE = 0o600
# KEYRING_SERVICE_NAME_AGENT_KEYS = "deepsecure-agent-keys" # Commented out or removed

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
    def __init__(self, deepsecure_dir_override: Optional[Path] = None, identity_store_path_override: Optional[Path] = None, silent_mode: bool = False):
        self.key_manager = key_manager_module.key_manager
        self.silent_mode = silent_mode
        
        self.deepsecure_dir = deepsecure_dir_override if deepsecure_dir_override is not None else _MODULE_DEEPSECURE_DIR
        self.identity_store_path = identity_store_path_override if identity_store_path_override is not None else (self.deepsecure_dir / "identities")
        
        # Ensure base directory and identity store directory exist using instance paths
        try:
            self.deepsecure_dir.mkdir(parents=True, exist_ok=True)
            self.identity_store_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            if not self.silent_mode:
                print(f"[IdentityManager __init__] CRITICAL: Failed to create required directories ({self.deepsecure_dir}, {self.identity_store_path}): {e}", file=sys.stderr)
            raise IdentityManagerError(f"Failed to create required directories: {e}")

    def _generate_agent_id(self) -> str:
        return f"agent-{uuid.uuid4()}"

    def generate_ed25519_keypair_raw_b64(self) -> Dict[str, str]:
        """
        Generates a new Ed25519 key pair.
        Returns: Dict with "private_key" and "public_key" (base64-encoded raw bytes).
        """
        return self.key_manager.generate_identity_keypair()

    def get_public_key_fingerprint(self, public_key_b64: str, hash_algo: str = "sha256") -> str:
        """
        Generates a fingerprint for a base64-encoded raw public key.
        Format: algo:hex_hash
        """
        try:
            key_bytes = base64.b64decode(public_key_b64)
            if len(key_bytes) != 32: # Ed25519 public keys are 32 bytes
                raise ValueError("Public key bytes must be 32 bytes long for fingerprinting.")
            hasher = hashlib.new(hash_algo)
            hasher.update(key_bytes)
            return f"{hash_algo}:{hasher.hexdigest()}"
        except ValueError as ve: # Catch our specific ValueError
            raise IdentityManagerError(f"Invalid public key for fingerprinting: {ve}")
        except Exception as e: # Catch base64 decode errors or hashlib errors
            raise IdentityManagerError(f"Failed to generate fingerprint for public key '{public_key_b64[:10]}...': {e}")

    def _save_identity_metadata_to_file(self, agent_id: str, identity_metadata: Dict[str, Any]):
        """Saves ONLY the public metadata of an identity to a JSON file."""
        identity_file = self.identity_store_path / f"{agent_id}.json"
        
        metadata_to_save = identity_metadata.copy()
        if "private_key" in metadata_to_save:
            if not self.silent_mode:
                utils.console.print(f"[IdentityManager] INTERNAL WARNING: _save_identity_metadata_to_file called with private_key for {agent_id}. It will be removed before saving to file.", style="bold orange_red1")
            del metadata_to_save["private_key"]
            
        try:
            with open(identity_file, 'w') as f:
                json.dump(metadata_to_save, f, indent=2)
            identity_file.chmod(IDENTITY_FILE_MODE)
            if not self.silent_mode:
                utils.console.print(f"[IdentityManager] Saved identity metadata for [cyan]{agent_id}[/cyan] to {identity_file}", style="dim")
        except IOError as e:
            raise IdentityManagerError(f"Failed to save identity metadata for {agent_id} to {identity_file}: {e}")

    def create_identity(self, name: Optional[str] = None, existing_agent_id: Optional[str] = None) -> Dict[str, Any]:
        agent_id = existing_agent_id if existing_agent_id else self._generate_agent_id()
        
        identity_file_path = self.identity_store_path / f"{agent_id}.json"
        if identity_file_path.exists():
            raise IdentityManagerError(f"Cannot create identity: Agent ID '{agent_id}' metadata file already exists locally at {identity_file_path}.")

        keys = self.generate_ed25519_keypair_raw_b64()
        public_key_b64 = keys["public_key"]
        private_key_b64 = keys["private_key"]
        
        keyring_service_name = _get_keyring_service_name_for_agent(agent_id)

        try:
            keyring.set_password(keyring_service_name, agent_id, private_key_b64)
            if not self.silent_mode:
                utils.console.print(f"[IdentityManager] Private key for agent [cyan]{agent_id}[/cyan] securely stored in system keyring (Service: '{keyring_service_name}').", style="green")
        except NoKeyringError:
            msg = (f"CRITICAL SECURITY RISK: No system keyring backend found. "
                   f"Private key for agent {agent_id} cannot be stored securely. "
                   f"Aborting identity creation. Please install and configure a keyring backend.")
            if not self.silent_mode:
                utils.console.print(f"[IdentityManager] {msg}", style="bold red")
            raise IdentityManagerError(msg)
        except PasswordSetError as pse:
            msg = f"Failed to store private key in keyring for agent {agent_id} (PasswordSetError): {pse}. Check keyring access and permissions."
            if not self.silent_mode: utils.console.print(f"[IdentityManager] {msg}", style="bold red")
            raise IdentityManagerError(msg) from pse
        except Exception as e:
            msg = f"An unexpected error occurred while storing private key in keyring for agent {agent_id}: {e}"
            if not self.silent_mode: utils.console.print(f"[IdentityManager] {msg}", style="bold red")
            raise IdentityManagerError(msg) from e

        identity_metadata_for_file = {
            "id": agent_id,
            "name": name,
            "created_at": int(time.time()),
            "public_key": public_key_b64 
        }
        self._save_identity_metadata_to_file(agent_id, identity_metadata_for_file)
        
        # The returned dictionary is for immediate use by the caller (e.g. agent register command)
        # It includes the private key which was just stored in the keyring.
        identity_to_return = {**identity_metadata_for_file, "private_key": private_key_b64}
        try:
            identity_to_return["public_key_fingerprint"] = self.get_public_key_fingerprint(public_key_b64)
        except IdentityManagerError as e:
            if not self.silent_mode:
                utils.console.print(f"[IdentityManager] Warning: Could not generate fingerprint for new identity {agent_id}: {e}", style="yellow")
            identity_to_return["public_key_fingerprint"] = "Error/Unavailable"
        
        return identity_to_return

    def load_identity(self, agent_id: str) -> Optional[Dict[str, Any]]:
        identity_file_path = self.identity_store_path / f"{agent_id}.json"
        if not identity_file_path.exists():
            if not self.silent_mode:
                utils.console.print(f"[IdentityManager] No local identity metadata file found for agent {agent_id}.", style="dim")
            return None 
        
        try:
            with open(identity_file_path, 'r') as f:
                identity_metadata = json.load(f) 
            if "public_key" not in identity_metadata or identity_metadata.get("id") != agent_id:
                raise IdentityManagerError(f"Metadata for {agent_id} is corrupted, missing key fields, or ID mismatch.")
        except (json.JSONDecodeError, IOError, KeyError, IdentityManagerError) as e: 
            if not self.silent_mode: utils.console.print(f"[IdentityManager] Error loading or validating metadata for {agent_id} from {identity_file_path}: {e}", style="red")
            raise IdentityManagerError(f"Corrupted, unreadable, or invalid identity metadata for {agent_id}: {e}")

        retrieved_private_key: Optional[str] = None
        keyring_service_name = _get_keyring_service_name_for_agent(agent_id)
        try:
            retrieved_private_key = keyring.get_password(keyring_service_name, agent_id)
            if retrieved_private_key:
                if not self.silent_mode: utils.console.print(f"[IdentityManager] Successfully retrieved private key for agent {agent_id} from system keyring (Service: '{keyring_service_name}').", style="dim")
            else:
                if not self.silent_mode: 
                    utils.console.print(f"[IdentityManager] WARNING: Private key for agent [yellow]{agent_id}[/yellow] was NOT FOUND in the system keyring (Service: '{keyring_service_name}'). Metadata file exists, but private key is missing from secure storage.", style="bold yellow")
                    utils.console.print(f"    Service: '{keyring_service_name}', Username: '{agent_id}'", style="bold yellow")
                    utils.console.print(f"    Signing operations will fail for this agent if it relies on keyring.", style="bold yellow")
        except NoKeyringError:
            if not self.silent_mode: 
                utils.console.print(f"[IdentityManager] WARNING: No system keyring backend found when trying to load private key for agent [yellow]{agent_id}[/yellow] (Service: '{keyring_service_name}').", style="bold yellow")
                utils.console.print(f"    Cannot retrieve private key. Signing operations will fail.", style="bold yellow")
        except Exception as e:
            if not self.silent_mode: utils.console.print(f"[IdentityManager] WARNING: An unexpected error occurred while trying to retrieve private key from keyring for agent [yellow]{agent_id}[/yellow] (Service: '{keyring_service_name}'): {e}", style="bold yellow")
        
        identity_metadata["private_key"] = retrieved_private_key 
        
        try:
            identity_metadata["public_key_fingerprint"] = self.get_public_key_fingerprint(identity_metadata["public_key"])
        except Exception as e:
            if not self.silent_mode: utils.console.print(f"[IdentityManager] Warning: Could not generate fingerprint for loaded identity {agent_id} (public_key: '{identity_metadata.get('public_key')}'): {e}", style="yellow")
            identity_metadata["public_key_fingerprint"] = "Error/Unavailable"
            
        return identity_metadata

    def list_identities(self) -> List[Dict[str, Any]]:
        identities_summary = []
        if not self.identity_store_path.exists(): return identities_summary
            
        for identity_file in self.identity_store_path.glob("agent-*.json"):
            try:
                with open(identity_file, 'r') as f: data = json.load(f)
                if not data.get("id") or "public_key" not in data:
                    if not self.silent_mode: utils.console.print(f"[IdentityManager] Warning: Skipping invalid identity metadata file {identity_file.name} (missing id or public_key).", style="yellow")
                    continue
                summary_item = {
                    "id": data["id"], "name": data.get("name"), 
                    "created_at": data.get("created_at"),
                    "public_key_fingerprint": self.get_public_key_fingerprint(data["public_key"])
                }
                identities_summary.append(summary_item)
            except Exception as e: 
                if not self.silent_mode: utils.console.print(f"[IdentityManager] Warning: Could not load/process identity file {identity_file.name} for listing: {e}", style="yellow")
        return identities_summary

    def delete_identity(self, agent_id: str) -> bool:
        identity_file = self.identity_store_path / f"{agent_id}.json"
        file_deleted_successfully = False
        keyring_key_deleted_successfully = False
        if identity_file.exists():
            try:
                identity_file.unlink()
                if not self.silent_mode: utils.console.print(f"[IdentityManager] Deleted identity metadata file for {agent_id}.", style="dim")
                file_deleted_successfully = True
            except OSError as e:
                if not self.silent_mode: utils.console.print(f"[IdentityManager] Error deleting metadata file {identity_file.name}: {e}", style="red")
        else:
            if not self.silent_mode: utils.console.print(f"[IdentityManager] No local identity metadata file found for {agent_id} to delete.", style="dim")
            file_deleted_successfully = True

        keyring_service_name = _get_keyring_service_name_for_agent(agent_id)
        try:
            keyring.delete_password(keyring_service_name, agent_id)
            if not self.silent_mode: utils.console.print(f"[IdentityManager] Deleted private key for agent {agent_id} from system keyring (Service: '{keyring_service_name}').", style="dim")
            keyring_key_deleted_successfully = True
        except PasswordDeleteError: 
            if not self.silent_mode: utils.console.print(f"[IdentityManager] Private key for agent {agent_id} not found in system keyring (Service: '{keyring_service_name}') (considered success for deletion).", style="dim")
            keyring_key_deleted_successfully = True
        except NoKeyringError:
            if not self.silent_mode: utils.console.print(f"[IdentityManager] Warning: No system keyring backend. Cannot delete private key for agent {agent_id} from keyring (Service: '{keyring_service_name}').", style="bold yellow")
        except Exception as e:
            if not self.silent_mode: utils.console.print(f"[IdentityManager] Error deleting private key from keyring for agent {agent_id} (Service: '{keyring_service_name}'): {e}", style="red")
        return file_deleted_successfully and keyring_key_deleted_successfully

    def persist_generated_identity(
        self, 
        agent_id: str, 
        public_key_b64: str, 
        private_key_b64: str, 
        name: Optional[str] = None, 
        created_at_timestamp: Optional[int] = None 
    ) -> None:
        """
        Persists an already generated identity: private key to keyring, public metadata to file.
        This is used by the CLI when the agent_id is determined by the backend AFTER local key generation.
        """
        identity_file_path = self.identity_store_path / f"{agent_id}.json"
        if identity_file_path.exists():
            if not self.silent_mode: utils.console.print(f"[IdentityManager] Warning: Metadata file for agent [yellow]{agent_id}[/yellow] already exists. It will be updated, and keyring entry will be set/overwritten.", style="yellow")

        keyring_service_name = _get_keyring_service_name_for_agent(agent_id)
        try:
            keyring.set_password(keyring_service_name, agent_id, private_key_b64)
            if not self.silent_mode: utils.console.print(f"[IdentityManager] Private key for agent [cyan]{agent_id}[/cyan] securely stored/updated in system keyring (Service: '{keyring_service_name}').", style="green")
        except NoKeyringError:
            msg = (f"CRITICAL SECURITY RISK: No system keyring backend found. "
                   f"Private key for agent {agent_id} cannot be stored securely. "
                   f"Aborting persistence of local identity. The agent may be registered on the backend but local keys are not securely stored.")
            if not self.silent_mode: utils.console.print(f"[IdentityManager] {msg}", style="bold red")
            raise IdentityManagerError(msg)
        except PasswordSetError as pse:
            msg = f"Failed to store private key in keyring for agent {agent_id} (PasswordSetError): {pse}. Check keyring access and permissions."
            if not self.silent_mode: utils.console.print(f"[IdentityManager] {msg}", style="bold red")
            raise IdentityManagerError(msg) from pse
        except Exception as e:
            msg = f"An unexpected error occurred while storing private key in keyring for agent {agent_id}: {e}"
            if not self.silent_mode: utils.console.print(f"[IdentityManager] {msg}", style="bold red")
            raise IdentityManagerError(msg) from e

        identity_metadata_for_file = {
            "id": agent_id,
            "name": name,
            "created_at": created_at_timestamp if created_at_timestamp is not None else int(time.time()),
            "public_key": public_key_b64
        }
        self._save_identity_metadata_to_file(agent_id, identity_metadata_for_file)
        # utils.console.print(f"[IdentityManager] Local identity metadata for [cyan]{agent_id}[/cyan] saved.", style="dim") # _save_identity_metadata_to_file now prints this

# Singleton instance - this will be created with default paths initially
identity_manager = IdentityManager()

if __name__ == '__main__':
    # Basic test of the IdentityManager
    print("--- Testing IdentityManager ---")
    # Ensure utils.py is discoverable or provide a mock for console for standalone testing
    # For this example, assuming utils are available or direct print
    
    im = IdentityManager()

    # Test create
    print("\n1. Creating new identity 'TestAgentAlpha'...")
    try:
        alpha_identity = im.create_identity(name="TestAgentAlpha")
        print(f"Created Alpha: {alpha_identity['id']}, Fingerprint: {alpha_identity['public_key_fingerprint']}")
        alpha_id = alpha_identity['id']

        # Test create with existing ID (should fail)
        print("\n1b. Attempting to create with existing ID (should fail)...")
        try:
            im.create_identity(name="Duplicate", existing_agent_id=alpha_id)
        except IdentityManagerError as e:
            print(f"Caught expected error: {e}")


        # Test load
        print(f"\n2. Loading identity {alpha_id}...")
        loaded_alpha = im.load_identity(alpha_id)
        if loaded_alpha:
            print(f"Loaded Alpha: {loaded_alpha['id']}, Name: {loaded_alpha['name']}, Fingerprint: {loaded_alpha.get('public_key_fingerprint')}")
        else:
            print(f"Failed to load {alpha_id}")

        # Test list
        print("\n3. Listing identities...")
        all_identities = im.list_identities()
        print(f"Found {len(all_identities)} identities:")
        for ident in all_identities:
            print(f"  - ID: {ident['id']}, Name: {ident.get('name')}, Fingerprint: {ident.get('public_key_fingerprint')}")

        # Test delete
        print(f"\n4. Deleting identity {alpha_id}...")
        if im.delete_identity(alpha_id):
            print(f"Deleted {alpha_id} successfully.")
        else:
            print(f"Failed to delete {alpha_id}.")
        
        # Verify deletion by trying to load again
        print(f"\n5. Verifying deletion of {alpha_id}...")
        if not im.load_identity(alpha_id):
            print(f"{alpha_id} no longer exists (as expected).")
        else:
            print(f"Error: {alpha_id} still exists after deletion attempt.")

    except IdentityManagerError as e:
        print(f"An IdentityManagerError occurred during testing: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during testing: {e}")

    print("\n--- IdentityManager Test Complete ---") 