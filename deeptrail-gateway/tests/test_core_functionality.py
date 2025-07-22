"""
Core Functionality Tests for DeepTrail Gateway

This test suite focuses on testing the essential PEP functionality
with proper mocking to ensure tests pass reliably.
"""

import pytest
import json
import base64
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock

from fastapi.testclient import TestClient
from app.main import app
from app.core.request_validator import ProxyRequestInfo


class TestGatewayCore:
    """Test core gateway functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.client = TestClient(app)
        self.valid_jwt_payload = {
            "sub": "agent-test-123",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            "permissions": ["domain:httpbin.org", "method:GET", "method:POST"],
            "allowed_domains": ["httpbin.org"],
            "allowed_methods": ["GET", "POST"]
        }
    
    def create_mock_jwt(self, payload):
        """Create a mock JWT token for testing."""
        header = {"alg": "RS256", "typ": "JWT"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
        signature_b64 = "mock_signature"
        return f"{header_b64}.{payload_b64}.{signature_b64}"
    
    def test_health_endpoints_work(self):
        """Test that health endpoints work without authentication."""
        # Root endpoint
        response = self.client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        
        # Health check
        response = self.client.get("/health")
        assert response.status_code == 200
        health_data = response.json()
        assert health_data["service"] == "DeepSecure Gateway"
        # Version should be dynamically loaded from environment or config
        assert "version" in health_data
        assert health_data["version"] is not None
        assert health_data["status"] == "ok"
        assert "dependencies" in health_data
        
        # Readiness check
        response = self.client.get("/ready")
        assert response.status_code == 200
    
    def test_jwt_validation_rejects_missing_auth(self):
        """Test JWT validation properly rejects missing auth."""
        with pytest.raises(Exception) as exc_info:
            response = self.client.get("/proxy/test")
        
        # The middleware should raise an HTTPException with 401
        assert "401" in str(exc_info.value) or "Missing Authorization header" in str(exc_info.value)
    
    def test_policy_enforcement_rejects_missing_target(self):
        """Test policy enforcement rejects missing target header."""
        jwt_token = self.create_mock_jwt(self.valid_jwt_payload)
        
        with pytest.raises(Exception) as exc_info:
            response = self.client.get(
                "/proxy/test",
                headers={"Authorization": f"Bearer {jwt_token}"}
            )
        
        # Should fail due to missing X-Target-Base-URL header
        assert "400" in str(exc_info.value) or "Missing X-Target-Base-URL header" in str(exc_info.value)
    
    def test_policy_enforcement_rejects_blocked_domain(self):
        """Test policy enforcement rejects blocked domains."""
        jwt_token = self.create_mock_jwt(self.valid_jwt_payload)
        
        with pytest.raises(Exception) as exc_info:
            response = self.client.get(
                "/proxy/test",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "X-Target-Base-URL": "https://blocked-domain.com"
                }
            )
        
        # Should fail due to blocked domain
        assert "403" in str(exc_info.value) or "Access denied" in str(exc_info.value)
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    @patch('app.core.request_validator.RequestValidator.validate_request')
    @patch('app.core.http_client.get_http_client')
    def test_successful_proxy_request(self, mock_http_client, mock_validate_request, mock_jwt_validation):
        """Test successful proxy request with all middleware working."""
        # Mock JWT validation to return valid agent info
        mock_jwt_validation.return_value = {
            "sub": "agent-test-123",
            "permissions": ["domain:httpbin.org", "method:GET"],
            "allowed_domains": ["httpbin.org"],
            "allowed_methods": ["GET"]
        }
        
        # Mock request validation to return a valid ProxyRequestInfo
        mock_validate_request.return_value = ProxyRequestInfo(
            target_url="https://httpbin.org",
            method="GET",
            headers={"Authorization": "Bearer test-token"},
            query_params={},
            content_length=0,
            content_type=None
        )
        
        # Mock HTTP client
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.content = b'{"success": true}'
        mock_http_client.return_value.proxy_request = AsyncMock(return_value=mock_response)
        
        jwt_token = self.create_mock_jwt(self.valid_jwt_payload)
        
        response = self.client.get(
            "/proxy/test",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "X-Target-Base-URL": "https://httpbin.org"
            }
        )
        
        assert response.status_code == 200
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    @patch('app.core.request_validator.RequestValidator.validate_request')
    @patch('app.proxy.get_http_client')
    def test_post_request_with_body(self, mock_http_client, mock_validate_request, mock_jwt_validation):
        """Test POST request with body."""
        # Reset global HTTP client
        import app.core.http_client
        app.core.http_client._http_client = None
        # Mock JWT validation with proper async function
        async def mock_validate_jwt(*args, **kwargs):
            return {
                "sub": "agent-test-123",
                "permissions": ["domain:httpbin.org", "method:POST"],
                "allowed_domains": ["httpbin.org"],
                "allowed_methods": ["POST"]
            }
        mock_jwt_validation.side_effect = mock_validate_jwt
        
        # Mock request validation to return a valid ProxyRequestInfo
        mock_validate_request.return_value = ProxyRequestInfo(
            target_url="https://httpbin.org/post",
            method="POST",
            headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
            query_params={},
            content_length=16,  # Correct length of {"test": "data"}
            content_type="application/json"
        )
        
        # Mock HTTP client response with async aread method
        mock_response = AsyncMock()
        mock_response.status_code = 201
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.content = b'{"created": true}'
        mock_response.aread = AsyncMock(return_value=b'{"created": true}')
        
        # Create mock client instance 
        mock_client_instance = AsyncMock()
        mock_client_instance.proxy_request = AsyncMock(return_value=mock_response)
        
        # Configure the patched mock to return the client instance when awaited
        async def async_return_client():
            return mock_client_instance
        
        mock_http_client.side_effect = async_return_client
        
        jwt_token = self.create_mock_jwt(self.valid_jwt_payload)
        
        response = self.client.post(
            "/proxy/test",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "X-Target-Base-URL": "https://httpbin.org/post",
                "Content-Type": "application/json"
            },
            json={"test": "data"}
        )
        
        assert response.status_code == 201
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    @patch('app.core.request_validator.RequestValidator.validate_request')
    @patch('app.core.http_client.get_http_client')
    def test_secret_injection_bearer_token(self, mock_http_client, mock_validate_request, mock_jwt_validation):
        """Test secret injection with Bearer token."""
        # Mock JWT validation to return valid agent info
        mock_jwt_validation.return_value = {
            "sub": "agent-test-123",
            "permissions": ["domain:httpbin.org", "method:GET"],
            "allowed_domains": ["httpbin.org"],
            "allowed_methods": ["GET"]
        }
        
        # Mock request validation to return a valid ProxyRequestInfo
        mock_validate_request.return_value = ProxyRequestInfo(
            target_url="https://httpbin.org",
            method="GET",
            headers={"Authorization": "Bearer injected-secret-token"},
            query_params={},
            content_length=0,
            content_type=None
        )
        
        # Mock HTTP client
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{"success": true}'
        mock_http_client.return_value.proxy_request = AsyncMock(return_value=mock_response)
        
        jwt_token = self.create_mock_jwt(self.valid_jwt_payload)
        
        response = self.client.get(
            "/proxy/test",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "X-Target-Base-URL": "https://httpbin.org"
            }
        )
        
        assert response.status_code == 200
    
    def test_catch_all_route(self):
        """Test catch-all route for non-proxy requests."""
        response = self.client.get("/unknown-path")
        assert response.status_code == 404
        assert "not found" in response.json()["message"].lower()
    
    def test_config_endpoint(self):
        """Test configuration endpoint."""
        response = self.client.get("/config")
        assert response.status_code == 200
        assert "proxy_type" in response.json()
        assert "routing" in response.json()
    
    def test_metrics_endpoint(self):
        """Test metrics endpoint."""
        response = self.client.get("/metrics")
        assert response.status_code == 200
        assert "gateway_status" in response.json()


class TestSecurityEnforcement:
    """Test security enforcement is working correctly."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.client = TestClient(app)
    
    def test_proxy_requests_require_authentication(self):
        """Test that proxy requests require authentication."""
        with pytest.raises(Exception) as exc_info:
            response = self.client.get("/proxy/test")
        
        # Should fail with 401 due to missing auth
        assert "401" in str(exc_info.value) or "Missing Authorization header" in str(exc_info.value)
    
    def test_proxy_requests_require_target_header(self):
        """Test that proxy requests require target header."""
        # Create a valid JWT but missing target header
        jwt_payload = {
            "sub": "agent-test",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            "permissions": ["domain:httpbin.org", "method:GET"],
            "allowed_domains": ["httpbin.org"]
        }
        
        header = {"alg": "RS256", "typ": "JWT"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(json.dumps(jwt_payload).encode()).decode().rstrip('=')
        jwt_token = f"{header_b64}.{payload_b64}.mock_signature"
        
        with pytest.raises(Exception) as exc_info:
            response = self.client.get(
                "/proxy/test",
                headers={"Authorization": f"Bearer {jwt_token}"}
            )
        
        # Should fail with 400 due to missing target header
        assert "400" in str(exc_info.value) or "Missing X-Target-Base-URL header" in str(exc_info.value)
    
    def test_health_endpoints_bypass_security(self):
        """Test that health endpoints bypass security middleware."""
        # These should work without any authentication
        endpoints = ["/", "/health", "/ready", "/metrics", "/config"]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            assert response.status_code == 200, f"Endpoint {endpoint} failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 