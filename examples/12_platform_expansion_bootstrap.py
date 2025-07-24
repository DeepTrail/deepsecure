#!/usr/bin/env python3
"""
Example: Platform Expansion - Azure and Docker Agent Bootstrapping

This example demonstrates how to use DeepSecure's platform expansion features
to bootstrap agent identities using Azure Managed Identity and Docker container
identity mechanisms.

Key Features Demonstrated:
1. Azure Managed Identity token validation using IMDS
2. Docker container identity verification using runtime tokens
3. Platform-specific attestation policies
4. Secure agent identity bootstrapping across multiple platforms

Requirements:
- Azure VM with Managed Identity enabled (for Azure example)
- Docker daemon access (for Docker example)
- DeepSecure control plane running with attestation policies configured
"""

import os
import sys
import json
import time
import hashlib
import logging
from typing import Dict, Any

# Add deepsecure package to path for local development
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from deepsecure import Client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PlatformExpansionDemo:
    """Demonstrates Azure and Docker bootstrap functionality."""
    
    def __init__(self, control_plane_url: str = "http://localhost:8001"):
        """Initialize the demo with control plane connection."""
        self.control_plane_url = control_plane_url
        self.client = Client(deeptrail_control_url=control_plane_url)
        
    def demonstrate_azure_bootstrap(self):
        """
        Demonstrate Azure Managed Identity bootstrap process.
        
        This simulates the bootstrap process that would occur on an Azure VM
        with Managed Identity enabled.
        """
        print("\n=== Azure Managed Identity Bootstrap Demo ===")
        
        try:
            # Step 1: Simulate obtaining Azure IMDS token
            print("1. Obtaining Azure IMDS token...")
            
            # In a real Azure VM, this would call the Instance Metadata Service:
            # curl -H "Metadata: true" \
            #      "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/"
            
            # For demo purposes, we'll create a mock token
            mock_azure_token = self._create_mock_azure_token()
            print(f"   ✓ Obtained IMDS token (length: {len(mock_azure_token)} chars)")
            
            # Step 2: Call bootstrap endpoint
            print("2. Bootstrapping agent identity...")
            bootstrap_response = self._call_azure_bootstrap_endpoint(mock_azure_token)
            
            if bootstrap_response:
                print(f"   ✓ Agent bootstrapped successfully!")
                print(f"   Agent ID: {bootstrap_response['agent_id']}")
                print(f"   Public Key: {bootstrap_response['public_key_b64'][:50]}...")
                
                # Step 3: Demonstrate using the bootstrapped identity
                print("3. Testing bootstrapped identity...")
                self._test_bootstrapped_identity(bootstrap_response)
                
            else:
                print("   ❌ Bootstrap failed")
                
        except Exception as e:
            logger.error(f"Azure bootstrap demo failed: {e}")
            print(f"   ❌ Demo failed: {e}")
    
    def demonstrate_docker_bootstrap(self):
        """
        Demonstrate Docker container identity bootstrap process.
        
        This simulates the bootstrap process that would occur inside a
        Docker container with runtime identity verification.
        """
        print("\n=== Docker Container Identity Bootstrap Demo ===")
        
        try:
            # Step 1: Get container identity information
            print("1. Gathering container identity...")
            
            container_info = self._get_container_identity()
            print(f"   ✓ Container ID: {container_info['container_id'][:12]}...")
            print(f"   ✓ Image: {container_info['image_name']}")
            
            # Step 2: Generate runtime verification token
            print("2. Generating runtime verification token...")
            runtime_token = self._generate_runtime_token(container_info)
            print(f"   ✓ Runtime token: {runtime_token[:16]}...")
            
            # Step 3: Call bootstrap endpoint
            print("3. Bootstrapping agent identity...")
            bootstrap_response = self._call_docker_bootstrap_endpoint(
                container_info['container_id'], 
                runtime_token
            )
            
            if bootstrap_response:
                print(f"   ✓ Agent bootstrapped successfully!")
                print(f"   Agent ID: {bootstrap_response['agent_id']}")
                print(f"   Public Key: {bootstrap_response['public_key_b64'][:50]}...")
                
                # Step 4: Demonstrate using the bootstrapped identity
                print("4. Testing bootstrapped identity...")
                self._test_bootstrapped_identity(bootstrap_response)
                
            else:
                print("   ❌ Bootstrap failed")
                
        except Exception as e:
            logger.error(f"Docker bootstrap demo failed: {e}")
            print(f"   ❌ Demo failed: {e}")
    
    def setup_attestation_policies(self):
        """
        Set up attestation policies for Azure and Docker platforms.
        
        In production, these would be configured by administrators
        before agents attempt to bootstrap.
        """
        print("\n=== Setting Up Attestation Policies ===")
        
        try:
            # Azure attestation policy
            print("1. Creating Azure attestation policy...")
            azure_policy = {
                "platform": "azure_managed_identity",
                "selector": "subscription_id=12345678-1234-1234-1234-123456789012,resource_group=demo-rg,vm_name=demo-vm",
                "agent_name_to_bootstrap": "azure-demo-agent"
            }
            
            # Note: In real implementation, this would use the CLI or admin API
            print(f"   Policy: {azure_policy['selector']}")
            print(f"   → Agent: {azure_policy['agent_name_to_bootstrap']}")
            
            # Docker attestation policy  
            print("2. Creating Docker attestation policy...")
            docker_policy = {
                "platform": "docker_container",
                "selector": "image_name=deepsecure/agent:latest,image_digest=sha256:demo123456",
                "agent_name_to_bootstrap": "docker-demo-agent"
            }
            
            print(f"   Policy: {docker_policy['selector']}")
            print(f"   → Agent: {docker_policy['agent_name_to_bootstrap']}")
            
            print("   ✓ Attestation policies configured")
            
        except Exception as e:
            logger.error(f"Policy setup failed: {e}")
            print(f"   ❌ Policy setup failed: {e}")
    
    def _create_mock_azure_token(self) -> str:
        """Create a mock Azure IMDS token for demonstration."""
        # In production, this would be obtained from Azure IMDS
        import jwt
        
        # Mock payload representing Azure IMDS token
        payload = {
            "iss": "https://sts.windows.net/tenant-id/",
            "aud": "https://management.azure.com/",
            "sub": "principal-id",
            "oid": "87654321-4321-4321-4321-210987654321",
            "subscription_id": "12345678-1234-1234-1234-123456789012",
            "resource_group": "demo-rg",
            "vm_name": "demo-vm",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time())
        }
        
        # Note: In demo, we use a mock token. Real Azure tokens are signed by Azure.
        return jwt.encode(payload, "demo-secret", algorithm="HS256")
    
    def _get_container_identity(self) -> Dict[str, str]:
        """Get Docker container identity information."""
        # In a real container, this would read from container metadata
        return {
            "container_id": "abcdef123456789012345678901234567890123456789012345678901234",
            "image_name": "deepsecure/agent:latest",
            "image_digest": "sha256:demo123456789abcdef",
            "runtime_path": "/var/lib/docker/containers/abcdef123456"
        }
    
    def _generate_runtime_token(self, container_info: Dict[str, str]) -> str:
        """Generate a runtime verification token for Docker container."""
        # This simulates the runtime token generation process
        runtime_secret = os.environ.get('DOCKER_RUNTIME_SECRET', 'demo-secret')
        
        token_data = f"{container_info['container_id']}:{container_info['image_digest']}:{runtime_secret}"
        return hashlib.sha256(token_data.encode()).hexdigest()
    
    def _call_azure_bootstrap_endpoint(self, token: str) -> Dict[str, Any]:
        """Call the Azure bootstrap endpoint."""
        # This would make an HTTP call to /api/v1/auth/bootstrap/azure
        # For demo purposes, we'll simulate the response
        
        print("   → Calling /api/v1/auth/bootstrap/azure")
        print("   → Validating Azure IMDS token...")
        print("   → Matching attestation policy...")
        print("   → Generating Ed25519 key pair...")
        print("   → Creating agent in database...")
        
        return {
            "agent_id": "agent-" + str(time.time())[:10],
            "private_key_b64": "LS0tLS1CRUdJTi...",  # Mock private key
            "public_key_b64": "MCowBQYDK2VwAy..."    # Mock public key
        }
    
    def _call_docker_bootstrap_endpoint(self, container_id: str, runtime_token: str) -> Dict[str, Any]:
        """Call the Docker bootstrap endpoint."""
        # This would make an HTTP call to /api/v1/auth/bootstrap/docker
        # For demo purposes, we'll simulate the response
        
        print("   → Calling /api/v1/auth/bootstrap/docker")
        print("   → Validating container identity...")
        print("   → Verifying runtime token...")
        print("   → Matching attestation policy...")
        print("   → Generating Ed25519 key pair...")
        print("   → Creating agent in database...")
        
        return {
            "agent_id": "agent-" + str(time.time())[:10],
            "private_key_b64": "LS0tLS1CRUdJTi...",  # Mock private key
            "public_key_b64": "MCowBQYDK2VwAy..."    # Mock public key
        }
    
    def _test_bootstrapped_identity(self, bootstrap_response: Dict[str, Any]):
        """Test the bootstrapped identity by performing authentication."""
        print("   → Testing challenge-response authentication...")
        print("   → Requesting access token...")
        print("   → Verifying JWT token...")
        print("   ✓ Identity verification successful!")

def demonstrate_platform_security_benefits():
    """
    Explain the security benefits of platform expansion.
    """
    print("\n=== Platform Expansion Security Benefits ===")
    
    benefits = [
        {
            "benefit": "Platform-Native Identity",
            "description": "Leverages Azure Managed Identity and Docker runtime for secure, platform-native authentication"
        },
        {
            "benefit": "Zero-Trust Bootstrap",
            "description": "No pre-shared secrets or manual key distribution required"
        },
        {
            "benefit": "Attestation-Based Authorization", 
            "description": "Platform identity is verified against stored attestation policies before agent creation"
        },
        {
            "benefit": "Cryptographic Agent Identity",
            "description": "Each agent receives unique Ed25519 key pairs for unforgeable identity"
        },
        {
            "benefit": "Multi-Platform Support",
            "description": "Consistent security model across Kubernetes, AWS, Azure, and Docker environments"
        },
        {
            "benefit": "Audit Trail",
            "description": "Complete audit log of agent bootstrapping events for compliance and security monitoring"
        }
    ]
    
    for i, benefit in enumerate(benefits, 1):
        print(f"{i}. {benefit['benefit']}")
        print(f"   {benefit['description']}")
        print()

def main():
    """Run the platform expansion demonstration."""
    print("🛡️  DeepSecure Platform Expansion Demo")
    print("=" * 50)
    
    # Initialize demo
    demo = PlatformExpansionDemo()
    
    # Show security benefits
    demonstrate_platform_security_benefits()
    
    # Set up policies (in production, this would be done by administrators)
    demo.setup_attestation_policies()
    
    # Demonstrate Azure bootstrap
    demo.demonstrate_azure_bootstrap()
    
    # Demonstrate Docker bootstrap
    demo.demonstrate_docker_bootstrap()
    
    print("\n=== Demo Complete ===")
    print("🎉 Platform expansion enables secure agent bootstrapping")
    print("   across Azure and Docker environments!")
    
    print("\n📚 Next Steps:")
    print("   • Configure real attestation policies for your environment")
    print("   • Deploy agents in Azure VMs with Managed Identity")
    print("   • Use Docker containers with runtime token generation")
    print("   • Monitor agent bootstrap events in audit logs")

if __name__ == "__main__":
    main() 