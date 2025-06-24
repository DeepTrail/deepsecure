"""
Resource manager for Agent operations.
"""
import time
from typing import Optional, List

from .agent import Agent

# Low-level clients and managers
from deepsecure.core.identity_manager import identity_manager
from deepsecure.core.agent_client import client as agent_api_client

# Forward reference for type hinting the client
if False:
    from deepsecure.sdk import DeepSecure

class Agents:
    def __init__(self, client: "DeepSecure"):
        self._client = client

    def create(self, name: str, description: Optional[str] = None) -> Agent:
        """
        Creates a new agent, registers it, and stores its identity locally.

        This process is automated to provide a simple, one-call method for
        creating and configuring a new agent.

        Args:
            name: A human-readable name for the agent.
            description: An optional description for the agent.

        Returns:
            An Agent object representing the newly created agent.
        """
        # 1. Generate a new key pair for the agent.
        key_pair = identity_manager.generate_ed25519_keypair_raw_b64()
        public_key = key_pair["public_key"]
        private_key = key_pair["private_key"]

        # 2. Register the agent with the DeepSecure backend.
        registration_data = agent_api_client.register_agent(
            public_key=public_key,
            name=name,
            description=description
        )
        agent_id = registration_data["agent_id"]

        # 3. Securely store the agent's identity locally.
        identity_manager.persist_generated_identity(
            agent_id=agent_id,
            public_key_b64=public_key,
            private_key_b64=private_key,
            name=name,
            created_at_timestamp=int(time.time())
        )

        # 4. Return an Agent resource object.
        # The registration_data from the backend is used to populate the Agent object
        return Agent(client_ref=self, agent_data=registration_data)

    def list(self) -> List[Agent]:
        """
        Lists all available agents.

        Returns:
            A list of Agent objects.
        """
        # Call the low-level client to get the list of agents
        agent_list_response = agent_api_client.list_agents()
        
        # The response is a dict with an 'agents' key containing the list
        agents_data = agent_list_response.get("agents", [])
        
        # Convert the raw data into a list of high-level Agent objects
        return [Agent(client_ref=self, agent_data=data) for data in agents_data]

    def get(self, agent_id: str) -> Optional[Agent]:
        """
        Retrieves a single agent by its ID.

        Args:
            agent_id: The ID of the agent to retrieve.

        Returns:
            An Agent object if found, otherwise None.
        """
        # Call the low-level client to get the agent details
        agent_data = agent_api_client.describe_agent(agent_id=agent_id)
        
        if agent_data:
            return Agent(client_ref=self, agent_data=agent_data)
        
        return None

    def delete(self, agent_id: str) -> bool:
        """
        Deletes an agent.

        This performs a 'soft delete' on the backend (deactivates the agent)
        and permanently deletes the agent's local identity, including its
        private key.

        Args:
            agent_id: The ID of the agent to delete.

        Returns:
            True if the agent was successfully deleted, False otherwise.
        """
        try:
            # First, attempt to deactivate the agent on the backend
            agent_api_client.delete_agent(agent_id=agent_id)
            
            # If successful, purge the local identity
            identity_manager.delete_identity(agent_id=agent_id)
            
            return True
        except Exception as e:
            # TODO: Add more specific exception handling
            print(f"Error deleting agent {agent_id}: {e}")
            return False

    # Other methods like delete() will go here. 