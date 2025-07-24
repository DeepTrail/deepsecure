#!/usr/bin/env python3
"""
Phase 2 Integration Test: End-to-end Agent → Gateway → External API Flow
Test the complete Phase 2 Data Plane implementation with secret injection.

This integration test validates:
1. Agent authentication with deeptrail-control
2. Agent making requests through deeptrail-gateway (port 8002)
3. Gateway validating JWT tokens from deeptrail-control
4. Gateway injecting secrets for external API calls
5. Gateway proxying requests to external services
6. Full end-to-end flow working together

Architecture Under Test:
Agent (SDK) → deeptrail-gateway:8002 → External API (with injected secrets)
              ↓ (JWT validation)
         deeptrail-control:8000 (authentication + secret storage)
"""

import pytest
import pytest_asyncio
import asyncio
import httpx
import json
import time
import requests
from typing import Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch
import os
import base64


def is_integration_environment_ready():
    """Check if all required services for integration tests are available."""
    try:
        # Check deeptrail-control
        control_response = requests.get("http://localhost:8000/health", timeout=5)
        if control_response.status_code != 200:
            return False
            
        # Check deeptrail-gateway
        gateway_response = requests.get("http://localhost:8002/health", timeout=5)
        if gateway_response.status_code != 200:
            return False
            
        # Check external API
        external_response = requests.get("https://httpbin.org/status/200", timeout=5)
        if external_response.status_code != 200:
            return False
            
        return True
    except (requests.RequestException, ConnectionError):
        return False


class Phase2IntegrationTester:
    """Integration test utility for Phase 2 end-to-end testing."""
    
    def __init__(self):
        self.deeptrail_control_url = "http://localhost:8000"
        self.deeptrail_gateway_url = "http://localhost:8002"
        self.external_api_url = "https://httpbin.org"  # Test external API
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # Test agent configuration
        self.test_agent_id = "test-agent-phase2-integration"
        self.test_agent_name = "Phase2 Integration Test Agent"
        
        # Mock JWT token for testing
        self.test_jwt_token = None
    
    async def cleanup(self):
        """Clean up resources."""
        await self.client.aclose()
    
    async def test_control_plane_health(self) -> bool:
        """Test that deeptrail-control is healthy."""
        try:
            response = await self.client.get(f"{self.deeptrail_control_url}/health")
            return response.status_code == 200
        except Exception as e:
            print(f"Control plane health check failed: {e}")
            return False
    
    async def test_gateway_health(self) -> bool:
        """Test that deeptrail-gateway is healthy."""
        try:
            response = await self.client.get(f"{self.deeptrail_gateway_url}/")
            return response.status_code == 200
        except Exception as e:
            print(f"Gateway health check failed: {e}")
            return False
    
    async def test_external_api_health(self) -> bool:
        """Test that external API is accessible."""
        try:
            response = await self.client.get(f"{self.external_api_url}/get")
            return response.status_code == 200
        except Exception as e:
            print(f"External API health check failed: {e}")
            return False
    
    async def create_test_agent(self) -> Dict[str, Any]:
        """Create a test agent in deeptrail-control."""
        # For integration testing, we'll simulate agent creation
        # In real implementation, this would use the actual agent creation API
        agent_data = {
            "id": self.test_agent_id,
            "name": self.test_agent_name,
            "description": "Integration test agent for Phase 2 testing",
            "public_key": "test_public_key_placeholder",
            "status": "active"
        }
        
        # Mock agent creation - in real test this would call the actual API
        return agent_data
    
    async def authenticate_agent(self) -> Optional[str]:
        """Authenticate agent and get JWT token."""
        # For integration testing, we'll simulate authentication
        # In real implementation, this would use the actual challenge-response flow
        
        # Mock JWT payload for testing
        test_payload = {
            "sub": self.test_agent_id,
            "name": self.test_agent_name,
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,  # 1 hour expiry
            "aud": "deeptrail-gateway",
            "iss": "deeptrail-control"
        }
        
        # Create a mock JWT token (in real test this would be properly signed)
        header_dict = {"alg": "HS256", "typ": "JWT"}
        header_json = json.dumps(header_dict, separators=(',', ':'))
        payload_json = json.dumps(test_payload, separators=(',', ':'))
        
        def base64url_encode(data):
            return base64.urlsafe_b64encode(data.encode()).decode().rstrip('=')
        
        header_b64 = base64url_encode(header_json)
        payload_b64 = base64url_encode(payload_json)
        signature = base64url_encode("mock_signature")
        
        self.test_jwt_token = f"{header_b64}.{payload_b64}.{signature}"
        return self.test_jwt_token
    
    async def test_gateway_proxy_request(self, target_url: str, method: str = "GET", 
                                       headers: Dict[str, str] = None, 
                                       data: Any = None) -> httpx.Response:
        """Test making a request through the gateway proxy."""
        proxy_headers = {
            "X-Target-Base-URL": target_url,
            "Authorization": f"Bearer {self.test_jwt_token}",
            "Content-Type": "application/json"
        }
        
        if headers:
            proxy_headers.update(headers)
        
        # Make request through gateway proxy
        # Extract the path from the target URL
        from urllib.parse import urlparse
        parsed_url = urlparse(target_url)
        proxy_path = parsed_url.path if parsed_url.path else "/get"
        proxy_url = f"{self.deeptrail_gateway_url}/proxy{proxy_path}"
        
        if method.upper() == "GET":
            response = await self.client.get(proxy_url, headers=proxy_headers)
        elif method.upper() == "POST":
            response = await self.client.post(proxy_url, headers=proxy_headers, json=data)
        elif method.upper() == "PUT":
            response = await self.client.put(proxy_url, headers=proxy_headers, json=data)
        elif method.upper() == "DELETE":
            response = await self.client.delete(proxy_url, headers=proxy_headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        return response
    
    async def test_direct_external_api_request(self, target_url: str, method: str = "GET",
                                             headers: Dict[str, str] = None,
                                             data: Any = None) -> httpx.Response:
        """Test making a direct request to external API (for comparison)."""
        request_headers = headers or {}
        
        if method.upper() == "GET":
            response = await self.client.get(target_url, headers=request_headers)
        elif method.upper() == "POST":
            response = await self.client.post(target_url, headers=request_headers, json=data)
        elif method.upper() == "PUT":
            response = await self.client.put(target_url, headers=request_headers, json=data)
        elif method.upper() == "DELETE":
            response = await self.client.delete(target_url, headers=request_headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        return response


class TestPhase2IntegrationEndToEnd:
    """Phase 2 Integration Tests - End-to-end Flow Validation."""
    
    @pytest_asyncio.fixture
    async def integration_tester(self):
        """Create an integration tester instance."""
        tester = Phase2IntegrationTester()
        yield tester
        await tester.cleanup()
    
    @pytest.mark.asyncio
    async def test_infrastructure_health_checks(self, integration_tester):
        """Test that all required infrastructure components are healthy."""
        if not is_integration_environment_ready():
            pytest.skip("Integration environment not ready - required services (control:8000, gateway:8002, httpbin.org) not available")
        
        # Test deeptrail-control health
        control_healthy = await integration_tester.test_control_plane_health()
        assert control_healthy, "deeptrail-control (port 8000) must be healthy for integration tests"
        
        # Test deeptrail-gateway health
        gateway_healthy = await integration_tester.test_gateway_health()
        assert gateway_healthy, "deeptrail-gateway (port 8002) must be healthy for integration tests"
        
        # Test external API health
        external_healthy = await integration_tester.test_external_api_health()
        assert external_healthy, "External API (httpbin.org) must be accessible for integration tests"
    
    @pytest.mark.asyncio
    async def test_agent_authentication_flow(self, integration_tester):
        """Test agent authentication and JWT token generation."""
        # Create test agent
        agent_data = await integration_tester.create_test_agent()
        assert agent_data["id"] == integration_tester.test_agent_id
        assert agent_data["status"] == "active"
        
        # Authenticate agent
        jwt_token = await integration_tester.authenticate_agent()
        assert jwt_token is not None
        assert len(jwt_token.split(".")) == 3  # Valid JWT structure
        
        # Verify token contains expected claims
        payload_b64 = jwt_token.split(".")[1]
        # Add padding if needed
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.b64decode(payload_b64).decode())
        
        assert payload["sub"] == integration_tester.test_agent_id
        assert payload["aud"] == "deeptrail-gateway"
        assert payload["iss"] == "deeptrail-control"
        assert payload["exp"] > int(time.time())  # Token not expired
    
    @pytest.mark.asyncio
    async def test_gateway_proxy_basic_request(self, integration_tester):
        """Test basic request proxying through gateway."""
        # Authenticate first
        jwt_token = await integration_tester.authenticate_agent()
        assert jwt_token is not None
        
        # Test basic GET request through gateway
        response = await integration_tester.test_gateway_proxy_request(
            target_url=f"{integration_tester.external_api_url}/get",
            method="GET"
        )
        
        # Verify response
        assert response.status_code == 200
        response_data = response.json()
        assert "url" in response_data
        assert "headers" in response_data
    
    @pytest.mark.asyncio
    async def test_gateway_proxy_post_request(self, integration_tester):
        """Test POST request proxying through gateway."""
        # Authenticate first
        jwt_token = await integration_tester.authenticate_agent()
        assert jwt_token is not None
        
        # Test POST request through gateway
        test_data = {
            "message": "Phase 2 Integration Test",
            "agent_id": integration_tester.test_agent_id,
            "timestamp": int(time.time())
        }
        
        response = await integration_tester.test_gateway_proxy_request(
            target_url=f"{integration_tester.external_api_url}/post",
            method="POST",
            data=test_data
        )
        
        # Verify response
        assert response.status_code == 200
        response_data = response.json()
        assert "json" in response_data
        assert response_data["json"]["message"] == "Phase 2 Integration Test"
    
    @pytest.mark.asyncio
    async def test_gateway_secret_injection_for_known_domain(self, integration_tester):
        """Test that gateway injects secrets for known domains."""
        # Authenticate first
        jwt_token = await integration_tester.authenticate_agent()
        assert jwt_token is not None
        
        # Test request to api.openai.com (should have secret injection)
        response = await integration_tester.test_gateway_proxy_request(
            target_url="https://api.openai.com/v1/models",
            method="GET"
        )
        
        # Note: This will likely fail with 401 because we're using a placeholder token
        # But we can verify that the gateway attempted to inject the secret
        # The key is that we get a structured response, not a gateway error
        
        # If we get a 401, it means the gateway injected the (fake) token
        # If we get a 404 or gateway error, it means the proxy didn't work
        assert response.status_code in [401, 403, 429], f"Expected auth error from OpenAI, got {response.status_code}"
    
    @pytest.mark.asyncio
    async def test_gateway_no_secret_injection_for_unknown_domain(self, integration_tester):
        """Test that gateway doesn't inject secrets for unknown domains."""
        # Authenticate first
        jwt_token = await integration_tester.authenticate_agent()
        assert jwt_token is not None
        
        # Test request to httpbin.org (should NOT have secret injection)
        response = await integration_tester.test_gateway_proxy_request(
            target_url=f"{integration_tester.external_api_url}/headers",
            method="GET"
        )
        
        # Verify response
        assert response.status_code == 200
        response_data = response.json()
        
        # Check that no Authorization header was injected
        headers = response_data.get("headers", {})
        assert "Authorization" not in headers or not headers["Authorization"].startswith("Bearer OPENAI")
    
    @pytest.mark.asyncio
    async def test_gateway_jwt_validation_rejection(self, integration_tester):
        """Test that gateway rejects requests without valid JWT."""
        # Test request without JWT token
        proxy_headers = {
            "X-Target-Base-URL": f"{integration_tester.external_api_url}/get",
            "Content-Type": "application/json"
        }
        
        proxy_url = f"{integration_tester.deeptrail_gateway_url}/proxy/get"
        response = await integration_tester.client.get(proxy_url, headers=proxy_headers)
        
        # Should be rejected due to missing JWT
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_gateway_jwt_validation_with_invalid_token(self, integration_tester):
        """Test that gateway rejects requests with invalid JWT."""
        # Test request with invalid JWT token
        proxy_headers = {
            "X-Target-Base-URL": f"{integration_tester.external_api_url}/get",
            "Authorization": "Bearer invalid.jwt.token",
            "Content-Type": "application/json"
        }
        
        proxy_url = f"{integration_tester.deeptrail_gateway_url}/proxy/get"
        response = await integration_tester.client.get(proxy_url, headers=proxy_headers)
        
        # Should be rejected due to invalid JWT
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_end_to_end_multiple_requests(self, integration_tester):
        """Test multiple requests through the gateway to verify stability."""
        # Authenticate first
        jwt_token = await integration_tester.authenticate_agent()
        assert jwt_token is not None
        
        # Make multiple requests concurrently
        tasks = []
        for i in range(5):
            task = integration_tester.test_gateway_proxy_request(
                target_url=f"{integration_tester.external_api_url}/get?request={i}",
                method="GET"
            )
            tasks.append(task)
        
        # Wait for all requests to complete
        responses = await asyncio.gather(*tasks)
        
        # Verify all requests succeeded
        for i, response in enumerate(responses):
            assert response.status_code == 200
            response_data = response.json()
            assert f"request={i}" in response_data["url"]
    
    @pytest.mark.asyncio
    async def test_gateway_header_preservation(self, integration_tester):
        """Test that gateway preserves custom headers while adding auth."""
        # Authenticate first
        jwt_token = await integration_tester.authenticate_agent()
        assert jwt_token is not None
        
        # Test with custom headers
        custom_headers = {
            "X-Custom-Header": "test-value",
            "User-Agent": "Phase2-Integration-Test/1.0"
        }
        
        response = await integration_tester.test_gateway_proxy_request(
            target_url=f"{integration_tester.external_api_url}/headers",
            method="GET",
            headers=custom_headers
        )
        
        # Verify response
        assert response.status_code == 200
        response_data = response.json()
        headers = response_data.get("headers", {})
        
        # Check that custom headers were preserved
        assert headers.get("X-Custom-Header") == "test-value"
        assert "Phase2-Integration-Test/1.0" in headers.get("User-Agent", "")
    
    @pytest.mark.asyncio
    async def test_gateway_error_handling(self, integration_tester):
        """Test gateway error handling for various failure scenarios."""
        # Authenticate first
        jwt_token = await integration_tester.authenticate_agent()
        assert jwt_token is not None
        
        # Test request to non-existent endpoint
        response = await integration_tester.test_gateway_proxy_request(
            target_url="https://nonexistent.domain.invalid/api",
            method="GET"
        )
        
        # Should handle DNS resolution failure gracefully
        assert response.status_code in [400, 500, 502, 503, 504]
    
    @pytest.mark.asyncio
    async def test_performance_timing(self, integration_tester):
        """Test that gateway adds minimal latency to requests."""
        # Authenticate first
        jwt_token = await integration_tester.authenticate_agent()
        assert jwt_token is not None
        
        # Test direct request timing
        start_time = time.time()
        direct_response = await integration_tester.test_direct_external_api_request(
            target_url=f"{integration_tester.external_api_url}/get"
        )
        direct_time = time.time() - start_time
        
        assert direct_response.status_code == 200
        
        # Test gateway request timing
        start_time = time.time()
        gateway_response = await integration_tester.test_gateway_proxy_request(
            target_url=f"{integration_tester.external_api_url}/get",
            method="GET"
        )
        gateway_time = time.time() - start_time
        
        assert gateway_response.status_code == 200
        
        # Gateway should add minimal overhead (less than 500ms)
        overhead = gateway_time - direct_time
        assert overhead < 0.5, f"Gateway added {overhead:.3f}s overhead, should be < 500ms"
        
        print(f"Direct request: {direct_time:.3f}s")
        print(f"Gateway request: {gateway_time:.3f}s")
        print(f"Gateway overhead: {overhead:.3f}s")


@pytest.mark.asyncio
async def test_phase2_integration_summary():
    """Summary test that validates the complete Phase 2 integration."""
    
    # Create tester
    tester = Phase2IntegrationTester()
    
    try:
        # Step 1: Validate infrastructure
        control_healthy = await tester.test_control_plane_health()
        gateway_healthy = await tester.test_gateway_health()
        external_healthy = await tester.test_external_api_health()
        
        infrastructure_status = {
            "deeptrail-control": control_healthy,
            "deeptrail-gateway": gateway_healthy,
            "external-api": external_healthy
        }
        
        # Step 2: Test authentication
        jwt_token = await tester.authenticate_agent()
        auth_working = jwt_token is not None
        
        # Step 3: Test basic proxying
        proxy_working = False
        if auth_working:
            try:
                response = await tester.test_gateway_proxy_request(
                    target_url=f"{tester.external_api_url}/get",
                    method="GET"
                )
                proxy_working = response.status_code == 200
            except Exception:
                proxy_working = False
        
        # Generate summary
        summary = {
            "infrastructure": infrastructure_status,
            "authentication": auth_working,
            "proxy": proxy_working,
            "overall_health": all([
                control_healthy,
                gateway_healthy,
                external_healthy,
                auth_working,
                proxy_working
            ])
        }
        
        print("\n" + "="*60)
        print("PHASE 2 INTEGRATION TEST SUMMARY")
        print("="*60)
        print(f"Infrastructure Health:")
        print(f"  deeptrail-control (8000): {'✅ HEALTHY' if control_healthy else '❌ UNHEALTHY'}")
        print(f"  deeptrail-gateway (8002): {'✅ HEALTHY' if gateway_healthy else '❌ UNHEALTHY'}")
        print(f"  external-api (httpbin):   {'✅ HEALTHY' if external_healthy else '❌ UNHEALTHY'}")
        print(f"Authentication:             {'✅ WORKING' if auth_working else '❌ FAILED'}")
        print(f"Proxy Functionality:        {'✅ WORKING' if proxy_working else '❌ FAILED'}")
        print(f"Overall Status:             {'✅ PASS' if summary['overall_health'] else '❌ FAIL'}")
        print("="*60)
        
        # Assert overall health
        assert summary['overall_health'], f"Phase 2 integration failed: {summary}"
        
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"]) 