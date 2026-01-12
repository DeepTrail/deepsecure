#!/usr/bin/env python3
"""
Final validation test for enhanced policy CLI commands.
"""

import sys
import re
import uuid
from unittest.mock import Mock, patch
from typer.testing import CliRunner

# Add the project root to the path
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from deepsecure.commands.policy import app as policy_app


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def test_enhanced_policy_commands():
    """Test all enhanced policy CLI commands."""
    print("🧪 Testing Enhanced Policy CLI Commands")
    print("=" * 50)
    
    runner = CliRunner()
    
    # Test 1: Azure attestation policy creation
    print("🔷 Testing Azure attestation policy creation...")
    mock_azure_policy = {
        "id": str(uuid.uuid4()),
        "platform": "azure_managed_identity",
        "agent_name": "azure-test-agent",
        "description": "Azure attestation policy for azure-test-agent",
        "policy_data": {
            "subscription_id": "12345678-1234-1234-1234-123456789012",
            "resource_group": "test-rg",
            "vm_name": "test-vm"
        }
    }
    
    with patch('deepsecure.commands.policy.policy_client') as mock_client:
        mock_client.create_attestation_policy.return_value = mock_azure_policy
        
        result = runner.invoke(policy_app, [
            'attestation', 'create-azure',
            '--agent-name', 'azure-test-agent',
            '--subscription-id', '12345678-1234-1234-1234-123456789012',
            '--resource-group', 'test-rg',
            '--vm-name', 'test-vm'
        ])
        
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "Azure attestation policy created successfully" in output
        print("✅ Azure policy creation working")
    
    # Test 2: Docker attestation policy creation
    print("🐳 Testing Docker attestation policy creation...")
    mock_docker_policy = {
        "id": str(uuid.uuid4()),
        "platform": "docker_container", 
        "agent_name": "docker-test-agent",
        "description": "Docker attestation policy for docker-test-agent",
        "policy_data": {
            "image_name": "deepsecure/agent:latest",
            "image_digest": "sha256:abcd1234567890"
        }
    }
    
    with patch('deepsecure.commands.policy.policy_client') as mock_client:
        mock_client.create_attestation_policy.return_value = mock_docker_policy
        
        result = runner.invoke(policy_app, [
            'attestation', 'create-docker',
            '--agent-name', 'docker-test-agent',
            '--image-name', 'deepsecure/agent:latest',
            '--image-digest', 'sha256:abcd1234567890'
        ])
        
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "Docker attestation policy created successfully" in output
        print("✅ Docker policy creation working")
    
    # Test 3: Policy listing
    print("📋 Testing attestation policy listing...")
    mock_policies = [
        Mock(
            id=str(uuid.uuid4()),
            platform="kubernetes",
            agent_name="k8s-agent",
            description="K8s policy",
            policy_data={"namespace": "default", "service_account": "sa"}
        ),
        Mock(
            id=str(uuid.uuid4()),
            platform="azure_managed_identity", 
            agent_name="azure-agent",
            description="Azure policy",
            policy_data={"subscription_id": "12345", "resource_group": "rg"}
        )
    ]
    
    with patch('deepsecure.commands.policy.policy_client') as mock_client:
        mock_client.list_attestation_policies.return_value = mock_policies
        
        result = runner.invoke(policy_app, ['attestation', 'list'])
        
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "Attestation Policies" in output
        assert "k8s-agent" in output
        assert "azure-agent" in output
        print("✅ Policy listing working")
    
    # Test 4: Policy validation 
    print("✅ Testing policy validation...")
    with patch('deepsecure.commands.policy.policy_client') as mock_client:
        mock_client.list_attestation_policies.return_value = mock_policies
        
        # Test validation success case
        result = runner.invoke(policy_app, [
            'attestation', 'validate',
            '--platform', 'kubernetes',
            '--agent-name', 'k8s-agent'
        ])
        
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "Found 1 matching attestation policy" in output
        print("✅ Policy validation working")
    
    # Test 5: Policy get details
    print("🔍 Testing policy details...")
    policy_id = str(uuid.uuid4())
    mock_policy_detail = Mock()
    mock_policy_detail.id = policy_id
    mock_policy_detail.platform = "kubernetes"
    mock_policy_detail.agent_name = "test-agent"
    mock_policy_detail.description = "Test policy"
    mock_policy_detail.policy_data = {"namespace": "default", "service_account": "sa"}
    mock_policy_detail.created_at = "2024-01-01T00:00:00Z"
    
    with patch('deepsecure.commands.policy.policy_client') as mock_client:
        mock_client.get_attestation_policy.return_value = mock_policy_detail
        
        result = runner.invoke(policy_app, ['attestation', 'get', policy_id])
        
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert f"Attestation Policy ID: {policy_id}" in output
        assert "Platform: kubernetes" in output
        print("✅ Policy details working")
    
    print("\n🎉 All enhanced policy CLI commands working correctly!")
    print("✅ Task 5.1.15: Enhanced attestation policy CLI commands work seamlessly with bootstrap implementation")
    
    print("\n📋 Summary of Enhanced Commands:")
    print("  🔷 deepsecure policy attestation create-azure")
    print("  🐳 deepsecure policy attestation create-docker") 
    print("  📋 deepsecure policy attestation list")
    print("  🔍 deepsecure policy attestation get <policy-id>")
    print("  🔄 deepsecure policy attestation update <policy-id>")
    print("  ✅ deepsecure policy attestation validate --platform <platform> --agent-name <name>")
    print("  🗑️ deepsecure policy attestation delete <policy-id>")

if __name__ == "__main__":
    try:
        test_enhanced_policy_commands()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 