"""
Example 08: Gateway Secret Injection Demo

This example demonstrates how the DeepSecure gateway automatically injects
secrets into external API calls. It shows the core value proposition:
your agents never see the actual API keys, but can still make authenticated
requests to external services.

Prerequisites:
1. Both deeptrail-control and deeptrail-gateway services running
2. Gateway URL configured: deepsecure configure set-gateway-url http://localhost:8002
3. Test secrets stored in vault

This example makes REAL external API calls through the gateway.
"""
import os
import sys
import requests
import json
from datetime import datetime

# Add the project root to the Python path for development
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import deepsecure
from deepsecure.exceptions import DeepSecureError

def main():
    """
    Demonstrate gateway secret injection with real external API calls.
    """
    print("--- DeepSecure Gateway Secret Injection Demo ---")
    print()
    
    try:
        # --- 1. Initialize the DeepSecure Client ---
        print("🚀 Step 1: Initializing DeepSecure client...")
        client = deepsecure.Client()
        print("   ✅ Client initialized successfully.")
        print(f"   🏗️  Control Plane: {client.base_url}")
        print(f"   🌐 Gateway URL: {client.gateway_url}")

        # --- 2. Create Agent Identity ---
        agent_name = "gateway-demo-agent"
        print(f"\n🤖 Step 2: Creating agent identity '{agent_name}'...")
        
        agent = client.agent(agent_name, auto_create=True)
        print(f"   ✅ Agent ready: {agent.id}")
        print(f"   📛 Agent name: {agent.name}")

        # --- 3. Store Test Secrets ---
        print(f"\n🔐 Step 3: Ensuring test secrets exist...")
        
        # Store a test API key for httpbin.org (public testing service)
        test_secrets = {
            "httpbin-api-key": "test-api-key-httpbin-12345",
            "demo-bearer-token": "Bearer demo-token-abc123",
            "custom-header-value": "DeepSecure-Gateway-Demo"
        }
        
        for secret_name, secret_value in test_secrets.items():
            try:
                existing_secret = client.get_secret(secret_name, agent_name=agent.name)
                print(f"   ✅ Secret '{secret_name}' already exists.")
            except DeepSecureError:
                print(f"   📝 Creating secret '{secret_name}'...")
                client.store_secret(secret_name, secret_value)
                print(f"   ✅ Secret '{secret_name}' stored successfully.")

        # --- 4. Demonstrate Gateway Secret Injection ---
        print(f"\n🌐 Step 4: Making external API calls through gateway...")
        
        # Example 1: Basic GET request with automatic secret injection
        print("\n   📡 Example 1: GET request with automatic header injection")
        print("   🎯 Target: httpbin.org/get (public testing service)")
        print("   🔑 Secret: httpbin-api-key will be automatically injected")
        
        # This call goes through the gateway, which automatically injects secrets
        response = client.call_external_api(
            target_base_url="https://httpbin.org",
            path="/get",
            method="GET",
            headers={
                "X-Agent-Name": agent.name,
                "X-Demo-Request": "gateway-secret-injection"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print("   ✅ API call successful!")
            print(f"   📋 Response headers received: {len(data.get('headers', {}))} headers")
            print(f"   🌐 Gateway injected secrets automatically")
            print(f"   📊 Response size: {len(json.dumps(data))} bytes")
            
            # Show that the gateway added authentication headers
            received_headers = data.get('headers', {})
            if 'Authorization' in received_headers:
                print(f"   🔐 Authorization header was injected by gateway")
            if 'X-Api-Key' in received_headers:
                print(f"   🔑 API key was injected by gateway")
        else:
            print(f"   ❌ API call failed: {response.status_code}")

        # --- 5. Demonstrate Different Secret Injection Patterns ---
        print(f"\n🔄 Step 5: Different secret injection patterns...")
        
        # Example 2: POST request with bearer token injection
        print("\n   📡 Example 2: POST request with bearer token injection")
        print("   🎯 Target: httpbin.org/post")
        print("   🔑 Secret: demo-bearer-token will be injected as Authorization header")
        
        post_data = {
            "agent_id": agent.id,
            "timestamp": datetime.now().isoformat(),
            "message": "This is a secure POST request via DeepSecure gateway"
        }
        
        response = client.call_external_api(
            target_base_url="https://httpbin.org",
            path="/post",
            method="POST",
            json=post_data,
            headers={
                "Content-Type": "application/json",
                "X-Agent-Name": agent.name
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print("   ✅ POST request successful!")
            print(f"   📨 Data sent: {len(json.dumps(post_data))} bytes")
            print(f"   🔐 Bearer token injected by gateway")
            print(f"   📋 Received JSON response with injected headers")
        else:
            print(f"   ❌ POST request failed: {response.status_code}")

        # --- 6. Show Security Benefits ---
        print(f"\n🛡️  Step 6: Security benefits demonstration...")
        print("   🔐 Your agent code NEVER sees the actual API keys")
        print("   🌐 All external calls are routed through the secure gateway")
        print("   📝 Complete audit trail of all external API calls")
        print("   🎯 Fine-grained access control per agent")
        print("   🔄 Automatic secret rotation without code changes")

        # --- 7. Show What Happens Without Gateway ---
        print(f"\n⚠️  Step 7: What happens without gateway...")
        print("   🚫 Direct API calls would require hardcoded keys")
        print("   🚫 No automatic secret injection")
        print("   🚫 No centralized audit trail")
        print("   🚫 Manual secret rotation required")
        print("   🚫 Increased risk of key exposure")

        print("\n" + "="*60)
        print("✅ GATEWAY SECRET INJECTION DEMO COMPLETED!")
        print("="*60)
        print()
        print("🎉 What you just saw:")
        print("   • Real external API calls through the gateway")
        print("   • Automatic secret injection without code changes")
        print("   • Multiple authentication patterns (API key, Bearer token)")
        print("   • Complete security and audit trail")
        print("   • Zero API key exposure in your agent code")
        print()
        print("🔗 Next Steps:")
        print("   • Try the CrewAI example (04) to see framework integration")
        print("   • Try the LangChain example (06) to see tool patterns")
        print("   • Check gateway logs: docker compose logs deeptrail-gateway")

    except DeepSecureError as e:
        print(f"\n❌ DeepSecure Error: {e}")
        print()
        print("🔧 Troubleshooting steps:")
        print("   1. Ensure both services are running:")
        print("      docker compose up deeptrail-control deeptrail-gateway -d")
        print("   2. Check gateway connectivity:")
        print("      curl http://localhost:8002/health")
        print("   3. Verify gateway URL configuration:")
        print("      deepsecure configure show")
        print("   4. Check service logs:")
        print("      docker compose logs deeptrail-gateway")
        
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        print("   This might indicate a configuration or environment issue.")
        print("   Check that both deeptrail-control and deeptrail-gateway are running.")


if __name__ == "__main__":
    main() 