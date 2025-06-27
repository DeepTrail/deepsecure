"""
Example 01: Create an Agent and Fetch a Secret

This example demonstrates the basic workflow of using the DeepSecure SDK
to create a new agent identity and then use that agent to securely fetch
a secret from the vault.

This is the "Hello World" example for DeepSecure - it shows the core
concepts in the simplest possible way.
"""
import os
import sys

# Add the project root to the Python path for development
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import deepsecure
from deepsecure.exceptions import DeepSecureError

def main():
    """
    Main function demonstrating the basic DeepSecure workflow.
    """
    print("--- DeepSecure SDK: Basic Agent & Secret Example ---")
    print()
    
    try:
        # --- 1. Initialize the DeepSecure Client ---
        # The client automatically loads configuration from:
        # - Environment variables (DEEPSECURE_CREDSERVICE_URL, DEEPSECURE_CREDSERVICE_API_TOKEN)
        # - CLI configuration (`deepsecure configure`)
        print("🚀 Step 1: Initializing DeepSecure client...")
        client = deepsecure.Client()
        print("   ✅ Client initialized successfully.")
        print(f"   📡 Connected to: {client.base_url}")

        # --- 2. Create or Get an Agent Identity ---
        # This will create a new agent identity if one doesn't exist locally,
        # including generating cryptographic keys and registering with the backend.
        agent_name = "hello-world-agent"
        print(f"\\n🤖 Step 2: Creating agent identity '{agent_name}'...")
        
        agent = client.agent(agent_name, auto_create=True)
        print(f"   ✅ Agent ready: {agent.id}")
        print(f"   📛 Agent name: {agent.name}")

        # --- 3. Store a Test Secret (Optional - for demonstration) ---
        # In real scenarios, secrets are typically stored by administrators
        # or during setup. Here we'll store one for demonstration.
        secret_name = "example-api-key"
        print(f"\\n🔐 Step 3: Ensuring test secret '{secret_name}' exists...")
        
        try:
            # Try to fetch the secret first to see if it exists
            test_secret = client.get_secret(secret_name, agent_name=agent.name)
            print(f"   ✅ Secret '{secret_name}' already exists.")
        except DeepSecureError:
            # Secret doesn't exist, so store a demo one
            print(f"   📝 Secret '{secret_name}' not found. Creating demo secret...")
            demo_secret_value = "demo-api-key-12345"
            client.store_secret(secret_name, demo_secret_value)
            print(f"   ✅ Demo secret '{secret_name}' stored successfully.")

        # --- 4. Fetch the Secret Securely ---
        # This demonstrates the core value proposition: secure, just-in-time
        # secret retrieval using the agent's identity.
        print(f"\\n🔑 Step 4: Fetching secret '{secret_name}' using agent identity...")
        
        secret = client.get_secret(secret_name, agent_name=agent.name)
        print(f"   ✅ Secret fetched successfully!")
        print(f"   📋 Secret name: {secret.name}")
        print(f"   ⏰ Expires at: {secret.expires_at.isoformat()}")
        print(f"   🔒 Value: '{secret.value[:8]}...' (truncated for security)")

        # --- 5. Demonstrate Secure Usage ---
        # Show how the secret object prevents accidental exposure
        print(f"\\n🛡️  Step 5: Security demonstration...")
        print(f"   📄 Secret object display: {secret}")
        print(f"   💡 Notice: The secret value is hidden in the object representation")
        print(f"   🔓 Access value when needed: secret.value -> '{secret.value}'")

        # --- 6. Example Usage in Application ---
        print(f"\\n🔧 Step 6: Example application usage...")
        print("   In a real application, you would use the secret like this:")
        print("   ```python")
        print("   import requests")
        print("   api_key = secret.value")
        print("   response = requests.get('https://api.example.com/data',")
        print("                          headers={'Authorization': f'Bearer {api_key}'})")
        print("   ```")

        print("\\n" + "="*60)
        print("✅ EXAMPLE COMPLETED SUCCESSFULLY!")
        print("="*60)
        print()
        print("🎉 What you just accomplished:")
        print("   • Created a unique agent identity with cryptographic keys")
        print("   • Registered the agent with the DeepSecure backend")
        print("   • Stored a secret in the secure vault")
        print("   • Fetched the secret using the agent's identity")
        print("   • Demonstrated secure secret handling patterns")

    except DeepSecureError as e:
        print(f"\\n❌ DeepSecure Error: {e}")
        print()
        print("🔧 Troubleshooting steps:")
        print("   1. Ensure the credservice backend is running:")
        print("      docker compose -f credservice/docker-compose.yml up -d")
        print("   2. Configure the CLI:")
        print("      deepsecure configure")
        print("   3. Check the service status:")
        print("      curl http://127.0.0.1:8001/health")
        
    except Exception as e:
        print(f"\\n❌ Unexpected Error: {e}")
        print("   This might indicate a configuration or environment issue.")


if __name__ == "__main__":
    main() 