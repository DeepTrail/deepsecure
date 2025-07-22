#!/usr/bin/env python3
"""
Demo script showing DeepTrail Gateway integration with DeepSecure SDK.

This demonstrates the end-to-end workflow that the integration tests verify:
1. Agent creation via SDK
2. Credential issuance
3. Request through gateway with authentication
4. Policy enforcement and secret injection
5. Proxy forwarding to external service
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path for deepsecure imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx


class IntegrationDemo:
    """Demonstrates the integration between gateway and SDK."""
    
    def __init__(self):
        self.control_url = "http://localhost:8000"
        self.gateway_url = "http://localhost:8002"
        self.external_service = "https://httpbin.org"
        
    async def check_services(self) -> bool:
        """Check if both services are running."""
        print("🔍 Checking service availability...")
        
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                # Check control plane
                control_response = await client.get(f"{self.control_url}/health")
                if control_response.status_code == 200:
                    print(f"✅ DeepTrail Control is running at {self.control_url}")
                else:
                    print(f"❌ DeepTrail Control returned {control_response.status_code}")
                    return False
                
                # Check gateway
                gateway_response = await client.get(f"{self.gateway_url}/health")
                if gateway_response.status_code == 200:
                    print(f"✅ DeepTrail Gateway is running at {self.gateway_url}")
                else:
                    print(f"❌ DeepTrail Gateway returned {gateway_response.status_code}")
                    return False
                
                return True
                
            except Exception as e:
                print(f"❌ Service check failed: {e}")
                return False
    
    async def demo_unauthenticated_request(self):
        """Demonstrate that unauthenticated requests are rejected."""
        print("\n🚫 Testing unauthenticated request (should be rejected)...")
        
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                response = await client.get(
                    f"{self.gateway_url}/proxy/get",
                    headers={"X-Target-Base-URL": self.external_service}
                )
                
                if response.status_code == 401:
                    print("✅ Unauthenticated request correctly rejected (401)")
                else:
                    print(f"❌ Unexpected response: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Request failed: {e}")
    
    async def demo_invalid_jwt_request(self):
        """Demonstrate that invalid JWT tokens are rejected."""
        print("\n🔐 Testing invalid JWT token (should be rejected)...")
        
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                response = await client.get(
                    f"{self.gateway_url}/proxy/get",
                    headers={
                        "X-Target-Base-URL": self.external_service,
                        "Authorization": "Bearer invalid-jwt-token"
                    }
                )
                
                if response.status_code == 401:
                    print("✅ Invalid JWT correctly rejected (401)")
                else:
                    print(f"❌ Unexpected response: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Request failed: {e}")
    
    async def demo_missing_target_url(self):
        """Demonstrate that requests without target URL are rejected."""
        print("\n🎯 Testing missing target URL (should be rejected)...")
        
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                response = await client.get(
                    f"{self.gateway_url}/proxy/get",
                    headers={"Authorization": "Bearer some-token"}
                )
                
                if response.status_code == 400:
                    print("✅ Missing target URL correctly rejected (400)")
                else:
                    print(f"❌ Unexpected response: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Request failed: {e}")
    
    def demo_sdk_workflow(self):
        """Demonstrate the SDK workflow (mocked for demo purposes)."""
        print("\n📚 Demonstrating DeepSecure SDK workflow...")
        
        # This would normally use the actual SDK, but for demo purposes
        # we'll show what the workflow would look like
        
        print("1. 🤖 Creating agent with SDK:")
        print("   client = deepsecure.Client()")
        print("   agent = client.agents.create(name='demo-agent')")
        print("   # Agent created with Ed25519 key pair")
        
        print("\n2. 🎫 Issuing credential:")
        print("   credential = client.vault.issue_credential(")
        print("       agent_id=agent.id,")
        print("       scope='read:web',")
        print("       resource='https://httpbin.org'")
        print("   )")
        print("   # JWT token issued with 1-hour expiry")
        
        print("\n3. 🔐 Fetching secret:")
        print("   secret = client.vault.get_secret(")
        print("       agent_id=agent.id,")
        print("       secret_name='api-key'")
        print("   )")
        print("   # Secret retrieved for injection")
        
        print("\n4. 🌐 Making request through gateway:")
        print("   # SDK automatically routes through gateway")
        print("   # Gateway validates JWT, enforces policy, injects secret")
        print("   # Request forwarded to external service")
        
        print("\n✅ SDK workflow demonstration complete")
    
    def demo_integration_test_scenarios(self):
        """Show what the integration tests verify."""
        print("\n🧪 Integration Test Scenarios:")
        
        scenarios = [
            "✅ Gateway health check",
            "✅ Control plane health check", 
            "✅ Unauthenticated request rejection",
            "✅ Invalid JWT rejection",
            "✅ Valid JWT acceptance",
            "✅ Policy enforcement (allow/deny)",
            "✅ Secret injection functionality",
            "✅ Request forwarding to external services",
            "✅ SDK client initialization",
            "✅ Agent creation and management",
            "✅ Credential issuance workflow",
            "✅ End-to-end proxy workflow",
            "✅ Security boundary enforcement",
            "✅ Performance characteristics",
            "✅ Concurrent request handling",
            "✅ Error handling and resilience"
        ]
        
        for scenario in scenarios:
            print(f"  {scenario}")
        
        print(f"\n📊 Total test scenarios: {len(scenarios)}")
    
    def show_test_commands(self):
        """Show how to run the integration tests."""
        print("\n🚀 Running Integration Tests:")
        
        print("\n1. Local testing (services already running):")
        print("   python run_integration_tests.py --mode local")
        
        print("\n2. Docker testing (automated setup):")
        print("   python run_integration_tests.py --mode docker")
        
        print("\n3. Specific test patterns:")
        print("   python run_integration_tests.py --pattern 'test_gateway_health'")
        print("   python run_integration_tests.py --pattern 'test_sdk'")
        
        print("\n4. Direct pytest:")
        print("   pytest -v -m integration tests/test_integration.py")
        print("   pytest -v -m 'integration and e2e' tests/test_integration.py")
        
        print("\n5. Test categories:")
        print("   pytest -v -m 'integration and performance'")
        print("   pytest -v -m 'integration and security'")
    
    async def run_demo(self):
        """Run the complete integration demo."""
        print("🎭 DeepTrail Gateway Integration Demo")
        print("=" * 50)
        
        # Check if services are running
        if not await self.check_services():
            print("\n❌ Services are not running. Please start them first:")
            print("   docker-compose up -d")
            return
        
        # Demo the security features
        await self.demo_unauthenticated_request()
        await self.demo_invalid_jwt_request()
        await self.demo_missing_target_url()
        
        # Show SDK workflow
        self.demo_sdk_workflow()
        
        # Show integration test scenarios
        self.demo_integration_test_scenarios()
        
        # Show test commands
        self.show_test_commands()
        
        print("\n🎯 Integration Demo Complete!")
        print("\nNext steps:")
        print("1. Run the integration tests: python run_integration_tests.py")
        print("2. Check the test results and coverage")
        print("3. Review the test documentation in README_INTEGRATION_TESTS.md")


async def main():
    """Main entry point for the demo."""
    demo = IntegrationDemo()
    await demo.run_demo()


if __name__ == "__main__":
    asyncio.run(main()) 