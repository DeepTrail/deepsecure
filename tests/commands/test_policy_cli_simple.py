#!/usr/bin/env python3
"""
Simple test script to debug policy CLI integration issues.
"""

import sys
import uuid
from unittest.mock import Mock, patch
from typer.testing import CliRunner

# Add the project root to the path
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from deepsecure.commands.policy import app as policy_app

def test_basic_azure_creation():
    """Test basic Azure policy creation."""
    print("Testing Azure policy creation...")
    
    runner = CliRunner()
    
    mock_policy = {
        "id": str(uuid.uuid4()),
        "platform": "azure_managed_identity",
        "agent_name": "azure-test-agent",
        "description": "Test policy",
        "policy_data": {
            "subscription_id": "12345678-1234-1234-1234-123456789012",
            "resource_group": "test-rg",
            "vm_name": "test-vm"
        }
    }
    
    with patch('deepsecure.commands.policy.policy_client') as mock_client:
        mock_client.create_attestation_policy.return_value = mock_policy
        
        result = runner.invoke(policy_app, [
            'attestation', 'create-azure',
            '--agent-name', 'azure-test-agent',
            '--subscription-id', '12345678-1234-1234-1234-123456789012',
            '--resource-group', 'test-rg',
            '--vm-name', 'test-vm'
        ])
        
        print(f"Exit code: {result.exit_code}")
        print(f"Output: {result.stdout}")
        if result.stderr:
            print(f"Error: {result.stderr}")
        if result.exception:
            print(f"Exception: {result.exception}")
            import traceback
            traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)
        
        assert result.exit_code == 0
        print("✅ Azure policy creation test passed")

def test_basic_listing():
    """Test basic policy listing."""
    print("Testing policy listing...")
    
    runner = CliRunner()
    
    mock_policies = [
        Mock(
            id=str(uuid.uuid4()),
            platform="kubernetes",
            agent_name="test-agent",
            description="Test policy",
            policy_data={"namespace": "default", "service_account": "sa"}
        )
    ]
    
    with patch('deepsecure.commands.policy.policy_client') as mock_client:
        mock_client.list_attestation_policies.return_value = mock_policies
        
        result = runner.invoke(policy_app, ['attestation', 'list'])
        
        print(f"Exit code: {result.exit_code}")
        print(f"Output: {result.stdout}")
        if result.stderr:
            print(f"Error: {result.stderr}")
        if result.exception:
            print(f"Exception: {result.exception}")
            import traceback
            traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)
        
        assert result.exit_code == 0
        print("✅ Policy listing test passed")

if __name__ == "__main__":
    try:
        test_basic_azure_creation()
        test_basic_listing()
        print("✅ All basic tests passed!")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 