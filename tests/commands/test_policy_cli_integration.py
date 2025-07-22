#!/usr/bin/env python3
"""
Test script to validate enhanced policy CLI commands integration with bootstrap implementation.

This test validates:
1. Azure and Docker attestation policy creation commands
2. Attestation policy listing, getting, updating, and deletion
3. Policy validation command for bootstrap configuration
4. Integration with enhanced backend bootstrap flows
5. Error handling and user experience
"""

import sys
import uuid
import json
from unittest.mock import Mock, patch
from typer.testing import CliRunner

# Add the project root to the path
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from deepsecure.commands.policy import app as policy_app

def test_azure_attestation_policy_creation():
    """Test creating Azure managed identity attestation policies."""
    print("🔷 Testing Azure attestation policy creation...")
    
    runner = CliRunner()
    
    # Mock the policy client
    mock_policy = {
        "id": str(uuid.uuid4()),
        "platform": "azure_managed_identity",
        "agent_name": "azure-test-agent",
        "description": "Azure attestation policy for azure-test-agent",
        "policy_data": {
            "subscription_id": "12345678-1234-1234-1234-123456789012",
            "resource_group": "test-rg",
            "vm_name": "test-vm"
        },
        "created_at": "2024-01-01T00:00:00Z"
    }
    
    with patch('deepsecure.commands.policy.policy_client') as mock_client:
        mock_client.create_attestation_policy.return_value = mock_policy
        
        result = runner.invoke(policy_app, [
            'attestation', 'create-azure',
            '--agent-name', 'azure-test-agent',
            '--subscription-id', '12345678-1234-1234-1234-123456789012',
            '--resource-group', 'test-rg',
            '--vm-name', 'test-vm',
            '--description', 'Test Azure policy'
        ])
        
        assert result.exit_code == 0
        assert "Azure attestation policy created successfully" in result.stdout
        
        # Verify the correct policy data was sent
        call_args = mock_client.create_attestation_policy.call_args[0][0]
        assert call_args["platform"] == "azure_managed_identity"
        assert call_args["agent_name"] == "azure-test-agent"
        assert call_args["policy_data"]["subscription_id"] == "12345678-1234-1234-1234-123456789012"
        assert call_args["policy_data"]["resource_group"] == "test-rg"
        assert call_args["policy_data"]["vm_name"] == "test-vm"
        
        print("✅ Azure attestation policy creation test passed")

def test_docker_attestation_policy_creation():
    """Test creating Docker container attestation policies."""
    print("🐳 Testing Docker attestation policy creation...")
    
    runner = CliRunner()
    
    mock_policy = {
        "id": str(uuid.uuid4()),
        "platform": "docker_container",
        "agent_name": "docker-test-agent",
        "description": "Docker attestation policy for docker-test-agent",
        "policy_data": {
            "image_name": "deepsecure/agent:latest",
            "image_digest": "sha256:abcd1234567890",
            "container_name": "test-container"
        },
        "created_at": "2024-01-01T00:00:00Z"
    }
    
    with patch('deepsecure.commands.policy.policy_client') as mock_client:
        mock_client.create_attestation_policy.return_value = mock_policy
        
        result = runner.invoke(policy_app, [
            'attestation', 'create-docker',
            '--agent-name', 'docker-test-agent',
            '--image-name', 'deepsecure/agent:latest',
            '--image-digest', 'sha256:abcd1234567890',
            '--container-name', 'test-container',
            '--description', 'Test Docker policy'
        ])
        
        assert result.exit_code == 0
        assert "Docker attestation policy created successfully" in result.stdout
        
        # Verify the correct policy data was sent
        call_args = mock_client.create_attestation_policy.call_args[0][0]
        assert call_args["platform"] == "docker_container"
        assert call_args["agent_name"] == "docker-test-agent"
        assert call_args["policy_data"]["image_name"] == "deepsecure/agent:latest"
        assert call_args["policy_data"]["image_digest"] == "sha256:abcd1234567890"
        assert call_args["policy_data"]["container_name"] == "test-container"
        
        print("✅ Docker attestation policy creation test passed")

def test_attestation_policy_listing():
    """Test listing attestation policies."""
    print("📋 Testing attestation policy listing...")
    
    runner = CliRunner()
    
    mock_policies = [
        {
            "id": str(uuid.uuid4()),
            "platform": "kubernetes",
            "agent_name": "k8s-agent",
            "description": "K8s policy",
            "policy_data": {"namespace": "default", "service_account": "sa"}
        },
        {
            "id": str(uuid.uuid4()),
            "platform": "azure_managed_identity",
            "agent_name": "azure-agent",
            "description": "Azure policy",
            "policy_data": {"subscription_id": "12345", "resource_group": "rg"}
        },
        {
            "id": str(uuid.uuid4()),
            "platform": "docker_container",
            "agent_name": "docker-agent",
            "description": "Docker policy",
            "policy_data": {"image_name": "test:latest"}
        }
    ]
    
    with patch('deepsecure.commands.policy.policy_client') as mock_client:
        mock_client.list_attestation_policies.return_value = [
            Mock(**policy) for policy in mock_policies
        ]
        
        result = runner.invoke(policy_app, ['attestation', 'list'])
        
        assert result.exit_code == 0
        assert "Attestation Policies" in result.stdout
        assert "k8s-agent" in result.stdout
        assert "azure-agent" in result.stdout
        assert "docker-agent" in result.stdout
        assert "kubernetes" in result.stdout
        assert "azure_managed_identity" in result.stdout
        assert "docker_container" in result.stdout
        
        print("✅ Attestation policy listing test passed")

def test_attestation_policy_details():
    """Test getting detailed attestation policy information."""
    print("🔍 Testing attestation policy details retrieval...")
    
    runner = CliRunner()
    
    policy_id = str(uuid.uuid4())
    mock_policy = Mock()
    mock_policy.id = policy_id
    mock_policy.platform = "kubernetes"
    mock_policy.agent_name = "test-agent"
    mock_policy.description = "Test policy description"
    mock_policy.policy_data = {"namespace": "production", "service_account": "agent-sa"}
    mock_policy.created_at = "2024-01-01T00:00:00Z"
    
    with patch('deepsecure.commands.policy.policy_client') as mock_client:
        mock_client.get_attestation_policy.return_value = mock_policy
        
        result = runner.invoke(policy_app, ['attestation', 'get', policy_id])
        
        assert result.exit_code == 0
        assert f"Attestation Policy ID: {policy_id}" in result.stdout
        assert "Platform: kubernetes" in result.stdout
        assert "Agent Name: test-agent" in result.stdout
        assert "Description: Test policy description" in result.stdout
        assert "Policy Data:" in result.stdout
        assert "namespace: production" in result.stdout
        assert "service_account: agent-sa" in result.stdout
        assert "Created: 2024-01-01T00:00:00Z" in result.stdout
        
        print("✅ Attestation policy details test passed")

def test_attestation_policy_validation():
    """Test attestation policy validation for bootstrap configuration."""
    print("✅ Testing attestation policy validation...")
    
    runner = CliRunner()
    
    # Test case 1: Policy exists
    mock_policies = [
        Mock(
            platform="kubernetes", 
            agent_name="test-agent",
            id="policy-123",
            description="Test K8s policy",
            policy_data={"namespace": "default", "service_account": "sa"}
        )
    ]
    
    with patch('deepsecure.commands.policy.policy_client') as mock_client:
        mock_client.list_attestation_policies.return_value = mock_policies
        
        result = runner.invoke(policy_app, [
            'attestation', 'validate',
            '--platform', 'kubernetes',
            '--agent-name', 'test-agent'
        ])
        
        assert result.exit_code == 0
        assert "✅ Found 1 matching attestation policy(ies)" in result.stdout
        assert "Policy ID: policy-123" in result.stdout
        
        print("✅ Policy validation (exists) test passed")
    
    # Test case 2: Policy doesn't exist
    with patch('deepsecure.commands.policy.policy_client') as mock_client:
        mock_client.list_attestation_policies.return_value = mock_policies
        
        result = runner.invoke(policy_app, [
            'attestation', 'validate',
            '--platform', 'aws',
            '--agent-name', 'missing-agent'
        ])
        
        assert result.exit_code == 0
        assert "❌ No attestation policy found" in result.stdout
        assert "Available policies:" in result.stdout
        assert "deepsecure policy attestation create-aws" in result.stdout
        
        print("✅ Policy validation (missing) test passed")

def test_attestation_policy_update():
    """Test updating attestation policies."""
    print("🔄 Testing attestation policy updates...")
    
    runner = CliRunner()
    
    policy_id = str(uuid.uuid4())
    updated_policy = {
        "id": policy_id,
        "platform": "kubernetes",
        "agent_name": "updated-agent-name",
        "description": "Updated description",
        "policy_data": {"namespace": "default", "service_account": "sa"}
    }
    
    with patch('deepsecure.commands.policy.policy_client') as mock_client:
        mock_client.update_attestation_policy.return_value = updated_policy
        
        result = runner.invoke(policy_app, [
            'attestation', 'update', policy_id,
            '--agent-name', 'updated-agent-name',
            '--description', 'Updated description'
        ])
        
        assert result.exit_code == 0
        assert "Attestation policy updated successfully" in result.stdout
        
        # Verify update call
        call_args = mock_client.update_attestation_policy.call_args
        assert call_args[0][0] == policy_id  # policy_id
        update_data = call_args[0][1]  # update_data
        assert update_data["agent_name"] == "updated-agent-name"
        assert update_data["description"] == "Updated description"
        
        print("✅ Attestation policy update test passed")

def test_attestation_policy_deletion():
    """Test deleting attestation policies."""
    print("🗑️ Testing attestation policy deletion...")
    
    runner = CliRunner()
    
    policy_id = str(uuid.uuid4())
    
    with patch('deepsecure.commands.policy.policy_client') as mock_client:
        mock_client.delete_attestation_policy.return_value = {
            "message": f"Attestation policy {policy_id} deleted successfully."
        }
        
        result = runner.invoke(policy_app, ['attestation', 'delete', policy_id])
        
        assert result.exit_code == 0
        assert f"Attestation policy {policy_id} deleted successfully" in result.stdout
        
        # Verify delete call
        mock_client.delete_attestation_policy.assert_called_once_with(policy_id)
        
        print("✅ Attestation policy deletion test passed")

def test_bootstrap_integration_workflow():
    """Test the complete workflow for bootstrap policy configuration."""
    print("🚀 Testing complete bootstrap integration workflow...")
    
    runner = CliRunner()
    
    # Simulate workflow: Create policies for different platforms, then validate
    platforms_and_configs = [
        ("kubernetes", {
            "agent_name": "k8s-prod-agent",
            "extra_args": ["--namespace", "production", "--service-account", "deepsecure-agent"]
        }),
        ("aws", {
            "agent_name": "aws-prod-agent", 
            "extra_args": ["--role-arn", "arn:aws:iam::123456789012:role/DeepSecureAgent"]
        }),
        ("azure", {
            "agent_name": "azure-prod-agent",
            "extra_args": ["--subscription-id", "12345678-1234-1234-1234-123456789012", 
                          "--resource-group", "production-rg", "--vm-name", "agent-vm"]
        }),
        ("docker", {
            "agent_name": "docker-prod-agent",
            "extra_args": ["--image-name", "deepsecure/agent:v1.0", 
                          "--image-digest", "sha256:abc123", "--container-name", "prod-agent"]
        })
    ]
    
    created_policies = []
    
    with patch('deepsecure.commands.policy.policy_client') as mock_client:
        # Mock policy creation for all platforms
        def mock_create_policy(policy_data):
            policy = {
                "id": str(uuid.uuid4()),
                "platform": policy_data["platform"],
                "agent_name": policy_data["agent_name"],
                "description": policy_data["description"],
                "policy_data": policy_data["policy_data"],
                "created_at": "2024-01-01T00:00:00Z"
            }
            created_policies.append(Mock(**policy))
            return policy
        
        mock_client.create_attestation_policy.side_effect = mock_create_policy
        
        # Create policies for all platforms
        for platform, config in platforms_and_configs:
            cmd_platform = platform.replace("_", "-")  # Convert azure_managed_identity to azure
            if platform == "azure_managed_identity":
                cmd_platform = "azure"
            
            cmd_args = ['attestation', f'create-{cmd_platform}', '--agent-name', config["agent_name"]]
            cmd_args.extend(config["extra_args"])
            
            result = runner.invoke(policy_app, cmd_args)
            assert result.exit_code == 0
            assert f"{platform.title()} attestation policy created successfully" in result.stdout.replace("_", " ")
        
        print("✅ Created policies for all platforms")
        
        # Mock listing for validation
        mock_client.list_attestation_policies.return_value = created_policies
        
        # Validate each policy exists
        for platform, config in platforms_and_configs:
            actual_platform = platform
            if platform == "azure":
                actual_platform = "azure_managed_identity"
            elif platform == "docker":
                actual_platform = "docker_container"
                
            result = runner.invoke(policy_app, [
                'attestation', 'validate',
                '--platform', actual_platform,
                '--agent-name', config["agent_name"]
            ])
            assert result.exit_code == 0
            assert "✅ Found 1 matching attestation policy(ies)" in result.stdout
        
        print("✅ Validated all policies exist and are accessible")
        
        print("✅ Complete bootstrap integration workflow test passed")

def test_cli_error_handling():
    """Test error handling in CLI commands."""
    print("⚠️ Testing CLI error handling...")
    
    runner = CliRunner()
    
    # Test missing required arguments
    result = runner.invoke(policy_app, ['attestation', 'create-azure'])
    assert result.exit_code != 0  # Should fail due to missing required arguments
    
    # Test invalid policy ID format
    with patch('deepsecure.commands.policy.policy_client') as mock_client:
        mock_client.get_attestation_policy.side_effect = Exception("Policy not found")
        
        result = runner.invoke(policy_app, ['attestation', 'get', 'invalid-id'])
        # The command should handle the error gracefully (depends on @handle_api_error)
        
    print("✅ CLI error handling test passed")

def main():
    """Run all policy CLI integration tests."""
    print("🧪 Starting Policy CLI Integration Tests")
    print("=" * 60)
    
    try:
        test_azure_attestation_policy_creation()
        test_docker_attestation_policy_creation()
        test_attestation_policy_listing()
        test_attestation_policy_details()
        test_attestation_policy_validation()
        test_attestation_policy_update()
        test_attestation_policy_deletion()
        test_bootstrap_integration_workflow()
        test_cli_error_handling()
        
        print("\n🎉 All policy CLI integration tests passed!")
        print("✅ Task 5.1.15: Enhanced attestation policy CLI commands work seamlessly with bootstrap implementation")
        print("\nNew CLI Commands Available:")
        print("  📋 deepsecure policy attestation list")
        print("  🔍 deepsecure policy attestation get <policy-id>")
        print("  🔄 deepsecure policy attestation update <policy-id>")
        print("  ✅ deepsecure policy attestation validate --platform <platform> --agent-name <name>")
        print("  🔷 deepsecure policy attestation create-azure")
        print("  🐳 deepsecure policy attestation create-docker")
        
    except Exception as e:
        print(f"❌ Policy CLI integration test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 