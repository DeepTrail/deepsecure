"""
Comprehensive Tests for DeepTrail Gateway Core PEP Functionality

This test suite validates the essential components of the Policy Enforcement Point (PEP):
- JWT validation middleware
- Policy enforcement middleware  
- Secret injection middleware
- Basic HTTP request proxying
- Integration between all components

Test Structure:
1. Core PEP Component Tests
2. Middleware Integration Tests
3. End-to-End Proxy Tests
4. Security and Error Handling Tests
5. Performance and Edge Case Tests

Key Testing Strategy:
- Mock security middleware for business logic tests
- Test security enforcement separately with proper expectations
- Use proper async mocking patterns for FastAPI
"""

import pytest
import asyncio
import json
import base64
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, Optional

import httpx
from fastapi.testclient import TestClient
from fastapi import FastAPI, Request, HTTPException

# Import the application and components
from app.main import app
from app.middleware.jwt_validation import JWTValidationMiddleware
from app.middleware.policy_enforcement import PolicyEnforcementMiddleware, PolicyResult
from app.middleware.secret_injection import SecretInjectionMiddleware
from app.core.proxy_config import ProxyConfig, load_config
from app.core.request_logger import RequestLogger, LoggingConfig
from app.core.request_validator import ProxyRequestInfo


class TestJWTValidationMiddleware:
    """Test JWT validation middleware functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.client = TestClient(app, raise_server_exceptions=False)
        self.valid_jwt_payload = {
            "sub": "agent-test-123",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            "permissions": ["domain:httpbin.org", "method:GET", "method:POST"],
            "allowed_domains": ["httpbin.org"],
            "allowed_methods": ["GET", "POST"]
        }
    
    def create_mock_jwt(self, payload: Dict[str, Any]) -> str:
        """Create a mock JWT token for testing (not cryptographically secure)."""
        header = {"alg": "RS256", "typ": "JWT"}
        
        # Base64url encode header and payload
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
        signature_b64 = "mock_signature"
        
        return f"{header_b64}.{payload_b64}.{signature_b64}"
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    @patch('app.core.request_validator.RequestValidator.validate_request')
    @patch('app.core.http_client.get_http_client')
    def test_jwt_validation_success(self, mock_client, mock_validate_request, mock_jwt_validation):
        """Test successful JWT validation."""
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
        
        # Mock HTTP client response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.content = b'{"test": "response"}'
        mock_client.return_value.proxy_request = AsyncMock(return_value=mock_response)
        
        jwt_token = self.create_mock_jwt(self.valid_jwt_payload)
        
        response = self.client.get(
            "/proxy/test",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "X-Target-Base-URL": "https://httpbin.org"
            }
        )
        
        # Should not fail JWT validation
        assert response.status_code == 200
        mock_jwt_validation.assert_called_once()
    
    def test_jwt_validation_missing_header(self):
        """Test JWT validation with missing Authorization header."""
        response = self.client.get(
            "/proxy/test",
            headers={"X-Target-Base-URL": "https://httpbin.org"}
        )
        
        assert response.status_code == 401
        assert "Missing Authorization header" in response.json()["detail"]
    
    def test_jwt_validation_invalid_format(self):
        """Test JWT validation with invalid header format."""
        response = self.client.get(
            "/proxy/test",
            headers={
                "Authorization": "Invalid token format",
                "X-Target-Base-URL": "https://httpbin.org"
            }
        )
        
        assert response.status_code == 401
        assert "Invalid Authorization header format" in response.json()["detail"]
    
    def test_jwt_validation_expired_token(self):
        """Test JWT validation with expired token."""
        expired_payload = self.valid_jwt_payload.copy()
        expired_payload["exp"] = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())
        
        jwt_token = self.create_mock_jwt(expired_payload)
        
        response = self.client.get(
            "/proxy/test",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "X-Target-Base-URL": "https://httpbin.org"
            }
        )
        
        assert response.status_code == 401
        assert "JWT token expired" in response.json()["detail"]
    
    def test_jwt_validation_missing_subject(self):
        """Test JWT validation with missing subject claim."""
        invalid_payload = self.valid_jwt_payload.copy()
        del invalid_payload["sub"]
        
        jwt_token = self.create_mock_jwt(invalid_payload)
        
        response = self.client.get(
            "/proxy/test",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "X-Target-Base-URL": "https://httpbin.org"
            }
        )
        
        assert response.status_code == 401
        assert "JWT token missing subject claim" in response.json()["detail"]
    
    def test_jwt_validation_bypassed_for_health_endpoints(self):
        """Test that JWT validation is bypassed for health endpoints."""
        response = self.client.get("/health")
        assert response.status_code == 200
        
        response = self.client.get("/ready")
        assert response.status_code == 200
        
        response = self.client.get("/")
        assert response.status_code == 200


class TestPolicyEnforcementMiddleware:
    """Test policy enforcement middleware functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.client = TestClient(app, raise_server_exceptions=False)
        self.valid_jwt_payload = {
            "sub": "agent-test-123",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            "permissions": ["domain:api.openai.com", "method:GET", "method:POST"],
            "allowed_domains": ["api.openai.com", "httpbin.org"],
            "allowed_methods": ["GET", "POST"]
        }
    
    def create_mock_jwt(self, payload: Dict[str, Any]) -> str:
        """Create a mock JWT token for testing."""
        header = {"alg": "RS256", "typ": "JWT"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
        signature_b64 = "mock_signature"
        return f"{header_b64}.{payload_b64}.{signature_b64}"
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    @patch('app.core.request_validator.RequestValidator.validate_request')
    @patch('app.core.http_client.get_http_client')
    def test_policy_enforcement_allowed_domain(self, mock_client, mock_validate_request, mock_jwt_validation):
        """Test policy enforcement allows access to permitted domain."""
        # Mock JWT validation to return valid agent info
        mock_jwt_validation.return_value = {
            "sub": "agent-test-123",
            "permissions": ["domain:api.openai.com", "method:GET"],
            "allowed_domains": ["api.openai.com"],
            "allowed_methods": ["GET"]
        }
        
        # Mock request validation to return a valid ProxyRequestInfo
        mock_validate_request.return_value = ProxyRequestInfo(
            target_url="https://api.openai.com",
            method="GET",
            headers={"Authorization": "Bearer test-token"},
            query_params={},
            content_length=0,
            content_type=None
        )
        
        # Mock HTTP client response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.content = b'{"test": "response"}'
        mock_client.return_value.proxy_request = AsyncMock(return_value=mock_response)
        
        jwt_token = self.create_mock_jwt(self.valid_jwt_payload)
        
        response = self.client.get(
            "/proxy/test",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "X-Target-Base-URL": "https://api.openai.com"
            }
        )
        
        # Should not fail policy enforcement
        assert response.status_code == 200
        mock_jwt_validation.assert_called_once()
    
    def test_policy_enforcement_blocked_domain(self):
        """Test policy enforcement blocks access to non-permitted domain."""
        jwt_token = self.create_mock_jwt(self.valid_jwt_payload)
        
        response = self.client.get(
            "/proxy/test",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "X-Target-Base-URL": "https://blocked-domain.com"
            }
        )
        
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]
    
    def test_policy_enforcement_allowed_method(self):
        """Test policy enforcement allows permitted HTTP methods."""
        jwt_token = self.create_mock_jwt(self.valid_jwt_payload)
        
        # Test GET method (allowed)
        response = self.client.get(
            "/proxy/test",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "X-Target-Base-URL": "https://api.openai.com"
            }
        )
        assert response.status_code != 403
        
        # Test POST method (allowed)
        response = self.client.post(
            "/proxy/test",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "X-Target-Base-URL": "https://api.openai.com"
            }
        )
        assert response.status_code != 403
    
    def test_policy_enforcement_missing_target_header(self):
        """Test policy enforcement with missing X-Target-Base-URL header."""
        jwt_token = self.create_mock_jwt(self.valid_jwt_payload)
        
        response = self.client.get(
            "/proxy/test",
            headers={"Authorization": f"Bearer {jwt_token}"}
        )
        
        assert response.status_code == 400
        assert "Missing X-Target-Base-URL header" in response.json()["detail"]
    
    def test_policy_enforcement_bypassed_for_health_endpoints(self):
        """Test that policy enforcement is bypassed for health endpoints."""
        response = self.client.get("/health")
        assert response.status_code == 200


class TestSecretInjectionMiddleware:
    """Test secret injection middleware functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.client = TestClient(app, raise_server_exceptions=False)
        self.valid_jwt_payload = {
            "sub": "agent-test-123",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            "permissions": ["domain:api.openai.com", "method:GET"],
            "allowed_domains": ["api.openai.com", "httpbin.org"],
            "allowed_methods": ["GET"]
        }
    
    def create_mock_jwt(self, payload: Dict[str, Any]) -> str:
        """Create a mock JWT token for testing."""
        header = {"alg": "RS256", "typ": "JWT"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
        signature_b64 = "mock_signature"
        return f"{header_b64}.{payload_b64}.{signature_b64}"
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    @patch('app.core.request_validator.RequestValidator.validate_request')
    @patch('app.middleware.secret_injection.SecretInjectionMiddleware._get_secret_for_domain')
    @patch('app.core.http_client.get_http_client')
    def test_secret_injection_bearer_token(self, mock_client, mock_get_secret, mock_validate_request, mock_jwt_validation):
        """Test secret injection with Bearer token."""
        # Mock JWT validation to return valid agent info
        mock_jwt_validation.return_value = {
            "sub": "agent-test-123",
            "permissions": ["domain:api.openai.com", "method:GET"],
            "allowed_domains": ["api.openai.com"],
            "allowed_methods": ["GET"]
        }
        
        # Mock request validation to return a valid ProxyRequestInfo
        mock_validate_request.return_value = ProxyRequestInfo(
            target_url="https://api.openai.com",
            method="GET",
            headers={"Authorization": "Bearer test-token"},
            query_params={},
            content_length=0,
            content_type=None
        )
        
        # Mock secret configuration
        mock_get_secret.return_value = {
            "type": "bearer",
            "value": "test-bearer-token"
        }
        
        # Mock HTTP client response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b"test response"
        mock_client.return_value.proxy_request = AsyncMock(return_value=mock_response)
        
        jwt_token = self.create_mock_jwt(self.valid_jwt_payload)
        
        response = self.client.get(
            "/proxy/test",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "X-Target-Base-URL": "https://api.openai.com"
            }
        )
        
        # Verify the request was made with injected secret
        mock_client.return_value.proxy_request.assert_called_once()
        assert response.status_code == 200
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    @patch('app.core.request_validator.RequestValidator.validate_request')
    @patch('app.middleware.secret_injection.SecretInjectionMiddleware._get_secret_for_domain')
    @patch('app.core.http_client.get_http_client')
    def test_secret_injection_no_secret_needed(self, mock_client, mock_get_secret, mock_validate_request, mock_jwt_validation):
        """Test secret injection when no secret is needed."""
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
        
        # Mock no secret configuration
        mock_get_secret.return_value = {
            "type": "none",
            "value": None
        }
        
        # Mock HTTP client response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b"test response"
        mock_client.return_value.proxy_request = AsyncMock(return_value=mock_response)
        
        jwt_token = self.create_mock_jwt(self.valid_jwt_payload)
        
        response = self.client.get(
            "/proxy/test",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "X-Target-Base-URL": "https://httpbin.org"
            }
        )
        
        assert response.status_code == 200


class TestProxyCore:
    """Test core proxy functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.client = TestClient(app, raise_server_exceptions=False)
        self.valid_jwt_payload = {
            "sub": "agent-test-123",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            "permissions": ["domain:httpbin.org", "method:GET", "method:POST"],
            "allowed_domains": ["httpbin.org"],
            "allowed_methods": ["GET", "POST"]
        }
    
    def create_mock_jwt(self, payload: Dict[str, Any]) -> str:
        """Create a mock JWT token for testing."""
        header = {"alg": "RS256", "typ": "JWT"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
        signature_b64 = "mock_signature"
        return f"{header_b64}.{payload_b64}.{signature_b64}"
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    @patch('app.core.request_validator.RequestValidator.validate_request')
    @patch('app.core.http_client.get_http_client')
    def test_proxy_get_request(self, mock_client, mock_validate_request, mock_jwt_validation):
        """Test basic GET request proxying."""
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
        
        # Mock HTTP client response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.content = b'{"test": "response"}'
        mock_client.return_value.proxy_request = AsyncMock(return_value=mock_response)
        
        jwt_token = self.create_mock_jwt(self.valid_jwt_payload)
        
        response = self.client.get(
            "/proxy/get",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "X-Target-Base-URL": "https://httpbin.org"
            }
        )
        
        assert response.status_code == 200
        mock_client.return_value.proxy_request.assert_called_once()
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    @patch('app.core.request_validator.RequestValidator.validate_request')
    @patch('app.core.http_client.get_http_client')
    def test_proxy_post_request_with_body(self, mock_client, mock_validate_request, mock_jwt_validation):
        """Test POST request proxying with request body."""
        # Mock JWT validation to return valid agent info
        mock_jwt_validation.return_value = {
            "sub": "agent-test-123",
            "permissions": ["domain:httpbin.org", "method:POST"],
            "allowed_domains": ["httpbin.org"],
            "allowed_methods": ["POST"]
        }
        
        # Mock request validation to return a valid ProxyRequestInfo
        mock_validate_request.return_value = ProxyRequestInfo(
            target_url="https://httpbin.org",
            method="POST",
            headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
            query_params={},
            content_length=16,
            content_type="application/json"
        )
        
        # Mock HTTP client response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.content = b'{"created": true}'
        mock_client.return_value.proxy_request = AsyncMock(return_value=mock_response)
        
        jwt_token = self.create_mock_jwt(self.valid_jwt_payload)
        
        response = self.client.post(
            "/proxy/post",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "X-Target-Base-URL": "https://httpbin.org",
                "Content-Type": "application/json"
            },
            json={"test": "data"}
        )
        
        assert response.status_code == 201
        mock_client.return_value.proxy_request.assert_called_once()
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    @patch('app.core.request_validator.RequestValidator.validate_request')
    @patch('app.core.http_client.get_http_client')
    def test_proxy_error_handling(self, mock_client, mock_validate_request, mock_jwt_validation):
        """Test proxy error handling."""
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
        
        # Mock HTTP client to raise an exception
        mock_client.return_value.proxy_request = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
        
        jwt_token = self.create_mock_jwt(self.valid_jwt_payload)
        
        response = self.client.get(
            "/proxy/test",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "X-Target-Base-URL": "https://httpbin.org"
            }
        )
        
        # Should return 500 for connection errors
        assert response.status_code == 500
    
    def test_proxy_request_without_prefix(self):
        """Test that requests without /proxy prefix are handled correctly."""
        response = self.client.get("/test")
        assert response.status_code == 404
        assert "not found" in response.json()["message"].lower()


class TestHealthEndpoints:
    """Test health check and monitoring endpoints."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.client = TestClient(app, raise_server_exceptions=False)
    
    def test_root_endpoint(self):
        """Test root health endpoint."""
        response = self.client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert "DeepTrail Gateway is running" in response.json()["message"]
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        assert response.status_code == 200
        health_data = response.json()
        assert health_data["service"] == "DeepSecure Gateway"
        # Version should be dynamically loaded from environment or config
        assert "version" in health_data
        assert health_data["version"] is not None
        assert health_data["status"] == "ok"
        assert "dependencies" in health_data
    
    def test_ready_endpoint(self):
        """Test readiness check endpoint."""
        response = self.client.get("/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"
    
    def test_metrics_endpoint(self):
        """Test metrics endpoint."""
        response = self.client.get("/metrics")
        assert response.status_code == 200
        assert "requests_processed" in response.json()
        assert "gateway_status" in response.json()
    
    def test_config_endpoint(self):
        """Test configuration endpoint."""
        response = self.client.get("/config")
        assert response.status_code == 200
        assert "proxy_type" in response.json()
        assert "routing" in response.json()
        assert "authentication" in response.json()


class TestEndToEndIntegration:
    """Test end-to-end integration of all components."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.client = TestClient(app, raise_server_exceptions=False)
        self.valid_jwt_payload = {
            "sub": "agent-integration-test",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            "permissions": ["domain:api.openai.com", "method:GET", "method:POST"],
            "allowed_domains": ["api.openai.com", "httpbin.org"],
            "allowed_methods": ["GET", "POST"]
        }
    
    def create_mock_jwt(self, payload: Dict[str, Any]) -> str:
        """Create a mock JWT token for testing."""
        header = {"alg": "RS256", "typ": "JWT"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
        signature_b64 = "mock_signature"
        return f"{header_b64}.{payload_b64}.{signature_b64}"
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    @patch('app.core.request_validator.RequestValidator.validate_request')
    @patch('app.middleware.secret_injection.SecretInjectionMiddleware._get_secret_for_domain')
    @patch('app.core.http_client.get_http_client')
    def test_full_request_flow(self, mock_client, mock_get_secret, mock_validate_request, mock_jwt_validation):
        """Test complete request flow through all middleware."""
        # Mock JWT validation to return valid agent info
        mock_jwt_validation.return_value = {
            "sub": "agent-integration-test",
            "permissions": ["domain:api.openai.com", "method:POST"],
            "allowed_domains": ["api.openai.com"],
            "allowed_methods": ["POST"]
        }
        
        # Mock request validation to return a valid ProxyRequestInfo
        mock_validate_request.return_value = ProxyRequestInfo(
            target_url="https://api.openai.com",
            method="POST",
            headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
            query_params={},
            content_length=100,
            content_type="application/json"
        )
        
        # Mock secret injection
        mock_get_secret.return_value = {
            "type": "bearer",
            "value": "test-api-key"
        }
        
        # Mock HTTP client response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.content = b'{"success": true}'
        mock_client.return_value.proxy_request = AsyncMock(return_value=mock_response)
        
        jwt_token = self.create_mock_jwt(self.valid_jwt_payload)
        
        response = self.client.post(
            "/proxy/chat/completions",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "X-Target-Base-URL": "https://api.openai.com",
                "Content-Type": "application/json"
            },
            json={"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Hello"}]}
        )
        
        # Verify the request went through all middleware successfully
        assert response.status_code == 200
        assert response.json()["success"] is True
        
        # Verify HTTP client was called
        mock_client.return_value.proxy_request.assert_called_once()
        
        # Verify secret injection was attempted
        mock_get_secret.assert_called_once()
    
    def test_security_rejection_flow(self):
        """Test security rejection at different middleware layers."""
        jwt_token = self.create_mock_jwt(self.valid_jwt_payload)
        
        # Test policy enforcement rejection
        response = self.client.get(
            "/proxy/test",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "X-Target-Base-URL": "https://blocked-domain.com"
            }
        )
        
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]


class TestPerformanceAndEdgeCases:
    """Test performance characteristics and edge cases."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.client = TestClient(app, raise_server_exceptions=False)
        self.valid_jwt_payload = {
            "sub": "agent-perf-test",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            "permissions": ["domain:httpbin.org", "method:GET", "method:POST"],
            "allowed_domains": ["httpbin.org"],
            "allowed_methods": ["GET", "POST"]
        }
    
    def create_mock_jwt(self, payload: Dict[str, Any]) -> str:
        """Create a mock JWT token for testing."""
        header = {"alg": "RS256", "typ": "JWT"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
        signature_b64 = "mock_signature"
        return f"{header_b64}.{payload_b64}.{signature_b64}"
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    @patch('app.core.request_validator.RequestValidator.validate_request')
    @patch('app.core.http_client.get_http_client')
    def test_large_request_handling(self, mock_client, mock_validate_request, mock_jwt_validation):
        """Test handling of large requests."""
        # Mock JWT validation to return valid agent info
        mock_jwt_validation.return_value = {
            "sub": "agent-perf-test",
            "permissions": ["domain:httpbin.org", "method:POST"],
            "allowed_domains": ["httpbin.org"],
            "allowed_methods": ["POST"]
        }
        
        # Mock request validation to return a valid ProxyRequestInfo
        mock_validate_request.return_value = ProxyRequestInfo(
            target_url="https://httpbin.org",
            method="POST",
            headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
            query_params={},
            content_length=1000,
            content_type="application/json"
        )
        
        # Mock HTTP client response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{"processed": true}'
        mock_client.return_value.proxy_request = AsyncMock(return_value=mock_response)
        
        jwt_token = self.create_mock_jwt(self.valid_jwt_payload)
        
        # Create a large payload (but within limits)
        large_data = {"data": "x" * 1000}
        
        response = self.client.post(
            "/proxy/test",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "X-Target-Base-URL": "https://httpbin.org",
                "Content-Type": "application/json"
            },
            json=large_data
        )
        
        assert response.status_code == 200
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    @patch('app.core.request_validator.RequestValidator.validate_request')
    @patch('app.core.http_client.get_http_client')
    def test_malformed_requests(self, mock_client, mock_validate_request, mock_jwt_validation):
        """Test handling of malformed requests."""
        # Mock JWT validation to return valid agent info
        mock_jwt_validation.return_value = {
            "sub": "agent-perf-test",
            "permissions": ["domain:httpbin.org", "method:POST"],
            "allowed_domains": ["httpbin.org"],
            "allowed_methods": ["POST"]
        }
        
        # Mock request validation to return a valid ProxyRequestInfo
        mock_validate_request.return_value = ProxyRequestInfo(
            target_url="https://httpbin.org",
            method="POST",
            headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
            query_params={},
            content_length=12,
            content_type="application/json"
        )
        
        # Mock HTTP client response  
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{"processed": true}'
        mock_client.return_value.proxy_request = AsyncMock(return_value=mock_response)
        
        jwt_token = self.create_mock_jwt(self.valid_jwt_payload)
        
        # Test with malformed JSON
        response = self.client.post(
            "/proxy/test",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "X-Target-Base-URL": "https://httpbin.org",
                "Content-Type": "application/json"
            },
            data="invalid json"
        )
        
        # Should handle malformed JSON gracefully
        assert response.status_code == 200
    
    @patch('app.middleware.jwt_validation.JWTValidationMiddleware._validate_jwt_token')
    @patch('app.core.request_validator.RequestValidator.validate_request')
    @patch('app.core.http_client.get_http_client')
    def test_concurrent_requests(self, mock_client, mock_validate_request, mock_jwt_validation):
        """Test handling of concurrent requests."""
        # Mock JWT validation to return valid agent info
        mock_jwt_validation.return_value = {
            "sub": "agent-perf-test",
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
        
        # Mock HTTP client response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{"success": true}'
        mock_client.return_value.proxy_request = AsyncMock(return_value=mock_response)
        
        jwt_token = self.create_mock_jwt(self.valid_jwt_payload)
        
        # Make multiple concurrent requests
        responses = []
        for i in range(5):
            response = self.client.get(
                f"/proxy/test-{i}",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "X-Target-Base-URL": "https://httpbin.org"
                }
            )
            responses.append(response)
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == 200


# Test configuration and fixtures
@pytest.fixture
def test_config():
    """Provide test configuration."""
    return {
        "proxy_type": "deeptrail-gateway",
        "host": "127.0.0.1",
        "port": 8002,
        "control_plane_url": "http://localhost:8000",
        "security": {
            "block_internal_ips": True,
            "max_request_size": 10485760,  # 10MB
            "request_timeout": 30
        },
        "routing": {
            "target_header": "X-Target-Base-URL",
            "path_prefix": "/proxy"
        },
        "authentication": {
            "jwt_validation": True
        },
        "policy": {
            "enforcement_mode": "strict"
        },
        "logging": {
            "enable_request_logging": True,
            "log_level": "INFO"
        }
    }


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"]) 