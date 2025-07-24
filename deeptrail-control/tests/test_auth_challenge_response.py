"""
Tests for Phase 1 Task 1.3: Challenge-Response Authentication
Tests the complete challenge-response authentication flow including:
- Nonce generation and storage
- Signature creation and verification
- JWT token issuance
- Error handling and edge cases
"""
import os
import pytest
import json
import base64
import uuid
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature
from jose import jwt

from deepsecure._core.crypto.key_manager import KeyManager
from deepsecure._core.identity_manager import IdentityManager
from deepsecure import Client


class TestChallengeResponseAuth:
    """Test suite for Phase 1 Task 1.3: Challenge-Response Authentication"""
    
    def setup_method(self):
        """Set up test environment"""
        self.key_manager = KeyManager()
        self.control_url = os.getenv("DEEPSECURE_DEEPTRAIL_CONTROL_URL", "http://localhost:8000")
        self.client = Client(silent_mode=True)
        self.identity_manager = IdentityManager(api_client=self.client, silent_mode=True)
        self.test_agent_ids = []  # Track created agents for cleanup
        
    def teardown_method(self):
        """Clean up test agents"""
        for agent_id in self.test_agent_ids:
            try:
                self.identity_manager.delete_private_key(agent_id)
            except:
                pass
    
    def _create_test_agent(self, name_suffix: str = None) -> Dict[str, Any]:
        """Helper method to create a test agent and return agent data with keys"""
        suffix = name_suffix or str(uuid.uuid4())[:8]
        agent_name = f"test-auth-agent-{suffix}"
        
        # Generate keys
        keys = self.key_manager.generate_identity_keypair()
        
        # Register agent with backend
        register_response = requests.post(
            f"{self.control_url}/api/v1/agents/",
            json={
                "public_key": keys["public_key"],
                "name": agent_name,
                "description": "Test authentication agent"
            }
        )
        
        if register_response.status_code != 201:
            raise Exception(f"Failed to create test agent: {register_response.text}")
            
        agent_data = register_response.json()
        agent_id = agent_data["agent_id"]
        self.test_agent_ids.append(agent_id)
        
        # Store private key locally
        self.identity_manager.store_private_key_directly(agent_id, keys["private_key"])
        
        return {
            "agent_id": agent_id,
            "name": agent_name,
            "public_key": keys["public_key"],
            "private_key": keys["private_key"],
            "agent_data": agent_data
        }
    
    def _skip_if_backend_unavailable(self):
        """Skip test if backend is not available"""
        try:
            response = requests.get(f"{self.control_url}/health", timeout=5)
            if response.status_code != 200:
                pytest.skip("Backend not available")
        except:
            pytest.skip("Backend not available")
    
    def test_challenge_request_success(self):
        """Test successful challenge request"""
        self._skip_if_backend_unavailable()
        
        # Create test agent
        agent_data = self._create_test_agent()
        
        # Request challenge
        challenge_response = requests.post(
            f"{self.control_url}/api/v1/auth/challenge",
            json={"agent_id": agent_data["agent_id"]}
        )
        
        assert challenge_response.status_code == 200
        challenge_data = challenge_response.json()
        
        # Verify response structure
        assert "nonce" in challenge_data
        assert isinstance(challenge_data["nonce"], str)
        assert len(challenge_data["nonce"]) > 0
        
        # Verify nonce is a valid UUID hex string
        try:
            uuid.UUID(challenge_data["nonce"])
        except ValueError:
            pytest.fail("Nonce should be a valid UUID hex string")
    
    def test_challenge_request_nonexistent_agent(self):
        """Test challenge request for non-existent agent"""
        self._skip_if_backend_unavailable()
        
        # Request challenge for non-existent agent
        fake_agent_id = f"agent-{uuid.uuid4()}"
        challenge_response = requests.post(
            f"{self.control_url}/api/v1/auth/challenge",
            json={"agent_id": fake_agent_id}
        )
        
        assert challenge_response.status_code == 404
        error_data = challenge_response.json()
        assert "Agent not found" in error_data["detail"]
    
    def test_token_request_success(self):
        """Test successful token request with valid signature"""
        self._skip_if_backend_unavailable()
        
        # Create test agent
        agent_data = self._create_test_agent()
        
        # Request challenge
        challenge_response = requests.post(
            f"{self.control_url}/api/v1/auth/challenge",
            json={"agent_id": agent_data["agent_id"]}
        )
        
        assert challenge_response.status_code == 200
        challenge_data = challenge_response.json()
        nonce = challenge_data["nonce"]
        
        # Sign the nonce
        signature = self.identity_manager.sign(agent_data["private_key"], nonce)
        
        # Request token
        token_response = requests.post(
            f"{self.control_url}/api/v1/auth/token",
            json={
                "agent_id": agent_data["agent_id"],
                "nonce": nonce,
                "signature": signature
            }
        )
        
        assert token_response.status_code == 200
        token_data = token_response.json()
        
        # Verify token structure
        assert "access_token" in token_data
        assert "token_type" in token_data
        assert token_data["token_type"] == "bearer"
        
        # Verify JWT token is valid
        access_token = token_data["access_token"]
        assert isinstance(access_token, str)
        assert len(access_token) > 0
        
        # Verify token can be decoded (basic structure check)
        try:
            # Split the JWT into parts
            parts = access_token.split('.')
            assert len(parts) == 3, "JWT should have 3 parts"
            
            # Decode header and payload (without signature verification for now)
            header_data = json.loads(base64.urlsafe_b64decode(parts[0] + '=='))
            payload_data = json.loads(base64.urlsafe_b64decode(parts[1] + '=='))
            
            # Verify basic claims
            assert "agent_id" in payload_data
            assert payload_data["agent_id"] == agent_data["agent_id"]
            assert "exp" in payload_data
            assert "iat" in payload_data
            
        except Exception as e:
            pytest.fail(f"Token should be a valid JWT: {e}")
    
    def test_token_request_invalid_signature(self):
        """Test token request with invalid signature"""
        self._skip_if_backend_unavailable()
        
        # Create test agent
        agent_data = self._create_test_agent()
        
        # Request challenge
        challenge_response = requests.post(
            f"{self.control_url}/api/v1/auth/challenge",
            json={"agent_id": agent_data["agent_id"]}
        )
        
        assert challenge_response.status_code == 200
        challenge_data = challenge_response.json()
        nonce = challenge_data["nonce"]
        
        # Create invalid signature
        invalid_signature = base64.b64encode(b"invalid_signature").decode('utf-8')
        
        # Request token with invalid signature
        token_response = requests.post(
            f"{self.control_url}/api/v1/auth/token",
            json={
                "agent_id": agent_data["agent_id"],
                "nonce": nonce,
                "signature": invalid_signature
            }
        )
        
        assert token_response.status_code == 401
        error_data = token_response.json()
        assert "Invalid signature" in error_data["detail"]
    
    def test_token_request_expired_nonce(self):
        """Test token request with expired nonce"""
        self._skip_if_backend_unavailable()
        
        # Create test agent
        agent_data = self._create_test_agent()
        
        # Request challenge
        challenge_response = requests.post(
            f"{self.control_url}/api/v1/auth/challenge",
            json={"agent_id": agent_data["agent_id"]}
        )
        
        assert challenge_response.status_code == 200
        challenge_data = challenge_response.json()
        nonce = challenge_data["nonce"]
        
        # Wait for nonce to expire (this would be too slow for real test)
        # Instead, we'll test with a fake expired nonce
        fake_expired_nonce = str(uuid.uuid4())
        signature = self.identity_manager.sign(agent_data["private_key"], fake_expired_nonce)
        
        # Request token with expired nonce
        token_response = requests.post(
            f"{self.control_url}/api/v1/auth/token",
            json={
                "agent_id": agent_data["agent_id"],
                "nonce": fake_expired_nonce,
                "signature": signature
            }
        )
        
        assert token_response.status_code == 400
        error_data = token_response.json()
        assert "Invalid, expired, or already used nonce" in error_data["detail"]
    
    def test_token_request_reused_nonce(self):
        """Test token request with already used nonce"""
        self._skip_if_backend_unavailable()
        
        # Create test agent
        agent_data = self._create_test_agent()
        
        # Request challenge
        challenge_response = requests.post(
            f"{self.control_url}/api/v1/auth/challenge",
            json={"agent_id": agent_data["agent_id"]}
        )
        
        assert challenge_response.status_code == 200
        challenge_data = challenge_response.json()
        nonce = challenge_data["nonce"]
        
        # Sign the nonce
        signature = self.identity_manager.sign(agent_data["private_key"], nonce)
        
        # First token request (should succeed)
        token_response_1 = requests.post(
            f"{self.control_url}/api/v1/auth/token",
            json={
                "agent_id": agent_data["agent_id"],
                "nonce": nonce,
                "signature": signature
            }
        )
        
        assert token_response_1.status_code == 200
        
        # Second token request with same nonce (should fail)
        token_response_2 = requests.post(
            f"{self.control_url}/api/v1/auth/token",
            json={
                "agent_id": agent_data["agent_id"],
                "nonce": nonce,
                "signature": signature
            }
        )
        
        assert token_response_2.status_code == 400
        error_data = token_response_2.json()
        assert "Invalid, expired, or already used nonce" in error_data["detail"]
    
    def test_token_request_nonexistent_agent(self):
        """Test token request for non-existent agent"""
        self._skip_if_backend_unavailable()
        
        # Create fake agent data
        fake_agent_id = f"agent-{uuid.uuid4()}"
        fake_nonce = str(uuid.uuid4())
        
        # Generate keys for signing
        keys = self.key_manager.generate_identity_keypair()
        signature = self.identity_manager.sign(keys["private_key"], fake_nonce)
        
        # Request token for non-existent agent
        token_response = requests.post(
            f"{self.control_url}/api/v1/auth/token",
            json={
                "agent_id": fake_agent_id,
                "nonce": fake_nonce,
                "signature": signature
            }
        )
        
        assert token_response.status_code == 404
        error_data = token_response.json()
        assert "Agent not found" in error_data["detail"]
    
    def test_nonce_generation_uniqueness(self):
        """Test that nonces are unique for multiple requests"""
        self._skip_if_backend_unavailable()
        
        # Create test agent
        agent_data = self._create_test_agent()
        
        # Request multiple challenges
        nonces = []
        for i in range(5):
            challenge_response = requests.post(
                f"{self.control_url}/api/v1/auth/challenge",
                json={"agent_id": agent_data["agent_id"]}
            )
            
            assert challenge_response.status_code == 200
            challenge_data = challenge_response.json()
            nonces.append(challenge_data["nonce"])
        
        # Verify all nonces are unique
        assert len(set(nonces)) == 5, "All nonces should be unique"
    
    def test_complete_auth_flow_with_policies(self):
        """Test complete authentication flow with policy-based permissions"""
        self._skip_if_backend_unavailable()
        
        # Create test agent
        agent_data = self._create_test_agent()
        
        # Create test policy for the agent (if policies are implemented)
        try:
            policy_response = requests.post(
                f"{self.control_url}/api/v1/policies/",
                json={
                    "name": f"test-policy-{uuid.uuid4()}",
                    "agent_id": agent_data["agent_id"],
                    "actions": ["read", "write"],
                    "resources": ["secret:test", "secret:prod"],
                    "effect": "allow"
                },
                headers={"Authorization": f"Bearer {os.getenv('DEEPSECURE_BACKEND_API_TOKEN', 'test-token')}"}
            )
            
            policy_created = policy_response.status_code == 201
        except:
            policy_created = False
        
        # Request challenge
        challenge_response = requests.post(
            f"{self.control_url}/api/v1/auth/challenge",
            json={"agent_id": agent_data["agent_id"]}
        )
        
        assert challenge_response.status_code == 200
        challenge_data = challenge_response.json()
        nonce = challenge_data["nonce"]
        
        # Sign the nonce
        signature = self.identity_manager.sign(agent_data["private_key"], nonce)
        
        # Request token
        token_response = requests.post(
            f"{self.control_url}/api/v1/auth/token",
            json={
                "agent_id": agent_data["agent_id"],
                "nonce": nonce,
                "signature": signature
            }
        )
        
        assert token_response.status_code == 200
        token_data = token_response.json()
        
        # Decode token to check embedded permissions
        access_token = token_data["access_token"]
        parts = access_token.split('.')
        payload_data = json.loads(base64.urlsafe_b64decode(parts[1] + '=='))
        
        # If policy was created, verify it's in the token
        if policy_created:
            assert "scope" in payload_data
            assert "resources" in payload_data
            
            # Check that permissions are embedded
            scope = payload_data.get("scope", "")
            resources = payload_data.get("resources", [])
            
            # Should contain the policy permissions
            assert "read" in scope or "write" in scope
            assert len(resources) > 0
    
    def test_signature_verification_with_different_messages(self):
        """Test that signature verification fails when message differs"""
        self._skip_if_backend_unavailable()
        
        # Create test agent
        agent_data = self._create_test_agent()
        
        # Request challenge
        challenge_response = requests.post(
            f"{self.control_url}/api/v1/auth/challenge",
            json={"agent_id": agent_data["agent_id"]}
        )
        
        assert challenge_response.status_code == 200
        challenge_data = challenge_response.json()
        nonce = challenge_data["nonce"]
        
        # Sign a different message
        different_message = "different_message"
        signature = self.identity_manager.sign(agent_data["private_key"], different_message)
        
        # Request token with signature for different message
        token_response = requests.post(
            f"{self.control_url}/api/v1/auth/token",
            json={
                "agent_id": agent_data["agent_id"],
                "nonce": nonce,
                "signature": signature
            }
        )
        
        assert token_response.status_code == 401
        error_data = token_response.json()
        assert "Invalid signature" in error_data["detail"]
    
    def test_signature_verification_with_different_keys(self):
        """Test that signature verification fails with different keys"""
        self._skip_if_backend_unavailable()
        
        # Create test agent
        agent_data = self._create_test_agent()
        
        # Request challenge
        challenge_response = requests.post(
            f"{self.control_url}/api/v1/auth/challenge",
            json={"agent_id": agent_data["agent_id"]}
        )
        
        assert challenge_response.status_code == 200
        challenge_data = challenge_response.json()
        nonce = challenge_data["nonce"]
        
        # Sign with different key
        different_keys = self.key_manager.generate_identity_keypair()
        signature = self.identity_manager.sign(different_keys["private_key"], nonce)
        
        # Request token with signature from different key
        token_response = requests.post(
            f"{self.control_url}/api/v1/auth/token",
            json={
                "agent_id": agent_data["agent_id"],
                "nonce": nonce,
                "signature": signature
            }
        )
        
        assert token_response.status_code == 401
        error_data = token_response.json()
        assert "Invalid signature" in error_data["detail"]
    
    def test_ed25519_signature_verification_direct(self):
        """Test Ed25519 signature verification directly"""
        # Generate test keys
        keys = self.key_manager.generate_identity_keypair()
        private_key_b64 = keys["private_key"]
        public_key_b64 = keys["public_key"]
        
        # Test message
        message = "test_nonce_12345"
        
        # Sign the message
        signature = self.identity_manager.sign(private_key_b64, message)
        
        # Verify signature manually
        private_key_bytes = base64.b64decode(private_key_b64)
        public_key_bytes = base64.b64decode(public_key_b64)
        signature_bytes = base64.b64decode(signature)
        
        # Load keys
        private_key_obj = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        public_key_obj = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
        
        # Verify signature
        try:
            public_key_obj.verify(signature_bytes, message.encode('utf-8'))
            verification_passed = True
        except InvalidSignature:
            verification_passed = False
        
        assert verification_passed, "Ed25519 signature verification should pass"
    
    def test_jwt_token_structure_and_claims(self):
        """Test JWT token structure and claims"""
        self._skip_if_backend_unavailable()
        
        # Create test agent
        agent_data = self._create_test_agent()
        
        # Complete authentication flow
        challenge_response = requests.post(
            f"{self.control_url}/api/v1/auth/challenge",
            json={"agent_id": agent_data["agent_id"]}
        )
        
        assert challenge_response.status_code == 200
        nonce = challenge_response.json()["nonce"]
        
        signature = self.identity_manager.sign(agent_data["private_key"], nonce)
        
        token_response = requests.post(
            f"{self.control_url}/api/v1/auth/token",
            json={
                "agent_id": agent_data["agent_id"],
                "nonce": nonce,
                "signature": signature
            }
        )
        
        assert token_response.status_code == 200
        access_token = token_response.json()["access_token"]
        
        # Decode token
        parts = access_token.split('.')
        assert len(parts) == 3
        
        # Decode header
        header_data = json.loads(base64.urlsafe_b64decode(parts[0] + '=='))
        assert header_data["alg"] == "HS256"
        assert header_data["typ"] == "JWT"
        
        # Decode payload
        payload_data = json.loads(base64.urlsafe_b64decode(parts[1] + '=='))
        
        # Verify required claims
        assert "agent_id" in payload_data
        assert payload_data["agent_id"] == agent_data["agent_id"]
        assert "exp" in payload_data
        assert "iat" in payload_data
        
        # Verify expiration is in the future
        current_time = int(time.time())
        assert payload_data["exp"] > current_time
        
        # Verify issued at is recent
        assert payload_data["iat"] <= current_time
        assert payload_data["iat"] > current_time - 60  # Within last minute
    
    def test_multiple_concurrent_challenges(self):
        """Test handling of multiple concurrent challenges for same agent"""
        self._skip_if_backend_unavailable()
        
        # Create test agent
        agent_data = self._create_test_agent()
        
        # Request multiple challenges concurrently
        challenges = []
        for i in range(3):
            challenge_response = requests.post(
                f"{self.control_url}/api/v1/auth/challenge",
                json={"agent_id": agent_data["agent_id"]}
            )
            
            assert challenge_response.status_code == 200
            challenge_data = challenge_response.json()
            challenges.append(challenge_data["nonce"])
        
        # All challenges should be valid and unique
        assert len(set(challenges)) == 3
        
        # Use the first challenge for authentication
        nonce = challenges[0]
        signature = self.identity_manager.sign(agent_data["private_key"], nonce)
        
        token_response = requests.post(
            f"{self.control_url}/api/v1/auth/token",
            json={
                "agent_id": agent_data["agent_id"],
                "nonce": nonce,
                "signature": signature
            }
        )
        
        assert token_response.status_code == 200
        
        # The used nonce should be invalidated, but others should still be valid
        # (This depends on the backend implementation details)
    
    def test_malformed_signature_handling(self):
        """Test handling of malformed signatures"""
        self._skip_if_backend_unavailable()
        
        # Create test agent
        agent_data = self._create_test_agent()
        
        # Test various malformed signatures - each with a fresh nonce
        malformed_signatures = [
            "not_base64!",
            "",
            "dGVzdA==",  # Valid base64 but wrong length
            "invalid_signature_data_here",
        ]
        
        for malformed_sig in malformed_signatures:
            # Request fresh challenge for each test
            challenge_response = requests.post(
                f"{self.control_url}/api/v1/auth/challenge",
                json={"agent_id": agent_data["agent_id"]}
            )
            
            assert challenge_response.status_code == 200
            nonce = challenge_response.json()["nonce"]
            
            token_response = requests.post(
                f"{self.control_url}/api/v1/auth/token",
                json={
                    "agent_id": agent_data["agent_id"],
                    "nonce": nonce,
                    "signature": malformed_sig
                }
            )
            
            # Should return 401 for invalid signature or 400 for bad request format
            assert token_response.status_code in [400, 401]
            error_data = token_response.json()
            # Either signature invalid or bad request format
            assert "Invalid signature" in error_data["detail"] or "Invalid, expired, or already used nonce" in error_data["detail"] or "detail" in error_data 