"""
Example 01: Create an Agent and Issue a Credential

This example demonstrates the basic workflow of using the DeepSecure SDK
to create a new agent and then use that agent's identity to issue a
short-lived, scoped credential.
"""
import os
import sys
from typing import Optional
import base64

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from deepsecure.client import Client
from deepsecure.exceptions import DeepSecureClientError
from deepsecure._core.identity_manager import identity_manager
from deepsecure._core.agent_client import client as agent_api_client

def main():
    """
    Main function to run the example.
    """
    # --- 1. Configure the SDK ---
    # The SDK needs to be configured with your API key and the URL of the
    # credential service. For this example, we'll get them from environment
    # variables.
    # In a real application, you might use a more robust configuration system.
    api_key = os.environ.get("DEEPSECURE_API_TOKEN")
    credservice_url = os.environ.get("DEEPSECURE_CREDSERVICE_URL")

    if not api_key or not credservice_url:
        print("Error: Please set the DEEPSECURE_API_TOKEN and DEEPSECURE_CREDSERVICE_URL environment variables.")
        return

    # Initialize the client using the login function
    try:
        client = deepsecure.login(api_key=api_key, base_url=credservice_url)
        print("SDK initialized successfully.")
    except Exception as e:
        print(f"Error initializing SDK: {e}")
        return

    # --- 2. Create a New Agent ---
    # This single call will:
    #   - Generate a new cryptographic key pair for the agent.
    #   - Register the agent with the backend service.
    #   - Securely store the agent's private key in your system's keyring.
    try:
        agent_name = "example-agent-01"
        print(f"Creating a new agent named '{agent_name}'...")
        agent = client.agents.create(name=agent_name, description="An agent created for an example script.")
        print(f"Agent created successfully! Agent ID: {agent.id}")
    except DeepSecureClientError as e:
        print(f"Error creating agent: {e}")
        return

    # --- 3. Issue a Credential ---
    # Now, we can use the agent object to issue a credential.
    # The SDK handles the cryptographic signing process automatically.
    try:
        scope = "database:read"
        print(f"Issuing a credential for agent {agent.id} with scope '{scope}'...")
        credential = agent.issue_credential(scope=scope, ttl=60) # 60-second expiry
        print("Credential issued successfully!")
        print(f"  Credential ID: {credential.id}")
        print(f"  Token: {credential.token[:20]}...")
        print(f"  Expires At: {credential.expires_at}")
    except DeepSecureClientError as e:
        print(f"Error issuing credential: {e}")
        return
        
    # --- 4. Cleanup ---
    # It's good practice to delete agents you no longer need.
    # This will deactivate the agent on the backend and remove its local keys.
    try:
        print(f"Cleaning up by deleting agent {agent.id}...")
        client.agents.delete(agent_id=agent.id)
        print("Agent deleted successfully.")
    except DeepSecureClientError as e:
        print(f"Error deleting agent: {e}")


if __name__ == "__main__":
    main() 