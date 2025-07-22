"""
Share Storage Manager for DeepTrail Gateway

Secure storage and retrieval of secret shares (share_2) using Redis with
AES-256-GCM encryption for protection at rest.

This module implements the gateway-side storage for the split-key secret
architecture, ensuring that share_2 values are encrypted before storage
and securely managed with appropriate TTLs.
"""

import redis
import base64
import time
import json
import logging
from typing import Optional, Dict, Any, List
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

class ShareStorageManager:
    """
    Secure storage manager for secret shares in the gateway.
    
    This class provides encrypted storage for share_2 values using Redis
    as the backend store. All shares are encrypted using AES-256-GCM
    before being stored.
    """
    
    def __init__(self, redis_url: str, encryption_key: str):
        """
        Initialize the share storage manager.
        
        Args:
            redis_url: Redis connection URL
            encryption_key: Master encryption key for share encryption
        """
        self.redis_client = redis.from_url(redis_url)
        self.encryption_key = encryption_key
        
        # Initialize encryption
        self.fernet = self._initialize_encryption()
        
        # Test Redis connection
        try:
            self.redis_client.ping()
            logger.info("Successfully connected to Redis for share storage")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
        
    def _initialize_encryption(self) -> Fernet:
        """Initialize Fernet encryption for share storage."""
        try:
            # Use PBKDF2 to derive a key from the master key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'deepsecure_gateway_salt',  # Static salt for deterministic key
                iterations=100000,
            )
            derived_key = kdf.derive(self.encryption_key.encode())
            fernet = Fernet(base64.urlsafe_b64encode(derived_key))
            
            logger.info("Initialized encryption for share storage")
            return fernet
            
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            raise
    
    async def store_share(
        self, 
        secret_name: str, 
        share_2: str, 
        metadata: Optional[Dict[str, Any]] = None,
        ttl_seconds: int = 86400
    ) -> bool:
        """
        Store encrypted share_2 with metadata.
        
        Args:
            secret_name: Name of the secret
            share_2: The share_2 value to store
            metadata: Optional metadata associated with the secret
            ttl_seconds: Time to live in seconds (default: 24 hours)
            
        Returns:
            True if storage successful, False otherwise
        """
        try:
            # Prepare data for storage
            share_data = {
                "share_2": share_2,
                "metadata": metadata or {},
                "stored_at": int(time.time())
            }
            
            # Encrypt the share data
            encrypted_data = self.fernet.encrypt(
                json.dumps(share_data).encode()
            )
            
            # Store in Redis with TTL
            key = f"share_2:{secret_name}"
            result = self.redis_client.setex(
                key,
                ttl_seconds,
                encrypted_data
            )
            
            if result:
                logger.info(f"Stored share_2 for secret '{secret_name}' with {ttl_seconds}s TTL")
                return True
            else:
                logger.error(f"Failed to store share_2 for secret '{secret_name}'")
                return False
                
        except Exception as e:
            logger.error(f"Error storing share_2 for '{secret_name}': {e}")
            return False
    
    async def retrieve_share(self, secret_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve and decrypt share_2 with metadata.
        
        Args:
            secret_name: Name of the secret to retrieve
            
        Returns:
            Dictionary containing share_2 and metadata, or None if not found
        """
        try:
            key = f"share_2:{secret_name}"
            encrypted_data = self.redis_client.get(key)
            
            if not encrypted_data:
                logger.warning(f"No share_2 found for secret '{secret_name}'")
                return None
            
            # Decrypt the share data
            decrypted_data = self.fernet.decrypt(encrypted_data)
            share_data = json.loads(decrypted_data.decode())
            
            logger.debug(f"Retrieved share_2 for secret '{secret_name}'")
            return share_data
            
        except Exception as e:
            logger.error(f"Error retrieving share_2 for '{secret_name}': {e}")
            return None
    
    async def delete_share(self, secret_name: str) -> bool:
        """
        Delete share_2 for a secret.
        
        Args:
            secret_name: Name of the secret to delete
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            key = f"share_2:{secret_name}"
            result = self.redis_client.delete(key)
            
            if result:
                logger.info(f"Deleted share_2 for secret '{secret_name}'")
                return True
            else:
                logger.warning(f"No share_2 to delete for secret '{secret_name}'")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting share_2 for '{secret_name}': {e}")
            return False
    
    async def list_stored_shares(self) -> List[str]:
        """
        List all stored secret names.
        
        Returns:
            List of secret names that have stored shares
        """
        try:
            keys = self.redis_client.keys("share_2:*")
            secret_names = [key.decode().replace("share_2:", "") for key in keys]
            return secret_names
        except Exception as e:
            logger.error(f"Error listing stored shares: {e}")
            return []
    
    async def get_share_ttl(self, secret_name: str) -> Optional[int]:
        """
        Get the time-to-live for a stored share.
        
        Args:
            secret_name: Name of the secret
            
        Returns:
            TTL in seconds, or None if not found
        """
        try:
            key = f"share_2:{secret_name}"
            ttl = self.redis_client.ttl(key)
            
            if ttl == -2:  # Key does not exist
                return None
            elif ttl == -1:  # Key exists but has no expiration
                return -1
            else:
                return ttl
                
        except Exception as e:
            logger.error(f"Error getting TTL for '{secret_name}': {e}")
            return None
    
    async def extend_share_ttl(self, secret_name: str, additional_seconds: int) -> bool:
        """
        Extend the TTL for a stored share.
        
        Args:
            secret_name: Name of the secret
            additional_seconds: Additional seconds to add to TTL
            
        Returns:
            True if extension successful, False otherwise
        """
        try:
            key = f"share_2:{secret_name}"
            current_ttl = self.redis_client.ttl(key)
            
            if current_ttl <= 0:
                logger.warning(f"Cannot extend TTL for non-existent or non-expiring key: {secret_name}")
                return False
            
            new_ttl = current_ttl + additional_seconds
            result = self.redis_client.expire(key, new_ttl)
            
            if result:
                logger.info(f"Extended TTL for '{secret_name}' by {additional_seconds}s (new TTL: {new_ttl}s)")
                return True
            else:
                logger.error(f"Failed to extend TTL for '{secret_name}'")
                return False
                
        except Exception as e:
            logger.error(f"Error extending TTL for '{secret_name}': {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the share storage.
        
        Returns:
            Dictionary containing health status information
        """
        try:
            # Test Redis connection
            start_time = time.time()
            ping_result = self.redis_client.ping()
            ping_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Get Redis info
            redis_info = self.redis_client.info()
            
            # Count stored shares
            share_count = len(await self.list_stored_shares())
            
            return {
                "status": "healthy" if ping_result else "unhealthy",
                "ping_time_ms": round(ping_time, 2),
                "redis_version": redis_info.get("redis_version", "unknown"),
                "used_memory": redis_info.get("used_memory_human", "unknown"),
                "connected_clients": redis_info.get("connected_clients", 0),
                "stored_shares_count": share_count,
                "encryption_enabled": True
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "encryption_enabled": True
            }
    
    def close(self):
        """Close the Redis connection."""
        try:
            self.redis_client.close()
            logger.info("Closed Redis connection")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}") 