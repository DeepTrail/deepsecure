import requests
from typing import Optional, Type, TypeVar
import base64

from cryptography.hazmat.primitives.asymmetric import ed25519
# No specific serialization needed for raw bytes from ed25519, but good to be aware of for other key types.
# from cryptography.hazmat.primitives import serialization 
from pydantic import ValidationError, BaseModel

from deepsecure.core import config
from deepsecure.core.exceptions import (
    APIError,
    AuthenticationError,
    InvalidRequestError,
    NotFoundError,
    NetworkError,
    ServiceUnavailableError,
    DeepSecureClientError # Added base client error
)
from deepsecure.core.schemas import (
    CredentialIssueRequest,
    AgentKeyRotateRequest,
    CredentialResponse,
    CredentialBase, # Make sure CredentialBase is imported
    RevocationResponse,
    AgentKeyRotationResponse,
    VerificationResponse,
    AgentDetailsResponse,
    ErrorDetail
)
from rich import print
from rich.json import JSON

# Define a TypeVar for BaseModel subtypes used in _make_request
BM = TypeVar('BM', bound=BaseModel)

# Helper to generate ephemeral keys if not provided
class EphemeralKeyPair:
    def __init__(self, public_key_b64: str, private_key_b64: str):
        self.public_key_b64 = public_key_b64
        self.private_key_b64 = private_key_b64

def _generate_ephemeral_keys() -> EphemeralKeyPair:
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    private_key_b64 = base64.b64encode(private_key.private_bytes_raw()).decode('utf-8')
    public_key_b64 = base64.b64encode(public_key.public_bytes_raw()).decode('utf-8')
    
    return EphemeralKeyPair(public_key_b64=public_key_b64, private_key_b64=private_key_b64)

class VaultClient:
    """
    Client for interacting with the DeepSecure Vault, typically via CredService.
    """
    def __init__(
        self,
        credservice_url: Optional[str] = None,
        api_token: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initializes the VaultClient.

        Args:
            credservice_url: The URL of the CredService. If None, it's fetched from config.
            api_token: The API token for CredService. If None, it's fetched from config.
            timeout: Request timeout in seconds.
        """
        self.credservice_url = credservice_url or config.get_effective_credservice_url()
        self.api_token = api_token or config.get_effective_api_token()
        self.timeout = timeout

        if not self.credservice_url:
            # Consider raising a custom exception
            print("[bold red]Error: CredService URL is not configured. Use 'deepsecure configure set-url <URL>' or set DEEPSECURE_CREDSERVICE_URL.[/bold red]")
            raise DeepSecureClientError("CredService URL not configured. Use 'deepsecure configure set-url <URL>' or set DEEPSECURE_CREDSERVICE_URL.")

        if not self.api_token:
            # Consider raising a custom exception
            print("[bold red]Error: API token is not configured. Use 'deepsecure configure set-token' or set DEEPSECURE_CREDSERVICE_API_TOKEN.[/bold red]")
            raise DeepSecureClientError("API token not configured. Use 'deepsecure configure set-token' or set DEEPSECURE_CREDSERVICE_API_TOKEN.")
        
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {self.api_token}"})

    def _make_request(self, method: str, endpoint: str, response_model: Optional[Type[BM]] = None, **kwargs) -> Optional[BM]:
        """Helper method to make requests to the CredService."""
        url = f"{self.credservice_url.rstrip('/')}/{endpoint.lstrip('/')}"
        resource_type_for_error = endpoint.split('/')[1] if '/' in endpoint else endpoint # e.g. 'vault' or 'agents'
        resource_id_for_error = endpoint.split('/')[-1] if endpoint.split('/')[-1] != resource_type_for_error else None

        try:
            response = self._session.request(method, url, timeout=self.timeout, **kwargs)
            
            # Handle 204 No Content before trying to parse JSON
            if response.status_code == 204:
                if response_model:
                    # For 204, if a model is expected, behavior depends on model definition.
                    # If all fields in response_model are optional, an empty instance can be returned.
                    # Otherwise, returning None might be more appropriate.
                    try:
                        # Attempt to create model with no data; works if all fields have defaults/are Optional
                        return response_model()
                    except ValidationError:
                        # If model cannot be instantiated empty (e.g. required fields with no defaults)
                        # then returning None is safer if the caller expects the model type or None.
                        return None 
                return None # No model expected, no content, return None
                
            response.raise_for_status() # Raises HTTPError for other bad responses (4XX or 5XX)
            json_response = response.json()
            if response_model:
                return response_model.model_validate(json_response)
            # This path should ideally not be taken if response_model is always provided for successful calls
            # For now, if no model, return raw dict, but client methods should handle this.
            raise DeepSecureClientError(f"No response model provided for successful request to {url}, returning raw data.")
        except ValidationError as e:
            print(f"[bold red]Response validation error for {url}: {e}[/bold red]")
            # Consider a more specific client exception for response parsing/validation issues
            raise DeepSecureClientError(f"Failed to validate API response from {url}: {e}") from e
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            error_details_dict = {}
            error_message = e.response.text
            try:
                # Try to parse with ErrorDetail model first
                parsed_error = ErrorDetail.model_validate(e.response.json())
                error_message = parsed_error.detail
                error_details_dict = parsed_error.model_dump()
            except (requests.exceptions.JSONDecodeError, ValidationError):
                # If it doesn't fit ErrorDetail, or not JSON, use raw text
                pass 
            
            print(f"[bold red]HTTP Error ({status_code}) for {url}. Server message: {error_message}[/bold red]")

            if status_code == 401:
                raise AuthenticationError(message=error_message, status_code=status_code, error_details=error_details_dict) from e
            elif status_code == 403:
                raise AuthenticationError(message=f"Forbidden: You do not have permission to access this resource. {error_message}", status_code=status_code, error_details=error_details_dict) from e
            elif status_code == 404:
                raise NotFoundError(resource_type=resource_type_for_error, resource_id=resource_id_for_error, status_code=status_code, error_details=error_details_dict) from e
            elif status_code == 400 or status_code == 422:
                raise InvalidRequestError(message=f"Invalid request to {url}. {error_message}", status_code=status_code, error_details=error_details_dict) from e
            elif 500 <= status_code < 600:
                raise ServiceUnavailableError(message=f"Service unavailable for {url}. {error_message}", status_code=status_code, error_details=error_details_dict) from e
            else:
                # Generic APIError for other 4xx errors
                raise APIError(message=f"API error for {url}. {error_message}", status_code=status_code, error_details=error_details_dict) from e
        except requests.exceptions.Timeout as e:
            print(f"[bold red]Request Timeout for {url}: {e}[/bold red]")
            raise NetworkError(message=f"Request to {url} timed out", original_exception=e) from e
        except requests.exceptions.ConnectionError as e:
            print(f"[bold red]Connection Error for {url}: {e}[/bold red]")
            raise NetworkError(message=f"Could not connect to {url}", original_exception=e) from e
        except requests.exceptions.RequestException as e: # Catch-all for other requests issues
            print(f"[bold red]Request Exception for {url}: {e}[/bold red]")
            raise NetworkError(message=f"An unexpected network error occurred while requesting {url}", original_exception=e) from e

    def issue(
        self, 
        scope: str, 
        agent_id: Optional[str] = None, 
        ttl: int = 300, # Parameter name is already ttl
        ephemeral_public_key_b64: Optional[str] = None,
        ephemeral_private_key_b64: Optional[str] = None 
    ) -> CredentialResponse:
        final_ephemeral_public_key_b64 = ephemeral_public_key_b64
        final_ephemeral_private_key_b64_to_return = ephemeral_private_key_b64

        if final_ephemeral_public_key_b64 is None:
            keys = _generate_ephemeral_keys()
            final_ephemeral_public_key_b64 = keys.public_key_b64
            final_ephemeral_private_key_b64_to_return = keys.private_key_b64
        
        # For now, since client-side signing is not implemented, we send None for signature.
        # The server-side schema has signature as Optional[str] = Field(None, ...)
        # and the server-side endpoint logic bypasses verification if signature is None.
        actual_signature_to_send = None 

        try:
            request_payload_model = CredentialIssueRequest(
                scope=scope,
                ttl=ttl, 
                agent_id=agent_id,
                ephemeral_public_key=final_ephemeral_public_key_b64,
                signature=actual_signature_to_send # Sending None
            )
        except ValidationError as e:
            # This will catch if, for example, ttl is out of Field(ge=60) range from schema
            raise InvalidRequestError(f"Invalid parameters for issuing credential: {e}", error_details=e.errors()) from e

        # server_response will be an instance of CredentialBase
        server_response = self._make_request(
            "POST", 
            "api/v1/vault/credentials",
            response_model=CredentialBase,
            json=request_payload_model.model_dump(exclude_none=True)
        )
        
        try:
            final_response = CredentialResponse(
                **server_response.model_dump(),
                ephemeral_public_key_b64=final_ephemeral_public_key_b64, 
                ephemeral_private_key_b64=final_ephemeral_private_key_b64_to_return
            )
        except ValidationError as e:
            raise DeepSecureClientError(f"Failed to construct final CredentialResponse from server data: {e}") from e
        
        return final_response

    def revoke(self, credential_id: str) -> RevocationResponse:
        """
        Revokes an existing credential.
        """
        print(f"[VaultClient.revoke] Requesting revocation for credential_id='{credential_id}'")
        response_data = self._make_request(
            "POST", 
            f"api/v1/vault/credentials/{credential_id}/revoke",
            response_model=RevocationResponse
        )
        print(f"[VaultClient.revoke] Revocation response: {response_data}")
        return response_data

    def rotate(self, agent_id: str, new_public_key_b64: str) -> AgentKeyRotationResponse:
        """
        Rotates the identity keys for an agent by notifying the backend of the new public key.
        The caller is responsible for generating the new key pair and managing the private key.

        Args:
            agent_id: The ID of the agent whose identity is to be rotated.
            new_public_key_b64: The new base64 encoded public key for the agent.

        Returns:
            A dictionary containing the rotation status.
        """
        print(f"[VaultClient.rotate] Requesting rotation for agent_id='{agent_id}' with new public key.")
        payload = {"new_public_key": new_public_key_b64}
        response_data = self._make_request(
            "POST", 
            f"api/v1/vault/agents/{agent_id}/rotate-identity",
            response_model=AgentKeyRotationResponse,
            json=payload
        )
        print(f"[VaultClient.rotate] Rotation response for agent {agent_id}: {response_data}")
        return response_data

    def verify(self, credential_id: str) -> VerificationResponse:
        """
        Verifies a credential's validity with the CredService.
        """
        print(f"[VaultClient.verify] Verifying credential_id='{credential_id}'")
        response_data = self._make_request(
            "GET", 
            f"api/v1/vault/credentials/{credential_id}/verify",
            response_model=VerificationResponse
        )
        print(f"[VaultClient.verify] Verification response: {response_data}")
        return response_data

    def get_agent_details(self, agent_id: str) -> AgentDetailsResponse:
        """
        Retrieves details for a specific agent from the CredService.
        """
        print(f"[VaultClient.get_agent_details] Getting details for agent_id='{agent_id}'")
        response_data = self._make_request(
            "GET", 
            f"api/v1/agents/{agent_id}",
            response_model=AgentDetailsResponse
        )
        print(f"[VaultClient.get_agent_details] Agent details response: {response_data}")
        return response_data

# Example Usage (for testing purposes if this file is run directly)
if __name__ == "__main__":
    print("DeepSecure VaultClient Test Script")
    print("==================================")
    print("Ensure DEEPSECURE_CREDSERVICE_URL and DEEPSECURE_CREDSERVICE_API_TOKEN are set, or configured via CLI.")

    TEST_AGENT_ID = "agent-7b927548-cff2-4175-8de3-dc192c857ae1" # Use your registered agent ID
    client: Optional[VaultClient] = None
    issued_credential_id: Optional[str] = None

    try:
        print("\nInitializing VaultClient...")
        client = VaultClient()
        print("[green]VaultClient initialized successfully.[/green]")

        # --- Phase 3: Agent Operations (Part 1: Get Details) ---
        print(f"\n--- Testing Phase 3: Agent Operations (Get Details for {TEST_AGENT_ID}) ---")
        try:
            print(f"Fetching details for agent: {TEST_AGENT_ID}")
            agent_details = client.get_agent_details(agent_id=TEST_AGENT_ID)
            print("[green]Agent details retrieved successfully:[/green]")
            print(JSON(agent_details.model_dump_json(indent=2)))
            original_public_key = agent_details.public_key
        except NotFoundError as e:
            print(f"[bold red]Error: Agent {TEST_AGENT_ID} not found. Please register it first. {e}[/bold red]")
            # Exit if a known agent isn't found, as other tests depend on it.
            exit(1) 
        except (APIError, NetworkError, DeepSecureClientError) as e:
            print(f"[bold red]Error fetching agent details: {type(e).__name__} - {e}[/bold red]")
            exit(1)

        # --- Phase 2: Core Vault Operations ---
        print(f"\n--- Testing Phase 2: Core Vault Operations (for agent {TEST_AGENT_ID}) ---")
        try:
            # 1. Issue Credential
            print("Issuing new credential...")
            issued_cred = client.issue(scope="test:vaultclient:lifecycle", agent_id=TEST_AGENT_ID, ttl=120)
            print("[green]Credential issued successfully:[/green]")
            print(JSON(issued_cred.model_dump_json(indent=2)))
            issued_credential_id = issued_cred.credential_id

            # 2. Verify Valid Credential
            print(f"\nVerifying credential {issued_credential_id} (should be valid)...")
            verify_status_valid = client.verify(credential_id=issued_credential_id)
            print("[green]Verification response (valid):[/green]")
            print(JSON(verify_status_valid.model_dump_json(indent=2)))
            if not verify_status_valid.is_valid or verify_status_valid.status != "valid":
                print(f"[bold red]Assertion Failed: Expected valid credential, got is_valid={verify_status_valid.is_valid}, status='{verify_status_valid.status}'[/bold red]")
            else:
                print("[green]Assertion Passed: Credential is valid.[/green]")

            # 3. Revoke Credential
            print(f"\nRevoking credential {issued_credential_id}...")
            revoke_status = client.revoke(credential_id=issued_credential_id)
            print("[green]Revocation response:[/green]")
            print(JSON(revoke_status.model_dump_json(indent=2)))
            if revoke_status.status != "revoked":
                 print(f"[bold red]Assertion Failed: Expected revocation status 'revoked', got '{revoke_status.status}'[/bold red]")
            else:
                print("[green]Assertion Passed: Credential revoked.[/green]")

            # 4. Verify Revoked Credential
            print(f"\nVerifying credential {issued_credential_id} (should be revoked)...")
            verify_status_revoked = client.verify(credential_id=issued_credential_id)
            print("[green]Verification response (revoked):[/green]")
            print(JSON(verify_status_revoked.model_dump_json(indent=2)))
            if verify_status_revoked.is_valid or verify_status_revoked.status != "revoked":
                print(f"[bold red]Assertion Failed: Expected revoked credential, got is_valid={verify_status_revoked.is_valid}, status='{verify_status_revoked.status}'[/bold red]")
            else:
                print("[green]Assertion Passed: Credential is revoked.[/green]")

        except (APIError, NetworkError, DeepSecureClientError) as e:
            print(f"[bold red]Error during Core Vault Operations test: {type(e).__name__} - {e}[/bold red]")

        # --- Phase 3: Agent Operations (Part 2: Rotate Key & Verify) ---
        print(f"\n--- Testing Phase 3: Agent Operations (Rotate Key for {TEST_AGENT_ID}) ---")
        try:
            print("Generating new key pair for rotation...")
            new_key_pair_for_rotation = _generate_ephemeral_keys()
            new_public_key_b64 = new_key_pair_for_rotation.public_key_b64
            print(f"New public key for rotation: {new_public_key_b64}")

            print(f"Rotating key for agent: {TEST_AGENT_ID}")
            rotation_response = client.rotate(agent_id=TEST_AGENT_ID, new_public_key_b64=new_public_key_b64)
            print("[green]Rotation response (expecting 204 No Content, client returns empty model or None):[/green]")
            if rotation_response:
                print(JSON(rotation_response.model_dump_json(indent=2)))
            else:
                print("Rotation call returned None (expected for 204 No Content if model can't be empty-instantiated).")
            print("[green]Agent key rotation call completed.[/green]")
            
            print(f"\nFetching details for agent {TEST_AGENT_ID} after rotation...")
            agent_details_after_rotation = client.get_agent_details(agent_id=TEST_AGENT_ID)
            print("[green]Agent details after rotation:[/green]")
            print(JSON(agent_details_after_rotation.model_dump_json(indent=2)))
            if agent_details_after_rotation.public_key == new_public_key_b64:
                print("[green]Assertion Passed: Agent public key successfully rotated.[/green]")
            else:
                print(f"[bold red]Assertion Failed: Agent public key not rotated. Expected '{new_public_key_b64}', Got '{agent_details_after_rotation.public_key}'[/bold red]")

        except (APIError, NetworkError, DeepSecureClientError) as e:
            print(f"[bold red]Error during Agent Key Rotation test: {type(e).__name__} - {e}[/bold red]")

        # --- Error Handling Simulation Tests (Optional) ---
        print("\n--- Simulating Error Conditions ---")
        # Test NotFoundError for agent details
        print("Attempting to get details for a non-existent agent...")
        try:
            client.get_agent_details(agent_id="agent_does_not_exist_XYZ123")
        except NotFoundError as e:
            print(f"[green]Successfully caught NotFoundError (non-existent agent): {e}[/green]")
        except (APIError, NetworkError, DeepSecureClientError) as e:
            print(f"[yellow]Caught other error during non-existent agent test: {type(e).__name__} - {e}[/yellow]")

        # Test AuthenticationError (requires a client with a bad token)
        # print("\nAttempting call with a bad API token...")
        # try:
        #     if client.credservice_url:
        #         bad_token_client = VaultClient(credservice_url=client.credservice_url, api_token="deliberately_bad_token_string_value_test123")
        #         bad_token_client.get_agent_details(agent_id=TEST_AGENT_ID) # Any call would do
        #     else:
        #         print("[yellow]Skipping bad token test: credservice_url not available.[/yellow]")
        # except AuthenticationError as e:
        #     print(f"[green]Successfully caught AuthenticationError (bad token): {e}[/green]")
        # except (APIError, NetworkError, DeepSecureClientError) as e:
        #     print(f"[yellow]Caught other error during bad token test: {type(e).__name__} - {e}[/yellow]")

        # Test NetworkError (Timeout)
        # print("\nAttempting call that should time out...")
        # try:
        #     timeout_client = VaultClient(credservice_url="http://10.255.255.1", api_token="dummy_token_timeout", timeout=1)
        #     timeout_client.get_agent_details(agent_id="any_agent_for_timeout")
        # except NetworkError as e:
        #     if "timed out" in str(e).lower() or (e.original_exception and "timeout" in str(e.original_exception).lower()):
        #         print(f"[green]Successfully caught NetworkError (Timeout): {e}[/green]")
        #     else:
        #         print(f"[yellow]Caught NetworkError (expected Timeout, got: {e.original_exception}): {e}[/yellow]")
        # except (APIError, DeepSecureClientError) as e:
        #      print(f"[yellow]Caught other error during timeout test: {type(e).__name__} - {e}[/yellow]")

    except DeepSecureClientError as e: # Catches client init errors or other generic client issues
        print(f"\n[bold red]VaultClient operational error: {type(e).__name__} - {e}[/bold red]")
    except Exception as e:
        print(f"\n[bold red]An unexpected error occurred in the test script: {type(e).__name__} - {e}[/bold red]")

    print("\nVaultClient Test Script Finished.") 