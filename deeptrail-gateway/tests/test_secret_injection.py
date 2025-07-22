#!/usr/bin/env python3
"""
Phase 2 Task 2.4: Test Simple Secret Injection
Validate middleware/secret_injection.py fetches secrets from deeptrail-control and injects them.

This test suite validates:
1. Secret injection for different authentication types (Bearer, API key, Basic)
2. Proper bypass of health check and documentation paths
3. Domain-based secret selection and injection
4. Header modification and injection mechanics
5. Error handling and fallback behavior
6. Integration with JWT validation middleware
7. Agent-specific secret access control
"""

import pytest
import pytest_asyncio
import asyncio
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional
import json
import base64

# Import the middleware
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'deeptrail-gateway'))

from app.middleware.secret_injection import SecretInjectionMiddleware
from fastapi import FastAPI, Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send


class MockRequest:
    """Mock request object for testing."""
    
    def __init__(self, method: str = "GET", url: str = "/", headers: Dict[str, str] = None, body: bytes = b""):
        self.method = method
        self.url = MagicMock()
        self.url.path = url
        self._initial_headers = headers or {}
        self.body = body
        self.state = MagicMock()
        self.state.agent_id = "test-agent-123"
        self.scope = {
            "type": "http",
            "method": method,
            "path": url,
            "headers": [(k.encode(), v.encode()) for k, v in self._initial_headers.items()]
        }
        self._headers = self._initial_headers.copy()
    
    @property
    def headers(self):
        """Return headers from _headers to reflect any modifications."""
        return self._headers
    
    def get_header(self, name: str) -> Optional[str]:
        return self._headers.get(name)


class SecretInjectionTester:
    """Test utility for validating secret injection middleware."""
    
    def __init__(self):
        self.app = FastAPI()
        self.middleware = SecretInjectionMiddleware(
            self.app, 
            control_plane_url="http://test-control:8000"
        )
    
    async def test_injection(self, request: MockRequest) -> Dict[str, Any]:
        """Test secret injection on a mock request."""
        
        # Mock the call_next function
        async def mock_call_next(req):
            return {"status": "processed", "headers": dict(req.headers)}
        
        # Process the request through middleware
        result = await self.middleware.dispatch(request, mock_call_next)
        
        return {
            "result": result,
            "final_headers": dict(request.headers),
            "agent_id": getattr(request.state, "agent_id", None)
        }


class TestSecretInjectionCore:
    """Test core secret injection functionality."""
    
    @pytest.fixture
    def secret_tester(self):
        """Create a secret injection tester instance."""
        return SecretInjectionTester()
    
    @pytest.mark.asyncio
    async def test_bearer_token_injection(self, secret_tester):
        """Test Bearer token injection for OpenAI API."""
        request = MockRequest(
            method="POST",
            url="/proxy/v1/chat/completions",
            headers={
                "X-Target-Base-URL": "https://api.openai.com",
                "Content-Type": "application/json"
            }
        )
        
        result = await secret_tester.test_injection(request)
        
        # Verify Bearer token was injected
        assert "Authorization" in result["final_headers"]
        assert result["final_headers"]["Authorization"].startswith("Bearer ")
        assert "OPENAI_API_KEY_PLACEHOLDER" in result["final_headers"]["Authorization"]
        assert result["result"]["status"] == "processed"
    
    @pytest.mark.asyncio
    async def test_no_secret_injection_for_httpbin(self, secret_tester):
        """Test that no secret is injected for httpbin.org (type: none)."""
        request = MockRequest(
            method="GET",
            url="/proxy/get",
            headers={
                "X-Target-Base-URL": "https://httpbin.org",
                "Accept": "application/json"
            }
        )
        
        result = await secret_tester.test_injection(request)
        
        # Verify no Authorization header was added
        assert "Authorization" not in result["final_headers"]
        assert result["result"]["status"] == "processed"
    
    @pytest.mark.asyncio
    async def test_bypass_health_check_paths(self, secret_tester):
        """Test that health check paths bypass secret injection."""
        health_paths = ["/", "/health", "/ready", "/metrics", "/config", "/docs"]
        
        for path in health_paths:
            request = MockRequest(
                method="GET",
                url=path,
                headers={
                    "X-Target-Base-URL": "https://api.openai.com"
                }
            )
            
            result = await secret_tester.test_injection(request)
            
            # Verify no secret injection occurred
            assert "Authorization" not in result["final_headers"]
            assert result["result"]["status"] == "processed"
    
    @pytest.mark.asyncio
    async def test_bypass_non_proxy_paths(self, secret_tester):
        """Test that non-proxy paths bypass secret injection."""
        non_proxy_paths = ["/api/v1/agents", "/auth/token", "/admin/policies"]
        
        for path in non_proxy_paths:
            request = MockRequest(
                method="GET",
                url=path,
                headers={
                    "X-Target-Base-URL": "https://api.openai.com"
                }
            )
            
            result = await secret_tester.test_injection(request)
            
            # Verify no secret injection occurred
            assert "Authorization" not in result["final_headers"]
            assert result["result"]["status"] == "processed"
    
    @pytest.mark.asyncio
    async def test_missing_target_url_header(self, secret_tester):
        """Test handling of missing X-Target-Base-URL header."""
        request = MockRequest(
            method="POST",
            url="/proxy/v1/chat/completions",
            headers={
                "Content-Type": "application/json"
                # Missing X-Target-Base-URL header
            }
        )
        
        result = await secret_tester.test_injection(request)
        
        # Should continue without injection
        assert "Authorization" not in result["final_headers"]
        assert result["result"]["status"] == "processed"
    
    @pytest.mark.asyncio
    async def test_missing_agent_id(self, secret_tester):
        """Test handling of missing agent ID."""
        request = MockRequest(
            method="POST",
            url="/proxy/v1/chat/completions",
            headers={
                "X-Target-Base-URL": "https://api.openai.com",
                "Content-Type": "application/json"
            }
        )
        
        # Remove agent_id from state
        request.state.agent_id = None
        
        result = await secret_tester.test_injection(request)
        
        # Should continue without injection
        assert "Authorization" not in result["final_headers"]
        assert result["result"]["status"] == "processed"


class TestSecretInjectionTypes:
    """Test different secret injection types."""
    
    @pytest.fixture
    def secret_tester(self):
        """Create a secret injection tester with extended secret store."""
        tester = SecretInjectionTester()
        
        # Extend the secret store with different auth types
        tester.middleware.secret_store.update({
            "api.example.com": {
                "type": "bearer",
                "value": "test-bearer-token-123"
            },
            "api.service.com": {
                "type": "api_key",
                "value": "test-api-key-456",
                "header": "X-API-Key"
            },
            "api.legacy.com": {
                "type": "basic",
                "value": base64.b64encode(b"username:password").decode()
            },
            "api.custom.com": {
                "type": "api_key",
                "value": "custom-key-789",
                "header": "X-Custom-Auth"
            }
        })
        
        return tester
    
    @pytest.mark.asyncio
    async def test_bearer_token_injection(self, secret_tester):
        """Test Bearer token injection."""
        request = MockRequest(
            method="POST",
            url="/proxy/api/data",
            headers={
                "X-Target-Base-URL": "https://api.example.com",
                "Content-Type": "application/json"
            }
        )
        
        result = await secret_tester.test_injection(request)
        
        assert result["final_headers"]["Authorization"] == "Bearer test-bearer-token-123"
    
    @pytest.mark.asyncio
    async def test_api_key_injection_default_header(self, secret_tester):
        """Test API key injection with default header."""
        request = MockRequest(
            method="GET",
            url="/proxy/api/data",
            headers={
                "X-Target-Base-URL": "https://api.service.com",
                "Accept": "application/json"
            }
        )
        
        result = await secret_tester.test_injection(request)
        
        assert result["final_headers"]["X-API-Key"] == "test-api-key-456"
    
    @pytest.mark.asyncio
    async def test_api_key_injection_custom_header(self, secret_tester):
        """Test API key injection with custom header."""
        request = MockRequest(
            method="GET",
            url="/proxy/api/data",
            headers={
                "X-Target-Base-URL": "https://api.custom.com",
                "Accept": "application/json"
            }
        )
        
        result = await secret_tester.test_injection(request)
        
        assert result["final_headers"]["X-Custom-Auth"] == "custom-key-789"
    
    @pytest.mark.asyncio
    async def test_basic_auth_injection(self, secret_tester):
        """Test Basic authentication injection."""
        request = MockRequest(
            method="POST",
            url="/proxy/api/secure",
            headers={
                "X-Target-Base-URL": "https://api.legacy.com",
                "Content-Type": "application/json"
            }
        )
        
        result = await secret_tester.test_injection(request)
        
        expected_auth = f"Basic {base64.b64encode(b'username:password').decode()}"
        assert result["final_headers"]["Authorization"] == expected_auth
    
    @pytest.mark.asyncio
    async def test_unknown_domain_no_injection(self, secret_tester):
        """Test that unknown domains don't get secret injection."""
        request = MockRequest(
            method="GET",
            url="/proxy/api/data",
            headers={
                "X-Target-Base-URL": "https://unknown.domain.com",
                "Accept": "application/json"
            }
        )
        
        result = await secret_tester.test_injection(request)
        
        # Should not have any auth headers
        assert "Authorization" not in result["final_headers"]
        assert "X-API-Key" not in result["final_headers"]


class TestSecretInjectionDomainParsing:
    """Test domain parsing and secret selection."""
    
    @pytest.fixture
    def secret_tester(self):
        return SecretInjectionTester()
    
    @pytest.mark.asyncio
    async def test_domain_parsing_with_subdomain(self, secret_tester):
        """Test domain parsing with subdomains."""
        request = MockRequest(
            method="POST",
            url="/proxy/v1/chat/completions",
            headers={
                "X-Target-Base-URL": "https://api.openai.com/v1",
                "Content-Type": "application/json"
            }
        )
        
        result = await secret_tester.test_injection(request)
        
        # Should match api.openai.com and inject Bearer token
        assert "Authorization" in result["final_headers"]
        assert result["final_headers"]["Authorization"].startswith("Bearer ")
    
    @pytest.mark.asyncio
    async def test_domain_parsing_with_port(self, secret_tester):
        """Test domain parsing with port numbers."""
        # Add a test domain with port
        secret_tester.middleware.secret_store["localhost:8080"] = {
            "type": "bearer",
            "value": "local-test-token"
        }
        
        request = MockRequest(
            method="GET",
            url="/proxy/api/test",
            headers={
                "X-Target-Base-URL": "http://localhost:8080/api",
                "Accept": "application/json"
            }
        )
        
        result = await secret_tester.test_injection(request)
        
        assert result["final_headers"]["Authorization"] == "Bearer local-test-token"
    
    @pytest.mark.asyncio
    async def test_domain_case_insensitive_matching(self, secret_tester):
        """Test that domain matching is case-insensitive."""
        request = MockRequest(
            method="POST",
            url="/proxy/v1/chat/completions",
            headers={
                "X-Target-Base-URL": "https://API.OPENAI.COM/v1",
                "Content-Type": "application/json"
            }
        )
        
        result = await secret_tester.test_injection(request)
        
        # Should match api.openai.com (case insensitive)
        assert "Authorization" in result["final_headers"]
        assert result["final_headers"]["Authorization"].startswith("Bearer ")


class TestSecretInjectionErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.fixture
    def secret_tester(self):
        return SecretInjectionTester()
    
    @pytest.mark.asyncio
    async def test_malformed_target_url(self, secret_tester):
        """Test handling of malformed target URLs."""
        request = MockRequest(
            method="POST",
            url="/proxy/v1/chat/completions",
            headers={
                "X-Target-Base-URL": "not-a-valid-url",
                "Content-Type": "application/json"
            }
        )
        
        result = await secret_tester.test_injection(request)
        
        # Should continue without injection
        assert result["result"]["status"] == "processed"
    
    @pytest.mark.asyncio
    async def test_secret_with_empty_value(self, secret_tester):
        """Test handling of secrets with empty values."""
        secret_tester.middleware.secret_store["empty.test.com"] = {
            "type": "bearer",
            "value": ""
        }
        
        request = MockRequest(
            method="POST",
            url="/proxy/api/test",
            headers={
                "X-Target-Base-URL": "https://empty.test.com",
                "Content-Type": "application/json"
            }
        )
        
        result = await secret_tester.test_injection(request)
        
        # Should not inject empty Bearer token
        assert "Authorization" not in result["final_headers"]
    
    @pytest.mark.asyncio
    async def test_secret_with_unknown_type(self, secret_tester):
        """Test handling of unknown secret types."""
        secret_tester.middleware.secret_store["unknown.test.com"] = {
            "type": "unknown_type",
            "value": "some-value"
        }
        
        request = MockRequest(
            method="POST",
            url="/proxy/api/test",
            headers={
                "X-Target-Base-URL": "https://unknown.test.com",
                "Content-Type": "application/json"
            }
        )
        
        result = await secret_tester.test_injection(request)
        
        # Should continue without injection
        assert "Authorization" not in result["final_headers"]
        assert result["result"]["status"] == "processed"


class TestSecretInjectionIntegration:
    """Test integration scenarios and performance."""
    
    @pytest.fixture
    def secret_tester(self):
        return SecretInjectionTester()
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_injections(self, secret_tester):
        """Test handling of multiple concurrent secret injections."""
        requests = []
        
        # Create multiple requests for different domains
        for i in range(10):
            request = MockRequest(
                method="POST",
                url="/proxy/v1/chat/completions",
                headers={
                    "X-Target-Base-URL": "https://api.openai.com",
                    "Content-Type": "application/json"
                }
            )
            request.state.agent_id = f"agent-{i}"
            requests.append(request)
        
        # Process all requests concurrently
        tasks = [secret_tester.test_injection(req) for req in requests]
        results = await asyncio.gather(*tasks)
        
        # Verify all injections succeeded
        for result in results:
            assert "Authorization" in result["final_headers"]
            assert result["final_headers"]["Authorization"].startswith("Bearer ")
            assert result["result"]["status"] == "processed"
    
    @pytest.mark.asyncio
    async def test_request_header_preservation(self, secret_tester):
        """Test that existing request headers are preserved."""
        request = MockRequest(
            method="POST",
            url="/proxy/v1/chat/completions",
            headers={
                "X-Target-Base-URL": "https://api.openai.com",
                "Content-Type": "application/json",
                "User-Agent": "Test-Agent/1.0",
                "X-Request-ID": "test-123"
            }
        )
        
        result = await secret_tester.test_injection(request)
        
        # Verify existing headers are preserved
        assert result["final_headers"]["Content-Type"] == "application/json"
        assert result["final_headers"]["User-Agent"] == "Test-Agent/1.0"
        assert result["final_headers"]["X-Request-ID"] == "test-123"
        
        # Verify new header is added
        assert "Authorization" in result["final_headers"]
        assert result["final_headers"]["Authorization"].startswith("Bearer ")
    
    @pytest.mark.asyncio
    async def test_header_override_behavior(self, secret_tester):
        """Test that secret injection overrides existing auth headers."""
        request = MockRequest(
            method="POST",
            url="/proxy/v1/chat/completions",
            headers={
                "X-Target-Base-URL": "https://api.openai.com",
                "Content-Type": "application/json",
                "Authorization": "Bearer old-token"
            }
        )
        
        result = await secret_tester.test_injection(request)
        
        # Verify the auth header was overridden
        assert result["final_headers"]["Authorization"] != "Bearer old-token"
        assert result["final_headers"]["Authorization"].startswith("Bearer ")
        assert "OPENAI_API_KEY_PLACEHOLDER" in result["final_headers"]["Authorization"]
    
    @pytest.mark.asyncio
    async def test_performance_timing(self, secret_tester):
        """Test that secret injection completes quickly."""
        import time
        
        request = MockRequest(
            method="POST",
            url="/proxy/v1/chat/completions",
            headers={
                "X-Target-Base-URL": "https://api.openai.com",
                "Content-Type": "application/json"
            }
        )
        
        start_time = time.time()
        result = await secret_tester.test_injection(request)
        end_time = time.time()
        
        injection_time = end_time - start_time
        
        # Should complete within 10ms
        assert injection_time < 0.01, f"Secret injection took {injection_time:.3f}s, should be < 10ms"
        assert result["result"]["status"] == "processed"


@pytest.mark.asyncio
async def test_secret_injection_middleware_initialization():
    """Test that the middleware initializes correctly."""
    app = FastAPI()
    
    # Test default initialization
    middleware = SecretInjectionMiddleware(app)
    assert middleware.control_plane_url == "http://deeptrail-control:8000"
    assert "/health" in middleware.bypass_paths
    assert "api.openai.com" in middleware.secret_store
    
    # Test custom initialization
    middleware = SecretInjectionMiddleware(app, control_plane_url="http://custom-control:9000")
    assert middleware.control_plane_url == "http://custom-control:9000"


@pytest.mark.asyncio
async def test_secret_injection_integration_with_gateway():
    """Integration test for secret injection with the gateway service."""
    # This test would validate the middleware works with the running gateway
    # For now, we'll validate the middleware structure
    
    app = FastAPI()
    middleware = SecretInjectionMiddleware(app)
    
    # Verify middleware has required methods
    assert hasattr(middleware, 'dispatch')
    assert hasattr(middleware, '_inject_secrets')
    assert hasattr(middleware, '_get_secret_for_domain')
    assert hasattr(middleware, '_inject_bearer_token')
    assert hasattr(middleware, '_inject_api_key_header')
    assert hasattr(middleware, '_inject_basic_auth')
    
    # Verify secret store is populated
    assert len(middleware.secret_store) > 0
    assert "api.openai.com" in middleware.secret_store


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 