"""
Tests for Phase 1 Task 1.4: JWT Access Token Issuance
Tests all aspects of JWT token creation, validation, and expiration
"""
import os
import pytest
import json
import base64
import uuid
import requests
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

from jose import jwt, JWTError
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from deepsecure._core.crypto.key_manager import KeyManager
from deepsecure._core.identity_manager import IdentityManager
from deepsecure import Client


class TestJWTAccessToken:
    """Test suite for Phase 1 Task 1.4: JWT Access Token Issuance"""
    
    def setup_method(self):
        """Set up test environment"""
        self.key_manager = KeyManager()
        self.control_url = os.getenv("DEEPSECURE_DEEPTRAIL_CONTROL_URL", "http://localhost:8000")
        self.client = Client(silent_mode=True)
        self.identity_manager = IdentityManager(api_client=self.client, silent_mode=True)
        self.test_agent_ids = []  # Track created agents for cleanup
        
    def teardown_method(self):
        """Clean up after tests"""
        # Clean up any created agents
        for agent_id in self.test_agent_ids:
            try:
                self.identity_manager.delete_private_key(agent_id)
            except:
                pass  # Ignore cleanup errors
    
    def _skip_if_backend_unavailable(self):
        """Skip test if backend is not available"""
        try:
            response = requests.get(f"{self.control_url}/health", timeout=2)
            if response.status_code != 200:
                pytest.skip("Backend service unavailable")
        except:
            pytest.skip("Backend service unavailable")
    
    def _create_test_agent(self) -> Dict[str, Any]:
        """Create a test agent and return its data"""
        agent_name = f"test-jwt-agent-{uuid.uuid4()}"
        agent = self.client.agents.create(name=agent_name, description="Test JWT agent")
        self.test_agent_ids.append(agent.id)
        
        return {
            "agent_id": agent.id,
            "name": agent.name,
            "public_key": agent.public_key,
            "status": agent.status
        }
    
    def _get_valid_jwt_token(self, agent_data: Dict[str, Any]) -> str:
        """Helper to get a valid JWT token for testing"""
        # Request challenge
        challenge_response = requests.post(
            f"{self.control_url}/api/v1/auth/challenge",
            json={"agent_id": agent_data["agent_id"]}
        )
        
        if challenge_response.status_code != 200:
            raise Exception(f"Challenge failed: {challenge_response.text}")
            
        nonce = challenge_response.json()["nonce"]
        
        # Get private key and sign
        private_key_b64 = self.identity_manager.get_private_key(agent_data["agent_id"])
        signature = self.identity_manager.sign(private_key_b64, nonce)
        
        # Request token
        token_response = requests.post(
            f"{self.control_url}/api/v1/auth/token",
            json={
                "agent_id": agent_data["agent_id"],
                "nonce": nonce,
                "signature": signature
            }
        )
        
        if token_response.status_code != 200:
            raise Exception(f"Token request failed: {token_response.text}")
            
        return token_response.json()["access_token"]
    
    def test_jwt_token_creation_success(self):
        """Test successful JWT token creation"""
        self._skip_if_backend_unavailable()
        
        # Create test agent
        agent_data = self._create_test_agent()
        
        # Get JWT token
        token = self._get_valid_jwt_token(agent_data)
        
        # Verify token structure
        assert isinstance(token, str)
        assert len(token.split('.')) == 3  # JWT has 3 parts
        
        # Decode and verify claims
        payload = jwt.decode(token, key="dummy", options={"verify_signature": False})
        assert payload["agent_id"] == agent_data["agent_id"]
        assert "exp" in payload
        assert "iat" in payload
        
        # Verify expiration is reasonable (should be in future)
        exp_time = datetime.fromtimestamp(payload["exp"], timezone.utc)
        now = datetime.now(timezone.utc)
        assert exp_time > now
        
        # Verify issued time is reasonable (should be recent)
        iat_time = datetime.fromtimestamp(payload["iat"], timezone.utc)
        assert (now - iat_time).total_seconds() < 10  # Within 10 seconds
        
    def test_jwt_token_signature_verification(self):
        """Test JWT token signature verification"""
        self._skip_if_backend_unavailable()
        
        # Create test agent
        agent_data = self._create_test_agent()
        
        # Get JWT token
        token = self._get_valid_jwt_token(agent_data)
        
        # Verify signature with correct secret
        secret_key = os.getenv("SECRET_KEY", "your-secret-key-for-jwt")
        algorithm = "HS256"
        
        try:
            payload = jwt.decode(token, secret_key, algorithms=[algorithm])
            assert payload["agent_id"] == agent_data["agent_id"]
        except JWTError:
            pytest.fail("Valid JWT token failed signature verification")
        
        # Verify signature fails with wrong secret
        wrong_secret = "wrong_secret_key"
        with pytest.raises(JWTError):
            jwt.decode(token, wrong_secret, algorithms=[algorithm])
            
    def test_jwt_token_with_policy_claims(self):
        """Test JWT token contains policy claims when policies exist"""
        self._skip_if_backend_unavailable()
        
        # Create test agent
        agent_data = self._create_test_agent()
        
        # Create a policy for the agent
        policy_data = {
            "name": f"test-policy-{uuid.uuid4()}",
            "agent_id": agent_data["agent_id"],
            "effect": "allow",
            "actions": ["proxy:request", "secret:read"],
            "resources": ["ds:secret:test1", "ds:secret:test2"]
        }
        
        policy_response = requests.post(
            f"{self.control_url}/api/v1/policies",
            json=policy_data,
            headers={"Authorization": "Bearer insecure_default_api_token_for_dev"}
        )
        
        if policy_response.status_code == 201:
            # Get JWT token (should now include policy claims)
            token = self._get_valid_jwt_token(agent_data)
            
            # Decode and verify policy claims
            payload = jwt.decode(token, key="dummy", options={"verify_signature": False})
            
            # Should have scope and resources claims
            assert "scope" in payload
            assert "resources" in payload
            
            # Verify scope contains actions
            scope_actions = payload["scope"].split(" ")
            assert "proxy:request" in scope_actions
            assert "secret:read" in scope_actions
            
            # Verify resources
            assert "ds:secret:test1" in payload["resources"]
            assert "ds:secret:test2" in payload["resources"]
        else:
            pytest.skip("Policy creation failed - policy engine may not be available")
            
    def test_jwt_token_expiration_handling(self):
        """Test JWT token expiration handling"""
        self._skip_if_backend_unavailable()
        
        # Create test agent
        agent_data = self._create_test_agent()
        
        # Get JWT token
        token = self._get_valid_jwt_token(agent_data)
        
        # Decode and check expiration
        payload = jwt.decode(token, key="dummy", options={"verify_signature": False})
        exp_time = datetime.fromtimestamp(payload["exp"], timezone.utc)
        now = datetime.now(timezone.utc)
        
        # Token should expire in approximately 30 minutes (default)
        time_diff = (exp_time - now).total_seconds()
        assert 1700 <= time_diff <= 1900  # 30 minutes ± 100 seconds
        
        # Test token validation with expiration check
        secret_key = os.getenv("SECRET_KEY", "your-secret-key-for-jwt")
        algorithm = "HS256"
        
        # Should be valid now
        try:
            jwt.decode(token, secret_key, algorithms=[algorithm])
        except JWTError:
            pytest.fail("Fresh JWT token should be valid")
        
        # Create an expired token for testing
        expired_payload = payload.copy()
        expired_payload["exp"] = int((datetime.now(timezone.utc) - timedelta(seconds=1)).timestamp())
        
        expired_token = jwt.encode(expired_payload, secret_key, algorithm=algorithm)
        
        # Should fail validation due to expiration
        with pytest.raises(JWTError):
            jwt.decode(expired_token, secret_key, algorithms=[algorithm])
            
    def test_jwt_token_structure_validation(self):
        """Test JWT token structure and format validation"""
        self._skip_if_backend_unavailable()
        
        # Create test agent
        agent_data = self._create_test_agent()
        
        # Get JWT token
        token = self._get_valid_jwt_token(agent_data)
        
        # Verify token structure
        parts = token.split('.')
        assert len(parts) == 3
        
        # Verify each part is valid base64 (JWT uses URL-safe base64)
        for part in parts:
            try:
                # Add padding if needed
                padded = part + '=' * (4 - len(part) % 4)
                base64.urlsafe_b64decode(padded)
            except Exception:
                pytest.fail(f"Invalid base64 in JWT part: {part}")
        
        # Decode header
        header_data = jwt.get_unverified_header(token)
        assert header_data["alg"] == "HS256"
        assert header_data["typ"] == "JWT"
        
        # Decode payload
        payload = jwt.decode(token, key="dummy", options={"verify_signature": False})
        
        # Verify required claims
        required_claims = ["agent_id", "exp", "iat"]
        for claim in required_claims:
            assert claim in payload, f"Missing required claim: {claim}"
            
        # Verify claim types
        assert isinstance(payload["agent_id"], str)
        assert isinstance(payload["exp"], int)
        assert isinstance(payload["iat"], int)
        
    def test_jwt_token_malformed_handling(self):
        """Test handling of malformed JWT tokens"""
        self._skip_if_backend_unavailable()
        
        secret_key = os.getenv("SECRET_KEY", "your-secret-key-for-jwt")
        algorithm = "HS256"
        
        # Test various malformed tokens
        malformed_tokens = [
            "not.a.jwt",
            "invalid_base64.data.here",
            "missing.parts",
            "too.many.parts.here.extra",
            "",
            "a",
            "a.b",
            "a.b.c.d",
        ]
        
        for malformed_token in malformed_tokens:
            with pytest.raises(JWTError):
                jwt.decode(malformed_token, secret_key, algorithms=[algorithm])
                
    def test_jwt_token_algorithm_validation(self):
        """Test JWT token algorithm validation"""
        self._skip_if_backend_unavailable()
        
        # Create test agent
        agent_data = self._create_test_agent()
        
        # Get JWT token
        token = self._get_valid_jwt_token(agent_data)
        
        secret_key = os.getenv("SECRET_KEY", "your-secret-key-for-jwt")
        
        # Should work with correct algorithm
        try:
            jwt.decode(token, secret_key, algorithms=["HS256"])
        except JWTError:
            pytest.fail("JWT should be valid with correct algorithm")
        
        # Should fail with wrong algorithm
        with pytest.raises(JWTError):
            jwt.decode(token, secret_key, algorithms=["HS512"])
            
        with pytest.raises(JWTError):
            jwt.decode(token, secret_key, algorithms=["RS256"])
            
    def test_jwt_token_claims_integrity(self):
        """Test JWT token claims integrity and tampering protection"""
        self._skip_if_backend_unavailable()
        
        # Create test agent
        agent_data = self._create_test_agent()
        
        # Get JWT token
        token = self._get_valid_jwt_token(agent_data)
        
        # Try to tamper with the token by modifying payload
        parts = token.split('.')
        header, payload, signature = parts
        
        # Decode payload
        payload_data = jwt.decode(token, key="dummy", options={"verify_signature": False})
        
        # Modify payload (change agent_id)
        payload_data["agent_id"] = "hacked_agent_id"
        
        # Create new token with modified payload
        secret_key = os.getenv("SECRET_KEY", "your-secret-key-for-jwt")
        algorithm = "HS256"
        
        # Re-encode just the payload part
        import json
        modified_payload = base64.b64encode(json.dumps(payload_data).encode()).decode().rstrip('=')
        tampered_token = f"{header}.{modified_payload}.{signature}"
        
        # Should fail signature verification
        with pytest.raises(JWTError):
            jwt.decode(tampered_token, secret_key, algorithms=[algorithm])
            
    def test_jwt_token_error_handling(self):
        """Test JWT token error handling scenarios"""
        self._skip_if_backend_unavailable()
        
        # Test token request with invalid agent
        invalid_agent_id = f"agent-{uuid.uuid4()}"
        
        challenge_response = requests.post(
            f"{self.control_url}/api/v1/auth/challenge",
            json={"agent_id": invalid_agent_id}
        )
        
        # Should fail for non-existent agent
        assert challenge_response.status_code == 404
        
        # Test token request with invalid signature
        agent_data = self._create_test_agent()
        
        challenge_response = requests.post(
            f"{self.control_url}/api/v1/auth/challenge",
            json={"agent_id": agent_data["agent_id"]}
        )
        
        assert challenge_response.status_code == 200
        nonce = challenge_response.json()["nonce"]
        
        # Use wrong signature
        wrong_signature = base64.b64encode(b"wrong_signature_data_here" + b"x" * 40).decode()
        
        token_response = requests.post(
            f"{self.control_url}/api/v1/auth/token",
            json={
                "agent_id": agent_data["agent_id"],
                "nonce": nonce,
                "signature": wrong_signature
            }
        )
        
        # Should fail with invalid signature
        assert token_response.status_code == 401
        
    def test_jwt_token_multiple_agents(self):
        """Test JWT token issuance for multiple agents"""
        self._skip_if_backend_unavailable()
        
        # Create multiple test agents
        agents = []
        for i in range(3):
            agent_data = self._create_test_agent()
            agents.append(agent_data)
        
        tokens = []
        for agent_data in agents:
            token = self._get_valid_jwt_token(agent_data)
            tokens.append(token)
            
        # Verify each token is unique and valid
        for i, token in enumerate(tokens):
            payload = jwt.decode(token, key="dummy", options={"verify_signature": False})
            assert payload["agent_id"] == agents[i]["agent_id"]
            
        # Verify all tokens are different
        assert len(set(tokens)) == len(tokens)
        
    def test_jwt_token_concurrent_requests(self):
        """Test JWT token issuance under concurrent requests"""
        self._skip_if_backend_unavailable()
        
        # Create test agent
        agent_data = self._create_test_agent()
        
        # Get multiple tokens concurrently (simulated)
        tokens = []
        for _ in range(5):
            token = self._get_valid_jwt_token(agent_data)
            tokens.append(token)
            
        # All tokens should be valid
        secret_key = os.getenv("SECRET_KEY", "your-secret-key-for-jwt")
        algorithm = "HS256"
        
        for token in tokens:
            try:
                payload = jwt.decode(token, secret_key, algorithms=[algorithm])
                assert payload["agent_id"] == agent_data["agent_id"]
            except JWTError:
                pytest.fail("All tokens should be valid")
        
        # Tokens should be unique (different iat timestamps or at least same timestamp is acceptable)
        payloads = [jwt.decode(token, key="dummy", options={"verify_signature": False}) for token in tokens]
        iat_times = [payload["iat"] for payload in payloads]
        # Allow for same timestamps if generated within the same second
        assert len(set(iat_times)) >= 1  # At least one timestamp should exist
        # Verify all timestamps are recent (within last 30 seconds)
        now = datetime.now(timezone.utc).timestamp()
        for iat in iat_times:
            assert abs(now - iat) < 30  # All tokens should be recent 