# deepsecure/core/agent_client.py
from typing import Optional, Dict, List, Any
import logging

from .base_client import BaseClient # Inherit from BaseClient
from .. import utils # For logging or other utilities if needed
from ..exceptions import ApiError # For raising specific API errors

logger = logging.getLogger(__name__)

class AgentClient(BaseClient):
    """Client for interacting with the Agent Management API endpoints in credservice."""

    def __init__(self):
        super().__init__() # Initialize BaseClient
        # self.service_name = "agents" # Or similar if BaseClient uses it for paths
        self.api_prefix = "/api/v1/agents" # Define the common API prefix for agents

    def register_agent(self, public_key: str, name: Optional[str], description: Optional[str]) -> Dict[str, Any]:
        """Register a new agent with the backend service.

        Args:
            public_key: Base64 encoded string of the raw Ed25519 public key.
            name: Optional human-readable name for the agent.
            description: Optional description for the agent.

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
        # Remove None values from payload if backend expects them to be absent
        payload = {k: v for k, v in payload.items() if v is not None}
        
        logger.info(f"Registering agent with backend. Name: {name}, PK starts with: {public_key[:20]}...")
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
            matching the structure of credservice.schemas.agent.AgentList.

        Raises:
            ApiError: If the backend API call fails.
        """
        params = {"skip": skip, "limit": limit}
        logger.info(f"Listing agents from backend. Skip: {skip}, Limit: {limit}")
        try:
            response_data = self._request(
                method="GET",
                path=f"{self.api_prefix}/",
                params=params,
                is_backend_request=True
            )
            # The backend is expected to return a dict like {"agents": [...], "total": ...}
            # Ensure this client method returns what the CLI command expects.
            # The placeholder client returned List[Dict], but actual backend returns AgentList model structure.
            logger.info(f"Successfully fetched {len(response_data.get('agents', []))} agents. Total available: {response_data.get('total')}")
            return response_data 
        except ApiError as e:
            logger.error(f"Failed to list agents. Status: {e.status_code}, Detail: {e.message}")
            raise

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
        try:
            # Backend DELETE /api/v1/agents/{agent_id} now returns 200 OK with the updated agent object.
            response_data = self._request(
                method="DELETE",
                path=f"{self.api_prefix}/{agent_id}",
                is_backend_request=True
            )
            
            # Expecting the agent object directly from _request if successful (2xx)
            if response_data and response_data.get("agent_id") == agent_id:
                logger.info(f"Agent {agent_id} successfully deactivated by backend. Status: {response_data.get('status')}")
                return response_data # Return the full agent object
            else:
                logger.error(f"Agent {agent_id} deactivation attempt returned unexpected data structure: {response_data}")
                # This indicates a mismatch between client expectation and actual successful response structure
                raise ApiError(f"Unexpected response structure after agent deactivation for {agent_id}.", status_code=None)

        except ApiError as e:
            # BaseClient._handle_response raises ApiError for non-2xx. We catch it here.
            # If it was 404, it will be ApiError with status_code=404.
            # The CLI command will decide how to interpret 404 (e.g., agent already gone).
            logger.error(f"API error during deactivation of agent {agent_id}. Status: {e.status_code}, Detail: {e.message}")
            raise # Re-raise for the command layer to handle

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