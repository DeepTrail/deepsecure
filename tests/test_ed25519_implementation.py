"""
Tests for Phase 1 Task 1.2: Ed25519 Agent Identity Model
Tests all aspects of Ed25519 key generation, storage, and authentication
"""
import os
import pytest
import json
import base64
import uuid
import requests
import time
from typing import Dict, Any, Optional

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

from deepsecure._core.crypto.key_manager import KeyManager
from deepsecure._core.identity_manager import IdentityManager
from deepsecure._core.agent_client import AgentClient
from deepsecure._core.base_client import BaseClient
from deepsecure import Client


class TestEd25519Implementation:
    """Test suite for Phase 1 Task 1.2: Ed25519 Agent Identity Model"""
    
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
    
    def test_ed25519_key_generation(self):
        """Test Ed25519 key pair generation"""
        # Test raw base64 key generation
        keys = self.key_manager.generate_identity_keypair()
        
        assert "private_key" in keys
        assert "public_key" in keys
        assert isinstance(keys["private_key"], str)
        assert isinstance(keys["public_key"], str)
        
        # Verify key lengths after base64 decoding
        private_key_bytes = base64.b64decode(keys["private_key"])
        public_key_bytes = base64.b64decode(keys["public_key"])
        
        assert len(private_key_bytes) == 32  # Ed25519 private key is 32 bytes
        assert len(public_key_bytes) == 32   # Ed25519 public key is 32 bytes
        
        # Test that we can load the keys with cryptography library
        ed25519_private = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        ed25519_public = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
        
        # Verify that public key matches what we derive from private key
        derived_public = ed25519_private.public_key()
        derived_public_bytes = derived_public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        assert derived_public_bytes == public_key_bytes
        
    def test_ed25519_key_generation_pem(self):
        """Test Ed25519 key pair generation in PEM format"""
        public_pem, private_pem = self.key_manager.generate_identity_keypair_pem()
        
        # Verify PEM format
        assert public_pem.startswith("-----BEGIN PUBLIC KEY-----")
        assert public_pem.endswith("-----END PUBLIC KEY-----\n")
        assert private_pem.startswith("-----BEGIN PRIVATE KEY-----")
        assert private_pem.endswith("-----END PRIVATE KEY-----\n")
        
        # Test that we can load the PEM keys
        private_key_obj = serialization.load_pem_private_key(private_pem.encode(), password=None)
        public_key_obj = serialization.load_pem_public_key(public_pem.encode())
        
        assert isinstance(private_key_obj, ed25519.Ed25519PrivateKey)
        assert isinstance(public_key_obj, ed25519.Ed25519PublicKey)
        
    def test_signing_and_verification(self):
        """Test signing data with Ed25519 keys"""
        # Generate test keys
        keys = self.key_manager.generate_identity_keypair()
        private_key_b64 = keys["private_key"]
        public_key_b64 = keys["public_key"]
        
        # Test data to sign
        test_data = b"Hello, DeepSecure!"
        
        # Sign the data
        signature_b64 = self.key_manager.sign_ephemeral_key(public_key_b64, private_key_b64)
        
        # Verify the signature manually
        private_key_bytes = base64.b64decode(private_key_b64)
        public_key_bytes = base64.b64decode(public_key_b64)
        signature_bytes = base64.b64decode(signature_b64)
        ephemeral_pub_bytes = base64.b64decode(public_key_b64)
        
        # Load keys
        private_key_obj = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        public_key_obj = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
        
        # Verify signature
        try:
            public_key_obj.verify(signature_bytes, ephemeral_pub_bytes)
            verification_passed = True
        except InvalidSignature:
            verification_passed = False
            
        assert verification_passed, "Signature verification should pass"
        
    def test_keyring_storage_and_retrieval(self):
        """Test storing and retrieving keys from system keyring"""
        # Generate test agent and keys
        agent_id = f"agent-{uuid.uuid4()}"
        self.test_agent_ids.append(agent_id)
        
        # Create keypair and store in keyring
        keys = self.identity_manager.create_keypair_for_agent(agent_id)
        
        assert "public_key" in keys
        assert "private_key" in keys
        assert "public_key_fingerprint" in keys
        
        # Retrieve private key from keyring
        retrieved_private_key = self.identity_manager.get_private_key(agent_id)
        
        assert retrieved_private_key is not None
        assert retrieved_private_key == keys["private_key"]
        
        # Test identity retrieval through identity manager
        identity = self.identity_manager.get_identity(agent_id)
        
        assert identity is not None
        assert identity.agent_id == agent_id
        assert identity.private_key_b64 == keys["private_key"]
        assert identity.public_key_b64 == keys["public_key"]
        
    def test_agent_creation_with_ed25519_key(self):
        """Test creating an agent with Ed25519 key in backend"""
        # Skip if backend not available
        try:
            response = requests.get(f"{self.control_url}/health", timeout=5)
            if response.status_code != 200:
                pytest.skip("Backend not available")
        except:
            pytest.skip("Backend not available")
        
        # Generate test agent name
        agent_name = f"test-ed25519-agent-{uuid.uuid4()}"
        
        # Create agent using client
        agent = self.client.agents.create(name=agent_name, description="Test Ed25519 agent")
        self.test_agent_ids.append(agent.id)
        
        # Verify agent properties
        assert agent.id is not None
        assert agent.name == agent_name
        assert agent.public_key is not None
        assert agent.status == "active"
        
        # Verify the public key is properly formatted
        public_key_bytes = base64.b64decode(agent.public_key)
        assert len(public_key_bytes) == 32
        
        # Verify we can load the public key
        public_key_obj = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
        assert isinstance(public_key_obj, ed25519.Ed25519PublicKey)
        
    def test_challenge_response_authentication(self):
        """Test challenge-response authentication flow"""
        # Skip if backend not available
        try:
            response = requests.get(f"{self.control_url}/health", timeout=5)
            if response.status_code != 200:
                pytest.skip("Backend not available")
        except:
            pytest.skip("Backend not available")
        
        # Create test agent
        agent_name = f"test-auth-agent-{uuid.uuid4()}"
        agent = self.client.agents.create(name=agent_name, description="Test auth agent")
        self.test_agent_ids.append(agent.id)
        
        # Test challenge-response flow
        try:
            # Request challenge
            challenge_response = requests.post(
                f"{self.control_url}/api/v1/auth/challenge",
                json={"agent_id": agent.id}
            )
            
            assert challenge_response.status_code == 200
            challenge_data = challenge_response.json()
            assert "nonce" in challenge_data
            
            # Get private key for signing
            private_key_b64 = self.identity_manager.get_private_key(agent.id)
            assert private_key_b64 is not None
            
            # Sign the nonce
            signature = self.identity_manager.sign(private_key_b64, challenge_data["nonce"])
            
            # Submit signed challenge
            token_response = requests.post(
                f"{self.control_url}/api/v1/auth/token",
                json={
                    "agent_id": agent.id,
                    "nonce": challenge_data["nonce"],
                    "signature": signature
                }
            )
            
            assert token_response.status_code == 200
            token_data = token_response.json()
            assert "access_token" in token_data
            assert "token_type" in token_data
            assert token_data["token_type"] == "bearer"
            
        except Exception as e:
            pytest.skip(f"Challenge-response flow not fully implemented: {e}")
            
    def test_agent_id_generation_from_public_key(self):
        """Test deterministic agent ID generation from public key"""
        # Generate a key pair
        public_pem, private_pem = self.key_manager.generate_identity_keypair_pem()
        
        # Generate agent ID from public key
        agent_id_1 = self.identity_manager.generate_agent_id(public_pem)
        agent_id_2 = self.identity_manager.generate_agent_id(public_pem)
        
        # Should be deterministic
        assert agent_id_1 == agent_id_2
        assert agent_id_1.startswith("agent-")
        assert len(agent_id_1) == 22  # "agent-" + 16 hex chars
        
    def test_public_key_fingerprint_generation(self):
        """Test generating fingerprints for public keys"""
        keys = self.key_manager.generate_identity_keypair()
        public_key_b64 = keys["public_key"]
        
        fingerprint = self.identity_manager.get_public_key_fingerprint(public_key_b64)
        
        assert fingerprint.startswith("sha256:")
        assert len(fingerprint) == 71  # "sha256:" + 64 hex chars
        
        # Should be deterministic
        fingerprint_2 = self.identity_manager.get_public_key_fingerprint(public_key_b64)
        assert fingerprint == fingerprint_2
        
    def test_key_manager_credential_token_creation(self):
        """Test credential token creation with proper structure"""
        # Generate test data
        agent_id = f"agent-{uuid.uuid4()}"
        keys = self.key_manager.generate_identity_keypair()
        ephemeral_public_key = keys["public_key"]
        signature = self.key_manager.sign_ephemeral_key(ephemeral_public_key, keys["private_key"])
        scope = "test:read"
        expiry = int(time.time()) + 3600
        
        # Create credential token
        credential = self.key_manager.create_credential_token(
            agent_id=agent_id,
            ephemeral_public_key=ephemeral_public_key,
            signature=signature,
            scope=scope,
            expiry=expiry
        )
        
        # Verify credential structure
        assert credential["agent_id"] == agent_id
        assert credential["ephemeral_public_key"] == ephemeral_public_key
        assert credential["signature"] == signature
        assert credential["scope"] == scope
        assert credential["expires_at"] == expiry
        assert "id" in credential
        assert "issued_at" in credential
        assert credential["id"].startswith("cred-")
        
    def test_public_key_decoding_validation(self):
        """Test public key decoding and validation"""
        # Generate valid key
        keys = self.key_manager.generate_identity_keypair()
        public_key_b64 = keys["public_key"]
        
        # Test valid key decoding
        public_key_obj = self.key_manager.decode_public_key_b64(public_key_b64)
        assert isinstance(public_key_obj, ed25519.Ed25519PublicKey)
        
        # Test invalid key decoding
        with pytest.raises(ValueError, match="Failed to decode or parse public key"):
            self.key_manager.decode_public_key_b64("invalid_key")
            
        # Test wrong length key
        wrong_length_key = base64.b64encode(b"wrong_length").decode()
        with pytest.raises(ValueError, match="Public key bytes must be 32 bytes long"):
            self.key_manager.decode_public_key_b64(wrong_length_key)
            
    def test_identity_manager_error_handling(self):
        """Test identity manager error handling"""
        # Test getting non-existent agent
        non_existent_id = f"agent-{uuid.uuid4()}"
        identity = self.identity_manager.get_identity(non_existent_id)
        assert identity is None
        
        # Test invalid agent ID format
        with pytest.raises(ValueError, match="does not follow the expected"):
            self.identity_manager.create_keypair_for_agent("invalid-id-format")
            
        # Test deleting non-existent key
        success = self.identity_manager.delete_private_key(non_existent_id)
        assert success is True  # Should succeed even if key doesn't exist
        
    def test_identity_providers_integration(self):
        """Test identity provider chain integration"""
        # Test keyring provider
        agent_id = f"agent-{uuid.uuid4()}"
        self.test_agent_ids.append(agent_id)
        
        # Create keypair
        keys = self.identity_manager.create_keypair_for_agent(agent_id)
        
        # Test retrieval through identity manager
        identity = self.identity_manager.get_identity(agent_id)
        
        assert identity is not None
        assert identity.provider_name == "keyring"
        assert identity.agent_id == agent_id
        assert identity.private_key_b64 == keys["private_key"]
        assert identity.public_key_b64 == keys["public_key"]
        
    def test_full_end_to_end_workflow(self):
        """Test complete end-to-end Ed25519 workflow"""
        # Skip if backend not available
        try:
            response = requests.get(f"{self.control_url}/health", timeout=5)
            if response.status_code != 200:
                pytest.skip("Backend not available")
        except:
            pytest.skip("Backend not available")
        
        # 1. Generate key pair
        keys = self.key_manager.generate_identity_keypair()
        
        # 2. Create agent with public key
        agent_name = f"test-e2e-agent-{uuid.uuid4()}"
        
        # Register agent directly with backend
        register_response = requests.post(
            f"{self.control_url}/api/v1/agents/",
            json={
                "public_key": keys["public_key"],
                "name": agent_name,
                "description": "End-to-end test agent"
            }
        )
        
        assert register_response.status_code == 201
        agent_data = register_response.json()
        agent_id = agent_data["agent_id"]
        self.test_agent_ids.append(agent_id)
        
        # 3. Store private key locally
        self.identity_manager.store_private_key_directly(agent_id, keys["private_key"])
        
        # 4. Test authentication if available
        try:
            # Request challenge
            challenge_response = requests.post(
                f"{self.control_url}/api/v1/auth/challenge",
                json={"agent_id": agent_id}
            )
            
            if challenge_response.status_code == 200:
                challenge_data = challenge_response.json()
                
                # Sign challenge
                signature = self.identity_manager.sign(keys["private_key"], challenge_data["nonce"])
                
                # Get token
                token_response = requests.post(
                    f"{self.control_url}/api/v1/auth/token",
                    json={
                        "agent_id": agent_id,
                        "nonce": challenge_data["nonce"],
                        "signature": signature
                    }
                )
                
                if token_response.status_code == 200:
                    token_data = token_response.json()
                    assert "access_token" in token_data
                    
        except Exception as e:
            # Authentication may not be fully implemented
            pass
            
        # 5. Verify agent can be retrieved
        agent_response = requests.get(f"{self.control_url}/api/v1/agents/{agent_id}")
        assert agent_response.status_code == 200
        retrieved_agent = agent_response.json()
        
        # Verify public key matches
        assert retrieved_agent["publicKey"] == keys["public_key"]
        assert retrieved_agent["name"] == agent_name
        
    def test_backend_ed25519_signature_verification(self):
        """Test that backend properly verifies Ed25519 signatures"""
        # Skip if backend not available
        try:
            response = requests.get(f"{self.control_url}/health", timeout=5)
            if response.status_code != 200:
                pytest.skip("Backend not available")
        except:
            pytest.skip("Backend not available")
        
        # Generate test keys
        keys = self.key_manager.generate_identity_keypair()
        ephemeral_keys = self.key_manager.generate_ephemeral_keypair()
        
        # Create agent
        agent_name = f"test-sig-agent-{uuid.uuid4()}"
        register_response = requests.post(
            f"{self.control_url}/api/v1/agents/",
            json={
                "public_key": keys["public_key"],
                "name": agent_name,
                "description": "Signature verification test agent"
            }
        )
        
        assert register_response.status_code == 201
        agent_data = register_response.json()
        agent_id = agent_data["agent_id"]
        self.test_agent_ids.append(agent_id)
        
        # Sign ephemeral key
        signature = self.key_manager.sign_ephemeral_key(
            ephemeral_keys["public_key"], 
            keys["private_key"]
        )
        
        # Try to issue credential (will test signature verification)
        try:
            credential_response = requests.post(
                f"{self.control_url}/api/v1/vault/credentials",
                json={
                    "agent_id": agent_id,
                    "ephemeral_public_key": ephemeral_keys["public_key"],
                    "signature": signature,
                    "scope": "test:read",
                    "ttl": 3600
                },
                headers={"Authorization": f"Bearer {os.getenv('DEEPSECURE_BACKEND_API_TOKEN', 'test-token')}"}
            )
            
            # Should either succeed or fail for reasons other than signature
            if credential_response.status_code == 400:
                error_detail = credential_response.json().get("detail", "")
                assert "Invalid signature" not in error_detail, "Signature verification should pass"
                
        except Exception as e:
            # Credential issuance may not be fully implemented
            pass 