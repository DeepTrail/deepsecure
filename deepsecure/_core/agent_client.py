# deepsecure/core/agent_client.py
from typing import Optional, Dict, List, Any, TYPE_CHECKING
import logging
import httpx

from .base_client import BaseClient # Inherit from BaseClient
from .. import utils # For logging or other utilities if needed
from ..exceptions import ApiError # For raising specific API errors
from ..exceptions import DeepSecureClientError # For raising specific client errors
from .config import get_effective_deeptrail_control_url
from ..resources.agent import Agent
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

if TYPE_CHECKING:
    from .base_client import BaseClient as BaseClientType

logger = logging.getLogger(__name__)

class AgentClient(BaseClient):
    """Client for interacting with the Agent Management API endpoints in deeptrail-control."""

    def __init__(self, api_url: Optional[str] = None, silent_mode: bool = False):
        super().__init__(silent_mode=silent_mode) # Pass silent_mode to BaseClient
        # self.service_name = "agents" # Or similar if BaseClient uses it for paths
        self.api_prefix = "/api/v1/agents" # Define the common API prefix for agents
        self._api_url = api_url or get_effective_deeptrail_control_url()
        self._parent_client: Optional['BaseClientType'] = None  # Will be set by parent Client

    def _request(self, method: str, path: str, **kwargs) -> Any:
        """
        Override _request to use parent client's authentication when available.
        For authenticated requests (like delete_agent), we need to use the parent's auth.
        """
        # Pop is_backend_request from kwargs since it's not needed by the HTTP client
        is_backend_request = kwargs.pop("is_backend_request", False)
        
        # If we have a parent client with authentication, use its _authenticated_request method
        if (self._parent_client and 
            hasattr(self._parent_client, '_authenticated_request') and
            hasattr(self._parent_client, '_identity_manager')):
            
            # For authenticated endpoints, we need an agent_id
            # We'll get it from the path (e.g., "/api/v1/agents/{agent_id}")
            agent_id = None
            if method in ["DELETE", "PUT", "PATCH"] and "/" in path.rstrip("/"):
                # Extract agent_id from path like "/api/v1/agents/agent-123..."
                path_parts = path.strip("/").split("/")
                if len(path_parts) >= 4 and path_parts[-1].startswith("agent-"):
                    agent_id = path_parts[-1]
            
            if agent_id:
                # Use parent's authenticated request
                return self._parent_client._authenticated_request(
                    method=method, 
                    path=path, 
                    agent_id=agent_id,
                    **kwargs
                )
        
        # Fall back to the regular BaseClient._request for unauthenticated requests
        return super()._request(method, path, **kwargs)

    def create(self, name: str, description: Optional[str] = None) -> Agent:
        """
        Creates a new agent, handling key generation and storage.
        This is the primary user-facing method for agent creation.
        """
        # This is a bit of a circular dependency, but the IdentityManager
        # is the source of truth for key operations.
        # We create a temporary one here to generate keys.
        from .identity_manager import IdentityManager
        identity_manager = IdentityManager(api_client=self, silent_mode=self._silent_mode)

        # 1. Generate a new key pair for the agent
        keys = identity_manager.generate_ed25519_keypair_raw_b64()
        public_key_b64 = keys["public_key"]
        private_key_b64 = keys["private_key"]

        # 2. Call the unauthenticated endpoint to create the agent
        agent_data = self.create_agent_unauthenticated(
            public_key=public_key_b64, name=name
        )
        agent_id = agent_data["agent_id"]

        # 3. Securely store the private key locally
        identity_manager.store_private_key_directly(agent_id, private_key_b64)

        # 4. Return a rich Agent resource object
        agent_data_dict = {
            "agent_id": agent_id,
            "name": agent_data.get("name"),
            "public_key": agent_data.get("publicKey"),  # API returns camelCase
            "created_at": agent_data.get("created_at"),
            "status": agent_data.get("status"),
            "description": agent_data.get("description")
        }
        
        return Agent(
            client_ref=self,
            agent_data=agent_data_dict
        )

    def create_agent_unauthenticated(self, public_key: str, name: Optional[str]) -> Dict[str, Any]:
        """
        Creates a new agent via a standardized unauthenticated API call.
        This is used for the initial agent creation from the CLI.
        """
        if not self._api_url:
            raise DeepSecureClientError("Deeptrail Control URL is not configured.")

        payload = {
            "public_key": public_key,
            "name": name,
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        try:
            # Use standardized unauthenticated request method for consistent routing
            response = self._unauthenticated_request(
                "POST",
                f"{self.api_prefix}/",
                json=payload
            )
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to create agent via unauthenticated call. Status: {e.response.status_code}, Detail: {e.response.text}")
            raise ApiError(f"Failed to create agent: {e.response.text}", status_code=e.response.status_code) from e
        except Exception as e:
            logger.error(f"An unexpected error occurred during unauthenticated agent creation: {e}")
            raise DeepSecureClientError(f"An unexpected error occurred: {e}") from e

    def register_agent(self, public_key: str, name: Optional[str], description: Optional[str], agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Register a new agent with the backend service.

        Args:
            public_key: Base64 encoded string of the raw Ed25519 public key.
            name: Optional human-readable name for the agent.
            description: Optional description for the agent.
            agent_id: Optional agent ID. If provided, the backend will use this ID.

        Returns:
            A dictionary representing the registered agent's details from the backend.

        Raises:
            ApiError: If the backend API call fails.
        """
        payload = {
            "public_key": public_key,
            "name": name,
            "description": description,
        }
        
        if agent_id:
            payload["agent_id"] = agent_id
        # Remove None values from payload if backend expects them to be absent
        payload = {k: v for k, v in payload.items() if v is not None}
        
        pk_preview = f"{public_key[:20]}..." if public_key else "None"
        logger.info(f"Registering agent with backend. Name: {name}, PK starts with: {pk_preview}")
        try:
            response_data = self._request(
                method="POST",
                path=f"{self.api_prefix}/", # Path for POST is typically the collection root
                data=payload,
                is_backend_request=True
            )
            logger.info(f"Agent registered successfully. Agent ID: {response_data.get('agent_id')}")
            return response_data
        except ApiError as e:
            logger.error(f"Failed to register agent. Status: {e.status_code}, Detail: {e.message}")
            raise # Re-raise the ApiError caught by _request or _handle_response

    def list_agents(self, skip: int = 0, limit: int = 100) -> Dict[str, Any]: # Return type matches AgentList schema structure
        """List agents from the backend service with pagination.

        Args:
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            A dictionary containing a list of agent details and a total count, 
            matching the structure of deeptrail-control.schemas.agent.AgentList.

        Raises:
            ApiError: If the backend API call fails.
        """
        params = {"skip": skip, "limit": limit}
        logger.info(f"Listing agents from backend. Skip: {skip}, Limit: {limit}")
        
        # This needs to be unauthenticated for the test fixture to work.
        if not self._api_url:
            raise DeepSecureClientError("Deeptrail Control URL is not configured.")

        try:
            # Use standardized unauthenticated request method for consistent routing
            response = self._unauthenticated_request(
                "GET",
                f"{self.api_prefix}/",
                params=params
            )
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to list agents via unauthenticated call. Status: {e.response.status_code}, Detail: {e.response.text}")
            raise ApiError(f"Failed to list agents: {e.response.text}", status_code=e.response.status_code) from e
        except Exception as e:
            logger.error(f"An unexpected error occurred during unauthenticated agent list: {e}")
            raise DeepSecureClientError(f"An unexpected error occurred: {e}") from e

    def get_by_name(self, name: str, auto_create: bool = False) -> "Agent":
        """
        Retrieves an agent by its unique name.

        Args:
            name: The name of the agent to retrieve.
            auto_create: If True, creates the agent if it does not exist.

        Returns:
            An Agent resource object.

        Raises:
            DeepSecureClientError: If the agent is not found and auto_create is False.
        """
        all_agents_response = self.list_agents(limit=500) # Backend limit is 500
        agents = all_agents_response.get("agents", [])
        
        found_agent = next((agent for agent in agents if agent.get("name") == name), None)

        if found_agent:
            return Agent(client_ref=self, agent_data=found_agent)

        if auto_create:
            # Use the dependency-injected identity manager from BaseClient
            keys = self._identity_manager.generate_ed25519_keypair_raw_b64()
            new_agent_data = self.create_agent_unauthenticated(public_key=keys['public_key'], name=name)
            # Store the new key in the keyring
            self._identity_manager.store_private_key_directly(new_agent_data['agent_id'], keys['private_key'])
            return Agent(client_ref=self, agent_data=new_agent_data)
        
        raise DeepSecureClientError(f"Agent with name '{name}' not found.")

    def describe_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Describe a specific agent by its ID from the backend service.

        Args:
            agent_id: The unique identifier of the agent.

        Returns:
            A dictionary representing the agent's details, or None if not found (404).

        Raises:
            ApiError: If the backend API call fails for reasons other than 404.
        """
        logger.info(f"Describing agent with ID: {agent_id} from backend.")
        try:
            response_data = self._request(
                method="GET",
                path=f"{self.api_prefix}/{agent_id}",
                is_backend_request=True
            )
            logger.info(f"Successfully fetched details for agent ID: {agent_id}")
            return response_data
        except ApiError as e:
            if e.status_code == 404:
                logger.warning(f"Agent with ID {agent_id} not found in backend.")
                return None # Return None for 404 as per common client patterns
            logger.error(f"Failed to describe agent {agent_id}. Status: {e.status_code}, Detail: {e.message}")
            raise # Re-raise for other errors

    def update_agent(self, agent_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing agent on the backend service.

        Args:
            agent_id: The ID of the agent to update.
            update_data: A dictionary containing fields to update (e.g., name, description, status).

        Returns:
            A dictionary representing the updated agent's details.

        Raises:
            ApiError: If the API call fails.
        """
        logger.info(f"Updating agent {agent_id} with data: {update_data}")
        try:
            response_data = self._request(
                method="PATCH", # Using PATCH for partial updates
                path=f"{self.api_prefix}/{agent_id}",
                data=update_data,
                is_backend_request=True
            )
            logger.info(f"Successfully updated agent {agent_id}.")
            return response_data
        except ApiError as e:
            logger.error(f"Failed to update agent {agent_id}. Status: {e.status_code}, Detail: {e.message}")
            raise

    def delete_agent(self, agent_id: str) -> Dict[str, Any]: # Changed return type to Dict
        """Deactivates an agent (soft delete) via the backend service.

        Args:
            agent_id: The unique identifier of the agent to deactivate.
            
        Returns:
            A dictionary representing the deactivated agent's details from the backend.

        Raises:
            ApiError: If the backend API call fails (e.g., not 404 or 200).
        """
        logger.info(f"Deactivating agent (soft delete) with ID: {agent_id} via backend.")
        
        # Agent deletion should go directly to the control plane, not through the gateway
        if not self._api_url:
            raise DeepSecureClientError("Deeptrail Control URL is not configured.")

        url = f"{self._api_url.rstrip('/')}{self.api_prefix}/{agent_id}"
        
        try:
            # Use authentication if parent client is available
            if (self._parent_client and 
                hasattr(self._parent_client, '_identity_manager') and
                hasattr(self._parent_client, 'get_access_token')):
                
                # Get JWT token for authentication
                jwt_token = self._parent_client.get_access_token(agent_id)
                headers = {"Authorization": f"Bearer {jwt_token}"}
                
                with httpx.Client() as client:
                    response = client.delete(url, headers=headers)
                    response.raise_for_status()
                    response_data = response.json() if response.content else {"success": True}
                    
                    # Expecting the agent object directly from the response if successful (2xx)
                    if response_data and response_data.get("agent_id") == agent_id:
                        logger.info(f"Agent {agent_id} successfully deactivated by backend. Status: {response_data.get('status')}")
                        return response_data # Return the full agent object
                    else:
                        logger.info(f"Agent {agent_id} successfully deleted.")
                        return response_data
                        
            else:
                # Fallback to unauthenticated request (shouldn't happen for delete)
                with httpx.Client() as client:
                    response = client.delete(url)
                    response.raise_for_status()
                    response_data = response.json() if response.content else {"success": True}
                    logger.info(f"Successfully deleted agent {agent_id}.")
                    return response_data
                    
        except httpx.HTTPStatusError as e:
            logger.error(f"API error during deactivation of agent {agent_id}. Status: {e.response.status_code}, Detail: {e.response.text}")
            raise ApiError(f"Failed to delete agent: {e.response.text}", status_code=e.response.status_code) from e
        except Exception as e:
            logger.error(f"An unexpected error occurred during agent deletion: {e}")
            raise DeepSecureClientError(f"An unexpected error occurred: {e}") from e

    def bootstrap_kubernetes(self, k8s_token: str, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Bootstrap an agent's identity using a Kubernetes Service Account Token.
        Enhanced to work with the new backend implementation with proper error handling and keyring storage.
        """
        try:
            # Use the enhanced base client method
            response = super().bootstrap_kubernetes(k8s_token, agent_id)
            
            # Parse the response using the new BootstrapResponse schema
            identity_data = response.json()
            
            # Validate required fields from BootstrapResponse
            required_fields = ["agent_id", "private_key_b64", "public_key_b64"]
            missing_fields = [field for field in required_fields if field not in identity_data]
            
            if missing_fields:
                raise DeepSecureClientError(
                    f"Incomplete bootstrap response from server. Missing fields: {missing_fields}"
                )
            
            new_agent_id = identity_data["agent_id"]
            private_key_b64 = identity_data["private_key_b64"]
            public_key_b64 = identity_data["public_key_b64"]
            
            # Securely store the new private key in the local keyring
            if new_agent_id and private_key_b64:
                from .identity_manager import IdentityManager
                identity_manager = IdentityManager(api_client=self, silent_mode=self._silent_mode)
                identity_manager.store_private_key_directly(new_agent_id, private_key_b64)
                
                if not self._silent_mode:
                    logger.info(f"Successfully bootstrapped Kubernetes agent {new_agent_id} and stored private key in keyring")
            
            return {
                "agent_id": new_agent_id,
                "public_key": public_key_b64,
                "bootstrap_platform": "kubernetes",
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Failed to bootstrap Kubernetes identity: {e}")
            raise DeepSecureClientError(f"Kubernetes bootstrap failed: {e}") from e

    def bootstrap_aws(self, iam_token: str, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Bootstrap an agent's identity using an AWS STS token.
        Enhanced to work with the new backend implementation with proper error handling and keyring storage.
        """
        try:
            # Use the enhanced base client method
            response = super().bootstrap_aws(iam_token, agent_id)
            
            # Parse the response using the new BootstrapResponse schema
            identity_data = response.json()
            
            # Validate required fields from BootstrapResponse
            required_fields = ["agent_id", "private_key_b64", "public_key_b64"]
            missing_fields = [field for field in required_fields if field not in identity_data]
            
            if missing_fields:
                raise DeepSecureClientError(
                    f"Incomplete bootstrap response from server. Missing fields: {missing_fields}"
                )
            
            new_agent_id = identity_data["agent_id"]
            private_key_b64 = identity_data["private_key_b64"]
            public_key_b64 = identity_data["public_key_b64"]
            
            # Securely store the new private key in the local keyring
            if new_agent_id and private_key_b64:
                from .identity_manager import IdentityManager
                identity_manager = IdentityManager(api_client=self, silent_mode=self._silent_mode)
                identity_manager.store_private_key_directly(new_agent_id, private_key_b64)
                
                if not self._silent_mode:
                    logger.info(f"Successfully bootstrapped AWS agent {new_agent_id} and stored private key in keyring")
            
            return {
                "agent_id": new_agent_id,
                "public_key": public_key_b64,
                "bootstrap_platform": "aws",
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Failed to bootstrap AWS identity: {e}")
            raise DeepSecureClientError(f"AWS bootstrap failed: {e}") from e

    def bootstrap_azure(self, imds_token: str, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Bootstrap an agent's identity using an Azure Managed Identity token.
        New method for Azure platform support.
        """
        try:
            # Use the enhanced base client method
            response = super().bootstrap_azure(imds_token, agent_id)
            
            # Parse the response using the new BootstrapResponse schema
            identity_data = response.json()
            
            # Validate required fields from BootstrapResponse
            required_fields = ["agent_id", "private_key_b64", "public_key_b64"]
            missing_fields = [field for field in required_fields if field not in identity_data]
            
            if missing_fields:
                raise DeepSecureClientError(
                    f"Incomplete bootstrap response from server. Missing fields: {missing_fields}"
                )
            
            new_agent_id = identity_data["agent_id"]
            private_key_b64 = identity_data["private_key_b64"]
            public_key_b64 = identity_data["public_key_b64"]
            
            # Securely store the new private key in the local keyring
            if new_agent_id and private_key_b64:
                from .identity_manager import IdentityManager
                identity_manager = IdentityManager(api_client=self, silent_mode=self._silent_mode)
                identity_manager.store_private_key_directly(new_agent_id, private_key_b64)
                
                if not self._silent_mode:
                    logger.info(f"Successfully bootstrapped Azure agent {new_agent_id} and stored private key in keyring")
            
            return {
                "agent_id": new_agent_id,
                "public_key": public_key_b64,
                "bootstrap_platform": "azure",
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Failed to bootstrap Azure identity: {e}")
            raise DeepSecureClientError(f"Azure bootstrap failed: {e}") from e

    def bootstrap_docker(self, runtime_token: str, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Bootstrap an agent's identity using a Docker container runtime token.
        New method for Docker platform support.
        """
        try:
            # Use the enhanced base client method  
            response = super().bootstrap_docker(runtime_token, agent_id)
            
            # Parse the response using the new BootstrapResponse schema
            identity_data = response.json()
            
            # Validate required fields from BootstrapResponse
            required_fields = ["agent_id", "private_key_b64", "public_key_b64"]
            missing_fields = [field for field in required_fields if field not in identity_data]
            
            if missing_fields:
                raise DeepSecureClientError(
                    f"Incomplete bootstrap response from server. Missing fields: {missing_fields}"
                )
            
            new_agent_id = identity_data["agent_id"]
            private_key_b64 = identity_data["private_key_b64"]
            public_key_b64 = identity_data["public_key_b64"]
            
            # Securely store the new private key in the local keyring
            if new_agent_id and private_key_b64:
                from .identity_manager import IdentityManager
                identity_manager = IdentityManager(api_client=self, silent_mode=self._silent_mode)
                identity_manager.store_private_key_directly(new_agent_id, private_key_b64)
                
                if not self._silent_mode:
                    logger.info(f"Successfully bootstrapped Docker agent {new_agent_id} and stored private key in keyring")
            
            return {
                "agent_id": new_agent_id,
                "public_key": public_key_b64,
                "bootstrap_platform": "docker",
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Failed to bootstrap Docker identity: {e}")
            raise DeepSecureClientError(f"Docker bootstrap failed: {e}") from e

    def get(self, agent_id: str) -> "Agent":
        """
        Retrieves an agent by its ID.
        """
        # Implementation of the get method

# Singleton instance for easy access from command modules
client = AgentClient()

if __name__ == '__main__':
    # Basic test of the placeholder client
    print("--- Testing AgentClient Placeholder ---")
    test_client = AgentClient()

    # Test register
    print("\n1. Registering new agent...")
    reg_info = test_client.register_agent("ssh-ed25519 AAAA...", "TestAgent1", "A test agent for placeholder.")
    print(f"Registered: {reg_info}")
    agent_id_1 = reg_info["agent_id"]

    # Test list
    print("\n2. Listing agents...")
    agents = test_client.list_agents(skip=0, limit=100)
    print(f"Listed agents ({len(agents.get('agents', []))} out of {agents.get('total')} total):")
    for ag in agents.get('agents', []):
        print(f"  - {ag.get('name')} ({ag.get('agent_id')})")

    # Test describe
    print(f"\n3. Describing agent {agent_id_1}...")
    desc_info = test_client.describe_agent(agent_id_1)
    print(f"Described: {desc_info}")
    
    print(f"\n4. Describing a non-existent agent...")
    desc_info_fail = test_client.describe_agent("non-existent-id")
    print(f"Describe non-existent: {desc_info_fail}")

    # Test delete
    print(f"\n5. Deleting agent {agent_id_1}...")
    del_status = test_client.delete_agent(agent_id_1)
    print(f"Deletion status: {del_status}")
    
    print(f"\n6. Deleting a non-deletable agent (mock failure)...")
    del_status_fail = test_client.delete_agent("non-deletable-id")
    print(f"Deletion status (mock failure): {del_status_fail}")
    
    print("\n--- Placeholder Test Complete ---") 