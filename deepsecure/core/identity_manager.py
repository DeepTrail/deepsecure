# deepsecure/core/identity_manager.py
import os
import json
import time
import uuid
import hashlib
import base64 # For decoding keys for fingerprinting
from pathlib import Path
from typing import Dict, Any, Optional, List

# Ensuring correct relative imports for a package structure
from .crypto.key_manager import key_manager as key_manager_instance # Corrected import for the instance
from .. import utils
from ..exceptions import IdentityManagerError, DeepSecureError # Assuming DeepSecureError is base

IDENTITY_STORE_PATH = Path(os.path.expanduser("~/.deepsecure/identities"))
DEEPSECURE_DIR = Path(os.path.expanduser("~/.deepsecure"))
IDENTITY_FILE_MODE = 0o600

class IdentityManager:
    def __init__(self):
        self.key_manager = key_manager_instance # Use the imported instance
        self.identity_store_path = IDENTITY_STORE_PATH
        
        try:
            DEEPSECURE_DIR.mkdir(exist_ok=True)
            self.identity_store_path.mkdir(exist_ok=True)
        except OSError as e:
            # This is a critical failure if directories can't be made.
            raise IdentityManagerError(f"Failed to create required directories ({DEEPSECURE_DIR}, {self.identity_store_path}): {e}")


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
            hasher = hashlib.new(hash_algo)
            hasher.update(key_bytes)
            return f"{hash_algo}:{hasher.hexdigest()}"
        except Exception as e: # Catch base64 decode errors or hashlib errors
            raise IdentityManagerError(f"Failed to generate fingerprint: {e}")

    def create_identity(self, name: Optional[str] = None, existing_agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates a new agent ID (or uses existing_agent_id if provided), 
        Ed25519 key pair, saves it locally, and returns the identity.
        'name' is for local reference.
        Returns: The full identity dictionary.
        Raises: IdentityManagerError if saving fails or if existing_agent_id is taken.
        """
        agent_id = existing_agent_id if existing_agent_id else self._generate_agent_id()
        
        identity_file = self.identity_store_path / f"{agent_id}.json"
        if existing_agent_id and identity_file.exists():
            raise IdentityManagerError(f"Cannot create identity: Agent ID '{agent_id}' already exists locally.")

        keys = self.generate_ed25519_keypair_raw_b64()
        
        identity_data = {
            "id": agent_id,
            "name": name,
            "created_at": int(time.time()),
            "public_key": keys["public_key"], # base64 raw
            "private_key": keys["private_key"] # base64 raw
        }
        
        self.save_identity(agent_id, identity_data)
        # Add fingerprint to the returned dict for convenience, but not stored in file by default
        identity_data["public_key_fingerprint"] = self.get_public_key_fingerprint(keys["public_key"])
        return identity_data

    def save_identity(self, agent_id: str, identity_data: Dict[str, Any]):
        """Saves the identity data to a local JSON file. Overwrites if exists."""
        identity_file = self.identity_store_path / f"{agent_id}.json"
        # Ensure private key is not inadvertently removed if not present in partial update
        if "private_key" not in identity_data and identity_file.exists():
             try:
                with open(identity_file, 'r') as f:
                    existing_data = json.load(f)
                if "private_key" in existing_data:
                    identity_data["private_key"] = existing_data["private_key"]
             except Exception: # Ignore if reading old file fails, proceed with new data
                 pass


        try:
            with open(identity_file, 'w') as f:
                json.dump(identity_data, f, indent=2)
            identity_file.chmod(IDENTITY_FILE_MODE)
        except IOError as e:
            raise IdentityManagerError(f"Failed to save identity for {agent_id}: {e}")

    def load_identity(self, agent_id: str) -> Optional[Dict[str, Any]]:
        identity_file = self.identity_store_path / f"{agent_id}.json"
        if not identity_file.exists():
            return None
        try:
            with open(identity_file, 'r') as f:
                identity = json.load(f)
            # Add fingerprint for convenience
            if "public_key" in identity:
                identity["public_key_fingerprint"] = self.get_public_key_fingerprint(identity["public_key"])
            return identity
        except (json.JSONDecodeError, IOError, IdentityManagerError) as e: # Catch fingerprint error too
            # Log this error as it might mean corrupted file
            utils.console.print(f"[IdentityManager] Warning: Failed to load or parse identity for {agent_id}: {e}", style="yellow")
            # Optionally re-raise or return None based on strictness
            # For now, let's return None as if it's not loadable = not found in usable state
            return None 


    def list_identities(self) -> List[Dict[str, Any]]:
        identities = []
        if not self.identity_store_path.exists():
            return identities
            
        for identity_file in self.identity_store_path.glob("agent-*.json"): # More specific glob
            agent_id_from_filename = identity_file.stem
            try:
                with open(identity_file, 'r') as f:
                    data = json.load(f)
                
                # Basic validation
                if not data.get("id") or "public_key" not in data:
                    utils.console.print(f"[IdentityManager] Warning: Skipping invalid identity file {identity_file.name} (missing id or public_key).", style="yellow")
                    continue

                list_item = {
                    "id": data["id"],
                    "name": data.get("name"),
                    "created_at": data.get("created_at"),
                    "public_key_fingerprint": self.get_public_key_fingerprint(data["public_key"])
                }
                identities.append(list_item)
            except (json.JSONDecodeError, IOError, IdentityManagerError, KeyError) as e:
                utils.console.print(f"[IdentityManager] Warning: Could not load/process identity file {identity_file.name}: {e}", style="yellow")
        return identities

    def delete_identity(self, agent_id: str) -> bool:
        identity_file = self.identity_store_path / f"{agent_id}.json"
        if not identity_file.exists():
            return True 
        try:
            identity_file.unlink()
            return True
        except OSError as e:
            utils.console.print(f"[IdentityManager] Error deleting identity file {identity_file.name}: {e}", style="red")
            raise IdentityManagerError(f"OS error deleting identity {agent_id}: {e}")


# Singleton instance
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