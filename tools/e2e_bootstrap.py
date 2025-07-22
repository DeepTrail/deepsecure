# tests/e2e_bootstrap_script.py
import os
import json
from deepsecure.client import DeepSecure

def main():
    """
    This script simulates an agent in a production environment attempting
    to bootstrap its identity.
    It initializes the DeepSecure client, which automatically detects the
    environment (K8s, AWS, or local) and tries to get an identity.
    The resulting identity (or an error) is printed to stdout as JSON.
    """
    try:
        # In a real agent, you might pass the agent_id if it's known
        # via a Downward API or similar mechanism.
        agent_id_to_find = os.environ.get("DEEPSECURE_AGENT_ID")
        
        # The DeepSecure client automatically handles the environment
        # detection and identity provider chaining.
        client = DeepSecure(
            # In a real scenario, this would point to the production service
            base_url="http://localhost:8000",
            agent_id=agent_id_to_find,
            silent_mode=True,
        )
        
        # The get_identity() call triggers the bootstrap process
        identity = client.get_identity()
        
        if identity:
            # For testing, we serialize the dataclass to JSON
            print(json.dumps({
                "status": "success",
                "agent_id": identity.agent_id,
                "public_key_b64": identity.public_key_b64,
                "provider_name": identity.provider_name,
            }))
        else:
            print(json.dumps({
                "status": "error",
                "message": "Failed to acquire identity. No provider succeeded.",
            }))
            
    except Exception as e:
        print(json.dumps({
            "status": "error",
            "message": f"An unexpected exception occurred: {e}",
        }))

if __name__ == "__main__":
    main() 