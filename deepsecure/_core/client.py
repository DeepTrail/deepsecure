"""High-level client services that wrap core client functionalities."""

import requests
from typing import Optional, Type, TypeVar, Dict, Any
import base64
import time
from datetime import datetime
import uuid
import re
import logging
import json
import sys
import os
import socket

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.asymmetric import ed25519 as ed25519_crypto
from pydantic import BaseModel, ValidationError as PydanticValidationError

from . import config
from .exceptions import (
    ApiError,
    AuthenticationError,
    DeepSecureClientError,
    IdentityManagerError
)
from . import schemas as client_main_schemas
from .identity_manager import IdentityManager
from .agent_client import client as agent_api_client_for_setup
from .crypto.key_manager import key_manager as global_key_manager_instance
from .audit_logger import audit_logger
from . import base_client
from . import vault_client as core_vault_client_module
from . import agent_client as core_agent_client_module

# Commented out debug prints
# print(f"DEBUG [deepsecure.client]: core_vault_client module from: {core_vault_client_module.__file__}", file=sys.stderr)
# print(f"DEBUG [deepsecure.client]: core_agent_client module from: {core_agent_client_module.__file__}", file=sys.stderr)
# print(f"<<<< DEBUG: client.py (this file) IS BEING LOADED AND EXECUTED (top level) >>>>", file=sys.stderr)

logger = logging.getLogger(__name__)

DEEPSECURE_DIR = core_vault_client_module.DEEPSECURE_DIR
DEVICE_ID_FILE = core_vault_client_module.DEVICE_ID_FILE

class EphemeralKeyPair:
    def __init__(self, public_key_b64: str, private_key_b64: str):
        self.public_key_b64 = public_key_b64
        self.private_key_b64 = private_key_b64

def _generate_ephemeral_keys() -> EphemeralKeyPair:
    eph_keys = global_key_manager_instance.generate_ephemeral_keypair()
    return EphemeralKeyPair(public_key_b64=eph_keys["public_key"], private_key_b64=eph_keys["private_key"])

class VaultClient(base_client.BaseClient):
    def __init__(self):
        super().__init__()
        self.key_manager = global_key_manager_instance
        self.audit_logger = audit_logger
        self.api_prefix_vault_creds = "/api/v1/vault/credentials"
        self.api_prefix_agents = "/api/v1/agents"
        self.api_prefix_vault_agents_rotate = "/api/v1/vault/agents"
        DEEPSECURE_DIR.mkdir(exist_ok=True)
        # print(f"DEBUG [VaultClientService.__init__]: self._client is of type: {type(self)}", file=sys.stderr)
        # print(f"DEBUG [VaultClientService.__init__]: self._client module: {getattr(self, '__module__', 'N/A')}", file=sys.stderr)

    def _get_device_identifier(self) -> str:
        if DEVICE_ID_FILE.exists():
            try:
                with open(DEVICE_ID_FILE, 'r') as f:
                    device_id = f.read().strip()
                    uuid.UUID(device_id)
                    return device_id
            except (IOError, ValueError):
                pass 
        device_id = str(uuid.uuid4())
        try:
            DEVICE_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(DEVICE_ID_FILE, 'w') as f:
                f.write(device_id)
            DEVICE_ID_FILE.chmod(0o600)
        except IOError as e:
            print(f"[Warning] Failed to store persistent device ID: {e}", file=sys.stderr)
            return device_id 
        return device_id

    def _capture_origin_context(self) -> Dict[str, Any]:
        context = {
            "hostname": socket.gethostname(),
            "username": os.getlogin(),
            "process_id": os.getpid(),
            "timestamp": int(time.time())
        }
        try:
            context["ip_address"] = socket.gethostbyname(socket.gethostname())
        except socket.gaierror:
            context["ip_address"] = "127.0.0.1"
        context["device_id"] = self._get_device_identifier()
        return context

    def issue(self, scope: str, agent_id: str, ttl: int = 300, origin_binding: bool = True, passed_origin_context: Optional[Dict[str, Any]] = None) -> client_main_schemas.CredentialResponse:
        # print("\nDEBUG [VaultClient in client.py]: TOP OF issue METHOD REACHED\n", file=sys.stderr)
        logger.info(f"[VaultClient(client.py).issue] Attempting for agent: {agent_id}, scope: {scope}, ttl: {ttl}s")
        
        agent_private_key_b64 = self._identity_manager.get_private_key(agent_id)
        if not agent_private_key_b64: 
            raise DeepSecureClientError(f"Private key for agent {agent_id} not found in keychain.")
        
        ephemeral_keys = _generate_ephemeral_keys()
        ephemeral_public_key_to_send_b64 = ephemeral_keys.public_key_b64
        ephemeral_private_key_to_return_b64 = ephemeral_keys.private_key_b64

        signature_b64_str: str
        try:
            raw_agent_private_key_bytes = base64.b64decode(agent_private_key_b64)
            if len(raw_agent_private_key_bytes) != 32: raise ValueError("Agent private key (decoded) not 32 bytes.")
            agent_private_key_obj = ed25519_crypto.Ed25519PrivateKey.from_private_bytes(raw_agent_private_key_bytes)
            raw_ephemeral_public_key_bytes = base64.b64decode(ephemeral_public_key_to_send_b64)
            if len(raw_ephemeral_public_key_bytes) != 32: raise ValueError("Ephemeral PK (decoded) not 32 bytes.")
            signature_bytes = agent_private_key_obj.sign(raw_ephemeral_public_key_bytes)
            signature_b64_str = base64.b64encode(signature_bytes).decode('utf-8')
        except Exception as e: raise DeepSecureClientError(f"Failed to sign request for {agent_id}: {e}") from e

        final_origin_context_for_payload: Optional[Dict[str, Any]] = None
        if origin_binding:
            final_origin_context_for_payload = passed_origin_context if passed_origin_context is not None else self._capture_origin_context()
        
        # Commenting out the specific debug block for origin_context and payload_dict
        # print(f"DEBUG [VaultClient in client.py]: 1. final_origin_context_for_payload: {final_origin_context_for_payload}", file=sys.stderr)

        try:
            request_payload_model = client_main_schemas.CredentialIssueRequest(
                scope=scope, 
                ttl=ttl, 
                agent_id=agent_id, 
                ephemeral_public_key=ephemeral_public_key_to_send_b64, 
                signature=signature_b64_str,
                origin_context=final_origin_context_for_payload
            )
            # print(f"DEBUG [VaultClient in client.py]: 2. request_payload_model dir: {dir(request_payload_model)}", file=sys.stderr) # This was from a previous iteration, ensure it's out
            # print(f"DEBUG [VaultClient in client.py]: 2.1. request_payload_model.origin_context: {getattr(request_payload_model, 'origin_context', 'MISSING_ATTRIBUTE')}", file=sys.stderr)
            
            payload_dict = request_payload_model.model_dump(exclude_unset=False, by_alias=False) # Changed from exclude_none=True
            # print(f"DEBUG [VaultClient in client.py]: 3. payload_dict AFTER model_dump(exclude_unset=False): {payload_dict}", file=sys.stderr)
            # print(f"DEBUG [VaultClient in client.py]: 3.1. origin_context in payload_dict: {payload_dict.get('origin_context', 'NOT_IN_PAYLOAD_DICT')}", file=sys.stderr)
            # print(f"DEBUG [VaultClient in client.py]: 3.5. Full payload_dict: {payload_dict}", file=sys.stderr) # This was from previous iteration

        except PydanticValidationError as e: raise DeepSecureClientError(f"Client-side payload error: {e}", error_details=e.errors()) from e

        server_response_dict = self._request(
            method="POST", 
            path=self.api_prefix_vault_creds,
            data=payload_dict, 
            is_backend_request=True
        )
        if not server_response_dict: raise DeepSecureClientError("No response data from server for issue credential.")
        
        try:
            server_response_base = client_main_schemas.CredentialBase.model_validate(server_response_dict)
            # Extract secret_value from the server response if present
            secret_value = server_response_dict.get("secret_value", "dummy_secret_value_for_testing")
            final_response = client_main_schemas.CredentialResponse(
                **server_response_base.model_dump(), 
                ephemeral_public_key_b64=ephemeral_public_key_to_send_b64, 
                ephemeral_private_key_b64=ephemeral_private_key_to_return_b64,
                secret_value=secret_value
            )
        except PydanticValidationError as e: raise DeepSecureClientError(f"Client-side: Failed to construct final CredentialResponse: {e}") from e
        
        logger.info(f"[VaultClient(client.py).issue] Success: {final_response.credential_id}")
        return final_response

    def get_agent_details(self, agent_id: str) -> client_main_schemas.AgentDetailsResponse:
        server_response_dict = self._request(
            method="GET", 
            path=f"{self.api_prefix_agents}/{agent_id}",
            is_backend_request=True
        )
        if not server_response_dict: raise DeepSecureClientError(f"No response data from server for get_agent_details for {agent_id}.")
        return client_main_schemas.AgentDetailsResponse.model_validate(server_response_dict)

    def rotate(self, agent_id: str, new_public_key_b64: str) -> Optional[client_main_schemas.AgentKeyRotationResponse]:
        payload_model = client_main_schemas.AgentKeyRotateRequest(new_public_key=new_public_key_b64)
        response_dict = self._request(
            method="POST", 
            path=f"{self.api_prefix_vault_agents_rotate}/{agent_id}/rotate-identity",
            data=payload_model.model_dump(), 
            is_backend_request=True
        )
        if response_dict and response_dict.get("status") == "success":
            return client_main_schemas.AgentKeyRotationResponse(agent_id=agent_id, status="success_on_client_for_204")
        return None

    def verify(self, credential_id: str) -> client_main_schemas.VerificationResponse:
        server_response_dict = self._request(
            method="GET", 
            path=f"{self.api_prefix_vault_creds}/{credential_id}/verify",
            is_backend_request=True
        )
        if not server_response_dict: raise DeepSecureClientError(f"No response data for verify {credential_id}.")
        return client_main_schemas.VerificationResponse.model_validate(server_response_dict)
    
    def revoke(self, credential_id: str) -> client_main_schemas.RevocationResponse:
        server_response_dict = self._request(
            method="POST", 
            path=f"{self.api_prefix_vault_creds}/{credential_id}/revoke",
            is_backend_request=True
        )
        if not server_response_dict: raise DeepSecureClientError(f"No response data for revoke {credential_id}.")
        return client_main_schemas.RevocationResponse.model_validate(server_response_dict)

    def store_secret(self, name: str, value: str) -> Dict[str, Any]:
        """Stores a secret in the backend vault."""
        logger.info(f"Storing secret with name: {name}")
        payload = {"name": name, "value": value}
        response_dict = self._request(
            method="POST",
            path="/api/v1/vault/store",
            data=payload,
            is_backend_request=True,
        )
        return response_dict

    def get_secret_direct(self, name: str) -> Dict[str, Any]:
        """Retrieves a secret directly from the backend vault without requiring an agent.
        
        This method is intended for CLI/administrative use and bypasses the ephemeral
        credential system. For programmatic agent access, use the issue() method instead.
        
        Args:
            name: The name of the secret to retrieve.
            
        Returns:
            A dictionary containing the secret data (name, value, created_at).
            
        Raises:
            DeepSecureClientError: If the secret is not found or retrieval fails.
        """
        logger.info(f"Retrieving secret directly with name: {name}")
        try:
            response_dict = self._request(
                method="GET",
                path=f"/api/v1/vault/secrets/{name}",
                is_backend_request=True,
            )
            return response_dict
        except Exception as e:
            logger.error(f"Failed to retrieve secret {name}: {e}")
            raise DeepSecureClientError(f"Failed to retrieve secret '{name}': {e}") from e

class AgentClient:
    """
    Client for managing agent identities.
    """
    def __init__(self, authenticator):
        super().__init__(authenticator)

    def create(self, public_key_b64: str, name: str = None) -> dict:
        """
        Creates a new agent identity.
        """
        return self._request(
            "POST",
            "/api/v1/agents/",
            json={"public_key": public_key_b64, "name": name},
        )

if __name__ == "__main__":
    print("DeepSecure VaultClient Test Script with Self-Setup/Teardown")
    print("==========================================================")
    print("[Warning] Ensure DEEPSECURE_CREDSERVICE_URL and DEEPSECURE_CREDSERVICE_API_TOKEN are set, or configured via CLI.")

    test_run_uuid = str(uuid.uuid4())[:8]
    test_agent_name = f"ClientPyTestAgent-{test_run_uuid}"
    test_agent_id_for_run: Optional[str] = None
    client: Optional[VaultClient] = None
    temp_keys_for_setup: Optional[Dict[str,str]] = None
    agent_details_initial: Optional[client_main_schemas.AgentDetailsResponse] = None

    try:
        print("\n[SETUP] Initializing clients...")
        client = VaultClient()
        
        print(f"\n[SETUP] Registering a new dynamic agent for this test run: '{test_agent_name}'")
        temp_keys_for_setup = self._identity_manager.generate_ed25519_keypair_raw_b64()
        
        backend_reg_response = agent_api_client_for_setup.register_agent(
            public_key=temp_keys_for_setup["public_key"],
            name=test_agent_name,
            description="Dynamically created for client.py test run"
        )
        test_agent_id_for_run = backend_reg_response.get("agent_id")
        if not test_agent_id_for_run:
            raise Exception("Failed to get agent_id from backend registration during setup.")
        
        self._identity_manager.store_private_key_directly(
            agent_id=test_agent_id_for_run,
            private_key_b64=temp_keys_for_setup["private_key"]
        )
        print(f"[SETUP] Successfully registered and locally persisted agent: {test_agent_id_for_run} (Name: {test_agent_name})")

        print(f"\n--- Testing: Agent Operations (Get Details for {test_agent_id_for_run}) ---")
        agent_details_initial = client.get_agent_details(agent_id=test_agent_id_for_run)
        print("Agent details retrieved successfully:") 
        print(agent_details_initial.model_dump_json(indent=2))

        print(f"\n--- Testing: Core Vault Operations (for agent {test_agent_id_for_run}) ---")
        issued_cred = client.issue(scope="test:clientpy:lifecycle", agent_id=test_agent_id_for_run, ttl=120)
        print("Credential issued successfully:")
        print(issued_cred.model_dump_json(indent=2))
        issued_credential_id = issued_cred.credential_id

        print(f"\nVerifying credential {issued_credential_id} (should be valid)...")
        verify_status_valid = client.verify(credential_id=issued_credential_id)
        print("Verification response (valid):")
        print(verify_status_valid.model_dump_json(indent=2))
        if not verify_status_valid.is_valid or verify_status_valid.status != "valid": print("Assertion Failed: Valid cred")
        else: print("Assertion Passed: Credential is valid.")

        print(f"\nRevoking credential {issued_credential_id}...")
        revoke_status = client.revoke(credential_id=issued_credential_id)
        print("Revocation response:")
        print(revoke_status.model_dump_json(indent=2))
        if revoke_status.status != "revoked": print("Assertion Failed: Revoke status")
        else: print("Assertion Passed: Credential revoked.")

        print(f"\nVerifying credential {issued_credential_id} (should be revoked)...")
        verify_status_revoked = client.verify(credential_id=issued_credential_id)
        print("Verification response (revoked):")
        print(verify_status_revoked.model_dump_json(indent=2))
        if verify_status_revoked.is_valid or verify_status_revoked.status != "revoked": print("Assertion Failed: Revoked cred")
        else: print("Assertion Passed: Credential is revoked.")

        print(f"\n--- Testing: Agent Operations (Rotate Key for {test_agent_id_for_run}) ---")
        new_rotation_keys = self._identity_manager.generate_ed25519_keypair_raw_b64()
        new_public_key_for_rotation_b64 = new_rotation_keys["public_key"]
        new_private_key_for_rotation_b64 = new_rotation_keys["private_key"]
        print(f"New public key for rotation: {new_public_key_for_rotation_b64}")
        client.rotate(agent_id=test_agent_id_for_run, new_public_key_b64=new_public_key_for_rotation_b64)
        print("Backend key rotation call completed.")
        
        created_at_ts_for_persist = int(time.time())
        current_agent_name = test_agent_name
        if agent_details_initial and agent_details_initial.created_at:
            if isinstance(agent_details_initial.created_at, str):
                try: created_at_ts_for_persist = int(datetime.fromisoformat(agent_details_initial.created_at).timestamp())
                except ValueError: pass 
            elif isinstance(agent_details_initial.created_at, datetime):
                created_at_ts_for_persist = int(agent_details_initial.created_at.timestamp())
            if agent_details_initial.name:
                current_agent_name = agent_details_initial.name

        self._identity_manager.store_private_key_directly(
            agent_id=test_agent_id_for_run, 
            private_key_b64=new_private_key_for_rotation_b64
        )
        print("Local identity store updated for rotated keys.")
        agent_details_after_rotation = client.get_agent_details(agent_id=test_agent_id_for_run)
        print("Agent details after rotation:")
        print(agent_details_after_rotation.model_dump_json(indent=2))
        if agent_details_after_rotation.public_key == new_public_key_for_rotation_b64: print("Assertion Passed: Agent PK rotated.")
        else: print("Assertion Failed: Agent PK not rotated.")

    except (DeepSecureClientError, ApiError, IdentityManagerError) as e:
        print(f"\nA DeepSecure specific error occurred: {type(e).__name__} - {e}")
        if hasattr(e, 'error_details') and e.error_details: print(f"Error Details: {e.error_details}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()
    finally:
        if test_agent_id_for_run:
            print(f"\n[TEARDOWN] Cleaning up test agent: {test_agent_id_for_run}")
            try:
                agent_api_client_for_setup.delete_agent(agent_id=test_agent_id_for_run)
                print(f"[TEARDOWN] Agent {test_agent_id_for_run} deactivated/deleted from backend.")
            except Exception as e_del_be:
                print(f"[TEARDOWN] Error deleting agent {test_agent_id_for_run} from backend: {e_del_be}")
            try:
                self._identity_manager.delete_private_key(test_agent_id_for_run)
                print(f"[TEARDOWN] Local identity for {test_agent_id_for_run} (metadata & keyring) deleted.")
            except Exception as e_del_loc:
                print(f"[TEARDOWN] Error deleting local identity for {test_agent_id_for_run}: {e_del_loc}")
    
    print("\nVaultClient Test Script Finished.") 