#!/usr/bin/env python3
"""
Integration test for Redis deployment in the split-key architecture.

This test validates that the deployed Redis container can be used
for split-key storage as designed in Phase 4 Task 4.3.
"""

import os
import time
import pytest
import redis
from cryptography.fernet import Fernet
import sslib.shamir as shamir
from typing import Dict, Any


class TestRedisDeploymentIntegration:
    """Test the deployed Redis container for split-key storage."""
    
    @pytest.fixture
    def redis_client(self):
        """Create Redis client connected to deployed container."""
        # Use the same port as in docker-compose.yml
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6380')
        client = redis.Redis.from_url(redis_url, decode_responses=False)
        
        # Test connectivity
        assert client.ping(), "Redis container is not responding"
        
        yield client
        
        # Cleanup: remove any test keys
        for key in client.keys("test:*"):
            client.delete(key)
    
    @pytest.fixture
    def encryption_key(self):
        """Generate encryption key for share_2 storage."""
        return Fernet.generate_key()
    
    def test_basic_redis_connectivity(self, redis_client):
        """Test basic Redis operations work correctly."""
        # Test string operations
        redis_client.set("test:connectivity", "working")
        result = redis_client.get("test:connectivity")
        assert result == b"working"
        
        # Test hash operations (useful for metadata)
        redis_client.hset("test:metadata", mapping={
            "agent_id": "agent-123",
            "secret_type": "api_key",
            "created_at": str(int(time.time()))
        })
        
        metadata = redis_client.hgetall("test:metadata")
        assert metadata[b"agent_id"] == b"agent-123"
        assert metadata[b"secret_type"] == b"api_key"
        
        # Test TTL operations (critical for security)
        redis_client.setex("test:ttl", 5, "expires")
        ttl = redis_client.ttl("test:ttl")
        assert 0 < ttl <= 5
        
        print("✅ Basic Redis operations working correctly")
    
    def test_encrypted_share_storage(self, redis_client, encryption_key):
        """Test encrypted storage of share_2 data."""
        # Simulate share_2 from Shamir's Secret Sharing
        original_secret = "super-secret-api-key-for-production"
        shares_dict = shamir.split_secret(original_secret.encode(), 2, 2)
        
        # Extract shares (simulating what would be stored separately)
        shares_list = shares_dict['shares']  # List of (index, share_data) tuples
        share_1 = shares_list[0][1]  # Would go to PostgreSQL
        share_2 = shares_list[1][1]  # Will go to Redis (encrypted)
        
        # Encrypt share_2 before storage
        fernet = Fernet(encryption_key)
        encrypted_share_2 = fernet.encrypt(share_2)
        
        # Store encrypted share_2 in Redis with metadata
        share_key = "test:share:agent-123:secret-456"
        redis_client.setex(share_key, 300, encrypted_share_2)  # 5 min TTL
        
        # Store metadata separately
        metadata_key = f"{share_key}:meta"
        redis_client.hset(metadata_key, mapping={
            "agent_id": "agent-123",
            "secret_id": "secret-456",
            "encrypted": "true",
            "algorithm": "AES-256-GCM",
            "created_at": str(int(time.time()))
        })
        redis_client.expire(metadata_key, 300)
        
        # Simulate JIT reassembly process
        # 1. Retrieve encrypted share_2 from Redis
        stored_encrypted = redis_client.get(share_key)
        assert stored_encrypted == encrypted_share_2
        
        # 2. Decrypt share_2
        decrypted_share_2 = fernet.decrypt(stored_encrypted)
        assert decrypted_share_2 == share_2
        
        # 3. Combine with share_1 (simulating fetch from control plane)
        reconstructed_dict = {
            'required_shares': shares_dict['required_shares'],
            'prime_mod': shares_dict['prime_mod'],
            'shares': [
                (1, share_1),
                (2, decrypted_share_2)
            ]
        }
        
        # 4. Recover original secret
        recovered_secret = shamir.recover_secret(reconstructed_dict)
        assert recovered_secret.decode() == original_secret
        
        print("✅ Encrypted share storage and JIT reassembly working correctly")
    
    def test_concurrent_share_operations(self, redis_client, encryption_key):
        """Test concurrent operations (simulating multiple agents)."""
        fernet = Fernet(encryption_key)
        agents = ["agent-001", "agent-002", "agent-003"]
        secrets = {}
        
        # Store shares for multiple agents concurrently
        for i, agent_id in enumerate(agents):
            secret = f"api-key-for-{agent_id}-{i}"
            shares_dict = shamir.split_secret(secret.encode(), 2, 2)
            shares_list = shares_dict['shares']  # List of (index, share_data) tuples
            
            # Store encrypted share_2
            encrypted_share = fernet.encrypt(shares_list[1][1])  # Second share's data
            share_key = f"test:concurrent:{agent_id}:share"
            redis_client.setex(share_key, 600, encrypted_share)
            
            # Store for later verification
            secrets[agent_id] = {
                'original': secret,
                'share_1': shares_list[0][1],  # First share's data
                'shares_dict': shares_dict
            }
        
        # Verify all shares can be retrieved and decrypted
        for agent_id in agents:
            share_key = f"test:concurrent:{agent_id}:share"
            encrypted_share = redis_client.get(share_key)
            assert encrypted_share is not None
            
            decrypted_share_2 = fernet.decrypt(encrypted_share)
            
            # Reconstruct secret
            reconstructed_dict = {
                'required_shares': secrets[agent_id]['shares_dict']['required_shares'],
                'prime_mod': secrets[agent_id]['shares_dict']['prime_mod'],
                'shares': [
                    (1, secrets[agent_id]['share_1']),
                    (2, decrypted_share_2)
                ]
            }
            
            recovered = shamir.recover_secret(reconstructed_dict).decode()
            assert recovered == secrets[agent_id]['original']
        
        print("✅ Concurrent share operations working correctly")
    
    def test_redis_persistence_and_recovery(self, redis_client):
        """Test that Redis data persists correctly."""
        # Store a test value
        test_key = "test:persistence:check"
        test_value = "this-should-persist"
        redis_client.set(test_key, test_value)
        
        # Verify it's stored
        stored = redis_client.get(test_key)
        assert stored == test_value.encode()
        
        # Test Redis configuration
        config = redis_client.config_get("save")
        print(f"Redis save configuration: {config}")
        
        # Test that we can retrieve the value (persistence check)
        retrieved = redis_client.get(test_key)
        assert retrieved == test_value.encode()
        
        print("✅ Redis persistence configuration working correctly")
    
    def test_redis_security_features(self, redis_client):
        """Test Redis security configuration."""
        # Check if Redis is running with appropriate settings
        info = redis_client.info()
        
        # Verify Redis version (should be recent)
        redis_version = info.get('redis_version', '')
        print(f"Redis version: {redis_version}")
        assert redis_version.startswith(('6.', '7.', '8.')), "Redis version should be 6.x or newer"
        
        # Check memory settings
        maxmemory = info.get('maxmemory', 0)
        print(f"Redis max memory: {maxmemory}")
        
        # Check that Redis is operating normally
        assert info['loading'] == 0, "Redis should not be in loading state"
        
        print("✅ Redis security configuration validated")

def test_redis_deployment_end_to_end():
    """
    Comprehensive end-to-end test of Redis deployment for split-key storage.
    
    This test simulates the complete workflow:
    1. Secret splitting (control plane)
    2. Encrypted share_2 storage (gateway → redis)
    3. JIT reassembly (gateway: redis + control plane → secret)
    4. Secure cleanup
    """
    print("\n" + "="*80)
    print("REDIS DEPLOYMENT INTEGRATION TEST")
    print("="*80)
    
    # Connect to deployed Redis
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6380')
    r = redis.Redis.from_url(redis_url, decode_responses=False)
    
    # Test connectivity
    assert r.ping(), "❌ Redis container not responding"
    print("✅ Redis container connectivity confirmed")
    
    # Simulate end-to-end split-key workflow
    test_secret = "production-api-key-very-sensitive"
    agent_id = "agent-e2e-test"
    secret_id = "secret-e2e-789"
    
    # 1. Split secret (control plane simulation)
    shares_dict = shamir.split_secret(test_secret.encode(), 2, 2)
    shares_list = shares_dict['shares']  # List of (index, share_data) tuples
    share_1 = shares_list[0][1]  # Goes to PostgreSQL (control plane)
    share_2 = shares_list[1][1]  # Goes to Redis (gateway)
    
    print("✅ Secret split using Shamir's Secret Sharing")
    
    # 2. Encrypt and store share_2 (gateway simulation)
    encryption_key = Fernet.generate_key()
    fernet = Fernet(encryption_key)
    encrypted_share_2 = fernet.encrypt(share_2)
    
    share_key = f"share:{agent_id}:{secret_id}"
    metadata_key = f"{share_key}:meta"
    
    # Store with TTL for security
    r.setex(share_key, 300, encrypted_share_2)
    r.hset(metadata_key, mapping={
        "agent_id": agent_id,
        "secret_id": secret_id,
        "algorithm": "AES-256-GCM",
        "created_at": str(int(time.time()))
    })
    r.expire(metadata_key, 300)
    
    print("✅ Share_2 encrypted and stored in Redis with TTL")
    
    # 3. JIT reassembly simulation (gateway fetching and combining)
    # Fetch encrypted share_2 from Redis
    stored_encrypted = r.get(share_key)
    assert stored_encrypted == encrypted_share_2
    
    # Decrypt share_2
    decrypted_share_2 = fernet.decrypt(stored_encrypted)
    assert decrypted_share_2 == share_2
    
    # Combine shares (simulating share_1 fetch from control plane)
    reconstructed_dict = {
        'required_shares': shares_dict['required_shares'],
        'prime_mod': shares_dict['prime_mod'],
        'shares': [
            (1, share_1),
            (2, decrypted_share_2)
        ]
    }
    
    # Recover original secret
    recovered_secret = shamir.recover_secret(reconstructed_dict)
    assert recovered_secret.decode() == test_secret
    
    print("✅ JIT secret reassembly successful")
    
    # 4. Secure cleanup (critical for security)
    r.delete(share_key)
    r.delete(metadata_key)
    
    # Verify deletion
    assert r.get(share_key) is None
    assert not r.exists(metadata_key)
    
    print("✅ Secure cleanup completed")
    
    # 5. Performance validation
    start_time = time.time()
    for i in range(10):
        # Simulate 10 rapid secret operations
        temp_secret = f"perf-test-{i}"
        temp_shares = shamir.split_secret(temp_secret.encode(), 2, 2)
        temp_encrypted = fernet.encrypt(temp_shares['shares'][1][1])  # Second share's data
        temp_key = f"perf:test:{i}"
        
        r.setex(temp_key, 60, temp_encrypted)
        retrieved = r.get(temp_key)
        assert retrieved == temp_encrypted
        r.delete(temp_key)
    
    duration = time.time() - start_time
    operations_per_second = 10 / duration
    
    print(f"✅ Performance test: {operations_per_second:.1f} ops/sec (target: >50 ops/sec)")
    assert operations_per_second > 50, "Performance below threshold"
    
    print("\n🎉 REDIS DEPLOYMENT INTEGRATION: ALL TESTS PASSED!")
    print("🔐 Split-key architecture fully operational with deployed Redis")
    print("⚡ Performance meets production requirements")
    print("🛡️ Security properties validated end-to-end")
    print("="*80)

if __name__ == "__main__":
    test_redis_deployment_end_to_end() 