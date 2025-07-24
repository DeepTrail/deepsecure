#!/usr/bin/env python3
"""
Test script to validate secure keyring storage for bootstrapped agent keys.

This test validates:
1. Keyring service name generation follows the correct pattern
2. Bootstrap process stores keys securely in OS keyring
3. Keys can be retrieved and used for authentication
4. Keys can be deleted securely
5. Error handling for keyring operations
"""

import sys
import uuid
import base64
import keyring
from keyring.errors import NoKeyringError, PasswordDeleteError
from unittest.mock import Mock, patch

# Add the project root to the path
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from deepsecure._core.identity_provider import _get_keyring_service_name_for_agent
from deepsecure._core.identity_manager import IdentityManager
from deepsecure._core.agent_client import AgentClient
from deepsecure._core.base_client import BaseClient

def test_keyring_service_name_generation():
    """Test that keyring service names are generated correctly."""
    print("🔧 Testing keyring service name generation...")
    
    # Test normal agent ID
    agent_id = "agent-ebd9cd4a-1234-5678-9abc-def012345678"
    expected_service_name = "deepsecure_agent-ebd9cd4a_private_key"
    actual_service_name = _get_keyring_service_name_for_agent(agent_id)
    
    assert actual_service_name == expected_service_name, f"Expected {expected_service_name}, got {actual_service_name}"
    print(f"✅ Service name generation correct: {actual_service_name}")
    
    # Test invalid agent ID format
    try:
        _get_keyring_service_name_for_agent("invalid-id")
        assert False, "Should have raised ValueError for invalid agent ID"
    except ValueError as e:
        print(f"✅ Correctly rejected invalid agent ID: {e}")
    
    print("✅ Keyring service name generation tests passed\n")

def test_keyring_storage_operations():
    """Test basic keyring storage operations."""
    print("🔑 Testing keyring storage operations...")
    
    # Create test agent and key
    test_agent_id = f"agent-{uuid.uuid4()}"
    test_private_key = base64.b64encode(b"test_private_key_32_bytes_exactly").decode()
    
    try:
        # Initialize identity manager
        mock_client = Mock(spec=BaseClient)
        identity_manager = IdentityManager(api_client=mock_client, silent_mode=True)
        
        # Test storing private key
        identity_manager.store_private_key_directly(test_agent_id, test_private_key)
        print(f"✅ Successfully stored private key for {test_agent_id}")
        
        # Test retrieving private key
        retrieved_key = identity_manager.get_private_key(test_agent_id)
        assert retrieved_key == test_private_key, f"Retrieved key doesn't match stored key"
        print(f"✅ Successfully retrieved private key for {test_agent_id}")
        
        # Test deleting private key
        success = identity_manager.delete_private_key(test_agent_id)
        assert success, "Key deletion should succeed"
        print(f"✅ Successfully deleted private key for {test_agent_id}")
        
        # Verify key is deleted
        retrieved_key_after_delete = identity_manager.get_private_key(test_agent_id)
        assert retrieved_key_after_delete is None, "Key should be None after deletion"
        print(f"✅ Verified key is deleted for {test_agent_id}")
        
    except Exception as e:
        print(f"❌ Keyring operation failed: {e}")
        # Clean up if test failed
        try:
            identity_manager.delete_private_key(test_agent_id)
        except:
            pass
        raise
    
    print("✅ Basic keyring storage operations tests passed\n")

def test_bootstrap_keyring_integration():
    """Test that bootstrap process integrates properly with keyring storage."""
    print("🚀 Testing bootstrap keyring integration...")
    
    test_agent_id = f"agent-{uuid.uuid4()}"
    
    try:
        # Mock a successful bootstrap response
        mock_response = Mock()
        mock_response.json.return_value = {
            "agent_id": test_agent_id,
            "private_key_b64": base64.b64encode(b"bootstrap_private_key_32_bytes").decode(),
            "public_key_b64": base64.b64encode(b"bootstrap_public_key_32_bytes").decode(),
            "correlation_id": "test-correlation-123"
        }
        mock_response.status_code = 200
        
        # Create agent client with mocked HTTP response
        with patch('deepsecure._core.base_client.BaseClient.bootstrap_kubernetes') as mock_bootstrap:
            mock_bootstrap.return_value = mock_response
            
            mock_base_client = Mock(spec=BaseClient)
            agent_client = AgentClient(mock_base_client)
            agent_client._silent_mode = True
            
            # Test Kubernetes bootstrap
            result = agent_client.bootstrap_kubernetes("mock-k8s-token", test_agent_id)
            
            # Verify bootstrap response
            assert result["agent_id"] == test_agent_id
            assert result["success"] == True
            assert result["bootstrap_platform"] == "kubernetes"
            print(f"✅ Bootstrap response validated for {test_agent_id}")
            
            # Verify key was stored in keyring
            identity_manager = IdentityManager(api_client=mock_base_client, silent_mode=True)
            stored_key = identity_manager.get_private_key(test_agent_id)
            
            expected_key = base64.b64encode(b"bootstrap_private_key_32_bytes").decode()
            assert stored_key == expected_key, "Private key not properly stored in keyring"
            print(f"✅ Private key properly stored in keyring for {test_agent_id}")
            
    except Exception as e:
        print(f"❌ Bootstrap keyring integration failed: {e}")
        raise
    finally:
        # Clean up
        try:
            identity_manager = IdentityManager(api_client=Mock(spec=BaseClient), silent_mode=True)
            identity_manager.delete_private_key(test_agent_id)
        except:
            pass
    
    print("✅ Bootstrap keyring integration tests passed\n")

def test_keyring_error_handling():
    """Test error handling for keyring operations."""
    print("⚠️  Testing keyring error handling...")
    
    test_agent_id = f"agent-{uuid.uuid4()}"
    
    # Test handling when keyring is not available
    with patch('keyring.set_password', side_effect=NoKeyringError("No keyring backend")):
        try:
            mock_client = Mock(spec=BaseClient)
            identity_manager = IdentityManager(api_client=mock_client, silent_mode=True)
            identity_manager.store_private_key_directly(test_agent_id, "test-key")
            assert False, "Should have raised IdentityManagerError"
        except Exception as e:
            assert "No system keyring backend found" in str(e)
            print("✅ Correctly handled NoKeyringError during storage")
    
    # Test handling when retrieving from unavailable keyring
    with patch('keyring.get_password', side_effect=NoKeyringError("No keyring backend")):
        mock_client = Mock(spec=BaseClient)
        identity_manager = IdentityManager(api_client=mock_client, silent_mode=True)
        key = identity_manager.get_private_key(test_agent_id)
        assert key is None, "Should return None when keyring unavailable"
        print("✅ Correctly handled NoKeyringError during retrieval")
    
    # Test handling when deleting from unavailable keyring
    with patch('keyring.delete_password', side_effect=NoKeyringError("No keyring backend")):
        mock_client = Mock(spec=BaseClient)
        identity_manager = IdentityManager(api_client=mock_client, silent_mode=True)
        success = identity_manager.delete_private_key(test_agent_id)
        assert success == False, "Should return False when keyring unavailable"
        print("✅ Correctly handled NoKeyringError during deletion")
    
    print("✅ Keyring error handling tests passed\n")

def test_keyring_security_validation():
    """Test security aspects of keyring storage."""
    print("🔒 Testing keyring security validation...")
    
    test_agent_id = f"agent-{uuid.uuid4()}"
    sensitive_key = base64.b64encode(b"super_secret_private_key_32_bytes").decode()
    
    try:
        mock_client = Mock(spec=BaseClient)
        identity_manager = IdentityManager(api_client=mock_client, silent_mode=True)
        
        # Store the key
        identity_manager.store_private_key_directly(test_agent_id, sensitive_key)
        
        # Verify the key is stored under the correct service name
        expected_service_name = _get_keyring_service_name_for_agent(test_agent_id)
        stored_key = keyring.get_password(expected_service_name, test_agent_id)
        
        assert stored_key == sensitive_key, "Key not stored under correct service name"
        print(f"✅ Key stored under correct service name: {expected_service_name}")
        
        # Verify keys from different agents are isolated
        other_agent_id = f"agent-{uuid.uuid4()}"
        other_key = identity_manager.get_private_key(other_agent_id)
        assert other_key is None, "Should not retrieve key for different agent"
        print("✅ Agent key isolation verified")
        
        # Clean up
        identity_manager.delete_private_key(test_agent_id)
        
    except Exception as e:
        print(f"❌ Security validation failed: {e}")
        raise
    
    print("✅ Keyring security validation tests passed\n")

def main():
    """Run all keyring storage validation tests."""
    print("🧪 Starting Keyring Storage Validation Tests")
    print("=" * 60)
    
    try:
        test_keyring_service_name_generation()
        test_keyring_storage_operations()
        test_bootstrap_keyring_integration()
        test_keyring_error_handling()
        test_keyring_security_validation()
        
        print("🎉 All keyring storage validation tests passed!")
        print("✅ Task 5.1.14: Secure keyring storage is properly implemented")
        
    except Exception as e:
        print(f"❌ Keyring storage validation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 