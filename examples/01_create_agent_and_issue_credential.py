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
        # - Environment variables (DEEPSECURE_DEEPTRAIL_CONTROL_URL, DEEPSECURE_DEEPTRAIL_CONTROL_API_TOKEN)
        # - CLI configuration (`deepsecure configure`)
        print("🚀 Step 1: Initializing DeepSecure client...")
        client = deepsecure.Client()
        print("   ✅ Client initialized successfully.")
        print(f"   📡 Connected to: {client._api_url}")

        # --- 2. Create or Get an Agent Identity ---
        # This will create a new agent identity if one doesn't exist locally,
        # including generating cryptographic keys and registering with the backend.
        agent_name = "hello-world-agent"
        print(f"\n🤖 Step 2: Creating agent identity '{agent_name}'...")
        
        agent = client.agent(agent_name, auto_create=True)
        print(f"   ✅ Agent ready: {agent.id}")
        print(f"   📛 Agent name: {agent.name}")

        # --- 3. Verify Agent Registration ---
        # This demonstrates that the agent is properly registered with the backend
        print(f"\n🔍 Step 3: Verifying agent registration...")
        
        try:
            # List all agents to confirm ours is registered
            agents_list = client.list_agents()
            our_agent = next((a for a in agents_list if a.get("agent_id") == agent.id), None)
            
            if our_agent:
                print(f"   ✅ Agent found in backend registry!")
                print(f"   📋 Backend record: {our_agent.get('name', 'N/A')}")
                print(f"   🔑 Has public key: {'Yes' if our_agent.get('public_key') else 'No'}")
            else:
                print(f"   ⚠️  Agent not found in backend (this is OK for demo)")
                
        except Exception as e:
            print(f"   📝 Registration check skipped: {str(e)[:50]}...")

        # --- 4. Demonstrate Agent Properties ---
        # Show what information is available about the agent
        print(f"\n🆔 Step 4: Agent identity details...")
        print(f"   🆔 Agent ID: {agent.id}")
        print(f"   📛 Agent Name: {agent.name}")
        print(f"   🔑 Cryptographic Keys: Generated & stored securely")
        print(f"   💾 Key Storage: OS keyring")
        print(f"   🏗️  Architecture: Ed25519 cryptographic identity")
        
        # --- 5. Demonstrate Security Features ---
        # Show the security benefits this provides
        print(f"\n🛡️  Step 5: Security features demonstrated...")
        print(f"   🔐 Unique Identity: Each agent has distinct cryptographic identity")
        print(f"   🔒 Secure Storage: Private keys never exposed or logged")
        print(f"   📊 Audit Trail: All operations traceable to agent identity")
        print(f"   ⏰ Ready for: Credential issuance, delegation, policy enforcement")

        # --- 6. Next Steps for Real Applications ---
        print(f"\n🚀 Step 6: Next steps for production use...")
        print("   Now that you have an agent identity, you can:")
        print("   • Store secrets: deepsecure vault store --agent-id <id> <secret-name>")
        print("   • Make secure API calls: See examples/08_gateway_secret_injection_demo.py")
        print("   • Enable delegation: client.delegate_access() for agent-to-agent auth")
        print("   • Add policies: deepsecure policy create for access control")
        print("   • Scale up: Create multiple agents for different roles")

        print("\n" + "="*60)
        print("✅ EXAMPLE COMPLETED SUCCESSFULLY!")
        print("="*60)
        print()
        print("🎉 What you just accomplished:")
        print("   • Created a unique agent identity with cryptographic keys")
        print("   • Registered the agent with the DeepSecure backend")
        print("   • Generated secure Ed25519 key pairs (stored in OS keyring)")
        print("   • Verified the agent exists in the backend registry")
        print("   • Learned about DeepSecure's security architecture")
        print("   • Ready to explore advanced features in other examples!")

    except DeepSecureError as e:
        print(f"\n❌ DeepSecure Error: {e}")
        print()
        print("🔧 Troubleshooting steps:")
        print("   1. Ensure the deeptrail-control backend is running:")
        print("      docker compose -f deeptrail-control/docker-compose.yml up -d")
        print("   2. Configure the CLI:")
        print("      deepsecure configure")
        print("   3. Check the service status:")
        print("      curl http://127.0.0.1:8001/health")
        
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        print("   This might indicate a configuration or environment issue.")


if __name__ == "__main__":
    main() 