# deepsecure/core/agent_client.py
from typing import Optional, Dict, List, Any
from pathlib import Path
import uuid # For generating mock IDs
import time # For mock timestamps

# Attempt to import utils from the correct relative path
try:
    from .. import utils
except ImportError:
    # This fallback might be needed if running this file directly for testing,
    # though typically it's imported as part of the deepsecure package.
    # A more robust solution would involve path manipulation or ensuring PYTHONPATH is set.
    # For now, we'll assume it's imported correctly within the package.
    # If utils are critical for placeholder to run standalone, this needs refinement.
    class MockUtils:
        def generate_id(self, length=8):
            return str(uuid.uuid4())[:length]
        def format_timestamp(self, ts):
            return str(ts)
        def now_epoch(self):
            return time.time()
        class MockConsole:
            def print(self, msg):
                print(msg)
        console = MockConsole()
    utils = MockUtils()


# from .base_client import BaseClient # If you have a base client for HTTP requests

# class AgentClient(BaseClient): # Example if using a base client
class AgentClient:
    def __init__(self):
        # self.base_url = f"{self.settings.credservice_url}/api/v1/agents" # Example
        # For now, no actual HTTP client initialization is needed for the placeholder
        pass

    def register_agent(self, public_key_pem: str, name: Optional[str], description: Optional[str]) -> Dict[str, Any]:
        """
        Placeholder for registering an agent with the backend.
        """
        utils.console.print(f"[AgentClient-Placeholder] Registering agent: PK starts with {public_key_pem[:30] if public_key_pem else 'N/A'}..., Name: {name}")
        
        # Simulate backend generating an agent_id
        agent_id = f"agent-{utils.generate_id(8)}"
        
        # Simulate fingerprint generation (very basic)
        fingerprint = f"mock:fp:{utils.generate_id(12)}"
        if public_key_pem: # rudimentary check
            fingerprint = f"sha256:{utils.generate_id(8)}" # more "realistic" mock

        response_data = {
            "agent_id": agent_id,
            "name": name,
            "description": description,
            "public_key_fingerprint": fingerprint,
            "created_at": utils.format_timestamp(utils.now_epoch()),
            "message": "Agent registered successfully (placeholder)."
        }
        utils.console.print(f"[AgentClient-Placeholder] Mock response: {response_data}")
        return response_data

    def list_agents(self, local_identities: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        Placeholder for listing agents from the backend and combining with local ones.
        """
        utils.console.print(f"[AgentClient-Placeholder] Listing remote agents...")
        
        # Simulate some remote agents
        remote_agents = [
            {
                "agent_id": f"remote-agent-{utils.generate_id(4)}",
                "name": "RemoteAgentAlpha",
                "public_key_fingerprint": f"mock:fp:remote{utils.generate_id(4)}",
                "status": "active",
                "source": "remote", # To distinguish from local ones if merged
                "created_at": utils.format_timestamp(utils.now_epoch() - 7200) # 2 hours ago
            },
            {
                "agent_id": f"remote-agent-{utils.generate_id(4)}",
                "name": "RemoteAgentBeta",
                "public_key_fingerprint": f"mock:fp:remote{utils.generate_id(4)}",
                "status": "inactive",
                "source": "remote",
                "created_at": utils.format_timestamp(utils.now_epoch() - 36000) # 10 hours ago
            }
        ]
        utils.console.print(f"[AgentClient-Placeholder] Mock remote agents: {remote_agents}")

        all_agents = list(remote_agents) # Make a copy
        if local_identities:
            utils.console.print(f"[AgentClient-Placeholder] Merging {len(local_identities)} local identities.")
            # Ensure local identities have a 'source' field for consistency
            for local_agent in local_identities:
                local_agent['source'] = 'local'
            all_agents.extend(local_identities)
        
        return all_agents

    def describe_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Placeholder for describing a specific agent from the backend.
        """
        utils.console.print(f"[AgentClient-Placeholder] Describing agent: {agent_id}")
        
        # Simulate finding an agent by ID (very basic check)
        if "remote-agent" in agent_id or "agent-" in agent_id: # Crude check for mock IDs
            mock_agent_details = {
                "agent_id": agent_id,
                "name": f"Mock Agent {agent_id.split('-')[-1]}",
                "description": "This is a detailed description from the mock service for this agent.",
                "public_key": "ssh-ed25519 AAAA... (full public key from mock service)",
                "public_key_fingerprint": f"mock:fp:{utils.generate_id(6)}{agent_id[-4:]}",
                "status": "active" if "alpha" in agent_id.lower() or len(agent_id) % 2 == 0 else "inactive", # mock status
                "created_at": utils.format_timestamp(utils.now_epoch() - (len(agent_id) * 1000)), # mock created_at
                "last_seen_at": utils.format_timestamp(utils.now_epoch() - (len(agent_id) * 100)), # mock last_seen
                "metadata": {
                    "custom_info": "some_mock_value",
                    "tags": ["mock", "placeholder"]
                }
            }
            utils.console.print(f"[AgentClient-Placeholder] Mock details for {agent_id}: {mock_agent_details}")
            return mock_agent_details
        
        utils.console.print(f"[AgentClient-Placeholder] Agent {agent_id} not found in mock service.")
        return None


    def delete_agent(self, agent_id: str, revoke_credentials: bool) -> bool:
        """
        Placeholder for deleting an agent from the backend.
        """
        utils.console.print(f"[AgentClient-Placeholder] Deleting agent: {agent_id}, Revoke credentials: {revoke_credentials}")
        
        # Simulate success/failure (e.g., based on agent_id pattern or just always succeed for placeholder)
        if "non-deletable" in agent_id:
            utils.console.print(f"[AgentClient-Placeholder] Mock simulating failure to delete agent {agent_id}.")
            return False 
        
        utils.console.print(f"[AgentClient-Placeholder] Mock simulating successful deletion of agent {agent_id}.")
        return True # Placeholder always succeeds unless specific condition met

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
    agents = test_client.list_agents(local_identities=[{"agent_id": "local-123", "name":"LocalOnlyAgent"}])
    print(f"Listed agents ({len(agents)}):")
    for ag in agents:
        print(f"  - {ag.get('name')} ({ag.get('agent_id')}) - Source: {ag.get('source')}")

    # Test describe
    print(f"\n3. Describing agent {agent_id_1}...")
    desc_info = test_client.describe_agent(agent_id_1)
    print(f"Described: {desc_info}")
    
    print(f"\n4. Describing a non-existent agent...")
    desc_info_fail = test_client.describe_agent("non-existent-id")
    print(f"Describe non-existent: {desc_info_fail}")

    # Test delete
    print(f"\n5. Deleting agent {agent_id_1}...")
    del_status = test_client.delete_agent(agent_id_1, revoke_credentials=True)
    print(f"Deletion status: {del_status}")
    
    print(f"\n6. Deleting a non-deletable agent (mock failure)...")
    del_status_fail = test_client.delete_agent("non-deletable-id", revoke_credentials=True)
    print(f"Deletion status (mock failure): {del_status_fail}")
    
    print("\n--- Placeholder Test Complete ---") 