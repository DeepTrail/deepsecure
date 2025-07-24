#!/usr/bin/env python3
"""
Test script for validating SDK bootstrap integration with the enhanced backend.
Tests all platform integrations, error handling, and security features.
"""
import sys
import os
import time
import json
import logging
from typing import Dict, Any
from unittest.mock import patch, MagicMock

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from deepsecure import Client
    from deepsecure._core.agent_client import AgentClient
    from deepsecure._core.identity_provider import (
        KubernetesIdentityProvider,
        AwsIdentityProvider,
        AzureIdentityProvider,
        DockerIdentityProvider
    )
    from deepsecure.exceptions import DeepSecureClientError
except ImportError as e:
    print(f"Import error: {e}")
    print("This test requires the deepsecure package to be available")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SDKBootstrapIntegrationTester:
    """Test class for validating SDK bootstrap integration."""
    
    def __init__(self, control_plane_url: str = "http://localhost:8001"):
        self.control_plane_url = control_plane_url
        
    def test_kubernetes_bootstrap_integration(self):
        """Test Kubernetes bootstrap integration with mock responses."""
        logger.info("=== Testing Kubernetes Bootstrap Integration ===")
        
        # Mock successful backend response
        mock_response_data = {
            "agent_id": "agent-k8s-test-123",
            "private_key_b64": "dGVzdC1wcml2YXRlLWtleQ==",  # base64 encoded test data
            "public_key_b64": "dGVzdC1wdWJsaWMta2V5"  # base64 encoded test data
        }
        
        with patch('httpx.Client.post') as mock_post:
            # Mock successful HTTP response
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response
            
            # Mock keyring storage
            with patch('keyring.set_password') as mock_keyring_set, \
                 patch('keyring.get_password') as mock_keyring_get:
                
                mock_keyring_get.return_value = mock_response_data["private_key_b64"]
                
                try:
                    # Test AgentClient bootstrap
                    agent_client = AgentClient(api_url=self.control_plane_url, silent_mode=True)
                    result = agent_client.bootstrap_kubernetes("mock-k8s-token")
                    
                    # Validate result
                    assert result["agent_id"] == mock_response_data["agent_id"]
                    assert result["bootstrap_platform"] == "kubernetes"
                    assert result["success"] == True
                    
                    # Verify backend call was made correctly
                    mock_post.assert_called_once()
                    call_args = mock_post.call_args
                    assert "/api/v1/auth/bootstrap/kubernetes" in call_args[0][0]
                    assert call_args[1]["json"]["token"] == "mock-k8s-token"
                    
                    # Verify keyring operations
                    mock_keyring_set.assert_called_once()
                    mock_keyring_get.assert_called_once()
                    
                    logger.info("✓ Kubernetes bootstrap integration successful")
                    
                except Exception as e:
                    logger.error(f"✗ Kubernetes bootstrap integration failed: {e}")
                    return False
                    
        return True
    
    def test_aws_bootstrap_integration(self):
        """Test AWS bootstrap integration with mock responses."""
        logger.info("=== Testing AWS Bootstrap Integration ===")
        
        # Mock successful backend response
        mock_response_data = {
            "agent_id": "agent-aws-test-456",
            "private_key_b64": "dGVzdC1hd3MtcHJpdmF0ZS1rZXk=",
            "public_key_b64": "dGVzdC1hd3MtcHVibGljLWtleQ=="
        }
        
        with patch('httpx.Client.post') as mock_post:
            # Mock successful HTTP response
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response
            
            # Mock keyring storage
            with patch('keyring.set_password') as mock_keyring_set, \
                 patch('keyring.get_password') as mock_keyring_get:
                
                mock_keyring_get.return_value = mock_response_data["private_key_b64"]
                
                try:
                    # Test AgentClient bootstrap
                    agent_client = AgentClient(api_url=self.control_plane_url, silent_mode=True)
                    result = agent_client.bootstrap_aws("arn:aws:iam::123456789012:role/test-role")
                    
                    # Validate result
                    assert result["agent_id"] == mock_response_data["agent_id"]
                    assert result["bootstrap_platform"] == "aws"
                    assert result["success"] == True
                    
                    # Verify backend call was made correctly
                    mock_post.assert_called_once()
                    call_args = mock_post.call_args
                    assert "/api/v1/auth/bootstrap/aws" in call_args[0][0]
                    assert call_args[1]["json"]["token"] == "arn:aws:iam::123456789012:role/test-role"
                    
                    logger.info("✓ AWS bootstrap integration successful")
                    
                except Exception as e:
                    logger.error(f"✗ AWS bootstrap integration failed: {e}")
                    return False
                    
        return True
    
    def test_azure_bootstrap_integration(self):
        """Test Azure bootstrap integration with mock responses."""
        logger.info("=== Testing Azure Bootstrap Integration ===")
        
        # Mock successful backend response
        mock_response_data = {
            "agent_id": "agent-azure-test-789",
            "private_key_b64": "dGVzdC1henVyZS1wcml2YXRlLWtleQ==",
            "public_key_b64": "dGVzdC1henVyZS1wdWJsaWMta2V5"
        }
        
        with patch('httpx.Client.post') as mock_post:
            # Mock successful HTTP response
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response
            
            # Mock keyring storage
            with patch('keyring.set_password') as mock_keyring_set, \
                 patch('keyring.get_password') as mock_keyring_get:
                
                mock_keyring_get.return_value = mock_response_data["private_key_b64"]
                
                try:
                    # Test AgentClient bootstrap
                    agent_client = AgentClient(api_url=self.control_plane_url, silent_mode=True)
                    result = agent_client.bootstrap_azure("mock-azure-imds-token")
                    
                    # Validate result
                    assert result["agent_id"] == mock_response_data["agent_id"]
                    assert result["bootstrap_platform"] == "azure"
                    assert result["success"] == True
                    
                    # Verify backend call was made correctly
                    mock_post.assert_called_once()
                    call_args = mock_post.call_args
                    assert "/api/v1/auth/bootstrap/azure" in call_args[0][0]
                    assert call_args[1]["json"]["token"] == "mock-azure-imds-token"
                    
                    logger.info("✓ Azure bootstrap integration successful")
                    
                except Exception as e:
                    logger.error(f"✗ Azure bootstrap integration failed: {e}")
                    return False
                    
        return True
    
    def test_docker_bootstrap_integration(self):
        """Test Docker bootstrap integration with mock responses."""
        logger.info("=== Testing Docker Bootstrap Integration ===")
        
        # Mock successful backend response
        mock_response_data = {
            "agent_id": "agent-docker-test-abc",
            "private_key_b64": "dGVzdC1kb2NrZXItcHJpdmF0ZS1rZXk=",
            "public_key_b64": "dGVzdC1kb2NrZXItcHVibGljLWtleQ=="
        }
        
        with patch('httpx.Client.post') as mock_post:
            # Mock successful HTTP response
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response
            
            # Mock keyring storage
            with patch('keyring.set_password') as mock_keyring_set, \
                 patch('keyring.get_password') as mock_keyring_get:
                
                mock_keyring_get.return_value = mock_response_data["private_key_b64"]
                
                try:
                    # Test AgentClient bootstrap
                    agent_client = AgentClient(api_url=self.control_plane_url, silent_mode=True)
                    result = agent_client.bootstrap_docker("mock-docker-runtime-token")
                    
                    # Validate result
                    assert result["agent_id"] == mock_response_data["agent_id"]
                    assert result["bootstrap_platform"] == "docker"
                    assert result["success"] == True
                    
                    # Verify backend call was made correctly
                    mock_post.assert_called_once()
                    call_args = mock_post.call_args
                    assert "/api/v1/auth/bootstrap/docker" in call_args[0][0]
                    assert call_args[1]["json"]["token"] == "mock-docker-runtime-token"
                    
                    logger.info("✓ Docker bootstrap integration successful")
                    
                except Exception as e:
                    logger.error(f"✗ Docker bootstrap integration failed: {e}")
                    return False
                    
        return True
    
    def test_error_handling_integration(self):
        """Test error handling integration with structured backend errors."""
        logger.info("=== Testing Error Handling Integration ===")
        
        error_test_cases = [
            {
                "name": "Token Validation Error",
                "status_code": 401,
                "error_response": {
                    "detail": {
                        "error": "token_validation_failed",
                        "message": "Invalid token signature",
                        "error_code": "TOKEN_VALIDATION_FAILED",
                        "platform": "kubernetes",
                        "correlation_id": "test-correlation-123"
                    }
                },
                "expected_message": "Token validation failed"
            },
            {
                "name": "Policy Not Found Error",
                "status_code": 403,
                "error_response": {
                    "detail": {
                        "error": "policy_not_found",
                        "message": "No matching policy found",
                        "error_code": "POLICY_NOT_FOUND",
                        "platform": "kubernetes",
                        "correlation_id": "test-correlation-456"
                    }
                },
                "expected_message": "No matching policy found"
            },
            {
                "name": "External Service Error",
                "status_code": 502,
                "error_response": {
                    "detail": {
                        "error": "external_service_error",
                        "message": "External service temporarily unavailable",
                        "error_code": "EXTERNAL_SERVICE_ERROR",
                        "platform": "aws",
                        "correlation_id": "test-correlation-789"
                    }
                },
                "expected_message": "External service unavailable"
            },
            {
                "name": "Network Timeout Error",
                "status_code": 504,
                "error_response": {
                    "detail": {
                        "error": "network_timeout",
                        "message": "Request timed out",
                        "error_code": "NETWORK_TIMEOUT",
                        "platform": "azure",
                        "correlation_id": "test-correlation-999"
                    }
                },
                "expected_message": "Bootstrap timeout"
            }
        ]
        
        success_count = 0
        
        for test_case in error_test_cases:
            try:
                with patch('httpx.Client.post') as mock_post:
                    # Mock HTTP error response
                    from httpx import HTTPStatusError, Response, Request
                    
                    mock_response = MagicMock()
                    mock_response.status_code = test_case["status_code"]
                    mock_response.json.return_value = test_case["error_response"]
                    mock_response.text = json.dumps(test_case["error_response"])
                    
                    # Create mock request for HTTPStatusError
                    mock_request = MagicMock()
                    mock_post.side_effect = HTTPStatusError(
                        message=f"HTTP {test_case['status_code']}",
                        request=mock_request,
                        response=mock_response
                    )
                    
                    # Test error handling
                    agent_client = AgentClient(api_url=self.control_plane_url, silent_mode=True)
                    
                    try:
                        result = agent_client.bootstrap_kubernetes("invalid-token")
                        logger.error(f"✗ {test_case['name']}: Expected error but got success")
                    except DeepSecureClientError as e:
                        if test_case["expected_message"] in str(e):
                            logger.info(f"✓ {test_case['name']}: Error handled correctly")
                            success_count += 1
                        else:
                            logger.error(f"✗ {test_case['name']}: Unexpected error message: {e}")
                    except Exception as e:
                        logger.error(f"✗ {test_case['name']}: Unexpected exception type: {type(e).__name__}: {e}")
                        
            except Exception as e:
                logger.error(f"✗ {test_case['name']}: Test setup failed: {e}")
        
        logger.info(f"Error handling integration: {success_count}/{len(error_test_cases)} tests passed")
        return success_count == len(error_test_cases)
    
    def test_identity_provider_integration(self):
        """Test identity provider integration with enhanced backend."""
        logger.info("=== Testing Identity Provider Integration ===")
        
        mock_client = MagicMock()
        
        # Test Kubernetes Identity Provider
        try:
            k8s_provider = KubernetesIdentityProvider(client=mock_client, silent_mode=True)
            
            # Mock file system calls
            with patch('os.path.exists') as mock_exists, \
                 patch('builtins.open', create=True) as mock_open:
                
                mock_exists.return_value = True
                mock_open.return_value.__enter__.return_value.read.return_value = "mock-k8s-token"
                
                # Mock bootstrap response
                mock_client.bootstrap_kubernetes.return_value = {
                    "agent_id": "agent-k8s-provider-test",
                    "public_key": "mock-public-key"
                }
                
                # Mock keyring
                with patch('keyring.get_password') as mock_keyring_get:
                    mock_keyring_get.return_value = "mock-private-key"
                    
                    identity = k8s_provider.get_identity("test-agent")
                    
                    if identity and identity.agent_id == "agent-k8s-provider-test":
                        logger.info("✓ Kubernetes Identity Provider integration successful")
                    else:
                        logger.error("✗ Kubernetes Identity Provider integration failed")
                        return False
                        
        except Exception as e:
            logger.error(f"✗ Kubernetes Identity Provider integration failed: {e}")
            return False
        
        # Test Azure Identity Provider
        try:
            azure_provider = AzureIdentityProvider(client=mock_client, silent_mode=True)
            
            # Mock Azure IMDS calls
            with patch('requests.get') as mock_requests:
                # Mock IMDS availability check
                mock_instance_response = MagicMock()
                mock_instance_response.status_code = 200
                
                # Mock token response
                mock_token_response = MagicMock()
                mock_token_response.json.return_value = {"access_token": "mock-azure-token"}
                mock_token_response.raise_for_status.return_value = None
                
                mock_requests.side_effect = [mock_instance_response, mock_token_response]
                
                # Mock bootstrap response
                mock_client.bootstrap_azure.return_value = {
                    "agent_id": "agent-azure-provider-test",
                    "public_key": "mock-azure-public-key"
                }
                
                # Mock keyring
                with patch('keyring.get_password') as mock_keyring_get:
                    mock_keyring_get.return_value = "mock-azure-private-key"
                    
                    identity = azure_provider.get_identity("test-agent")
                    
                    if identity and identity.agent_id == "agent-azure-provider-test":
                        logger.info("✓ Azure Identity Provider integration successful")
                    else:
                        logger.error("✗ Azure Identity Provider integration failed")
                        return False
                        
        except Exception as e:
            logger.error(f"✗ Azure Identity Provider integration failed: {e}")
            return False
        
        return True
    
    def test_correlation_id_integration(self):
        """Test correlation ID integration for audit logging."""
        logger.info("=== Testing Correlation ID Integration ===")
        
        with patch('httpx.Client.post') as mock_post:
            # Mock successful HTTP response
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "agent_id": "agent-correlation-test",
                "private_key_b64": "dGVzdA==",
                "public_key_b64": "dGVzdA=="
            }
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response
            
            with patch('keyring.set_password'), patch('keyring.get_password') as mock_get:
                mock_get.return_value = "dGVzdA=="
                
                try:
                    agent_client = AgentClient(api_url=self.control_plane_url, silent_mode=True)
                    result = agent_client.bootstrap_kubernetes("test-token")
                    
                    # Verify correlation ID header was sent
                    mock_post.assert_called_once()
                    call_args = mock_post.call_args
                    headers = call_args[1].get("headers", {})
                    
                    if "X-Correlation-ID" in headers:
                        logger.info("✓ Correlation ID integration successful")
                        return True
                    else:
                        logger.error("✗ Correlation ID header not found in request")
                        return False
                        
                except Exception as e:
                    logger.error(f"✗ Correlation ID integration failed: {e}")
                    return False
    
    def run_all_tests(self):
        """Run all SDK bootstrap integration tests."""
        logger.info("🔗 Starting SDK Bootstrap Integration Tests")
        logger.info("=" * 60)
        
        test_results = []
        
        try:
            # Run all test methods
            test_results.append(("Kubernetes Bootstrap", self.test_kubernetes_bootstrap_integration()))
            test_results.append(("AWS Bootstrap", self.test_aws_bootstrap_integration()))
            test_results.append(("Azure Bootstrap", self.test_azure_bootstrap_integration()))
            test_results.append(("Docker Bootstrap", self.test_docker_bootstrap_integration()))
            test_results.append(("Error Handling", self.test_error_handling_integration()))
            test_results.append(("Identity Providers", self.test_identity_provider_integration()))
            test_results.append(("Correlation IDs", self.test_correlation_id_integration()))
            
            # Summary
            passed = sum(1 for _, result in test_results if result)
            total = len(test_results)
            
            logger.info("=" * 60)
            logger.info(f"SDK Bootstrap Integration Tests: {passed}/{total} passed")
            logger.info("")
            
            for test_name, result in test_results:
                status = "✅ PASS" if result else "❌ FAIL"
                logger.info(f"  {status} {test_name}")
            
            if passed == total:
                logger.info("")
                logger.info("🎉 All SDK bootstrap integration tests passed!")
                logger.info("")
                logger.info("Enhanced SDK integration provides:")
                logger.info("  🔗 Seamless backend integration")
                logger.info("  🛡️ Comprehensive error handling")
                logger.info("  🔐 Secure keyring storage")
                logger.info("  📊 Audit logging with correlation IDs")
                logger.info("  🌐 Multi-platform support (K8s, AWS, Azure, Docker)")
                logger.info("  ✅ Response validation and verification")
                logger.info("  🚀 Production-ready reliability")
            else:
                logger.error(f"❌ {total - passed} tests failed. Please review the implementation.")
                
        except Exception as e:
            logger.error(f"Test execution failed: {e}")

if __name__ == "__main__":
    tester = SDKBootstrapIntegrationTester()
    tester.run_all_tests() 