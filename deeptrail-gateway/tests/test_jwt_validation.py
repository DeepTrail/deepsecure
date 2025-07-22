"""
Test Phase 2 Task 2.3: JWT Validation Middleware

This test suite validates the JWT validation middleware in deeptrail-gateway
to ensure proper authentication of agents and resolve the Phase 1 JWT validation
issues where vault credentials endpoint returned 401 despite valid tokens.

Critical Focus Areas:
1. JWT signature validation using deeptrail-control public key
2. JWT claims validation (exp, iat, agent_id)
3. Invalid token rejection
4. Token expiration handling
5. Integration with FastAPI middleware stack
"""

import pytest
import json
import base64
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

import httpx
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# Import the JWT validation middleware
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'deeptrail-gateway'))

from app.middleware.jwt_validation import JWTValidationMiddleware, JWTValidationError


class TestJWTValidationMiddleware:
    """Test suite for JWT validation middleware."""
    
    def setup_method(self):
        """Set up test fixtures for each test method."""
        self.app = FastAPI()
        self.middleware = JWTValidationMiddleware(
            self.app,
            control_plane_url="http://localhost:8000"
        )
        
        # Add a test endpoint
        @self.app.get("/proxy/test")
        async def test_endpoint():
            return {"message": "success"}
        
        @self.app.get("/health")
        async def health_endpoint():
            return {"status": "healthy"}
        
        # Add middleware to app
        self.app.add_middleware(JWTValidationMiddleware, control_plane_url="http://localhost:8000")
        
        self.client = TestClient(self.app)
    
    def create_test_jwt(self, payload: Dict[str, Any]) -> str:
        """Create a test JWT token with the given payload."""
        # Create JWT header
        header = {"alg": "HS256", "typ": "JWT"}
        header_b64 = base64.urlsafe_b64encode(
            json.dumps(header).encode()
        ).decode().rstrip("=")
        
        # Create JWT payload
        payload_b64 = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).decode().rstrip("=")
        
        # Create dummy signature (for testing without validation)
        signature = "dummy_signature"
        signature_b64 = base64.urlsafe_b64encode(signature.encode()).decode().rstrip("=")
        
        return f"{header_b64}.{payload_b64}.{signature_b64}"
    
    def create_valid_jwt_payload(self, agent_id: str = "agent-test-123") -> Dict[str, Any]:
        """Create a valid JWT payload for testing."""
        current_time = datetime.now(timezone.utc)
        return {
            "sub": agent_id,
            "agent_id": agent_id,
            "iat": int(current_time.timestamp()),
            "exp": int((current_time + timedelta(hours=1)).timestamp()),
            "permissions": ["read", "write"]
        }
    
    # Test 1: Valid JWT Token Processing
    def test_valid_jwt_token_accepted(self):
        """Test that valid JWT tokens are accepted."""
        payload = self.create_valid_jwt_payload()
        token = self.create_test_jwt(payload)
        
        response = self.client.get(
            "/proxy/test",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert response.json() == {"message": "success"}
    
    def test_valid_jwt_token_claim_extraction(self):
        """Test that JWT claims are properly extracted."""
        agent_id = "agent-test-456"
        payload = self.create_valid_jwt_payload(agent_id)
        token = self.create_test_jwt(payload)
        
        # Test with a custom endpoint that returns request state
        @self.app.get("/proxy/claims")
        async def claims_endpoint(request: Request):
            return {
                "agent_id": getattr(request.state, "agent_id", None),
                "permissions": getattr(request.state, "agent_permissions", [])
            }
        
        response = self.client.get(
            "/proxy/claims",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == agent_id
        assert data["permissions"] == ["read", "write"]
    
    def test_jwt_token_expiration_validation(self):
        """Test that JWT token expiration is properly validated."""
        current_time = datetime.now(timezone.utc)
        payload = {
            "sub": "agent-test-789",
            "agent_id": "agent-test-789",
            "iat": int(current_time.timestamp()),
            "exp": int((current_time + timedelta(hours=1)).timestamp()),
        }
        token = self.create_test_jwt(payload)
        
        response = self.client.get(
            "/proxy/test",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
    
    # Test 2: Invalid JWT Token Rejection
    def test_expired_jwt_token_rejected(self):
        """Test that expired JWT tokens are rejected."""
        current_time = datetime.now(timezone.utc)
        payload = {
            "sub": "agent-test-expired",
            "agent_id": "agent-test-expired",
            "iat": int((current_time - timedelta(hours=2)).timestamp()),
            "exp": int((current_time - timedelta(hours=1)).timestamp()),  # Expired
        }
        token = self.create_test_jwt(payload)
        
        response = self.client.get(
            "/proxy/test",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()
    
    def test_malformed_jwt_token_rejected(self):
        """Test that malformed JWT tokens are rejected."""
        malformed_token = "not.a.valid.jwt.token"
        
        response = self.client.get(
            "/proxy/test",
            headers={"Authorization": f"Bearer {malformed_token}"}
        )
        
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()
    
    def test_missing_subject_claim_rejected(self):
        """Test that JWT tokens missing subject claim are rejected."""
        current_time = datetime.now(timezone.utc)
        payload = {
            # Missing 'sub' claim
            "agent_id": "agent-test-no-sub",
            "iat": int(current_time.timestamp()),
            "exp": int((current_time + timedelta(hours=1)).timestamp()),
        }
        token = self.create_test_jwt(payload)
        
        response = self.client.get(
            "/proxy/test",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 401
        assert "subject" in response.json()["detail"].lower()
    
    def test_missing_authorization_header_rejected(self):
        """Test that requests without Authorization header are rejected."""
        response = self.client.get("/proxy/test")
        
        assert response.status_code == 401
        assert "missing" in response.json()["detail"].lower()
        assert "Authorization" in response.json()["detail"]
    
    def test_invalid_authorization_header_format_rejected(self):
        """Test that invalid Authorization header formats are rejected."""
        # Test various invalid formats
        invalid_headers = [
            "Invalid token_here",
            "Bearer",
            "Basic token_here",
            "token_without_scheme",
        ]
        
        for header in invalid_headers:
            response = self.client.get(
                "/proxy/test",
                headers={"Authorization": header}
            )
            
            assert response.status_code == 401
            assert "invalid" in response.json()["detail"].lower()
    
    # Test 3: Bypass Paths
    def test_health_endpoint_bypasses_jwt_validation(self):
        """Test that health check endpoints bypass JWT validation."""
        response = self.client.get("/health")
        
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
    
    def test_bypass_paths_no_jwt_required(self):
        """Test that configured bypass paths don't require JWT."""
        bypass_paths = ["/", "/health", "/ready", "/metrics", "/docs"]
        
        for path in bypass_paths:
            # Add endpoints for testing
            @self.app.get(path)
            async def bypass_endpoint():
                return {"path": path}
            
            response = self.client.get(path)
            # Should not return 401 (JWT validation should be bypassed)
            assert response.status_code != 401
    
    def test_non_proxy_paths_bypass_jwt_validation(self):
        """Test that non-proxy paths bypass JWT validation."""
        @self.app.get("/api/test")
        async def non_proxy_endpoint():
            return {"message": "non-proxy"}
        
        response = self.client.get("/api/test")
        
        assert response.status_code == 200
        assert response.json() == {"message": "non-proxy"}
    
    # Test 4: JWT Validation Error Handling
    def test_jwt_validation_error_handling(self):
        """Test proper error handling for JWT validation errors."""
        # Test various error scenarios
        test_cases = [
            ("", 401, "missing"),
            ("Bearer", 401, "invalid"),
            ("Bearer invalid.jwt", 401, "invalid"),
            ("Basic dXNlcjpwYXNz", 401, "invalid"),
        ]
        
        for auth_header, expected_status, expected_detail in test_cases:
            response = self.client.get(
                "/proxy/test",
                headers={"Authorization": auth_header} if auth_header else {}
            )
            
            assert response.status_code == expected_status
            assert expected_detail in response.json()["detail"].lower()
    
    # Test 5: JWT Validation Integration
    def test_jwt_middleware_integration_with_fastapi(self):
        """Test JWT middleware integration with FastAPI."""
        # Test that middleware is properly integrated
        middlewares = [m.cls for m in self.app.user_middleware]
        assert JWTValidationMiddleware in middlewares
    
    def test_jwt_validation_performance(self):
        """Test JWT validation performance."""
        payload = self.create_valid_jwt_payload()
        token = self.create_test_jwt(payload)
        
        # Measure time for JWT validation
        start_time = time.time()
        
        for _ in range(100):
            response = self.client.get(
                "/proxy/test",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200
        
        end_time = time.time()
        avg_time = (end_time - start_time) / 100
        
        # JWT validation should be fast (< 10ms per request)
        assert avg_time < 0.01, f"JWT validation too slow: {avg_time:.4f}s"
    
    # Test 6: Advanced JWT Validation (Future Enhancement)
    def test_jwt_signature_validation_placeholder(self):
        """Test placeholder for future JWT signature validation."""
        # This test documents the need for proper JWT signature validation
        # Currently the middleware doesn't validate signatures
        
        # Create a token with invalid signature
        payload = self.create_valid_jwt_payload()
        header = {"alg": "HS256", "typ": "JWT"}
        header_b64 = base64.urlsafe_b64encode(
            json.dumps(header).encode()
        ).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).decode().rstrip("=")
        
        # Use obviously invalid signature
        invalid_signature = "invalid_signature"
        token = f"{header_b64}.{payload_b64}.{invalid_signature}"
        
        response = self.client.get(
            "/proxy/test",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Currently this passes because signature validation is not implemented
        # TODO: This should fail once proper signature validation is implemented
        assert response.status_code == 200  # Will be 401 after signature validation
    
    # Test 7: Integration with deeptrail-control
    def test_jwt_validation_with_real_control_plane_token(self):
        """Test JWT validation with real token from deeptrail-control."""
        # This test requires integration with the actual control plane
        # and should be run as part of integration testing
        
        # Skip this test if not in integration mode
        if not os.getenv("INTEGRATION_TEST"):
            pytest.skip("Skipping integration test")
        
        # TODO: Get real JWT token from deeptrail-control
        # TODO: Validate it using the gateway middleware
        # TODO: Ensure it works end-to-end
        pass
    
    # Test 8: Error Response Format
    def test_jwt_validation_error_response_format(self):
        """Test that JWT validation errors return proper response format."""
        response = self.client.get("/proxy/test")
        
        assert response.status_code == 401
        assert "detail" in response.json()
        assert "WWW-Authenticate" in response.headers
        assert response.headers["WWW-Authenticate"] == "Bearer"
    
    # Test 9: Request State Management
    def test_jwt_payload_added_to_request_state(self):
        """Test that JWT payload is properly added to request state."""
        agent_id = "agent-state-test"
        payload = self.create_valid_jwt_payload(agent_id)
        token = self.create_test_jwt(payload)
        
        @self.app.get("/proxy/state")
        async def state_endpoint(request: Request):
            return {
                "has_agent_id": hasattr(request.state, "agent_id"),
                "has_permissions": hasattr(request.state, "agent_permissions"),
                "has_jwt_payload": hasattr(request.state, "jwt_payload"),
                "agent_id": getattr(request.state, "agent_id", None)
            }
        
        response = self.client.get(
            "/proxy/state",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["has_agent_id"] is True
        assert data["has_permissions"] is True
        assert data["has_jwt_payload"] is True
        assert data["agent_id"] == agent_id


class TestJWTValidationEnterpriseGradeFeatures:
    """Test suite for future enterprise-grade JWT validation features."""
    
    def test_public_key_fetching_placeholder(self):
        """Test placeholder for public key fetching from control plane."""
        # This test documents the need for public key fetching
        middleware = JWTValidationMiddleware(FastAPI())
        
        # Method exists but is not implemented
        assert hasattr(middleware, '_fetch_public_key')
        # TODO: Implement and test public key fetching
    
    def test_signature_validation_placeholder(self):
        """Test placeholder for JWT signature validation."""
        # This test documents the need for signature validation
        middleware = JWTValidationMiddleware(FastAPI())
        
        # Method exists but is not implemented
        assert hasattr(middleware, '_validate_jwt_signature')
        # TODO: Implement and test signature validation
    
    def test_token_revocation_placeholder(self):
        """Test placeholder for token revocation checking."""
        # This test documents the need for token revocation
        middleware = JWTValidationMiddleware(FastAPI())
        
        # Method exists but is not implemented
        assert hasattr(middleware, '_check_token_revocation')
        # TODO: Implement and test token revocation


class TestJWTValidationFixForPhase1Issues:
    """Test suite to address specific Phase 1 JWT validation issues."""
    
    def test_phase1_jwt_issue_reproduction(self):
        """Test to reproduce the Phase 1 JWT validation issue."""
        # This test reproduces the issue where vault credentials endpoint
        # returned 401 despite valid tokens
        
        # Create a token that would be valid from deeptrail-control
        payload = {
            "sub": "agent-phase1-test",
            "agent_id": "agent-phase1-test",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }
        
        # Create token in the format that deeptrail-control would create
        token = self._create_control_plane_jwt(payload)
        
        # Test that gateway accepts this token
        middleware = JWTValidationMiddleware(FastAPI())
        
        # This should validate successfully
        # (Currently it will because signature validation is not implemented)
        # TODO: Once signature validation is implemented, ensure this works
    
    def _create_control_plane_jwt(self, payload: Dict[str, Any]) -> str:
        """Create a JWT token in the format that deeptrail-control would create."""
        # This should match the format from deeptrail-control
        # TODO: Ensure this matches the actual format from control plane
        header = {"alg": "HS256", "typ": "JWT"}
        header_b64 = base64.urlsafe_b64encode(
            json.dumps(header).encode()
        ).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).decode().rstrip("=")
        signature_b64 = "control_plane_signature"
        
        return f"{header_b64}.{payload_b64}.{signature_b64}"
    
    def test_phase1_jwt_issue_resolution(self):
        """Test that Phase 1 JWT issues are resolved."""
        # This test ensures that the JWT validation works properly
        # for tokens issued by deeptrail-control
        
        # TODO: Implement proper JWT signature validation
        # TODO: Test with real tokens from deeptrail-control
        # TODO: Ensure gateway accepts valid tokens
        # TODO: Ensure gateway rejects invalid tokens
        pass


# Test execution and validation
if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 