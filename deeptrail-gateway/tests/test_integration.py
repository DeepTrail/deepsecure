"""
Integration tests for DeepTrail Gateway with DeepTrail Control service.

These tests verify end-to-end functionality between the gateway and control plane,
including authentication, policy enforcement, secret injection, and proxy forwarding.
"""

import pytest
import asyncio
import json
import time
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, Optional

import httpx
from fastapi.testclient import TestClient

# Test configuration
DEEPTRAIL_CONTROL_URL = os.getenv("DEEPTRAIL_CONTROL_URL", "http://localhost:8000")
DEEPTRAIL_GATEWAY_URL = os.getenv("DEEPTRAIL_GATEWAY_URL", "http://localhost:8002")
TEST_TIMEOUT = 30  # seconds


@pytest.fixture(scope="module")
def integration_config():
    """Configuration for integration tests."""
    return {
        "control_plane_url": DEEPTRAIL_CONTROL_URL,
        "gateway_url": DEEPTRAIL_GATEWAY_URL,
        "timeout": TEST_TIMEOUT,
        "test_agent_name": "test-integration-agent",
        "test_service_url": "https://httpbin.org"
    }


@pytest.fixture(scope="module")
async def http_client():
    """Async HTTP client for integration tests."""
    async with httpx.AsyncClient(timeout=TEST_TIMEOUT) as client:
        yield client


@pytest.fixture
def mock_deepsecure_client():
    """Mock DeepSecure client for testing SDK integration."""
    with patch('deepsecure.Client') as mock_client:
        # Mock the client instance
        client_instance = Mock()
        
        # Mock agent creation
        mock_agent = Mock()
        mock_agent.id = "agent-12345678-1234-1234-1234-123456789012"
        mock_agent.name = "test-integration-agent"
        mock_agent.public_key = "test-public-key"
        
        client_instance.agents.create.return_value = mock_agent
        client_instance.agents.get.return_value = mock_agent
        
        # Mock credential issuance
        mock_credential = Mock()
        mock_credential.id = "cred-12345678-1234-1234-1234-123456789012"
        mock_credential.access_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZ2VudC0xMjM0NTY3OC0xMjM0LTEyMzQtMTIzNC0xMjM0NTY3ODkwMTIiLCJpYXQiOjE2MjM5NzYwMDAsImV4cCI6MTYyMzk3OTYwMCwic2NvcGUiOiJyZWFkOndlYiIsInJlc291cmNlIjoiaHR0cHM6Ly9odHRwYmluLm9yZyJ9.test-signature"
        mock_credential.expires_at = int(time.time()) + 3600
        
        client_instance.vault.issue_credential.return_value = mock_credential
        
        # Mock secret fetching
        mock_secret = Mock()
        mock_secret.name = "test-api-key"
        mock_secret.value = "sk-test-api-key-value"
        
        client_instance.vault.get_secret.return_value = mock_secret
        
        mock_client.return_value = client_instance
        yield client_instance


@pytest.mark.integration
class TestGatewayControlPlaneIntegration:
    """Test integration between gateway and control plane."""
    
    async def test_gateway_health_check(self, http_client: httpx.AsyncClient, integration_config: Dict[str, Any]):
        """Test that the gateway is healthy and responding."""
        response = await http_client.get(f"{integration_config['gateway_url']}/health")
        assert response.status_code == 200
        
        health_data = response.json()
        assert health_data["service"] == "DeepSecure Gateway"
        # Version should be dynamically loaded from environment or config
        assert "version" in health_data
        assert health_data["version"] is not None
        assert health_data["status"] == "ok"
        assert "dependencies" in health_data
        assert "control_plane" in health_data["dependencies"]
        assert "redis" in health_data["dependencies"]
    
    async def test_control_plane_health_check(self, http_client: httpx.AsyncClient, integration_config: Dict[str, Any]):
        """Test that the control plane is healthy and responding."""
        response = await http_client.get(f"{integration_config['control_plane_url']}/health")
        assert response.status_code == 200
        
        health_data = response.json()
        assert health_data["service"] == "DeepSecure Control Plane"
        assert health_data["status"] == "ok"
        assert "version" in health_data
        assert "dependencies" in health_data
        assert "database" in health_data["dependencies"]
    
    async def test_gateway_proxy_without_auth(self, http_client: httpx.AsyncClient, integration_config: Dict[str, Any]):
        """Test that the gateway rejects requests without authentication."""
        headers = {
            "X-Target-Base-URL": integration_config["test_service_url"]
        }
        
        response = await http_client.get(
            f"{integration_config['gateway_url']}/proxy/get",
            headers=headers
        )
        
        # Should be rejected due to missing authentication
        assert response.status_code == 401
        assert "Authorization" in response.text or "Unauthorized" in response.text
    
    async def test_gateway_proxy_with_invalid_jwt(self, http_client: httpx.AsyncClient, integration_config: Dict[str, Any]):
        """Test that the gateway rejects requests with invalid JWT."""
        headers = {
            "X-Target-Base-URL": integration_config["test_service_url"],
            "Authorization": "Bearer invalid-jwt-token"
        }
        
        response = await http_client.get(
            f"{integration_config['gateway_url']}/proxy/get",
            headers=headers
        )
        
        # Should be rejected due to invalid JWT
        assert response.status_code == 401
        assert "invalid" in response.text.lower() or "unauthorized" in response.text.lower()
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    async def test_gateway_proxy_with_valid_jwt(self, mock_jwt_validation, http_client: httpx.AsyncClient, integration_config: Dict[str, Any]):
        """Test that the gateway forwards requests with valid JWT."""
        # Mock JWT validation to return valid agent info
        mock_jwt_validation.return_value = {
            "agent_id": "agent-12345678-1234-1234-1234-123456789012",
            "sub": "agent-12345678-1234-1234-1234-123456789012",
            "scope": "read:web",
            "resource": "https://httpbin.org",
            "exp": int(time.time()) + 3600
        }
        
        headers = {
            "X-Target-Base-URL": integration_config["test_service_url"],
            "Authorization": "Bearer valid-jwt-token"
        }
        
        with patch('app.core.http_client.get_http_client') as mock_http_client:
            # Mock the HTTP client response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"Content-Type": "application/json"}
            mock_response.content = b'{"test": "success"}'
            mock_response.text = '{"test": "success"}'
            
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_http_client.return_value = mock_client
            
            response = await http_client.get(
                f"{integration_config['gateway_url']}/proxy/get",
                headers=headers
            )
            
            # Should be successful
            assert response.status_code == 200
            assert "test" in response.text


@pytest.mark.integration
class TestDeepSecureSDKIntegration:
    """Test integration with the DeepSecure SDK."""
    
    def test_sdk_client_initialization(self, mock_deepsecure_client, integration_config: Dict[str, Any]):
        """Test that the SDK client can be initialized with gateway URL."""
        from deepsecure import Client
        
        # Test client initialization
        client = Client(
            deeptrail_control_url=integration_config["control_plane_url"],
            deeptrail_gateway_url=integration_config["gateway_url"]
        )
        
        assert client is not None
        assert client.gateway_url == integration_config["gateway_url"]
    
    def test_sdk_agent_creation(self, mock_deepsecure_client, integration_config: Dict[str, Any]):
        """Test agent creation through the SDK."""
        from deepsecure import Client
        
        client = Client(
            deeptrail_control_url=integration_config["control_plane_url"],
            deeptrail_gateway_url=integration_config["gateway_url"]
        )
        
        # Test agent creation
        agent = client.agents.create(name=integration_config["test_agent_name"])
        
        assert agent is not None
        assert agent.name == integration_config["test_agent_name"]
        assert agent.id.startswith("agent-")
        assert agent.public_key is not None
    
    def test_sdk_credential_issuance(self, mock_deepsecure_client, integration_config: Dict[str, Any]):
        """Test credential issuance through the SDK."""
        from deepsecure import Client
        
        client = Client(
            deeptrail_control_url=integration_config["control_plane_url"],
            deeptrail_gateway_url=integration_config["gateway_url"]
        )
        
        # Test credential issuance
        credential = client.vault.issue_credential(
            agent_id="agent-12345678-1234-1234-1234-123456789012",
            scope="read:web",
            resource="https://httpbin.org"
        )
        
        assert credential is not None
        assert credential.access_token is not None
        assert credential.expires_at > int(time.time())
    
    def test_sdk_secret_fetching(self, mock_deepsecure_client, integration_config: Dict[str, Any]):
        """Test secret fetching through the SDK."""
        from deepsecure import Client
        
        client = Client(
            deeptrail_control_url=integration_config["control_plane_url"],
            deeptrail_gateway_url=integration_config["gateway_url"]
        )
        
        # Test secret fetching
        secret = client.vault.get_secret(
            agent_id="agent-12345678-1234-1234-1234-123456789012",
            secret_name="test-api-key"
        )
        
        assert secret is not None
        assert secret.name == "test-api-key"
        assert secret.value == "sk-test-api-key-value"


@pytest.mark.integration
@pytest.mark.e2e
class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    @patch('app.middleware.secret_injection.SecretInjectionMiddleware._inject_secrets')
    async def test_complete_proxy_workflow(self, mock_secret_injection, mock_jwt_validation, 
                                         http_client: httpx.AsyncClient, integration_config: Dict[str, Any]):
        """Test complete workflow: authentication -> policy check -> secret injection -> proxy."""
        
        # Mock JWT validation
        mock_jwt_validation.return_value = {
            "agent_id": "agent-12345678-1234-1234-1234-123456789012",
            "sub": "agent-12345678-1234-1234-1234-123456789012",
            "scope": "read:web",
            "resource": "https://httpbin.org",
            "exp": int(time.time()) + 3600
        }
        
        # Mock secret injection
        mock_secret_injection.return_value = {
            "Authorization": "Bearer injected-api-key"
        }
        
        headers = {
            "X-Target-Base-URL": integration_config["test_service_url"],
            "Authorization": "Bearer valid-jwt-token"
        }
        
        with patch('app.core.http_client.get_http_client') as mock_http_client:
            # Mock the HTTP client response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"Content-Type": "application/json"}
            mock_response.content = b'{"headers": {"Authorization": "Bearer injected-api-key"}}'
            mock_response.text = '{"headers": {"Authorization": "Bearer injected-api-key"}}'
            
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_http_client.return_value = mock_client
            
            response = await http_client.get(
                f"{integration_config['gateway_url']}/proxy/headers",
                headers=headers
            )
            
            # Verify the complete workflow
            assert response.status_code == 200
            
            # Verify JWT validation was called
            mock_jwt_validation.assert_called_once()
            
            # Verify secret injection was called
            mock_secret_injection.assert_called_once()
            
            # Verify the proxied request included the injected secret
            response_data = response.json()
            assert "headers" in response_data
            assert response_data["headers"]["Authorization"] == "Bearer injected-api-key"
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    @patch('app.middleware.policy_enforcement.PolicyEnforcementMiddleware._enforce_policy')
    async def test_policy_enforcement_workflow(self, mock_policy_enforcement, mock_jwt_validation,
                                             http_client: httpx.AsyncClient, integration_config: Dict[str, Any]):
        """Test policy enforcement in the complete workflow."""
        
        # Mock JWT validation
        mock_jwt_validation.return_value = {
            "agent_id": "agent-12345678-1234-1234-1234-123456789012",
            "sub": "agent-12345678-1234-1234-1234-123456789012",
            "scope": "read:web",
            "resource": "https://httpbin.org",
            "exp": int(time.time()) + 3600
        }
        
        # Mock policy enforcement - allow the request
        mock_policy_enforcement.return_value = True
        
        headers = {
            "X-Target-Base-URL": integration_config["test_service_url"],
            "Authorization": "Bearer valid-jwt-token"
        }
        
        with patch('app.core.http_client.get_http_client') as mock_http_client:
            # Mock the HTTP client response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"Content-Type": "application/json"}
            mock_response.content = b'{"test": "policy-allowed"}'
            mock_response.text = '{"test": "policy-allowed"}'
            
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_http_client.return_value = mock_client
            
            response = await http_client.get(
                f"{integration_config['gateway_url']}/proxy/get",
                headers=headers
            )
            
            # Verify policy enforcement was called
            mock_policy_enforcement.assert_called_once()
            
            # Verify request was allowed
            assert response.status_code == 200
            assert "policy-allowed" in response.text
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    @patch('app.middleware.policy_enforcement.PolicyEnforcementMiddleware._enforce_policy')
    async def test_policy_denial_workflow(self, mock_policy_enforcement, mock_jwt_validation,
                                        http_client: httpx.AsyncClient, integration_config: Dict[str, Any]):
        """Test policy denial in the complete workflow."""
        
        # Mock JWT validation
        mock_jwt_validation.return_value = {
            "agent_id": "agent-12345678-1234-1234-1234-123456789012",
            "sub": "agent-12345678-1234-1234-1234-123456789012",
            "scope": "read:web",
            "resource": "https://httpbin.org",
            "exp": int(time.time()) + 3600
        }
        
        # Mock policy enforcement - deny the request
        mock_policy_enforcement.return_value = False
        
        headers = {
            "X-Target-Base-URL": integration_config["test_service_url"],
            "Authorization": "Bearer valid-jwt-token"
        }
        
        response = await http_client.get(
            f"{integration_config['gateway_url']}/proxy/get",
            headers=headers
        )
        
        # Verify policy enforcement was called
        mock_policy_enforcement.assert_called_once()
        
        # Verify request was denied
        assert response.status_code == 403
        assert "forbidden" in response.text.lower() or "denied" in response.text.lower()


@pytest.mark.integration
@pytest.mark.performance
class TestPerformanceIntegration:
    """Test performance characteristics of the integration."""
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    async def test_gateway_response_time(self, mock_jwt_validation, http_client: httpx.AsyncClient, 
                                       integration_config: Dict[str, Any]):
        """Test that the gateway responds within acceptable time limits."""
        
        # Mock JWT validation
        mock_jwt_validation.return_value = {
            "agent_id": "agent-12345678-1234-1234-1234-123456789012",
            "sub": "agent-12345678-1234-1234-1234-123456789012",
            "scope": "read:web",
            "resource": "https://httpbin.org",
            "exp": int(time.time()) + 3600
        }
        
        headers = {
            "X-Target-Base-URL": integration_config["test_service_url"],
            "Authorization": "Bearer valid-jwt-token"
        }
        
        with patch('app.core.http_client.get_http_client') as mock_http_client:
            # Mock the HTTP client response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"Content-Type": "application/json"}
            mock_response.content = b'{"test": "performance"}'
            mock_response.text = '{"test": "performance"}'
            
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_http_client.return_value = mock_client
            
            start_time = time.time()
            response = await http_client.get(
                f"{integration_config['gateway_url']}/proxy/get",
                headers=headers
            )
            end_time = time.time()
            
            # Verify response time is acceptable (< 1 second for mocked response)
            response_time = end_time - start_time
            assert response_time < 1.0, f"Response time {response_time:.2f}s exceeds 1.0s limit"
            
            # Verify response is successful
            assert response.status_code == 200
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    async def test_concurrent_requests(self, mock_jwt_validation, http_client: httpx.AsyncClient,
                                     integration_config: Dict[str, Any]):
        """Test that the gateway handles concurrent requests properly."""
        
        # Mock JWT validation
        mock_jwt_validation.return_value = {
            "agent_id": "agent-12345678-1234-1234-1234-123456789012",
            "sub": "agent-12345678-1234-1234-1234-123456789012",
            "scope": "read:web",
            "resource": "https://httpbin.org",
            "exp": int(time.time()) + 3600
        }
        
        headers = {
            "X-Target-Base-URL": integration_config["test_service_url"],
            "Authorization": "Bearer valid-jwt-token"
        }
        
        with patch('app.core.http_client.get_http_client') as mock_http_client:
            # Mock the HTTP client response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"Content-Type": "application/json"}
            mock_response.content = b'{"test": "concurrent"}'
            mock_response.text = '{"test": "concurrent"}'
            
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_http_client.return_value = mock_client
            
            # Create multiple concurrent requests
            tasks = []
            for i in range(10):
                task = http_client.get(
                    f"{integration_config['gateway_url']}/proxy/get",
                    headers=headers
                )
                tasks.append(task)
            
            # Execute all requests concurrently
            responses = await asyncio.gather(*tasks)
            
            # Verify all requests were successful
            for response in responses:
                assert response.status_code == 200
                assert "concurrent" in response.text


@pytest.mark.integration
@pytest.mark.security
class TestSecurityIntegration:
    """Test security aspects of the integration."""
    
    async def test_blocked_internal_ips(self, http_client: httpx.AsyncClient, integration_config: Dict[str, Any]):
        """Test that requests to internal IPs are blocked."""
        internal_urls = [
            "http://127.0.0.1:8080",
            "http://localhost:8080",
            "http://10.0.0.1:8080",
            "http://192.168.1.1:8080",
            "http://172.16.0.1:8080"
        ]
        
        for internal_url in internal_urls:
            headers = {
                "X-Target-Base-URL": internal_url,
                "Authorization": "Bearer valid-jwt-token"
            }
            
            response = await http_client.get(
                f"{integration_config['gateway_url']}/proxy/get",
                headers=headers
            )
            
            # Should be blocked due to internal IP
            assert response.status_code in [400, 403], f"Internal URL {internal_url} should be blocked"
    
    async def test_missing_target_url_header(self, http_client: httpx.AsyncClient, integration_config: Dict[str, Any]):
        """Test that requests without target URL header are rejected."""
        headers = {
            "Authorization": "Bearer valid-jwt-token"
        }
        
        response = await http_client.get(
            f"{integration_config['gateway_url']}/proxy/get",
            headers=headers
        )
        
        # Should be rejected due to missing target URL header
        assert response.status_code == 400
        assert "target" in response.text.lower() or "url" in response.text.lower()
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    async def test_request_size_limits(self, mock_jwt_validation, http_client: httpx.AsyncClient,
                                     integration_config: Dict[str, Any]):
        """Test that large requests are handled appropriately."""
        
        # Mock JWT validation
        mock_jwt_validation.return_value = {
            "agent_id": "agent-12345678-1234-1234-1234-123456789012",
            "sub": "agent-12345678-1234-1234-1234-123456789012",
            "scope": "write:web",
            "resource": "https://httpbin.org",
            "exp": int(time.time()) + 3600
        }
        
        headers = {
            "X-Target-Base-URL": integration_config["test_service_url"],
            "Authorization": "Bearer valid-jwt-token",
            "Content-Type": "application/json"
        }
        
        # Create a large payload (1MB)
        large_payload = {"data": "x" * (1024 * 1024)}
        
        with patch('app.core.http_client.get_http_client') as mock_http_client:
            # Mock the HTTP client response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"Content-Type": "application/json"}
            mock_response.content = b'{"received": "large_payload"}'
            mock_response.text = '{"received": "large_payload"}'
            
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_http_client.return_value = mock_client
            
            response = await http_client.post(
                f"{integration_config['gateway_url']}/proxy/post",
                headers=headers,
                json=large_payload
            )
            
            # Should handle large requests appropriately
            # (either accept them or reject with appropriate error)
            assert response.status_code in [200, 413, 400] 